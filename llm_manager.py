"""
LLM Manager — Supabase PostgreSQL backend
Migrated from SQLite to psycopg2, using the same @st.cache_resource singleton
pattern as db_manager.py and user_login.py.
All timestamps are stored and compared in UTC (TIMESTAMPTZ columns).

CHANGES vs v11:
  1. Global atomic key counter (_global_key_counter) replaces per-session key_index
     so all concurrent users/threads rotate across ALL 100 keys evenly.
  2. In-memory failure/cooldown cache (_mem_failures, _mem_usage) eliminates DB
     round-trips on the hot request path; Supabase writes are async/deferred.
  3. Exponential back-off with full jitter on per-key retries (no fixed sleep).
  4. Keys are pre-shuffled once at import time and re-shuffled after each full
     rotation cycle to prevent multiple workers always hitting the same key.
  5. Thread-safe in-memory usage counters mirror Supabase (flush async).
  6. _classify_error now catches httpx/groq status codes in addition to strings.
  7. get_healthy_keys() uses in-memory cache first; DB is only a fallback/refresh.
  8. call_llm() tries all healthy keys before giving up (no early exit on transient).
  9. All existing safety mechanisms (cooldown, quota, TPM, caching) are preserved.
 10. TAB_1_RESUME.py call signature unchanged — drop-in replacement.
"""

import hashlib
import itertools
import os
import random
import threading
import time
from datetime import datetime, timedelta
from typing import List, Optional

import psycopg2
import psycopg2.extras
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

# ── Per-minute token rate limiter (Groq free tier — model-specific) ──────────
# Groq's real per-key TPM ceiling differs by model:
#   openai/gpt-oss-120b     : ~8,000 TPM   (lower ceiling + hidden reasoning
#                              tokens count against it) — empirically safe ~3500
# Since keys are shared across ALL concurrent users, headroom matters more for
# the model with the smaller budget, not less.
TPM_LIMIT_DEFAULT  = 6000
TPM_LIMIT_BY_MODEL = {
    "openai/gpt-oss-120b":     6000,   # real ceiling ~8000; ~2000 token buffer for output + multi-user drift
    "openai/gpt-oss-20b":      6000,
}
TPM_WINDOW_SECONDS = 60

# ── Real per-request ceiling (separate from the shared TPM budget above) ─────
# TPM_LIMIT_BY_MODEL is deliberately conservative — it reserves headroom so ONE
# user's call doesn't starve every other concurrent user sharing the same key
# in the same 60s window. It is NOT the point at which Groq actually rejects a
# single request as too large. Using the conservative shared figure for the
# fail-fast "is this prompt physically too big" check below was wrong — it was
# rejecting valid single requests that easily fit in the model's real context
# window just because they exceeded the smaller shared-budget target.
REQUEST_CEILING_DEFAULT  = 8000
REQUEST_CEILING_BY_MODEL = {
    "openai/gpt-oss-120b":     8000,
    "openai/gpt-oss-20b":      8000,
}

def _request_ceiling_for(model: str) -> int:
    return REQUEST_CEILING_BY_MODEL.get(model, REQUEST_CEILING_DEFAULT)

# ── Token estimation (model-specific) ────────────────────────────────────────
# CHARS_PER_TOKEN is a rough heuristic, not a real tokenizer call — but the
# ratio isn't the same across model families, and it matters for how tight
# the fail-fast/TPM guard actually is:
#   openai/gpt-oss-*        : uses an o200k-based tokenizer wrapped in the
#                              Harmony chat format (system/developer/user
#                              "channels" with special role/marker tokens).
#                              Use a slightly LOWER chars/token ratio here
#                              (i.e. assume MORE tokens per char) so the
#                              estimate stays conservative rather than
#                              under-counting and risking another 413.
CHARS_PER_TOKEN_DEFAULT  = 3.6
CHARS_PER_TOKEN_BY_MODEL = {
    "openai/gpt-oss-120b":     3.6,
    "openai/gpt-oss-20b":      3.6,
}
# Fixed per-call overhead for Harmony-format structural tokens (channel tags,
# role markers, etc.) that a raw text-length estimate doesn't see at all.
HARMONY_OVERHEAD_TOKENS_BY_MODEL = {
    "openai/gpt-oss-120b": 120,
    "openai/gpt-oss-20b":  120,
}

# ── Reasoning-model config ────────────────────────────────────────────────────
# GPT-OSS models default to reasoning_effort="medium" on Groq, which burns
# hidden chain-of-thought tokens on every call (counted against TPM) even for
# tasks like structured JSON extraction that don't need deep reasoning.
# Force "low" unless a call site explicitly opts into more.
REASONING_EFFORT_BY_MODEL = {
    "openai/gpt-oss-120b": "low",
    "openai/gpt-oss-20b":  "low",
}


def _tpm_limit_for(model: str) -> int:
    return TPM_LIMIT_BY_MODEL.get(model, TPM_LIMIT_DEFAULT)

# ── Retry / back-off config ───────────────────────────────────────────────────
MAX_RETRIES_PER_KEY = 1            # attempts per key before moving on
BACKOFF_BASE        = 0.4          # seconds — full-jitter base
BACKOFF_MAX         = 8.0          # seconds — cap for a single inter-key sleep

# ── Groq error signals ────────────────────────────────────────────────────────
_QUOTA_SIGNALS    = ["quota", "rate limit", "429", "too many requests",
                     "rateLimitError", "rate_limit_exceeded"]
_DEAD_KEY_SIGNALS = ["invalid api key", "unauthorized", "401", "403",
                     "api key", "authentication", "permission denied",
                     "invalid_api_key"]
# 413s are about the request itself (too many tokens for this model's TPM/
# context ceiling) — no key will ever succeed, so don't burn through the pool.
_OVERSIZED_SIGNALS = ["413", "payload too large", "request too large",
                      "request entity too large", "content too large"]

# ─────────────────────────────────────────────────────────────────────────────
# IN-MEMORY STATE  (module-level, shared across all threads in one worker)
# ─────────────────────────────────────────────────────────────────────────────

# TPM tracker: { api_key: [(timestamp_float, token_count), ...] }
_tpm_tracker: dict = {}
_tpm_lock = threading.Lock()

# Global atomic round-robin counter — incremented on every successful key pick.
# Using itertools.count() which is C-level and GIL-safe for simple increments.
_global_key_counter = itertools.count(0)
_counter_lock = threading.Lock()
_counter_value: int = 0           # shadow value so we can read current index

# In-memory failure cache: { api_key: {"time": float, "reason": str} }
_mem_failures: dict = {}
_mem_failures_lock = threading.Lock()

# In-memory daily usage: { api_key: {"count": int, "date": str} }
_mem_usage: dict = {}
_mem_usage_lock = threading.Lock()

# Reconnect + rotation locks
_reconnect_lock      = threading.Lock()
_key_rotation_lock   = threading.Lock()

# Module-level connection holder (not via st.cache_resource to avoid cross-module clear)
_llm_conn_holder: dict = {"conn": None}

# Cached ordered key list — rebuilt whenever the underlying secrets are loaded.
# Shape: List[str], shuffled once at load time and periodically re-shuffled.
_cached_keys: List[str] = []
_cached_keys_lock = threading.Lock()
_keys_loaded_at: float = 0.0
KEY_CACHE_TTL = 3600.0   # reload from secrets at most once per hour


# ── Timezone helper ───────────────────────────────────────────────────────────
def _key_id(api_key: str) -> str:
    """
    Returns a safe DB identifier for an API key.
    Stores first 8 chars (for human identification) + SHA256 suffix.
    The raw key is NEVER written to the database — only this masked form.
    Example: gsk_1R3Y...a3f9c2d8e1b4c5d6
    """
    return api_key[:8] + "..." + hashlib.sha256(api_key.encode()).hexdigest()[:16]


def get_utc_now() -> datetime:
    return datetime.now(pytz.utc)


# ── Connection management (isolated, no global cache_resource.clear()) ────────
def _make_llm_connection():
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
    )
    conn.autocommit = False
    return conn


def _conn():
    """Return a live psycopg2 connection (real SELECT 1 liveness check)."""
    with _reconnect_lock:
        conn = _llm_conn_holder.get("conn")
        need_reconnect = False

        if conn is None:
            need_reconnect = True
        else:
            try:
                with conn.cursor() as cur:
                    cur.execute("SELECT 1")
                conn.rollback()
            except Exception:
                need_reconnect = True
                try:
                    conn.close()
                except Exception:
                    pass

        if need_reconnect:
            _llm_conn_holder["conn"] = _make_llm_connection()

        return _llm_conn_holder["conn"]


def _execute(sql: str, params=None, fetch: str = "none"):
    """
    Run SQL inside an implicit transaction.
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
        return result
    except Exception:
        try:
            conn.rollback()
        except Exception:
            pass
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
        usage_count INTEGER  NOT NULL DEFAULT 0,
        last_reset  DATE     NOT NULL DEFAULT CURRENT_DATE
    );
    """
    conn = _conn()
    try:
        with conn.cursor() as cur:
            cur.execute(ddl)
        conn.commit()
    except Exception:
        try:
            conn.rollback()
        except Exception:
            pass
        raise

init_db()


# ── Cache cleanup ─────────────────────────────────────────────────────────────
def cleanup_cache():
    """Delete expired cache rows and permanently dead keys."""
    cutoff_cache = get_utc_now() - timedelta(hours=CACHE_EXPIRY_HOURS)
    cutoff_dead  = get_utc_now() - timedelta(days=DEAD_KEY_REMOVE_DAYS)
    try:
        _execute("DELETE FROM llm_cache WHERE timestamp < %s", (cutoff_cache,))
        _execute("DELETE FROM key_failures WHERE fail_time < %s", (cutoff_dead,))
    except Exception:
        pass


# ── Per-minute token rate limiter helpers ─────────────────────────────────────
def _estimate_tokens(text: str, model: str = "") -> int:
    ratio = CHARS_PER_TOKEN_BY_MODEL.get(model, CHARS_PER_TOKEN_DEFAULT)
    overhead = HARMONY_OVERHEAD_TOKENS_BY_MODEL.get(model, 0)
    return max(1, int(len(text) / ratio)) + overhead


def _get_key_tpm(api_key: str, now: float) -> int:
    window_start = now - TPM_WINDOW_SECONDS
    entries = _tpm_tracker.get(api_key, [])
    return sum(cnt for ts, cnt in entries if ts >= window_start)


def _record_key_tokens(api_key: str, token_count: int, now: float):
    window_start = now - TPM_WINDOW_SECONDS
    with _tpm_lock:
        entries = _tpm_tracker.get(api_key, [])
        entries = [(ts, cnt) for ts, cnt in entries if ts >= window_start]
        entries.append((now, token_count))
        _tpm_tracker[api_key] = entries


def _key_has_tpm_headroom(api_key: str, estimated_tokens: int, model: str = "") -> bool:
    now = time.time()
    with _tpm_lock:
        current_tpm = _get_key_tpm(api_key, now)
    return (current_tpm + estimated_tokens) <= _tpm_limit_for(model)


def get_keys_with_tpm_headroom(api_keys: list, estimated_tokens: int, model: str = "") -> list:
    now = time.time()
    limit = _tpm_limit_for(model)
    with _tpm_lock:
        headroom = [k for k in api_keys
                    if (_get_key_tpm(k, now) + estimated_tokens) <= limit]
    return headroom if headroom else api_keys


# ── In-memory failure helpers ─────────────────────────────────────────────────
def _mem_record_failure(api_key: str, reason: str):
    with _mem_failures_lock:
        _mem_failures[api_key] = {"time": time.time(), "reason": reason}


def _mem_clear_failure(api_key: str):
    with _mem_failures_lock:
        _mem_failures.pop(api_key, None)


def _mem_is_in_cooldown(api_key: str) -> bool:
    with _mem_failures_lock:
        entry = _mem_failures.get(api_key)
    if not entry:
        return False
    cooldown_secs = (
        QUOTA_COOLDOWN_MINUTES * 60
        if entry["reason"] == "quota"
        else FAILURE_COOLDOWN_MINUTES * 60
    )
    return (time.time() - entry["time"]) < cooldown_secs


def _mem_increment_usage(api_key: str):
    today = datetime.now(pytz.utc).strftime("%Y-%m-%d")
    with _mem_usage_lock:
        rec = _mem_usage.get(api_key)
        if rec is None or rec["date"] != today:
            _mem_usage[api_key] = {"count": 1, "date": today}
        else:
            rec["count"] += 1


def _mem_usage_over_limit(api_key: str) -> bool:
    today = datetime.now(pytz.utc).strftime("%Y-%m-%d")
    with _mem_usage_lock:
        rec = _mem_usage.get(api_key)
    if rec is None:
        return False
    return rec["date"] == today and rec["count"] >= DAILY_KEY_LIMIT


# ── Background Supabase flush (fire-and-forget threads) ──────────────────────
def _async_mark_failure(api_key: str, reason: str):
    """Write failure to Supabase in a background thread."""
    def _write():
        try:
            mark_key_failure(api_key, reason)
        except Exception:
            pass
    threading.Thread(target=_write, daemon=True).start()


def _async_increment_usage(api_key: str):
    """Write usage increment to Supabase in a background thread."""
    def _write():
        try:
            increment_key_usage(api_key)
        except Exception:
            pass
    threading.Thread(target=_write, daemon=True).start()


def _async_clear_failure(api_key: str):
    """Clear failure from Supabase in a background thread."""
    def _write():
        try:
            clear_key_failure(api_key)
        except Exception:
            pass
    threading.Thread(target=_write, daemon=True).start()


# ── API key loader ────────────────────────────────────────────────────────────
def load_groq_api_keys() -> List[str]:
    """
    Load Groq keys from Streamlit secrets (preferred) or environment.
    Keys are cached in memory for KEY_CACHE_TTL seconds to avoid repeated
    secret reads. The list is shuffled once on load so that the starting
    position is randomised across worker restarts.
    """
    global _cached_keys, _keys_loaded_at

    now = time.time()
    with _cached_keys_lock:
        if _cached_keys and (now - _keys_loaded_at) < KEY_CACHE_TTL:
            return list(_cached_keys)

        raw = ""
        try:
            raw = st.secrets.get("GROQ_API_KEYS", "") or ""
        except Exception:
            pass

        if not raw:
            raw = os.getenv("GROQ_API_KEYS", "") or ""

        keys = [k.strip() for k in raw.split(",") if k.strip()]

        if not keys:
            raise ValueError("❌ No Groq API keys found in secrets or environment.")

        # Shuffle once so workers don't all start at key[0]
        random.shuffle(keys)
        _cached_keys    = keys
        _keys_loaded_at = now
        return list(_cached_keys)


# ── Prompt hashing ────────────────────────────────────────────────────────────
def hash_prompt(prompt: str, model: str) -> str:
    return hashlib.sha256(f"{model}|{prompt}".encode("utf-8")).hexdigest()


# ── Cache R/W ─────────────────────────────────────────────────────────────────
def get_cached_response(prompt: str, model: str) -> Optional[str]:
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
        pass
    return None


def set_cached_response(prompt: str, model: str, response: str):
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
        pass


# ── Key tracking (Supabase) ───────────────────────────────────────────────────
def increment_key_usage(api_key: str):
    try:
        _execute(
            """
            INSERT INTO key_usage (api_key, usage_count, last_reset)
            VALUES (%s, 1, CURRENT_DATE)
            ON CONFLICT (api_key) DO UPDATE
                SET usage_count = CASE
                        WHEN key_usage.last_reset = CURRENT_DATE
                        THEN key_usage.usage_count + 1
                        ELSE 1
                    END,
                    last_reset = CURRENT_DATE
            """,
            (_key_id(api_key),),  # ← masked — raw key never stored in DB
        )
    except Exception:
        pass


def mark_key_failure(api_key: str, reason: str = "error"):
    try:
        _execute(
            """
            INSERT INTO key_failures (api_key, fail_time, reason)
            VALUES (%s, NOW(), %s)
            ON CONFLICT (api_key) DO UPDATE
                SET fail_time = EXCLUDED.fail_time,
                    reason    = EXCLUDED.reason
            """,
            (_key_id(api_key), reason),  # ← masked — raw key never stored in DB
        )
    except Exception:
        pass


def clear_key_failure(api_key: str):
    try:
        _execute("DELETE FROM key_failures WHERE api_key = %s", (_key_id(api_key),))
    except Exception:
        pass


# ── Error classifier ──────────────────────────────────────────────────────────
def _classify_error(error: Exception) -> str:
    """
    Returns:
        'quota'     — rate limited → 60-min cooldown
        'dead'      — bad/invalid key → 5-min cooldown
        'transient' — network blip / server 500 / timeout → do NOT touch the key
    """
    msg = str(error).lower()

    # Also check numeric HTTP status if available (groq SDK / httpx)
    status_code = None
    for attr in ("status_code", "response", "http_status"):
        try:
            val = getattr(error, attr, None)
            if isinstance(val, int):
                status_code = val
                break
            if hasattr(val, "status_code"):
                status_code = val.status_code
                break
        except Exception:
            pass

    if status_code == 413 or any(s in msg for s in _OVERSIZED_SIGNALS):
        return "oversized"
    if status_code == 429 or any(s in msg for s in _QUOTA_SIGNALS):
        return "quota"
    if status_code in (401, 403) or any(s in msg for s in _DEAD_KEY_SIGNALS):
        return "dead"
    return "transient"


# ── Healthy key filter (in-memory first, Supabase fallback) ──────────────────
def get_healthy_keys(api_keys: list) -> list:
    """
    Return subset of api_keys that pass in-memory health checks.
    Falls back to DB refresh if in-memory data seems incomplete.
    FIX 8 preserved: DB failure returns all keys rather than empty list.
    """
    today = get_utc_now().strftime("%Y-%m-%d")

    # Fast path — use only in-memory state (no DB round-trip)
    healthy_fast = []
    for key in api_keys:
        if _mem_is_in_cooldown(key):
            continue
        if _mem_usage_over_limit(key):
            continue
        healthy_fast.append(key)

    # If we filtered out nothing at all (first run, empty mem-state), do a
    # one-shot DB refresh to seed the in-memory tables.
    if len(healthy_fast) == len(api_keys):
        _seed_mem_from_db(api_keys, today)
        # Re-filter after seeding
        healthy_fast = [k for k in api_keys
                        if not _mem_is_in_cooldown(k)
                        and not _mem_usage_over_limit(k)]

    if not healthy_fast:
        # All keys appear unhealthy — return all as last resort
        healthy_fast = list(api_keys)

    # Stable sort + shuffle (preserves FIX 9 intent)
    healthy_fast.sort()
    random.shuffle(healthy_fast)
    return healthy_fast


def _seed_mem_from_db(api_keys: list, today: str):
    """
    One-shot DB read to seed in-memory failure + usage tables.
    Runs at startup or after a full key cycle.
    DB stores masked key IDs (_key_id) — we build a reverse map to
    match DB rows back to raw in-memory keys.
    """
    # Build reverse map: masked_id → raw_key
    id_to_key = {_key_id(k): k for k in api_keys}
    masked_ids = list(id_to_key.keys())

    try:
        failures_rows = _execute(
            "SELECT api_key, fail_time, reason FROM key_failures WHERE api_key = ANY(%s)",
            (masked_ids,),
            fetch="all",
        ) or []
        usage_rows = _execute(
            "SELECT api_key, usage_count, last_reset FROM key_usage WHERE api_key = ANY(%s)",
            (masked_ids,),
            fetch="all",
        ) or []
    except Exception:
        return  # DB unavailable — leave mem state as-is

    now_ts = time.time()

    with _mem_failures_lock:
        for row in failures_rows:
            raw_key = id_to_key.get(row["api_key"])
            if not raw_key:
                continue
            fail_dt = row["fail_time"]
            if isinstance(fail_dt, str):
                fail_dt = datetime.strptime(fail_dt, "%Y-%m-%d %H:%M:%S")
            if fail_dt.tzinfo is None:
                fail_dt = pytz.utc.localize(fail_dt)
            fail_ts = fail_dt.timestamp()
            reason  = row.get("reason", "error")
            cooldown = (QUOTA_COOLDOWN_MINUTES if reason == "quota"
                        else FAILURE_COOLDOWN_MINUTES) * 60
            # Only seed if the cooldown is still active
            if (now_ts - fail_ts) < cooldown:
                _mem_failures[raw_key] = {
                    "time":   fail_ts,
                    "reason": reason,
                }

    with _mem_usage_lock:
        for row in usage_rows:
            raw_key = id_to_key.get(row["api_key"])
            if not raw_key:
                continue
            last_reset = row["last_reset"]
            if hasattr(last_reset, "isoformat"):
                last_reset = last_reset.isoformat()[:10]
            elif isinstance(last_reset, datetime):
                last_reset = last_reset.strftime("%Y-%m-%d")
            usage_count = row["usage_count"] if last_reset == today else 0
            _mem_usage[raw_key] = {
                "count": usage_count,
                "date":  today,
            }


# ── Global key-index picker ───────────────────────────────────────────────────
def _pick_start_index(n: int) -> int:
    """
    Atomically advance the global round-robin counter and return a start
    index within [0, n).  Thread-safe — uses a lock around the counter read.
    """
    global _counter_value
    with _counter_lock:
        idx = _counter_value % n
        _counter_value += 1
    return idx


# ── Single LLM call ───────────────────────────────────────────────────────────
def try_call_llm(prompt: str, api_key: str, model: str, temperature: float) -> str:
    kwargs = {}
    effort = REASONING_EFFORT_BY_MODEL.get(model)
    if effort:
        # GPT-OSS models default to reasoning_effort="medium" on Groq, which
        # burns hidden chain-of-thought tokens (counted against TPM) even for
        # plain extraction tasks. Force "low" unless overridden above.
        kwargs["model_kwargs"] = {"reasoning_effort": effort}
    llm = ChatGroq(model=model, temperature=temperature, groq_api_key=api_key, **kwargs)
    return llm.invoke(prompt).content


# ── Main entry point ──────────────────────────────────────────────────────────
def call_llm(
    prompt: str,
    session,
    model: str = "openai/gpt-oss-120b",
    temperature: float = 0,
) -> str:
    """
    Distribute LLM calls evenly across all 100 Groq keys.

    Strategy:
      1. Supabase cache hit → return immediately (zero LLM cost).
      2. User-supplied key → try first if TPM headroom exists.
      3. Global round-robin across all healthy admin keys, headroom keys first.
         - In-memory failure/usage checks (no DB round-trip on hot path).
         - Exponential back-off with full jitter between key attempts.
         - Background threads flush usage/failure updates to Supabase.
      4. Over-budget keys tried last as graceful fallback.

    Thread/multi-user safety:
      - _pick_start_index() uses a module-level atomic counter so concurrent
        users always pick different starting keys even in the same worker.
      - All shared state is protected by per-purpose locks.
      - Supabase writes happen in daemon threads (fire-and-forget).
    """
    if session is None:
        session = {}

    # ── Throttled cleanup ─────────────────────────────────────────────────────
    _last_cleanup = session.get("_last_cleanup_ts", 0)
    if time.time() - _last_cleanup > CLEANUP_INTERVAL_SECONDS:
        threading.Thread(target=cleanup_cache, daemon=True).start()
        try:
            session["_last_cleanup_ts"] = time.time()
        except Exception:
            pass

    # ── Cache hit ─────────────────────────────────────────────────────────────
    cached = get_cached_response(prompt, model)
    if cached:
        return cached

    estimated_tokens = _estimate_tokens(prompt, model)
    last_error = None

    # ── Fail-fast: prompt is too big for this model on ANY key ────────────────
    # A 413 from Groq means the request itself exceeds the model's per-request
    # token ceiling — no amount of key rotation fixes that. Catching it here
    # avoids burning through the whole 100-key pool on a guaranteed failure.
    # NOTE: this must check against the REAL per-request ceiling, not the
    # conservative shared TPM_LIMIT_BY_MODEL figure — that figure is a
    # per-minute multi-user budget target, not a hard per-request limit, and
    # using it here was rejecting valid requests that fit fine in one call.
    model_limit_check = _request_ceiling_for(model)
    if estimated_tokens > model_limit_check:
        return (
            f"❌ Prompt too large for {model}: ~{estimated_tokens} estimated "
            f"tokens exceeds its ~{model_limit_check} per-request ceiling. "
            f"Truncate the input before calling call_llm()."
        )

    # ── User-supplied key ─────────────────────────────────────────────────────
    user_key = ""
    raw_user_key = session.get("user_groq_key", "")
    if isinstance(raw_user_key, str):
        user_key = raw_user_key.strip()

    if user_key and _key_has_tpm_headroom(user_key, estimated_tokens, model):
        try:
            response = try_call_llm(prompt, user_key, model, temperature)
            _record_key_tokens(user_key, estimated_tokens, time.time())
            set_cached_response(prompt, model, response)
            _async_increment_usage(user_key)
            return response
        except Exception as e:
            err_type = _classify_error(e)
            if err_type == "quota":
                _mem_record_failure(user_key, "quota")
                _record_key_tokens(user_key, _tpm_limit_for(model), time.time())
                _async_mark_failure(user_key, "quota")
            elif err_type == "dead":
                _mem_record_failure(user_key, "error")
                _async_mark_failure(user_key, "error")
            # "oversized" falls through here too — user-key attempt simply
            # fails and admin-key rotation below will hit the same fail-fast
            # check via model_limit_check, so no special-case needed.
            last_error = e

    # ── Admin key rotation ────────────────────────────────────────────────────
    try:
        all_admin_keys = load_groq_api_keys()
    except ValueError as e:
        return f"❌ LLM unavailable: {e}"

    healthy_keys = get_healthy_keys(all_admin_keys)
    if not healthy_keys:
        return f"❌ LLM unavailable: {last_error or 'No healthy API keys available'}"

    # Partition: TPM-headroom keys first, over-budget keys as fallback
    now_ts = time.time()
    model_tpm_limit = _tpm_limit_for(model)
    with _tpm_lock:
        keys_with_headroom = [
            k for k in healthy_keys
            if (_get_key_tpm(k, now_ts) + estimated_tokens) <= model_tpm_limit
        ]
        keys_over_budget = [k for k in healthy_keys if k not in set(keys_with_headroom)]

    admin_keys = keys_with_headroom + keys_over_budget
    n          = len(admin_keys)

    # Global round-robin start index (thread-safe, no per-session state needed)
    start = _pick_start_index(n)

    attempt = 0
    for offset in range(n):
        idx = (start + offset) % n
        key = admin_keys[idx]

        # Exponential back-off with full jitter (no fixed sleep for headroom keys)
        if attempt > 0:
            cap   = min(BACKOFF_BASE * (2 ** (attempt - 1)), BACKOFF_MAX)
            sleep = random.uniform(0, cap)
            if sleep > 0.05:
                time.sleep(sleep)

        # Extra small pause before over-budget keys to reduce burst collisions
        if key in keys_over_budget and attempt == 0:
            time.sleep(random.uniform(0.5, 1.5))

        try:
            response = try_call_llm(prompt, key, model, temperature)
            # Success ──────────────────────────────────────────────────────────
            _record_key_tokens(key, estimated_tokens, time.time())
            set_cached_response(prompt, model, response)
            _mem_increment_usage(key)
            _async_increment_usage(key)
            _mem_clear_failure(key)
            _async_clear_failure(key)
            return response

        except Exception as e:
            err_type = _classify_error(e)
            if err_type == "oversized":
                # Every key will 413 on this same prompt — stop immediately.
                last_error = e
                break
            if err_type == "quota":
                _mem_record_failure(key, "quota")
                _record_key_tokens(key, model_tpm_limit, time.time())
                _async_mark_failure(key, "quota")
            elif err_type == "dead":
                _mem_record_failure(key, "error")
                _async_mark_failure(key, "error")
            # transient: key stays healthy, try next
            last_error = e
            attempt   += 1

    return f"❌ LLM unavailable: {last_error or 'All API keys exhausted'}"
