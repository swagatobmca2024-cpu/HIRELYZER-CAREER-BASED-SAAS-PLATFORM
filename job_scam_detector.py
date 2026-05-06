"""
job_scam_detector.py  —  Production Grade v2
─────────────────────────────────────────────
Advanced Job Scam & Fake Company Detector tab.

Detection Layers:
  A. LIVE NETWORK CHECKS (real HTTP calls, parallel threads)
     1. Domain Age          — RDAP / rdap.org JSON API
     2. Site Reachability   — HEAD request with timeout
     3. Typosquatting       — SequenceMatcher vs known brand list
     4. Free-Email Domain   — curated blocklist
     5. MCA Registry Check  — mca.gov.in public search

  B. RULE ENGINE  (15 weighted signals, zero network needed)
     upfront_payment, mlm_pyramid, too_good_salary, vague_description,
     free_email_contact, urgency_pressure, no_company_info, req_paradox,
     personal_info_demand, location_mismatch, poor_grammar,
     unrealistic_benefits, missing_salary, work_from_home_bait,
     generic_template

  C. LLM DEEP ANALYSIS  (Groq llama-3.3-70b-versatile)
     AI risk score 0-100, fake-company evidence, linguistic analysis,
     salary reality check, scam pattern classification, confidence score

  D. BLENDED SCORING
     55% AI + 30% rule_score + 15% probe_penalty
     rules + probes act as hard floor; final capped at 100

  E. UI — production grade
     Zero emojis. Pure SVG icon system throughout.
     Verdict banner, 4-metric breakdown, live-probe status table,
     per-signal cards with weight bars, AI deep-dive, checklist,
     session history sidebar.
"""

from __future__ import annotations

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
# SVG ICON LIBRARY
# ─────────────────────────────────────────────────────────────────────────────

def _i(paths: str, size: int = 14, stroke: str = "currentColor", sw: int = 2) -> str:
    """Render inline SVG."""
    return (
        f'<svg width="{size}" height="{size}" viewBox="0 0 24 24" '
        f'fill="none" stroke="{stroke}" stroke-width="{sw}" '
        f'stroke-linecap="round" stroke-linejoin="round" '
        f'style="vertical-align:-2px;flex-shrink:0;">{paths}</svg>'
    )


class SVG:
    SHIELD       = '<path d="M12 22s8-4 8-10V5l-8-3-8 3v7c0 6 8 10 8 10z"/>'
    CHECK_CIRCLE = '<path d="M22 11.08V12a10 10 0 1 1-5.93-9.14"/><polyline points="22 4 12 14.01 9 11.01"/>'
    X_CIRCLE     = '<circle cx="12" cy="12" r="10"/><line x1="15" y1="9" x2="9" y2="15"/><line x1="9" y1="9" x2="15" y2="15"/>'
    ALERT_TRI    = '<path d="M10.29 3.86L1.82 18a2 2 0 0 0 1.71 3h16.94a2 2 0 0 0 1.71-3L13.71 3.86a2 2 0 0 0-3.42 0z"/><line x1="12" y1="9" x2="12" y2="13"/><line x1="12" y1="17" x2="12.01" y2="17"/>'
    ALERT_CIRCLE = '<circle cx="12" cy="12" r="10"/><line x1="12" y1="8" x2="12" y2="12"/><line x1="12" y1="16" x2="12.01" y2="16"/>'
    INFO         = '<circle cx="12" cy="12" r="10"/><line x1="12" y1="16" x2="12" y2="12"/><line x1="12" y1="8" x2="12.01" y2="8"/>'
    SKULL        = '<circle cx="12" cy="11" r="5"/><path d="M9 17v1a3 3 0 0 0 6 0v-1"/><path d="M12 6V4"/>'
    EYE          = '<path d="M1 12s4-8 11-8 11 8 11 8-4 8-11 8-11-8-11-8z"/><circle cx="12" cy="12" r="3"/>'
    GLOBE        = '<circle cx="12" cy="12" r="10"/><line x1="2" y1="12" x2="22" y2="12"/><path d="M12 2a15.3 15.3 0 0 1 4 10 15.3 15.3 0 0 1-4 10 15.3 15.3 0 0 1-4-10 15.3 15.3 0 0 1 4-10z"/>'
    WIFI_OFF     = '<line x1="1" y1="1" x2="23" y2="23"/><path d="M16.72 11.06A10.94 10.94 0 0 1 19 12.55"/><path d="M5 12.55a10.94 10.94 0 0 1 5.17-2.39"/><line x1="12" y1="20" x2="12.01" y2="20"/>'
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
    MAIL_WARN    = '<path d="M4 4h16c1.1 0 2 .9 2 2v12c0 1.1-.9 2-2 2H4c-1.1 0-2-.9-2-2V6c0-1.1.9-2 2-2z"/><polyline points="22,6 12,13 2,6"/><line x1="12" y1="10" x2="12" y2="14"/>'
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
    CLIPBOARD    = '<path d="M16 4h2a2 2 0 0 1 2 2v14a2 2 0 0 1-2 2H6a2 2 0 0 1-2-2V6a2 2 0 0 1 2-2h2"/><rect x="8" y="2" width="8" height="4" rx="1" ry="1"/>'
    LAYERS       = '<polygon points="12 2 2 7 12 12 22 7 12 2"/><polyline points="2 17 12 22 22 17"/><polyline points="2 12 12 17 22 12"/>'
    AWARD        = '<circle cx="12" cy="8" r="6"/><path d="M15.477 12.89L17 22l-5-3-5 3 1.523-9.11"/>'
    PHONE        = '<path d="M22 16.92v3a2 2 0 0 1-2.18 2 19.79 19.79 0 0 1-8.63-3.07A19.5 19.5 0 0 1 4.69 13 19.79 19.79 0 0 1 1.61 4.36 2 2 0 0 1 3.6 2h3a2 2 0 0 1 2 1.72c.127.96.361 1.903.7 2.81a2 2 0 0 1-.45 2.11L7.91 9.91a16 16 0 0 0 6.1 6.1l1.27-.63a2 2 0 0 1 2.11.45c.907.339 1.85.573 2.81.7A2 2 0 0 1 22 16.92z"/>'


# Signal → icon path
_SIG_ICON: dict[str, str] = {
    "upfront_payment":      SVG.CREDIT_CARD,
    "mlm_pyramid":          SVG.TRIANGLE,
    "too_good_salary":      SVG.TRENDING_UP,
    "unrealistic_benefits": SVG.DOLLAR,
    "vague_description":    SVG.EDIT,
    "free_email_contact":   SVG.MAIL_WARN,
    "urgency_pressure":     SVG.CLOCK,
    "no_company_info":      SVG.BUILDING,
    "req_paradox":          SVG.LAYERS,
    "personal_info_demand": SVG.ID_CARD,
    "location_mismatch":    SVG.MAP_PIN,
    "work_from_home_bait":  SVG.HOME,
    "missing_salary":       SVG.DOLLAR_OFF,
    "poor_grammar":         SVG.FILE_TEXT,
    "generic_template":     SVG.COPY,
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
    "rocketmail.com","zohomail.com",
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

# ── Phrase lists ──────────────────────────────────────────────────────────────

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
    r"be part of.*revolution",r"make.*difference",
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
    r"salary.*negotiable.*up.*to.*\d{6}",r"\d.*crore.*annual",
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
    r"headquartered.*abroad.*pay.*in.*inr",
]
_WFH_PHRASES = [
    r"100%.*work.*from.*home.*high.*salary",r"part.time.*earn.*full.time.*salary",
    r"just.*[0-9].*hour.*day.*earn",r"online.*job.*no.*skill.*required",
    r"data.*entry.*earn.*\d{4,}",r"captcha.*job",r"ad.*posting.*earn",
    r"copy.*paste.*earn",r"form.*filling.*earn",
]


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
            headers={"User-Agent": "ScamDetector/2.0"},
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
                    out.update(
                        status="young" if age < 180 else "old",
                        age_days=age,
                        registered=dt.strftime("%d %b %Y"),
                        detail=f"Registered {dt.strftime('%d %b %Y')} ({age} days ago)",
                    )
                    return out
                except ValueError:
                    continue
        out["detail"] = "Registration date not in RDAP response"
    except Exception as e:
        out["status"]  = "error"
        out["detail"]  = f"RDAP unavailable: {type(e).__name__}"
    return out


def _probe_site_reachable(domain: str) -> dict:
    out = {"reachable": None, "status_code": None, "detail": ""}
    if not domain:
        return out
    for scheme in ("https", "http"):
        try:
            req = urllib.request.Request(
                f"{scheme}://{domain}", method="HEAD",
                headers={"User-Agent": "Mozilla/5.0 ScamDetector/2.0"},
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
        sc = max(
            difflib.SequenceMatcher(None, d_sld, b_sld).ratio(),
            difflib.SequenceMatcher(None, domain, b).ratio(),
        )
        if sc > best:
            best, brand = sc, b
    out["similarity"]    = round(best, 3)
    out["closest_brand"] = brand
    if best >= 0.72 and domain != brand:
        out["is_squatter"] = True
        out["detail"] = f"'{domain}' is {int(best*100)}% similar to '{brand}' — possible impersonation"
    else:
        out["detail"] = f"No close brand match (best: {int(best*100)}% similarity to {brand})"
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
    out["detail"] = "No free/personal email domains detected" if emails else "No email address found in input"
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
            url,
            headers={"User-Agent": "Mozilla/5.0 (compatible; ScamDetector/2.0)",
                     "Accept": "application/json, text/html"},
        )
        with urllib.request.urlopen(req, timeout=_T_MCA) as resp:
            raw = resp.read().decode("utf-8", errors="ignore")

        stopwords = {"LIMITED","PRIVATE","PUBLIC","INDIA","SERVICES","SOLUTIONS",
                     "TECHNOLOGIES","CONSULTANCY","ENTERPRISES","AND","THE"}
        words = [w for w in name_clean.upper().split() if len(w) > 3 and w not in stopwords]
        hits  = sum(1 for w in words if w in raw.upper())

        if hits >= max(1, len(words) // 2):
            out.update(found=True, detail="Company name found in MCA database — legally registered")
        elif "no record" in raw.lower() or "not found" in raw.lower():
            out.update(found=False, detail="Company NOT found in MCA — may not be legally registered in India")
        else:
            out["detail"] = "MCA search inconclusive — verify at mca.gov.in"
    except Exception as e:
        out["detail"] = f"MCA lookup unavailable ({type(e).__name__}) — verify manually"
    return out


def run_live_probes(job: dict) -> dict:
    website = job.get("website", "")
    contact = job.get("contact", "") + " " + job.get("description", "")
    company = job.get("company", "")

    domain = _extract_domain(website)
    if not domain:
        for em_dom in re.findall(r"[\w.+\-]+@([\w\-]+\.[a-zA-Z]{2,})", contact):
            if em_dom.lower() not in _FREE_DOMAINS:
                domain = em_dom
                break

    probes: dict = {
        "domain_age":    {"status": "skipped", "detail": "No domain provided"},
        "site_reach":    {"reachable": None,   "detail": "No domain provided"},
        "typosquat":     {"is_squatter": False, "detail": "No domain provided"},
        "free_email":    {"uses_free_domain": False, "detail": ""},
        "mca":           {"found": None,       "detail": ""},
    }

    lock = threading.Lock()

    def _run(key: str, fn, arg: str):
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
    full = " ".join([
        job.get("title",""), job.get("description",""), job.get("requirements",""),
        job.get("benefits",""), job.get("contact",""), job.get("salary",""),
    ])

    sigs: dict = {}

    def _add(k: str, label: str, detail: str, hits=None):
        sigs[k] = {"label": label, "detail": detail, "hits": (hits or [])[:3]}

    h = _any(full, _PAY_PHRASES)
    if h:
        _add("upfront_payment","Upfront Payment Demanded",
             "Legitimate employers never ask you to pay before or during hiring.",h)

    h = _any(full, _MLM_PHRASES)
    if h:
        _add("mlm_pyramid","MLM / Pyramid Scheme Indicators",
             "Language suggests a recruitment-based commission model, not a real job.",h)

    if _salary_outlier(job.get("salary","") + " " + job.get("description","")):
        _add("too_good_salary","Unrealistically High Salary",
             "Offered compensation is far above verified market rates for this role.")

    h = _any(full, _UNREALISTIC_PHRASES)
    if h:
        _add("unrealistic_benefits","Unrealistic Benefit Claims",
             "Promised earnings or perks are statistically implausible.",h)

    h = _any(full, _VAGUE_PHRASES)
    if len(h) >= 2:
        _add("vague_description","Vague / Generic Description",
             "Real postings specify responsibilities. Vagueness may hide a non-existent role.",h)

    free_hits = [e for e in re.findall(r"[\w.+\-]+@([\w\-]+\.[a-zA-Z]{2,})",full)
                 if e.lower() in _FREE_DOMAINS]
    if free_hits:
        _add("free_email_contact","Personal / Free Email Used",
             "Corporate recruiters use company domain email, not Gmail/Yahoo/Hotmail.",free_hits)

    h = _any(full, _URGENCY_PHRASES)
    if h:
        _add("urgency_pressure","Artificial Urgency / Pressure Tactics",
             "Creating panic prevents candidates from properly researching the company.",h)

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
    if h:
        _add("personal_info_demand","Premature Personal Info Request",
             "Requesting Aadhaar/PAN/passport at application stage is a major red flag.",h)

    h = _any(full, _LOCATION_CLUES)
    if h:
        _add("location_mismatch","Location / Jurisdiction Mismatch",
             "Company location, pay currency and candidate requirements do not align.",h)

    h = _any(full, _WFH_PHRASES)
    if h:
        _add("work_from_home_bait","WFH Bait — Data Entry / Form Filling",
             "High-pay 'work from home' roles with no skills required are almost always scams.",h)

    if not job.get("salary","").strip() or len(job.get("salary","").strip()) < 4:
        _add("missing_salary","Salary Completely Absent",
             "Hidden salary is commonly used to lure, then lowball candidates.")

    g_hits = _any(full, _GRAMMAR_PATTERNS)
    if len(g_hits) >= 2:
        _add("poor_grammar","Suspicious Grammar / Formatting",
             "Excessive punctuation, random CAPS or known spam-text patterns detected.",g_hits)

    score = min(sum(_WEIGHTS.get(k,0) for k in sigs), 100)
    return {"signals": sigs, "rule_score": score}


# ─────────────────────────────────────────────────────────────────────────────
# LLM
# ─────────────────────────────────────────────────────────────────────────────

def _llm_prompt(job: dict, probe_warnings: list[str]) -> str:
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

Required JSON schema (all keys, no extras):
{{
  "ai_risk_score": <0-100>,
  "verdict": "<SAFE|SUSPICIOUS|LIKELY_SCAM|DEFINITE_SCAM>",
  "company_legitimacy": "<VERIFIED|UNVERIFIABLE|LIKELY_FAKE|GHOST_COMPANY>",
  "top_red_flags": ["<str>","<str>","<str>"],
  "positive_signals": ["<str>"],
  "fake_company_evidence": "<detailed reasoning>",
  "linguistic_analysis": "<tone, urgency, grammar observations>",
  "salary_assessment": "<realistic or not for this role and location>",
  "recommended_action": "<specific advice for the job seeker>",
  "similar_scam_type": "<known pattern name or Unknown>",
  "confidence": <0-100>
}}"""


# ─────────────────────────────────────────────────────────────────────────────
# ORCHESTRATOR
# ─────────────────────────────────────────────────────────────────────────────

def analyze_job_posting(job: dict, call_llm_fn, session) -> dict:
    rules   = _run_rules(job)
    probes  = run_live_probes(job)
    penalty, warnings = _probe_risk(probes)

    llm_raw  = call_llm_fn(_llm_prompt(job, warnings), session,
                            model="llama-3.3-70b-versatile", temperature=0)
    llm_data: dict = {}
    try:
        clean = re.sub(r"```json|```", "", llm_raw).strip()
        m = re.search(r"\{.*\}", clean, re.DOTALL)
        if m:
            llm_data = json.loads(m.group())
    except Exception:
        pass

    ai_s   = int(llm_data.get("ai_risk_score", rules["rule_score"]))
    rule_s = rules["rule_score"]
    blended = int(0.55 * ai_s + 0.30 * rule_s + 0.15 * penalty)
    blended = min(max(blended, rule_s, penalty), 100)

    _sev = {"SAFE":0,"SUSPICIOUS":1,"LIKELY_SCAM":2,"DEFINITE_SCAM":3}
    sv = ("DEFINITE_SCAM" if blended>=75 else "LIKELY_SCAM" if blended>=50
          else "SUSPICIOUS" if blended>=25 else "SAFE")
    av = llm_data.get("verdict", sv)
    final = av if _sev.get(av,1) > _sev.get(sv,0) else sv

    return {
        "blended_score": blended, "rule_score": rule_s,
        "ai_score": ai_s,         "probe_penalty": penalty,
        "final_verdict": final,   "signals": rules["signals"],
        "probes": probes,         "probe_warnings": warnings,
        "llm": llm_data,          "job": job,
        "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M"),
    }


# ─────────────────────────────────────────────────────────────────────────────
# VERDICT CONFIG
# ─────────────────────────────────────────────────────────────────────────────

_V_CFG = {
    "SAFE":          {"icon":SVG.CHECK_CIRCLE, "color":"#22c55e",
                      "bg":"rgba(34,197,94,0.07)",  "border":"rgba(34,197,94,0.25)",
                      "label":"SAFE TO APPLY"},
    "SUSPICIOUS":    {"icon":SVG.ALERT_TRI,    "color":"#f59e0b",
                      "bg":"rgba(245,158,11,0.07)", "border":"rgba(245,158,11,0.25)",
                      "label":"PROCEED WITH CAUTION"},
    "LIKELY_SCAM":   {"icon":SVG.ALERT_CIRCLE, "color":"#ef4444",
                      "bg":"rgba(239,68,68,0.07)",  "border":"rgba(239,68,68,0.25)",
                      "label":"LIKELY SCAM"},
    "DEFINITE_SCAM": {"icon":SVG.SKULL,        "color":"#dc2626",
                      "bg":"rgba(220,38,38,0.09)",  "border":"rgba(220,38,38,0.35)",
                      "label":"DEFINITE SCAM — DO NOT APPLY"},
    "UNKNOWN":       {"icon":SVG.INFO,          "color":"#6b7280",
                      "bg":"rgba(107,114,128,0.07)","border":"rgba(107,114,128,0.2)",
                      "label":"INCONCLUSIVE"},
}
_C_BADGE = {
    "VERIFIED":      (SVG.CHECK_CIRCLE,"#22c55e"),
    "UNVERIFIABLE":  (SVG.ALERT_TRI,   "#f59e0b"),
    "LIKELY_FAKE":   (SVG.FLAG,        "#ef4444"),
    "GHOST_COMPANY": (SVG.GHOST,       "#dc2626"),
}


def _bar(score: int, color: str) -> str:
    return (f'<div style="background:rgba(255,255,255,0.06);border-radius:999px;'
            f'height:7px;overflow:hidden;margin:7px 0;">'
            f'<div style="height:7px;width:{score}%;background:{color};'
            f'border-radius:999px;"></div></div>')


def _badge(text: str, color: str, bg: str) -> str:
    return (f'<span style="background:{bg};color:{color};padding:2px 9px;'
            f'border-radius:999px;font-size:0.71rem;font-weight:600;">{text}</span>')


# ─────────────────────────────────────────────────────────────────────────────
# UI SECTIONS
# ─────────────────────────────────────────────────────────────────────────────

def _render_verdict_banner(result: dict):
    v   = result["final_verdict"]
    cfg = _V_CFG.get(v, _V_CFG["UNKNOWN"])
    s   = result["blended_score"]
    st.markdown(f"""
    <div style="padding:26px;border-radius:14px;background:{cfg['bg']};
                border:1.5px solid {cfg['border']};margin-bottom:20px;text-align:center;">
      <div style="display:flex;align-items:center;justify-content:center;
                  gap:10px;margin-bottom:8px;">
        {_i(cfg['icon'], 26, cfg['color'])}
        <div style="font-size:1.4rem;font-weight:700;color:{cfg['color']};
                    letter-spacing:0.4px;">{cfg['label']}</div>
      </div>
      <div style="color:#c9d1d9;font-size:0.88rem;">
        Risk Score: <strong style="color:{cfg['color']};font-size:1.1rem;">{s}/100</strong>
      </div>
      {_bar(s, cfg['color'])}
    </div>""", unsafe_allow_html=True)


def _render_score_row(result: dict):
    cfg = _V_CFG.get(result["final_verdict"], _V_CFG["UNKNOWN"])
    def _card(icon_path, label, val, color):
        return f"""
        <div style="background:rgba(255,255,255,0.03);border:1px solid rgba(255,255,255,0.07);
                    border-radius:10px;padding:15px;text-align:center;">
          <div style="display:flex;align-items:center;justify-content:center;gap:5px;
                      color:#6b7280;font-size:0.68rem;text-transform:uppercase;
                      letter-spacing:1px;margin-bottom:5px;">
            {_i(icon_path,11,'#6b7280')}{label}
          </div>
          <div style="font-size:1.85rem;font-weight:700;color:{color};">{val}</div>
        </div>"""
    c1,c2,c3,c4 = st.columns(4)
    c1.markdown(_card(SVG.CPU,      "AI Score",      result["ai_score"],      cfg["color"]),  unsafe_allow_html=True)
    c2.markdown(_card(SVG.LIST,     "Rule Score",    result["rule_score"],    "#f59e0b"),      unsafe_allow_html=True)
    c3.markdown(_card(SVG.GLOBE,    "Probe Penalty", result["probe_penalty"], "#38bdf8"),      unsafe_allow_html=True)
    c4.markdown(_card(SVG.ZAP,      "Signals",       len(result["signals"]), "#a78bfa"),      unsafe_allow_html=True)


def _render_probe_table(probes: dict):
    def _row(icon_path, label, badge_html, detail):
        return (
            f'<tr style="border-bottom:1px solid rgba(255,255,255,0.05);">'
            f'<td style="padding:10px 14px;white-space:nowrap;">'
            f'<div style="display:flex;align-items:center;gap:7px;color:#c9d1d9;font-size:0.81rem;">'
            f'{_i(icon_path,12,"#8b949e")}{label}</div></td>'
            f'<td style="padding:10px 14px;">{badge_html}</td>'
            f'<td style="padding:10px 14px;color:#8b949e;font-size:0.77rem;">{detail}</td>'
            f'</tr>'
        )

    rows = []

    # 1 Domain age
    age = probes.get("domain_age", {})
    st_ = age.get("status","unknown")
    if st_ == "young":   b = _badge("YOUNG DOMAIN","#dc2626","rgba(220,38,38,0.12)")
    elif st_ == "old":   b = _badge("ESTABLISHED","#22c55e","rgba(34,197,94,0.12)")
    elif st_ == "error": b = _badge("LOOKUP FAILED","#6b7280","rgba(107,114,128,0.12)")
    else:                b = _badge("NO DOMAIN","#6b7280","rgba(107,114,128,0.12)")
    rows.append(_row(SVG.CALENDAR,"Domain Age",b,age.get("detail","")))

    # 2 Site reachable
    r = probes.get("site_reach",{})
    if r.get("reachable") is True:  b = _badge("REACHABLE","#22c55e","rgba(34,197,94,0.12)")
    elif r.get("reachable") is False:b = _badge("UNREACHABLE","#dc2626","rgba(220,38,38,0.12)")
    else:                            b = _badge("NOT CHECKED","#6b7280","rgba(107,114,128,0.12)")
    rows.append(_row(SVG.SERVER,"Site Reachability",b,r.get("detail","")))

    # 3 Typosquatting
    t = probes.get("typosquat",{})
    if t.get("is_squatter"):
        b = _badge("TYPOSQUAT RISK","#dc2626","rgba(220,38,38,0.12)")
    else:
        pct = int(t.get("similarity",0)*100)
        b = _badge(f"LOW RISK ({pct}%)","#f59e0b","rgba(245,158,11,0.12)") if pct>=50 \
            else _badge("CLEAR","#22c55e","rgba(34,197,94,0.12)")
    rows.append(_row(SVG.COPY,"Typosquatting",b,t.get("detail","")))

    # 4 Free email
    fe = probes.get("free_email",{})
    b  = _badge("FREE EMAIL","#dc2626","rgba(220,38,38,0.12)") if fe.get("uses_free_domain") \
         else _badge("CLEAR","#22c55e","rgba(34,197,94,0.12)")
    rows.append(_row(SVG.MAIL,"Email Domain",b,fe.get("detail","")))

    # 5 MCA
    mca = probes.get("mca",{})
    if mca.get("found") is True:  b = _badge("FOUND IN MCA","#22c55e","rgba(34,197,94,0.12)")
    elif mca.get("found") is False:b = _badge("NOT IN MCA","#dc2626","rgba(220,38,38,0.12)")
    else:                          b = _badge("INCONCLUSIVE","#f59e0b","rgba(245,158,11,0.12)")
    rows.append(_row(SVG.BUILDING,"MCA Registry (India)",b,mca.get("detail","")))

    st.markdown(f"""
    <div style="border:1px solid rgba(255,255,255,0.08);border-radius:10px;
                overflow:hidden;margin-bottom:18px;">
      <div style="background:rgba(255,255,255,0.03);padding:10px 14px;
                  font-size:0.72rem;font-weight:600;color:#8b949e;
                  text-transform:uppercase;letter-spacing:1px;
                  display:flex;align-items:center;gap:7px;">
        {_i(SVG.GLOBE,11,'#6b7280')} Live Network Probes
      </div>
      <table style="width:100%;border-collapse:collapse;">
        <thead><tr style="border-bottom:1px solid rgba(255,255,255,0.07);">
          <th style="padding:7px 14px;font-size:0.68rem;color:#6b7280;font-weight:500;text-align:left;width:20%;">Check</th>
          <th style="padding:7px 14px;font-size:0.68rem;color:#6b7280;font-weight:500;text-align:left;width:18%;">Result</th>
          <th style="padding:7px 14px;font-size:0.68rem;color:#6b7280;font-weight:500;text-align:left;">Detail</th>
        </tr></thead>
        <tbody>{''.join(rows)}</tbody>
      </table>
    </div>""", unsafe_allow_html=True)


def _render_signal_cards(signals: dict):
    if not signals:
        st.markdown(f"""
        <div style="display:flex;align-items:center;gap:8px;padding:14px 16px;
                    background:rgba(34,197,94,0.06);border:1px solid rgba(34,197,94,0.18);
                    border-radius:8px;color:#22c55e;font-size:0.84rem;">
          {_i(SVG.CHECK_CIRCLE,14,'#22c55e')} No rule-based red flags detected.
        </div>""", unsafe_allow_html=True)
        return

    cols = st.columns(2)
    for i,(k,sig) in enumerate(signals.items()):
        w     = _WEIGHTS.get(k,5)
        color = "#ef4444" if w>=18 else "#f59e0b" if w>=10 else "#a78bfa"
        hits_html = (
            f'<div style="margin-top:5px;font-size:0.69rem;color:#6b7280;font-style:italic;">'
            f'Matched: {", ".join(sig["hits"][:2])}</div>'
            if sig.get("hits") else ""
        )
        with cols[i%2]:
            st.markdown(f"""
            <div style="background:rgba(255,255,255,0.025);border:1px solid {color}28;
                        border-radius:10px;padding:13px;margin-bottom:9px;">
              <div style="display:flex;align-items:flex-start;gap:8px;">
                {_i(_SIG_ICON.get(k,SVG.ALERT_TRI),13,color)}
                <div style="flex:1;">
                  <div style="font-weight:600;color:{color};font-size:0.83rem;">
                    {sig['label']}</div>
                  <div style="color:#8b949e;font-size:0.76rem;margin-top:3px;
                              line-height:1.5;">{sig['detail']}</div>
                  {hits_html}
                  <div style="display:flex;align-items:center;gap:5px;margin-top:7px;">
                    <span style="font-size:0.64rem;color:#6b7280;">Weight</span>
                    <div style="flex:1;background:rgba(255,255,255,0.06);border-radius:999px;
                                height:4px;overflow:hidden;">
                      <div style="height:4px;width:{min(w*4,100)}%;background:{color};
                                  border-radius:999px;"></div>
                    </div>
                    <span style="font-size:0.67rem;color:{color};font-weight:700;">+{w}</span>
                  </div>
                </div>
              </div>
            </div>""", unsafe_allow_html=True)


def _render_ai_dive(llm: dict):
    if not llm:
        st.markdown('<p style="color:#6b7280;font-size:0.82rem;">AI analysis unavailable.</p>',
                    unsafe_allow_html=True)
        return

    cl  = llm.get("company_legitimacy","UNVERIFIABLE")
    ci, cc = _C_BADGE.get(cl,(_C_BADGE["UNVERIFIABLE"]))

    st.markdown(f"""
    <div style="display:grid;grid-template-columns:1fr 1fr;gap:9px;margin-bottom:13px;">
      <div style="background:rgba(255,255,255,0.03);border:1px solid rgba(255,255,255,0.07);
                  border-radius:8px;padding:11px;">
        <div style="font-size:0.67rem;color:#6b7280;text-transform:uppercase;
                    letter-spacing:1px;margin-bottom:5px;">Company Status</div>
        <div style="display:flex;align-items:center;gap:5px;color:{cc};font-weight:600;
                    font-size:0.83rem;">{_i(ci,12,cc)}{cl.replace('_',' ')}</div>
      </div>
      <div style="background:rgba(255,255,255,0.03);border:1px solid rgba(255,255,255,0.07);
                  border-radius:8px;padding:11px;">
        <div style="font-size:0.67rem;color:#6b7280;text-transform:uppercase;
                    letter-spacing:1px;margin-bottom:5px;">Scam Pattern</div>
        <div style="color:#a78bfa;font-weight:600;font-size:0.83rem;">
          {llm.get('similar_scam_type','Unknown')}</div>
      </div>
    </div>""", unsafe_allow_html=True)

    fc1, fc2 = st.columns(2)
    with fc1:
        st.markdown('<div style="font-size:0.73rem;font-weight:600;color:#ef4444;'
                    'text-transform:uppercase;letter-spacing:0.8px;margin-bottom:7px;">'
                    'AI Red Flags</div>', unsafe_allow_html=True)
        for f in llm.get("top_red_flags",[])[:5]:
            st.markdown(f'<div style="background:rgba(239,68,68,0.05);border-left:2px solid #ef4444;'
                        f'padding:6px 10px;border-radius:0 5px 5px 0;margin-bottom:5px;'
                        f'color:#fca5a5;font-size:0.79rem;">{f}</div>', unsafe_allow_html=True)
    with fc2:
        st.markdown('<div style="font-size:0.73rem;font-weight:600;color:#22c55e;'
                    'text-transform:uppercase;letter-spacing:0.8px;margin-bottom:7px;">'
                    'Positive Signals</div>', unsafe_allow_html=True)
        pos = llm.get("positive_signals",[])
        if pos:
            for p in pos[:5]:
                st.markdown(f'<div style="background:rgba(34,197,94,0.05);border-left:2px solid #22c55e;'
                            f'padding:6px 10px;border-radius:0 5px 5px 0;margin-bottom:5px;'
                            f'color:#86efac;font-size:0.79rem;">{p}</div>', unsafe_allow_html=True)
        else:
            st.markdown('<div style="color:#6b7280;font-size:0.79rem;font-style:italic;">'
                        'No positive signals identified.</div>', unsafe_allow_html=True)

    for field, icon_path, title in [
        ("fake_company_evidence", SVG.GHOST,     "Company Legitimacy Analysis"),
        ("linguistic_analysis",   SVG.FILE_TEXT, "Linguistic Pattern Analysis"),
        ("salary_assessment",     SVG.DOLLAR,    "Salary Reality Check"),
        ("recommended_action",    SVG.SHIELD,    "Recommended Action"),
    ]:
        val = llm.get(field,"")
        if not val:
            continue
        st.markdown(f"""
        <div style="background:rgba(255,255,255,0.02);border:1px solid rgba(255,255,255,0.06);
                    border-radius:8px;padding:13px;margin-bottom:9px;">
          <div style="display:flex;align-items:center;gap:6px;font-size:0.7rem;
                      font-weight:600;color:#8b949e;text-transform:uppercase;
                      letter-spacing:0.8px;margin-bottom:7px;">
            {_i(icon_path,11,'#6b7280')}{title}
          </div>
          <div style="color:#c9d1d9;font-size:0.83rem;line-height:1.65;">{val}</div>
        </div>""", unsafe_allow_html=True)

    conf = llm.get("confidence","—")
    st.markdown(f'<div style="text-align:right;color:#6b7280;font-size:0.7rem;margin-top:3px;">'
                f'AI Confidence: {conf}/100</div>', unsafe_allow_html=True)


_CHECKLIST = [
    (SVG.SEARCH,    "Search company name + 'scam' or 'fraud' on Google",               True),
    (SVG.BUILDING,  "Verify company on LinkedIn, MCA.gov.in, or Companies House",       True),
    (SVG.CALENDAR,  "Check domain age on whois.domaintools.com",                        True),
    (SVG.LINK,      "Confirm the vacancy exists on the official company careers page",  True),
    (SVG.CREDIT_CARD,"Never pay any fee before or during the hiring process",           True),
    (SVG.MAIL,      "Verify recruiter email domain matches the company website domain", True),
    (SVG.EYE,       "Reverse image search the recruiter's profile photo",               False),
    (SVG.AWARD,     "Check Glassdoor / AmbitionBox for employee reviews",              True),
    (SVG.PHONE,     "Call the company's official number to confirm the vacancy",        False),
    (SVG.ID_CARD,   "Never submit Aadhaar/PAN/passport at initial application stage",   True),
]


def _render_checklist(result: dict):
    st.markdown('<div style="font-size:0.72rem;font-weight:600;color:#8b949e;'
                'text-transform:uppercase;letter-spacing:1px;margin-bottom:10px;">'
                'Manual Verification Checklist</div>', unsafe_allow_html=True)
    for idx,(icon_path,text,default) in enumerate(_CHECKLIST):
        st.checkbox(text, value=default, key=f"jsd_c_{idx}_{id(result)}")

    st.markdown("""
    <div style="margin-top:14px;padding:11px 15px;
                background:rgba(56,189,248,0.05);border:1px solid rgba(56,189,248,0.14);
                border-radius:8px;color:#7dd3fc;font-size:0.8rem;line-height:1.6;">
      <strong>Tip:</strong> If 3 or more items fail this checklist AND the AI score
      exceeds 40, walk away. No legitimate employer requires upfront payment.
    </div>""", unsafe_allow_html=True)


def _add_to_history(result: dict):
    h = st.session_state.setdefault("jsd_history",[])
    h.insert(0,{"title":result["job"].get("title","Untitled"),
                "company":result["job"].get("company","Unknown"),
                "score":result["blended_score"],
                "verdict":result["final_verdict"],
                "time":result["timestamp"]})
    st.session_state["jsd_history"] = h[:10]


def _render_history():
    history = st.session_state.get("jsd_history",[])
    if not history:
        st.markdown('<div style="color:#6b7280;font-size:0.79rem;text-align:center;'
                    'padding:18px 0;font-style:italic;">No analyses yet.</div>',
                    unsafe_allow_html=True)
        return
    for h in history:
        cfg = _V_CFG.get(h["verdict"],_V_CFG["UNKNOWN"])
        st.markdown(f"""
        <div style="padding:9px 11px;background:rgba(255,255,255,0.02);
                    border:1px solid rgba(255,255,255,0.06);border-radius:8px;
                    margin-bottom:6px;">
          <div style="color:#c9d1d9;font-size:0.8rem;font-weight:500;overflow:hidden;
                      white-space:nowrap;text-overflow:ellipsis;">{h['title']}</div>
          <div style="color:#6b7280;font-size:0.7rem;margin-top:1px;">{h['company']}</div>
          <div style="display:flex;justify-content:space-between;align-items:center;
                      margin-top:5px;">
            <span style="color:#6b7280;font-size:0.68rem;">{h['time']}</span>
            <span style="color:{cfg['color']};font-size:0.75rem;font-weight:700;">
              {h['score']}/100</span>
          </div>
          {_bar(h['score'],cfg['color'])}
        </div>""", unsafe_allow_html=True)


# ─────────────────────────────────────────────────────────────────────────────
# AUTO-EXTRACT HELPERS
# ─────────────────────────────────────────────────────────────────────────────

def _xf(text:str, kws:list)->str:
    for kw in kws:
        m=re.search(rf"(?i){kw}[:\s]+([^\n]{{3,60}})",text or "")
        if m: return m.group(1).strip()
    return ""

def _xu(text:str)->str:
    m=re.search(r"https?://[^\s)\"']{4,}",text or "")
    return m.group(0) if m else ""

def _xs(text:str)->str:
    m=re.search(r"(?i)(salary|ctc|pay|package|compensation)[:\s]+([^\n]{3,60})",text or "")
    if m: return m.group(2).strip()
    m2=re.search(r"(?:₹|INR|\$|USD)[\s\d,\-LPAlpa.]+",text or "")
    return m2.group(0).strip() if m2 else ""

def _xc(text:str)->str:
    emails=re.findall(r"[\w.+\-]+@[\w\-]+\.[a-zA-Z]{2,}",text or "")
    phones=re.findall(r"[+]?[\d\s\-(]{10,15}",text or "")
    return " | ".join(emails[:1]+phones[:1])


# ─────────────────────────────────────────────────────────────────────────────
# MAIN RENDER ENTRY POINT
# ─────────────────────────────────────────────────────────────────────────────

def render_job_scam_detector_tab(call_llm_fn):
    """
    Call this from maaaaain_py.py:
        with tab_scam:
            render_job_scam_detector_tab(call_llm)
    """
    # ── Header ─────────────────────────────────────────────────────────────────
    st.markdown(f"""
    <div style="padding:18px 0 4px;">
      <div style="display:flex;align-items:center;gap:12px;margin-bottom:6px;">
        {_i(SVG.SHIELD,30,'#ef4444',1.8)}
        <div>
          <h2 style="margin:0;color:#e6edf3;font-size:1.42rem;font-weight:700;">
            Job Scam Detector</h2>
          <p style="margin:2px 0 0;color:#8b949e;font-size:0.82rem;">
            AI analysis + live network probes to detect fake job postings
            and fraudulent companies before you apply.
          </p>
        </div>
      </div>
    </div>""", unsafe_allow_html=True)

    # Feature pills
    def _pill(icon_path, text, color):
        return (f'<span style="display:inline-flex;align-items:center;gap:5px;'
                f'background:rgba(255,255,255,0.04);color:{color};padding:4px 10px;'
                f'border-radius:999px;font-size:0.7rem;border:1px solid {color}30;">'
                f'{_i(icon_path,10,color)}{text}</span>')

    st.markdown(
        '<div style="display:flex;flex-wrap:wrap;gap:6px;margin-bottom:20px;">'
        + _pill(SVG.CPU,       "AI Deep Analysis",      "#a78bfa")
        + _pill(SVG.CALENDAR,  "Domain Age Probe",       "#38bdf8")
        + _pill(SVG.MAIL,      "Free Email Detection",   "#f59e0b")
        + _pill(SVG.COPY,      "Typosquat Check",        "#ef4444")
        + _pill(SVG.BUILDING,  "MCA Registry",           "#22c55e")
        + _pill(SVG.SERVER,    "Site Reachability",      "#6366f1")
        + _pill(SVG.LIST,      "15-Signal Rule Engine",  "#8b949e")
        + '</div>',
        unsafe_allow_html=True,
    )

    # ── Layout ─────────────────────────────────────────────────────────────────
    form_col, hist_col = st.columns([3,1], gap="large")

    with hist_col:
        st.markdown(
            f'<div style="display:flex;align-items:center;gap:6px;font-size:0.72rem;'
            f'font-weight:600;color:#8b949e;text-transform:uppercase;'
            f'letter-spacing:1px;margin-bottom:8px;">'
            f'{_i(SVG.HISTORY,11,"#6b7280")} Recent Analyses</div>',
            unsafe_allow_html=True,
        )
        _render_history()

    with form_col:
        st.markdown(
            f'<div style="display:flex;align-items:center;gap:6px;font-size:0.82rem;'
            f'font-weight:600;color:#c9d1d9;margin-bottom:11px;">'
            f'{_i(SVG.EDIT,13)} Enter Job Posting Details</div>',
            unsafe_allow_html=True,
        )

        mode = st.radio("mode",["Paste Full Job Description","Fill Individual Fields"],
                        horizontal=True, key="jsd_mode", label_visibility="collapsed")
        job: dict = {}

        if mode == "Paste Full Job Description":
            raw = st.text_area(
                "Paste the full job description",height=255,key="jsd_raw",
                placeholder="Paste the complete posting — company name, website, salary, "
                            "requirements, benefits, contact details...",
            )
            job = {"title":_xf(raw,["position","role","title","job"]),
                   "company":_xf(raw,["company","organization","firm"]),
                   "website":_xu(raw), "location":_xf(raw,["location","city","based in"]),
                   "salary":_xs(raw), "description":raw, "requirements":raw,
                   "benefits":raw, "contact":_xc(raw)}
            c1,c2 = st.columns(2)
            job["title"]   = c1.text_input("Detected Title",   value=job["title"],   key="jsd_dt")
            job["company"] = c2.text_input("Detected Company", value=job["company"], key="jsd_dc")
            job["salary"]  = c1.text_input("Detected Salary",  value=job["salary"],  key="jsd_ds")
            job["contact"] = c2.text_input("Detected Contact", value=job["contact"], key="jsd_dco")
            job["website"] = st.text_input("Detected Website", value=job["website"], key="jsd_dw")
        else:
            a,b_ = st.columns(2)
            job["title"]    = a.text_input("Job Title",       placeholder="e.g., Software Engineer",  key="jsd_t")
            job["company"]  = b_.text_input("Company Name",   placeholder="e.g., Acme Corp",          key="jsd_co")
            c,d = st.columns(2)
            job["website"]  = c.text_input("Company Website", placeholder="https://acmecorp.com",     key="jsd_w")
            job["location"] = d.text_input("Location",        placeholder="e.g., Bangalore, India",   key="jsd_l")
            e,f = st.columns(2)
            job["salary"]   = e.text_input("Salary Offered",  placeholder="e.g., 8-12 LPA",           key="jsd_sa")
            job["contact"]  = f.text_input("Contact Email",   placeholder="e.g., hr@acme.com",        key="jsd_ct")
            job["description"]  = st.text_area("Job Description",  height=120,key="jsd_d",
                                                placeholder="Describe the role and responsibilities...")
            job["requirements"] = st.text_area("Requirements",     height=85, key="jsd_r",
                                                placeholder="Required skills, experience, qualifications...")
            job["benefits"]     = st.text_area("Benefits / Perks", height=65, key="jsd_b",
                                                placeholder="What the employer offers...")

        full_check = " ".join(str(v) for v in job.values()).strip()
        if len(full_check) < 30:
            st.markdown(f"""
            <div style="display:flex;align-items:center;gap:7px;padding:11px 14px;
                        background:rgba(56,189,248,0.05);border:1px solid rgba(56,189,248,0.14);
                        border-radius:8px;color:#7dd3fc;font-size:0.8rem;margin-top:8px;">
              {_i(SVG.INFO,12,'#38bdf8')}
              Enter a job description or fill the fields above to start analysis.
            </div>""", unsafe_allow_html=True)
        else:
            if st.button("Analyse for Scam Signals", type="primary",
                          use_container_width=True, key="jsd_btn"):
                with st.spinner("Running AI analysis and live network probes..."):
                    try:
                        res = analyze_job_posting(job, call_llm_fn, st.session_state)
                        st.session_state["jsd_last_result"] = res
                        _add_to_history(res)
                    except Exception as exc:
                        st.error(f"Analysis failed: {exc}")

    # ── Results ────────────────────────────────────────────────────────────────
    res = st.session_state.get("jsd_last_result")
    if not res:
        return

    st.markdown("<hr style='border-color:rgba(255,255,255,0.07);margin:18px 0;'>",
                unsafe_allow_html=True)
    st.markdown(f'<div style="display:flex;align-items:center;gap:7px;font-size:0.92rem;'
                f'font-weight:700;color:#e6edf3;margin-bottom:13px;">'
                f'{_i(SVG.BAR_CHART,14)} Analysis Results</div>', unsafe_allow_html=True)

    _render_verdict_banner(res)
    _render_score_row(res)
    st.markdown("<br>", unsafe_allow_html=True)
    _render_probe_table(res["probes"])

    t1, t2, t3 = st.tabs(["Detected Signals","AI Deep Dive","Safety Checklist"])

    with t1:
        st.markdown(f'<p style="color:#8b949e;font-size:0.8rem;margin-bottom:11px;">'
                    f'{len(res["signals"])} rule-based signal(s) fired — '
                    f'each contributes to the overall risk score.</p>',
                    unsafe_allow_html=True)
        _render_signal_cards(res["signals"])

    with t2:
        _render_ai_dive(res.get("llm",{}))

    with t3:
        _render_checklist(res)

    # Disclaimer
    st.markdown(f"""
    <div style="margin-top:18px;padding:10px 15px;
                background:rgba(107,114,128,0.04);border:1px solid rgba(107,114,128,0.13);
                border-radius:8px;display:flex;align-items:flex-start;gap:7px;
                color:#6b7280;font-size:0.73rem;">
      {_i(SVG.INFO,11,'#6b7280')}
      <span><strong style="color:#8b949e;">Disclaimer:</strong>
      This tool uses AI pattern matching and live network probes.
      It cannot guarantee 100% accuracy. A SAFE verdict does not guarantee
      a legitimate job. Always perform your own due diligence.</span>
    </div>""", unsafe_allow_html=True)
