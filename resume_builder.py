# resume_builder.py — 21 ATS-friendly resume templates
# All section logic lives once in _render_single_col / _render_two_col.
# Templates are thin theme configs — zero logic duplication.

from io import BytesIO
from reportlab.lib.pagesizes import A4
from reportlab.lib import colors
from reportlab.lib.units import mm
from reportlab.lib.styles import ParagraphStyle
from reportlab.lib.enums import TA_LEFT, TA_CENTER, TA_RIGHT, TA_JUSTIFY
from reportlab.platypus import (
    SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle,
    HRFlowable, ListFlowable, ListItem, Image,
)

PAGE_W, PAGE_H = A4
MARGIN    = 15 * mm
SIDEBAR_W = 160
MAIN_W    = PAGE_W - 2 * MARGIN - SIDEBAR_W - 6  # ≈ 380


# ─────────────────────────────────────────────────────────────────────────────
# DATA HELPERS
# ─────────────────────────────────────────────────────────────────────────────

def _get(ss, key, default=""):
    if isinstance(ss, dict):
        return ss.get(key, default) or default
    return getattr(ss, key, default) or default

def _entries(ss, key, default=None):
    default = default or []
    if isinstance(ss, dict):
        return ss.get(key, default) or default
    return getattr(ss, key, default) or default

def _skills_list(raw):
    """Split a comma/newline-separated skills string into a clean list."""
    items = []
    for chunk in str(raw).replace('\n', ',').split(','):
        s = chunk.strip().strip('-•*·>–—★✦').strip()
        if s:
            items.append(s)
    return items

def _deg(e):
    d = e.get('degree', '')
    return ', '.join(d) if isinstance(d, list) else d

def _img(b, size=80):
    if not b:
        return None
    try:
        return Image(BytesIO(b), width=size, height=size)
    except Exception:
        return None

def _link(url, label, hex_color):
    if not url:
        return label
    if not url.startswith('http'):
        url = 'https://' + url
    return f'<link href="{url}"><font color="{hex_color}">{label}</font></link>'


# ─────────────────────────────────────────────────────────────────────────────
# FLOWABLE BUILDERS
# ─────────────────────────────────────────────────────────────────────────────

def _parse_bullets(text):
    PREFIXES = ("-", "•", "*", "·", ">", "–", "—", "★", "✦")
    result = []
    for line in str(text).replace('\r\n', '\n').replace('\r', '\n').split('\n'):
        s = line.strip()
        if not s:
            continue
        is_b = False
        for p in PREFIXES:
            if s.startswith(p):
                s = s[len(p):].strip()
                is_b = True
                break
        result.append((is_b, s))
    return result

def _bullets(text, style_normal, style_bullet, bullet_color=None):
    """Render bulleted/plain text. Returns a list of flowables."""
    if not text or not str(text).strip():
        return []
    items = _parse_bullets(text)
    if not items:
        return []
    out, buf = [], []

    def flush():
        if buf:
            out.append(ListFlowable(
                [ListItem(Paragraph(t, style_bullet), leftIndent=12,
                          bulletColor=bullet_color or colors.black) for t in buf],
                bulletType='bullet', start='•', leftIndent=8, bulletFontSize=7))
            buf.clear()

    for is_b, content in items:
        if is_b:
            buf.append(content)
        else:
            flush()
            out.append(Paragraph(content, style_normal))
    flush()
    return out

def _skills_inline(raw, style):
    """Render skills as plain comma-separated text — ATS-friendly, never breaks."""
    items = _skills_list(raw)
    if not items:
        return []
    return [Paragraph(', '.join(items), style), Spacer(1, 4)]

def _skills_2col(raw, style, width):
    """Two-column bulleted skills list."""
    items = _skills_list(raw)
    if not items:
        return []
    rows = []
    for i in range(0, len(items), 2):
        left = Paragraph(f'• {items[i]}', style)
        right = Paragraph(f'• {items[i+1]}', style) if i + 1 < len(items) else Paragraph('', style)
        rows.append([left, right])
    t = Table(rows, colWidths=[width / 2, width / 2])
    t.setStyle(TableStyle([
        ('LEFTPADDING',  (0,0), (-1,-1), 0),
        ('RIGHTPADDING', (0,0), (-1,-1), 0),
        ('TOPPADDING',   (0,0), (-1,-1), 1),
        ('BOTTOMPADDING',(0,0), (-1,-1), 1),
    ]))
    return [t, Spacer(1, 4)]

def _row2(left_para, right_para, width, lw=0.72):
    """Two-cell row: left content, right content right-aligned."""
    t = Table([[left_para, right_para]], colWidths=[width * lw, width * (1 - lw)])
    t.setStyle(TableStyle([
        ('ALIGN',        (1,0), (1,0), 'RIGHT'),
        ('VALIGN',       (0,0), (-1,-1), 'TOP'),
        ('LEFTPADDING',  (0,0), (-1,-1), 0),
        ('RIGHTPADDING', (0,0), (-1,-1), 0),
        ('TOPPADDING',   (0,0), (-1,-1), 0),
        ('BOTTOMPADDING',(0,0), (-1,-1), 0),
    ]))
    return t

def _new_doc(buf):
    return SimpleDocTemplate(buf, pagesize=A4,
                             leftMargin=MARGIN, rightMargin=MARGIN,
                             topMargin=MARGIN, bottomMargin=MARGIN)


# ─────────────────────────────────────────────────────────────────────────────
# TWO-COLUMN LAYOUT ENGINE
# ─────────────────────────────────────────────────────────────────────────────

def _two_col(buf, sidebar_items, main_items, sb_bg, sb_bd):
    """Frame-based two-column layout with painted sidebar background."""
    from reportlab.platypus import BaseDocTemplate, Frame, PageTemplate, FrameBreak
    from reportlab.pdfgen.canvas import Canvas as _BaseCanvas

    SB_X = MARGIN
    MN_X = MARGIN + SIDEBAR_W + 6
    PH   = PAGE_H - 2 * MARGIN

    def _canvas_factory(bg, bd):
        class _C(_BaseCanvas):
            def showPage(self):
                self.saveState()
                self.setFillColor(bg)
                self.setStrokeColor(bd)
                self.rect(SB_X, MARGIN, SIDEBAR_W, PH, fill=1, stroke=1)
                self.restoreState()
                super().showPage()
            def save(self):
                self.saveState()
                self.setFillColor(bg)
                self.setStrokeColor(bd)
                self.rect(SB_X, MARGIN, SIDEBAR_W, PH, fill=1, stroke=1)
                self.restoreState()
                super().save()
        return _C

    sb_frame = Frame(SB_X, MARGIN, SIDEBAR_W, PH,
                     leftPadding=10, rightPadding=8, topPadding=8, bottomPadding=6,
                     showBoundary=0)
    mn_frame = Frame(MN_X, MARGIN, MAIN_W, PH,
                     leftPadding=10, rightPadding=4, topPadding=8, bottomPadding=6,
                     showBoundary=0)

    doc = BaseDocTemplate(buf, pagesize=A4,
                          leftMargin=MARGIN, rightMargin=MARGIN,
                          topMargin=MARGIN, bottomMargin=MARGIN)
    doc.addPageTemplates([PageTemplate(id='twocol', frames=[sb_frame, mn_frame])])
    flowables = list(sidebar_items) + [FrameBreak()] + list(main_items)
    doc.build(flowables, canvasmaker=_canvas_factory(sb_bg, sb_bd))


# ─────────────────────────────────────────────────────────────────────────────
# CORE SECTION RENDERER  (used by both layouts)
# ─────────────────────────────────────────────────────────────────────────────

def _build_sections(ss, styles, width, story, link_hex, skills_mode='inline'):
    """
    Append all resume sections to `story`.

    styles  – dict with keys: PN (normal), PB (bullet), BD (bold), MU (muted),
              DT (date), SK (skills)
    skills_mode – 'inline' | '2col'
    """
    PN  = styles['PN']
    PB  = styles['PB']
    BD  = styles['BD']
    MU  = styles['MU']
    DT  = styles['DT']
    SK  = styles['SK']
    sec = styles['_sec']   # callable(title) → appends header to story

    # ── Summary ──────────────────────────────────────────────────────────────
    sm = _get(ss, 'summary')
    if sm:
        sec("Professional Summary")
        for f in _bullets(sm, PN, PB):
            story.append(f)
        story.append(Spacer(1, 4))

    # ── Work Experience ───────────────────────────────────────────────────────
    exps = [e for e in _entries(ss, 'experience_entries')
            if e.get('company') or e.get('title')]
    if exps:
        sec("Work Experience")
        for e in exps:
            company = e.get('company', '')
            title   = e.get('title', '')
            dur     = e.get('duration', '')
            label   = f"<b>{company}</b>" + (f" — {title}" if title else '')
            story.append(_row2(Paragraph(label, BD), Paragraph(dur, DT), width))
            for f in _bullets(e.get('description', ''), PN, PB):
                story.append(f)
            story.append(Spacer(1, 6))

    # ── Education ─────────────────────────────────────────────────────────────
    edus = [e for e in _entries(ss, 'education_entries')
            if e.get('institution') or e.get('degree')]
    if edus:
        sec("Education")
        for e in edus:
            inst  = e.get('institution', '')
            deg   = _deg(e)
            label = f"<b>{inst}</b>" + (f" — {deg}" if deg else '')
            story.append(_row2(Paragraph(label, BD), Paragraph(e.get('year', ''), DT), width))
            if e.get('details'):
                story.append(Paragraph(e['details'], MU))
            story.append(Spacer(1, 4))

    # ── Skills ────────────────────────────────────────────────────────────────
    for field, label in [('skills',     'Technical Skills'),
                         ('Softskills', 'Soft Skills'),
                         ('languages',  'Languages'),
                         ('interests',  'Interests')]:
        v = _get(ss, field)
        if v:
            sec(label)
            if skills_mode == '2col':
                story.extend(_skills_2col(v, SK, width))
            else:
                story.extend(_skills_inline(v, SK))

    # ── Projects ──────────────────────────────────────────────────────────────
    projs      = [p for p in _entries(ss, 'project_entries') if p.get('title')]
    proj_links = _entries(ss, 'project_links')
    if projs:
        sec("Projects")
        for i, p in enumerate(projs):
            lnk   = proj_links[i] if i < len(proj_links) else ''
            title = _link(lnk, p.get('title', ''), link_hex) if lnk else p.get('title', '')
            tech  = p.get('tech', '').strip()
            # Tech displayed as plain text on the same line — never a pill table
            heading = f"<b>{title}</b>"
            if tech:
                heading += f"  |  <font color='grey'>{tech}</font>"
            story.append(Paragraph(heading, BD))
            for f in _bullets(p.get('description', ''), PN, PB):
                story.append(f)
            story.append(Spacer(1, 6))

    # ── Certifications ────────────────────────────────────────────────────────
    certs = [c for c in _entries(ss, 'certificate_links') if c.get('name')]
    if certs:
        sec("Certifications")
        for c in certs:
            nm = (_link(c.get('link', ''), c.get('name', ''), link_hex)
                  if c.get('link') else c.get('name', ''))
            story.append(_row2(Paragraph(nm, BD), Paragraph(c.get('duration', ''), DT), width))
            if c.get('description'):
                story.append(Paragraph(c['description'], MU))
            story.append(Spacer(1, 4))


# ─────────────────────────────────────────────────────────────────────────────
# SINGLE-COLUMN RENDERER
# ─────────────────────────────────────────────────────────────────────────────

def _render_single_col(session_state, profile_img_bytes, theme):
    """
    theme keys:
        accent        – primary color (HexColor)
        heading       – name/section heading color
        muted         – secondary text color
        link_hex      – link color as '#xxxxxx' string
        name_size     – name font size (default 22)
        name_align    – TA_LEFT / TA_CENTER
        sec_style     – 'underline' | 'banner' | 'caps_hr' | 'left_bar'
        skills_mode   – 'inline' | '2col'
        name_upper    – bool: force name to uppercase
    """
    acc        = theme['accent']
    head_col   = theme.get('heading', acc)
    muted      = theme.get('muted',   colors.HexColor('#6b7280'))
    body_col   = theme.get('body',    colors.HexColor('#1f2937'))
    link_hex   = theme.get('link_hex', '#1d4ed8')
    name_size  = theme.get('name_size', 22)
    name_align = theme.get('name_align', TA_LEFT)
    sec_style  = theme.get('sec_style', 'underline')
    skills_mode= theme.get('skills_mode', 'inline')
    name_upper = theme.get('name_upper', False)

    buf = BytesIO()
    ss  = session_state
    W   = PAGE_W - 2 * MARGIN
    doc = _new_doc(buf)

    # ── Styles ────────────────────────────────────────────────────────────────
    NM = ParagraphStyle('NM', fontName='Helvetica-Bold',   fontSize=name_size,
                        textColor=head_col, alignment=name_align, leading=name_size + 6)
    JT = ParagraphStyle('JT', fontName='Helvetica-Oblique',fontSize=12,
                        textColor=acc, alignment=name_align, leading=16, spaceAfter=2)
    CO = ParagraphStyle('CO', fontName='Helvetica',        fontSize=9,
                        textColor=muted, alignment=name_align, leading=13)
    SH = ParagraphStyle('SH', fontName='Helvetica-Bold',   fontSize=11,
                        textColor=head_col, leading=15, spaceBefore=10, spaceAfter=3)
    PN = ParagraphStyle('PN', fontName='Helvetica',        fontSize=10,
                        textColor=body_col, leading=14, spaceAfter=2)
    PB = ParagraphStyle('PB', fontName='Helvetica',        fontSize=10,
                        textColor=body_col, leading=14)
    BD = ParagraphStyle('BD', fontName='Helvetica-Bold',   fontSize=10,
                        textColor=head_col, leading=14)
    MU = ParagraphStyle('MU', fontName='Helvetica',        fontSize=9,
                        textColor=muted, leading=13)
    DT = ParagraphStyle('DT', fontName='Helvetica-Bold',   fontSize=9,
                        textColor=acc, leading=13)
    SK = ParagraphStyle('SK', fontName='Helvetica',        fontSize=10,
                        textColor=body_col, leading=14)

    story = []

    # ── Header ────────────────────────────────────────────────────────────────
    name = _get(ss, 'name') or 'Your Name'
    if name_upper:
        name = name.upper()
    jt = _get(ss, 'job_title')
    cp = [_get(ss, k) for k in ['email','phone','location','linkedin','github','portfolio']
          if _get(ss, k)]
    iv = _img(profile_img_bytes, 72)

    if sec_style == 'banner':
        # Colored banner header
        hdr_items = [Paragraph(name, NM)]
        if jt: hdr_items.append(Paragraph(jt, JT))
        if cp: hdr_items.append(Paragraph('  |  '.join(cp), CO))
        if iv:
            inner = Table([[hdr_items, iv]], colWidths=[W - 80, 80])
            inner.setStyle(TableStyle([('VALIGN',(0,0),(-1,-1),'MIDDLE'),
                                        ('LEFTPADDING',(0,0),(-1,-1),0),
                                        ('RIGHTPADDING',(0,0),(-1,-1),0)]))
            hdr_items = [inner]
        band = Table([[hdr_items]], colWidths=[W])
        band.setStyle(TableStyle([
            ('BACKGROUND',   (0,0),(-1,-1), theme.get('banner_bg', acc)),
            ('TOPPADDING',   (0,0),(-1,-1), 14),
            ('BOTTOMPADDING',(0,0),(-1,-1), 14),
            ('LEFTPADDING',  (0,0),(-1,-1), 14),
            ('RIGHTPADDING', (0,0),(-1,-1), 14),
        ]))
        story.append(band)
        story.append(Spacer(1, 8))
    else:
        # Standard stacked header (photo right if present)
        hdr_block = [Paragraph(name, NM)]
        if jt: hdr_block.append(Paragraph(jt, JT))
        if cp: hdr_block.append(Paragraph('  |  '.join(cp), CO))
        if iv:
            row = Table([[hdr_block, iv]], colWidths=[W - 80, 80])
            row.setStyle(TableStyle([('VALIGN',(0,0),(-1,-1),'TOP'),
                                      ('LEFTPADDING',(0,0),(-1,-1),0),
                                      ('RIGHTPADDING',(0,0),(-1,-1),0)]))
            story.append(row)
        else:
            for fl in hdr_block:
                story.append(fl)
        story.append(HRFlowable(width=W, thickness=2, color=acc, spaceBefore=6, spaceAfter=8))

    # ── Section header factory ────────────────────────────────────────────────
    if sec_style in ('underline', 'banner'):
        def _sec(title):
            story.append(Paragraph(title, SH))
            story.append(HRFlowable(width=W, thickness=0.5, color=acc, spaceAfter=4))

    elif sec_style == 'caps_hr':
        SH_CAPS = ParagraphStyle('SHC', fontName='Helvetica-Bold', fontSize=9,
                                 textColor=head_col, leading=13,
                                 spaceBefore=14, spaceAfter=2, wordSpace=2)
        def _sec(title):
            story.append(Paragraph(title.upper(), SH_CAPS))
            story.append(HRFlowable(width=W, thickness=0.5, color=acc, spaceAfter=4))

    elif sec_style == 'full_banner':
        SH_WH = ParagraphStyle('SHWH', fontName='Helvetica-Bold', fontSize=10,
                               textColor=colors.white, leading=14)
        def _sec(title):
            bx = Table([[Paragraph(f'  {title}', SH_WH)]], colWidths=[W])
            bx.setStyle(TableStyle([
                ('BACKGROUND',   (0,0),(-1,-1), theme.get('banner_bg', acc)),
                ('TOPPADDING',   (0,0),(-1,-1), 4),
                ('BOTTOMPADDING',(0,0),(-1,-1), 4),
                ('LEFTPADDING',  (0,0),(-1,-1), 6),
                ('RIGHTPADDING', (0,0),(-1,-1), 6),
            ]))
            story.append(bx)
            story.append(Spacer(1, 5))

    elif sec_style == 'box_bg':
        SH_BG = ParagraphStyle('SHBG', fontName='Helvetica-Bold', fontSize=11,
                               textColor=head_col, leading=15, spaceAfter=2)
        bg_col = theme.get('sec_bg', colors.HexColor('#f3f4f6'))
        def _sec(title):
            bx = Table([[Paragraph(f'  {title}', SH_BG)]], colWidths=[W])
            bx.setStyle(TableStyle([
                ('BACKGROUND',   (0,0),(-1,-1), bg_col),
                ('TOPPADDING',   (0,0),(-1,-1), 4),
                ('BOTTOMPADDING',(0,0),(-1,-1), 4),
                ('LEFTPADDING',  (0,0),(-1,-1), 6),
                ('RIGHTPADDING', (0,0),(-1,-1), 6),
            ]))
            story.append(bx)
            story.append(Spacer(1, 4))

    else:  # plain / italic
        def _sec(title):
            story.append(Paragraph(title, SH))
            story.append(HRFlowable(width=W, thickness=0.5, color=acc, spaceAfter=4))

    # ── Sections ──────────────────────────────────────────────────────────────
    styles = dict(PN=PN, PB=PB, BD=BD, MU=MU, DT=DT, SK=SK, _sec=_sec)
    _build_sections(ss, styles, W, story, link_hex, skills_mode)

    doc.build(story)
    buf.seek(0)
    return buf


# ─────────────────────────────────────────────────────────────────────────────
# TWO-COLUMN RENDERER
# ─────────────────────────────────────────────────────────────────────────────

def _render_two_col(session_state, profile_img_bytes, theme):
    """
    theme keys (in addition to _render_single_col keys):
        sb_bg         – sidebar background color
        sb_bd         – sidebar border/rule color
        sb_txt        – sidebar body text color
        sb_light      – sidebar light text / subtext color
        main_heading  – main panel heading color (defaults to accent)
    """
    acc       = theme['accent']
    sb_bg     = theme.get('sb_bg',  acc)
    sb_bd     = theme.get('sb_bd',  acc)
    sb_txt    = theme.get('sb_txt', colors.white)
    sb_light  = theme.get('sb_light', colors.HexColor('#e0e0e0'))
    muted     = theme.get('muted',    colors.HexColor('#6b7280'))
    body_col  = theme.get('body',     colors.HexColor('#1f2937'))
    m_head    = theme.get('main_heading', acc)
    link_hex  = theme.get('link_hex', '#1d4ed8')
    skills_mode = theme.get('skills_mode', 'inline')

    buf = BytesIO()
    ss  = session_state
    SW  = SIDEBAR_W - 18   # usable sidebar width
    MW  = MAIN_W - 12      # usable main width

    # ── Sidebar styles ────────────────────────────────────────────────────────
    sbN = ParagraphStyle('sbN', fontName='Helvetica-Bold',   fontSize=13,
                         textColor=sb_txt, alignment=TA_CENTER, leading=18, spaceAfter=2)
    sbT = ParagraphStyle('sbT', fontName='Helvetica-Oblique',fontSize=10,
                         textColor=sb_light, alignment=TA_CENTER, leading=13, spaceAfter=6)
    sbS = ParagraphStyle('sbS', fontName='Helvetica-Bold',   fontSize=8,
                         textColor=sb_light, leading=12, spaceBefore=10, spaceAfter=2)
    sbI = ParagraphStyle('sbI', fontName='Helvetica',        fontSize=9,
                         textColor=sb_light, leading=13, spaceAfter=3)
    sbK = ParagraphStyle('sbK', fontName='Helvetica',        fontSize=9,
                         textColor=sb_txt, leading=13, spaceAfter=2)

    # ── Main styles ───────────────────────────────────────────────────────────
    mH  = ParagraphStyle('mH',  fontName='Helvetica-Bold',   fontSize=11,
                         textColor=m_head, leading=15, spaceBefore=10, spaceAfter=3)
    mN  = ParagraphStyle('mN',  fontName='Helvetica',        fontSize=10,
                         textColor=body_col, leading=14, spaceAfter=2)
    mB  = ParagraphStyle('mB',  fontName='Helvetica',        fontSize=10,
                         textColor=body_col, leading=14)
    mBD = ParagraphStyle('mBD', fontName='Helvetica-Bold',   fontSize=10,
                         textColor=m_head, leading=14)
    mMU = ParagraphStyle('mMU', fontName='Helvetica',        fontSize=9,
                         textColor=muted, leading=13)
    mDT = ParagraphStyle('mDT', fontName='Helvetica-Bold',   fontSize=9,
                         textColor=acc, leading=13)
    mSK = ParagraphStyle('mSK', fontName='Helvetica',        fontSize=10,
                         textColor=body_col, leading=14)

    # ── Build sidebar ─────────────────────────────────────────────────────────
    def sb_sec(title, sidebar):
        sidebar.append(HRFlowable(width=SW, thickness=0.4, color=sb_bd, spaceAfter=2))
        sidebar.append(Paragraph(title.upper(), sbS))

    sidebar = []
    iv = _img(profile_img_bytes, 80)
    if iv:
        sidebar += [iv, Spacer(1, 6)]
    sidebar.append(Paragraph(_get(ss, 'name') or 'Your Name', sbN))
    if _get(ss, 'job_title'):
        sidebar.append(Paragraph(_get(ss, 'job_title'), sbT))

    # Contact info
    for k, lbl in [('email','Email'), ('phone','Phone'), ('location','Location'),
                   ('linkedin','LinkedIn'), ('github','GitHub'), ('portfolio','Portfolio')]:
        v = _get(ss, k)
        if v:
            sb_sec(lbl, sidebar)
            sidebar.append(Paragraph(v, sbI))

    # Skills in sidebar — always as inline comma-separated text (ATS-safe)
    for field, lbl in [('skills','Skills'), ('Softskills','Soft Skills'),
                       ('languages','Languages'), ('interests','Interests')]:
        v = _get(ss, field)
        if v:
            sb_sec(lbl, sidebar)
            sidebar.extend(_skills_inline(v, sbK))

    # ── Build main ────────────────────────────────────────────────────────────
    main = []

    def m_sec(title):
        main.append(Paragraph(title, mH))
        main.append(HRFlowable(width=MW, thickness=0.5, color=sb_bd, spaceAfter=4))

    styles = dict(PN=mN, PB=mB, BD=mBD, MU=mMU, DT=mDT, SK=mSK, _sec=m_sec)
    _build_sections(ss, styles, MW, main, link_hex, skills_mode)

    _two_col(buf, sidebar, main, sb_bg, sb_bd)
    buf.seek(0)
    return buf


# ═════════════════════════════════════════════════════════════════════════════
# 21 TEMPLATE FUNCTIONS  — each is a thin wrapper around a renderer + theme
# ═════════════════════════════════════════════════════════════════════════════

def render_template_default_professional(ss, img=None):
    return _render_single_col(ss, img, dict(
        accent=colors.HexColor('#3b82f6'),
        heading=colors.HexColor('#1e3a5f'),
        muted=colors.HexColor('#6b7280'),
        body=colors.HexColor('#1f2937'),
        link_hex='#3b82f6',
        name_size=22, name_align=TA_CENTER,
        sec_style='underline',
        skills_mode='inline',
    ))

def render_template_modern_minimal(ss, img=None):
    return _render_single_col(ss, img, dict(
        accent=colors.HexColor('#0d9488'),
        heading=colors.HexColor('#0d9488'),
        muted=colors.HexColor('#6b7280'),
        body=colors.HexColor('#1f2937'),
        link_hex='#0d9488',
        name_size=26, name_align=TA_LEFT,
        sec_style='caps_hr',
        skills_mode='inline',
    ))

def render_template_elegant_sidebar(ss, img=None):
    return _render_two_col(ss, img, dict(
        accent=colors.HexColor('#7c3aed'),
        sb_bg=colors.HexColor('#7c3aed'),
        sb_bd=colors.HexColor('#a78bfa'),
        sb_txt=colors.white,
        sb_light=colors.HexColor('#ede9fe'),
        body=colors.HexColor('#1f2937'),
        muted=colors.HexColor('#6b7280'),
        main_heading=colors.HexColor('#7c3aed'),
        link_hex='#7c3aed',
        skills_mode='inline',
    ))

def render_template_classic_clean(ss, img=None):
    return _render_single_col(ss, img, dict(
        accent=colors.HexColor('#374151'),
        heading=colors.HexColor('#111827'),
        muted=colors.HexColor('#6b7280'),
        body=colors.HexColor('#374151'),
        link_hex='#374151',
        name_size=22, name_align=TA_CENTER,
        sec_style='caps_hr',
        skills_mode='2col',
    ))

def render_template_executive(ss, img=None):
    return _render_single_col(ss, img, dict(
        accent=colors.HexColor('#b45309'),   # gold
        heading=colors.HexColor('#1e3a5f'),  # navy
        muted=colors.HexColor('#6b7280'),
        body=colors.HexColor('#1e293b'),
        link_hex='#1e3a5f',
        name_size=22, name_align=TA_LEFT,
        sec_style='underline',
        skills_mode='2col',
    ))

def render_template_timeline(ss, img=None):
    return _render_single_col(ss, img, dict(
        accent=colors.HexColor('#f59e0b'),
        heading=colors.HexColor('#b45309'),
        muted=colors.HexColor('#9ca3af'),
        body=colors.HexColor('#374151'),
        link_hex='#b45309',
        name_size=22, name_align=TA_LEFT,
        sec_style='caps_hr',
        skills_mode='inline',
    ))

def render_template_corporate_blue(ss, img=None):
    return _render_two_col(ss, img, dict(
        accent=colors.HexColor('#1d4ed8'),
        sb_bg=colors.HexColor('#1d4ed8'),
        sb_bd=colors.HexColor('#93c5fd'),
        sb_txt=colors.white,
        sb_light=colors.HexColor('#dbeafe'),
        body=colors.HexColor('#1e293b'),
        muted=colors.HexColor('#64748b'),
        main_heading=colors.HexColor('#1d4ed8'),
        link_hex='#1d4ed8',
        skills_mode='inline',
    ))

def render_template_creative_green(ss, img=None):
    return _render_two_col(ss, img, dict(
        accent=colors.HexColor('#166534'),
        sb_bg=colors.HexColor('#166534'),
        sb_bd=colors.HexColor('#86efac'),
        sb_txt=colors.white,
        sb_light=colors.HexColor('#dcfce7'),
        body=colors.HexColor('#1a2e1a'),
        muted=colors.HexColor('#6b7280'),
        main_heading=colors.HexColor('#166534'),
        link_hex='#166534',
        skills_mode='inline',
    ))

def render_template_warm_terracotta(ss, img=None):
    return _render_two_col(ss, img, dict(
        accent=colors.HexColor('#c2410c'),
        sb_bg=colors.HexColor('#c2410c'),
        sb_bd=colors.HexColor('#fdba74'),
        sb_txt=colors.white,
        sb_light=colors.HexColor('#ffedd5'),
        body=colors.HexColor('#1c1917'),
        muted=colors.HexColor('#78716c'),
        main_heading=colors.HexColor('#c2410c'),
        link_hex='#c2410c',
        skills_mode='inline',
    ))

def render_template_navy_prestige(ss, img=None):
    return _render_single_col(ss, img, dict(
        accent=colors.HexColor('#b45309'),   # gold accent
        heading=colors.HexColor('#1e3a5f'),  # navy
        muted=colors.HexColor('#6b7280'),
        body=colors.HexColor('#1e293b'),
        link_hex='#1e3a5f',
        name_size=22, name_align=TA_LEFT,
        sec_style='underline',
        skills_mode='2col',
    ))

def render_template_slate_gray(ss, img=None):
    return _render_single_col(ss, img, dict(
        accent=colors.HexColor('#475569'),
        heading=colors.HexColor('#334155'),
        muted=colors.HexColor('#94a3b8'),
        body=colors.HexColor('#1e293b'),
        link_hex='#334155',
        name_size=22, name_align=TA_LEFT,
        sec_style='banner',
        banner_bg=colors.HexColor('#334155'),
        skills_mode='inline',
    ))

def render_template_teal_impact(ss, img=None):
    return _render_two_col(ss, img, dict(
        accent=colors.HexColor('#0f766e'),
        sb_bg=colors.HexColor('#0f766e'),
        sb_bd=colors.HexColor('#5eead4'),
        sb_txt=colors.white,
        sb_light=colors.HexColor('#ccfbf1'),
        body=colors.HexColor('#1a2e2e'),
        muted=colors.HexColor('#6b7280'),
        main_heading=colors.HexColor('#0f766e'),
        link_hex='#0f766e',
        skills_mode='inline',
    ))

def render_template_burgundy_classic(ss, img=None):
    return _render_single_col(ss, img, dict(
        accent=colors.HexColor('#881337'),
        heading=colors.HexColor('#881337'),
        muted=colors.HexColor('#78716c'),
        body=colors.HexColor('#1a0a0a'),
        link_hex='#881337',
        name_size=20, name_align=TA_CENTER,
        sec_style='underline',
        skills_mode='2col',
        name_upper=True,
    ))

def render_template_indigo_tech(ss, img=None):
    return _render_two_col(ss, img, dict(
        accent=colors.HexColor('#4338ca'),
        sb_bg=colors.HexColor('#4338ca'),
        sb_bd=colors.HexColor('#a5b4fc'),
        sb_txt=colors.white,
        sb_light=colors.HexColor('#e0e7ff'),
        body=colors.HexColor('#1e1b4b'),
        muted=colors.HexColor('#6b7280'),
        main_heading=colors.HexColor('#4338ca'),
        link_hex='#4338ca',
        skills_mode='inline',
    ))

def render_template_forest_green(ss, img=None):
    return _render_single_col(ss, img, dict(
        accent=colors.HexColor('#15803d'),
        heading=colors.HexColor('#14532d'),
        muted=colors.HexColor('#6b7280'),
        body=colors.HexColor('#1a2e1a'),
        link_hex='#14532d',
        name_size=22, name_align=TA_LEFT,
        sec_style='full_banner',
        banner_bg=colors.HexColor('#14532d'),
        skills_mode='inline',
    ))

def render_template_pure_white(ss, img=None):
    return _render_single_col(ss, img, dict(
        accent=colors.HexColor('#9ca3af'),
        heading=colors.HexColor('#111111'),
        muted=colors.HexColor('#9ca3af'),
        body=colors.HexColor('#374151'),
        link_hex='#374151',
        name_size=28, name_align=TA_LEFT,
        sec_style='caps_hr',
        skills_mode='inline',
    ))

def render_template_midnight_black(ss, img=None):
    return _render_single_col(ss, img, dict(
        accent=colors.HexColor('#f59e0b'),  # gold on dark
        heading=colors.HexColor('#f9fafb'),
        muted=colors.HexColor('#9ca3af'),
        body=colors.HexColor('#e5e7eb'),
        link_hex='#f59e0b',
        name_size=22, name_align=TA_LEFT,
        sec_style='box_bg',
        sec_bg=colors.HexColor('#1f2937'),
        skills_mode='inline',
    ))

def render_template_soft_lavender(ss, img=None):
    return _render_single_col(ss, img, dict(
        accent=colors.HexColor('#6366f1'),
        heading=colors.HexColor('#7c3aed'),
        muted=colors.HexColor('#9ca3af'),
        body=colors.HexColor('#374151'),
        link_hex='#6366f1',
        name_size=22, name_align=TA_LEFT,
        sec_style='banner',
        banner_bg=colors.HexColor('#f5f3ff'),
        skills_mode='inline',
    ))

def render_template_warm_sand(ss, img=None):
    return _render_single_col(ss, img, dict(
        accent=colors.HexColor('#b45309'),
        heading=colors.HexColor('#92400e'),
        muted=colors.HexColor('#a8a29e'),
        body=colors.HexColor('#44403c'),
        link_hex='#92400e',
        name_size=22, name_align=TA_LEFT,
        sec_style='underline',
        skills_mode='inline',
    ))

def render_template_ice_blue(ss, img=None):
    return _render_single_col(ss, img, dict(
        accent=colors.HexColor('#0369a1'),
        heading=colors.HexColor('#0c4a6e'),
        muted=colors.HexColor('#94a3b8'),
        body=colors.HexColor('#1e3a5f'),
        link_hex='#0369a1',
        name_size=22, name_align=TA_LEFT,
        sec_style='full_banner',
        banner_bg=colors.HexColor('#0c4a6e'),
        skills_mode='inline',
    ))

def render_template_rose_gold(ss, img=None):
    return _render_single_col(ss, img, dict(
        accent=colors.HexColor('#db2777'),
        heading=colors.HexColor('#be185d'),
        muted=colors.HexColor('#9ca3af'),
        body=colors.HexColor('#4a044e'),
        link_hex='#be185d',
        name_size=22, name_align=TA_LEFT,
        sec_style='banner',
        banner_bg=colors.HexColor('#be185d'),
        skills_mode='inline',
    ))


# ─────────────────────────────────────────────────────────────────────────────
# REGISTRY
# ─────────────────────────────────────────────────────────────────────────────

RESUME_TEMPLATES = {
    "Default Professional": render_template_default_professional,
    "Modern Minimal":       render_template_modern_minimal,
    "Elegant Sidebar":      render_template_elegant_sidebar,
    "Classic Clean":        render_template_classic_clean,
    "Executive":            render_template_executive,
    "Timeline":             render_template_timeline,
    "Corporate Blue":       render_template_corporate_blue,
    "Creative Green":       render_template_creative_green,
    "Warm Terracotta":      render_template_warm_terracotta,
    "Navy Prestige":        render_template_navy_prestige,
    "Slate Gray":           render_template_slate_gray,
    "Teal Impact":          render_template_teal_impact,
    "Burgundy Classic":     render_template_burgundy_classic,
    "Indigo Tech":          render_template_indigo_tech,
    "Forest Green":         render_template_forest_green,
    "Pure White":           render_template_pure_white,
    "Midnight Black":       render_template_midnight_black,
    "Soft Lavender":        render_template_soft_lavender,
    "Warm Sand":            render_template_warm_sand,
    "Ice Blue":             render_template_ice_blue,
    "Rose Gold":            render_template_rose_gold,
}

def render_resume(template_name, session_state, profile_img_bytes=None):
    """Dispatch to named template. Returns BytesIO PDF."""
    fn = RESUME_TEMPLATES.get(template_name, render_template_default_professional)
    return fn(session_state, profile_img_bytes)

# HTML-compat shims kept for any legacy imports
def _fmt_desc(text, **kw): return text or ""
def _cert_name_html(cert, link_style, span_style=""): return cert.get('name', '')
