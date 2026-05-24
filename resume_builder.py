# resume_builder.py — 21 ATS-compliant resume templates
#
# Design principles (per Jobscan, Zety, Harvard OCS, Indeed standards):
#   • Standard section headings ATS systems recognise
#   • Single-column layouts by default; two-column only where recruiters expect it
#   • Section order: Summary → Experience → Education → Skills → Projects → Certs
#   • Skills as plain comma-separated text — never pill/chip tables
#   • Tech stack on projects rendered inline as plain text
#   • No images/graphics in the parse flow
#   • Standard fonts only (Helvetica = Arial-equivalent in ReportLab)
#   • Bullets via ReportLab ListFlowable — clean, parseable
#   • All 21 templates share ONE section-render function — zero logic duplication

from io import BytesIO
from reportlab.lib.pagesizes import A4
from reportlab.lib import colors
from reportlab.lib.units import mm
from reportlab.lib.styles import ParagraphStyle
from reportlab.lib.enums import TA_LEFT, TA_CENTER, TA_RIGHT
from reportlab.platypus import (
    SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle,
    HRFlowable, ListFlowable, ListItem, Image,
)

PAGE_W, PAGE_H = A4
MARGIN    = 18 * mm          # 1-inch margins — ATS standard
SIDEBAR_W = 155
BODY_W    = PAGE_W - 2 * MARGIN         # usable single-col width
MAIN_W    = PAGE_W - 2 * MARGIN - SIDEBAR_W - 8   # two-col main width


# ─────────────────────────────────────────────────────────────────────────────
# DATA ACCESS
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

def _deg(e):
    d = e.get('degree', '')
    return ', '.join(d) if isinstance(d, list) else d

def _skills_list(raw):
    items = []
    for chunk in str(raw).replace('\n', ',').split(','):
        s = chunk.strip().strip('-•*·>–—★✦').strip()
        if s:
            items.append(s)
    return items

def _img(b, size=72):
    if not b:
        return None
    try:
        return Image(BytesIO(b), width=size, height=size)
    except Exception:
        return None

def _href(url, label, hex_col):
    if not url:
        return label
    if not url.startswith('http'):
        url = 'https://' + url
    return f'<link href="{url}"><font color="{hex_col}">{label}</font></link>'


# ─────────────────────────────────────────────────────────────────────────────
# FLOWABLE PRIMITIVES
# ─────────────────────────────────────────────────────────────────────────────

def _parse_lines(text):
    """Split text into (is_bullet, content) pairs."""
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

def _bullets(text, sn, sb, bc=colors.HexColor('#555555')):
    """Return flowables for bullet/plain mixed text. ATS-parseable ListFlowable."""
    if not text or not str(text).strip():
        return []
    lines = _parse_lines(text)
    if not lines:
        return []
    out, buf = [], []

    def flush():
        if buf:
            out.append(ListFlowable(
                [ListItem(Paragraph(t, sb), leftIndent=10, bulletColor=bc)
                 for t in buf],
                bulletType='bullet', start='•', leftIndent=6, bulletFontSize=6,
                spaceAfter=0))
            buf.clear()

    for is_b, content in lines:
        if is_b:
            buf.append(content)
        else:
            flush()
            out.append(Paragraph(content, sn))
    flush()
    return out

def _skills_line(raw, style):
    """Plain comma-separated skills paragraph — maximum ATS compatibility."""
    items = _skills_list(raw)
    if not items:
        return []
    return [Paragraph(', '.join(items), style), Spacer(1, 3)]

def _skills_2col(raw, style, width):
    """Two-column bullet list for skills."""
    items = _skills_list(raw)
    if not items:
        return []
    rows = []
    for i in range(0, len(items), 2):
        l = Paragraph(f'• {items[i]}', style)
        r = Paragraph(f'• {items[i+1]}', style) if i + 1 < len(items) else Paragraph('', style)
        rows.append([l, r])
    t = Table(rows, colWidths=[width/2]*2)
    t.setStyle(TableStyle([
        ('LEFTPADDING',  (0,0),(-1,-1), 0), ('RIGHTPADDING', (0,0),(-1,-1), 0),
        ('TOPPADDING',   (0,0),(-1,-1), 1), ('BOTTOMPADDING',(0,0),(-1,-1), 1),
    ]))
    return [t, Spacer(1, 3)]

def _row2(left, right, width, lw=0.72):
    """Left content + right-aligned date/label."""
    t = Table([[left, right]], colWidths=[width*lw, width*(1-lw)])
    t.setStyle(TableStyle([
        ('ALIGN',        (1,0),(1,0),'RIGHT'),
        ('VALIGN',       (0,0),(-1,-1),'TOP'),
        ('LEFTPADDING',  (0,0),(-1,-1),0), ('RIGHTPADDING', (0,0),(-1,-1),0),
        ('TOPPADDING',   (0,0),(-1,-1),0), ('BOTTOMPADDING',(0,0),(-1,-1),0),
    ]))
    return t

def _new_doc(buf, lm=MARGIN, rm=MARGIN, tm=MARGIN, bm=MARGIN):
    return SimpleDocTemplate(buf, pagesize=A4,
                             leftMargin=lm, rightMargin=rm,
                             topMargin=tm, bottomMargin=bm)


# ─────────────────────────────────────────────────────────────────────────────
# TWO-COLUMN ENGINE  (sidebar + main)
# ─────────────────────────────────────────────────────────────────────────────

def _two_col_doc(buf, sidebar_items, main_items, sb_bg, sb_bd):
    from reportlab.platypus import BaseDocTemplate, Frame, PageTemplate, FrameBreak
    from reportlab.pdfgen.canvas import Canvas as _C

    SB_X = MARGIN
    MN_X = MARGIN + SIDEBAR_W + 8
    PH   = PAGE_H - 2 * MARGIN

    def _canvas_factory(bg, bd):
        class _CV(_C):
            def _paint(self):
                self.saveState()
                self.setFillColor(bg); self.setStrokeColor(bd)
                self.rect(SB_X, MARGIN, SIDEBAR_W, PH, fill=1, stroke=0)
                self.restoreState()
            def showPage(self):
                self._paint(); super().showPage()
            def save(self):
                self._paint(); super().save()
        return _CV

    sb_frame = Frame(SB_X, MARGIN, SIDEBAR_W, PH,
                     leftPadding=10, rightPadding=8, topPadding=10, bottomPadding=8)
    mn_frame = Frame(MN_X, MARGIN, MAIN_W, PH,
                     leftPadding=8, rightPadding=4, topPadding=10, bottomPadding=8)
    doc = BaseDocTemplate(buf, pagesize=A4,
                          leftMargin=MARGIN, rightMargin=MARGIN,
                          topMargin=MARGIN, bottomMargin=MARGIN)
    doc.addPageTemplates([PageTemplate(id='two', frames=[sb_frame, mn_frame])])
    doc.build(list(sidebar_items) + [FrameBreak()] + list(main_items),
              canvasmaker=_canvas_factory(sb_bg, sb_bd))


# ─────────────────────────────────────────────────────────────────────────────
# CORE SECTION BUILDER  — called by every template
#
# ATS section order (industry standard):
#   Summary → Work Experience → Education → Skills → Projects → Certifications
# ─────────────────────────────────────────────────────────────────────────────

def _sections(ss, story, W, styles, link_hex, skills_render='line'):
    """
    Append all resume sections to `story`.

    styles keys: PN, PB, BD, MU, DT, SK, _sec
      PN  — normal body paragraph
      PB  — bullet item body
      BD  — bold label (company / institution name)
      MU  — muted / secondary text
      DT  — date / right-side label
      SK  — skills text
      _sec(title) — appends a section heading + rule to story
    """
    PN = styles['PN']; PB = styles['PB']; BD = styles['BD']
    MU = styles['MU']; DT = styles['DT']; SK = styles['SK']
    sec = styles['_sec']

    # ── Professional Summary ─────────────────────────────────────────────────
    sm = _get(ss, 'summary')
    if sm:
        sec("Professional Summary")
        for f in _bullets(sm, PN, PB): story.append(f)
        story.append(Spacer(1, 4))

    # ── Work Experience ──────────────────────────────────────────────────────
    exps = [e for e in _entries(ss, 'experience_entries')
            if e.get('company') or e.get('title')]
    if exps:
        sec("Work Experience")
        for e in exps:
            co  = e.get('company', '')
            ttl = e.get('title', '')
            dur = e.get('duration', '')
            # Company bold, em-dash, title — standard recruiter layout
            label = f"<b>{co}</b>" + (f" \u2014 {ttl}" if ttl else '')
            story.append(_row2(Paragraph(label, BD), Paragraph(dur, DT), W))
            for f in _bullets(e.get('description', ''), PN, PB): story.append(f)
            story.append(Spacer(1, 6))

    # ── Education ────────────────────────────────────────────────────────────
    edus = [e for e in _entries(ss, 'education_entries')
            if e.get('institution') or e.get('degree')]
    if edus:
        sec("Education")
        for e in edus:
            inst = e.get('institution', '')
            deg  = _deg(e)
            yr   = e.get('year', '')
            label = f"<b>{inst}</b>" + (f" \u2014 {deg}" if deg else '')
            story.append(_row2(Paragraph(label, BD), Paragraph(yr, DT), W))
            if e.get('details'):
                story.append(Paragraph(e['details'], MU))
            story.append(Spacer(1, 4))

    # ── Skills ───────────────────────────────────────────────────────────────
    # Each category gets its own labelled line — maximises keyword density for ATS
    for field, label in [('skills',     'Technical Skills'),
                         ('Softskills', 'Soft Skills'),
                         ('languages',  'Languages'),
                         ('interests',  'Interests')]:
        v = _get(ss, field)
        if v:
            sec(label)
            if skills_render == '2col':
                story.extend(_skills_2col(v, SK, W))
            else:
                story.extend(_skills_line(v, SK))

    # ── Projects ─────────────────────────────────────────────────────────────
    projs      = [p for p in _entries(ss, 'project_entries') if p.get('title')]
    proj_links = _entries(ss, 'project_links')
    if projs:
        sec("Projects")
        for i, p in enumerate(projs):
            lnk   = proj_links[i] if i < len(proj_links) else ''
            title = _href(lnk, p.get('title',''), link_hex) if lnk else p.get('title','')
            tech  = p.get('tech','').strip()
            # Inline tech: "Project Name  |  Python, Django, PostgreSQL"
            head  = f"<b>{title}</b>" + (f"  |  {tech}" if tech else '')
            story.append(Paragraph(head, BD))
            for f in _bullets(p.get('description',''), PN, PB): story.append(f)
            story.append(Spacer(1, 6))

    # ── Certifications ───────────────────────────────────────────────────────
    certs = [c for c in _entries(ss, 'certificate_links') if c.get('name')]
    if certs:
        sec("Certifications")
        for c in certs:
            nm = (_href(c.get('link',''), c.get('name',''), link_hex)
                  if c.get('link') else c.get('name',''))
            story.append(_row2(Paragraph(nm, BD),
                               Paragraph(c.get('duration',''), DT), W))
            if c.get('description'):
                story.append(Paragraph(c['description'], MU))
            story.append(Spacer(1, 4))


# ─────────────────────────────────────────────────────────────────────────────
# SINGLE-COLUMN RENDERER
# ─────────────────────────────────────────────────────────────────────────────

def _single(ss, img, theme):
    """
    theme keys
    ----------
    accent      HexColor   — accent / link color
    heading     HexColor   — section heading + name color
    body        HexColor   — body text color        (default #1a1a1a)
    muted       HexColor   — secondary text         (default #555555)
    link_hex    str        — hex string for hyperlinks
    name_size   int        — name font pt            (default 22)
    name_align  TA_*       — name alignment          (default TA_LEFT)
    name_upper  bool       — force uppercase name    (default False)
    sec_style   str        — 'line'|'caps'|'banner'|'box'|'thick'
    skills      str        — 'line'|'2col'
    """
    acc       = theme['accent']
    head_col  = theme.get('heading', acc)
    body_col  = theme.get('body',    colors.HexColor('#1a1a1a'))
    muted_col = theme.get('muted',   colors.HexColor('#555555'))
    link_hex  = theme.get('link_hex','#1a1a1a')
    name_sz   = theme.get('name_size', 22)
    name_al   = theme.get('name_align', TA_LEFT)
    sec_sty   = theme.get('sec_style', 'line')
    sk_mode   = theme.get('skills', 'line')
    W         = BODY_W

    buf = BytesIO(); ss_ = ss; doc = _new_doc(buf)

    # ── Type styles ───────────────────────────────────────────────────────────
    NM = ParagraphStyle('NM', fontName='Helvetica-Bold', fontSize=name_sz,
                        textColor=head_col, alignment=name_al, leading=name_sz+4)
    JT = ParagraphStyle('JT', fontName='Helvetica', fontSize=12,
                        textColor=acc, alignment=name_al, leading=16, spaceAfter=2)
    CO = ParagraphStyle('CO', fontName='Helvetica', fontSize=9,
                        textColor=muted_col, alignment=name_al, leading=13)
    SH = ParagraphStyle('SH', fontName='Helvetica-Bold', fontSize=11,
                        textColor=head_col, leading=14, spaceBefore=10, spaceAfter=2)
    PN = ParagraphStyle('PN', fontName='Helvetica', fontSize=10,
                        textColor=body_col, leading=14, spaceAfter=1)
    PB = ParagraphStyle('PB', fontName='Helvetica', fontSize=10,
                        textColor=body_col, leading=14)
    BD = ParagraphStyle('BD', fontName='Helvetica-Bold', fontSize=10,
                        textColor=body_col, leading=14)
    MU = ParagraphStyle('MU', fontName='Helvetica', fontSize=9,
                        textColor=muted_col, leading=13)
    DT = ParagraphStyle('DT', fontName='Helvetica', fontSize=9,
                        textColor=muted_col, leading=13)
    SK = ParagraphStyle('SK', fontName='Helvetica', fontSize=10,
                        textColor=body_col, leading=14)

    story = []

    # ── Header ────────────────────────────────────────────────────────────────
    name = _get(ss_, 'name') or 'Your Name'
    if theme.get('name_upper'): name = name.upper()
    jt   = _get(ss_, 'job_title')
    cp   = [_get(ss_, k) for k in ['email','phone','location','linkedin','github','portfolio']
            if _get(ss_, k)]
    iv   = _img(img)

    if sec_sty == 'banner':
        # Colored header band
        hdr = [Paragraph(name, NM)]
        if jt:  hdr.append(Paragraph(jt, JT))
        if cp:  hdr.append(Paragraph('  |  '.join(cp), CO))
        if iv:
            inner = Table([[hdr, iv]], colWidths=[W-78, 78])
            inner.setStyle(TableStyle([('VALIGN',(0,0),(-1,-1),'MIDDLE'),
                ('LEFTPADDING',(0,0),(-1,-1),0),('RIGHTPADDING',(0,0),(-1,-1),0)]))
            hdr = [inner]
        band = Table([[hdr]], colWidths=[W])
        band.setStyle(TableStyle([
            ('BACKGROUND',   (0,0),(-1,-1), theme.get('banner_bg', head_col)),
            ('TOPPADDING',   (0,0),(-1,-1), 14), ('BOTTOMPADDING',(0,0),(-1,-1), 14),
            ('LEFTPADDING',  (0,0),(-1,-1), 14), ('RIGHTPADDING', (0,0),(-1,-1), 14),
        ]))
        story.append(band); story.append(Spacer(1,8))
    else:
        # Standard stacked header
        hdr_block = [Paragraph(name, NM)]
        if jt: hdr_block.append(Paragraph(jt, JT))
        if cp: hdr_block.append(Paragraph('  |  '.join(cp), CO))
        if iv:
            row = Table([[hdr_block, iv]], colWidths=[W-78, 78])
            row.setStyle(TableStyle([('VALIGN',(0,0),(-1,-1),'TOP'),
                ('LEFTPADDING',(0,0),(-1,-1),0),('RIGHTPADDING',(0,0),(-1,-1),0)]))
            story.append(row)
        else:
            for fl in hdr_block: story.append(fl)

        # Separator below header
        if sec_sty == 'thick':
            story.append(HRFlowable(width=W, thickness=3, color=acc, spaceBefore=6, spaceAfter=8))
        else:
            story.append(HRFlowable(width=W, thickness=1.5, color=acc, spaceBefore=6, spaceAfter=8))

    # ── Section heading factory ───────────────────────────────────────────────
    if sec_sty in ('line', 'thick', 'banner'):
        def _sec(title):
            story.append(Paragraph(title, SH))
            story.append(HRFlowable(width=W, thickness=0.5, color=acc, spaceAfter=4))

    elif sec_sty == 'caps':
        SH_C = ParagraphStyle('SHC', fontName='Helvetica-Bold', fontSize=9,
                               textColor=head_col, leading=12,
                               spaceBefore=12, spaceAfter=2, wordSpace=1.5)
        def _sec(title):
            story.append(Paragraph(title.upper(), SH_C))
            story.append(HRFlowable(width=W, thickness=0.8, color=acc, spaceAfter=4))

    elif sec_sty == 'box':
        SH_B = ParagraphStyle('SHB', fontName='Helvetica-Bold', fontSize=10,
                               textColor=colors.white, leading=13)
        def _sec(title):
            bx = Table([[Paragraph(f'  {title}', SH_B)]], colWidths=[W])
            bx.setStyle(TableStyle([
                ('BACKGROUND',(0,0),(-1,-1), head_col),
                ('TOPPADDING',(0,0),(-1,-1),4), ('BOTTOMPADDING',(0,0),(-1,-1),4),
                ('LEFTPADDING',(0,0),(-1,-1),6), ('RIGHTPADDING',(0,0),(-1,-1),6),
            ]))
            story.append(bx); story.append(Spacer(1,4))

    elif sec_sty == 'leftbar':
        def _sec(title):
            bar = Table([[Paragraph('',SH), Paragraph(title, SH)]],
                        colWidths=[4, W-4])
            bar.setStyle(TableStyle([
                ('BACKGROUND',(0,0),(0,-1), acc),
                ('LEFTPADDING',(0,0),(-1,-1),0),('RIGHTPADDING',(0,0),(-1,-1),0),
                ('TOPPADDING',(0,0),(-1,-1),0),('BOTTOMPADDING',(0,0),(-1,-1),0),
                ('LEFTPADDING',(1,0),(1,-1),8),
                ('VALIGN',(0,0),(-1,-1),'MIDDLE'),
            ]))
            story.append(bar); story.append(Spacer(1,4))

    else:
        def _sec(title):
            story.append(Paragraph(title, SH))
            story.append(HRFlowable(width=W, thickness=0.5, color=acc, spaceAfter=4))

    # ── Build all sections ────────────────────────────────────────────────────
    _sections(ss_, story, W,
              dict(PN=PN, PB=PB, BD=BD, MU=MU, DT=DT, SK=SK, _sec=_sec),
              link_hex, sk_mode)
    doc.build(story); buf.seek(0); return buf


# ─────────────────────────────────────────────────────────────────────────────
# TWO-COLUMN RENDERER
# ─────────────────────────────────────────────────────────────────────────────

def _two_col(ss, img, theme):
    """
    Two-column layout: colored sidebar (contact + skills) + main (sections).
    ATS note: two-col PDFs are parseable by modern ATS (Workday, Greenhouse,
    Lever) when text layer is clean. Sidebar contact info still scanned.
    """
    acc      = theme['accent']
    sb_bg    = theme.get('sb_bg',    acc)
    sb_bd    = theme.get('sb_bd',    acc)
    sb_txt   = theme.get('sb_txt',   colors.white)
    sb_sub   = theme.get('sb_sub',   colors.HexColor('#dddddd'))
    body_col = theme.get('body',     colors.HexColor('#1a1a1a'))
    muted    = theme.get('muted',    colors.HexColor('#555555'))
    m_head   = theme.get('main_heading', acc)
    link_hex = theme.get('link_hex', '#1a1a1a')
    sk_mode  = theme.get('skills',   'line')
    SW = SIDEBAR_W - 18

    # Sidebar styles
    sbN = ParagraphStyle('sbN', fontName='Helvetica-Bold', fontSize=13,
                         textColor=sb_txt, alignment=TA_CENTER, leading=17, spaceAfter=2)
    sbT = ParagraphStyle('sbT', fontName='Helvetica', fontSize=10,
                         textColor=sb_sub, alignment=TA_CENTER, leading=13, spaceAfter=5)
    sbS = ParagraphStyle('sbS', fontName='Helvetica-Bold', fontSize=8,
                         textColor=sb_sub, leading=12, spaceBefore=10, spaceAfter=2)
    sbI = ParagraphStyle('sbI', fontName='Helvetica', fontSize=9,
                         textColor=sb_txt, leading=13, spaceAfter=3)
    sbK = ParagraphStyle('sbK', fontName='Helvetica', fontSize=9,
                         textColor=sb_txt, leading=13, spaceAfter=2)

    # Main styles
    mH  = ParagraphStyle('mH', fontName='Helvetica-Bold', fontSize=11,
                         textColor=m_head, leading=14, spaceBefore=10, spaceAfter=2)
    mN  = ParagraphStyle('mN', fontName='Helvetica', fontSize=10,
                         textColor=body_col, leading=14, spaceAfter=1)
    mB  = ParagraphStyle('mB', fontName='Helvetica', fontSize=10,
                         textColor=body_col, leading=14)
    mBD = ParagraphStyle('mBD', fontName='Helvetica-Bold', fontSize=10,
                         textColor=body_col, leading=14)
    mMU = ParagraphStyle('mMU', fontName='Helvetica', fontSize=9,
                         textColor=muted, leading=13)
    mDT = ParagraphStyle('mDT', fontName='Helvetica', fontSize=9,
                         textColor=muted, leading=13)
    mSK = ParagraphStyle('mSK', fontName='Helvetica', fontSize=10,
                         textColor=body_col, leading=14)

    def sb_sec(title, sidebar):
        sidebar.append(HRFlowable(width=SW, thickness=0.4, color=sb_bd, spaceAfter=2))
        sidebar.append(Paragraph(title.upper(), sbS))

    # Build sidebar
    sidebar = []
    iv = _img(img, 76)
    if iv: sidebar += [iv, Spacer(1,6)]
    sidebar.append(Paragraph(_get(ss,'name') or 'Your Name', sbN))
    if _get(ss,'job_title'): sidebar.append(Paragraph(_get(ss,'job_title'), sbT))

    for k, lbl in [('email','Email'),('phone','Phone'),('location','Location'),
                   ('linkedin','LinkedIn'),('github','GitHub'),('portfolio','Portfolio')]:
        v = _get(ss, k)
        if v: sb_sec(lbl, sidebar); sidebar.append(Paragraph(v, sbI))

    for field, lbl in [('skills','Technical Skills'),('Softskills','Soft Skills'),
                       ('languages','Languages'),('interests','Interests')]:
        v = _get(ss, field)
        if v:
            sb_sec(lbl, sidebar)
            sidebar.extend(_skills_line(v, sbK))

    # Build main
    main = []
    MW   = MAIN_W

    def m_sec(title):
        main.append(Paragraph(title, mH))
        main.append(HRFlowable(width=MW, thickness=0.5, color=sb_bd, spaceAfter=4))

    _sections(ss, main, MW,
              dict(PN=mN, PB=mB, BD=mBD, MU=mMU, DT=mDT, SK=mSK, _sec=m_sec),
              link_hex, sk_mode)

    buf = BytesIO()
    _two_col_doc(buf, sidebar, main, sb_bg, sb_bd)
    buf.seek(0); return buf


# ═════════════════════════════════════════════════════════════════════════════
# 21 TEMPLATES
#
# Naming convention reflects style/industry — no color in the name where
# possible, but kept for backwards-compatibility with the existing registry.
#
# Layout families:
#   Single-column (15): classic recruiter-friendly; 100% ATS safe
#   Two-column    ( 6): sidebar layout; ATS-safe with modern parsers
# ═════════════════════════════════════════════════════════════════════════════

# ── 1. Default Professional ── clean, navy, single-col, underline sections ──
def render_template_default_professional(ss, img=None):
    return _single(ss, img, dict(
        accent=colors.HexColor('#2563eb'),
        heading=colors.HexColor('#1e3a5f'),
        body=colors.HexColor('#1a1a1a'), muted=colors.HexColor('#555555'),
        link_hex='#2563eb',
        name_size=24, name_align=TA_LEFT,
        sec_style='line', skills='line',
    ))

# ── 2. Modern Minimal ── teal caps sections, ample whitespace ──
def render_template_modern_minimal(ss, img=None):
    return _single(ss, img, dict(
        accent=colors.HexColor('#0d9488'),
        heading=colors.HexColor('#0d9488'),
        body=colors.HexColor('#1f2937'), muted=colors.HexColor('#6b7280'),
        link_hex='#0d9488',
        name_size=26, name_align=TA_LEFT,
        sec_style='caps', skills='line',
    ))

# ── 3. Elegant Sidebar ── purple two-col, skills in sidebar ──
def render_template_elegant_sidebar(ss, img=None):
    return _two_col(ss, img, dict(
        accent=colors.HexColor('#7c3aed'),
        sb_bg=colors.HexColor('#7c3aed'), sb_bd=colors.HexColor('#a78bfa'),
        sb_txt=colors.white, sb_sub=colors.HexColor('#ede9fe'),
        body=colors.HexColor('#1f2937'), muted=colors.HexColor('#6b7280'),
        main_heading=colors.HexColor('#7c3aed'), link_hex='#7c3aed',
        skills='line',
    ))

# ── 4. Classic Clean ── monochrome, caps-hr, two-col skills list ──
def render_template_classic_clean(ss, img=None):
    return _single(ss, img, dict(
        accent=colors.HexColor('#374151'),
        heading=colors.HexColor('#111827'),
        body=colors.HexColor('#374151'), muted=colors.HexColor('#6b7280'),
        link_hex='#374151',
        name_size=22, name_align=TA_CENTER,
        sec_style='caps', skills='2col',
    ))

# ── 5. Executive ── navy/gold, thick rule, two-col skills ──
def render_template_executive(ss, img=None):
    return _single(ss, img, dict(
        accent=colors.HexColor('#b45309'),
        heading=colors.HexColor('#1e3a5f'),
        body=colors.HexColor('#1e293b'), muted=colors.HexColor('#6b7280'),
        link_hex='#1e3a5f',
        name_size=24, name_align=TA_LEFT,
        sec_style='thick', skills='2col',
    ))

# ── 6. Timeline ── amber, caps, left-aligned ──
def render_template_timeline(ss, img=None):
    return _single(ss, img, dict(
        accent=colors.HexColor('#d97706'),
        heading=colors.HexColor('#92400e'),
        body=colors.HexColor('#374151'), muted=colors.HexColor('#9ca3af'),
        link_hex='#92400e',
        name_size=22, name_align=TA_LEFT,
        sec_style='caps', skills='line',
    ))

# ── 7. Corporate Blue ── navy two-col ──
def render_template_corporate_blue(ss, img=None):
    return _two_col(ss, img, dict(
        accent=colors.HexColor('#1d4ed8'),
        sb_bg=colors.HexColor('#1d4ed8'), sb_bd=colors.HexColor('#93c5fd'),
        sb_txt=colors.white, sb_sub=colors.HexColor('#dbeafe'),
        body=colors.HexColor('#1e293b'), muted=colors.HexColor('#64748b'),
        main_heading=colors.HexColor('#1d4ed8'), link_hex='#1d4ed8',
        skills='line',
    ))

# ── 8. Creative Green ── forest green two-col ──
def render_template_creative_green(ss, img=None):
    return _two_col(ss, img, dict(
        accent=colors.HexColor('#166534'),
        sb_bg=colors.HexColor('#166534'), sb_bd=colors.HexColor('#86efac'),
        sb_txt=colors.white, sb_sub=colors.HexColor('#dcfce7'),
        body=colors.HexColor('#1a2e1a'), muted=colors.HexColor('#6b7280'),
        main_heading=colors.HexColor('#166534'), link_hex='#166534',
        skills='line',
    ))

# ── 9. Warm Terracotta ── terracotta two-col ──
def render_template_warm_terracotta(ss, img=None):
    return _two_col(ss, img, dict(
        accent=colors.HexColor('#c2410c'),
        sb_bg=colors.HexColor('#c2410c'), sb_bd=colors.HexColor('#fdba74'),
        sb_txt=colors.white, sb_sub=colors.HexColor('#ffedd5'),
        body=colors.HexColor('#1c1917'), muted=colors.HexColor('#78716c'),
        main_heading=colors.HexColor('#c2410c'), link_hex='#c2410c',
        skills='line',
    ))

# ── 10. Navy Prestige ── navy/gold, leftbar sections ──
def render_template_navy_prestige(ss, img=None):
    return _single(ss, img, dict(
        accent=colors.HexColor('#1e3a5f'),
        heading=colors.HexColor('#1e3a5f'),
        body=colors.HexColor('#1e293b'), muted=colors.HexColor('#6b7280'),
        link_hex='#1e3a5f',
        name_size=24, name_align=TA_LEFT,
        sec_style='leftbar', skills='2col',
    ))

# ── 11. Slate Gray ── slate, banner header, underline sections ──
def render_template_slate_gray(ss, img=None):
    return _single(ss, img, dict(
        accent=colors.HexColor('#475569'),
        heading=colors.HexColor('#334155'),
        body=colors.HexColor('#1e293b'), muted=colors.HexColor('#94a3b8'),
        link_hex='#334155',
        name_size=22, name_align=TA_LEFT,
        sec_style='banner',
        banner_bg=colors.HexColor('#334155'),
        skills='line',
    ))

# ── 12. Teal Impact ── teal two-col ──
def render_template_teal_impact(ss, img=None):
    return _two_col(ss, img, dict(
        accent=colors.HexColor('#0f766e'),
        sb_bg=colors.HexColor('#0f766e'), sb_bd=colors.HexColor('#5eead4'),
        sb_txt=colors.white, sb_sub=colors.HexColor('#ccfbf1'),
        body=colors.HexColor('#1a2e2e'), muted=colors.HexColor('#6b7280'),
        main_heading=colors.HexColor('#0f766e'), link_hex='#0f766e',
        skills='line',
    ))

# ── 13. Burgundy Classic ── burgundy, centered name, two-col skills ──
def render_template_burgundy_classic(ss, img=None):
    return _single(ss, img, dict(
        accent=colors.HexColor('#881337'),
        heading=colors.HexColor('#881337'),
        body=colors.HexColor('#1a0a0a'), muted=colors.HexColor('#78716c'),
        link_hex='#881337',
        name_size=22, name_align=TA_CENTER,
        sec_style='line', skills='2col',
        name_upper=True,
    ))

# ── 14. Indigo Tech ── indigo two-col ──
def render_template_indigo_tech(ss, img=None):
    return _two_col(ss, img, dict(
        accent=colors.HexColor('#4338ca'),
        sb_bg=colors.HexColor('#4338ca'), sb_bd=colors.HexColor('#a5b4fc'),
        sb_txt=colors.white, sb_sub=colors.HexColor('#e0e7ff'),
        body=colors.HexColor('#1e1b4b'), muted=colors.HexColor('#6b7280'),
        main_heading=colors.HexColor('#4338ca'), link_hex='#4338ca',
        skills='line',
    ))

# ── 15. Forest Green ── dark green, box sections ──
def render_template_forest_green(ss, img=None):
    return _single(ss, img, dict(
        accent=colors.HexColor('#15803d'),
        heading=colors.HexColor('#14532d'),
        body=colors.HexColor('#1a2e1a'), muted=colors.HexColor('#6b7280'),
        link_hex='#14532d',
        name_size=22, name_align=TA_LEFT,
        sec_style='box', skills='line',
    ))

# ── 16. Pure White ── ultra-minimal, large name, hairline rules ──
def render_template_pure_white(ss, img=None):
    return _single(ss, img, dict(
        accent=colors.HexColor('#9ca3af'),
        heading=colors.HexColor('#111111'),
        body=colors.HexColor('#374151'), muted=colors.HexColor('#9ca3af'),
        link_hex='#374151',
        name_size=28, name_align=TA_LEFT,
        sec_style='caps', skills='line',
    ))

# ── 17. Midnight Black ── dark theme, gold accents, box sections ──
def render_template_midnight_black(ss, img=None):
    return _single(ss, img, dict(
        accent=colors.HexColor('#d97706'),
        heading=colors.HexColor('#f9fafb'),
        body=colors.HexColor('#e5e7eb'), muted=colors.HexColor('#9ca3af'),
        link_hex='#d97706',
        name_size=24, name_align=TA_LEFT,
        sec_style='box', skills='line',
    ))

# ── 18. Soft Lavender ── lavender, banner header ──
def render_template_soft_lavender(ss, img=None):
    return _single(ss, img, dict(
        accent=colors.HexColor('#6366f1'),
        heading=colors.HexColor('#4338ca'),
        body=colors.HexColor('#374151'), muted=colors.HexColor('#9ca3af'),
        link_hex='#6366f1',
        name_size=22, name_align=TA_LEFT,
        sec_style='banner',
        banner_bg=colors.HexColor('#4338ca'),
        skills='line',
    ))

# ── 19. Warm Sand ── warm amber, leftbar sections ──
def render_template_warm_sand(ss, img=None):
    return _single(ss, img, dict(
        accent=colors.HexColor('#b45309'),
        heading=colors.HexColor('#92400e'),
        body=colors.HexColor('#44403c'), muted=colors.HexColor('#a8a29e'),
        link_hex='#92400e',
        name_size=22, name_align=TA_LEFT,
        sec_style='leftbar', skills='line',
    ))

# ── 20. Ice Blue ── cool blue, box sections ──
def render_template_ice_blue(ss, img=None):
    return _single(ss, img, dict(
        accent=colors.HexColor('#0369a1'),
        heading=colors.HexColor('#0c4a6e'),
        body=colors.HexColor('#1e3a5f'), muted=colors.HexColor('#94a3b8'),
        link_hex='#0369a1',
        name_size=22, name_align=TA_LEFT,
        sec_style='box', skills='line',
    ))

# ── 21. Rose Gold ── pink, banner header ──
def render_template_rose_gold(ss, img=None):
    return _single(ss, img, dict(
        accent=colors.HexColor('#db2777'),
        heading=colors.HexColor('#be185d'),
        body=colors.HexColor('#4a044e'), muted=colors.HexColor('#9ca3af'),
        link_hex='#be185d',
        name_size=22, name_align=TA_LEFT,
        sec_style='banner',
        banner_bg=colors.HexColor('#be185d'),
        skills='line',
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

# Legacy shims
def _fmt_desc(text, **kw): return text or ""
def _cert_name_html(cert, link_style, span_style=""): return cert.get('name','')
