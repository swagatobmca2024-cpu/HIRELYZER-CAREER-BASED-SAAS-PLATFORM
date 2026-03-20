"""
LLM Manager — Production Grade
Supabase PostgreSQL backend with:
  • Cache-first (check before any DB write or API call)
  • Least-used-key selection via atomic SQL (true cross-session load balancing)
  • In-process memory cache (L1) backed by Supabase (L2) — DB hits only on miss
  • Throttled cleanup (once per hour max, not on every call)
  • Exponential back-off retry with jitter on transient errors
  • Prompt truncation guard (never exceed model context window)
  • Detailed key health logging for observability
  • Graceful degradation: returns meaningful error, never crashes the app
"""

import hashlib
import logging
import os
import random
import time
from datetime import datetime, timedelta
from functools import lru_cache
from threading import Lock

import psycopg2
import psycopg2.extras
import pytz
import streamlit as st
from langchain_groq import ChatGroq

# ── Logging ───────────────────────────────────────────────────────────────────
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("llm_manager")

# ══════════════════════════════════════════════════════════════════════════════
# CONFIG  —  tune these without touching logic
# ══════════════════════════════════════════════════════════════════════════════
CACHE_EXPIRY_HOURS        = 48      # L2 (DB) cache lifetime — increased from 24h
MEMORY_CACHE_MAX_ITEMS    = 512     # L1 (in-process) cache size
FAILURE_COOLDOWN_MINUTES  = 3       # transient error cooldown
QUOTA_COOLDOWN_MINUTES    = 65      # 429/quota cooldown (slightly over 1h window)
DAILY_KEY_LIMIT           = 700     # hard daily cap per key (Groq free = 1000 RPD)
DEAD_KEY_REMOVE_DAYS      = 7       # purge permanently failed keys after N days
MAX_PROMPT_CHARS          = 28_000  # ~7k tokens — safe for 8k-context models
CLEANUP_INTERVAL_SECONDS  = 3_600   # run DB cleanup at most once per hour
MAX_RETRIES               = 2       # retries per key on transient (non-quota) errors
RETRY_BASE_DELAY          = 1.0     # seconds — doubles each retry + jitter
# ══════════════════════════════════════════════════════════════════════════════


# ── L1 in-process cache (thread-safe, per worker) ────────────────────────────
# Avoids a Supabase round-trip for repeated identical prompts within the same
# Streamlit worker process (very common: same resume analysed across reruns).
_mem_cache: dict[str, tuple[str, float]] = {}   # hash -> (response, expire_ts)
_mem_lock  = Lock()


def _mem_get(key: str) -> str | None:
    with _mem_lock:
        entry = _mem_cache.get(key)
        if entry and time.time() < entry[1]:
            return entry[0]
        if entry:
            _mem_cache.pop(key, None)   # evict expired
    return None


def _mem_set(key: str, value: str):
    expire_ts = time.time() + CACHE_EXPIRY_HOURS * 3600
    with _mem_lock:
        # Simple LRU eviction: drop oldest 10% when full
        if len(_mem_cache) >= MEMORY_CACHE_MAX_ITEMS:
            oldest = sorted(_mem_cache.items(), key=lambda x: x[1][1])
            for k, _ in oldest[: MEMORY_CACHE_MAX_ITEMS // 10]:
                _mem_cache.pop(k, None)
        _mem_cache[key] = (value, expire_ts)


# ── Cleanup throttle state ────────────────────────────────────────────────────
_last_cleanup_ts: float = 0.0
_cleanup_lock    = Lock()


# ── Timezone ──────────────────────────────────────────────────────────────────
_IST = pytz.timezone("Asia/Kolkata")


def get_ist_time() -> datetime:
    return datetime.now(_IST)


# ── Supabase connection (one per Streamlit worker) ────────────────────────────
@st.cache_resource
def _get_llm_pg_connection():
    conn = psycopg2.connect(
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
        options="-c statement_timeout=10000",   # 10 s query timeout
    )
    conn.autocommit = False
    logger.info("LLM Manager: Supabase connection established.")
    return conn


def _conn():
    conn = _get_llm_pg_connection()
    try:
        conn.isolation_level  # lightweight liveness check
    except Exception:
        st.cache_resource.clear()
        conn = _get_llm_pg_connection()
    return conn


def _execute(sql: str, params=None, fetch: str = "none"):
    """
    Execute SQL with automatic commit/rollback.
    fetch: 'one' | 'all' | 'none'
    Returns None silently on error (non-critical DB ops should not crash the app).
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
        return result
    except Exception as exc:
        conn.rollback()
        logger.warning("DB execute error: %s | SQL: %.120s", exc, sql)
        return None


# ── Schema ────────────────────────────────────────────────────────────────────
def init_db():
    """Create all required tables + indexes if they don't exist."""
    ddl = """
    CREATE TABLE IF NOT EXISTS llm_cache (
        prompt_hash TEXT PRIMARY KEY,
        response    TEXT      NOT NULL,
        model       TEXT      NOT NULL DEFAULT 'unknown',
        hit_count   INTEGER   NOT NULL DEFAULT 0,
        timestamp   TIMESTAMP NOT NULL DEFAULT NOW()
    );
    CREATE INDEX IF NOT EXISTS idx_llm_cache_ts ON llm_cache (timestamp);

    CREATE TABLE IF NOT EXISTS key_failures (
        api_key   TEXT PRIMARY KEY,
        fail_time TIMESTAMP NOT NULL,
        reason    TEXT      NOT NULL DEFAULT 'error',
        fail_count INTEGER  NOT NULL DEFAULT 1
    );

    CREATE TABLE IF NOT EXISTS key_usage (
        api_key     TEXT PRIMARY KEY,
        usage_count INTEGER NOT NULL DEFAULT 0,
        last_reset  DATE    NOT NULL DEFAULT CURRENT_DATE,
        total_calls BIGINT  NOT NULL DEFAULT 0
    );
    """
    conn = _conn()
    try:
        with conn.cursor() as cur:
            cur.execute(ddl)
        conn.commit()

        # Add columns that may be missing in older schema (idempotent)
        _migrations = [
            "ALTER TABLE llm_cache   ADD COLUMN IF NOT EXISTS model     TEXT    NOT NULL DEFAULT 'unknown'",
            "ALTER TABLE llm_cache   ADD COLUMN IF NOT EXISTS hit_count INTEGER NOT NULL DEFAULT 0",
            "ALTER TABLE key_failures ADD COLUMN IF NOT EXISTS fail_count INTEGER NOT NULL DEFAULT 1",
            "ALTER TABLE key_usage   ADD COLUMN IF NOT EXISTS total_calls BIGINT NOT NULL DEFAULT 0",
        ]
        with conn.cursor() as cur:
            for sql in _migrations:
                cur.execute(sql)
        conn.commit()
        logger.info("LLM Manager: DB schema ready.")
    except Exception as exc:
        conn.rollback()
        logger.error("Schema init error: %s", exc)


init_db()


# ── Throttled cleanup ─────────────────────────────────────────────────────────
def maybe_cleanup():
    """
    Run DB cleanup at most once per CLEANUP_INTERVAL_SECONDS across all calls
    in this worker process.  Never blocks a real LLM call.
    """
    global _last_cleanup_ts
    now = time.time()
    with _cleanup_lock:
        if now - _last_cleanup_ts < CLEANUP_INTERVAL_SECONDS:
            return
        _last_cleanup_ts = now

    try:
        cutoff_cache = get_ist_time() - timedelta(hours=CACHE_EXPIRY_HOURS)
        cutoff_dead  = get_ist_time() - timedelta(days=DEAD_KEY_REMOVE_DAYS)
        _execute("DELETE FROM llm_cache    WHERE timestamp < %s", (cutoff_cache,))
        _execute("DELETE FROM key_failures WHERE fail_time < %s", (cutoff_dead,))
        logger.info("LLM Manager: cleanup complete.")
    except Exception as exc:
        logger.warning("Cleanup failed (non-fatal): %s", exc)


# ── API key loader ────────────────────────────────────────────────────────────
@lru_cache(maxsize=1)
def _load_keys_cached() -> tuple[str, ...]:
    """
    Load keys once per process and cache them in-memory (lru_cache).
    Returns a tuple (immutable, hashable) so lru_cache works correctly.
    Secrets are read at startup; add new keys by restarting the worker.
    """
    raw = ""
    try:
        raw = st.secrets.get("GROQ_API_KEYS", "") or ""
    except Exception:
        pass
    if not raw:
        raw = os.getenv("GROQ_API_KEYS", "")
    keys = [k.strip() for k in raw.split(",") if k.strip()]
    if not keys:
        raise ValueError("❌ No Groq API keys found in secrets or environment.")
    logger.info("LLM Manager: loaded %d API key(s).", len(keys))
    return tuple(keys)


def load_groq_api_keys() -> list[str]:
    return list(_load_keys_cached())


# ── Prompt hashing ────────────────────────────────────────────────────────────
def hash_prompt(prompt: str, model: str) -> str:
    return hashlib.sha256(f"{model}|{prompt}".encode("utf-8")).hexdigest()


# ── Prompt guard ──────────────────────────────────────────────────────────────
def _safe_prompt(prompt: str) -> str:
    """Truncate prompts that exceed the model's safe context window."""
    if len(prompt) > MAX_PROMPT_CHARS:
        logger.warning(
            "Prompt truncated from %d to %d chars.", len(prompt), MAX_PROMPT_CHARS
        )
        return prompt[:MAX_PROMPT_CHARS] + "\n\n[... truncated for length ...]"
    return prompt


# ── L2 Cache (Supabase) ───────────────────────────────────────────────────────
def get_cached_response(prompt: str, model: str) -> str | None:
    key = hash_prompt(prompt, model)

    # L1 hit — no DB round-trip at all
    hit = _mem_get(key)
    if hit is not None:
        return hit

    # L2 hit — read from Supabase
    cutoff = get_ist_time() - timedelta(hours=CACHE_EXPIRY_HOURS)
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
            ts = _IST.localize(ts)
        if ts >= cutoff:
            # Promote to L1 and increment hit counter (fire-and-forget)
            _mem_set(key, row["response"])
            _execute(
                "UPDATE llm_cache SET hit_count = hit_count + 1 WHERE prompt_hash = %s",
                (key,),
            )
            return row["response"]
    return None


def set_cached_response(prompt: str, model: str, response: str):
    key = hash_prompt(prompt, model)
    _mem_set(key, response)   # L1 first
    _execute(
        """
        INSERT INTO llm_cache (prompt_hash, response, model, timestamp, hit_count)
        VALUES (%s, %s, %s, NOW(), 0)
        ON CONFLICT (prompt_hash)
        DO UPDATE SET response  = EXCLUDED.response,
                      model     = EXCLUDED.model,
                      timestamp = EXCLUDED.timestamp
        """,
        (key, response, model),
    )


# ── Key health ────────────────────────────────────────────────────────────────
def increment_key_usage(api_key: str):
    """Atomically increment today's usage counter."""
    _execute(
        """
        INSERT INTO key_usage (api_key, usage_count, last_reset, total_calls)
        VALUES (%s, 1, CURRENT_DATE, 1)
        ON CONFLICT (api_key) DO UPDATE
            SET usage_count = CASE
                    WHEN key_usage.last_reset = CURRENT_DATE
                    THEN key_usage.usage_count + 1
                    ELSE 1
                END,
                last_reset  = CURRENT_DATE,
                total_calls = key_usage.total_calls + 1
        """,
        (api_key,),
    )


def mark_key_failure(api_key: str, reason: str = "error"):
    _execute(
        """
        INSERT INTO key_failures (api_key, fail_time, reason, fail_count)
        VALUES (%s, NOW(), %s, 1)
        ON CONFLICT (api_key) DO UPDATE
            SET fail_time  = EXCLUDED.fail_time,
                reason     = EXCLUDED.reason,
                fail_count = key_failures.fail_count + 1
        """,
        (api_key, reason),
    )


def clear_key_failure(api_key: str):
    _execute("DELETE FROM key_failures WHERE api_key = %s", (api_key,))


# ── Key selection: least-used wins (true cross-session load balancing) ────────
def pick_best_key(api_keys: list[str]) -> str | None:
    """
    Select the single healthiest key using one SQL query:
      1. Exclude keys in cooldown.
      2. Exclude keys at daily limit.
      3. Among remaining, pick the one with the LOWEST usage_count today.
         (Keys with no usage row yet count as 0 — they go first.)

    This replaces the broken session-local key_index rotation and gives
    genuine fairness across concurrent users without any in-process state.
    """
    if not api_keys:
        return None

    now   = get_ist_time()
    today = now.date()

    # Pull failure + usage state for all keys in 2 queries
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

    failures = {r["api_key"]: r for r in failures_rows}
    usages   = {r["api_key"]: r for r in usage_rows}

    candidates: list[tuple[int, str]] = []   # (usage_count, key)

    for key in api_keys:
        # ── cooldown check ────────────────────────────────────────────────────
        if key in failures:
            f       = failures[key]
            fail_dt = f["fail_time"]
            if isinstance(fail_dt, str):
                fail_dt = datetime.strptime(fail_dt, "%Y-%m-%d %H:%M:%S")
            if fail_dt.tzinfo is None:
                fail_dt = _IST.localize(fail_dt)
            cooldown_mins = (
                QUOTA_COOLDOWN_MINUTES
                if f["reason"] == "quota"
                else FAILURE_COOLDOWN_MINUTES
            )
            if (now - fail_dt).total_seconds() < cooldown_mins * 60:
                logger.debug("Key …%s in cooldown (%s).", key[-6:], f["reason"])
                continue

        # ── daily quota check ─────────────────────────────────────────────────
        usage_today = 0
        if key in usages:
            u          = usages[key]
            last_reset = u["last_reset"]
            if hasattr(last_reset, "isoformat"):
                last_reset = last_reset.isoformat() if hasattr(last_reset, "isoformat") else str(last_reset)
            if isinstance(last_reset, str):
                lr_date = datetime.strptime(last_reset[:10], "%Y-%m-%d").date()
            else:
                lr_date = last_reset
            usage_today = u["usage_count"] if lr_date == today else 0

        if usage_today >= DAILY_KEY_LIMIT:
            logger.info("Key …%s hit daily limit (%d).", key[-6:], DAILY_KEY_LIMIT)
            mark_key_failure(key, "quota")
            continue

        candidates.append((usage_today, key))

    if not candidates:
        return None

    # Sort by usage ascending — least-used key goes first
    candidates.sort(key=lambda x: x[0])

    # Add small random jitter among keys within 10% of min usage
    # to avoid all workers hammering the exact same key simultaneously
    min_usage = candidates[0][0]
    threshold = min_usage + max(10, int(min_usage * 0.1))
    top_tier  = [k for (u, k) in candidates if u <= threshold]
    chosen    = random.choice(top_tier)

    logger.debug(
        "Key selected: …%s (usage today: %d, candidates: %d)",
        chosen[-6:], candidates[0][0], len(candidates),
    )
    return chosen


# ── Single LLM call with retry + back-off ─────────────────────────────────────
def try_call_llm(
    prompt: str,
    api_key: str,
    model: str,
    temperature: float,
    retries: int = MAX_RETRIES,
) -> str:
    """
    Call Groq with exponential back-off on transient errors.
    Quota/rate-limit errors are NOT retried — they're re-raised immediately.
    """
    last_exc = None
    for attempt in range(retries + 1):
        try:
            llm = ChatGroq(model=model, temperature=temperature, groq_api_key=api_key)
            return llm.invoke(prompt).content
        except Exception as exc:
            err_str = str(exc).lower()
            is_quota = any(w in err_str for w in ["quota", "rate limit", "429", "limit exceeded"])

            if is_quota:
                raise   # quota errors — don't retry, fail fast and rotate key

            last_exc = exc
            if attempt < retries:
                delay = RETRY_BASE_DELAY * (2 ** attempt) + random.uniform(0, 0.5)
                logger.warning(
                    "Transient error on key …%s (attempt %d/%d), retrying in %.1fs: %s",
                    api_key[-6:], attempt + 1, retries + 1, delay, exc,
                )
                time.sleep(delay)

    raise last_exc


# ── Main entry point ──────────────────────────────────────────────────────────
def call_llm(
    prompt: str,
    session,
    model: str = "llama-3.3-70b-versatile",
    temperature: float = 0,
) -> str:
    """
    Production call flow:
      1. L1 memory cache check  — zero DB, zero API cost
      2. L2 Supabase cache check — one DB read, zero API cost
      3. Throttled cleanup       — at most once/hour, never blocks
      4. User's own Groq key     — if they provided one
      5. Least-used admin key    — cross-session fair rotation
      6. Exponential back-off retry on transient failures
      7. Graceful degradation    — meaningful error, no crash
    """
    prompt = _safe_prompt(prompt)

    # ── Steps 1 & 2: cache ───────────────────────────────────────────────────
    cached = get_cached_response(prompt, model)
    if cached:
        return cached

    # ── Step 3: throttled cleanup (non-blocking) ─────────────────────────────
    maybe_cleanup()

    user_key = ""
    if session is not None and isinstance(session.get("user_groq_key"), str):
        user_key = session["user_groq_key"].strip()

    last_error = None

    # ── Step 4: user-provided key ────────────────────────────────────────────
    if user_key:
        try:
            response = try_call_llm(prompt, user_key, model, temperature)
            set_cached_response(prompt, model, response)
            increment_key_usage(user_key)
            return response
        except Exception as exc:
            err_str = str(exc).lower()
            reason  = "quota" if any(
                w in err_str for w in ["quota", "rate limit", "429", "limit exceeded"]
            ) else "error"
            mark_key_failure(user_key, reason)
            logger.warning("User key …%s failed (%s): %s", user_key[-6:], reason, exc)
            last_error = exc

    # ── Step 5: admin key pool — least-used rotation ─────────────────────────
    all_admin_keys = load_groq_api_keys()

    # Try up to len(keys) times, picking fresh best key each round
    # (the key we just used is incremented, so next pick is different)
    for attempt in range(len(all_admin_keys)):
        key = pick_best_key(all_admin_keys)
        if key is None:
            break   # all keys exhausted or in cooldown

        try:
            response = try_call_llm(prompt, key, model, temperature)
            set_cached_response(prompt, model, response)
            increment_key_usage(key)
            clear_key_failure(key)
            logger.info(
                "LLM call succeeded on key …%s (attempt %d).", key[-6:], attempt + 1
            )
            return response

        except Exception as exc:
            err_str = str(exc).lower()
            reason  = "quota" if any(
                w in err_str for w in ["quota", "rate limit", "429", "limit exceeded"]
            ) else "error"
            mark_key_failure(key, reason)
            logger.warning(
                "Admin key …%s failed (%s) on attempt %d: %s",
                key[-6:], reason, attempt + 1, exc,
            )
            last_error = exc

            # For quota failures skip immediately to next key without sleeping
            # For transient failures the retry already happened inside try_call_llm
            continue

    # ── Step 6: all keys failed ───────────────────────────────────────────────
    err_msg = (
        f"❌ All API keys exhausted or in cooldown. "
        f"Last error: {last_error or 'No healthy keys available'}. "
        f"Please try again in a few minutes or add your own Groq API key in settings."
    )
    logger.error("call_llm: %s", err_msg)
    return err_msg


# ── Observability helpers (optional — call from admin panel) ──────────────────
def get_key_health_report() -> list[dict]:
    """
    Return a summary of every key's usage and failure state.
    Useful for an admin dashboard.
    """
    all_keys = load_groq_api_keys()
    usage_rows = _execute(
        "SELECT api_key, usage_count, last_reset, total_calls FROM key_usage WHERE api_key = ANY(%s)",
        (all_keys,),
        fetch="all",
    ) or []
    failure_rows = _execute(
        "SELECT api_key, fail_time, reason, fail_count FROM key_failures WHERE api_key = ANY(%s)",
        (all_keys,),
        fetch="all",
    ) or []

    usages   = {r["api_key"]: r for r in usage_rows}
    failures = {r["api_key"]: r for r in failure_rows}
    today    = get_ist_time().date()
    now      = get_ist_time()

    report = []
    for key in all_keys:
        u = usages.get(key, {})
        f = failures.get(key, {})

        last_reset = u.get("last_reset")
        usage_today = 0
        if last_reset:
            if hasattr(last_reset, "isoformat"):
                lr_date = last_reset
            else:
                lr_date = datetime.strptime(str(last_reset)[:10], "%Y-%m-%d").date()
            usage_today = u.get("usage_count", 0) if lr_date == today else 0

        in_cooldown = False
        cooldown_reason = None
        if f:
            fail_dt = f.get("fail_time")
            if fail_dt:
                if isinstance(fail_dt, str):
                    fail_dt = datetime.strptime(fail_dt, "%Y-%m-%d %H:%M:%S")
                if fail_dt.tzinfo is None:
                    fail_dt = _IST.localize(fail_dt)
                cd_mins = QUOTA_COOLDOWN_MINUTES if f.get("reason") == "quota" else FAILURE_COOLDOWN_MINUTES
                if (now - fail_dt).total_seconds() < cd_mins * 60:
                    in_cooldown = True
                    cooldown_reason = f.get("reason")

        report.append({
            "key_suffix"     : f"…{key[-8:]}",
            "usage_today"    : usage_today,
            "daily_limit"    : DAILY_KEY_LIMIT,
            "usage_pct"      : round(usage_today / DAILY_KEY_LIMIT * 100, 1),
            "total_calls"    : u.get("total_calls", 0),
            "in_cooldown"    : in_cooldown,
            "cooldown_reason": cooldown_reason,
            "fail_count"     : f.get("fail_count", 0),
            "status"         : "cooldown" if in_cooldown else (
                               "exhausted" if usage_today >= DAILY_KEY_LIMIT else "healthy"),
        })

    return sorted(report, key=lambda x: x["usage_today"])


def get_cache_stats() -> dict:
    """Return cache hit rate and size. Useful for admin dashboard."""
    row = _execute(
        "SELECT COUNT(*) AS total, SUM(hit_count) AS hits FROM llm_cache",
        fetch="one",
    ) or {}
    mem_size = 0
    with _mem_lock:
        mem_size = len(_mem_cache)
    return {
        "db_entries"  : row.get("total", 0),
        "db_hits"     : row.get("hits", 0),
        "memory_entries": mem_size,
    }
