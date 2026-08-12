# =============================================================
# tab3_ui.py
# All Streamlit UI rendering for Tab 3: CSS injection,
# job search interactive form, analytics dashboard,
# featured companies section, market insights, salary cards,
# and the reusable job card HTML builder.
# =============================================================

import streamlit as st
import streamlit.components.v1 as components
import uuid
from datetime import datetime
from zoneinfo import ZoneInfo

from tab3_data import (
    JOB_TITLES, LOCATIONS,
    JOB_MARKET_INSIGHTS,
    get_featured_companies,
)
from tab3_backend import (
    fetch_live_jobs,
    fetch_linkedin_jobs,
    save_job_search,
    delete_saved_job_search,
    get_saved_job_searches,
    get_total_saved_searches_count,
    get_available_platforms,
    fetch_analytics_data,
    clean_html,
)


# ═══════════════════════════════════════════════════════════════
# CSS INJECTION
# ═══════════════════════════════════════════════════════════════

def _inject_tab3_css():
    st.markdown("""
    <style>
    /* ═══════════════════════════════════════════════════════════
       TAB3 — Job Search Hub  · Premium Dark Theme
       Inherits global variables from tab1 CSS. Re-declares
       only the component classes specific to this tab.
       ═══════════════════════════════════════════════════════════ */

    :root {
        --t3-bg:          #080c12;
        --t3-surface:     rgba(255,255,255,0.04);
        --t3-border:      rgba(255,255,255,0.07);
        --t3-border-acc:  rgba(56,189,248,0.28);
        --t3-cyan:        #38bdf8;
        --t3-violet:      #818cf8;
        --t3-emerald:     #34d399;
        --t3-amber:       #fbbf24;
        --t3-rose:        #fb7185;
        --t3-text:        #f0f4f8;
        --t3-muted:       #64748b;
        --t3-font:        -apple-system, BlinkMacSystemFont, "SF Pro Display", "DM Sans", "Segoe UI", Roboto, sans-serif;
        --t3-ease:        cubic-bezier(0.4, 0, 0.2, 1);
    }

    /* ── Keyframes ── */
    @keyframes t3-fadeUp   { from { opacity:0; transform:translateY(14px); } to { opacity:1; transform:translateY(0); } }
    @keyframes t3-shimmer  { 0% { transform:translateX(-100%) skewX(-12deg); } 100% { transform:translateX(220%) skewX(-12deg); } }
    @keyframes t3-floatY   { 0%,100% { transform:translateY(0); } 50% { transform:translateY(-5px); } }
    @keyframes t3-pulse    { 0%,100% { opacity:1; } 50% { opacity:0.75; } }

    /* ══════════════════════════════════
       JOB SEARCH PAGE HEADER
       ══════════════════════════════════ */
    .t3-page-header {
        text-align: center;
        padding: 36px 24px 28px;
        position: relative;
    }
    .t3-page-title {
        font-family: var(--t3-font);
        font-size: 2rem;
        font-weight: 800;
        letter-spacing: -0.035em;
        color: var(--t3-text);
        line-height: 1.15;
        margin: 0 0 8px;
    }
    .t3-page-title span {
        background: linear-gradient(135deg, var(--t3-cyan) 0%, var(--t3-violet) 100%);
        -webkit-background-clip: text;
        -webkit-text-fill-color: transparent;
        background-clip: text;
    }
    .t3-page-sub {
        font-family: var(--t3-font);
        font-size: 0.875rem;
        color: var(--t3-muted);
        letter-spacing: 0.02em;
    }
    .t3-page-header::after {
        content: '';
        display: block;
        width: 48px;
        height: 2px;
        background: linear-gradient(90deg, var(--t3-cyan), var(--t3-violet));
        margin: 18px auto 0;
        border-radius: 2px;
    }

    /* ══════════════════════════════════
       MODE BADGE
       ══════════════════════════════════ */
    .mode-badge-wrap { text-align: center; margin: 0 0 10px 0; }
    .mode-badge {
        display: inline-flex;
        align-items: center;
        gap: 7px;
        padding: 8px 22px;
        border-radius: 99px;
        font-family: var(--t3-font);
        font-weight: 700;
        font-size: 0.8rem;
        letter-spacing: 0.04em;
        backdrop-filter: blur(16px);
        -webkit-backdrop-filter: blur(16px);
        border: 1px solid rgba(56,189,248,0.22);
        background: linear-gradient(135deg, rgba(56,189,248,0.14) 0%, rgba(129,140,248,0.08) 100%);
        color: var(--t3-cyan);
        transition: all 0.22s var(--t3-ease);
    }

    /* ══════════════════════════════════
       SECTION TITLE HEADERS
       ══════════════════════════════════ */
    .title-header {
        font-family: var(--t3-font) !important;
        font-size: 1.35rem !important;
        font-weight: 800 !important;
        letter-spacing: -0.025em !important;
        text-align: center !important;
        margin: 40px 0 24px !important;
        background: linear-gradient(135deg, var(--t3-cyan) 0%, var(--t3-violet) 100%) !important;
        -webkit-background-clip: text !important;
        -webkit-text-fill-color: transparent !important;
        background-clip: text !important;
        position: relative !important;
        animation: none !important;
    }
    .title-header::after {
        content: '' !important;
        position: absolute !important;
        bottom: -8px !important;
        left: 50% !important;
        transform: translateX(-50%) !important;
        width: 40px !important;
        height: 2px !important;
        background: linear-gradient(90deg, var(--t3-cyan), var(--t3-violet)) !important;
        border-radius: 2px !important;
    }

    /* ══════════════════════════════════
       COMPANY CARDS
       ══════════════════════════════════ */
    .company-card {
        background: var(--t3-surface);
        backdrop-filter: blur(24px) saturate(160%);
        -webkit-backdrop-filter: blur(24px) saturate(160%);
        color: var(--t3-text);
        border: 1px solid var(--t3-border);
        border-radius: 18px;
        padding: 24px;
        margin-bottom: 18px;
        box-shadow: 0 8px 32px rgba(0,0,0,0.3), inset 0 1px 0 rgba(255,255,255,0.05);
        transition: transform 0.26s var(--t3-ease),
                    box-shadow 0.26s var(--t3-ease),
                    border-color 0.26s var(--t3-ease);
        cursor: pointer;
        text-decoration: none;
        display: block;
        position: relative;
        overflow: hidden;
        animation: t3-fadeUp 0.5s ease forwards;
    }
    .company-card::before {
        content: '';
        position: absolute;
        top: 0; left: -100%;
        width: 55%; height: 100%;
        background: linear-gradient(90deg, transparent, rgba(56,189,248,0.05), transparent);
        animation: t3-shimmer 4s infinite;
        pointer-events: none;
    }
    .company-card:hover {
        transform: translateY(-5px);
        box-shadow: 0 16px 48px rgba(0,0,0,0.45), 0 0 36px rgba(56,189,248,0.10);
        border-color: var(--t3-border-acc);
        text-decoration: none;
        color: var(--t3-text);
    }

    /* ── Company card inner elements ── */
    .company-header {
        font-family: var(--t3-font);
        font-size: 1.05rem;
        font-weight: 700;
        letter-spacing: -0.01em;
        display: flex;
        align-items: center;
        margin-bottom: 10px;
        position: relative;
        z-index: 2;
        color: var(--t3-text);
    }
    .company-logo {
        height: 32px;
        width: auto;
        max-width: 90px;
        object-fit: contain;
        margin-right: 12px;
        flex-shrink: 0;
    }
    /* External logos (Google, Microsoft etc) get subtle dark-mode treatment */
    .company-card img[src^="https"] {
        filter: brightness(0.92) contrast(1.05);
        transition: filter 0.2s ease;
    }
    .company-card:hover img[src^="https"] {
        filter: brightness(1) contrast(1.1);
    }
    /* Data URI badge logos — no filter, already styled */
    .company-card img[src^="data"] {
        border-radius: 6px;
        filter: none;
    }

    /* ══════════════════════════════════
       CATEGORY PILLS
       ══════════════════════════════════ */
    .pill {
        display: inline-flex;
        align-items: center;
        background: rgba(255,255,255,0.05);
        padding: 4px 12px;
        border-radius: 99px;
        margin: 5px 6px 0 0;
        font-family: var(--t3-font);
        font-size: 0.75rem;
        font-weight: 600;
        letter-spacing: 0.03em;
        border: 1px solid rgba(255,255,255,0.09);
        color: var(--t3-muted);
        transition: all 0.2s var(--t3-ease);
        position: relative;
        overflow: hidden;
    }
    .pill:hover {
        background: rgba(56,189,248,0.10);
        border-color: rgba(56,189,248,0.30);
        color: var(--t3-cyan);
        transform: translateY(-1px);
        box-shadow: 0 3px 10px rgba(56,189,248,0.12);
    }

    /* ══════════════════════════════════
       JOB RESULT CARDS (iframed cards)
       ══════════════════════════════════ */
    .job-result-card {
        transition: transform 0.22s var(--t3-ease), box-shadow 0.22s var(--t3-ease) !important;
    }
    .job-result-card:hover {
        transform: translateY(-4px) !important;
        box-shadow: 0 14px 40px rgba(0,0,0,0.5) !important;
    }

    /* ── Apply button shimmer ── */
    .job-button::before {
        content: '';
        position: absolute;
        top: 0; left: -100%;
        width: 55%; height: 100%;
        background: linear-gradient(90deg, transparent, rgba(255,255,255,0.12), transparent);
        transition: left 0.45s ease;
        z-index: 1;
    }
    .job-button:hover::before { left: 150%; }
    .job-button:hover {
        transform: translateY(-2px);
        filter: brightness(1.1);
    }

    /* ══════════════════════════════════
       SAVED SEARCH CARDS
       ══════════════════════════════════ */
    .saved-search-card {
        background: var(--t3-surface);
        backdrop-filter: blur(20px);
        -webkit-backdrop-filter: blur(20px);
        border-radius: 14px;
        padding: 18px 20px;
        margin-bottom: 12px;
        border: 1px solid var(--t3-border);
        box-shadow: 0 4px 20px rgba(0,0,0,0.25);
        transition: all 0.22s var(--t3-ease);
        position: relative;
        overflow: hidden;
        font-family: var(--t3-font);
    }
    .saved-search-card:hover {
        border-color: var(--t3-border-acc);
        transform: translateX(3px);
        box-shadow: 0 6px 28px rgba(0,0,0,0.3);
    }

    /* ══════════════════════════════════
       ANALYTICS DASHBOARD HEADER
       ══════════════════════════════════ */
    .analytics-header {
        background: linear-gradient(160deg,
            rgba(14,20,32,0.95) 0%,
            rgba(8,12,18,0.98) 100%);
        backdrop-filter: blur(28px);
        -webkit-backdrop-filter: blur(28px);
        padding: 28px 32px 22px;
        border-radius: 20px;
        border: 1px solid rgba(56,189,248,0.14);
        margin-bottom: 24px;
        box-shadow: 0 12px 40px rgba(0,0,0,0.35);
        text-align: center;
        position: relative;
        overflow: hidden;
    }
    .analytics-header::before {
        content: '';
        position: absolute;
        top: -40%; left: -20%;
        width: 60%; height: 180%;
        background: radial-gradient(ellipse, rgba(56,189,248,0.06) 0%, transparent 70%);
        pointer-events: none;
    }
    .analytics-header h2 {
        font-family: var(--t3-font) !important;
        font-size: 1.5rem !important;
        font-weight: 800 !important;
        letter-spacing: -0.025em !important;
        background: linear-gradient(135deg, var(--t3-cyan) 0%, var(--t3-violet) 55%, var(--t3-rose) 100%);
        -webkit-background-clip: text !important;
        -webkit-text-fill-color: transparent !important;
        background-clip: text !important;
        margin: 0 !important;
    }
    .analytics-header p {
        color: var(--t3-muted) !important;
        font-size: 0.8rem !important;
        letter-spacing: 0.03em !important;
        margin: 6px 0 0 !important;
        font-family: var(--t3-font) !important;
    }

    /* ══════════════════════════════════
       KPI CARDS (analytics)
       ══════════════════════════════════ */
    .kpi-card {
        background: linear-gradient(145deg,
            rgba(14,20,32,0.90) 0%,
            rgba(20,28,43,0.95) 100%);
        border: 1px solid var(--t3-border);
        border-radius: 16px;
        padding: 20px 16px 18px;
        text-align: center;
        box-shadow: 0 4px 20px rgba(0,0,0,0.25), inset 0 1px 0 rgba(255,255,255,0.04);
        transition: all 0.24s var(--t3-ease);
        min-height: 110px;
        font-family: var(--t3-font);
    }
    .kpi-card:hover {
        transform: translateY(-4px);
        box-shadow: 0 12px 36px rgba(0,0,0,0.4);
        border-color: var(--t3-border-acc);
    }

    /* ══════════════════════════════════
       MARKET INSIGHT CARDS (skills/locations/salary)
       ══════════════════════════════════ */
    .insight-card {
        background: var(--t3-surface);
        backdrop-filter: blur(20px);
        -webkit-backdrop-filter: blur(20px);
        border: 1px solid var(--t3-border);
        border-radius: 14px;
        padding: 16px 18px;
        margin-bottom: 12px;
        transition: all 0.22s var(--t3-ease);
        position: relative;
        overflow: hidden;
    }
    .insight-card::before {
        content: '';
        position: absolute;
        left: 0; top: 0; bottom: 0;
        width: 3px;
        background: linear-gradient(180deg, var(--t3-cyan) 0%, var(--t3-violet) 100%);
        border-radius: 0 0 0 14px;
    }
    .insight-card:hover {
        border-color: var(--t3-border-acc);
        transform: translateX(4px);
        background: rgba(255,255,255,0.055);
    }
    .insight-card h4 {
        font-family: var(--t3-font) !important;
        font-size: 0.875rem !important;
        font-weight: 600 !important;
        margin: 0 0 6px !important;
        letter-spacing: -0.01em !important;
    }
    .insight-card p {
        font-family: var(--t3-font) !important;
        font-size: 0.8rem !important;
        margin: 0 !important;
        color: var(--t3-muted) !important;
    }

    /* ══════════════════════════════════
       EMPTY STATE PLACEHOLDERS
       ══════════════════════════════════ */
    .empty-state {
        background: var(--t3-surface);
        backdrop-filter: blur(16px);
        border: 1.5px dashed rgba(255,255,255,0.10);
        border-radius: 18px;
        padding: 48px 32px;
        text-align: center;
        color: var(--t3-muted);
        font-family: var(--t3-font);
        animation: t3-fadeUp 0.5s ease forwards;
    }
    .empty-state .icon { font-size: 2.5rem; margin-bottom: 14px; }
    .empty-state .title { font-size: 1rem; font-weight: 700; color: #94a3b8; margin-bottom: 6px; }
    .empty-state .sub   { font-size: 0.8rem; color: var(--t3-muted); }

    /* ══════════════════════════════════
       SECTION DIVIDER
       ══════════════════════════════════ */
    .t3-section-label {
        font-family: var(--t3-font) !important;
        font-size: 0.7rem !important;
        font-weight: 700 !important;
        letter-spacing: 0.12em !important;
        text-transform: uppercase !important;
        color: #334155 !important;
        border-bottom: 1px solid rgba(255,255,255,0.06) !important;
        padding-bottom: 8px !important;
        margin: 28px 0 16px !important;
    }

    /* ══════════════════════════════════
       ANALYTICS FOOTER
       ══════════════════════════════════ */
    .analytics-footer {
        color: #2d3748 !important;
        font-size: 0.7rem !important;
        text-align: right !important;
        margin-top: 14px !important;
        padding-top: 10px !important;
        border-top: 1px solid rgba(255,255,255,0.05) !important;
        font-family: var(--t3-font) !important;
        letter-spacing: 0.02em !important;
    }

    /* ══════════════════════════════════
       SCROLLBAR
       ══════════════════════════════════ */
    ::-webkit-scrollbar { width: 6px; height: 6px; }
    ::-webkit-scrollbar-track { background: rgba(255,255,255,0.02); }
    ::-webkit-scrollbar-thumb {
        background: rgba(56,189,248,0.3);
        border-radius: 99px;
    }
    ::-webkit-scrollbar-thumb:hover { background: rgba(56,189,248,0.55); }

    /* ══════════════════════════════════
       RESPONSIVE
       ══════════════════════════════════ */
    @media (max-width: 768px) {
        .company-card { padding: 18px; margin-bottom: 14px; }
        .t3-page-title { font-size: 1.5rem !important; }
        .company-header { font-size: 0.95rem; }
        .title-header { font-size: 1.1rem !important; }
    }

    /* ══════════════════════════════════
       FORM SUBMIT BUTTON STYLING
       ══════════════════════════════════ */

    /* Base flex layout for all form submit buttons */
    [data-testid="stForm"] button[kind="primaryFormSubmit"],
    [data-testid="stForm"] button[kind="secondaryFormSubmit"] {
        display: inline-flex !important;
        align-items: center !important;
        justify-content: center !important;
        gap: 8px !important;
        font-weight: 600 !important;
        letter-spacing: 0.02em !important;
    }

    /* Hide Streamlit's built-in ⊗ SVG so only our label emoji shows */
    [data-testid="stForm"] button[kind="primaryFormSubmit"] svg,
    [data-testid="stForm"] button[kind="secondaryFormSubmit"] svg {
        display: none !important;
    }
    </style>
    """, unsafe_allow_html=True)
# ← end of _inject_tab3_css()


# ═══════════════════════════════════════════════════════════════
# REUSABLE JOB CARD RENDERER
# ═══════════════════════════════════════════════════════════════

def render_job_card(title, link, platform_name, brand_color, platform_gradient, company=None, location=None, salary=None, description=None):
    """
    Reusable function to render a modern job card with consistent styling.

    Args:
        title: Job title or role
        link: Apply link URL
        platform_name: Name of the platform (LinkedIn, Naukri, etc.)
        brand_color: Platform brand color (hex)
        platform_gradient: CSS gradient for platform
        company: Company name (optional)
        location: Job location (optional)
        salary: Salary information (optional)
        description: Job description (optional)

    Returns:
        tuple: (html_string, estimated_height)
    """
    # Platform icon mapping — inline SVG
    icon_map = {
        "LinkedIn": '<svg xmlns="http://www.w3.org/2000/svg" width="20" height="20" viewBox="0 0 24 24" fill="#0A66C2"><path d="M20.447 20.452h-3.554v-5.569c0-1.328-.027-3.037-1.852-3.037-1.853 0-2.136 1.445-2.136 2.939v5.667H9.351V9h3.414v1.561h.046c.477-.9 1.637-1.85 3.37-1.85 3.601 0 4.267 2.37 4.267 5.455v6.286zM5.337 7.433a2.062 2.062 0 01-2.063-2.065 2.064 2.064 0 112.063 2.065zm1.782 13.019H3.555V9h3.564v11.452zM22.225 0H1.771C.792 0 0 .774 0 1.729v20.542C0 23.227.792 24 1.771 24h20.451C23.2 24 24 23.227 24 22.271V1.729C24 .774 23.2 0 22.222 0h.003z"/></svg>',
        "Naukri": '<svg xmlns="http://www.w3.org/2000/svg" width="20" height="20" viewBox="0 0 24 24" fill="#FF5722"><path d="M12 2C6.48 2 2 6.48 2 12s4.48 10 10 10 10-4.48 10-10S17.52 2 12 2zm-1 14H9V8h2v8zm4 0h-2V8h2v8z"/></svg>',
        "FoundIt (Monster)": '<svg xmlns="http://www.w3.org/2000/svg" width="20" height="20" viewBox="0 0 24 24" fill="#7C4DFF"><circle cx="12" cy="12" r="10"/><path fill="white" d="M12 6a6 6 0 100 12A6 6 0 0012 6zm0 2a4 4 0 110 8 4 4 0 010-8zm0 2a2 2 0 100 4 2 2 0 000-4z"/></svg>',
        "RapidAPI (Live)": '<svg xmlns="http://www.w3.org/2000/svg" width="20" height="20" viewBox="0 0 24 24" fill="#00FF88"><path d="M13 2L3 14h9l-1 8 10-12h-9l1-8z"/></svg>'
    }
    icon = icon_map.get(platform_name, '<svg xmlns="http://www.w3.org/2000/svg" width="20" height="20" viewBox="0 0 24 24" fill="#94a3b8"><path d="M14 2H6a2 2 0 00-2 2v16a2 2 0 002 2h12a2 2 0 002-2V8l-6-6zm-1 1.5L18.5 9H13V3.5zM6 20V4h5v7h7v9H6z"/></svg>')

    # Build metadata section and calculate height
    metadata_html = ""
    estimated_height = 180  # Base height (platform + title + button + padding)

    if company:
        metadata_html += f"""
        <div style="color: #aaaaaa; font-size: 14px; margin-bottom: 8px; z-index: 2; position: relative; display:flex; align-items:center; gap:6px;">
            <svg xmlns="http://www.w3.org/2000/svg" width="13" height="13" viewBox="0 0 24 24" fill="none" stroke="#888" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M3 9l9-7 9 7v11a2 2 0 01-2 2H5a2 2 0 01-2-2z"/><polyline points="9 22 9 12 15 12 15 22"/></svg>
            <b>{company}</b>
        </div>
        """
        estimated_height += 30

    if location:
        metadata_html += f"""
        <div style="color: #aaaaaa; font-size: 14px; margin-bottom: 8px; z-index: 2; position: relative; display:flex; align-items:center; gap:6px;">
            <svg xmlns="http://www.w3.org/2000/svg" width="13" height="13" viewBox="0 0 24 24" fill="none" stroke="#888" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><circle cx="12" cy="10" r="3"/><path d="M12 2a8 8 0 018 8c0 5.25-8 14-8 14S4 15.25 4 10a8 8 0 018-8z"/></svg>
            {location}
        </div>
        """
        estimated_height += 30

    if salary and salary not in ["Check site", "N/A - N/A "]:
        metadata_html += f"""
        <div style="color: #aaaaaa; font-size: 14px; margin-bottom: 8px; z-index: 2; position: relative; display:flex; align-items:center; gap:6px;">
            <svg xmlns="http://www.w3.org/2000/svg" width="13" height="13" viewBox="0 0 24 24" fill="none" stroke="#888" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><line x1="12" y1="1" x2="12" y2="23"/><path d="M17 5H9.5a3.5 3.5 0 000 7h5a3.5 3.5 0 010 7H6"/></svg>
            {salary}
        </div>
        """
        estimated_height += 30

    if description and description != "Open this platform to view full details.":
        # Estimate height based on description length
        desc_lines = len(description) // 60 + 1
        estimated_height += (desc_lines * 22) + 15
        metadata_html += f"""
        <div style="color: #999999; font-size: 14px; margin-bottom: 15px; line-height: 1.6; z-index: 2; position: relative;">
            {description}
        </div>
        """

    # Create the job card HTML
    job_card_html = f"""
<!DOCTYPE html>
<html>
<head>
<style>
    * {{
        margin: 0;
        padding: 0;
        box-sizing: border-box;
    }}
    body {{
        background: transparent;
        font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;
    }}
    @keyframes shimmer {{
        0% {{ transform: translateX(-100%); }}
        100% {{ transform: translateX(100%); }}
    }}
    .shimmer-overlay {{
        position: absolute;
        top: 0;
        left: 0;
        width: 100%;
        height: 100%;
        background: linear-gradient(90deg, transparent, rgba(255,255,255,0.05), transparent);
        transform: translateX(-100%);
        animation: shimmer 3s infinite;
        z-index: 1;
    }}
    .job-result-card {{
        background: linear-gradient(135deg, #1e1e1e 0%, #2d2d2d 100%);
        padding: 22px;
        border-radius: 20px;
        border-left: 6px solid {brand_color};
        box-shadow: 0 8px 32px rgba(0,0,0,0.3), 0 0 20px {brand_color}40;
        position: relative;
        overflow: hidden;
        transition: all 0.4s cubic-bezier(0.175, 0.885, 0.32, 1.275);
    }}
    .job-result-card:hover {{
        transform: translateY(-3px);
        box-shadow: 0 12px 40px rgba(0,0,0,0.4), 0 0 30px {brand_color}60;
    }}
    .job-button {{
        background: {platform_gradient};
        color: white;
        padding: 12px 20px;
        border: none;
        border-radius: 12px;
        font-size: 16px;
        font-weight: bold;
        cursor: pointer;
        box-shadow: 0 4px 15px {brand_color}50;
        transition: all 0.3s ease;
        position: relative;
        overflow: hidden;
        text-decoration: none;
        display: inline-block;
    }}
    .job-button:hover {{
        transform: translateY(-2px);
        box-shadow: 0 6px 20px {brand_color}70;
    }}
</style>
</head>
<body>
<div class="job-result-card">
    <div class="shimmer-overlay"></div>

    <!-- Platform Badge -->
    <div style="display:flex; align-items:center; gap:8px; margin-bottom: 12px; z-index: 2; position: relative; font-weight: bold; color: {brand_color}; font-size:15px;">
        {icon} {platform_name}
    </div>

    <!-- Job Title -->
    <div style="color: #ffffff; font-size: 18px; margin-bottom: 12px; font-weight: bold; z-index: 2; position: relative; line-height: 1.4;">
        {title}
    </div>

    <!-- Metadata (company, location, salary, description) -->
    {metadata_html}

    <!-- Apply Button -->
    <a href="{link}" target="_blank" style="text-decoration: none; z-index: 2; position: relative;">
        <button class="job-button">
            <span style="position: relative; z-index: 2; display:flex; align-items:center; gap:6px;"><svg xmlns="http://www.w3.org/2000/svg" width="15" height="15" viewBox="0 0 24 24" fill="none" stroke="white" stroke-width="2.5" stroke-linecap="round" stroke-linejoin="round"><line x1="5" y1="12" x2="19" y2="12"/><polyline points="12 5 19 12 12 19"/></svg> Apply Now</span>
        </button>
    </a>
</div>
</body>
</html>
"""
    return job_card_html, estimated_height


# ═══════════════════════════════════════════════════════════════
# MAIN JOB SEARCH INTERACTIVE FRAGMENT
# ═══════════════════════════════════════════════════════════════

@st.fragment
def _job_search_interactive():
    st.markdown("""
    <div class="t3-page-header">
        <div class="t3-page-title">Job <span>Search Hub</span></div>
        <div class="t3-page-sub">Find your next opportunity across live listings, LinkedIn, Naukri, and more</div>
    </div>
    """, unsafe_allow_html=True)

    # Initialize session state for search mode
    if 'search_mode' not in st.session_state:
        st.session_state.search_mode = "LinkedIn Scraper"

    is_external = st.session_state.search_mode == "LinkedIn Scraper"

    badge_color  = "linear-gradient(135deg,#2196F3,#1565C0)" if is_external else "linear-gradient(135deg,#00E676,#00A550)"
    badge_tcolor = "#ffffff" if is_external else "#002a18"
    badge_text_ext  = '<svg xmlns="http://www.w3.org/2000/svg" width="13" height="13" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" style="display:inline;vertical-align:middle;"><circle cx="12" cy="12" r="10"/><line x1="2" y1="12" x2="22" y2="12"/><path d="M12 2a15.3 15.3 0 014 10 15.3 15.3 0 01-4 10 15.3 15.3 0 01-4-10 15.3 15.3 0 014-10z"/></svg>  LinkedIn Scraper Mode Active'
    badge_text_rap  = '<svg xmlns="http://www.w3.org/2000/svg" width="13" height="13" viewBox="0 0 24 24" fill="currentColor" style="display:inline;vertical-align:middle;"><path d="M13 2L3 14h9l-1 8 10-12h-9l1-8z"/></svg>  RapidAPI Jobs Mode Active'
    badge_text = badge_text_ext if is_external else badge_text_rap

    ext_bg      = "linear-gradient(135deg,#2196F3,#1565C0)" if is_external     else "rgba(35,35,35,0.95)"
    rapid_bg    = "linear-gradient(135deg,#00E676,#00A550)"  if not is_external else "rgba(35,35,35,0.95)"
    ext_color   = "#ffffff"  if is_external     else "rgba(255,255,255,0.45)"
    rapid_color = "#002a18"  if not is_external else "rgba(255,255,255,0.45)"
    ext_shadow  = "0 4px 20px rgba(33,150,243,0.5)"  if is_external     else "none"
    rapid_shadow= "0 4px 20px rgba(0,200,100,0.45)"  if not is_external else "none"

    # ── Badge first ──
    badge_bg = "linear-gradient(135deg,rgba(56,189,248,0.18) 0%,rgba(79,163,227,0.10) 100%)" if is_external else "linear-gradient(135deg,rgba(52,211,153,0.18) 0%,rgba(52,211,153,0.08) 100%)"
    badge_border = "rgba(56,189,248,0.30)" if is_external else "rgba(52,211,153,0.28)"
    badge_col = "#7dd3fc" if is_external else "#6ee7b7"

    st.markdown(f"""
    <div class="mode-badge-wrap">
        <span class="mode-badge" style="background:{badge_bg};border-color:{badge_border};color:{badge_col};">
            {badge_text}
        </span>
    </div>
    """, unsafe_allow_html=True)

    # ── Pill toggle: components.html renders the styled visual AND handles clicks ──
    # On click it calls window.parent.postMessage. A companion <script> injected by
    # components.html itself (same iframe) fires the message, and we catch it via
    # a polling mechanism that sets sessionStorage, which a Streamlit button re-checks.
    # SIMPLEST working pattern: put both visual div AND a real <button> inside the iframe;
    # clicking the styled div triggers a form submit that postMessages to parent.
    # Parent catches it → clicks the relevant hidden real Streamlit button.
    #
    # BUT: st.markdown strips <script>. So instead we use components.html for EVERYTHING:
    # visual pill + JS that directly clicks Streamlit buttons in the parent DOM.
    # This works because components.html uses allow-same-origin in its sandbox.

    components.html(f"""<!DOCTYPE html>
<html>
<head>
<style>
  *{{margin:0;padding:0;box-sizing:border-box;}}
  body{{background:transparent;font-family:-apple-system,BlinkMacSystemFont,'Segoe UI',Roboto,sans-serif;padding:2px 0 6px;}}
  .toggle{{display:flex;justify-content:center;}}
  .btn{{
    width:260px;padding:15px 10px;font-size:15px;font-weight:700;
    letter-spacing:.3px;border:1px solid rgba(255,255,255,0.13);
    display:flex;align-items:center;justify-content:center;gap:9px;
    cursor:pointer;user-select:none;transition:filter .18s ease;
  }}
  .btn:hover{{filter:brightness(1.14);}}
  .btn-left{{border-radius:50px 0 0 50px;border-right:none;
    background:{ext_bg};color:{ext_color};box-shadow:{ext_shadow};}}
  .btn-right{{border-radius:0 50px 50px 0;border-left:none;
    background:{rapid_bg};color:{rapid_color};box-shadow:{rapid_shadow};}}
  .dot{{width:12px;height:12px;border-radius:50%;border:2px solid currentColor;flex-shrink:0;}}
  .active .dot{{background:currentColor;}}
</style>
</head>
<body>
  <div class="toggle">
    <div class="btn btn-left {'active' if is_external else ''}" id="btn-ext">
      <span class="dot"></span><span><svg xmlns="http://www.w3.org/2000/svg" width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" style="vertical-align:middle;margin-right:4px;"><circle cx="12" cy="12" r="10"/><line x1="2" y1="12" x2="22" y2="12"/><path d="M12 2a15.3 15.3 0 014 10 15.3 15.3 0 01-4 10 15.3 15.3 0 01-4-10 15.3 15.3 0 014-10z"/></svg> LinkedIn Scraper</span>
    </div>
    <div class="btn btn-right {'active' if not is_external else ''}" id="btn-rapid">
      <span class="dot"></span><span><svg xmlns="http://www.w3.org/2000/svg" width="14" height="14" viewBox="0 0 24 24" fill="currentColor" style="vertical-align:middle;margin-right:4px;"><path d="M13 2L3 14h9l-1 8 10-12h-9l1-8z"/></svg> RapidAPI Jobs</span>
    </div>
  </div>
  <script>
    function clickParentButton(labelFragment) {{
      // Walk the parent document for Streamlit buttons matching the label
      var parentDoc = window.parent.document;
      var buttons = parentDoc.querySelectorAll('button');
      for (var i = 0; i < buttons.length; i++) {{
        if (buttons[i].innerText && buttons[i].innerText.indexOf(labelFragment) !== -1) {{
          buttons[i].click();
          return;
        }}
      }}
    }}
    document.getElementById('btn-ext').addEventListener('click', function() {{
      clickParentButton('LinkedIn Scraper Mode');
    }});
    document.getElementById('btn-rapid').addEventListener('click', function() {{
      clickParentButton('RapidAPI Jobs Mode');
    }});
  </script>
</body>
</html>""", height=65)

    # ── The real Streamlit buttons — styled small but visible and always functional ──
    # components.html JS clicks these; user can also click them directly as fallback.
    col_l, col_r = st.columns(2)
    with col_l:
        if st.button("LinkedIn Scraper Mode", key="btn_mode_external", use_container_width=True):
            if st.session_state.search_mode != "LinkedIn Scraper":
                st.session_state.rapid_role_val = None
                st.session_state.rapid_loc_val  = None
            st.session_state.search_mode = "LinkedIn Scraper"
            st.rerun(scope="fragment")
    with col_r:
        if st.button("RapidAPI Jobs Mode", key="btn_mode_rapid", use_container_width=True):
            if st.session_state.search_mode != "RapidAPI Jobs":
                st.session_state.ext_role_val    = None
                st.session_state.ext_loc_val     = None
                st.session_state.ext_exp_val     = ""
                st.session_state.ext_type_val    = ""
                st.session_state.ext_foundit_val = ""
                st.session_state["_ext_clear_count"] = st.session_state.get("_ext_clear_count", 0) + 1
            st.session_state.search_mode = "RapidAPI Jobs"
            st.rerun(scope="fragment")

    st.markdown("<div style='margin-top:10px'></div>", unsafe_allow_html=True)
    search_mode = st.session_state.search_mode

    if search_mode == "LinkedIn Scraper":
        # Shadow keys for clear — never set widget keys directly
        if "ext_role_val" not in st.session_state:
            st.session_state.ext_role_val = None
        if "ext_loc_val" not in st.session_state:
            st.session_state.ext_loc_val = None
        if "_ext_clear_count" not in st.session_state:
            st.session_state["_ext_clear_count"] = 0

        # Compute index from shadow values
        _ext_role_idx  = JOB_TITLES.index(st.session_state.ext_role_val) if st.session_state.ext_role_val in JOB_TITLES else None
        _ext_loc_idx   = LOCATIONS.index(st.session_state.ext_loc_val)   if st.session_state.ext_loc_val  in LOCATIONS  else None
        _ext_c = st.session_state["_ext_clear_count"]

        with st.expander("LinkedIn Scraper — Live Job Listings", expanded=True):
            with st.form(f"external_search_form_{_ext_c}", clear_on_submit=False):
                st.markdown("""<label style="font-size:0.82rem;font-weight:600;color:#94a3b8;display:flex;align-items:center;gap:6px;margin-bottom:2px;"><svg xmlns="http://www.w3.org/2000/svg" width="13" height="13" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><rect x="2" y="7" width="20" height="14" rx="2"/><path d="M16 21V5a2 2 0 00-2-2h-4a2 2 0 00-2 2v16"/></svg> JOB DOMAIN</label>""", unsafe_allow_html=True)
                job_role = st.selectbox(
                    "Job Domain",
                    JOB_TITLES,
                    index=_ext_role_idx,
                    placeholder="Select Job Domain",
                    key=f"external_role_{_ext_c}",
                    label_visibility="collapsed"
                )

                st.markdown("""<label style="font-size:0.82rem;font-weight:600;color:#94a3b8;display:flex;align-items:center;gap:6px;margin-bottom:2px;"><svg xmlns="http://www.w3.org/2000/svg" width="13" height="13" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><circle cx="12" cy="10" r="3"/><path d="M12 2a8 8 0 018 8c0 5.25-8 14-8 14S4 15.25 4 10a8 8 0 018-8z"/></svg> LOCATION</label>""", unsafe_allow_html=True)
                location = st.selectbox(
                    "Location",
                    LOCATIONS,
                    index=_ext_loc_idx,
                    placeholder="Select Location",
                    key=f"external_location_{_ext_c}",
                    label_visibility="collapsed"
                )

                col1, col2 = st.columns(2)
                with col1:
                    st.markdown("""<label style="font-size:0.82rem;font-weight:600;color:#94a3b8;display:flex;align-items:center;gap:6px;margin-bottom:2px;"><svg xmlns="http://www.w3.org/2000/svg" width="13" height="13" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><rect x="3" y="4" width="18" height="16" rx="2"/><line x1="16" y1="2" x2="16" y2="6"/><line x1="8" y1="2" x2="8" y2="6"/><line x1="3" y1="10" x2="21" y2="10"/></svg> DATE POSTED</label>""", unsafe_allow_html=True)
                    time_frame = st.selectbox(
                        "Date Posted",
                        ["24h", "7d", "30d"],
                        key=f"external_timeframe_{_ext_c}",
                        label_visibility="collapsed"
                    )
                with col2:
                    st.markdown("""<label style="font-size:0.82rem;font-weight:600;color:#94a3b8;display:flex;align-items:center;gap:6px;margin-bottom:2px;">NUMBER OF JOBS</label>""", unsafe_allow_html=True)
                    num_results = st.slider(
                        "Number of Jobs",
                        min_value=1, max_value=5, value=3, step=1,
                        key=f"external_numresults_{_ext_c}",
                        label_visibility="collapsed"
                    )

                col_btn1, col_spacer, col_btn2 = st.columns([3, 0.4, 3])
                with col_btn1:
                    search_clicked = st.form_submit_button("🔍  Search Jobs", use_container_width=True)
                with col_btn2:
                    clear_clicked = st.form_submit_button("✕  Clear Form", use_container_width=True)

        # Handle clear — reset shadow keys + bump clear counter to re-render widgets fresh
        if clear_clicked:
            st.session_state.ext_role_val = None
            st.session_state.ext_loc_val  = None
            st.session_state["_ext_clear_count"] = st.session_state.get("_ext_clear_count", 0) + 1
            st.rerun(scope="fragment")

        # Sync shadow keys from widget values on search
        if search_clicked:
            st.session_state.ext_role_val = job_role
            st.session_state.ext_loc_val  = location

        if search_clicked and not job_role:
            st.warning("Please select a Job Domain to search.")
        elif search_clicked and not location:
            st.warning("Please select a Location to search.")

        if search_clicked and job_role and location:
            with st.spinner("Fetching live jobs from LinkedIn..."):
                results = fetch_linkedin_jobs(
                    job_role,
                    location,
                    time_frame=time_frame,
                    results=num_results
                )

            # Save search results if user is logged in
            if hasattr(st.session_state, 'username') and st.session_state.username:
                formatted_results = []
                for job in results:
                    formatted_results.append({
                        "platform": "LinkedIn (Live)",
                        "apply_link": job.get("job_apply_link", "#"),
                        "company":    clean_html(job.get("employer_name", "")),
                    })
                # If LinkedIn returned 0 jobs (quota/network/no matches), still
                # insert 1 placeholder row so the search count always increases —
                # same pattern as RapidAPI mode.
                if not formatted_results:
                    formatted_results = [{
                        "platform": "LinkedIn (Live)",
                        "apply_link": "#",
                        "company": "",
                    }]
                _session_id = str(uuid.uuid4())  # one UUID per search click
                save_job_search(
                    st.session_state.username,
                    job_role,
                    location,
                    formatted_results,
                    _session_id
                )
                st.session_state["_search_just_saved"] = True

            st.markdown("""<div style="display:flex; align-items:center; gap:10px; margin:18px 0 14px;"><svg xmlns="http://www.w3.org/2000/svg" width="22" height="22" viewBox="0 0 24 24" fill="none" stroke="url(#gext)" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><defs><linearGradient id="gext" x1="0%" y1="0%" x2="100%" y2="100%"><stop offset="0%" stop-color="#38bdf8"/><stop offset="100%" stop-color="#818cf8"/></linearGradient></defs><circle cx="11" cy="11" r="8"/><line x1="21" y1="21" x2="16.65" y2="16.65"/></svg><span style="font-size:1.35rem; font-weight:800; letter-spacing:-0.025em; background:linear-gradient(135deg,#38bdf8,#818cf8); -webkit-background-clip:text; -webkit-text-fill-color:transparent; background-clip:text; font-family:var(--t3-font);">LinkedIn Job Results</span></div>""", unsafe_allow_html=True)

            if results:
                for job in results:
                    job_title = clean_html(job.get("job_title", "N/A"))
                    job_company = clean_html(job.get("employer_name", "Unknown"))
                    job_location = f"{job.get('job_city','')}, {job.get('job_country','')}"
                    job_type_disp = job.get("job_employment_type", "N/A")
                    job_mode = "Remote" if job.get("job_is_remote") else "On-site"
                    job_publisher = clean_html(job.get("job_publisher", "LinkedIn"))
                    _raw_desc = job.get("job_description") or ""
                    job_description = clean_html(_raw_desc).strip()
                    _desc_missing = len(job_description) < 10
                    if not _desc_missing and len(job_description) > 350:
                        job_description = job_description[:350].rsplit(' ', 1)[0] + "..."

                    raw_date = job.get("job_posted_at_datetime_utc", "")
                    formatted_date = "N/A"
                    if raw_date and str(raw_date).strip() not in ("N/A", "None", "null", ""):
                        try:
                            date_obj = datetime.fromisoformat(str(raw_date).replace("Z", "+00:00"))
                            formatted_date = date_obj.strftime("%b %d, %Y")
                        except (ValueError, AttributeError):
                            formatted_date = str(raw_date)[:10]

                    btn_color = "#0e76a8"
                    platform_gradient = "linear-gradient(135deg, #0e76a8 0%, #1a8cc8 100%)"

                    job_card_html = f"""
<div class="job-result-card" style="
    background: linear-gradient(135deg, #1e1e1e 0%, #2d2d2d 100%);
    padding: 25px;
    border-radius: 20px;
    margin-bottom: 25px;
    border-left: 6px solid {btn_color};
    box-shadow: 0 8px 32px rgba(0,0,0,0.3), 0 0 20px {btn_color}40;
    position: relative;
    overflow: hidden;
    transition: all 0.4s cubic-bezier(0.175, 0.885, 0.32, 1.275);
">
    <div class="shimmer-overlay"></div>

    <div style="display:flex; align-items:center; gap:8px; font-size: 15px; margin-bottom: 15px; color: {btn_color}; font-weight: bold;">
        <svg xmlns="http://www.w3.org/2000/svg" width="18" height="18" viewBox="0 0 24 24" fill="{btn_color}"><path d="M13 2L3 14h9l-1 8 10-12h-9l1-8z"/></svg> LinkedIn (Live)
    </div>

    <div style="color: #ffffff; font-size: 22px; margin-bottom: 10px; font-weight: 600; line-height: 1.4;">
        {job_title}
    </div>

    <div style="color: #aaaaaa; font-size: 16px; margin-bottom: 15px; display:flex; align-items:center; gap:6px;">
        <svg xmlns="http://www.w3.org/2000/svg" width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="#888" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M3 9l9-7 9 7v11a2 2 0 01-2 2H5a2 2 0 01-2-2z"/><polyline points="9 22 9 12 15 12 15 22"/></svg>
        <b>{job_company}</b>
    </div>

    <div style="display: grid; grid-template-columns: repeat(2, 1fr); gap: 10px; margin-bottom: 15px;">
        <div style="color: #cccccc; font-size: 14px; display:flex; align-items:center; gap:5px;"><svg xmlns="http://www.w3.org/2000/svg" width="13" height="13" viewBox="0 0 24 24" fill="none" stroke="#94a3b8" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><circle cx="12" cy="10" r="3"/><path d="M12 2a8 8 0 018 8c0 5.25-8 14-8 14S4 15.25 4 10a8 8 0 018-8z"/></svg> <b>Location:</b> {job_location}</div>
        <div style="color: #cccccc; font-size: 14px; display:flex; align-items:center; gap:5px;"><svg xmlns="http://www.w3.org/2000/svg" width="13" height="13" viewBox="0 0 24 24" fill="none" stroke="#94a3b8" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><rect x="2" y="7" width="20" height="14" rx="2"/><path d="M16 21V5a2 2 0 00-2-2h-4a2 2 0 00-2 2v16"/></svg> <b>Type:</b> {job_type_disp}</div>
        <div style="color: #cccccc; font-size: 14px; display:flex; align-items:center; gap:5px;"><svg xmlns="http://www.w3.org/2000/svg" width="13" height="13" viewBox="0 0 24 24" fill="none" stroke="#94a3b8" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><circle cx="12" cy="12" r="10"/><line x1="2" y1="12" x2="22" y2="12"/><path d="M12 2a15.3 15.3 0 014 10 15.3 15.3 0 01-4 10 15.3 15.3 0 01-4-10 15.3 15.3 0 014-10z"/></svg> <b>Mode:</b> {job_mode}</div>
        <div style="color: #cccccc; font-size: 14px; display:flex; align-items:center; gap:5px;"><svg xmlns="http://www.w3.org/2000/svg" width="13" height="13" viewBox="0 0 24 24" fill="none" stroke="#94a3b8" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><rect x="3" y="4" width="18" height="18" rx="2"/><line x1="16" y1="2" x2="16" y2="6"/><line x1="8" y1="2" x2="8" y2="6"/><line x1="3" y1="10" x2="21" y2="10"/></svg> <b>Posted:</b> {formatted_date}</div>
    </div>

    {(
        f'''<div style="color:#999;font-size:14px;margin-bottom:20px;line-height:1.6;">{job_description}</div>'''
        if not _desc_missing else
        f'''<a href="{job.get("job_apply_link","#")}" target="_blank" style="text-decoration:none;display:inline-flex;align-items:center;gap:10px;
            background:linear-gradient(135deg,rgba(14,118,168,0.08),rgba(14,118,168,0.03));
            border:1px dashed rgba(14,118,168,0.35);border-radius:12px;
            padding:12px 18px;margin-bottom:20px;cursor:pointer;
            transition:all 0.25s ease;width:fit-content;">
            <svg xmlns="http://www.w3.org/2000/svg" width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="{btn_color}" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><circle cx="12" cy="12" r="10"/><line x1="12" y1="8" x2="12" y2="12"/><line x1="12" y1="16" x2="12.01" y2="16"/></svg>
            <span style="color:#aaa;font-size:13px;">Description not available in preview —</span>
            <span style="color:{btn_color};font-size:13px;font-weight:600;display:flex;align-items:center;gap:5px;">
                View full details on LinkedIn
                <svg xmlns="http://www.w3.org/2000/svg" width="13" height="13" viewBox="0 0 24 24" fill="none" stroke="{btn_color}" stroke-width="2.5" stroke-linecap="round" stroke-linejoin="round"><path d="M18 13v6a2 2 0 01-2 2H5a2 2 0 01-2-2V8a2 2 0 012-2h6"/><polyline points="15 3 21 3 21 9"/><line x1="10" y1="14" x2="21" y2="3"/></svg>
            </span>
        </a>'''
    )}

    <a href="{job.get('job_apply_link', '#')}" target="_blank" style="text-decoration: none;">
        <button class="job-button" style="
            background: {platform_gradient};
            color: white; border: none; padding: 12px 24px;
            border-radius: 10px; font-weight: 600; font-size: 14px;
            cursor: pointer; width: 100%;
        ">Apply on LinkedIn</button>
    </a>
</div>
"""
                    st.markdown(job_card_html, unsafe_allow_html=True)
            else:
                st.info("No live LinkedIn listings found for this search. Try a different role, location, or date range.")

    else:
        # Shadow keys for RapidAPI clear
        if "rapid_role_val" not in st.session_state:
            st.session_state.rapid_role_val = None
        if "rapid_loc_val" not in st.session_state:
            st.session_state.rapid_loc_val = None
        if "_rapid_clear_count" not in st.session_state:
            st.session_state["_rapid_clear_count"] = 0

        _rapid_role_idx = JOB_TITLES.index(st.session_state.rapid_role_val) if st.session_state.rapid_role_val in JOB_TITLES else None
        _rapid_loc_idx  = LOCATIONS.index(st.session_state.rapid_loc_val)   if st.session_state.rapid_loc_val  in LOCATIONS  else None
        _rapid_c = st.session_state["_rapid_clear_count"]

        # RapidAPI Jobs Section — collapsible expander
        with st.expander("RapidAPI Live Job Search", expanded=True):
            with st.form(f"rapid_search_form_{_rapid_c}", clear_on_submit=False):
                st.markdown("""<label style="font-size:0.82rem;font-weight:600;color:#94a3b8;display:flex;align-items:center;gap:6px;margin-bottom:2px;"><svg xmlns="http://www.w3.org/2000/svg" width="13" height="13" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><rect x="2" y="7" width="20" height="14" rx="2"/><path d="M16 21V5a2 2 0 00-2-2h-4a2 2 0 00-2 2v16"/></svg> JOB DOMAIN</label>""", unsafe_allow_html=True)
                rapid_job_role = st.selectbox(
                    "Job Domain",
                    JOB_TITLES,
                    index=_rapid_role_idx,
                    placeholder="Select Job Domain",
                    key=f"rapid_role_{_rapid_c}",
                    label_visibility="collapsed"
                )

                st.markdown("""<label style="font-size:0.82rem;font-weight:600;color:#94a3b8;display:flex;align-items:center;gap:6px;margin-bottom:2px;"><svg xmlns="http://www.w3.org/2000/svg" width="13" height="13" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><circle cx="12" cy="10" r="3"/><path d="M12 2a8 8 0 018 8c0 5.25-8 14-8 14S4 15.25 4 10a8 8 0 018-8z"/></svg> LOCATION</label>""", unsafe_allow_html=True)
                rapid_location = st.selectbox(
                    "Location",
                    LOCATIONS,
                    index=_rapid_loc_idx,
                    placeholder="Select Location",
                    key=f"rapid_location_{_rapid_c}",
                    label_visibility="collapsed"
                )

                # Number of results
                st.markdown("""<label style="font-size:0.82rem;font-weight:600;color:#94a3b8;display:flex;align-items:center;gap:6px;margin-bottom:2px;"><svg xmlns="http://www.w3.org/2000/svg" width="13" height="13" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><line x1="18" y1="20" x2="18" y2="10"/><line x1="12" y1="20" x2="12" y2="4"/><line x1="6" y1="20" x2="6" y2="14"/></svg> NUMBER OF JOBS TO FETCH</label>""", unsafe_allow_html=True)
                num_results = st.slider("Number of Jobs to Fetch", min_value=1, max_value=5, value=3, step=1, key="rapid_num_results", label_visibility="collapsed")

                # Advanced Filters
                with st.expander("Advanced Filters"):
                    st.markdown("""<label style="font-size:0.82rem;font-weight:600;color:#94a3b8;display:flex;align-items:center;gap:6px;margin-bottom:2px;"><svg xmlns="http://www.w3.org/2000/svg" width="13" height="13" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><rect x="3" y="4" width="18" height="16" rx="2"/><line x1="16" y1="2" x2="16" y2="6"/><line x1="8" y1="2" x2="8" y2="6"/><line x1="3" y1="10" x2="21" y2="10"/></svg> DATE POSTED</label>""", unsafe_allow_html=True)
                    date_posted = st.selectbox(
                        "Date Posted",
                        ["all", "today", "3days", "week", "month"],
                        key="rapid_date",
                        label_visibility="collapsed"
                    )
                    st.markdown("""<label style="font-size:0.82rem;font-weight:600;color:#94a3b8;display:flex;align-items:center;gap:6px;margin-bottom:2px;"><svg xmlns="http://www.w3.org/2000/svg" width="13" height="13" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M14 2H6a2 2 0 00-2 2v16a2 2 0 002 2h12a2 2 0 002-2V8z"/><polyline points="14 2 14 8 20 8"/><line x1="16" y1="13" x2="8" y2="13"/><line x1="16" y1="17" x2="8" y2="17"/></svg> JOB TYPE</label>""", unsafe_allow_html=True)
                    rapid_job_type = st.selectbox(
                        "Job Type",
                        ["", "Full-time", "Part-time", "Contract", "Internship"],
                        key="rapid_type",
                        label_visibility="collapsed"
                    )
                    remote_only = st.checkbox("Remote Only", key="rapid_remote")
                    st.markdown("""<label style="font-size:0.82rem;font-weight:600;color:#94a3b8;display:flex;align-items:center;gap:6px;margin-bottom:2px;"><svg xmlns="http://www.w3.org/2000/svg" width="13" height="13" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><circle cx="12" cy="12" r="10"/><line x1="2" y1="12" x2="22" y2="12"/><path d="M12 2a15.3 15.3 0 014 10 15.3 15.3 0 01-4 10 15.3 15.3 0 01-4-10 15.3 15.3 0 014-10z"/></svg> Radius (km)</label>""", unsafe_allow_html=True)
                    radius = st.number_input("Radius (km)", min_value=0, max_value=200, value=50, key="rapid_radius", label_visibility="collapsed")
                    st.markdown("""<label style="font-size:0.82rem;font-weight:600;color:#94a3b8;display:flex;align-items:center;gap:6px;margin-bottom:2px;"><svg xmlns="http://www.w3.org/2000/svg" width="13" height="13" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M9 11l3 3L22 4"/><path d="M21 12v7a2 2 0 01-2 2H5a2 2 0 01-2-2V5a2 2 0 012-2h11"/></svg> Job Requirements</label>""", unsafe_allow_html=True)
                    job_requirements = st.multiselect(
                        "Job Requirements",
                        ["under_3_years_experience", "more_than_3_years_experience", "no_experience", "no_degree"],
                        key="rapid_req",
                        label_visibility="collapsed"
                    )

                col_btn1, col_spacer, col_btn2 = st.columns([3, 0.4, 3])
                with col_btn1:
                    rapid_search_clicked = st.form_submit_button("🔍  Search Live Jobs", use_container_width=True)
                with col_btn2:
                    rapid_clear_clicked = st.form_submit_button("✕  Clear Form", use_container_width=True)

        # Handle clear — reset shadow keys + bump clear counter to re-render widgets fresh
        if rapid_clear_clicked:
            st.session_state.rapid_role_val = None
            st.session_state.rapid_loc_val  = None
            st.session_state["_rapid_clear_count"] = st.session_state.get("_rapid_clear_count", 0) + 1
            st.rerun(scope="fragment")

        # Sync shadow keys on search
        if rapid_search_clicked:
            st.session_state.rapid_role_val = rapid_job_role
            st.session_state.rapid_loc_val  = rapid_location

        if rapid_search_clicked and not rapid_job_role:
            st.warning("Please select a Job Domain to search.")
        elif rapid_search_clicked and not rapid_location:
            st.warning("Please select a Location to search.")

        if rapid_search_clicked and rapid_job_role and rapid_location:
            with st.spinner("Fetching live jobs from RapidAPI..."):
                results = fetch_live_jobs(
                    rapid_job_role,
                    rapid_location,
                    job_type=rapid_job_type if rapid_job_type else None,
                    remote_only=remote_only,
                    results=num_results
                )

            # Save search results if user is logged in
            if hasattr(st.session_state, 'username') and st.session_state.username:
                formatted_results = []
                for job in results:
                    formatted_results.append({
                        "platform": "RapidAPI (Live)",
                        "apply_link": job.get("job_apply_link", "#"),
                        "company":    clean_html(job.get("employer_name", "")),
                    })
                # If RapidAPI returned 0 jobs (quota/network/no matches), still
                # insert 1 placeholder row so the search count always increases.
                if not formatted_results:
                    formatted_results = [{
                        "platform": "RapidAPI (Live)",
                        "apply_link": "#",
                        "company": "",
                    }]
                _session_id = str(uuid.uuid4())  # one UUID per search click
                save_job_search(
                    st.session_state.username,
                    rapid_job_role,
                    rapid_location,
                    formatted_results,
                    _session_id
                )
                # NOTE: prune_old_searches intentionally NOT called here.
                # Pruning was hard-capping row count at 50 — every new insert
                # was immediately deleted back to the limit, freezing the count.
                # Signal pagination to reset to page 1 so stale offset never
                # causes a row to be skipped or duplicated in Saved Searches.
                st.session_state["_search_just_saved"] = True

            st.markdown("""<div style="display:flex; align-items:center; gap:10px; margin:18px 0 14px;"><svg xmlns="http://www.w3.org/2000/svg" width="22" height="22" viewBox="0 0 24 24" fill="none" stroke="url(#grap)" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><defs><linearGradient id="grap" x1="0%" y1="0%" x2="100%" y2="100%"><stop offset="0%" stop-color="#34d399"/><stop offset="100%" stop-color="#38bdf8"/></linearGradient></defs><path d="M13 2L3 14h9l-1 8 10-12h-9l1-8z"/></svg><span style="font-size:1.35rem; font-weight:800; letter-spacing:-0.025em; background:linear-gradient(135deg,#34d399,#38bdf8); -webkit-background-clip:text; -webkit-text-fill-color:transparent; background-clip:text; font-family:var(--t3-font);">RapidAPI Job Results</span></div>""", unsafe_allow_html=True)


            if results:
                for job in results:
                    # Clean all job fields
                    job_title = clean_html(job.get("job_title", "N/A"))
                    job_company = clean_html(job.get("employer_name", "Unknown"))
                    job_location = f"{job.get('job_city','')}, {job.get('job_country','')}"
                    job_salary = f"{job.get('job_min_salary','None')} - {job.get('job_max_salary','None')} {job.get('job_salary_currency','')}"
                    job_type = job.get("job_employment_type", "N/A")
                    job_mode = "Remote" if job.get("job_is_remote") else "On-site"
                    job_publisher = clean_html(job.get("job_publisher", "N/A"))
                    # --- Description: robust fallback, never shows bare "..." ---
                    _highlights = job.get("job_highlights") or {}
                    _raw_desc = (
                        job.get("job_description")
                        or " ".join(_highlights.get("Qualifications", []))
                        or " ".join(_highlights.get("Responsibilities", []))
                        or " ".join(_highlights.get("Benefits", []))
                        or ""
                    )
                    job_description = clean_html(_raw_desc).strip()
                    _desc_missing = len(job_description) < 10
                    if not _desc_missing and len(job_description) > 350:
                        job_description = job_description[:350].rsplit(' ', 1)[0] + "..."

                    # --- Date: robust fallback chain ---
                    formatted_date = "N/A"
                    raw_date = (
                        job.get("job_posted_at_datetime_utc")
                        or job.get("job_posted_at_timestamp_friendly")
                        or ""
                    )
                    if raw_date and str(raw_date).strip() not in ("N/A", "None", "null", ""):
                        try:
                            date_obj = datetime.fromisoformat(
                                str(raw_date).replace("Z", "+00:00")
                            )
                            formatted_date = date_obj.strftime("%b %d, %Y")
                        except (ValueError, AttributeError):
                            formatted_date = str(raw_date)[:10]

                    # Colors
                    btn_color = "#00ff88"
                    platform_gradient = "linear-gradient(135deg, #00ff88 0%, #00cc6f 100%)"

                    # Custom HTML card
                    job_card_html = f"""
<div class="job-result-card" style="
    background: linear-gradient(135deg, #1e1e1e 0%, #2d2d2d 100%);
    padding: 25px;
    border-radius: 20px;
    margin-bottom: 25px;
    border-left: 6px solid {btn_color};
    box-shadow: 0 8px 32px rgba(0,0,0,0.3), 0 0 20px {btn_color}40;
    position: relative;
    overflow: hidden;
    transition: all 0.4s cubic-bezier(0.175, 0.885, 0.32, 1.275);
">
    <div class="shimmer-overlay"></div>

    <!-- Platform Badge -->
    <div style="display:flex; align-items:center; gap:8px; font-size: 15px; margin-bottom: 15px; color: {btn_color}; font-weight: bold;">
        <svg xmlns="http://www.w3.org/2000/svg" width="18" height="18" viewBox="0 0 24 24" fill="{btn_color}"><path d="M13 2L3 14h9l-1 8 10-12h-9l1-8z"/></svg> RapidAPI (Live)
    </div>

    <!-- Job Title -->
    <div style="color: #ffffff; font-size: 22px; margin-bottom: 10px; font-weight: 600; line-height: 1.4;">
        {job_title}
    </div>

    <!-- Company -->
    <div style="color: #aaaaaa; font-size: 16px; margin-bottom: 15px; display:flex; align-items:center; gap:6px;">
        <svg xmlns="http://www.w3.org/2000/svg" width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="#888" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M3 9l9-7 9 7v11a2 2 0 01-2 2H5a2 2 0 01-2-2z"/><polyline points="9 22 9 12 15 12 15 22"/></svg>
        <b>{job_company}</b>
    </div>

    <!-- Job Details Grid -->
    <div style="display: grid; grid-template-columns: repeat(2, 1fr); gap: 10px; margin-bottom: 15px;">
        <div style="color: #cccccc; font-size: 14px; display:flex; align-items:center; gap:5px;"><svg xmlns="http://www.w3.org/2000/svg" width="13" height="13" viewBox="0 0 24 24" fill="none" stroke="#94a3b8" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><circle cx="12" cy="10" r="3"/><path d="M12 2a8 8 0 018 8c0 5.25-8 14-8 14S4 15.25 4 10a8 8 0 018-8z"/></svg> <b>Location:</b> {job_location}</div>
        <div style="color: #cccccc; font-size: 14px; display:flex; align-items:center; gap:5px;"><svg xmlns="http://www.w3.org/2000/svg" width="13" height="13" viewBox="0 0 24 24" fill="none" stroke="#94a3b8" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><line x1="12" y1="1" x2="12" y2="23"/><path d="M17 5H9.5a3.5 3.5 0 000 7h5a3.5 3.5 0 010 7H6"/></svg> <b>Salary:</b> {job_salary}</div>
        <div style="color: #cccccc; font-size: 14px; display:flex; align-items:center; gap:5px;"><svg xmlns="http://www.w3.org/2000/svg" width="13" height="13" viewBox="0 0 24 24" fill="none" stroke="#94a3b8" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><rect x="2" y="7" width="20" height="14" rx="2"/><path d="M16 21V5a2 2 0 00-2-2h-4a2 2 0 00-2 2v16"/></svg> <b>Type:</b> {job_type}</div>
        <div style="color: #cccccc; font-size: 14px; display:flex; align-items:center; gap:5px;"><svg xmlns="http://www.w3.org/2000/svg" width="13" height="13" viewBox="0 0 24 24" fill="none" stroke="#94a3b8" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><circle cx="12" cy="12" r="10"/><line x1="2" y1="12" x2="22" y2="12"/><path d="M12 2a15.3 15.3 0 014 10 15.3 15.3 0 01-4 10 15.3 15.3 0 01-4-10 15.3 15.3 0 014-10z"/></svg> <b>Mode:</b> {job_mode}</div>
        <div style="color: #cccccc; font-size: 14px; display:flex; align-items:center; gap:5px;"><svg xmlns="http://www.w3.org/2000/svg" width="13" height="13" viewBox="0 0 24 24" fill="none" stroke="#94a3b8" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><rect x="3" y="4" width="18" height="18" rx="2"/><line x1="16" y1="2" x2="16" y2="6"/><line x1="8" y1="2" x2="8" y2="6"/><line x1="3" y1="10" x2="21" y2="10"/></svg> <b>Posted:</b> {formatted_date}</div>
        <div style="color: #cccccc; font-size: 14px; display:flex; align-items:center; gap:5px;"><svg xmlns="http://www.w3.org/2000/svg" width="13" height="13" viewBox="0 0 24 24" fill="none" stroke="#94a3b8" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M14 2H6a2 2 0 00-2 2v16a2 2 0 002 2h12a2 2 0 002-2V8z"/></svg> <b>Source:</b> {job_publisher}</div>
    </div>

    <!-- Description / Smart CTA -->
    {(
        f'''<div style="color:#999;font-size:14px;margin-bottom:20px;line-height:1.6;">{job_description}</div>'''
        if not _desc_missing else
        f'''<a href="{job.get("job_apply_link","#")}" target="_blank" style="text-decoration:none;display:inline-flex;align-items:center;gap:10px;
            background:linear-gradient(135deg,rgba(0,255,136,0.08),rgba(0,255,136,0.03));
            border:1px dashed rgba(0,255,136,0.35);border-radius:12px;
            padding:12px 18px;margin-bottom:20px;cursor:pointer;
            transition:all 0.25s ease;width:fit-content;">
            <svg xmlns="http://www.w3.org/2000/svg" width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="#00ff88" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><circle cx="12" cy="12" r="10"/><line x1="12" y1="8" x2="12" y2="12"/><line x1="12" y1="16" x2="12.01" y2="16"/></svg>
            <span style="color:#aaa;font-size:13px;">Description not available in preview —</span>
            <span style="color:#00ff88;font-size:13px;font-weight:600;display:flex;align-items:center;gap:5px;">
                View full details on site
                <svg xmlns="http://www.w3.org/2000/svg" width="13" height="13" viewBox="0 0 24 24" fill="none" stroke="#00ff88" stroke-width="2.5" stroke-linecap="round" stroke-linejoin="round"><path d="M18 13v6a2 2 0 01-2 2H5a2 2 0 01-2-2V8a2 2 0 012-2h6"/><polyline points="15 3 21 3 21 9"/><line x1="10" y1="14" x2="21" y2="3"/></svg>
            </span>
        </a>'''
    )}

    <!-- Apply Button -->
    <a href="{job.get('job_apply_link', '#')}" target="_blank" style="text-decoration: none;">
        <button class="job-button" style="
            background: {platform_gradient};
            color: white;
            padding: 12px 24px;
            border: none;
            border-radius: 12px;
            font-size: 16px;
            font-weight: 600;
            cursor: pointer;
            box-shadow: 0 4px 15px {btn_color}50;
            transition: all 0.3s ease;
            display: inline-flex;
            align-items: center;
            gap: 7px;
        ">
            <svg xmlns="http://www.w3.org/2000/svg" width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="white" stroke-width="2.5" stroke-linecap="round" stroke-linejoin="round"><line x1="5" y1="12" x2="19" y2="12"/><polyline points="12 5 19 12 12 19"/></svg> Apply Now
        </button>
    </a>
</div>
"""
                    components.html(job_card_html, height=450, scrolling=False)

            else:
                st.info("No jobs found. Try adjusting your search criteria.")
        elif rapid_search_clicked:
            st.warning("Please select both a Job Domain and Location to perform the search.")

    # Display saved job searches if user is logged in (skip for admin)
    if hasattr(st.session_state, 'username') and st.session_state.username and st.session_state.username != "admin":
        # Get available platforms for filtering
        available_platforms = get_available_platforms(st.session_state.username)
        platform_options = ["All"] + available_platforms

        # ── Pagination reset guard ────────────────────────────────────────────
        # When a new search was just saved, the count/page caches may still hold
        # stale values.  Force-clear them NOW (before computing max_pages) and
        # reset the slider to page 1 so the offset is always 0 → no skipped or
        # duplicated rows (the FoundIt-vanishes / Naukri-twice bug).
        if st.session_state.get("_search_just_saved"):
            get_saved_job_searches.clear()
            get_total_saved_searches_count.clear()
            get_available_platforms.clear()
            # Reset the page slider key so Streamlit re-creates it at value=1
            if "page_slider" in st.session_state:
                st.session_state["page_slider"] = 1
            st.session_state["_search_just_saved"] = False

        # Get total count of searches
        total_searches = get_total_saved_searches_count(st.session_state.username)

        st.markdown("""<p class='t3-section-label' style='display:flex;align-items:center;gap:6px;'><svg xmlns="http://www.w3.org/2000/svg" width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="#38bdf8" stroke-width="2.5" stroke-linecap="round" stroke-linejoin="round"><path d="M21 10c0 7-9 13-9 13s-9-6-9-13a9 9 0 0118 0z"/><circle cx="12" cy="10" r="3"/></svg> Your Saved Job Searches</p>""", unsafe_allow_html=True)

        if total_searches > 0:
            # Controls for filtering and pagination
            col1, col2 = st.columns([2, 1])

            with col1:
                platform_filter = st.selectbox(
                    "Filter by Platform",
                    platform_options,
                    key="platform_filter"
                )

            with col2:
                # Calculate pagination
                searches_per_page = 5
                filtered_count = get_total_saved_searches_count(st.session_state.username, platform_filter)
                max_pages = max(1, (filtered_count + searches_per_page - 1) // searches_per_page)

                if max_pages > 1:
                    current_page = st.slider(
                        "📄 Page",
                        min_value=1,
                        max_value=max_pages,
                        key="page_slider"
                    )
                else:
                    current_page = 1

            # Calculate offset for pagination
            offset = (current_page - 1) * searches_per_page

            # Get filtered and paginated results
            saved_searches = get_saved_job_searches(
                st.session_state.username,
                limit=searches_per_page,
                offset=offset,
                platform_filter=platform_filter
            )

            if saved_searches:
                # Calculate and display search count info
                start_index = offset + 1
                end_index = min(offset + len(saved_searches), filtered_count)

                if platform_filter != "All":
                    st.markdown(f"**Showing {start_index}-{end_index} of {filtered_count} searches for {platform_filter}**")
                else:
                    st.markdown(f"**Showing {start_index}-{end_index} of {filtered_count} searches**")

                for search in saved_searches:
                    # timestamp is already a UTC-aware datetime from get_saved_job_searches
                    timestamp_utc = search["timestamp"]
                    if timestamp_utc is None:
                        formatted_time = "Unknown time"
                    else:
                        timestamp_ist = timestamp_utc.astimezone(ZoneInfo('Asia/Kolkata'))
                        formatted_time = timestamp_ist.strftime("%b %d, %Y at %I:%M %p IST")

                    # Platform styling
                    platform_lower = search["platform"].lower()
                    if "rapidapi" in platform_lower or "live" in platform_lower:
                        platform_color = "#00ff88"
                        platform_icon = '<svg xmlns="http://www.w3.org/2000/svg" width="14" height="14" viewBox="0 0 24 24" fill="#00ff88"><path d="M13 2L3 14h9l-1 8 10-12h-9l1-8z"/></svg>'
                    elif platform_lower == "linkedin":
                        platform_color = "#0e76a8"
                        platform_icon = '<svg xmlns="http://www.w3.org/2000/svg" width="14" height="14" viewBox="0 0 24 24" fill="#0A66C2"><path d="M20.447 20.452h-3.554v-5.569c0-1.328-.027-3.037-1.852-3.037-1.853 0-2.136 1.445-2.136 2.939v5.667H9.351V9h3.414v1.561h.046c.477-.9 1.637-1.85 3.37-1.85 3.601 0 4.267 2.37 4.267 5.455v6.286zM5.337 7.433a2.062 2.062 0 01-2.063-2.065 2.064 2.064 0 112.063 2.065zm1.782 13.019H3.555V9h3.564v11.452zM22.225 0H1.771C.792 0 0 .774 0 1.729v20.542C0 23.227.792 24 1.771 24h20.451C23.2 24 24 23.227 24 22.271V1.729C24 .774 23.2 0 22.222 0h.003z"/></svg>'
                    elif platform_lower == "naukri":
                        platform_color = "#ff5722"
                        platform_icon = '<svg xmlns="http://www.w3.org/2000/svg" width="14" height="14" viewBox="0 0 24 24" fill="#FF5722"><path d="M20 6h-2.18c.07-.44.18-.88.18-1.36C18 2.06 15.96 0 13.36 0c-1.4 0-2.72.6-3.64 1.6L8 3.34 6.28 1.6C5.36.6 4.04 0 2.64 0 1.04 0 0 1.04 0 2.64c0 .48.08.92.18 1.36H0v16a2 2 0 002 2h20a2 2 0 002-2V8a2 2 0 00-2-2z"/></svg>'
                    elif "foundit" in platform_lower:
                        platform_color = "#7c4dff"
                        platform_icon = '<svg xmlns="http://www.w3.org/2000/svg" width="14" height="14" viewBox="0 0 24 24" fill="#7C4DFF"><circle cx="12" cy="12" r="10"/><path fill="white" d="M10 8h4v4h-4zm0 6h4v2h-4z"/></svg>'
                    else:
                        platform_color = "#00c4cc"
                        platform_icon = '<svg xmlns="http://www.w3.org/2000/svg" width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="#00c4cc" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M14 2H6a2 2 0 00-2 2v16a2 2 0 002 2h12a2 2 0 002-2V8z"/><polyline points="14 2 14 8 20 8"/></svg>'

                    # Create columns for the card content and delete button
                    card_col, delete_col = st.columns([10, 1])

                    with card_col:
                        # Show company name only for RapidAPI results (others have no real company data)
                        _is_rapid = "rapidapi" in search["platform"].lower() or "live" in search["platform"].lower()
                        _company_raw = search.get("company", "").strip()
                        _company = (_company_raw[:30] + "...") if len(_company_raw) > 30 else _company_raw
                        # Build company line OUTSIDE f-string to avoid curly brace conflicts
                        if _is_rapid and _company:
                            _company_html = (
                                "<div style='color:#64748b;font-size:0.75rem;font-weight:400;"
                                "margin-top:2px;margin-bottom:2px;'> · " + _company + "</div>"
                            )
                        else:
                            _company_html = ""
                        # Build card HTML using string concatenation to avoid ALL f-string curly brace conflicts
                        _card_html = (
                            "<div class='saved-search-card' style='border-left:3px solid " + platform_color + ";'>"
                            "<div style='display:flex;justify-content:space-between;align-items:flex-start;margin-bottom:12px;'>"
                            "<div>"
                            "<div style='color:#f0f4f8;font-size:0.9rem;font-weight:600;margin-bottom:2px;font-family:var(--t3-font);letter-spacing:-0.01em;'>"
                            + platform_icon + " " + search["role"] + " in " + search["location"] +
                            "</div>"
                            + _company_html +
                            "<div style='color:" + platform_color + ";font-size:0.75rem;font-weight:600;text-transform:uppercase;letter-spacing:0.05em;font-family:var(--t3-font);'>"
                            + search["platform"] +
                            "</div>"
                            "</div>"
                            "<div style='color:#334155;font-size:0.72rem;text-align:right;font-family:var(--t3-font);letter-spacing:0.02em;white-space:nowrap;flex-shrink:0;margin-left:12px;'>"
                            + formatted_time +
                            "</div>"
                            "</div>"
                            "<a href='" + search["url"] + "' target='_blank' style='text-decoration:none;'>"
                            "<div style='display:inline-flex;align-items:center;gap:6px;"
                            "background:linear-gradient(135deg," + platform_color + "22 0%," + platform_color + "11 100%);"
                            "color:" + platform_color + ";"
                            "padding:7px 16px;border:1px solid " + platform_color + "44;"
                            "border-radius:99px;font-size:0.78rem;font-weight:600;font-family:var(--t3-font);"
                            "letter-spacing:0.03em;transition:all 0.2s ease;cursor:pointer;'>"
                            "<svg xmlns='http://www.w3.org/2000/svg' width='12' height='12' viewBox='0 0 24 24' fill='none' stroke='currentColor' stroke-width='2.5' stroke-linecap='round' stroke-linejoin='round'>"
                            "<path d='M18 13v6a2 2 0 01-2 2H5a2 2 0 01-2-2V8a2 2 0 012-2h6'/>"
                            "<polyline points='15 3 21 3 21 9'/><line x1='10' y1='14' x2='21' y2='3'/></svg> View Jobs"
                            "</div></a></div>"
                        )
                        st.markdown(_card_html, unsafe_allow_html=True)

                    with delete_col:
                        if st.button("🗑", key=f"delete_{search['id']}", help="Delete this search"):
                            success = delete_saved_job_search(search['id'])
                            if success:
                                st.rerun(scope="fragment")
            else:
                st.markdown(f"""
<div class="empty-state">
    <div class="icon"><svg xmlns="http://www.w3.org/2000/svg" width="40" height="40" viewBox="0 0 24 24" fill="none" stroke="#64748b" stroke-width="1.5" stroke-linecap="round" stroke-linejoin="round"><circle cx="11" cy="11" r="8"/><line x1="21" y1="21" x2="16.65" y2="16.65"/></svg></div>
    <div class="title">No results found</div>
    <div class="sub">No saved searches for {platform_filter if platform_filter != 'All' else 'this page'}.</div>
</div>
""", unsafe_allow_html=True)
        else:
            # No saved searches at all
            st.markdown("""
<div class="empty-state">
    <div class="icon"><svg xmlns="http://www.w3.org/2000/svg" width="40" height="40" viewBox="0 0 24 24" fill="none" stroke="#64748b" stroke-width="1.5" stroke-linecap="round" stroke-linejoin="round"><path d="M22 16.92v3a2 2 0 01-2.18 2 19.79 19.79 0 01-8.63-3.07A19.5 19.5 0 013.07 9.8 19.79 19.79 0 01.1 1.18 2 2 0 012.11 0h3a2 2 0 012 1.72c.127.96.361 1.903.7 2.81a2 2 0 01-.45 2.11L6.09 7.91a16 16 0 006 6l1.27-1.27a2 2 0 012.11-.45c.907.339 1.85.573 2.81.7A2 2 0 0122 16.92z"/></svg></div>
    <div class="title">No saved searches yet</div>
    <div class="sub">Start searching to see your job history here.</div>
</div>
""", unsafe_allow_html=True)


# ═══════════════════════════════════════════════════════════════
# ANALYTICS DASHBOARD FRAGMENT
# Isolated so chart interactions (orientation toggles, scope
# radio) do NOT rerun the job-search form above, and a fresh
# search clears fetch_analytics_data cache so this fragment
# re-fetches immediately on its next rerun.
# ═══════════════════════════════════════════════════════════════

@st.fragment
def _analytics_dashboard():
    import plotly.graph_objects as go
    import plotly.express as px
    import pandas as pd

    # ── Plotly dark theme base config ────────────────────────────
    _PLOTLY_BASE = dict(
        paper_bgcolor="rgba(0,0,0,0)",
        plot_bgcolor="rgba(15,15,26,0.6)",
        font=dict(family="Inter, sans-serif", color="#cccccc", size=12),
        margin=dict(l=10, r=55, t=35, b=10),
    )
    _XAXIS = dict(
        gridcolor="rgba(255,255,255,0.06)",
        zerolinecolor="rgba(255,255,255,0.08)",
        tickfont=dict(size=11, color="#999"),
    )
    _YAXIS = dict(
        gridcolor="rgba(255,255,255,0.06)",
        zerolinecolor="rgba(255,255,255,0.08)",
        tickfont=dict(size=11, color="#999"),
    )

    st.markdown("---")
    st.markdown("""
    <div class="analytics-header">
        <div style='display:flex; align-items:center; justify-content:center; gap:12px; margin-bottom:4px;'>
            <svg xmlns="http://www.w3.org/2000/svg" width="28" height="28" viewBox="0 0 24 24" fill="none" stroke="#38bdf8" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round" style="flex-shrink:0;">
                <line x1="18" y1="20" x2="18" y2="10"/>
                <line x1="12" y1="20" x2="12" y2="4"/>
                <line x1="6" y1="20" x2="6" y2="14"/>
                <polyline points="2 20 22 20"/>
            </svg>
            <h2>Search Analytics Dashboard</h2>
            <svg xmlns="http://www.w3.org/2000/svg" width="22" height="22" viewBox="0 0 24 24" fill="none" stroke="#818cf8" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round" style="flex-shrink:0;">
                <circle cx="11" cy="11" r="8"/>
                <line x1="21" y1="21" x2="16.65" y2="16.65"/>
            </svg>
        </div>
        <p>Real-time insights from your job search history · All times in <b style="color:#38bdf8">IST (UTC+5:30)</b></p>
    </div>
    """, unsafe_allow_html=True)

    # ── Analytics Scope Toggle ────────────────────────────────────
    # Track previous scope so we can bust the cache the moment scope changes
    if "_prev_analytics_scope" not in st.session_state:
        st.session_state["_prev_analytics_scope"] = "My Analytics"

    _scope_col, _refresh_col = st.columns([5, 1])
    with _scope_col:
        st.markdown("""<label style="font-size:0.82rem;font-weight:600;color:#94a3b8;display:flex;align-items:center;gap:6px;margin-bottom:4px;">
            <svg xmlns="http://www.w3.org/2000/svg" width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M1 6l5 5 5-5"/><path d="M6 11V3"/><path d="M23 18l-5-5-5 5"/><path d="M18 13v8"/></svg>
            Analytics Scope</label>""", unsafe_allow_html=True)
        analytics_scope = st.radio(
            "Analytics Scope",
            ["My Analytics", "Global Analytics"],
            horizontal=True,
            key="analytics_scope_toggle",
            label_visibility="collapsed"
        )
    with _refresh_col:
        st.markdown("""<label style="font-size:0.82rem;font-weight:600;color:transparent;display:block;margin-bottom:4px;">.</label>""", unsafe_allow_html=True)
        if st.button("↺ Refresh", key="analytics_refresh_btn", help="Force-fetch latest data"):
            fetch_analytics_data.clear()

    is_my_analytics = analytics_scope == "My Analytics"

    # If the user just switched scope, clear the cache so the new scope
    # fetches fresh data immediately instead of returning the cached value
    if analytics_scope != st.session_state["_prev_analytics_scope"]:
        fetch_analytics_data.clear()
        st.session_state["_prev_analytics_scope"] = analytics_scope

    # Determine scope
    current_user = st.session_state.username if hasattr(st.session_state, 'username') and st.session_state.username else None
    scope_user = current_user if is_my_analytics else None

    if is_my_analytics and not current_user:
        st.warning("Please log in to view your personal analytics.")
    else:
        df_analytics = fetch_analytics_data(scope_username=scope_user)

        # ── Empty State Guard ──────────────────────────────────────
        if df_analytics.empty:
            st.markdown("""
            <div class="empty-state">
                <div class="icon"><svg xmlns="http://www.w3.org/2000/svg" width="40" height="40" viewBox="0 0 24 24" fill="none" stroke="#64748b" stroke-width="1.5" stroke-linecap="round" stroke-linejoin="round"><path d="M22 16.92v3a2 2 0 01-2.18 2 19.79 19.79 0 01-8.63-3.07A19.5 19.5 0 013.07 9.8 19.79 19.79 0 01.1 1.18 2 2 0 012.11 0h3a2 2 0 012 1.72c.127.96.361 1.903.7 2.81a2 2 0 01-.45 2.11L6.09 7.91a16 16 0 006 6l1.27-1.27a2 2 0 012.11-.45c.907.339 1.85.573 2.81.7A2 2 0 0122 16.92z"/></svg></div>
                <div class="title">No Data Yet</div>
                <div class="sub">Perform job searches to populate your analytics dashboard.</div>
            </div>
            """, unsafe_allow_html=True)
        else:
            # ── Compute KPIs ───────────────────────────────────────
            # Raw row count — every inserted record counts:
            #   LinkedIn Scraper slider=N: 1 click → N rows → +N
            #   RapidAPI slider=N:         1 click → N rows → +N
            # No session grouping, no deduplication, no cap.
            total_searches      = len(df_analytics)
            unique_roles        = df_analytics['role'].nunique()
            unique_locations    = df_analytics['location'].nunique()
            top_platform_series = df_analytics['platform'].value_counts()
            most_used_platform  = top_platform_series.index[0] if not top_platform_series.empty else "N/A"
            top_plat_count      = int(top_platform_series.iloc[0]) if not top_platform_series.empty else 0

            # ── KPI Cards — custom HTML (no truncation) ───────────
            st.markdown("<div style='height:8px'></div>", unsafe_allow_html=True)
            kpi1, kpi2, kpi3, kpi4 = st.columns(4)

            def _kpi_card(col, icon_svg, label, value, sub, accent):
                col.markdown(f"""
                <div class="kpi-card" style="border-color:{accent}22;">
                    <div style='margin-bottom:8px; display:flex; align-items:center; justify-content:center;'>{icon_svg}</div>
                    <div style='
                        color:{accent};
                        font-size:0.68rem;
                        font-weight:700;
                        letter-spacing:0.09em;
                        text-transform:uppercase;
                        margin-bottom:5px;
                        font-family:var(--t3-font);
                    '>{label}</div>
                    <div style='
                        color:#f0f4f8;
                        font-size:1.6rem;
                        font-weight:800;
                        line-height:1;
                        margin-bottom:5px;
                        word-break:break-word;
                        font-family:var(--t3-font);
                        letter-spacing:-0.02em;
                    '>{value}</div>
                    <div style='color:#334155; font-size:0.72rem; font-family:var(--t3-font);'>{sub}</div>
                </div>
                """, unsafe_allow_html=True)

            _kpi_card(kpi1, '<svg xmlns="http://www.w3.org/2000/svg" width="22" height="22" viewBox="0 0 24 24" fill="none" stroke="#00c4cc" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round"><circle cx="11" cy="11" r="8"/><line x1="21" y1="21" x2="16.65" y2="16.65"/></svg>', "Total Searches", f"{total_searches:,}", "all recorded", "#00c4cc")
            _kpi_card(kpi2, '<svg xmlns="http://www.w3.org/2000/svg" width="22" height="22" viewBox="0 0 24 24" fill="none" stroke="#7c4dff" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round"><rect x="2" y="7" width="20" height="14" rx="2"/><path d="M16 21V5a2 2 0 00-2-2h-4a2 2 0 00-2 2v16"/></svg>', "Unique Roles", f"{unique_roles:,}", "distinct job titles", "#7c4dff")
            _kpi_card(kpi3, '<svg xmlns="http://www.w3.org/2000/svg" width="22" height="22" viewBox="0 0 24 24" fill="none" stroke="#34d399" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round"><circle cx="12" cy="10" r="3"/><path d="M12 2a8 8 0 018 8c0 5.25-8 14-8 14S4 15.25 4 10a8 8 0 018-8z"/></svg>', "Unique Locations", f"{unique_locations:,}", "distinct cities/regions", "#34d399")
            _kpi_card(kpi4, '<svg xmlns="http://www.w3.org/2000/svg" width="22" height="22" viewBox="0 0 24 24" fill="none" stroke="#fbbf24" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round"><path d="M12 2l3.09 6.26L22 9.27l-5 4.87 1.18 6.88L12 17.77l-6.18 3.25L7 14.14 2 9.27l6.91-1.01L12 2z"/></svg>', "Top Platform", most_used_platform, f"{top_plat_count} searches", "#fbbf24")

            st.markdown("<div style='height:24px'></div>", unsafe_allow_html=True)

            # ── SECTION HEADER helper ─────────────────────────────
            def _section_header(icon_svg, title, subtitle, accent):
                st.markdown(f"""
                <div style='
                    display:flex; align-items:center; gap:10px;
                    margin-bottom:14px; padding-bottom:10px;
                    border-bottom: 1px solid rgba(255,255,255,0.06);
                    font-family:var(--t3-font);
                '>
                    <span style='display:flex;align-items:center;flex-shrink:0;'>{icon_svg}</span>
                    <div>
                        <div style='
                            color:{accent};
                            font-size:0.875rem;
                            font-weight:700;
                            letter-spacing:-0.01em;
                        '>{title}</div>
                        <div style='color:#334155; font-size:0.72rem; letter-spacing:0.04em; text-transform:uppercase;'>{subtitle}</div>
                    </div>
                </div>
                """, unsafe_allow_html=True)

            # ── ROW 1: Top Roles + Top Locations ─────────────────
            col_roles, col_locs = st.columns(2)

            with col_roles:
                _section_header('<svg xmlns="http://www.w3.org/2000/svg" width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="#00c4cc" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><circle cx="11" cy="11" r="8"/><line x1="21" y1="21" x2="16.65" y2="16.65"/></svg>', "Top 5 Most Searched Roles", "by search frequency", "#00c4cc")
                roles_orient = st.radio("Orientation", ["↔ Horizontal", "↕ Vertical"], index=0, horizontal=True, key="roles_orient")
                top_roles = (
                    df_analytics['role'].value_counts().head(5)
                    .reset_index()
                )
                top_roles.columns = ['Role', 'Count']
                top_roles = top_roles.sort_values('Count')
                _ROLE_COLORS = ['#00c4cc', '#7c4dff', '#34d399', '#fbbf24', '#f87171']
                _role_bar_colors = [_ROLE_COLORS[i % len(_ROLE_COLORS)] for i in range(len(top_roles))]
                if roles_orient == "↔ Horizontal":
                    fig_roles = go.Figure(go.Bar(
                        x=top_roles['Count'],
                        y=top_roles['Role'],
                        orientation='h',
                        marker=dict(
                            color=_role_bar_colors,
                            line=dict(color='rgba(255,255,255,0.15)', width=1),
                        ),
                        text=top_roles['Count'],
                        textposition='outside',
                        textfont=dict(color='#ffffff', size=12, family='Inter'),
                        hovertemplate='<b>%{y}</b><br>Searches: %{x}<extra></extra>',
                        cliponaxis=False,
                    ))
                    _roles_h_max = int(top_roles['Count'].max()) if not top_roles.empty else 1
                    fig_roles.update_layout(
                        **_PLOTLY_BASE, height=260, showlegend=False,
                        xaxis_title=None, yaxis_title=None,
                        xaxis=dict(**_XAXIS, showgrid=True, range=[0, _roles_h_max * 1.25]),
                        yaxis=dict(**_YAXIS, showgrid=False),
                    )
                else:
                    fig_roles = go.Figure(go.Bar(
                        x=top_roles['Role'],
                        y=top_roles['Count'],
                        orientation='v',
                        marker=dict(
                            color=_role_bar_colors,
                            line=dict(color='rgba(255,255,255,0.15)', width=1),
                        ),
                        text=top_roles['Count'],
                        textposition='outside',
                        textfont=dict(color='#ffffff', size=12, family='Inter'),
                        hovertemplate='<b>%{x}</b><br>Searches: %{y}<extra></extra>',
                        cliponaxis=False,
                    ))
                    _roles_v_max = int(top_roles['Count'].max()) if not top_roles.empty else 1
                    fig_roles.update_layout(
                        **_PLOTLY_BASE, height=260, showlegend=False,
                        xaxis_title=None, yaxis_title=None,
                        xaxis=dict(**_XAXIS, tickangle=-25),
                        yaxis=dict(**_YAXIS, showgrid=True, range=[0, _roles_v_max * 1.25]),
                    )
                st.plotly_chart(fig_roles, use_container_width=True, config={
                    "displayModeBar": True,
                    "displaylogo": False,
                    "modeBarButtonsToRemove": ["select2d", "lasso2d", "autoScale2d"],
                    "toImageButtonOptions": {"format": "png", "filename": "top_roles"},
                    "scrollZoom": False,
                })

            with col_locs:
                _section_header('<svg xmlns="http://www.w3.org/2000/svg" width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="#7c4dff" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><circle cx="12" cy="10" r="3"/><path d="M12 2a8 8 0 018 8c0 5.25-8 14-8 14S4 15.25 4 10a8 8 0 018-8z"/></svg>', "Top 5 Most Searched Locations", "by search frequency", "#7c4dff")
                locs_orient = st.radio("Orientation", ["↔ Horizontal", "↕ Vertical"], index=0, horizontal=True, key="locs_orient")
                top_locs = (
                    df_analytics['location'].value_counts().head(5)
                    .reset_index()
                )
                top_locs.columns = ['Location', 'Count']
                top_locs = top_locs.sort_values('Count')
                _LOC_COLORS = ['#7c4dff', '#f87171', '#fbbf24', '#34d399', '#00c4cc']
                _loc_bar_colors = [_LOC_COLORS[i % len(_LOC_COLORS)] for i in range(len(top_locs))]
                if locs_orient == "↔ Horizontal":
                    fig_locs = go.Figure(go.Bar(
                        x=top_locs['Count'],
                        y=top_locs['Location'],
                        orientation='h',
                        marker=dict(
                            color=_loc_bar_colors,
                            line=dict(color='rgba(255,255,255,0.15)', width=1),
                        ),
                        text=top_locs['Count'],
                        textposition='outside',
                        textfont=dict(color='#ffffff', size=12, family='Inter'),
                        hovertemplate='<b>%{y}</b><br>Searches: %{x}<extra></extra>',
                        cliponaxis=False,
                    ))
                    _locs_h_max = int(top_locs['Count'].max()) if not top_locs.empty else 1
                    fig_locs.update_layout(
                        **_PLOTLY_BASE, height=260, showlegend=False,
                        xaxis_title=None, yaxis_title=None,
                        xaxis=dict(**_XAXIS, showgrid=True, range=[0, _locs_h_max * 1.25]),
                        yaxis=dict(**_YAXIS, showgrid=False),
                    )
                else:
                    fig_locs = go.Figure(go.Bar(
                        x=top_locs['Location'],
                        y=top_locs['Count'],
                        orientation='v',
                        marker=dict(
                            color=_loc_bar_colors,
                            line=dict(color='rgba(255,255,255,0.15)', width=1),
                        ),
                        text=top_locs['Count'],
                        textposition='outside',
                        textfont=dict(color='#ffffff', size=12, family='Inter'),
                        hovertemplate='<b>%{x}</b><br>Searches: %{y}<extra></extra>',
                        cliponaxis=False,
                    ))
                    _locs_v_max = int(top_locs['Count'].max()) if not top_locs.empty else 1
                    fig_locs.update_layout(
                        **_PLOTLY_BASE, height=260, showlegend=False,
                        xaxis_title=None, yaxis_title=None,
                        xaxis=dict(**_XAXIS, tickangle=-25),
                        yaxis=dict(**_YAXIS, showgrid=True, range=[0, _locs_v_max * 1.25]),
                    )
                st.plotly_chart(fig_locs, use_container_width=True, config={
                    "displayModeBar": True,
                    "displaylogo": False,
                    "modeBarButtonsToRemove": ["select2d", "lasso2d", "autoScale2d"],
                    "toImageButtonOptions": {"format": "png", "filename": "top_locations"},
                    "scrollZoom": False,
                })

            # ── ROW 2: Platform Distribution (donut) + Trend (area line) ──
            col_plat, col_trend = st.columns(2)

            with col_plat:
                _section_header('<svg xmlns="http://www.w3.org/2000/svg" width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="#fbbf24" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><rect x="2" y="3" width="20" height="14" rx="2"/><line x1="8" y1="21" x2="16" y2="21"/><line x1="12" y1="17" x2="12" y2="21"/></svg>', "Platform Usage Distribution", "share of all searches", "#fbbf24")
                plat_orient = st.radio("Orientation", ["↕ Vertical", "↔ Horizontal"], index=0, horizontal=True, key="plat_orient")
                plat_dist = (
                    df_analytics.groupby('platform').size()
                    .reset_index(name='Count')
                    .sort_values('Count', ascending=False)
                )
                _PLAT_COLOR_MAP = {
                    'rapidapi (live)': '#00ff88',
                    'linkedin':        '#0e76a8',
                    'naukri':          '#ff5722',
                    'foundit (monster)': '#7c4dff',
                }
                _PLAT_FALLBACKS = ['#fbbf24', '#f87171', '#00c4cc', '#34d399', '#a78bfa']
                def _plat_color(name, idx):
                    return _PLAT_COLOR_MAP.get(name.lower(), _PLAT_FALLBACKS[idx % len(_PLAT_FALLBACKS)])

                if plat_orient == "↕ Vertical":
                    _pv_colors = [_plat_color(p, i) for i, p in enumerate(plat_dist['platform'])]
                    fig_plat = go.Figure(go.Bar(
                        x=plat_dist['platform'],
                        y=plat_dist['Count'],
                        orientation='v',
                        marker=dict(
                            color=_pv_colors,
                            line=dict(color='rgba(255,255,255,0.15)', width=1),
                        ),
                        text=plat_dist['Count'],
                        textposition='outside',
                        textfont=dict(color='#ffffff', size=11, family='Inter'),
                        hovertemplate='<b>%{x}</b><br>Searches: %{y}<extra></extra>',
                        cliponaxis=False,
                    ))
                    _plat_v_max = int(plat_dist['Count'].max()) if not plat_dist.empty else 1
                    fig_plat.update_layout(
                        **_PLOTLY_BASE, height=270, showlegend=False,
                        xaxis=dict(**_XAXIS, tickangle=-25),
                        yaxis=dict(**_YAXIS, range=[0, _plat_v_max * 1.25]),
                        bargap=0.3,
                    )
                else:
                    plat_dist_h = plat_dist.sort_values('Count')
                    _ph_colors = [_plat_color(p, i) for i, p in enumerate(plat_dist_h['platform'])]
                    fig_plat = go.Figure(go.Bar(
                        x=plat_dist_h['Count'],
                        y=plat_dist_h['platform'],
                        orientation='h',
                        marker=dict(
                            color=_ph_colors,
                            line=dict(color='rgba(255,255,255,0.15)', width=1),
                        ),
                        text=plat_dist_h['Count'],
                        textposition='outside',
                        textfont=dict(color='#ffffff', size=11, family='Inter'),
                        hovertemplate='<b>%{y}</b><br>Searches: %{x}<extra></extra>',
                        cliponaxis=False,
                    ))
                    _plat_h_max = int(plat_dist_h['Count'].max()) if not plat_dist_h.empty else 1
                    fig_plat.update_layout(
                        **_PLOTLY_BASE, height=270, showlegend=False,
                        xaxis=dict(**_XAXIS, showgrid=True, range=[0, _plat_h_max * 1.25]),
                        yaxis=dict(**_YAXIS, showgrid=False),
                        bargap=0.3,
                    )
                st.plotly_chart(fig_plat, use_container_width=True, config={
                    "displayModeBar": True,
                    "displaylogo": False,
                    "modeBarButtonsToRemove": ["select2d", "lasso2d", "autoScale2d"],
                    "toImageButtonOptions": {"format": "png", "filename": "platform_distribution"},
                    "scrollZoom": False,
                })

            with col_trend:
                _section_header('<svg xmlns="http://www.w3.org/2000/svg" width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="#34d399" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><polyline points="22 7 13.5 15.5 8.5 10.5 2 17"/><polyline points="16 7 22 7 22 13"/></svg>', "Search Trend Over Time (IST)", "daily activity", "#34d399")
                trend_data = (
                    df_analytics.groupby('date').size()
                    .reset_index(name='Searches')
                    .sort_values('date')
                )

                fig_trend = go.Figure()
                # Area fill
                fig_trend.add_trace(go.Scatter(
                    x=trend_data['date'],
                    y=trend_data['Searches'],
                    mode='lines+markers',
                    line=dict(color='#34d399', width=2.5, shape='spline'),
                    marker=dict(size=7, color='#34d399', line=dict(color='#0f1f18', width=2)),
                    fill='tozeroy',
                    fillcolor='rgba(52,211,153,0.08)',
                    hovertemplate='<b>%{x}</b><br>Searches: %{y}<extra></extra>',
                    name='Searches',
                ))
                fig_trend.update_layout(
                    **_PLOTLY_BASE,
                    height=270,
                    showlegend=False,
                    xaxis=dict(**_XAXIS, tickangle=-25),
                    yaxis=dict(**_YAXIS),
                )
                st.plotly_chart(fig_trend, use_container_width=True, config={
                                    "displayModeBar": True,
                                    "displaylogo": False,
                                    "modeBarButtonsToRemove": ["select2d", "lasso2d", "autoScale2d"],
                                    "toImageButtonOptions": {"format": "png", "filename": "search_trend"},
                                    "scrollZoom": False,
                                })

            # ── ROW 3: Peak Hour (IST, full width) ───────────────
            _section_header('<svg xmlns="http://www.w3.org/2000/svg" width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="#f87171" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><circle cx="12" cy="12" r="10"/><polyline points="12 6 12 12 16 14"/></svg>', "Peak Search Hour — IST (0–23 Distribution)", "when you search most — converted to Indian Standard Time", "#f87171")
            hour_orient = st.radio("Orientation", ["↕ Vertical", "↔ Horizontal"], index=0, horizontal=True, key="hour_orient")

            # Build full 0-23 with IST hours
            hour_counts = df_analytics.groupby('hour').size().reset_index(name='Searches')
            all_hours   = pd.DataFrame({'hour': range(24)})
            hour_dist   = (
                all_hours.merge(hour_counts, on='hour', how='left').fillna(0).astype({'Searches': int})
            )
            hour_dist['Label'] = hour_dist['hour'].apply(lambda h: f"{h:02d}:00–{h:02d}:59")
            peak_hour = int(hour_dist.loc[hour_dist['Searches'].idxmax(), 'hour'])
            peak_label = f"{peak_hour:02d}:00–{peak_hour:02d}:59"

            # Color bars: highlight peak hour in bright red
            bar_colors = [
                '#f87171' if h == peak_hour else '#4a1515'
                for h in hour_dist['hour']
            ]
            bar_opacities = [1.0 if h == peak_hour else 0.65 for h in hour_dist['hour']]

            if hour_orient == "↕ Vertical":
                fig_hour = go.Figure(go.Bar(
                    x=hour_dist['Label'],
                    y=hour_dist['Searches'],
                    marker_color=bar_colors,
                    marker_opacity=bar_opacities,
                    marker_line=dict(color='rgba(248,113,113,0.3)', width=0.5),
                    text=[str(v) if v > 0 else '' for v in hour_dist['Searches']],
                    textposition='outside',
                    textfont=dict(color='#f87171', size=10, family='Inter'),
                    hovertemplate='<b>%{x} IST</b><br>Searches: %{y}<extra></extra>',
                    cliponaxis=False,
                ))
                # Annotation for peak
                if hour_dist['Searches'].max() > 0:
                    fig_hour.add_annotation(
                        x=peak_label,
                        y=hour_dist['Searches'].max(),
                        text=f"⚡ Peak: {peak_hour:02d}:00 IST",
                        showarrow=True, arrowhead=2, arrowcolor='#f87171',
                        font=dict(color='#f87171', size=12, family='Inter'),
                        bgcolor='rgba(248,113,113,0.15)',
                        bordercolor='#f87171', borderwidth=1, borderpad=5, yshift=10,
                    )
                _hour_v_max = int(hour_dist['Searches'].max()) if hour_dist['Searches'].max() > 0 else 1
                fig_hour.update_layout(
                    **_PLOTLY_BASE, height=290, showlegend=False, bargap=0.15,
                    xaxis=dict(**{**_XAXIS, "tickfont": dict(size=10, color="#999"), "tickangle": -45}),
                    yaxis=dict(**_YAXIS, range=[0, _hour_v_max * 1.3]),
                )
            else:
                fig_hour = go.Figure(go.Bar(
                    x=hour_dist['Searches'],
                    y=hour_dist['Label'],
                    orientation='h',
                    marker_color=bar_colors,
                    marker_opacity=bar_opacities,
                    marker_line=dict(color='rgba(248,113,113,0.3)', width=0.5),
                    text=[str(v) if v > 0 else '' for v in hour_dist['Searches']],
                    textposition='outside',
                    textfont=dict(color='#f87171', size=10, family='Inter'),
                    hovertemplate='<b>%{y} IST</b><br>Searches: %{x}<extra></extra>',
                    cliponaxis=False,
                ))
                if hour_dist['Searches'].max() > 0:
                    fig_hour.add_annotation(
                        y=peak_label,
                        x=hour_dist['Searches'].max(),
                        text=f"⚡ Peak: {peak_hour:02d}:00 IST",
                        showarrow=True, arrowhead=2, arrowcolor='#f87171',
                        font=dict(color='#f87171', size=12, family='Inter'),
                        bgcolor='rgba(248,113,113,0.15)',
                        bordercolor='#f87171', borderwidth=1, borderpad=5, xshift=10,
                    )
                _hour_h_max = int(hour_dist['Searches'].max()) if hour_dist['Searches'].max() > 0 else 1
                fig_hour.update_layout(
                    **_PLOTLY_BASE, height=600, showlegend=False, bargap=0.15,
                    xaxis=dict(**_XAXIS, showgrid=True, range=[0, _hour_h_max * 1.25]),
                    yaxis=dict(**{**_YAXIS, "tickfont": dict(size=10, color="#999")}),
                )
            st.plotly_chart(fig_hour, use_container_width=True, config={
                "displayModeBar": True,
                "displaylogo": False,
                "modeBarButtonsToRemove": ["select2d", "lasso2d", "autoScale2d"],
                "toImageButtonOptions": {"format": "png", "filename": "peak_hour"},
                "scrollZoom": False,
            })

            # ── Footer ────────────────────────────────────────────
            scope_label = f"@{current_user}" if is_my_analytics else "all users"
            ist_now = datetime.now(ZoneInfo('Asia/Kolkata')).strftime("%b %d, %Y %I:%M %p IST")
            st.markdown(f"""
            <div class="analytics-footer">
                {total_searches:,} records · {scope_label} · Updated {ist_now} · Supabase PostgreSQL
            </div>
            """, unsafe_allow_html=True)

    # ============================================================
    # END OF SEARCH ANALYTICS DASHBOARD
    # ============================================================
# ← _analytics_dashboard() fragment ends here


# ═══════════════════════════════════════════════════════════════
# FEATURED COMPANIES SECTION
# ═══════════════════════════════════════════════════════════════

def render_featured_companies():
    st.markdown("""### <div class='title-header'><svg xmlns="http://www.w3.org/2000/svg" width="22" height="22" viewBox="0 0 24 24" fill="none" stroke="url(#g1)" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" style="vertical-align:middle;margin-right:8px;"><defs><linearGradient id="g1" x1="0%" y1="0%" x2="100%" y2="0%"><stop offset="0%" stop-color="#38bdf8"/><stop offset="100%" stop-color="#818cf8"/></linearGradient></defs><path d="M3 9l9-7 9 7v11a2 2 0 01-2 2H5a2 2 0 01-2-2z"/><polyline points="9 22 9 12 15 12 15 22"/></svg> Featured Companies</div>""", unsafe_allow_html=True)

    selected_category = st.selectbox("Browse Featured Companies By Category", ["All", "tech", "indian_tech", "global_corps"])
    companies_to_show = get_featured_companies() if selected_category == "All" else get_featured_companies(selected_category)

    for company in companies_to_show:
        category_tags = ''.join([f"<span class='pill'>{cat}</span>" for cat in company['categories']])
        logo_url = company.get('logo_url', '')
        company_color = company.get('color', '#38bdf8')
        logo_html = f'<img src="{logo_url}" alt="{company["name"]} logo" style="height:32px; width:auto; max-width:90px; object-fit:contain; margin-right:12px; flex-shrink:0; filter:brightness(1) contrast(1);" />' if logo_url else f'<span style="width:32px;height:32px;border-radius:8px;background:{company_color}22;display:inline-flex;align-items:center;justify-content:center;margin-right:12px;flex-shrink:0;"><svg xmlns=\'http://www.w3.org/2000/svg\' width=\'18\' height=\'18\' viewBox=\'0 0 24 24\' fill=\'{company_color}\'><path d=\'M12 7V3H2v18h20V7H12zM6 19H4v-2h2v2zm0-4H4v-2h2v2zm0-4H4V9h2v2zm0-4H4V5h2v2zm4 12H8v-2h2v2zm0-4H8v-2h2v2zm0-4H8V9h2v2zm0-4H8V5h2v2zm10 12h-8v-2h2v-2h-2v-2h2v-2h-2V9h8v10zm-2-8h-2v2h2v-2zm0 4h-2v2h2v-2z\'/></svg></span>'
        st.markdown(f"""
        <a href="{company['careers_url']}" class="company-card" target="_blank">
            <div class="company-header">
                {logo_html}
                <span style="color:var(--t3-text); font-size:1.05rem; font-weight:700;">{company['name']}</span>
                <svg xmlns="http://www.w3.org/2000/svg" width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="rgba(255,255,255,0.25)" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" style="margin-left:auto; flex-shrink:0;"><path d="M18 13v6a2 2 0 01-2 2H5a2 2 0 01-2-2V8a2 2 0 012-2h6"/><polyline points="15 3 21 3 21 9"/><line x1="10" y1="14" x2="21" y2="3"/></svg>
            </div>
            <p style="
                margin-bottom: 14px;
                line-height: 1.6;
                position: relative;
                z-index: 2;
                color: #64748b;
                font-size: 0.85rem;
                font-family: -apple-system, BlinkMacSystemFont, 'SF Pro Display', sans-serif;
            ">{company['description']}</p>
            <div style="position: relative; z-index: 2;">{category_tags}</div>
        </a>
        """, unsafe_allow_html=True)


# ═══════════════════════════════════════════════════════════════
# JOB MARKET TRENDS SECTION
# ═══════════════════════════════════════════════════════════════

def render_market_trends():
    st.markdown("""### <div class='title-header'><svg xmlns="http://www.w3.org/2000/svg" width="22" height="22" viewBox="0 0 24 24" fill="none" stroke="url(#g2)" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" style="vertical-align:middle;margin-right:8px;"><defs><linearGradient id="g2" x1="0%" y1="0%" x2="100%" y2="0%"><stop offset="0%" stop-color="#38bdf8"/><stop offset="100%" stop-color="#818cf8"/></linearGradient></defs><polyline points="22 7 13.5 15.5 8.5 10.5 2 17"/><polyline points="16 7 22 7 22 13"/></svg> Job Market Trends</div>""", unsafe_allow_html=True)
    col1, col2 = st.columns(2)

    with col1:
        st.markdown("""
        <p style='
            font-size:0.7rem; font-weight:700; letter-spacing:0.10em;
            text-transform:uppercase; color:#334155;
            border-bottom:1px solid rgba(255,255,255,0.06);
            padding-bottom:8px; margin-bottom:14px;
            font-family:-apple-system,BlinkMacSystemFont,"SF Pro Display",sans-serif;
            display:flex; align-items:center; gap:6px;
        '><svg xmlns="http://www.w3.org/2000/svg" width="13" height="13" viewBox="0 0 24 24" fill="#38bdf8"><path d="M13 2L3 14h9l-1 8 10-12h-9l1-8z"/></svg> Trending Skills</p>
        """, unsafe_allow_html=True)
        for skill in JOB_MARKET_INSIGHTS["trending_skills"]:
            st.markdown(f"""
            <div class="insight-card">
                <h4 style="color:#38bdf8; display:flex; align-items:center; gap:7px;">
                    <svg xmlns="http://www.w3.org/2000/svg" width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="#38bdf8" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><circle cx="12" cy="12" r="3"/><path d="M19.07 4.93a10 10 0 010 14.14M4.93 4.93a10 10 0 000 14.14"/></svg>
                    {skill['name']}
                </h4>
                <p>Growth Rate: <span style="color:#34d399; font-weight:700;">{skill['growth']}</span></p>
            </div>
            """, unsafe_allow_html=True)

    with col2:
        st.markdown("""
        <p style='
            font-size:0.7rem; font-weight:700; letter-spacing:0.10em;
            text-transform:uppercase; color:#334155;
            border-bottom:1px solid rgba(255,255,255,0.06);
            padding-bottom:8px; margin-bottom:14px;
            font-family:-apple-system,BlinkMacSystemFont,"SF Pro Display",sans-serif;
            display:flex; align-items:center; gap:6px;
        '><svg xmlns="http://www.w3.org/2000/svg" width="13" height="13" viewBox="0 0 24 24" fill="none" stroke="#818cf8" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><circle cx="12" cy="10" r="3"/><path d="M12 2a8 8 0 018 8c0 5.25-8 14-8 14S4 15.25 4 10a8 8 0 018-8z"/></svg> Top Job Locations</p>
        """, unsafe_allow_html=True)
        for loc in JOB_MARKET_INSIGHTS["top_locations"]:
            st.markdown(f"""
            <div class="insight-card" style="--left-bar: var(--t3-violet);">
                <h4 style="color:#818cf8; display:flex; align-items:center; gap:7px;">
                    <svg xmlns="http://www.w3.org/2000/svg" width="13" height="13" viewBox="0 0 24 24" fill="#818cf8"><circle cx="12" cy="10" r="3"/><path d="M12 2a8 8 0 018 8c0 5.25-8 14-8 14S4 15.25 4 10a8 8 0 018-8z"/></svg>
                    {loc['name']}
                </h4>
                <p>Openings: <span style="color:#fbbf24; font-weight:700;">{loc['jobs']}</span></p>
            </div>
            """, unsafe_allow_html=True)


# ═══════════════════════════════════════════════════════════════
# SALARY INSIGHTS SECTION
# ═══════════════════════════════════════════════════════════════

def render_salary_insights():
    st.markdown("""### <div class='title-header'><svg xmlns="http://www.w3.org/2000/svg" width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="url(#g3)" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" style="vertical-align:middle;margin-right:8px;"><defs><linearGradient id="g3" x1="0%" y1="0%" x2="100%" y2="0%"><stop offset="0%" stop-color="#38bdf8"/><stop offset="100%" stop-color="#34d399"/></linearGradient></defs><line x1="12" y1="1" x2="12" y2="23"/><path d="M17 5H9.5a3.5 3.5 0 000 7h5a3.5 3.5 0 010 7H6"/></svg> Salary Insights</div>""", unsafe_allow_html=True)
    for role in JOB_MARKET_INSIGHTS["salary_insights"]:
        st.markdown(f"""
        <div class="insight-card">
            <h4 style="color:#34d399; display:flex; align-items:center; gap:7px;">
                <svg xmlns="http://www.w3.org/2000/svg" width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="#34d399" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><rect x="2" y="7" width="20" height="14" rx="2"/><path d="M16 21V5a2 2 0 00-2-2h-4a2 2 0 00-2 2v16"/></svg>
                {role['role']}
            </h4>
            <p style="margin-bottom:5px !important;">
                Experience: <span style="color:#7dd3fc; font-weight:600;">{role['experience']}</span>
            </p>
            <p>Salary Range: <span style="color:#34d399; font-weight:700;">{role['range']}</span></p>
        </div>
        """, unsafe_allow_html=True)
