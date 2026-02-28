import os
os.environ["STREAMLIT_WATCHDOG"] = "false"
import json
import random
import string
import re
import asyncio
import io
import urllib.parse
import base64
from io import BytesIO
from collections import Counter
from datetime import datetime
import time

# Third-party library imports
import streamlit as st
import streamlit.components.v1 as components
from base64 import b64encode
import requests
import fitz
import numpy as np
import pandas as pd
import matplotlib.pyplot as plt
import altair as alt
from PIL import Image
from pdf2image import convert_from_path
from dotenv import load_dotenv
from nltk.stem import WordNetLemmatizer
from docx import Document
from docx.shared import Pt, RGBColor, Inches
from docx.oxml import OxmlElement
from docx.oxml.ns import qn
from docx.opc.constants import RELATIONSHIP_TYPE as RT
from xhtml2pdf import pisa
from pydantic import BaseModel
from streamlit_pdf_viewer import pdf_viewer

# Heavy libraries - loaded with caching
import torch

# Langchain & Embeddings

from langchain_text_splitters import CharacterTextSplitter 
from langchain_community.vectorstores import FAISS 
from langchain_community.embeddings import HuggingFaceEmbeddings 
from langchain_groq import ChatGroq  # optional if you're using it













# Local project imports
from llm_manager import call_llm, load_groq_api_keys
from db_manager import (
    db_manager,
    insert_candidate,
    get_top_domains_by_score,
    get_database_stats,
    detect_domain_from_title_and_description,
    get_domain_similarity
)
from user_login import (
    create_user_table,
    add_user,
    complete_registration,
    verify_user,
    get_logins_today,
    get_total_registered_users,
    log_user_action,
    username_exists,
    email_exists,
    is_valid_email,
    save_user_api_key,
    get_user_api_key,
    get_all_user_logs,
    generate_otp,
    send_email_otp,
    get_user_by_email,
    update_password_by_email,
    is_strong_password,
    domain_has_mx_record
)

# ============================================================
# 💾 Persistent Storage Configuration for Streamlit Cloud
# ============================================================
os.makedirs(".streamlit_storage", exist_ok=True)
DB_PATH = os.path.join(".streamlit_storage", "resume_data.db")

def html_to_pdf_bytes(html_string):
    styled_html = f"""
    <html>
    <head>
        <meta charset="UTF-8">
        <style>
            @page {{
                size: 400mm 297mm;  /* Original custom large page size */
                margin-top: 10mm;
                margin-bottom: 10mm;
                margin-left: 10mm;
                margin-right: 10mm;
            }}
            body {{
                font-size: 14pt;
                font-family: "Segoe UI", "Helvetica", sans-serif;
                line-height: 1.5;
                color: #000;
            }}
            h1, h2, h3 {{
                color: #2f4f6f;
            }}
            table {{
                width: 100%;
                border-collapse: collapse;
                margin-bottom: 15px;
            }}
            td {{
                padding: 4px;
                vertical-align: top;
                border: 1px solid #ccc;
            }}
            .section-title {{
                background-color: #e0e0e0;
                font-weight: bold;
                padding: 6px;
                margin-top: 10px;
            }}
            .box {{
                padding: 8px;
                margin-top: 6px;
                background-color: #f9f9f9;
                border-left: 4px solid #999;  /* More elegant than full border */
            }}
            ul {{
                margin: 0.5em 0;
                padding-left: 1.5em;
            }}
            li {{
                margin-bottom: 5px;
            }}
        </style>
    </head>
    <body>
        {html_string}
    </body>
    </html>
    """

    pdf_io = BytesIO()
    pisa.CreatePDF(styled_html, dest=pdf_io)
    pdf_io.seek(0)
    return pdf_io

def generate_cover_letter_from_resume_builder():
    name = st.session_state.get("name", "")
    job_title = st.session_state.get("job_title", "")
    summary = st.session_state.get("summary", "")
    skills = st.session_state.get("skills", "")
    location = st.session_state.get("location", "")
    today_date = datetime.today().strftime("%B %d, %Y")

    # ✅ Input boxes for contact info
    company = st.text_input("🏢 Target Company", placeholder="e.g., Google")
    linkedin = st.text_input("🔗 LinkedIn URL", placeholder="e.g., https://linkedin.com/in/username")
    email = st.text_input("📧 Email", placeholder="e.g., you@example.com")
    mobile = st.text_input("📞 Mobile Number", placeholder="e.g., +91 9876543210")

    # ✅ Button to prevent relooping
    if st.button("✉️ Generate Cover Letter"):
        # ✅ Validate input before generating
        if not all([name, job_title, summary, skills, company, linkedin, email, mobile]):
            st.warning("⚠️ Please fill in all fields including LinkedIn, email, and mobile.")
            return

        prompt = f"""
You are a world-class executive cover letter writer with 20+ years of experience helping candidates land roles at top-tier companies.

Write a compelling, personalized cover letter using the candidate information below.

COVER LETTER STRUCTURE:
1. **Header** — Date, Hiring Manager, Company Name
2. **Opening Paragraph** — Hook with specific value proposition; mention the role and why this company specifically
3. **Core Value Paragraph** — Top 2 achievements from their background (quantified if possible); connect directly to company's likely needs
4. **Skills-Fit Paragraph** — Bridge candidate skills to the role requirements; show cultural awareness
5. **Closing Paragraph** — Confident call to action; express enthusiasm; professional closing

TONE: Professional, confident, specific — NOT generic. Avoid clichés like "I am passionate about..." or "I believe I would be a great fit."
INCLUDE the contact block at the very top: Name, LinkedIn, Email, Phone.
ENSURE company name appears only once (in the header or salutation).
LENGTH: 3 short-to-medium paragraphs. Maximum 350 words.

### CANDIDATE DETAILS:
- Full Name: {name}
- Job Title Applying For: {job_title}
- Professional Summary: {summary}
- Key Skills: {skills}
- Location: {location}
- Date: {today_date}

### COMPANY DETAILS:
- Target Company: {company}
- Candidate LinkedIn: {linkedin}
- Candidate Email: {email}
- Candidate Phone: {mobile}

### INSTRUCTIONS:
- Return PLAIN TEXT ONLY — no HTML, no markdown, no asterisks
- Do NOT mention company name more than once
- Make it feel tailored — not templated
- End with: "Sincerely," followed by the candidate's full name
"""

        # ✅ Call LLM
        cover_letter = call_llm(prompt, session=st.session_state).strip()

        # ✅ Store plain text
        st.session_state["cover_letter"] = cover_letter

        # ✅ Build HTML wrapper for preview (safe)
        cover_letter_html = f"""
        <div style="font-family: Georgia, serif; font-size: 13pt; line-height: 1.6; 
                    color: #000; background: #fff; padding: 25px; 
                    border-radius: 8px; box-shadow: 0px 2px 6px rgba(0,0,0,0.1); 
                    max-width: 800px; margin: auto;">
            <div style="text-align:center; margin-bottom:15px;">
                <div style="font-size:18pt; font-weight:bold; color:#003366;">{name}</div>
                <div style="font-size:14pt; color:#555;">{job_title}</div>
                <div style="font-size:10pt; margin-top:5px;">
                    <a href="{linkedin}" style="color:#003366;">{linkedin}</a><br/>
                    📧 {email} | 📞 {mobile}
                </div>
            </div>
            <hr/>
            <pre style="white-space: pre-wrap; font-family: Georgia, serif; font-size: 12pt; color:#000;">
{cover_letter}
            </pre>
        </div>
        """

        st.session_state["cover_letter_html"] = cover_letter_html

        # ✅ Show nicely in Streamlit
        st.markdown(cover_letter_html, unsafe_allow_html=True)

# ------------------- Initialize -------------------
# ✅ Initialize database in persistent storage
create_user_table()

# ------------------- Tab-Specific Notification System -------------------
if "login_notification" not in st.session_state:
    st.session_state.login_notification = {"type": None, "text": None, "expires": 0.0}
if "register_notification" not in st.session_state:
    st.session_state.register_notification = {"type": None, "text": None, "expires": 0.0}

def notify(tab, msg_type, text, duration=3.0):
    """Show auto-disappearing message for specific tab (login/register)."""
    notification_key = f"{tab}_notification"
    st.session_state[notification_key] = {
        "type": msg_type,
        "text": text,
        "expires": time.time() + duration,
    }

def render_notification(tab):
    """Render notification in a fixed center slot for specific tab (prevents button shifting)."""
    notification_key = f"{tab}_notification"
    notif = st.session_state[notification_key]

    # Always reserve space for notification (60px height)
    if notif["type"] and time.time() < notif["expires"]:
        # Show active notification
        if notif["type"] == "success":
            st.success(notif["text"])
        elif notif["type"] == "error":
            st.error(notif["text"])
        elif notif["type"] == "warning":
            st.warning(notif["text"])
        elif notif["type"] == "info":
            st.info(notif["text"])
    else:
        # Reserve space with empty div to prevent layout shift
        st.markdown("<div style='height:60px;'></div>", unsafe_allow_html=True)

def display_timer(remaining_seconds, expired=False, key_suffix=""):
    """
    Display a server-synced timer with glassmorphism styling.
    Server-side validation ensures OTP expiry is accurately enforced.

    Args:
        remaining_seconds: Time remaining in seconds (server-calculated)
        expired: Whether the timer has expired
        key_suffix: Unique suffix for the timer component
    """
    minutes = remaining_seconds // 60
    seconds = remaining_seconds % 60

    if expired or remaining_seconds <= 0:
        st.markdown("""
        <div class='timer-display timer-expired' style="
            background: linear-gradient(135deg, rgba(255, 99, 71, 0.18) 0%, rgba(255, 99, 71, 0.08) 100%);
            backdrop-filter: blur(15px);
            -webkit-backdrop-filter: blur(15px);
            border: 2px solid rgba(255, 99, 71, 0.4);
            border-radius: 14px;
            padding: 16px 24px;
            margin: 20px 0;
            text-align: center;
            box-shadow: 0 4px 20px rgba(255, 99, 71, 0.15), inset 0 1px 0 rgba(255, 255, 255, 0.1);
        ">
            <span class='timer-text' style="
                color: #FF6347;
                font-size: 1.15em;
                font-weight: bold;
                font-family: 'Orbitron', sans-serif;
                text-shadow: 0 0 18px rgba(255, 99, 71, 0.5);
            ">⏱️ OTP Expired</span>
        </div>
        """, unsafe_allow_html=True)
    else:
        # Client-side countdown for UX, but server validates on action
        st.components.v1.html(f"""
        <div class='timer-display' id='timer-{key_suffix}' style="
            background: linear-gradient(135deg, rgba(255, 215, 0, 0.18) 0%, rgba(255, 165, 0, 0.08) 100%);
            backdrop-filter: blur(15px);
            -webkit-backdrop-filter: blur(15px);
            border: 2px solid rgba(255, 215, 0, 0.4);
            border-radius: 14px;
            padding: 16px 24px;
            margin: 20px 0;
            text-align: center;
            box-shadow: 0 4px 20px rgba(255, 215, 0, 0.15), inset 0 1px 0 rgba(255, 255, 255, 0.1);
        ">
            <span class='timer-text' style="
                color: #FFD700;
                font-size: 1.15em;
                font-weight: bold;
                font-family: 'Orbitron', sans-serif;
                text-shadow: 0 0 18px rgba(255, 215, 0, 0.5);
            ">⏱️ Time Remaining: <span id='countdown-{key_suffix}'>{minutes:02d}:{seconds:02d}</span></span>
        </div>
        <script>
        (function() {{
            let remaining = {remaining_seconds};
            const countdownEl = document.getElementById('countdown-{key_suffix}');
            const timerEl = document.getElementById('timer-{key_suffix}');

            const interval = setInterval(() => {{
                remaining--;
                if (remaining <= 0) {{
                    clearInterval(interval);
                    if (timerEl) {{
                        timerEl.style.background = 'linear-gradient(135deg, rgba(255, 99, 71, 0.18) 0%, rgba(255, 99, 71, 0.08) 100%)';
                        timerEl.style.border = '2px solid rgba(255, 99, 71, 0.4)';
                        timerEl.innerHTML = "<span style='color: #FF6347; font-size: 1.15em; font-weight: bold; font-family: Orbitron, sans-serif; text-shadow: 0 0 18px rgba(255, 99, 71, 0.5);'>⏱️ OTP Expired</span>";
                    }}
                }} else {{
                    const mins = Math.floor(remaining / 60);
                    const secs = remaining % 60;
                    if (countdownEl) {{
                        countdownEl.textContent = `${{mins.toString().padStart(2, '0')}}:${{secs.toString().padStart(2, '0')}}`;
                    }}
                }}
            }}, 1000);
        }})();
        </script>
        """, height=80)

# ------------------- Initialize Session State -------------------
if "authenticated" not in st.session_state:
    st.session_state.authenticated = False
if "username" not in st.session_state:
    st.session_state.username = None
if "processed_files" not in st.session_state:
    st.session_state.processed_files = set()

# Forgot password session states
if "reset_stage" not in st.session_state:
    st.session_state.reset_stage = "none"
if "reset_email" not in st.session_state:
    st.session_state.reset_email = ""
if "reset_otp" not in st.session_state:
    st.session_state.reset_otp = ""
if "reset_otp_time" not in st.session_state:
    st.session_state.reset_otp_time = 0

# Live validation session states for register tab
if "last_validated_email" not in st.session_state:
    st.session_state.last_validated_email = ""
if "last_validated_username" not in st.session_state:
    st.session_state.last_validated_username = ""
if "last_validated_password" not in st.session_state:
    st.session_state.last_validated_password = ""

# ------------------- CSS Styling -------------------
st.markdown("""
<style>
body, .main {
    background-color: #0d1117;
    color: white;
}

/* Smooth fade animation for notifications */
div.stAlert {
    border-radius: 12px;
    padding: 10px 14px;
    animation: fadein 0.3s, fadeout 0.3s 2.7s;
    text-align: center;
}
@keyframes fadein { from {opacity: 0;} to {opacity: 1;} }
@keyframes fadeout { from {opacity: 1;} to {opacity: 0;} }

.login-card {
    background: #161b22;
    padding: 30px;
    border-radius: 20px;
    box-shadow: 0 0 25px rgba(0,0,0,0.3);
    transition: all 0.4s ease;
}
.login-card:hover {
    transform: translateY(-6px) scale(1.01);
    box-shadow: 0 0 45px rgba(0,255,255,0.25);
}
.stTextInput > div > input {
    background-color: #0d1117;
    color: white;
    border: 1px solid #30363d;
    border-radius: 10px;
    padding: 0.6em;
}
.stTextInput > div > input:hover {
    border: 1px solid #00BFFF;
    box-shadow: 0 0 8px rgba(0,191,255,0.2);
}
.stTextInput > label {
    color: #c9d1d9;
}
.stButton > button {
    background-color: #238636;
    color: white;
    border-radius: 10px;
    padding: 0.6em 1.5em;
    border: none;
    font-weight: bold;
}
.stButton > button:hover {
    background-color: #2ea043;
    box-shadow: 0 0 10px rgba(46,160,67,0.4);
    transform: scale(1.02);
}
.feature-card {
    background: radial-gradient(circle at top left, #1f2937, #111827);
    padding: 20px;
    border-radius: 15px;
    box-shadow: 0 0 20px rgba(0,255,255,0.1);
    text-align: center;
    transition: transform 0.3s ease, box-shadow 0.3s ease;
    color: #fff;
    margin-bottom: 20px;
}
.feature-card:hover {
    transform: translateY(-10px);
    box-shadow: 0 0 30px rgba(0,255,255,0.4);
}
.feature-card h3 {
    color: #00BFFF;
}
.feature-card p {
    color: #c9d1d9;
}
</style>
""", unsafe_allow_html=True)
# 🔹 VIDEO BACKGROUND & GLOW TEXT

# ------------------- BEFORE LOGIN -------------------
if not st.session_state.authenticated:
    

    # -------- Sidebar --------
    with st.sidebar:
        st.markdown("<h1 style='color:#00BFFF;'>Smart Resume AI</h1>", unsafe_allow_html=True)
        st.markdown("<p style='color:#c9d1d9;'>Transform your career with AI-powered resume analysis, job matching, and smart insights.</p>", unsafe_allow_html=True)

        features = [
            ("https://img.icons8.com/fluency/48/resume.png", "Resume Analyzer", "Get feedback, scores, and tips powered by AI along with the biased words detection and rewriting the resume in an inclusive way."),
            ("https://img.icons8.com/fluency/48/resume-website.png", "Resume Builder", "Build modern, eye-catching resumes easily."),
            ("https://img.icons8.com/fluency/48/job.png", "Job Search", "Find tailored job matches."),
            ("https://img.icons8.com/fluency/48/classroom.png", "Course Suggestions", "Get upskilling recommendations based on your goals."),
            ("https://img.icons8.com/fluency/48/combo-chart.png", "Interactive Dashboard", "Visualize trends, scores, and analytics."),
        ]

        for icon, title, desc in features:
            st.markdown(f"""
            <div class="feature-card">
                <img src="{icon}" width="40"/>
                <h3>{title}</h3>
                <p>{desc}</p>
            </div>
            """, unsafe_allow_html=True)

    # -------- Animated Cards --------
    image_url = "https://cdn-icons-png.flaticon.com/512/3135/3135768.png"
    response = requests.get(image_url)
    img_base64 = b64encode(response.content).decode()

    st.markdown(f"""
    <style>
    .animated-cards {{
      margin-top: 30px;
      display: flex;
      justify-content: center;
      position: relative;
      height: 300px;
    }}
    .animated-cards img {{
      position: absolute;
      width: 240px;
      animation: splitCards 2.5s ease-in-out infinite alternate;
      z-index: 1;
    }}
    .animated-cards img:nth-child(1) {{ animation-delay: 0s; z-index: 3; }}
    .animated-cards img:nth-child(2) {{ animation-delay: 0.3s; z-index: 2; }}
    .animated-cards img:nth-child(3) {{ animation-delay: 0.6s; z-index: 1; }}
    @keyframes splitCards {{
      0% {{ transform: scale(1) translateX(0) rotate(0deg); opacity: 1; }}
      100% {{ transform: scale(1) translateX(var(--x-offset)) rotate(var(--rot)); opacity: 1; }}
    }}
    .card-left {{ --x-offset: -80px; --rot: -5deg; }}
    .card-center {{ --x-offset: 0px; --rot: 0deg; }}
    .card-right {{ --x-offset: 80px; --rot: 5deg; }}
    </style>
    <div class="animated-cards">
        <img class="card-left" src="data:image/png;base64,{img_base64}" />
        <img class="card-center" src="data:image/png;base64,{img_base64}" />
        <img class="card-right" src="data:image/png;base64,{img_base64}" />
    </div>
    """, unsafe_allow_html=True)

    # -------- Counter Section (Updated Layout & Style with glassmorphism and shimmer) --------

    # Fetch counters
    total_users = get_total_registered_users()
    active_logins = get_logins_today()
    stats = get_database_stats()

# Replace static 15 with dynamic count
    resumes_uploaded = stats.get("total_candidates", 0)

    active_domains = stats.get("unique_domains", 0)


    glassmorphism_counter_style = """
    <style>
    @keyframes shimmer {
        0% { background-position: -200% 0; }
        100% { background-position: 200% 0; }
    }
    
    @keyframes float {
        0%, 100% { transform: translateY(0px); }
        50% { transform: translateY(-5px); }
    }

    .counter-grid {
        display: grid;
        grid-template-columns: repeat(2, 250px);
        column-gap: 40px;
        row-gap: 25px;
        justify-content: center;
        padding: 30px 10px;
        max-width: 600px;
        margin: 0 auto;
    }

    .counter-box {
        background: linear-gradient(135deg, 
            rgba(0, 191, 255, 0.1) 0%, 
            rgba(30, 144, 255, 0.05) 50%, 
            rgba(0, 191, 255, 0.1) 100%);
        backdrop-filter: blur(15px);
        -webkit-backdrop-filter: blur(15px);
        border: 1px solid rgba(0, 191, 255, 0.2);
        border-radius: 16px;
        width: 100%;
        height: 120px;
        display: flex;
        flex-direction: column;
        justify-content: center;
        align-items: center;
        position: relative;
        overflow: hidden;
        transition: all 0.3s ease;
        animation: float 3s ease-in-out infinite;
    }

    .counter-box::before {
        content: '';
        position: absolute;
        top: 0;
        left: -100%;
        width: 100%;
        height: 100%;
        background: linear-gradient(
            90deg,
            transparent,
            rgba(0, 191, 255, 0.3),
            transparent
        );
        animation: shimmer 2s infinite;
    }

    .counter-box:hover {
        transform: translateY(-8px) scale(1.02);
        background: linear-gradient(135deg, 
            rgba(0, 191, 255, 0.15) 0%, 
            rgba(30, 144, 255, 0.08) 50%, 
            rgba(0, 191, 255, 0.15) 100%);
        border: 1px solid rgba(0, 191, 255, 0.4);
        box-shadow: 
            0 20px 40px rgba(0, 191, 255, 0.1),
            inset 0 1px 0 rgba(255, 255, 255, 0.1);
    }

    .counter-box:nth-child(1) { animation-delay: 0s; }
    .counter-box:nth-child(2) { animation-delay: 0.5s; }
    .counter-box:nth-child(3) { animation-delay: 1s; }
    .counter-box:nth-child(4) { animation-delay: 1.5s; }

    .counter-number {
        font-size: 2.2em;
        font-weight: bold;
        color: #00BFFF;
        margin: 0;
        position: relative;
        z-index: 2;
        text-shadow: 0 0 20px rgba(0, 191, 255, 0.5);
    }

    .counter-label {
        margin-top: 8px;
        font-size: 1em;
        color: #c9d1d9;
        position: relative;
        z-index: 2;
        text-shadow: 0 1px 2px rgba(0, 0, 0, 0.3);
    }
    </style>
    """

    st.markdown(glassmorphism_counter_style, unsafe_allow_html=True)

    st.markdown(f"""
    <div class="counter-grid">
        <div class="counter-box">
            <div class="counter-number">{total_users}</div>
            <div class="counter-label">Total Users</div>
        </div>
        <div class="counter-box">
            <div class="counter-number">{active_domains}</div>
            <div class="counter-label">Active Domains</div>
        </div>
        <div class="counter-box">
            <div class="counter-number">{resumes_uploaded}</div>
            <div class="counter-label">Resumes Uploaded</div>
        </div>
        <div class="counter-box">
            <div class="counter-number">{active_logins}</div>
            <div class="counter-label">Active Sessions</div>
        </div>
    </div>
    """, unsafe_allow_html=True)

if not st.session_state.get("authenticated", False):

    # ✅ Futuristic silhouette
    image_url = "https://cdn-icons-png.flaticon.com/512/4140/4140047.png"
    response = requests.get(image_url)
    img_base64 = b64encode(response.content).decode()

    # ✅ Inject glassmorphism CSS with shimmer effects
    st.markdown(f"""
    <style>
    @import url('https://fonts.googleapis.com/css2?family=Orbitron:wght@600&display=swap');

    @keyframes shimmer {{
        0% {{ background-position: -200% 0; }}
        100% {{ background-position: 200% 0; }}
    }}

    @keyframes glassShimmer {{
        0% {{ transform: translateX(-100%) skewX(-15deg); }}
        100% {{ transform: translateX(200%) skewX(-15deg); }}
    }}

    /* ===== Card Shuffle Animation ===== */
    .animated-cards {{
      margin-top: 40px;
      display: flex;
      justify-content: center;
      position: relative;
      height: 260px;
    }}
    .animated-cards img {{
      position: absolute;
      width: 220px;
      animation: splitCards 2.5s ease-in-out infinite alternate;
      z-index: 1;
      filter: drop-shadow(0 0 15px rgba(0,191,255,0.3));
    }}
    .animated-cards img:nth-child(1) {{ animation-delay: 0s; z-index: 3; }}
    .animated-cards img:nth-child(2) {{ animation-delay: 0.3s; z-index: 2; }}
    .animated-cards img:nth-child(3) {{ animation-delay: 0.6s; z-index: 1; }}

    @keyframes splitCards {{
      0%   {{ transform: scale(1) translateX(0) rotate(0deg); opacity: 1; }}
      100% {{ transform: scale(1) translateX(var(--x-offset)) rotate(var(--rot)); opacity: 1; }}
    }}
    .card-left   {{ --x-offset: -80px; --rot: -4deg; }}
    .card-center {{ --x-offset: 0px;  --rot: 0deg;  }}
    .card-right  {{ --x-offset: 80px;  --rot: 4deg;  }}

    /* ===== Glassmorphism Login Card ===== */
    .login-card {{
      background: linear-gradient(135deg,
        rgba(0, 191, 255, 0.1) 0%,
        rgba(30, 144, 255, 0.05) 50%,
        rgba(0, 191, 255, 0.1) 100%);
      backdrop-filter: blur(20px);
      -webkit-backdrop-filter: blur(20px);
      border: 1px solid rgba(0, 191, 255, 0.2);
      border-radius: 20px;
      padding: 25px;
      box-shadow:
        0 8px 32px rgba(0, 191, 255, 0.1),
        inset 0 1px 0 rgba(255, 255, 255, 0.1);
      font-family: 'Orbitron', sans-serif;
      color: white;
      margin-top: 20px;
      opacity: 0;
      transform: translateX(-120%);
      animation: slideInLeft 1.2s ease-out forwards;
      position: relative;
      overflow: hidden;
    }}

    .login-card::before {{
      content: '';
      position: absolute;
      top: 0;
      left: -100%;
      width: 100%;
      height: 100%;
      background: linear-gradient(
        90deg,
        transparent,
        rgba(0, 191, 255, 0.2),
        transparent
      );
      animation: glassShimmer 3s infinite;
    }}

    @keyframes slideInLeft {{
      0%   {{ transform: translateX(-120%); opacity: 0; }}
      100% {{ transform: translateX(0); opacity: 1; }}
    }}

    .login-card h2 {{
      text-align: center;
      font-size: 1.6rem;
      text-shadow: 0 0 15px rgba(0, 191, 255, 0.5);
      margin-bottom: 15px;
      position: relative;
      z-index: 2;
    }}
    .login-card h2 span {{ color: #00BFFF; }}

    /* ===== Enhanced Message Cards with Consistent Layout ===== */
    .slide-message {{
      position: relative;
      overflow: hidden;
      margin: 16px 0;
      padding: 14px 20px;
      border-radius: 14px;
      font-weight: 600;
      font-size: 0.95em;
      display: flex;
      align-items: center;
      justify-content: flex-start;
      gap: 12px;
      animation: slideIn 0.6s cubic-bezier(0.34, 1.56, 0.64, 1) forwards;
      backdrop-filter: blur(15px);
      -webkit-backdrop-filter: blur(15px);
      box-shadow:
        0 4px 20px rgba(0, 0, 0, 0.15),
        inset 0 1px 0 rgba(255, 255, 255, 0.1);
      width: 100%;
      max-width: 100%;
      box-sizing: border-box;
      line-height: 1.5;
      font-family: 'Orbitron', sans-serif;
      transition: all 0.3s cubic-bezier(0.4, 0, 0.2, 1);
      min-height: 50px;
    }}

    .slide-message:hover {{
      transform: translateY(-3px) scale(1.01);
      box-shadow:
        0 8px 30px rgba(0, 0, 0, 0.25),
        inset 0 1px 0 rgba(255, 255, 255, 0.15);
    }}

    .slide-message::before {{
      content: '';
      position: absolute;
      top: 0;
      left: -100%;
      width: 100%;
      height: 100%;
      background: linear-gradient(
        90deg,
        transparent,
        rgba(255, 255, 255, 0.1),
        transparent
      );
      transition: left 0.5s;
    }}

    .slide-message:hover::before {{
      left: 100%;
    }}

    .slide-message svg {{
      width: 22px;
      height: 22px;
      flex-shrink: 0;
      filter: drop-shadow(0 0 6px currentColor);
      z-index: 2;
    }}

    .slide-message-text {{
      flex: 1;
      z-index: 2;
      position: relative;
      word-wrap: break-word;
      overflow-wrap: break-word;
      white-space: normal;
    }}

    .success-msg {{
      background: linear-gradient(135deg,
        rgba(0, 255, 127, 0.20) 0%,
        rgba(0, 255, 127, 0.08) 100%);
      border: 2px solid rgba(0, 255, 127, 0.4);
      color: #00FF7F;
      text-shadow: 0 0 12px rgba(0, 255, 127, 0.4);
    }}

    .error-msg {{
      background: linear-gradient(135deg,
        rgba(255, 99, 71, 0.20) 0%,
        rgba(255, 99, 71, 0.08) 100%);
      border: 2px solid rgba(255, 99, 71, 0.4);
      color: #FF6347;
      text-shadow: 0 0 12px rgba(255, 99, 71, 0.4);
    }}

    .info-msg {{
      background: linear-gradient(135deg,
        rgba(30, 144, 255, 0.20) 0%,
        rgba(30, 144, 255, 0.08) 100%);
      border: 2px solid rgba(30, 144, 255, 0.4);
      color: #1E90FF;
      text-shadow: 0 0 12px rgba(30, 144, 255, 0.4);
    }}

    .warn-msg {{
      background: linear-gradient(135deg,
        rgba(255, 215, 0, 0.20) 0%,
        rgba(255, 215, 0, 0.08) 100%);
      border: 2px solid rgba(255, 215, 0, 0.4);
      color: #FFD700;
      text-shadow: 0 0 12px rgba(255, 215, 0, 0.4);
    }}

    @keyframes slideIn {{
      0%   {{
        transform: translateX(-50px);
        opacity: 0;
      }}
      100% {{
        transform: translateX(0);
        opacity: 1;
      }}
    }}

    /* ===== Improved Timer Display ===== */
    .timer-display {{
      background: linear-gradient(135deg,
        rgba(255, 215, 0, 0.18) 0%,
        rgba(255, 165, 0, 0.08) 100%);
      backdrop-filter: blur(15px);
      -webkit-backdrop-filter: blur(15px);
      border: 2px solid rgba(255, 215, 0, 0.4);
      border-radius: 14px;
      padding: 16px 24px;
      margin: 20px 0;
      text-align: center;
      box-shadow:
        0 4px 20px rgba(255, 215, 0, 0.15),
        inset 0 1px 0 rgba(255, 255, 255, 0.1);
      transition: all 0.3s cubic-bezier(0.4, 0, 0.2, 1);
      position: relative;
      overflow: hidden;
    }}

    .timer-display::before {{
      content: '';
      position: absolute;
      top: 0;
      left: -100%;
      width: 100%;
      height: 100%;
      background: linear-gradient(
        90deg,
        transparent,
        rgba(255, 215, 0, 0.2),
        transparent
      );
      animation: glassShimmer 3s infinite;
    }}

    .timer-display:hover {{
      box-shadow:
        0 8px 30px rgba(255, 215, 0, 0.25),
        inset 0 1px 0 rgba(255, 255, 255, 0.15);
      transform: translateY(-3px);
    }}

    .timer-text {{
      color: #FFD700;
      font-size: 1.15em;
      font-weight: bold;
      font-family: 'Orbitron', sans-serif;
      text-shadow: 0 0 18px rgba(255, 215, 0, 0.5);
      position: relative;
      z-index: 2;
    }}

    .timer-expired {{
      background: linear-gradient(135deg,
        rgba(255, 99, 71, 0.18) 0%,
        rgba(255, 99, 71, 0.08) 100%);
      border: 2px solid rgba(255, 99, 71, 0.4);
    }}

    .timer-expired .timer-text {{
      color: #FF6347;
      text-shadow: 0 0 18px rgba(255, 99, 71, 0.5);
    }}

    /* ===== Glassmorphism Buttons ===== */
    .stButton>button {{
      background: linear-gradient(135deg, 
        rgba(0, 191, 255, 0.2) 0%, 
        rgba(30, 144, 255, 0.1) 100%);
      backdrop-filter: blur(15px);
      -webkit-backdrop-filter: blur(15px);
      color: white;
      border: 1px solid rgba(0, 191, 255, 0.3);
      border-radius: 12px;
      font-family: 'Orbitron', sans-serif;
      font-weight: bold;
      padding: 8px 20px;
      box-shadow: 
        0 4px 16px rgba(0, 191, 255, 0.1),
        inset 0 1px 0 rgba(255, 255, 255, 0.1);
      transition: all 0.3s ease;
      position: relative;
      overflow: hidden;
    }}
    
    .stButton>button::before {{
      content: '';
      position: absolute;
      top: 0;
      left: -100%;
      width: 100%;
      height: 100%;
      background: linear-gradient(
        90deg,
        transparent,
        rgba(255, 255, 255, 0.2),
        transparent
      );
      transition: left 0.5s;
    }}
    
    .stButton>button:hover {{
      transform: translateY(-2px);
      background: linear-gradient(135deg, 
        rgba(0, 191, 255, 0.3) 0%, 
        rgba(30, 144, 255, 0.15) 100%);
      border: 1px solid rgba(0, 191, 255, 0.5);
      box-shadow: 
        0 8px 25px rgba(0, 191, 255, 0.2),
        inset 0 1px 0 rgba(255, 255, 255, 0.2);
    }}
    
    .stButton>button:hover::before {{
      left: 100%;
    }}

    /* ===== Glassmorphism Input Fields ===== */
    .stTextInput input {{
      background: linear-gradient(135deg, 
        rgba(0, 191, 255, 0.08) 0%, 
        rgba(30, 144, 255, 0.04) 100%);
      backdrop-filter: blur(15px);
      -webkit-backdrop-filter: blur(15px);
      border: 1px solid rgba(0, 191, 255, 0.2);
      border-radius: 10px;
      padding: 10px;
      color: #E0F7FF;
      font-family: 'Orbitron', sans-serif;
      box-shadow: 
        0 4px 16px rgba(0, 191, 255, 0.05),
        inset 0 1px 0 rgba(255, 255, 255, 0.05);
      transition: all 0.3s ease-in-out;
    }}
    .stTextInput input:focus {{
      outline: none !important;
      background: linear-gradient(135deg, 
        rgba(0, 191, 255, 0.12) 0%, 
        rgba(30, 144, 255, 0.06) 100%);
      border: 1px solid rgba(0, 191, 255, 0.4);
      box-shadow: 
        0 8px 25px rgba(0, 191, 255, 0.15),
        inset 0 1px 0 rgba(255, 255, 255, 0.1);
      transform: translateY(-1px);
    }}
    .stTextInput label {{
      font-family: 'Orbitron', sans-serif;
      color: #00BFFF !important;
      text-shadow: 0 0 10px rgba(0, 191, 255, 0.3);
    }}
    </style>

    <!-- Animated Cards -->
    <div class="animated-cards">
        <img class="card-left" src="data:image/png;base64,{img_base64}" />
        <img class="card-center" src="data:image/png;base64,{img_base64}" />
        <img class="card-right" src="data:image/png;base64,{img_base64}" />
    </div>
    """, unsafe_allow_html=True)

    # -------- Login/Register Layout --------
    left, center, right = st.columns([1, 2, 1])

    with center:
        st.markdown(
            "<div class='login-card'><h2 style='text-align:center;'>🔐 Login to <span style='color:#00BFFF;'>HIRELYZER</span></h2>",
            unsafe_allow_html=True,
        )

        login_tab, register_tab = st.tabs(["Login", "Register"])

        # ---------------- LOGIN TAB ----------------
        with login_tab:
            # Show login or forgot password flow based on reset_stage
            if st.session_state.reset_stage == "none":
                # Normal Login UI
                st.markdown("<h3 style='color:#00BFFF; text-align:center;'>🔐 Login to Your Account</h3>", unsafe_allow_html=True)

                user = st.text_input("👤 Username or Email", key="login_user")
                pwd = st.text_input("🔑 Password", type="password", key="login_pass")

                # Render notification area (reserves space)
                render_notification("login")

                if st.button("🚀 Login", key="login_btn", use_container_width=True):
                    success, saved_key = verify_user(user.strip(), pwd.strip())
                    if success:
                        st.session_state.authenticated = True
                        # username is already set in session by verify_user()
                        if saved_key:
                            st.session_state["user_groq_key"] = saved_key
                        log_user_action(st.session_state.username, "login")

                        notify("login", "success", "✅ Login successful!")
                        time.sleep(3.0)
                        st.rerun()
                    else:
                        notify("login", "error", "❌ Invalid credentials. Please try again.")
                        st.rerun()

                st.markdown("<br>", unsafe_allow_html=True)

                # Forgot Password Link
                if st.button("🔑 Forgot Password?", key="forgot_pw_link"):
                    st.session_state.reset_stage = "request_email"
                    st.rerun()

            # ============================================================
            # FORGOT PASSWORD FLOW - Stage 1: Request Email
            # ============================================================
            elif st.session_state.reset_stage == "request_email":
                st.markdown("<h3 style='color:#00BFFF; text-align:center;'>🔐 Reset Password</h3>", unsafe_allow_html=True)
                st.markdown("<p style='color:#c9d1d9; text-align:center;'>Enter your registered email to receive an OTP</p>", unsafe_allow_html=True)

                email_input = st.text_input("📧 Email Address", key="reset_email_input")

                # Render notification area (reserves space)
                render_notification("login")

                col1, col2 = st.columns(2)
                with col1:
                    if st.button("📤 Send OTP", key="send_otp_btn", use_container_width=True):
                        if email_input.strip():
                            if get_user_by_email(email_input.strip()):
                                # Generate and send OTP
                                otp = generate_otp()
                                success = send_email_otp(email_input.strip(), otp)

                                if success:
                                    st.session_state.reset_email = email_input.strip()
                                    st.session_state.reset_otp = otp
                                    st.session_state.reset_otp_time = time.time()
                                    st.session_state.reset_stage = "verify_otp"

                                    notify("login", "success", "✅ OTP sent successfully to your email!")
                                    time.sleep(0.5)
                                    st.rerun()
                                else:
                                    notify("login", "error", "❌ Failed to send OTP. Please try again.")
                                    st.rerun()
                            else:
                                notify("login", "error", "❌ Email not found. Please register first.")
                                st.rerun()
                        else:
                            notify("login", "warning", "⚠️ Please enter your email address.")
                            st.rerun()

                with col2:
                    if st.button("↩️ Back to Login", key="back_to_login_1", use_container_width=True):
                        st.session_state.reset_stage = "none"
                        st.rerun()

            # ============================================================
            # FORGOT PASSWORD FLOW - Stage 2: Verify OTP
            # ============================================================
            elif st.session_state.reset_stage == "verify_otp":
                st.markdown("<h3 style='color:#00BFFF; text-align:center;'>📩 Verify OTP</h3>", unsafe_allow_html=True)
                st.markdown(f"<p style='color:#c9d1d9; text-align:center;'>Enter the 6-digit OTP sent to <strong>{st.session_state.reset_email}</strong></p>", unsafe_allow_html=True)

                # Calculate elapsed and remaining time (server-side)
                elapsed_time = time.time() - st.session_state.reset_otp_time
                remaining_time = max(0, int(180 - elapsed_time))

                # Display timer
                display_timer(remaining_time, expired=(remaining_time == 0), key_suffix="forgot_pw")

                # Check if OTP expired (3 minutes)
                if remaining_time == 0:
                    # OTP Expired - Show resend option
                    render_notification("login")
                    notify("login", "error", "⏱️ OTP expired. Please request a new one.")

                    col1, col2 = st.columns(2)
                    with col1:
                        if st.button("🔄 Resend OTP", key="resend_otp_btn", use_container_width=True):
                            # Generate new OTP
                            otp = generate_otp()
                            success = send_email_otp(st.session_state.reset_email, otp)

                            if success:
                                st.session_state.reset_otp = otp
                                st.session_state.reset_otp_time = time.time()
                                notify("login", "info", "📨 New OTP sent!")
                                time.sleep(0.5)
                                st.rerun()
                            else:
                                notify("login", "error", "❌ Failed to send OTP. Please try again.")
                                st.rerun()

                    with col2:
                        if st.button("↩️ Back to Login", key="back_to_login_expired", use_container_width=True):
                            st.session_state.reset_stage = "none"
                            st.rerun()
                else:
                    # OTP still valid - Show verification form
                    otp_input = st.text_input("🔢 Enter 6-Digit OTP", key="otp_input", max_chars=6)

                    # Render notification area (reserves space)
                    render_notification("login")

                    col1, col2 = st.columns(2)
                    with col1:
                        if st.button("✅ Verify OTP", key="verify_otp_btn", use_container_width=True):
                            # Re-check expiry on server side before verifying
                            current_elapsed = time.time() - st.session_state.reset_otp_time
                            if current_elapsed >= 180:
                                notify("login", "error", "⏱️ OTP has expired. Please request a new one.")
                                st.rerun()
                            elif otp_input.strip() == st.session_state.reset_otp:
                                st.session_state.reset_stage = "reset_password"
                                notify("login", "success", "✅ OTP verified successfully!")
                                time.sleep(0.5)
                                st.rerun()
                            else:
                                notify("login", "error", "❌ Invalid OTP. Please try again.")
                                st.rerun()

                    with col2:
                        if st.button("↩️ Back to Login", key="back_to_login_2", use_container_width=True):
                            st.session_state.reset_stage = "none"
                            st.rerun()

            # ============================================================
            # FORGOT PASSWORD FLOW - Stage 3: Reset Password
            # ============================================================
            elif st.session_state.reset_stage == "reset_password":
                st.markdown("<h3 style='color:#00BFFF; text-align:center;'>🔐 Reset Password</h3>", unsafe_allow_html=True)
                st.markdown("<p style='color:#c9d1d9; text-align:center;'>Enter your new password</p>", unsafe_allow_html=True)

                new_password = st.text_input("🔑 New Password", type="password", key="new_password_input")
                confirm_password = st.text_input("🔑 Confirm Password", type="password", key="confirm_password_input")

                st.caption("Password must be at least 8 characters, include uppercase, lowercase, number, and special character.")

                # Render notification area (reserves space)
                render_notification("login")

                if st.button("✅ Reset Password", key="reset_password_btn", use_container_width=True):
                    if new_password.strip() and confirm_password.strip():
                        if new_password == confirm_password:
                            success = update_password_by_email(st.session_state.reset_email, new_password)

                            if success:
                                notify("login", "success", "✅ Password reset successful! Please log in again.")

                                # Log the password reset action
                                log_user_action(st.session_state.reset_email, "password_reset")

                                # Reset all forgot password session states
                                st.session_state.reset_stage = "none"
                                st.session_state.reset_email = ""
                                st.session_state.reset_otp = ""
                                st.session_state.reset_otp_time = 0

                                time.sleep(1)
                                st.rerun()
                            else:
                                notify("login", "error", "❌ Failed to reset password. Please try again.")
                                st.rerun()
                        else:
                            notify("login", "error", "❌ Passwords do not match.")
                            st.rerun()
                    else:
                        notify("login", "warning", "⚠️ Please fill in both password fields.")
                        st.rerun()

                if st.button("↩️ Back to Login", key="back_to_login_3"):
                    st.session_state.reset_stage = "none"
                    st.rerun()

        # ---------------- REGISTER TAB ----------------
        with register_tab:
            # Check if OTP was sent and pending verification
            if 'pending_registration' in st.session_state:
                st.markdown("<h3 style='color:#00BFFF; text-align:center;'>📧 Verify Your Email</h3>", unsafe_allow_html=True)
                st.markdown(f"<p style='color:#c9d1d9; text-align:center;'>Enter the 6-digit OTP sent to <strong>{st.session_state.pending_registration['email']}</strong></p>", unsafe_allow_html=True)

                # Calculate remaining time
                from datetime import datetime
                elapsed = (datetime.now(st.session_state.pending_registration['timestamp'].tzinfo) - st.session_state.pending_registration['timestamp']).total_seconds()
                remaining = max(0, 180 - int(elapsed))

                # Display timer
                display_timer(remaining, expired=(remaining == 0), key_suffix="register")

                if remaining == 0:
                    # OTP Expired
                    render_notification("register")
                    notify("register", "error", "⏱️ OTP expired. Please request a new one.")

                    col1, col2 = st.columns(2)
                    with col1:
                        if st.button("🔄 Resend OTP", key="reg_resend_expired_btn", use_container_width=True):
                            pending = st.session_state.pending_registration
                            success, message = add_user(pending['username'], pending['password'], pending['email'])
                            if success:
                                notify("register", "success", "✅ New OTP sent!")
                                time.sleep(0.5)
                                st.rerun()
                            else:
                                notify("register", "error", f"❌ {message}")
                                st.rerun()
                    with col2:
                        if st.button("↩️ Start Over", key="reg_start_over_btn", use_container_width=True):
                            del st.session_state.pending_registration
                            st.rerun()
                else:
                    # OTP still valid
                    otp_input = st.text_input("🔢 Enter 6-Digit OTP", key="reg_otp_input", max_chars=6)

                    # Render notification area (reserves space)
                    render_notification("register")

                    col1, col2, col3 = st.columns(3)
                    with col1:
                        if st.button("✅ Verify", key="verify_reg_otp_btn", use_container_width=True):
                            # Cache username BEFORE calling complete_registration
                            cached_username = st.session_state.pending_registration['username']

                            # Re-check expiry before verification
                            current_elapsed = (datetime.now(st.session_state.pending_registration['timestamp'].tzinfo) - st.session_state.pending_registration['timestamp']).total_seconds()
                            if current_elapsed >= 180:
                                notify("register", "error", "⏱️ OTP has expired. Please request a new one.")
                                st.rerun()
                            else:
                                success, message = complete_registration(otp_input.strip())
                                if success:
                                    notify("register", "success", message)
                                    log_user_action(cached_username, "register")
                                    time.sleep(0.5)
                                    st.rerun()
                                else:
                                    notify("register", "error", message)
                                    st.rerun()

                    with col2:
                        if st.button("🔄 Resend", key="resend_reg_otp_btn", use_container_width=True):
                            pending = st.session_state.pending_registration
                            success, message = add_user(pending['username'], pending['password'], pending['email'])
                            if success:
                                notify("register", "info", "📨 New OTP sent successfully!")
                                time.sleep(0.5)
                                st.rerun()
                            else:
                                notify("register", "error", f"❌ {message}")
                                st.rerun()

                    with col3:
                        if st.button("↩️ Back", key="back_to_reg_btn", use_container_width=True):
                            del st.session_state.pending_registration
                            st.rerun()

            else:
                # Normal registration form
                st.markdown("<h3 style='color:#00BFFF; text-align:center;'>🧾 Register New User</h3>", unsafe_allow_html=True)

                # Email input with live validation
                new_email = st.text_input("📧 Email", key="reg_email", placeholder="your@email.com")

                # Email validation placeholder (using st.empty for dynamic updates)
                email_validation_placeholder = st.empty()

                # Check if email changed and validate
                if new_email and new_email != st.session_state.last_validated_email:
                    if not is_valid_email(new_email.strip()):
                        with email_validation_placeholder:
                            st.markdown(
                                '<div class="slide-message warn-msg"><span class="slide-message-text">⚠️ Invalid email format.</span></div>',
                                unsafe_allow_html=True
                            )
                        st.session_state.last_validated_email = new_email
                    elif email_exists(new_email.strip()):
                        with email_validation_placeholder:
                            st.markdown(
                                '<div class="slide-message error-msg"><span class="slide-message-text">❌ Email already registered.</span></div>',
                                unsafe_allow_html=True
                            )
                        st.session_state.last_validated_email = new_email
                    else:
                        with email_validation_placeholder:
                            st.markdown(
                                '<div class="slide-message success-msg"><span class="slide-message-text">✅ Email is available.</span></div>',
                                unsafe_allow_html=True
                            )
                        st.session_state.last_validated_email = new_email
                        # Auto-hide after 3 seconds by clearing after delay
                        time.sleep(3)
                        email_validation_placeholder.empty()
                elif not new_email:
                    email_validation_placeholder.empty()
                    st.session_state.last_validated_email = ""

                # Username input with live validation
                new_user = st.text_input("👤 Username", key="reg_user")

                # Username validation placeholder
                username_validation_placeholder = st.empty()

                # Check if username changed and validate
                if new_user and new_user != st.session_state.last_validated_username:
                    if username_exists(new_user.strip()):
                        with username_validation_placeholder:
                            st.markdown(
                                '<div class="slide-message error-msg"><span class="slide-message-text">❌ Username already exists.</span></div>',
                                unsafe_allow_html=True
                            )
                        st.session_state.last_validated_username = new_user
                    else:
                        with username_validation_placeholder:
                            st.markdown(
                                '<div class="slide-message success-msg"><span class="slide-message-text">✅ Username is available.</span></div>',
                                unsafe_allow_html=True
                            )
                        st.session_state.last_validated_username = new_user
                        time.sleep(3)
                        username_validation_placeholder.empty()
                elif not new_user:
                    username_validation_placeholder.empty()
                    st.session_state.last_validated_username = ""

                # Password input with live validation
                new_pass = st.text_input("🔑 Password", type="password", key="reg_pass")
                st.caption("Password must be at least 8 characters, include uppercase, lowercase, number, and special character.")

                # Password validation placeholder
                password_validation_placeholder = st.empty()

                # Check if password changed and validate
                if new_pass and new_pass != st.session_state.last_validated_password:
                    if not is_strong_password(new_pass):
                        with password_validation_placeholder:
                            st.markdown(
                                '<div class="slide-message warn-msg"><span class="slide-message-text">⚠️ Password must be at least 8 characters and strong.</span></div>',
                                unsafe_allow_html=True
                            )
                        st.session_state.last_validated_password = new_pass
                    else:
                        with password_validation_placeholder:
                            st.markdown(
                                '<div class="slide-message success-msg"><span class="slide-message-text">✅ Strong password.</span></div>',
                                unsafe_allow_html=True
                            )
                        st.session_state.last_validated_password = new_pass
                        time.sleep(3)
                        password_validation_placeholder.empty()
                elif not new_pass:
                    password_validation_placeholder.empty()
                    st.session_state.last_validated_password = ""

                # Render notification area (reserves space)
                render_notification("register")

                if st.button("📧 Register & Send OTP", key="register_btn", use_container_width=True):
                    if new_email.strip() and new_user.strip() and new_pass.strip():
                        # Validate before attempting registration
                        if not is_valid_email(new_email.strip()):
                            notify("register", "warning", "⚠️ Invalid email format.")
                            st.rerun()
                        elif email_exists(new_email.strip()):
                            notify("register", "error", "🚫 Email already registered.")
                            st.rerun()
                        elif username_exists(new_user.strip()):
                            notify("register", "error", "🚫 Username already exists.")
                            st.rerun()
                        else:
                            success, message = add_user(new_user.strip(), new_pass.strip(), new_email.strip())
                            if success:
                                notify("register", "success", message)
                                time.sleep(0.5)
                                st.rerun()
                            else:
                                notify("register", "error", message)
                                st.rerun()
                    else:
                        notify("register", "warning", "⚠️ Please fill in all fields (email, username, and password).")
                        st.rerun()

        st.markdown("</div>", unsafe_allow_html=True)

    st.stop()

# ------------------- AFTER LOGIN -------------------
if st.session_state.get("authenticated"):
    st.markdown(
        f"<h2 style='color:#00BFFF;'>Welcome to HIRELYZER, <span style='color:white;'>{st.session_state.username}</span> 👋</h2>",
        unsafe_allow_html=True,
    )

    # 🔓 LOGOUT BUTTON
    if st.button("🚪 Logout"):
        log_user_action(st.session_state.get("username", "unknown"), "logout")

        # ✅ Clear all session keys safely
        for key in list(st.session_state.keys()):
            del st.session_state[key]

        st.success("✅ Logged out successfully.")
        st.rerun()  # Force rerun to prevent stale UI

    # 🔑 GROQ API KEY SECTION (SIDEBAR)
    st.sidebar.markdown("### 🔑 Groq API Key")

    # ✅ Load saved key from DB
    saved_key = get_user_api_key(st.session_state.username)
    masked_preview = f"****{saved_key[-6:]}" if saved_key else ""

    user_api_key_input = st.sidebar.text_input(
        "Your Groq API Key (Optional)",
        placeholder=masked_preview,
        type="password"
    )

    # ✅ Save or reuse key
    if user_api_key_input:
        st.session_state["user_groq_key"] = user_api_key_input
        save_user_api_key(st.session_state.username, user_api_key_input)
        st.sidebar.success("✅ New key saved and in use.")
    elif saved_key:
        st.session_state["user_groq_key"] = saved_key
        st.sidebar.info(f"ℹ️ Using your previously saved API key ({masked_preview})")
    else:
        st.sidebar.warning("⚠ Using shared admin key with possible usage limits")

    # 🧹 Clear saved key
    if st.sidebar.button("🗑️ Clear My API Key"):
        st.session_state["user_groq_key"] = None
        save_user_api_key(st.session_state.username, None)
        st.sidebar.success("✅ Cleared saved Groq API key. Now using shared admin key.")

if st.session_state.username == "admin":
    st.markdown("<hr>", unsafe_allow_html=True)
    st.markdown("<h2 style='color:#00BFFF;'>📊 Admin Dashboard</h2>", unsafe_allow_html=True)

    # Metrics row
    col1, col2 = st.columns(2)
    with col1:
        st.metric("👤 Total Registered Users", get_total_registered_users())
    with col2:
        st.metric("📅 Logins Today (IST)", get_logins_today())

    # Removed API key usage section (no longer tracked)
    # Activity log
    st.markdown("<h3 style='color:#00BFFF;'>📋 Admin Activity Log</h3>", unsafe_allow_html=True)
    logs = get_all_user_logs()
    if logs:
        st.dataframe(
            {
                "Username": [log[0] for log in logs],
                "Action": [log[1] for log in logs],
                "Timestamp": [log[2] for log in logs]
            },
            use_container_width=True
        )
    else:
        st.info("No logs found yet.")

    st.divider()
    st.subheader("📦 Database Backup & Download")

    if os.path.exists(DB_PATH):
        with open(DB_PATH, "rb") as f:
            st.download_button(
                "⬇️ Download resume_data.db",
                data=f,
                file_name="resume_data_backup.db",
                mime="application/octet-stream"
            )
    else:
        st.warning("⚠️ No database file found yet.")
# Always-visible tabs
tab_labels = [
    "📊 Dashboard",
    "🧾 Resume Builder",
    "💼 Job Search",
    "📚 Course Recommendation"
]

# Add Admin tab only for admin user
if st.session_state.username == "admin":
    tab_labels.append("📁 Admin DB View")

# Create tabs dynamically
tabs = st.tabs(tab_labels)

# Unpack first four (always exist)
tab1, tab2, tab3, tab4 = tabs[:4]

# Handle optional admin tab
tab5 = tabs[4] if len(tabs) > 4 else None
with tab1:
    st.markdown("""
    <style>
    @import url('https://fonts.googleapis.com/css2?family=Orbitron:wght@400;700&display=swap');

    html, body, [class*="css"] {
        font-family: 'Orbitron', sans-serif;
        background-color: #0b0c10;
        color: #c5c6c7;
        scroll-behavior: smooth;
    }

    /* ---------- SCROLLBAR ---------- */
    ::-webkit-scrollbar { width: 8px; }
    ::-webkit-scrollbar-track { background: #1f2833; }
    ::-webkit-scrollbar-thumb { background: #00ffff; border-radius: 4px; }

    /* ---------- BANNER ---------- */
    .banner-container {
        width: 100%;
        height: 80px;
        background: linear-gradient(90deg, #000428, #004e92);
        border-bottom: 2px solid cyan;
        overflow: hidden;
        display: flex;
        align-items: center;
        justify-content: flex-start;
        position: relative;
        margin-bottom: 20px;
        border-radius: 12px;
        backdrop-filter: blur(14px);
    }
    .pulse-bar {
        position: absolute;
        display: flex;
        align-items: center;
        font-size: 22px;
        font-weight: bold;
        color: #00ffff;
        white-space: nowrap;
        animation: glideIn 12s linear infinite;
        text-shadow: 0 0 10px #00ffff;
    }
    .pulse-bar .bar {
        width: 10px;
        height: 30px;
        margin-right: 10px;
        background: #00ffff;
        box-shadow: 0 0 8px cyan;
        animation: pulse 1s ease-in-out infinite;
    }
    @keyframes glideIn {
        0% { left: -50%; opacity: 0; }
        10% { opacity: 1; }
        90% { opacity: 1; }
        100% { left: 110%; opacity: 0; }
    }
    @keyframes pulse {
        0%, 100% { height: 20px; background-color: #00ffff; }
        50% { height: 40px; background-color: #ff00ff; }
    }

    /* ---------- HEADER ---------- */
    .header {
        font-size: 28px;
        font-weight: bold;
        text-align: center;
        text-transform: uppercase;
        letter-spacing: 2px;
        padding: 20px 30px;  /* ✅ More spacing inside the bar */
        color: #00ffff;
        text-shadow: 0px 0px 10px #00ffff;
        position: relative;
        overflow: hidden;
        border-radius: 14px;
        background: rgba(10,20,40,0.35);
        backdrop-filter: blur(14px);
        border: 1px solid rgba(0,200,255,0.5);
        box-shadow: 0 0 12px rgba(0,200,255,0.25);
    }
    .header::before {
        content: "";
        position: absolute;
        top: -50%;
        left: -50%;
        width: 200%;
        height: 200%;
        background: linear-gradient(
            120deg,
            rgba(255,255,255,0.18) 0%,
            rgba(255,255,255,0.05) 40%,
            transparent 60%
        );
        transform: rotate(25deg);
        transition: all 0.6s;
    }
    .header:hover::before { left: 100%; top: 100%; }

    /* ---------- SHIMMER (COMMON) ---------- */
    .shimmer::before {
        content: "";
        position: absolute;
        top: -50%;
        left: -50%;
        width: 200%;
        height: 200%;
        background: linear-gradient(
            120deg,
            rgba(255,255,255,0.15) 0%,
            rgba(255,255,255,0.05) 40%,
            transparent 60%
        );
        transform: rotate(25deg);
        transition: all 0.6s;
    }
    .shimmer:hover::before { left: 100%; top: 100%; }

    /* ---------- FILE UPLOADER ---------- */
    .stFileUploader > div > div {
        border: 1px solid rgba(0,200,255,0.5);
        border-radius: 14px;
        background: rgba(10,20,40,0.35);
        backdrop-filter: blur(14px);
        color: #cce6ff;
        box-shadow: 0 0 12px rgba(0,200,255,0.3);
        position: relative;
        overflow: hidden;
    }
    .stFileUploader > div > div::before {
        content: "";
        position: absolute; top: -50%; left: -50%;
        width: 200%; height: 200%;
        background: linear-gradient(120deg,
            rgba(255,255,255,0.15) 0%,
            rgba(255,255,255,0.05) 40%,
            transparent 60%);
        transform: rotate(25deg);
        transition: all 0.6s;
    }
    .stFileUploader > div > div:hover::before { left: 100%; top: 100%; }

    /* ---------- BUTTONS ---------- */
    .stButton > button {
        position: relative;
        overflow: hidden;
        background: rgba(10,20,40,0.35);
        border: 1px solid rgba(0,200,255,0.6);
        color: #e6f7ff;
        border-radius: 14px;
        padding: 10px 20px;
        font-size: 16px;
        font-weight: 500;
        text-transform: uppercase;
        backdrop-filter: blur(16px);
        box-shadow: 0 0 12px rgba(0,200,255,0.35),
                    inset 0 0 20px rgba(0,200,255,0.05);
        transition: all 0.3s ease-in-out;
    }
    .stButton > button::before {
        content: "";
        position: absolute; top: -50%; left: -50%;
        width: 200%; height: 200%;
        background: linear-gradient(120deg,
            rgba(255,255,255,0.15) 0%,
            rgba(255,255,255,0.05) 40%,
            transparent 60%);
        transform: rotate(25deg);
        transition: all 0.6s;
    }
    .stButton > button:hover::before { left: 100%; top: 100%; }

    /* ---------- INPUTS ---------- */
    .stTextInput > div > input,
    .stTextArea > div > textarea {
        position: relative;
        overflow: hidden;
        background: rgba(10,20,40,0.35);
        border: 1px solid rgba(0,200,255,0.6);
        border-radius: 14px;
        color: #e6f7ff;
        padding: 10px;
        backdrop-filter: blur(16px);
        box-shadow: 0 0 12px rgba(0,200,255,0.3),
                    inset 0 0 15px rgba(0,200,255,0.05);
        transition: all 0.3s ease-in-out;
    }

    /* ---------- CHAT MESSAGES ---------- */
    .stChatMessage {
        position: relative;
        overflow: hidden;
        font-size: 18px;
        background: rgba(10,20,40,0.35);
        border: 1px solid rgba(0,200,255,0.5);
        border-radius: 14px;
        padding: 14px;
        color: #e6f7ff;
        text-shadow: 0 0 6px rgba(0,200,255,0.7);
        box-shadow: 0 0 12px rgba(0,200,255,0.3),
                    inset 0 0 15px rgba(0,200,255,0.05);
    }
    .stChatMessage::before {
        content: "";
        position: absolute; top: -50%; left: -50%;
        width: 200%; height: 200%;
        background: linear-gradient(120deg,
            rgba(255,255,255,0.15) 0%,
            rgba(255,255,255,0.05) 40%,
            transparent 60%);
        transform: rotate(25deg);
        transition: all 0.6s;
    }
    .stChatMessage:hover::before { left: 100%; top: 100%; }

    /* ---------- METRICS ---------- */
    .stMetric {
        position: relative;
        overflow: hidden;
        background-color: rgba(10,20,40,0.35);
        border: 1px solid rgba(0,200,255,0.6);
        border-radius: 14px;
        padding: 15px;
        box-shadow: 0 0 12px rgba(0,200,255,0.35),
                    inset 0 0 20px rgba(0,200,255,0.05);
        text-align: center;
    }
    .stMetric::before {
        content: "";
        position: absolute; top: -50%; left: -50%;
        width: 200%; height: 200%;
        background: linear-gradient(120deg,
            rgba(255,255,255,0.15) 0%,
            rgba(255,255,255,0.05) 40%,
            transparent 60%);
        transform: rotate(25deg);
        transition: all 0.6s;
    }
    .stMetric:hover::before { left: 100%; top: 100%; }

    /* ---------- MOBILE ---------- */
    @media (max-width: 768px) {
        .pulse-bar { font-size: 16px; }
        .header { font-size: 20px; }
    }
    </style>

    <!-- Banner -->
    <div class="banner-container">
        <div class="pulse-bar">
            <div class="bar"></div>
            <div>HIRELYZER - Elevate Your Resume Analysis</div>
        </div>
    </div>

    <!-- Header -->
    <div class="header">💼 HIRELYZER - AI BASED ETHICAL RESUME ANALYZER</div>
    """, unsafe_allow_html=True)

# Load environment variables
load_dotenv()

# Detect Device
DEVICE = "cuda" if torch.cuda.is_available() else "cpu"
torch.backends.cudnn.benchmark = True
working_dir = os.path.dirname(os.path.abspath(__file__))

# ------------------- Lazy Initialization -------------------
@st.cache_resource(show_spinner=False)
def get_easyocr_reader():
    import easyocr
    return easyocr.Reader(["en"], gpu=torch.cuda.is_available())

@st.cache_data(show_spinner=False)
def ensure_nltk():
    import nltk
    nltk.download('wordnet', quiet=True)
    return WordNetLemmatizer()

lemmatizer = ensure_nltk()
reader = get_easyocr_reader()

def generate_docx(text, filename="bias_free_resume.docx"):
    doc = Document()

    # ── Page margins (standard resume: 1 inch all sides) ──
    from docx.oxml.ns import qn as _qn
    from docx.oxml import OxmlElement as _OE
    section = doc.sections[0]
    section.top_margin    = Inches(1.0)
    section.bottom_margin = Inches(1.0)
    section.left_margin   = Inches(1.0)
    section.right_margin  = Inches(1.0)

    # ── Document title heading ──
    title = doc.add_heading('Bias-Free Resume', 0)
    title.alignment = 1  # center
    title_run = title.runs[0]
    title_run.font.color.rgb = RGBColor(0x2F, 0x4F, 0x6F)
    title_run.font.size = Pt(18)

    doc.add_paragraph()  # spacer

    # ── Process text: detect section headers and bullet points ──
    lines = text.strip().split('\n')
    for line in lines:
        stripped = line.strip()
        if not stripped:
            doc.add_paragraph()
            continue

        # Section headers (emoji + CAPS or all-caps lines)
        if (stripped.isupper() and len(stripped) > 3) or \
           any(stripped.startswith(e) for e in ['🏷️','📞','📧','📍','🔗','🌐','✍️','🛠️','💼','🧑‍💼','📂','🎓','🏫','🤝','🌟','🎯']):
            p = doc.add_heading(stripped, level=2)
            p.runs[0].font.color.rgb = RGBColor(0x2F, 0x4F, 0x6F)
            p.runs[0].font.size = Pt(12)
            continue

        # Bullet points
        if stripped.startswith(('•', '-', '*')):
            content = stripped.lstrip('•-* ').strip()
            p = doc.add_paragraph(style='List Bullet')
            run = p.add_run(content)
            run.font.size = Pt(10.5)
            p.paragraph_format.space_after = Pt(3)
            continue

        # Regular paragraph
        p = doc.add_paragraph(stripped)
        p.runs[0].font.size = Pt(10.5)
        p.paragraph_format.space_after = Pt(4)

    buffer = BytesIO()
    doc.save(buffer)
    buffer.seek(0)
    return buffer

# Extract text from PDF
def extract_text_from_pdf(file_path):
    try:
        doc = fitz.open(file_path)
        text_list = [page.get_text("text") for page in doc if page.get_text("text").strip()]
        doc.close()
        return text_list if text_list else extract_text_from_images(file_path)
    except Exception as e:
        st.error(f"⚠ Error extracting text: {e}")
        return []

def extract_text_from_images(pdf_path):
    try:
        images = convert_from_path(pdf_path, dpi=150, first_page=1, last_page=5)
        return ["\n".join(reader.readtext(np.array(img), detail=0)) for img in images]
    except Exception as e:
        st.error(f"⚠ Error extracting from image: {e}")
        return []

def safe_extract_text(uploaded_file):
    """
    Safely extracts text from uploaded file.
    Prevents app crash if file is not a resume or unreadable.
    """
    try:
        # Save uploaded file to a temp location
        temp_path = f"/tmp/{uploaded_file.name}"
        with open(temp_path, "wb") as f:
            f.write(uploaded_file.getbuffer())

        # Try PDF text extraction
        text_list = extract_text_from_pdf(temp_path)

        # If nothing readable found
        if not text_list or all(len(t.strip()) == 0 for t in text_list):
            st.warning("⚠️ This file doesn't look like a resume or contains no readable text.")
            return None

        return "\n".join(text_list)

    except Exception as e:
        st.error(f"⚠️ Could not process this file: {e}")
        return None

# Detect bias in resume
# Predefined gender-coded word lists
gender_words = {
    "masculine": [
        # Dominance / aggression-coded
        "active", "aggressive", "ambitious", "assertive", "autonomous", "boast", "bold",
        "challenging", "competitive", "confident", "courageous", "decisive", "determined", "dominant", "driven",
        "dynamic", "forceful", "independent", "individualistic", "intellectual", "lead", "leader", "objective",
        "outspoken", "persistent", "principled", "proactive", "resilient", "self-reliant", "self-sufficient",
        "strong", "superior", "tenacious", "guru", "tech guru", "technical guru", "visionary", "manpower",
        "strongman", "command", "assert", "headstrong", "rockstar", "superstar", "go-getter", "trailblazer",
        "results-driven", "fast-paced", "determination", "competitive spirit",
        # Additional research-backed masculine-coded terms (Gaucher et al., 2011)
        "analytical", "backbone", "challenge", "champion", "combat", "conquer", "courageous",
        "crusade", "debate", "fearless", "fight", "grit", "hustle", "impact", "ninja",
        "power", "ruthless", "self-starter", "sharp", "warrior", "win", "wrestler",
        "alpha", "beast", "brutally honest", "cutting-edge", "dominate", "edge", "elite",
        "fearless", "grind", "hardcore", "hero", "high-performance", "intense",
        "kill it", "relentless", "savage", "slayer", "tiger", "tough", "uncompromising"
    ],
    
    "feminine": [
        # Communal / warmth-coded
        "affectionate", "agreeable", "attentive", "collaborative", "committed", "compassionate", "considerate",
        "cooperative", "dependable", "dependent", "emotional", "empathetic", "enthusiastic", "friendly", "gentle",
        "honest", "inclusive", "interpersonal", "kind", "loyal", "modest", "nurturing", "pleasant", "polite",
        "sensitive", "supportive", "sympathetic", "tactful", "tender", "trustworthy", "understanding", "warm",
        "yield", "adaptable", "communal", "helpful", "dedicated", "respectful", "nurture", "sociable",
        "relationship-oriented", "team player", "people-oriented", "empathetic listener",
        "gentle communicator", "open-minded",
        # Additional research-backed feminine-coded terms
        "balance", "caring", "child-friendly", "connect", "connection", "flexible hours",
        "harmony", "heart", "humanize", "mindful", "patience", "patient", "peace",
        "personal touch", "responsive", "share", "sharing", "together", "unite",
        "welcoming", "wholesome", "connect with", "feeling", "feelings", "giving back",
        "heartfelt", "humanity", "inspire", "inspired", "passion", "passionate",
        "personable", "relate", "relatable", "soften", "soft skills", "spread",
        "thrive", "togetherness", "transparent", "uplift", "vulnerable"
    ]
}

def detect_bias(text):
    # Split into sentences using simple delimiters
    sentences = re.split(r'(?<=[.!?])\s+', text.strip())

    masc_set, fem_set = set(), set()
    masculine_found, feminine_found = [] , []

    masculine_words = sorted(gender_words["masculine"], key=len, reverse=True)
    feminine_words = sorted(gender_words["feminine"], key=len, reverse=True)

    for sent in sentences:
        sent_text = sent.strip()
        sent_lower = sent_text.lower()
        matched_spans = []

        def is_overlapping(start, end):
            return any(start < e and end > s for s, e in matched_spans)

        # 🔵 Highlight masculine words in blue
        for word in masculine_words:
            pattern = re.compile(rf'\b{re.escape(word)}\b', re.IGNORECASE)
            for match in pattern.finditer(sent_lower):
                start, end = match.span()
                if not is_overlapping(start, end):
                    matched_spans.append((start, end))
                    key = (word.lower(), sent_text)
                    if key not in masc_set:
                        masc_set.add(key)
                        highlighted = re.sub(
                            rf'\b({re.escape(word)})\b',
                            r'<span style="color:blue;">\1</span>',
                            sent_text,
                            flags=re.IGNORECASE
                        )
                        masculine_found.append({
                            "word": word,
                            "sentence": highlighted
                        })

        # 🔴 Highlight feminine words in red
        for word in feminine_words:
            pattern = re.compile(rf'\b{re.escape(word)}\b', re.IGNORECASE)
            for match in pattern.finditer(sent_lower):
                start, end = match.span()
                if not is_overlapping(start, end):
                    matched_spans.append((start, end))
                    key = (word.lower(), sent_text)
                    if key not in fem_set:
                        fem_set.add(key)
                        highlighted = re.sub(
                            rf'\b({re.escape(word)})\b',
                            r'<span style="color:red;">\1</span>',
                            sent_text,
                            flags=re.IGNORECASE
                        )
                        feminine_found.append({
                            "word": word,
                            "sentence": highlighted
                        })

    masc = len(masculine_found)
    fem = len(feminine_found)
    total = masc + fem
    bias_score = min(total / 20, 1.0) if total > 0 else 0.0

    return round(bias_score, 2), masc, fem, masculine_found, feminine_found

replacement_mapping = {
    "masculine": {
        "active": "engaged",
        "aggressive": "proactive",
        "ambitious": "motivated",
        "analytical": "detail-oriented",
        "assertive": "direct",
        "autonomous": "self-directed",
        "boast": "highlight",
        "bold": "confident",
        "challenging": "demanding",
        "competitive": "goal-oriented",
        "confident": "self-assured",
        "courageous": "bold",
        "decisive": "action-oriented",
        "determined": "focused",
        "dominant": "influential",
        "driven": "committed",
        "dynamic": "adaptable",
        "forceful": "persuasive",
        "guru": "technical expert",
        "independent": "self-sufficient",
        "individualistic": "self-motivated",
        "intellectual": "knowledgeable",
        "lead": "guide",
        "leader": "team lead",
        "objective": "unbiased",
        "outspoken": "expressive",
        "persistent": "tenacious",
        "principled": "ethical",
        "proactive": "initiative-taking",
        "resilient": "adaptable",
        "self-reliant": "resourceful",
        "self-sufficient": "capable",
        "strong": "capable",
        "superior": "exceptional",
        "tenacious": "determined",
        "technical guru": "technical expert",
        "visionary": "forward-thinking",
        "manpower": "workforce",
        "strongman": "resilient individual",
        "command": "direct",
        "assert": "state clearly",
        "headstrong": "determined",
        "rockstar": "top performer",
        "superstar": "outstanding contributor",
        "go-getter": "initiative-taker",
        "trailblazer": "innovator",
        "results-driven": "outcome-focused",
        "fast-paced": "dynamic",
        "determination": "commitment",
        "competitive spirit": "goal-oriented mindset",
        # New additions
        "ninja": "specialist",
        "warrior": "dedicated professional",
        "alpha": "senior",
        "beast": "high performer",
        "dominate": "excel in",
        "elite": "high-performing",
        "relentless": "persistent",
        "savage": "highly skilled",
        "hustle": "work efficiently",
        "grit": "resilience",
        "hardcore": "rigorous",
        "hero": "key contributor",
        "ruthless": "highly focused",
        "kill it": "excel",
        "champion": "advocate",
        "conquer": "achieve",
        "fight": "address",
        "win": "achieve success",
        "crush": "exceed targets",
        "unstoppable": "highly motivated",
        "fearless": "courageous",
        "power": "capability",
        "backbone": "core strength",
        "sharp": "perceptive"
    },
    
    "feminine": {
        "affectionate": "approachable",
        "agreeable": "cooperative",
        "attentive": "observant",
        "collaborative": "team-oriented",
        "collaborate": "team-oriented",
        "collaborated": "worked together",
        "committed": "dedicated",
        "compassionate": "caring",
        "considerate": "thoughtful",
        "cooperative": "supportive",
        "dependable": "reliable",
        "dependent": "team-oriented",
        "emotional": "passionate",
        "empathetic": "perceptive",
        "enthusiastic": "energized",
        "gentle": "respectful",
        "honest": "transparent",
        "inclusive": "open-minded",
        "interpersonal": "people-focused",
        "kind": "respectful",
        "loyal": "dedicated",
        "modest": "measured",
        "nurturing": "supportive",
        "pleasant": "professional",
        "polite": "courteous",
        "sensitive": "perceptive",
        "supportive": "enabling",
        "sympathetic": "understanding",
        "tactful": "diplomatic",
        "tender": "considerate",
        "trustworthy": "reliable",
        "understanding": "empathetic",
        "warm": "welcoming",
        "yield": "adjust",
        "adaptable": "flexible",
        "communal": "team-centered",
        "helpful": "contributive",
        "dedicated": "committed",
        "respectful": "professional",
        "nurture": "develop",
        "sociable": "collegial",
        "relationship-oriented": "team-focused",
        "team player": "collaborative member",
        "people-oriented": "stakeholder-focused",
        "empathetic listener": "active listener",
        "gentle communicator": "considerate communicator",
        "open-minded": "inclusive",
        # New additions
        "passionate": "highly motivated",
        "inspired": "driven by purpose",
        "inspire": "motivate",
        "vulnerable": "transparent",
        "heartfelt": "sincere",
        "harmony": "alignment",
        "caring": "attentive",
        "patient": "thorough",
        "wholesome": "balanced",
        "togetherness": "team cohesion",
        "soft skills": "professional competencies",
        "personal touch": "tailored approach",
        "feeling": "assessment",
        "feelings": "perspectives",
        "transparent": "accountable",
        "uplift": "elevate",
        "thrive": "excel",
        "welcoming": "inclusive",
        "relatable": "accessible",
        "connect": "engage",
        "together": "collaboratively",
        "sharing": "distributing",
        "mindful": "deliberate",
        "balance": "manage effectively"
    }
}

def rewrite_text_with_llm(text, replacement_mapping, user_location):
    """
    Enhanced resume rewrite engine (backward compatible).
    - Improves structure, clarity, and ATS readiness
    - Fills missing sections using internal evidence
    - Maintains bias-free language
    - Preserves and ENFORCES suggested job titles output
    """

    # -----------------------------
    # Format bias replacement rules
    # -----------------------------
    formatted_mapping = "\n".join(
        [f'- "{key}" → "{value}"' for key, value in replacement_mapping.items()]
    )

    # -----------------------------
    # MASTER PROMPT
    # -----------------------------
    prompt = f"""
You are an elite Resume Optimization Engine used by Fortune 500 recruiters and executive career coaches.

You will receive:
1. Original Resume Text
2. Bias Replacement Rules
3. Candidate Location

Your goal is to TRANSFORM the resume into a top-1% recruiter-ready document:
ATS-optimized, bias-free, quantification-rich, and professionally compelling.

═══════════════════════════════════════════════════
🔒 ABSOLUTE RULES (NON-NEGOTIABLE)
═══════════════════════════════════════════════════

- DO NOT fabricate companies, job titles, degrees, institutions, or dates
- DO NOT invent metrics or statistics not implied by the resume
- DO NOT add certifications or skills that don't appear anywhere in the resume
- You MAY:
  ✅ Strengthen and expand existing bullet points with stronger action verbs
  ✅ CREATE missing sections if clear evidence exists elsewhere in the resume
  ✅ Move skills from projects/experience into the dedicated Skills section
  ✅ Infer tool proficiency ONLY when strongly implied (e.g., "built Flask API" → Python/Flask listed)
  ✅ Estimate impact framing ONLY when role implies it (e.g., "customer support" → "resolved X+ client issues")
  ✅ Reorder sections for maximum ATS impact

═══════════════════════════════════════════════════
📌 OPTIMIZATION RULES
═══════════════════════════════════════════════════

1. **Professional Summary** — Write a 3–4 sentence executive-level summary that:
   - Opens with seniority + core domain (e.g., "Results-driven Data Engineer with 3+ years...")
   - Highlights top 2–3 technical strengths with specificity
   - Closes with value proposition aligned to career goals

2. **Experience Bullet Points** — Every bullet MUST follow:
   → **Action Verb + Specific Task + Technology/Method Used + Quantified Impact**
   → Example: "Engineered real-time data pipeline using Apache Kafka and Spark, reducing latency by 40%"
   → Use STRONG action verbs: Architected, Engineered, Designed, Deployed, Optimized, Automated, Reduced, Increased, Led, Built, Launched, Delivered

3. **Skills Section** — Must include ALL technologies, tools, frameworks, platforms, and methodologies mentioned ANYWHERE in the resume.
   Format as clean ATS-friendly lists grouped by category:
   - Programming Languages | Frameworks & Libraries | Cloud & DevOps | Databases | Tools & Platforms | Soft Skills

4. **Projects Section** — Each project must include:
   - Project name + brief (1 sentence) description
   - Full tech stack used
   - Your specific role/contribution
   - Outcome, metric, or learning

5. **Education** — Include: Degree, Institution, Year, GPA (if strong), Relevant Coursework (if applicable)

6. **Certifications** — List ALL found in resume. Add plausible ones ONLY if tool names strongly imply them.

7. **Sections to create if evidence exists but are missing:**
   🛠️ Skills | 📂 Projects | 🎓 Certifications | 🤝 Professional Competencies | 🌟 Interests

═══════════════════════════════════════════════════
🧾 REQUIRED OUTPUT STRUCTURE
═══════════════════════════════════════════════════

Return a COMPLETE, polished resume with these sections (skip only if truly impossible):

🏷️ Full Name  
📞 Phone Number  
📧 Email Address  
📍 Location  
🔗 LinkedIn Profile URL  
🌐 GitHub / Portfolio URL  

✍️ Professional Summary  
🛠️ Technical Skills  
💼 Work Experience  
🧑‍💼 Internships (if applicable)  
📂 Projects  
🎓 Certifications & Training  
🏫 Education  
🤝 Professional Competencies  
🌟 Interests & Extracurriculars  

Formatting requirements:
- Bullet points (•) for all list items
- Clean spacing between sections
- Section headers in CAPS or bold
- ATS-safe formatting (no tables, columns, or special characters)
- Tense: past for completed roles, present for current role

═══════════════════════════════════════════════════
🧠 BIAS REPLACEMENT RULES (APPLY EXACTLY)
═══════════════════════════════════════════════════
{formatted_mapping}

═══════════════════════════════════════════════════
📄 ORIGINAL RESUME
═══════════════════════════════════════════════════
\"\"\"{text}\"\"\"

═══════════════════════════════════════════════════
🎯 MANDATORY JOB TITLE SUGGESTIONS
═══════════════════════════════════════════════════

After the resume, include a clearly separated section:

### 🎯 Suggested Job Titles (Based on Resume)

Provide EXACTLY **5 job titles** suited for a candidate in **{user_location}**.

For EACH job title, provide:
- A specific reason why this role fits the candidate's background
- A DIRECT LinkedIn job search URL using the exact format below

FORMAT STRICTLY AS:

1. **[Job Title]** — [Specific reason based on resume content]  
🔗 https://www.linkedin.com/jobs/search/?keywords=[URL+encoded+title]&location={urllib.parse.quote(user_location)}

2. **[Job Title]** — ...  
🔗 ...

(Continue for all 5)

═══════════════════════════════════════════════════
✅ FINAL OUTPUT
═══════════════════════════════════════════════════
1. Fully optimized, bias-free resume (complete, not a summary)
2. Suggested Job Titles section (MANDATORY — 5 titles with URLs)
"""

    # -----------------------------
    # Call LLM
    # -----------------------------
    response = call_llm(prompt, session=st.session_state)
    return response


def rewrite_and_highlight(text, replacement_mapping, user_location):
    highlighted_text = text
    masculine_count, feminine_count = 0, 0
    detected_masculine_words, detected_feminine_words = [], []
    matched_spans = []

    masculine_words = sorted(gender_words["masculine"], key=len, reverse=True)
    feminine_words = sorted(gender_words["feminine"], key=len, reverse=True)

    def span_overlaps(start, end):
        return any(s < end and e > start for s, e in matched_spans)

    # Highlight and count masculine words
    for word in masculine_words:
        pattern = re.compile(rf'\b{re.escape(word)}\b', re.IGNORECASE)
        for match in pattern.finditer(highlighted_text):
            start, end = match.span()
            if span_overlaps(start, end):
                continue

            word_match = match.group(0)
            colored = f"<span style='color:blue;'>{word_match}</span>"

            # Replace word in the highlighted text
            highlighted_text = highlighted_text[:start] + colored + highlighted_text[end:]
            shift = len(colored) - len(word_match)
            matched_spans = [(s if s < start else s + shift, e if s < start else e + shift) for s, e in matched_spans]
            matched_spans.append((start, start + len(colored)))

            masculine_count += 1

            # Get sentence context and highlight
            sentence_match = re.search(r'([^.]*?\b' + re.escape(word_match) + r'\b[^.]*\.)', text, re.IGNORECASE)
            if sentence_match:
                sentence = sentence_match.group(1).strip()
                colored_sentence = re.sub(
                    rf'\b({re.escape(word_match)})\b',
                    r"<span style='color:blue;'>\1</span>",
                    sentence,
                    flags=re.IGNORECASE
                )
                detected_masculine_words.append({
                    "word": word_match,
                    "sentence": colored_sentence
                })
            break  # Only one match per word

    # Highlight and count feminine words
    for word in feminine_words:
        pattern = re.compile(rf'\b{re.escape(word)}\b', re.IGNORECASE)
        for match in pattern.finditer(highlighted_text):
            start, end = match.span()
            if span_overlaps(start, end):
                continue

            word_match = match.group(0)
            colored = f"<span style='color:red;'>{word_match}</span>"

            # Replace word in the highlighted text
            highlighted_text = highlighted_text[:start] + colored + highlighted_text[end:]
            shift = len(colored) - len(word_match)
            matched_spans = [(s if s < start else s + shift, e if s < start else e + shift) for s, e in matched_spans]
            matched_spans.append((start, start + len(colored)))

            feminine_count += 1

            # Get sentence context and highlight
            sentence_match = re.search(r'([^.]*?\b' + re.escape(word_match) + r'\b[^.]*\.)', text, re.IGNORECASE)
            if sentence_match:
                sentence = sentence_match.group(1).strip()
                colored_sentence = re.sub(
                    rf'\b({re.escape(word_match)})\b',
                    r"<span style='color:red;'>\1</span>",
                    sentence,
                    flags=re.IGNORECASE
                )
                detected_feminine_words.append({
                    "word": word_match,
                    "sentence": colored_sentence
                })
            break  # Only one match per word

    # Rewrite text with neutral terms
    rewritten_text = rewrite_text_with_llm(
        text,
        replacement_mapping["masculine"] | replacement_mapping["feminine"],
        user_location
    )

    return highlighted_text, rewritten_text, masculine_count, feminine_count, detected_masculine_words, detected_feminine_words

# ✅ Enhanced Grammar evaluation using LLM with suggestions
def get_grammar_score_with_llm(text, max_score=5):
    grammar_prompt = f"""
You are a senior HR language quality specialist and professional resume reviewer with 15+ years of experience evaluating resumes for Fortune 500 companies.

Analyze the following resume text across FIVE dimensions and provide an overall language quality score:

**EVALUATION DIMENSIONS:**
1. **Grammar & Mechanics** — Correct grammar, punctuation, subject-verb agreement, tense consistency
2. **Clarity & Conciseness** — Ideas expressed directly; no filler words or redundancy
3. **Professional Tone** — Appropriate formality, no informal slang or casual phrasing
4. **Action Verb Usage** — Starts bullet points with strong, quantifiable action verbs (e.g., "Led", "Engineered", "Reduced")
5. **ATS Language Alignment** — Industry-standard terminology, keyword density, no keyword stuffing

**SCORING SCALE (out of {max_score}):**
- {max_score}: Exceptional — Flawless grammar, powerful action verbs, crystal-clear and professional throughout
- {max_score-1}: Very Good — Minor stylistic issues; highly professional and readable
- {max_score-2}: Good — Some grammar or clarity issues but largely professional and effective
- {max_score-3}: Fair — Noticeable grammar, tone, or clarity problems that could affect readability
- {max_score-4}: Poor — Multiple errors affecting professional impression; needs significant editing
- 0-1: Very Poor — Significant language issues that would cause ATS rejection or recruiter dismissal

**IMPORTANT:** Be balanced — a technically competent resume with minor grammar issues should not be harshly penalized. Focus on overall professional impression.

Return EXACTLY in this format (no extra text):

Score: <number>
Feedback: <single sentence summarizing overall language quality and tone>
Suggestions:
- <Actionable suggestion 1 with example if helpful>
- <Actionable suggestion 2 with example if helpful>
- <Actionable suggestion 3 with example if helpful>
- <Actionable suggestion 4 with example if helpful>
- <Actionable suggestion 5 with example if helpful>

---
{text}
---
"""

    response = call_llm(grammar_prompt, session=st.session_state).strip()
    score_match = re.search(r"Score:\s*(\d+)", response)
    feedback_match = re.search(r"Feedback:\s*(.+)", response)
    suggestions = re.findall(r"- (.+)", response)

    score = int(score_match.group(1)) if score_match else max(3, max_score-2)  # More generous default
    feedback = feedback_match.group(1).strip() if feedback_match else "Language quality appears adequate for professional communication."
    return score, feedback, suggestions

# ✅ Main ATS Evaluation Function
def ats_percentage_score(
    resume_text,
    job_description,
    job_title="Unknown",
    logic_profile_score=None,
    edu_weight=20,
    exp_weight=35,
    skills_weight=30,
    lang_weight=5,
    keyword_weight=10
):
    import datetime

    # ✅ Grammar evaluation
    grammar_score, grammar_feedback, grammar_suggestions = get_grammar_score_with_llm(
        resume_text, max_score=lang_weight
    )

    # ✅ Domain similarity detection using LLM
    resume_domain = db_manager.detect_domain_llm(
        "Unknown", 
        resume_text, 
        session=st.session_state  # ✅ pass the Groq API key from session
    )
    job_domain = db_manager.detect_domain_llm(
        job_title, 
        job_description, 
        session=st.session_state  # ✅ pass the Groq API key from session
    )
    similarity_score = get_domain_similarity(resume_domain, job_domain)

    # ✅ Balanced domain penalty
    MAX_DOMAIN_PENALTY = 15
    domain_penalty = round((1 - similarity_score) * MAX_DOMAIN_PENALTY)

    # ✅ Optional profile score note
    logic_score_note = (
        f"\n\nOptional Note: The system also calculated a logic-based profile score of {logic_profile_score}/100 "
        f"based on resume length, experience, and skills."
        if logic_profile_score else ""
    )

    # ✅ FIXED: Stable education scoring with 2025 cutoff
    current_year = datetime.datetime.now().year
    current_month = datetime.datetime.now().month
    
    # ✅ FIXED: Education completion detection with 2025 cutoff
    def determine_education_status(education_text, end_year_str):
        """
        Determine if education is completed or ongoing based on 2025 cutoff and keywords.
        Returns 'completed' or 'ongoing'.
        """
        try:
            end_year = int(end_year_str.strip())
        except (ValueError, AttributeError):
            # If we can't parse the year, default to ongoing
            return "ongoing"
        
        # Apply 2025 cutoff rule (HARDCODED - NOT dynamic)
        if end_year < 2025:
            education_status = "completed"
        elif end_year == 2025:
            education_status = "completed"
        else:  # end_year > 2025
            education_status = "ongoing"
        
        # Check for explicit keywords that might override numeric rules
        education_lower = education_text.lower()
        ongoing_keywords = ["pursuing", "present", "ongoing", "currently enrolled", "in progress"]
        completed_keywords = ["graduated", "completed", "finished"]
        
        # Override rule: If end year < 2025, always completed regardless of text
        if end_year < 2025:
            return "completed"
        
        # For years >= 2025, check keywords
        if end_year < 2025:
            return "completed"
        
        # For years >= 2025, check keywords
        if any(keyword in education_lower for keyword in ongoing_keywords):
            education_status = "ongoing"
        elif any(keyword in education_lower for keyword in completed_keywords):
            education_status = "completed"
        
        return education_status
    
    # ✅ UPDATED: Stable education scoring with priority degrees minimum
    prompt = f"""
You are a senior ATS (Applicant Tracking System) Evaluator and Technical Recruiter with 15+ years of experience at top-tier tech firms.
Your evaluation must be rigorous, consistent, evidence-based, and match industry-standard hiring benchmarks.

You specialize in: AI/ML, Blockchain, Cloud Computing, Data Engineering, Software Development, DevOps, and Cybersecurity roles.

═══════════════════════════════════════════════════
🎯 EVALUATION PHILOSOPHY
═══════════════════════════════════════════════════
- Score based on EVIDENCE found in the resume — not assumptions
- Reward quantified achievements (numbers, percentages, scale)
- Credit projects, GitHub, hackathons, Kaggle, open-source contributions, certifications
- Penalize vague claims without evidence ("good communication skills")
- Recognize career stage: entry-level vs senior vs lead
- Prioritize recency: skills/experience from the last 3 years matter most
- Be encouraging but calibrated: do not inflate scores without evidence

═══════════════════════════════════════════════════
📐 SCORING FRAMEWORK
═══════════════════════════════════════════════════

**🎓 Education Score ({edu_weight} points max):**

PRIORITY RULE — Minimum {int(edu_weight * 0.75)} pts for these degrees (completed OR pursuing):
  • BSc/MSc Computer Science or Mathematics
  • MCA (Master of Computer Applications)  
  • BE/BTech Computer Science or IT
  • BCA + MCA combination

DATE PARSING (STRICT — Non-negotiable):
  • End year < 2025 → ✅ COMPLETED (hardcoded cutoff)
  • End year = 2025 → ✅ COMPLETED
  • End year > 2025 → 🔄 ONGOING
  • Keywords "pursuing", "in progress", "currently enrolled" → 🔄 ONGOING
  • Keywords "graduated", "completed", "finished" → ✅ COMPLETED
  • If end year < 2025, ALWAYS mark completed regardless of text

Scoring bands:
  • {int(edu_weight * 0.90)}–{edu_weight}: Outstanding — completed highly relevant degree + exceptional academic record
  • {int(edu_weight * 0.75)}–{int(edu_weight * 0.85)}: Excellent — priority degree (completed or ongoing), good standing
  • {int(edu_weight * 0.60)}–{int(edu_weight * 0.70)}: Very Good — related STEM/technical degree
  • {int(edu_weight * 0.45)}–{int(edu_weight * 0.55)}: Good — partially related degree with transferable foundation
  • {int(edu_weight * 0.30)}–{int(edu_weight * 0.40)}: Fair — unrelated degree with relevant self-learning evidence
  • {int(edu_weight * 0.15)}–{int(edu_weight * 0.25)}: Basic — minimal or no degree information
  • 0–{int(edu_weight * 0.10)}: Insufficient — no education details at all

**💼 Experience Score ({exp_weight} points max):**

Evaluate: years of relevant experience, role seniority, domain fit, impact, leadership, quantification.

  • {int(exp_weight * 0.91)}–{exp_weight}: Exceptional — exceeds requirements; strong leadership; quantified high-impact results
  • {int(exp_weight * 0.80)}–{int(exp_weight * 0.89)}: Excellent — meets/exceeds years; strong domain fit; clear achievements
  • {int(exp_weight * 0.69)}–{int(exp_weight * 0.77)}: Very Good — adequate years; good domain fit; solid responsibilities
  • {int(exp_weight * 0.57)}–{int(exp_weight * 0.66)}: Good — reasonable experience; relevant domain; some achievements
  • {int(exp_weight * 0.43)}–{int(exp_weight * 0.54)}: Fair — some gaps but shows clear potential and transferable skills
  • {int(exp_weight * 0.29)}–{int(exp_weight * 0.40)}: Basic — limited experience but relevant direction shown
  • {int(exp_weight * 0.14)}–{int(exp_weight * 0.26)}: Entry Level — minimal experience; strong potential only
  • 0–{int(exp_weight * 0.11)}: Insufficient — major gaps; no transferable evidence

NOTE: Internships, freelance projects, and open-source contributions count as valid experience.

**🛠️ Skills Score ({skills_weight} points max):**

Match each listed skill against job description requirements. Reward:
  • Hard skills: programming languages, frameworks, tools, platforms
  • Certifications: AWS, GCP, Azure, Kubernetes, Terraform, etc.
  • Emerging skills: LLMs, GenAI, Vector DBs, Web3, MLOps, DeFi, Smart Contracts

  • {int(skills_weight * 0.93)}–{skills_weight}: Outstanding — 90%+ required skills; expert proficiency; recent hands-on usage
  • {int(skills_weight * 0.80)}–{int(skills_weight * 0.90)}: Excellent — 80%+ required skills; advanced proficiency
  • {int(skills_weight * 0.67)}–{int(skills_weight * 0.77)}: Very Good — 70%+ required skills; competent usage
  • {int(skills_weight * 0.53)}–{int(skills_weight * 0.63)}: Good — 60%+ required skills; working knowledge
  • {int(skills_weight * 0.40)}–{int(skills_weight * 0.50)}: Fair — 50%+ skills OR strong foundational skills
  • {int(skills_weight * 0.27)}–{int(skills_weight * 0.37)}: Basic — 40%+ skills; clear learning trajectory
  • {int(skills_weight * 0.13)}–{int(skills_weight * 0.23)}: Limited — 30%+ skills; self-learning evident
  • 0–{int(skills_weight * 0.10)}: Insufficient — fewer than 30% required skills

**🔑 Keyword Score ({keyword_weight} points max):**

Systematically extract ALL critical terms from the job description:
technical tools, frameworks, methodologies, role titles, industry terms, certification names.
Compare against resume. Credit synonyms and equivalent terms.

  • {int(keyword_weight * 0.90)}–{keyword_weight}: Excellent — 85%+ critical terms; strong industry vocabulary
  • {int(keyword_weight * 0.80)}: Very Good — 75%+ critical terms
  • {int(keyword_weight * 0.60)}–{int(keyword_weight * 0.70)}: Good — 65%+ critical terms
  • {int(keyword_weight * 0.40)}–{int(keyword_weight * 0.50)}: Fair — 50%+ critical terms
  • {int(keyword_weight * 0.20)}–{int(keyword_weight * 0.30)}: Basic — 35%+ critical terms
  • {int(keyword_weight * 0.10)}: Limited — 20%+ critical terms
  • 0: Poor — fewer than 20% critical terms

═══════════════════════════════════════════════════
📋 REQUIRED OUTPUT FORMAT
═══════════════════════════════════════════════════

Follow this EXACT structure. Do not skip any section:

### 🏷️ Candidate Name
<Extract full name from resume header or contact section>

### 🏫 Education Analysis
**Score:** <0–{edu_weight}> / {edu_weight}

**Scoring Rationale:**
- Degree Level & Relevance: <Does it qualify for minimum {int(edu_weight * 0.75)}-pt rule? Which degree?>
- Completion Status: <Apply strict 2025 cutoff rule; state year and final status>
- Academic Quality Indicators: <GPA, honors, relevant coursework if mentioned>
- **Score Justification:** <Explain exact score with evidence from resume>

### 💼 Experience Analysis
**Score:** <0–{exp_weight}> / {exp_weight}

**Experience Breakdown:**
- Total Years of Relevant Experience: <X years — include internships, freelance, open-source>
- Role Progression & Seniority: <Entry → Mid → Senior trajectory>
- Domain Alignment: <How well does background match job domain?>
- Quantified Achievements: <List metrics found: % improvement, $ savings, users served, etc.>
- Leadership & Ownership Evidence: <Managed teams? Led projects? Mentored?>
- Technology Currency: <Are skills/tools recent and relevant (last 3 years)?>
- **Score Justification:** <Explain score with specific resume evidence>

### 🛠 Skills Analysis
**Score:** <0–{skills_weight}> / {skills_weight}

**Skills Assessment:**
- Core Technical Skills Matched: <List matched skills with evidence>
- Emerging/Cutting-Edge Skills: <LLMs, GenAI, Web3, MLOps, Cloud, etc.>
- Certifications Detected: <List any certifications found>
- Soft Skills with Evidence: <Only count if backed by concrete examples>
- Proficiency Depth: <Surface knowledge vs. demonstrated project usage>

**Skills Gaps (Development Opportunities):**
- <Gap 1 — specific missing skill from job description>
- <Gap 2 — specific missing skill>
- <Gap 3 — specific missing skill>
- <Gap 4 — specific missing skill>
- <Gap 5 — specific missing skill>

**Score Justification:** <Explain with matched vs. required skills ratio>

### 🗣 Language Quality Analysis
**Score:** {grammar_score} / {lang_weight}
**Grammar & Professional Tone:** {grammar_feedback}
**Assessment:** <Specific feedback on action verb usage, clarity, tense consistency, and ATS language>

### 🔑 Keyword Analysis
**Score:** <0–{keyword_weight}> / {keyword_weight}

**Keyword Assessment:**
- Industry Terminology Match: <Percentage and specific matches found>
- Role-Specific Keywords Present: <List matched keywords>
- Technical Vocabulary: <Tools, frameworks, platforms found in both>
- Keyword Density Quality: <Natural integration vs. stuffing>

**Keyword Enhancement Opportunities:**
- <Critical keyword 1 from job description — not in resume>
- <Critical keyword 2>
- <Critical keyword 3>
- <Critical keyword 4>
- <Critical keyword 5>
- <Critical keyword 6>
- <Critical keyword 7>
- <Critical keyword 8>

**Score Justification:** <Evidence-based explanation>

### ✅ Final Assessment

**Overall Evaluation:**
<5–7 sentences covering: candidate's unique value proposition, strongest evidence-backed qualifications, key gaps, culture/team fit signals, and a clear hire/interview recommendation>

**Top 3 Strengths (with evidence):**
1. <Strength 1 — backed by resume evidence>
2. <Strength 2 — backed by resume evidence>
3. <Strength 3 — backed by resume evidence>

**Top 3 Development Areas:**
1. <Gap 1 framed as a growth opportunity>
2. <Gap 2 framed as a growth opportunity>
3. <Gap 3 framed as a growth opportunity>

**Hiring Recommendation:** <Strongly Recommend / Recommend / Recommend with Reservations / Do Not Recommend> — <2-sentence reasoning>

---

**EVALUATION CONTEXT:**
- Current Date: {datetime.datetime.now().strftime('%B %Y')} (Year: {current_year}, Month: {current_month})
- Grammar Score Pre-evaluated: {grammar_score} / {lang_weight} — {grammar_feedback}
- Resume Domain Detected: {resume_domain}
- Target Job Domain: {job_domain}
- Domain Similarity Score: {similarity_score:.2f}/1.0
- Domain Mismatch Penalty Applied: {domain_penalty}/{MAX_DOMAIN_PENALTY} pts

---

📄 **JOB DESCRIPTION:**
{job_description}

📄 **RESUME TEXT:**
{resume_text}

{logic_score_note}
"""
   
   
    ats_result = call_llm(prompt, session=st.session_state).strip()

    def extract_section(pattern, text, default="N/A"):
        match = re.search(pattern, text, re.DOTALL)
        return match.group(1).strip() if match else default

    def extract_score(pattern, text, default=0):
        match = re.search(pattern, text)
        return int(match.group(1)) if match else default

    # Extract key sections
    candidate_name = extract_section(r"### 🏷️ Candidate Name(.*?)###", ats_result, "Not Found")
    edu_analysis = extract_section(r"### 🏫 Education Analysis(.*?)###", ats_result)
    exp_analysis = extract_section(r"### 💼 Experience Analysis(.*?)###", ats_result)
    skills_analysis = extract_section(r"### 🛠 Skills Analysis(.*?)###", ats_result)
    lang_analysis = extract_section(r"### 🗣 Language Quality Analysis(.*?)###", ats_result)
    keyword_analysis = extract_section(r"### 🔑 Keyword Analysis(.*?)###", ats_result)
    final_thoughts = extract_section(r"### ✅ Final Assessment(.*)", ats_result)

    # Extract scores with improved patterns (LLM now scores directly using sidebar weights)
    edu_score = extract_score(r"\*\*Score:\*\*\s*(\d+)", edu_analysis)
    exp_score = extract_score(r"\*\*Score:\*\*\s*(\d+)", exp_analysis)
    skills_score = extract_score(r"\*\*Score:\*\*\s*(\d+)", skills_analysis)
    keyword_score = extract_score(r"\*\*Score:\*\*\s*(\d+)", keyword_analysis)
    lang_score = grammar_score  # Grammar score already uses lang_weight

    # ✅ Apply minimum thresholds to avoid overly harsh penalties
    edu_score = max(edu_score, int(edu_weight * 0.15))  # Minimum 15% of weight
    exp_score = max(exp_score, int(exp_weight * 0.15))  # Minimum 15% of weight
    skills_score = max(skills_score, int(skills_weight * 0.15))  # Minimum 15% of weight
    keyword_score = max(keyword_score, int(keyword_weight * 0.10))  # Minimum 10% of weight

    # Extract missing items with better parsing - now called "opportunities"
    missing_keywords_section = extract_section(r"\*\*Keyword Enhancement Opportunities:\*\*(.*?)(?:\*\*|###|\Z)", keyword_analysis)
    missing_skills_section = extract_section(r"\*\*Skills Gaps \(Opportunities for Growth\):\*\*(.*?)(?:\*\*|###|\Z)", skills_analysis)
    
    # Fallback to old patterns if new ones don't match
    if not missing_keywords_section.strip():
        missing_keywords_section = extract_section(r"\*\*Missing Critical Keywords:\*\*(.*?)(?:\*\*|###|\Z)", keyword_analysis)
    if not missing_skills_section.strip():
        missing_skills_section = extract_section(r"\*\*Missing Critical Skills:\*\*(.*?)(?:\*\*|###|\Z)", skills_analysis)
    
    # Improved extraction - handle multiple formats and get all items
    def extract_list_items(text):
        if not text.strip():
            return "None identified"
        
        # Find all bullet points with various formats
        items = []
        lines = text.strip().split('\n')
        
        for line in lines:
            line = line.strip()
            if not line:
                continue
                
            # Remove various bullet point formats
            cleaned_line = re.sub(r'^[-•*]\s*', '', line)  # Remove -, •, * bullets
            cleaned_line = re.sub(r'^\d+\.\s*', '', cleaned_line)  # Remove numbered lists
            cleaned_line = cleaned_line.strip()
            
            if cleaned_line and len(cleaned_line) > 2:  # Avoid empty or very short items
                items.append(cleaned_line)
        
        return ', '.join(items) if items else "None identified"
    
    missing_keywords = extract_list_items(missing_keywords_section)
    missing_skills = extract_list_items(missing_skills_section)

    # ✅ IMPROVED: More balanced total score calculation
    total_score = edu_score + exp_score + skills_score + lang_score + keyword_score
    
    # Apply domain penalty more gently
    total_score = max(total_score - domain_penalty, int(total_score * 0.7))  # Never go below 70% of pre-penalty score
    
    # ✅ IMPROVED: More generous score caps and bonus for well-rounded candidates
    total_score = min(total_score, 100)
    total_score = max(total_score, 15)  # Minimum score of 15 to avoid completely crushing candidates

    # ✅ Industry-standard score labels with clear hiring signal
    formatted_score = (
        "🌟 Exceptional Match — Top 10% Candidate" if total_score >= 85 else
        "✅ Strong Match — Recommend for Interview" if total_score >= 70 else
        "🟡 Good Potential — Competitive Candidate" if total_score >= 55 else
        "⚠️ Fair Match — Needs Resume Optimization" if total_score >= 40 else
        "🔄 Developing — Significant Skill Gaps" if total_score >= 25 else
        "❌ Poor Match — Major Role Misalignment"
    )

    # ✅ Format suggestions nicely
    suggestions_html = ""
    if grammar_suggestions:
        suggestions_html = "<ul>" + "".join([f"<li>{s}</li>" for s in grammar_suggestions]) + "</ul>"

    updated_lang_analysis = f"""
{lang_analysis}
<br><b>LLM Feedback Summary:</b> {grammar_feedback}
<br><b>Improvement Suggestions:</b> {suggestions_html}
"""

    # Enhanced final thoughts with domain analysis and industry benchmarks
    final_thoughts += f"""

**📊 Technical Evaluation Details:**
- Domain Similarity Score: {similarity_score:.2f}/1.0 ({int(similarity_score * 100)}% domain alignment)
- Domain Penalty Applied: -{domain_penalty} pts (out of max -{MAX_DOMAIN_PENALTY} pts)
- Resume Domain Detected: {resume_domain}
- Target Job Domain: {job_domain}
- Grammar & Language Pre-Score: {grammar_score}/{lang_weight}

**📈 Score Interpretation (Industry Benchmarks):**
- 85–100: 🌟 Top 10% candidates — Strong interview recommendation
- 70–84: ✅ Above average — Likely to advance past ATS screening
- 55–69: 🟡 Competitive — May advance with strong cover letter
- 40–54: ⚠️ Below average — Needs resume optimization before applying
- 25–39: 🔄 Significant gaps — Upskilling recommended
- 0–24: ❌ Major misalignment — Not suitable for this specific role

**🔍 ATS Scoring Notes:**
- Minimum score thresholds applied to prevent unfair penalization
- Transferable skills, projects, and open-source contributions were credited
- Career stage (entry/mid/senior) considered in experience scoring
- Date parsing uses 2025 cutoff for education completion determination
"""

    return ats_result, {
        "Candidate Name": candidate_name,
        "Education Score": edu_score,
        "Experience Score": exp_score,
        "Skills Score": skills_score,
        "Language Score": lang_score,
        "Keyword Score": keyword_score,
        "ATS Match %": total_score,
        "Formatted Score": formatted_score,
        "Education Analysis": edu_analysis,
        "Experience Analysis": exp_analysis,
        "Skills Analysis": skills_analysis,
        "Language Analysis": updated_lang_analysis,
        "Keyword Analysis": keyword_analysis,
        "Final Thoughts": final_thoughts,
        "Missing Keywords": missing_keywords,
        "Missing Skills": missing_skills,
        "Resume Domain": resume_domain,
        "Job Domain": job_domain,
        "Domain Penalty": domain_penalty,
        "Domain Similarity Score": similarity_score
    }

# Setup Vector DB
def setup_vectorstore(documents):
    embeddings = HuggingFaceEmbeddings(model_name="sentence-transformers/all-MiniLM-L6-v2")
    if DEVICE == "cuda":
        embeddings.model = embeddings.model.to(torch.device("cuda"))
    text_splitter = CharacterTextSplitter(chunk_size=500, chunk_overlap=100)
    doc_chunks = text_splitter.split_text("\n".join(documents))
    return FAISS.from_texts(doc_chunks, embeddings)

# Create Conversational Chain
def create_chain(vectorstore):
    # 🔁 Get a rotated admin key
    keys = load_groq_api_keys()
    index = st.session_state.get("key_index", 0)
    groq_api_key = keys[index % len(keys)]
    st.session_state["key_index"] = index + 1

    # ✅ Create the ChatGroq object
    llm = ChatGroq(model="llama-3.3-70b-versatile", temperature=0, groq_api_key=groq_api_key)

    # ✅ Build the chain
    chain = ConversationalRetrievalChain.from_llm(
        llm=llm,
        retriever=vectorstore.as_retriever(),
        return_source_documents=True
    )
    return chain

# Chat history
if "chat_history" not in st.session_state:
    st.session_state.chat_history = []

# ---------------- Sidebar Layout with Inline Images ----------------
st.sidebar.markdown("### 🏷️ Job Information")

# ---------------- Job Information Dropdown ----------------
with st.sidebar.expander("![Job](https://img.icons8.com/ios-filled/20/briefcase.png) Enter Job Details", expanded=False):
    job_title = st.text_input(
        "![Job](https://img.icons8.com/ios-filled/20/briefcase.png) Job Title"
    )

    user_location = st.text_input(
        "![Location](https://img.icons8.com/ios-filled/20/marker.png) Preferred Job Location (City, Country)"
    )

    job_description = st.text_area(
        "![Description](https://img.icons8.com/ios-filled/20/document.png) Paste Job Description",
        height=200
    )

    if job_description.strip() == "":
        st.warning("Please enter a job description to evaluate the resumes.")

# ---------------- Advanced Weights Dropdown ----------------
with st.sidebar.expander("![Settings](https://img.icons8.com/ios-filled/20/settings.png) Customize ATS Scoring Weights", expanded=False):
    edu_weight = st.slider("![Education](https://img.icons8.com/ios-filled/20/graduation-cap.png) Education Weight", 0, 50, 20)
    exp_weight = st.slider("![Experience](https://img.icons8.com/ios-filled/20/portfolio.png) Experience Weight", 0, 50, 35)
    skills_weight = st.slider("![Skills](https://img.icons8.com/ios-filled/20/gear.png) Skills Match Weight", 0, 50, 30)
    lang_weight = st.slider("![Language](https://img.icons8.com/ios-filled/20/language.png) Language Quality Weight", 0, 10, 5)
    keyword_weight = st.slider("![Keyword](https://img.icons8.com/ios-filled/20/key.png) Keyword Match Weight", 0, 20, 10)

    total_weight = edu_weight + exp_weight + skills_weight + lang_weight + keyword_weight

    # ---------------- Inline SVG Validation ----------------
    if total_weight != 100:
        st.markdown(
            f"""
            <div style="display:flex;align-items:center;gap:6px;
                        border:1px solid #fca5a5;
                        background:#fee2e2;
                        padding:8px;
                        border-radius:6px;">
                <svg xmlns="http://www.w3.org/2000/svg" width="18" height="18" fill="red" viewBox="0 0 24 24">
                    <path d="M12 2C6.48 2 2 6.48 2 12s4.48 10 10 10
                             10-4.48 10-10S17.52 2 12 2zm0 15
                             c-.83 0-1.5.67-1.5 1.5S11.17 20
                             12 20s1.5-.67 1.5-1.5S12.83 17
                             12 17zm1-4V7h-2v6h2z"/>
                </svg>
                <span style="color:#b91c1c;font-weight:500;">
                    Total = {total_weight}. Please make it exactly 100.
                </span>
            </div>
            """,
            unsafe_allow_html=True
        )
    else:
        st.markdown(
            f"""
            <div style="display:flex;align-items:center;gap:6px;
                        border:1px solid #86efac;
                        background:#dcfce7;
                        padding:8px;
                        border-radius:6px;">
                <svg xmlns="http://www.w3.org/2000/svg" width="18" height="18" fill="green" viewBox="0 0 24 24">
                    <path d="M9 16.2l-3.5-3.5-1.4 1.4L9
                             19 20.3 7.7l-1.4-1.4z"/>
                </svg>
                <span style="color:#166534;font-weight:500;">
                    Total weight = 100
                </span>
            </div>
            """,
            unsafe_allow_html=True
        )

with tab1:
    # 🎨 CSS for sliding success message
    st.markdown("""
    <style>
    .slide-message {
      position: relative;
      overflow: hidden;
      margin: 10px 0;
      padding: 10px 15px;
      border-radius: 10px;
      font-weight: bold;
      display: flex;
      align-items: center;
      gap: 8px;
      animation: slideIn 0.8s ease forwards;
    }
    .slide-message svg {
      width: 18px;
      height: 18px;
      flex-shrink: 0;
    }
    .success-msg { background: rgba(0,255,127,0.12); border-left: 5px solid #00FF7F; color:#00FF7F; }
    .error-msg   { background: rgba(255,99,71,0.12);  border-left: 5px solid #FF6347; color:#FF6347; }
    .warn-msg    { background: rgba(255,215,0,0.12); border-left: 5px solid #FFD700; color:#FFD700; }

    @keyframes slideIn {
      0%   { transform: translateX(100%); opacity: 0; }
      100% { transform: translateX(0); opacity: 1; }
    }
    </style>
    """, unsafe_allow_html=True)

    uploaded_files = st.file_uploader(
        "📄 Upload PDF Resumes",
        type=["pdf"],
        accept_multiple_files=True,
        help="Upload one or more resumes in PDF format (max 200MB each)."
    )

    if uploaded_files:
        for uploaded_file in uploaded_files:
            with st.container():
                st.subheader(f"📄 Original Resume Preview: {uploaded_file.name}")

                try:
                    # ✅ Show PDF preview safely
                    pdf_viewer(
                        uploaded_file.read(),
                        key=f"pdf_viewer_{uploaded_file.name}"
                    )

                    # Reset pointer so file can be read again later
                    uploaded_file.seek(0)

                    # ✅ Extract text safely
                    resume_text = safe_extract_text(uploaded_file)

                    if resume_text:
                        st.markdown(f"""
                        <div class='slide-message success-msg'>
                            <svg xmlns="http://www.w3.org/2000/svg" fill="none" stroke="currentColor"
                              stroke-width="2" viewBox="0 0 24 24"><path d="M5 13l4 4L19 7"/></svg>
                            ✅ Successfully processed <b>{uploaded_file.name}</b>
                        </div>
                        """, unsafe_allow_html=True)
                        # 🔹 Continue with ATS scoring, bias detection, etc. here
                    else:
                        st.markdown(f"""
                        <div class='slide-message warn-msg'>
                            ⚠️ <b>{uploaded_file.name}</b> does not contain valid resume text.
                        </div>
                        """, unsafe_allow_html=True)

                except Exception as e:
                    st.markdown(f"""
                    <div class='slide-message error-msg'>
                        ❌ Could not display or process <b>{uploaded_file.name}</b>: {e}
                    </div>
                    """, unsafe_allow_html=True)

# ✅ Initialize state
# Initialize session state
if "resume_data" not in st.session_state:
    st.session_state.resume_data = []

if "processed_files" not in st.session_state:
    st.session_state.processed_files = set()

resume_data = st.session_state.resume_data

# ✏️ Resume Evaluation Logic
if uploaded_files and job_description:
    all_text = []

    for uploaded_file in uploaded_files:
        if uploaded_file.name in st.session_state.processed_files:
            continue

        # ✅ Improved optimized scanner animation with better performance
        scanner_placeholder = st.empty()

        # ✅ IMPROVED: More efficient CSS animations with GPU acceleration
        OPTIMIZED_SCANNER_HTML = f"""
        <style>
        .scanner-overlay {{
            position: fixed;
            top: 0; left: 0;
            width: 100vw; height: 100vh;
            background: linear-gradient(135deg, #0b0c10 0%, #1a1c29 100%);
            display: flex;
            flex-direction: column;
            justify-content: center;
            align-items: center;
            z-index: 9999;
            will-change: transform, opacity;
        }}
        
        .scanner-doc {{
            width: 280px;
            height: 340px;
            background: linear-gradient(145deg, #f8f9fa, #e9ecef);
            border-radius: 16px;
            position: relative;
            overflow: hidden;
            box-shadow: 0 20px 40px rgba(0, 191, 255, 0.3);
            transform: translateZ(0);
            will-change: transform;
            animation: docFloat 3s ease-in-out infinite alternate;
        }}
        
        @keyframes docFloat {{
            0% {{ transform: translateY(0px) scale(1); }}
            100% {{ transform: translateY(-8px) scale(1.02); }}
        }}
        
        .doc-header {{
            padding: 20px;
            text-align: center;
            border-bottom: 2px solid #e9ecef;
        }}
        
        .doc-avatar {{
            width: 50px;
            height: 50px;
            background: linear-gradient(135deg, #667eea, #764ba2);
            border-radius: 50%;
            margin: 0 auto 10px;
            display: flex;
            align-items: center;
            justify-content: center;
            font-size: 20px;
            color: white;
        }}
        
        .doc-title {{
            font-size: 16px;
            font-weight: bold;
            color: #2c3e50;
            margin-bottom: 5px;
            font-family: 'Segoe UI', sans-serif;
        }}
        
        .doc-content {{
            padding: 15px;
            font-size: 12px;
            color: #6c757d;
            line-height: 1.4;
        }}
        
        .scan-line {{
            position: absolute;
            top: 0; left: 0;
            width: 100%; height: 4px;
            background: linear-gradient(90deg, transparent, rgba(0,191,255,0.8), transparent);
            animation: scanMove 2.5s ease-in-out infinite;
            box-shadow: 0 0 20px rgba(0,191,255,0.6);
            transform: translateZ(0);
            will-change: transform;
        }}
        
        @keyframes scanMove {{
            0% {{ top: 0; opacity: 1; }}
            50% {{ opacity: 0.8; }}
            100% {{ top: 340px; opacity: 1; }}
        }}
        
        .scanner-text {{
            margin-top: 30px;
            font-family: 'Orbitron', 'Segoe UI', sans-serif;
            font-weight: 600;
            font-size: 18px;
            color: #00bfff;
            text-shadow: 0 0 10px rgba(0,191,255,0.5);
            animation: textPulse 2s ease-in-out infinite;
        }}
        
        @keyframes textPulse {{
            0%, 100% {{ opacity: 1; transform: scale(1); }}
            50% {{ opacity: 0.8; transform: scale(1.05); }}
        }}
        
        .progress-bar {{
            width: 200px;
            height: 4px;
            background: rgba(255,255,255,0.2);
            border-radius: 2px;
            margin-top: 20px;
            overflow: hidden;
        }}
        
        .progress-fill {{
            height: 100%;
            background: linear-gradient(90deg, #00bfff, #1e90ff);
            border-radius: 2px;
            animation: progressFill 3s ease-in-out infinite;
            transform: translateX(-100%);
        }}
        
        @keyframes progressFill {{
            0% {{ transform: translateX(-100%); }}
            100% {{ transform: translateX(0); }}
        }}
        
        /* Mobile optimizations */
        @media (max-width: 768px) {{
            .scanner-doc {{ width: 240px; height: 300px; }}
            .scanner-text {{ font-size: 16px; }}
        }}
        </style>
        
        <div class="scanner-overlay">
            <div class="scanner-doc">
                <div class="scan-line"></div>
                <div class="doc-header">
                    <div class="doc-avatar">👤</div>
                    <div class="doc-title">{job_title}</div>
                </div>
                <div class="doc-content">
                    • Analyzing candidate profile...<br>
                    • Extracting key skills...<br>
                    • Matching with job requirements...<br>
                    • Calculating ATS compatibility...<br>
                    • Checking for bias patterns...
                </div>
            </div>
            <div class="scanner-text">Scanning Resume...</div>
            <div class="progress-bar">
                <div class="progress-fill"></div>
            </div>
        </div>
        """
        
        scanner_placeholder.markdown(OPTIMIZED_SCANNER_HTML, unsafe_allow_html=True)

        # ✅ Save uploaded file
        file_path = os.path.join(working_dir, uploaded_file.name)
        with open(file_path, "wb") as f:
            f.write(uploaded_file.getbuffer())

        # ✅ Reduced delay for better UX
        time.sleep(4)

        # ✅ Extract text from PDF
        text = extract_text_from_pdf(file_path)
        if not text:
            st.warning(f"⚠️ Could not extract text from {uploaded_file.name}. Skipping.")
            scanner_placeholder.empty()
            continue

        all_text.append(" ".join(text))
        full_text = " ".join(text)

        # ✅ Bias detection
        bias_score, masc_count, fem_count, detected_masc, detected_fem = detect_bias(full_text)

        # ✅ Rewrite and highlight gender-biased words
        highlighted_text, rewritten_text, _, _, _, _ = rewrite_and_highlight(
            full_text, replacement_mapping, user_location
        )

        # ✅ LLM-based ATS Evaluation
        ats_result, ats_scores = ats_percentage_score(
            resume_text=full_text,
            job_description=job_description,
            logic_profile_score=None,
            edu_weight=edu_weight,
            exp_weight=exp_weight,
            skills_weight=skills_weight,
            lang_weight=lang_weight,
            keyword_weight=keyword_weight
        )

        # ✅ Extract structured ATS values
        candidate_name = ats_scores.get("Candidate Name", "Not Found")
        ats_score = ats_scores.get("ATS Match %", 0)
        edu_score = ats_scores.get("Education Score", 0)
        exp_score = ats_scores.get("Experience Score", 0)
        skills_score = ats_scores.get("Skills Score", 0)
        lang_score = ats_scores.get("Language Score", 0)
        keyword_score = ats_scores.get("Keyword Score", 0)
        formatted_score = ats_scores.get("Formatted Score", "N/A")
        fit_summary = ats_scores.get("Final Thoughts", "N/A")
        language_analysis_full = ats_scores.get("Language Analysis", "N/A")

        missing_keywords_raw = ats_scores.get("Missing Keywords", "N/A")
        missing_skills_raw = ats_scores.get("Missing Skills", "N/A")
        missing_keywords = [kw.strip() for kw in missing_keywords_raw.split(",") if kw.strip()] if missing_keywords_raw != "N/A" else []
        missing_skills = [sk.strip() for sk in missing_skills_raw.split(",") if sk.strip()] if missing_skills_raw != "N/A" else []

        domain = db_manager.detect_domain_llm(
            job_title,
            job_description,
            session=st.session_state  # ✅ pass the Groq API key from session
        )

        bias_flag = "🔴 High Bias" if bias_score > 0.6 else "🟢 Fair"
        ats_flag = "⚠️ Low ATS" if ats_score < 50 else "✅ Good ATS"

        # ✅ Store everything in session state
        st.session_state.resume_data.append({
            "Resume Name": uploaded_file.name,
            "Candidate Name": candidate_name,
            "ATS Report": ats_result,
            "ATS Match %": ats_score,
            "Formatted Score": formatted_score,
            "Education Score": edu_score,
            "Experience Score": exp_score,
            "Skills Score": skills_score,
            "Language Score": lang_score,
            "Keyword Score": keyword_score,
            "Education Analysis": ats_scores.get("Education Analysis", ""),
            "Experience Analysis": ats_scores.get("Experience Analysis", ""),
            "Skills Analysis": ats_scores.get("Skills Analysis", ""),
            "Language Analysis": language_analysis_full,
            "Keyword Analysis": ats_scores.get("Keyword Analysis", ""),
            "Final Thoughts": fit_summary,
            "Missing Keywords": missing_keywords,
            "Missing Skills": missing_skills,
            "Bias Score (0 = Fair, 1 = Biased)": bias_score,
            "Bias Status": bias_flag,
            "Masculine Words": masc_count,
            "Feminine Words": fem_count,
            "Detected Masculine Words": detected_masc,
            "Detected Feminine Words": detected_fem,
            "Text Preview": full_text[:300] + "...",
            "Highlighted Text": highlighted_text,
            "Rewritten Text": rewritten_text,
            "Domain": domain
        })

        insert_candidate(
            (
                uploaded_file.name,
                candidate_name,
                ats_score,
                edu_score,
                exp_score,
                skills_score,
                lang_score,
                keyword_score,
                bias_score
            ),
            job_title=job_title,
            job_description=job_description
        )

        st.session_state.processed_files.add(uploaded_file.name)

        # ✅ IMPROVED: Smoother success animation with better transitions
        SUCCESS_HTML = """
        <style>
        .success-overlay {
            position: fixed;
            top: 0; left: 0;
            width: 100vw; height: 100vh;
            background: linear-gradient(135deg, #0b0c10 0%, #1a1c29 100%);
            display: flex;
            flex-direction: column;
            justify-content: center;
            align-items: center;
            z-index: 9999;
            animation: fadeIn 0.5s ease-out;
        }
        
        @keyframes fadeIn {
            0% { opacity: 0; }
            100% { opacity: 1; }
        }
        
        .success-circle {
            width: 140px;
            height: 140px;
            border: 3px solid #00bfff;
            border-radius: 50%;
            position: relative;
            display: flex;
            align-items: center;
            justify-content: center;
            background: radial-gradient(circle, rgba(0,191,255,0.1) 0%, rgba(0,191,255,0.05) 50%, transparent 100%);
            animation: successPulse 2s ease-in-out infinite;
        }
        
        @keyframes successPulse {
            0%, 100% { 
                transform: scale(1);
                box-shadow: 0 0 20px rgba(0,191,255,0.3);
            }
            50% { 
                transform: scale(1.05);
                box-shadow: 0 0 30px rgba(0,191,255,0.6);
            }
        }
        
        .success-checkmark {
            font-size: 48px;
            color: #00ff7f;
            animation: checkmarkPop 0.8s ease-out;
        }
        
        @keyframes checkmarkPop {
            0% { transform: scale(0) rotate(-45deg); opacity: 0; }
            50% { transform: scale(1.2) rotate(-10deg); opacity: 0.8; }
            100% { transform: scale(1) rotate(0deg); opacity: 1; }
        }
        
        .success-text {
            margin-top: 25px;
            font-family: 'Orbitron', 'Segoe UI', sans-serif;
            font-size: 20px;
            font-weight: 600;
            color: #00bfff;
            text-shadow: 0 0 10px rgba(0,191,255,0.5);
            animation: textSlideUp 0.8s ease-out 0.3s both;
        }
        
        @keyframes textSlideUp {
            0% { transform: translateY(20px); opacity: 0; }
            100% { transform: translateY(0); opacity: 1; }
        }
        
        .success-subtitle {
            margin-top: 10px;
            font-size: 14px;
            color: #8e9aaf;
            animation: textSlideUp 0.8s ease-out 0.5s both;
        }
        </style>
        
        <div class="success-overlay">
            <div class="success-circle">
                <div class="success-checkmark">✓</div>
            </div>
            <div class="success-text">Scan Complete!</div>
            <div class="success-subtitle">Resume analysis ready</div>
        </div>
        """
        
        # Clear scanner and show success animation
        scanner_placeholder.empty()
        success_placeholder = st.empty()
        success_placeholder.markdown(SUCCESS_HTML, unsafe_allow_html=True)

        # ⏳ Shorter delay for better UX, then clear and rerun
        time.sleep(3)
        success_placeholder.empty()
        st.rerun()

    # ✅ Optional vectorstore setup
    if all_text:
        st.session_state.vectorstore = setup_vectorstore(all_text)
        st.session_state.chain = create_chain(st.session_state.vectorstore)

# 🔄 Developer Reset Button
with tab1:
    if st.button("🔄 Refresh view"):
        st.session_state.processed_files.clear()
        st.session_state.resume_data.clear()

        # Temporary placeholder for sliding success message
        msg_placeholder = st.empty()
        msg_placeholder.markdown("""
        <div class='slide-message success-msg'>
            <svg xmlns="http://www.w3.org/2000/svg" fill="none" stroke="currentColor"
              stroke-width="2" viewBox="0 0 24 24"><path d="M5 13l4 4L19 7"/></svg>
            ✅ Cleared uploaded resume history. You can re-upload now.
        </div>
        """, unsafe_allow_html=True)

        # Wait 3 seconds then clear message
        time.sleep(3)
        msg_placeholder.empty()

def generate_resume_report_html(resume):
    candidate_name = resume.get('Candidate Name', 'Not Found')
    resume_name = resume.get('Resume Name', 'Unknown')
    rewritten_text = resume.get('Rewritten Text', '').replace("\n", "<br/>")

    masculine_words_list = resume.get("Detected Masculine Words", [])
    masculine_words = "".join(
        f"<b>{item.get('word','')}</b>: {item.get('sentence','')}<br/>"
        for item in masculine_words_list
    ) if masculine_words_list else "<i>None detected.</i>"

    feminine_words_list = resume.get("Detected Feminine Words", [])
    feminine_words = "".join(
        f"<b>{item.get('word','')}</b>: {item.get('sentence','')}<br/>"
        for item in feminine_words_list
    ) if feminine_words_list else "<i>None detected.</i>"

    ats_report_html = resume.get("ATS Report", "").replace("\n", "<br/>")

    def style_analysis(analysis, fallback="N/A"):
        if not analysis or analysis == "N/A":
            return f"<p><i>{fallback}</i></p>"

        if "**Score:**" in analysis:
            parts = analysis.split("**Score:**")
            rest = parts[1].split("**", 1)
            score_text = rest[0].strip()
            remaining = rest[1].strip() if len(rest) > 1 else ""
            return f"<p><b>Score:</b> {score_text}</p><p>{remaining}</p>"
        else:
            return f"<p>{analysis}</p>"

    edu_analysis = style_analysis(resume.get("Education Analysis", "").replace("\n", "<br/>"))
    exp_analysis = style_analysis(resume.get("Experience Analysis", "").replace("\n", "<br/>"))
    skills_analysis = style_analysis(resume.get("Skills Analysis", "").replace("\n", "<br/>"))
    keyword_analysis = style_analysis(resume.get("Keyword Analysis", "").replace("\n", "<br/>"))
    final_thoughts = resume.get("Final Thoughts", "N/A").replace("\n", "<br/>")

    lang_analysis_raw = resume.get("Language Analysis", "").replace("\n", "<br/>")
    lang_analysis = f"<div>{lang_analysis_raw}</div>" if lang_analysis_raw else "<p><i>No language analysis available.</i></p>"

    ats_match = resume.get('ATS Match %', 'N/A')
    edu_score = resume.get('Education Score', 'N/A')
    exp_score = resume.get('Experience Score', 'N/A')
    skills_score = resume.get('Skills Score', 'N/A')
    lang_score = resume.get('Language Score', 'N/A')
    keyword_score = resume.get('Keyword Score', 'N/A')
    masculine_count = len(masculine_words_list)
    feminine_count = len(feminine_words_list)
    bias_score = resume.get('Bias Score (0 = Fair, 1 = Biased)', 'N/A')

    return f"""
    <html>
    <head>
        <style>
            body {{
                font-family: Helvetica, sans-serif;
                font-size: 12pt;
                line-height: 1.5;
                color: #000;
            }}
            h1, h2 {{
                color: #2f4f6f;
            }}
            table {{
                width: 100%;
                border-collapse: collapse;
                margin-bottom: 15px;
            }}
            td {{
                padding: 4px;
                vertical-align: top;
                border: 1px solid #ccc;
            }}
            ul {{
                margin: 0.5em 0;
                padding-left: 1.4em;
            }}
            li {{
                margin-bottom: 5px;
            }}
            .section-title {{
                background-color: #e0e0e0;
                font-weight: bold;
                padding: 6px;
                margin-top: 12px;
                border-left: 4px solid #666;
            }}
            .box {{
                padding: 10px;
                margin-top: 6px;
                background-color: #f9f9f9;
                border-left: 4px solid #999;
            }}
        </style>
    </head>
    <body>

    <h1>Resume Analysis Report</h1>

    <h2>Candidate: {candidate_name}</h2>
    <p><b>Resume File:</b> {resume_name}</p>

    <h2>ATS Evaluation</h2>
    <table>
        <tr><td><b>ATS Match</b></td><td>{ats_match}%</td></tr>
        <tr><td><b>Education</b></td><td>{edu_score}</td></tr>
        <tr><td><b>Experience</b></td><td>{exp_score}</td></tr>
        <tr><td><b>Skills</b></td><td>{skills_score}</td></tr>
        <tr><td><b>Language</b></td><td>{lang_score}</td></tr>
        <tr><td><b>Keyword</b></td><td>{keyword_score}</td></tr>
    </table>

    <div class="section-title">ATS Report</div>
    <div class="box">{ats_report_html}</div>

    <div class="section-title">Education Analysis</div>
    <div class="box">{edu_analysis}</div>

    <div class="section-title">Experience Analysis</div>
    <div class="box">{exp_analysis}</div>

    <div class="section-title">Skills Analysis</div>
    <div class="box">{skills_analysis}</div>

    <div class="section-title">Language Analysis</div>
    <div class="box">{lang_analysis}</div>

    <div class="section-title">Keyword Analysis</div>
    <div class="box">{keyword_analysis}</div>

    <div class="section-title">Final Thoughts</div>
    <div class="box">{final_thoughts}</div>

    <h2>Gender Bias Analysis</h2>
    <table>
        <tr><td><b>Masculine Words</b></td><td>{masculine_count}</td></tr>
        <tr><td><b>Feminine Words</b></td><td>{feminine_count}</td></tr>
        <tr><td><b>Bias Score (0 = Fair, 1 = Biased)</b></td><td>{bias_score}</td></tr>
    </table>

    <div class="section-title">Masculine Words Detected</div>
    <div class="box">{masculine_words}</div>

    <div class="section-title">Feminine Words Detected</div>
    <div class="box">{feminine_words}</div>

    <h2>Rewritten Bias-Free Resume</h2>
    <div class="box">{rewritten_text}</div>

    </body>
    </html>
    """

# === TAB 1: Dashboard ===
with tab1:
    resume_data = st.session_state.get("resume_data", [])

    if resume_data:
        # ✅ Calculate total counts safely
        total_masc = sum(len(r.get("Detected Masculine Words", [])) for r in resume_data)
        total_fem = sum(len(r.get("Detected Feminine Words", [])) for r in resume_data)
        avg_bias = round(np.mean([r.get("Bias Score (0 = Fair, 1 = Biased)", 0) for r in resume_data]), 2)
        total_resumes = len(resume_data)

        st.markdown("### 📊 Summary Statistics")
        col1, col2, col3, col4 = st.columns(4)
        with col1:
            st.metric("📄 Resumes Uploaded", total_resumes)
        with col2:
            st.metric("🔎 Avg. Bias Score", avg_bias)
        with col3:
            st.metric("🔵 Total Masculine Words", total_masc)
        with col4:
            st.metric("🔴 Total Feminine Words", total_fem)

        st.markdown("### 🗂️ Resumes Overview")
        df = pd.DataFrame(resume_data)

        # ✅ Add calculated count columns safely
        df["Masculine Words Count"] = df["Detected Masculine Words"].apply(lambda x: len(x) if isinstance(x, list) else 0)
        df["Feminine Words Count"] = df["Detected Feminine Words"].apply(lambda x: len(x) if isinstance(x, list) else 0)

        overview_cols = [
            "Resume Name", "Candidate Name", "ATS Match %", "Education Score",
            "Experience Score", "Skills Score", "Language Score", "Keyword Score",
            "Bias Score (0 = Fair, 1 = Biased)", "Masculine Words Count", "Feminine Words Count"
        ]

        st.dataframe(df[overview_cols], use_container_width=True)

        st.markdown("### 📊 Visual Analysis")
        chart_tab1, chart_tab2 = st.tabs(["📉 Bias Score Chart", "⚖ Gender-Coded Words"])
        with chart_tab1:
            st.subheader("Bias Score Comparison Across Resumes")
            st.bar_chart(df.set_index("Resume Name")[["Bias Score (0 = Fair, 1 = Biased)"]])
        with chart_tab2:
            st.subheader("Masculine vs Feminine Word Usage")
            fig, ax = plt.subplots(figsize=(10, 5))
            index = np.arange(len(df))
            bar_width = 0.35
            ax.bar(index, df["Masculine Words Count"], bar_width, label="Masculine", color="#3498db")
            ax.bar(index + bar_width, df["Feminine Words Count"], bar_width, label="Feminine", color="#e74c3c")
            ax.set_xlabel("Resumes", fontsize=12)
            ax.set_ylabel("Word Count", fontsize=12)
            ax.set_title("Gender-Coded Word Usage per Resume", fontsize=14)
            ax.set_xticks(index + bar_width / 2)
            ax.set_xticklabels(df["Resume Name"], rotation=45, ha='right')
            ax.legend()
            st.pyplot(fig)

        st.markdown("### 📝 Detailed Resume Reports")
        for resume in resume_data:
            candidate_name = resume.get("Candidate Name", "Not Found")
            resume_name = resume.get("Resume Name", "Unknown")
            missing_keywords = resume.get("Missing Keywords", [])
            missing_skills = resume.get("Missing Skills", [])

            with st.expander(f"📄 {resume_name} | {candidate_name}"):
                st.markdown(f"### 📊 ATS Evaluation for: **{candidate_name}**")
                score_col1, score_col2, score_col3 = st.columns(3)
                with score_col1:
                    st.metric("📈 Overall Match", f"{resume.get('ATS Match %', 'N/A')}%")
                with score_col2:
                    st.metric("🏆 Formatted Score", resume.get("Formatted Score", "N/A"))
                with score_col3:
                    st.metric("🧠 Language Quality", f"{resume.get('Language Score', 'N/A')} / {lang_weight}")

                col_a, col_b, col_c, col_d = st.columns(4)
                with col_a:
                    st.metric("🎓 Education Score", f"{resume.get('Education Score', 'N/A')} / {edu_weight}")
                with col_b:
                    st.metric("💼 Experience Score", f"{resume.get('Experience Score', 'N/A')} / {exp_weight}")
                with col_c:
                    st.metric("🛠 Skills Score", f"{resume.get('Skills Score', 'N/A')} / {skills_weight}")
                with col_d:
                    st.metric("🔍 Keyword Score", f"{resume.get('Keyword Score', 'N/A')} / {keyword_weight}")

                # Fit summary
                st.markdown("### 📝 Fit Summary")
                st.write(resume.get('Final Thoughts', 'N/A'))

                # ATS Report
                if resume.get("ATS Report"):
                    st.markdown("### 📋 ATS Evaluation Report")
                    st.markdown(resume["ATS Report"], unsafe_allow_html=True)

                # ATS Chart
                st.markdown("### 📊 ATS Score Breakdown Chart")
                ats_df = pd.DataFrame({
                    'Component': ['Education', 'Experience', 'Skills', 'Language', 'Keywords'],
                    'Score': [
                        resume.get("Education Score", 0),
                        resume.get("Experience Score", 0),
                        resume.get("Skills Score", 0),
                        resume.get("Language Score", 0),
                        resume.get("Keyword Score", 0)
                    ]
                })
                ats_chart = alt.Chart(ats_df).mark_bar().encode(
                    x=alt.X('Component', sort=None),
                    y=alt.Y('Score', scale=alt.Scale(domain=[0, 50])),
                    color='Component',
                    tooltip=['Component', 'Score']
                ).properties(
                    title="ATS Evaluation Breakdown",
                    width=600,
                    height=300
                )
                st.altair_chart(ats_chart, use_container_width=True)

                # 🔷 Detailed ATS Analysis Cards
                st.markdown("### 🔍 Detailed ATS Section Analyses")
                for section_title, key in [
                    ("🏫 Education Analysis", "Education Analysis"),
                    ("💼 Experience Analysis", "Experience Analysis"),
                    ("🛠 Skills Analysis", "Skills Analysis"),
                    ("🗣 Language Quality Analysis", "Language Analysis"),
                    ("🔑 Keyword Analysis", "Keyword Analysis"),
                    ("✅ Final Thoughts", "Final Thoughts")
                ]:
                    analysis_content = resume.get(key, "N/A")
                    if "**Score:**" in analysis_content:
                        parts = analysis_content.split("**Score:**")
                        rest = parts[1].split("**", 1)
                        score_text = rest[0].strip()
                        remaining = rest[1].strip() if len(rest) > 1 else ""
                        formatted_score = f"<div style='background:#4c1d95;color:white;padding:8px;border-radius:6px;margin-bottom:5px;'><b>Score:</b> {score_text}</div>"
                        analysis_html = formatted_score + f"<p>{remaining}</p>"
                    else:
                        analysis_html = f"<p>{analysis_content}</p>"

                    st.markdown(f"""
<div style="background:#5b3cc4; color:white; padding:10px; border-radius:6px;">
  <h3>{section_title}</h3>
</div>
<div style="background:#2d2d3a; color:white; padding:10px; border-radius:6px;">
{analysis_html}
</div>
""", unsafe_allow_html=True)

                st.divider()

                detail_tab1, detail_tab2 = st.tabs(["🔎 Bias Analysis", "✅ Rewritten Resume"])

                with detail_tab1:
                    st.markdown("#### Bias-Highlighted Original Text")
                    st.markdown(resume["Highlighted Text"], unsafe_allow_html=True)

                    st.markdown("### 📌 Gender-Coded Word Counts:")
                    bias_col1, bias_col2 = st.columns(2)

                    with bias_col1:
                        st.metric("🔵 Masculine Words", len(resume["Detected Masculine Words"]))
                        if resume["Detected Masculine Words"]:
                            st.markdown("### 📚 Detected Masculine Words with Context:")
                            for item in resume["Detected Masculine Words"]:
                                word = item['word']
                                sentence = item['sentence']
                                st.write(f"🔵 **{word}**: {sentence}", unsafe_allow_html=True)
                        else:
                            st.info("No masculine words detected.")

                    with bias_col2:
                        st.metric("🔴 Feminine Words", len(resume["Detected Feminine Words"]))
                        if resume["Detected Feminine Words"]:
                            st.markdown("### 📚 Detected Feminine Words with Context:")
                            for item in resume["Detected Feminine Words"]:
                                word = item['word']
                                sentence = item['sentence']
                                st.write(f"🔴 **{word}**: {sentence}", unsafe_allow_html=True)
                        else:
                            st.info("No feminine words detected.")

                with detail_tab2:
                    st.markdown("#### ✨ Bias-Free Rewritten Resume")
                    st.write(resume["Rewritten Text"])
                    docx_file = generate_docx(resume["Rewritten Text"])
                    st.download_button(
                        label="📥 Download Bias-Free Resume (.docx)",
                        data=docx_file,
                        file_name=f"{resume['Resume Name'].split('.')[0]}_bias_free.docx",
                        mime="application/vnd.openxmlformats-officedocument.wordprocessingml.document",
                        use_container_width=True,
                        key=f"download_docx_{resume['Resume Name']}"
                    )
                    html_report = generate_resume_report_html(resume)
                    
                    pdf_file = html_to_pdf_bytes(html_report)
                    st.download_button(
                    label="📄 Download Full Analysis Report (.pdf)",
                    data=pdf_file,
                    file_name=f"{resume['Resume Name'].split('.')[0]}_report.pdf",
                    mime="application/pdf",
                    use_container_width=True,
                    key=f"download_pdf_{resume['Resume Name']}"
                    )               

    else:           
        st.warning("⚠️ Please upload resumes to view dashboard analytics.")
from xhtml2pdf import pisa
from io import BytesIO

def html_to_pdf_bytes(html_string):
    styled_html = f"""
    <html>
    <head>
        <meta charset="UTF-8">
        <style>
            @page {{
                size: 400mm 297mm;  /* Original custom large page size */
                margin-top: 10mm;
                margin-bottom: 10mm;
                margin-left: 10mm;
                margin-right: 10mm;
            }}
            body {{
                font-size: 14pt;
                font-family: "Segoe UI", "Helvetica", sans-serif;
                line-height: 1.5;
                color: #000;
            }}
            h1, h2, h3 {{
                color: #2f4f6f;
            }}
            table {{
                width: 100%;
                border-collapse: collapse;
                margin-bottom: 15px;
            }}
            td {{
                padding: 4px;
                vertical-align: top;
                border: 1px solid #ccc;
            }}
            .section-title {{
                background-color: #e0e0e0;
                font-weight: bold;
                padding: 6px;
                margin-top: 10px;
            }}
            .box {{
                padding: 8px;
                margin-top: 6px;
                background-color: #f9f9f9;
                border-left: 4px solid #999;  /* More elegant than full border */
            }}
            ul {{
                margin: 0.5em 0;
                padding-left: 1.5em;
            }}
            li {{
                margin-bottom: 5px;
            }}
        </style>
    </head>
    <body>
        {html_string}
    </body>
    </html>
    """

    pdf_io = BytesIO()
    pisa.CreatePDF(styled_html, dest=pdf_io)
    pdf_io.seek(0)
    return pdf_io

def _fmt_desc(text, font_size="14px", color="#374151", line_height="1.75"):
    """
    ATS-friendly, readable description formatter shared by all 9 templates.

    Rules:
    - Lines starting with  - / • / * / · / > become proper <li> bullet items
      wrapped in a <ul> block (consecutive bullets are grouped).
    - Blank lines produce paragraph breaks (<p> spacing).
    - Non-bullet, non-blank lines become plain <p> paragraphs.
    - Never outputs raw <br> soup — every line gets a proper container.
    """
    if not text or not text.strip():
        return ""

    BULLET_PREFIXES = ("-", "•", "*", "·", ">", "–", "—")

    def is_bullet(line):
        stripped = line.strip()
        for p in BULLET_PREFIXES:
            if stripped.startswith(p):
                return stripped[len(p):].strip()
        return None

    lines = text.replace('\r\n', '\n').replace('\r', '\n').split('\n')

    base_style = (
        f"font-size:{font_size};"
        f"color:{color};"
        f"line-height:{line_height};"
        f"margin:0 0 6px 0;"
        f"padding:0;"
    )
    p_style   = f"style='{base_style}'"
    ul_style  = f"style='margin:0 0 8px 0;padding-left:20px;list-style-type:disc;'"
    li_style  = (
        f"style='"
        f"font-size:{font_size};"
        f"color:{color};"
        f"line-height:{line_height};"
        f"margin-bottom:4px;"
        f"'"
    )

    segments   = []   # list of ('p', text) | ('bullets', [text, ...]) | ('blank',)
    bullet_buf = []

    def flush_bullets():
        if bullet_buf:
            segments.append(('bullets', list(bullet_buf)))
            bullet_buf.clear()

    for raw in lines:
        line = raw.rstrip()
        if not line.strip():
            flush_bullets()
            segments.append(('blank',))
            continue
        b = is_bullet(line)
        if b is not None:
            bullet_buf.append(b)
        else:
            flush_bullets()
            segments.append(('p', line.strip()))

    flush_bullets()

    # Collapse consecutive blanks
    out_segs = []
    prev_blank = False
    for seg in segments:
        if seg[0] == 'blank':
            if not prev_blank and out_segs:
                out_segs.append(seg)
            prev_blank = True
        else:
            prev_blank = False
            out_segs.append(seg)

    html_parts = []
    for seg in out_segs:
        if seg[0] == 'blank':
            html_parts.append(f"<div style='height:6px;'></div>")
        elif seg[0] == 'p':
            html_parts.append(f"<p {p_style}>{seg[1]}</p>")
        elif seg[0] == 'bullets':
            items = "".join(f"<li {li_style}>{item}</li>" for item in seg[1])
            html_parts.append(f"<ul {ul_style}>{items}</ul>")

    return "".join(html_parts)


def render_template_default(session_state, profile_img_html=""):
    """Default professional template - keeps the exact same design as before"""
    
    # Enhanced SKILLS with professional, muted colors
    skills_html = "".join(
        f"""
        <div style='display:inline-block; 
                    background: linear-gradient(135deg, #e2e8f0 0%, #cbd5e1 100%);
                    color: #334155; 
                    padding: 10px 18px; 
                    margin: 8px 8px 8px 0; 
                    border-radius: 25px; 
                    font-size: 14px; 
                    font-weight: 600;
                    box-shadow: 0 2px 8px rgba(148, 163, 184, 0.2);
                    transition: all 0.3s ease;
                    text-shadow: none;
                    border: 1px solid rgba(148, 163, 184, 0.3);'>
            {s.strip()}
        </div>
        """
        for s in session_state['skills'].split(',')
        if s.strip()
    )

    # Enhanced LANGUAGES with soft, professional design
    languages_html = "".join(
        f"""
        <div style='display:inline-block; 
                    background: linear-gradient(135deg, #f1f5f9 0%, #e2e8f0 100%);
                    color: #475569; 
                    padding: 10px 18px; 
                    margin: 8px 8px 8px 0; 
                    border-radius: 25px; 
                    font-size: 14px; 
                    font-weight: 600;
                    box-shadow: 0 2px 8px rgba(100, 116, 139, 0.15);
                    transition: all 0.3s ease;
                    text-shadow: none;
                    border: 1px solid rgba(148, 163, 184, 0.3);'>
            {lang.strip()}
        </div>
        """
        for lang in session_state['languages'].split(',')
        if lang.strip()
    )

    # Enhanced INTERESTS with subtle colors
    interests_html = "".join(
        f"""
        <div style='display:inline-block; 
                    background: linear-gradient(135deg, #f0f9ff 0%, #e0f2fe 100%);
                    color: #0f172a; 
                    padding: 10px 18px; 
                    margin: 8px 8px 8px 0; 
                    border-radius: 25px; 
                    font-size: 14px; 
                    font-weight: 600;
                    box-shadow: 0 2px 8px rgba(14, 165, 233, 0.1);
                    transition: all 0.3s ease;
                    text-shadow: none;
                    border: 1px solid rgba(186, 230, 253, 0.5);'>
            {interest.strip()}
        </div>
        """
        for interest in session_state['interests'].split(',')
        if interest.strip()
    )

    # Enhanced SOFT SKILLS with warm but professional styling
    Softskills_html = "".join(
        f"""
        <div style='display:inline-block; 
                    background: linear-gradient(135deg, #fefce8 0%, #fef3c7 100%);
                    color: #451a03; 
                    padding: 10px 20px; 
                    margin: 8px 8px 8px 0; 
                    border-radius: 25px; 
                    font-size: 14px; 
                    font-family: "Segoe UI", sans-serif; 
                    font-weight: 600;
                    box-shadow: 0 2px 8px rgba(217, 119, 6, 0.1);
                    transition: all 0.3s ease;
                    border: 1px solid rgba(254, 215, 170, 0.6);'>
            {skill.strip().title()}
        </div>
        """
        for skill in session_state['Softskills'].split(',')
        if skill.strip()
    )

    # Enhanced EXPERIENCE with professional, subtle design
    experience_html = ""
    for exp in session_state.experience_entries:
        if exp["company"] or exp["title"]:
            # Handle paragraphs and single line breaks using ATS-friendly formatter
            description_html = _fmt_desc(exp["description"], font_size="15px", color="#374151", line_height="1.75")

            experience_html += f"""
            <div style='
                margin-bottom: 24px;
                padding: 20px;
                border-radius: 12px;
                background: linear-gradient(145deg, #fafafa 0%, #f4f4f5 100%);
                box-shadow: 
                    0 4px 12px rgba(0, 0, 0, 0.05),
                    0 1px 3px rgba(0, 0, 0, 0.1);
                font-family: "Inter", "Segoe UI", sans-serif;
                color: #374151;
                line-height: 1.6;
                border: 1px solid rgba(229, 231, 235, 0.8);
                position: relative;
                overflow: hidden;
            '>
                <!-- Subtle accent bar -->
                <div style='
                    position: absolute;
                    top: 0;
                    left: 0;
                    right: 0;
                    height: 3px;
                    background: linear-gradient(90deg, #6b7280, #9ca3af);
                '></div>
                
                <!-- Header Card -->
                <div style='
                    background: rgba(255, 255, 255, 0.8);
                    border-radius: 8px;
                    padding: 14px 18px;
                    margin-bottom: 12px;
                    border: 1px solid rgba(229, 231, 235, 0.6);
                '>
                    <div style='
                        display: flex;
                        justify-content: space-between;
                        align-items: center;
                        font-weight: 700;
                        font-size: 18px;
                        margin-bottom: 6px;
                        color: #1f2937;
                        width: 100%;
                    '>
                        <div style='display: flex; align-items: center;'>
                            <div style='
                                width: 6px; 
                                height: 6px; 
                                background: #6b7280;
                                border-radius: 50%; 
                                margin-right: 12px;
                            '></div>
                            <span>{exp['company']}</span>
                        </div>
                        <div style='
                            display: inline-flex;
                            align-items: center;
                            gap: 6px;
                            background: linear-gradient(135deg, #f9fafb, #f3f4f6);
                            color: #374151;
                            padding: 5px 14px;
                            border-radius: 16px;
                            font-size: 14px;
                            font-weight: 600;
                            box-shadow: 0 1px 3px rgba(0,0,0,0.1);
                            border: 1px solid rgba(209, 213, 219, 0.5);
                        '>
                            <svg xmlns="http://www.w3.org/2000/svg" width="14" height="14" fill="currentColor" viewBox="0 0 16 16">
                                <path d="M3.5 0a.5.5 0 0 1 .5.5V1h8V.5a.5.5 0 0 1 1 0V1h1a2 2 0 0 1 2 2v11a2 2 0 0 1-2 2H2a2 2 0 0 1-2-2V3a2 2 0 0 1 2-2h1V.5a.5.5 0 0 1 .5-.5zM1 4v10a1 1 0 0 0 1 1h12a1 1 0 0 0 1-1V4H1z"/>
                            </svg>
                            <span>{exp['duration']}</span>
                        </div>
                    </div>

                    <div style='
                        display: flex;
                        align-items: center;
                        font-size: 16px;
                        font-weight: 600;
                        color: #4b5563;
                    '>
                        <div style='
                            width: 4px; 
                            height: 4px; 
                            background: #6b7280;
                            border-radius: 50%; 
                            margin-right: 10px;
                        '></div>
                        <span>{exp['title']}</span>
                    </div>
                </div>

                <!-- Description -->
                <div style='
                    font-size: 15px;
                    font-weight: 500;
                    color: #374151;
                    line-height: 1.7;
                    padding-left: 8px;
                '>
                    <div style='
                        border-left: 2px solid #d1d5db;
                        padding-left: 16px;
                        margin-left: 8px;
                    '>
                        {description_html}
                    </div>
                </div>
            </div>
            """

    # Convert experience to list if multiple lines
    # Escape HTML and convert line breaks
    summary_html = _fmt_desc(session_state['summary'], font_size="15px", color="#374151", line_height="1.8")

    # Enhanced EDUCATION with professional styling
    education_html = ""
    for edu in session_state.education_entries:
        if edu.get("institution") or edu.get("details"):
            degree_text = ""
            if edu.get("degree"):
                degree_val = edu["degree"]
                if isinstance(degree_val, list):
                    degree_val = ", ".join(degree_val)
                degree_text = f"""
                <div style='
                    display: flex; 
                    align-items: center; 
                    font-size: 15px; 
                    color: #374151; 
                    margin-bottom: 8px;
                    font-weight: 600;
                '>
                    <div style='
                        width: 4px; 
                        height: 4px; 
                        background: #6b7280;
                        border-radius: 50%; 
                        margin-right: 10px;
                    '></div>
                    <b>{degree_val}</b>
                </div>
                """

            # Education Card
            education_html += f"""
            <div style='
                margin-bottom: 26px;
                padding: 22px 26px;
                border-radius: 12px;
                background: linear-gradient(145deg, #f9fafb 0%, #f3f4f6 100%);
                box-shadow: 
                    0 4px 12px rgba(0, 0, 0, 0.06),
                    0 1px 3px rgba(0, 0, 0, 0.08);
                font-family: "Inter", "Segoe UI", sans-serif;
                color: #1f2937;
                line-height: 1.6;
                border: 1px solid #e5e7eb;
                position: relative;
                overflow: hidden;
            '>
                <!-- Subtle accent bar -->
                <div style='
                    position: absolute;
                    top: 0;
                    left: 0;
                    right: 0;
                    height: 3px;
                    background: linear-gradient(90deg, #6b7280, #9ca3af);
                '></div>

                <div style='
                    display: flex;
                    justify-content: space-between;
                    align-items: center;
                    font-size: 18px;
                    font-weight: 700;
                    margin-bottom: 12px;
                    width: 100%;
                    color: #111827;
                '>
                    <div style='display: flex; align-items: center;'>
                        <div style='
                            width: 6px; 
                            height: 6px; 
                            background: #6b7280;
                            border-radius: 50%; 
                            margin-right: 12px;
                        '></div>
                        <span>{edu.get('institution', '')}</span>
                    </div>
                    <div style='
                        display: flex;
                        align-items: center;
                        gap: 6px;
                        background: rgba(255, 255, 255, 0.7);
                        color: #374151;
                        padding: 6px 16px;
                        border-radius: 16px;
                        font-weight: 600;
                        font-size: 14px;
                        box-shadow: 0 1px 3px rgba(0,0,0,0.1);
                        border: 1px solid #d1d5db;
                    '>
                        <!-- Inline SVG Calendar Icon -->
                        <svg xmlns="http://www.w3.org/2000/svg" 
                            fill="none" viewBox="0 0 24 24" 
                            stroke="currentColor" width="16" height="16">
                            <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" 
                                d="M8 7V3m8 4V3m-9 8h10M5 21h14a2 2 0 002-2V7a2 
                                2 0 00-2-2H5a2 2 0 00-2 2v12a2 2 0 002 2z" />
                        </svg>
                        {edu.get('year', '')}
                    </div>
                </div>
                {degree_text}
                <div style='
                    font-size: 14px; 
                    font-style: italic;
                    color: #374151;
                    line-height: 1.6;
                    padding-left: 18px;
                    border-left: 2px solid #9ca3af;
                '>
                    {edu.get('details', '')}
                </div>
            </div>
            """

    # Enhanced PROJECTS with professional card design
    projects_html = ""
    for proj in session_state.project_entries:
        if proj.get("title") or proj.get("description"):
            tech_val = proj.get("tech")
            if isinstance(tech_val, list):
                tech_val = ", ".join(tech_val)
            tech_text = f"""
            <div style='
                display: flex; 
                align-items: center; 
                font-size: 14px; 
                color: #374151; 
                margin-bottom: 12px;
                font-weight: 600;
                background: rgba(255, 255, 255, 0.7);
                padding: 8px 16px;
                border-radius: 8px;
                border: 1px solid rgba(229, 231, 235, 0.6);
            '>
                <div style='
                    width: 4px; 
                    height: 4px; 
                    background: #6b7280;
                    border-radius: 50%; 
                    margin-right: 10px;
                '></div>
                <b>Technologies:</b>&nbsp;&nbsp;{tech_val if tech_val else ''}
            </div>
            """ if tech_val else ""

            description_items = _fmt_desc(proj.get("description",""), font_size="15px", color="#334155", line_height="1.75") if proj.get("description") else ""

            projects_html += f"""
            <div style='
                margin-bottom: 30px;
                padding: 26px;
                border-radius: 12px;
                background: linear-gradient(145deg, #f8fafc 0%, #f1f5f9 100%);
                box-shadow: 
                    0 4px 12px rgba(100, 116, 139, 0.1),
                    0 1px 3px rgba(0, 0, 0, 0.1);
                font-family: "Inter", "Segoe UI", sans-serif;
                color: #334155;
                line-height: 1.7;
                border: 1px solid rgba(203, 213, 225, 0.5);
                position: relative;
                overflow: hidden;
            '>
                <!-- Subtle accent bar -->
                <div style='
                    position: absolute;
                    top: 0;
                    left: 0;
                    right: 0;
                    height: 3px;
                    background: linear-gradient(90deg, #64748b, #94a3b8);
                '></div>

                <div style='
                    font-size: 19px;
                    font-weight: 700;
                    margin-bottom: 16px;
                    display: flex;
                    justify-content: space-between;
                    align-items: center;
                    color: #1e293b;
                    width: 100%;
                '>
                    <div style='display: flex; align-items: center;'>
                        <div style='
                            width: 6px; 
                            height: 6px; 
                            background: #64748b;
                            border-radius: 50%; 
                            margin-right: 12px;
                        '></div>
                        <span>{proj.get('title', '')}</span>
                    </div>
                    <div style='
                        display: flex;
                        align-items: center;
                        gap: 6px;
                        background: linear-gradient(135deg, #f1f5f9, #e2e8f0);
                        color: #334155;
                        padding: 8px 18px;
                        border-radius: 16px;
                        font-weight: 600;
                        font-size: 14px;
                        box-shadow: 0 1px 3px rgba(0,0,0,0.1);
                        border: 1px solid rgba(203, 213, 225, 0.6);
                    '>
                        <!-- Inline SVG Clock Icon -->
                        <svg xmlns="http://www.w3.org/2000/svg" 
                            fill="none" viewBox="0 0 24 24" 
                            stroke="currentColor" width="16" height="16">
                            <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" 
                                d="M12 8v4l3 3m6-3a9 9 0 11-18 0 
                                   9 9 0 0118 0z" />
                        </svg>
                        {proj.get('duration', '')}
                    </div>
                </div>
                {tech_text}
                <div style='
                    font-size: 15px; 
                    color: #334155;
                    background: rgba(255, 255, 255, 0.6);
                    padding: 18px;
                    border-radius: 8px;
                    border: 1px solid rgba(229, 231, 235, 0.6);
                    line-height: 1.75;
                '>
                    {description_items}
                </div>
            </div>
            """

    # Enhanced PROJECT LINKS with professional styling
    project_links_html = ""
    if session_state.project_links:
        project_links_html = """
        <div style='margin-bottom: 20px;'>
            <h4 class='section-title' style='
                color: #374151;
                font-size: 20px;
                margin-bottom: 8px;
                display: flex;
                align-items: center;
                padding-bottom: 4px;
            '>
                <div style='
                    width: 6px; 
                    height: 6px; 
                    background: #6b7280;
                    border-radius: 50%; 
                    margin-right: 12px;
                '></div>
                Project Links
            </h4>
        </div>
        """ + "".join(
            f"""
            <div style='
                background: linear-gradient(135deg, #f9fafb 0%, #f3f4f6 100%);
                padding: 14px 20px;
                border-radius: 8px;
                margin-bottom: 12px;
                border: 1px solid rgba(209, 213, 219, 0.6);
                box-shadow: 0 2px 4px rgba(0, 0, 0, 0.05);
            '>
                <div style='
                    width: 4px; 
                    height: 4px; 
                    background: #6b7280;
                    border-radius: 50%; 
                    display: inline-block;
                    margin-right: 12px;
                    vertical-align: middle;
                '></div>
                <a href="{link}" style='
                    color: #374151; 
                    font-weight: 600; 
                    text-decoration: none;
                    font-size: 15px;
                '><svg xmlns="http://www.w3.org/2000/svg" width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" style="vertical-align:middle;margin-right:5px;"><path d="M10 13a5 5 0 0 0 7.54.54l3-3a5 5 0 0 0-7.07-7.07l-1.72 1.71"/><path d="M14 11a5 5 0 0 0-7.54-.54l-3 3a5 5 0 0 0 7.07 7.07l1.71-1.71"/></svg>Project {i+1}</a>
            </div>
            """
            for i, link in enumerate(session_state.project_links)
        )

    # Enhanced CERTIFICATES with professional design
    certificate_links_html = ""
    if session_state.certificate_links:
        certificate_links_html = """
        <h4 class='section-title' style='
            color: #374151;
            font-size: 20px;
            margin-bottom: 16px;
            display: flex;
            align-items: center;
        '>
            <div style='
                width: 6px; 
                height: 6px; 
                background: #6b7280;
                border-radius: 50%; 
                margin-right: 12px;
            '></div>
            Certificates
        </h4>
        """
        for cert in session_state.certificate_links:
            if cert["name"] and cert["link"]:
                description = _fmt_desc(cert.get('description', ''), font_size="15px", color="#374151", line_height="1.75")
                name = cert['name']
                link = cert['link']
                duration = cert.get('duration', '')

                card_html = f"""
                <div style='
                    background: linear-gradient(145deg, #f9fafb 0%, #f3f4f6 100%);
                    padding: 24px 28px;
                    border-radius: 12px;
                    margin-bottom: 26px;
                    box-shadow: 
                        0 4px 12px rgba(107, 114, 128, 0.08),
                        0 1px 3px rgba(0, 0, 0, 0.08);
                    font-family: "Inter", "Segoe UI", sans-serif;
                    color: #374151;
                    position: relative;
                    line-height: 1.7;
                    border: 1px solid rgba(209, 213, 219, 0.6);
                    overflow: hidden;
                '>
                    <!-- Accent bar -->
                    <div style='
                        position: absolute;
                        top: 0;
                        left: 0;
                        right: 0;
                        height: 3px;
                        background: linear-gradient(90deg, #6b7280, #9ca3af);
                    '></div>

                    <!-- Duration Badge -->
                    <div style='
                        position: absolute;
                        top: 20px;
                        right: 28px;
                        font-size: 13px;
                        font-weight: 600;
                        color: #374151;
                        background: linear-gradient(135deg, #ffffff, #f9fafb);
                        padding: 8px 14px;
                        border-radius: 16px;
                        box-shadow: 0 2px 4px rgba(0, 0, 0, 0.08);
                        border: 1px solid rgba(209, 213, 219, 0.6);
                        display: flex;
                        align-items: center;
                        gap: 6px;
                    '>
                        <!-- Inline SVG clock icon -->
                        <svg xmlns="http://www.w3.org/2000/svg" 
                            fill="none" viewBox="0 0 24 24" 
                            stroke="currentColor" width="14" height="14">
                            <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" 
                                d="M12 6v6l4 2m6-2a10 10 0 11-20 0 10 10 0 0120 0z"/>
                        </svg>
                        {duration}
                    </div>

                    <!-- Certificate Title -->
                    <div style='
                        font-size: 18px;
                        font-weight: 700;
                        color: #111827;
                        margin-bottom: 12px;
                        margin-right: 120px;
                        display: flex;
                        align-items: center;
                    '>
                        <div style='
                            width: 6px; 
                            height: 6px; 
                            background: #6b7280;
                            border-radius: 50%; 
                            margin-right: 12px;
                        '></div>
                        <a href="{link}" target="_blank" style='
                            color: #111827;
                            text-decoration: none;
                            transition: color 0.3s ease;
                        '>{name}</a>
                    </div>

                    <!-- Description -->
                    <div style='
                        font-size: 15px;
                        color: #374151;
                        background: rgba(255, 255, 255, 0.8);
                        padding: 16px;
                        border-radius: 8px;
                        border: 1px solid rgba(209, 213, 219, 0.6);
                        line-height: 1.6;
                    '>
                        <div style='
                            display: flex;
                            align-items: flex-start;
                            margin-bottom: 8px;
                        '>
                            <div style='
                                width: 4px; 
                                height: 4px; 
                                background: #6b7280;
                                border-radius: 50%; 
                                margin-right: 12px;
                                margin-top: 8px;
                                flex-shrink: 0;
                            '></div>
                            <div>{description}</div>
                        </div>
                    </div>
                </div>
                """
                certificate_links_html += card_html

    # ── SVG icons for contact ──────────────────────────────────────────
    SVG_DEFAULT = {
        'email':    '<svg xmlns="http://www.w3.org/2000/svg" width="13" height="13" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M4 4h16c1.1 0 2 .9 2 2v12c0 1.1-.9 2-2 2H4c-1.1 0-2-.9-2-2V6c0-1.1.9-2 2-2z"/><polyline points="22,6 12,13 2,6"/></svg>',
        'phone':    '<svg xmlns="http://www.w3.org/2000/svg" width="13" height="13" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M22 16.92v3a2 2 0 0 1-2.18 2 19.79 19.79 0 0 1-8.63-3.07A19.5 19.5 0 0 1 4.69 12 19.79 19.79 0 0 1 1.65 3.37 2 2 0 0 1 3.64 1h3a2 2 0 0 1 2 1.72c.127.96.361 1.903.7 2.81a2 2 0 0 1-.45 2.11L7.91 8.8a16 16 0 0 0 6.29 6.29l.98-.98a2 2 0 0 1 2.11-.45c.907.339 1.85.573 2.81.7A2 2 0 0 1 22 16.92z"/></svg>',
        'location': '<svg xmlns="http://www.w3.org/2000/svg" width="13" height="13" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M21 10c0 7-9 13-9 13s-9-6-9-13a9 9 0 0 1 18 0z"/><circle cx="12" cy="10" r="3"/></svg>',
        'linkedin': '<svg xmlns="http://www.w3.org/2000/svg" width="13" height="13" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M16 8a6 6 0 0 1 6 6v7h-4v-7a2 2 0 0 0-2-2 2 2 0 0 0-2 2v7h-4v-7a6 6 0 0 1 6-6z"/><rect x="2" y="9" width="4" height="12"/><circle cx="4" cy="4" r="2"/></svg>',
        'portfolio': '<svg xmlns="http://www.w3.org/2000/svg" width="13" height="13" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><circle cx="12" cy="12" r="10"/><line x1="2" y1="12" x2="22" y2="12"/><path d="M12 2a15.3 15.3 0 0 1 4 10 15.3 15.3 0 0 1-4 10 15.3 15.3 0 0 1-4-10 15.3 15.3 0 0 1 4-10z"/></svg>',
    }

    def _badge_default(item, bg="rgba(255,255,255,0.2)", color="#ffffff"):
        return (f"<span style='display:inline-block;background:{bg};color:{color};border-radius:4px;"
                f"padding:3px 10px;margin:3px 3px 3px 0;font-size:12px;font-weight:600;border:1px solid rgba(255,255,255,0.3);'>{item.strip()}</span>")

    def _badges_default(items_str, bg="rgba(255,255,255,0.2)", color="#ffffff"):
        return "".join(_badge_default(s, bg, color) for s in items_str.split(',') if s.strip())

    contact_html_default = ""
    for _key in ['location', 'phone', 'email', 'linkedin', 'portfolio']:
        val = session_state.get(_key, '')
        if not val:
            continue
        if _key == 'email':
            val_html = f"<a href='mailto:{val}' style='color:#ffffff;text-decoration:none;word-break:break-all;font-weight:500;'>{val}</a>"
        elif _key in ('linkedin', 'portfolio'):
            href = val if val.startswith('http') else f"https://{val}"
            val_html = f"<a href='{href}' target='_blank' style='color:#ffffff;text-decoration:none;word-break:break-all;font-weight:500;'>{val}</a>"
        else:
            val_html = f"<span style='color:#ffffff;word-break:break-all;'>{val}</span>"
        contact_html_default += (
            f"<div style='margin-bottom:9px;font-size:13px;color:#ffffff;"
            f"display:flex;align-items:center;gap:8px;'>"
            f"<span style='flex-shrink:0;opacity:0.9;'>{SVG_DEFAULT.get(_key,'')}</span>{val_html}</div>"
        )

    def _main_sec_default(title, body):
        return (f"<div style='margin-bottom:26px;'>"
                f"<h3 style='font-size:13px;letter-spacing:2px;text-transform:uppercase;font-weight:700;"
                f"color:#374151;border-bottom:2px solid #9ca3af;padding-bottom:5px;margin-bottom:14px;'>{title}</h3>"
                f"{body}</div>")

    def _side_sec_default(title, body):
        return (f"<div style='margin-bottom:24px;'>"
                f"<h3 style='font-size:11px;letter-spacing:2px;text-transform:uppercase;color:#ffffff;"
                f"font-weight:800;border-bottom:1px solid rgba(255,255,255,0.35);padding-bottom:6px;margin-bottom:12px;'>{title}</h3>"
                f"{body}</div>")

    # Fix profile image to standard circle size
    import re as _re_default
    fixed_img_default = ""
    if profile_img_html:
        _img_m = _re_default.search(r'<img[^>]*>', profile_img_html)
        if _img_m:
            _img_tag = _img_m.group(0)
            _img_tag = _re_default.sub(r"style=['\"][^'\"]*['\"]", "", _img_tag)
            _img_tag = _img_tag.replace("<img ", "<img style='width:108px;height:108px;border-radius:50%;object-fit:cover;object-position:center;border:3px solid rgba(255,255,255,0.5);display:block;margin:0 auto;' ")
            fixed_img_default = _img_tag

    # Cert sidebar (white text on dark bg)
    cert_default_html = ""
    for cert in session_state.certificate_links:
        if cert.get('name'):
            cert_default_html += (
                f"<div style='margin-bottom:10px;padding:8px;background:rgba(255,255,255,0.1);border-radius:6px;border:1px solid rgba(255,255,255,0.2);'>"
                f"<a href='{cert.get('link','#')}' style='color:#ffffff;font-size:13px;font-weight:600;text-decoration:none;'>{cert.get('name','')}</a>"
                f"<div style='font-size:11px;color:rgba(255,255,255,0.8);'>{cert.get('duration','')}</div></div>"
            )

    proj_links_default_html = ""
    if session_state.project_links:
        proj_links_default_html = "".join(
            f"<div style='margin-bottom:6px;'><a href='{lnk}' target='_blank' style='color:#ffffff;font-size:12px;font-weight:600;'>&#128279; Project {i+1}</a></div>"
            for i, lnk in enumerate(session_state.project_links)
        )

    html_content = f"""<!DOCTYPE html>
<html lang='en'>
<head><meta charset='UTF-8'><title>{session_state.get('name','')} - Professional Resume</title>
<style>* {{ box-sizing:border-box; margin:0; padding:0; }} body {{ font-family:'Segoe UI',sans-serif; background:#fff; }}</style>
</head>
<body>
<table role='presentation' style='width:100%;min-height:100vh;border-collapse:collapse;table-layout:fixed;'>
<tr>
  <td style='width:300px;background:linear-gradient(180deg,#374151,#4b5563);color:#ffffff;padding:36px 24px;vertical-align:top;'>
    {'<div style="margin:0 auto 14px;text-align:center;">' + fixed_img_default + '</div>' if fixed_img_default else ''}
    <h1 style='font-size:21px;font-weight:800;color:#ffffff;text-align:center;margin-bottom:4px;'>{session_state.get('name','')}</h1>
    <div style='font-size:13px;color:#e5e7eb;text-align:center;margin-bottom:24px;font-weight:600;letter-spacing:1px;text-transform:uppercase;'>{session_state.get('job_title','')}</div>
    {_side_sec_default("Contact", contact_html_default)}
    {_side_sec_default("Skills", _badges_default(session_state.get('skills',''),'rgba(255,255,255,0.18)','#ffffff')) if session_state.get('skills') else ''}
    {_side_sec_default("Soft Skills", _badges_default(session_state.get('Softskills',''),'rgba(255,255,255,0.18)','#ffffff')) if session_state.get('Softskills') else ''}
    {_side_sec_default("Languages", _badges_default(session_state.get('languages',''),'rgba(255,255,255,0.18)','#ffffff')) if session_state.get('languages') else ''}
    {_side_sec_default("Interests", _badges_default(session_state.get('interests',''),'rgba(255,255,255,0.18)','#ffffff')) if session_state.get('interests') else ''}
    {_side_sec_default("Certifications", cert_default_html) if cert_default_html else ''}
    {_side_sec_default("Project Links", proj_links_default_html) if proj_links_default_html else ''}
  </td>
  <td style='padding:40px 44px;background:#fff;vertical-align:top;'>
    {_main_sec_default("Professional Summary", summary_html) if summary_html else ''}
    {_main_sec_default("Work Experience", experience_html) if experience_html else ''}
    {_main_sec_default("Education", education_html) if education_html else ''}
    {_main_sec_default("Projects", projects_html) if projects_html else ''}
  </td>
</tr>
</table>
</body></html>"""

    return html_content

def render_template_modern(session_state, profile_img_html=""):
    """Modern Minimal template - ATS-friendly single-column layout with clean inline styles"""
    import re as _re_mod

    # Fix profile image: extract <img> only, apply clean inline styles
    fixed_img_mod = ""
    if profile_img_html:
        _img_m = _re_mod.search(r'<img[^>]*>', profile_img_html)
        if _img_m:
            _img_tag = _img_m.group(0)
            _img_tag = _re_mod.sub(r"style=['\"][^'\"]*['\"]", "", _img_tag)
            _img_tag = _img_tag.replace(
                "<img ",
                "<img style='width:100px;height:100px;border-radius:50%;object-fit:cover;"
                "object-position:center;border:3px solid #2563eb;display:block;margin:0 auto 12px;' "
            )
            fixed_img_mod = _img_tag

    # Helper: build a comma-separated tag list (ATS-safe plain spans)
    def _tag_list(items_str, bg="#eff6ff", color="#1e3a8a", border="#bfdbfe"):
        return "".join(
            f"<span style='display:inline-block;background:{bg};color:{color};"
            f"border:1px solid {border};border-radius:4px;padding:4px 12px;"
            f"margin:3px 4px 3px 0;font-size:13px;font-weight:600;'>{s.strip()}</span>"
            for s in items_str.split(',') if s.strip()
        )

    # Section header helper (left-aligned, underlined — ATS parses left-to-right)
    def _section(title, body):
        return (
            f"<div style='margin-bottom:28px;'>"
            f"<h3 style='font-size:15px;font-weight:700;color:#1e3a8a;text-transform:uppercase;"
            f"letter-spacing:1.5px;border-bottom:2px solid #2563eb;padding-bottom:5px;"
            f"margin-bottom:14px;text-align:left;'>{title}</h3>"
            f"{body}</div>"
        )

    # Contact line
    contact_parts = []
    for key, label in [('location', ''), ('phone', ''), ('email', ''), ('linkedin', 'LinkedIn'), ('portfolio', 'Portfolio')]:
        val = session_state.get(key, '')
        if not val:
            continue
        if key == 'email':
            contact_parts.append(f"<a href='mailto:{val}' style='color:#1e3a8a;text-decoration:none;font-weight:500;'>{val}</a>")
        elif key in ('linkedin', 'portfolio'):
            href = val if val.startswith('http') else f"https://{val}"
            contact_parts.append(f"<a href='{href}' target='_blank' style='color:#1e3a8a;text-decoration:none;font-weight:500;'>{label}: {val}</a>")
        else:
            contact_parts.append(f"<span style='color:#1f2937;'>{val}</span>")
    contact_html = " &nbsp;|&nbsp; ".join(contact_parts)

    # Work Experience
    exp_html = ""
    for exp in session_state.experience_entries:
        if exp.get('company') or exp.get('title'):
            desc = _fmt_desc(exp.get('description', ''), font_size='14px', color='#1f2937', line_height='1.75')
            exp_html += (
                f"<div style='margin-bottom:20px;padding:16px 18px;border-left:3px solid #2563eb;"
                f"background:#f8faff;border-radius:0 8px 8px 0;'>"
                f"<div style='display:flex;justify-content:space-between;align-items:baseline;flex-wrap:wrap;gap:6px;margin-bottom:4px;'>"
                f"<strong style='font-size:15px;color:#1e3a8a;'>{exp.get('title','')}</strong>"
                f"<span style='font-size:13px;color:#374151;background:#e0e7ff;padding:2px 10px;"
                f"border-radius:6px;font-weight:600;border:1px solid #c7d2fe;'>{exp.get('duration','')}</span>"
                f"</div>"
                f"<div style='font-size:14px;color:#374151;font-weight:600;margin-bottom:8px;'>{exp.get('company','')}</div>"
                f"<div style='font-size:14px;color:#1f2937;line-height:1.7;'>{desc}</div>"
                f"</div>"
            )

    # Education
    edu_html = ""
    for edu in session_state.education_entries:
        if edu.get('institution') or edu.get('degree'):
            degree_val = edu.get('degree', '')
            if isinstance(degree_val, list):
                degree_val = ", ".join(degree_val)
            edu_html += (
                f"<div style='margin-bottom:16px;padding:14px 16px;border-left:3px solid #2563eb;"
                f"background:#f8faff;border-radius:0 8px 8px 0;'>"
                f"<div style='display:flex;justify-content:space-between;align-items:baseline;flex-wrap:wrap;gap:6px;margin-bottom:4px;'>"
                f"<strong style='font-size:15px;color:#1e3a8a;'>{edu.get('institution','')}</strong>"
                f"<span style='font-size:13px;color:#374151;background:#e0e7ff;padding:2px 10px;"
                f"border-radius:6px;font-weight:600;border:1px solid #c7d2fe;'>{edu.get('year','')}</span>"
                f"</div>"
                f"<div style='font-size:14px;color:#374151;font-weight:600;margin-bottom:4px;'>{degree_val}</div>"
                f"<div style='font-size:13px;color:#374151;'>{edu.get('details','')}</div>"
                f"</div>"
            )

    # Projects
    proj_html = ""
    proj_links_all = getattr(session_state, 'project_links', []) or []
    for idx, proj in enumerate(session_state.project_entries):
        if proj.get('title'):
            desc = _fmt_desc(proj.get('description', ''), font_size='14px', color='#1f2937', line_height='1.75')
            proj_link_html = ""
            if idx < len(proj_links_all) and proj_links_all[idx]:
                proj_link_html = (
                    f"<div style='margin-top:6px;'>"
                    f"<a href='{proj_links_all[idx]}' target='_blank' style='color:#2563eb;"
                    f"font-size:13px;font-weight:600;'>View Project / GitHub</a></div>"
                )
            proj_html += (
                f"<div style='margin-bottom:18px;padding:14px 16px;border-left:3px solid #2563eb;"
                f"background:#f8faff;border-radius:0 8px 8px 0;'>"
                f"<div style='display:flex;justify-content:space-between;align-items:baseline;flex-wrap:wrap;gap:6px;margin-bottom:4px;'>"
                f"<strong style='font-size:15px;color:#1e3a8a;'>{proj.get('title','')}</strong>"
                f"<span style='font-size:13px;color:#374151;background:#e0e7ff;padding:2px 10px;"
                f"border-radius:6px;font-weight:600;border:1px solid #c7d2fe;'>{proj.get('duration','')}</span>"
                f"</div>"
                f"<div style='font-size:13px;color:#374151;font-weight:600;margin-bottom:6px;'>Tech Stack: {proj.get('tech','')}</div>"
                f"<div style='font-size:14px;color:#1f2937;'>{desc}</div>"
                f"{proj_link_html}</div>"
            )

    # Certifications
    cert_html = ""
    for cert in session_state.certificate_links:
        if cert.get('name'):
            cert_desc = _fmt_desc(cert.get('description', ''), font_size='13px', color='#1f2937', line_height='1.7')
            cert_html += (
                f"<div style='margin-bottom:14px;padding:12px 14px;border-left:3px solid #2563eb;"
                f"background:#f8faff;border-radius:0 8px 8px 0;'>"
                f"<div style='display:flex;justify-content:space-between;align-items:baseline;flex-wrap:wrap;gap:6px;margin-bottom:4px;'>"
                f"<a href='{cert.get('link','#')}' target='_blank' style='font-size:14px;font-weight:700;"
                f"color:#1e3a8a;text-decoration:none;'>{cert.get('name','')}</a>"
                f"<span style='font-size:12px;color:#374151;background:#e0e7ff;padding:2px 8px;"
                f"border-radius:6px;font-weight:600;border:1px solid #c7d2fe;'>{cert.get('duration','')}</span>"
                f"</div>"
                f"<div style='font-size:13px;color:#1f2937;'>{cert_desc}</div>"
                f"</div>"
            )

    # Summary
    summary_mod = _fmt_desc(session_state.get('summary', ''), font_size='14px', color='#1f2937', line_height='1.8')

    # Skills and tags
    skills_str = session_state.get('skills', '')
    softskills_str = session_state.get('Softskills', '')
    languages_str = session_state.get('languages', '')
    interests_str = session_state.get('interests', '')

    # Project links section
    proj_links_section = ""
    if proj_links_all:
        links_body = "".join(
            f"<div style='margin-bottom:6px;'>"
            f"<a href='{lnk}' target='_blank' style='color:#2563eb;font-size:14px;font-weight:600;'>Project {i+1}: {lnk}</a>"
            f"</div>"
            for i, lnk in enumerate(proj_links_all) if lnk
        )
        proj_links_section = _section("Project Links", links_body) if links_body else ""

    html_content = f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<title>{session_state.get('name', '')} - Resume</title>
</head>
<body style="font-family:'Segoe UI',Arial,Helvetica,sans-serif;line-height:1.6;color:#1f2937;background:#ffffff;max-width:860px;margin:0 auto;padding:36px 32px;">

  <!-- HEADER -->
  <div style="text-align:center;margin-bottom:30px;padding-bottom:20px;border-bottom:3px solid #2563eb;">
    {fixed_img_mod if fixed_img_mod else ''}
    <h1 style="font-size:28px;font-weight:800;color:#1e3a8a;margin-bottom:6px;">{session_state.get('name', '')}</h1>
    <div style="font-size:16px;color:#374151;font-weight:600;margin-bottom:12px;">{session_state.get('job_title', '')}</div>
    <div style="font-size:13px;color:#374151;line-height:2;">{contact_html}</div>
  </div>

  <!-- BODY -->
  {_section("Professional Summary", f"<div style='font-size:14px;color:#1f2937;line-height:1.8;padding:14px 16px;background:#f8faff;border-radius:8px;border:1px solid #e0e7ff;'>{summary_mod}</div>") if summary_mod else ''}
  {_section("Work Experience", exp_html) if exp_html else ''}
  {_section("Education", edu_html) if edu_html else ''}
  {_section("Projects", proj_html) if proj_html else ''}
  {_section("Technical Skills", f"<div style='padding:8px 0;'>{_tag_list(skills_str)}</div>") if skills_str.strip() else ''}
  {_section("Core Competencies", f"<div style='padding:8px 0;'>{_tag_list(softskills_str, '#fef3c7', '#92400e', '#fde68a')}</div>") if softskills_str.strip() else ''}
  {_section("Languages", f"<div style='padding:8px 0;'>{_tag_list(languages_str, '#f0fdf4', '#14532d', '#bbf7d0')}</div>") if languages_str.strip() else ''}
  {_section("Interests", f"<div style='padding:8px 0;'>{_tag_list(interests_str, '#fdf4ff', '#581c87', '#e9d5ff')}</div>") if interests_str.strip() else ''}
  {_section("Professional Certifications", cert_html) if cert_html else ''}
  {proj_links_section}

</body>
</html>"""

    return html_content

def render_template_sidebar(session_state, profile_img_html=""):
    """Enhanced elegant sidebar template with improved styling, pill tags, and better visual hierarchy"""
    
    # Process lists for pill-style tags
    skills_list = [s.strip() for s in session_state['skills'].split(',') if s.strip()]
    languages_list = [l.strip() for l in session_state['languages'].split(',') if l.strip()]
    interests_list = [i.strip() for i in session_state['interests'].split(',') if i.strip()]
    softskills_list = [s.strip() for s in session_state['Softskills'].split(',') if s.strip()]
    
    # Create pill-style tags for sidebar sections
    skills_pills = "".join([
        f"""<div style="
            display: inline-block;
            background: rgba(56, 189, 248, 0.25);
            color: #ffffff;
            padding: 8px 16px;
            margin: 5px 8px 5px 0;
            border-radius: 18px;
            font-size: 0.85rem;
            font-weight: 600;
            border: 1px solid rgba(56, 189, 248, 0.5);
            box-shadow: 0 2px 4px rgba(56, 189, 248, 0.1);
        ">{skill}</div>""" for skill in skills_list
    ])
    
    languages_pills = "".join([
        f"""<div style="
            display: inline-block;
            background: rgba(34, 197, 94, 0.25);
            color: #ffffff;
            padding: 8px 16px;
            margin: 5px 8px 5px 0;
            border-radius: 18px;
            font-size: 0.85rem;
            font-weight: 600;
            border: 1px solid rgba(34, 197, 94, 0.5);
            box-shadow: 0 2px 4px rgba(34, 197, 94, 0.1);
        ">{lang}</div>""" for lang in languages_list
    ])
    
    interests_pills = "".join([
        f"""<div style="
            display: inline-block;
            background: rgba(245, 158, 11, 0.25);
            color: #ffffff;
            padding: 8px 16px;
            margin: 5px 8px 5px 0;
            border-radius: 18px;
            font-size: 0.85rem;
            font-weight: 600;
            border: 1px solid rgba(245, 158, 11, 0.5);
            box-shadow: 0 2px 4px rgba(245, 158, 11, 0.1);
        ">{interest}</div>""" for interest in interests_list
    ])
    
    softskills_pills = "".join([
        f"""<div style="
            display: inline-block;
            background: rgba(168, 85, 247, 0.25);
            color: #ffffff;
            padding: 8px 16px;
            margin: 5px 8px 5px 0;
            border-radius: 18px;
            font-size: 0.85rem;
            font-weight: 600;
            border: 1px solid rgba(168, 85, 247, 0.5);
            box-shadow: 0 2px 4px rgba(168, 85, 247, 0.1);
        ">{skill}</div>""" for skill in softskills_list
    ])
    
    # Fix profile image to standard circle size
    import re as _re_sb
    fixed_img_sb = ""
    if profile_img_html:
        _img_m = _re_sb.search(r'<img[^>]*>', profile_img_html)
        if _img_m:
            _img_tag = _img_m.group(0)
            _img_tag = _re_sb.sub(r"style=['\"][^'\"]*['\"]", "", _img_tag)
            _img_tag = _img_tag.replace("<img ", "<img style='width:108px;height:108px;border-radius:50%;object-fit:cover;object-position:center;border:3px solid #38bdf8;display:block;margin:0 auto;' ")
            fixed_img_sb = _img_tag

    SVG_SB = {
        'email':    '<svg xmlns="http://www.w3.org/2000/svg" width="13" height="13" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M4 4h16c1.1 0 2 .9 2 2v12c0 1.1-.9 2-2 2H4c-1.1 0-2-.9-2-2V6c0-1.1.9-2 2-2z"/><polyline points="22,6 12,13 2,6"/></svg>',
        'phone':    '<svg xmlns="http://www.w3.org/2000/svg" width="13" height="13" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M22 16.92v3a2 2 0 0 1-2.18 2 19.79 19.79 0 0 1-8.63-3.07A19.5 19.5 0 0 1 4.69 12 19.79 19.79 0 0 1 1.65 3.37 2 2 0 0 1 3.64 1h3a2 2 0 0 1 2 1.72c.127.96.361 1.903.7 2.81a2 2 0 0 1-.45 2.11L7.91 8.8a16 16 0 0 0 6.29 6.29l.98-.98a2 2 0 0 1 2.11-.45c.907.339 1.85.573 2.81.7A2 2 0 0 1 22 16.92z"/></svg>',
        'location': '<svg xmlns="http://www.w3.org/2000/svg" width="13" height="13" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M21 10c0 7-9 13-9 13s-9-6-9-13a9 9 0 0 1 18 0z"/><circle cx="12" cy="10" r="3"/></svg>',
        'linkedin': '<svg xmlns="http://www.w3.org/2000/svg" width="13" height="13" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M16 8a6 6 0 0 1 6 6v7h-4v-7a2 2 0 0 0-2-2 2 2 0 0 0-2 2v7h-4v-7a6 6 0 0 1 6-6z"/><rect x="2" y="9" width="4" height="12"/><circle cx="4" cy="4" r="2"/></svg>',
        'portfolio': '<svg xmlns="http://www.w3.org/2000/svg" width="13" height="13" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><circle cx="12" cy="12" r="10"/><line x1="2" y1="12" x2="22" y2="12"/><path d="M12 2a15.3 15.3 0 0 1 4 10 15.3 15.3 0 0 1-4 10 15.3 15.3 0 0 1-4-10 15.3 15.3 0 0 1 4-10z"/></svg>',
    }

    contact_html_sb = ""
    for _key in ['location', 'phone', 'email', 'linkedin', 'portfolio']:
        val = session_state.get(_key, '')
        if not val:
            continue
        if _key == 'email':
            val_html = f"<a href='mailto:{val}' style='color:#ffffff;text-decoration:none;word-break:break-all;font-weight:500;'>{val}</a>"
        elif _key in ('linkedin', 'portfolio'):
            href = val if val.startswith('http') else f"https://{val}"
            val_html = f"<a href='{href}' target='_blank' style='color:#ffffff;text-decoration:none;word-break:break-all;font-weight:500;'>{val}</a>"
        else:
            val_html = f"<span style='color:#ffffff;word-break:break-all;'>{val}</span>"
        contact_html_sb += (
            f"<div style='margin-bottom:9px;font-size:13px;color:#ffffff;"
            f"display:flex;align-items:center;gap:8px;'>"
            f"<span style='flex-shrink:0;opacity:0.9;'>{SVG_SB.get(_key,'')}</span>{val_html}</div>"
        )

    def _badge_sb(item, bg="rgba(56,189,248,0.25)", color="#ffffff"):
        return (f"<span style='display:inline-block;background:{bg};color:{color};border-radius:4px;"
                f"padding:3px 10px;margin:3px 3px 3px 0;font-size:12px;font-weight:600;border:1px solid rgba(56,189,248,0.4);'>{item.strip()}</span>")

    def _badges_sb(items_str, bg="rgba(56,189,248,0.25)", color="#ffffff"):
        return "".join(_badge_sb(s, bg, color) for s in items_str.split(',') if s.strip())

    def _main_sec_sb(title, body):
        return (f"<div style='margin-bottom:26px;'>"
                f"<h3 style='font-size:13px;letter-spacing:2px;text-transform:uppercase;font-weight:700;"
                f"color:#0c4a6e;border-bottom:2px solid #38bdf8;padding-bottom:5px;margin-bottom:14px;'>{title}</h3>"
                f"{body}</div>")

    def _side_sec_sb(title, body):
        return (f"<div style='margin-bottom:24px;'>"
                f"<h3 style='font-size:11px;letter-spacing:2px;text-transform:uppercase;color:#ffffff;"
                f"font-weight:800;border-bottom:1px solid rgba(56,189,248,0.4);padding-bottom:6px;margin-bottom:12px;'>{title}</h3>"
                f"{body}</div>")

    cert_sb_html = ""
    for cert in session_state.certificate_links:
        if cert.get('name'):
            cert_sb_html += (
                f"<div style='margin-bottom:10px;padding:8px;background:rgba(255,255,255,0.1);border-radius:6px;border:1px solid rgba(56,189,248,0.3);'>"
                f"<a href='{cert.get('link','#')}' style='color:#ffffff;font-size:13px;font-weight:600;text-decoration:none;'>{cert.get('name','')}</a>"
                f"<div style='font-size:11px;color:rgba(255,255,255,0.8);'>{cert.get('duration','')}</div></div>"
            )

    proj_links_sb = ""
    if session_state.project_links:
        proj_links_sb = "".join(
            f"<div style='margin-bottom:6px;'><a href='{lnk}' target='_blank' style='color:#ffffff;font-size:12px;font-weight:600;'>&#128279; Project {i+1}</a></div>"
            for i, lnk in enumerate(session_state.project_links)
        )

    exp_sb = ""
    for exp in session_state.experience_entries:
        if exp.get('company') or exp.get('title'):
            desc = _fmt_desc(exp.get('description', ''), font_size='13px', color='#374151', line_height='1.75')
            exp_sb += (
                f"<div style='margin-bottom:20px;border-left:3px solid #38bdf8;padding-left:14px;'>"
                f"<div style='display:flex;justify-content:space-between;align-items:baseline;flex-wrap:wrap;gap:6px;'>"
                f"<strong style='font-size:15px;color:#0c4a6e;'>{exp.get('company','')}</strong>"
                f"<span style='font-size:12px;color:#64748b;background:#f0f9ff;padding:2px 8px;border-radius:8px;'>{exp.get('duration','')}</span>"
                f"</div>"
                f"<div style='font-size:13px;color:#0284c7;font-weight:700;margin-bottom:5px;'>{exp.get('title','')}</div>"
                f"<div style='font-size:13px;color:#374151;line-height:1.7;'>{desc}</div></div>"
                f"<div style='border-bottom:1px dashed #bae6fd;margin-bottom:12px;'></div>"
            )

    edu_sb = ""
    for edu in session_state.education_entries:
        if edu.get('institution'):
            degree_val = edu.get('degree', '')
            if isinstance(degree_val, list):
                degree_val = ", ".join(degree_val)
            edu_sb += (
                f"<div style='margin-bottom:14px;border-left:3px solid #38bdf8;padding-left:12px;'>"
                f"<strong style='font-size:14px;color:#0c4a6e;'>{edu.get('institution','')}</strong>"
                f"<span style='float:right;font-size:12px;color:#64748b;'>{edu.get('year','')}</span>"
                f"<div style='clear:both;font-size:13px;color:#0284c7;font-style:italic;font-weight:600;'>{degree_val}</div>"
                f"<div style='font-size:12px;color:#6b7280;'>{edu.get('details','')}</div></div>"
            )

    proj_sb = ""
    proj_links_all_sb = getattr(session_state, 'project_links', []) or []
    for idx, proj in enumerate(session_state.project_entries):
        if proj.get('title'):
            desc = _fmt_desc(proj.get('description', ''), font_size='13px', color='#374151', line_height='1.75')
            proj_link_html = ""
            if idx < len(proj_links_all_sb) and proj_links_all_sb[idx]:
                proj_link_html = f"<div style='margin-top:5px;'><a href='{proj_links_all_sb[idx]}' target='_blank' style='color:#0284c7;font-size:12px;font-weight:600;'>&#128279; View Project / GitHub</a></div>"
            proj_sb += (
                f"<div style='margin-bottom:14px;padding:12px 14px;background:#f0f9ff;border-radius:6px;border-left:3px solid #38bdf8;'>"
                f"<div style='display:flex;justify-content:space-between;flex-wrap:wrap;gap:4px;'>"
                f"<strong style='font-size:14px;color:#0c4a6e;'>{proj.get('title','')}</strong>"
                f"<span style='font-size:12px;color:#64748b;'>{proj.get('duration','')}</span>"
                f"</div>"
                f"<div style='font-size:12px;color:#0284c7;font-weight:600;margin-bottom:4px;'>{proj.get('tech','')}</div>"
                f"<div style='font-size:13px;color:#374151;'>{desc}</div>"
                f"{proj_link_html}</div>"
            )

    summary_sb = _fmt_desc(session_state.get('summary', ''), font_size='13px', color='#374151', line_height='1.8')
    job_title_sb = session_state.get('job_title', '') or session_state.get('title', '')

    html_content = f"""<!DOCTYPE html>
<html lang='en'>
<head><meta charset='UTF-8'><title>{session_state.get('name','')} - Resume</title>
<style>* {{ box-sizing:border-box; margin:0; padding:0; }} body {{ font-family:'Segoe UI',sans-serif; background:#fff; }}</style>
</head>
<body>
<table role='presentation' style='width:100%;min-height:100vh;border-collapse:collapse;table-layout:fixed;'>
<tr>
  <td style='width:300px;background:linear-gradient(180deg,#1e293b,#334155);color:white;padding:36px 24px;vertical-align:top;'>
    {'<div style="margin:0 auto 14px;text-align:center;">' + fixed_img_sb + '</div>' if fixed_img_sb else ''}
    <h1 style='font-size:21px;font-weight:800;color:#ffffff;text-align:center;margin-bottom:4px;'>{session_state.get('name','')}</h1>
    <div style='font-size:13px;color:#38bdf8;text-align:center;margin-bottom:24px;font-weight:600;letter-spacing:1px;text-transform:uppercase;'>{job_title_sb}</div>
    {_side_sec_sb("Contact", contact_html_sb)}
    {_side_sec_sb("Skills", _badges_sb(session_state.get('skills',''),'rgba(56,189,248,0.25)','#ffffff')) if session_state.get('skills') else ''}
    {_side_sec_sb("Soft Skills", _badges_sb(session_state.get('Softskills',''),'rgba(255,255,255,0.12)','#ffffff')) if session_state.get('Softskills') else ''}
    {_side_sec_sb("Languages", _badges_sb(session_state.get('languages',''),'rgba(255,255,255,0.12)','#ffffff')) if session_state.get('languages') else ''}
    {_side_sec_sb("Interests", _badges_sb(session_state.get('interests',''),'rgba(255,255,255,0.12)','#ffffff')) if session_state.get('interests') else ''}
    {_side_sec_sb("Certifications", cert_sb_html) if cert_sb_html else ''}
    {_side_sec_sb("Project Links", proj_links_sb) if proj_links_sb else ''}
  </td>
  <td style='padding:40px 44px;background:#fff;vertical-align:top;'>
    {_main_sec_sb("Professional Summary", summary_sb) if summary_sb else ''}
    {_main_sec_sb("Work Experience", exp_sb) if exp_sb else ''}
    {_main_sec_sb("Education", edu_sb) if edu_sb else ''}
    {_main_sec_sb("Projects", proj_sb) if proj_sb else ''}
  </td>
</tr>
</table>
</body></html>"""

    return html_content
    


# ─────────────────────────────────────────────────────────────
# NEW TEMPLATE 1: Classic Clean (Single Column)
# ─────────────────────────────────────────────────────────────
def render_template_classic(session_state, profile_img_html=""):
    """Classic Clean — single-column, black & white, ATS-friendly"""
    import re as _re

    def pills(items_str, color="#1e3a5f"):
        return "".join(
            f"<span style='display:inline-block;background:#f0f4f8;color:{color};border:1px solid #c7d2e0;"
            f"border-radius:4px;padding:4px 12px;margin:4px 4px 4px 0;font-size:13px;font-weight:600;'>{s.strip()}</span>"
            for s in items_str.split(',') if s.strip()
        )

    # Fix image: extract just the <img> tag, strip all styles, apply clean circle styles
    def _fix_img(html, size=88):
        if not html:
            return ""
        img_match = _re.search(r'<img[^>]*>', html)
        if not img_match:
            return ""
        img_tag = img_match.group(0)
        img_tag = _re.sub(r"style=['\"][^'\"]*['\"]", "", img_tag)
        img_tag = img_tag.replace("<img ", f"<img style='width:{size}px;height:{size}px;border-radius:50%;object-fit:cover;object-position:center;display:block;margin:0 auto 10px;border:2px solid #1e3a5f;' ")
        return img_tag

    experience_html = ""
    for exp in session_state.experience_entries:
        if exp.get("company") or exp.get("title"):
            desc = _fmt_desc(exp.get('description',''), font_size='14px', color='#374151', line_height='1.75')
            experience_html += f"""
            <div style='margin-bottom:18px;'>
                <div style='display:flex;justify-content:space-between;align-items:baseline;'>
                    <strong style='font-size:16px;color:#1a1a1a;'>{exp.get('company','')}</strong>
                    <span style='font-size:13px;color:#555;'>{exp.get('duration','')}</span>
                </div>
                <div style='font-size:14px;color:#1e3a5f;font-weight:600;font-style:italic;margin-bottom:6px;'>{exp.get('title','')}</div>
                <div style='font-size:14px;color:#333;line-height:1.7;'>{desc}</div>
            </div>
            <hr style='border:none;border-top:1px solid #e5e7eb;margin:12px 0;'>"""

    education_html = ""
    for edu in session_state.education_entries:
        if edu.get("institution") or edu.get("degree"):
            degree_val = edu.get("degree","")
            if isinstance(degree_val, list): degree_val = ", ".join(degree_val)
            education_html += f"""
            <div style='margin-bottom:14px;'>
                <div style='display:flex;justify-content:space-between;'>
                    <strong style='font-size:15px;'>{edu.get('institution','')}</strong>
                    <span style='font-size:13px;color:#555;'>{edu.get('year','')}</span>
                </div>
                <div style='font-size:14px;color:#555;font-style:italic;'>{degree_val}</div>
                <div style='font-size:13px;color:#666;'>{edu.get('details','')}</div>
            </div>"""

    projects_html = ""
    for idx, proj in enumerate(session_state.project_entries):
        if proj.get("title"):
            desc = _fmt_desc(proj.get('description',''), font_size='14px', color='#374151', line_height='1.75')
            # Per-project links
            proj_link_html = ""
            proj_links = getattr(session_state, 'project_links', []) or []
            if idx < len(proj_links) and proj_links[idx]:
                proj_link_html = f"<div style='margin-top:5px;font-size:13px;'><a href='{proj_links[idx]}' target='_blank' style='color:#1e3a5f;font-weight:600;'>&#128279; View Project / GitHub</a></div>"
            projects_html += f"""
            <div style='margin-bottom:16px;'>
                <div style='display:flex;justify-content:space-between;'>
                    <strong style='font-size:15px;color:#1e3a5f;'>{proj.get('title','')}</strong>
                    <span style='font-size:13px;color:#555;'>{proj.get('duration','')}</span>
                </div>
                <div style='font-size:13px;color:#555;margin-bottom:4px;'><b>Tech:</b> {proj.get('tech','')}</div>
                <div style='font-size:14px;color:#333;line-height:1.6;'>{desc}</div>
                {proj_link_html}
            </div>"""

    # All project links section
    all_links_html = ""
    proj_links_all = getattr(session_state, 'project_links', []) or []
    if proj_links_all:
        links_items = "".join(
            f"<div style='margin-bottom:6px;'><a href='{lnk}' target='_blank' style='color:#1e3a5f;font-weight:600;font-size:14px;'>&#128279; Project {i+1}: {lnk}</a></div>"
            for i, lnk in enumerate(proj_links_all)
        )
        all_links_html = links_items

    cert_html = ""
    for cert in session_state.certificate_links:
        if cert.get("name"):
            desc = _fmt_desc(cert.get('description',''), font_size='13px', color='#444', line_height='1.7')
            cert_html += f"""
            <div style='margin-bottom:12px;'>
                <div style='display:flex;justify-content:space-between;'>
                    <a href='{cert.get("link","#")}' target='_blank' style='font-weight:600;color:#1e3a5f;font-size:15px;text-decoration:none;'>{cert.get("name","")}</a>
                    <span style='font-size:13px;color:#555;'>{cert.get("duration","")}</span>
                </div>
                <div style='font-size:13px;color:#444;'>{desc}</div>
            </div>"""

    def section(title, content):
        return f"""
        <div style='margin-bottom:24px;'>
            <h2 style='font-size:14px;font-weight:700;letter-spacing:2px;text-transform:uppercase;
                color:#1e3a5f;border-bottom:2px solid #1e3a5f;padding-bottom:4px;margin-bottom:14px;'>{title}</h2>
            {content}
        </div>"""

    # Contact line with portfolio & github — hyperlinked where applicable
    def _contact_link(key, val):
        if key == 'email':
            return f"<a href='mailto:{val}' style='color:#1e3a5f;text-decoration:none;'>{val}</a>"
        elif key in ('linkedin', 'portfolio', 'github'):
            href = val if val.startswith('http') else f"https://{val}"
            return f"<a href='{href}' target='_blank' style='color:#1e3a5f;text-decoration:none;'>{val}</a>"
        else:
            return val

    contact_parts = []
    for key in ['email','phone','location','linkedin','portfolio','github']:
        val = session_state.get(key,'')
        if val:
            contact_parts.append(_contact_link(key, val))
    contact_line = " &nbsp;|&nbsp; ".join(contact_parts)

    summary_html = _fmt_desc(session_state.get('summary',''), font_size='14px', color='#374151', line_height='1.8')
    fixed_img = _fix_img(profile_img_html)
    job_title_line = f"<div style='font-size:16px;color:#1e3a5f;font-weight:600;margin-top:4px;'>{session_state.get('job_title','')}</div>" if session_state.get('job_title','') else ""

    html_content = f"""<!DOCTYPE html>
<html lang='en'>
<head><meta charset='UTF-8'><title>{session_state.get('name','')} - Resume</title>
<style>
  * {{ box-sizing:border-box; margin:0; padding:0; }}
  body {{ font-family:'Georgia',serif; color:#1a1a1a; background:#fff; padding:40px 60px; line-height:1.6; }}
  a {{ color:#1e3a5f; }}
</style>
</head>
<body>
  <div style='text-align:center;margin-bottom:6px;'>
    {fixed_img}
    <h1 style='font-size:32px;font-weight:700;letter-spacing:1px;color:#1a1a1a;'>{session_state.get('name','')}</h1>
    {job_title_line}
    <div style='font-size:13px;color:#666;margin-top:6px;'>{contact_line}</div>
  </div>
  <hr style='border:none;border-top:3px solid #1e3a5f;margin:16px 0 24px 0;'>

  {section("Professional Summary", summary_html) if summary_html else ''}
  {section("Work Experience", experience_html) if experience_html else ''}
  {section("Education", education_html) if education_html else ''}
  {section("Technical Skills", pills(session_state.get('skills',''))) if session_state.get('skills') else ''}
  {section("Soft Skills", pills(session_state.get('Softskills',''), '#2d6a4f')) if session_state.get('Softskills') else ''}
  {section("Languages", pills(session_state.get('languages',''), '#5c3d11')) if session_state.get('languages') else ''}
  {section("Interests", pills(session_state.get('interests',''), '#4a1942')) if session_state.get('interests') else ''}
  {section("Projects", projects_html) if projects_html else ''}
  {section("Project Links", all_links_html) if all_links_html else ''}
  {section("Certifications", cert_html) if cert_html else ''}
</body></html>"""
    return html_content


# ─────────────────────────────────────────────────────────────
# NEW TEMPLATE 2: Executive (Single Column, Dark Header)
# ─────────────────────────────────────────────────────────────
def render_template_executive(session_state, profile_img_html=""):
    """Executive — single-column with bold dark header band and clean body"""
    import re as _re

    def tag_row(items_str, bg="#eef2ff", color="#3730a3"):
        return "".join(
            f"<span style='display:inline-block;background:{bg};color:{color};border-radius:3px;"
            f"padding:3px 10px;margin:3px 3px 3px 0;font-size:13px;font-weight:600;'>{s.strip()}</span>"
            for s in items_str.split(',') if s.strip()
        )

    # Fix image properly: extract just <img> tag, strip existing styles, apply contained fixed-size circle
    def _fix_img(html, size=96):
        if not html:
            return ""
        img_match = _re.search(r'<img[^>]*>', html)
        if not img_match:
            return ""
        img_tag = img_match.group(0)
        img_tag = _re.sub(r"style=['\"][^'\"]*['\"]", "", img_tag)
        img_tag = img_tag.replace(
            "<img ",
            f"<img style='width:{size}px;height:{size}px;border-radius:50%;object-fit:cover;object-position:center;border:3px solid #fff;display:block;' "
        )
        return img_tag

    exp_html = ""
    for exp in session_state.experience_entries:
        if exp.get("company") or exp.get("title"):
            desc = _fmt_desc(exp.get("description",""), font_size='14px', color='#374151', line_height='1.75')
            exp_html += f"""
            <div style='margin-bottom:20px;padding-left:16px;border-left:3px solid #3730a3;'>
                <div style='display:flex;justify-content:space-between;flex-wrap:wrap;gap:6px;'>
                    <div><span style='font-size:16px;font-weight:700;color:#111;'>{exp.get('company','')}</span>
                    &nbsp;<span style='font-size:14px;color:#3730a3;font-weight:600;font-style:italic;'>— {exp.get('title','')}</span></div>
                    <span style='font-size:13px;color:#777;white-space:nowrap;'>{exp.get('duration','')}</span>
                </div>
                <div style='font-size:14px;color:#333;margin-top:6px;line-height:1.7;'>{desc}</div>
            </div>"""

    edu_html = ""
    for edu in session_state.education_entries:
        if edu.get("institution"):
            degree_val = edu.get("degree","")
            if isinstance(degree_val, list): degree_val = ", ".join(degree_val)
            edu_html += f"""
            <div style='margin-bottom:12px;padding-left:16px;border-left:3px solid #3730a3;'>
                <div style='display:flex;justify-content:space-between;'>
                    <strong style='font-size:15px;'>{edu.get('institution','')}</strong>
                    <span style='font-size:13px;color:#777;'>{edu.get('year','')}</span>
                </div>
                <div style='font-size:14px;color:#3730a3;font-style:italic;font-weight:600;'>{degree_val}</div>
                <div style='font-size:13px;color:#666;'>{edu.get('details','')}</div>
            </div>"""

    proj_html = ""
    for idx, proj in enumerate(session_state.project_entries):
        if proj.get("title"):
            desc = _fmt_desc(proj.get('description',''), font_size='14px', color='#374151', line_height='1.75')
            proj_links = getattr(session_state, 'project_links', []) or []
            proj_link_html = ""
            if idx < len(proj_links) and proj_links[idx]:
                proj_link_html = f"<div style='margin-top:5px;'><a href='{proj_links[idx]}' target='_blank' style='color:#3730a3;font-size:13px;font-weight:600;'>&#128279; View Project / GitHub</a></div>"
            proj_html += f"""
            <div style='margin-bottom:14px;padding-left:16px;border-left:3px solid #3730a3;'>
                <div style='display:flex;justify-content:space-between;'>
                    <strong style='font-size:15px;color:#1a1a1a;'>{proj.get('title','')}</strong>
                    <span style='font-size:13px;color:#777;'>{proj.get('duration','')}</span>
                </div>
                <div style='font-size:13px;color:#3730a3;font-weight:600;'><b>Stack:</b> {proj.get('tech','')}</div>
                <div style='font-size:14px;margin-top:4px;'>{desc}</div>
                {proj_link_html}
            </div>"""

    # All project links
    proj_links_all = getattr(session_state, 'project_links', []) or []
    proj_links_section = ""
    if proj_links_all:
        items = "".join(
            f"<div style='margin-bottom:6px;'><a href='{lnk}' target='_blank' style='color:#3730a3;font-size:14px;font-weight:600;'>&#128279; Project {i+1}: {lnk}</a></div>"
            for i, lnk in enumerate(proj_links_all)
        )
        proj_links_section = items

    cert_html = ""
    for cert in session_state.certificate_links:
        if cert.get("name"):
            cert_html += f"""
            <div style='margin-bottom:10px;'>
                <a href='{cert.get("link","#")}' target='_blank' style='font-weight:600;font-size:15px;color:#3730a3;text-decoration:none;'>{cert.get("name","")}</a>
                <span style='font-size:13px;color:#777;'> &nbsp;·&nbsp; {cert.get("duration","")}</span>
                <div style='font-size:13px;color:#444;'>{cert.get("description","").replace(chr(10),"<br>")}</div>
            </div>"""

    def sec(title, body):
        return f"""
        <div style='margin-bottom:28px;'>
            <h2 style='font-size:13px;letter-spacing:2.5px;text-transform:uppercase;font-weight:700;
                color:#3730a3;margin-bottom:12px;padding-bottom:5px;border-bottom:1px solid #c7d7f5;'>{title}</h2>
            {body}
        </div>"""

    # SVG icons for contact
    SVG_EMAIL = '<svg xmlns="http://www.w3.org/2000/svg" width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" style="vertical-align:middle;margin-right:5px;"><path d="M4 4h16c1.1 0 2 .9 2 2v12c0 1.1-.9 2-2 2H4c-1.1 0-2-.9-2-2V6c0-1.1.9-2 2-2z"/><polyline points="22,6 12,13 2,6"/></svg>'
    SVG_PHONE = '<svg xmlns="http://www.w3.org/2000/svg" width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" style="vertical-align:middle;margin-right:5px;"><path d="M22 16.92v3a2 2 0 0 1-2.18 2 19.79 19.79 0 0 1-8.63-3.07A19.5 19.5 0 0 1 4.69 12 19.79 19.79 0 0 1 1.65 3.37 2 2 0 0 1 3.64 1h3a2 2 0 0 1 2 1.72c.127.96.361 1.903.7 2.81a2 2 0 0 1-.45 2.11L7.91 8.8a16 16 0 0 0 6.29 6.29l.98-.98a2 2 0 0 1 2.11-.45c.907.339 1.85.573 2.81.7A2 2 0 0 1 22 16.92z"/></svg>'
    SVG_LOCATION = '<svg xmlns="http://www.w3.org/2000/svg" width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" style="vertical-align:middle;margin-right:5px;"><path d="M21 10c0 7-9 13-9 13s-9-6-9-13a9 9 0 0 1 18 0z"/><circle cx="12" cy="10" r="3"/></svg>'
    SVG_LINKEDIN = '<svg xmlns="http://www.w3.org/2000/svg" width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" style="vertical-align:middle;margin-right:5px;"><path d="M16 8a6 6 0 0 1 6 6v7h-4v-7a2 2 0 0 0-2-2 2 2 0 0 0-2 2v7h-4v-7a6 6 0 0 1 6-6z"/><rect x="2" y="9" width="4" height="12"/><circle cx="4" cy="4" r="2"/></svg>'
    SVG_GITHUB = '<svg xmlns="http://www.w3.org/2000/svg" width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" style="vertical-align:middle;margin-right:5px;"><path d="M9 19c-5 1.5-5-2.5-7-3m14 6v-3.87a3.37 3.37 0 0 0-.94-2.61c3.14-.35 6.44-1.54 6.44-7A5.44 5.44 0 0 0 20 4.77 5.07 5.07 0 0 0 19.91 1S18.73.65 16 2.48a13.38 13.38 0 0 0-7 0C6.27.65 5.09 1 5.09 1A5.07 5.07 0 0 0 5 4.77a5.44 5.44 0 0 0-1.5 3.78c0 5.42 3.3 6.61 6.44 7A3.37 3.37 0 0 0 9 18.13V22"/></svg>'
    SVG_PORTFOLIO = '<svg xmlns="http://www.w3.org/2000/svg" width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" style="vertical-align:middle;margin-right:5px;"><circle cx="12" cy="12" r="10"/><line x1="2" y1="12" x2="22" y2="12"/><path d="M12 2a15.3 15.3 0 0 1 4 10 15.3 15.3 0 0 1-4 10 15.3 15.3 0 0 1-4-10 15.3 15.3 0 0 1 4-10z"/></svg>'

    contact_items = [
        (session_state.get('email',''), SVG_EMAIL, 'email'),
        (session_state.get('phone',''), SVG_PHONE, 'phone'),
        (session_state.get('location',''), SVG_LOCATION, 'location'),
        (session_state.get('linkedin',''), SVG_LINKEDIN, 'linkedin'),
        (session_state.get('portfolio',''), SVG_PORTFOLIO, 'portfolio'),
        (session_state.get('github',''), SVG_GITHUB, 'github'),
    ]
    def _exec_contact_item(val, icon, key):
        if key == 'email':
            return f"<span>{icon}<a href='mailto:{val}' style='color:#a5b4fc;text-decoration:none;'>{val}</a></span>"
        elif key == 'phone' or key == 'location':
            return f"<span>{icon}{val}</span>"
        else:
            href = val if val.startswith('http') else f"https://{val}"
            return f"<span>{icon}<a href='{href}' target='_blank' style='color:#a5b4fc;text-decoration:none;'>{val}</a></span>"
    contact_html = " &nbsp; ".join(
        _exec_contact_item(val, icon, key) for val, icon, key in contact_items if val
    )

    summary_html = _fmt_desc(session_state.get('summary',''), font_size='14px', color='#374151', line_height='1.8')
    fixed_img = _fix_img(profile_img_html)
    job_title_val = session_state.get('job_title','') or session_state.get('title','')

    return f"""<!DOCTYPE html>
<html lang='en'>
<head><meta charset='UTF-8'><title>{session_state.get('name','')} - Executive Resume</title>
<style>* {{ box-sizing:border-box; margin:0; padding:0; }} body {{ font-family:'Segoe UI',Arial,sans-serif; color:#1a1a1a; background:#fff; line-height:1.6; }}</style>
</head>
<body>
  <!-- Header Band -->
  <div style='background:linear-gradient(135deg,#1e1b4b 0%,#3730a3 100%);color:white;padding:36px 50px;'>
    <table role='presentation' style='width:100%;border-collapse:collapse;'>
    <tr>
      <td style='vertical-align:middle;'>
        <h1 style='font-size:34px;font-weight:800;letter-spacing:-0.5px;'>{session_state.get('name','')}</h1>
        <div style='font-size:17px;color:#c7d2fe;margin-top:6px;font-weight:600;'>{job_title_val}</div>
        <div style='font-size:13px;color:#a5b4fc;margin-top:10px;'>{contact_html}</div>
      </td>
      {'<td style="vertical-align:middle;text-align:right;width:110px;">' + fixed_img + '</td>' if fixed_img else ''}
    </tr>
    </table>
  </div>
  <!-- Body -->
  <div style='padding:36px 50px;'>
    {sec("Summary", summary_html) if summary_html else ''}
    {sec("Experience", exp_html) if exp_html else ''}
    {sec("Education", edu_html) if edu_html else ''}
    {sec("Skills", tag_row(session_state.get('skills',''))) if session_state.get('skills') else ''}
    {sec("Soft Skills", tag_row(session_state.get('Softskills',''),'#ecfdf5','#065f46')) if session_state.get('Softskills') else ''}
    {sec("Languages", tag_row(session_state.get('languages',''),'#fef9ee','#78350f')) if session_state.get('languages') else ''}
    {sec("Interests", tag_row(session_state.get('interests',''),'#fdf4ff','#7e22ce')) if session_state.get('interests') else ''}
    {sec("Projects", proj_html) if proj_html else ''}
    {sec("Project Links", proj_links_section) if proj_links_section else ''}
    {sec("Certifications", cert_html) if cert_html else ''}
  </div>
</body></html>"""


# ─────────────────────────────────────────────────────────────
# NEW TEMPLATE 3: Timeline (Single Column, Timeline Design)
# ─────────────────────────────────────────────────────────────
def render_template_timeline(session_state, profile_img_html=""):
    """Timeline — single-column with vertical timeline for experience & education"""
    import re as _re

    def chips(items_str, bg="#fef3c7", color="#92400e"):
        return "".join(
            f"<span style='display:inline-block;background:{bg};color:{color};border-radius:20px;"
            f"padding:4px 14px;margin:4px 4px 4px 0;font-size:13px;font-weight:600;'>{s.strip()}</span>"
            for s in items_str.split(',') if s.strip()
        )

    def _fix_img(html, size=95):
        if not html:
            return ""
        img_match = _re.search(r'<img[^>]*>', html)
        if not img_match:
            return ""
        img_tag = img_match.group(0)
        img_tag = _re.sub(r"style=['\"][^'\"]*['\"]", "", img_tag)
        img_tag = img_tag.replace(
            "<img ",
            f"<img style='width:{size}px;height:{size}px;border-radius:50%;object-fit:cover;object-position:center;border:4px solid #0d9488;display:block;' "
        )
        return img_tag

    def timeline_item(title, subtitle, date, body, accent="#0d9488", proj_link=""):
        link_html = f"<div style='margin-top:5px;'><a href='{proj_link}' target='_blank' style='color:{accent};font-size:13px;font-weight:600;'>&#128279; View Project / GitHub</a></div>" if proj_link else ""
        return f"""
        <div style='display:flex;margin-bottom:24px;position:relative;'>
            <div style='flex-shrink:0;display:flex;flex-direction:column;align-items:center;margin-right:20px;'>
                <div style='width:14px;height:14px;background:{accent};border-radius:50%;border:3px solid white;box-shadow:0 0 0 2px {accent};z-index:1;'></div>
                <div style='width:2px;flex:1;background:#e2e8f0;margin-top:4px;'></div>
            </div>
            <div style='flex:1;padding-bottom:10px;'>
                <div style='display:flex;justify-content:space-between;align-items:baseline;flex-wrap:wrap;'>
                    <strong style='font-size:16px;color:#1a1a1a;'>{title}</strong>
                    <span style='font-size:12px;color:#64748b;background:#f1f5f9;padding:2px 10px;border-radius:10px;'>{date}</span>
                </div>
                <div style='font-size:14px;color:{accent};font-weight:600;margin-bottom:5px;'>{subtitle}</div>
                <div style='font-size:14px;color:#374151;line-height:1.7;'>{body}</div>
                {link_html}
            </div>
        </div>"""

    exp_items = "".join(
        timeline_item(
            e.get('company',''), e.get('title',''), e.get('duration',''),
            _fmt_desc(e.get('description',''), font_size='14px', color='#374151', line_height='1.75'), "#0d9488"
        )
        for e in session_state.experience_entries if e.get('company') or e.get('title')
    )

    edu_items = "".join(
        timeline_item(
            e.get('institution',''),
            (e.get('degree','') if not isinstance(e.get('degree',''),list) else ', '.join(e.get('degree',[]))),
            e.get('year',''), e.get('details',''), "#6366f1"
        )
        for e in session_state.education_entries if e.get('institution')
    )

    proj_links_all = getattr(session_state, 'project_links', []) or []
    proj_items = "".join(
        timeline_item(
            p.get('title',''), f"Stack: {p.get('tech','')}",  p.get('duration',''),
            _fmt_desc(p.get('description',''), font_size='14px', color='#374151', line_height='1.75'),
            "#f59e0b",
            proj_links_all[i] if i < len(proj_links_all) else ""
        )
        for i, p in enumerate(session_state.project_entries) if p.get('title')
    )

    all_links_html = ""
    if proj_links_all:
        items = "".join(
            f"<div style='margin-bottom:8px;'><a href='{lnk}' target='_blank' style='color:#0d9488;font-size:14px;font-weight:600;'>&#128279; Project {i+1}: {lnk}</a></div>"
            for i, lnk in enumerate(proj_links_all)
        )
        all_links_html = items

    cert_items = "".join(
        f"<div style='margin-bottom:10px;display:flex;align-items:center;gap:10px;'>"
        f"<span style='width:8px;height:8px;background:#0d9488;border-radius:50%;flex-shrink:0;'></span>"
        f"<a href='{c.get('link','#')}' target='_blank' style='font-weight:600;color:#0d9488;font-size:14px;text-decoration:none;'>{c.get('name','')}</a>"
        f"<span style='font-size:12px;color:#64748b;'>· {c.get('duration','')}</span></div>"
        for c in session_state.certificate_links if c.get('name')
    )

    def sec(title, body, accent="#0d9488"):
        return f"""
        <div style='margin-bottom:30px;'>
            <h2 style='font-size:18px;font-weight:700;color:{accent};margin-bottom:16px;
                padding-bottom:6px;border-bottom:2px solid {accent};letter-spacing:0.5px;'>{title}</h2>
            {body}
        </div>"""

    fixed_img = _fix_img(profile_img_html)
    job_title_val = session_state.get('job_title','') or session_state.get('title','')

    contact_parts = []
    for key in ['email','phone','location','linkedin','portfolio','github']:
        val = session_state.get(key,'')
        if val:
            if key == 'email':
                contact_parts.append(f"<a href='mailto:{val}' style='color:#64748b;text-decoration:none;'>{val}</a>")
            elif key in ('linkedin', 'portfolio', 'github'):
                href = val if val.startswith('http') else f"https://{val}"
                contact_parts.append(f"<a href='{href}' target='_blank' style='color:#64748b;text-decoration:none;'>{val}</a>")
            else:
                contact_parts.append(val)
    contact_line = " · ".join(contact_parts)
    summary_html = _fmt_desc(session_state.get('summary',''), font_size='14px', color='#374151', line_height='1.8')

    return f"""<!DOCTYPE html>
<html lang='en'>
<head><meta charset='UTF-8'><title>{session_state.get('name','')} - Timeline Resume</title>
<style>* {{ box-sizing:border-box; margin:0; padding:0; }} body {{ font-family:'Segoe UI',sans-serif; background:#fff; color:#1a1a1a; }}</style>
</head>
<body>
  <div style='background:#0d9488;height:6px;'></div>
  <div style='padding:36px 50px 24px;border-bottom:1px solid #e2e8f0;'>
    <table role='presentation' style='width:100%;border-collapse:collapse;'>
    <tr>
      <td style='vertical-align:middle;'>
        <h1 style='font-size:36px;font-weight:800;color:#134e4a;letter-spacing:-1px;'>{session_state.get('name','')}</h1>
        <div style='font-size:17px;color:#0d9488;font-weight:700;margin-top:4px;'>{job_title_val}</div>
        <div style='font-size:13px;color:#64748b;margin-top:8px;'>{contact_line}</div>
      </td>
      {'<td style="vertical-align:middle;text-align:right;width:110px;">' + fixed_img + '</td>' if fixed_img else ''}
    </tr>
    </table>
  </div>
  <div style='padding:30px 50px;'>
    {sec("About Me", summary_html) if summary_html else ''}
    {sec("Experience", exp_items) if exp_items else ''}
    {sec("Education", edu_items, "#6366f1") if edu_items else ''}
    {sec("Projects", proj_items, "#f59e0b") if proj_items else ''}
    {sec("Project Links", all_links_html) if all_links_html else ''}
    {sec("Skills", chips(session_state.get('skills',''),'#ccfbf1','#134e4a')) if session_state.get('skills') else ''}
    {sec("Soft Skills", chips(session_state.get('Softskills',''),'#ede9fe','#4c1d95')) if session_state.get('Softskills') else ''}
    {sec("Languages", chips(session_state.get('languages',''),'#fef9c3','#713f12')) if session_state.get('languages') else ''}
    {sec("Interests", chips(session_state.get('interests',''),'#fee2e2','#991b1b')) if session_state.get('interests') else ''}
    {sec("Certifications", cert_items) if cert_items else ''}
  </div>
</body></html>"""
# ─────────────────────────────────────────────────────────────
# NEW TEMPLATE 4: Corporate Two-Column (Blue Theme)
# ─────────────────────────────────────────────────────────────
def render_template_corporate(session_state, profile_img_html=""):
    """Corporate Blue Two-Column — ATS-friendly, advanced blue accent sidebar"""
    import re as _re

    def _fix_img(html, size=108):
        if not html:
            return ""
        img_match = _re.search(r'<img[^>]*>', html)
        if not img_match:
            return ""
        img_tag = img_match.group(0)
        img_tag = _re.sub(r"style=['\"][^\'\"]*['\"]", "", img_tag)
        img_tag = img_tag.replace("<img ", f"<img style='width:{size}px;height:{size}px;border-radius:50%;object-fit:cover;object-position:center;border:3px solid #93c5fd;display:block;margin:0 auto;' ")
        return img_tag

    def badge(item, bg="#1d4ed8", color="#fff"):
        return (f"<span style='display:inline-block;background:{bg};color:{color};border-radius:4px;"
                f"padding:3px 10px;margin:3px 3px 3px 0;font-size:12px;font-weight:600;'>{item.strip()}</span>")

    def badges(items_str, bg="#1d4ed8", color="#fff"):
        return "".join(badge(s, bg, color) for s in items_str.split(',') if s.strip())

    exp_html = ""
    for exp in session_state.experience_entries:
        if exp.get('company') or exp.get('title'):
            desc = _fmt_desc(exp.get('description',''), font_size='13px', color='#374151', line_height='1.75')
            exp_html += f"""
            <div style='margin-bottom:20px;border-left:3px solid #1d4ed8;padding-left:14px;'>
                <div style='display:flex;justify-content:space-between;align-items:baseline;flex-wrap:wrap;gap:6px;'>
                    <strong style='font-size:15px;color:#1e3a8a;'>{exp.get('company','')}</strong>
                    <span style='font-size:12px;color:#64748b;background:#eff6ff;padding:2px 8px;border-radius:8px;'>{exp.get('duration','')}</span>
                </div>
                <div style='font-size:13px;color:#3b82f6;font-weight:700;margin-bottom:5px;'>{exp.get('title','')}</div>
                <div style='font-size:13px;color:#374151;line-height:1.7;'>{desc}</div>
            </div>
            <div style='border-bottom:1px dashed #bfdbfe;margin-bottom:12px;'></div>"""

    edu_html = ""
    for edu in session_state.education_entries:
        if edu.get('institution'):
            degree_val = edu.get('degree','')
            if isinstance(degree_val, list): degree_val = ", ".join(degree_val)
            edu_html += f"""
            <div style='margin-bottom:14px;border-left:3px solid #1d4ed8;padding-left:12px;'>
                <strong style='font-size:14px;color:#1e3a8a;'>{edu.get('institution','')}</strong>
                <span style='float:right;font-size:12px;color:#64748b;'>{edu.get('year','')}</span>
                <div style='clear:both;font-size:13px;color:#3b82f6;font-style:italic;font-weight:600;'>{degree_val}</div>
                <div style='font-size:12px;color:#6b7280;'>{edu.get('details','')}</div>
            </div>"""

    proj_html = ""
    proj_links_all = getattr(session_state, 'project_links', []) or []
    for idx, proj in enumerate(session_state.project_entries):
        if proj.get('title'):
            desc = _fmt_desc(proj.get('description',''), font_size='13px', color='#374151', line_height='1.75')
            proj_link_html = ""
            if idx < len(proj_links_all) and proj_links_all[idx]:
                proj_link_html = f"<div style='margin-top:5px;'><a href='{proj_links_all[idx]}' target='_blank' style='color:#1d4ed8;font-size:12px;font-weight:600;'>&#128279; View Project / GitHub</a></div>"
            proj_html += f"""
            <div style='margin-bottom:14px;padding:12px 14px;background:#eff6ff;border-radius:6px;border-left:3px solid #1d4ed8;'>
                <div style='display:flex;justify-content:space-between;flex-wrap:wrap;gap:4px;'>
                    <strong style='font-size:14px;color:#1e3a8a;'>{proj.get('title','')}</strong>
                    <span style='font-size:12px;color:#64748b;'>{proj.get('duration','')}</span>
                </div>
                <div style='font-size:12px;color:#3b82f6;font-weight:600;margin-bottom:4px;'>{proj.get('tech','')}</div>
                <div style='font-size:13px;color:#374151;'>{desc}</div>
                {proj_link_html}
            </div>"""

    cert_sidebar = ""
    for cert in session_state.certificate_links:
        if cert.get('name'):
            cert_sidebar += f"""
            <div style='margin-bottom:10px;padding:8px;background:rgba(255,255,255,0.1);border-radius:6px;'>
                <a href='{cert.get("link","#")}' style='color:#93c5fd;font-size:13px;font-weight:600;text-decoration:none;'>{cert.get('name','')}</a>
                <div style='font-size:11px;color:#bfdbfe;'>{cert.get('duration','')}</div>
            </div>"""

    all_links_html = ""
    if proj_links_all:
        items = "".join(
            f"<div style='margin-bottom:6px;'><a href='{lnk}' target='_blank' style='color:#93c5fd;font-size:12px;font-weight:600;'>&#128279; Project {i+1}</a></div>"
            for i, lnk in enumerate(proj_links_all)
        )
        all_links_html = items

    SVG_ICONS = {
        'email': '<svg xmlns="http://www.w3.org/2000/svg" width="13" height="13" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M4 4h16c1.1 0 2 .9 2 2v12c0 1.1-.9 2-2 2H4c-1.1 0-2-.9-2-2V6c0-1.1.9-2 2-2z"/><polyline points="22,6 12,13 2,6"/></svg>',
        'phone': '<svg xmlns="http://www.w3.org/2000/svg" width="13" height="13" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M22 16.92v3a2 2 0 0 1-2.18 2 19.79 19.79 0 0 1-8.63-3.07A19.5 19.5 0 0 1 4.69 12 19.79 19.79 0 0 1 1.65 3.37 2 2 0 0 1 3.64 1h3a2 2 0 0 1 2 1.72c.127.96.361 1.903.7 2.81a2 2 0 0 1-.45 2.11L7.91 8.8a16 16 0 0 0 6.29 6.29l.98-.98a2 2 0 0 1 2.11-.45c.907.339 1.85.573 2.81.7A2 2 0 0 1 22 16.92z"/></svg>',
        'location': '<svg xmlns="http://www.w3.org/2000/svg" width="13" height="13" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M21 10c0 7-9 13-9 13s-9-6-9-13a9 9 0 0 1 18 0z"/><circle cx="12" cy="10" r="3"/></svg>',
        'linkedin': '<svg xmlns="http://www.w3.org/2000/svg" width="13" height="13" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M16 8a6 6 0 0 1 6 6v7h-4v-7a2 2 0 0 0-2-2 2 2 0 0 0-2 2v7h-4v-7a6 6 0 0 1 6-6z"/><rect x="2" y="9" width="4" height="12"/><circle cx="4" cy="4" r="2"/></svg>',
        'portfolio': '<svg xmlns="http://www.w3.org/2000/svg" width="13" height="13" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><circle cx="12" cy="12" r="10"/><line x1="2" y1="12" x2="22" y2="12"/><path d="M12 2a15.3 15.3 0 0 1 4 10 15.3 15.3 0 0 1-4 10 15.3 15.3 0 0 1-4-10 15.3 15.3 0 0 1 4-10z"/></svg>',
        'github': '<svg xmlns="http://www.w3.org/2000/svg" width="13" height="13" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M9 19c-5 1.5-5-2.5-7-3m14 6v-3.87a3.37 3.37 0 0 0-.94-2.61c3.14-.35 6.44-1.54 6.44-7A5.44 5.44 0 0 0 20 4.77 5.07 5.07 0 0 0 19.91 1S18.73.65 16 2.48a13.38 13.38 0 0 0-7 0C6.27.65 5.09 1 5.09 1A5.07 5.07 0 0 0 5 4.77a5.44 5.44 0 0 0-1.5 3.78c0 5.42 3.3 6.61 6.44 7A3.37 3.37 0 0 0 9 18.13V22"/></svg>'
    }

    contact_html = ""
    for key in ['email','phone','location','linkedin','portfolio','github']:
        val = session_state.get(key,'')
        if val:
            if key == 'email':
                val_html = f"<a href='mailto:{val}' style='color:#bfdbfe;text-decoration:none;word-break:break-all;'>{val}</a>"
            elif key in ('linkedin', 'portfolio', 'github'):
                href = val if val.startswith('http') else f"https://{val}"
                val_html = f"<a href='{href}' target='_blank' style='color:#bfdbfe;text-decoration:none;word-break:break-all;'>{val}</a>"
            else:
                val_html = f"<span style='word-break:break-all;'>{val}</span>"
            contact_html += f"<div style='margin-bottom:8px;font-size:12px;color:#bfdbfe;display:flex;align-items:center;gap:5px;'><span style='flex-shrink:0;'>{SVG_ICONS[key]}</span>{val_html}</div>"

    summary_html = _fmt_desc(session_state.get('summary',''), font_size='13px', color='#374151', line_height='1.8')
    fixed_img = _fix_img(profile_img_html)
    job_title_val = session_state.get('job_title','') or session_state.get('title','')

    def main_sec(title, body):
        return f"""<div style='margin-bottom:26px;'>
            <h3 style='font-size:13px;letter-spacing:2px;text-transform:uppercase;font-weight:700;color:#1e3a8a;
                border-bottom:2px solid #3b82f6;padding-bottom:5px;margin-bottom:14px;'>{title}</h3>{body}</div>"""

    def side_sec(title, body):
        return f"""<div style='margin-bottom:24px;'>
            <h3 style='font-size:11px;letter-spacing:2px;text-transform:uppercase;color:#93c5fd;font-weight:700;
                border-bottom:1px solid rgba(147,197,253,0.3);padding-bottom:5px;margin-bottom:12px;'>{title}</h3>{body}</div>"""

    return f"""<!DOCTYPE html>
<html lang='en'>
<head><meta charset='UTF-8'><title>{session_state.get('name','')} - Corporate Resume</title>
<style>* {{ box-sizing:border-box; margin:0; padding:0; }} body {{ font-family:'Segoe UI',sans-serif; background:#fff; }}</style>
</head>
<body>
<table role='presentation' style='width:100%;min-height:100vh;border-collapse:collapse;table-layout:fixed;'>
<tr>
  <td style='width:300px;background:linear-gradient(180deg,#1e3a8a,#1d4ed8);color:white;padding:36px 24px;vertical-align:top;'>
    {'<div style="margin:0 auto 14px;text-align:center;">' + fixed_img + '</div>' if fixed_img else ''}
    <h1 style='font-size:21px;font-weight:800;color:#fff;text-align:center;margin-bottom:4px;'>{session_state.get('name','')}</h1>
    <div style='font-size:13px;color:#93c5fd;text-align:center;margin-bottom:24px;font-weight:600;'>{job_title_val}</div>
    {side_sec("Contact", contact_html)}
    {side_sec("Skills", badges(session_state.get('skills',''),'rgba(255,255,255,0.15)','#e0f2fe')) if session_state.get('skills') else ''}
    {side_sec("Soft Skills", badges(session_state.get('Softskills',''),'rgba(255,255,255,0.1)','#ddd6fe')) if session_state.get('Softskills') else ''}
    {side_sec("Languages", badges(session_state.get('languages',''),'rgba(255,255,255,0.1)','#fef3c7')) if session_state.get('languages') else ''}
    {side_sec("Interests", badges(session_state.get('interests',''),'rgba(255,255,255,0.1)','#fce7f3')) if session_state.get('interests') else ''}
    {side_sec("Certifications", cert_sidebar) if cert_sidebar else ''}
    {side_sec("Project Links", all_links_html) if all_links_html else ''}
  </td>
  <td style='padding:40px 44px;background:#fff;vertical-align:top;'>
    {main_sec("Professional Summary", summary_html) if summary_html else ''}
    {main_sec("Work Experience", exp_html) if exp_html else ''}
    {main_sec("Education", edu_html) if edu_html else ''}
    {main_sec("Projects", proj_html) if proj_html else ''}
  </td>
</tr>
</table>
</body></html>"""


def render_template_creative_green(session_state, profile_img_html=""):
    """Creative Green Two-Column — ATS-friendly, fresh green accents"""
    import re as _re

    def _fix_img(html, size=100):
        if not html:
            return ""
        img_match = _re.search(r'<img[^>]*>', html)
        if not img_match:
            return ""
        img_tag = img_match.group(0)
        img_tag = _re.sub(r"style=['\"][^\'\"]*['\"]", "", img_tag)
        img_tag = img_tag.replace("<img ", f"<img style='width:{size}px;height:{size}px;border-radius:50%;object-fit:cover;object-position:center;border:4px solid #059669;display:block;margin:0 auto;' ")
        return img_tag

    def pill(s, bg="#d1fae5", color="#065f46"):
        return (f"<span style='display:inline-block;background:{bg};color:{color};border-radius:20px;"
                f"padding:4px 12px;margin:3px 3px 3px 0;font-size:12px;font-weight:600;'>{s.strip()}</span>")

    def pills(items_str, bg="#d1fae5", color="#065f46"):
        return "".join(pill(s, bg, color) for s in items_str.split(',') if s.strip())

    exp_html = ""
    for exp in session_state.experience_entries:
        if exp.get('company') or exp.get('title'):
            desc = _fmt_desc(exp.get('description',''), font_size='13px', color='#374151', line_height='1.75')
            exp_html += f"""
            <div style='margin-bottom:18px;padding:14px;border-radius:8px;background:#f0fdf4;border-left:4px solid #059669;'>
                <div style='display:flex;justify-content:space-between;flex-wrap:wrap;gap:5px;'>
                    <strong style='font-size:15px;color:#064e3b;'>{exp.get('company','')}</strong>
                    <span style='font-size:12px;color:#6b7280;background:#dcfce7;padding:2px 8px;border-radius:10px;'>{exp.get('duration','')}</span>
                </div>
                <div style='font-size:13px;color:#059669;font-weight:700;margin:3px 0 6px;'>{exp.get('title','')}</div>
                <div style='font-size:13px;color:#374151;line-height:1.7;'>{desc}</div>
            </div>"""

    edu_html = ""
    for edu in session_state.education_entries:
        if edu.get('institution'):
            degree_val = edu.get('degree','')
            if isinstance(degree_val,list): degree_val = ", ".join(degree_val)
            edu_html += f"""
            <div style='margin-bottom:14px;padding:12px;background:#f0fdf4;border-radius:6px;border-left:3px solid #059669;'>
                <div style='display:flex;justify-content:space-between;'>
                    <strong style='font-size:14px;color:#064e3b;'>{edu.get('institution','')}</strong>
                    <span style='font-size:12px;color:#6b7280;'>{edu.get('year','')}</span>
                </div>
                <div style='font-size:13px;color:#059669;font-style:italic;font-weight:600;'>{degree_val}</div>
                <div style='font-size:12px;color:#6b7280;'>{edu.get('details','')}</div>
            </div>"""

    proj_html = ""
    proj_links_all = getattr(session_state, 'project_links', []) or []
    for idx, proj in enumerate(session_state.project_entries):
        if proj.get('title'):
            desc = _fmt_desc(proj.get('description',''), font_size='13px', color='#374151', line_height='1.75')
            proj_link_html = ""
            if idx < len(proj_links_all) and proj_links_all[idx]:
                proj_link_html = f"<div style='margin-top:5px;'><a href='{proj_links_all[idx]}' target='_blank' style='color:#059669;font-size:12px;font-weight:600;'>&#128279; View Project / GitHub</a></div>"
            proj_html += f"""
            <div style='margin-bottom:14px;padding:12px;background:#fff;border:1px solid #a7f3d0;border-radius:8px;'>
                <div style='display:flex;justify-content:space-between;flex-wrap:wrap;gap:4px;'>
                    <strong style='font-size:14px;color:#064e3b;'>{proj.get('title','')}</strong>
                    <span style='font-size:12px;color:#6b7280;'>{proj.get('duration','')}</span>
                </div>
                <div style='font-size:12px;color:#059669;font-weight:600;margin-bottom:4px;'>{proj.get('tech','')}</div>
                <div style='font-size:13px;color:#374151;'>{desc}</div>
                {proj_link_html}
            </div>"""

    contact_html = ""
    SVG_ICONS = {
        'email': '<svg xmlns="http://www.w3.org/2000/svg" width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M4 4h16c1.1 0 2 .9 2 2v12c0 1.1-.9 2-2 2H4c-1.1 0-2-.9-2-2V6c0-1.1.9-2 2-2z"/><polyline points="22,6 12,13 2,6"/></svg>',
        'phone': '<svg xmlns="http://www.w3.org/2000/svg" width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M22 16.92v3a2 2 0 0 1-2.18 2 19.79 19.79 0 0 1-8.63-3.07A19.5 19.5 0 0 1 4.69 12 19.79 19.79 0 0 1 1.65 3.37 2 2 0 0 1 3.64 1h3a2 2 0 0 1 2 1.72c.127.96.361 1.903.7 2.81a2 2 0 0 1-.45 2.11L7.91 8.8a16 16 0 0 0 6.29 6.29l.98-.98a2 2 0 0 1 2.11-.45c.907.339 1.85.573 2.81.7A2 2 0 0 1 22 16.92z"/></svg>',
        'location': '<svg xmlns="http://www.w3.org/2000/svg" width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M21 10c0 7-9 13-9 13s-9-6-9-13a9 9 0 0 1 18 0z"/><circle cx="12" cy="10" r="3"/></svg>',
        'linkedin': '<svg xmlns="http://www.w3.org/2000/svg" width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M16 8a6 6 0 0 1 6 6v7h-4v-7a2 2 0 0 0-2-2 2 2 0 0 0-2 2v7h-4v-7a6 6 0 0 1 6-6z"/><rect x="2" y="9" width="4" height="12"/><circle cx="4" cy="4" r="2"/></svg>',
        'portfolio': '<svg xmlns="http://www.w3.org/2000/svg" width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><circle cx="12" cy="12" r="10"/><line x1="2" y1="12" x2="22" y2="12"/><path d="M12 2a15.3 15.3 0 0 1 4 10 15.3 15.3 0 0 1-4 10 15.3 15.3 0 0 1-4-10 15.3 15.3 0 0 1 4-10z"/></svg>',
        'github': '<svg xmlns="http://www.w3.org/2000/svg" width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M9 19c-5 1.5-5-2.5-7-3m14 6v-3.87a3.37 3.37 0 0 0-.94-2.61c3.14-.35 6.44-1.54 6.44-7A5.44 5.44 0 0 0 20 4.77 5.07 5.07 0 0 0 19.91 1S18.73.65 16 2.48a13.38 13.38 0 0 0-7 0C6.27.65 5.09 1 5.09 1A5.07 5.07 0 0 0 5 4.77a5.44 5.44 0 0 0-1.5 3.78c0 5.42 3.3 6.61 6.44 7A3.37 3.37 0 0 0 9 18.13V22"/></svg>'
    }
    for key in ['email','phone','location','linkedin','portfolio','github']:
        val = session_state.get(key,'')
        if val:
            if key == 'email':
                val_html = f"<a href='mailto:{val}' style='color:#059669;text-decoration:none;word-break:break-all;'>{val}</a>"
            elif key in ('linkedin', 'portfolio', 'github'):
                href = val if val.startswith('http') else f"https://{val}"
                val_html = f"<a href='{href}' target='_blank' style='color:#059669;text-decoration:none;word-break:break-all;'>{val}</a>"
            else:
                val_html = f"<span style='word-break:break-all;'>{val}</span>"
            contact_html += f"<div style='display:flex;align-items:center;margin-bottom:8px;font-size:13px;color:#374151;gap:6px;'><span style='flex-shrink:0;color:#059669;'>{SVG_ICONS[key]}</span>{val_html}</div>"

    cert_html = ""
    for cert in session_state.certificate_links:
        if cert.get('name'):
            cert_html += (f"<div style='margin-bottom:8px;'>"
                          f"<a href='{cert.get('link','#')}' style='color:#059669;font-size:13px;font-weight:600;text-decoration:none;'>{cert.get('name','')}</a>"
                          f"<span style='font-size:12px;color:#6b7280;'> · {cert.get('duration','')}</span>"
                          f"</div>")

    all_links_html = ""
    if proj_links_all:
        items = "".join(
            f"<div style='margin-bottom:6px;'><a href='{lnk}' target='_blank' style='color:#059669;font-size:12px;font-weight:600;'>&#128279; Project {i+1}</a></div>"
            for i, lnk in enumerate(proj_links_all)
        )
        all_links_html = items

    fixed_img = _fix_img(profile_img_html)
    job_title_val = session_state.get('job_title','') or session_state.get('title','')
    summary_html = _fmt_desc(session_state.get('summary',''), font_size='13px', color='#374151', line_height='1.8')

    def side_sec(title, body):
        return f"""<div style='margin-bottom:22px;'>
            <h3 style='font-size:11px;letter-spacing:2px;text-transform:uppercase;color:#059669;font-weight:700;
                border-bottom:2px solid #a7f3d0;padding-bottom:4px;margin-bottom:10px;'>{title}</h3>{body}</div>"""

    def main_sec(title, body):
        return f"""<div style='margin-bottom:26px;'>
            <h3 style='font-size:13px;letter-spacing:1.5px;text-transform:uppercase;color:#064e3b;font-weight:700;
                border-bottom:2px solid #059669;padding-bottom:4px;margin-bottom:12px;'>{title}</h3>{body}</div>"""

    return f"""<!DOCTYPE html>
<html lang='en'>
<head><meta charset='UTF-8'><title>{session_state.get('name','')} - Creative Resume</title>
<style>* {{ box-sizing:border-box; margin:0; padding:0; }} body {{ font-family:'Segoe UI',sans-serif; background:#f0fdf4; }}</style>
</head>
<body>
<table role='presentation' style='width:100%;min-height:100vh;border-collapse:collapse;table-layout:fixed;'>
<tr>
  <td style='width:280px;background:#fff;border-right:2px solid #a7f3d0;padding:32px 22px;vertical-align:top;'>
    {'<div style="margin:0 auto 14px;text-align:center;">' + fixed_img + '</div>' if fixed_img else ''}
    <h1 style='font-size:20px;font-weight:800;color:#064e3b;text-align:center;margin-bottom:4px;'>{session_state.get('name','')}</h1>
    <div style='font-size:13px;color:#059669;text-align:center;font-weight:700;margin-bottom:22px;'>{job_title_val}</div>
    {side_sec("Contact", contact_html)}
    {side_sec("Skills", pills(session_state.get('skills',''))) if session_state.get('skills') else ''}
    {side_sec("Soft Skills", pills(session_state.get('Softskills',''),'#ede9fe','#5b21b6')) if session_state.get('Softskills') else ''}
    {side_sec("Languages", pills(session_state.get('languages',''),'#fef3c7','#92400e')) if session_state.get('languages') else ''}
    {side_sec("Interests", pills(session_state.get('interests',''),'#fce7f3','#9d174d')) if session_state.get('interests') else ''}
    {side_sec("Certifications", cert_html) if cert_html else ''}
    {side_sec("Project Links", all_links_html) if all_links_html else ''}
  </td>
  <td style='padding:36px 40px;background:#f0fdf4;vertical-align:top;'>
    {main_sec("About Me", summary_html) if summary_html else ''}
    {main_sec("Experience", exp_html) if exp_html else ''}
    {main_sec("Education", edu_html) if edu_html else ''}
    {main_sec("Projects", proj_html) if proj_html else ''}
  </td>
</tr>
</table>
</body></html>"""


def render_template_terracotta(session_state, profile_img_html=""):
    """Warm Terracotta Two-Column — ATS-friendly, warm professional tones"""
    import re as _re

    def _fix_img(html, size=105):
        if not html:
            return ""
        img_match = _re.search(r'<img[^>]*>', html)
        if not img_match:
            return ""
        img_tag = img_match.group(0)
        img_tag = _re.sub(r"style=['\"][^\'\"]*['\"]", "", img_tag)
        img_tag = img_tag.replace("<img ", f"<img style='width:{size}px;height:{size}px;border-radius:50%;object-fit:cover;object-position:center;border:3px solid #fde68a;display:block;margin:0 auto;' ")
        return img_tag

    def chip(s, bg="#fef3c7", color="#78350f"):
        return (f"<span style='display:inline-block;background:{bg};color:{color};border-radius:3px;"
                f"padding:3px 10px;margin:3px 3px 3px 0;font-size:12px;font-weight:600;border:1px solid {bg};'>{s.strip()}</span>")

    def chips(items_str, bg="#fef3c7", color="#78350f"):
        return "".join(chip(s, bg, color) for s in items_str.split(',') if s.strip())

    exp_html = ""
    for exp in session_state.experience_entries:
        if exp.get('company') or exp.get('title'):
            desc = _fmt_desc(exp.get('description',''), font_size='13px', color='#374151', line_height='1.75')
            exp_html += f"""
            <div style='margin-bottom:18px;border-left:3px solid #d97706;padding-left:14px;'>
                <div style='display:flex;justify-content:space-between;flex-wrap:wrap;gap:5px;'>
                    <strong style='font-size:15px;color:#292524;'>{exp.get('company','')}</strong>
                    <span style='font-size:12px;color:#a8a29e;background:#fafaf9;padding:2px 8px;border-radius:4px;'>{exp.get('duration','')}</span>
                </div>
                <div style='font-size:13px;color:#b45309;font-weight:700;margin:3px 0 5px;'>{exp.get('title','')}</div>
                <div style='font-size:13px;color:#44403c;line-height:1.7;'>{desc}</div>
            </div>"""

    edu_html = ""
    for edu in session_state.education_entries:
        if edu.get('institution'):
            degree_val = edu.get('degree','')
            if isinstance(degree_val,list): degree_val = ", ".join(degree_val)
            edu_html += f"""
            <div style='margin-bottom:14px;padding:10px;background:#fafaf9;border-radius:6px;border:1px solid #e7e5e4;border-left:3px solid #d97706;'>
                <div style='display:flex;justify-content:space-between;'>
                    <strong style='font-size:14px;color:#292524;'>{edu.get('institution','')}</strong>
                    <span style='font-size:12px;color:#a8a29e;'>{edu.get('year','')}</span>
                </div>
                <div style='font-size:13px;color:#b45309;font-style:italic;font-weight:600;'>{degree_val}</div>
                <div style='font-size:12px;color:#78716c;'>{edu.get('details','')}</div>
            </div>"""

    proj_html = ""
    proj_links_all = getattr(session_state, 'project_links', []) or []
    for idx, proj in enumerate(session_state.project_entries):
        if proj.get('title'):
            desc = _fmt_desc(proj.get('description',''), font_size='13px', color='#374151', line_height='1.75')
            proj_link_html = ""
            if idx < len(proj_links_all) and proj_links_all[idx]:
                proj_link_html = f"<div style='margin-top:5px;'><a href='{proj_links_all[idx]}' target='_blank' style='color:#b45309;font-size:12px;font-weight:600;'>&#128279; View Project / GitHub</a></div>"
            proj_html += f"""
            <div style='margin-bottom:14px;padding:12px;background:#fafaf9;border-radius:6px;border:1px solid #d6d3d1;border-left:3px solid #d97706;'>
                <div style='display:flex;justify-content:space-between;flex-wrap:wrap;gap:4px;'>
                    <strong style='font-size:14px;color:#292524;'>{proj.get('title','')}</strong>
                    <span style='font-size:12px;color:#a8a29e;'>{proj.get('duration','')}</span>
                </div>
                <div style='font-size:12px;color:#b45309;font-weight:600;margin-bottom:4px;'>{proj.get('tech','')}</div>
                <div style='font-size:13px;color:#44403c;'>{desc}</div>
                {proj_link_html}
            </div>"""

    contact_html = ""
    SVG_ICONS = {
        'email': '<svg xmlns="http://www.w3.org/2000/svg" width="13" height="13" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M4 4h16c1.1 0 2 .9 2 2v12c0 1.1-.9 2-2 2H4c-1.1 0-2-.9-2-2V6c0-1.1.9-2 2-2z"/><polyline points="22,6 12,13 2,6"/></svg>',
        'phone': '<svg xmlns="http://www.w3.org/2000/svg" width="13" height="13" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M22 16.92v3a2 2 0 0 1-2.18 2 19.79 19.79 0 0 1-8.63-3.07A19.5 19.5 0 0 1 4.69 12 19.79 19.79 0 0 1 1.65 3.37 2 2 0 0 1 3.64 1h3a2 2 0 0 1 2 1.72c.127.96.361 1.903.7 2.81a2 2 0 0 1-.45 2.11L7.91 8.8a16 16 0 0 0 6.29 6.29l.98-.98a2 2 0 0 1 2.11-.45c.907.339 1.85.573 2.81.7A2 2 0 0 1 22 16.92z"/></svg>',
        'location': '<svg xmlns="http://www.w3.org/2000/svg" width="13" height="13" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M21 10c0 7-9 13-9 13s-9-6-9-13a9 9 0 0 1 18 0z"/><circle cx="12" cy="10" r="3"/></svg>',
        'linkedin': '<svg xmlns="http://www.w3.org/2000/svg" width="13" height="13" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M16 8a6 6 0 0 1 6 6v7h-4v-7a2 2 0 0 0-2-2 2 2 0 0 0-2 2v7h-4v-7a6 6 0 0 1 6-6z"/><rect x="2" y="9" width="4" height="12"/><circle cx="4" cy="4" r="2"/></svg>',
        'portfolio': '<svg xmlns="http://www.w3.org/2000/svg" width="13" height="13" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><circle cx="12" cy="12" r="10"/><line x1="2" y1="12" x2="22" y2="12"/><path d="M12 2a15.3 15.3 0 0 1 4 10 15.3 15.3 0 0 1-4 10 15.3 15.3 0 0 1-4-10 15.3 15.3 0 0 1 4-10z"/></svg>',
        'github': '<svg xmlns="http://www.w3.org/2000/svg" width="13" height="13" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M9 19c-5 1.5-5-2.5-7-3m14 6v-3.87a3.37 3.37 0 0 0-.94-2.61c3.14-.35 6.44-1.54 6.44-7A5.44 5.44 0 0 0 20 4.77 5.07 5.07 0 0 0 19.91 1S18.73.65 16 2.48a13.38 13.38 0 0 0-7 0C6.27.65 5.09 1 5.09 1A5.07 5.07 0 0 0 5 4.77a5.44 5.44 0 0 0-1.5 3.78c0 5.42 3.3 6.61 6.44 7A3.37 3.37 0 0 0 9 18.13V22"/></svg>'
    }
    for key in ['email','phone','location','linkedin','portfolio','github']:
        val = session_state.get(key,'')
        if val:
            if key == 'email':
                val_html = f"<a href='mailto:{val}' style='color:#fde68a;text-decoration:none;word-break:break-all;'>{val}</a>"
            elif key in ('linkedin', 'portfolio', 'github'):
                href = val if val.startswith('http') else f"https://{val}"
                val_html = f"<a href='{href}' target='_blank' style='color:#fde68a;text-decoration:none;word-break:break-all;'>{val}</a>"
            else:
                val_html = f"<span style='word-break:break-all;'>{val}</span>"
            contact_html += f"<div style='margin-bottom:9px;font-size:12px;color:#e7e5e4;display:flex;align-items:center;gap:5px;'><span style='flex-shrink:0;'>{SVG_ICONS[key]}</span>{val_html}</div>"

    cert_html = ""
    for cert in session_state.certificate_links:
        if cert.get('name'):
            cert_html += f"<div style='margin-bottom:9px;padding:8px;background:rgba(255,255,255,0.1);border-radius:5px;'><a href='{cert.get('link','#')}' style='color:#fde68a;font-size:12px;font-weight:600;text-decoration:none;'>{cert.get('name','')}</a><div style='font-size:11px;color:#d4b896;'>{cert.get('duration','')}</div></div>"

    all_links_html = ""
    if proj_links_all:
        items = "".join(
            f"<div style='margin-bottom:6px;'><a href='{lnk}' target='_blank' style='color:#fde68a;font-size:12px;font-weight:600;'>&#128279; Project {i+1}</a></div>"
            for i, lnk in enumerate(proj_links_all)
        )
        all_links_html = items

    fixed_img = _fix_img(profile_img_html)
    job_title_val = session_state.get('job_title','') or session_state.get('title','')
    summary_html = _fmt_desc(session_state.get('summary',''), font_size='13px', color='#374151', line_height='1.8')

    def side_sec(title, body):
        return f"""<div style='margin-bottom:22px;'>
            <h3 style='font-size:11px;letter-spacing:2.5px;text-transform:uppercase;color:#fde68a;font-weight:700;
                border-bottom:1px solid rgba(253,230,138,0.3);padding-bottom:5px;margin-bottom:10px;'>{title}</h3>{body}</div>"""

    def main_sec(title, body):
        return f"""<div style='margin-bottom:26px;'>
            <h3 style='font-size:13px;letter-spacing:1.5px;text-transform:uppercase;color:#b45309;font-weight:700;
                border-bottom:2px solid #d97706;padding-bottom:4px;margin-bottom:12px;'>{title}</h3>{body}</div>"""

    return f"""<!DOCTYPE html>
<html lang='en'>
<head><meta charset='UTF-8'><title>{session_state.get('name','')} - Terracotta Resume</title>
<style>* {{ box-sizing:border-box; margin:0; padding:0; }} body {{ font-family:'Segoe UI',sans-serif; background:#fafaf9; }}</style>
</head>
<body>
<table role='presentation' style='width:100%;min-height:100vh;border-collapse:collapse;table-layout:fixed;'>
<tr>
  <td style='width:290px;background:linear-gradient(180deg,#7c2d12,#b45309);color:white;padding:34px 22px;vertical-align:top;'>
    {'<div style="margin:0 auto 14px;text-align:center;">' + fixed_img + '</div>' if fixed_img else ''}
    <h1 style='font-size:20px;font-weight:800;color:#fff;text-align:center;margin-bottom:4px;letter-spacing:-0.3px;'>{session_state.get('name','')}</h1>
    <div style='font-size:13px;color:#fde68a;text-align:center;font-weight:700;margin-bottom:24px;'>{job_title_val}</div>
    {side_sec("Contact", contact_html)}
    {side_sec("Skills", chips(session_state.get('skills',''),'rgba(253,230,138,0.2)','#fef3c7')) if session_state.get('skills') else ''}
    {side_sec("Soft Skills", chips(session_state.get('Softskills',''),'rgba(255,255,255,0.1)','#f3f4f6')) if session_state.get('Softskills') else ''}
    {side_sec("Languages", chips(session_state.get('languages',''),'rgba(255,255,255,0.1)','#e0f2fe')) if session_state.get('languages') else ''}
    {side_sec("Interests", chips(session_state.get('interests',''),'rgba(255,255,255,0.1)','#fce7f3')) if session_state.get('interests') else ''}
    {side_sec("Certifications", cert_html) if cert_html else ''}
    {side_sec("Project Links", all_links_html) if all_links_html else ''}
  </td>
  <td style='padding:38px 42px;background:#fafaf9;vertical-align:top;'>
    {main_sec("Professional Summary", summary_html) if summary_html else ''}
    {main_sec("Work Experience", exp_html) if exp_html else ''}
    {main_sec("Education", edu_html) if edu_html else ''}
    {main_sec("Projects", proj_html) if proj_html else ''}
  </td>
</tr>
</table>
</body></html>"""


def generate_cover_letter_from_resume_builder():
    import streamlit as st
    from datetime import datetime
    import re
    from llm_manager import call_llm  # Ensure you import this

    name = st.session_state.get("name", "")
    job_title = st.session_state.get("job_title", "")
    summary = st.session_state.get("summary", "")
    skills = st.session_state.get("skills", "")
    location = st.session_state.get("location", "")
    today_date = datetime.today().strftime("%B %d, %Y")

    # ✅ Input boxes for contact info
    company = st.text_input("🏢 Target Company", placeholder="e.g., Google")
    linkedin = st.text_input("🔗 LinkedIn URL", placeholder="e.g., https://linkedin.com/in/username")
    email = st.text_input("📧 Email", placeholder="e.g., you@example.com")
    mobile = st.text_input("📞 Mobile Number", placeholder="e.g., +91 9876543210")

    # ✅ Button to prevent relooping
    if st.button("✉️ Generate Cover Letter"):
        # ✅ Validate input before generating
        if not all([name, job_title, summary, skills, company, linkedin, email, mobile]):
            st.warning("⚠️ Please fill in all fields including LinkedIn, email, and mobile.")
            return

        prompt = f"""
You are a professional cover letter writer.

Write a formal and compelling cover letter using the information below. 
Format it as a real letter with:
1. Date
2. Recipient heading
3. Proper salutation
4. Three short paragraphs
5. Professional closing

Ensure you **only include the company name once** in the header or salutation, 
and avoid repeating it redundantly in the body.

### Heading Info:
{today_date}
Hiring Manager, {company}, {location}

### Candidate Info:
- Name: {name}
- Job Title: {job_title}
- Summary: {summary}
- Skills: {skills}
- Location: {location}

### Instructions:
- Do not use HTML tags. 
- Return plain text only.
"""

        # ✅ Call LLM
        cover_letter = call_llm(prompt, session=st.session_state).strip()

        # ✅ Store plain text
        st.session_state["cover_letter"] = cover_letter

        # ✅ Build HTML wrapper for preview (safe)
        cover_letter_html = f"""
        <div style="font-family: Georgia, serif; font-size: 13pt; line-height: 1.6; 
                    color: #000; background: #fff; padding: 25px; 
                    border-radius: 8px; box-shadow: 0px 2px 6px rgba(0,0,0,0.1); 
                    max-width: 800px; margin: auto;">
            <div style="text-align:center; margin-bottom:15px;">
                <div style="font-size:18pt; font-weight:bold; color:#003366;">{name}</div>
                <div style="font-size:14pt; color:#555;">{job_title}</div>
                <div style="font-size:10pt; margin-top:5px;">
                    <a href="{linkedin}" style="color:#003366;">{linkedin}</a><br/>
                    📧 {email} | 📞 {mobile}
                </div>
            </div>
            <hr/>
            <pre style="white-space: pre-wrap; font-family: Georgia, serif; font-size: 12pt; color:#000;">
{cover_letter}
            </pre>
        </div>
        """

        st.session_state["cover_letter_html"] = cover_letter_html

        # ✅ Show nicely in Streamlit
        st.markdown(cover_letter_html, unsafe_allow_html=True)

# Import necessary modules first
import streamlit as st

# Tab setup (assuming this is within a tab2 context)
with tab2:
    st.session_state.active_tab = "Resume Builder"

    # ---------- Title with Blue Glassmorphism + Shine ----------
    st.markdown("""
    <style>
    .glass-title {
        background: rgba(10, 20, 40, 0.5);
        border-radius: 20px;
        padding: 20px;
        backdrop-filter: blur(14px);
        box-shadow: 0 8px 32px rgba(0, 200, 255, 0.25);
        border: 1px solid rgba(0, 200, 255, 0.3);
        text-align: center;
        position: relative;
        overflow: hidden;
    }
    .glass-title h2 {
        color: #4da6ff;
        margin: 0;
        text-shadow: 0 0 12px rgba(0,200,255,0.7);
        font-weight: 600;
    }
    .glass-title::before {
        content: "";
        position: absolute;
        top: -50%;
        left: -50%;
        width: 200%;
        height: 200%;
        background: linear-gradient(
            120deg,
            rgba(255,255,255,0.18) 0%,
            rgba(255,255,255,0.05) 40%,
            transparent 60%
        );
        transform: rotate(25deg);
        transition: all 0.6s;
    }
    .glass-title:hover::before {
        left: 100%;
        top: 100%;
    }
    </style>

    <div class="glass-title">
        <h2>🧾 Advanced Resume Builder</h2>
    </div>
    """, unsafe_allow_html=True)

    st.markdown("<hr style='border-top: 2px solid rgba(0,200,255,0.4);'>", unsafe_allow_html=True)

    # ---------- Global Styles (Glassmorphism + Glow + Shine) ----------
    st.markdown("""
        <style>
        /* File uploader */
        .uploadedFile { 
            background: rgba(10, 20, 40, 0.6) !important;
            border: 1px solid rgba(0,200,255,0.5) !important;
            border-radius: 14px !important;
            color: #cce6ff !important;
            box-shadow: 0 0 12px rgba(0,200,255,0.3) !important;
        }

        /* Sidebar expander style */
        .streamlit-expanderHeader {
            background: rgba(10, 20, 40, 0.45);
            border-radius: 12px;
            color: #4da6ff !important;
            font-weight: bold;
            backdrop-filter: blur(12px);
            box-shadow: 0 4px 12px rgba(0,200,255,0.25);
            transition: all 0.3s ease-in-out;
        }
        .streamlit-expanderHeader:hover {
            background: rgba(0, 200, 255, 0.12);
            box-shadow: 0 0 16px rgba(0,200,255,0.4);
        }
        .streamlit-expanderContent {
            background: rgba(10, 20, 40, 0.45);
            border-radius: 10px;
            padding: 8px;
            color: #e6f7ff;
        }

        /* Selectbox */
        div[data-baseweb="select"] {
            background: rgba(10, 20, 40, 0.35);
            border: 1px solid rgba(0, 200, 255, 0.6);
            border-radius: 12px;
            color: #e6f7ff;
            backdrop-filter: blur(14px);
            box-shadow: 0 0 10px rgba(0,200,255,0.3);
        }

        /* Buttons with Shine Effect */
        div.stButton > button {
            position: relative;
            background: rgba(10, 20, 40, 0.35);
            border: 1px solid rgba(0, 200, 255, 0.6);
            color: #e6f7ff;
            border-radius: 14px;
            padding: 10px 20px;
            font-size: 15px;
            font-weight: 500;
            backdrop-filter: blur(16px);
            box-shadow: 0 0 12px rgba(0, 200, 255, 0.35),
                        inset 0 0 20px rgba(0, 200, 255, 0.05);
            overflow: hidden;
            transition: all 0.3s ease-in-out;
        }
        div.stButton > button::before {
            content: "";
            position: absolute;
            top: -50%;
            left: -50%;
            width: 200%;
            height: 200%;
            background: linear-gradient(
                120deg,
                rgba(255,255,255,0.15) 0%,
                rgba(255,255,255,0.05) 40%,
                transparent 60%
            );
            transform: rotate(25deg);
            transition: all 0.6s;
        }
        div.stButton > button:hover::before {
            left: 100%;
            top: 100%;
        }
        div.stButton > button:hover {
            background: rgba(0, 200, 255, 0.12);
            box-shadow: 0 0 20px rgba(0, 200, 255, 0.65),
                        inset 0 0 25px rgba(0, 200, 255, 0.15);
            transform: translateY(-2px);
        }
        div.stButton > button:active {
            transform: scale(0.95);
            box-shadow: 0 0 10px rgba(0, 200, 255, 0.45);
        }
        </style>
    """, unsafe_allow_html=True)

    # 🎨 Template Selection
    st.markdown("### 🎨 Choose Resume Template")
    selected_template = st.selectbox(
        "🎨 Choose Resume Template",
        [
            "Default (Professional)",
            "Modern Minimal",
            "Elegant Sidebar",
            "Classic Clean (Single Column)",
            "Executive (Single Column)",
            "Timeline (Single Column)",
            "Corporate Blue (Two Column)",
            "Creative Green (Two Column)",
            "Warm Terracotta (Two Column)",
        ],
        key="template_selector"
    )

    # 📸 Upload profile photo
    uploaded_image = st.file_uploader("Upload a Profile Image", type=["png", "jpg", "jpeg"], key="profile_img_upload")
    profile_img_html = ""

    if uploaded_image:
        import base64
        encoded_image = base64.b64encode(uploaded_image.read()).decode()
        st.session_state["encoded_profile_image"] = encoded_image

        profile_img_html = f"""
        <div style="display: flex; justify-content: flex-end; margin-top: 20px;">
            <img src="data:image/png;base64,{encoded_image}" alt="Profile Photo"
                 style="
                    width: 140px;
                    height: 140px;
                    border-radius: 50%;
                    object-fit: cover;
                    object-position: center;
                    border: 4px solid rgba(255,255,255,0.6);
                    box-shadow:
                        0 0 0 3px #4da6ff,
                        0 8px 25px rgba(77, 166, 255, 0.3),
                        0 4px 15px rgba(0, 0, 0, 0.15);
                    transition: transform 0.3s ease-in-out;
                "
                onmouseover="this.style.transform='scale(1.07)'"
                onmouseout="this.style.transform='scale(1)'"
             />
        </div>
        """
        st.markdown(profile_img_html, unsafe_allow_html=True)
    else:
        st.info("📸 Please upload a clear, front-facing profile photo (square or vertical preferred).")

    # ---------------- Session State Defaults ----------------
    fields = ["name", "email", "phone", "linkedin", "location", "portfolio", "summary",
              "skills", "languages", "interests", "Softskills", "job_title"]
    for f in fields:
        st.session_state.setdefault(f, "")

    st.session_state.setdefault("experience_entries", [{"title": "", "company": "", "duration": "", "description": ""}])
    st.session_state.setdefault("education_entries", [{"degree": "", "institution": "", "year": "", "details": ""}])
    st.session_state.setdefault("project_entries", [{"title": "", "tech": "", "duration": "", "description": ""}])
    st.session_state.setdefault("project_links", [])
    st.session_state.setdefault("certificate_links", [{"name": "", "link": "", "duration": "", "description": ""}])
    st.session_state.setdefault("form_key_counter", 0)

    # ---------------- Sidebar (ONLY in Tab 2) ----------------
    with st.sidebar:
        st.markdown("### ✨ Manage Resume Sections")

        if "edit_mode" not in st.session_state:
            st.session_state.edit_mode = "Add"

        mode = st.selectbox("Mode", ["Add", "Delete"], index=0, key="mode_dropdown")
        st.session_state.edit_mode = mode
        st.markdown("---")

        # 💼 Experience
        with st.expander("💼 Experience"):
            if st.button(f"{'➕ Add' if mode=='Add' else '❌ Delete'} Experience", key="exp_btn"):
                if mode == "Add":
                    st.session_state.experience_entries.append(
                        {"title": "", "company": "", "duration": "", "description": ""}
                    )
                elif mode == "Delete" and len(st.session_state.experience_entries) > 1:
                    st.session_state.experience_entries.pop()

        # 🎓 Education
        with st.expander("🎓 Education"):
            if st.button(f"{'➕ Add' if mode=='Add' else '❌ Delete'} Education", key="edu_btn"):
                if mode == "Add":
                    st.session_state.education_entries.append(
                        {"degree": "", "institution": "", "year": "", "details": ""}
                    )
                elif mode == "Delete" and len(st.session_state.education_entries) > 1:
                    st.session_state.education_entries.pop()

        # 🛠 Projects
        with st.expander("🛠 Projects"):
            if st.button(f"{'➕ Add' if mode=='Add' else '❌ Delete'} Project", key="proj_btn"):
                if mode == "Add":
                    st.session_state.project_entries.append(
                        {"title": "", "tech": "", "duration": "", "description": ""}
                    )
                elif mode == "Delete" and len(st.session_state.project_entries) > 1:
                    st.session_state.project_entries.pop()

        # 📜 Certificates
        with st.expander("📜 Certificates"):
            if st.button(f"{'➕ Add' if mode=='Add' else '❌ Delete'} Certificate", key="cert_btn"):
                if mode == "Add":
                    st.session_state.certificate_links.append(
                        {"name": "", "link": "", "duration": "", "description": ""}
                    )
                elif mode == "Delete" and len(st.session_state.certificate_links) > 1:
                    st.session_state.certificate_links.pop()

    # ---------------- Resume Form ----------------
    fk = st.session_state["form_key_counter"]
    with st.form(f"resume_form_{fk}", clear_on_submit=False):
        st.markdown("### 👤 <u>Personal Information</u>", unsafe_allow_html=True)
        col1, col2 = st.columns(2)
        with col1:
            st.session_state.name = st.text_input("👤 Full Name", value=st.session_state.name, key=f"name_input_{fk}")
            st.session_state.phone = st.text_input("📞 Phone Number", value=st.session_state.phone, key=f"phone_input_{fk}")
            st.session_state.location = st.text_input("📍 Location", value=st.session_state.location, key=f"loc_input_{fk}")
        with col2:
            st.session_state.email = st.text_input("📧 Email", value=st.session_state.email, key=f"email_input_{fk}")
            st.session_state.linkedin = st.text_input("🔗 LinkedIn", value=st.session_state.linkedin, key=f"ln_input_{fk}")
            st.session_state.portfolio = st.text_input("🌐 Portfolio", value=st.session_state.portfolio, key=f"port_input_{fk}")
            st.session_state.job_title = st.text_input("💼 Job Title", value=st.session_state.job_title, key=f"job_input_{fk}")

        st.markdown("### 📝 <u>Professional Summary</u>", unsafe_allow_html=True)
        st.session_state.summary = st.text_area("Summary", value=st.session_state.summary, key=f"summary_input_{fk}")

        st.markdown("### 💼 <u>Skills, Languages, Interests & Soft Skills</u>", unsafe_allow_html=True)
        st.session_state.skills = st.text_area("Skills (comma-separated)", value=st.session_state.skills, key=f"skills_input_{fk}")
        st.session_state.languages = st.text_area("Languages (comma-separated)", value=st.session_state.languages, key=f"lang_input_{fk}")
        st.session_state.interests = st.text_area("Interests (comma-separated)", value=st.session_state.interests, key=f"int_input_{fk}")
        st.session_state.Softskills = st.text_area("Softskills (comma-separated)", value=st.session_state.Softskills, key=f"soft_input_{fk}")

        st.markdown("### 🧱 <u>Work Experience</u>", unsafe_allow_html=True)
        for idx, exp in enumerate(st.session_state.experience_entries):
            with st.expander(f"Experience #{idx+1}", expanded=True):
                exp["title"] = st.text_input("Job Title", value=exp.get("title", ""), key=f"title_{idx}_{len(st.session_state.experience_entries)}_{fk}")
                exp["company"] = st.text_input("Company", value=exp.get("company", ""), key=f"company_{idx}_{len(st.session_state.experience_entries)}_{fk}")
                exp["duration"] = st.text_input("Duration", value=exp.get("duration", ""), key=f"duration_{idx}_{len(st.session_state.experience_entries)}_{fk}")
                exp["description"] = st.text_area("Description", value=exp.get("description", ""), key=f"description_{idx}_{len(st.session_state.experience_entries)}_{fk}")

        st.markdown("### 🎓 <u>Education</u>", unsafe_allow_html=True)
        for idx, edu in enumerate(st.session_state.education_entries):
            with st.expander(f"Education #{idx+1}", expanded=True):
                edu["degree"] = st.text_input("Degree", value=edu.get("degree", ""), key=f"degree_{idx}_{len(st.session_state.education_entries)}_{fk}")
                edu["institution"] = st.text_input("Institution", value=edu.get("institution", ""), key=f"institution_{idx}_{len(st.session_state.education_entries)}_{fk}")
                edu["year"] = st.text_input("Year", value=edu.get("year", ""), key=f"edu_year_{idx}_{len(st.session_state.education_entries)}_{fk}")
                edu["details"] = st.text_area("Details", value=edu.get("details", ""), key=f"edu_details_{idx}_{len(st.session_state.education_entries)}_{fk}")

        st.markdown("### 🛠 <u>Projects</u>", unsafe_allow_html=True)
        for idx, proj in enumerate(st.session_state.project_entries):
            with st.expander(f"Project #{idx+1}", expanded=True):
                proj["title"] = st.text_input("Project Title", value=proj.get("title", ""), key=f"proj_title_{idx}_{len(st.session_state.project_entries)}_{fk}")
                proj["tech"] = st.text_input("Tech Stack", value=proj.get("tech", ""), key=f"proj_tech_{idx}_{len(st.session_state.project_entries)}_{fk}")
                proj["duration"] = st.text_input("Duration", value=proj.get("duration", ""), key=f"proj_duration_{idx}_{len(st.session_state.project_entries)}_{fk}")
                proj["description"] = st.text_area("Description", value=proj.get("description", ""), key=f"proj_desc_{idx}_{len(st.session_state.project_entries)}_{fk}")

        st.markdown("### 🔗 Project Links")
        project_links_input = st.text_area("Enter one project link per line:", value="\n".join(st.session_state.project_links), key=f"proj_links_input_{fk}")
        if project_links_input:
            st.session_state.project_links = [link.strip() for link in project_links_input.splitlines() if link.strip()]

        st.markdown("### 🧾 <u>Certificates</u>", unsafe_allow_html=True)
        for idx, cert in enumerate(st.session_state.certificate_links):
            with st.expander(f"Certificate #{idx+1}", expanded=True):
                cert["name"] = st.text_input("Certificate Name", value=cert.get("name", ""), key=f"cert_name_{idx}_{len(st.session_state.certificate_links)}_{fk}")
                cert["link"] = st.text_input("Certificate Link", value=cert.get("link", ""), key=f"cert_link_{idx}_{len(st.session_state.certificate_links)}_{fk}")
                cert["duration"] = st.text_input("Duration", value=cert.get("duration", ""), key=f"cert_duration_{idx}_{len(st.session_state.certificate_links)}_{fk}")
                cert["description"] = st.text_area("Description", value=cert.get("description", ""), key=f"cert_description_{idx}_{len(st.session_state.certificate_links)}_{fk}")

        btn_col1, btn_col2 = st.columns([1, 1])
        with btn_col1:
            submitted = st.form_submit_button("📑 Generate Resume", use_container_width=True)
        with btn_col2:
            clear_clicked = st.form_submit_button("🗑️ Clear Form", use_container_width=True)

        if submitted:
            st.success("✅ Resume Generated Successfully! Scroll down to preview or download.")

        if clear_clicked:
            # Reset only resume-related keys — do NOT clear() or rerun() as that
            # wipes tab context and navigates back to the main/home page.
            # Instead, reset values in-place and bump the form key counter so
            # all widgets re-render empty on this same run, no page jump.
            _new_counter = st.session_state.get("form_key_counter", 0) + 1
            resume_fields = ["name", "email", "phone", "linkedin", "location",
                             "portfolio", "summary", "skills", "languages",
                             "interests", "Softskills", "job_title"]
            for _f in resume_fields:
                st.session_state[_f] = ""
            st.session_state["experience_entries"] = [{"title": "", "company": "", "duration": "", "description": ""}]
            st.session_state["education_entries"] = [{"degree": "", "institution": "", "year": "", "details": ""}]
            st.session_state["project_entries"] = [{"title": "", "tech": "", "duration": "", "description": ""}]
            st.session_state["project_links"] = []
            st.session_state["certificate_links"] = [{"name": "", "link": "", "duration": "", "description": ""}]
            for _key in ["generated_html", "ai_output", "cover_letter",
                         "cover_letter_html", "encoded_profile_image"]:
                st.session_state.pop(_key, None)
            st.session_state["form_key_counter"] = _new_counter

    st.markdown("""
    <style>
        .heading-large {
            font-size: 36px;
            font-weight: bold;
            color: #336699;
        }
        .subheading-large {
            font-size: 30px;
            font-weight: bold;
            color: #336699;
        }
        .tab-section {
            margin-top: 20px;
        }
    </style>
    """, unsafe_allow_html=True)

    # --- Visual Resume Preview Section (only shown after form is submitted) ---
    if "generated_html" in st.session_state:
        st.markdown("## 🧾 <span style='color:#336699;'>Resume Preview</span>", unsafe_allow_html=True)
        st.markdown("<hr style='border-top: 2px solid #bbb;'>", unsafe_allow_html=True)

        left, right = st.columns([1, 2])

        with left:
            st.markdown(f"""
                <h2 style='color:#2f2f2f;margin-bottom:0;'>{st.session_state['name']}</h2>
                <h4 style='margin-top:5px;color:#444;'>{st.session_state['job_title']}</h4>
                <p style='font-size:14px;'>
                📍 {st.session_state['location']}<br>
                📞 {st.session_state['phone']}<br>
                📧 <a href="mailto:{st.session_state['email']}">{st.session_state['email']}</a><br>
                🔗 <a href="{st.session_state['linkedin']}" target="_blank">LinkedIn</a><br>
                🌐 <a href="{st.session_state['portfolio']}" target="_blank">Portfolio</a>
                </p>
            """, unsafe_allow_html=True)

            st.markdown("<h4 style='color:#336699;'>Skills</h4><hr style='margin-top:-10px;'>", unsafe_allow_html=True)
            for skill in [s.strip() for s in st.session_state["skills"].split(",") if s.strip()]:
                st.markdown(f"<div style='margin-left:10px;'>• {skill}</div>", unsafe_allow_html=True)

            st.markdown("<h4 style='color:#336699;'>Languages</h4><hr style='margin-top:-10px;'>", unsafe_allow_html=True)
            for lang in [l.strip() for l in st.session_state["languages"].split(",") if l.strip()]:
                st.markdown(f"<div style='margin-left:10px;'>• {lang}</div>", unsafe_allow_html=True)

            st.markdown("<h4 style='color:#336699;'>Interests</h4><hr style='margin-top:-10px;'>", unsafe_allow_html=True)
            for interest in [i.strip() for i in st.session_state["interests"].split(",") if i.strip()]:
                st.markdown(f"<div style='margin-left:10px;'>• {interest}</div>", unsafe_allow_html=True)

            st.markdown("<h4 style='color:#336699;'>Softskills</h4><hr style='margin-top:-10px;'>", unsafe_allow_html=True)
            for ss in [i.strip() for i in st.session_state["Softskills"].split(",") if i.strip()]:
                st.markdown(f"<div style='margin-left:10px;'>• {ss}</div>", unsafe_allow_html=True)

        with right:
            st.markdown("<h4 style='color:#336699;'>Summary</h4><hr style='margin-top:-10px;'>", unsafe_allow_html=True)
            summary_text = st.session_state["summary"].replace("\n", "<br>")
            st.markdown(f"<p style='font-size:17px;'>{summary_text}</p>", unsafe_allow_html=True)

            st.markdown("<h4 style='color:#336699;'>Experience</h4><hr style='margin-top:-10px;'>", unsafe_allow_html=True)
            for exp in st.session_state.experience_entries:
                if exp["company"] or exp["title"]:
                    st.markdown(f"""
                    <div style='margin-bottom:15px; padding:10px; border-radius:8px;'>
                        <div style='display:flex; justify-content:space-between;'>
                            <b>🏢 {exp['company']}</b><span style='color:gray;'>📆 {exp['duration']}</span>
                        </div>
                        <div style='font-size:14px;'>💼 <i>{exp['title']}</i></div>
                        <div style='font-size:17px;'>📝 {exp['description']}</div>
                    </div>
                    """, unsafe_allow_html=True)

            st.markdown("<h4 style='color:#336699;'>🎓 Education</h4><hr style='margin-top:-10px;'>", unsafe_allow_html=True)
            for edu in st.session_state.education_entries:
                if edu["institution"] or edu["degree"]:
                    st.markdown(f"""
                    <div style='margin-bottom:15px; padding:10px 15px; border-radius:8px;'>
                        <div style='display:flex; justify-content:space-between; font-size:16px; font-weight:bold;'>
                            <span>🏫 {edu['institution']}</span>
                            <span style='color:gray;'>📅 {edu['year']}</span>
                        </div>
                        <div style='font-size:14px;'>🎓 <i>{edu['degree']}</i></div>
                        <div style='font-size:14px;'>📄 {edu['details']}</div>
                    </div>
                    """, unsafe_allow_html=True)

            st.markdown("<h4 style='color:#336699;'>Projects</h4><hr style='margin-top:-10px;'>", unsafe_allow_html=True)
            for proj in st.session_state.project_entries:
                if proj.get("title"):
                    st.markdown(f"""
                    <div style='margin-bottom:15px; padding:10px;'>
                        <strong style='font-size:16px;'>{proj['title']}</strong><br>
                        <span style='font-size:14px;'>🛠️ <strong>Tech Stack:</strong> {proj['tech']}</span><br>
                        <span style='font-size:14px;'>⏳ <strong>Duration:</strong> {proj['duration']}</span><br>
                        <span style='font-size:17px;'>📝 <strong>Description:</strong> {proj['description']}</span>
                    </div>
                    """, unsafe_allow_html=True)

            if st.session_state.project_links:
                st.markdown("<h4 style='color:#336699;'>Project Links</h4><hr style='margin-top:-10px;'>", unsafe_allow_html=True)
                for i, link in enumerate(st.session_state.project_links):
                    st.markdown(f"[🔗 Project {i+1}]({link})", unsafe_allow_html=True)

            if st.session_state.certificate_links:
                st.markdown("<h4 style='color:#336699;'>Certificates</h4><hr style='margin-top:-10px;'>", unsafe_allow_html=True)
                for cert in st.session_state.certificate_links:
                    if cert["name"] and cert["link"]:
                        st.markdown(f"""
                        <div style='display:flex; justify-content:space-between;'>
                            <a href="{cert['link']}" target="_blank"><b>📄 {cert['name']}</b></a>
                            <span style='color:gray;'>{cert['duration']}</span>
                        </div>
                        <div style='margin-bottom:10px; font-size:14px;'>{cert['description']}</div>
                        """, unsafe_allow_html=True)

import re

with tab2:
    st.markdown("## ✨ <span style='color:#336699;'>Enhanced AI Resume Preview</span>", unsafe_allow_html=True)
    st.markdown("<hr style='border-top: 2px solid #bbb;'>", unsafe_allow_html=True)

    col1, spacer, col2 = st.columns([1, 0.2, 1])

    with col1:
        if st.button("🔁 Clear Preview"):
            st.session_state.pop("ai_output", None)

    with col2:
        if st.button("🚀 Generate AI Resume Preview"):
            # Normalize and ensure at least 2 experience entries
            experience_entries = st.session_state.get('experience_entries', [])
            normalized_experience_entries = []
            for entry in experience_entries:
                if isinstance(entry, dict):
                    title = entry.get("title", "")
                    desc = entry.get("description", "")
                    formatted = f"{title}\n{desc}".strip()
                else:
                    formatted = entry.strip()
                normalized_experience_entries.append(formatted)
            while len(normalized_experience_entries) < 2:
                normalized_experience_entries.append("Placeholder Experience")

            # Normalize and ensure at least 2 project entries
            project_entries = st.session_state.get('project_entries', [])
            normalized_project_entries = []
            for entry in project_entries:
                if isinstance(entry, dict):
                    title = entry.get("title", "")
                    desc = entry.get("description", "")
                    formatted = f"{title}\n{desc}".strip()
                else:
                    formatted = entry.strip()
                normalized_project_entries.append(formatted)
            while len(normalized_project_entries) < 2:
                normalized_project_entries.append("Placeholder Project")

            enhance_prompt = f"""
            You are a professional and unbiased Resume Optimization Specialist with deep knowledge of ATS systems,
            industry hiring standards, and professional resume writing conventions. Your goal is to enhance the
            provided resume data for the role:
            "{st.session_state['job_title']}" — ensuring strong ATS alignment, linguistic precision, and
            real-world industry relevance.

            ROLE-SPECIFIC INSTRUCTION:
            - Tailor every section strictly toward the competencies, technical skills, and outcomes expected
              for "{st.session_state['job_title']}".
            - Infer the most essential 6–10 role-defining skills, tools, and responsibilities using industry standards.
            - Prioritize factual accuracy, clarity, and hiring relevance over creative or generic rewriting.

            LANGUAGE & TONE GUIDELINES:
            - Maintain neutral, inclusive, and strictly professional tone.
            - Avoid biased, informal, exaggerated, or marketing-style terms (e.g., “rockstar,” “guru,” “ninja”).
            - Use concise, quantifiable, outcome-focused language.
            - Do NOT repeat the same verbs, verb roots, phrases, or semantic actions across different sections.
            - Focus on measurable impact, scope, and responsibility.
            - Avoid subjective adjectives like "excellent" or "great" — prefer evidence-based outcomes.

            ABSOLUTE PRONOUN & VOICE RESTRICTIONS (NON-NEGOTIABLE):
            - NEVER use first-person language under any circumstance (I, me, my, we, our).
            - NEVER use gendered pronouns or possessives
              (he, she, him, her, his, hers, himself, herself).
            - NEVER refer to the AI, system, assistant, or writer in the output.
            - ALL content must be written in third-person, candidate-focused, resume-standard language.
            - Prefer implicit subject sentences or neutral nouns such as
              “the candidate”, “the professional”, or role-based references.

            CRITICAL PROFESSIONAL WRITING CONSTRAINT (VERY IMPORTANT):
            - Treat each resume section as a completely isolated linguistic document.
            - Once a verb, phrase, or action concept appears in one section, it is forbidden in all other sections,
              even if reworded, paraphrased, or changed in tense.
            - Each section (Summary, Experience, Projects, Skills, SoftSkills, Interests) MUST use a distinct
              vocabulary set and unique action intent.
            - Any repetition across sections is a strict quality failure.

            GLOBAL ACTION & VERB ISOLATION PROTOCOL (MANDATORY EXECUTION STEP):

            Before generating any resume content, you MUST internally perform the following steps:

            STEP 1 — SECTION VOCABULARY PLANNING (INTERNAL, DO NOT OUTPUT):
            - Create a private, internal list of verbs and action concepts for EACH section:
              • Summary_Verb_Set
              • Experience_Verb_Set
              • Projects_Verb_Set
              • Interests_Action_Set
            - Each list MUST contain only verbs or action concepts unique to that section.
            - NO verb, verb root, synonym, or semantic action may appear in more than one list.

            STEP 2 — VOCABULARY LOCKING:
            - Once a verb or action concept is assigned to a section, it becomes permanently locked.
            - Locked verbs or actions are FORBIDDEN in all other sections, even if paraphrased.

            STEP 3 — ENFORCED GENERATION:
            - While writing each section, use ONLY the verbs and action concepts from its locked set.
            - If a conflict is detected, you MUST rewrite the conflicting section completely
              before producing final output.

            FAILURE CONDITION:
            - Any repeated verb, verb root, synonym, or semantic action across sections
              is considered a critical failure and must be corrected before output.

            FORMATTING REQUIREMENTS (FOLLOW EXACTLY):
            Each section must start with its label followed by a colon and then the formatted content.

            SECTION ENHANCEMENT RULES:

            SECTION-SPECIFIC LANGUAGE ENFORCEMENT:

            - SUMMARY:
              Use third-person PRESENT tense ONLY.
              Every bullet MUST begin with a third-person singular verb
              (e.g., specializes, positions, focuses, leverages).
              Do NOT use base verb forms (e.g., specialize, bring, focus).
              Do NOT use past or future tense.
              Use high-level professional positioning and strategic identity language only.
              Do NOT include implementation, execution, or tooling verbs.

            - EXPERIENCE:
              Use PAST tense ONLY.
              Use ownership, accountability, delivery, and responsibility-oriented language
              (e.g., led, governed, executed, resolved, delivered).
              Emphasize outcomes, scope, and measurable impact.
              Do NOT reuse verbs, phrases, or semantic actions from the Summary.

            - PROJECTS:
              Use PAST tense ONLY.
              Use deep technical, engineering, and system-design language
              (e.g., architected, engineered, integrated, optimized, validated).
              Projects MUST reflect industry-standard, real-world complexity.
              Avoid basic CRUD apps, toy projects, or academic-only descriptions.
              Emphasize architecture, constraints, scalability, performance, or security.
              Do NOT reuse verbs, phrases, or action ideas from Summary or Experience.

            - SKILLS & SOFTSKILLS:
              Nouns only.
              List-only format.
              Do NOT include descriptive or explanatory sentences.

            - INTERESTS:
              Use professional learning, exploration, contribution, or domain-engagement language.
              Avoid overlap with Skills or Projects.

            1. SUMMARY:
               Write 3–4 bullet points defining the candidate’s current professional identity,
               specialization, and measurable strengths for "{st.session_state['job_title']}". 

            2. EXPERIENCE:
               Present entries as (A., B., C.) containing:
               - Company Name (Duration)
               - Role title
               - 3–4 bullets focused on achievements, ownership, and measurable impact
               - Include tools, metrics, scale, and outcomes where applicable

            3. PROJECTS:
               Present as (A., B., C.) with:
               - Project Title
               - Tech Stack: (only relevant, production-grade technologies)
               - Duration: (timeframe)
               - Description:
                 - System or feature engineered
                 - Technical decisions or architectural approach
                 - Performance, scalability, or security improvement with metrics
                 - Complexity handled or constraints solved
                 - Final measurable outcome or professional learning

            4. SKILLS:
               List 6–8 current, job-relevant technical skills only.

            5. SOFTSKILLS:
               List 6–8 professional traits related to collaboration, ownership,
               adaptability, communication, and analytical thinking.

            6. LANGUAGES:
               Include spoken or written languages only.

            7. INTERESTS:
               Include 3–6 professional or domain-aligned interests.

            8. CERTIFICATES:
               Include 3–6 verified, industry-recognized certifications with provider and duration.

            DOMAIN-SPECIFIC FOCUS:
            - Technical Roles → Frameworks, programming languages, CI/CD, cloud platforms, scalability, security.
            - Security Roles → Threat modeling, SIEM tools, incident response, compliance frameworks.
            - Data Roles → Python, SQL, analytics, machine learning, visualization, statistics.
            - Management Roles → Leadership, KPIs, process optimization, strategic execution.

            OUTPUT FORMAT (STRICTLY FOLLOW THIS STRUCTURE):

            Summary:
            • [Third-person present tense, strategic positioning, measurable impact]
            • [Distinct professional strength with role alignment]
            • [Unique competency with quantified outcome]

            Experience:
            A. [Company Name] ([Duration])
               • [Role Title]
               • [Achievement with metrics]
               • [Ownership or delivery responsibility]
               • [Process or performance improvement]

            B. [Company Name] ([Duration])
               • [Role Title]
               • [Achievement with measurable outcome]
               • [Contribution or responsibility]

            Projects:
            A. [Project Title]
               • Tech Stack: [Relevant technologies only]
               • Duration: [Start – End]
               • Description:
                 - [System or feature engineered]
                 - [Technical decisions and implementation]
                 - [Measured improvement or result]
                 - [Complexity handled or innovation]

            B. [Project Title]
               • Tech Stack: [Relevant technologies only]
               • Duration: [Start – End]
               • Description:
                 - [Technical scope]
                 - [Challenges solved]
                 - [Quantified results]
                 - [Skills demonstrated]

            Skills:
            [Skill 1], [Skill 2], [Skill 3], [Skill 4], [Skill 5], [Skill 6], [Skill 7], [Skill 8]

            SoftSkills:
            [Soft Skill 1], [Soft Skill 2], [Soft Skill 3], [Soft Skill 4], [Soft Skill 5], [Soft Skill 6]

            Languages:
            [Language 1], [Language 2], [Language 3]

            Interests:
            [Interest 1], [Interest 2], [Interest 3], [Interest 4]

            Certificates:
            [Certificate Name] – [Provider] ([Duration/Level])
            [Certificate Name] – [Provider] ([Duration/Level])
            [Certificate Name] – [Provider] ([Duration/Level])

            ENHANCEMENT SOURCE DATA:
            Enhance the following inputs while maintaining factual accuracy
            and logical alignment with "{st.session_state['job_title']}":

            Summary:
            {st.session_state['summary']}

            Experience:
            {normalized_experience_entries}

            Projects:
            {normalized_project_entries}

            Skills:
            {st.session_state['skills']}

            SoftSkills:
            {st.session_state['Softskills']}

            Languages:
            {st.session_state['languages']}

            Interests:
            {st.session_state['interests']}

            Certificates:
            {[cert['name'] for cert in st.session_state['certificate_links'] if cert['name']]}

            FINAL QUALITY & DE-DUPLICATION CHECK (MANDATORY):
            - Ensure verb tense consistency per section.
            - Ensure zero verb, phrase, or semantic repetition across sections.
            - If any conflict exists, rewrite the later section entirely before output.

            IMPORTANT:
            - Do NOT fabricate companies, experience, or certifications.
            - Maintain professional, ATS-optimized language.
            - Output ONLY the formatted resume content without explanations.
            """





            with st.spinner("🧠 Thinking..."):
                ai_output = call_llm(enhance_prompt, session=st.session_state)
                st.session_state["ai_output"] = ai_output

    # ------------------------- PARSE + RENDER -------------------------
    if "ai_output" in st.session_state:
        ai_output = st.session_state["ai_output"]

        def extract_section(label, output, default=""):
            match = re.search(rf"{label}:\s*(.*?)(?=\n\w+:|\Z)", output, re.DOTALL)
            return match.group(1).strip() if match else default

        summary_enhanced = extract_section("Summary", ai_output, st.session_state['summary'])
        experience_raw = extract_section("Experience", ai_output)
        experience_blocks = re.split(r"\n(?=[A-Z]\. )", experience_raw.strip())
        projects_raw = extract_section("Projects", ai_output)
        projects_blocks = re.split(r"\n(?=[A-Z]\. )", projects_raw.strip())
        skills_list = extract_section("Skills", ai_output, st.session_state['skills'])
        softskills_list = extract_section("SoftSkills", ai_output, st.session_state['Softskills'])
        languages_list = extract_section("Languages", ai_output, st.session_state['languages'])
        interests_list = extract_section("Interests", ai_output, st.session_state['interests'])
        certificates_list = extract_section("Certificates", ai_output)

        # ------------------------- UI RENDER -------------------------
        left, right = st.columns([1, 2])

        with left:
            st.markdown(f"""
                <h2 style='color:#2f2f2f;margin-bottom:0;'>{st.session_state['name']}</h2>
                <h4 style='margin-top:5px;color:#444;'>{st.session_state['job_title']}</h4>
                <p style='font-size:14px;'>
                📍 {st.session_state['location']}<br>
                📞 {st.session_state['phone']}<br>
                📧 <a href="mailto:{st.session_state['email']}">{st.session_state['email']}</a><br>
                🔗 <a href="{st.session_state['linkedin']}" target="_blank">LinkedIn</a><br>
                🌐 <a href="{st.session_state['portfolio']}" target="_blank">Portfolio</a>
                </p>
            """, unsafe_allow_html=True)

            def render_bullet_section(title, items):
                st.markdown(f"<h4 style='color:#336699;'>{title}</h4><hr style='margin-top:-10px;'>", unsafe_allow_html=True)
                for item in [i.strip() for i in items.split(",") if i.strip()]:
                    st.markdown(f"<div style='margin-left:10px;'>• {item}</div>", unsafe_allow_html=True)

            render_bullet_section("Skills", skills_list)
            render_bullet_section("Languages", languages_list)
            render_bullet_section("Interests", interests_list)
            render_bullet_section("Soft Skills", softskills_list)

        with right:
            formatted_summary = summary_enhanced.replace('\n• ', '<br>• ').replace('\n', '<br>')
            st.markdown("<h4 style='color:#336699;'>Summary</h4><hr style='margin-top:-10px;'>", unsafe_allow_html=True)
            st.markdown(f"<p style='font-size:17px;'>{formatted_summary}</p>", unsafe_allow_html=True)

            # Experience
            if experience_blocks:
                st.markdown("<h4 style='color:#336699;'>Experience</h4><hr style='margin-top:-10px;'>", unsafe_allow_html=True)
                experience_titles = [entry.get("title", "").strip().upper() for entry in st.session_state.experience_entries]
                for idx, exp_block in enumerate(experience_blocks):
                    lines = exp_block.strip().split("\n")
                    if not lines:
                        continue
                    heading = lines[0]
                    description_lines = lines[1:]
                    match = re.match(r"[A-Z]\.\s*(.+?)\s*\((.*?)\)", heading)
                    company, duration = (match.group(1).strip(), match.group(2).strip()) if match else (heading, "")
                    role = experience_titles[idx] if idx < len(experience_titles) else ""
                    formatted_exp = "<br>".join(description_lines)

                    st.markdown(f"""
                    <div style='margin-bottom:15px; padding:10px; border-radius:8px;'>
                        <div style='display:flex; justify-content:space-between;'>
                            <b>🏢 {company.upper()}</b><span style='color:gray;'>📆 {duration}</span>
                        </div>
                        <div style='font-size:14px;'>💼 <i>{role}</i></div>
                        <div style='font-size:17px;'>📝 {formatted_exp}</div>
                    </div>
                    """, unsafe_allow_html=True)

            # Education
            st.markdown("<h4 style='color:#336699;'>🎓 Education</h4><hr style='margin-top:-10px;'>", unsafe_allow_html=True)
            for edu in st.session_state.education_entries:
                st.markdown(f"""
                <div style='margin-bottom:15px; padding:10px 15px; border-radius:8px;'>
                    <div style='display: flex; justify-content: space-between; font-size: 16px; font-weight: bold;'>
                        <span>🏫 {edu['institution']}</span>
                        <span style='color: gray;'>📅 {edu['year']}</span>
                    </div>
                    <div style='font-size: 14px;'>🎓 <i>{edu['degree']}</i></div>
                    <div style='font-size: 14px;'>📄 {edu['details']}</div>
                </div>
                """, unsafe_allow_html=True)

            # Projects
            if projects_blocks:
                st.markdown("<h4 style='color:#336699;'>Projects</h4><hr style='margin-top:-10px;'>", unsafe_allow_html=True)
                for idx, proj_block in enumerate(projects_blocks):
                    proj = st.session_state.project_entries[idx] if idx < len(st.session_state.project_entries) else {}
                    title = proj.get("title", "")
                    tech = proj.get("tech", "")
                    duration = proj.get("duration", "")
                    description = proj_block
                    for keyword in [title, f"Tech Stack: {tech}", f"Duration: {duration}"]:
                        if keyword and keyword in description:
                            description = description.replace(keyword, "")
                    formatted_proj = description.strip().replace('\n• ', '<br>• ').replace('\n', '<br>')
                    label = chr(65 + idx)

                    st.markdown(f"""
                    <div style='margin-bottom:15px; padding: 10px;'>
                        <strong style='font-size:16px;'>📌 <span style='color:#444;'>{label}. </span>{title}</strong><br>
                        <span style='font-size:14px;'>🛠️ <strong>Tech Stack:</strong> {tech}</span><br>
                        <span style='font-size:14px;'>⏳ <strong>Duration:</strong> {duration}</span><br>
                        <span style='font-size:17px;'>📄 <strong>Description:</strong></span><br>
                        <div style='margin-top:4px; font-size:15px;'>{formatted_proj}</div>
                    </div>
                    """, unsafe_allow_html=True)

            # Certificates
            if certificates_list:
                st.markdown("<h4 style='color:#336699;'>📜 Certificates</h4><hr style='margin-top:-10px;'>", unsafe_allow_html=True)
                certs = re.split(r"\n|(?<=\))(?=\s*[A-Z])|(?<=[a-z]\))(?= [A-Z])", certificates_list)
                for cert in [c.strip() for c in certs if c.strip()]:
                    st.markdown(f"<div style='margin-left:10px;'>• {cert}</div>", unsafe_allow_html=True)

            if st.session_state.project_links:
                st.markdown("<h4 style='color:#336699;'>Project Links</h4><hr style='margin-top:-10px;'>", unsafe_allow_html=True)
                for i, link in enumerate(st.session_state.project_links):
                    st.markdown(f"[🔗 Project {i+1}]({link})", unsafe_allow_html=True)

    # Generate HTML content based on selected template — only on submit, stored in session_state
    if submitted:
        # Determine which template to use
        if selected_template == "Default (Professional)":
            html_content = render_template_default(st.session_state, profile_img_html)
        elif selected_template == "Modern Minimal":
            html_content = render_template_modern(st.session_state, profile_img_html)
        elif selected_template == "Elegant Sidebar":
            html_content = render_template_sidebar(st.session_state, profile_img_html)
        elif selected_template == "Classic Clean (Single Column)":
            html_content = render_template_classic(st.session_state, profile_img_html)
        elif selected_template == "Executive (Single Column)":
            html_content = render_template_executive(st.session_state, profile_img_html)
        elif selected_template == "Timeline (Single Column)":
            html_content = render_template_timeline(st.session_state, profile_img_html)
        elif selected_template == "Corporate Blue (Two Column)":
            html_content = render_template_corporate(st.session_state, profile_img_html)
        elif selected_template == "Creative Green (Two Column)":
            html_content = render_template_creative_green(st.session_state, profile_img_html)
        elif selected_template == "Warm Terracotta (Two Column)":
            html_content = render_template_terracotta(st.session_state, profile_img_html)
        else:
            # Fallback to default
            html_content = render_template_default(st.session_state, profile_img_html)

        # Store the generated content
        st.session_state["generated_html"] = html_content

with tab2:
    # ==========================
    # 📥 Resume Download Header
    # ==========================
    if "generated_html" in st.session_state:
        st.markdown(
            """
            <div style='text-align: center; margin-top: 20px; margin-bottom: 30px;'>
                <h2 style='color: #2f4f6f; font-family: Arial, sans-serif; font-size: 24px;'>
                    📥 Download Your Resume
                </h2>
                <p style="color:#555; font-size:14px;">
                    Choose your preferred format below
                </p>
            </div>
            """,
            unsafe_allow_html=True
        )

        col1, = st.columns(1)

        # HTML Resume Download Button
        with col1:
            html_bytes = st.session_state["generated_html"].encode("utf-8")
            html_file = BytesIO(html_bytes)
            
            st.download_button(
                label="⬇️ Download as Template",
                data=html_file,
                file_name=f"{st.session_state['name'].replace(' ', '_')}_Resume.html",
                mime="text/html",
                key="download_resume_html"
            )

        # PDF Resume Download Button
        pdf_resume_bytes = html_to_pdf_bytes(st.session_state["generated_html"])
        
        # ✅ Extra Help Note
        st.markdown("""
        ✅ After downloading your HTML resume, you can 
        <a href="https://www.sejda.com/html-to-pdf" target="_blank" style="color:#2f4f6f; text-decoration:none;">
        convert it to PDF using Sejda's free online tool</a>.
        """, unsafe_allow_html=True)

        # ==========================
        # 📩 Cover Letter Expander
        # ==========================
        with st.expander("📩 Generate Cover Letter from This Resume"):
            generate_cover_letter_from_resume_builder()

        # ==========================
        # ✉️ Generated Cover Letter Downloads (NO PREVIEW HERE)
        # ==========================
        if "cover_letter" in st.session_state:
            st.markdown(
                """
                <div style="margin-top: 30px; margin-bottom: 20px;">
                    <h3 style="color: #003366;">✉️ Generated Cover Letter</h3>
                    <p style="color:#555; font-size:14px;">
                        You can download your generated cover letter in multiple formats.
                    </p>
                </div>
                """,
                unsafe_allow_html=True
            )

            # ✅ Use already-rendered HTML from session (don't show again)
            styled_cover_letter = st.session_state.get("cover_letter_html", "")

            # ✅ Generate PDF from styled HTML
            pdf_file = html_to_pdf_bytes(styled_cover_letter)

            # ✅ DOCX Generator (preserves line breaks)
            def create_docx_from_text(text, filename="cover_letter.docx"):
                from docx import Document
                bio = BytesIO()
                doc = Document()
                doc.add_heading("Cover Letter", 0)

                for line in text.split("\n"):
                    if line.strip():
                        doc.add_paragraph(line)
                    else:
                        doc.add_paragraph("")  # preserve empty lines

                doc.save(bio)
                bio.seek(0)
                return bio

            # ==========================
            # 📥 Cover Letter Download Buttons
            # ==========================
            st.markdown("""
            <div style="margin-top: 25px; margin-bottom: 15px;">
                <strong>⬇️ Download Your Cover Letter:</strong>
            </div>
            """, unsafe_allow_html=True)

            col1,col2 = st.columns(2)
            with col1:
                st.download_button(
                    label="📥 Download Cover Letter (.docx)",
                    data=create_docx_from_text(st.session_state["cover_letter"]),
                    file_name=f"{st.session_state['name'].replace(' ', '_')}_Cover_Letter.docx",
                    mime="application/vnd.openxmlformats-officedocument.wordprocessingml.document",
                    key="download_coverletter_docx"
                )
            
            with col2:
                st.download_button(
                    label="📥 Download Cover Letter (Template)",
                    data=styled_cover_letter.encode("utf-8"),
                    file_name=f"{st.session_state['name'].replace(' ', '_')}_Cover_Letter.html",
                    mime="text/html",
                    key="download_coverletter_html"
                )

            # ✅ Helper note
            st.markdown("""
            ✅ If the HTML cover letter doesn't display properly, you can 
            <a href="https://www.sejda.com/html-to-pdf" target="_blank" style="color:#2f4f6f; text-decoration:none;">
            convert it to PDF using Sejda's free online tool</a>.
            """, unsafe_allow_html=True)
FEATURED_COMPANIES = {
    "tech": [
        {
            "name": "Google",
            "logo_url": "https://upload.wikimedia.org/wikipedia/commons/2/2f/Google_2015_logo.svg",
            "color": "#4285F4",
            "careers_url": "https://careers.google.com",
            "description": "Leading technology company known for search, cloud, and innovation",
            "categories": ["Software", "AI/ML", "Cloud", "Data Science"]
        },
        {
            "name": "Microsoft",
            "logo_url": "https://upload.wikimedia.org/wikipedia/commons/4/44/Microsoft_logo.svg",
            "color": "#00A4EF",
            "careers_url": "https://careers.microsoft.com",
            "description": "Global leader in software, cloud, and enterprise solutions",
            "categories": ["Software", "Cloud", "Gaming", "Enterprise"]
        },
        {
            "name": "Amazon",
            "logo_url": "https://upload.wikimedia.org/wikipedia/commons/a/a9/Amazon_logo.svg",
            "color": "#FF9900",
            "careers_url": "https://www.amazon.jobs",
            "description": "E-commerce and cloud computing giant",
            "categories": ["Software", "Operations", "Cloud", "Retail"]
        },
        {
            "name": "Apple",
            "logo_url": "https://upload.wikimedia.org/wikipedia/commons/f/fa/Apple_logo_black.svg",
            "color": "#555555",
            "careers_url": "https://www.apple.com/careers",
            "description": "Innovation leader in consumer technology",
            "categories": ["Software", "Hardware", "Design", "AI/ML"]
        },
        {
            "name": "Facebook",
            "logo_url": "https://upload.wikimedia.org/wikipedia/commons/0/05/Facebook_Logo_%282019%29.png",
            "color": "#1877F2",
            "careers_url": "https://www.metacareers.com/",
            "description": "Social media and technology company",
            "categories": ["Software", "Marketing", "Networking", "AI/ML"]
        },
        {
            "name": "Netflix",
            "logo_url": "https://upload.wikimedia.org/wikipedia/commons/0/08/Netflix_2015_logo.svg",
            "color": "#E50914",
            "careers_url": "https://explore.jobs.netflix.net/careers",
            "description": "Streaming media company",
            "categories": ["Software", "Marketing", "Design", "Service"],
            "website": "https://jobs.netflix.com/",
            "industry": "Entertainment & Technology"
        }
    ],
    "indian_tech": [
        {
            "name": "TCS",
            "logo_url": "https://upload.wikimedia.org/wikipedia/commons/f/f6/TCS_New_Logo.svg",
            "color": "#0070C0",
            "careers_url": "https://www.tcs.com/careers",
            "description": "India's largest IT services company",
            "categories": ["IT Services", "Consulting", "Digital"]
        },
        {
            "name": "Infosys",
            "logo_url": "https://upload.wikimedia.org/wikipedia/commons/5/55/Infosys_logo.svg",
            "color": "#007CC3",
            "careers_url": "https://www.infosys.com/careers",
            "description": "Global leader in digital services and consulting",
            "categories": ["IT Services", "Consulting", "Digital"]
        },
        {
            "name": "Wipro",
            "logo_url": "https://upload.wikimedia.org/wikipedia/commons/8/80/Wipro_Primary_Logo_Color_RGB.svg",
            "color": "#341F65",
            "careers_url": "https://careers.wipro.com",
            "description": "Leading global information technology company",
            "categories": ["IT Services", "Consulting", "Digital"]
        },
        {
            "name": "HCL",
            "logo_url": "https://upload.wikimedia.org/wikipedia/commons/5/5e/HCL_Technologies_logo.svg",
            "color": "#0075C9",
            "careers_url": "https://www.hcltech.com/careers",
            "description": "Global technology company",
            "categories": ["IT Services", "Engineering", "Digital"]
        }
    ],
    "global_corps": [
        {
            "name": "IBM",
            "logo_url": "https://upload.wikimedia.org/wikipedia/commons/5/51/IBM_logo.svg",
            "color": "#1F70C1",
            "careers_url": "https://www.ibm.com/careers",
            "description": "Global leader in technology and consulting",
            "categories": ["Software", "Consulting", "AI/ML", "Cloud"],
            "website": "https://www.ibm.com/careers/",
            "industry": "Technology & Consulting"
        },
        {
            "name": "Accenture",
            "logo_url": "https://upload.wikimedia.org/wikipedia/commons/8/80/Accenture_Logo.svg",
            "color": "#A100FF",
            "careers_url": "https://www.accenture.com/careers",
            "description": "Global professional services company",
            "categories": ["Consulting", "Technology", "Digital"]
        },
        {
            "name": "Cognizant",
            "logo_url": "https://upload.wikimedia.org/wikipedia/commons/6/6e/Cognizant_logo_2022.svg",
            "color": "#1299D8",
            "careers_url": "https://careers.cognizant.com",
            "description": "Leading professional services company",
            "categories": ["IT Services", "Consulting", "Digital"]
        }
    ]
}


JOB_MARKET_INSIGHTS = {
    "trending_skills": [
        {"name": "Artificial Intelligence", "growth": "+45%", "icon": "fas fa-brain"},
        {"name": "Cloud Computing", "growth": "+38%", "icon": "fas fa-cloud"},
        {"name": "Data Science", "growth": "+35%", "icon": "fas fa-chart-line"},
        {"name": "Cybersecurity", "growth": "+32%", "icon": "fas fa-shield-alt"},
        {"name": "DevOps", "growth": "+30%", "icon": "fas fa-code-branch"},
        {"name": "Machine Learning", "growth": "+28%", "icon": "fas fa-robot"},
        {"name": "Blockchain", "growth": "+25%", "icon": "fas fa-lock"},
        {"name": "Big Data", "growth": "+23%", "icon": "fas fa-database"},
        {"name": "Internet of Things", "growth": "+21%", "icon": "fas fa-wifi"}
    ],
    "top_locations": [
        {"name": "Bangalore", "jobs": "50,000+", "icon": "fas fa-city"},
        {"name": "Mumbai", "jobs": "35,000+", "icon": "fas fa-city"},
        {"name": "Delhi NCR", "jobs": "30,000+", "icon": "fas fa-city"},
        {"name": "Hyderabad", "jobs": "25,000+", "icon": "fas fa-city"},
        {"name": "Pune", "jobs": "20,000+", "icon": "fas fa-city"},
        {"name": "Chennai", "jobs": "15,000+", "icon": "fas fa-city"},
        {"name": "Noida", "jobs": "10,000+", "icon": "fas fa-city"},
        {"name": "Vadodara", "jobs": "7,000+", "icon": "fas fa-city"},
        {"name": "Ahmedabad", "jobs": "6,000+", "icon": "fas fa-city"},
        {"name": "Remote", "jobs": "3,000+", "icon": "fas fa-globe-americas"},
    ],
    "salary_insights": [
        {"role": "Machine Learning Engineer", "range": "10-35 LPA", "experience": "0-5 years"},
        {"role": "Big Data Engineer", "range": "8-30 LPA", "experience": "0-5 years"},
        {"role": "Software Engineer", "range": "5-25 LPA", "experience": "0-5 years"},
        {"role": "Data Scientist", "range": "8-30 LPA", "experience": "0-5 years"},
        {"role": "DevOps Engineer", "range": "6-28 LPA", "experience": "0-5 years"},
        {"role": "UI/UX Designer", "range": "5-25 LPA", "experience": "0-5 years"},
        {"role": "Full Stack Developer", "range": "8-30 LPA", "experience": "0-5 years"},
        {"role": "C++/C#/Python/Java Developer", "range": "6-26 LPA", "experience": "0-5 years"},
        {"role": "Django Developer", "range": "7-27 LPA", "experience": "0-5 years"},
        {"role": "Cloud Engineer", "range": "6-26 LPA", "experience": "0-5 years"},
        {"role": "Google Cloud/AWS/Azure Engineer", "range": "6-26 LPA", "experience": "0-5 years"},
        {"role": "Salesforce Engineer", "range": "6-26 LPA", "experience": "0-5 years"},
    ]
}

def get_featured_companies(category=None):
    """Get featured companies with original logos, optionally filtered by category"""
    def has_valid_logo(company):
        return "logo_url" in company and company["logo_url"].startswith("https://upload.wikimedia.org/")

    if category and category in FEATURED_COMPANIES:
        return [company for company in FEATURED_COMPANIES[category] if has_valid_logo(company)]

    return [
        company for companies in FEATURED_COMPANIES.values()
        for company in companies if has_valid_logo(company)
    ]


def get_market_insights():
    """Get job market insights"""
    return JOB_MARKET_INSIGHTS

def get_company_info(company_name):
    """Get company information by name"""
    for companies in FEATURED_COMPANIES.values():
        for company in companies:
            if company["name"] == company_name:
                return company
    return None

def get_companies_by_industry(industry):
    """Get list of companies by industry"""
    companies = []
    for companies_list in FEATURED_COMPANIES.values():
        for company in companies_list:
            if "industry" in company and company["industry"] == industry:
                companies.append(company)
    return companies

# Sample job search function
import uuid
import urllib.parse
import sqlite3
import datetime
import streamlit as st
from zoneinfo import ZoneInfo
import requests
import re

# ✅ RapidAPI Configuration (from Streamlit secrets)
RAPID_API_KEY = st.secrets["rapidapi"]["key"]
RAPID_API_HOST = st.secrets["rapidapi"]["host"]

def clean_html(raw_html: str) -> str:
    """Remove HTML tags and comments from API descriptions."""
    if not raw_html:
        return ""
    # Remove comments
    raw_html = re.sub(r"<!--.*?-->", "", raw_html, flags=re.DOTALL)
    # Remove all tags
    return re.sub(r"<.*?>", "", raw_html).strip()

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
            "description": clean_html(job.get("job_description",""))[:200] + "...",
            "apply_link": job.get("job_apply_link", "#")
        })

    # 2️⃣ Add LinkedIn, Naukri, FoundIt links (existing function)
    external_links = search_jobs(job_role, location, experience_level, job_type, foundit_experience)
    for job in external_links:
        results.append({
            "platform": job["title"].split(":")[0],
            "title": job["title"].split(":")[1].strip(),
            "company": "N/A",
            "location": location,
            "salary": "Check site",
            "date": "N/A",
            "type": "N/A",
            "remote": "N/A",
            "publisher": job["title"].split(":")[0],
            "description": "Open this platform to view full details.",
            "apply_link": job["link"]
        })

    return results


# Database functions for job search history
def init_job_search_db():
    """Initialize the job search database and create user_jobs table if not exists"""
    try:
        conn = sqlite3.connect('resume_data.db')
        cursor = conn.cursor()

        cursor.execute('''
            CREATE TABLE IF NOT EXISTS user_jobs (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                username TEXT NOT NULL,
                role TEXT NOT NULL,
                location TEXT NOT NULL,
                platform TEXT NOT NULL,
                url TEXT NOT NULL,
                timestamp DATETIME DEFAULT CURRENT_TIMESTAMP
            )
        ''')

        conn.commit()
        conn.close()
    except Exception as e:
        st.error(f"Database initialization error: {e}")

def save_job_search(username, role, location, results):
    """Save job search results to database for logged-in user"""
    if not username:
        return

    try:
        conn = sqlite3.connect('resume_data.db')
        cursor = conn.cursor()

        for result in results:
            # Extract platform name from title or use platform field
            platform = result.get("platform", "Unknown")
            url = result.get("apply_link", "#")

            cursor.execute('''
                INSERT INTO user_jobs (username, role, location, platform, url, timestamp)
                VALUES (?, ?, ?, ?, ?, ?)
            ''', (username, role, location, platform, url, datetime.datetime.now()))

        conn.commit()
        conn.close()

    except Exception as e:
        st.error(f"Error saving job search: {e}")

def prune_old_searches(username):
    """Keep only the last 50 saved job searches per user (optional cleanup)"""
    if not username:
        return

    try:
        conn = sqlite3.connect('resume_data.db')
        cursor = conn.cursor()

        # Delete all but the most recent 50 searches for this user
        cursor.execute('''
            DELETE FROM user_jobs
            WHERE username = ? AND id NOT IN (
                SELECT id FROM user_jobs
                WHERE username = ?
                ORDER BY timestamp DESC
                LIMIT 50
            )
        ''', (username, username))

        conn.commit()
        conn.close()

    except Exception as e:
        st.error(f"Error pruning old searches: {e}")

def delete_saved_job_search(search_id):
    """Delete a saved job search by its ID"""
    try:
        conn = sqlite3.connect('resume_data.db')
        cursor = conn.cursor()

        cursor.execute('DELETE FROM user_jobs WHERE id = ?', (search_id,))

        conn.commit()
        conn.close()

    except Exception as e:
        st.error(f"Error deleting job search: {e}")

def get_saved_job_searches(username, limit=10, offset=0, platform_filter=None):
    """Get saved job searches for a user with filtering and pagination"""
    if not username:
        return []

    try:
        conn = sqlite3.connect('resume_data.db')
        cursor = conn.cursor()

        # Build the query with optional platform filter
        if platform_filter and platform_filter != "All":
            cursor.execute('''
                SELECT id, role, location, platform, url, timestamp
                FROM user_jobs
                WHERE username = ? AND platform = ?
                ORDER BY timestamp DESC
                LIMIT ? OFFSET ?
            ''', (username, platform_filter, limit, offset))
        else:
            cursor.execute('''
                SELECT id, role, location, platform, url, timestamp
                FROM user_jobs
                WHERE username = ?
                ORDER BY timestamp DESC
                LIMIT ? OFFSET ?
            ''', (username, limit, offset))

        results = cursor.fetchall()
        conn.close()

        return [
            {
                "id": row[0],
                "role": row[1],
                "location": row[2],
                "platform": row[3],
                "url": row[4],
                "timestamp": row[5]
            }
            for row in results
        ]
    except Exception as e:
        st.error(f"Error fetching saved searches: {e}")
        return []

def get_total_saved_searches_count(username, platform_filter=None):
    """Get total count of saved searches for pagination"""
    if not username:
        return 0

    try:
        conn = sqlite3.connect('resume_data.db')
        cursor = conn.cursor()

        if platform_filter and platform_filter != "All":
            cursor.execute('SELECT COUNT(*) FROM user_jobs WHERE username = ? AND platform = ?', (username, platform_filter))
        else:
            cursor.execute('SELECT COUNT(*) FROM user_jobs WHERE username = ?', (username,))

        count = cursor.fetchone()[0]
        conn.close()

        return count
    except Exception as e:
        st.error(f"Error getting search count: {e}")
        return 0

def get_available_platforms(username):
    """Get list of platforms that the user has searched on"""
    if not username:
        return []

    try:
        conn = sqlite3.connect('resume_data.db')
        cursor = conn.cursor()

        cursor.execute('SELECT DISTINCT platform FROM user_jobs WHERE username = ? ORDER BY platform', (username,))

        platforms = [row[0] for row in cursor.fetchall()]
        conn.close()

        return platforms
    except Exception as e:
        st.error(f"Error fetching platforms: {e}")
        return []

def slugify(text: str) -> str:
    """Convert text into a safe slug (lowercase, hyphenated, no special chars)."""
    text = text.lower().strip()
    text = re.sub(r"[^\w\s-]", "", text)
    text = re.sub(r"\s+", "-", text)
    return text

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
    # Platform icon mapping
    icon_map = {
        "LinkedIn": "🔵",
        "Naukri": "🏢",
        "FoundIt (Monster)": "🌐",
        "RapidAPI (Live)": "⚡"
    }
    icon = icon_map.get(platform_name, "📄")

    # Build metadata section and calculate height
    metadata_html = ""
    estimated_height = 180  # Base height (platform + title + button + padding)

    if company:
        metadata_html += f"""
        <div style="color: #aaaaaa; font-size: 14px; margin-bottom: 8px; z-index: 2; position: relative;">
            🏢 <b>{company}</b>
        </div>
        """
        estimated_height += 30

    if location:
        metadata_html += f"""
        <div style="color: #aaaaaa; font-size: 14px; margin-bottom: 8px; z-index: 2; position: relative;">
            📍 {location}
        </div>
        """
        estimated_height += 30

    if salary and salary not in ["Check site", "N/A - N/A "]:
        metadata_html += f"""
        <div style="color: #aaaaaa; font-size: 14px; margin-bottom: 8px; z-index: 2; position: relative;">
            💰 {salary}
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
    <div style="font-size: 20px; margin-bottom: 12px; z-index: 2; position: relative; font-weight: bold; color: {brand_color};">
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
            <span style="position: relative; z-index: 2;">🚀 Apply Now →</span>
        </button>
    </a>
</div>
</body>
</html>
"""
    return job_card_html, estimated_height

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

    # LinkedIn URL
    linkedin_url = f"https://www.linkedin.com/jobs/search/?keywords={role_encoded}&location={loc_encoded}"
    if experience_level in linkedin_exp_map:
        linkedin_url += f"&f_E={linkedin_exp_map[experience_level]}"
    if job_type in job_type_map:
        linkedin_url += f"&f_JT={job_type_map[job_type]}"

    # Determine experience values
    if foundit_experience is not None:
        experience_range = f"{foundit_experience}~{foundit_experience}"
        experience_exact = str(foundit_experience)
    else:
        experience_range = experience_range_map.get(experience_level, "")
        experience_exact = experience_exact_map.get(experience_level, "")

    # Naukri URL – no forced "and-india"
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



def add_hyperlink(paragraph, url, text, color="0000FF", underline=True):
    """
    A function to add a hyperlink to a paragraph.
    """
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

# Initialize database
init_job_search_db()

# Your existing tab3 code with enhanced CSS styling
with tab3:
    st.markdown("<h1 style='text-align: center; color: #ffffff; margin-bottom: 30px;'>🟦 Job Search Hub</h1>", unsafe_allow_html=True)

    # Initialize session state for search mode
    if 'search_mode' not in st.session_state:
        st.session_state.search_mode = "External Platforms"

    # Modern Toggle Switch with Circular Indicator
    is_external = st.session_state.search_mode == "External Platforms"

    toggle_html = f"""
    <style>
    .toggle-switch-container {{
        display: flex;
        justify-content: center;
        align-items: center;
        margin-bottom: 30px;
        gap: 0;
    }}
    .toggle-option {{
        background: rgba(40, 40, 40, 0.95);
        padding: 18px 35px;
        color: rgba(255, 255, 255, 0.4);
        font-size: 15px;
        font-weight: 600;
        border: 1px solid rgba(255, 255, 255, 0.15);
        display: flex;
        align-items: center;
        gap: 12px;
        transition: all 0.3s ease;
        cursor: pointer;
        position: relative;
    }}
    .toggle-option.left {{
        border-radius: 16px 0 0 16px;
        border-right: none;
    }}
    .toggle-option.right {{
        border-radius: 0 16px 16px 0;
        border-left: none;
    }}
    .toggle-option.active {{
        color: #ffffff;
    }}
    .toggle-option.active.external {{
        background: linear-gradient(135deg, #2196F3 0%, #1976D2 100%);
        border-color: #1976D2;
    }}
    .toggle-option.active.rapid {{
        background: linear-gradient(135deg, #00E676 0%, #00C853 100%);
        border-color: #00C853;
    }}
    .toggle-circle {{
        width: 16px;
        height: 16px;
        border-radius: 50%;
        border: 2px solid rgba(255, 255, 255, 0.4);
        background: transparent;
        transition: all 0.3s ease;
    }}
    .toggle-option.active .toggle-circle {{
        background: #ffffff;
        border-color: #ffffff;
    }}
    .toggle-option:hover:not(.active) {{
        background: rgba(55, 55, 55, 0.95);
        color: rgba(255, 255, 255, 0.7);
    }}
    .active-badge {{
        text-align: center;
        padding: 15px;
        margin-bottom: 25px;
    }}
    .badge {{
        background: linear-gradient(135deg, #2196F3 0%, #1976D2 100%);
        padding: 10px 25px;
        border-radius: 20px;
        color: white;
        font-weight: 600;
        font-size: 14px;
        display: inline-block;
    }}
    .badge.rapid {{
        background: linear-gradient(135deg, #00E676 0%, #00C853 100%);
    }}
    </style>

    <div class="toggle-switch-container">
        <div class="toggle-option left {'active external' if is_external else ''}" id="toggle-external">
            <div class="toggle-circle"></div>
            <span>🌐 External Platforms (LinkedIn, Naukri, FoundIt)</span>
        </div>
        <div class="toggle-option right {'active rapid' if not is_external else ''}" id="toggle-rapid">
            <div class="toggle-circle"></div>
            <span>⚡ RapidAPI Jobs (India Only)</span>
        </div>
    </div>

    <div class="active-badge">
        <span class="badge {'rapid' if not is_external else ''}">
            {'🌐 External Platforms Mode Active' if is_external else '⚡ RapidAPI Jobs Mode Active'}
        </span>
    </div>
    """

    st.markdown(toggle_html, unsafe_allow_html=True)

    # Create clickable buttons (hidden but functional)
    col_btn1, col_btn2 = st.columns(2)

    with col_btn1:
        if st.button("Switch to External Platforms", key="btn_external"):
            st.session_state.search_mode = "External Platforms"
            st.rerun()

    with col_btn2:
        if st.button("Switch to RapidAPI Jobs", key="btn_rapid"):
            st.session_state.search_mode = "RapidAPI Jobs"
            st.rerun()

    search_mode = st.session_state.search_mode

    if search_mode == "External Platforms":
        # External Platforms Section
        col1, col2 = st.columns(2)

        with col1:
            job_role = st.text_input("💼 Job Title / Skills", placeholder="e.g., Data Scientist", key="external_role")
            experience_level = st.selectbox(
                "📈 Experience Level",
                ["", "Internship", "Entry Level", "Associate", "Mid-Senior Level", "Director", "Executive"],
                key="external_exp"
            )

        with col2:
            location = st.text_input("📍 Location", placeholder="e.g., Bangalore, India", key="external_loc")
            job_type = st.selectbox(
                "📋 Job Type",
                ["", "Full-time", "Part-time", "Contract", "Temporary", "Volunteer", "Internship"],
                key="external_type"
            )

        foundit_experience = st.text_input("🔢 FoundIt Experience (Years)", placeholder="e.g., 1", key="external_foundit")

        search_clicked = st.button("🔎 Search External Jobs", key="search_external")

        if search_clicked:
            if job_role.strip() and location.strip():
                # Call search_jobs function for external platforms
                results = search_jobs(job_role, location, experience_level, job_type, foundit_experience)

                # Save search results if user is logged in
                if hasattr(st.session_state, 'username') and st.session_state.username:
                    # Convert results to format expected by save_job_search
                    formatted_results = []
                    for result in results:
                        platform_name = result["title"].split(":")[0]
                        formatted_results.append({
                            "platform": platform_name,
                            "apply_link": result["link"]
                        })
                    save_job_search(st.session_state.username, job_role, location, formatted_results)

                st.markdown("## 🎯 External Job Search Results")

                for job in results:
                    platform = job["title"].split(":")[0].lower()

                    # Platform styling
                    if "linkedin" in platform:
                        platform_name = "LinkedIn"
                        btn_color = "#0e76a8"
                        platform_gradient = "linear-gradient(135deg, #0e76a8 0%, #1a8cc8 100%)"
                    elif "naukri" in platform:
                        platform_name = "Naukri"
                        btn_color = "#ff5722"
                        platform_gradient = "linear-gradient(135deg, #ff5722 0%, #ff7043 100%)"
                    elif "foundit" in platform:
                        platform_name = "FoundIt (Monster)"
                        btn_color = "#7c4dff"
                        platform_gradient = "linear-gradient(135deg, #7c4dff 0%, #9c64ff 100%)"
                    else:
                        platform_name = platform.title()
                        btn_color = "#00c4cc"
                        platform_gradient = "linear-gradient(135deg, #00c4cc 0%, #26d0ce 100%)"

                    # Render card using reusable function
                    job_card_html, card_height = render_job_card(
                        title=job_role,
                        link=job['link'],
                        platform_name=platform_name,
                        brand_color=btn_color,
                        platform_gradient=platform_gradient,
                        location=location,
                        description="Open this platform to view full details."
                    )
                    st.components.v1.html(job_card_html, height=card_height, scrolling=False)
            else:
                st.warning("⚠️ Please enter both the Job Title and Location to perform the search.")

    else:
        # RapidAPI Jobs Section
        col1, col2 = st.columns(2)

        with col1:
            rapid_job_role = st.text_input("💼 Job Title / Skills", placeholder="e.g., Python Developer", key="rapid_role")

        with col2:
            rapid_location = st.text_input("📍 Location", placeholder="e.g., Mumbai", key="rapid_loc")

        # Number of results
        num_results = st.slider("📊 Number of Jobs to Fetch", min_value=5, max_value=50, value=10, step=5, key="rapid_num_results")

        # Advanced Filters
        with st.expander("🔧 Advanced Filters"):
            date_posted = st.selectbox(
                "📅 Date Posted",
                ["all", "today", "3days", "week", "month"],
                key="rapid_date"
            )
            rapid_job_type = st.selectbox(
                "📋 Job Type",
                ["", "Full-time", "Part-time", "Contract", "Internship"],
                key="rapid_type"
            )
            remote_only = st.checkbox("🏠 Remote Only", key="rapid_remote")
            radius = st.number_input("📏 Radius (km)", min_value=0, max_value=200, value=50, key="rapid_radius")
            job_requirements = st.multiselect(
                "📝 Job Requirements",
                ["under_3_years_experience", "more_than_3_years_experience", "no_experience", "no_degree"],
                key="rapid_req"
            )

        search_rapid_clicked = st.button("🔎 Search Rapid Jobs", key="search_rapid")

        if search_rapid_clicked:
            if rapid_job_role.strip() and rapid_location.strip():

             with st.spinner("⚡ Fetching live jobs from RapidAPI..."):
            # Call fetch_live_jobs with parameters
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
                            "apply_link": job.get("job_apply_link", "#")
                       })
                    save_job_search(
                st.session_state.username,
                rapid_job_role,
                rapid_location,
                formatted_results
                )

                st.markdown("## 🎯 RapidAPI Job Results")


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
                        job_description = clean_html(job.get("job_description", ""))[:250] + "..."

                        # Format date
                        formatted_date = "N/A"
                        if job.get("job_posted_at_datetime_utc") and job["job_posted_at_datetime_utc"] != "N/A":
                            try:
                                date_obj = datetime.datetime.fromisoformat(job["job_posted_at_datetime_utc"].replace('Z', '+00:00'))
                                formatted_date = date_obj.strftime("%b %d, %Y")
                            except:
                                formatted_date = job["job_posted_at_datetime_utc"]

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
    <div style="font-size: 18px; margin-bottom: 15px; color: {btn_color}; font-weight: bold;">
        ⚡ RapidAPI (Live)
    </div>

    <!-- Job Title -->
    <div style="color: #ffffff; font-size: 22px; margin-bottom: 10px; font-weight: 600; line-height: 1.4;">
        {job_title}
    </div>

    <!-- Company -->
    <div style="color: #aaaaaa; font-size: 16px; margin-bottom: 15px;">
        🏢 <b>{job_company}</b>
    </div>

    <!-- Job Details Grid -->
    <div style="display: grid; grid-template-columns: repeat(2, 1fr); gap: 10px; margin-bottom: 15px;">
        <div style="color: #cccccc; font-size: 14px;">📍 <b>Location:</b> {job_location}</div>
        <div style="color: #cccccc; font-size: 14px;">💰 <b>Salary:</b> {job_salary}</div>
        <div style="color: #cccccc; font-size: 14px;">📋 <b>Type:</b> {job_type}</div>
        <div style="color: #cccccc; font-size: 14px;">🌍 <b>Mode:</b> {job_mode}</div>
        <div style="color: #cccccc; font-size: 14px;">📅 <b>Posted:</b> {formatted_date}</div>
        <div style="color: #cccccc; font-size: 14px;">📰 <b>Source:</b> {job_publisher}</div>
    </div>

    <!-- Description -->
    <div style="color: #999999; font-size: 14px; margin-bottom: 20px; line-height: 1.6;">
        {job_description}
    </div>

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
        ">
            🚀 Apply Now →
        </button>
    </a>
</div>
"""
                        
                        st.components.v1.html(job_card_html, height=450, scrolling=False)


                else:
                    st.info("No jobs found. Try adjusting your search criteria.")
            else:
                st.warning("⚠️ Please enter both the Job Title and Location to perform the search.")

    # Display saved job searches if user is logged in
    if hasattr(st.session_state, 'username') and st.session_state.username:
        # Get available platforms for filtering
        available_platforms = get_available_platforms(st.session_state.username)
        platform_options = ["All"] + available_platforms

        # Get total count of searches
        total_searches = get_total_saved_searches_count(st.session_state.username)

        st.markdown("### 📌 Your Saved Job Searches")

        if total_searches > 0:
            # Controls for filtering and pagination
            col1, col2 = st.columns([2, 1])

            with col1:
                platform_filter = st.selectbox(
                    "🔍 Filter by Platform",
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
                        value=1,
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
                    # Format timestamp - Convert UTC to IST
                    timestamp = datetime.datetime.strptime(search["timestamp"], "%Y-%m-%d %H:%M:%S.%f")
                    # Assume stored timestamp is in UTC, convert to IST
                    timestamp_utc = timestamp.replace(tzinfo=ZoneInfo('UTC'))
                    timestamp_ist = timestamp_utc.astimezone(ZoneInfo('Asia/Kolkata'))
                    formatted_time = timestamp_ist.strftime("%b %d, %Y at %I:%M %p IST")

                    # Platform styling
                    platform_lower = search["platform"].lower()
                    if "rapidapi" in platform_lower or "live" in platform_lower:
                        platform_color = "#00ff88"
                        platform_icon = "⚡"
                    elif platform_lower == "linkedin":
                        platform_color = "#0e76a8"
                        platform_icon = "🔵"
                    elif platform_lower == "naukri":
                        platform_color = "#ff5722"
                        platform_icon = "🏢"
                    elif "foundit" in platform_lower:
                        platform_color = "#7c4dff"
                        platform_icon = "🌐"
                    else:
                        platform_color = "#00c4cc"
                        platform_icon = "📄"

                    # Create columns for the card content and delete button
                    card_col, delete_col = st.columns([10, 1])

                    with card_col:
                        st.markdown(f"""
<div class="job-result-card" style="
    background: linear-gradient(135deg, #1a1a1a 0%, #2a2a2a 100%);
    padding: 20px;
    border-radius: 15px;
    margin-bottom: 15px;
    border-left: 4px solid {platform_color};
    box-shadow: 0 4px 16px rgba(0,0,0,0.2);
    position: relative;
    overflow: hidden;
">
    <div style="display: flex; justify-content: space-between; align-items: flex-start; margin-bottom: 15px;">
        <div>
            <div style="color: #ffffff; font-size: 16px; font-weight: 600; margin-bottom: 5px;">
                {platform_icon} {search['role']} in {search['location']}
            </div>
            <div style="color: {platform_color}; font-size: 14px; font-weight: 500;">
                {search['platform']}
            </div>
        </div>
        <div style="color: #888; font-size: 12px; text-align: right;">
            {formatted_time}
        </div>
    </div>
    <a href="{search['url']}" target="_blank" style="text-decoration: none;">
        <button class="job-button" style="
            background: linear-gradient(135deg, {platform_color} 0%, {platform_color}dd 100%);
            color: white;
            padding: 8px 16px;
            border: none;
            border-radius: 8px;
            font-size: 14px;
            font-weight: 500;
            cursor: pointer;
            transition: all 0.3s ease;
        ">
            🔗 View Jobs →
        </button>
    </a>
</div>
""", unsafe_allow_html=True)

                    with delete_col:
                        # Delete button
                        if st.button("🗑", key=f"delete_{search['id']}", help="Delete this search"):
                            delete_saved_job_search(search['id'])
                            st.rerun()
            else:
                # No results for the current filter
                st.markdown(f"""
<div style="
    background: linear-gradient(135deg, #1a1a1a 0%, #2a2a2a 100%);
    padding: 20px;
    border-radius: 15px;
    text-align: center;
    color: #888;
    border: 2px dashed #444;
">
    <div style="font-size: 24px; margin-bottom: 10px;">🔍</div>
    <div>No saved searches found for {platform_filter if platform_filter != 'All' else 'this page'}.</div>
</div>
""", unsafe_allow_html=True)
        else:
            # No saved searches at all
            st.markdown("""
<div style="
    background: linear-gradient(135deg, #1a1a1a 0%, #2a2a2a 100%);
    padding: 20px;
    border-radius: 15px;
    text-align: center;
    color: #888;
    border: 2px dashed #444;
">
    <div style="font-size: 24px; margin-bottom: 10px;">📭</div>
    <div>No saved job searches yet. Start searching to see your history here!</div>
</div>
""", unsafe_allow_html=True)

    # ============================================================
    # 📊 SEARCH ANALYTICS DASHBOARD  (v2 — IST time + Advanced UI)
    # ============================================================
    import pandas as pd
    import plotly.graph_objects as go
    import plotly.express as px

    # ── Plotly dark theme base config ────────────────────────────
    _PLOTLY_BASE = dict(
        paper_bgcolor="rgba(0,0,0,0)",
        plot_bgcolor="rgba(15,15,26,0.6)",
        font=dict(family="Inter, sans-serif", color="#cccccc", size=12),
        margin=dict(l=10, r=10, t=35, b=10),
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
    <div style='
        background: linear-gradient(135deg, #0a0a15 0%, #111128 50%, #0d1525 100%);
        padding: 32px 36px 24px 36px;
        border-radius: 24px;
        border: 1px solid rgba(0,196,204,0.25);
        margin-bottom: 28px;
        box-shadow: 0 12px 48px rgba(0,196,204,0.12), 0 0 0 1px rgba(124,77,255,0.1);
    '>
        <div style='display:flex; align-items:center; justify-content:center; gap:14px; margin-bottom:6px;'>
            <span style='font-size:32px;'>📊</span>
            <h2 style='
                background: linear-gradient(135deg, #00c4cc 0%, #7c4dff 60%, #f87171 100%);
                -webkit-background-clip: text;
                -webkit-text-fill-color: transparent;
                background-clip: text;
                font-size: 30px;
                font-weight: 800;
                margin: 0;
                letter-spacing: -0.5px;
            '>Search Analytics Dashboard</h2>
        </div>
        <p style='color: #555; text-align: center; margin: 0; font-size: 13px; letter-spacing: 0.3px;'>
            Real-time insights from your job search history · All times in <b style="color:#00c4cc">IST (UTC+5:30)</b>
        </p>
    </div>
    """, unsafe_allow_html=True)

    # ── Analytics Scope Toggle ────────────────────────────────────
    analytics_scope = st.radio(
        "📡 Analytics Scope",
        ["🙋 My Analytics", "🌐 Global Analytics"],
        horizontal=True,
        key="analytics_scope_toggle"
    )
    is_my_analytics = analytics_scope == "🙋 My Analytics"

    # ── Helper: fetch data from DB with IST conversion ───────────
    def fetch_analytics_data(scope_username=None):
        """
        Fetch user_jobs rows and convert timestamps to IST (UTC+5:30).
        Returns a pandas DataFrame or empty DataFrame on error.
        """
        try:
            conn = sqlite3.connect('resume_data.db')
            if scope_username:
                query = "SELECT role, location, platform, timestamp FROM user_jobs WHERE username = ?"
                df = pd.read_sql_query(query, conn, params=(scope_username,))
            else:
                query = "SELECT role, location, platform, timestamp FROM user_jobs"
                df = pd.read_sql_query(query, conn)
            conn.close()

            if not df.empty:
                # Parse as UTC then convert to IST (+05:30) — fixes 5-6 hour offset
                df['timestamp'] = pd.to_datetime(df['timestamp'], errors='coerce', utc=True)
                df = df.dropna(subset=['timestamp'])
                df['timestamp_ist'] = df['timestamp'].dt.tz_convert('Asia/Kolkata')
                df['date'] = df['timestamp_ist'].dt.date.astype(str)
                df['hour'] = df['timestamp_ist'].dt.hour          # IST hour (0-23)
                df['weekday'] = df['timestamp_ist'].dt.day_name() # IST weekday
            return df
        except Exception:
            return pd.DataFrame(columns=['role', 'location', 'platform', 'timestamp', 'date', 'hour', 'weekday'])

    # Determine scope
    current_user = st.session_state.username if hasattr(st.session_state, 'username') and st.session_state.username else None
    scope_user = current_user if is_my_analytics else None

    if is_my_analytics and not current_user:
        st.warning("⚠️ Please log in to view your personal analytics.")
    else:
        df_analytics = fetch_analytics_data(scope_username=scope_user)

        # ── Empty State Guard ──────────────────────────────────────
        if df_analytics.empty:
            st.markdown("""
            <div style='
                background: linear-gradient(135deg, #111120 0%, #1a1a30 100%);
                padding: 50px 40px;
                border-radius: 20px;
                text-align: center;
                border: 2px dashed #333;
                margin: 20px 0;
            '>
                <div style='font-size: 48px; margin-bottom: 16px;'>📭</div>
                <div style='font-size: 20px; font-weight: 700; color: #aaa; margin-bottom: 10px;'>No Data Yet</div>
                <div style='font-size: 14px; color: #666;'>Perform job searches to populate your analytics dashboard.</div>
            </div>
            """, unsafe_allow_html=True)
        else:
            # ── Compute KPIs ───────────────────────────────────────
            total_searches      = len(df_analytics)
            unique_roles        = df_analytics['role'].nunique()
            unique_locations    = df_analytics['location'].nunique()
            top_platform_series = df_analytics['platform'].value_counts()
            most_used_platform  = top_platform_series.index[0] if not top_platform_series.empty else "N/A"
            top_plat_count      = int(top_platform_series.iloc[0]) if not top_platform_series.empty else 0

            # ── KPI Cards — custom HTML (no truncation) ───────────
            st.markdown("<div style='height:8px'></div>", unsafe_allow_html=True)
            kpi1, kpi2, kpi3, kpi4 = st.columns(4)

            def _kpi_card(col, icon, label, value, sub, accent):
                col.markdown(f"""
                <div style='
                    background: linear-gradient(145deg, #111120 0%, #1a1a2e 100%);
                    border: 1px solid {accent}44;
                    border-radius: 18px;
                    padding: 22px 18px 18px 18px;
                    text-align: center;
                    box-shadow: 0 4px 24px {accent}18, inset 0 1px 0 rgba(255,255,255,0.04);
                    transition: all 0.3s ease;
                    min-height: 120px;
                '>
                    <div style='font-size:26px; margin-bottom:6px;'>{icon}</div>
                    <div style='color:{accent}; font-size:11px; font-weight:600; letter-spacing:1px; text-transform:uppercase; margin-bottom:4px;'>{label}</div>
                    <div style='color:#ffffff; font-size:26px; font-weight:800; line-height:1; margin-bottom:4px; word-break:break-word;'>{value}</div>
                    <div style='color:#555; font-size:11px;'>{sub}</div>
                </div>
                """, unsafe_allow_html=True)

            _kpi_card(kpi1, "🔎", "Total Searches",    f"{total_searches:,}",   "all recorded",              "#00c4cc")
            _kpi_card(kpi2, "💼", "Unique Roles",       f"{unique_roles:,}",     "distinct job titles",       "#7c4dff")
            _kpi_card(kpi3, "📍", "Unique Locations",   f"{unique_locations:,}", "distinct cities/regions",   "#34d399")
            _kpi_card(kpi4, "🏆", "Top Platform",       most_used_platform,      f"{top_plat_count} searches","#fbbf24")

            st.markdown("<div style='height:24px'></div>", unsafe_allow_html=True)

            # ── SECTION HEADER helper ─────────────────────────────
            def _section_header(icon, title, subtitle, accent):
                st.markdown(f"""
                <div style='
                    display:flex; align-items:center; gap:10px;
                    margin-bottom:12px; padding-bottom:10px;
                    border-bottom: 1px solid {accent}33;
                '>
                    <span style='font-size:20px;'>{icon}</span>
                    <div>
                        <div style='color:{accent}; font-size:15px; font-weight:700;'>{title}</div>
                        <div style='color:#555; font-size:11px;'>{subtitle}</div>
                    </div>
                </div>
                """, unsafe_allow_html=True)

            # ── ROW 1: Top Roles + Top Locations ─────────────────
            col_roles, col_locs = st.columns(2)

            with col_roles:
                _section_header("🎯", "Top 5 Most Searched Roles", "by search frequency", "#00c4cc")
                roles_orient = st.radio("Orientation", ["↔ Horizontal", "↕ Vertical"], index=0, horizontal=True, key="roles_orient")
                top_roles = (
                    df_analytics['role'].value_counts().head(5)
                    .reset_index()
                )
                top_roles.columns = ['Role', 'Count']
                top_roles = top_roles.sort_values('Count')
                if roles_orient == "↔ Horizontal":
                    fig_roles = go.Figure(go.Bar(
                        x=top_roles['Count'],
                        y=top_roles['Role'],
                        orientation='h',
                        marker=dict(
                            color=top_roles['Count'],
                            colorscale=[[0, '#004d52'], [0.5, '#00a0a8'], [1, '#00c4cc']],
                            line=dict(color='rgba(0,196,204,0.4)', width=1),
                        ),
                        text=top_roles['Count'],
                        textposition='outside',
                        textfont=dict(color='#00c4cc', size=12, family='Inter'),
                        hovertemplate='<b>%{y}</b><br>Searches: %{x}<extra></extra>',
                    ))
                    fig_roles.update_layout(
                        **_PLOTLY_BASE, height=260, showlegend=False,
                        xaxis_title=None, yaxis_title=None,
                        xaxis=dict(**_XAXIS, showgrid=True),
                        yaxis=dict(**_YAXIS, showgrid=False),
                    )
                else:
                    fig_roles = go.Figure(go.Bar(
                        x=top_roles['Role'],
                        y=top_roles['Count'],
                        orientation='v',
                        marker=dict(
                            color=top_roles['Count'],
                            colorscale=[[0, '#004d52'], [0.5, '#00a0a8'], [1, '#00c4cc']],
                            line=dict(color='rgba(0,196,204,0.4)', width=1),
                        ),
                        text=top_roles['Count'],
                        textposition='outside',
                        textfont=dict(color='#00c4cc', size=12, family='Inter'),
                        hovertemplate='<b>%{x}</b><br>Searches: %{y}<extra></extra>',
                    ))
                    fig_roles.update_layout(
                        **_PLOTLY_BASE, height=260, showlegend=False,
                        xaxis_title=None, yaxis_title=None,
                        xaxis=dict(**_XAXIS, tickangle=-25),
                        yaxis=dict(**_YAXIS, showgrid=True),
                    )
                st.plotly_chart(fig_roles, use_container_width=True, config={
                    "displayModeBar": True,
                    "displaylogo": False,
                    "modeBarButtonsToRemove": ["select2d", "lasso2d", "autoScale2d"],
                    "toImageButtonOptions": {"format": "png", "filename": "top_roles"},
                    "scrollZoom": False,
                })

            with col_locs:
                _section_header("📍", "Top 5 Most Searched Locations", "by search frequency", "#7c4dff")
                locs_orient = st.radio("Orientation", ["↔ Horizontal", "↕ Vertical"], index=0, horizontal=True, key="locs_orient")
                top_locs = (
                    df_analytics['location'].value_counts().head(5)
                    .reset_index()
                )
                top_locs.columns = ['Location', 'Count']
                top_locs = top_locs.sort_values('Count')
                if locs_orient == "↔ Horizontal":
                    fig_locs = go.Figure(go.Bar(
                        x=top_locs['Count'],
                        y=top_locs['Location'],
                        orientation='h',
                        marker=dict(
                            color=top_locs['Count'],
                            colorscale=[[0, '#1e0052'], [0.5, '#5c29c0'], [1, '#7c4dff']],
                            line=dict(color='rgba(124,77,255,0.4)', width=1),
                        ),
                        text=top_locs['Count'],
                        textposition='outside',
                        textfont=dict(color='#7c4dff', size=12, family='Inter'),
                        hovertemplate='<b>%{y}</b><br>Searches: %{x}<extra></extra>',
                    ))
                    fig_locs.update_layout(
                        **_PLOTLY_BASE, height=260, showlegend=False,
                        xaxis_title=None, yaxis_title=None,
                        xaxis=dict(**_XAXIS, showgrid=True),
                        yaxis=dict(**_YAXIS, showgrid=False),
                    )
                else:
                    fig_locs = go.Figure(go.Bar(
                        x=top_locs['Location'],
                        y=top_locs['Count'],
                        orientation='v',
                        marker=dict(
                            color=top_locs['Count'],
                            colorscale=[[0, '#1e0052'], [0.5, '#5c29c0'], [1, '#7c4dff']],
                            line=dict(color='rgba(124,77,255,0.4)', width=1),
                        ),
                        text=top_locs['Count'],
                        textposition='outside',
                        textfont=dict(color='#7c4dff', size=12, family='Inter'),
                        hovertemplate='<b>%{x}</b><br>Searches: %{y}<extra></extra>',
                    ))
                    fig_locs.update_layout(
                        **_PLOTLY_BASE, height=260, showlegend=False,
                        xaxis_title=None, yaxis_title=None,
                        xaxis=dict(**_XAXIS, tickangle=-25),
                        yaxis=dict(**_YAXIS, showgrid=True),
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
                _section_header("🏢", "Platform Usage Distribution", "share of all searches", "#fbbf24")
                plat_orient = st.radio("Orientation", ["↕ Vertical", "↔ Horizontal"], index=0, horizontal=True, key="plat_orient")
                plat_dist = (
                    df_analytics.groupby('platform').size()
                    .reset_index(name='Count')
                    .sort_values('Count', ascending=False)
                )
                if plat_orient == "↕ Vertical":
                    fig_plat = go.Figure(go.Bar(
                        x=plat_dist['platform'],
                        y=plat_dist['Count'],
                        orientation='v',
                        marker=dict(
                            color=plat_dist['Count'],
                            colorscale=[[0,'#3d2e00'],[0.5,'#c0900e'],[1,'#fbbf24']],
                            line=dict(color='rgba(251,191,36,0.4)', width=1),
                        ),
                        text=plat_dist['Count'],
                        textposition='outside',
                        textfont=dict(color='#fbbf24', size=11, family='Inter'),
                        hovertemplate='<b>%{x}</b><br>Searches: %{y}<extra></extra>',
                    ))
                    fig_plat.update_layout(
                        **_PLOTLY_BASE, height=270, showlegend=False,
                        xaxis=dict(**_XAXIS, tickangle=-25),
                        yaxis=dict(**_YAXIS),
                        bargap=0.3,
                    )
                else:
                    plat_dist_h = plat_dist.sort_values('Count')
                    fig_plat = go.Figure(go.Bar(
                        x=plat_dist_h['Count'],
                        y=plat_dist_h['platform'],
                        orientation='h',
                        marker=dict(
                            color=plat_dist_h['Count'],
                            colorscale=[[0,'#3d2e00'],[0.5,'#c0900e'],[1,'#fbbf24']],
                            line=dict(color='rgba(251,191,36,0.4)', width=1),
                        ),
                        text=plat_dist_h['Count'],
                        textposition='outside',
                        textfont=dict(color='#fbbf24', size=11, family='Inter'),
                        hovertemplate='<b>%{y}</b><br>Searches: %{x}<extra></extra>',
                    ))
                    fig_plat.update_layout(
                        **_PLOTLY_BASE, height=270, showlegend=False,
                        xaxis=dict(**_XAXIS, showgrid=True),
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
                _section_header("📈", "Search Trend Over Time (IST)", "daily activity", "#34d399")
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
            _section_header("🕐", "Peak Search Hour — IST (0–23 Distribution)", "when you search most — converted to Indian Standard Time", "#f87171")
            hour_orient = st.radio("Orientation", ["↕ Vertical", "↔ Horizontal"], index=0, horizontal=True, key="hour_orient")

            # Build full 0-23 with IST hours
            hour_counts = df_analytics.groupby('hour').size().reset_index(name='Searches')
            all_hours   = pd.DataFrame({'hour': range(24)})
            hour_dist   = (
                all_hours.merge(hour_counts, on='hour', how='left').fillna(0).astype({'Searches': int})
            )
            hour_dist['Label'] = hour_dist['hour'].apply(lambda h: f"{h:02d}:00")
            peak_hour = int(hour_dist.loc[hour_dist['Searches'].idxmax(), 'hour'])

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
                ))
                # Annotation for peak
                if hour_dist['Searches'].max() > 0:
                    fig_hour.add_annotation(
                        x=f"{peak_hour:02d}:00",
                        y=hour_dist['Searches'].max(),
                        text=f"⚡ Peak: {peak_hour:02d}:00 IST",
                        showarrow=True, arrowhead=2, arrowcolor='#f87171',
                        font=dict(color='#f87171', size=12, family='Inter'),
                        bgcolor='rgba(248,113,113,0.15)',
                        bordercolor='#f87171', borderwidth=1, borderpad=5, yshift=10,
                    )
                fig_hour.update_layout(
                    **_PLOTLY_BASE, height=290, showlegend=False, bargap=0.15,
                    xaxis=dict(**{**_XAXIS, "tickfont": dict(size=10, color="#999"), "tickangle": -45}),
                    yaxis=dict(**_YAXIS),
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
                ))
                if hour_dist['Searches'].max() > 0:
                    fig_hour.add_annotation(
                        y=f"{peak_hour:02d}:00",
                        x=hour_dist['Searches'].max(),
                        text=f"⚡ Peak: {peak_hour:02d}:00 IST",
                        showarrow=True, arrowhead=2, arrowcolor='#f87171',
                        font=dict(color='#f87171', size=12, family='Inter'),
                        bgcolor='rgba(248,113,113,0.15)',
                        bordercolor='#f87171', borderwidth=1, borderpad=5, xshift=10,
                    )
                fig_hour.update_layout(
                    **_PLOTLY_BASE, height=600, showlegend=False, bargap=0.15,
                    xaxis=dict(**_XAXIS, showgrid=True),
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
            ist_now = datetime.datetime.now(ZoneInfo('Asia/Kolkata')).strftime("%b %d, %Y %I:%M %p IST")
            st.markdown(f"""
            <div style='
                color: #444;
                font-size: 11px;
                text-align: right;
                margin-top: 12px;
                padding-top: 10px;
                border-top: 1px solid #1e1e2e;
            '>
                {total_searches:,} records · {scope_label} · Updated {ist_now} · resume_data.db
            </div>
            """, unsafe_allow_html=True)

    # ============================================================
    # END OF SEARCH ANALYTICS DASHBOARD
    # ============================================================

    # Enhanced CSS with advanced animations and effects
    st.markdown("""
    <style>
    @import url('https://fonts.googleapis.com/css2?family=Inter:wght@300;400;500;600;700&display=swap');

    /* Global Enhancements */
    .stApp {
        font-family: 'Inter', sans-serif;
    }

    /* Advanced Glow Animation */
    @keyframes glow {
        0% {
            box-shadow: 0 0 5px rgba(255,255,255,0.1), 0 0 10px rgba(0,255,255,0.1), 0 0 15px rgba(0,255,255,0.1);
        }
        50% {
            box-shadow: 0 0 10px rgba(255,255,255,0.2), 0 0 20px rgba(0,255,255,0.4), 0 0 30px rgba(0,255,255,0.3);
        }
        100% {
            box-shadow: 0 0 5px rgba(255,255,255,0.1), 0 0 10px rgba(0,255,255,0.1), 0 0 15px rgba(0,255,255,0.1);
        }
    }

    /* Shimmer Effect */
    @keyframes shimmer {
        0% {
            transform: translateX(-100%);
        }
        100% {
            transform: translateX(100%);
        }
    }

    .shimmer-overlay {
        position: absolute;
        top: 0;
        left: 0;
        width: 100%;
        height: 100%;
        background: linear-gradient(90deg, transparent, rgba(255,255,255,0.05), transparent);
        transform: translateX(-100%);
        animation: shimmer 3s infinite;
        z-index: 1;
    }

    /* Floating Animation */
    @keyframes float {
        0%, 100% {
            transform: translateY(0px);
        }
        50% {
            transform: translateY(-5px);
        }
    }

    /* Pulse Animation */
    @keyframes pulse {
        0%, 100% {
            transform: scale(1);
        }
        50% {
            transform: scale(1.02);
        }
    }

    /* Enhanced Company Cards */
    .company-card {
        background: linear-gradient(135deg, #1e1e1e 0%, #2d2d2d 100%);
        color: #ffffff;
        border-radius: 20px;
        padding: 25px;
        margin-bottom: 25px;
        box-shadow: 0 8px 32px rgba(0,0,0,0.3);
        transition: all 0.4s cubic-bezier(0.175, 0.885, 0.32, 1.275);
        cursor: pointer;
        text-decoration: none;
        display: block;
        animation: glow 4s infinite alternate, float 6s ease-in-out infinite;
        position: relative;
        overflow: hidden;
        border: 1px solid rgba(255,255,255,0.1);
    }

    .company-card::before {
        content: '';
        position: absolute;
        top: 0;
        left: 0;
        right: 0;
        bottom: 0;
        background: linear-gradient(135deg, rgba(0,255,255,0.1) 0%, rgba(255,0,255,0.1) 100%);
        opacity: 0;
        transition: opacity 0.3s ease;
        z-index: 1;
    }

    .company-card:hover::before {
        opacity: 1;
    }

    .company-card:hover {
        transform: translateY(-8px) scale(1.02);
        box-shadow: 0 20px 40px rgba(0,0,0,0.4), 0 0 30px rgba(0, 255, 255, 0.3);
        border-color: rgba(0,255,255,0.5);
    }

    /* Job Result Cards */
    .job-result-card:hover {
        transform: translateY(-5px) scale(1.01);
        box-shadow: 0 15px 40px rgba(0,0,0,0.4) !important;
    }

    /* Enhanced Buttons */
    .job-button::before {
        content: '';
        position: absolute;
        top: 0;
        left: -100%;
        width: 100%;
        height: 100%;
        background: linear-gradient(90deg, transparent, rgba(255,255,255,0.2), transparent);
        transition: left 0.5s;
        z-index: 1;
    }

    .job-button:hover::before {
        left: 100%;
    }

    .job-button:hover {
        transform: translateY(-2px);
        box-shadow: 0 8px 25px rgba(0,0,0,0.3);
    }

    /* Enhanced Pills */
    .pill {
        display: inline-block;
        background: linear-gradient(135deg, #333 0%, #444 100%);
        padding: 8px 16px;
        border-radius: 25px;
        margin: 6px 8px 0 0;
        font-size: 13px;
        font-weight: 500;
        border: 1px solid rgba(255,255,255,0.1);
        transition: all 0.3s ease;
        position: relative;
        overflow: hidden;
    }

    .pill::before {
        content: '';
        position: absolute;
        top: 0;
        left: 0;
        right: 0;
        bottom: 0;
        background: linear-gradient(135deg, rgba(0,255,255,0.2) 0%, rgba(255,0,255,0.2) 100%);
        opacity: 0;
        transition: opacity 0.3s ease;
    }

    .pill:hover::before {
        opacity: 1;
    }

    .pill:hover {
        transform: translateY(-2px);
        box-shadow: 0 4px 12px rgba(0,255,255,0.3);
    }

    /* Enhanced Title Headers */
    .title-header {
        color: #ffffff;
        font-size: 28px;
        margin-top: 50px;
        margin-bottom: 30px;
        font-weight: 700;
        text-align: center;
        background: linear-gradient(135deg, #00c4cc 0%, #7c4dff 100%);
        -webkit-background-clip: text;
        -webkit-text-fill-color: transparent;
        background-clip: text;
        position: relative;
        animation: pulse 3s infinite;
    }

    .title-header::after {
        content: '';
        position: absolute;
        bottom: -10px;
        left: 50%;
        transform: translateX(-50%);
        width: 60px;
        height: 3px;
        background: linear-gradient(135deg, #00c4cc 0%, #7c4dff 100%);
        border-radius: 2px;
    }

    /* Company Logo Enhancement */
    .company-logo {
        font-size: 28px;
        margin-right: 12px;
        filter: drop-shadow(0 0 8px rgba(255,255,255,0.3));
        animation: float 4s ease-in-out infinite;
    }

    .company-header {
        font-size: 24px;
        font-weight: 700;
        display: flex;
        align-items: center;
        margin-bottom: 15px;
        position: relative;
        z-index: 2;
    }

    /* Responsive Enhancements */
    @media (max-width: 768px) {
        .company-card, .job-result-card {
            padding: 20px;
            margin-bottom: 20px;
        }

        .title-header {
            font-size: 24px;
        }

        .company-header {
            font-size: 20px;
        }
    }

    /* Scrollbar Styling */
    ::-webkit-scrollbar {
        width: 8px;
    }

    ::-webkit-scrollbar-track {
        background: #1e1e1e;
    }

    ::-webkit-scrollbar-thumb {
        background: linear-gradient(135deg, #00c4cc 0%, #7c4dff 100%);
        border-radius: 4px;
    }

    ::-webkit-scrollbar-thumb:hover {
        background: linear-gradient(135deg, #26d0ce 0%, #9c64ff 100%);
    }
    </style>
    """, unsafe_allow_html=True)

    # ---------- Company Lookup by Domain ----------


    # ---------- Featured Companies ----------
    st.markdown("### <div class='title-header'>🏢 Featured Companies</div>", unsafe_allow_html=True)

    selected_category = st.selectbox("📂 Browse Featured Companies By Category", ["All", "tech", "indian_tech", "global_corps"])
    companies_to_show = get_featured_companies() if selected_category == "All" else get_featured_companies(selected_category)

    for company in companies_to_show:
        category_tags = ''.join([f"<span class='pill'>{cat}</span>" for cat in company['categories']])
        st.markdown(f"""
        <a href="{company['careers_url']}" class="company-card" target="_blank">
            <div class="company-header">
                <span class="company-logo">{company.get('emoji', '🏢')}</span>
                {company['name']}
            </div>
            <p style="margin-bottom: 15px; line-height: 1.6; position: relative; z-index: 2;">{company['description']}</p>
            <div style="position: relative; z-index: 2;">{category_tags}</div>
        </a>
        """, unsafe_allow_html=True)

    # ---------- Market Insights ----------
    st.markdown("### <div class='title-header'>📈 Job Market Trends</div>", unsafe_allow_html=True)
    col1, col2 = st.columns(2)

    with col1:
        st.markdown("#### <div style='color: #00c4cc; font-size: 20px; font-weight: 600; margin-bottom: 20px;'>🚀 Trending Skills</div>", unsafe_allow_html=True)
        for skill in JOB_MARKET_INSIGHTS["trending_skills"]:
            st.markdown(f"""
            <div class="company-card">
                <h4 style="color: #00c4cc; margin-bottom: 10px; position: relative; z-index: 2;">🔧 {skill['name']}</h4>
                <p style="position: relative; z-index: 2;">📈 Growth Rate: <span style="color: #4ade80; font-weight: 600;">{skill['growth']}</span></p>
            </div>
            """, unsafe_allow_html=True)

    with col2:
        st.markdown("#### <div style='color: #7c4dff; font-size: 20px; font-weight: 600; margin-bottom: 20px;'>🌍 Top Job Locations</div>", unsafe_allow_html=True)
        for loc in JOB_MARKET_INSIGHTS["top_locations"]:
            st.markdown(f"""
            <div class="company-card">
                <h4 style="color: #7c4dff; margin-bottom: 10px; position: relative; z-index: 2;">📍 {loc['name']}</h4>
                <p style="position: relative; z-index: 2;">💼 Openings: <span style="color: #fbbf24; font-weight: 600;">{loc['jobs']}</span></p>
            </div>
            """, unsafe_allow_html=True)

    # ---------- Salary Insights ----------
    st.markdown("### <div class='title-header'>💰 Salary Insights</div>", unsafe_allow_html=True)
    for role in JOB_MARKET_INSIGHTS["salary_insights"]:
        st.markdown(f"""
        <div class="company-card">
            <h4 style="color: #10b981; margin-bottom: 10px; position: relative; z-index: 2;">💼 {role['role']}</h4>
            <p style="margin-bottom: 8px; position: relative; z-index: 2;">📅 Experience: <span style="color: #60a5fa; font-weight: 500;">{role['experience']}</span></p>
            <p style="position: relative; z-index: 2;">💵 Salary Range: <span style="color: #34d399; font-weight: 600;">{role['range']}</span></p>
        </div>
        """, unsafe_allow_html=True)



            with st.expander("📋 See All Your Interview Records"):
                # Exclude raw DB 'id' — inject a clean per-user sequential # instead
                display_cols = [c for c in ['role', 'domain', 'avg_score', 'weighted_score', 'knowledge_avg', 'communication_avg',
                                             'relevance_avg', 'difficulty', 'interview_mode', 'total_questions', 'duration_seconds',
                                             'follow_up_count', 'depth_score', 'behavior_class', 'completed_on']
                                if c in df.columns]
                rename_map = {
                    'avg_score': 'Score', 'weighted_score': 'Adjusted Score', 'knowledge_avg': 'Knowledge',
                    'communication_avg': 'Communication', 'relevance_avg': 'Relevance',
                    'difficulty': 'Level', 'interview_mode': 'Format',
                    'total_questions': 'Questions', 'duration_seconds': 'Duration (s)',
                    'completed_on': 'Date', 'role': 'Role', 'domain': 'Career Area',
                    'follow_up_count': 'Follow-ups', 'depth_score': 'Depth', 'behavior_class': 'Style'
                }
                display_df = df[display_cols].rename(columns=rename_map)
                # Per-user sequential numbering: always starts at 1 regardless of DB id
                display_df.insert(0, '#', range(1, len(display_df) + 1))

                # Build enhanced HTML table with score badges, trend arrows, best-row highlight
                _score_col = 'Score'
                _scores_list_disp = display_df[_score_col].tolist() if _score_col in display_df.columns else []
                _best_score_val = max(_scores_list_disp) if _scores_list_disp else None

                def _badge(v):
                    if pd.isna(v): return '<span style="color:#666">N/A</span>'
                    v = float(v)
                    if v >= 8.5: return f'<span class="badge-excellent">{v:.1f}</span>'
                    elif v >= 7.0: return f'<span class="badge-good">{v:.1f}</span>'
                    elif v >= 5.5: return f'<span class="badge-average">{v:.1f}</span>'
                    elif v >= 4.0: return f'<span class="badge-weak">{v:.1f}</span>'
                    else: return f'<span class="badge-poor">{v:.1f}</span>'

                def _trend_arrow(current, prev):
                    if prev is None or pd.isna(prev): return ''
                    delta = float(current) - float(prev)
                    if delta > 0.3: return f'<span style="color:#00e676;font-size:14px;" title="+{delta:.1f}">▲</span>'
                    elif delta < -0.3: return f'<span style="color:#f44336;font-size:14px;" title="{delta:.1f}">▼</span>'
                    else: return f'<span style="color:#ffcc02;font-size:14px;" title="~{delta:.1f}">●</span>'

                _th_style = "padding:9px 12px;color:#00c3ff;text-align:left;font-size:11px;text-transform:uppercase;letter-spacing:0.07em;border-bottom:1px solid rgba(0,195,255,0.3);white-space:nowrap;"
                _td_style = "padding:8px 12px;color:#e0e0e0;font-size:13px;white-space:nowrap;"

                _headers = list(display_df.columns)
                _header_row = "".join([f'<th style="{_th_style}">{h}</th>' for h in _headers]) + f'<th style="{_th_style}">Trend</th>'

                _body_rows = ""
                _prev_score = None
                for i, row in display_df.iterrows():
                    _cur_score = row.get('Score', None)
                    _is_best = (not pd.isna(_cur_score) and not pd.isna(_best_score_val) and float(_cur_score) == float(_best_score_val))
                    _row_bg = 'background:rgba(0,230,118,0.10);' if _is_best else ('background:rgba(255,255,255,0.02);' if i % 2 == 0 else '')
                    _cells = ""
                    for col_name in _headers:
                        val = row[col_name]
                        if col_name in ('Score', 'Adjusted Score', 'Knowledge', 'Communication', 'Relevance'):
                            _cells += f'<td style="{_td_style}text-align:center;">{_badge(val)}</td>'
                        elif col_name == 'Level':
                            _lc = {'Easy':'#69f0ae','Medium':'#ffcc02','Hard':'#f44336'}.get(str(val), '#aaa')
                            _cells += f'<td style="{_td_style}"><span style="color:{_lc};font-weight:600;">{val}</span></td>'
                        elif col_name == '#':
                            _crown = ' 🏆' if _is_best else ''
                            _cells += f'<td style="{_td_style}font-weight:600;">{val}{_crown}</td>'
                        else:
                            _disp_val = str(val) if not pd.isna(val) else '—'
                            _cells += f'<td style="{_td_style}">{_disp_val}</td>'
                    _arrow = _trend_arrow(_cur_score, _prev_score) if not pd.isna(_cur_score) else ''
                    _cells += f'<td style="{_td_style}text-align:center;">{_arrow}</td>'
                    _body_rows += f'<tr style="{_row_bg}">{_cells}</tr>'
                    if not pd.isna(_cur_score):
                        _prev_score = _cur_score

                st.markdown(f"""
                <div style="overflow-x:auto;border-radius:10px;border:1px solid rgba(0,195,255,0.2);margin-top:8px;">
                <table style="width:100%;border-collapse:collapse;background:rgba(15,20,25,0.85);">
                  <thead><tr>{_header_row}</tr></thead>
                  <tbody>{_body_rows}</tbody>
                </table></div>
                <p style="color:rgba(255,255,255,0.4);font-size:11px;margin-top:6px;">
                  🏆 Gold rows = personal best &nbsp;|&nbsp; ▲ improved &nbsp;▼ dipped &nbsp;● steady vs previous interview
                </p>
                """, unsafe_allow_html=True)







if tab5:
	with tab5:
		import sqlite3
		import pandas as pd
		import matplotlib.pyplot as plt
		import numpy as np
		import streamlit as st
		from datetime import datetime, timedelta
		import plotly.express as px
		import plotly.graph_objects as go
		from plotly.subplots import make_subplots
		import time
		import glob, os

		# Import enhanced database manager functions
		from db_manager import (
			get_top_domains_by_score,
			get_resume_count_by_day,
			get_average_ats_by_domain,
			get_domain_distribution,
			get_bias_distribution,
			filter_candidates_by_date,
			delete_candidate_by_id,
			get_all_candidates,
			get_candidate_by_id,
			get_domain_performance_stats,
			get_daily_ats_stats,
			get_flagged_candidates,
			get_database_stats,
			analyze_domain_transitions,
			export_to_csv,
			cleanup_old_records,
			DatabaseManager
		)

		# Initialize enhanced database manager
		@st.cache_resource
		def get_db_manager():
			return DatabaseManager()

		db_manager = get_db_manager()

		def create_enhanced_pie_chart(df, values_col, labels_col, title):
			"""Create an enhanced pie chart with better styling"""
			fig = px.pie(
				df, 
				values=values_col, 
				names=labels_col,
				title=title,
				color_discrete_sequence=px.colors.qualitative.Set3
			)
			fig.update_traces(
				textposition='inside', 
				textinfo='percent+label',
				hovertemplate='<b>%{label}</b><br>Count: %{value}<br>Percentage: %{percent}<extra></extra>'
			)
			fig.update_layout(
				showlegend=True,
				legend=dict(orientation="v", yanchor="middle", y=0.5, xanchor="left", x=1.01),
				margin=dict(t=50, b=50, l=50, r=150)
			)
			return fig

		def create_enhanced_bar_chart(df, x_col, y_col, title, orientation='v'):
			"""Create enhanced bar chart with better interactivity"""
			if orientation == 'v':
				fig = px.bar(df, x=x_col, y=y_col, title=title, 
							color=y_col, color_continuous_scale='viridis')
				fig.update_xaxes(tickangle=45)
			else:
				fig = px.bar(df, x=y_col, y=x_col, title=title, orientation='h',
							color=y_col, color_continuous_scale='viridis')
			
			fig.update_traces(
				hovertemplate='<b>%{y if orientation == "v" else x}</b><br>Value: %{x if orientation == "v" else y}<extra></extra>'
			)
			fig.update_layout(showlegend=False, margin=dict(t=50, b=50, l=50, r=50))
			return fig

		def load_domain_distribution():
			"""Enhanced domain distribution loading with error handling"""
			try:
				df = get_domain_distribution()
				if not df.empty:
					df = df.sort_values(by="count", ascending=False).reset_index(drop=True)
					return df
			except Exception as e:
				st.error(f"Error loading domain distribution: {e}")
			return pd.DataFrame()

		# Enhanced Data Loading with Caching
		@st.cache_data(ttl=300)  # Cache for 5 minutes
		def load_all_candidates():
			try:
				return get_all_candidates()
			except Exception as e:
				st.error(f"Error loading candidates: {e}")
				return pd.DataFrame()

		# -------- Glassmorphism Styles with Shimmer --------
		st.markdown("""
		<style>
		.glass-box {
			background: rgba(10, 20, 40, 0.55);
			border-radius: 18px;
			padding: 2rem;
			backdrop-filter: blur(14px);
			border: 1px solid rgba(0, 200, 255, 0.35);
			box-shadow: 0 8px 32px rgba(0, 200, 255, 0.25);
			position: relative;
			overflow: hidden;
			text-align: center;
			margin-bottom: 2rem;
		}
		.glass-box::before {
			content: "";
			position: absolute;
			top: -50%;
			left: -50%;
			width: 200%;
			height: 200%;
			background: linear-gradient(
				120deg,
				rgba(255,255,255,0.15) 0%,
				rgba(255,255,255,0.05) 40%,
				transparent 60%
			);
			transform: rotate(25deg);
			animation: shimmer 6s infinite;
		}
		@keyframes shimmer {
			0% { top: -50%; left: -50%; }
			50% { top: 100%; left: 100%; }
			100% { top: -50%; left: -50%; }
		}
		.glass-box h1, .glass-box h2 {
			color: #4da6ff;
			text-shadow: 0 0 12px rgba(0,200,255,0.7);
			margin: 0 0 0.5rem 0;
			font-weight: 600;
		}
		.glass-box p {
			color: #cce6ff;
			margin: 0;
			font-size: 0.95rem;
		}

		/* Glassy input fields */
		.stTextInput > div > div > input {
			background: rgba(255, 255, 255, 0.08) !important;
			border: 1px solid rgba(0, 200, 255, 0.3) !important;
			border-radius: 12px !important;
			padding: 10px !important;
			color: #e6f7ff !important;
			font-weight: 500 !important;
			backdrop-filter: blur(10px) !important;
		}
		.stTextInput > div > div > input:focus {
			border: 1px solid rgba(0, 200, 255, 0.8) !important;
			box-shadow: 0 0 12px rgba(0, 200, 255, 0.6) !important;
			outline: none !important;
		}

		/* Glassy button */
		.stButton > button {
			background: rgba(0, 200, 255, 0.15);
			border: 1px solid rgba(0, 200, 255, 0.4);
			border-radius: 12px;
			color: #e6f7ff;
			padding: 0.6rem 1.2rem;
			font-weight: bold;
			backdrop-filter: blur(8px);
			transition: all 0.3s ease;
		}
		.stButton > button:hover {
			background: rgba(0, 200, 255, 0.3);
			box-shadow: 0 0 16px rgba(0, 200, 255, 0.7);
			transform: translateY(-2px);
		}
		</style>
		""", unsafe_allow_html=True)

		# ---------------- Enhanced Authentication System ----------------
		if "admin_logged_in" not in st.session_state:
			st.session_state.admin_logged_in = False

		if not st.session_state.admin_logged_in:
			st.markdown("""
			<div class="glass-box">
				<h2>🔐 Admin Authentication Required</h2>
				<p>Please enter your email and password to access the admin dashboard</p>
			</div>
			""", unsafe_allow_html=True)
			
			col1, col2, col3 = st.columns([1, 2, 1])
			with col2:
				email = st.text_input("📧 Enter Admin Email", placeholder="Enter email...")
				password = st.text_input("🔑 Enter Admin Password", type="password", placeholder="Enter password...")
				login_clicked = st.button("🚀 Login", use_container_width=True)

				if login_clicked:
					valid_email = "admin@example.com"
					valid_password = "Swagato@2002"

					if email == valid_email and password == valid_password:
						st.session_state.admin_logged_in = True
						st.success("✅ Authentication successful! Redirecting to dashboard...")
						st.rerun()
					else:
						msg_placeholder = st.empty()
						msg_placeholder.markdown("""
							<div style='
								background-color: #ff4d4d;
								color: white;
								padding: 10px 15px;
								border-radius: 10px;
								text-align: center;
								animation: slideDown 0.5s ease-in-out;
							'>❌ Invalid credentials. Please try again.</div>
							<style>
							@keyframes slideDown {
								0% {transform: translateY(-50px); opacity: 0;}
								100% {transform: translateY(0); opacity: 1;}
							}
							</style>
						""", unsafe_allow_html=True)
						time.sleep(3)
						msg_placeholder.empty()

			st.stop()

		# ---------------- Enhanced Header with Database Stats ----------------
		st.markdown("""
		<div class="glass-box">
			<h1>🛡️ Enhanced Admin Database Panel</h1>
			<p>Advanced Resume Analysis System Dashboard</p>
		</div>
		""", unsafe_allow_html=True)

		# Enhanced Control Panel
		col1, col2, col3, col4 = st.columns(4)
		with col1:
			if st.button("🔄 Refresh All Data", use_container_width=True):
				st.cache_data.clear()
				st.rerun()
		with col2:
			if st.button("📊 Database Stats", use_container_width=True):
				st.session_state.show_db_stats = True
		with col3:
			if st.button("🧹 Cleanup Old Records", use_container_width=True):
				st.session_state.show_cleanup = True
		with col4:
			if st.button("🚪 Secure Logout", use_container_width=True):
				st.session_state.admin_logged_in = False
				st.success("👋 Logged out successfully.")
				st.rerun()

		# Database Statistics Panel
		if st.session_state.get('show_db_stats', False):
			with st.expander("📈 Database Statistics", expanded=True):
				try:
					stats = get_database_stats()
					if stats:
						col1, col2, col3, col4 = st.columns(4)
						with col1:
							st.metric("Total Candidates", stats.get('total_candidates', 0))
						with col2:
							st.metric("Average ATS Score", f"{stats.get('avg_ats_score', 0):.2f}")
						with col3:
							st.metric("Unique Domains", stats.get('unique_domains', 0))
						with col4:
							st.metric("Database Size", f"{stats.get('database_size_mb', 0):.2f} MB")
						
						col5, col6 = st.columns(2)
						with col5:
							st.metric("Earliest Record", stats.get('earliest_date', 'N/A'))
						with col6:
							st.metric("Latest Record", stats.get('latest_date', 'N/A'))
				except Exception as e:
					st.error(f"Error loading database statistics: {e}")

		# Cleanup Panel
		if st.session_state.get('show_cleanup', False):
			with st.expander("🧹 Database Cleanup", expanded=True):
				days_to_keep = st.slider("Days to Keep", 30, 730, 365)
				if st.button("⚠️ Cleanup Old Records"):
					try:
						deleted_count = cleanup_old_records(days_to_keep)
						if deleted_count > 0:
							st.success(f"✅ Cleaned up {deleted_count} old records")
						else:
							st.info("ℹ️ No old records found to cleanup")
					except Exception as e:
						st.error(f"Error during cleanup: {e}")

		st.markdown("<hr style='border-top: 2px solid #bbb; margin: 2rem 0;'>", unsafe_allow_html=True)

		df = load_all_candidates()

		# Enhanced Search and Filter Section
		st.markdown("### 🔍 Advanced Search & Filters")
		
		col1, col2 = st.columns(2)
		with col1:
			search = st.text_input("🔍 Search by Candidate Name", placeholder="Enter candidate name...")
			if search:
				df = df[df["candidate_name"].str.contains(search, case=False, na=False)]
		
		with col2:
			domain_filter = st.selectbox("🏢 Filter by Domain", 
									options=["All Domains"] + list(df["domain"].unique()) if not df.empty else ["All Domains"])
			if domain_filter != "All Domains":
				df = df[df["domain"] == domain_filter]

		# Enhanced Date Filter
		st.markdown("#### 📅 Date Range Filter")
		col1, col2, col3 = st.columns(3)
		with col1:
			start_date = st.date_input("📅 Start Date", value=datetime.now() - timedelta(days=30))
		with col2:
			end_date = st.date_input("📅 End Date", value=datetime.now())
		with col3:
			if st.button("🎯 Apply Filters", use_container_width=True):
				try:
					df = filter_candidates_by_date(str(start_date), str(end_date))
					if domain_filter != "All Domains":
						df = df[df["domain"] == domain_filter]
					if search:
						df = df[df["candidate_name"].str.contains(search, case=False, na=False)]
					st.success(f"✅ Filters applied. Found {len(df)} candidates.")
				except Exception as e:
					st.error(f"Error applying filters: {e}")

		# Enhanced Candidates Display
		if df.empty:
			st.info("ℹ️ No candidate data available with current filters.")
		else:
			st.markdown(f"### 📋 Candidates Overview ({len(df)} records)")
			
			# Enhanced metrics
			col1, col2, col3, col4 = st.columns(4)
			with col1:
				st.metric("Total Candidates", len(df))
			with col2:
				st.metric("Avg ATS Score", f"{df['ats_score'].mean():.2f}")
			with col3:
				st.metric("Avg Bias Score", f"{df['bias_score'].mean():.3f}")
			with col4:
				st.metric("Unique Domains", df['domain'].nunique())

			# Enhanced data display with sorting
			sort_column = st.selectbox("📊 Sort by", 
								options=['timestamp', 'ats_score', 'bias_score', 'candidate_name', 'domain'])
			sort_order = st.radio("Sort Order", ["Descending", "Ascending"], horizontal=True)
			
			df_sorted = df.sort_values(by=sort_column, ascending=(sort_order == "Ascending"))
			
			# Display with enhanced formatting
			st.dataframe(
				df_sorted.style.format({
					'ats_score': '{:.0f}',
					'edu_score': '{:.0f}',
					'exp_score': '{:.0f}',
					'skills_score': '{:.0f}',
					'lang_score': '{:.0f}',
					'keyword_score': '{:.0f}',
					'bias_score': '{:.3f}'
				}),
				use_container_width=True,
				height=400
			)

			# Enhanced Export Options
			col1, col2 = st.columns(2)
			with col1:
				csv_data = df_sorted.to_csv(index=False)
				st.download_button(
					label="📥 Download Filtered Data (CSV)",
					data=csv_data,
					file_name=f"candidates_filtered_{datetime.now().strftime('%Y%m%d_%H%M%S')}.csv",
					mime="text/csv",
					use_container_width=True
				)
			with col2:
				if st.button("📤 Export All Data", use_container_width=True):
					try:
						filename = f"full_export_{datetime.now().strftime('%Y%m%d_%H%M%S')}.csv"
						if export_to_csv(filename):
							st.success(f"✅ Data exported to {filename}")
						else:
							st.error("❌ Export failed")
					except Exception as e:
						st.error(f"Export error: {e}")

			st.markdown("### 📂 Export Archive")
			export_files = sorted(glob.glob("full_export_*.csv"), reverse=True)

			if export_files:
				for file in export_files:
					with open(file, "rb") as f:
						st.download_button(
							label=f"⬇️ Download {os.path.basename(file)}",
							data=f,
							file_name=os.path.basename(file),
							mime="text/csv",
							use_container_width=True
						)
			else:
				st.info("📭 No export files found yet.")

			# Enhanced Delete Functionality
			with st.expander("🗑️ Delete Candidate", expanded=False):
				st.warning("⚠️ This action cannot be undone!")
				delete_id = st.number_input("Enter Candidate ID", min_value=1, step=1, key="delete_id")
				
				if delete_id in df["id"].values:
					candidate_info = get_candidate_by_id(delete_id)
					if not candidate_info.empty:
						st.info("📄 Candidate to be deleted:")
						st.dataframe(candidate_info, use_container_width=True)
						
						if st.button("❌ Confirm Delete", type="primary"):
							try:
								if delete_candidate_by_id(delete_id):
									st.success(f"✅ Candidate with ID {delete_id} deleted successfully.")
									st.cache_data.clear()
									st.rerun()
								else:
									st.error("❌ Failed to delete candidate.")
							except Exception as e:
								st.error(f"Delete error: {e}")
				elif delete_id > 0:
					st.error("❌ Candidate ID not found.")

		# Enhanced Analytics Section
		st.markdown("<hr style='border-top: 2px solid #bbb; margin: 2rem 0;'>", unsafe_allow_html=True)
		st.markdown("## 📊 Advanced Analytics Dashboard")

		# Enhanced Top Domains Analysis
		st.markdown("### 🏆 Top Performing Domains")
		
		try:
			top_domains = get_top_domains_by_score(limit=10)
			if top_domains:
				df_top = pd.DataFrame(top_domains, columns=["domain", "avg_ats", "count"])
				
				col1, col2 = st.columns([1, 2])
				with col1:
					sort_order = st.radio("📊 Sort by ATS", ["⬆️ High to Low", "⬇️ Low to High"], horizontal=True)
					limit = st.slider("Show Top N Domains", 1, len(df_top), value=min(8, len(df_top)))
				
				ascending = sort_order == "⬇️ Low to High"
				df_sorted = df_top.sort_values(by="avg_ats", ascending=ascending).head(limit)
				
				# Interactive chart
				fig = create_enhanced_bar_chart(df_sorted, "domain", "avg_ats", 
										"Average ATS Score by Domain", orientation='h')
				st.plotly_chart(fig, use_container_width=True)
				
				# Enhanced domain cards with glassmorphism
				st.markdown("""
				<style>
				@keyframes tab5-shimmer {
					0% { background-position: -200% 0; }
					100% { background-position: 200% 0; }
				}
				.tab5-domain-card {
					background: rgba(10, 20, 40, 0.3);
					backdrop-filter: blur(10px);
					border: 1px solid rgba(0, 200, 255, 0.2);
					box-shadow: 0 4px 12px rgba(0, 0, 0, 0.3);
					border-radius: 15px;
					padding: 15px;
					margin-bottom: 15px;
					transition: all 0.3s ease;
					cursor: pointer;
					position: relative;
					overflow: hidden;
				}
				.tab5-domain-card::before {
					content: "";
					position: absolute;
					top: 0;
					left: 0;
					width: 100%;
					height: 100%;
					background: linear-gradient(
						120deg,
						transparent 0%,
						rgba(255, 255, 255, 0.08) 50%,
						transparent 100%
					);
					background-size: 200% 100%;
					opacity: 0;
					transition: opacity 0.3s ease;
				}
				.tab5-domain-card:hover::before {
					opacity: 1;
					animation: tab5-shimmer 1.5s ease-in-out infinite;
				}
				.tab5-domain-card:hover {
					transform: translateY(-2px);
					border-color: rgba(0, 200, 255, 0.35);
					background: rgba(10, 20, 40, 0.4);
				}
				</style>
				""", unsafe_allow_html=True)

				for i, row in df_sorted.iterrows():
					progress_value = row['avg_ats'] / 100
					st.markdown(f"""
					<div class="tab5-domain-card">
						<div style="display: flex; justify-content: space-between; align-items: center; position: relative; z-index: 1;">
							<h4 style="margin: 0; color: #5eb8ff;">📁 {row['domain']}</h4>
							<span style="
								background: rgba(0, 200, 255, 0.1);
								border: 1px solid rgba(0, 200, 255, 0.25);
								color: #5eb8ff;
								padding: 5px 10px;
								border-radius: 20px;
								font-size: 12px;
								font-weight: bold;
								backdrop-filter: blur(8px);
							">
								Rank #{i+1}
							</span>
						</div>
						<div style="margin: 10px 0; position: relative; z-index: 1;">
							<div style="
								background: rgba(255, 255, 255, 0.05);
								border-radius: 10px;
								height: 8px;
								overflow: hidden;
							">
								<div style="
									background: linear-gradient(90deg, rgba(0, 200, 255, 0.4), rgba(0, 255, 200, 0.5));
									height: 100%;
									width: {progress_value*100}%;
									transition: width 0.3s ease;
								"></div>
							</div>
						</div>
						<div style="display: flex; justify-content: space-between; margin-top: 10px; position: relative; z-index: 1;">
							<span style="color: #cce6ff;"><b>🧠 Avg ATS:</b> <span style="color: #5eb8ff; font-weight: bold;">{row['avg_ats']:.2f}</span></span>
							<span style="color: #cce6ff;"><b>📄 Resumes:</b> <span style="color: #5eb8ff; font-weight: bold;">{row['count']}</span></span>
						</div>
					</div>
					""", unsafe_allow_html=True)
			else:
				st.info("ℹ️ No domain performance data available.")
		except Exception as e:
			st.error(f"Error loading top domains: {e}")

		# Enhanced Domain Distribution
		st.markdown("### 📊 Domain Distribution Analysis")

		try:
			df_domain_dist = load_domain_distribution()
			if not df_domain_dist.empty:
				col1, col2 = st.columns(2)
				with col1:
					chart_type = st.radio(
						"📊 Visualization Type:",
						["📈 Interactive Bar Chart", "🥧 Interactive Pie Chart"],
						horizontal=True
					)
				with col2:
					max_val = len(df_domain_dist)
					if max_val <= 5:
						show_top_n = max_val  # No slider, just show all available domains
					else:
						show_top_n = st.slider(
							"Show Top N Domains",
							min_value=5,
							max_value=max_val,
							value=min(10, max_val)
						)

				df_top_domains = df_domain_dist.head(show_top_n)

				if chart_type == "📈 Interactive Bar Chart":
					fig = create_enhanced_bar_chart(df_top_domains, "domain", "count", 
											"Resume Count by Domain")
					st.plotly_chart(fig, use_container_width=True)
				else:
					fig = create_enhanced_pie_chart(df_top_domains, "count", "domain", 
											"Domain Distribution")
					st.plotly_chart(fig, use_container_width=True)

				# Summary statistics
				with st.expander("📋 Domain Statistics Summary"):
					st.dataframe(
						df_domain_dist.style.format({'percentage': '{:.2f}%'}),
						use_container_width=True
					)
			else:
				st.info("ℹ️ No domain distribution data available.")
		except Exception as e:
			st.error(f"Error loading domain distribution: {e}")

		# Enhanced ATS Performance Analysis
		st.markdown("### 📈 ATS Performance Analysis")
		
		try:
			df_ats = get_average_ats_by_domain()
			if not df_ats.empty:
				col1, col2 = st.columns(2)
				with col1:
					chart_orientation = st.radio("Chart Style", ["Vertical", "Horizontal"], horizontal=True)
				with col2:
					color_scheme = st.selectbox("Color Scheme", 
										["plasma", "viridis", "inferno", "magma", "turbo"])
				
				orientation = 'v' if chart_orientation == "Vertical" else 'h'
				fig = px.bar(df_ats, 
							x="domain" if orientation == 'v' else "avg_ats_score",
							y="avg_ats_score" if orientation == 'v' else "domain",
							title="Average ATS Score by Domain",
							orientation=orientation,
							color="avg_ats_score",
							color_continuous_scale=color_scheme,
							text="avg_ats_score",
							template="plotly_dark")  # Use dark theme for better readability
				
				fig.update_traces(texttemplate='%{text:.1f}', textposition='outside')
				if orientation == 'v':
					fig.update_xaxes(tickangle=45)
				
				# Enhanced layout for better readability
				fig.update_layout(
					showlegend=False,
					plot_bgcolor='rgba(0,0,0,0.1)',
					paper_bgcolor='rgba(0,0,0,0.05)',
					font=dict(color='white', size=12),
					title=dict(font=dict(size=16, color='white')),
					xaxis=dict(
						gridcolor='rgba(255,255,255,0.2)',
						tickfont=dict(color='white')
					),
					yaxis=dict(
						gridcolor='rgba(255,255,255,0.2)',
						tickfont=dict(color='white')
					),
					margin=dict(t=60, b=80, l=80, r=50)
				)
				
				st.plotly_chart(fig, use_container_width=True)
			else:
				st.info("ℹ️ No ATS performance data available.")
		except Exception as e:
			st.error(f"Error loading ATS performance data: {e}")

		# Enhanced Timeline Analysis
		st.markdown("### 📈 Resume Upload Timeline & Trends")
		
		try:
			df_timeline = get_resume_count_by_day()
			df_daily_ats = get_daily_ats_stats(days_limit=90)
			
			if not df_timeline.empty:
				df_timeline = df_timeline.sort_values("day")
				df_timeline["7_day_avg"] = df_timeline["count"].rolling(window=7, min_periods=1).mean()
				df_timeline["30_day_avg"] = df_timeline["count"].rolling(window=30, min_periods=1).mean()
				
				# Create subplot with proper spacing and formatting
				fig = make_subplots(
					rows=2, cols=1,
					subplot_titles=('Daily Upload Count with Moving Averages', 'Daily Average ATS Score Trend'),
					vertical_spacing=0.25,
					specs=[[{"secondary_y": False}], [{"secondary_y": False}]]
				)
				
				# Convert day column to datetime for proper spacing
				df_timeline['day'] = pd.to_datetime(df_timeline['day'])
				
				# Upload count plot
				fig.add_trace(
					go.Scatter(x=df_timeline["day"], y=df_timeline["count"], 
								mode='lines+markers', name='Daily Uploads',
								line=dict(color='#1f77b4', width=2),
								marker=dict(size=6)),
					row=1, col=1
				)
				
				fig.add_trace(
					go.Scatter(x=df_timeline["day"], y=df_timeline["7_day_avg"], 
								mode='lines', name='7-Day Average',
								line=dict(color='#ff7f0e', width=2, dash='dash')),
					row=1, col=1
				)
				
				fig.add_trace(
					go.Scatter(x=df_timeline["day"], y=df_timeline["30_day_avg"], 
								mode='lines', name='30-Day Average',
								line=dict(color='#2ca02c', width=2, dash='dot')),
					row=1, col=1
				)
				
				# ATS trend plot
				if not df_daily_ats.empty:
					df_daily_ats['date'] = pd.to_datetime(df_daily_ats['date'])
					fig.add_trace(
						go.Scatter(x=df_daily_ats["date"], y=df_daily_ats["avg_ats"], 
									mode='lines+markers', name='Daily Avg ATS',
									line=dict(color='#d62728', width=2),
									marker=dict(size=6)),
						row=2, col=1
					)
				
				# Update layout for better spacing and readability
				fig.update_layout(
					height=700, 
					showlegend=True,
					legend=dict(
						orientation="h",
						yanchor="bottom",
						y=1.02,
						xanchor="right",
						x=1
					),
					margin=dict(t=80, b=70, l=50, r=50)
				)
				
				# Update x-axes for proper date formatting and spacing
				fig.update_xaxes(title_text="Date", row=2, col=1)
				fig.update_xaxes(
					tickformat="%Y-%m-%d",
					tickangle=30,
					dtick="D1" if len(df_timeline) <= 30 else "D7",
					row=1, col=1
				)
				fig.update_xaxes(
					tickformat="%Y-%m-%d",
					tickangle=30,
					dtick="D1" if len(df_daily_ats) <= 30 else "D7",
					row=2, col=1
				)
				
				fig.update_yaxes(title_text="Upload Count", row=1, col=1)
				fig.update_yaxes(title_text="Average ATS Score", row=2, col=1)
				
				st.plotly_chart(fig, use_container_width=True)
				
				# Timeline statistics
				col1, col2, col3, col4 = st.columns(4)
				with col1:
					st.metric("Total Days", len(df_timeline))
				with col2:
					st.metric("Peak Daily Uploads", df_timeline["count"].max())
				with col3:
					st.metric("Avg Daily Uploads", f"{df_timeline['count'].mean():.1f}")
				with col4:
					if not df_daily_ats.empty:
						st.metric("Avg ATS Trend", f"{df_daily_ats['avg_ats'].mean():.2f}")
			else:
				st.info("ℹ️ No timeline data available.")
		except Exception as e:
			st.error(f"Error loading timeline data: {e}")

		# Enhanced Bias Analysis
		st.markdown("### 🧠 Advanced Bias Analysis")
		
		col1, col2 = st.columns(2)
		with col1:
			bias_threshold_pie = st.slider("Bias Detection Threshold", 
									min_value=0.0, max_value=1.0, value=0.6, step=0.05)
		with col2:
			analysis_type = st.radio("Analysis Type", ["Distribution", "Flagged Candidates"], horizontal=True)
		
		try:
			if analysis_type == "Distribution":
				df_bias = get_bias_distribution(threshold=bias_threshold_pie)
				if not df_bias.empty and "bias_category" in df_bias.columns:
					fig = create_enhanced_pie_chart(df_bias, "count", "bias_category", 
											f"Bias Distribution (Threshold: {bias_threshold_pie})")
					st.plotly_chart(fig, use_container_width=True)
					
					# Bias statistics
					col1, col2 = st.columns(2)
					with col1:
						total_candidates = df_bias["count"].sum()
						biased_count = df_bias[df_bias["bias_category"] == "Biased"]["count"].iloc[0] if len(df_bias[df_bias["bias_category"] == "Biased"]) > 0 else 0
						st.metric("Total Analyzed", total_candidates)
					with col2:
						bias_percentage = (biased_count / total_candidates * 100) if total_candidates > 0 else 0
						st.metric("Bias Percentage", f"{bias_percentage:.1f}%")
				else:
					st.info("📭 No bias distribution data available.")
			
			else:  # Flagged Candidates
				flagged_df = get_flagged_candidates(threshold=bias_threshold_pie)
				if not flagged_df.empty:
					st.markdown(f"**🚩 {len(flagged_df)} candidates flagged with bias score > {bias_threshold_pie}**")
					
					# Enhanced flagged candidates display
					display_df = flagged_df.copy()
					display_df = display_df.sort_values('bias_score', ascending=False)
					
					st.dataframe(
						display_df.style.format({'bias_score': '{:.3f}', 'ats_score': '{:.0f}'}),
						use_container_width=True,
						height=300
					)
					
					# Flagged candidates statistics
					col1, col2, col3 = st.columns(3)
					with col1:
						st.metric("Flagged Count", len(flagged_df))
					with col2:
						st.metric("Avg Bias Score", f"{flagged_df['bias_score'].mean():.3f}")
					with col3:
						st.metric("Avg ATS Score", f"{flagged_df['ats_score'].mean():.1f}")
				else:
					st.success("✅ No candidates flagged above the selected threshold.")
		except Exception as e:
			st.error(f"Error in bias analysis: {e}")

		# Enhanced Domain Performance Deep Dive
		with st.expander("🔍 Domain Performance Deep Dive", expanded=False):
			try:
				df_performance = get_domain_performance_stats()
				if not df_performance.empty:
					st.markdown("#### Comprehensive Domain Performance Metrics")
					
					# Performance heatmap
					performance_cols = ['avg_ats_score', 'avg_edu_score', 'avg_exp_score', 
								'avg_skills_score', 'avg_lang_score', 'avg_keyword_score']
					
					if all(col in df_performance.columns for col in performance_cols):
						heatmap_data = df_performance[['domain'] + performance_cols].set_index('domain')
						
						fig = px.imshow(heatmap_data.T, 
									title="Domain Performance Heatmap",
									color_continuous_scale="RdYlGn",
									aspect="auto")
						fig.update_layout(height=400)
						st.plotly_chart(fig, use_container_width=True)
					
					# Detailed performance table
					st.dataframe(
						df_performance.style.format({
							col: '{:.2f}' for col in performance_cols + ['avg_bias_score']
						}),
						use_container_width=True
					)
				else:
					st.info("ℹ️ No detailed performance data available.")
			except Exception as e:
				st.error(f"Error loading performance deep dive: {e}")

		# Footer with system information
		st.markdown("<hr style='border-top: 1px solid #ddd; margin: 2rem 0;'>", unsafe_allow_html=True)
		st.markdown("""
		<div style='text-align: center; color: #666; font-size: 0.9em; padding: 1rem;'>
			<p>🛡️ Enhanced Admin Dashboard | Powered by Advanced Database Manager</p>
			<p>Last updated: {}</p>
		</div>
		""".format(datetime.now().strftime("%Y-%m-%d %H:%M:%S")), unsafe_allow_html=True)
