# =============================================================
# tab3_backend.py
# All backend logic for Tab 3: database (Supabase/psycopg2),
# RapidAPI job fetching, URL builders, and analytics queries.
# No Streamlit UI rendering happens here.
# =============================================================

import uuid
import urllib.parse
import re
import html as _html
from datetime import datetime
from zoneinfo import ZoneInfo

import requests
import psycopg2
import psycopg2.extras
import pandas as pd
import streamlit as st

from tab3_data import JOB_TITLES, LOCATIONS


# ── RapidAPI Configuration (from Streamlit secrets) ──────────
RAPID_API_KEY  = st.secrets["rapidapi"]["key"]
RAPID_API_HOST = st.secrets["rapidapi"]["host"]


# ═══════════════════════════════════════════════════════════════
# DATABASE — Supabase / PostgreSQL
# ═══════════════════════════════════════════════════════════════

@st.cache_resource(show_spinner=False)
def _get_pg_conn():
    """
    Return a *persistent* psycopg2 connection that is reused across reruns.
    st.cache_resource guarantees this is created only once per server process,
    eliminating the repeated-connection anti-pattern that plagues Streamlit apps.
    autocommit=True avoids dangling transactions on cached connections.
    """
    conn = psycopg2.connect(
        host=st.secrets["SUPABASE_HOST"],
        dbname=st.secrets["SUPABASE_DB"],
        user=st.secrets["SUPABASE_USER"],
        password=st.secrets["SUPABASE_PASSWORD"],
        port=int(st.secrets["SUPABASE_PORT"]),
        sslmode="require",
        connect_timeout=10,
    )
    conn.autocommit = True
    return conn


def _pg():
    """
    Return the cached connection, transparently reconnecting if the server
    closed the socket (e.g. after idle timeout on Supabase's pooler).
    """
    conn = _get_pg_conn()
    try:
        # lightweight liveness probe — raises if connection is dead
        conn.cursor().execute("SELECT 1")
    except Exception:
        # evict stale cached resource so next call re-connects
        _get_pg_conn.clear()
        conn = _get_pg_conn()
    return conn


def init_job_search_db():
    """
    Ensure user_jobs table exists in Supabase PostgreSQL.
    Uses SERIAL (auto-increment) and TIMESTAMPTZ so all timestamps are UTC-aware.
    Safe to call on every startup — CREATE TABLE IF NOT EXISTS is idempotent.
    """
    try:
        cur = _pg().cursor()
        cur.execute("""
            CREATE TABLE IF NOT EXISTS user_jobs (
                id        SERIAL PRIMARY KEY,
                username  TEXT        NOT NULL,
                role      TEXT        NOT NULL,
                location  TEXT        NOT NULL,
                platform  TEXT        NOT NULL,
                url       TEXT        NOT NULL,
                company   TEXT        NOT NULL DEFAULT '',
                timestamp TIMESTAMPTZ NOT NULL DEFAULT NOW()
            )
        """)
        # Add company column to existing tables that were created before this change
        # ADD COLUMN IF NOT EXISTS is idempotent — safe to run every startup
        cur.execute("""
            ALTER TABLE user_jobs ADD COLUMN IF NOT EXISTS company TEXT NOT NULL DEFAULT ''
        """)
        # Index for fast per-user lookups (ignored if already exists)
        cur.execute("""
            CREATE INDEX IF NOT EXISTS idx_user_jobs_username
            ON user_jobs (username)
        """)
    except Exception as e:
        st.error(f"Database initialization error: {e}")


def save_job_search(username, role, location, results):
    """Save job search results to Supabase PostgreSQL for the logged-in user."""
    if not username:
        return

    for attempt in range(2):  # retry once on stale connection
        try:
            cur = _pg().cursor()
            now = datetime.now(ZoneInfo('UTC'))
            psycopg2.extras.execute_batch(
                cur,
                """
                INSERT INTO user_jobs (username, role, location, platform, url, company, timestamp)
                VALUES (%s, %s, %s, %s, %s, %s, %s)
                """,
                [
                    (username, role, location,
                     r.get("platform", "Unknown"),
                     r.get("apply_link", "#"),
                     r.get("company", ""),   # ← company name (only set for RapidAPI results)
                     now)
                    for r in results
                ],
                page_size=50,
            )
            # Invalidate ALL cached reads so dashboard updates immediately
            get_saved_job_searches.clear()
            get_total_saved_searches_count.clear()
            get_available_platforms.clear()
            fetch_analytics_data.clear()   # ← clears both My + Global analytics
            return  # success — exit retry loop
        except psycopg2.OperationalError:
            _get_pg_conn.clear()           # force reconnect on next attempt
            if attempt == 1:
                st.error("Database connection lost while saving. Please retry the search.")
        except Exception as e:
            st.error(f"Error saving job search: {e}")
            return


def prune_old_searches(username):
    """Keep only the last 50 saved job searches per user (optional cleanup)."""
    if not username:
        return

    try:
        cur = _pg().cursor()
        cur.execute("""
            DELETE FROM user_jobs
            WHERE username = %s AND id NOT IN (
                SELECT id FROM user_jobs
                WHERE username = %s
                ORDER BY timestamp DESC, id DESC
                LIMIT 50
            )
        """, (username, username))
        get_saved_job_searches.clear()
        get_total_saved_searches_count.clear()
    except Exception as e:
        st.error(f"Error pruning old searches: {e}")


def delete_saved_job_search(search_id):
    """Delete a saved job search by its ID."""
    try:
        cur = _pg().cursor()
        cur.execute("DELETE FROM user_jobs WHERE id = %s", (search_id,))
        get_saved_job_searches.clear()
        get_total_saved_searches_count.clear()
        get_available_platforms.clear()
        fetch_analytics_data.clear()   # ← analytics reflects deletions immediately
    except Exception as e:
        st.error(f"Error deleting job search: {e}")


@st.cache_data(ttl=30, show_spinner=False)
def get_saved_job_searches(username, limit=10, offset=0, platform_filter=None):
    """
    Get saved job searches for a user with filtering and pagination.
    Results are cached for 30 s to prevent repeated DB calls on widget interaction /
    Streamlit reruns that don't change the arguments.
    """
    if not username:
        return []

    try:
        cur = _pg().cursor(cursor_factory=psycopg2.extras.RealDictCursor)

        if platform_filter and platform_filter != "All":
            cur.execute("""
                SELECT id, role, location, platform, url, company, timestamp
                FROM user_jobs
                WHERE username = %s AND platform = %s
                ORDER BY timestamp DESC, id DESC
                LIMIT %s OFFSET %s
            """, (username, platform_filter, limit, offset))
        else:
            cur.execute("""
                SELECT id, role, location, platform, url, company, timestamp
                FROM user_jobs
                WHERE username = %s
                ORDER BY timestamp DESC, id DESC
                LIMIT %s OFFSET %s
            """, (username, limit, offset))

        rows = cur.fetchall()
        return [
            {
                "id":        row["id"],
                "role":      row["role"],
                "location":  row["location"],
                "platform":  row["platform"],
                "url":       row["url"],
                "company":   row["company"] or "",
                # Normalise to a plain UTC-aware datetime for downstream formatting
                "timestamp": row["timestamp"].astimezone(ZoneInfo('UTC')) if row["timestamp"] else None,
            }
            for row in rows
        ]
    except Exception as e:
        st.error(f"Error fetching saved searches: {e}")
        return []


@st.cache_data(ttl=30, show_spinner=False)
def get_total_saved_searches_count(username, platform_filter=None):
    """Get total count of saved searches for pagination (cached 30 s)."""
    if not username:
        return 0

    try:
        cur = _pg().cursor()
        if platform_filter and platform_filter != "All":
            cur.execute(
                "SELECT COUNT(*) FROM user_jobs WHERE username = %s AND platform = %s",
                (username, platform_filter)
            )
        else:
            cur.execute(
                "SELECT COUNT(*) FROM user_jobs WHERE username = %s",
                (username,)
            )
        return cur.fetchone()[0]
    except Exception as e:
        st.error(f"Error getting search count: {e}")
        return 0


@st.cache_data(ttl=60, show_spinner=False)
def get_available_platforms(username):
    """Get distinct platforms the user has searched on (cached 60 s)."""
    if not username:
        return []

    try:
        cur = _pg().cursor()
        cur.execute(
            "SELECT DISTINCT platform FROM user_jobs WHERE username = %s ORDER BY platform",
            (username,)
        )
        return [row[0] for row in cur.fetchall()]
    except Exception as e:
        st.error(f"Error fetching platforms: {e}")
        return []


@st.cache_data(ttl=60, show_spinner=False)
def fetch_analytics_data(scope_username=None):
    """
    Fetch user_jobs rows and convert timestamps to IST (UTC+5:30).
    Cached for 60 s at MODULE LEVEL so the cache actually persists across reruns.
    Returns a pandas DataFrame or empty DataFrame on error.
    """
    try:
        cur = _pg().cursor(cursor_factory=psycopg2.extras.RealDictCursor)
        if scope_username:
            cur.execute(
                "SELECT role, location, platform, timestamp FROM user_jobs WHERE username = %s",
                (scope_username,)
            )
        else:
            cur.execute(
                "SELECT role, location, platform, timestamp FROM user_jobs"
            )
        rows = cur.fetchall()
        df = pd.DataFrame(rows, columns=['role', 'location', 'platform', 'timestamp'])
        if not df.empty:
            df['timestamp'] = pd.to_datetime(df['timestamp'], utc=True, errors='coerce')
            df = df.dropna(subset=['timestamp'])
            df['timestamp_ist'] = df['timestamp'].dt.tz_convert('Asia/Kolkata')
            df['date']    = df['timestamp_ist'].dt.date.astype(str)
            df['hour']    = df['timestamp_ist'].dt.hour
            df['weekday'] = df['timestamp_ist'].dt.day_name()
        return df
    except Exception:
        return pd.DataFrame(columns=['role', 'location', 'platform', 'timestamp', 'date', 'hour', 'weekday'])


# ═══════════════════════════════════════════════════════════════
# API — RapidAPI JSearch + LinkedIn Data
# ═══════════════════════════════════════════════════════════════

def fetch_live_jobs(job_role, location, job_type=None, remote_only=False, results=10):
    url = f"https://{RAPID_API_HOST}/search"
    querystring = {
        "query": f"{job_role} in {location}",
        "page": "1",
        "num_pages": "1",
        "remote_jobs_only": str(remote_only).lower()
    }

    # 🔹 Map UI dropdown values to RapidAPI accepted filters
    type_map = {
        "Full-time": "FULLTIME",
        "Part-time": "PARTTIME",
        "Contract": "CONTRACTOR",
        "Internship": "INTERN",
        "Temporary": "TEMPORARY",
        "Volunteer": "VOLUNTEER"
    }
    if job_type and job_type in type_map:
        querystring["employment_types"] = type_map[job_type]

    headers = {
        "X-RapidAPI-Key": RAPID_API_KEY,
        "X-RapidAPI-Host": RAPID_API_HOST
    }
    try:
        response = requests.get(url, headers=headers, params=querystring)
        if response.status_code == 200:
            return response.json().get("data", [])[:results]
        else:
            return []
    except Exception:
        return []


def fetch_company_by_domain(domain: str):
    """Fetch company information by domain using LinkedIn Data API"""
    url = f"https://linkedin-data-api.p.rapidapi.com/get-company-by-domain?domain={domain}"
    headers = {
        "X-RapidAPI-Key": RAPID_API_KEY,
        "X-RapidAPI-Host": "linkedin-data-api.p.rapidapi.com"
    }
    try:
        response = requests.get(url, headers=headers)
        if response.status_code == 200:
            return response.json()
        else:
            return None
    except Exception:
        return None


def unified_search(job_role, location, experience_level=None, job_type=None, foundit_experience=None):
    results = []

    # 1️⃣ Fetch live jobs from RapidAPI JSearch
    live_jobs = fetch_live_jobs(job_role, location, job_type=job_type, results=5)
    for job in live_jobs:
        results.append({
            "platform": "RapidAPI (Live)",
            "title": clean_html(job.get("job_title", "N/A")),
            "company": clean_html(job.get("employer_name", "Unknown")),
            "location": f"{job.get('job_city','')}, {job.get('job_country','')}",
            "salary": f"{job.get('job_min_salary','NA')} - {job.get('job_max_salary','NA')} {job.get('job_salary_currency','')}",
            "date": job.get("job_posted_at_datetime_utc", "N/A"),
            "type": job.get("job_employment_type","N/A"),
            "remote": "Remote" if job.get("job_is_remote") else "On-site",
            "publisher": clean_html(job.get("job_publisher","N/A")),
            "description": (lambda d: d[:200].rsplit(" ",1)[0]+"..." if len(d)>200 else d if len(d)>=10 else "preview unavailable")(clean_html(job.get("job_description","") or ""  )),
            "apply_link": job.get("job_apply_link", "#")
        })

    # 2️⃣ Add LinkedIn, Naukri, FoundIt links (existing function)
    external_links = search_jobs(job_role, location, experience_level, job_type, foundit_experience)
    for job in external_links:
        # Use maxsplit=1 to safely handle job titles that contain colons
        parts = job["title"].split(":", 1)
        results.append({
            "platform": parts[0].strip(),
            "title": parts[1].strip() if len(parts) > 1 else job["title"],
            "company": "",   # no company data for external redirect links
            "location": location,
            "salary": "Check site",
            "date": "N/A",
            "type": "N/A",
            "remote": "N/A",
            "publisher": parts[0].strip(),
            "description": "Open this platform to view full details.",
            "apply_link": job["link"]
        })

    return results


# ═══════════════════════════════════════════════════════════════
# URL BUILDERS — LinkedIn / Naukri / FoundIt
# ═══════════════════════════════════════════════════════════════

def search_jobs(job_role, location, experience_level=None, job_type=None, foundit_experience=None):
    # Encode query values
    role_encoded = urllib.parse.quote_plus(job_role.strip())
    loc_encoded = urllib.parse.quote_plus(location.strip())

    # Slugs
    role_path_naukri = job_role.strip().lower().replace(" ", "-")
    city_part = location.strip().split(",")[0].strip()
    city_naukri = city_part.lower().replace(" ", "-")
    # Only encode what the user entered for the query
    city_query_naukri = urllib.parse.quote_plus(location.strip())

    # FoundIt slugs
    role_path_foundit = slugify(job_role)
    city_path_foundit = slugify(city_part)

    # Experience mappings
    experience_range_map = {
        "Internship": "0~0", "Entry Level": "1~1", "Associate": "2~3",
        "Mid-Senior Level": "4~7", "Director": "8~15", "Executive": "16~20"
    }
    experience_exact_map = {
        "Internship": "0", "Entry Level": "1", "Associate": "2",
        "Mid-Senior Level": "4", "Director": "8", "Executive": "16"
    }
    linkedin_exp_map = {
        "Internship": "1", "Entry Level": "2", "Associate": "3",
        "Mid-Senior Level": "4", "Director": "5", "Executive": "6"
    }
    job_type_map = {
        "Full-time": "F", "Part-time": "P", "Contract": "C",
        "Temporary": "T", "Volunteer": "V", "Internship": "I"
    }

    # LinkedIn URL (always scoped to India to prevent geo-ambiguity)
    # e.g. "Delhi NCR" → "Delhi NCR, India" so LinkedIn doesn't resolve to Delhi, Ohio
    # "Remote (India)" already contains "india" so it is left as-is
    if "india" not in location.strip().lower():
        linkedin_location = f"{location.strip()}, India"
    else:
        linkedin_location = location.strip()
    linkedin_loc_encoded = urllib.parse.quote_plus(linkedin_location)

    linkedin_url = f"https://www.linkedin.com/jobs/search/?keywords={role_encoded}&location={linkedin_loc_encoded}"
    if experience_level in linkedin_exp_map:
        linkedin_url += f"&f_E={linkedin_exp_map[experience_level]}"
    if job_type in job_type_map:
        linkedin_url += f"&f_JT={job_type_map[job_type]}"

    # Naukri & FoundIt share the same experience value:
    # if the years field is filled → use that; else fall back to dropdown
    foundit_exp_clean = str(foundit_experience).strip() if foundit_experience is not None else ""
    if foundit_exp_clean:
        experience_range = f"{foundit_exp_clean}~{foundit_exp_clean}"
        experience_exact = foundit_exp_clean
    else:
        experience_range = experience_range_map.get(experience_level, "")
        experience_exact = experience_exact_map.get(experience_level, "")

    # Naukri URL – shares experience_exact with FoundIt
    naukri_url = (
        f"https://www.naukri.com/{role_path_naukri}-jobs-in-{city_naukri}"
        f"?k={role_encoded}&l={city_query_naukri}"
    )
    if experience_exact:
        naukri_url += f"&experience={experience_exact}"
    naukri_url += "&nignbevent_src=jobsearchDeskGNB"

    # FoundIt URL
    search_id = uuid.uuid4()
    child_search_id = uuid.uuid4()
    if role_path_foundit and city_path_foundit:
        foundit_url = (
            f"https://www.foundit.in/search/{role_path_foundit}-jobs-in-{city_path_foundit}"
            f"?query={role_encoded}&locations={loc_encoded}"
            f"&experienceRanges={urllib.parse.quote_plus(experience_range)}"
            f"&experience={experience_exact}"
            f"&queryDerived=true"
            f"&searchId={search_id}&child_search_id={child_search_id}"
        )
    else:
        foundit_url = (
            f"https://www.foundit.in/search/result?query={role_encoded}&locations={loc_encoded}"
            f"&experienceRanges={urllib.parse.quote_plus(experience_range)}"
            f"&experience={experience_exact}"
            f"&queryDerived=true"
            f"&searchId={search_id}&child_search_id={child_search_id}"
        )

    return [
        {"title": f"LinkedIn: {job_role} jobs in {location}", "link": linkedin_url},
        {"title": f"Naukri: {job_role} jobs in {location}", "link": naukri_url},
        {"title": f"FoundIt (Monster): {job_role} jobs in {location}", "link": foundit_url}
    ]


# ═══════════════════════════════════════════════════════════════
# UTILITIES
# ═══════════════════════════════════════════════════════════════

def clean_html(raw_html: str) -> str:
    """Remove HTML tags, comments and decode HTML entities from API descriptions."""
    if not raw_html:
        return ""
    raw_html = re.sub(r"<!--.*?-->", "", raw_html, flags=re.DOTALL)
    cleaned = re.sub(r"<.*?>", "", raw_html).strip()
    return _html.unescape(cleaned)


def slugify(text: str) -> str:
    """Convert text into a safe slug (lowercase, hyphenated, no special chars)."""
    text = text.lower().strip()
    text = re.sub(r"[^\w\s-]", "", text)
    text = re.sub(r"\s+", "-", text)
    return text


def add_hyperlink(paragraph, url, text, color="0000FF", underline=True):
    """
    A function to add a hyperlink to a paragraph.
    """
    from docx.oxml.shared import OxmlElement, qn
    from docx.opc.constants import RELATIONSHIP_TYPE as RT

    part = paragraph.part
    r_id = part.relate_to(url, RT.HYPERLINK, is_external=True)

    hyperlink = OxmlElement('w:hyperlink')
    hyperlink.set(qn('r:id'), r_id)

    new_run = OxmlElement('w:r')
    rPr = OxmlElement('w:rPr')

    # Color and underline
    if underline:
        u = OxmlElement('w:u')
        u.set(qn('w:val'), 'single')
        rPr.append(u)

    color_element = OxmlElement('w:color')
    color_element.set(qn('w:val'), color)
    rPr.append(color_element)

    new_run.append(rPr)

    text_elem = OxmlElement('w:t')
    text_elem.text = text
    new_run.append(text_elem)

    hyperlink.append(new_run)
    paragraph._p.append(hyperlink)
    return hyperlink
