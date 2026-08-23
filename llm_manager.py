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
import re
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

# ── Per-minute token rate limiter (Groq free tier: ~6000 TPM per key) ────────
TPM_LIMIT          = 5500          # stay slightly under the 6000 hard limit
TPM_WINDOW_SECONDS = 60
CHARS_PER_TOKEN    = 4             # 1 token ≈ 4 chars (conservative)

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
# 413 → payload too large. This is an INPUT problem, not a key problem.
# Never rotate keys, never mark quota/dead, never retry the same prompt as-is.
_PAYLOAD_TOO_LARGE_SIGNALS = [
    "413", "payload too large", "request too large", "too large",
    "content too large", "request entity too large",
]
# 400 → bad request. Invalid/malformed request parameters (e.g. an
# unsupported reasoning_effort value, a bad JSON body, an invalid model
# param). This is NEVER a key-health problem — every key would hit the
# exact same 400, so we must NOT rotate through all API keys, mark the
# key dead, or mark quota. Fail fast with a controlled error instead.
_BAD_REQUEST_SIGNALS = [
    "400", "bad request", "invalid_request_error", "invalid request",
]
# Output got cut off because the completion budget (reasoning + visible
# tokens for GPT-OSS) ran out. A new key will NOT fix this — it is a
# generation/output problem, never a key-health problem.
_LENGTH_SIGNALS = ["length", "max_tokens", "max_completion_tokens",
                    "context_length_exceeded", "finish_reason=length"]

# ── Centralized model configuration ───────────────────────────────────────────
# ONE place to change the active model. Nothing else in the codebase should
# hardcode a model string — everything reads DEFAULT_MODEL or GPT_OSS_CONFIG.
DEFAULT_MODEL = "openai/gpt-oss-120b"

# GPT-OSS is a REASONING model: reasoning tokens + visible output tokens share
# ONE completion budget. Do not set one giant global max_tokens — pick a small,
# task-appropriate reasoning effort + output budget for each kind of call.
#
#   reasoning_effort      : "low" | "medium" | "high"
#                            (Groq's GPT-OSS 20B/120B API only supports these
#                             three values — "none" is not accepted, so
#                             deterministic extraction/formatting tasks use
#                             "low" instead.)
#   max_completion_tokens : ceiling passed to ChatGroq — covers reasoning +
#                            output. (Groq's chat.completions API rejects the
#                            legacy "max_tokens" param for these models; the
#                            correct param name is "max_completion_tokens".)
GPT_OSS_CONFIG = {
    # Call A — rewrite the resume into ATS-optimised plain text ONLY.
    "resume_rewrite": {
        "reasoning_effort": "low",
        "max_completion_tokens": 2200,
    },
    # Call B — turn the already-rewritten resume into strict JSON ONLY.
    # Deterministic extraction/formatting task → lowest reasoning effort,
    # so most of the budget goes to visible JSON output.
    "json_extraction": {
        "reasoning_effort": "low",
        # Raised from 2200 → 3600: education/certifications/additional sit
        # at the END of the JSON schema (after skills, experience, and
        # projects). On verbose resumes with several experience/project
        # entries × 3-5 bullets each, the 2200 budget could be exhausted
        # before the model ever wrote the "education" key — the plain-text
        # rewrite (Call A, separate budget) still showed education fine,
        # which is exactly the "shows in UI, missing in template" symptom.
        # _attempt_json_repair() closes whatever structure was open at the
        # cutoff, producing technically-valid JSON that is silently missing
        # trailing keys — see the completeness check in
        # resume_engine._call_b_extract_json() for the other half of this fix.
        "max_completion_tokens": 3600,
    },
    # Call C — exactly 5 job titles. Tiny, deterministic.
    "job_titles": {
        "reasoning_effort": "low",
        "max_completion_tokens": 400,
    },
    # ATS scoring narrative — benefits from reasoning, larger structured output.
    "ats_analysis": {
        "reasoning_effort": "medium",
        # Raised from 2400 → 4000: the prompt asks for 7 sections
        # ([SEC:CANDIDATE_NAME] ... [SEC:FINAL]) and reasoning + all visible
        # output share this one budget. [SEC:FINAL] is both the last and the
        # largest section requested, so it was the first casualty whenever
        # the model ran out of budget — silently truncating the response
        # right before writing it, which _extract() then defaulted to "N/A".
        "max_completion_tokens": 4000,
    },
    # AI Interview Coach evaluation.
    "interview_evaluation": {
        "reasoning_effort": "medium",
        "max_completion_tokens": 1500,
    },
    # Small deterministic classification/formatting helpers (domain
    # detection, format-check JSON, grammar score, cover letters, etc).
    "quick_extraction": {
        "reasoning_effort": "low",
        "max_completion_tokens": 900,
    },
    # Job Scam Detector — Layer A: extract title/company/location/salary/
    # website/contact from raw posting text into JSON. Deterministic
    # extraction, small schema — same shape as quick_extraction's job.
    "job_scam_extraction": {
        "reasoning_effort": "low",
        "max_completion_tokens": 900,
    },
    # Job Scam Detector — Layer C: AI deep-analysis verdict. Output includes
    # a red_flags array plus three free-text fields (explanation,
    # recommended_action, salary_assessment paragraph) — comparable verbosity
    # to ats_analysis, and genuinely benefits from reasoning since it's
    # weighing fraud signals, not just formatting.
    "job_scam_analysis": {
        "reasoning_effort": "medium",
        "max_completion_tokens": 2400,
    },
    # Cover letter generation — 5-part structured letter, up to ~350 words.
    # Bigger than the quick single-paragraph cover letter in cover_letter.py,
    # so it gets its own slightly larger budget rather than risking a cut-off
    # closing paragraph under quick_extraction's 900-token ceiling.
    "cover_letter": {
        "reasoning_effort": "low",
        "max_completion_tokens": 1200,
    },
    # Resume Builder — "AI Enhance" one-shot generator: summary + multiple
    # experience entries with bullets + multiple project entries with
    # bullets + skills + soft skills + languages + interests + certificates,
    # all in a single completion. This is architecturally the same
    # "several sections in one call" shape that caused the education/
    # certifications truncation bug in the resume analyzer's JSON
    # extraction — certificates sits LAST in this prompt's requested
    # section order too, so it's the most exposed to the same failure mode.
    # Generous budget + medium reasoning (this is creative generation, not
    # pure formatting) to give it room to actually finish.
    "resume_builder_enhance": {
        "reasoning_effort": "medium",
        "max_completion_tokens": 4000,
    },
    # AI Interview Coach — live per-answer scoring (Hard mode, or the
    # simpler pass/fail style single-answer scorer). Small fixed output:
    # one score + 1-2 sentence feedback.
    "interview_answer_score": {
        "reasoning_effort": "low",
        "max_completion_tokens": 500,
    },
    # AI Interview Coach — chain-of-thought single-answer evaluation.
    # Structured JSON: key_concepts/strengths/gaps arrays + 3 scores + a
    # 2-4 paragraph feedback field, optionally a follow-up question for
    # Hard mode. Genuinely benefits from reasoning (it's doing multi-step
    # analysis before scoring, not just formatting).
    "interview_evaluation": {
        "reasoning_effort": "medium",
        "max_completion_tokens": 1800,
    },
    # AI Interview Coach — BATCH scoring for Easy/Medium mode: scores every
    # answer in the interview in ONE call, output size scales with question
    # count. This is a FLOOR/default only — the call site computes a
    # per-interview override (base + per-question allowance) via
    # max_completion_tokens_override, since a fixed budget can't fit both a
    # 3-question and a 10-question interview. On total parse failure this
    # currently falls back to generic feedback for the WHOLE interview, so
    # under-budgeting here is a real quality risk, not just truncation.
    "interview_batch_scoring": {
        "reasoning_effort": "low",
        "max_completion_tokens": 3000,
    },
    # AI Interview Coach — adaptive follow-up question generation (Hard
    # mode only, one question at a time). Small output.
    "interview_followup": {
        "reasoning_effort": "low",
        "max_completion_tokens": 400,
    },
    # AI Interview Coach — question-set generation (resume-based or
    # domain-based, several questions per call, sometimes with rationale/
    # metadata per question).
    "interview_question_generation": {
        "reasoning_effort": "low",
        "max_completion_tokens": 2000,
    },
    # AI Interview Coach — resume analysis feeding into interview question
    # generation (extracts skills/experience context, not a full rewrite).
    "interview_resume_analysis": {
        "reasoning_effort": "low",
        "max_completion_tokens": 1500,
    },
    # AI Interview Coach — combined startup call: resume context extraction
    # + resume-based questions + generic domain questions, all in one JSON
    # response (replaces 3 separate calls). Bigger than a single
    # question-generation call since it's carrying all three outputs.
    "interview_startup_combined": {
        "reasoning_effort": "low",
        "max_completion_tokens": 2600,
    },
    # Fallback for any call site that doesn't specify a task_type.
    "default": {

        "reasoning_effort": "low",
        "max_completion_tokens": 1500,
    },
}


def get_task_config(task_type: str) -> dict:
    """Look up the GPT-OSS config for a task, falling back to 'default'."""
    return GPT_OSS_CONFIG.get(task_type, GPT_OSS_CONFIG["default"])


# ── Unicode punctuation sanitizer ─────────────────────────────────────────────
# GPT-OSS (unlike Llama 3.3) frequently writes "typographically polished"
# punctuation — non-breaking hyphens, minus signs, figure dashes — instead of
# plain ASCII "-". These specific characters fall OUTSIDE the WinAnsiEncoding
# (cp1252) charset that both python-docx's default fonts and xhtml2pdf/
# ReportLab's base14 Helvetica rely on, so they render as a black "tofu"
# missing-glyph box in the generated DOCX/PDF (and inconsistently in some UI
# contexts) instead of a hyphen. En dash (–) and em dash (—) ARE in cp1252 and
# render fine — this is specifically about the codepoints that are NOT.
#
# Call this on every piece of LLM-generated text before it is displayed,
# cached, or handed to a document generator, so the fix holds regardless of
# which renderer touches the text.
_UNICODE_PUNCT_MAP = {
    "\u2010": "-",   # HYPHEN
    "\u2011": "-",   # NON-BREAKING HYPHEN  ← the usual culprit
    "\u2012": "-",   # FIGURE DASH
    "\u2015": "-",   # HORIZONTAL BAR
    "\u2043": "-",   # HYPHEN BULLET
    "\u2212": "-",   # MINUS SIGN
    "\u2018": "'",   # LEFT SINGLE QUOTATION MARK
    "\u2019": "'",   # RIGHT SINGLE QUOTATION MARK
    "\u201a": "'",   # SINGLE LOW-9 QUOTATION MARK
    "\u201c": '"',   # LEFT DOUBLE QUOTATION MARK
    "\u201d": '"',   # RIGHT DOUBLE QUOTATION MARK
    "\u201e": '"',   # DOUBLE LOW-9 QUOTATION MARK
    "\u2026": "...", # HORIZONTAL ELLIPSIS
    "\ufeff": "",    # BYTE ORDER MARK / zero-width no-break space
    "\u200b": "",    # ZERO WIDTH SPACE
}
_UNICODE_PUNCT_RE = re.compile("|".join(re.escape(k) for k in _UNICODE_PUNCT_MAP))


def sanitize_llm_text(text) -> str:
    """
    Normalize LLM output text so it renders safely in every downstream
    surface (Streamlit UI, python-docx, xhtml2pdf/ReportLab). Safe to call
    on already-clean ASCII text (no-op), safe to call on full JSON strings
    (only touches punctuation characters, never touches the ASCII double
    quotes JSON syntax depends on), and safe to call on None/non-str input.
    """
    if not text or not isinstance(text, str):
        return text or ""
    return _UNICODE_PUNCT_RE.sub(lambda m: _UNICODE_PUNCT_MAP[m.group(0)], text)

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
def _estimate_tokens(text: str) -> int:
    return max(1, len(text) // CHARS_PER_TOKEN)


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


def _key_has_tpm_headroom(api_key: str, estimated_tokens: int) -> bool:
    now = time.time()
    with _tpm_lock:
        current_tpm = _get_key_tpm(api_key, now)
    return (current_tpm + estimated_tokens) <= TPM_LIMIT


def get_keys_with_tpm_headroom(api_keys: list, estimated_tokens: int) -> list:
    now = time.time()
    with _tpm_lock:
        headroom = [k for k in api_keys
                    if (_get_key_tpm(k, now) + estimated_tokens) <= TPM_LIMIT]
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
def hash_prompt(prompt: str, model: str, task_type: str = "default",
                 max_completion_tokens_override: Optional[int] = None) -> str:
    """
    Cache key includes prompt + model + the generation config that governs
    output shape (reasoning effort / token budget). This guarantees a cached
    Llama response is never returned for a GPT-OSS request, and that two
    task types sharing similar prompt text never collide either. When a
    caller overrides the token budget (e.g. batch scoring scaling its
    budget by question count), that override is folded into the key too —
    otherwise a cached response generated with a smaller budget could get
    served back for a request that actually needed more room.
    """
    cfg = get_task_config(task_type)
    budget = max_completion_tokens_override or cfg.get('max_completion_tokens')
    sig = f"{model}|{task_type}|{cfg.get('reasoning_effort')}|{budget}"
    return hashlib.sha256(f"{sig}|{prompt}".encode("utf-8")).hexdigest()


# ── Cache R/W ─────────────────────────────────────────────────────────────────
def get_cached_response(prompt: str, model: str, task_type: str = "default",
                         max_completion_tokens_override: Optional[int] = None) -> Optional[str]:
    key    = hash_prompt(prompt, model, task_type, max_completion_tokens_override)
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


def set_cached_response(prompt: str, model: str, response: str, task_type: str = "default",
                         max_completion_tokens_override: Optional[int] = None):
    key = hash_prompt(prompt, model, task_type, max_completion_tokens_override)
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
        'quota'              — rate limited → 60-min cooldown, rotate key
        'dead'                — bad/invalid key → 5-min cooldown, rotate key
        'payload_too_large'   — 413: the REQUEST is too big. Never a key
                                 problem — do NOT rotate, do NOT cooldown the
                                 key, do NOT retry the same prompt as-is.
        'bad_request'          — 400: malformed/invalid request parameters
                                 (bad reasoning_effort, bad JSON body, bad
                                 model param, etc). Never a key problem —
                                 every key hits the identical 400. Do NOT
                                 rotate through other keys, do NOT mark the
                                 key dead, do NOT mark quota. Log the actual
                                 Groq response body and fail fast.
        'length'               — completion budget (reasoning + output) ran
                                 out before finishing. A new key will not
                                 produce more output — never rotate for this.
        'transient'            — network blip / server 500 / timeout → do NOT
                                 touch the key, just try the next one.
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

    if status_code == 413 or any(s in msg for s in _PAYLOAD_TOO_LARGE_SIGNALS):
        return "payload_too_large"
    if status_code == 429 or any(s in msg for s in _QUOTA_SIGNALS):
        return "quota"
    if status_code in (401, 403) or any(s in msg for s in _DEAD_KEY_SIGNALS):
        return "dead"
    # 400 must be checked before the generic dead/length fallbacks below —
    # an invalid request parameter is not an API-key or output-budget issue.
    if status_code == 400 or any(s in msg for s in _BAD_REQUEST_SIGNALS):
        return "bad_request"
    if any(s in msg for s in _LENGTH_SIGNALS):
        return "length"
    return "transient"


def _extract_error_body(error: Exception) -> str:
    """Best-effort extraction of the raw Groq response body for logging a
    400 bad_request. Groq/httpx exceptions may expose this under different
    attributes depending on SDK version, so we try the common ones."""
    for attr in ("body", "response", "message"):
        try:
            val = getattr(error, attr, None)
            if val is None:
                continue
            if isinstance(val, (str, bytes)):
                return val if isinstance(val, str) else val.decode("utf-8", "replace")
            # httpx.Response-like object
            text = getattr(val, "text", None)
            if text:
                return text
            body_attr = getattr(val, "body", None)
            if body_attr:
                return str(body_attr)
        except Exception:
            pass
    return str(error)


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


class LengthFinishError(Exception):
    """Raised when the model stopped because its completion budget
    (reasoning + visible output for GPT-OSS) ran out, not because of an
    API/key error. Classified as 'length' — never rotates keys."""
    pass


def _build_chat_groq(model: str, api_key: str, temperature: float, task_type: str,
                      max_completion_tokens_override: Optional[int] = None):
    """
    Construct a ChatGroq client with the task-appropriate reasoning effort
    and output-token budget from GPT_OSS_CONFIG.

    reasoning_effort support varies by installed langchain-groq version:
      - Newer versions accept it as a first-class constructor kwarg.
      - Some versions only forward it if passed as part of model_kwargs.
    We try the documented first-class kwarg first and fall back gracefully
    so this never hard-crashes on an older pinned version. Non-GPT-OSS
    models (which don't support reasoning_effort) simply skip the field.
    """
    cfg = get_task_config(task_type)
    max_completion_tokens = max_completion_tokens_override or cfg.get("max_completion_tokens")
    reasoning_effort = cfg.get("reasoning_effort")
    is_gpt_oss = "gpt-oss" in (model or "").lower()

    base_kwargs = dict(
        model=model, temperature=temperature, groq_api_key=api_key,
        # Disable the Groq SDK's own internal retry-on-429. Without this,
        # the SDK silently retries with its own backoff (observed: a 45s
        # blocking wait) BEFORE our exception ever reaches _classify_error().
        # That means our quota cooldown, key rotation, and TPM tracking
        # never even see the 429 happened — the whole custom multi-key
        # architecture gets bypassed for that call, and the calling thread
        # just hangs for the SDK's retry window instead. Setting this to 0
        # makes every 429 surface immediately as an exception so call_llm()
        # can classify it and rotate to the next key right away, which is
        # the entire point of having 100 keys instead of 1.
        max_retries=0,
    )
    if max_completion_tokens:
        # Groq's chat.completions API rejects "max_tokens" for these models —
        # pass max_completion_tokens directly (never via model_kwargs).
        base_kwargs["max_completion_tokens"] = max_completion_tokens

    if is_gpt_oss and reasoning_effort:
        try:
            return ChatGroq(**base_kwargs, reasoning_effort=reasoning_effort)
        except TypeError:
            pass
        try:
            return ChatGroq(**base_kwargs, model_kwargs={"reasoning_effort": reasoning_effort})
        except TypeError:
            pass
        # Installed langchain-groq version supports neither path — proceed
        # without reasoning_effort rather than crashing the whole request.
        return ChatGroq(**base_kwargs)

    return ChatGroq(**base_kwargs)


# ── Single LLM call ───────────────────────────────────────────────────────────
def try_call_llm(
    prompt: str,
    api_key: str,
    model: str,
    temperature: float,
    task_type: str = "default",
    max_completion_tokens_override: Optional[int] = None,
) -> str:
    llm = _build_chat_groq(model, api_key, temperature, task_type, max_completion_tokens_override)
    ai_message = llm.invoke(prompt)
    content = ai_message.content or ""

    # ── Detect completion-budget truncation (separate from API errors) ──────
    finish_reason = None
    try:
        meta = getattr(ai_message, "response_metadata", None) or {}
        finish_reason = meta.get("finish_reason") or meta.get("stop_reason")
        if not finish_reason:
            gen_info = getattr(ai_message, "generation_info", None) or {}
            finish_reason = gen_info.get("finish_reason")
    except Exception:
        pass

    if finish_reason == "length":
        if not content.strip():
            # Budget exhausted with literally nothing visible returned.
            raise LengthFinishError(
                f"finish_reason=length — completion budget exhausted for task "
                f"'{task_type}' before any visible output was produced."
            )
        # ── Partial truncation ────────────────────────────────────────────
        # The model produced *some* visible output before running out of
        # budget — most often the case when a prompt asks for several
        # ordered sections and the model gets cut off partway through a
        # later one. Previously this returned silently, so callers (and
        # regex/JSON extractors downstream) had no way to tell a truncated
        # response from a complete one — a missing trailing section just
        # looked like the model chose not to answer it. Content is still
        # returned here (a partial response is more useful than none), but
        # this must be visible so it doesn't get mistaken for a normal
        # empty/"N/A" field further down the pipeline.
        print(
            f"⚠️ length: task '{task_type}' hit its completion budget after "
            f"producing {len(content)} chars — response is likely missing "
            f"one or more trailing sections. Consider raising "
            f"max_completion_tokens for this task_type in GPT_OSS_CONFIG."
        )

    return content


# ── Main entry point ──────────────────────────────────────────────────────────
def call_llm(
    prompt: str,
    session,
    model: str = DEFAULT_MODEL,
    temperature: float = 0,
    task_type: str = "default",
    max_completion_tokens_override: Optional[int] = None,
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

    413 / length handling (IMPORTANT — different from key-health errors):
      - 413 (payload_too_large): the INPUT is too big for this request. No
        key can fix that. We do NOT rotate, do NOT cooldown the key, and do
        NOT retry the same oversized prompt against another key. We fail
        fast with a controlled error so the caller can shrink the prompt.
      - length: the completion budget (reasoning + visible tokens) ran out.
        A different key will not produce more output. We do NOT rotate for
        this either — we fail fast so the caller can use a smaller task or
        adjust its GPT_OSS_CONFIG budget.

    task_type selects the GPT-OSS reasoning effort + output-token budget
    from GPT_OSS_CONFIG (see top of file) and is folded into the cache key
    so a cached response from one task/model can never leak into another.

    max_completion_tokens_override lets a caller scale the completion
    budget beyond the task_type's fixed default for a specific call — e.g.
    interview batch-scoring, where output size scales with the number of
    questions being scored in one call and a single fixed budget can't fit
    both a 3-question and a 10-question interview. Folded into the cache
    key too, same reasoning as task_type.

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
    cached = get_cached_response(prompt, model, task_type, max_completion_tokens_override)
    if cached:
        return cached

    # Reserve BOTH prompt and expected completion tokens against a key's
    # TPM budget — a headroom check that only counted the prompt was letting
    # calls get routed to keys that looked fine on paper but didn't actually
    # have room for the completion, causing real Groq 429s that then surface
    # as an empty/failed section (e.g. ATS analysis or JSON extraction
    # returning nothing) once the shared, process-wide TPM budget got eaten
    # into by earlier calls in the same analysis or a prior upload within
    # the same 60-second window.
    estimated_tokens = _estimate_tokens(prompt) + (
        max_completion_tokens_override or get_task_config(task_type).get("max_completion_tokens", 0)
    )
    last_error = None

    # ── User-supplied key ─────────────────────────────────────────────────────
    user_key = ""
    raw_user_key = session.get("user_groq_key", "")
    if isinstance(raw_user_key, str):
        user_key = raw_user_key.strip()

    if user_key and _key_has_tpm_headroom(user_key, estimated_tokens):
        try:
            response = try_call_llm(prompt, user_key, model, temperature, task_type,
                                     max_completion_tokens_override)
            _record_key_tokens(user_key, estimated_tokens, time.time())
            set_cached_response(prompt, model, response, task_type, max_completion_tokens_override)
            _async_increment_usage(user_key)
            return response
        except Exception as e:
            err_type = _classify_error(e)
            if err_type == "payload_too_large":
                # Never a key problem — fail fast, do not touch key health,
                # do not fall through to admin key rotation with the same
                # oversized prompt.
                return "❌ payload_too_large: request input is too large for this call. Reduce the prompt/resume size and retry."
            if err_type == "length":
                return "❌ length: completion budget exhausted before producing output. Retrying with another key will not help."
            if err_type == "bad_request":
                # 400: invalid request parameters. Every key would hit the
                # identical error — do NOT fall through to admin key
                # rotation, do NOT mark this key dead/quota. Log the actual
                # Groq response body and fail fast with a controlled error.
                print(f"❌ bad_request (400) from Groq — user key: {_extract_error_body(e)}")
                return "❌ bad_request: the request was rejected as invalid (400). Rotating keys will not help — check the request parameters."
            if err_type == "quota":
                _mem_record_failure(user_key, "quota")
                _record_key_tokens(user_key, TPM_LIMIT, time.time())
                _async_mark_failure(user_key, "quota")
            elif err_type == "dead":
                _mem_record_failure(user_key, "error")
                _async_mark_failure(user_key, "error")
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
    with _tpm_lock:
        keys_with_headroom = [
            k for k in healthy_keys
            if (_get_key_tpm(k, now_ts) + estimated_tokens) <= TPM_LIMIT
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
            response = try_call_llm(prompt, key, model, temperature, task_type,
                                     max_completion_tokens_override)
            # Success ──────────────────────────────────────────────────────────
            _record_key_tokens(key, estimated_tokens, time.time())
            set_cached_response(prompt, model, response, task_type, max_completion_tokens_override)
            _mem_increment_usage(key)
            _async_increment_usage(key)
            _mem_clear_failure(key)
            _async_clear_failure(key)
            return response

        except Exception as e:
            err_type = _classify_error(e)

            # ── 413: input problem, not a key problem. Stop immediately — ──
            # retrying across 99 more keys with the same oversized prompt
            # just produces 99 more 413s. Fail fast with a controlled error
            # so the caller can shrink/chunk the input and retry once.
            if err_type == "payload_too_large":
                return ("❌ payload_too_large: request input is too large for "
                        "this call. Reduce the prompt/resume size and retry — "
                        "rotating keys will not help.")

            # ── length: completion budget exhausted, not a key problem. ──
            # A different key has the same model with the same budget and
            # will exhaust the same way. Fail fast instead of burning
            # through every key for a guaranteed-identical outcome.
            if err_type == "length":
                return ("❌ length: completion budget exhausted before "
                        "producing output for this task. Rotating keys will "
                        "not help — use a smaller task or larger budget.")

            # ── 400: invalid request parameters, not a key problem. ──
            # Every remaining key would receive the identical 400, so we
            # stop immediately instead of burning through the whole key
            # pool. Log the actual Groq response body, do NOT mark the
            # key dead, do NOT mark quota, and return a controlled error.
            if err_type == "bad_request":
                print(f"❌ bad_request (400) from Groq — key rotation halted: {_extract_error_body(e)}")
                return ("❌ bad_request: the request was rejected as invalid "
                        "(400). Rotating keys will not help — check the "
                        "request parameters (e.g. reasoning_effort, "
                        "max_completion_tokens, model).")

            if err_type == "quota":
                _mem_record_failure(key, "quota")
                _record_key_tokens(key, TPM_LIMIT, time.time())
                _async_mark_failure(key, "quota")
                print(f"⚠️ quota (429) — key cooling down for task '{task_type}' "
                      f"(prompt+budget estimate: {estimated_tokens} tok). "
                      f"Rotating to next key.")
            elif err_type == "dead":
                _mem_record_failure(key, "error")
                _async_mark_failure(key, "error")
            # transient: key stays healthy, try next
            last_error = e
            attempt   += 1

    print(f"❌ All keys exhausted for task '{task_type}' — every key hit quota/dead/transient "
          f"within this rotation pass. This is the failure mode that shows up as an empty/"
          f"missing analysis section in the UI.")
    return f"❌ LLM unavailable: {last_error or 'All API keys exhausted'}"
