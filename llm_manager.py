import hashlib
import os
import random
import sqlite3
from datetime import datetime, timedelta
from langchain_groq import ChatGroq

# ---- CONFIG ----
WORKING_DIR = os.path.dirname(os.path.abspath(__file__))
DB_FILE = os.path.join(WORKING_DIR, "llm_data.sqlite")
CACHE_EXPIRY_HOURS = 24
FAILURE_COOLDOWN_MINUTES = 5
QUOTA_COOLDOWN_MINUTES = 60
DAILY_KEY_LIMIT = 800
DEAD_KEY_REMOVE_DAYS = 3  # auto-remove permanently dead keys after X days

# ---- DB Init ----
def init_db():
    with sqlite3.connect(DB_FILE, check_same_thread=False, timeout=10) as conn:
        conn.execute("""
            CREATE TABLE IF NOT EXISTS llm_cache (
                prompt_hash TEXT PRIMARY KEY,
                response TEXT,
                timestamp DATETIME
            )
        """)
        conn.execute("""
            CREATE TABLE IF NOT EXISTS key_failures (
                api_key TEXT PRIMARY KEY,
                fail_time DATETIME,
                reason TEXT
            )
        """)
        conn.execute("""
            CREATE TABLE IF NOT EXISTS key_usage (
                api_key TEXT PRIMARY KEY,
                usage_count INTEGER,
                last_reset DATE
            )
        """)
init_db()

# ---- Auto-clean expired cache ----
def cleanup_cache():
    cutoff = datetime.utcnow() - timedelta(hours=CACHE_EXPIRY_HOURS)
    with sqlite3.connect(DB_FILE, check_same_thread=False, timeout=10) as conn:
        conn.execute("DELETE FROM llm_cache WHERE timestamp < ?", (cutoff.strftime("%Y-%m-%d %H:%M:%S"),))
    # Auto-remove dead keys older than DEAD_KEY_REMOVE_DAYS
    cutoff_dead = datetime.utcnow() - timedelta(days=DEAD_KEY_REMOVE_DAYS)
    with sqlite3.connect(DB_FILE, check_same_thread=False, timeout=10) as conn:
        conn.execute("DELETE FROM key_failures WHERE fail_time < ?", (cutoff_dead.strftime("%Y-%m-%d %H:%M:%S"),))

# ---- Load API Keys ----
def load_groq_api_keys():
    try:
        import streamlit as st
        secret_keys = st.secrets.get("GROQ_API_KEYS", "")
        if secret_keys:
            keys = [k.strip() for k in secret_keys.split(",") if k.strip()]
            random.shuffle(keys)
            return keys
    except:
        pass
    env_keys = os.getenv("GROQ_API_KEYS")
    if env_keys:
        keys = [k.strip() for k in env_keys.split(",") if k.strip()]
        random.shuffle(keys)
        return keys
    raise ValueError("❌ No Groq API keys found.")

# ---- Hash Prompt ----
def hash_prompt(prompt: str, model: str, extra_key: str = "") -> str:
    """
    Create a unique hash for caching based on model + prompt + any extra
    context (e.g. scoring weights). Changing extra_key busts the cache
    so stale results from old weights are never returned.
    """
    return hashlib.sha256(f"{model}|{extra_key}|{prompt}".encode("utf-8")).hexdigest()


# ---- Cache Handling ----
def get_cached_response(prompt: str, model: str, extra_key: str = ""):
    """Fetch cached response if still valid"""
    key = hash_prompt(prompt, model, extra_key)
    cutoff = datetime.utcnow() - timedelta(hours=CACHE_EXPIRY_HOURS)
    with sqlite3.connect(DB_FILE, check_same_thread=False, timeout=10) as conn:
        row = conn.execute("SELECT response, timestamp FROM llm_cache WHERE prompt_hash = ?", (key,)).fetchone()
    if row:
        response, ts_str = row
        if datetime.strptime(ts_str, "%Y-%m-%d %H:%M:%S") >= cutoff:
            return response
    return None

def set_cached_response(prompt: str, model: str, response: str, extra_key: str = ""):
    """Store response in cache"""
    key = hash_prompt(prompt, model, extra_key)
    ts = datetime.utcnow().strftime("%Y-%m-%d %H:%M:%S")
    with sqlite3.connect(DB_FILE, check_same_thread=False, timeout=10) as conn:
        conn.execute("""
            INSERT OR REPLACE INTO llm_cache (prompt_hash, response, timestamp)
            VALUES (?, ?, ?)
        """, (key, response, ts))

# ---- Key Tracking ----
def increment_key_usage(api_key):
    """Track daily usage count per key"""
    today = datetime.utcnow().strftime("%Y-%m-%d")
    with sqlite3.connect(DB_FILE, check_same_thread=False, timeout=10) as conn:
        row = conn.execute("SELECT usage_count, last_reset FROM key_usage WHERE api_key=?", (api_key,)).fetchone()
        if row:
            usage_count, last_reset = row
            if last_reset != today:
                conn.execute("UPDATE key_usage SET usage_count=1, last_reset=? WHERE api_key=?", (today, api_key))
            else:
                conn.execute("UPDATE key_usage SET usage_count=usage_count+1 WHERE api_key=?", (api_key,))
        else:
            conn.execute("INSERT INTO key_usage (api_key, usage_count, last_reset) VALUES (?, ?, ?)",
                         (api_key, 1, today))

def mark_key_failure(api_key, reason="error"):
    """Mark a key as failed (with cooldown tracking)"""
    with sqlite3.connect(DB_FILE, check_same_thread=False, timeout=10) as conn:
        conn.execute("""
            INSERT OR REPLACE INTO key_failures (api_key, fail_time, reason)
            VALUES (?, ?, ?)
        """, (api_key, datetime.utcnow().strftime("%Y-%m-%d %H:%M:%S"), reason))

def clear_key_failure(api_key):
    """Remove a key from failure list"""
    with sqlite3.connect(DB_FILE, check_same_thread=False, timeout=10) as conn:
        conn.execute("DELETE FROM key_failures WHERE api_key = ?", (api_key,))

def get_healthy_keys(api_keys):
    """Return keys that are not in cooldown and under quota"""
    now = datetime.utcnow()
    healthy = []
    with sqlite3.connect(DB_FILE, check_same_thread=False, timeout=10) as conn:
        for key in api_keys:
            # Check cooldown
            row = conn.execute("SELECT fail_time, reason FROM key_failures WHERE api_key = ?", (key,)).fetchone()
            if row:
                fail_time, reason = row
                fail_dt = datetime.strptime(fail_time, "%Y-%m-%d %H:%M:%S")
                cooldown = QUOTA_COOLDOWN_MINUTES if reason == "quota" else FAILURE_COOLDOWN_MINUTES
                if (now - fail_dt).total_seconds() < cooldown * 60:
                    continue
            # Check quota
            usage = conn.execute("SELECT usage_count, last_reset FROM key_usage WHERE api_key=?", (key,)).fetchone()
            if usage:
                usage_count, last_reset = usage
                if last_reset != now.strftime("%Y-%m-%d"):
                    usage_count = 0
                if usage_count >= DAILY_KEY_LIMIT:
                    mark_key_failure(key, "quota")
                    continue
            healthy.append(key)
    random.shuffle(healthy)
    return healthy

# ---- LLM Call ----
def try_call_llm(prompt, api_key, model, temperature):
    """Make a single LLM call"""
    llm = ChatGroq(model=model, temperature=temperature, groq_api_key=api_key)
    return llm.invoke(prompt).content

# ---- Main ----
def call_llm(prompt: str, session, model="llama-3.3-70b-versatile", temperature=0):
    """
    Main entry: checks cache, tries user key, falls back to admin keys.

    Cache busting: scoring weights stored in session are included in the
    cache key so changing sidebar weights always triggers a fresh LLM call
    instead of returning a stale cached result.

    Error handling: raises RuntimeError with a clear message if all keys
    fail, so callers can catch it and show a proper UI error instead of
    silently treating the error string as a score.
    """
    # ── Build cache-busting key from session weights ──────────────────────
    # Include any scoring weights present in the session so that changing
    # weights always produces a fresh response rather than a cached one.
    weight_fingerprint = "|".join(str(session.get(k, "")) for k in [
        "edu_weight", "exp_weight", "skills_weight",
        "lang_weight", "keyword_weight",
    ])

    # 🔹 Step 1: Cache first
    cleanup_cache()
    cached = get_cached_response(prompt, model, extra_key=weight_fingerprint)
    if cached:
        return cached

    if "key_index" not in session:
        session["key_index"] = 0

    user_key = session.get("user_groq_key", "").strip() if isinstance(session.get("user_groq_key"), str) else ""
    last_error = None

    # 🔹 Step 2: Try user-provided key
    if user_key:
        try:
            response = try_call_llm(prompt, user_key, model, temperature)
            set_cached_response(prompt, model, response, extra_key=weight_fingerprint)
            increment_key_usage(user_key)
            return response
        except Exception as e:
            reason = "quota" if any(w in str(e).lower() for w in ["quota", "rate limit", "429"]) else "error"
            mark_key_failure(user_key, reason)
            last_error = e

    # 🔹 Step 3: Rotate through admin keys
    admin_keys = get_healthy_keys(load_groq_api_keys())
    if admin_keys:
        start_index = session["key_index"] % len(admin_keys)
        for offset in range(len(admin_keys)):
            idx = (start_index + offset) % len(admin_keys)
            key = admin_keys[idx]
            try:
                response = try_call_llm(prompt, key, model, temperature)
                set_cached_response(prompt, model, response, extra_key=weight_fingerprint)
                increment_key_usage(key)
                clear_key_failure(key)
                session["key_index"] = (idx + 1) % len(admin_keys)
                return response
            except Exception as e:
                reason = "quota" if any(w in str(e).lower() for w in ["quota", "rate limit", "429"]) else "error"
                mark_key_failure(key, reason)
                last_error = e

    # 🔹 All keys exhausted — raise so callers can show a proper UI error
    raise RuntimeError(
        f"LLM unavailable — all API keys failed or are in cooldown. "
        f"Last error: {last_error or 'No healthy API keys found'}"
    )
