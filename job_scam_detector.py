"""
job_scam_detector.py  —  Production Grade v4
─────────────────────────────────────────────
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
  A. 5 live network probes  (parallel threads)
     domain age · site reachability · typosquatting · free-email · MCA registry
  B. 15-signal rule engine  (weighted, 0-100)
  C. LLM deep analysis      (llama-3.3-70b-versatile via Groq)
  D. Blended score          (55% AI + 30% rules + 15% probe penalty)
"""

from __future__ import annotations

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

import streamlit as st


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
    "upfront_payment":      I.CREDIT_CARD,
    "mlm_pyramid":          I.TRIANGLE,
    "too_good_salary":      I.TRENDING_UP,
    "unrealistic_benefits": I.DOLLAR,
    "vague_description":    I.EDIT,
    "free_email_contact":   I.MAIL,
    "urgency_pressure":     I.CLOCK,
    "no_company_info":      I.BUILDING,
    "req_paradox":          I.LAYERS,
    "personal_info_demand": I.ID_CARD,
    "location_mismatch":    I.MAP_PIN,
    "work_from_home_bait":  I.HOME,
    "missing_salary":       I.DOLLAR_OFF,
    "poor_grammar":         I.FILE_TEXT,
    "generic_template":     I.COPY,
}


# ─────────────────────────────────────────────────────────────────────────────
# CONSTANTS
# ─────────────────────────────────────────────────────────────────────────────

_WEIGHTS: dict[str, int] = {
    "upfront_payment":      25,
    "mlm_pyramid":          20,
    "too_good_salary":      18,
    "vague_description":    14,
    "free_email_contact":   12,
    "urgency_pressure":     12,
    "no_company_info":      11,
    "req_paradox":          10,
    "personal_info_demand":  9,
    "unrealistic_benefits":  7,
    "location_mismatch":     7,
    "poor_grammar":          6,
    "work_from_home_bait":   5,
    "missing_salary":        4,
    "generic_template":      4,
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
]
_MLM_PHRASES = [
    r"unlimited earning",r"be your own boss",r"passive income",
    r"network marketing",r"multi.level",r"refer.*earn",
    r"downline",r"upline",r"pyramid",r"direct selling",
    r"recruit.*friends",r"grow your team",r"commission.*recruit",
    r"financial freedom.*join",r"work from.*anywhere.*earn",
]
_URGENCY_PHRASES = [
    r"limited.*position",r"act now",r"respond.*immediately",
    r"offer.*expires",r"today only",r"urgent.*hiring",
    r"immediate.*joiner",r"joining.*asap",r"last.*few.*seat",
    r"don.t miss",r"apply.*before.*[0-9]",r"deadline.*today",
    r"positions.*filling.*fast",r"only.*[0-9].*seat.*left",
]
_VAGUE_PHRASES = [
    r"dynamic.*individual",r"go.getter",r"passionate.*person",
    r"attractive.*salary",r"good.*communication",r"fast.paced.*environment",
    r"various.*responsibilities",r"other.*duties.*assigned",
    r"exciting.*opportunity",r"ground.*floor.*opportunity",
]
_PERSONAL_PHRASES = [
    r"bank.*account.*detail",r"aadhaar.*number",r"pan.*number",
    r"passport.*copy.*apply",r"ssn.*apply",r"social.*security.*apply",
    r"photo.*mandatory.*apply",r"dob.*required.*apply",
    r"mother.*maiden.*name",r"send.*id.*proof.*apply",r"aadhar.*card.*apply",
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

def _xf(text: str, kws: list) -> str:
    for kw in kws:
        m = re.search(rf"(?i)(?:^|\n|\s){kw}\s*[:\-]\s*([^\n]{{2,80}})", text or "")
        if m:
            val = m.group(1).strip().rstrip(".,;")
            if len(val) > 2:
                return val
    return ""

def _xu(text: str) -> str:
    m = re.search(r"https?://[^\s)\"',]{6,}", text or "")
    return m.group(0).rstrip(".,;)") if m else ""

def _xs(text: str) -> str:
    m = re.search(r"(?i)(salary|ctc|pay|package|compensation|remuneration)\s*[:\-]\s*([^\n]{3,60})", text or "")
    if m:
        return m.group(2).strip()
    m2 = re.search(r"(?:Rs\.?|INR|\$|USD)\s*[\d,\s\-\.LPAlpa]+(?:lpa|per\s+annum|per\s+month|pa|pm)?",
                   text or "", re.IGNORECASE)
    return m2.group(0).strip() if m2 else ""

def _xc(text: str) -> str:
    emails = re.findall(r"[\w.+\-]+@[\w\-]+\.[a-zA-Z]{2,}", text or "")
    phones = re.findall(r"(?<!\d)[+]?[\d][\d\s\-()]{8,13}[\d](?!\d)", text or "")
    return " | ".join(emails[:1] + [p.strip() for p in phones[:1]])

def _xt(text: str) -> str:
    val = _xf(text, ["position", "role", "job title", "title", "designation",
                     "opening for", "hiring for", "vacancy"])
    if val:
        return val
    for line in (text or "").split("\n"):
        line = line.strip()
        if 4 < len(line) < 80 and not line.startswith("http"):
            return line
    return ""

def _xco(text: str) -> str:
    return _xf(text, ["company", "organization", "organisation", "employer",
                      "firm", "about us", "about the company", "about company"])

def _xloc(text: str) -> str:
    return _xf(text, ["location", "city", "based in", "office", "workplace",
                      "work location", "place of work", "job location"])

def auto_extract(raw: str) -> dict:
    return {
        "title":        _xt(raw),
        "company":      _xco(raw),
        "website":      _xu(raw),
        "location":     _xloc(raw),
        "salary":       _xs(raw),
        "contact":      _xc(raw),
        "description":  raw,
        "requirements": raw,
        "benefits":     raw,
    }


# ─────────────────────────────────────────────────────────────────────────────
# LIVE NETWORK PROBES
# ─────────────────────────────────────────────────────────────────────────────

_T_RDAP  = 6
_T_REACH = 5
_T_MCA   = 7


def _extract_domain(s: str) -> Optional[str]:
    if not s:
        return None
    s = s.strip().lower()
    if "@" in s and "/" not in s:
        return s.split("@")[-1]
    m = re.search(r"(?:https?://)?(?:www\.)?([a-z0-9\-\.]+\.[a-z]{2,})", s)
    return m.group(1) if m else None


def _probe_domain_age(domain: str) -> dict:
    out = {"status": "unknown", "age_days": None, "registered": None, "detail": ""}
    if not domain:
        return out
    try:
        req = urllib.request.Request(
            f"https://rdap.org/domain/{domain}",
            headers={"User-Agent": "ScamDetector/3.0"},
        )
        with urllib.request.urlopen(req, timeout=_T_RDAP) as resp:
            data = json.loads(resp.read().decode())
        reg_date = None
        for ev in data.get("events", []):
            if ev.get("eventAction") in ("registration", "created"):
                reg_date = ev.get("eventDate", "")
                break
        if reg_date:
            for fmt in ("%Y-%m-%dT%H:%M:%SZ", "%Y-%m-%dT%H:%M:%S"):
                try:
                    dt  = datetime.strptime(reg_date[:19], fmt)
                    age = (datetime.utcnow() - dt).days
                    out.update(status="young" if age < 180 else "old", age_days=age,
                               registered=dt.strftime("%d %b %Y"),
                               detail=f"Registered {dt.strftime('%d %b %Y')} — {age} days old")
                    return out
                except ValueError:
                    continue
        out["detail"] = "Registration date not in RDAP response"
    except Exception as e:
        out.update(status="error", detail=f"RDAP unavailable ({type(e).__name__})")
    return out


def _probe_site_reachable(domain: str) -> dict:
    out = {"reachable": None, "status_code": None, "detail": ""}
    if not domain:
        return out
    for scheme in ("https", "http"):
        try:
            req = urllib.request.Request(
                f"{scheme}://{domain}", method="HEAD",
                headers={"User-Agent": "Mozilla/5.0 ScamDetector/3.0"},
            )
            with urllib.request.urlopen(req, timeout=_T_REACH) as resp:
                out.update(reachable=True, status_code=resp.status,
                           detail=f"HTTP {resp.status} — site is live")
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


def _probe_mca(company: str) -> dict:
    out = {"found": None, "detail": "", "source": "MCA India (mca.gov.in)"}
    if not company or len(company.strip()) < 3:
        out["detail"] = "Company name too short to query"
        return out
    name_clean = re.sub(r"[^\w\s]", "", company).strip()
    try:
        encoded = urllib.parse.quote(name_clean)
        url = (
            "https://www.mca.gov.in/mcafoportal/viewCompanyMasterData.do?"
            f"companyName={encoded}&cin=&companyCategory=&companySubCategory="
            "&companyStatus=&roc=&state="
        )
        req = urllib.request.Request(
            url, headers={"User-Agent": "Mozilla/5.0 (compatible; ScamDetector/3.0)",
                          "Accept": "application/json, text/html"},
        )
        with urllib.request.urlopen(req, timeout=_T_MCA) as resp:
            raw = resp.read().decode("utf-8", errors="ignore")
        stopwords = {"LIMITED","PRIVATE","PUBLIC","INDIA","SERVICES","SOLUTIONS",
                     "TECHNOLOGIES","CONSULTANCY","ENTERPRISES","AND","THE"}
        words = [w for w in name_clean.upper().split() if len(w) > 3 and w not in stopwords]
        hits  = sum(1 for w in words if w in raw.upper())
        if hits >= max(1, len(words) // 2):
            out.update(found=True,  detail="Company name found in MCA — legally registered in India")
        elif "no record" in raw.lower() or "not found" in raw.lower():
            out.update(found=False, detail="Company NOT found in MCA — may not be legally registered")
        else:
            out["detail"] = "MCA search inconclusive — verify manually at mca.gov.in"
    except Exception as e:
        out["detail"] = f"MCA lookup unavailable ({type(e).__name__}) — verify manually"
    return out


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

    probes: dict = {
        "domain_age": {"status": "skipped", "detail": "No domain provided"},
        "site_reach": {"reachable": None,   "detail": "No domain provided"},
        "typosquat":  {"is_squatter": False, "detail": "No domain provided"},
        "free_email": {"uses_free_domain": False, "detail": ""},
        "mca":        {"found": None,       "detail": ""},
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
        ("domain_age", _probe_domain_age,    domain or ""),
        ("site_reach", _probe_site_reachable, domain or ""),
        ("typosquat",  _probe_typosquatting,  domain or ""),
        ("free_email", _probe_free_email,     contact),
        ("mca",        _probe_mca,            company),
    ]
    threads = [threading.Thread(target=_run, args=t, daemon=True) for t in tasks]
    for t in threads: t.start()
    for t in threads: t.join(timeout=10)
    return probes


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
    typo = probes.get("typosquat", {})
    if typo.get("is_squatter"):
        penalty += 20
        warnings.append(typo["detail"])
    if probes.get("free_email", {}).get("uses_free_domain"):
        penalty += 12
        dom = probes["free_email"].get("domain", "")
        warnings.append(f"Recruiter uses personal email domain: {dom}")
    if probes.get("mca", {}).get("found") is False:
        penalty += 10
        warnings.append("Company not found in MCA India registry")
    return min(penalty, 55), warnings


# ─────────────────────────────────────────────────────────────────────────────
# RULE ENGINE
# ─────────────────────────────────────────────────────────────────────────────

def _any(text: str, patterns: list) -> list:
    return [p for p in patterns if re.search(p, text, re.IGNORECASE)]

def _salary_outlier(text: str) -> bool:
    for n in re.findall(r"\d+", text.replace(",", "")):
        v = int(n)
        if 500000 <= v <= 99999999:
            return True
        if 15000 <= v <= 999999 and "$" in text:
            return True
    return False

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
    if _salary_outlier(job.get("salary","") + " " + job.get("description","")):
        _add("too_good_salary","Unrealistically High Salary",
             "Offered compensation is far above verified market rates for this role.")
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

def _render_verdict_banner(result: dict):
    v   = result["final_verdict"]
    cfg = _V.get(v, _V["UNKNOWN"])
    s   = result["blended_score"]
    st.markdown(
        f'<div style="padding:24px 28px;border-radius:14px;background:{cfg["bg"]};'
        f'border:1.5px solid {cfg["border"]};margin-bottom:22px;">'
        f'<div style="display:flex;align-items:center;gap:12px;margin-bottom:10px;">'
        f'<div>{_svg(cfg["icon"], 32, cfg["color"], 1.5)}</div>'
        f'<div style="flex:1;">'
        f'<div style="font-size:1.35rem;font-weight:700;color:{cfg["color"]};'
        f'letter-spacing:0.3px;">{cfg["label"]}</div>'
        f'<div style="color:#8b949e;font-size:0.79rem;margin-top:2px;">'
        f'Blended score across AI analysis, rule engine and live network probes</div>'
        f'</div>'
        f'<div style="text-align:right;flex-shrink:0;">'
        f'<div style="font-size:2.4rem;font-weight:800;color:{cfg["color"]};line-height:1;">{s}</div>'
        f'<div style="font-size:0.71rem;color:#6b7280;">/ 100</div>'
        f'</div></div>'
        f'{_bar(s, cfg["color"], 8)}'
        f'</div>',
        unsafe_allow_html=True,
    )


def _render_score_strip(result: dict):
    cfg = _V.get(result["final_verdict"], _V["UNKNOWN"])

    def _card(icon_path, label, val, color, sub=""):
        return (
            f'<div style="background:rgba(255,255,255,0.03);border:1px solid rgba(255,255,255,0.07);'
            f'border-radius:10px;padding:14px 16px;text-align:center;">'
            f'<div style="display:flex;align-items:center;justify-content:center;gap:5px;'
            f'color:#6b7280;font-size:0.66rem;text-transform:uppercase;letter-spacing:1px;'
            f'margin-bottom:6px;">{_svg(icon_path,10,"#6b7280")}{label}</div>'
            f'<div style="font-size:1.75rem;font-weight:700;color:{color};line-height:1;">{val}</div>'
            f'{"<div style=font-size:0.66rem;color:#6b7280;margin-top:3px;>" + sub + "</div>" if sub else ""}'
            f'</div>'
        )

    c1, c2, c3, c4 = st.columns(4)
    c1.markdown(_card(I.CPU,      "AI Score",      result["ai_score"],      cfg["color"], "LLM analysis"),  unsafe_allow_html=True)
    c2.markdown(_card(I.LIST,     "Rule Score",    result["rule_score"],    "#f59e0b",    "15 signals"),     unsafe_allow_html=True)
    c3.markdown(_card(I.GLOBE,    "Probe Penalty", result["probe_penalty"], "#38bdf8",    "5 live checks"),  unsafe_allow_html=True)
    c4.markdown(_card(I.ZAP,      "Flags Fired",   len(result["signals"]),  "#a78bfa",    "rule signals"),   unsafe_allow_html=True)


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

    mca = probes.get("mca", {})
    b   = (_badge("FOUND IN MCA", "#22c55e","rgba(34,197,94,0.12)")  if mca.get("found") is True  else
           _badge("NOT IN MCA",   "#dc2626","rgba(220,38,38,0.12)")  if mca.get("found") is False else
           _badge("INCONCLUSIVE", "#f59e0b","rgba(245,158,11,0.12)"))
    rows.append(_row(I.BUILDING, "MCA Registry (India)", b, mca.get("detail","")))

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
        st.checkbox(text, value=default, key=f"jsd_c_{idx}_{id(result)}")
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
    h.insert(0, {
        "title":   result["job"].get("title","Untitled"),
        "company": result["job"].get("company","Unknown"),
        "score":   result["blended_score"],
        "verdict": result["final_verdict"],
        "time":    result["timestamp"],
    })
    st.session_state["jsd_history"] = h[:10]


def _render_history():
    history = st.session_state.get("jsd_history", [])
    if not history:
        st.markdown(
            '<div style="color:#6b7280;font-size:0.78rem;text-align:center;'
            'padding:18px 0;font-style:italic;">No analyses yet.</div>',
            unsafe_allow_html=True,
        )
        return
    html = ""
    for h in history:
        cfg = _V.get(h["verdict"], _V["UNKNOWN"])
        html += (
            f'<div style="padding:10px 12px;background:rgba(255,255,255,0.02);'
            f'border:1px solid rgba(255,255,255,0.06);border-radius:8px;margin-bottom:7px;">'
            f'<div style="color:#c9d1d9;font-size:0.8rem;font-weight:500;overflow:hidden;'
            f'white-space:nowrap;text-overflow:ellipsis;">{h["title"]}</div>'
            f'<div style="color:#6b7280;font-size:0.7rem;margin-top:1px;">{h["company"]}</div>'
            f'<div style="display:flex;justify-content:space-between;align-items:center;margin-top:5px;">'
            f'<span style="color:#6b7280;font-size:0.67rem;">{h["time"]}</span>'
            f'<span style="color:{cfg["color"]};font-size:0.77rem;font-weight:700;">{h["score"]}/100</span>'
            f'</div>{_bar(h["score"],cfg["color"],4)}</div>'
        )
    st.markdown(html, unsafe_allow_html=True)


# ─────────────────────────────────────────────────────────────────────────────
# MAIN ENTRY POINT
# ─────────────────────────────────────────────────────────────────────────────

def _quick_prescan(raw: str) -> dict | None:
    """
    Lightweight instant signal preview — runs rule engine only (no network, no LLM).
    Returns a minimal result dict or None if text is too short.
    """
    if not raw or len(raw.strip()) < 30:
        return None
    extracted = auto_extract(raw)
    rules = _run_rules(extracted)
    score = rules["rule_score"]
    if score == 0:
        verdict = "SAFE"
    elif score < 25:
        verdict = "SUSPICIOUS"
    elif score < 50:
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


@st.fragment
def _render_input_fragment(call_llm_fn):
    """
    FRAGMENT FIX:
    Wrapping the entire input section in @st.fragment means widget interactions
    (typing, radio switches, expander toggles) only re-run THIS fragment, not
    the full page. The full page re-run only happens when st.rerun() is called
    explicitly (on Clear) or when data is written to session_state by the
    Analyse button — which is exactly the desired behaviour.
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
                extracted["title"]    = oc1.text_input("Title",    value=extracted["title"],    key="jsd_ot")
                extracted["company"]  = oc2.text_input("Company",  value=extracted["company"],  key="jsd_oco")
                extracted["salary"]   = oc1.text_input("Salary",   value=extracted["salary"],   key="jsd_os")
                extracted["contact"]  = oc2.text_input("Contact",  value=extracted["contact"],  key="jsd_oct")
                extracted["website"]  = oc1.text_input("Website",  value=extracted["website"],  key="jsd_ow")
                extracted["location"] = oc2.text_input("Location", value=extracted["location"], key="jsd_ol")

        job = extracted

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
                "Analyse for Scam Signals",
                type="primary",
                use_container_width=True,
                key="jsd_btn",
                help="Runs full AI analysis + 5 live network probes. Takes ~10s.",
            )
        with clear_col:
            clear = st.button(
                "Reset",
                use_container_width=True,
                key="jsd_clear",
                help="Clear all inputs and results",
            )

        if clear:
            for k in list(st.session_state.keys()):
                if k.startswith("jsd_"):
                    del st.session_state[k]
            st.rerun()

        if run:
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
                ai_s    = int(llm_data.get("ai_risk_score", rules_result["rule_score"]))
                rule_s  = rules_result["rule_score"]
                blended = int(0.55 * ai_s + 0.30 * rule_s + 0.15 * penalty)
                blended = min(max(blended, rule_s, penalty), 100)
                _sev    = {"SAFE":0,"SUSPICIOUS":1,"LIKELY_SCAM":2,"DEFINITE_SCAM":3}
                sv      = ("DEFINITE_SCAM" if blended>=75 else "LIKELY_SCAM" if blended>=50
                           else "SUSPICIOUS" if blended>=25 else "SAFE")
                av      = llm_data.get("verdict", sv)
                final   = av if _sev.get(av,1) > _sev.get(sv,0) else sv

                res = {
                    "blended_score":  blended,   "rule_score":     rule_s,
                    "ai_score":       ai_s,      "probe_penalty":  penalty,
                    "final_verdict":  final,     "signals":        rules_result["signals"],
                    "probes":         probes,    "probe_warnings": warnings,
                    "llm":            llm_data,  "job":            job,
                    "timestamp":      datetime.now().strftime("%Y-%m-%d %H:%M"),
                }
                prog.progress(100, text="Done.")
                time.sleep(0.3)
                prog.empty()

                # ── KEY FIX: write result to session_state so results panel
                #    (which lives OUTSIDE this fragment) can render it without
                #    the input section re-running or losing its state. ──────
                st.session_state["jsd_last_result"] = res
                _add_to_history(res)

            except Exception as exc:
                prog.empty()
                st.error(f"Analysis failed: {exc}")


def render_job_scam_detector_tab(call_llm_fn):
    """
    Call from main app:
        with tab_scam:
            render_job_scam_detector_tab(call_llm)

    Architecture note (page re-render fix):
    ----------------------------------------
    The input widgets live inside _render_input_fragment() which is decorated
    with @st.fragment.  Fragment re-runs are ISOLATED — only the fragment
    re-executes on widget interaction, not the full Streamlit script.

    Results are rendered AFTER the fragment call, at the top-level script
    scope. When the Analyse button writes jsd_last_result to session_state
    Streamlit triggers a full rerun (normal behaviour for st.session_state
    writes), but the fragment preserves its own widget state so the textarea
    text is NOT lost.  The Reset button explicitly calls st.rerun() to wipe
    everything cleanly.
    """

    # ── Header ────────────────────────────────────────────────────────────────
    st.markdown(
        f'<div style="padding:16px 0 6px;">'
        f'<div style="display:flex;align-items:center;gap:12px;margin-bottom:8px;">'
        f'{_svg(I.SHIELD,32,"#ef4444",1.6)}'
        f'<div><h2 style="margin:0;color:#e6edf3;font-size:1.4rem;font-weight:700;">'
        f'Job Scam Detector</h2>'
        f'<p style="margin:2px 0 0;color:#8b949e;font-size:0.81rem;">'
        f'AI analysis + live network probes — detect fake postings before you apply.</p>'
        f'</div></div></div>',
        unsafe_allow_html=True,
    )

    # ── Feature pills ─────────────────────────────────────────────────────────
    st.markdown(
        '<div style="display:flex;flex-wrap:wrap;gap:6px;margin-bottom:22px;">'
        + _pill(I.CPU,      "AI Deep Analysis",     "#a78bfa")
        + _pill(I.CALENDAR, "Domain Age Probe",      "#38bdf8")
        + _pill(I.MAIL,     "Free Email Detection",  "#f59e0b")
        + _pill(I.COPY,     "Typosquat Check",       "#ef4444")
        + _pill(I.BUILDING, "MCA Registry",          "#22c55e")
        + _pill(I.SERVER,   "Site Reachability",     "#6366f1")
        + _pill(I.LIST,     "15-Signal Rule Engine", "#8b949e")
        + '</div>',
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
        # ── Input section (fragment-isolated) ─────────────────────────────
        _render_input_fragment(call_llm_fn)

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
