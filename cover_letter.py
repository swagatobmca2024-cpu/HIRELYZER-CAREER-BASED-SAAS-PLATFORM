# cover_letter.py
# ══════════════════════════════════════════════════════════════════════════════
# COVER LETTER TEMPLATES — 6 ReportLab Platypus cover letter templates
# Each template returns BytesIO PDF
# + generate_cover_letter_from_resume_builder() Streamlit UI function
# ══════════════════════════════════════════════════════════════════════════════

from io import BytesIO
from reportlab.lib.pagesizes import A4
from reportlab.lib import colors
from reportlab.lib.units import mm
from reportlab.lib.styles import ParagraphStyle
from reportlab.lib.enums import TA_LEFT, TA_CENTER, TA_RIGHT, TA_JUSTIFY
from reportlab.platypus import (
    SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle, HRFlowable
)

PAGE_W, PAGE_H = A4
MARGIN = 20 * mm


def _cl_doc(buf):
    return SimpleDocTemplate(buf, pagesize=A4,
                             leftMargin=MARGIN, rightMargin=MARGIN,
                             topMargin=MARGIN, bottomMargin=MARGIN)


def _contact_line(data, sep=' | ', link_color='#1e3a5f'):
    parts = []
    email = data.get('email', '')
    phone = data.get('phone', '')
    loc   = data.get('location', '')
    li    = data.get('linkedin', '')
    if email: parts.append(email)
    if phone: parts.append(phone)
    if loc:   parts.append(loc)
    if li:
        url = li if li.startswith('http') else f'https://{li}'
        parts.append(f'<link href="{url}"><font color="{link_color}">{li}</font></link>')
    return sep.join(parts)


# ══════════════════════════════════════════════════════════════════════════════
# TEMPLATE 1 — Professional (navy, serif-feel)
# ══════════════════════════════════════════════════════════════════════════════
def render_cover_letter_professional(data):
    C_NAV  = colors.HexColor('#1e3a5f')
    C_TEXT = colors.HexColor('#1a1a1a')
    C_MUTED= colors.HexColor('#555555')
    buf = BytesIO()
    doc = _cl_doc(buf)
    W   = PAGE_W - 2 * MARGIN

    h_name  = ParagraphStyle('n',  fontName='Helvetica-Bold',   fontSize=26, textColor=C_NAV,  leading=32)
    h_title = ParagraphStyle('t',  fontName='Helvetica',        fontSize=13, textColor=C_MUTED, leading=18, spaceAfter=4)
    h_cont  = ParagraphStyle('c',  fontName='Helvetica',        fontSize=10, textColor=C_MUTED, leading=14)
    p_date  = ParagraphStyle('d',  fontName='Helvetica',        fontSize=11, textColor=C_TEXT,  leading=15, spaceBefore=16, spaceAfter=14)
    p_recip = ParagraphStyle('r',  fontName='Helvetica-Bold',   fontSize=11, textColor=C_TEXT,  leading=15, spaceAfter=2)
    p_co    = ParagraphStyle('co', fontName='Helvetica',        fontSize=11, textColor=C_MUTED, leading=15, spaceAfter=14)
    p_sal   = ParagraphStyle('s',  fontName='Helvetica',        fontSize=11, textColor=C_TEXT,  leading=16, spaceAfter=14)
    p_body  = ParagraphStyle('b',  fontName='Helvetica',        fontSize=11, textColor=C_TEXT,  leading=17, spaceAfter=12, alignment=TA_JUSTIFY)
    p_close = ParagraphStyle('cl', fontName='Helvetica',        fontSize=11, textColor=C_TEXT,  leading=16, spaceBefore=14, spaceAfter=4)
    p_sig   = ParagraphStyle('sg', fontName='Helvetica-Bold',   fontSize=12, textColor=C_NAV,   leading=16)
    p_sigj  = ParagraphStyle('sj', fontName='Helvetica',        fontSize=10, textColor=C_MUTED, leading=14)

    name     = data.get('name', 'Your Name')
    job_title= data.get('job_title', '')
    company  = data.get('company', 'Hiring Company')
    hiring   = data.get('hiring_manager', 'Hiring Manager')
    date_str = data.get('date', '')
    paras    = data.get('body_paragraphs', [])

    story = []
    story.append(Paragraph(name, h_name))
    if job_title: story.append(Paragraph(job_title, h_title))
    cl = _contact_line(data, sep='  |  ', link_color='#1e3a5f')
    if cl: story.append(Paragraph(cl, h_cont))
    story.append(HRFlowable(width=W, thickness=2.5, color=C_NAV, spaceBefore=10, spaceAfter=4))

    if date_str: story.append(Paragraph(date_str, p_date))
    story.append(Paragraph(hiring, p_recip))
    story.append(Paragraph(company, p_co))
    story.append(Paragraph(f'Dear {hiring},', p_sal))
    for p in paras:
        if p.strip(): story.append(Paragraph(p.strip(), p_body))
    story.append(Paragraph(f'I would welcome the opportunity to discuss how my experience aligns with {company}. Thank you for your time and consideration.', p_body))
    story.append(Paragraph('Sincerely,', p_close))
    story.append(Paragraph(name, p_sig))
    if job_title: story.append(Paragraph(job_title, p_sigj))

    doc.build(story)
    buf.seek(0)
    return buf


# ══════════════════════════════════════════════════════════════════════════════
# TEMPLATE 2 — Modern (teal accent, clean sans)
# ══════════════════════════════════════════════════════════════════════════════
def render_cover_letter_modern(data):
    C_ACC  = colors.HexColor('#0d9488')
    C_TEXT = colors.HexColor('#1f2937')
    C_MUTED= colors.HexColor('#6b7280')
    buf = BytesIO()
    doc = _cl_doc(buf)
    W   = PAGE_W - 2 * MARGIN

    h_name  = ParagraphStyle('n',  fontName='Helvetica-Bold',   fontSize=24, textColor=C_TEXT,  leading=30)
    h_title = ParagraphStyle('t',  fontName='Helvetica',        fontSize=12, textColor=C_ACC,   leading=16, spaceAfter=2)
    h_cont  = ParagraphStyle('c',  fontName='Helvetica',        fontSize=9,  textColor=C_MUTED, leading=13)
    p_date  = ParagraphStyle('d',  fontName='Helvetica',        fontSize=10, textColor=C_MUTED, leading=14, spaceBefore=16, spaceAfter=12)
    p_recip = ParagraphStyle('r',  fontName='Helvetica-Bold',   fontSize=11, textColor=C_TEXT,  leading=15, spaceAfter=2)
    p_co    = ParagraphStyle('co', fontName='Helvetica',        fontSize=10, textColor=C_MUTED, leading=14, spaceAfter=14)
    p_sal   = ParagraphStyle('s',  fontName='Helvetica',        fontSize=11, textColor=C_TEXT,  leading=16, spaceAfter=14)
    p_body  = ParagraphStyle('b',  fontName='Helvetica',        fontSize=11, textColor=C_TEXT,  leading=17, spaceAfter=12)
    p_close = ParagraphStyle('cl', fontName='Helvetica',        fontSize=11, textColor=C_TEXT,  leading=16, spaceBefore=16, spaceAfter=4)
    p_sig   = ParagraphStyle('sg', fontName='Helvetica-Bold',   fontSize=13, textColor=C_TEXT,  leading=17)
    p_sigj  = ParagraphStyle('sj', fontName='Helvetica',        fontSize=10, textColor=C_ACC,   leading=14)

    name     = data.get('name', 'Your Name')
    job_title= data.get('job_title', '')
    company  = data.get('company', 'Company')
    hiring   = data.get('hiring_manager', 'Hiring Manager')
    date_str = data.get('date', '')
    paras    = data.get('body_paragraphs', [])

    story = []
    # Header with teal bar on right
    hdr_name_block = [Paragraph(name, h_name)]
    if job_title: hdr_name_block.append(Paragraph(job_title, h_title))
    cl = _contact_line(data, sep='  ·  ', link_color='#0d9488')
    if cl: hdr_name_block.append(Paragraph(cl, h_cont))

    hdr = Table([[hdr_name_block]], colWidths=[W])
    hdr.setStyle(TableStyle([('LEFTPADDING',(0,0),(-1,-1),0),('RIGHTPADDING',(0,0),(-1,-1),0),
                              ('TOPPADDING',(0,0),(-1,-1),0),('BOTTOMPADDING',(0,0),(-1,-1),0)]))
    story.append(hdr)
    story.append(HRFlowable(width=W, thickness=3.5, color=C_ACC, spaceBefore=8, spaceAfter=12))

    if date_str: story.append(Paragraph(date_str, p_date))
    story.append(Paragraph(hiring, p_recip))
    story.append(Paragraph(company, p_co))
    story.append(Paragraph(f'Dear {hiring},', p_sal))
    for p in paras:
        if p.strip(): story.append(Paragraph(p.strip(), p_body))
    story.append(Paragraph(f"I'd love the opportunity to discuss how I can contribute to {company}. Thank you for considering my application.", p_body))
    story.append(Paragraph('Best regards,', p_close))
    # Sign-off with teal underline
    story.append(HRFlowable(width=120, thickness=2, color=C_ACC, spaceAfter=4))
    story.append(Paragraph(name, p_sig))
    if job_title: story.append(Paragraph(job_title, p_sigj))

    doc.build(story)
    buf.seek(0)
    return buf


# ══════════════════════════════════════════════════════════════════════════════
# TEMPLATE 3 — Creative (user-chosen accent, bold sidebar strip)
# ══════════════════════════════════════════════════════════════════════════════
def render_cover_letter_creative(data):
    raw_acc = data.get('accent_color', '#7c3aed')
    try:
        C_ACC = colors.HexColor(raw_acc)
    except Exception:
        C_ACC = colors.HexColor('#7c3aed')
    C_TEXT = colors.HexColor('#1f2937')
    C_MUTED= colors.HexColor('#6b7280')

    buf = BytesIO()
    doc = _cl_doc(buf)
    W   = PAGE_W - 2 * MARGIN

    sb_name = ParagraphStyle('sn', fontName='Helvetica-Bold',   fontSize=18, textColor=colors.white, alignment=TA_CENTER, leading=24, spaceAfter=4)
    sb_t    = ParagraphStyle('st', fontName='Helvetica-Oblique',fontSize=10, textColor=colors.HexColor('#e0d7ff'), alignment=TA_CENTER, leading=14, spaceAfter=6)
    sb_c    = ParagraphStyle('sc', fontName='Helvetica',        fontSize=9,  textColor=colors.HexColor('#e9e3ff'), alignment=TA_CENTER, leading=13)
    m_date  = ParagraphStyle('d',  fontName='Helvetica',        fontSize=10, textColor=C_MUTED, leading=14, spaceAfter=12)
    m_recip = ParagraphStyle('r',  fontName='Helvetica-Bold',   fontSize=11, textColor=C_TEXT,  leading=15, spaceAfter=2)
    m_co    = ParagraphStyle('co', fontName='Helvetica',        fontSize=10, textColor=C_MUTED, leading=14, spaceAfter=14)
    m_sal   = ParagraphStyle('s',  fontName='Helvetica',        fontSize=11, textColor=C_TEXT,  leading=16, spaceAfter=12)
    m_body  = ParagraphStyle('b',  fontName='Helvetica',        fontSize=11, textColor=C_TEXT,  leading=17, spaceAfter=12)
    m_close = ParagraphStyle('cl', fontName='Helvetica',        fontSize=11, textColor=C_TEXT,  leading=16, spaceBefore=14, spaceAfter=4)
    m_sig   = ParagraphStyle('sg', fontName='Helvetica-Bold',   fontSize=12, textColor=C_ACC,   leading=16)

    name     = data.get('name', 'Your Name')
    job_title= data.get('job_title', '')
    company  = data.get('company', 'Company')
    hiring   = data.get('hiring_manager', 'Hiring Manager')
    date_str = data.get('date', '')
    paras    = data.get('body_paragraphs', [])

    STRIP_W = 130
    MAIN_W  = W - STRIP_W - 8

    # Sidebar strip
    sb_items = [Spacer(1, 20), Paragraph(name, sb_name)]
    if job_title: sb_items.append(Paragraph(job_title, sb_t))
    cl = _contact_line(data, sep='\n', link_color='#ffffff')
    if cl:
        for part in cl.split('|'):
            sb_items.append(Paragraph(part.strip(), sb_c))

    # Main content
    main_items = []
    if date_str: main_items.append(Paragraph(date_str, m_date))
    main_items.append(Paragraph(hiring, m_recip))
    main_items.append(Paragraph(company, m_co))
    main_items.append(Paragraph(f'Dear {hiring},', m_sal))
    for p in paras:
        if p.strip(): main_items.append(Paragraph(p.strip(), m_body))
    main_items.append(Paragraph(f"I look forward to the opportunity to bring my passion and skills to {company}. Thank you for your consideration.", m_body))
    main_items.append(Paragraph('Warm regards,', m_close))
    main_items.append(Paragraph(name, m_sig))

    body = Table([[sb_items, main_items]], colWidths=[STRIP_W, MAIN_W])
    body.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (0, -1), C_ACC),
        ('VALIGN', (0, 0), (-1, -1), 'TOP'),
        ('LEFTPADDING', (0, 0), (0, -1), 10),
        ('RIGHTPADDING', (0, 0), (0, -1), 8),
        ('LEFTPADDING', (1, 0), (1, -1), 12),
        ('RIGHTPADDING', (1, 0), (1, -1), 0),
        ('TOPPADDING', (0, 0), (-1, -1), 8),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 8),
    ]))
    doc.build([body])
    buf.seek(0)
    return buf


# ══════════════════════════════════════════════════════════════════════════════
# TEMPLATE 4 — Executive (deep navy, gold accent, justified)
# ══════════════════════════════════════════════════════════════════════════════
def render_cover_letter_executive(data):
    C_NAV  = colors.HexColor('#1e3a5f')
    C_GOLD = colors.HexColor('#b7791f')
    C_TEXT = colors.HexColor('#1a202c')
    C_MUTED= colors.HexColor('#718096')
    buf = BytesIO()
    doc = _cl_doc(buf)
    W   = PAGE_W - 2 * MARGIN

    h_name  = ParagraphStyle('n',  fontName='Helvetica-Bold',   fontSize=28, textColor=C_NAV,   leading=34, alignment=TA_CENTER)
    h_title = ParagraphStyle('t',  fontName='Helvetica-Oblique',fontSize=13, textColor=C_GOLD,  leading=18, spaceAfter=4, alignment=TA_CENTER)
    h_cont  = ParagraphStyle('c',  fontName='Helvetica',        fontSize=10, textColor=C_MUTED, leading=14, alignment=TA_CENTER)
    p_date  = ParagraphStyle('d',  fontName='Helvetica',        fontSize=11, textColor=C_TEXT,  leading=15, spaceBefore=16, spaceAfter=14)
    p_recip = ParagraphStyle('r',  fontName='Helvetica-Bold',   fontSize=11, textColor=C_TEXT,  leading=15, spaceAfter=2)
    p_co    = ParagraphStyle('co', fontName='Helvetica',        fontSize=11, textColor=C_MUTED, leading=15, spaceAfter=14)
    p_sal   = ParagraphStyle('s',  fontName='Helvetica',        fontSize=11, textColor=C_TEXT,  leading=16, spaceAfter=14)
    p_body  = ParagraphStyle('b',  fontName='Helvetica',        fontSize=11, textColor=C_TEXT,  leading=18, spaceAfter=12, alignment=TA_JUSTIFY)
    p_close = ParagraphStyle('cl', fontName='Helvetica',        fontSize=11, textColor=C_TEXT,  leading=16, spaceBefore=18, spaceAfter=4)
    p_sig   = ParagraphStyle('sg', fontName='Helvetica-Bold',   fontSize=13, textColor=C_NAV,   leading=18)
    p_sigj  = ParagraphStyle('sj', fontName='Helvetica',        fontSize=10, textColor=C_GOLD,  leading=14)

    name     = data.get('name', 'Your Name')
    job_title= data.get('job_title', '')
    company  = data.get('company', 'Company')
    hiring   = data.get('hiring_manager', 'Hiring Manager')
    date_str = data.get('date', '')
    paras    = data.get('body_paragraphs', [])

    story = []
    story.append(Paragraph(name, h_name))
    if job_title: story.append(Paragraph(job_title, h_title))
    cl = _contact_line(data, sep='  |  ', link_color='#1e3a5f')
    if cl: story.append(Paragraph(cl, h_cont))
    story.append(HRFlowable(width=W, thickness=2.5, color=C_NAV, spaceBefore=8, spaceAfter=3))
    story.append(HRFlowable(width=W, thickness=1,   color=C_GOLD,spaceBefore=0, spaceAfter=12))

    if date_str: story.append(Paragraph(date_str, p_date))
    story.append(Paragraph(hiring, p_recip))
    story.append(Paragraph(company, p_co))
    story.append(Paragraph(f'Dear {hiring},', p_sal))
    for p in paras:
        if p.strip(): story.append(Paragraph(p.strip(), p_body))
    story.append(Paragraph(f'I welcome the opportunity to discuss how my leadership and expertise align with {company}\'s vision. Thank you for your time.', p_body))
    story.append(Paragraph('Respectfully yours,', p_close))
    story.append(HRFlowable(width=150, thickness=1, color=C_GOLD, spaceAfter=4))
    story.append(Paragraph(name, p_sig))
    if job_title: story.append(Paragraph(job_title, p_sigj))

    doc.build(story)
    buf.seek(0)
    return buf


# ══════════════════════════════════════════════════════════════════════════════
# TEMPLATE 5 — Entry Level (clean, friendly, green accent)
# ══════════════════════════════════════════════════════════════════════════════
def render_cover_letter_entry_level(data):
    C_GRN  = colors.HexColor('#16a34a')
    C_TEXT = colors.HexColor('#1f2937')
    C_MUTED= colors.HexColor('#6b7280')
    buf = BytesIO()
    doc = _cl_doc(buf)
    W   = PAGE_W - 2 * MARGIN

    h_name  = ParagraphStyle('n',  fontName='Helvetica-Bold',   fontSize=22, textColor=C_GRN,  leading=28)
    h_title = ParagraphStyle('t',  fontName='Helvetica',        fontSize=12, textColor=C_TEXT, leading=16, spaceAfter=2)
    h_cont  = ParagraphStyle('c',  fontName='Helvetica',        fontSize=9,  textColor=C_MUTED,leading=13)
    p_date  = ParagraphStyle('d',  fontName='Helvetica',        fontSize=10, textColor=C_MUTED,leading=14, spaceBefore=16, spaceAfter=12)
    p_recip = ParagraphStyle('r',  fontName='Helvetica-Bold',   fontSize=11, textColor=C_TEXT, leading=15, spaceAfter=2)
    p_co    = ParagraphStyle('co', fontName='Helvetica',        fontSize=10, textColor=C_MUTED,leading=14, spaceAfter=14)
    p_sal   = ParagraphStyle('s',  fontName='Helvetica',        fontSize=11, textColor=C_TEXT, leading=16, spaceAfter=12)
    p_body  = ParagraphStyle('b',  fontName='Helvetica',        fontSize=11, textColor=C_TEXT, leading=17, spaceAfter=12)
    p_close = ParagraphStyle('cl', fontName='Helvetica',        fontSize=11, textColor=C_TEXT, leading=16, spaceBefore=14, spaceAfter=4)
    p_sig   = ParagraphStyle('sg', fontName='Helvetica-Bold',   fontSize=12, textColor=C_GRN,  leading=16)
    p_sigj  = ParagraphStyle('sj', fontName='Helvetica',        fontSize=10, textColor=C_MUTED,leading=14)

    name     = data.get('name', 'Your Name')
    job_title= data.get('job_title', '')
    company  = data.get('company', 'Company')
    hiring   = data.get('hiring_manager', 'Hiring Manager')
    date_str = data.get('date', '')
    paras    = data.get('body_paragraphs', [])

    story = []
    story.append(Paragraph(name, h_name))
    if job_title: story.append(Paragraph(job_title, h_title))
    cl = _contact_line(data, sep=' · ', link_color='#16a34a')
    if cl: story.append(Paragraph(cl, h_cont))
    story.append(HRFlowable(width=W, thickness=2, color=C_GRN, spaceBefore=8, spaceAfter=12))

    if date_str: story.append(Paragraph(date_str, p_date))
    story.append(Paragraph(hiring, p_recip))
    story.append(Paragraph(company, p_co))
    story.append(Paragraph(f'Dear {hiring},', p_sal))
    for p in paras:
        if p.strip(): story.append(Paragraph(p.strip(), p_body))
    story.append(Paragraph(f'Thank you for considering my application to {company}. I am eager to learn, contribute, and grow with your team.', p_body))
    story.append(Paragraph('Sincerely,', p_close))
    story.append(Paragraph(name, p_sig))
    if job_title: story.append(Paragraph(job_title, p_sigj))

    doc.build(story)
    buf.seek(0)
    return buf


# ══════════════════════════════════════════════════════════════════════════════
# TEMPLATE 6 — ATS (plain, keyword-optimised, no decorative elements)
# ══════════════════════════════════════════════════════════════════════════════
def render_cover_letter_ats(data):
    C_TEXT = colors.HexColor('#000000')
    C_MUTED= colors.HexColor('#333333')
    buf = BytesIO()
    doc = _cl_doc(buf)
    W   = PAGE_W - 2 * MARGIN

    h_name  = ParagraphStyle('n',  fontName='Helvetica-Bold',fontSize=14, textColor=C_TEXT, leading=18)
    h_cont  = ParagraphStyle('c',  fontName='Helvetica',     fontSize=10, textColor=C_MUTED,leading=14, spaceAfter=6)
    p_date  = ParagraphStyle('d',  fontName='Helvetica',     fontSize=11, textColor=C_TEXT, leading=15, spaceBefore=10, spaceAfter=10)
    p_recip = ParagraphStyle('r',  fontName='Helvetica-Bold',fontSize=11, textColor=C_TEXT, leading=15, spaceAfter=2)
    p_co    = ParagraphStyle('co', fontName='Helvetica',     fontSize=11, textColor=C_TEXT, leading=15, spaceAfter=12)
    p_sal   = ParagraphStyle('s',  fontName='Helvetica',     fontSize=11, textColor=C_TEXT, leading=16, spaceAfter=12)
    p_body  = ParagraphStyle('b',  fontName='Helvetica',     fontSize=11, textColor=C_TEXT, leading=17, spaceAfter=12)
    p_close = ParagraphStyle('cl', fontName='Helvetica',     fontSize=11, textColor=C_TEXT, leading=16, spaceBefore=12, spaceAfter=4)
    p_sig   = ParagraphStyle('sg', fontName='Helvetica-Bold',fontSize=11, textColor=C_TEXT, leading=16)

    name     = data.get('name', 'Your Name')
    job_title= data.get('job_title', '')
    company  = data.get('company', 'Company')
    hiring   = data.get('hiring_manager', 'Hiring Manager')
    date_str = data.get('date', '')
    paras    = data.get('body_paragraphs', [])
    # ATS keyword block from skills
    key_skills = data.get('key_skills', '')

    story = []
    story.append(Paragraph(name, h_name))
    if job_title: story.append(Paragraph(job_title, h_cont))
    cl = _contact_line(data, sep=' | ', link_color='#000000')
    if cl: story.append(Paragraph(cl, h_cont))
    story.append(HRFlowable(width=W, thickness=1, color=C_TEXT, spaceBefore=4, spaceAfter=4))

    if date_str: story.append(Paragraph(date_str, p_date))
    story.append(Paragraph(hiring, p_recip))
    story.append(Paragraph(company, p_co))
    story.append(Paragraph(f'Dear {hiring},', p_sal))
    for p in paras:
        if p.strip(): story.append(Paragraph(p.strip(), p_body))
    story.append(Paragraph(f'I am confident that my qualifications make me a strong candidate for this role at {company}. I welcome the opportunity to discuss my application further.', p_body))

    # ATS keyword section
    if key_skills and key_skills.strip():
        story.append(HRFlowable(width=W, thickness=0.5, color=C_MUTED, spaceBefore=8, spaceAfter=6))
        kw_style = ParagraphStyle('kw', fontName='Helvetica-Bold', fontSize=10, textColor=C_TEXT, leading=14, spaceAfter=4)
        story.append(Paragraph('Key Skills:', kw_style))
        story.append(Paragraph(key_skills, p_body))

    story.append(Paragraph('Sincerely,', p_close))
    story.append(Paragraph(name, p_sig))
    if job_title: story.append(Paragraph(job_title, p_sig))

    doc.build(story)
    buf.seek(0)
    return buf


# ── Registry & dispatcher ──────────────────────────────────────────────────────
COVER_LETTER_TEMPLATES = {
    "Professional": render_cover_letter_professional,
    "Modern":       render_cover_letter_modern,
    "Creative":     render_cover_letter_creative,
    "Executive":    render_cover_letter_executive,
    "Entry Level":  render_cover_letter_entry_level,
    "ATS":          render_cover_letter_ats,
}


def render_cover_letter(template_name, data):
    """Return BytesIO PDF for the given cover letter template."""
    fn = COVER_LETTER_TEMPLATES.get(template_name, render_cover_letter_professional)
    return fn(data)


# ══════════════════════════════════════════════════════════════════════════════
# Streamlit UI — generate_cover_letter_from_resume_builder()
# ══════════════════════════════════════════════════════════════════════════════

def generate_cover_letter_from_resume_builder():
    import streamlit as st
    from datetime import datetime, timezone, timedelta
    import re as _re

    name      = st.session_state.get("name", "")
    job_title = st.session_state.get("job_title", "")
    summary   = st.session_state.get("summary", "")
    skills    = st.session_state.get("skills", "")
    location  = st.session_state.get("location", "")

    IST = timezone(timedelta(hours=5, minutes=30))
    today_date = datetime.now(IST).strftime("%B %d, %Y")

    with st.form(key="cover_letter_form"):
        cover_letter_template = st.selectbox(
            "🎨 Choose Cover Letter Template",
            options=list(COVER_LETTER_TEMPLATES.keys()),
            index=0,
            key="cover_letter_template_select",
        )
        accent_color  = st.color_picker("🎨 Accent Colour (Creative template only)", value="#7c3aed", key="cl_accent_color")
        company       = st.text_input("🏢 Target Company", placeholder="e.g., Google")
        linkedin_val  = st.text_input("🔗 LinkedIn URL", placeholder="e.g., https://linkedin.com/in/username")
        email_val     = st.text_input("📧 Email", placeholder="e.g., you@example.com")
        mobile_val    = st.text_input("📞 Mobile Number", placeholder="e.g., +91 9876543210")
        submitted_cl  = st.form_submit_button("✉️ Generate Cover Letter")

    if cover_letter_template != "Creative":
        accent_color = "#003366"

    if submitted_cl:
        if not all([name, job_title, summary, skills, company, linkedin_val, email_val, mobile_val]):
            st.warning("⚠️ Please fill in all fields including LinkedIn, email, and mobile.")
            return

        prompt = f"""You are a professional cover letter writer.

Write ONLY the body paragraphs of a cover letter for the candidate below.
Do NOT include: date, recipient address, salutation ("Dear ..."), closing ("Sincerely"), or the candidate's name at the end.
Output exactly 3 paragraphs separated by a blank line (double newline). Each paragraph 2-4 sentences.

### Candidate Info:
- Name: {name}
- Job Title: {job_title}
- Target Company: {company}
- Location: {location}
- Summary: {summary}
- Skills: {skills}

### Rules:
- Do NOT include the date, header, salutation, or sign-off.
- Do NOT start with "Dear Hiring Manager" or any greeting.
- Do NOT end with "Sincerely" or the candidate's name.
- No HTML tags. Plain text only.
- Separate each paragraph with a blank line.
"""

        with st.spinner("✉️ Crafting your cover letter..."):
            try:
                from llm_manager import call_llm
                cover_letter_raw = call_llm(prompt, session=st.session_state).strip()
            except Exception as e:
                st.error(f"LLM error: {e}")
                return

        def _strip_boilerplate(text):
            lines = text.split('\n')
            cleaned = []
            skip_pats = [
                _re.compile(r'^\s*(january|february|march|april|may|june|july|august|september|october|november|december)\s+\d', _re.I),
                _re.compile(r'^\s*\d{1,2}[\/\-]\d{1,2}[\/\-]\d{2,4}'),
                _re.compile(r'^\s*dear\b', _re.I),
                _re.compile(r'^\s*(sincerely|regards|best regards|yours truly|warm regards|respectfully)', _re.I),
            ]
            for line in lines:
                if any(p.match(line) for p in skip_pats):
                    continue
                cleaned.append(line)
            return '\n'.join(cleaned).strip()

        body_text = _strip_boilerplate(cover_letter_raw)
        st.session_state["cover_letter"] = body_text

        normalised  = _re.sub(r'\n{3,}', '\n\n', body_text)
        raw_paras   = normalised.split('\n\n')
        if len(raw_paras) <= 1:
            raw_paras = normalised.split('\n')
        body_paragraphs = [p.strip() for p in raw_paras if p.strip()]

        cl_data = {
            "name":            name,
            "job_title":       job_title,
            "email":           email_val,
            "phone":           mobile_val,
            "location":        location,
            "linkedin":        linkedin_val,
            "company":         company,
            "hiring_manager":  "Hiring Manager",
            "role":            job_title,
            "date":            today_date,
            "body_paragraphs": body_paragraphs,
            "key_skills":      skills,
            "accent_color":    accent_color,
        }

        pdf_buf = render_cover_letter(cover_letter_template, cl_data)
        pdf_bytes = pdf_buf.read()
        st.session_state["cover_letter_pdf"] = pdf_bytes

        st.success("✅ Cover letter generated successfully!")

        # PDF download
        st.download_button(
            label="📥 Download Cover Letter (PDF)",
            data=pdf_bytes,
            file_name=f"{name.replace(' ', '_')}_Cover_Letter.pdf",
            mime="application/pdf",
            key="download_cl_pdf",
        )

        # DOCX download
        try:
            from docx import Document as _DocxDocument
            bio = BytesIO()
            doc_x = _DocxDocument()
            doc_x.add_heading("Cover Letter", 0)
            for line in body_text.split("\n"):
                doc_x.add_paragraph(line if line.strip() else "")
            doc_x.save(bio)
            bio.seek(0)
            st.download_button(
                label="📥 Download Cover Letter (.docx)",
                data=bio,
                file_name=f"{name.replace(' ', '_')}_Cover_Letter.docx",
                mime="application/vnd.openxmlformats-officedocument.wordprocessingml.document",
                key="download_cl_docx",
            )
        except ImportError:
            st.info("Install python-docx for DOCX download support.")
