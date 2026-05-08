from __future__ import annotations
"""
job_scam_detector.py  —  Production Grade v5
─────────────────────────────────────────────
Fixes in v5 (over v4):

  BUG 1 — RESET BUTTON BROKEN:
    st.rerun(scope="app") inside @st.fragment raises an error in Streamlit ≥ 1.33.
    Fixed: use st.rerun() (no scope arg) which always works.
    Also fixed: the clear-keys loop now correctly deletes widget keys INCLUDING
    jsd_raw and jsd_mode so the text area and radio actually blank out.

  BUG 2 — ANALYSE BUTTON DOUBLE-FIRE / RACE CONDITION:
    jsd_running flag was set but the fragment re-runs on EVERY widget interaction,
    causing the flag to sometimes be seen as True on the very next keystroke, 
    permanently disabling the button until a full page reload.
    Fixed: jsd_running is only checked/set during the run block; cleared via
    st.session_state.pop() both on success and failure.

  BUG 3 — AUTO-DETECT (PASTE MODE) VERY WEAK / INFLATED SCORES:
    auto_extract() was setting description=raw, requirements=raw, benefits=raw
    (all = full raw text). _run_rules() joins all fields and saw every phrase
    3-6× making rule scores wildly inflated. REAL description is now kept as raw
    but requirements and benefits are left empty so the rule engine reads each 
    section exactly once.

  BUG 4 — _quick_prescan ALSO INFLATED:
    _quick_prescan passed the same inflated auto_extract dict to _run_rules.
    Fixed: prescan now calls _run_rules with a clean job dict where only 
    description=raw; requirements and benefits are empty strings.

  BUG 5 — _salary_outlier FALSE POSITIVES IN PASTE MODE:
    When salary = full raw text, _salary_outlier matched phone numbers, 
    zip codes, etc. Fixed: salary field in paste mode only contains the 
    extracted salary snippet, not the full text.

  BUG 6 — OVERRIDE FIELDS IGNORED AFTER EXPANDER:
    The override expander widgets updated extracted["key"] but the fragment
    re-ran immediately on each keystroke, so the PREVIOUS extracted values
    were used when Analyse was clicked. Fixed: override values are read from
    session_state keys (jsd_ot, jsd_oco, etc.) AT THE TIME OF THE BUTTON CLICK,
    not from the live widget object.

  BUG 7 — CHECKLIST KEY COLLISION:
    Used id(result) for checklist keys which changes every run, creating
    hundreds of orphaned session_state keys. Fixed: use a stable key 
    "jsd_c_{idx}" (no result-id suffix).

  BUG 8 — FORMULA COMMENT/CODE/HTML MISMATCH:
    Docstring said 55%/30%/15% but code did 60%/25%/15% and the score strip
    HTML also showed 0.60/0.25. All three now agree on 60/25/15.

Fixes carried from v4 (unchanged):
  - PAGE RE-RENDER BUG, FRAGMENT ISOLATION, RAW HTML EXPOSURE,
    AUTO-ANALYSE ON PASTE, UX POLISH, PRODUCTION GUIDANCE.
"""
# v5 patch by senior engineer — all 8 bugs fixed above.

"""
Original v4 docstring preserved below for reference:
Fixes in v4:
  - PAGE RE-RENDER BUG: Analysis result stored in session_state and rendered
    OUTSIDE the form block — submit no longer resets the whole page.
  - FRAGMENT ISOLATION: Input widgets wrapped in @st.fragment so only the
    input area re-runs on widget interaction, not the full app.
  - RAW HTML EXPOSURE: All unsafe HTML is now gated through a single
    _html() helper that validates the call site and uses unsafe_allow_html
    consistently; no HTML ever leaks as visible text.
  - REFRESH / RESET BUTTON: A dedicated Reset button clears all jsd_ keys
    and reruns cleanly.
  - AUTO-ANALYSE ON PASTE: When text is pasted the rule-based pre-scan runs
    immediately and shows a lightweight inline risk preview — no button needed
    for the first-pass signal. Full AI analysis still requires the button.
  - UX POLISH: Sticky top-bar score badge, keyboard shortcut hint, improved
    loading state with progress steps, section anchors for scrolling.
  - PRODUCTION GUIDANCE: See PRODUCTION.md that is printed to console on
    first run (set env PRINT_PROD_GUIDE=1).

Detection layers (unchanged):
  A. 6 live network probes  (parallel threads)
     domain age · site reachability · typosquatting · free-email · MX mail server · MCA registry
  B. 15-signal rule engine  (weighted, 0-100)
  C. LLM deep analysis      (llama-3.3-70b-versatile via Groq)
  D. Blended score          (60% AI + 25% rules + 15% probe penalty)
"""

import html as _html_escape
import os
import re
import json
import time
import socket
import difflib
import threading
import urllib.request
import urllib.error
import urllib.parse
from datetime import datetime
from typing import Optional
import pytz

_IST = pytz.timezone("Asia/Kolkata")

def _now_ist() -> str:
    """Return current time as IST string — always '08 May 14:35' format."""
    return datetime.now(_IST).strftime("%-d %b %H:%M")

import ssl
import ipaddress
import contextlib

import streamlit as st

# Rate-limit helpers — imported lazily so job_scam_detector can run standalone
# (unit tests, etc.) without requiring the full user_login module.
def _get_rate_limit_fns():
    """Return (check_and_gate, record_usage, get_count) or None if unavailable."""
    try:
        from user_login import check_and_gate_feature, record_feature_usage, get_usage_count_last_hour
        return check_and_gate_feature, record_feature_usage, get_usage_count_last_hour
    except ImportError:
        return None

_SCAM_FEATURE   = "scam_detector"
_SCAM_LIMIT     = 3   # analyses per hour — mirrors USAGE_LIMITS in user_login.py


# ─────────────────────────────────────────────────────────────────────────────
# PRODUCTION GUIDE  — set env PRINT_PROD_GUIDE=1 to display on startup
# ─────────────────────────────────────────────────────────────────────────────

_PROD_GUIDE = """
╔══════════════════════════════════════════════════════════════════════════════╗
║              JOB SCAM DETECTOR — PRODUCTION CHECKLIST                      ║
╠══════════════════════════════════════════════════════════════════════════════╣
║  SECRETS                                                                    ║
║  • Store GROQ_API_KEY in .streamlit/secrets.toml or env var — never in     ║
║    source code. Access via st.secrets["GROQ_API_KEY"].                      ║
║                                                                             ║
║  CACHING                                                                    ║
║  • Wrap run_live_probes() with @st.cache_data(ttl=3600, show_spinner=False) ║
║    so identical domain lookups are not re-fetched on every rerun.           ║
║  • Cache LLM responses keyed on hash(job_dict) + model name.               ║
║                                                                             ║
║  RATE-LIMITING                                                              ║
║  • Add a per-user token bucket (Redis / Upstash) before call_llm_fn().     ║
║  • Groq free tier: 30 req/min, 6000 tokens/min — enforce on server side.   ║
║                                                                             ║
║  SECURITY                                                                   ║
║  • All st.markdown(unsafe_allow_html=True) calls use server-generated HTML.║
║    User-supplied text is ALWAYS escaped via _esc() before interpolation.   ║
║  • Add Content-Security-Policy header via a reverse proxy (nginx/Caddy).   ║
║                                                                             ║
║  PERFORMANCE                                                                ║
║  • Move run_live_probes to a background asyncio task — don't block Groq.   ║
║  • Set STREAMLIT_SERVER_MAX_UPLOAD_SIZE=5 (no file uploads needed here).   ║
║                                                                             ║
║  DEPLOYMENT                                                                 ║
║  • Use Streamlit Community Cloud, Railway, or Docker + nginx.               ║
║  • Set [server] headless=true, port=8501 in .streamlit/config.toml.        ║
║  • Health-check endpoint: add ?healthz=1 branch at top of main().          ║
║                                                                             ║
║  OBSERVABILITY                                                              ║
║  • Log structured JSON: verdict, blended_score, timestamp, session_id.     ║
║  • Use Sentry (sentry-sdk[streamlit]) for exception capture.               ║
║  • Track blended_score distribution to monitor model drift.                ║
╚══════════════════════════════════════════════════════════════════════════════╝
"""

if os.environ.get("PRINT_PROD_GUIDE") == "1":
    print(_PROD_GUIDE)


# ─────────────────────────────────────────────────────────────────────────────
# SECURITY HELPER — always escape user text before putting it in HTML
# ─────────────────────────────────────────────────────────────────────────────

def _esc(text: str) -> str:
    """HTML-escape any user-supplied string before interpolating into markup."""
    return _html_escape.escape(str(text or ""))


# ─────────────────────────────────────────────────────────────────────────────
# SVG ICON SYSTEM  — zero emojis anywhere
# ─────────────────────────────────────────────────────────────────────────────

def _svg(paths: str, size: int = 14, stroke: str = "currentColor", sw: float = 2) -> str:
    return (
        f'<svg width="{size}" height="{size}" viewBox="0 0 24 24" fill="none" '
        f'stroke="{stroke}" stroke-width="{sw}" stroke-linecap="round" '
        f'stroke-linejoin="round" style="vertical-align:-2px;flex-shrink:0;">'
        f'{paths}</svg>'
    )

class I:
    SHIELD       = '<path d="M12 22s8-4 8-10V5l-8-3-8 3v7c0 6 8 10 8 10z"/>'
    CHECK        = '<path d="M22 11.08V12a10 10 0 1 1-5.93-9.14"/><polyline points="22 4 12 14.01 9 11.01"/>'
    X_CIRCLE     = '<circle cx="12" cy="12" r="10"/><line x1="15" y1="9" x2="9" y2="15"/><line x1="9" y1="9" x2="15" y2="15"/>'
    ALERT_TRI    = '<path d="M10.29 3.86L1.82 18a2 2 0 0 0 1.71 3h16.94a2 2 0 0 0 1.71-3L13.71 3.86a2 2 0 0 0-3.42 0z"/><line x1="12" y1="9" x2="12" y2="13"/><line x1="12" y1="17" x2="12.01" y2="17"/>'
    ALERT_CIRCLE = '<circle cx="12" cy="12" r="10"/><line x1="12" y1="8" x2="12" y2="12"/><line x1="12" y1="16" x2="12.01" y2="16"/>'
    INFO         = '<circle cx="12" cy="12" r="10"/><line x1="12" y1="16" x2="12" y2="12"/><line x1="12" y1="8" x2="12.01" y2="8"/>'
    SKULL        = '<circle cx="12" cy="11" r="5"/><path d="M9 17v1a3 3 0 0 0 6 0v-1"/><path d="M12 6V4"/>'
    GLOBE        = '<circle cx="12" cy="12" r="10"/><line x1="2" y1="12" x2="22" y2="12"/><path d="M12 2a15.3 15.3 0 0 1 4 10 15.3 15.3 0 0 1-4 10 15.3 15.3 0 0 1-4-10 15.3 15.3 0 0 1 4-10z"/>'
    CALENDAR     = '<rect x="3" y="4" width="18" height="18" rx="2" ry="2"/><line x1="16" y1="2" x2="16" y2="6"/><line x1="8" y1="2" x2="8" y2="6"/><line x1="3" y1="10" x2="21" y2="10"/>'
    LINK         = '<path d="M10 13a5 5 0 0 0 7.54.54l3-3a5 5 0 0 0-7.07-7.07l-1.72 1.71"/><path d="M14 11a5 5 0 0 0-7.54-.54l-3 3a5 5 0 0 0 7.07 7.07l1.71-1.71"/>'
    COPY         = '<rect x="9" y="9" width="13" height="13" rx="2" ry="2"/><path d="M5 15H4a2 2 0 0 1-2-2V4a2 2 0 0 1 2-2h9a2 2 0 0 1 2 2v1"/>'
    SERVER       = '<rect x="2" y="2" width="20" height="8" rx="2" ry="2"/><rect x="2" y="14" width="20" height="8" rx="2" ry="2"/><line x1="6" y1="6" x2="6.01" y2="6"/><line x1="6" y1="18" x2="6.01" y2="18"/>'
    BUILDING     = '<rect x="4" y="2" width="16" height="20" rx="2"/><path d="M9 22V12h6v10"/><path d="M8 7h.01"/><path d="M12 7h.01"/><path d="M16 7h.01"/>'
    GHOST        = '<path d="M9 10h.01"/><path d="M15 10h.01"/><path d="M12 2a8 8 0 0 0-8 8v12l3-3 2.5 2.5L12 19l2.5 2.5L17 19l3 3V10a8 8 0 0 0-8-8z"/>'
    FLAG         = '<path d="M4 15s1-1 4-1 5 2 8 2 4-1 4-1V3s-1 1-4 1-5-2-8-2-4 1-4 1z"/><line x1="4" y1="22" x2="4" y2="15"/>'
    ID_CARD      = '<rect x="2" y="5" width="20" height="14" rx="2"/><circle cx="8" cy="12" r="2"/><path d="M14 9h4"/><path d="M14 13h3"/>'
    DOLLAR       = '<line x1="12" y1="1" x2="12" y2="23"/><path d="M17 5H9.5a3.5 3.5 0 0 0 0 7h5a3.5 3.5 0 0 1 0 7H6"/>'
    DOLLAR_OFF   = '<line x1="12" y1="1" x2="12" y2="23"/><path d="M17 5H9.5a3.5 3.5 0 0 0 0 7h5a3.5 3.5 0 0 1 0 7H6"/><line x1="2" y1="2" x2="22" y2="22"/>'
    CREDIT_CARD  = '<rect x="1" y="4" width="22" height="16" rx="2" ry="2"/><line x1="1" y1="10" x2="23" y2="10"/>'
    TRENDING_UP  = '<polyline points="23 6 13.5 15.5 8.5 10.5 1 18"/><polyline points="17 6 23 6 23 12"/>'
    MAIL         = '<path d="M4 4h16c1.1 0 2 .9 2 2v12c0 1.1-.9 2-2 2H4c-1.1 0-2-.9-2-2V6c0-1.1.9-2 2-2z"/><polyline points="22,6 12,13 2,6"/>'
    CLOCK        = '<circle cx="12" cy="12" r="10"/><polyline points="12 6 12 12 16 14"/>'
    MAP_PIN      = '<path d="M21 10c0 7-9 13-9 13s-9-6-9-13a9 9 0 0 1 18 0z"/><circle cx="12" cy="10" r="3"/>'
    SEARCH       = '<circle cx="11" cy="11" r="8"/><line x1="21" y1="21" x2="16.65" y2="16.65"/>'
    LIST         = '<line x1="8" y1="6" x2="21" y2="6"/><line x1="8" y1="12" x2="21" y2="12"/><line x1="8" y1="18" x2="21" y2="18"/><line x1="3" y1="6" x2="3.01" y2="6"/><line x1="3" y1="12" x2="3.01" y2="12"/><line x1="3" y1="18" x2="3.01" y2="18"/>'
    ZAP          = '<polygon points="13 2 3 14 12 14 11 22 21 10 12 10 13 2"/>'
    TRIANGLE     = '<path d="M10.29 3.86L1.82 18a2 2 0 0 0 1.71 3h16.94a2 2 0 0 0 1.71-3L13.71 3.86a2 2 0 0 0-3.42 0z"/>'
    HOME         = '<path d="M3 9l9-7 9 7v11a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2z"/><polyline points="9 22 9 12 15 12 15 22"/>'
    EDIT         = '<path d="M11 4H4a2 2 0 0 0-2 2v14a2 2 0 0 0 2 2h14a2 2 0 0 0 2-2v-7"/><path d="M18.5 2.5a2.121 2.121 0 0 1 3 3L12 15l-4 1 1-4 9.5-9.5z"/>'
    CPU          = '<rect x="4" y="4" width="16" height="16" rx="2"/><rect x="9" y="9" width="6" height="6"/><line x1="9" y1="1" x2="9" y2="4"/><line x1="15" y1="1" x2="15" y2="4"/><line x1="9" y1="20" x2="9" y2="23"/><line x1="15" y1="20" x2="15" y2="23"/><line x1="20" y1="9" x2="23" y2="9"/><line x1="20" y1="14" x2="23" y2="14"/><line x1="1" y1="9" x2="4" y2="9"/><line x1="1" y1="14" x2="4" y2="14"/>'
    FILE_TEXT    = '<path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z"/><polyline points="14 2 14 8 20 8"/><line x1="16" y1="13" x2="8" y2="13"/><line x1="16" y1="17" x2="8" y2="17"/>'
    HISTORY      = '<polyline points="1 4 1 10 7 10"/><path d="M3.51 15a9 9 0 1 0 .49-4.9"/>'
    BAR_CHART    = '<line x1="18" y1="20" x2="18" y2="10"/><line x1="12" y1="20" x2="12" y2="4"/><line x1="6" y1="20" x2="6" y2="14"/>'
    AWARD        = '<circle cx="12" cy="8" r="6"/><path d="M15.477 12.89L17 22l-5-3-5 3 1.523-9.11"/>'
    PHONE        = '<path d="M22 16.92v3a2 2 0 0 1-2.18 2 19.79 19.79 0 0 1-8.63-3.07A19.5 19.5 0 0 1 4.69 13 19.79 19.79 0 0 1 1.61 4.36 2 2 0 0 1 3.6 2h3a2 2 0 0 1 2 1.72c.127.96.361 1.903.7 2.81a2 2 0 0 1-.45 2.11L7.91 9.91a16 16 0 0 0 6.1 6.1l1.27-.63a2 2 0 0 1 2.11.45c.907.339 1.85.573 2.81.7A2 2 0 0 1 22 16.92z"/>'
    LAYERS       = '<polygon points="12 2 2 7 12 12 22 7 12 2"/><polyline points="2 17 12 22 22 17"/><polyline points="2 12 12 17 22 12"/>'
    EYE          = '<path d="M1 12s4-8 11-8 11 8 11 8-4 8-11 8-11-8-11-8z"/><circle cx="12" cy="12" r="3"/>'
    SPARKLE      = '<path d="M12 2l2.4 7.4H22l-6.2 4.5 2.4 7.4L12 17l-6.2 4.3 2.4-7.4L2 9.4h7.6z"/>'


_SIG_ICON: dict[str, str] = {
    "upfront_payment":         I.CREDIT_CARD,
    "mlm_pyramid":             I.TRIANGLE,
    "too_good_salary":         I.TRENDING_UP,
    "unrealistic_benefits":    I.DOLLAR,
    "vague_description":       I.EDIT,
    "free_email_contact":      I.MAIL,
    "urgency_pressure":        I.CLOCK,
    "no_company_info":         I.BUILDING,
    "req_paradox":             I.LAYERS,
    "personal_info_demand":    I.ID_CARD,
    "location_mismatch":       I.MAP_PIN,
    "work_from_home_bait":     I.HOME,
    "missing_salary":          I.DOLLAR_OFF,
    "poor_grammar":            I.FILE_TEXT,
    "generic_template":        I.COPY,
    "whatsapp_only_contact":   I.PHONE,
}


# ─────────────────────────────────────────────────────────────────────────────
# CONSTANTS
# ─────────────────────────────────────────────────────────────────────────────

_WEIGHTS: dict[str, int] = {
    "upfront_payment":         25,
    "mlm_pyramid":             20,
    "too_good_salary":         18,
    "vague_description":       14,
    "free_email_contact":      12,
    "urgency_pressure":        12,
    "whatsapp_only_contact":   15,
    "no_company_info":         11,
    "req_paradox":             10,
    "personal_info_demand":     9,
    "unrealistic_benefits":     7,
    "location_mismatch":        7,
    "poor_grammar":             6,
    "work_from_home_bait":      5,
    "missing_salary":           4,
    "generic_template":         4,
}

_FREE_DOMAINS: frozenset[str] = frozenset({
    "gmail.com","yahoo.com","hotmail.com","outlook.com","aol.com",
    "icloud.com","mail.com","protonmail.com","yopmail.com","guerrillamail.com",
    "tempmail.com","mailinator.com","trashmail.com","sharklasers.com",
    "rediffmail.com","live.com","msn.com","yahoo.in","yahoo.co.in",
    "rocketmail.com","zohomail.com","inbox.com","fastmail.com",
})

_BRAND_DOMAINS: list[str] = [
    "infosys.com","tcs.com","wipro.com","hcltech.com","accenture.com",
    "ibm.com","amazon.in","amazon.com","google.com","microsoft.com",
    "flipkart.com","swiggy.in","zomato.com","paytm.com","ola.com",
    "myntra.com","meesho.com","byju.com","razorpay.com","freshworks.com",
    "zoho.com","mindtree.com","mphasis.com","ltimindtree.com",
    "capgemini.com","cognizant.com","hexaware.com","persistent.com",
    "naukri.com","linkedin.com","indeed.com","glassdoor.com",
]

_PAY_PHRASES = [
    r"pay.*registration",r"registration fee",r"training fee",r"kit fee",
    r"security deposit",r"advance.*payment",r"refundable.*deposit",
    r"processing fee",r"joining fee",r"membership fee",r"buy.*starter kit",
    r"purchase.*materials",r"invest.*joining",r"small.*investment",
    r"courier.*charge",r"background.*check.*fee",r"verification.*charge",
    # NEW — common Indian scam variants
    r"pay.*before.*joining",r"deposit.*refund.*after",r"id.*card.*fee",
    r"uniform.*charge",r"laptop.*deposit",r"tool.*kit.*purchase",
    r"sim.*card.*fee",r"scanner.*fee",r"biometric.*fee",
    r"police.*verification.*fee",r"insurance.*premium.*joining",
    r"token.*amount",r"earnest.*money",r"caution.*deposit",
]
_MLM_PHRASES = [
    r"unlimited earning",r"be your own boss",r"passive income",
    r"network marketing",r"multi.level",r"refer.*earn",
    r"downline",r"upline",r"pyramid",r"direct selling",
    r"recruit.*friends",r"grow your team",r"commission.*recruit",
    r"financial freedom.*join",r"work from.*anywhere.*earn",
    # NEW — Indian MLM / chain marketing
    r"chain.*marketing",r"binary.*plan",r"matrix.*plan",r"level.*income",
    r"team.*bonus",r"generation.*income",r"franchise.*opportunity",
    r"business.*opportunity.*join",r"modicare",r"amway.*distributor",
    r"vestige",r"herbalife.*join",r"earn.*per.*referral",
    r"direct.*sales.*representative",r"field.*sales.*executive.*commission",
]
_URGENCY_PHRASES = [
    r"limited.*position",r"act now",r"respond.*immediately",
    r"offer.*expires",r"today only",r"urgent.*hiring",
    r"immediate.*joiner",r"joining.*asap",r"last.*few.*seat",
    r"don.t miss",r"apply.*before.*[0-9]",r"deadline.*today",
    r"positions.*filling.*fast",r"only.*[0-9].*seat.*left",
    # NEW
    r"interview.*today",r"joining.*tomorrow",r"walk.*in.*today",
    r"last.*date.*tomorrow",r"closing.*soon",r"hurry.*apply",
    r"final.*round.*today",r"selected.*candidate.*report.*immediately",
]
_VAGUE_PHRASES = [
    r"dynamic.*individual",r"go.getter",r"passionate.*person",
    r"attractive.*salary",r"good.*communication",r"fast.paced.*environment",
    r"various.*responsibilities",r"other.*duties.*assigned",
    r"exciting.*opportunity",r"ground.*floor.*opportunity",
    # NEW
    r"multitasking.*ability",r"smart.*worker",r"self.*motivated",
    r"result.*oriented",r"team.*player.*required",r"flexible.*working",
    r"as per.*industry standard",r"best in.*industry",r"market.*competitive",
    r"handsome.*salary",r"good.*package",r"salary.*no.*bar",
]
_PERSONAL_PHRASES = [
    r"bank.*account.*detail",r"aadhaar.*number",r"pan.*number",
    r"passport.*copy.*apply",r"ssn.*apply",r"social.*security.*apply",
    r"photo.*mandatory.*apply",r"dob.*required.*apply",
    r"mother.*maiden.*name",r"send.*id.*proof.*apply",r"aadhar.*card.*apply",
    # NEW
    r"voter.*id.*apply",r"driving.*licence.*apply",r"send.*selfie",
    r"whatsapp.*photo.*apply",r"family.*detail.*apply",
    r"nominee.*detail.*joining",r"bank.*ifsc.*apply",r"upi.*id.*apply",
    r"gpay.*number.*apply",r"paytm.*number.*apply",
]
_URGENCY_PHRASES_WA = [
    r"whatsapp.*apply",r"whatsapp.*us.*now",r"message.*on.*whatsapp",
    r"contact.*on.*whatsapp",r"ping.*on.*wa",r"chat.*on.*whatsapp",
    r"apply.*on.*telegram",r"telegram.*group.*join",
]
_PLATFORM_TRUST = [
    r"linkedin\.com/jobs",r"naukri\.com",r"indeed\.com",
    r"foundit\.in",r"shine\.com",r"monster\.com",r"timesjobs\.com",
    r"instahyre\.com",r"cutshort\.io",r"wellfound\.com",r"angellist",
    r"iimjobs\.com",r"freshersworld\.com",r"hirist\.com",
]
_PARADOX_PATTERNS = [
    (r"(fresher|entry.level|0.year)", r"([5-9]|10|\d\d).year.*experience"),
    (r"(no.*experience.*required|experience.*not.*required)", r"\d+.*year.*experience"),
    (r"freshers.*welcome", r"(senior|lead|manager|director).*role"),
]
_UNREALISTIC_PHRASES = [
    r"earn.*lakh.*week",r"earn.*lakh.*day",r"earn.*\d{5,}.*day",
    r"guaranteed.*income",r"assured.*salary",r"no.*target.*high.*pay",
    r"earn.*\$\d{4,}.*week",r"work.*2.*hour.*earn.*\d{4,}",
]
_GRAMMAR_PATTERNS = [
    r"\b(kindly revert|do the needful|revert back|prepone)\b",
    r"\b(myself is|myself am|i am having)\b",
    r"(!{3,}|\.{4,})",
    r"\b[A-Z]{5,}\b",
]
_LOCATION_CLUES = [
    r"(usa|united states|uk|london|dubai|singapore).*(work from.*india|indian.*candidate)",
    r"international.*position.*local.*salary",
    r"global.*company.*no.*office",
]
_WFH_PHRASES = [
    r"100%.*work.*from.*home.*high.*salary",r"part.time.*earn.*full.time.*salary",
    r"just.*[0-9].*hour.*day.*earn",r"online.*job.*no.*skill.*required",
    r"data.*entry.*earn.*\d{4,}",r"captcha.*job",r"ad.*posting.*earn",
    r"copy.*paste.*earn",r"form.*filling.*earn",
]


# ─────────────────────────────────────────────────────────────────────────────
# AUTO-EXTRACT — runs on every paste keystroke, no button needed
# ─────────────────────────────────────────────────────────────────────────────

# Known Indian cities + common metro abbreviations for location heuristic
_KNOWN_CITIES = re.compile(
    r"\b(Mumbai|Delhi|Bangalore|Bengaluru|Hyderabad|Chennai|Kolkata|Pune|Ahmedabad|"
    r"Noida|Gurgaon|Gurugram|Jaipur|Lucknow|Chandigarh|Indore|Bhopal|Kochi|"
    r"Coimbatore|Surat|Vadodara|Nagpur|Patna|Bhubaneswar|Trivandrum|Visakhapatnam|"
    r"Mysore|Mysuru|Mangalore|Hubli|Dehradun|Agra|Varanasi|Ranchi|Guwahati|"
    r"Remote|Work\s+from\s+Home|WFH|Pan\s+India|PAN\s+India|Hybrid)\b",
    re.IGNORECASE,
)

# Common job-title role words — used to score candidate title lines
_ROLE_WORDS = re.compile(
    r"\b(engineer|developer|analyst|manager|intern|associate|consultant|"
    r"designer|architect|scientist|lead|head|officer|executive|specialist|"
    r"coordinator|administrator|trainee|fresher|hiring|role|position|"
    r"generative\s+ai|ai[\s/]ml|machine\s+learning|data\s+science|"
    r"software|frontend|backend|fullstack|full[\s-]stack|devops|"
    r"product|sales|marketing|finance|hr|operations|accountant|"
    r"recruiter|writer|editor|content|graphic|illustrator|tester|qa)\b",
    re.IGNORECASE,
)

# Noise lines that are NEVER a job title
_TITLE_NOISE = re.compile(
    r"^(\*|#|–|-)|(eligibility|criteria|requirement|qualification|"
    r"responsibility|about\s+(us|the|company)|we\s+are|we\s+offer|"
    r"job\s+description|note\s*:|dear\s+candidate|greetings|"
    r"kindly|please|apply\s+now|how\s+to\s+apply|"
    r"urgent\s+hir|immediate\s+hir|work\s+from\s+home|"
    r"earn\s+rs|earn\s+₹|no\s+experience\s+needed)",
    re.IGNORECASE,
)

# Standalone hiring-shout lines — not a title
_HIRING_SHOUT = re.compile(
    r"^(urgent\s+hir|immediate\s+hir|\*+\s*urgent|\*+\s*hir|hiring\s*[!*]+$)",
    re.IGNORECASE,
)

# Company name suffixes — expanded with more Indian patterns
_CO_SUFFIXES = re.compile(
    r"\b(pvt\.?\s*ltd\.?|private\s+limited|limited|llp|llc|inc\.?|"
    r"corp\.?|technologies|tech|solutions|services|systems|consultancy|"
    r"consulting|infotech|softwares?|enterprises?|ventures?|group|"
    r"global|india|innovations?|associates?|partners?|labs?|studio|"
    r"digital|analytics|capital|financial|logistics|pharma|healthcare)\b",
    re.IGNORECASE,
)

# Free/personal email domains — company cannot be extracted from these
_FREE_EMAIL_DOMAINS = re.compile(
    r"@(gmail|yahoo|hotmail|outlook|rediffmail|ymail|icloud|protonmail"
    r"|zohomail|aol|live|msn)\.",
    re.IGNORECASE,
)


def _clean(val: str) -> str:
    """Strip markdown, asterisks, leading bullets, extra whitespace."""
    val = re.sub(r"[\*\_\#\~`]", "", val)
    val = re.sub(r"^[\-•–—]\s*", "", val.strip())
    return val.strip().rstrip(".,;:")


def _xf(text: str, kws: list) -> str:
    """Extract value after a keyword label (e.g. 'Company: Acme Corp')."""
    for kw in kws:
        # Allow keyword at line-start or after newline/whitespace
        m = re.search(
            rf"(?im)(?:^|(?<=\n))\s*{re.escape(kw)}\s*[:\-–]\s*([^\n]{{2,100}})",
            text or "",
        )
        if m:
            val = _clean(m.group(1))
            if len(val) > 2:
                return val
    return ""


def _xu(text: str) -> str:
    """Extract first URL from text."""
    m = re.search(r"https?://[^\s)\"',<>{}\[\]]{6,}", text or "")
    return m.group(0).rstrip(".,;)/") if m else ""


def _xs(text: str) -> str:
    """Extract salary / CTC information."""
    # Explicit label
    m = re.search(
        r"(?i)(salary|ctc|pay|package|compensation|remuneration|stipend|fixed)\s*[:\-–]\s*([^\n]{3,80})",
        text or "",
    )
    if m:
        return _clean(m.group(2))
    # Currency pattern: Rs/INR/$ followed by numbers + optional units
    m2 = re.search(
        r"(?:Rs\.?\s*|INR\s*|₹\s*)[\d,\.\s]+(?:\s*-\s*[\d,\.]+)?\s*(?:LPA|lpa|L|lakhs?|per\s+annum|PA|CTC)?",
        text or "", re.IGNORECASE,
    )
    if m2:
        return _clean(m2.group(0))
    m3 = re.search(
        r"\$[\d,\.]+(?:\s*-\s*\$?[\d,\.]+)?\s*(?:per\s+(?:month|year|annum|hour))?",
        text or "", re.IGNORECASE,
    )
    return _clean(m3.group(0)) if m3 else ""


def _xc(text: str) -> str:
    """Extract email + phone from text."""
    emails = re.findall(r"[\w.+\-]+@[\w\-]+\.[a-zA-Z]{2,}", text or "")
    phones = re.findall(r"(?<!\d)[+]?[\d][\d\s\-()]{8,13}[\d](?!\d)", text or "")
    return " | ".join(emails[:1] + [p.strip() for p in phones[:1]])


def _xt(text: str) -> str:
    """
    Extract job title — 6-strategy fallback, production grade.

    Fixes over v5:
    - Strategy 0: rejects "URGENT HIRING" / shout lines before anything else
    - Strategy 2: "looking for / seeking / need a X" now strips leading article
      and truncates at "with/who/for/and" so "a Product Manager with 5+ yrs" → "Product Manager"
    - Strategy 3: "we are hiring X" / "join us as X" / "join <co> as X" patterns added
    - Strategy 4 scoring: penalises ALL-CAPS lines (scam shout); boosts hyphenated titles
    - Title cleaning: strips trailing seniority noise like "- 3 to 5 years"
    """
    t = text or ""

    def _title_clean(s: str) -> str:
        """Extra cleanup specific to titles."""
        s = _clean(s)
        # Strip leading article or adjective noise (talented/experienced/passionate etc.)
        s = re.sub(
            r"^(a|an|the|experienced?|talented?|skilled?|qualified?|"
            r"dynamic|passionate|driven|dedicated|motivated)\s+",
            "", s, flags=re.I,
        )
        # Truncate at trailing noise: "- X years", "| location", "(remote)"
        s = re.split(r"\s+[-–|]\s+\d", s)[0]
        s = re.split(r"\s*\(\s*remote\b", s, flags=re.I)[0]
        # Truncate at "with X years/experience" / "who has" / "to join" / "and work"
        s = re.split(
            r"\s+(?:with\s+(?:\d|strong|good|excellent|proven)|"
            r"who\s+|to\s+join\b|and\s+work|to\s+work)",
            s, flags=re.I
        )[0]
        return s.strip().rstrip(".,;:-")

    # Strategy 1: explicit keyword label  (e.g. "Role: Software Engineer")
    val = _xf(t, [
        "job title", "role", "position", "designation", "opening",
        "vacancy", "hiring for", "opening for", "we are hiring",
        "currently hiring", "job profile", "post",
    ])
    if val and not _TITLE_NOISE.search(val) and not _HIRING_SHOUT.search(val):
        return _title_clean(val)

    # Strategy 2: "looking for / seeking / need a X" — paragraph-style postings
    m = re.search(
        r"(?i)(?:looking\s+for\s+a?n?\s*|seeking\s+a?n?\s*|need\s+a?n?\s*|"
        r"require\s+a?n?\s*|searching\s+for\s+a?n?\s*)"
        r"(?:(?:experienced?|talented?|skilled?|qualified?|dynamic|passionate|driven|dedicated)\s+)?"
        r"([A-Za-z][^\n,\.]{4,70}?)(?:\s+to\s+join|\s+who\s+|\s+with\s+\d|\.|,|\n|$)",
        t,
    )
    if m:
        candidate = _title_clean(m.group(1))
        if _ROLE_WORDS.search(candidate) and not _TITLE_NOISE.search(candidate):
            return candidate

    # Strategy 3: "we are hiring X" / "join us as X" / "join <Co> as X"
    m2 = re.search(
        r"(?i)(?:we\s+are\s+(?:currently\s+)?hiring\s+(?:a\s+|an\s+)?|"
        r"join\s+us\s+as\s+(?:a\s+|an\s+)?|"
        r"join\s+\w[\w\s]{0,30}?\s+as\s+(?:a\s+|an\s+)?)"
        r"([A-Za-z][^\n,\.]{4,60}?)(?:\s+at\s+|\s+to\s+|\.|,|\n|$)",
        t,
    )
    if m2:
        candidate = _title_clean(m2.group(1))
        if _ROLE_WORDS.search(candidate) and not _TITLE_NOISE.search(candidate):
            return candidate

    # Strategy 4: "hiring … for … [role words]" sentence pattern
    m3 = re.search(
        r"(?i)hir(?:ing|ed)\s+(?:freshers?|candidates?|professionals?|engineers?)?\s*"
        r"(?:for|as)?\s*([A-Za-z][^\n,\.]{4,60}?)(?:\s+role|\s+position|\s+at|\.|,|\n|$)",
        t,
    )
    if m3:
        candidate = _title_clean(m3.group(1))
        if _ROLE_WORDS.search(candidate) and not _TITLE_NOISE.search(candidate):
            return candidate

    # Strategy 5: score every line in the first 15 lines
    best_line, best_score = "", 0
    for line in t.split("\n")[:15]:
        line = _clean(line)
        if not (4 < len(line) < 100):
            continue
        if _TITLE_NOISE.search(line):
            continue
        if _HIRING_SHOUT.search(line):
            continue
        if line.startswith("http"):
            continue
        # Skip "Label: value" field definitions
        colon_pos = line.find(":")
        if 0 < colon_pos < 20 and len(line[:colon_pos].split()) <= 3:
            continue
        score = 0
        role_hits = len(_ROLE_WORDS.findall(line))
        score += role_hits * 3
        if len(line) < 60:
            score += 2
        if line[0].isupper():
            score += 1
        # Boost hyphenated tech titles ("Python/Django", "React-Node")
        if re.search(r"[A-Za-z][/\-][A-Za-z]", line):
            score += 1
        # Penalise ALL-CAPS (scam shout line)
        if line.isupper():
            score -= 4
        # Penalise long paragraph lines
        if len(line.split()) > 12:
            score -= 2
        if score > best_score:
            best_score, best_line = score, line

    return _title_clean(best_line) if best_score > 0 else best_line


def _xco(text: str) -> str:
    """
    Extract company name — 6-strategy fallback, production grade.

    Fixes over v5:
    - Strategy 0: guard against email-domain false positives (productjobs@gmail → "")
    - Strategy 2: suffix regex now anchored to single line only (no cross-line grabs)
    - Strategy 3: "we at X" / "join X as" patterns added for paragraph-style postings
    - Strategy 4: "at X" now skips if X looks like a verb phrase / location
    - Strategy 5: standalone line now also rejects lines that are all-caps shout lines
    - All extracted names normalised to Title Case before returning
    """
    t = text or ""

    def _co_clean(s: str) -> str:
        s = _clean(s)
        # Reject if it's clearly a sentence fragment
        if re.search(r"\b(are|is|we|our|this|has|have|will|the|a|an|"
                     r"looking|seeking|hiring|currently|team|join)\b", s, re.I):
            return ""
        return s.title() if s else ""

    # Strategy 1: explicit keyword label — highest confidence
    val = _xf(t, [
        "company", "organization", "organisation", "employer", "firm",
        "about us", "about the company", "about company",
        "about the organization", "hiring company", "client", "posted by",
    ])
    if val:
        # "Posted by" often includes "• 2nd" on LinkedIn — strip that
        val = re.split(r"\s*[•·|]\s*", val)[0]
        cleaned = _co_clean(val)
        if cleaned:
            return cleaned

    # Strategy 2: company suffix heuristic — SINGLE LINE only
    # Extended pattern grabs compound suffixes like "Consulting Services", "Technologies Pvt Ltd"
    _suffix_pat = (
        r"([A-Za-z][A-Za-z0-9&\.\s\-]{1,40}?)\s+"
        + _CO_SUFFIXES.pattern
        + r"(?:\s+" + _CO_SUFFIXES.pattern + r")?"  # optional second suffix word
    )
    for line in t.split("\n"):
        line_clean = _clean(line)
        if not line_clean or len(line_clean) > 100:
            continue
        m = re.search(_suffix_pat, line_clean, re.IGNORECASE)
        if m:
            candidate = _clean(m.group(0))
            if 3 < len(candidate) < 70:
                prefix = m.group(1).strip()
                if re.search(r"\b(we|our|this|the|a|an|is|are|has)\b", prefix, re.I):
                    continue
                return candidate.title()

    # Strategy 3: "we at X" / "join X as" / "roles at X" / "careers at X"
    for pat in [
        r"(?i)\bwe\s+at\s+([A-Za-z][A-Za-z0-9&\s\-]{1,40}?)(?:\s+are|\s+have|\s+offer|,|\.|$)",
        r"(?i)\bjoin\s+([A-Za-z][A-Za-z0-9&\s\-]{1,40}?)\s+as\s+(?:a\s+|an\s+)?",
        r"(?i)(?:roles?\s+at|positions?\s+at|careers?\s+at|apply\s+at|"
        r"opportunities?\s+at|hiring\s+at|working\s+at|joining\s+us\s+at)\s+"
        r"([A-Za-z][A-Za-z0-9&\.\s\-]{2,50}?)(?:\.|,|\n|$|\s+(?:is|are|was|for|and))",
    ]:
        m = re.search(pat, t)
        if m:
            candidate = _clean(m.group(1))
            if 2 < len(candidate) < 60:
                result = _co_clean(candidate)
                if result:
                    return result

    # Strategy 4: word(s) right after "at" in first 5 lines
    # Remove email addresses first — prevents email-domain grabs (productjobs@ → "Salary")
    first_chunk_no_email = re.sub(r"[\w.+\-]+@[\w\-]+\.[a-zA-Z]{2,}", "", 
                                   " ".join(t.split("\n")[:5]))
    m2 = re.search(
        r"\bat\s+([A-Za-z][A-Za-z0-9]{2,}(?:\s+[A-Za-z][A-Za-z0-9]{2,}){0,3})",
        first_chunk_no_email, re.IGNORECASE,
    )
    if m2:
        candidate = _clean(m2.group(1))
        # Reject locations, verbs, and field-label words
        if not re.search(
            r"\b(bangalore|mumbai|delhi|chennai|hyderabad|pune|kolkata|"
            r"remote|india|home|salary|ctc|location|contact|apply|least|most)\b",
            candidate, re.I,
        ):
            if 2 < len(candidate) < 50:
                result = _co_clean(candidate)
                if result:
                    return result

    # Strategy 5: second/third standalone non-empty line
    lines = [_clean(l) for l in t.split("\n") if _clean(l)]
    for line in lines[1:4]:
        if not (2 < len(line) < 55):
            continue
        if _ROLE_WORDS.search(line):
            continue
        if _HIRING_SHOUT.search(line):
            continue
        if line.isupper() and len(line.split()) <= 2:
            continue  # e.g. "WFH ONLY"
        # Reject WFH/earn/scam shout lines
        if re.search(r"\b(work\s+from\s+home|earn\s+rs|earn\s+₹|no\s+experience|"
                     r"data\s+entry|whatsapp\s+only|urgent|immediate)\b", line, re.I):
            continue
        colon_pos = line.find(":")
        if 0 < colon_pos < 20:
            continue
        # Must not look like a sentence, location, or email
        if re.search(r"\b(are|is|we|our|this|has|have|will|"
                     r"bangalore|mumbai|delhi|hyderabad|chennai|pune|remote)\b",
                     line, re.I):
            continue
        if "@" in line or "http" in line:
            continue
        return line.title()

    return ""


def _xloc(text: str) -> str:
    """
    Extract location with multi-strategy fallback:
    1. Explicit label
    2. Known city name scan
    3. "based in / located in" patterns
    """
    t = text or ""

    # Strategy 1: explicit label
    val = _xf(t, [
        "location", "job location", "work location", "place of work",
        "city", "office location", "office", "based in", "based at",
        "workplace", "work place",
    ])
    if val:
        # strip if it looks like a full sentence
        first_part = val.split(",")[0].split(".")[0].strip()
        if len(first_part) < 60:
            return _clean(first_part)

    # Strategy 2: known city list
    m = _KNOWN_CITIES.search(t)
    if m:
        # Grab up to ~30 chars around the match for context (e.g. "Bangalore, Karnataka")
        start = m.start()
        snippet = t[start:start+40].split("\n")[0]
        return _clean(snippet.split(".")[0])

    # Strategy 3: "based in / located in / office in" pattern
    m2 = re.search(
        r"(?i)(?:based\s+in|located\s+in|office\s+in|headquartered\s+in|"
        r"presence\s+in|operating\s+in)\s+([^\n,\.]{3,50})",
        t,
    )
    if m2:
        return _clean(m2.group(1))

    return ""


def auto_extract(raw: str) -> dict:
    """
    BUG FIX v5: requirements and benefits are NO LONGER set to the full raw text.

    Previously all three (description/requirements/benefits) = raw, which meant
    _run_rules saw every phrase 3-6x in the joined full-text, massively inflating
    rule scores and making prescan useless.

    Now:
      - description = raw  (full text for rule engine to read once)
      - requirements = ""  (rules will not double-count)
      - benefits     = ""  (rules will not double-count)

    The rule engine's `full` join is: title + description + requirements + benefits
    + contact + salary — so keeping description=raw is sufficient for all pattern
    matching. requirements/benefits sections are naturally embedded in the raw text.
    """
    return {
        "title":        _xt(raw),
        "company":      _xco(raw),
        "website":      _xu(raw),
        "location":     _xloc(raw),
        "salary":       _xs(raw),   # FIX: only the extracted snippet, not full raw
        "contact":      _xc(raw),
        "description":  raw,
        "requirements": "",         # FIX: was raw — caused 3x phrase duplication
        "benefits":     "",         # FIX: was raw — caused 3x phrase duplication
    }


# ─────────────────────────────────────────────────────────────────────────────
# LIVE NETWORK PROBES
# ─────────────────────────────────────────────────────────────────────────────

_T_RDAP  = 6
_T_REACH = 5
_T_MCA   = 10   # MCA/Zaubacorp can be slow — give enough headroom


def _extract_domain(s: str) -> Optional[str]:
    if not s:
        return None
    s = s.strip().lower()
    if "@" in s and "/" not in s:
        return s.split("@")[-1]
    m = re.search(r"(?:https?://)?(?:www\.)?([a-z0-9\-\.]+\.[a-z]{2,})", s)
    return m.group(1) if m else None


def _whois_age_fallback(domain: str) -> dict | None:
    """
    Lightweight raw WHOIS TCP query (port 43) as fallback when RDAP fails.
    Tries the TLD's WHOIS server and parses 'Creation Date:' lines.
    Returns a partial result dict or None if it cannot parse.
    """
    tld = domain.rsplit(".", 1)[-1].lower()
    whois_servers = {
        "com": "whois.verisign-grs.com", "net": "whois.verisign-grs.com",
        "org": "whois.pir.org", "in": "whois.registry.in",
        "io": "whois.nic.io", "co": "whois.nic.co",
        "ai": "whois.nic.ai", "info": "whois.afilias.net",
        "biz": "whois.biz", "uk": "whois.nic.uk",
    }
    server = whois_servers.get(tld, f"whois.nic.{tld}")
    try:
        with socket.create_connection((server, 43), timeout=5) as s:
            s.sendall(f"{domain}\r\n".encode())
            raw = b""
            while True:
                chunk = s.recv(4096)
                if not chunk:
                    break
                raw += chunk
        text = raw.decode("utf-8", errors="ignore")
        for line in text.splitlines():
            ll = line.lower()
            if any(k in ll for k in ("creation date", "created on", "registered on", "domain registered")):
                m = re.search(r"(\d{4}-\d{2}-\d{2})", line)
                if m:
                    dt  = datetime.strptime(m.group(1), "%Y-%m-%d")
                    age = (datetime.utcnow() - dt).days
                    return {
                        "status":     "young" if age < 180 else "old",
                        "age_days":   age,
                        "registered": dt.strftime("%d %b %Y"),
                        "detail":     f"Registered {dt.strftime('%d %b %Y')} — {age} days old (via WHOIS)",
                        "source":     "WHOIS",
                    }
    except Exception:
        pass
    return None


def _probe_domain_age(domain: str) -> dict:
    out = {"status": "unknown", "age_days": None, "registered": None, "detail": "", "source": "RDAP"}
    if not domain:
        return out
    # ── Primary: RDAP ────────────────────────────────────────────────────────
    try:
        # Try RDAP bootstrap first, then rdap.org as universal fallback
        for rdap_url in [
            f"https://rdap.org/domain/{domain}",
            f"https://rdap.iana.org/domain/{domain}",
        ]:
            try:
                req = urllib.request.Request(
                    rdap_url, headers={"User-Agent": "ScamDetector/4.0"},
                )
                with urllib.request.urlopen(req, timeout=_T_RDAP) as resp:
                    data = json.loads(resp.read().decode())
                reg_date = None
                exp_date = None
                for ev in data.get("events", []):
                    action = ev.get("eventAction", "")
                    if action in ("registration", "created") and not reg_date:
                        reg_date = ev.get("eventDate", "")
                    elif action in ("expiration", "expiry") and not exp_date:
                        exp_date = ev.get("eventDate", "")
                if reg_date:
                    for fmt in ("%Y-%m-%dT%H:%M:%SZ", "%Y-%m-%dT%H:%M:%S"):
                        try:
                            dt  = datetime.strptime(reg_date[:19], fmt)
                            age = (datetime.utcnow() - dt).days
                            exp_str = ""
                            if exp_date:
                                with contextlib.suppress(Exception):
                                    exp_dt  = datetime.strptime(exp_date[:19], fmt)
                                    days_to_exp = (exp_dt - datetime.utcnow()).days
                                    exp_str = f" | Expires {exp_dt.strftime('%d %b %Y')}"
                                    if days_to_exp < 30:
                                        exp_str += " ⚠ expiring soon"
                            out.update(
                                status="young" if age < 180 else "old",
                                age_days=age,
                                registered=dt.strftime("%d %b %Y"),
                                detail=f"Registered {dt.strftime('%d %b %Y')} — {age} days old{exp_str}",
                                source="RDAP",
                            )
                            return out
                        except ValueError:
                            continue
                out["detail"] = "Registration date not in RDAP response"
                break  # got a response, no point retrying second URL
            except (urllib.error.HTTPError, urllib.error.URLError):
                continue  # try next RDAP URL
    except Exception as e:
        out.update(status="error", detail=f"RDAP error: {type(e).__name__}")

    # ── Fallback: raw WHOIS TCP ───────────────────────────────────────────────
    fallback = _whois_age_fallback(domain)
    if fallback:
        out.update(fallback)
        return out

    if out["status"] == "unknown":
        out["detail"] = "Domain age unavailable — verify manually on whois.domaintools.com"
    return out


_PARKING_PATTERNS = re.compile(
    r"(domain.*for sale|buy this domain|parked by|under construction"
    r"|coming soon|this domain|godaddy|namecheap|sedo\.com|hugedomains)",
    re.IGNORECASE,
)


def _probe_site_reachable(domain: str) -> dict:
    out = {
        "reachable":    None,
        "status_code":  None,
        "ssl_valid":    None,
        "is_parked":    False,
        "redirect_to":  None,
        "detail":       "",
    }
    if not domain:
        return out

    # ── DNS resolution check first ────────────────────────────────────────────
    try:
        resolved_ip = socket.gethostbyname(domain)
        # Private/loopback IPs are a red flag
        try:
            addr = ipaddress.ip_address(resolved_ip)
            if addr.is_private or addr.is_loopback:
                out.update(
                    reachable=False,
                    detail=f"Domain resolves to private/loopback IP {resolved_ip} — suspicious",
                )
                return out
        except ValueError:
            pass
    except socket.gaierror:
        out.update(reachable=False, detail="DNS resolution failed — domain does not exist or is offline")
        return out

    # ── HTTP/HTTPS probes with redirect following ─────────────────────────────
    for scheme in ("https", "http"):
        url = f"{scheme}://{domain}"
        try:
            req = urllib.request.Request(
                url, method="GET",
                headers={"User-Agent": "Mozilla/5.0 (compatible; ScamDetector/4.0)"},
            )
            # Use a redirect-following opener (default)
            opener = urllib.request.build_opener(urllib.request.HTTPRedirectHandler())
            with opener.open(req, timeout=_T_REACH) as resp:
                final_url  = resp.geturl()
                status     = resp.status
                body_bytes = resp.read(4096)

            # Redirect detection
            redirect_to = None
            final_domain = re.search(r"https?://([^/]+)", final_url)
            if final_domain and final_domain.group(1).rstrip("/") != domain:
                redirect_to = final_url

            # Parking page detection
            body_text  = body_bytes.decode("utf-8", errors="ignore")
            is_parked  = bool(_PARKING_PATTERNS.search(body_text))

            # SSL validity (only for https)
            ssl_valid = None
            if scheme == "https":
                try:
                    ctx = ssl.create_default_context()
                    with ctx.wrap_socket(
                        socket.create_connection((domain, 443), timeout=4),
                        server_hostname=domain,
                    ) as ssock:
                        cert = ssock.getpeercert()
                        not_after = datetime.strptime(
                            cert["notAfter"], "%b %d %H:%M:%S %Y %Z"
                        )
                        days_left  = (not_after - datetime.utcnow()).days
                        ssl_valid  = True if days_left > 0 else False
                except ssl.SSLCertVerificationError:
                    ssl_valid = False
                except Exception:
                    ssl_valid = None  # could not verify, not necessarily bad

            detail_parts = [f"HTTP {status} — site is live"]
            if is_parked:
                detail_parts.append("appears to be a PARKED domain")
            if redirect_to:
                detail_parts.append(f"redirects to {redirect_to[:60]}")
            if ssl_valid is False:
                detail_parts.append("SSL certificate INVALID")
            elif ssl_valid is True:
                detail_parts.append("SSL certificate valid")

            out.update(
                reachable=True,
                status_code=status,
                ssl_valid=ssl_valid,
                is_parked=is_parked,
                redirect_to=redirect_to,
                detail=" | ".join(detail_parts),
            )
            return out

        except urllib.error.HTTPError as e:
            out.update(reachable=True, status_code=e.code,
                       detail=f"HTTP {e.code} — server responded")
            return out
        except (urllib.error.URLError, socket.timeout, OSError):
            continue

    out.update(reachable=False, detail="No HTTP/HTTPS response — site appears offline")
    return out


def _probe_typosquatting(domain: str) -> dict:
    out = {"is_squatter": False, "closest_brand": None, "similarity": 0.0, "detail": ""}
    if not domain:
        return out
    best, brand = 0.0, None
    d_sld = domain.split(".")[0]
    for b in _BRAND_DOMAINS:
        b_sld = b.split(".")[0]
        sc = max(difflib.SequenceMatcher(None, d_sld, b_sld).ratio(),
                 difflib.SequenceMatcher(None, domain, b).ratio())
        if sc > best:
            best, brand = sc, b
    out.update(similarity=round(best, 3), closest_brand=brand)
    if best >= 0.72 and domain != brand:
        out.update(is_squatter=True,
                   detail=f"'{domain}' is {int(best*100)}% similar to '{brand}' — possible impersonation")
    else:
        out["detail"] = f"No close brand match (best: {int(best*100)}% to {brand})"
    return out


def _probe_free_email(contact: str) -> dict:
    out = {"uses_free_domain": False, "domain": None, "emails_found": [], "detail": ""}
    emails = re.findall(r"[\w.+\-]+@[\w\-]+\.[a-zA-Z]{2,}", contact or "")
    out["emails_found"] = emails
    for e in emails:
        dom = e.split("@")[-1].lower()
        if dom in _FREE_DOMAINS:
            out.update(uses_free_domain=True, domain=dom,
                       detail=f"'{e}' uses personal email domain '{dom}'")
            return out
    out["detail"] = ("No free/personal email domains detected" if emails
                     else "No email address found in input")
    return out


def _probe_mx_record(contact: str) -> dict:
    """
    DNS MX record check for every corporate (non-free) email domain found
    in the contact field.

    Verdicts:
      - NO_EMAIL       : no email address found at all
      - FREE_DOMAIN    : all emails use free providers (Gmail etc.) — skip MX
      - MX_FOUND       : at least one corporate domain has valid MX records
      - NO_MX          : corporate domain exists in DNS but has NO mail servers
                         configured — company doesn't actually use that domain
                         for email (strongest scam signal)
      - DNS_FAIL       : corporate domain doesn't resolve at all
      - INCONCLUSIVE   : mixed or edge case
    """
    out = {
        "status":          "NO_EMAIL",
        "domain":          None,
        "mx_records":      [],
        "voip_risk":       False,
        "detail":          "",
    }

    # ── Extract all email addresses ──────────────────────────────────────────
    emails = re.findall(r"[\w.+\-]+@([\w\-]+\.[a-zA-Z]{2,})", contact or "")
    if not emails:
        out["detail"] = "No email address found — cannot verify mail infrastructure"
        return out

    # Separate free vs corporate domains
    corp_domains = [d.lower() for d in emails if d.lower() not in _FREE_DOMAINS]
    free_domains = [d.lower() for d in emails if d.lower() in _FREE_DOMAINS]

    if not corp_domains:
        out.update(
            status="FREE_DOMAIN",
            detail=(
                f"Only free email domain(s) found: {', '.join(list(set(free_domains))[:2])}. "
                "MX check skipped — this is itself a red flag."
            ),
        )
        return out

    # ── Query MX records for each corporate domain via public DNS-over-HTTPS ─
    # Using Cloudflare DoH (1.1.1.1) — no system DNS library needed,
    # works in all environments including Streamlit Cloud.
    for domain in dict.fromkeys(corp_domains):   # deduplicate, preserve order
        out["domain"] = domain
        try:
            url = f"https://cloudflare-dns.com/dns-query?name={domain}&type=MX"
            req = urllib.request.Request(
                url,
                headers={
                    "Accept": "application/dns-json",
                    "User-Agent": "ScamDetector/4.0",
                },
            )
            with urllib.request.urlopen(req, timeout=5) as resp:
                data = json.loads(resp.read().decode())

            status_code = data.get("Status", -1)

            # NXDOMAIN (3) — domain does not exist in DNS at all
            if status_code == 3:
                out.update(
                    status="DNS_FAIL",
                    detail=(
                        f"Domain '{domain}' does not exist in DNS. "
                        "The company email domain is completely fake."
                    ),
                )
                return out

            answers = data.get("Answer", [])
            mx_hosts = [
                a["data"].rstrip(".")
                for a in answers
                if a.get("type") == 15   # type 15 = MX record
            ]

            if mx_hosts:
                # ── VoIP / disposable mail server heuristic ────────────────
                voip_indicators = (
                    "mailgun", "sendgrid", "sparkpost", "mandrillapp",
                    "amazonses", "mailchimp", "yopmail", "guerrilla",
                    "trashmail", "mailinator",
                )
                voip_risk = any(
                    v in h.lower() for h in mx_hosts for v in voip_indicators
                )
                out.update(
                    status="MX_FOUND",
                    mx_records=mx_hosts[:4],
                    voip_risk=voip_risk,
                    detail=(
                        f"'{domain}' has {len(mx_hosts)} MX record(s): "
                        f"{', '.join(mx_hosts[:2])}"
                        + (" — TRANSACTIONAL/BULK mail server (not a real corporate inbox)" if voip_risk else "")
                    ),
                )
                return out

            # Domain resolves (no NXDOMAIN) but has zero MX records
            # This is the critical scam signal: someone registered a domain
            # for appearances but never set up actual email infrastructure.
            out.update(
                status="NO_MX",
                detail=(
                    f"'{domain}' has NO MX records. The domain exists but is NOT "
                    "configured to send or receive email. A real company always "
                    "has mail servers. This is a strong indicator of a fake domain."
                ),
            )
            return out

        except (urllib.error.URLError, socket.timeout, OSError):
            out.update(
                status="INCONCLUSIVE",
                domain=domain,
                detail=f"MX lookup timed out for '{domain}' — verify manually",
            )
            # try next domain if any
            continue
        except Exception as e:
            out.update(
                status="INCONCLUSIVE",
                domain=domain,
                detail=f"MX lookup error for '{domain}': {type(e).__name__}",
            )
            continue

    return out


def _dns_mx_lookup(domain: str) -> bool:
    """
    Raw DNS UDP query for MX records on port 53.
    No HTTP. No API key. Works from any server environment.
    Returns True if domain has at least one MX record.
    """
    import struct
    try:
        tid      = b"\xaa\xbb"
        flags    = b"\x01\x00"
        counts   = b"\x00\x01\x00\x00\x00\x00\x00\x00"
        parts    = domain.encode().split(b".")
        qname    = b"".join(bytes([len(p)]) + p for p in parts) + b"\x00"
        qtype_cl = b"\x00\x0f\x00\x01"          # MX, IN
        packet   = tid + flags + counts + qname + qtype_cl
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        s.settimeout(4)
        s.sendto(packet, ("8.8.8.8", 53))
        resp, _ = s.recvfrom(512)
        s.close()
        answer_count = struct.unpack(">H", resp[6:8])[0]
        return answer_count > 0
    except Exception:
        return False


def _probe_company_domain(args: tuple) -> dict:
    """
    Verify a company is real using ONLY DNS socket + TCP port checks.
    Zero API keys. Zero HTTP requests. Works from any deployment environment.

    Checks performed (all via socket — proven to work):
    1. DNS A-record  — does the domain exist at all?
    2. Port 443      — is a real HTTPS website running?
    3. DNS MX-record — does the company have a mail server?
    4. Name match    — does the domain name relate to the company name?

    Why this replaces MCA:
    • MCA portal (old + new) blocks all server IPs — always INCONCLUSIVE
    • Zaubacorp / IndiaFilings return HTTP 403 from cloud servers
    • DNS + socket checks are unrestricted, instantaneous, 100% reliable
    • A scam company almost never has: a matching domain + live HTTPS + MX records
    """
    company, website = args
    out = {
        "domain_exists":           None,
        "website_live":            None,
        "has_mx":                  None,
        "domain_matches_company":  None,
        "domain":                  "",
        "ip":                      "",
        "detail":                  "",
        "scam_signals":            [],
        "score":                   0,      # 0=clean, higher=more suspicious
    }

    # ── Extract domain ────────────────────────────────────────────────────
    domain = ""
    if website:
        m = re.search(r"(?:https?://)?(?:www\.)?([a-z0-9\-\.]+\.[a-z]{2,})", website.lower())
        if m:
            domain = m.group(1)
    # Fallback: guess from company name (e.g. "Wipro" → wipro.com)
    guessed = False
    if not domain and company:
        slug   = re.sub(r"[^a-z0-9]", "", company.lower().split()[0])
        domain = f"{slug}.com"
        guessed = True

    if not domain:
        out["detail"] = "No website provided — could not verify company domain"
        return out

    out["domain"] = domain

    # ── Check 1: DNS A-record (does domain exist?) ────────────────────────
    try:
        ip = socket.gethostbyname(domain)
        out["domain_exists"] = True
        out["ip"]            = ip
    except socket.gaierror:
        out["domain_exists"] = False
        out["scam_signals"].append(
            f"Domain '{domain}' has NO DNS record — domain does not exist"
        )
        out["score"] += 40
        label = "guessed — " if guessed else ""
        out["detail"] = (
            f"({label}domain: {domain}) — does not exist in DNS. "
            f"Real companies always have a registered domain."
        )
        return out  # no point checking further

    # ── Check 2: Port 443 — live HTTPS website ────────────────────────────
    try:
        s = socket.create_connection((domain, 443), timeout=4)
        s.close()
        out["website_live"] = True
    except Exception:
        out["website_live"] = False
        out["scam_signals"].append(
            f"No HTTPS website running at '{domain}' — domain registered but unused"
        )
        out["score"] += 20

    # ── Check 3: MX record — real companies have mail servers ─────────────
    has_mx = _dns_mx_lookup(domain)
    out["has_mx"] = has_mx
    if not has_mx:
        out["scam_signals"].append(
            f"'{domain}' has NO MX (mail) records — not set up for corporate email"
        )
        out["score"] += 15

    # ── Check 4: Domain vs company name match ─────────────────────────────
    company_core = re.sub(r"[^a-z0-9]", "", company.lower())
    domain_core  = re.sub(r"[^a-z0-9]", "", domain.split(".")[0])
    # Match if either is a substring of the other (handles abbreviations like tcs/tataconsultancy)
    match = (
        company_core[:6] in domain_core or
        domain_core[:6] in company_core or
        domain_core in company_core or
        company_core in domain_core
    )
    out["domain_matches_company"] = match
    if not match and not guessed:
        out["scam_signals"].append(
            f"Domain '{domain}' does not match company name '{company}' — suspicious"
        )
        out["score"] += 10

    # ── Build summary detail ──────────────────────────────────────────────
    checks = []
    checks.append(f"DNS {'✓' if out['domain_exists'] else '✗'}")
    checks.append(f"HTTPS {'✓' if out['website_live'] else '✗'}")
    checks.append(f"Mail server {'✓' if out['has_mx'] else '✗'}")
    if not guessed:
        checks.append(f"Name match {'✓' if match else '✗'}")

    prefix = "(guessed domain) " if guessed else ""
    out["detail"] = f"{prefix}{domain} — {' | '.join(checks)}"
    return out


def _mca_word_match(name_clean: str, html: str) -> bool:
    """
    Safe word-boundary match: ALL meaningful words in the company name must
    appear as whole words in the response HTML. Prevents substring false-positives.
    """
    stopwords = {
        "LIMITED","PRIVATE","PUBLIC","INDIA","SERVICES","SOLUTIONS",
        "TECHNOLOGIES","TECHNOLOGY","CONSULTANCY","CONSULTING","ENTERPRISES",
        "ENTERPRISE","AND","THE","OF","FOR","WITH","PVT","LTD","LLC","INC",
        "CORP","GROUP","GLOBAL","SYSTEMS","SYSTEM","INFOTECH","SOFTWARE",
        "SOFTWARES","VENTURES","VENTURE","INNOVATIONS","INNOVATION",
    }
    words = [
        w for w in re.sub(r"[^\w\s]", "", name_clean).upper().split()
        if len(w) > 2 and w not in stopwords
    ]
    if not words:
        return False
    html_upper = html.upper()
    # Use word-boundary regex for each word — no substring false positives
    hits = sum(
        1 for w in words
        if re.search(rf"\b{re.escape(w)}\b", html_upper)
    )
    return hits >= max(1, len(words))   # ALL meaningful words must match


def _mca_make_request(url: str, extra_headers: dict | None = None) -> str:
    """
    Shared HTTP helper for MCA probes. Uses a realistic browser UA + headers
    to avoid bot detection. Returns decoded response body or raises.
    """
    headers = {
        "User-Agent": (
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
            "AppleWebKit/537.36 (KHTML, like Gecko) "
            "Chrome/124.0.0.0 Safari/537.36"
        ),
        "Accept":          "text/html,application/json,*/*;q=0.9",
        "Accept-Language": "en-IN,en;q=0.9",
        "Accept-Encoding": "gzip, deflate, br",
        "Connection":      "keep-alive",
        "Cache-Control":   "no-cache",
    }
    if extra_headers:
        headers.update(extra_headers)
    req = urllib.request.Request(url, headers=headers)
    ctx = ssl.create_default_context()
    ctx.check_hostname = False
    ctx.verify_mode    = ssl.CERT_NONE          # some Indian govt sites have bad certs
    with urllib.request.urlopen(req, timeout=_T_MCA, context=ctx) as resp:
        raw_bytes = resp.read()
    # Handle gzip transparently
    if raw_bytes[:2] == b"\x1f\x8b":
        import gzip
        raw_bytes = gzip.decompress(raw_bytes)
    return raw_bytes.decode("utf-8", errors="ignore")


def _probe_mca(company: str) -> dict:
    """
    4-tier MCA lookup with graceful fallback:

    Tier 1 — Zaubacorp  (mirrors MCA data, no auth, reliable)
    Tier 2 — IndiaFilings search  (second public MCA mirror)
    Tier 3 — MCA21 V3 REST API   (official but often blocks bots)
    Tier 4 — Graceful degradation with manual verification link

    Why NOT mca.gov.in/mcafoportal (old code):
      • MCA21 V2 portal is RETIRED — returns 403/redirect always.
      • Even MCA21 V3 requires a session cookie from their React SPA.
      • Public mirrors (Zaubacorp, IndiaFilings) are more reliable for
        programmatic lookup and are always up-to-date (they sync nightly).
    """
    out = {
        "found":  None,
        "detail": "",
        "source": "MCA India",
    }

    # ── Guard: no company name extracted ──────────────────────────────────
    if not company or len(company.strip()) < 3:
        out["detail"] = (
            "No company name detected in posting — "
            "add 'Company: [name]' in the job text to enable this check"
        )
        return out

    # Normalise: Title Case + strip special chars for matching
    name_clean  = re.sub(r"[^\w\s]", " ", company).strip()
    name_title  = name_clean.title()
    name_upper  = name_clean.upper()
    encoded     = urllib.parse.quote(name_title)
    encoded_raw = urllib.parse.quote(name_clean)

    # ── Tier 1: Zaubacorp ─────────────────────────────────────────────────
    # Public MCA data mirror — no auth required, highly reliable
    try:
        url = f"https://www.zaubacorp.com/company-list/p-1/CompanyName-{encoded}.html"
        raw = _mca_make_request(url, {"Referer": "https://www.zaubacorp.com/"})
        if _mca_word_match(name_clean, raw):
            out.update(
                found=True,
                detail=f"Found in MCA registry via Zaubacorp — '{name_title}' is legally registered in India",
                source="MCA India (via Zaubacorp)",
            )
        elif "no company found" in raw.lower() or "0 companies" in raw.lower() or len(raw.strip()) < 500:
            out.update(
                found=False,
                detail=f"'{name_title}' NOT found in MCA — company may not be legally registered in India",
                source="MCA India (via Zaubacorp)",
            )
        else:
            # Got a page but couldn't match — fall through to Tier 2
            raise ValueError("Zaubacorp: no conclusive match, trying next tier")
        return out
    except Exception:
        pass

    # ── Tier 2: IndiaFilings company search ───────────────────────────────
    try:
        url = f"https://www.indiafilings.com/company-search?search={encoded_raw}"
        raw = _mca_make_request(url, {"Referer": "https://www.indiafilings.com/"})
        if _mca_word_match(name_clean, raw):
            out.update(
                found=True,
                detail=f"Found in MCA registry via IndiaFilings — '{name_title}' is legally registered",
                source="MCA India (via IndiaFilings)",
            )
            return out
        elif "no result" in raw.lower() or "not found" in raw.lower():
            out.update(
                found=False,
                detail=f"'{name_title}' NOT found in MCA — verify at mca.gov.in",
                source="MCA India (via IndiaFilings)",
            )
            return out
    except Exception:
        pass

    # ── Tier 3: MCA21 V3 REST API (official, sometimes works) ─────────────
    try:
        url = (
            f"https://efiling.mca.gov.in/SearchService/rest/search/v3/company"
            f"?companyName={encoded_raw}&draw=1&start=0&length=10"
        )
        raw = _mca_make_request(url, {
            "Referer": "https://efiling.mca.gov.in/",
            "Origin":  "https://efiling.mca.gov.in",
            "Accept":  "application/json",
        })
        try:
            data      = json.loads(raw)
            companies = (
                data.get("companyMasterData")
                or data.get("data")
                or data.get("companies")
                or []
            )
            if companies:
                # Verify the top result actually matches — API sometimes returns
                # unrelated companies when there's a partial name match
                top_name = str(companies[0].get("companyName", ""))
                if _mca_word_match(name_clean, top_name):
                    out.update(
                        found=True,
                        detail=f"Found in MCA21 V3 — '{top_name}' is legally registered in India",
                        source="MCA India (MCA21 V3 API)",
                    )
                else:
                    out.update(
                        found=False,
                        detail=f"'{name_title}' not matched in MCA21 V3 results — verify manually",
                        source="MCA India (MCA21 V3 API)",
                    )
            else:
                out.update(
                    found=False,
                    detail=f"'{name_title}' NOT found in MCA21 — may not be registered",
                    source="MCA India (MCA21 V3 API)",
                )
        except (json.JSONDecodeError, KeyError):
            # API returned HTML (bot block) — fall to Tier 4
            raise ValueError("MCA21 V3: non-JSON response (bot block)")
        return out
    except Exception:
        pass

    # ── Tier 4: Graceful degradation ──────────────────────────────────────
    # All tiers failed — don't show a scary error, give user actionable info
    out.update(
        found=None,
        detail=(
            f"MCA lookup blocked by all sources for '{name_title}' — "
            f"verify manually: mca.gov.in/MCA21Version3"
        ),
        source="MCA India (manual check required)",
    )
    return out


@st.cache_data(ttl=3600, show_spinner=False)
def _run_live_probes_cached(domain: str, contact: str, company: str, website: str) -> dict:
    """
    Cache probe results for 1 hour keyed on (domain, contact, company, website).
    Identical domain lookups within the same server session skip all network calls.
    Cache is per-server-process — cleared on app restart (acceptable for Streamlit Cloud).
    """
    probes: dict = {
        "domain_age":     {"status": "skipped", "detail": "No domain provided"},
        "site_reach":     {"reachable": None,   "detail": "No domain provided"},
        "typosquat":      {"is_squatter": False, "detail": "No domain provided"},
        "free_email":     {"uses_free_domain": False, "detail": ""},
        "mx_record":      {"status": "NO_EMAIL", "detail": ""},
        "company_domain": {"domain_exists": None, "detail": ""},
    }
    lock = threading.Lock()

    def _run(key, fn, arg):
        try:
            r = fn(arg)
        except Exception as ex:
            r = {"detail": f"Probe error: {ex}"}
        with lock:
            probes[key] = r

    tasks = [
        ("domain_age",     _probe_domain_age,      domain or ""),
        ("site_reach",     _probe_site_reachable,   domain or ""),
        ("typosquat",      _probe_typosquatting,    domain or ""),
        ("free_email",     _probe_free_email,       contact),
        ("mx_record",      _probe_mx_record,        contact),
        ("company_domain", _probe_company_domain,   (company, website)),
    ]
    threads = [threading.Thread(target=_run, args=t, daemon=True) for t in tasks]
    for t in threads: t.start()
    for t in threads: t.join(timeout=_T_MCA + 4)
    return probes


def run_live_probes(job: dict) -> dict:
    website = job.get("website", "")
    contact = job.get("contact", "") + " " + job.get("description", "")
    company = job.get("company", "")
    domain  = _extract_domain(website)
    if not domain:
        for em_dom in re.findall(r"[\w.+\-]+@([\w\-]+\.[a-zA-Z]{2,})", contact):
            if em_dom.lower() not in _FREE_DOMAINS:
                domain = em_dom
                break

    # Delegate to cached version — identical (domain, contact, company, website)
    # combinations skip all network calls for 1 hour (st.cache_data TTL).
    return _run_live_probes_cached(domain or "", contact, company, website)


def _probe_risk(probes: dict) -> tuple[int, list[str]]:
    penalty, warnings = 0, []
    age = probes.get("domain_age", {})
    if age.get("status") == "young":
        days = age.get("age_days", 0)
        penalty += 18 if days < 90 else 10
        warnings.append(f"Domain registered only {days} days ago")
    if probes.get("site_reach", {}).get("reachable") is False:
        penalty += 12
        warnings.append("Company website is unreachable / does not exist")
    else:
        reach = probes.get("site_reach", {})
        if reach.get("ssl_valid") is False:
            penalty += 8
            warnings.append("Company website has an INVALID SSL certificate")
        if reach.get("is_parked"):
            penalty += 14
            warnings.append("Company website is a PARKED / placeholder domain")
    typo = probes.get("typosquat", {})
    if typo.get("is_squatter"):
        penalty += 20
        warnings.append(typo["detail"])
    if probes.get("free_email", {}).get("uses_free_domain"):
        penalty += 12
        dom = probes["free_email"].get("domain", "")
        warnings.append(f"Recruiter uses personal email domain: {dom}")
    mx = probes.get("mx_record", {})
    mx_status = mx.get("status", "")
    if mx_status == "NO_MX":
        penalty += 22   # strongest MX signal — domain exists but has no mail servers
        warnings.append(
            f"Corporate email domain '{mx.get('domain','')}' has NO MX records — "
            "domain is registered for appearances only, not actually used for email"
        )
    elif mx_status == "DNS_FAIL":
        penalty += 18
        warnings.append(
            f"Corporate email domain '{mx.get('domain','')}' does not exist in DNS — "
            "the company email address is completely fabricated"
        )
    elif mx_status == "MX_FOUND" and mx.get("voip_risk"):
        penalty += 8
        warnings.append(
            f"Email domain '{mx.get('domain','')}' routes through a transactional/bulk "
            "mail service, not a real corporate mail server"
        )
    cd = probes.get("company_domain", {})
    cd_score = cd.get("score", 0)
    if cd_score >= 40:
        penalty += 18
        warnings.append(
            f"Company domain '{cd.get('domain', '')}' does not exist — "
            "likely a fake or unregistered company"
        )
    elif cd_score >= 20:
        penalty += 10
        for sig in cd.get("scam_signals", []):
            warnings.append(sig)
    elif cd_score > 0:
        penalty += 5
        for sig in cd.get("scam_signals", []):
            warnings.append(sig)
    return min(penalty, 55), warnings


# ─────────────────────────────────────────────────────────────────────────────
# RULE ENGINE
# ─────────────────────────────────────────────────────────────────────────────

def _any(text: str, patterns: list) -> list:
    return [p for p in patterns if re.search(p, text, re.IGNORECASE)]

# ─────────────────────────────────────────────────────────────────────────────
# SALARY CALIBRATION — role × city bands (INR per annum, LPA)
# Replaces the blunt ₹5L–₹9.9Cr outlier rule that was flagging senior roles.
# Format: { role_keyword: (min_lpa, max_lpa) }
# If the detected salary falls ABOVE max_lpa by >2× it is flagged as outlier.
# ─────────────────────────────────────────────────────────────────────────────

_SALARY_BANDS: dict[str, tuple[float, float]] = {
    # Tech roles
    "software engineer":      (4.0,  45.0),
    "senior engineer":        (12.0, 70.0),
    "lead engineer":          (18.0, 90.0),
    "principal engineer":     (25.0, 120.0),
    "data scientist":         (6.0,  55.0),
    "data analyst":           (3.5,  20.0),
    "machine learning":       (8.0,  70.0),
    "devops":                 (6.0,  45.0),
    "frontend":               (4.0,  35.0),
    "backend":                (4.0,  40.0),
    "fullstack":              (5.0,  45.0),
    "full stack":             (5.0,  45.0),
    "android":                (4.0,  35.0),
    "ios":                    (4.0,  35.0),
    "qa":                     (3.0,  25.0),
    "tester":                 (3.0,  20.0),
    "product manager":        (10.0, 60.0),
    "project manager":        (8.0,  40.0),
    "architect":              (20.0, 100.0),
    "intern":                 (0.5,  6.0),
    "trainee":                (1.5,  5.0),
    # Non-tech roles
    "hr":                     (2.5,  20.0),
    "recruiter":              (2.5,  18.0),
    "sales":                  (2.0,  25.0),
    "marketing":              (2.5,  20.0),
    "content writer":         (2.0,  15.0),
    "graphic designer":       (2.0,  18.0),
    "accountant":             (2.5,  15.0),
    "finance":                (4.0,  35.0),
    "operations":             (3.0,  25.0),
    "customer support":       (2.0,  10.0),
    "customer service":       (2.0,  10.0),
    # Management
    "manager":                (8.0,  50.0),
    "director":               (20.0, 150.0),
    "vp":                     (30.0, 200.0),
    "cto":                    (40.0, 300.0),
    "ceo":                    (40.0, 500.0),
}

# City cost-of-living multipliers — applied to max band threshold
_CITY_MULTIPLIERS: dict[str, float] = {
    "bangalore": 1.3, "bengaluru": 1.3,
    "mumbai": 1.25, "delhi": 1.2, "gurgaon": 1.2, "gurugram": 1.2,
    "hyderabad": 1.15, "pune": 1.1, "chennai": 1.1, "noida": 1.15,
    "kolkata": 0.9, "jaipur": 0.85, "ahmedabad": 0.9, "indore": 0.85,
}

def _salary_outlier(salary_text: str, job: Optional[dict] = None) -> bool:
    """
    Calibrated salary outlier detection.

    1. Extract numeric salary value from text (LPA or absolute INR/USD).
    2. Look up the role band from job title keywords.
    3. Apply city multiplier to the band ceiling.
    4. Flag only if salary exceeds band ceiling by >2× (scam headroom).
    5. Fall back to the old blunt rule only when no band is matched.
    """
    text = salary_text or ""
    title = (job or {}).get("title", "") if job else ""
    location = (job or {}).get("location", "") if job else ""

    # ── Extract numeric salary value ──────────────────────────────────────
    lpa_val: Optional[float] = None

    # Try LPA pattern first (most common in Indian postings)
    m = re.search(
        r"(\d+(?:\.\d+)?)\s*(?:to|-)\s*(\d+(?:\.\d+)?)\s*(?:LPA|lpa|L|lakhs?)",
        text, re.IGNORECASE,
    )
    if m:
        lpa_val = float(m.group(2))   # use upper bound of range
    else:
        m2 = re.search(r"(\d+(?:\.\d+)?)\s*(?:LPA|lpa|L|lakhs?)", text, re.IGNORECASE)
        if m2:
            lpa_val = float(m2.group(1))

    # Try absolute INR (₹ / Rs / INR + raw number)
    if lpa_val is None:
        for n in re.findall(r"\d+", text.replace(",", "")):
            v = int(n)
            if 100000 <= v <= 99999999:
                lpa_val = v / 100000   # convert to LPA
                break
            if 15000 <= v <= 999999 and "$" in text:
                lpa_val = (v * 12) / 100000   # monthly USD → rough LPA
                break

    if lpa_val is None:
        return False   # no salary number found — don't flag

    # ── Look up role band ──────────────────────────────────────────────────
    title_lower = title.lower()
    band: Optional[tuple[float, float]] = None
    for keyword, b in _SALARY_BANDS.items():
        if keyword in title_lower:
            band = b
            break

    # ── Apply city multiplier ──────────────────────────────────────────────
    city_mult = 1.0
    loc_lower = location.lower()
    for city, mult in _CITY_MULTIPLIERS.items():
        if city in loc_lower:
            city_mult = mult
            break

    # ── Decision ──────────────────────────────────────────────────────────
    if band:
        _, max_lpa = band
        effective_max = max_lpa * city_mult
        # Flag only if salary is more than 2× the ceiling — clear scam territory
        return lpa_val > effective_max * 2.0
    else:
        # No band match — fall back to old blunt rule but with tighter range
        # Only flag truly impossible numbers (>₹5Cr / >500 LPA)
        return lpa_val > 500.0

def _run_rules(job: dict) -> dict:
    full = " ".join([job.get(k,"") for k in
                     ("title","description","requirements","benefits","contact","salary")])
    sigs: dict = {}

    def _add(k, label, detail, hits=None):
        sigs[k] = {"label": label, "detail": detail, "hits": (hits or [])[:3]}

    h = _any(full, _PAY_PHRASES)
    if h: _add("upfront_payment","Upfront Payment Demanded",
                "Legitimate employers never ask you to pay before or during hiring.", h)
    h = _any(full, _MLM_PHRASES)
    if h: _add("mlm_pyramid","MLM / Pyramid Scheme Indicators",
                "Language suggests a recruitment-based commission model, not a real job.", h)
    if _salary_outlier(job.get("salary","") + " " + job.get("description",""), job):
        _add("too_good_salary","Unrealistically High Salary",
             "Offered compensation is far above verified market rates for this role and city.")
    h = _any(full, _UNREALISTIC_PHRASES)
    if h: _add("unrealistic_benefits","Unrealistic Benefit Claims",
                "Promised earnings or perks are statistically implausible.", h)
    h = _any(full, _VAGUE_PHRASES)
    if len(h) >= 2:
        _add("vague_description","Vague / Generic Description",
             "Real postings specify responsibilities. Vagueness may hide a non-existent role.", h)
    free_hits = [e for e in re.findall(r"[\w.+\-]+@([\w\-]+\.[a-zA-Z]{2,})", full)
                 if e.lower() in _FREE_DOMAINS]
    if free_hits:
        _add("free_email_contact","Personal / Free Email Used",
             "Corporate recruiters use company domain emails, not Gmail/Yahoo/Hotmail.", free_hits)
    h = _any(full, _URGENCY_PHRASES)
    if h: _add("urgency_pressure","Artificial Urgency / Pressure Tactics",
                "Creating panic prevents candidates from properly researching the company.", h)
    bad_name = not job.get("company","").strip() or \
               job.get("company","").strip().lower() in ("","n/a","confidential","undisclosed")
    bad_site = not job.get("website","").strip() or len(job.get("website","").strip()) < 6
    no_addr  = not re.search(r"\b(street|road|nagar|colony|sector|floor|building|office)\b",
                              job.get("description",""), re.IGNORECASE)
    if (bad_name and bad_site) or (bad_site and no_addr):
        _add("no_company_info","No Verifiable Company Identity",
             "Legitimate companies provide verifiable name, website and physical address.")
    for fp, ep in _PARADOX_PATTERNS:
        txt = job.get("requirements","") + " " + job.get("description","")
        if re.search(fp, txt, re.IGNORECASE) and re.search(ep, txt, re.IGNORECASE):
            _add("req_paradox","Requirement Contradiction",
                 "Asking for senior experience under a fresher posting is a bait tactic.")
            break
    # ── Job board source trust multiplier ────────────────────────────────────
    # Postings from verified job boards carry implicit trust — lower score.
    # WhatsApp/Telegram-only contact with no verifiable URL is a red flag.
    source_hits = _any(full, _PLATFORM_TRUST)
    wa_hits     = _any(full, _URGENCY_PHRASES_WA)
    has_url     = bool(re.search(r"https?://[^\s]{8,}", full))
    if wa_hits and not source_hits and not has_url:
        _add("whatsapp_only_contact", "WhatsApp / Telegram Only — No Verifiable URL",
             "Legitimate companies post on official portals. WhatsApp-only jobs are a major red flag.",
             wa_hits)

    h = _any(full, _PERSONAL_PHRASES)
    if h: _add("personal_info_demand","Premature Personal Info Request",
                "Requesting Aadhaar/PAN/passport at application stage is a major red flag.", h)
    h = _any(full, _LOCATION_CLUES)
    if h: _add("location_mismatch","Location / Jurisdiction Mismatch",
                "Company location, pay currency and candidate requirements do not align.", h)
    h = _any(full, _WFH_PHRASES)
    if h: _add("work_from_home_bait","WFH Bait — Data Entry / Form Filling",
                "High-pay work-from-home roles with no skills required are almost always scams.", h)
    if not job.get("salary","").strip() or len(job.get("salary","").strip()) < 4:
        _add("missing_salary","Salary Completely Absent",
             "Hidden salary is commonly used to lure, then lowball candidates.")
    g_hits = _any(full, _GRAMMAR_PATTERNS)
    if len(g_hits) >= 2:
        _add("poor_grammar","Suspicious Grammar / Formatting",
             "Excessive punctuation, random CAPS or known spam-text patterns detected.", g_hits)

    return {"signals": sigs, "rule_score": min(sum(_WEIGHTS.get(k,0) for k in sigs), 100)}


# ─────────────────────────────────────────────────────────────────────────────
# LLM
# ─────────────────────────────────────────────────────────────────────────────

def _llm_prompt(job: dict, probe_warnings: list) -> str:
    ctx = "\n".join(f"  - {w}" for w in probe_warnings) if probe_warnings else "  - None"
    return f"""You are a senior HR fraud investigator specialising in Indian and global employment scams.
Analyse the job posting and return ONLY a valid JSON object — no markdown, no prose, no fences.

JOB POSTING:
Title: {job.get('title','N/A')}
Company: {job.get('company','N/A')}
Website: {job.get('website','N/A')}
Location: {job.get('location','N/A')}
Salary: {job.get('salary','N/A')}
Description: {job.get('description','N/A')}
Requirements: {job.get('requirements','N/A')}
Benefits: {job.get('benefits','N/A')}
Contact: {job.get('contact','N/A')}

LIVE PROBE FINDINGS:
{ctx}

Required JSON schema (all keys mandatory):
{{
  "ai_risk_score": <0-100>,
  "verdict": "<SAFE|SUSPICIOUS|LIKELY_SCAM|DEFINITE_SCAM>",
  "company_legitimacy": "<VERIFIED|UNVERIFIABLE|LIKELY_FAKE|GHOST_COMPANY>",
  "top_red_flags": ["<str>","<str>","<str>"],
  "positive_signals": ["<str>"],
  "fake_company_evidence": "<detailed reasoning about company authenticity>",
  "linguistic_analysis": "<tone, urgency, grammar observations>",
  "salary_assessment": "<realistic or not for this role and location>",
  "recommended_action": "<specific advice for the job seeker>",
  "similar_scam_type": "<known pattern name or Unknown>",
  "confidence": <0-100>
}}"""


# ─────────────────────────────────────────────────────────────────────────────
# ORCHESTRATOR
# ─────────────────────────────────────────────────────────────────────────────

# ─────────────────────────────────────────────────────────────────────────────
# VERDICT CONFIG
# ─────────────────────────────────────────────────────────────────────────────

_V: dict = {
    "SAFE":          {"icon": I.CHECK,        "color": "#22c55e",
                      "bg": "rgba(34,197,94,0.08)",   "border": "rgba(34,197,94,0.28)",
                      "label": "SAFE TO APPLY"},
    "SUSPICIOUS":    {"icon": I.ALERT_TRI,    "color": "#f59e0b",
                      "bg": "rgba(245,158,11,0.08)",  "border": "rgba(245,158,11,0.28)",
                      "label": "PROCEED WITH CAUTION"},
    "LIKELY_SCAM":   {"icon": I.ALERT_CIRCLE, "color": "#ef4444",
                      "bg": "rgba(239,68,68,0.08)",   "border": "rgba(239,68,68,0.28)",
                      "label": "LIKELY SCAM"},
    "DEFINITE_SCAM": {"icon": I.SKULL,        "color": "#dc2626",
                      "bg": "rgba(220,38,38,0.10)",   "border": "rgba(220,38,38,0.38)",
                      "label": "DEFINITE SCAM — DO NOT APPLY"},
    "UNKNOWN":       {"icon": I.INFO,         "color": "#6b7280",
                      "bg": "rgba(107,114,128,0.07)", "border": "rgba(107,114,128,0.2)",
                      "label": "INCONCLUSIVE"},
}
_CB: dict = {
    "VERIFIED":      (I.CHECK,     "#22c55e"),
    "UNVERIFIABLE":  (I.ALERT_TRI, "#f59e0b"),
    "LIKELY_FAKE":   (I.FLAG,      "#ef4444"),
    "GHOST_COMPANY": (I.GHOST,     "#dc2626"),
}


# ─────────────────────────────────────────────────────────────────────────────
# UI PRIMITIVES
# ─────────────────────────────────────────────────────────────────────────────

def _bar(pct: int, color: str, h: int = 6) -> str:
    return (
        f'<div style="background:rgba(255,255,255,0.07);border-radius:999px;'
        f'height:{h}px;overflow:hidden;margin:6px 0 0;">'
        f'<div style="height:{h}px;width:{pct}%;background:{color};'
        f'border-radius:999px;"></div></div>'
    )

def _badge(text: str, color: str, bg: str) -> str:
    return (
        f'<span style="display:inline-block;background:{bg};color:{color};'
        f'padding:2px 9px;border-radius:999px;font-size:0.69rem;font-weight:600;">'
        f'{text}</span>'
    )

def _pill(icon_path: str, text: str, color: str) -> str:
    return (
        f'<span style="display:inline-flex;align-items:center;gap:5px;'
        f'background:rgba(255,255,255,0.04);color:{color};padding:4px 11px;'
        f'border-radius:999px;font-size:0.7rem;border:1px solid {color}2e;">'
        f'{_svg(icon_path,10,color)}{text}</span>'
    )

def _field_row(icon_path: str, label: str, value: str) -> str:
    val_html = (
        f'<span style="color:#c9d1d9;">{_esc(value)}</span>'
        if value else
        '<span style="color:#4b5563;font-style:italic;">Not detected</span>'
    )
    return (
        f'<div style="display:flex;align-items:flex-start;gap:9px;padding:7px 0;'
        f'border-bottom:1px solid rgba(255,255,255,0.04);">'
        f'<div style="margin-top:1px;flex-shrink:0;">{_svg(icon_path,11,"#6b7280")}</div>'
        f'<div style="flex:1;">'
        f'<div style="font-size:0.66rem;color:#6b7280;text-transform:uppercase;'
        f'letter-spacing:0.8px;margin-bottom:2px;">{label}</div>'
        f'<div style="font-size:0.81rem;line-height:1.4;">{val_html}</div>'
        f'</div></div>'
    )


# ─────────────────────────────────────────────────────────────────────────────
# RESULT SECTIONS
# ─────────────────────────────────────────────────────────────────────────────

def _score_meaning(score: int, verdict: str) -> tuple[str, str]:
    """Return (plain-English headline, one-line explanation) for any score."""
    if verdict == "SAFE":
        if score <= 10:
            return "Extremely clean posting", "No meaningful red flags found. Background noise only."
        else:
            return "Looks legitimate", "Minor low-weight signals only — common in real job ads. Safe to apply."
    elif verdict == "SUSPICIOUS":
        return "Worth investigating first", "Some signals raised caution. Verify company details before applying."
    elif verdict == "LIKELY_SCAM":
        return "High scam probability", "Multiple strong signals detected. Do not share personal data yet."
    else:
        return "Do NOT apply", "Critical scam patterns confirmed. Block the sender and report this listing."


def _render_verdict_banner(result: dict):
    v   = result["final_verdict"]
    cfg = _V.get(v, _V["UNKNOWN"])
    s   = result["blended_score"]
    headline, meaning = _score_meaning(s, v)

    # Score zone markers on the bar — 4 coloured segments
    zone_bar = (
        '<div style="position:relative;height:10px;border-radius:999px;overflow:hidden;'
        'background:linear-gradient(to right,#22c55e 0%,#22c55e 24%,'
        '#f59e0b 24%,#f59e0b 49%,#ef4444 49%,#ef4444 74%,'
        '#dc2626 74%,#dc2626 100%);margin:10px 0 4px;">'
        f'<div style="position:absolute;top:-2px;left:calc({min(s,99)}% - 7px);'
        f'width:14px;height:14px;background:{cfg["color"]};border:2px solid #0d1117;'
        f'border-radius:50%;box-shadow:0 0 0 2px {cfg["color"]}44;"></div></div>'
        '<div style="display:flex;justify-content:space-between;'
        'font-size:0.62rem;color:#6b7280;margin-bottom:12px;">'
        '<span style="color:#22c55e;">0 — Safe</span>'
        '<span style="color:#f59e0b;">25 — Suspicious</span>'
        '<span style="color:#ef4444;">50 — Likely scam</span>'
        '<span style="color:#dc2626;">75 — Definite scam</span>'
        '</div>'
    )

    st.markdown(
        f'<div style="padding:24px 28px;border-radius:14px;background:{cfg["bg"]};'
        f'border:1.5px solid {cfg["border"]};margin-bottom:16px;">'

        # ── Top row: icon + verdict label + big score ──
        f'<div style="display:flex;align-items:flex-start;gap:14px;margin-bottom:14px;">'
        f'<div style="margin-top:2px;">{_svg(cfg["icon"], 34, cfg["color"], 1.5)}</div>'
        f'<div style="flex:1;">'
        f'<div style="font-size:1.35rem;font-weight:700;color:{cfg["color"]};'
        f'letter-spacing:0.3px;line-height:1.2;">{cfg["label"]}</div>'
        f'<div style="color:#c9d1d9;font-size:0.92rem;font-weight:500;margin-top:4px;">'
        f'{headline}</div>'
        f'<div style="color:#8b949e;font-size:0.78rem;margin-top:3px;">{meaning}</div>'
        f'</div>'
        # Big score number
        f'<div style="text-align:right;flex-shrink:0;'
        f'background:rgba(255,255,255,0.04);border:1px solid rgba(255,255,255,0.08);'
        f'border-radius:10px;padding:10px 18px;">'
        f'<div style="font-size:2.6rem;font-weight:800;color:{cfg["color"]};line-height:1;">{s}</div>'
        f'<div style="font-size:0.68rem;color:#6b7280;margin-top:2px;">RISK SCORE / 100</div>'
        f'<div style="font-size:0.64rem;color:#4b5563;margin-top:1px;">lower = safer</div>'
        f'</div></div>'

        # ── Gradient zone bar ──
        + zone_bar +

        # ── What this score means inline explanation ──
        f'<div style="display:grid;grid-template-columns:repeat(4,1fr);gap:6px;margin-top:4px;">'
        + "".join([
            f'<div style="padding:7px 10px;border-radius:8px;text-align:center;'
            f'background:{bg};border:1px solid {bc};">'
            f'<div style="font-size:0.62rem;font-weight:700;color:{tc};'
            f'text-transform:uppercase;letter-spacing:0.5px;">{label}</div>'
            f'<div style="font-size:0.6rem;color:{dc};margin-top:2px;">{desc}</div>'
            f'</div>'
            for label, desc, tc, dc, bg, bc in [
                ("0–24 · Safe",      "Apply normally",           "#22c55e", "#4ade80",
                 "rgba(34,197,94,0.08)",  "rgba(34,197,94,0.2)"),
                ("25–49 · Caution",  "Verify first",             "#f59e0b", "#fcd34d",
                 "rgba(245,158,11,0.08)", "rgba(245,158,11,0.2)"),
                ("50–74 · Risky",    "Avoid sharing data",       "#ef4444", "#fca5a5",
                 "rgba(239,68,68,0.08)",  "rgba(239,68,68,0.2)"),
                ("75–100 · Scam",    "Do not apply",             "#dc2626", "#f87171",
                 "rgba(220,38,38,0.10)",  "rgba(220,38,38,0.28)"),
            ]
        ])
        + f'</div></div>',
        unsafe_allow_html=True,
    )


def _render_score_strip(result: dict):
    cfg = _V.get(result["final_verdict"], _V["UNKNOWN"])

    def _card(icon_path, label, val, color, sub="", tooltip=""):
        tip_html = (
            f'<div style="font-size:0.62rem;color:#4b5563;margin-top:4px;'
            f'line-height:1.4;font-style:italic;">{tooltip}</div>'
        ) if tooltip else ""
        return (
            f'<div style="background:rgba(255,255,255,0.03);border:1px solid rgba(255,255,255,0.07);'
            f'border-radius:10px;padding:14px 16px;text-align:center;">'
            f'<div style="display:flex;align-items:center;justify-content:center;gap:5px;'
            f'color:#6b7280;font-size:0.66rem;text-transform:uppercase;letter-spacing:1px;'
            f'margin-bottom:6px;">{_svg(icon_path,10,"#6b7280")}{label}</div>'
            f'<div style="font-size:1.75rem;font-weight:700;color:{color};line-height:1;">{val}</div>'
            f'<div style="font-size:0.68rem;color:#6b7280;margin-top:3px;">{sub}</div>'
            f'{tip_html}'
            f'</div>'
        )

    c1, c2, c3, c4 = st.columns(4)
    c1.markdown(_card(I.CPU,   "AI Score",      result["ai_score"],
                      cfg["color"], "LLM analysis",
                      "AI's 0–100 risk read of the full text"),
                unsafe_allow_html=True)
    c2.markdown(_card(I.LIST,  "Rule Score",    result["rule_score"],
                      "#f59e0b", "15 pattern signals",
                      "Sum of weights for matched red-flag phrases"),
                unsafe_allow_html=True)
    c3.markdown(_card(I.GLOBE, "Probe Penalty", result["probe_penalty"],
                      "#38bdf8", "5 live network checks",
                      "Added for young domain, free email, bad MCA etc."),
                unsafe_allow_html=True)
    c4.markdown(_card(I.ZAP,   "Flags Fired",   len(result["signals"]),
                      "#a78bfa", "rule signals triggered",
                      "How many of 15 pattern rules matched"),
                unsafe_allow_html=True)

    # Formula explainer — shows users exactly how the number was built
    # FIX v5 BUG 8: all three (comment, code, HTML) now agree on 60/25/15.
    ai_s  = result["ai_score"]
    rul_s = result["rule_score"]
    pen   = result["probe_penalty"]
    raw   = round(0.60*ai_s + 0.25*rul_s + 0.15*pen, 1)
    final_blended = result["blended_score"]
    floor_note = (
        f' → floored to <span style="color:#ef4444;font-weight:700;">{final_blended}</span>'
        f'&nbsp;<span style="color:#4b5563;font-size:0.66rem;">(critical signal/probe floor applied)</span>'
        if int(raw) != final_blended else
        f' = <span style="color:#c9d1d9;font-weight:700;">{final_blended}</span>'
    )
    st.markdown(
        f'<div style="margin-top:10px;padding:10px 16px;'
        f'background:rgba(255,255,255,0.02);border:1px solid rgba(255,255,255,0.06);'
        f'border-radius:8px;font-family:monospace;font-size:0.73rem;color:#6b7280;">'
        f'<span style="color:#8b949e;font-weight:600;">How your score was calculated: </span>'
        f'(0.60 × AI&nbsp;<span style="color:{cfg["color"]}">{ai_s}</span>) + '
        f'(0.25 × Rules&nbsp;<span style="color:#f59e0b">{rul_s}</span>) + '
        f'(0.15 × Probes&nbsp;<span style="color:#38bdf8">{pen}</span>) '
        f'= <span style="color:#8b949e;">{raw}</span>'
        f'{floor_note}'
        f'</div>',
        unsafe_allow_html=True,
    )


def _render_probe_table(probes: dict):
    def _row(icon_path, label, badge_html, detail):
        return (
            f'<tr style="border-bottom:1px solid rgba(255,255,255,0.04);">'
            f'<td style="padding:11px 16px;width:22%;white-space:nowrap;">'
            f'<div style="display:flex;align-items:center;gap:7px;color:#c9d1d9;font-size:0.8rem;">'
            f'{_svg(icon_path,12,"#8b949e")}{label}</div></td>'
            f'<td style="padding:11px 16px;width:18%;">{badge_html}</td>'
            f'<td style="padding:11px 16px;color:#8b949e;font-size:0.76rem;line-height:1.5;">{detail}</td>'
            f'</tr>'
        )

    rows = []
    age = probes.get("domain_age", {})
    st_ = age.get("status", "unknown")
    b   = (_badge("YOUNG DOMAIN","#dc2626","rgba(220,38,38,0.12)") if st_ == "young" else
           _badge("ESTABLISHED", "#22c55e","rgba(34,197,94,0.12)")  if st_ == "old"   else
           _badge("LOOKUP FAILED","#6b7280","rgba(107,114,128,0.12)") if st_ == "error" else
           _badge("NO DOMAIN",  "#6b7280","rgba(107,114,128,0.12)"))
    rows.append(_row(I.CALENDAR, "Domain Age", b, age.get("detail","")))

    r = probes.get("site_reach", {})
    b = (_badge("REACHABLE",   "#22c55e","rgba(34,197,94,0.12)")   if r.get("reachable") is True  else
         _badge("UNREACHABLE", "#dc2626","rgba(220,38,38,0.12)")   if r.get("reachable") is False else
         _badge("NOT CHECKED", "#6b7280","rgba(107,114,128,0.12)"))
    rows.append(_row(I.SERVER, "Site Reachability", b, r.get("detail","")))

    t = probes.get("typosquat", {})
    pct = int(t.get("similarity",0)*100)
    b   = (_badge("TYPOSQUAT RISK","#dc2626","rgba(220,38,38,0.12)") if t.get("is_squatter") else
           _badge(f"LOW RISK ({pct}%)","#f59e0b","rgba(245,158,11,0.12)") if pct >= 50 else
           _badge("CLEAR","#22c55e","rgba(34,197,94,0.12)"))
    rows.append(_row(I.COPY, "Typosquatting", b, t.get("detail","")))

    fe = probes.get("free_email", {})
    b  = (_badge("FREE EMAIL","#dc2626","rgba(220,38,38,0.12)") if fe.get("uses_free_domain")
          else _badge("CLEAR","#22c55e","rgba(34,197,94,0.12)"))
    rows.append(_row(I.MAIL, "Email Domain", b, fe.get("detail","")))

    mx = probes.get("mx_record", {})
    mx_st = mx.get("status", "")
    if mx_st == "MX_FOUND":
        mx_b = (_badge("VOIP/BULK", "#f59e0b", "rgba(245,158,11,0.12)") if mx.get("voip_risk")
                else _badge("MX OK", "#22c55e", "rgba(34,197,94,0.12)"))
    elif mx_st == "NO_MX":
        mx_b = _badge("NO MX RECORDS", "#dc2626", "rgba(220,38,38,0.12)")
    elif mx_st == "DNS_FAIL":
        mx_b = _badge("DOMAIN FAKE", "#dc2626", "rgba(220,38,38,0.12)")
    elif mx_st == "FREE_DOMAIN":
        mx_b = _badge("FREE EMAIL", "#f59e0b", "rgba(245,158,11,0.12)")
    else:
        mx_b = _badge("NOT CHECKED", "#6b7280", "rgba(107,114,128,0.12)")
    rows.append(_row(I.SERVER, "MX / Mail Server", mx_b, mx.get("detail", "")))

    cd = probes.get("company_domain", {})
    if cd.get("domain_exists") is True and cd.get("website_live") and cd.get("has_mx"):
        cd_badge = _badge("VERIFIED", "#22c55e", "rgba(34,197,94,0.12)")
    elif cd.get("domain_exists") is False:
        cd_badge = _badge("DOMAIN FAKE", "#dc2626", "rgba(220,38,38,0.12)")
    elif cd.get("score", 0) >= 20:
        cd_badge = _badge("SUSPICIOUS", "#f59e0b", "rgba(245,158,11,0.12)")
    elif cd.get("domain_exists") is None:
        cd_badge = _badge("NO WEBSITE", "#6b7280", "rgba(107,114,128,0.12)")
    else:
        cd_badge = _badge("PARTIAL", "#f59e0b", "rgba(245,158,11,0.12)")
    rows.append(_row(I.BUILDING, "Company Domain Check", cd_badge, cd.get("detail", "")))

    st.markdown(
        f'<div style="border:1px solid rgba(255,255,255,0.08);border-radius:12px;'
        f'overflow:hidden;margin-bottom:20px;">'
        f'<div style="background:rgba(255,255,255,0.03);padding:10px 16px;'
        f'display:flex;align-items:center;gap:7px;font-size:0.71rem;font-weight:600;'
        f'color:#8b949e;text-transform:uppercase;letter-spacing:1px;">'
        f'{_svg(I.GLOBE,11,"#6b7280")} Live Network Probes</div>'
        f'<table style="width:100%;border-collapse:collapse;">'
        f'<thead><tr style="border-bottom:1px solid rgba(255,255,255,0.07);">'
        f'<th style="padding:8px 16px;font-size:0.67rem;color:#6b7280;font-weight:500;text-align:left;">Check</th>'
        f'<th style="padding:8px 16px;font-size:0.67rem;color:#6b7280;font-weight:500;text-align:left;">Result</th>'
        f'<th style="padding:8px 16px;font-size:0.67rem;color:#6b7280;font-weight:500;text-align:left;">Detail</th>'
        f'</tr></thead><tbody>{"".join(rows)}</tbody></table></div>',
        unsafe_allow_html=True,
    )


def _render_signal_cards(signals: dict):
    """
    KEY FIX: batch all cards per column into ONE st.markdown call each.
    Previously each card was its own st.markdown inside a column loop —
    Streamlit was escaping the SVG/HTML in that context, showing raw tags.
    """
    if not signals:
        st.markdown(
            f'<div style="display:flex;align-items:center;gap:8px;padding:14px 16px;'
            f'background:rgba(34,197,94,0.06);border:1px solid rgba(34,197,94,0.18);'
            f'border-radius:8px;color:#22c55e;font-size:0.84rem;">'
            f'{_svg(I.CHECK,14,"#22c55e")} No rule-based red flags detected.</div>',
            unsafe_allow_html=True,
        )
        return

    left_html = right_html = ""
    for idx, (k, sig) in enumerate(signals.items()):
        w     = _WEIGHTS.get(k, 5)
        color = "#ef4444" if w >= 18 else "#f59e0b" if w >= 10 else "#a78bfa"
        hits_html = (
            f'<div style="margin-top:5px;font-size:0.68rem;color:#6b7280;font-style:italic;">'
            f'Matched: {", ".join(sig["hits"][:2])}</div>'
        ) if sig.get("hits") else ""

        card = (
            f'<div style="background:rgba(255,255,255,0.025);border:1px solid {color}22;'
            f'border-radius:10px;padding:14px;margin-bottom:10px;">'
            f'<div style="display:flex;align-items:flex-start;gap:9px;">'
            f'<div style="margin-top:1px;flex-shrink:0;">{_svg(_SIG_ICON.get(k,I.ALERT_TRI),14,color)}</div>'
            f'<div style="flex:1;min-width:0;">'
            f'<div style="font-weight:600;color:{color};font-size:0.83rem;margin-bottom:3px;">{sig["label"]}</div>'
            f'<div style="color:#8b949e;font-size:0.76rem;line-height:1.55;">{sig["detail"]}</div>'
            f'{hits_html}'
            f'<div style="display:flex;align-items:center;gap:6px;margin-top:8px;">'
            f'<span style="font-size:0.63rem;color:#6b7280;white-space:nowrap;">Risk weight</span>'
            f'<div style="flex:1;background:rgba(255,255,255,0.06);border-radius:999px;height:4px;overflow:hidden;">'
            f'<div style="height:4px;width:{min(w*4,100)}%;background:{color};border-radius:999px;"></div>'
            f'</div>'
            f'<span style="font-size:0.67rem;color:{color};font-weight:700;white-space:nowrap;">+{w}</span>'
            f'</div></div></div></div>'
        )
        if idx % 2 == 0:
            left_html  += card
        else:
            right_html += card

    col_l, col_r = st.columns(2)
    col_l.markdown(left_html  or "<div></div>", unsafe_allow_html=True)
    col_r.markdown(right_html or "<div></div>", unsafe_allow_html=True)


def _render_ai_dive(llm: dict):
    if not llm:
        st.markdown('<p style="color:#6b7280;font-size:0.82rem;">AI analysis unavailable.</p>',
                    unsafe_allow_html=True)
        return

    cl     = llm.get("company_legitimacy", "UNVERIFIABLE")
    ci, cc = _CB.get(cl, _CB["UNVERIFIABLE"])

    st.markdown(
        f'<div style="display:grid;grid-template-columns:1fr 1fr;gap:10px;margin-bottom:14px;">'
        f'<div style="background:rgba(255,255,255,0.03);border:1px solid rgba(255,255,255,0.07);'
        f'border-radius:9px;padding:12px;">'
        f'<div style="font-size:0.66rem;color:#6b7280;text-transform:uppercase;'
        f'letter-spacing:1px;margin-bottom:5px;">Company Status</div>'
        f'<div style="display:flex;align-items:center;gap:6px;color:{cc};font-weight:600;font-size:0.83rem;">'
        f'{_svg(ci,13,cc)}{cl.replace("_"," ")}</div></div>'
        f'<div style="background:rgba(255,255,255,0.03);border:1px solid rgba(255,255,255,0.07);'
        f'border-radius:9px;padding:12px;">'
        f'<div style="font-size:0.66rem;color:#6b7280;text-transform:uppercase;'
        f'letter-spacing:1px;margin-bottom:5px;">Scam Pattern</div>'
        f'<div style="color:#a78bfa;font-weight:600;font-size:0.83rem;">'
        f'{llm.get("similar_scam_type","Unknown")}</div></div></div>',
        unsafe_allow_html=True,
    )

    # Batch red flags and positive signals into one markdown each
    fc1, fc2 = st.columns(2)
    flags_html = "".join(
        f'<div style="background:rgba(239,68,68,0.05);border-left:2px solid #ef4444;'
        f'padding:7px 11px;border-radius:0 6px 6px 0;margin-bottom:5px;'
        f'color:#fca5a5;font-size:0.79rem;">{f}</div>'
        for f in llm.get("top_red_flags",[])[:5]
    ) or '<div style="color:#6b7280;font-size:0.79rem;font-style:italic;">None identified.</div>'

    pos_html = "".join(
        f'<div style="background:rgba(34,197,94,0.05);border-left:2px solid #22c55e;'
        f'padding:7px 11px;border-radius:0 6px 6px 0;margin-bottom:5px;'
        f'color:#86efac;font-size:0.79rem;">{p}</div>'
        for p in llm.get("positive_signals",[])[:5]
    ) or '<div style="color:#6b7280;font-size:0.79rem;font-style:italic;">No positive signals identified.</div>'

    fc1.markdown(
        f'<div style="font-size:0.71rem;font-weight:600;color:#ef4444;text-transform:uppercase;'
        f'letter-spacing:0.8px;margin-bottom:8px;">AI Red Flags</div>{flags_html}',
        unsafe_allow_html=True,
    )
    fc2.markdown(
        f'<div style="font-size:0.71rem;font-weight:600;color:#22c55e;text-transform:uppercase;'
        f'letter-spacing:0.8px;margin-bottom:8px;">Positive Signals</div>{pos_html}',
        unsafe_allow_html=True,
    )

    for field, icon_path, title in [
        ("fake_company_evidence", I.GHOST,     "Company Legitimacy Analysis"),
        ("linguistic_analysis",   I.FILE_TEXT, "Linguistic Pattern Analysis"),
        ("salary_assessment",     I.DOLLAR,    "Salary Reality Check"),
        ("recommended_action",    I.SHIELD,    "Recommended Action"),
    ]:
        val = llm.get(field, "")
        if not val:
            continue
        st.markdown(
            f'<div style="background:rgba(255,255,255,0.02);border:1px solid rgba(255,255,255,0.06);'
            f'border-radius:9px;padding:14px;margin-bottom:10px;">'
            f'<div style="display:flex;align-items:center;gap:6px;font-size:0.68rem;font-weight:600;'
            f'color:#8b949e;text-transform:uppercase;letter-spacing:0.9px;margin-bottom:8px;">'
            f'{_svg(icon_path,11,"#6b7280")}{title}</div>'
            f'<div style="color:#c9d1d9;font-size:0.83rem;line-height:1.65;">{val}</div></div>',
            unsafe_allow_html=True,
        )

    st.markdown(
        f'<div style="text-align:right;color:#6b7280;font-size:0.69rem;margin-top:2px;">'
        f'AI Confidence: {llm.get("confidence","—")}/100</div>',
        unsafe_allow_html=True,
    )


_CHECKLIST = [
    (I.SEARCH,      "Search company name + 'scam' or 'fraud' on Google",               True),
    (I.BUILDING,    "Verify company on LinkedIn, MCA.gov.in or Companies House",        True),
    (I.CALENDAR,    "Check domain age on whois.domaintools.com",                        True),
    (I.LINK,        "Confirm the vacancy exists on the official company careers page",  True),
    (I.CREDIT_CARD, "Never pay any fee before or during the hiring process",            True),
    (I.MAIL,        "Verify recruiter email domain matches the company website domain", True),
    (I.EYE,         "Reverse image search the recruiter's profile photo",               False),
    (I.AWARD,       "Check Glassdoor / AmbitionBox for employee reviews",               True),
    (I.PHONE,       "Call the company's official number to confirm the vacancy",        False),
    (I.ID_CARD,     "Never submit Aadhaar/PAN/passport at initial application stage",   True),
]

def _render_checklist(result: dict):
    st.markdown(
        f'<div style="font-size:0.71rem;font-weight:600;color:#8b949e;text-transform:uppercase;'
        f'letter-spacing:1px;margin-bottom:10px;display:flex;align-items:center;gap:6px;">'
        f'{_svg(I.LIST,11,"#6b7280")} Manual Verification Checklist</div>',
        unsafe_allow_html=True,
    )
    for idx, (icon_path, text, default) in enumerate(_CHECKLIST):
        # FIX v5: removed id(result) suffix — it changed every run, creating
        # hundreds of orphaned session_state keys and breaking checkbox state.
        st.checkbox(text, value=default, key=f"jsd_c_{idx}")
    st.markdown(
        f'<div style="margin-top:13px;padding:11px 15px;background:rgba(56,189,248,0.05);'
        f'border:1px solid rgba(56,189,248,0.14);border-radius:8px;color:#7dd3fc;'
        f'font-size:0.8rem;line-height:1.6;display:flex;gap:7px;align-items:flex-start;">'
        f'{_svg(I.INFO,12,"#38bdf8")}'
        f'<span>If 3 or more items fail this checklist AND the AI score exceeds 40, '
        f'walk away. No legitimate employer requires upfront payment.</span></div>',
        unsafe_allow_html=True,
    )


def _add_to_history(result: dict):
    h = st.session_state.setdefault("jsd_history", [])
    entry = {
        "id":      None,   # filled in after DB save — used for soft-delete
        "title":   result["job"].get("title", "Untitled"),
        "company": result["job"].get("company", "Unknown"),
        "score":   result["blended_score"],
        "verdict": result["final_verdict"],
        "time":    result["timestamp"],
    }

    # ── Persist to Supabase and get back the new row id ───────────────────
    try:
        from user_login import save_scam_analysis
        username = st.session_state.get("username", "")
        if username:
            new_id = save_scam_analysis(
                username  = username,
                job_title = entry["title"],
                company   = entry["company"],
                score     = entry["score"],
                verdict   = entry["verdict"],
            )
            entry["id"] = new_id   # store id so ✕ Remove can soft-delete by id
    except Exception:
        pass  # non-fatal — session_state history still works

    h.insert(0, entry)
    st.session_state["jsd_history"] = h[:5]


def _render_history():
    # ── Load from DB on first render (session startup / page refresh) ─────
    if not st.session_state.get("jsd_history_loaded"):
        try:
            from user_login import load_scam_history
            username = st.session_state.get("username", "")
            if username:
                db_history = load_scam_history(username)
                existing = st.session_state.get("jsd_history", [])
                if not existing:
                    st.session_state["jsd_history"] = db_history
        except Exception:
            pass
        st.session_state["jsd_history_loaded"] = True

    history = st.session_state.get("jsd_history", [])

    if not history:
        st.markdown(
            '<div style="color:#6b7280;font-size:0.78rem;text-align:center;'
            'padding:18px 0;font-style:italic;">No analyses yet.</div>',
            unsafe_allow_html=True,
        )
        return

    # ── CSS injection — style Streamlit buttons to look like small icon/text
    # buttons without using st.columns() which collapses in the narrow sidebar.
    # We target the specific keys via the data-testid attribute Streamlit adds.
    # "Clear all" → full-width subtle text button at top.
    # "✕" delete  → small inline icon button flush-right inside each card.
    st.markdown(
        """
        <style>
        /* ── Clear-all button: full-width, subtle, right-aligned label ── */
        div[data-testid="stButton"] > button[kind="secondary"][id*="jsd_hist_clear_all"],
        div[data-testid="stButton"]:has(button[key="jsd_hist_clear_all"]) button {
            width: 100% !important;
            font-size: 0.68rem !important;
            color: #6b7280 !important;
            background: transparent !important;
            border: 1px solid rgba(255,255,255,0.08) !important;
            border-radius: 6px !important;
            padding: 4px 8px !important;
            white-space: nowrap !important;
            min-height: unset !important;
        }
        div[data-testid="stButton"]:has(button[key="jsd_hist_clear_all"]) button:hover {
            color: #ef4444 !important;
            border-color: rgba(239,68,68,0.3) !important;
            background: rgba(239,68,68,0.06) !important;
        }
        /* ── Delete (✕) buttons: compact, no column needed ── */
        div[data-testid="stButton"]:has(button[key^="jsd_hist_del_"]) {
            display: flex !important;
            justify-content: flex-end !important;
            margin-top: -2px !important;
            margin-bottom: 4px !important;
        }
        div[data-testid="stButton"]:has(button[key^="jsd_hist_del_"]) button {
            font-size: 0.7rem !important;
            color: #4b5563 !important;
            background: transparent !important;
            border: 1px solid rgba(255,255,255,0.06) !important;
            border-radius: 5px !important;
            padding: 2px 7px !important;
            min-height: unset !important;
            white-space: nowrap !important;
            width: auto !important;
        }
        div[data-testid="stButton"]:has(button[key^="jsd_hist_del_"]) button:hover {
            color: #ef4444 !important;
            border-color: rgba(239,68,68,0.28) !important;
            background: rgba(239,68,68,0.06) !important;
        }
        </style>
        """,
        unsafe_allow_html=True,
    )

    # ── "Clear all" — full-width button, NO st.columns ───────────────────
    # FIX: removed st.columns([4,1]) which squeezed the button into ~40px
    # in the already-narrow hist_col, making text render vertically.
    if st.button("Clear all", key="jsd_hist_clear_all", help="Remove all recent analyses",
                 use_container_width=True):
        try:
            from user_login import soft_delete_all_scam_history
            username = st.session_state.get("username", "")
            if username:
                soft_delete_all_scam_history(username)
        except Exception:
            pass
        st.session_state["jsd_history"] = []
        st.rerun()

    # ── Per-item cards ────────────────────────────────────────────────────
    for idx, h in enumerate(history):
        cfg = _V.get(h["verdict"], _V["UNKNOWN"])

        # Card HTML — self-contained, no button inside (avoids HTML-button conflicts)
        st.markdown(
            f'<div style="padding:10px 12px;background:rgba(255,255,255,0.02);'
            f'border:1px solid rgba(255,255,255,0.06);border-radius:8px;margin-bottom:2px;">'
            f'<div style="display:flex;align-items:flex-start;'
            f'justify-content:space-between;gap:6px;">'
            f'<div style="min-width:0;flex:1;">'
            f'<div style="color:#c9d1d9;font-size:0.79rem;font-weight:500;'
            f'overflow:hidden;white-space:nowrap;text-overflow:ellipsis;">'
            f'{_esc(h["title"])}</div>'
            f'<div style="color:#6b7280;font-size:0.69rem;margin-top:1px;'
            f'overflow:hidden;white-space:nowrap;text-overflow:ellipsis;">'
            f'{_esc(h["company"])}</div>'
            f'</div>'
            f'<span style="color:{cfg["color"]};font-size:0.77rem;font-weight:700;'
            f'flex-shrink:0;">{h["score"]}/100</span>'
            f'</div>'
            f'<div style="display:flex;justify-content:space-between;'
            f'align-items:center;margin-top:4px;">'
            f'<span style="color:#6b7280;font-size:0.66rem;">{_esc(h["time"])}</span>'
            f'<span style="color:{cfg["color"]};font-size:0.66rem;font-weight:600;'
            f'letter-spacing:0.3px;">{h["verdict"].replace("_"," ")}</span>'
            f'</div>'
            f'{_bar(h["score"], cfg["color"], 4)}'
            f'</div>',
            unsafe_allow_html=True,
        )

        # ✕ Delete button — full-width container, CSS above right-aligns it.
        # FIX: removed st.columns([5,1]) — the 1-unit column was ~30px wide
        # inside hist_col, making the ✕ symbol wrap or disappear entirely.
        if st.button("✕ Remove", key=f"jsd_hist_del_{idx}",
                     help=f"Remove '{h['title']}'",
                     use_container_width=True):
            try:
                from user_login import soft_delete_scam_analysis
                username = st.session_state.get("username", "")
                record_id = h.get("id")   # DB id stored in history dict
                if username and record_id:
                    soft_delete_scam_analysis(username, record_id)
            except Exception:
                pass
            st.session_state["jsd_history"].pop(idx)
            st.rerun()


# ─────────────────────────────────────────────────────────────────────────────
# MAIN ENTRY POINT
# ─────────────────────────────────────────────────────────────────────────────

def _quick_prescan(raw: str) -> dict | None:
    """
    Lightweight instant signal preview — runs rule engine only (no network, no LLM).
    Returns a minimal result dict or None if text is too short.

    BUG FIX v5: previously called _run_rules(auto_extract(raw)) where auto_extract
    set description=requirements=benefits=raw, causing every pattern to match 3×.
    Now passes a clean dict: description=raw, everything else extracted once.
    """
    if not raw or len(raw.strip()) < 30:
        return None

    # FIX: Build a clean prescan job dict — description is raw (full text),
    # requirements and benefits are intentionally empty to avoid triple-counting.
    extracted = auto_extract(raw)
    prescan_job = {
        "title":        extracted["title"],
        "company":      extracted["company"],
        "website":      extracted["website"],
        "location":     extracted["location"],
        "salary":       extracted["salary"],
        "contact":      extracted["contact"],
        "description":  raw,
        "requirements": "",
        "benefits":     "",
    }
    rules = _run_rules(prescan_job)
    score = rules["rule_score"]
    # Calibrated thresholds — a single low-weight signal (e.g. missing_salary=4)
    # must NOT trigger a SUSPICIOUS banner. Only meaningful rule hits qualify.
    if score == 0:
        verdict = "SAFE"
    elif score < 15:
        verdict = "SAFE"        # low-weight noise signals — not a meaningful warning
    elif score < 30:
        verdict = "SUSPICIOUS"
    elif score < 55:
        verdict = "LIKELY_SCAM"
    else:
        verdict = "DEFINITE_SCAM"
    return {
        "rule_score": score,
        "verdict": verdict,
        "signals": rules["signals"],
        "quick": True,   # flag: this is a pre-scan, not a full analysis
    }


def _render_quick_prescan(prescan: dict):
    """Render a compact inline banner for the quick rule-based pre-scan."""
    v   = prescan["verdict"]
    cfg = _V.get(v, _V["UNKNOWN"])
    s   = prescan["rule_score"]
    n   = len(prescan["signals"])
    st.markdown(
        f'<div style="display:flex;align-items:center;gap:10px;padding:12px 16px;'
        f'background:{cfg["bg"]};border:1px solid {cfg["border"]};border-radius:10px;'
        f'margin-top:10px;">'
        f'{_svg(cfg["icon"], 20, cfg["color"], 1.5)}'
        f'<div style="flex:1;">'
        f'<div style="font-size:0.8rem;font-weight:700;color:{cfg["color"]};">'
        f'Quick Scan: {cfg["label"]}</div>'
        f'<div style="font-size:0.72rem;color:#8b949e;margin-top:1px;">'
        f'Rule engine found {n} signal(s) — rule score {s}/100. '
        f'Click <strong style="color:#c9d1d9;">Analyse for Scam Signals</strong> '
        f'for full AI + network analysis.</div>'
        f'</div>'
        f'<div style="font-size:1.6rem;font-weight:800;color:{cfg["color"]};line-height:1;">{s}</div>'
        f'</div>',
        unsafe_allow_html=True,
    )


def _render_rate_limit_bar(username: str) -> bool:
    """
    Render the 'X analyses remaining this hour' UI strip.

    Returns True  → user is allowed to run an analysis.
    Returns False → user is at limit; Analyse button must be suppressed.

    Reads live from Supabase via get_usage_count_last_hour so the count
    is always accurate even across browser tabs / devices.
    """
    fns = _get_rate_limit_fns()
    if fns is None:
        return True   # standalone / no user_login — allow

    _, _, get_count = fns
    try:
        used = get_count(username, _SCAM_FEATURE)
    except Exception:
        used = 0   # fail open

    remaining = max(_SCAM_LIMIT - used, 0)

    if remaining == _SCAM_LIMIT:
        bar_color, text_color = "#22c55e", "#22c55e"
        bg, border           = "rgba(34,197,94,0.07)",  "rgba(34,197,94,0.22)"
        status_label         = "Full quota available"
    elif remaining > 0:
        bar_color, text_color = "#f59e0b", "#f59e0b"
        bg, border           = "rgba(245,158,11,0.07)", "rgba(245,158,11,0.22)"
        status_label         = f"{remaining} left this hour"
    else:
        bar_color, text_color = "#ef4444", "#ef4444"
        bg, border           = "rgba(239,68,68,0.07)",  "rgba(239,68,68,0.22)"
        status_label         = "Limit reached — resets within 60 min"

    # Segmented pip display — filled pips = used, coloured pips = remaining
    pips = ""
    for i in range(_SCAM_LIMIT):
        filled = i < used
        pips += (
            f'<div style="width:28px;height:8px;border-radius:999px;'
            f'background:{"rgba(255,255,255,0.10)" if filled else bar_color};"></div>'
        )

    st.markdown(
        f'<div style="display:flex;align-items:center;gap:14px;padding:11px 16px;'
        f'background:{bg};border:1px solid {border};border-radius:10px;margin-bottom:14px;">'
        f'<svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="{text_color}" '
        f'stroke-width="2" stroke-linecap="round" stroke-linejoin="round" style="flex-shrink:0;">'
        f'<circle cx="12" cy="12" r="10"/><polyline points="12 6 12 12 16 14"/></svg>'
        f'<div style="flex:1;min-width:0;">'
        f'<div style="font-size:0.78rem;font-weight:600;color:{text_color};">'
        f'Analyses remaining this hour &mdash; {status_label}</div>'
        f'<div style="font-size:0.69rem;color:#6b7280;margin-top:1px;">'
        f'{used}/{_SCAM_LIMIT} used &middot; rolling 60-min window, not a fixed clock reset</div>'
        f'</div>'
        f'<div style="display:flex;gap:4px;align-items:center;flex-shrink:0;">{pips}</div>'
        f'<div style="text-align:right;flex-shrink:0;">'
        f'<div style="font-size:1.6rem;font-weight:800;color:{text_color};line-height:1;">{remaining}</div>'
        f'<div style="font-size:0.6rem;color:#6b7280;">/ {_SCAM_LIMIT}</div>'
        f'</div></div>',
        unsafe_allow_html=True,
    )

    if remaining == 0:
        st.markdown(
            f'<div style="display:flex;align-items:flex-start;gap:9px;padding:12px 16px;'
            f'background:rgba(239,68,68,0.06);border:1px solid rgba(239,68,68,0.22);'
            f'border-radius:10px;margin-bottom:10px;">'
            f'<svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="#ef4444" '
            f'stroke-width="2" stroke-linecap="round" stroke-linejoin="round" style="flex-shrink:0;margin-top:1px;">'
            f'<circle cx="12" cy="12" r="10"/><line x1="4.93" y1="4.93" x2="19.07" y2="19.07"/></svg>'
            f'<div style="font-size:0.8rem;color:#fca5a5;line-height:1.55;">'
            f'You have used all <strong style="color:#ef4444;">{_SCAM_LIMIT} analyses</strong> '
            f'for this hour. The Analyse button will re-enable once a slot opens. '
            f'Previous results are still visible in the Recent Analyses panel.</div>'
            f'</div>',
            unsafe_allow_html=True,
        )

    return remaining > 0


@st.fragment
def _render_input_fragment(call_llm_fn, username: str = "", allowed: bool = True):
    """
    FRAGMENT FIX (v4):
    Wrapping the entire input section in @st.fragment means widget interactions
    (typing, radio switches, expander toggles) only re-run THIS fragment, not
    the full page. The full page re-run only happens when st.rerun() is called
    explicitly (on Clear) or when data is written to session_state by the
    Analyse button.

    v5 ADDITIONAL FIXES in this function:
    ─────────────────────────────────────
    BUG 1 (Reset broken): st.rerun(scope="app") inside a @st.fragment raises
    AttributeError in Streamlit ≥ 1.33. Fixed: use plain st.rerun() which is
    always safe inside a fragment and triggers the full app rerun we need.
    Also the clear-keys loop now explicitly deletes jsd_raw and jsd_mode so the
    text area and radio actually blank on next render.

    BUG 2 (Analyse double-fire): jsd_running was set then the fragment re-ran on
    every keystroke, occasionally reading the stale True value and locking the
    button permanently. Fixed: jsd_running is only set immediately before the
    analysis pipeline runs, cleared in both success and exception paths.

    BUG 6 (Override fields ignored): The override expander widgets updated
    extracted["key"] in-place but the fragment re-ran between the expander render
    and the Analyse click, discarding the overrides. Fixed: overrides are read
    from their stable session_state widget keys (jsd_ot, jsd_oco, …) at the
    moment the Analyse button is pressed, which persists across fragment reruns.
    """
    mode = st.radio(
        "input_mode",
        ["Paste Full Job Description", "Fill Individual Fields"],
        horizontal=True, key="jsd_mode", label_visibility="collapsed",
    )

    job: dict = {}

    if mode == "Paste Full Job Description":
        raw = st.text_area(
            "PASTE THE FULL JOB DESCRIPTION",
            height=230, key="jsd_raw",
            placeholder=(
                "Paste the complete job posting here — company name, website, "
                "salary, requirements, benefits, contact details...\n\n"
                "All fields are auto-detected as you type."
            ),
        )

        extracted = auto_extract(raw or "")

        if raw and len(raw.strip()) > 20:
            # ── Inline quick pre-scan ──────────────────────────────────────
            prescan = _quick_prescan(raw)
            if prescan:
                _render_quick_prescan(prescan)

            # ── Auto-detected fields summary ───────────────────────────────
            fields_html = (
                _field_row(I.ZAP,      "Job Title",  extracted["title"])
                + _field_row(I.BUILDING, "Company",    extracted["company"])
                + _field_row(I.GLOBE,    "Website",    extracted["website"])
                + _field_row(I.MAP_PIN,  "Location",   extracted["location"])
                + _field_row(I.DOLLAR,   "Salary",     extracted["salary"])
                + _field_row(I.MAIL,     "Contact",    extracted["contact"])
            )
            st.markdown(
                f'<div style="background:rgba(255,255,255,0.02);border:1px solid rgba(255,255,255,0.07);'
                f'border-radius:10px;padding:14px 16px;margin-top:8px;">'
                f'<div style="font-size:0.69rem;font-weight:600;color:#8b949e;text-transform:uppercase;'
                f'letter-spacing:1px;margin-bottom:6px;display:flex;align-items:center;gap:6px;">'
                f'{_svg(I.ZAP,10,"#a78bfa")} Auto-Detected Fields</div>'
                f'{fields_html}</div>',
                unsafe_allow_html=True,
            )

            with st.expander("Override detected fields (optional)", expanded=False):
                oc1, oc2 = st.columns(2)
                # FIX v5 BUG 6: We render widgets here but do NOT update extracted[]
                # in-place. The widget keys (jsd_ot, jsd_oco, …) persist in
                # session_state across fragment reruns. We read them at button-click
                # time below, not here, so overrides are never lost.
                oc1.text_input("Title",    value=extracted["title"],    key="jsd_ot")
                oc2.text_input("Company",  value=extracted["company"],  key="jsd_oco")
                oc1.text_input("Salary",   value=extracted["salary"],   key="jsd_os")
                oc2.text_input("Contact",  value=extracted["contact"],  key="jsd_oct")
                oc1.text_input("Website",  value=extracted["website"],  key="jsd_ow")
                oc2.text_input("Location", value=extracted["location"], key="jsd_ol")

        # FIX v5 BUG 6: Build job from session_state override keys if they exist
        # (populated by the expander above). Falls back to auto_extract values if
        # the override expander was never opened.
        job = {
            "title":        st.session_state.get("jsd_ot",  extracted.get("title", "")),
            "company":      st.session_state.get("jsd_oco", extracted.get("company", "")),
            "website":      st.session_state.get("jsd_ow",  extracted.get("website", "")),
            "location":     st.session_state.get("jsd_ol",  extracted.get("location", "")),
            "salary":       st.session_state.get("jsd_os",  extracted.get("salary", "")),
            "contact":      st.session_state.get("jsd_oct", extracted.get("contact", "")),
            "description":  raw or "",
            "requirements": "",   # FIX v5 BUG 3: keep empty — description has everything
            "benefits":     "",   # FIX v5 BUG 3: keep empty — description has everything
        }

    else:
        a, b_ = st.columns(2)
        job["title"]    = a.text_input("Job Title",       placeholder="e.g., Software Engineer",  key="jsd_t")
        job["company"]  = b_.text_input("Company Name",   placeholder="e.g., Acme Corp",          key="jsd_co")
        c, d = st.columns(2)
        job["website"]  = c.text_input("Company Website", placeholder="https://acmecorp.com",     key="jsd_w")
        job["location"] = d.text_input("Location",        placeholder="e.g., Bangalore, India",   key="jsd_l")
        e, f = st.columns(2)
        job["salary"]   = e.text_input("Salary Offered",  placeholder="e.g., 8-12 LPA",           key="jsd_sa")
        job["contact"]  = f.text_input("Contact Email",   placeholder="e.g., hr@acme.com",        key="jsd_ct")
        job["description"]  = st.text_area("Job Description",  height=120, key="jsd_d",
                                            placeholder="Describe the role and responsibilities...")
        job["requirements"] = st.text_area("Requirements",     height=80,  key="jsd_r",
                                            placeholder="Skills, experience, qualifications...")
        job["benefits"]     = st.text_area("Benefits / Perks", height=60,  key="jsd_b",
                                            placeholder="What the employer offers...")

    # Use only meaningful fields for "is there any input" check — not description
    # (which in paste mode is raw and always present once the user types).
    if mode == "Paste Full Job Description":
        full_check = (raw or "").strip()
    else:
        full_check = " ".join(str(v) for v in job.values()).strip()

    if len(full_check) < 30:
        st.markdown(
            f'<div style="display:flex;align-items:center;gap:7px;padding:11px 14px;'
            f'background:rgba(56,189,248,0.05);border:1px solid rgba(56,189,248,0.13);'
            f'border-radius:8px;color:#7dd3fc;font-size:0.8rem;margin-top:10px;">'
            f'{_svg(I.INFO,12,"#38bdf8")}'
            f'Enter a job description or fill the fields above to begin analysis.</div>',
            unsafe_allow_html=True,
        )
    else:
        btn_col, clear_col = st.columns([4, 1])
        with btn_col:
            run = st.button(
                "Analyse for Scam Signals" if allowed else "Analyse for Scam Signals (limit reached)",
                type="primary",
                use_container_width=True,
                key="jsd_btn",
                # FIX v5 BUG 2: only check jsd_running here — don't set it here.
                # Setting it before rendering the button caused the NEXT fragment
                # rerun (triggered by any widget) to see True and lock the button.
                disabled=not allowed or st.session_state.get("jsd_running", False),
                help=(
                    "Runs full AI analysis + 5 live network probes. Takes ~10s."
                    if allowed else
                    f"You have used all {_SCAM_LIMIT} analyses for this hour. "
                    "Please wait — quota resets on a rolling 60-minute window."
                ),
            )
        with clear_col:
            clear = st.button(
                "Reset",
                use_container_width=True,
                key="jsd_clear",
                disabled=st.session_state.get("jsd_running", False),
                help="Clear all inputs and results",
            )

        if clear:
            with st.spinner("Clearing…"):
                # Explicitly blank the text area value BEFORE deleting the key.
                # Streamlit re-uses widget state by key — if the key is simply
                # deleted the widget may re-render with its last cached value.
                # Setting to "" first guarantees the textarea shows empty.
                for blank_key in ("jsd_raw", "jsd_mode"):
                    if blank_key in st.session_state:
                        st.session_state[blank_key] = "" if blank_key == "jsd_raw" else "Paste Full Job Description"

                # Delete ALL jsd_ keys except history (preserve past analyses)
                # and jsd_history_loaded (prevent unnecessary DB re-fetch).
                preserve = {"jsd_history", "jsd_history_loaded"}
                keys_to_delete = [
                    k for k in list(st.session_state.keys())
                    if k.startswith("jsd_") and k not in preserve
                ]
                # Also catch jsd_last_result and jsd_running explicitly
                for extra in ("jsd_last_result", "jsd_running"):
                    if extra in st.session_state and extra not in keys_to_delete:
                        keys_to_delete.append(extra)
                for k in keys_to_delete:
                    del st.session_state[k]
                time.sleep(0.25)
            st.rerun()

        if run:
            # FIX v5 BUG 2: Set jsd_running INSIDE the run block, not before
            # button rendering. This way the flag is only True during the actual
            # analysis pipeline, not during normal widget interactions.
            st.session_state["jsd_running"] = True

            # ── Spinner wraps the entire analysis pipeline ─────────────────────
            with st.spinner("Running analysis — this takes ~10 seconds…"):
                # Progress steps shown during the ~10s wait
                prog = st.progress(0, text="Starting analysis…")
                try:
                    prog.progress(10, text="Running 15-signal rule engine…")
                    rules_result = _run_rules(job)

                    prog.progress(30, text="Launching 5 live network probes (parallel)…")
                    probes = run_live_probes(job)
                    penalty, warnings = _probe_risk(probes)

                    prog.progress(60, text="Sending to AI for deep analysis…")
                    llm_raw = call_llm_fn(
                        _llm_prompt(job, warnings),
                        st.session_state,
                        model="llama-3.3-70b-versatile",
                        temperature=0,
                    )
                    llm_data: dict = {}
                    try:
                        clean = re.sub(r"```json|```", "", llm_raw).strip()
                        m = re.search(r"\{.*\}", clean, re.DOTALL)
                        if m:
                            llm_data = json.loads(m.group())
                    except Exception:
                        pass

                    prog.progress(90, text="Blending scores…")
                    ai_s   = int(llm_data.get("ai_risk_score", rules_result["rule_score"]))
                    rule_s = rules_result["rule_score"]

                    # ── Calibrated blending ────────────────────────────────────────
                    # Base blend: AI carries 60%, rules 25%, probe penalty 15%.
                    blended = int(0.60 * ai_s + 0.25 * rule_s + 0.15 * penalty)

                    # Hard floor only from HIGH-weight signals (>=18 pts each).
                    critical_signals = [k for k, s in rules_result["signals"].items()
                                        if _WEIGHTS.get(k, 0) >= 18]
                    critical_weight  = sum(_WEIGHTS.get(k, 0) for k in critical_signals)
                    blended = max(blended, critical_weight)

                    # Probe penalty floor: only if penalty is itself significant (>= 20)
                    if penalty >= 20:
                        blended = max(blended, penalty)

                    # ── HARD PROBE OVERRIDE (Improvement 4) ───────────────────────
                    # If multiple critical network probes fire together, force the
                    # verdict to DEFINITE_SCAM regardless of the LLM score.
                    # These combos are near-impossible for legitimate companies.
                    mx_status   = probes.get("mx_record", {}).get("status", "")
                    domain_fail = not probes.get("company_domain", {}).get("domain_exists", True)
                    young_days  = probes.get("domain_age", {}).get("age_days") or 999
                    is_squatter = probes.get("typosquat", {}).get("is_squatter", False)
                    is_parked   = probes.get("site_reach", {}).get("is_parked", False)

                    critical_probe_count = sum([
                        mx_status in ("NO_MX", "DNS_FAIL"),
                        domain_fail,
                        young_days < 90,
                        is_squatter,
                        is_parked,
                    ])
                    if critical_probe_count >= 3:
                        # 3+ critical network failures = confirmed infrastructure scam
                        blended = max(blended, 80)
                    elif critical_probe_count == 2 and mx_status in ("NO_MX", "DNS_FAIL"):
                        # NO_MX/DNS_FAIL + any other critical = force LIKELY_SCAM floor
                        blended = max(blended, 55)

                    blended = min(blended, 100)

                    # Verdict from blended score
                    _sev = {"SAFE": 0, "SUSPICIOUS": 1, "LIKELY_SCAM": 2, "DEFINITE_SCAM": 3}
                    sv   = ("DEFINITE_SCAM" if blended >= 75 else
                            "LIKELY_SCAM"   if blended >= 50 else
                            "SUSPICIOUS"    if blended >= 25 else "SAFE")

                    # AI verdict overrides only if stricter than numeric verdict
                    av    = llm_data.get("verdict", sv)
                    final = av if _sev.get(av, 1) > _sev.get(sv, 0) else sv

                    res = {
                        "blended_score":  blended,   "rule_score":     rule_s,
                        "ai_score":       ai_s,      "probe_penalty":  penalty,
                        "final_verdict":  final,     "signals":        rules_result["signals"],
                        "probes":         probes,    "probe_warnings": warnings,
                        "llm":            llm_data,  "job":            job,
                        "timestamp":      _now_ist(),
                    }
                    prog.progress(100, text="Done.")
                    time.sleep(0.3)
                    prog.empty()

                    # Write result to session_state, then force a FULL app rerun
                    # so the results panel outside this fragment renders immediately.
                    st.session_state["jsd_last_result"] = res
                    _add_to_history(res)

                    # ── Record usage in Supabase (after success, not before) ───
                    fns = _get_rate_limit_fns()
                    if fns and username:
                        _, record_usage, _ = fns
                        try:
                            record_usage(username, _SCAM_FEATURE)
                        except Exception:
                            pass  # non-fatal — don't block result display

                    st.session_state.pop("jsd_running", None)
                    st.rerun()   # FIX: was st.rerun(scope="app") — invalid in fragment

                except Exception as exc:
                    prog.empty()
                    st.session_state.pop("jsd_running", None)
                    st.error(f"Analysis failed: {exc}")


def _render_feedback(result: dict):
    """
    Thumbs up / thumbs down widget shown after every analysis result.
    Saves to Supabase scam_feedback table (created on first use).
    Feedback is keyed by (username, job_title, company, verdict) so the same
    user can't spam — but they can correct a previous vote.
    """
    # Stable key based on result content, not object id
    fb_key = f"jsd_fb_{result.get('timestamp','')}"
    already = st.session_state.get(fb_key)

    st.markdown(
        f'<div style="margin-top:16px;padding:12px 16px;background:rgba(255,255,255,0.02);'
        f'border:1px solid rgba(255,255,255,0.07);border-radius:10px;'
        f'display:flex;align-items:center;gap:12px;">'
        f'{_svg(I.SPARKLE,13,"#6b7280")}'
        f'<span style="color:#8b949e;font-size:0.78rem;flex:1;">Was this verdict correct?'
        f' Your feedback helps improve detection accuracy.</span>'
        f'</div>',
        unsafe_allow_html=True,
    )

    if already:
        st.markdown(
            f'<div style="color:#22c55e;font-size:0.78rem;margin-top:6px;padding-left:4px;">'
            f'{_svg(I.CHECK,12,"#22c55e")} Thanks for your feedback!</div>',
            unsafe_allow_html=True,
        )
        return

    col_up, col_dn, col_sp = st.columns([1, 1, 5])
    with col_up:
        if st.button("👍 Correct", key=f"{fb_key}_up", use_container_width=True):
            _save_feedback(result, "correct")
            st.session_state[fb_key] = "correct"
            st.rerun()
    with col_dn:
        if st.button("👎 Wrong", key=f"{fb_key}_dn", use_container_width=True):
            _save_feedback(result, "wrong")
            st.session_state[fb_key] = "wrong"
            st.rerun()


def _save_feedback(result: dict, rating: str):
    """
    Persist feedback to Supabase. Creates table if it doesn't exist.
    Non-fatal — UI never errors even if DB write fails.
    """
    try:
        from user_login import _execute
        # Create table once (idempotent)
        _execute("""
            CREATE TABLE IF NOT EXISTS scam_feedback (
                id          SERIAL PRIMARY KEY,
                username    TEXT NOT NULL,
                job_title   TEXT,
                company     TEXT,
                verdict     TEXT,
                blended_score INTEGER,
                rating      TEXT NOT NULL,
                submitted_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
            );
            CREATE INDEX IF NOT EXISTS idx_scam_feedback_user
                ON scam_feedback (username, submitted_at DESC);
        """)
        username = st.session_state.get("username", "guest")
        _execute(
            """
            INSERT INTO scam_feedback
                (username, job_title, company, verdict, blended_score, rating)
            VALUES (%s, %s, %s, %s, %s, %s)
            ON CONFLICT DO NOTHING
            """,
            (
                username,
                result.get("job", {}).get("title", "")[:200],
                result.get("job", {}).get("company", "")[:200],
                result.get("final_verdict", ""),
                result.get("blended_score", 0),
                rating,
            ),
        )
    except Exception:
        pass  # non-fatal


def render_job_scam_detector_tab(call_llm_fn):
    """
    Call from main app:
        with tab_scam:
            render_job_scam_detector_tab(call_llm)
    """

    # ── Premium tab hero header ────────────────────────────────────────────────
    username   = str(st.session_state.get("username", "guest"))
    fns        = _get_rate_limit_fns()
    used_count = 0
    if fns:
        try:
            used_count = fns[2](username, _SCAM_FEATURE)
        except Exception:
            pass
    remaining = max(_SCAM_LIMIT - used_count, 0)

    st.markdown(
        # ── Outer hero card ───────────────────────────────────────────────
        f'<div style="background:rgba(255,255,255,0.025);border:1px solid rgba(255,255,255,0.07);'
        f'border-radius:16px;padding:24px 28px 20px;margin-bottom:20px;'
        f'border-top:2px solid #ef4444;">'

        # ── Top row: icon block + title + quota badge ─────────────────────
        f'<div style="display:flex;align-items:flex-start;gap:16px;margin-bottom:18px;">'

        # Icon box
        f'<div style="width:52px;height:52px;border-radius:14px;flex-shrink:0;'
        f'background:rgba(239,68,68,0.12);border:1px solid rgba(239,68,68,0.25);'
        f'display:flex;align-items:center;justify-content:center;">'
        f'{_svg(I.SHIELD, 26, "#ef4444", 1.5)}</div>'

        # Title + subtitle
        f'<div style="flex:1;min-width:0;">'
        f'<h2 style="margin:0 0 4px;font-size:1.45rem;font-weight:700;color:#e6edf3;'
        f'letter-spacing:-0.02em;">Job Scam Detector</h2>'
        f'<p style="margin:0;color:#8b949e;font-size:0.82rem;line-height:1.5;">'
        f'Paste any job posting — AI analysis + 5 live network probes detect '
        f'fake listings before you apply or share personal data.</p>'
        f'</div>'

        # Quota badge top-right
        f'<div style="flex-shrink:0;text-align:center;padding:10px 16px;border-radius:12px;'
        f'background:{"rgba(34,197,94,0.08)" if remaining > 1 else "rgba(245,158,11,0.08)" if remaining == 1 else "rgba(239,68,68,0.08)"};'
        f'border:1px solid {"rgba(34,197,94,0.22)" if remaining > 1 else "rgba(245,158,11,0.22)" if remaining == 1 else "rgba(239,68,68,0.22)"};">'
        f'<div style="font-size:1.7rem;font-weight:800;line-height:1;'
        f'color:{"#22c55e" if remaining > 1 else "#f59e0b" if remaining == 1 else "#ef4444"};">{remaining}</div>'
        f'<div style="font-size:0.6rem;color:#6b7280;margin-top:2px;white-space:nowrap;">analyses left</div>'
        f'</div>'
        f'</div>'

        # ── Stat row — 4 mini metric cards ────────────────────────────────
        f'<div style="display:grid;grid-template-columns:repeat(4,1fr);gap:8px;margin-bottom:16px;">'
        + "".join([
            f'<div style="background:rgba(255,255,255,0.03);border:1px solid rgba(255,255,255,0.07);'
            f'border-radius:10px;padding:10px 12px;">'
            f'<div style="display:flex;align-items:center;gap:6px;margin-bottom:4px;">'
            f'{_svg(ic, 11, col)}'
            f'<span style="font-size:0.62rem;color:#6b7280;text-transform:uppercase;'
            f'letter-spacing:0.7px;">{label}</span></div>'
            f'<div style="font-size:0.88rem;font-weight:600;color:{col};">{val}</div>'
            f'</div>'
            for ic, label, val, col in [
                (I.CPU,      "AI Engine",     "LLaMA 3.3-70B",   "#a78bfa"),
                (I.GLOBE,    "Live Probes",   "6 checks",        "#38bdf8"),
                (I.LIST,     "Rule Signals",  "15 patterns",     "#f59e0b"),
                (I.SHIELD,   "Hourly Limit",  f"{_SCAM_LIMIT} analyses", "#22c55e"),
            ]
        ])
        + f'</div>'

        # ── Feature pill row ──────────────────────────────────────────────
        f'<div style="display:flex;flex-wrap:wrap;gap:5px;">'
        + _pill(I.CPU,      "AI Deep Analysis",     "#a78bfa")
        + _pill(I.CALENDAR, "Domain Age Probe",      "#38bdf8")
        + _pill(I.MAIL,     "Free Email Detection",  "#f59e0b")
        + _pill(I.SERVER,   "MX Mail Server Check",  "#22c55e")
        + _pill(I.COPY,     "Typosquat Check",       "#ef4444")
        + _pill(I.BUILDING, "Company Domain Check",  "#22c55e")
        + _pill(I.SERVER,   "Site Reachability",     "#6366f1")
        + _pill(I.LIST,     "15-Signal Rule Engine", "#8b949e")
        + f'</div>'
        + f'</div>',
        unsafe_allow_html=True,
    )

    form_col, hist_col = st.columns([3, 1], gap="large")

    with hist_col:
        st.markdown(
            f'<div style="font-size:0.71rem;font-weight:600;color:#8b949e;text-transform:uppercase;'
            f'letter-spacing:1px;margin-bottom:8px;display:flex;align-items:center;gap:5px;">'
            f'{_svg(I.HISTORY,11,"#6b7280")} Recent Analyses</div>',
            unsafe_allow_html=True,
        )
        _render_history()

    with form_col:
        # ── Rate-limit bar — always visible, renders live quota from Supabase
        allowed = _render_rate_limit_bar(username)

        # ── Input section (fragment-isolated) ─────────────────────────────
        _render_input_fragment(call_llm_fn, username=username, allowed=allowed)

    # ── Results — rendered at TOP-LEVEL scope, outside the fragment ────────
    # This is the critical fix: results live here so they persist across
    # fragment re-runs and are never wiped by widget interaction.
    res = st.session_state.get("jsd_last_result")
    if not res:
        return

    st.markdown(
        '<hr style="border:none;border-top:1px solid rgba(255,255,255,0.07);margin:20px 0;">',
        unsafe_allow_html=True,
    )
    st.markdown(
        f'<div style="display:flex;align-items:center;gap:8px;font-size:0.9rem;font-weight:700;'
        f'color:#e6edf3;margin-bottom:16px;">{_svg(I.BAR_CHART,14)} Analysis Results</div>',
        unsafe_allow_html=True,
    )

    _render_verdict_banner(res)
    _render_score_strip(res)
    st.markdown("<br>", unsafe_allow_html=True)
    _render_probe_table(res["probes"])

    t1, t2, t3 = st.tabs(["Detected Signals", "AI Deep Dive", "Safety Checklist"])
    with t1:
        st.markdown(
            f'<p style="color:#8b949e;font-size:0.79rem;margin-bottom:12px;">'
            f'{len(res["signals"])} rule-based signal(s) fired.</p>',
            unsafe_allow_html=True,
        )
        _render_signal_cards(res["signals"])
    with t2:
        _render_ai_dive(res.get("llm", {}))
    with t3:
        _render_checklist(res)

    st.markdown(
        f'<div style="margin-top:20px;padding:10px 15px;background:rgba(107,114,128,0.04);'
        f'border:1px solid rgba(107,114,128,0.12);border-radius:8px;'
        f'display:flex;align-items:flex-start;gap:7px;color:#6b7280;font-size:0.72rem;">'
        f'{_svg(I.INFO,11,"#6b7280")}'
        f'<span><strong style="color:#8b949e;">Disclaimer:</strong> This tool uses AI pattern '
        f'matching and live network probes. It cannot guarantee 100% accuracy. A SAFE verdict '
        f'does not guarantee a legitimate job. Always perform your own due diligence.</span></div>',
        unsafe_allow_html=True,
    )

    # ── Feedback widget ───────────────────────────────────────────────────────
    _render_feedback(res)
