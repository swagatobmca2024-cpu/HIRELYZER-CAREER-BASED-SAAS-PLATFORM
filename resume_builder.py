# resume_builder.py
# ══════════════════════════════════════════════════════════════════════════════
# RESUME TEMPLATES — 21 ReportLab Platypus resume templates
# Each template returns a BytesIO PDF
# ══════════════════════════════════════════════════════════════════════════════

from io import BytesIO
from reportlab.lib.pagesizes import A4
from reportlab.lib import colors
from reportlab.lib.units import mm
from reportlab.lib.styles import ParagraphStyle
from reportlab.lib.enums import TA_LEFT, TA_CENTER, TA_RIGHT, TA_JUSTIFY
from reportlab.platypus import (
    SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle,
    HRFlowable, ListFlowable, ListItem, Image
)

PAGE_W, PAGE_H = A4
MARGIN = 15 * mm
SIDEBAR_W = 160
MAIN_W = 380

# ── Shared helpers ─────────────────────────────────────────────────────────────

def _get(ss, key, default=""):
    if isinstance(ss, dict):
        return ss.get(key, default) or default
    return getattr(ss, key, default) or default

def _entries(ss, key, default=None):
    if default is None:
        default = []
    if isinstance(ss, dict):
        return ss.get(key, default) or default
    return getattr(ss, key, default) or default

def _parse_bullets(text):
    if not text or not text.strip():
        return []
    BULLET_PREFIXES = ("-", "•", "*", "·", ">", "–", "—")
    result = []
    for line in text.replace('\r\n', '\n').replace('\r', '\n').split('\n'):
        s = line.strip()
        if not s:
            continue
        is_b = False
        for p in BULLET_PREFIXES:
            if s.startswith(p):
                s = s[len(p):].strip()
                is_b = True
                break
        result.append((is_b, s))
    return result

def _build_desc_flowables(text, style_normal, style_bullet, bullet_color=None):
    if not text or not text.strip():
        return []
    items = _parse_bullets(text)
    if not items:
        return []
    flowables = []
    bullet_buf = []
    def flush_bullets():
        if bullet_buf:
            li_items = [ListItem(Paragraph(t, style_bullet),
                                 leftIndent=12,
                                 bulletColor=bullet_color or colors.black)
                        for t in bullet_buf]
            flowables.append(ListFlowable(li_items, bulletType='bullet',
                                          start='•', leftIndent=8, bulletFontSize=8))
            bullet_buf.clear()
    for is_b, content in items:
        if is_b:
            bullet_buf.append(content)
        else:
            flush_bullets()
            flowables.append(Paragraph(content, style_normal))
    flush_bullets()
    return flowables

def _pills_table(items_str, bg_color, text_color, border_color, base_style):
    if not items_str or not items_str.strip():
        return []
    items = [i.strip() for i in items_str.split(',') if i.strip()]
    if not items:
        return []
    pill_style = ParagraphStyle('pill', parent=base_style, fontSize=9,
                                 textColor=text_color, alignment=TA_CENTER, leading=12)
    rows = []
    row = []
    for item in items:
        row.append(Paragraph(item, pill_style))
        if len(row) == 5:
            rows.append(row)
            row = []
    if row:
        while len(row) < 5:
            row.append(Paragraph('', pill_style))
        rows.append(row)
    if not rows:
        return []
    col_w = (PAGE_W - 2 * MARGIN) / 5
    t = Table(rows, colWidths=[col_w] * 5)
    ts = TableStyle([
        ('BACKGROUND', (0, 0), (-1, -1), bg_color),
        ('TOPPADDING', (0, 0), (-1, -1), 4),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 4),
        ('LEFTPADDING', (0, 0), (-1, -1), 6),
        ('RIGHTPADDING', (0, 0), (-1, -1), 6),
    ])
    for r_i in range(len(rows)):
        for c_i in range(5):
            ts.add('BOX', (c_i, r_i), (c_i, r_i), 0.5, border_color)
    t.setStyle(ts)
    return [t, Spacer(1, 4)]

def _profile_image_flowable(img_bytes, size=80):
    if not img_bytes:
        return None
    try:
        bio = BytesIO(img_bytes)
        return Image(bio, width=size, height=size)
    except Exception:
        return None

def _safe_link(url, label, hex_color):
    """hex_color: string like '#3b82f6' OR a ReportLab Color object."""
    if not url:
        return label
    if not url.startswith('http'):
        url = 'https://' + url
    # Normalise colour to a proper CSS hex string
    if hasattr(hex_color, 'hexval'):
        # hexval() returns '0xRRGGBB' — convert to '#RRGGBB'
        hv = hex_color.hexval()          # e.g. '0x3b82f6'
        css = '#' + hv[2:]               # '#3b82f6'
    elif isinstance(hex_color, str) and hex_color.startswith('#'):
        css = hex_color
    else:
        css = '#000000'
    return f'<link href="{url}"><font color="{css}">{label}</font></link>'

def _row2_table(left_para, right_para, total_w):
    t = Table([[left_para, right_para]], colWidths=[total_w * 0.72, total_w * 0.28])
    t.setStyle(TableStyle([
        ('ALIGN', (1, 0), (1, 0), 'RIGHT'),
        ('VALIGN', (0, 0), (-1, -1), 'TOP'),
        ('LEFTPADDING', (0, 0), (-1, -1), 0),
        ('RIGHTPADDING', (0, 0), (-1, -1), 0),
        ('TOPPADDING', (0, 0), (-1, -1), 0),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 0),
    ]))
    return t

def _two_col_doc(buf, sidebar_items, main_items, sidebar_bg, sidebar_text_color, sidebar_border):
    doc = SimpleDocTemplate(buf, pagesize=A4,
                            leftMargin=MARGIN, rightMargin=MARGIN,
                            topMargin=MARGIN, bottomMargin=MARGIN)
    body = Table([[sidebar_items, main_items]], colWidths=[SIDEBAR_W, MAIN_W])
    body.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (0, -1), sidebar_bg),
        ('VALIGN', (0, 0), (-1, -1), 'TOP'),
        ('LEFTPADDING', (0, 0), (0, -1), 10),
        ('RIGHTPADDING', (0, 0), (0, -1), 8),
        ('LEFTPADDING', (1, 0), (1, -1), 10),
        ('RIGHTPADDING', (1, 0), (1, -1), 0),
        ('TOPPADDING', (0, 0), (-1, -1), 8),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 6),
        ('LINEAFTER', (0, 0), (0, -1), 1, sidebar_border),
    ]))
    doc.build([body])

# ══════════════════════════════════════════════════════════════════════════════
# Generic single-column builder (used by templates 1,4,5,6,11,13,15-21)
# ══════════════════════════════════════════════════════════════════════════════

def _build_single_col(session_state, profile_img_bytes,
                      c_name, c_acc, c_text, c_muted,
                      c_pill_bg, c_pill_bd, c_hr,
                      name_size=22, center_header=True,
                      section_style='underline',
                      summary_label="Professional Summary",
                      exp_label="Work Experience",
                      edu_label="Education",
                      proj_label="Projects",
                      cert_label="Certifications",
                      skills_label="Technical Skills",
                      soft_label="Soft Skills",
                      lang_label="Languages",
                      interest_label="Interests"):
    buf = BytesIO()
    doc = SimpleDocTemplate(buf, pagesize=A4,
                            leftMargin=MARGIN, rightMargin=MARGIN,
                            topMargin=MARGIN, bottomMargin=MARGIN)
    ss = session_state
    W = PAGE_W - 2 * MARGIN
    align = TA_CENTER if center_header else TA_LEFT

    h_name  = ParagraphStyle('nm',  fontName='Helvetica-Bold',   fontSize=name_size, textColor=c_name,  alignment=align, leading=name_size + 6)
    h_title = ParagraphStyle('ht',  fontName='Helvetica-Oblique',fontSize=12,        textColor=c_acc,   alignment=align, leading=16, spaceAfter=4)
    h_cont  = ParagraphStyle('hc',  fontName='Helvetica',        fontSize=9,         textColor=c_muted, alignment=align, leading=13)
    h_sec   = ParagraphStyle('hs',  fontName='Helvetica-Bold',   fontSize=11,        textColor=c_name,  leading=16, spaceBefore=10, spaceAfter=4)
    p_n     = ParagraphStyle('pn',  fontName='Helvetica',        fontSize=10,        textColor=c_text,  leading=14, spaceAfter=2)
    p_b     = ParagraphStyle('pb',  fontName='Helvetica',        fontSize=10,        textColor=c_text,  leading=14)
    p_bld   = ParagraphStyle('pbl', fontName='Helvetica-Bold',   fontSize=10,        textColor=c_name,  leading=14)
    p_m     = ParagraphStyle('pm',  fontName='Helvetica',        fontSize=9,         textColor=c_muted, leading=13)
    p_a     = ParagraphStyle('pa',  fontName='Helvetica-Bold',   fontSize=9,         textColor=c_acc,   leading=13)
    base    = ParagraphStyle('bs',  fontName='Helvetica',        fontSize=9)

    story = []
    if profile_img_bytes:
        img_fl = _profile_image_flowable(profile_img_bytes, 70)
        if img_fl:
            story.append(img_fl)
            story.append(Spacer(1, 4))
    story.append(Paragraph(_get(ss, 'name') or 'Your Name', h_name))
    jt = _get(ss, 'job_title')
    if jt:
        story.append(Paragraph(jt, h_title))
    cp = [_get(ss, k) for k in ['email', 'phone', 'location', 'linkedin', 'github', 'portfolio'] if _get(ss, k)]
    if cp:
        story.append(Paragraph(' | '.join(cp), h_cont))
    story.append(HRFlowable(width=W, thickness=2, color=c_hr, spaceBefore=6, spaceAfter=8))

    def section(title):
        story.append(Paragraph(title, h_sec))
        story.append(HRFlowable(width=W, thickness=0.5, color=c_acc, spaceAfter=4))

    def row2(l, r):
        story.append(_row2_table(Paragraph(l, p_bld), Paragraph(r, p_a), W))

    sm = _get(ss, 'summary')
    if sm:
        section(summary_label)
        for fl in _build_desc_flowables(sm, p_n, p_b, c_acc):
            story.append(fl)

    exps = [e for e in _entries(ss, 'experience_entries') if e.get('company') or e.get('title')]
    if exps:
        section(exp_label)
        for e in exps:
            row2(f"{e.get('company', '')} — {e.get('title', '')}", e.get('duration', ''))
            for fl in _build_desc_flowables(e.get('description', ''), p_n, p_b, c_acc):
                story.append(fl)
            story.append(Spacer(1, 6))

    edus = [e for e in _entries(ss, 'education_entries') if e.get('institution') or e.get('degree')]
    if edus:
        section(edu_label)
        for e in edus:
            dv = e.get('degree', '')
            if isinstance(dv, list):
                dv = ', '.join(dv)
            row2(f"{e.get('institution', '')} — {dv}", e.get('year', ''))
            if e.get('details'):
                story.append(Paragraph(e['details'], p_m))
            story.append(Spacer(1, 4))

    if _get(ss, 'skills'):
        section(skills_label)
        story.extend(_pills_table(_get(ss, 'skills'), c_pill_bg, c_name, c_pill_bd, base))
    if _get(ss, 'Softskills'):
        section(soft_label)
        story.extend(_pills_table(_get(ss, 'Softskills'), c_pill_bg, c_acc, c_pill_bd, base))
    if _get(ss, 'languages'):
        section(lang_label)
        story.extend(_pills_table(_get(ss, 'languages'), c_pill_bg, c_name, c_pill_bd, base))
    if _get(ss, 'interests'):
        section(interest_label)
        story.extend(_pills_table(_get(ss, 'interests'), c_pill_bg, c_name, c_pill_bd, base))

    projs = [p for p in _entries(ss, 'project_entries') if p.get('title')]
    proj_links = _entries(ss, 'project_links')
    if projs:
        section(proj_label)
        for idx, p in enumerate(projs):
            lnk = proj_links[idx] if idx < len(proj_links) else ''
            t = p.get('title', '')
            if lnk:
                t = _safe_link(lnk, t, c_acc)
            story.append(Paragraph(t, p_bld))
            if p.get('tech'):
                story.extend(_pills_table(p['tech'], c_pill_bg, c_acc, c_pill_bd, base))
            for fl in _build_desc_flowables(p.get('description', ''), p_n, p_b, c_acc):
                story.append(fl)
            story.append(Spacer(1, 6))

    certs = [c for c in _entries(ss, 'certificate_links') if c.get('name')]
    if certs:
        section(cert_label)
        for c in certs:
            lnk = c.get('link', '').strip()
            nm = c.get('name', '')
            if lnk:
                nm = _safe_link(lnk, nm, c_acc)
            row2(nm, c.get('duration', ''))
            if c.get('description'):
                story.append(Paragraph(c['description'], p_m))
            story.append(Spacer(1, 4))

    doc.build(story)
    buf.seek(0)
    return buf


# ══════════════════════════════════════════════════════════════════════════════
# Generic two-column sidebar builder
# ══════════════════════════════════════════════════════════════════════════════

def _build_two_col(session_state, profile_img_bytes,
                   sb_bg, sb_pill_bg, sb_pill_bd, sb_hr_color,
                   acc_color, text_color, muted_color,
                   sb_name_color=None, sb_item_color=None, sb_title_color=None,
                   summary_label="Professional Summary",
                   exp_label="Work Experience",
                   edu_label="Education",
                   proj_label="Projects",
                   cert_label="Certifications"):
    buf = BytesIO()
    ss = session_state
    if sb_name_color is None:
        sb_name_color = colors.white
    if sb_item_color is None:
        sb_item_color = colors.HexColor('#e2e8f0')
    if sb_title_color is None:
        sb_title_color = colors.HexColor('#cbd5e1')

    sb_name  = ParagraphStyle('sbn', fontName='Helvetica-Bold',   fontSize=13, textColor=sb_name_color,  alignment=TA_CENTER, leading=18, spaceAfter=3)
    sb_title = ParagraphStyle('sbt', fontName='Helvetica-Oblique',fontSize=10, textColor=sb_title_color, alignment=TA_CENTER, leading=13, spaceAfter=8)
    sb_sec   = ParagraphStyle('sbs', fontName='Helvetica-Bold',   fontSize=9,  textColor=colors.white,   leading=12, spaceBefore=10, spaceAfter=3)
    sb_item  = ParagraphStyle('sbi', fontName='Helvetica',        fontSize=9,  textColor=sb_item_color,  leading=13, spaceAfter=2)
    sb_pill  = ParagraphStyle('sbp', fontName='Helvetica',        fontSize=9,  textColor=sb_bg,          alignment=TA_CENTER, leading=12)
    m_h_name = ParagraphStyle('mhn', fontName='Helvetica-Bold',   fontSize=18, textColor=sb_bg,          leading=24)
    m_sec    = ParagraphStyle('ms',  fontName='Helvetica-Bold',   fontSize=11, textColor=sb_bg,          leading=16, spaceBefore=10, spaceAfter=3)
    m_normal = ParagraphStyle('mn',  fontName='Helvetica',        fontSize=10, textColor=text_color,     leading=14, spaceAfter=2)
    m_bullet = ParagraphStyle('mb',  fontName='Helvetica',        fontSize=10, textColor=text_color,     leading=14)
    m_bold   = ParagraphStyle('mbl', fontName='Helvetica-Bold',   fontSize=10, textColor=text_color,     leading=14)
    m_muted  = ParagraphStyle('mm',  fontName='Helvetica',        fontSize=9,  textColor=muted_color,    leading=13)
    m_acc    = ParagraphStyle('ma',  fontName='Helvetica-Bold',   fontSize=9,  textColor=acc_color,      leading=13)

    def sb_section(title, sidebar):
        sidebar.append(HRFlowable(width=SIDEBAR_W - 18, thickness=0.5, color=sb_hr_color, spaceAfter=3))
        sidebar.append(Paragraph(title.upper(), sb_sec))

    def add_pill(text, sidebar):
        t = Table([[Paragraph(text, sb_pill)]], colWidths=[SIDEBAR_W - 18])
        t.setStyle(TableStyle([
            ('BACKGROUND', (0, 0), (-1, -1), sb_pill_bg),
            ('BOX', (0, 0), (-1, -1), 0.5, sb_pill_bd),
            ('TOPPADDING', (0, 0), (-1, -1), 2),
            ('BOTTOMPADDING', (0, 0), (-1, -1), 2),
            ('LEFTPADDING', (0, 0), (-1, -1), 4),
            ('RIGHTPADDING', (0, 0), (-1, -1), 4),
        ]))
        sidebar.append(t)
        sidebar.append(Spacer(1, 3))

    sidebar = []
    if profile_img_bytes:
        img_fl = _profile_image_flowable(profile_img_bytes, 80)
        if img_fl:
            sidebar.append(img_fl)
            sidebar.append(Spacer(1, 6))
    sidebar.append(Paragraph(_get(ss, 'name') or 'Your Name', sb_name))
    jt = _get(ss, 'job_title')
    if jt:
        sidebar.append(Paragraph(jt, sb_title))
    for k, lbl in [('email', 'Email'), ('phone', 'Phone'), ('location', 'Location'),
                   ('linkedin', 'LinkedIn'), ('github', 'GitHub'), ('portfolio', 'Portfolio')]:
        v = _get(ss, k)
        if v:
            sb_section(lbl, sidebar)
            sidebar.append(Paragraph(v, sb_item))
    for field, lbl in [('skills', 'Skills'), ('Softskills', 'Soft Skills'),
                       ('languages', 'Languages'), ('interests', 'Interests')]:
        v = _get(ss, field)
        if v:
            sb_section(lbl, sidebar)
            for item in [i.strip() for i in v.split(',') if i.strip()]:
                add_pill(item, sidebar)

    main = []
    main.append(Paragraph(_get(ss, 'name') or 'Your Name', m_h_name))
    main.append(HRFlowable(width=MAIN_W - 10, thickness=2, color=acc_color, spaceAfter=6, spaceBefore=4))

    def m_section(title):
        main.append(Paragraph(title, m_sec))
        main.append(HRFlowable(width=MAIN_W - 10, thickness=0.5, color=acc_color, spaceAfter=4))

    def m_row2(l, r):
        main.append(_row2_table(Paragraph(l, m_bold), Paragraph(r, m_acc), MAIN_W - 10))

    sm = _get(ss, 'summary')
    if sm:
        m_section(summary_label)
        for fl in _build_desc_flowables(sm, m_normal, m_bullet, acc_color):
            main.append(fl)

    exps = [e for e in _entries(ss, 'experience_entries') if e.get('company') or e.get('title')]
    if exps:
        m_section(exp_label)
        for e in exps:
            m_row2(f"{e.get('company', '')} — {e.get('title', '')}", e.get('duration', ''))
            for fl in _build_desc_flowables(e.get('description', ''), m_normal, m_bullet, acc_color):
                main.append(fl)
            main.append(Spacer(1, 6))

    edus = [e for e in _entries(ss, 'education_entries') if e.get('institution') or e.get('degree')]
    if edus:
        m_section(edu_label)
        for e in edus:
            dv = e.get('degree', '')
            if isinstance(dv, list):
                dv = ', '.join(dv)
            m_row2(f"{e.get('institution', '')} — {dv}", e.get('year', ''))
            if e.get('details'):
                main.append(Paragraph(e['details'], m_muted))
            main.append(Spacer(1, 4))

    projs = [p for p in _entries(ss, 'project_entries') if p.get('title')]
    proj_links = _entries(ss, 'project_links')
    if projs:
        m_section(proj_label)
        for idx, p in enumerate(projs):
            lnk = proj_links[idx] if idx < len(proj_links) else ''
            t = p.get('title', '')
            if lnk:
                t = _safe_link(lnk, t, acc_color)
            main.append(Paragraph(t, m_bold))
            if p.get('tech'):
                tech_items = [i.strip() for i in p['tech'].split(',') if i.strip()]
                main.append(Paragraph('  |  '.join(tech_items), m_muted))
            for fl in _build_desc_flowables(p.get('description', ''), m_normal, m_bullet, acc_color):
                main.append(fl)
            main.append(Spacer(1, 6))

    certs = [c for c in _entries(ss, 'certificate_links') if c.get('name')]
    if certs:
        m_section(cert_label)
        for c in certs:
            lnk = c.get('link', '').strip()
            nm = c.get('name', '')
            if lnk:
                nm = _safe_link(lnk, nm, acc_color)
            m_row2(nm, c.get('duration', ''))
            if c.get('description'):
                main.append(Paragraph(c['description'], m_muted))
            main.append(Spacer(1, 4))

    _two_col_doc(buf, sidebar, main, sb_bg, colors.white, sb_pill_bd)
    buf.seek(0)
    return buf

# ══════════════════════════════════════════════════════════════════════════════
# TEMPLATE 1 — Default Professional
# ══════════════════════════════════════════════════════════════════════════════
def render_template_default_professional(session_state, profile_img_bytes=None):
    return _build_single_col(
        session_state, profile_img_bytes,
        c_name=colors.HexColor('#2f4f6f'),
        c_acc=colors.HexColor('#3b82f6'),
        c_text=colors.HexColor('#1f2937'),
        c_muted=colors.HexColor('#6b7280'),
        c_pill_bg=colors.HexColor('#dbeafe'),
        c_pill_bd=colors.HexColor('#93c5fd'),
        c_hr=colors.HexColor('#3b82f6'),
        name_size=22,
        summary_label="Professional Summary",
        exp_label="Work Experience",
    )

# ══════════════════════════════════════════════════════════════════════════════
# TEMPLATE 2 — Modern Minimal
# ══════════════════════════════════════════════════════════════════════════════
def render_template_modern_minimal(session_state, profile_img_bytes=None):
    """Teal accents, left-aligned name, slim dividers."""
    buf = BytesIO()
    doc = SimpleDocTemplate(buf, pagesize=A4,
                            leftMargin=MARGIN, rightMargin=MARGIN,
                            topMargin=MARGIN, bottomMargin=MARGIN)
    ss = session_state
    W = PAGE_W - 2 * MARGIN
    C_ACC  = colors.HexColor('#0d9488')
    C_TEXT = colors.HexColor('#1f2937')
    C_MUTED= colors.HexColor('#6b7280')
    C_PILL = colors.HexColor('#f0fdfa')
    C_BD   = colors.HexColor('#99f6e4')

    h_name  = ParagraphStyle('nm', fontName='Helvetica-Bold',   fontSize=24, textColor=C_TEXT,  alignment=TA_LEFT, leading=30)
    h_title = ParagraphStyle('ht', fontName='Helvetica',        fontSize=13, textColor=C_ACC,   leading=18, spaceAfter=2)
    h_cont  = ParagraphStyle('hc', fontName='Helvetica',        fontSize=9,  textColor=C_MUTED, leading=13)
    h_sec   = ParagraphStyle('hs', fontName='Helvetica-Bold',   fontSize=10, textColor=C_ACC,   leading=14, spaceBefore=10, spaceAfter=2)
    p_n     = ParagraphStyle('pn', fontName='Helvetica',        fontSize=10, textColor=C_TEXT,  leading=14, spaceAfter=2)
    p_b     = ParagraphStyle('pb', fontName='Helvetica',        fontSize=10, textColor=C_TEXT,  leading=14)
    p_bld   = ParagraphStyle('pbl',fontName='Helvetica-Bold',   fontSize=10, textColor=C_TEXT,  leading=14)
    p_m     = ParagraphStyle('pm', fontName='Helvetica',        fontSize=9,  textColor=C_MUTED, leading=13)
    p_a     = ParagraphStyle('pa', fontName='Helvetica-Bold',   fontSize=9,  textColor=C_ACC,   leading=13)
    base    = ParagraphStyle('bs', fontName='Helvetica',        fontSize=9)

    story = []
    name_txt = _get(ss, 'name') or 'Your Name'
    jt = _get(ss, 'job_title')
    cp = [_get(ss, k) for k in ['email', 'phone', 'location', 'linkedin', 'github', 'portfolio'] if _get(ss, k)]

    if profile_img_bytes:
        img_fl = _profile_image_flowable(profile_img_bytes, 80)
        if img_fl:
            hdr_content = [Paragraph(name_txt, h_name)]
            if jt: hdr_content.append(Paragraph(jt, h_title))
            if cp: hdr_content.append(Paragraph(' · '.join(cp), h_cont))
            hdr = Table([[hdr_content, img_fl]], colWidths=[W - 90, 90])
            hdr.setStyle(TableStyle([('VALIGN', (0, 0), (-1, -1), 'TOP'),
                                     ('LEFTPADDING', (0, 0), (-1, -1), 0),
                                     ('RIGHTPADDING', (0, 0), (-1, -1), 0)]))
            story.append(hdr)
        else:
            story.append(Paragraph(name_txt, h_name))
            if jt: story.append(Paragraph(jt, h_title))
            if cp: story.append(Paragraph(' · '.join(cp), h_cont))
    else:
        story.append(Paragraph(name_txt, h_name))
        if jt: story.append(Paragraph(jt, h_title))
        if cp: story.append(Paragraph(' · '.join(cp), h_cont))

    story.append(HRFlowable(width=W, thickness=3, color=C_ACC, spaceBefore=6, spaceAfter=10))

    def section(title):
        story.append(Paragraph(title.upper(), h_sec))
        story.append(HRFlowable(width=W, thickness=0.5, color=C_ACC, spaceAfter=4))

    def row2(l, r):
        story.append(_row2_table(Paragraph(l, p_bld), Paragraph(r, p_a), W))

    sm = _get(ss, 'summary')
    if sm:
        section("Summary")
        for fl in _build_desc_flowables(sm, p_n, p_b, C_ACC): story.append(fl)

    exps = [e for e in _entries(ss, 'experience_entries') if e.get('company') or e.get('title')]
    if exps:
        section("Experience")
        for e in exps:
            row2(f"{e.get('company', '')} — {e.get('title', '')}", e.get('duration', ''))
            for fl in _build_desc_flowables(e.get('description', ''), p_n, p_b, C_ACC): story.append(fl)
            story.append(Spacer(1, 6))

    edus = [e for e in _entries(ss, 'education_entries') if e.get('institution') or e.get('degree')]
    if edus:
        section("Education")
        for e in edus:
            dv = e.get('degree', '')
            if isinstance(dv, list): dv = ', '.join(dv)
            row2(f"{e.get('institution', '')} — {dv}", e.get('year', ''))
            if e.get('details'): story.append(Paragraph(e['details'], p_m))
            story.append(Spacer(1, 4))

    if _get(ss, 'skills'):    section("Skills");      story.extend(_pills_table(_get(ss, 'skills'),    C_PILL, C_ACC,  C_BD, base))
    if _get(ss, 'Softskills'):section("Soft Skills"); story.extend(_pills_table(_get(ss, 'Softskills'),colors.HexColor('#f0f9ff'), colors.HexColor('#0369a1'), colors.HexColor('#7dd3fc'), base))
    if _get(ss, 'languages'): section("Languages");  story.extend(_pills_table(_get(ss, 'languages'), colors.HexColor('#fefce8'), colors.HexColor('#854d0e'), colors.HexColor('#fde047'), base))
    if _get(ss, 'interests'): section("Interests");  story.extend(_pills_table(_get(ss, 'interests'), colors.HexColor('#fff7ed'), colors.HexColor('#c2410c'), colors.HexColor('#fb923c'), base))

    projs = [p for p in _entries(ss, 'project_entries') if p.get('title')]
    proj_links = _entries(ss, 'project_links')
    if projs:
        section("Projects")
        for idx, p in enumerate(projs):
            lnk = proj_links[idx] if idx < len(proj_links) else ''
            t = p.get('title', '')
            if lnk: t = _safe_link(lnk, t, '#0d9488')
            story.append(Paragraph(t, p_bld))
            if p.get('tech'): story.extend(_pills_table(p['tech'], C_PILL, C_ACC, C_BD, base))
            for fl in _build_desc_flowables(p.get('description', ''), p_n, p_b, C_ACC): story.append(fl)
            story.append(Spacer(1, 6))

    certs = [c for c in _entries(ss, 'certificate_links') if c.get('name')]
    if certs:
        section("Certifications")
        for c in certs:
            lnk = c.get('link', '').strip(); nm = c.get('name', '')
            if lnk: nm = _safe_link(lnk, nm, '#0d9488')
            row2(nm, c.get('duration', ''))
            if c.get('description'): story.append(Paragraph(c['description'], p_m))
            story.append(Spacer(1, 4))

    doc.build(story)
    buf.seek(0)
    return buf

# ══════════════════════════════════════════════════════════════════════════════
# TEMPLATE 3 — Elegant Sidebar (two-col, purple)
# ══════════════════════════════════════════════════════════════════════════════
def render_template_elegant_sidebar(session_state, profile_img_bytes=None):
    return _build_two_col(
        session_state, profile_img_bytes,
        sb_bg=colors.HexColor('#7c3aed'),
        sb_pill_bg=colors.HexColor('#ede9fe'),
        sb_pill_bd=colors.HexColor('#a78bfa'),
        sb_hr_color=colors.HexColor('#c4b5fd'),
        acc_color=colors.HexColor('#7c3aed'),
        text_color=colors.HexColor('#1f2937'),
        muted_color=colors.HexColor('#6b7280'),
        sb_title_color=colors.HexColor('#e9d5ff'),
        summary_label="Professional Summary",
    )

# ══════════════════════════════════════════════════════════════════════════════
# TEMPLATE 4 — Classic Clean
# ══════════════════════════════════════════════════════════════════════════════
def render_template_classic_clean(session_state, profile_img_bytes=None):
    return _build_single_col(
        session_state, profile_img_bytes,
        c_name=colors.HexColor('#374151'),
        c_acc=colors.HexColor('#6b7280'),
        c_text=colors.HexColor('#374151'),
        c_muted=colors.HexColor('#9ca3af'),
        c_pill_bg=colors.HexColor('#f9fafb'),
        c_pill_bd=colors.HexColor('#d1d5db'),
        c_hr=colors.HexColor('#374151'),
        name_size=20,
    )

# ══════════════════════════════════════════════════════════════════════════════
# TEMPLATE 5 — Executive (single-col, navy/gold)
# ══════════════════════════════════════════════════════════════════════════════
def render_template_executive(session_state, profile_img_bytes=None):
    buf = BytesIO()
    doc = SimpleDocTemplate(buf, pagesize=A4,
                            leftMargin=MARGIN, rightMargin=MARGIN,
                            topMargin=MARGIN, bottomMargin=MARGIN)
    ss = session_state
    W = PAGE_W - 2 * MARGIN
    C_NAVY = colors.HexColor('#1e3a5f')
    C_GOLD = colors.HexColor('#b7791f')
    C_TEXT = colors.HexColor('#1a202c')
    C_MUTED= colors.HexColor('#718096')
    C_BG   = colors.HexColor('#eff6ff')
    C_BD   = colors.HexColor('#93c5fd')

    h_name  = ParagraphStyle('nm', fontName='Helvetica-Bold',   fontSize=26, textColor=C_NAVY, alignment=TA_CENTER, leading=32, spaceAfter=4)
    h_title = ParagraphStyle('ht', fontName='Helvetica-Oblique',fontSize=14, textColor=C_GOLD, alignment=TA_CENTER, leading=18, spaceAfter=4)
    h_cont  = ParagraphStyle('hc', fontName='Helvetica',        fontSize=9,  textColor=C_MUTED,alignment=TA_CENTER, leading=13)
    h_sec   = ParagraphStyle('hs', fontName='Helvetica-Bold',   fontSize=12, textColor=C_NAVY, leading=18, spaceBefore=12, spaceAfter=4)
    p_n     = ParagraphStyle('pn', fontName='Helvetica',        fontSize=10, textColor=C_TEXT, leading=15, spaceAfter=3, alignment=TA_JUSTIFY)
    p_b     = ParagraphStyle('pb', fontName='Helvetica',        fontSize=10, textColor=C_TEXT, leading=15)
    p_bld   = ParagraphStyle('pbl',fontName='Helvetica-Bold',   fontSize=11, textColor=C_NAVY, leading=15)
    p_m     = ParagraphStyle('pm', fontName='Helvetica',        fontSize=9,  textColor=C_MUTED,leading=13)
    p_a     = ParagraphStyle('pa', fontName='Helvetica-Bold',   fontSize=9,  textColor=C_GOLD, leading=13)
    base    = ParagraphStyle('bs', fontName='Helvetica',        fontSize=9)

    story = []
    if profile_img_bytes:
        img_fl = _profile_image_flowable(profile_img_bytes, 80)
        if img_fl: story.append(img_fl); story.append(Spacer(1, 4))
    story.append(Paragraph(_get(ss, 'name') or 'Your Name', h_name))
    jt = _get(ss, 'job_title')
    if jt: story.append(Paragraph(jt, h_title))
    cp = [_get(ss, k) for k in ['email', 'phone', 'location', 'linkedin', 'github', 'portfolio'] if _get(ss, k)]
    if cp: story.append(Paragraph(' | '.join(cp), h_cont))
    story.append(HRFlowable(width=W, thickness=2.5, color=C_NAVY, spaceBefore=8, spaceAfter=4))
    story.append(HRFlowable(width=W, thickness=0.5, color=C_GOLD, spaceAfter=10))

    def section(title):
        story.append(Paragraph(title, h_sec))
        story.append(HRFlowable(width=W, thickness=1, color=C_NAVY, spaceAfter=6))

    def row2(l, r):
        story.append(_row2_table(Paragraph(l, p_bld), Paragraph(r, p_a), W))

    sm = _get(ss, 'summary')
    if sm:
        section("Executive Summary")
        for fl in _build_desc_flowables(sm, p_n, p_b, C_NAVY): story.append(fl)

    exps = [e for e in _entries(ss, 'experience_entries') if e.get('company') or e.get('title')]
    if exps:
        section("Professional Experience")
        for e in exps:
            row2(e.get('company', ''), e.get('duration', ''))
            if e.get('title'): story.append(Paragraph(e['title'], p_m))
            for fl in _build_desc_flowables(e.get('description', ''), p_n, p_b, C_NAVY): story.append(fl)
            story.append(Spacer(1, 8))

    edus = [e for e in _entries(ss, 'education_entries') if e.get('institution') or e.get('degree')]
    if edus:
        section("Education")
        for e in edus:
            dv = e.get('degree', '')
            if isinstance(dv, list): dv = ', '.join(dv)
            row2(f"{e.get('institution', '')} — {dv}", e.get('year', ''))
            if e.get('details'): story.append(Paragraph(e['details'], p_m))
            story.append(Spacer(1, 6))

    if _get(ss, 'skills'):    section("Core Competencies");      story.extend(_pills_table(_get(ss, 'skills'),    C_BG, C_NAVY, C_BD, base))
    if _get(ss, 'Softskills'):section("Leadership & Soft Skills");story.extend(_pills_table(_get(ss, 'Softskills'),C_BG, C_GOLD, C_BD, base))
    if _get(ss, 'languages'): section("Languages");               story.extend(_pills_table(_get(ss, 'languages'), C_BG, C_NAVY, C_BD, base))
    if _get(ss, 'interests'): section("Interests");               story.extend(_pills_table(_get(ss, 'interests'), C_BG, C_MUTED,C_BD, base))

    projs = [p for p in _entries(ss, 'project_entries') if p.get('title')]
    proj_links = _entries(ss, 'project_links')
    if projs:
        section("Key Projects")
        for idx, p in enumerate(projs):
            lnk = proj_links[idx] if idx < len(proj_links) else ''
            t = p.get('title', '')
            if lnk: t = _safe_link(lnk, t, '#1e3a5f')
            story.append(Paragraph(t, p_bld))
            if p.get('tech'): story.extend(_pills_table(p['tech'], C_BG, C_NAVY, C_BD, base))
            for fl in _build_desc_flowables(p.get('description', ''), p_n, p_b, C_NAVY): story.append(fl)
            story.append(Spacer(1, 6))

    certs = [c for c in _entries(ss, 'certificate_links') if c.get('name')]
    if certs:
        section("Certifications & Awards")
        for c in certs:
            lnk = c.get('link', '').strip(); nm = c.get('name', '')
            if lnk: nm = _safe_link(lnk, nm, '#1e3a5f')
            row2(nm, c.get('duration', ''))
            if c.get('description'): story.append(Paragraph(c['description'], p_m))
            story.append(Spacer(1, 4))

    doc.build(story)
    buf.seek(0)
    return buf

# ══════════════════════════════════════════════════════════════════════════════
# TEMPLATE 6 — Timeline (amber dot-spine layout)
# ══════════════════════════════════════════════════════════════════════════════
def render_template_timeline(session_state, profile_img_bytes=None):
    buf = BytesIO()
    doc = SimpleDocTemplate(buf, pagesize=A4,
                            leftMargin=MARGIN, rightMargin=MARGIN,
                            topMargin=MARGIN, bottomMargin=MARGIN)
    ss = session_state
    W = PAGE_W - 2 * MARGIN
    C_TL   = colors.HexColor('#b45309')
    C_DOT  = colors.HexColor('#f59e0b')
    C_TEXT = colors.HexColor('#374151')
    C_MUTED= colors.HexColor('#9ca3af')
    C_PILL = colors.HexColor('#fef3c7')
    C_BD   = colors.HexColor('#fcd34d')

    h_name  = ParagraphStyle('nm', fontName='Helvetica-Bold',   fontSize=22, textColor=C_TL,   alignment=TA_LEFT,   leading=28)
    h_title = ParagraphStyle('ht', fontName='Helvetica-Oblique',fontSize=13, textColor=C_TEXT,  leading=16, spaceAfter=4)
    h_cont  = ParagraphStyle('hc', fontName='Helvetica',        fontSize=9,  textColor=C_MUTED, leading=13)
    h_sec   = ParagraphStyle('hs', fontName='Helvetica-Bold',   fontSize=11, textColor=C_TL,    leading=16, spaceBefore=12, spaceAfter=4)
    p_n     = ParagraphStyle('pn', fontName='Helvetica',        fontSize=10, textColor=C_TEXT,  leading=14, spaceAfter=2)
    p_b     = ParagraphStyle('pb', fontName='Helvetica',        fontSize=10, textColor=C_TEXT,  leading=14)
    p_bld   = ParagraphStyle('pbl',fontName='Helvetica-Bold',   fontSize=10, textColor=C_TL,    leading=14)
    p_m     = ParagraphStyle('pm', fontName='Helvetica',        fontSize=9,  textColor=C_MUTED, leading=13)
    p_dur   = ParagraphStyle('pd', fontName='Helvetica-Bold',   fontSize=9,  textColor=C_DOT,   leading=13)
    base    = ParagraphStyle('bs', fontName='Helvetica',        fontSize=9)

    story = []
    story.append(Paragraph(_get(ss, 'name') or 'Your Name', h_name))
    jt = _get(ss, 'job_title')
    if jt: story.append(Paragraph(jt, h_title))
    cp = [_get(ss, k) for k in ['email', 'phone', 'location', 'linkedin', 'github', 'portfolio'] if _get(ss, k)]
    if cp: story.append(Paragraph(' | '.join(cp), h_cont))
    story.append(HRFlowable(width=W, thickness=2, color=C_TL, spaceBefore=6, spaceAfter=10))

    def section(title):
        story.append(Paragraph(title, h_sec))
        story.append(HRFlowable(width=W, thickness=0.5, color=C_TL, spaceAfter=4))

    def tl_entry(title, subtitle, duration, desc):
        dot_s = ParagraphStyle('dot', fontName='Helvetica-Bold', fontSize=14, textColor=C_DOT, leading=18)
        dot   = Paragraph('●', dot_s)
        content = [Paragraph(f'<b>{title}</b>', p_bld)]
        if subtitle: content.append(Paragraph(subtitle, p_m))
        if duration: content.append(Paragraph(duration, p_dur))
        if desc:
            for fl in _build_desc_flowables(desc, p_n, p_b, C_TL): content.append(fl)
        content.append(Spacer(1, 4))
        row = Table([[dot, content]], colWidths=[20, W - 20])
        row.setStyle(TableStyle([('VALIGN', (0, 0), (-1, -1), 'TOP'),
                                 ('LEFTPADDING', (0, 0), (-1, -1), 0),
                                 ('RIGHTPADDING', (0, 0), (-1, -1), 0),
                                 ('TOPPADDING', (0, 0), (-1, -1), 2),
                                 ('BOTTOMPADDING', (0, 0), (-1, -1), 4)]))
        story.append(row)

    sm = _get(ss, 'summary')
    if sm:
        section("Profile")
        for fl in _build_desc_flowables(sm, p_n, p_b, C_TL): story.append(fl)

    exps = [e for e in _entries(ss, 'experience_entries') if e.get('company') or e.get('title')]
    if exps:
        section("Work Experience")
        for e in exps:
            tl_entry(e.get('company', ''), e.get('title', ''), e.get('duration', ''), e.get('description', ''))

    edus = [e for e in _entries(ss, 'education_entries') if e.get('institution') or e.get('degree')]
    if edus:
        section("Education")
        for e in edus:
            dv = e.get('degree', '')
            if isinstance(dv, list): dv = ', '.join(dv)
            tl_entry(e.get('institution', ''), dv, e.get('year', ''), e.get('details', ''))

    if _get(ss, 'skills'):    section("Skills");      story.extend(_pills_table(_get(ss, 'skills'),    C_PILL, C_TL,  C_BD, base))
    if _get(ss, 'Softskills'):section("Soft Skills"); story.extend(_pills_table(_get(ss, 'Softskills'),C_PILL, C_TEXT,C_BD, base))
    if _get(ss, 'languages'): section("Languages");  story.extend(_pills_table(_get(ss, 'languages'), C_PILL, C_TL,  C_BD, base))
    if _get(ss, 'interests'): section("Interests");  story.extend(_pills_table(_get(ss, 'interests'), C_PILL, C_TL,  C_BD, base))

    projs = [p for p in _entries(ss, 'project_entries') if p.get('title')]
    proj_links = _entries(ss, 'project_links')
    if projs:
        section("Projects")
        for idx, p in enumerate(projs):
            lnk = proj_links[idx] if idx < len(proj_links) else ''
            t = p.get('title', '')
            if lnk: t = _safe_link(lnk, t, '#b45309')
            tl_entry(t, '', p.get('duration', ''), p.get('description', ''))
            if p.get('tech'): story.extend(_pills_table(p['tech'], C_PILL, C_TL, C_BD, base))

    certs = [c for c in _entries(ss, 'certificate_links') if c.get('name')]
    if certs:
        section("Certifications")
        for c in certs:
            lnk = c.get('link', '').strip(); nm = c.get('name', '')
            if lnk: nm = _safe_link(lnk, nm, '#b45309')
            tl_entry(nm, c.get('description', ''), c.get('duration', ''), '')

    doc.build(story)
    buf.seek(0)
    return buf

# ══════════════════════════════════════════════════════════════════════════════
# TEMPLATES 7-15 — Two-column and remaining single-column via generic builders
# ══════════════════════════════════════════════════════════════════════════════

def render_template_corporate_blue(session_state, profile_img_bytes=None):
    return _build_two_col(
        session_state, profile_img_bytes,
        sb_bg=colors.HexColor('#1d4ed8'),
        sb_pill_bg=colors.HexColor('#dbeafe'),
        sb_pill_bd=colors.HexColor('#93c5fd'),
        sb_hr_color=colors.HexColor('#60a5fa'),
        acc_color=colors.HexColor('#2563eb'),
        text_color=colors.HexColor('#1e293b'),
        muted_color=colors.HexColor('#64748b'),
        sb_title_color=colors.HexColor('#bfdbfe'),
    )

def render_template_creative_green(session_state, profile_img_bytes=None):
    return _build_two_col(
        session_state, profile_img_bytes,
        sb_bg=colors.HexColor('#166534'),
        sb_pill_bg=colors.HexColor('#dcfce7'),
        sb_pill_bd=colors.HexColor('#86efac'),
        sb_hr_color=colors.HexColor('#4ade80'),
        acc_color=colors.HexColor('#16a34a'),
        text_color=colors.HexColor('#1a2e1a'),
        muted_color=colors.HexColor('#6b7280'),
        sb_title_color=colors.HexColor('#bbf7d0'),
    )

def render_template_warm_terracotta(session_state, profile_img_bytes=None):
    return _build_two_col(
        session_state, profile_img_bytes,
        sb_bg=colors.HexColor('#c2410c'),
        sb_pill_bg=colors.HexColor('#ffedd5'),
        sb_pill_bd=colors.HexColor('#fdba74'),
        sb_hr_color=colors.HexColor('#fb923c'),
        acc_color=colors.HexColor('#ea580c'),
        text_color=colors.HexColor('#1c1917'),
        muted_color=colors.HexColor('#78716c'),
        sb_title_color=colors.HexColor('#fed7aa'),
    )

def render_template_navy_prestige(session_state, profile_img_bytes=None):
    """Navy sidebar with gold accents."""
    buf = BytesIO()
    ss = session_state
    C_SB   = colors.HexColor('#1e3a5f')
    C_GOLD = colors.HexColor('#f59e0b')
    C_ACC  = colors.HexColor('#2563eb')
    C_TEXT = colors.HexColor('#1e293b')
    C_MUTED= colors.HexColor('#64748b')
    C_SB_BD= colors.HexColor('#3b82f6')

    sb_name  = ParagraphStyle('sbn', fontName='Helvetica-Bold',   fontSize=13, textColor=colors.white,   alignment=TA_CENTER, leading=18, spaceAfter=3)
    sb_title = ParagraphStyle('sbt', fontName='Helvetica-Oblique',fontSize=10, textColor=C_GOLD,         alignment=TA_CENTER, leading=13, spaceAfter=8)
    sb_sec   = ParagraphStyle('sbs', fontName='Helvetica-Bold',   fontSize=9,  textColor=C_GOLD,         leading=12, spaceBefore=10, spaceAfter=3)
    sb_item  = ParagraphStyle('sbi', fontName='Helvetica',        fontSize=9,  textColor=colors.HexColor('#e2e8f0'), leading=13, spaceAfter=2)
    sb_pill  = ParagraphStyle('sbp', fontName='Helvetica',        fontSize=9,  textColor=C_SB,           alignment=TA_CENTER, leading=12)
    m_h_name = ParagraphStyle('mhn', fontName='Helvetica-Bold',   fontSize=18, textColor=C_SB,           leading=24)
    m_sec    = ParagraphStyle('ms',  fontName='Helvetica-Bold',   fontSize=11, textColor=C_SB,           leading=16, spaceBefore=10, spaceAfter=3)
    m_normal = ParagraphStyle('mn',  fontName='Helvetica',        fontSize=10, textColor=C_TEXT,         leading=14, spaceAfter=2)
    m_bullet = ParagraphStyle('mb',  fontName='Helvetica',        fontSize=10, textColor=C_TEXT,         leading=14)
    m_bold   = ParagraphStyle('mbl', fontName='Helvetica-Bold',   fontSize=10, textColor=C_TEXT,         leading=14)
    m_muted  = ParagraphStyle('mm',  fontName='Helvetica',        fontSize=9,  textColor=C_MUTED,        leading=13)
    m_acc    = ParagraphStyle('ma',  fontName='Helvetica-Bold',   fontSize=9,  textColor=C_ACC,          leading=13)

    def sb_section(title, sidebar):
        sidebar.append(HRFlowable(width=SIDEBAR_W - 18, thickness=0.5, color=C_GOLD, spaceAfter=3))
        sidebar.append(Paragraph(title.upper(), sb_sec))

    def add_pill(text, sidebar):
        t = Table([[Paragraph(text, sb_pill)]], colWidths=[SIDEBAR_W - 18])
        t.setStyle(TableStyle([('BACKGROUND', (0,0),(-1,-1), colors.HexColor('#eff6ff')),
                                ('BOX',(0,0),(-1,-1),0.5,C_SB_BD),
                                ('TOPPADDING',(0,0),(-1,-1),2),('BOTTOMPADDING',(0,0),(-1,-1),2),
                                ('LEFTPADDING',(0,0),(-1,-1),4),('RIGHTPADDING',(0,0),(-1,-1),4)]))
        sidebar.append(t); sidebar.append(Spacer(1,3))

    sidebar = []
    if profile_img_bytes:
        img_fl = _profile_image_flowable(profile_img_bytes, 80)
        if img_fl: sidebar.append(img_fl); sidebar.append(Spacer(1,6))
    sidebar.append(Paragraph(_get(ss,'name') or 'Your Name', sb_name))
    jt = _get(ss,'job_title')
    if jt: sidebar.append(Paragraph(jt, sb_title))
    for k,lbl in [('email','Email'),('phone','Phone'),('location','Location'),('linkedin','LinkedIn'),('github','GitHub'),('portfolio','Portfolio')]:
        v = _get(ss,k)
        if v: sb_section(lbl, sidebar); sidebar.append(Paragraph(v, sb_item))
    for field,lbl in [('skills','Skills'),('Softskills','Soft Skills'),('languages','Languages'),('interests','Interests')]:
        v = _get(ss,field)
        if v:
            sb_section(lbl, sidebar)
            for item in [i.strip() for i in v.split(',') if i.strip()]: add_pill(item, sidebar)

    main = []
    main.append(Paragraph(_get(ss,'name') or 'Your Name', m_h_name))
    main.append(HRFlowable(width=MAIN_W-10, thickness=2, color=C_SB, spaceAfter=2, spaceBefore=4))
    main.append(HRFlowable(width=MAIN_W-10, thickness=1, color=C_GOLD, spaceAfter=6))

    def m_section(title):
        main.append(Paragraph(title, m_sec))
        main.append(HRFlowable(width=MAIN_W-10, thickness=0.5, color=C_SB, spaceAfter=4))
    def m_row2(l,r):
        main.append(_row2_table(Paragraph(l,m_bold), Paragraph(r,m_acc), MAIN_W-10))

    sm = _get(ss,'summary')
    if sm:
        m_section("Professional Summary")
        for fl in _build_desc_flowables(sm,m_normal,m_bullet,C_ACC): main.append(fl)

    exps = [e for e in _entries(ss,'experience_entries') if e.get('company') or e.get('title')]
    if exps:
        m_section("Work Experience")
        for e in exps:
            m_row2(f"{e.get('company','')} — {e.get('title','')}", e.get('duration',''))
            for fl in _build_desc_flowables(e.get('description',''),m_normal,m_bullet,C_ACC): main.append(fl)
            main.append(Spacer(1,6))

    edus = [e for e in _entries(ss,'education_entries') if e.get('institution') or e.get('degree')]
    if edus:
        m_section("Education")
        for e in edus:
            dv = e.get('degree','')
            if isinstance(dv,list): dv=', '.join(dv)
            m_row2(f"{e.get('institution','')} — {dv}", e.get('year',''))
            if e.get('details'): main.append(Paragraph(e['details'],m_muted))
            main.append(Spacer(1,4))

    projs = [p for p in _entries(ss,'project_entries') if p.get('title')]
    proj_links = _entries(ss,'project_links')
    if projs:
        m_section("Projects")
        for idx,p in enumerate(projs):
            lnk = proj_links[idx] if idx < len(proj_links) else ''
            t = p.get('title','')
            if lnk: t = _safe_link(lnk,t,'#1e3a5f')
            main.append(Paragraph(t,m_bold))
            if p.get('tech'): main.append(Paragraph('  |  '.join([i.strip() for i in p['tech'].split(',') if i.strip()]),m_muted))
            for fl in _build_desc_flowables(p.get('description',''),m_normal,m_bullet,C_ACC): main.append(fl)
            main.append(Spacer(1,6))

    certs = [c for c in _entries(ss,'certificate_links') if c.get('name')]
    if certs:
        m_section("Certifications")
        for c in certs:
            lnk = c.get('link','').strip(); nm = c.get('name','')
            if lnk: nm = _safe_link(lnk,nm,'#1e3a5f')
            m_row2(nm, c.get('duration',''))
            if c.get('description'): main.append(Paragraph(c['description'],m_muted))
            main.append(Spacer(1,4))

    _two_col_doc(buf, sidebar, main, C_SB, colors.white, C_SB_BD)
    buf.seek(0)
    return buf

def render_template_slate_gray(session_state, profile_img_bytes=None):
    return _build_single_col(
        session_state, profile_img_bytes,
        c_name=colors.HexColor('#334155'),
        c_acc=colors.HexColor('#475569'),
        c_text=colors.HexColor('#334155'),
        c_muted=colors.HexColor('#94a3b8'),
        c_pill_bg=colors.HexColor('#f1f5f9'),
        c_pill_bd=colors.HexColor('#cbd5e1'),
        c_hr=colors.HexColor('#334155'),
        name_size=22,
        summary_label="Summary",
        exp_label="Experience",
    )

def render_template_teal_impact(session_state, profile_img_bytes=None):
    return _build_two_col(
        session_state, profile_img_bytes,
        sb_bg=colors.HexColor('#0f766e'),
        sb_pill_bg=colors.HexColor('#ccfbf1'),
        sb_pill_bd=colors.HexColor('#5eead4'),
        sb_hr_color=colors.HexColor('#2dd4bf'),
        acc_color=colors.HexColor('#0d9488'),
        text_color=colors.HexColor('#1a2e2e'),
        muted_color=colors.HexColor('#6b7280'),
        sb_title_color=colors.HexColor('#99f6e4'),
    )

def render_template_burgundy_classic(session_state, profile_img_bytes=None):
    return _build_single_col(
        session_state, profile_img_bytes,
        c_name=colors.HexColor('#881337'),
        c_acc=colors.HexColor('#9f1239'),
        c_text=colors.HexColor('#1a0a0a'),
        c_muted=colors.HexColor('#78716c'),
        c_pill_bg=colors.HexColor('#fff1f2'),
        c_pill_bd=colors.HexColor('#fda4af'),
        c_hr=colors.HexColor('#881337'),
        name_size=22,
        summary_label="Professional Summary",
        exp_label="Work Experience",
        skills_label="Technical Skills",
    )

def render_template_indigo_tech(session_state, profile_img_bytes=None):
    return _build_two_col(
        session_state, profile_img_bytes,
        sb_bg=colors.HexColor('#4338ca'),
        sb_pill_bg=colors.HexColor('#e0e7ff'),
        sb_pill_bd=colors.HexColor('#a5b4fc'),
        sb_hr_color=colors.HexColor('#818cf8'),
        acc_color=colors.HexColor('#4f46e5'),
        text_color=colors.HexColor('#1e1b4b'),
        muted_color=colors.HexColor('#6b7280'),
        sb_title_color=colors.HexColor('#c7d2fe'),
    )

def render_template_forest_green(session_state, profile_img_bytes=None):
    return _build_single_col(
        session_state, profile_img_bytes,
        c_name=colors.HexColor('#14532d'),
        c_acc=colors.HexColor('#15803d'),
        c_text=colors.HexColor('#1a2e1a'),
        c_muted=colors.HexColor('#6b7280'),
        c_pill_bg=colors.HexColor('#f0fdf4'),
        c_pill_bd=colors.HexColor('#86efac'),
        c_hr=colors.HexColor('#14532d'),
        name_size=22,
        summary_label="About Me",
    )

# ══════════════════════════════════════════════════════════════════════════════
# TEMPLATES 16-21 — Premium minimal single-column
# ══════════════════════════════════════════════════════════════════════════════

def render_template_pure_white(session_state, profile_img_bytes=None):
    return _build_single_col(
        session_state, profile_img_bytes,
        c_name=colors.HexColor('#111111'),
        c_acc=colors.HexColor('#374151'),
        c_text=colors.HexColor('#374151'),
        c_muted=colors.HexColor('#9ca3af'),
        c_pill_bg=colors.HexColor('#f9fafb'),
        c_pill_bd=colors.HexColor('#e5e7eb'),
        c_hr=colors.HexColor('#111111'),
        name_size=24,
    )

def render_template_midnight_black(session_state, profile_img_bytes=None):
    return _build_single_col(
        session_state, profile_img_bytes,
        c_name=colors.HexColor('#f59e0b'),
        c_acc=colors.HexColor('#fbbf24'),
        c_text=colors.HexColor('#e5e7eb'),
        c_muted=colors.HexColor('#9ca3af'),
        c_pill_bg=colors.HexColor('#1f2937'),
        c_pill_bd=colors.HexColor('#374151'),
        c_hr=colors.HexColor('#f59e0b'),
        name_size=24,
        center_header=False,
    )

def render_template_soft_lavender(session_state, profile_img_bytes=None):
    return _build_single_col(
        session_state, profile_img_bytes,
        c_name=colors.HexColor('#6366f1'),
        c_acc=colors.HexColor('#7c3aed'),
        c_text=colors.HexColor('#374151'),
        c_muted=colors.HexColor('#9ca3af'),
        c_pill_bg=colors.HexColor('#f5f3ff'),
        c_pill_bd=colors.HexColor('#ddd6fe'),
        c_hr=colors.HexColor('#6366f1'),
        name_size=22,
    )

def render_template_warm_sand(session_state, profile_img_bytes=None):
    return _build_single_col(
        session_state, profile_img_bytes,
        c_name=colors.HexColor('#92400e'),
        c_acc=colors.HexColor('#b45309'),
        c_text=colors.HexColor('#44403c'),
        c_muted=colors.HexColor('#a8a29e'),
        c_pill_bg=colors.HexColor('#fef3c7'),
        c_pill_bd=colors.HexColor('#fcd34d'),
        c_hr=colors.HexColor('#d97706'),
        name_size=22,
    )

def render_template_ice_blue(session_state, profile_img_bytes=None):
    return _build_single_col(
        session_state, profile_img_bytes,
        c_name=colors.HexColor('#0369a1'),
        c_acc=colors.HexColor('#0ea5e9'),
        c_text=colors.HexColor('#0c4a6e'),
        c_muted=colors.HexColor('#64748b'),
        c_pill_bg=colors.HexColor('#f0f9ff'),
        c_pill_bd=colors.HexColor('#bae6fd'),
        c_hr=colors.HexColor('#0369a1'),
        name_size=22,
    )

def render_template_rose_gold(session_state, profile_img_bytes=None):
    return _build_single_col(
        session_state, profile_img_bytes,
        c_name=colors.HexColor('#be185d'),
        c_acc=colors.HexColor('#db2777'),
        c_text=colors.HexColor('#4a044e'),
        c_muted=colors.HexColor('#9ca3af'),
        c_pill_bg=colors.HexColor('#fdf2f8'),
        c_pill_bd=colors.HexColor('#f0abfc'),
        c_hr=colors.HexColor('#be185d'),
        name_size=22,
    )

# ── Backward-compat aliases ────────────────────────────────────────────────────
render_template_default      = render_template_default_professional
render_template_modern       = render_template_modern_minimal
render_template_sidebar      = render_template_elegant_sidebar
render_template_classic      = render_template_classic_clean
render_template_executive    = render_template_executive
render_template_corporate    = render_template_corporate_blue
render_template_terracotta   = render_template_warm_terracotta
render_template_slate_gray   = render_template_slate_gray
render_template_teal_impact  = render_template_teal_impact
render_template_burgundy_classic = render_template_burgundy_classic
render_template_indigo_tech  = render_template_indigo_tech
render_template_forest_green = render_template_forest_green

# ── Template registry ─────────────────────────────────────────────────────────
RESUME_TEMPLATES = {
    "Default Professional":  render_template_default_professional,
    "Modern Minimal":        render_template_modern_minimal,
    "Elegant Sidebar":       render_template_elegant_sidebar,
    "Classic Clean":         render_template_classic_clean,
    "Executive":             render_template_executive,
    "Timeline":              render_template_timeline,
    "Corporate Blue":        render_template_corporate_blue,
    "Creative Green":        render_template_creative_green,
    "Warm Terracotta":       render_template_warm_terracotta,
    "Navy Prestige":         render_template_navy_prestige,
    "Slate Gray":            render_template_slate_gray,
    "Teal Impact":           render_template_teal_impact,
    "Burgundy Classic":      render_template_burgundy_classic,
    "Indigo Tech":           render_template_indigo_tech,
    "Forest Green":          render_template_forest_green,
    "Pure White":            render_template_pure_white,
    "Midnight Black":        render_template_midnight_black,
    "Soft Lavender":         render_template_soft_lavender,
    "Warm Sand":             render_template_warm_sand,
    "Ice Blue":              render_template_ice_blue,
    "Rose Gold":             render_template_rose_gold,
}

# Legacy display-name keys (taab2.py uses these in TEMPLATE_META)
RESUME_TEMPLATES["Default (Professional)"]           = render_template_default_professional
RESUME_TEMPLATES["Modern Minimal"]                   = render_template_modern_minimal
RESUME_TEMPLATES["Elegant Sidebar"]                  = render_template_elegant_sidebar
RESUME_TEMPLATES["Classic Clean (Single Column)"]    = render_template_classic_clean
RESUME_TEMPLATES["Executive (Single Column)"]        = render_template_executive
RESUME_TEMPLATES["Timeline (Single Column)"]         = render_template_timeline
RESUME_TEMPLATES["Corporate Blue (Two Column)"]      = render_template_corporate_blue
RESUME_TEMPLATES["Creative Green (Two Column)"]      = render_template_creative_green
RESUME_TEMPLATES["Warm Terracotta (Two Column)"]     = render_template_warm_terracotta
RESUME_TEMPLATES["Navy Prestige (Two Column)"]       = render_template_navy_prestige
RESUME_TEMPLATES["Slate Gray (Single Column)"]       = render_template_slate_gray
RESUME_TEMPLATES["Teal Impact (Two Column)"]         = render_template_teal_impact
RESUME_TEMPLATES["Burgundy Classic (Single Column)"] = render_template_burgundy_classic
RESUME_TEMPLATES["Indigo Tech (Two Column)"]         = render_template_indigo_tech
RESUME_TEMPLATES["Forest Green (Single Column)"]     = render_template_forest_green
RESUME_TEMPLATES["Pure White (Single Column)"]       = render_template_pure_white
RESUME_TEMPLATES["Midnight Black (Single Column)"]   = render_template_midnight_black
RESUME_TEMPLATES["Soft Lavender (Single Column)"]    = render_template_soft_lavender
RESUME_TEMPLATES["Warm Sand (Single Column)"]        = render_template_warm_sand
RESUME_TEMPLATES["Ice Blue (Single Column)"]         = render_template_ice_blue
RESUME_TEMPLATES["Rose Gold (Single Column)"]        = render_template_rose_gold


def render_resume(template_name, session_state, profile_img_bytes=None):
    """
    Render a resume from a named template. Returns BytesIO PDF.
    profile_img_bytes: raw image bytes (not base64).
    Falls back to Default Professional if template name not found.
    """
    fn = RESUME_TEMPLATES.get(template_name, render_template_default_professional)
    return fn(session_state, profile_img_bytes)


# ── HTML-compat shims (not used in PDF path; kept for any imports) ─────────────
def _fmt_desc(text, **kwargs):
    return text or ""

def _cert_name_html(cert, link_style, span_style=""):
    return cert.get('name', '')
