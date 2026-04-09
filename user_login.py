import psycopg2
import psycopg2.extras
import bcrypt
import streamlit as st
from datetime import datetime, timedelta
import pytz
import re
import os
import random
import threading
import smtplib
import uuid
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
import dns.resolver


# ── Connection management (isolated — never touches other modules' connections) ─
# FIX: replaced st.cache_resource singleton + .clear() with a module-level holder.
# st.cache_resource.clear() nukes ALL cached resources app-wide, which killed
# llm_manager and db_manager connections whenever a login DB hiccup occurred.

_user_conn_holder: dict = {"conn": None}
_user_reconnect_lock = threading.Lock()


def _make_user_connection():
    """Open a fresh psycopg2 connection for user_login operations."""
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
    """
    Return a live psycopg2 connection.

    FIX: Liveness check is a real SELECT 1 round-trip — the old code read
         conn.isolation_level which is a pure Python attribute and never
         touches the socket, so stale connections passed silently.
    FIX: Reconnect only replaces THIS module's connection; does NOT call
         st.cache_resource.clear() which would destroy all other connections.
    """
    with _user_reconnect_lock:
        conn = _user_conn_holder.get("conn")
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
            _user_conn_holder["conn"] = _make_user_connection()

        return _user_conn_holder["conn"]


def _execute(sql: str, params=None, fetch: str = "none"):
    """
    Run a SQL statement inside an implicit transaction.
    fetch: 'one' | 'all' | 'none'
    Commits on success, rolls back on error.
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


# ── Utility ──────────────────────────────────────────────────────────────────

def get_ist_time():
    ist = pytz.timezone("Asia/Kolkata")
    return datetime.now(ist)


def is_strong_password(password):
    return (
        len(password) >= 8 and
        re.search(r'[A-Z]', password) and
        re.search(r'[a-z]', password) and
        re.search(r'[0-9]', password) and
        re.search(r'[!@#$%^&*(),.?":{}|<>]', password)
    )


def is_valid_email(email):
    return re.match(r'^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$', email) is not None


def domain_has_mx_record(email):
    try:
        domain = email.split('@')[1]
        dns.resolver.resolve(domain, 'MX')
        return True
    except (dns.resolver.NoAnswer, dns.resolver.NXDOMAIN,
            dns.resolver.NoNameservers, IndexError):
        return False
    except Exception:
        return True


# ── Existence checks ─────────────────────────────────────────────────────────

def username_exists(username):
    row = _execute(
        "SELECT 1 FROM users WHERE username = %s", (username,), fetch="one"
    )
    return row is not None


def email_exists(email):
    row = _execute(
        "SELECT 1 FROM users WHERE email = %s", (email,), fetch="one"
    )
    return row is not None


# ── Table creation ───────────────────────────────────────────────────────────

def create_user_table():
    ddl = """
    CREATE TABLE IF NOT EXISTS users (
        id           SERIAL PRIMARY KEY,
        username     TEXT UNIQUE NOT NULL,
        password     TEXT NOT NULL,
        email        TEXT UNIQUE,
        groq_api_key TEXT
    );
    CREATE TABLE IF NOT EXISTS user_logs (
        id        SERIAL PRIMARY KEY,
        username  TEXT NOT NULL,
        action    TEXT NOT NULL,
        timestamp TEXT NOT NULL
    );
    CREATE TABLE IF NOT EXISTS feature_usage (
        id       SERIAL PRIMARY KEY,
        username TEXT NOT NULL,
        feature  TEXT NOT NULL,
        used_at  TIMESTAMPTZ NOT NULL DEFAULT NOW()
    );
    CREATE INDEX IF NOT EXISTS idx_feature_usage_lookup
        ON feature_usage (username, feature, used_at);
    CREATE TABLE IF NOT EXISTS login_tokens (
        id         SERIAL PRIMARY KEY,
        token      TEXT UNIQUE NOT NULL,
        username   TEXT NOT NULL,
        created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
        used       BOOLEAN NOT NULL DEFAULT FALSE
    );
    CREATE INDEX IF NOT EXISTS idx_login_tokens_token ON login_tokens (token);
    CREATE TABLE IF NOT EXISTS login_attempts (
        id         SERIAL PRIMARY KEY,
        identifier TEXT NOT NULL,
        attempted_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
    );
    CREATE INDEX IF NOT EXISTS idx_login_attempts_lookup
        ON login_attempts (identifier, attempted_at);
    """
    conn = _conn()
    try:
        with conn.cursor() as cur:
            cur.execute(ddl)
            # Prune feature_usage rows older than 2 hours — they are only needed
            # for the 1-hour rate-limit window. Without this the table grows forever.
            cur.execute("DELETE FROM feature_usage WHERE used_at < NOW() - INTERVAL '2 hours'")
            # Prune login_attempts older than 15 minutes — only needed for lockout window.
            cur.execute("DELETE FROM login_attempts WHERE attempted_at < (NOW() AT TIME ZONE 'Asia/Kolkata') - INTERVAL '15 minutes'")
        conn.commit()
    except Exception as e:
        # FIX: rollback on the SAME connection object, not a fresh _conn() call
        try:
            conn.rollback()
        except Exception:
            pass
        st.error(f"Error creating tables: {e}")


# ── OTP helpers ───────────────────────────────────────────────────────────────

def generate_otp():
    return str(random.randint(100000, 999999))


def _send_email(to_email: str, subject: str, body: str) -> bool:
    """Internal SMTP helper used by both registration and password reset."""
    try:
        sender_email = st.secrets["email_address"]
        sender_password = st.secrets["email_password"]

        msg = MIMEMultipart()
        msg['From'] = sender_email
        msg['To'] = to_email
        msg['Subject'] = subject
        msg.attach(MIMEText(body, 'plain'))

        server = smtplib.SMTP('smtp.gmail.com', 587)
        try:
            server.starttls()
            server.login(sender_email, sender_password)
            server.sendmail(sender_email, to_email, msg.as_string())
        finally:
            server.quit()  # always close — prevents SMTP connection leak on exception
        return True
    except smtplib.SMTPException as e:
        st.error(f"SMTP Error: {e}")
        return False
    except Exception as e:
        st.error(f"Error sending email: {e}")
        return False


def send_registration_otp(to_email: str, otp: str) -> bool:
    body = f"""Hello,

Welcome! Your verification OTP for registration is: {otp}

This OTP will expire in 3 minutes.

If you did not request this registration, please ignore this email.

Best regards,
Resume App Team
"""
    return _send_email(to_email, "Email Verification OTP", body)


def send_email_otp(to_email: str, otp: str) -> bool:
    body = f"""Hello,

Your OTP for password reset is: {otp}

This OTP will expire in 3 minutes.

If you did not request this password reset, please ignore this email.

Best regards,
Resume App Team
"""
    return _send_email(to_email, "Password Reset OTP", body)


# ── Registration ─────────────────────────────────────────────────────────────

def add_user(username, password, email=None):
    """
    Validate details and send OTP.  Does NOT write to DB yet.
    Returns (success: bool, message: str).
    """
    if not is_strong_password(password):
        return False, "⚠ Password must be at least 8 characters long and include uppercase, lowercase, number, and special character."
    if not email:
        return False, "⚠ Email is required for registration."
    if not is_valid_email(email):
        return False, "⚠ Invalid email format. Please provide a valid email address."
    if not domain_has_mx_record(email):
        return False, "⚠ Email domain does not exist or has no valid mail server."
    if email_exists(email):
        return False, "🚫 Email already exists. Please use a different email."
    if username_exists(username):
        return False, "🚫 Username already exists."

    otp = generate_otp()
    if not send_registration_otp(email, otp):
        return False, "❌ Failed to send OTP email. Please check your email address and try again."

    st.session_state.pending_registration = {
        'username': username,
        'password': password,
        'email': email,
        'otp': otp,
        'timestamp': get_ist_time(),
    }
    return True, "📧 Verification email sent! Please check your inbox for OTP."


def complete_registration(entered_otp):
    """
    Verify OTP and insert the new user into Supabase.
    Returns (success: bool, message: str).
    """
    if 'pending_registration' not in st.session_state:
        return False, "⚠ No pending registration found. Please start registration again."

    pending = st.session_state.pending_registration
    stored_otp = pending['otp']
    timestamp  = pending['timestamp']

    time_elapsed = (get_ist_time() - timestamp).total_seconds()
    if time_elapsed > 180:
        del st.session_state.pending_registration
        return False, "⏱ OTP has expired. Please register again."
    if entered_otp != stored_otp:
        return False, "❌ Invalid OTP. Please try again."

    username        = pending['username']
    password        = pending['password']
    email           = pending['email']
    hashed_password = bcrypt.hashpw(password.encode('utf-8'), bcrypt.gensalt()).decode('utf-8')

    try:
        _execute(
            "INSERT INTO users (username, password, email) VALUES (%s, %s, %s)",
            (username, hashed_password, email),
        )
        del st.session_state.pending_registration
        return True, "✅ Registration completed! You can now login."
    except psycopg2.errors.UniqueViolation as e:
        err = str(e)
        if 'username' in err:
            return False, "🚫 Username already exists."
        elif 'email' in err:
            return False, "🚫 Email already exists."
        return False, "🚫 Registration failed. Username or email already exists."
    except Exception as e:
        return False, f"❌ Database error: {e}"


# ── Magic Link Login ──────────────────────────────────────────────────────────

def _get_app_url() -> str:
    """Return the base app URL from secrets, falling back to localhost."""
    try:
        return st.secrets.get("APP_URL", "http://localhost:8501").rstrip("/")
    except Exception:
        return "http://localhost:8501"


def _send_login_link_email(to_email: str, username: str, token: str) -> bool:
    """Email a magic login link to the user."""
    app_url = _get_app_url()
    link = f"{app_url}/?login_token={token}"
    body = f"""Hello {username},

Someone (hopefully you!) requested a login to HIRELYZER.

Click the link below to confirm and complete your login:

{link}

This link will expire in 10 minutes and can only be used once.

If you did not attempt to log in, please ignore this email — your account remains secure.

Best regards,
HIRELYZER Team
"""
    return _send_email(to_email, "🔐 Confirm Your HIRELYZER Login", body)


def send_login_link(username_or_email: str, password: str):
    """
    Verify credentials, then send a magic login link.
    Returns (status, message, username_or_None).

    status values:
      'link_sent'   — credentials OK, email sent
      'bad_creds'   — wrong username/password
      'no_email'    — user has no email on record
      'email_fail'  — credentials OK but SMTP failed
    """
    # Resolve username + password + email
    if '@' in username_or_email:
        sql = "SELECT username, password, email, groq_api_key FROM users WHERE email = %s"
    else:
        sql = "SELECT username, password, email, groq_api_key FROM users WHERE username = %s"

    row = _execute(sql, (username_or_email,), fetch="one")
    if not row:
        return "bad_creds", "❌ Invalid credentials. Please try again.", None

    stored_hashed = row["password"]
    if not bcrypt.checkpw(password.encode("utf-8"), stored_hashed.encode("utf-8")):
        return "bad_creds", "❌ Invalid credentials. Please try again.", None

    actual_username = row["username"]
    email = row["email"]
    groq_key = row["groq_api_key"]

    if not email:
        return "no_email", "⚠️ No email linked to this account. Contact support.", None

    # Generate a secure token and persist it
    token = str(uuid.uuid4())
    try:
        _execute(
            "INSERT INTO login_tokens (token, username) VALUES (%s, %s)",
            (token, actual_username),
        )
    except Exception as e:
        return "email_fail", f"❌ Could not create login token: {e}", None

    # Send the email
    if not _send_login_link_email(email, actual_username, token):
        return "email_fail", "❌ Failed to send login email. Please try again.", None

    # Stash groq_key in session so verify_login_token can restore it
    st.session_state["_pending_login_groq_key"] = groq_key or ""
    return "link_sent", "📧 Login link sent! Check your inbox and click the link to sign in.", actual_username


def verify_login_token(token: str):
    """
    Validate a magic login token from the URL query param.
    If valid: sets session state and returns (True, username).
    If invalid/expired/used: returns (False, error_message).
    Token TTL = 10 minutes.
    """
    if not token:
        return False, "⚠️ No login token provided."

    row = _execute(
        "SELECT username, created_at, used FROM login_tokens WHERE token = %s",
        (token,),
        fetch="one",
    )
    if not row:
        return False, "❌ Invalid or expired login link."
    if row["used"]:
        return False, "⚠️ This login link has already been used. Please log in again."

    # Check expiry (10 minutes)
    created_at = row["created_at"]
    # created_at from Supabase is tz-aware UTC
    now_utc = datetime.now(pytz.utc)
    if isinstance(created_at, datetime) and created_at.tzinfo is None:
        created_at = pytz.utc.localize(created_at)
    age_seconds = (now_utc - created_at).total_seconds()
    if age_seconds > 600:
        return False, "⏱️ Login link has expired (10 min limit). Please log in again."

    username = row["username"]

    # Mark token as used
    try:
        _execute(
            "UPDATE login_tokens SET used = TRUE WHERE token = %s",
            (token,),
        )
    except Exception:
        pass  # non-fatal — proceed with login

    # Fetch groq key for session
    key_row = _execute(
        "SELECT groq_api_key FROM users WHERE username = %s", (username,), fetch="one"
    )
    groq_key = key_row["groq_api_key"] if key_row and key_row["groq_api_key"] else ""

    # Set session state
    st.session_state.username = username
    st.session_state.authenticated = True
    st.session_state.user_groq_key = groq_key

    return True, username


def cleanup_expired_login_tokens():
    """Delete login tokens older than 1 hour. Call once on app startup."""
    try:
        _execute(
            "DELETE FROM login_tokens WHERE created_at < NOW() - INTERVAL '1 hour'"
        )
    except Exception:
        pass  # non-fatal


# ── Brute-force protection ────────────────────────────────────────────────────

MAX_LOGIN_ATTEMPTS = 5          # max failures allowed
LOCKOUT_WINDOW_SECONDS = 900    # 15-minute rolling window


def _resolve_canonical_key(username_or_email: str) -> str:
    """
    Always resolve to the lowercase username so that logging in with
    an email vs username always hits the same counter in login_attempts.
    Falls back to the raw input (lowercased) if user doesn't exist —
    this still prevents enumeration since the counter tracks the typed value.
    """
    try:
        if '@' in username_or_email:
            row = _execute(
                "SELECT username FROM users WHERE email = %s",
                (username_or_email.lower(),),
                fetch="one",
            )
        else:
            row = _execute(
                "SELECT username FROM users WHERE username = %s",
                (username_or_email.lower(),),
                fetch="one",
            )
        if row:
            return row["username"].lower()
    except Exception:
        pass
    return username_or_email.lower()  # unknown user — track raw input


def _record_failed_login(identifier: str):
    """Log one failed login attempt using the canonical username key, timestamped in IST."""
    try:
        key = _resolve_canonical_key(identifier)
        ist_now = get_ist_time()
        _execute(
            "INSERT INTO login_attempts (identifier, attempted_at) VALUES (%s, %s)",
            (key, ist_now),
        )
    except Exception:
        pass  # non-fatal


def _clear_failed_logins(identifier: str):
    """Remove all failed attempts after a successful login."""
    try:
        key = _resolve_canonical_key(identifier)
        _execute(
            "DELETE FROM login_attempts WHERE identifier = %s",
            (key,),
        )
    except Exception:
        pass  # non-fatal


def check_brute_force(identifier: str):
    """
    Check if the identifier (username or email) is locked out.
    Resolves to canonical username first so email/username share one counter.
    Returns (allowed: bool, message: str).
    """
    try:
        key = _resolve_canonical_key(identifier)
        row = _execute(
            """
            SELECT COUNT(*) AS cnt FROM login_attempts
            WHERE identifier = %s
              AND attempted_at > (NOW() AT TIME ZONE 'Asia/Kolkata') - INTERVAL '15 minutes'
            """,
            (key,),
            fetch="one",
        )
        count = row["cnt"] if row else 0
    except Exception:
        return True, ""  # fail open — don't block on DB hiccup

    if count >= MAX_LOGIN_ATTEMPTS:
        remaining = LOCKOUT_WINDOW_SECONDS // 60
        return False, (
            f"🔒 Too many failed attempts. Account temporarily locked — "
            f"please try again in {remaining} minutes."
        )
    return True, ""


# ── Authentication ────────────────────────────────────────────────────────────

def verify_user(username_or_email, password):
    if '@' in username_or_email:
        sql = "SELECT username, password, groq_api_key FROM users WHERE email = %s"
    else:
        sql = "SELECT username, password, groq_api_key FROM users WHERE username = %s"

    row = _execute(sql, (username_or_email,), fetch="one")
    if row:
        actual_username = row["username"]
        stored_hashed   = row["password"]
        stored_key      = row["groq_api_key"]

        if bcrypt.checkpw(password.encode('utf-8'), stored_hashed.encode('utf-8')):
            _clear_failed_logins(actual_username)
            st.session_state.username      = actual_username
            st.session_state.user_groq_key = stored_key or ""
            return True, stored_key

    _record_failed_login(username_or_email)
    return False, None


# ── API key management ────────────────────────────────────────────────────────

def save_user_api_key(username, api_key):
    _execute(
        "UPDATE users SET groq_api_key = %s WHERE username = %s",
        (api_key, username),
    )
    st.session_state.user_groq_key = api_key


def get_user_api_key(username):
    row = _execute(
        "SELECT groq_api_key FROM users WHERE username = %s", (username,), fetch="one"
    )
    return row["groq_api_key"] if row and row["groq_api_key"] else None


# ── Logging ───────────────────────────────────────────────────────────────────

def log_user_action(username, action):
    timestamp = get_ist_time().strftime("%Y-%m-%d %H:%M:%S")
    _execute(
        "INSERT INTO user_logs (username, action, timestamp) VALUES (%s, %s, %s)",
        (username, action, timestamp),
    )


# ── Stats ─────────────────────────────────────────────────────────────────────

def get_total_registered_users():
    row = _execute("SELECT COUNT(*) AS cnt FROM users", fetch="one")
    return row["cnt"] if row else 0


def get_logins_today():
    today = get_ist_time().strftime('%Y-%m-%d')
    row = _execute(
        """
        SELECT COUNT(*) AS cnt FROM user_logs
        WHERE action = 'login' AND DATE(timestamp) = %s
        """,
        (today,),
        fetch="one",
    )
    return row["cnt"] if row else 0


def get_all_user_logs():
    rows = _execute(
        "SELECT username, action, timestamp FROM user_logs ORDER BY timestamp DESC",
        fetch="all",
    )
    return [(r["username"], r["action"], r["timestamp"]) for r in (rows or [])]


# ── Forgot password ───────────────────────────────────────────────────────────

def get_user_by_email(email):
    row = _execute(
        "SELECT username FROM users WHERE email = %s", (email,), fetch="one"
    )
    return row["username"] if row else None


def update_password_by_email(email, new_password):
    if not is_strong_password(new_password):
        st.error("Password must be at least 8 characters long and include uppercase, lowercase, number, and special character.")
        return False

    hashed_password = bcrypt.hashpw(new_password.encode('utf-8'), bcrypt.gensalt()).decode('utf-8')
    # FIX: acquire conn once and reuse it for both execute and rollback.
    # Old code called _conn() again in the except block which could return a
    # brand-new connection and rollback nothing, leaving the original transaction
    # in a broken state (InFailedSqlTransaction on all subsequent calls).
    conn = _conn()
    try:
        with conn.cursor() as cur:
            cur.execute(
                "UPDATE users SET password = %s WHERE email = %s",
                (hashed_password, email),
            )
            updated = cur.rowcount
        conn.commit()
        return updated > 0
    except Exception as e:
        try:
            conn.rollback()
        except Exception:
            pass
        st.error(f"Database error: {e}")
        return False


# ── Feature usage rate limiting ───────────────────────────────────────────────

USAGE_LIMITS = {
    "resume_analyzer": 2,
    "ai_coach": 2,
}


def get_usage_count_last_hour(username: str, feature: str) -> int:
    """Return how many times username used feature in the last 60 minutes."""
    try:
        row = _execute(
            """
            SELECT COUNT(*) AS cnt FROM feature_usage
            WHERE username = %s
              AND feature  = %s
              AND used_at  > NOW() - INTERVAL '1 hour'
            """,
            (username, feature),
            fetch="one",
        )
        return row["cnt"] if row else 0
    except Exception:
        return 0  # fail open — don't block users due to a DB hiccup


def record_feature_usage(username: str, feature: str):
    """Log one usage event. Call AFTER the feature successfully runs."""
    try:
        _execute(
            "INSERT INTO feature_usage (username, feature) VALUES (%s, %s)",
            (username, feature),
        )
    except Exception:
        pass  # non-fatal


def check_and_gate_feature(username: str, feature: str):
    """
    Check if user is within their hourly limit.
    Returns (allowed: bool, message: str).
    Call BEFORE running the feature.
    """
    limit = USAGE_LIMITS.get(feature, 999)
    count = get_usage_count_last_hour(username, feature)
    feature_label = "AI Coach" if feature == "ai_coach" else feature.replace('_', ' ').title()
    if count >= limit:
        svg_block = (
            '<svg width="14" height="14" viewBox="0 0 24 24" fill="none" '
            'stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" '
            'style="display:inline-block;vertical-align:middle;margin-right:6px;">'
            '<circle cx="12" cy="12" r="10"/>'
            '<line x1="4.93" y1="4.93" x2="19.07" y2="19.07"/>'
            '</svg>'
        )
        msg = (
            f'<div style="display:flex;align-items:center;font-size:0.88rem;color:#fca5a5;'
            f'background:rgba(251,113,133,0.08);border:1px solid rgba(251,113,133,0.25);'
            f'border-radius:8px;padding:10px 14px;font-family:-apple-system,sans-serif;">'
            f'{svg_block} You have reached the <b style="margin:0 4px;">{feature_label}</b> '
            f'limit of <b style="margin:0 4px;">{limit}</b> uses per hour. Please try again later.</div>'
        )
        return False, msg
    return True, f"{count}/{limit} uses this hour."
