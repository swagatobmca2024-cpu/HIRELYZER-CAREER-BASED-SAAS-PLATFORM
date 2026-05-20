import psycopg2
import psycopg2.extras
import bcrypt
import streamlit as st
from datetime import datetime, timedelta
import pytz
import re
import os
import secrets
import threading
import smtplib
import uuid
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
import dns.resolver


# ── Connection management (isolated — never touches other modules' connections) ─
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

    FIX v3: After a successful SELECT 1 liveness check, we now call rollback()
    inside a try/except so that any lingering aborted transaction is cleared
    before the connection is returned.  Previously a failed rollback() here
    would leave the connection in InFailedSqlTransaction, causing
    set_session/autocommit changes to raise ProgrammingError.
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
                # Always rollback after liveness check to discard any open/aborted txn
                try:
                    conn.rollback()
                except Exception:
                    need_reconnect = True
                    try:
                        conn.close()
                    except Exception:
                        pass
            except Exception:
                need_reconnect = True
                try:
                    conn.close()
                except Exception:
                    pass

        if need_reconnect:
            _user_conn_holder["conn"] = _make_user_connection()

        return _user_conn_holder["conn"]


def _reset_conn_to_default():
    """
    Ensure the connection is in a clean, non-autocommit state.
    Call this as a finally-guard whenever autocommit is toggled.
    """
    conn = _user_conn_holder.get("conn")
    if conn is None:
        return
    try:
        # Rollback any open/aborted transaction first — required before
        # changing autocommit, otherwise psycopg2 raises
        # "set_session cannot be used inside a transaction".
        conn.rollback()
    except Exception:
        pass
    try:
        conn.autocommit = False
    except Exception:
        # Connection is broken — drop it so the next call reconnects
        try:
            conn.close()
        except Exception:
            pass
        _user_conn_holder["conn"] = None


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
        email        TEXT UNIQUE
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
    CREATE TABLE IF NOT EXISTS scam_feedback (
        id           SERIAL PRIMARY KEY,
        username     TEXT NOT NULL,
        job_title    TEXT,
        company      TEXT,
        verdict      TEXT,
        blended_score INTEGER,
        rating       TEXT NOT NULL,
        submitted_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
    );
    CREATE INDEX IF NOT EXISTS idx_scam_feedback_user
        ON scam_feedback (username, submitted_at DESC);
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
    CREATE TABLE IF NOT EXISTS scam_analysis_history (
        id          SERIAL PRIMARY KEY,
        username    TEXT NOT NULL,
        job_title   TEXT,
        company     TEXT,
        score       INTEGER,
        verdict     TEXT,
        analysed_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
        is_deleted  BOOLEAN NOT NULL DEFAULT FALSE
    );
    CREATE INDEX IF NOT EXISTS idx_scam_history_user
        ON scam_analysis_history (username, analysed_at DESC);
    """
    conn = _conn()
    try:
        # ── FIX v3: rollback() BEFORE flipping autocommit ──────────────────
        # psycopg2 raises "set_session cannot be used inside a transaction"
        # if autocommit is changed while a transaction (even an aborted one)
        # is still open on the connection.  A rollback() always clears that,
        # whether the previous state was clean, mid-transaction, or aborted.
        try:
            conn.rollback()
        except Exception:
            pass

        conn.autocommit = True
        try:
            with conn.cursor() as cur:
                cur.execute(ddl)
                # Migration: add is_deleted column to existing tables
                try:
                    cur.execute(
                        "ALTER TABLE scam_analysis_history "
                        "ADD COLUMN is_deleted BOOLEAN NOT NULL DEFAULT FALSE"
                    )
                except psycopg2.errors.DuplicateColumn:
                    pass  # column already exists — safe to ignore
                except Exception:
                    pass
        finally:
            # ── FIX v3: restore autocommit=False in a finally block ────────
            # Previously this lived only in the except branch, so a mid-DDL
            # error would leave autocommit=True for the rest of the session,
            # silently skipping commits on all subsequent DML.
            _reset_conn_to_default()

        # Prune stale rows — DML, run in a normal transaction after DDL.
        with conn.cursor() as cur:
            cur.execute("DELETE FROM feature_usage WHERE used_at < NOW() - INTERVAL '2 hours'")
            cur.execute("DELETE FROM login_attempts WHERE attempted_at < NOW() - INTERVAL '15 minutes'")
        conn.commit()

    except Exception as e:
        # Guarantee the connection is back in a clean state no matter what.
        _reset_conn_to_default()
        st.error(f"Error creating tables: {e}")


# ── OTP helpers ───────────────────────────────────────────────────────────────

def generate_otp():
    return str(secrets.randbelow(900000) + 100000)


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
            server.quit()
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
    """
    if '@' in username_or_email:
        sql = "SELECT username, password, email FROM users WHERE email = %s"
    else:
        sql = "SELECT username, password, email FROM users WHERE username = %s"

    row = _execute(sql, (username_or_email,), fetch="one")
    if not row:
        _record_failed_login(username_or_email)
        return "bad_creds", "❌ Invalid credentials. Please try again.", None

    stored_hashed = row["password"]
    if not bcrypt.checkpw(password.encode("utf-8"), stored_hashed.encode("utf-8")):
        _record_failed_login(username_or_email)
        return "bad_creds", "❌ Invalid credentials. Please try again.", None

    actual_username = row["username"]
    email = row["email"]

    if not email:
        return "no_email", "⚠️ No email linked to this account. Contact support.", None

    token = str(uuid.uuid4())
    try:
        _execute(
            "INSERT INTO login_tokens (token, username) VALUES (%s, %s)",
            (token, actual_username),
        )
    except Exception as e:
        return "email_fail", f"❌ Could not create login token: {e}", None

    if not _send_login_link_email(email, actual_username, token):
        return "email_fail", "❌ Failed to send login email. Please try again.", None

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

    created_at = row["created_at"]
    now_utc = datetime.now(pytz.utc)
    if isinstance(created_at, datetime) and created_at.tzinfo is None:
        created_at = pytz.utc.localize(created_at)
    age_seconds = (now_utc - created_at).total_seconds()
    if age_seconds > 600:
        return False, "⏱️ Login link has expired (10 min limit). Please log in again."

    username = row["username"]

    try:
        _execute(
            "UPDATE login_tokens SET used = TRUE WHERE token = %s",
            (token,),
        )
    except Exception:
        pass  # non-fatal

    st.session_state.username = username
    st.session_state.authenticated = True

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

MAX_LOGIN_ATTEMPTS = 5
LOCKOUT_WINDOW_SECONDS = 900


def _resolve_canonical_key(username_or_email: str) -> str:
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
    return username_or_email.lower()


def _record_failed_login(identifier: str):
    try:
        key = _resolve_canonical_key(identifier)
        _execute(
            "INSERT INTO login_attempts (identifier) VALUES (%s)",
            (key,),
        )
    except Exception:
        pass


def _clear_failed_logins(identifier: str):
    try:
        key = _resolve_canonical_key(identifier)
        _execute(
            "DELETE FROM login_attempts WHERE identifier = %s",
            (key,),
        )
    except Exception:
        pass


def check_brute_force(identifier: str):
    try:
        key = _resolve_canonical_key(identifier)
        row = _execute(
            """
            SELECT COUNT(*) AS cnt FROM login_attempts
            WHERE identifier = %s
              AND attempted_at > NOW() - INTERVAL '15 minutes'
            """,
            (key,),
            fetch="one",
        )
        count = row["cnt"] if row else 0
    except Exception:
        return True, ""

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
        sql = "SELECT username, password FROM users WHERE email = %s"
    else:
        sql = "SELECT username, password FROM users WHERE username = %s"

    row = _execute(sql, (username_or_email,), fetch="one")
    if row:
        actual_username = row["username"]
        stored_hashed   = row["password"]

        if bcrypt.checkpw(password.encode('utf-8'), stored_hashed.encode('utf-8')):
            _clear_failed_logins(actual_username)
            st.session_state.username = actual_username
            return True, None

    _record_failed_login(username_or_email)
    return False, None


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
        WHERE action = 'login' AND DATE(timestamp::timestamp) = %s
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


def get_user_email_by_username(username: str) -> str:
    try:
        row = _execute(
            "SELECT email FROM users WHERE username = %s", (username,), fetch="one"
        )
        return row["email"] if row and row["email"] else ""
    except Exception:
        return ""


def send_analysis_email(
    to_email: str,
    candidate_name: str,
    pdf_bytes,
    docx_bytes,
    resume_filename: str,
) -> bool:
    try:
        import smtplib
        from email.mime.multipart import MIMEMultipart
        from email.mime.text import MIMEText
        from email.mime.base import MIMEBase
        from email import encoders as _enc

        sender_email    = st.secrets["email_address"]
        sender_password = st.secrets["email_password"]

        msg = MIMEMultipart()
        msg["From"]    = sender_email
        msg["To"]      = to_email
        msg["Subject"] = f"HIRELYZER — Resume Analysis Report for {candidate_name}"

        body = f"""\
Hello,

Your resume analysis on HIRELYZER has completed. Please find attached:

  1. Full Analysis Report (PDF)  — ATS scores, bias analysis, detailed feedback
  2. Optimised Resume (DOCX)     — Modern ATS template, bias-free rewrite

Candidate analysed : {candidate_name}
Original file      : {resume_filename}

These files were generated automatically after your analysis session.
No action is required — this email is for your records.

Best regards,
HIRELYZER Team
"""
        msg.attach(MIMEText(body, "plain"))

        if pdf_bytes is not None:
            pdf_bytes.seek(0)
            pdf_part = MIMEBase("application", "octet-stream")
            pdf_part.set_payload(pdf_bytes.read())
            _enc.encode_base64(pdf_part)
            safe_name = re.sub(r"[^\w\-.]", "_", candidate_name or "candidate")
            pdf_part.add_header(
                "Content-Disposition",
                "attachment",
                filename=f"{safe_name}_analysis_report.pdf",
            )
            msg.attach(pdf_part)

        if docx_bytes is not None:
            docx_bytes.seek(0)
            docx_part = MIMEBase("application", "octet-stream")
            docx_part.set_payload(docx_bytes.read())
            _enc.encode_base64(docx_part)
            safe_name = re.sub(r"[^\w\-.]", "_", candidate_name or "candidate")
            docx_part.add_header(
                "Content-Disposition",
                "attachment",
                filename=f"{safe_name}_optimised_resume_modern.docx",
            )
            msg.attach(docx_part)

        server = smtplib.SMTP("smtp.gmail.com", 587)
        try:
            server.starttls()
            server.login(sender_email, sender_password)
            server.sendmail(sender_email, to_email, msg.as_string())
        finally:
            server.quit()

        return True

    except Exception:
        return False


def update_password_by_email(email, new_password):
    if not is_strong_password(new_password):
        st.error("Password must be at least 8 characters long and include uppercase, lowercase, number, and special character.")
        return False

    hashed_password = bcrypt.hashpw(new_password.encode('utf-8'), bcrypt.gensalt()).decode('utf-8')
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
    "scam_detector": 3,
}


def get_usage_count_last_hour(username: str, feature: str) -> int:
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
        return 0


def record_feature_usage(username: str, feature: str):
    try:
        _execute(
            "INSERT INTO feature_usage (username, feature) VALUES (%s, %s)",
            (username, feature),
        )
    except Exception:
        pass


def check_and_gate_feature(username: str, feature: str):
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


# ── Scam analysis history (persistent across sessions) ───────────────────────

def save_scam_analysis(username: str, job_title: str, company: str, score: int, verdict: str) -> int | None:
    try:
        ist = pytz.timezone("Asia/Kolkata")
        now_ist = datetime.now(ist)

        new_row = _execute(
            """
            INSERT INTO scam_analysis_history
                (username, job_title, company, score, verdict, analysed_at)
            VALUES (%s, %s, %s, %s, %s, %s)
            RETURNING id
            """,
            (username, job_title or "Untitled", company or "Unknown",
             int(score), verdict, now_ist),
            fetch="one",
        )
        new_id = new_row["id"] if new_row else None

        return new_id
    except Exception:
        return None


def load_scam_history(username: str) -> list[dict]:
    try:
        rows = _execute(
            """
            SELECT id, job_title, company, score, verdict,
                   TO_CHAR(analysed_at AT TIME ZONE 'Asia/Kolkata', 'FMDD Mon HH24:MI') AS time
            FROM scam_analysis_history
            WHERE username  = %s
              AND is_deleted = FALSE
            ORDER BY analysed_at DESC
            LIMIT 5
            """,
            (username,),
            fetch="all",
        )
        return [
            {
                "id":      r["id"],
                "title":   r["job_title"],
                "company": r["company"],
                "score":   r["score"],
                "verdict": r["verdict"],
                "time":    r["time"],
            }
            for r in (rows or [])
        ]
    except Exception:
        return []


def soft_delete_scam_analysis(username: str, record_id: int) -> bool:
    try:
        _execute(
            """
            UPDATE scam_analysis_history
            SET is_deleted = TRUE
            WHERE id = %s AND username = %s
            """,
            (record_id, username),
        )
        return True
    except Exception:
        return False


def soft_delete_all_scam_history(username: str):
    try:
        _execute(
            """
            UPDATE scam_analysis_history
            SET is_deleted = TRUE
            WHERE username = %s AND is_deleted = FALSE
            """,
            (username,),
        )
    except Exception:
        pass


def delete_all_scam_history(username: str):
    pass  # do NOT delete from DB — records are permanent
