"""
LLM Manager — Supabase PostgreSQL backend
Migrated from SQLite to psycopg2, using the same @st.cache_resource singleton
pattern as db_manager.py and user_login.py.
All timestamps are stored and compared in UTC (TIMESTAMPTZ columns).

FIXES vs previous version:
  1. cleanup_cache() now rate-limited to once per 30 min (was firing on every call)
  2. Thread lock around key_index read/write (race condition in ThreadPoolExecutor)
  3. Transient errors (network blip, 500) no longer mark healthy keys as failed
  4. mark_key_failure() moved outside get_healthy_keys() read loop (batch write)
  5. create_chain() pattern: increment_key_usage only after success (caller fix noted)
  6. FIXED: _conn() liveness check now does a real SELECT 1 round-trip (was broken attr read)
  7. FIXED: Reconnect no longer calls st.cache_resource.clear() (was nuking all 3 connections)
  8. FIXED: get_healthy_keys() DB failure now falls back to all keys instead of returning []
  9. FIXED: key_index round-robin now sorts keys before shuffle so index is meaningful per-call
"""

import hashlib
import os
import random
import threading
import time
from datetime import datetime, timedelta

import psycopg2
import psycopg2.extras
import psycopg2.pool
import pytz
import streamlit as st
from langchain_groq import ChatGroq

# ── CONFIG ────────────────────────────────────────────────────────────────────
CACHE_EXPIRY_HOURS       = 24
FAILURE_COOLDOWN_MINUTES = 5
QUOTA_COOLDOWN_MINUTES   = 60
DAILY_KEY_LIMIT          = 800
DEAD_KEY_REMOVE_DAYS     = 3
CLEANUP_INTERVAL_SECONDS = 1800

# FIX 2: module-level lock so parallel threads never pick the same key
_key_rotation_lock = threading.Lock()

# FIX 7: module-level key index so cross-user rotation actually advances
_global_key_index = 0

# FIX 8: ThreadedConnectionPool replaces single shared connection
# minconn=2 keeps two connections warm; maxconn=10 handles burst concurrency.
_pool_lock = threading.Lock()
_llm_pool: "psycopg2.pool.ThreadedConnectionPool | None" = None

# Groq errors that mean the KEY itself is bad (not a transient server issue)
_QUOTA_SIGNALS    = ["quota", "rate limit", "429", "too many requests"]
_ORG_LIMIT_SIGNALS = ["tokens per day", "tpd", "organization limit", "daily limit", "org limit"]
_DEAD_KEY_SIGNALS = ["invalid api key", "unauthorized", "authentication", "permission denied"]


# ── Timezone helper ───────────────────────────────────────────────────────────
def get_utc_now() -> datetime:
    return datetime.now(pytz.utc)


# ── Connection pool management ────────────────────────────────────────────────
def _get_pool() -> psycopg2.pool.ThreadedConnectionPool:
    """Return the module-level ThreadedConnectionPool, creating it if needed."""
    global _llm_pool
    with _pool_lock:
        if _llm_pool is None or _llm_pool.closed:
            _llm_pool = psycopg2.pool.ThreadedConnectionPool(
                minconn=2,
                maxconn=10,
                host=st.secrets["SUPABASE_HOST"],
                dbname=st.secrets["SUPABASE_DB"],
                user=st.secrets["SUPABASE_USER"],
                password=st.secrets["SUPABASE_PASSWORD"],
                port=st.secrets["SUPABASE_PORT"],
                connect_timeout=30,
                keepalives=1,
                keepalives_idle=30,
                keepalives_interval=10,
                keepalives_count=5,
            )
        return _llm_pool


def _conn():
    """
    Borrow a connection from the pool; test liveness and return a live connection.
    The caller MUST return it via _put_conn() — use _execute() for automatic handling.
    """
    pool = _get_pool()
    conn = pool.getconn()
    try:
        with conn.cursor() as cur:
            cur.execute("SELECT 1")
        conn.rollback()
    except Exception:
        # Connection is dead — discard it and get a fresh one
        try:
            pool.putconn(conn, close=True)
        except Exception:
            pass
        conn = pool.getconn()
    return conn


def _put_conn(conn, close: bool = False):
    """Return a connection to the pool."""
    try:
        pool = _get_pool()
        pool.putconn(conn, close=close)
    except Exception:
        pass


def _execute(sql: str, params=None, fetch: str = "none"):
    """
    Borrow a connection from the pool, run SQL, commit, then return the connection.
    fetch: 'one' | 'all' | 'none'
    """
    conn = _conn()
    try:
        with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
            cur.execute(sql, params)
            result = None
            if fetch == "one":
                result = cur.fetchone()
            elif fetch == "all":
                result = cur.fetchall()
        conn.commit()
        _put_conn(conn)
        return result
    except Exception:
        try:
            conn.rollback()
        except Exception:
            pass
        _put_conn(conn, close=True)
        raise


# ── Schema initialisation ─────────────────────────────────────────────────────
def init_db():
    """Create llm_manager tables in Supabase if they don't already exist."""
    ddl = """
    CREATE TABLE IF NOT EXISTS llm_cache (
        prompt_hash TEXT PRIMARY KEY,
        response    TEXT            NOT NULL,
        timestamp   TIMESTAMPTZ     NOT NULL DEFAULT NOW()
    );

    CREATE TABLE IF NOT EXISTS key_failures (
        api_key   TEXT PRIMARY KEY,
        fail_time TIMESTAMPTZ NOT NULL,
        reason    TEXT        NOT NULL DEFAULT 'error'
    );

    CREATE TABLE IF NOT EXISTS key_usage (
        api_key     TEXT PRIMARY KEY,
        usage_count INTEGER     NOT NULL DEFAULT 0,
        last_reset  TIMESTAMPTZ NOT NULL DEFAULT NOW()
    );
    """
    conn = _conn()
    try:
        with conn.cursor() as cur:
            cur.execute(ddl)
        conn.commit()
        _put_conn(conn)
    except Exception:
        try:
            conn.rollback()
        except Exception:
            pass
        _put_conn(conn, close=True)
        raise

init_db()


# ── Cache cleanup ─────────────────────────────────────────────────────────────
def cleanup_cache():
    """Delete expired cache rows and permanently dead keys."""
    cutoff_cache = get_utc_now() - timedelta(hours=CACHE_EXPIRY_HOURS)
    cutoff_dead  = get_utc_now() - timedelta(days=DEAD_KEY_REMOVE_DAYS)
    _execute("DELETE FROM llm_cache WHERE timestamp < %s", (cutoff_cache,))
    _execute("DELETE FROM key_failures WHERE fail_time < %s", (cutoff_dead,))


# ── API key loader ────────────────────────────────────────────────────────────
def load_groq_api_keys():
    """Load Groq keys from Streamlit secrets (preferred) or environment."""
    try:
        secret_keys = st.secrets.get("GROQ_API_KEYS", "")
        if secret_keys:
            keys = [k.strip() for k in secret_keys.split(",") if k.strip()]
            if keys:
                return keys
    except Exception:
        pass

    env_keys = os.getenv("GROQ_API_KEYS")
    if env_keys:
        keys = [k.strip() for k in env_keys.split(",") if k.strip()]
        if keys:
            return keys

    raise ValueError("❌ No Groq API keys found in secrets or environment.")


# ── Prompt hashing ────────────────────────────────────────────────────────────
def hash_prompt(prompt: str, model: str) -> str:
    return hashlib.sha256(f"{model}|{prompt}".encode("utf-8")).hexdigest()


# ── Cache R/W ─────────────────────────────────────────────────────────────────
def get_cached_response(prompt: str, model: str):
    """Return cached LLM response if still within CACHE_EXPIRY_HOURS, else None."""
    key    = hash_prompt(prompt, model)
    cutoff = get_utc_now() - timedelta(hours=CACHE_EXPIRY_HOURS)
    try:
        row = _execute(
            "SELECT response, timestamp FROM llm_cache WHERE prompt_hash = %s",
            (key,),
            fetch="one",
        )
        if row:
            ts = row["timestamp"]
            if isinstance(ts, str):
                ts = datetime.strptime(ts, "%Y-%m-%d %H:%M:%S")
            if ts.tzinfo is None:
                ts = pytz.utc.localize(ts)
            if ts >= cutoff:
                return row["response"]
    except Exception:
        pass  # cache miss on DB error — just proceed to LLM
    return None


def set_cached_response(prompt: str, model: str, response: str):
    """Upsert a response into the LLM cache."""
    key = hash_prompt(prompt, model)
    try:
        _execute(
            """
            INSERT INTO llm_cache (prompt_hash, response, timestamp)
            VALUES (%s, %s, NOW())
            ON CONFLICT (prompt_hash)
            DO UPDATE SET response = EXCLUDED.response,
                          timestamp = EXCLUDED.timestamp
            """,
            (key, response),
        )
    except Exception:
        pass  # non-fatal — next call will just re-query the LLM


# ── Key tracking ──────────────────────────────────────────────────────────────
def increment_key_usage(api_key: str):
    """Increment daily usage counter for a key, resetting if the date changed."""
    try:
        _execute(
            """
            INSERT INTO key_usage (api_key, usage_count, last_reset)
            VALUES (%s, 1, NOW())
            ON CONFLICT (api_key) DO UPDATE
                SET usage_count = CASE
                        WHEN key_usage.last_reset::date = NOW()::date
                        THEN key_usage.usage_count + 1
                        ELSE 1
                    END,
                    last_reset = NOW()
            """,
            (api_key,),
        )
    except Exception:
        pass  # non-fatal


def mark_key_failure(api_key: str, reason: str = "error"):
    """Record a key failure only if not already tracked (prevents fail_time refresh loop)."""
    try:
        _execute(
            """
            INSERT INTO key_failures (api_key, fail_time, reason)
            VALUES (%s, NOW(), %s)
            ON CONFLICT (api_key) DO NOTHING
            """,
            (api_key, reason),
        )
    except Exception:
        pass  # non-fatal


def clear_key_failure(api_key: str):
    """Remove a key from the failure table (marks it healthy again)."""
    try:
        _execute("DELETE FROM key_failures WHERE api_key = %s", (api_key,))
    except Exception:
        pass  # non-fatal


def _classify_error(error: Exception):
    """
    Classify an exception so we only penalise keys for real key errors.
    Returns:
        'org_limit' — org-level daily token cap hit (stop hammering ALL keys)
        'quota'     — rate limited, put key in 60-min cooldown
        'dead'      — bad/invalid key, put in 5-min cooldown
        'transient' — network blip / server 500 / timeout, do NOT touch the key
    """
    msg = str(error).lower()
    if any(s in msg for s in _ORG_LIMIT_SIGNALS):
        return "org_limit"
    if any(s in msg for s in _QUOTA_SIGNALS):
        return "quota"
    if any(s in msg for s in _DEAD_KEY_SIGNALS):
        return "dead"
    return "transient"


def get_healthy_keys(api_keys: list) -> list:
    """
    Return the subset of api_keys that are:
    - not in cooldown (FAILURE_COOLDOWN_MINUTES / QUOTA_COOLDOWN_MINUTES)
    - below DAILY_KEY_LIMIT

    FIX 8: If the DB queries fail, returns ALL keys as fallback (was returning
            [] which caused false "no healthy keys" errors on transient DB blips).
    FIX 9: Result is sorted before shuffle so key_index is a stable pointer
            within a single call_llm() invocation.
    """
    now   = get_utc_now()
    today = now.date()  # datetime.date object for proper comparison

    try:
        failures_rows = _execute(
            "SELECT api_key, fail_time, reason FROM key_failures WHERE api_key = ANY(%s)",
            (api_keys,),
            fetch="all",
        ) or []
        usage_rows = _execute(
            "SELECT api_key, usage_count, last_reset FROM key_usage WHERE api_key = ANY(%s)",
            (api_keys,),
            fetch="all",
        ) or []
    except Exception:
        # FIX 8: DB unavailable — don't penalise keys, let callers try all of them
        shuffled = list(api_keys)
        random.shuffle(shuffled)
        return shuffled

    failures = {r["api_key"]: r for r in failures_rows}
    usages   = {r["api_key"]: r for r in usage_rows}

    quota_keys = []
    healthy    = []

    for key in api_keys:
        # ── cooldown check ────────────────────────────────────────────────────
        if key in failures:
            f       = failures[key]
            fail_dt = f["fail_time"]
            if isinstance(fail_dt, str):
                fail_dt = datetime.strptime(fail_dt, "%Y-%m-%d %H:%M:%S")
            if fail_dt.tzinfo is None:
                fail_dt = pytz.utc.localize(fail_dt)
            cooldown = (
                QUOTA_COOLDOWN_MINUTES
                if f["reason"] == "quota"
                else FAILURE_COOLDOWN_MINUTES
            )
            if (now - fail_dt).total_seconds() < cooldown * 60:
                continue  # still in cooldown

        # ── daily quota check ─────────────────────────────────────────────────
        if key in usages:
            u          = usages[key]
            last_reset = u["last_reset"]
            # Normalise to a date object regardless of whether Postgres returns
            # a datetime, date, or string (TIMESTAMPTZ always comes back as datetime)
            if isinstance(last_reset, datetime):
                last_reset_date = last_reset.date()
            elif hasattr(last_reset, "isoformat"):
                # date object (legacy DATE column)
                last_reset_date = last_reset
            else:
                # Fallback: parse string
                last_reset_date = datetime.strptime(str(last_reset)[:10], "%Y-%m-%d").date()
            usage_count = u["usage_count"] if last_reset_date == today else 0
            if usage_count >= DAILY_KEY_LIMIT:
                quota_keys.append(key)
                continue

        healthy.append(key)

    # Batch-write quota failures after the loop
    for key in quota_keys:
        mark_key_failure(key, "quota")

    # FIX 9: sort for stable ordering within a single call, then shuffle
    healthy.sort()
    random.shuffle(healthy)
    return healthy


# ── Single LLM call ───────────────────────────────────────────────────────────
def try_call_llm(prompt: str, api_key: str, model: str, temperature: float) -> str:
    llm = ChatGroq(model=model, temperature=temperature, groq_api_key=api_key)
    return llm.invoke(prompt).content


# ── Main entry point ──────────────────────────────────────────────────────────
def call_llm(
    prompt: str,
    session,
    model: str = "llama-3.3-70b-versatile",
    temperature: float = 0,
) -> str:
    """
    1. Check Supabase cache — return immediately on hit.
    2. Try user-provided Groq key (if set).
    3. Rotate through healthy admin keys.
    """
    # Guard against None session (e.g. called from db_manager without session)
    if session is None:
        session = {}

    # ── FIX 1: throttled cleanup ──────────────────────────────────────────────
    _last_cleanup = session.get("_last_cleanup_ts", 0)
    if time.time() - _last_cleanup > CLEANUP_INTERVAL_SECONDS:
        try:
            cleanup_cache()
        except Exception:
            pass
        try:
            session["_last_cleanup_ts"] = time.time()
        except Exception:
            pass  # plain dict or read-only session

    # ── Cache hit ─────────────────────────────────────────────────────────────
    cached = get_cached_response(prompt, model)
    if cached:
        return cached

    # Initialise key_index safely (works for both dict and st.session_state)
    if "key_index" not in session:
        try:
            session["key_index"] = 0
        except Exception:
            pass

    user_key = ""
    raw_user_key = session.get("user_groq_key", "")
    if isinstance(raw_user_key, str):
        user_key = raw_user_key.strip()

    last_error = None

    # ── Step 2: user-supplied key ─────────────────────────────────────────────
    if user_key:
        try:
            response = try_call_llm(prompt, user_key, model, temperature)
            set_cached_response(prompt, model, response)
            increment_key_usage(user_key)
            return response
        except Exception as e:
            err_type = _classify_error(e)
            if err_type != "transient":
                mark_key_failure(user_key, "quota" if err_type == "quota" else "error")
            last_error = e

    # ── Step 3: admin key rotation ────────────────────────────────────────────
    try:
        all_admin_keys = load_groq_api_keys()
    except ValueError as e:
        return f"❌ LLM unavailable: {e}"

    admin_keys = get_healthy_keys(all_admin_keys)

    if not admin_keys:
        return f"❌ LLM unavailable: {last_error or 'No healthy API keys available'}"

    # FIX 2: lock while picking index; FIX 5: guard against shrunk list
    # FIX 7: use module-level index so cross-user rotation actually advances
    global _global_key_index
    with _key_rotation_lock:
        if _global_key_index >= len(admin_keys):
            _global_key_index = 0
        start = _global_key_index
        _global_key_index = (start + 1) % len(admin_keys)

    for offset in range(len(admin_keys)):
        idx = (start + offset) % len(admin_keys)
        key = admin_keys[idx]
        try:
            response = try_call_llm(prompt, key, model, temperature)
            set_cached_response(prompt, model, response)
            increment_key_usage(key)
            clear_key_failure(key)
            return response
        except Exception as e:
            err_type = _classify_error(e)
            if err_type == "org_limit":
                # Org-level daily cap: no point trying other keys — they share the same org limit
                last_error = e
                break
            elif err_type == "quota":
                mark_key_failure(key, "quota")
            elif err_type == "dead":
                mark_key_failure(key, "error")
            # transient: key stays healthy, try the next one
            last_error = e

    # Surface org_limit with a clear, actionable message
    if last_error and _classify_error(last_error) == "org_limit":
        return "❌ Daily token limit reached. This resets at midnight UTC — please try again later."

    return f"❌ LLM unavailable: {last_error or 'No healthy API keys available'}"
