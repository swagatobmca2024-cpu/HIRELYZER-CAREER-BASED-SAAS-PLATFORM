# resume_builder.py  — 21 genuinely distinct ReportLab Platypus resume templates
# Each template returns BytesIO PDF with a unique layout identity.

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
MAIN_W    = 380

# ─────────────────────────────────────────────────────────────────────────────
# SHARED HELPERS
# ─────────────────────────────────────────────────────────────────────────────

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

def _bullets(text, sn, sb, bc=None):
    if not text or not text.strip():
        return []
    items = _parse_bullets(text)
    if not items:
        return []
    out, buf = [], []
    def flush():
        if buf:
            out.append(ListFlowable(
                [ListItem(Paragraph(t, sb), leftIndent=12, bulletColor=bc or colors.black) for t in buf],
                bulletType='bullet', start='•', leftIndent=8, bulletFontSize=7))
            buf.clear()
    for is_b, c in items:
        if is_b: buf.append(c)
        else: flush(); out.append(Paragraph(c, sn))
    flush()
    return out

def _img(b, size=80):
    if not b:
        return None
    try:
        return Image(BytesIO(b), width=size, height=size)
    except Exception:
        return None

def _link(url, label, css):
    if not url:
        return label
    if not url.startswith('http'):
        url = 'https://' + url
    return f'<link href="{url}"><font color="{css}">{label}</font></link>'

def _deg(e):
    d = e.get('degree', '')
    return ', '.join(d) if isinstance(d, list) else d

def _skills_list(raw):
    return [i.strip() for i in str(raw).split(',') if i.strip()]

def _pill_row(items, bg, fg, bd, w, n=5):
    if not items:
        return []
    ps = ParagraphStyle('pl', fontName='Helvetica', fontSize=9,
                         textColor=fg, alignment=TA_CENTER, leading=12)
    rows, row = [], []
    for item in items:
        row.append(Paragraph(item, ps))
        if len(row) == n:
            rows.append(row); row = []
    if row:
        while len(row) < n:
            row.append(Paragraph('', ps))
        rows.append(row)
    cw = w / n
    t = Table(rows, colWidths=[cw]*n)
    ts = TableStyle([('BACKGROUND',(0,0),(-1,-1),bg),
                     ('TOPPADDING',(0,0),(-1,-1),3),('BOTTOMPADDING',(0,0),(-1,-1),3),
                     ('LEFTPADDING',(0,0),(-1,-1),5),('RIGHTPADDING',(0,0),(-1,-1),5)])
    for ri in range(len(rows)):
        for ci in range(n):
            ts.add('BOX',(ci,ri),(ci,ri),0.5,bd)
    t.setStyle(ts)
    return [t, Spacer(1,4)]

def _pills(raw, bg, fg, bd, w, n=5):
    return _pill_row(_skills_list(raw), bg, fg, bd, w, n)

def _row2(lp, rp, w, lw=0.70):
    t = Table([[lp, rp]], colWidths=[w*lw, w*(1-lw)])
    t.setStyle(TableStyle([('ALIGN',(1,0),(1,0),'RIGHT'),('VALIGN',(0,0),(-1,-1),'TOP'),
                            ('LEFTPADDING',(0,0),(-1,-1),0),('RIGHTPADDING',(0,0),(-1,-1),0),
                            ('TOPPADDING',(0,0),(-1,-1),0),('BOTTOMPADDING',(0,0),(-1,-1),0)]))
    return t

def _new_doc(buf):
    return SimpleDocTemplate(buf, pagesize=A4,
                             leftMargin=MARGIN, rightMargin=MARGIN,
                             topMargin=MARGIN, bottomMargin=MARGIN)

def _two_col(buf, sidebar_items, main_items, sb_bg, sb_bd):
    """
    Frame-based two-column layout — supports multi-page content without crashing.
    Sidebar background is painted as a filled rectangle on every page via a
    custom Canvas subclass, so it appears behind the sidebar frame content.
    """
    from reportlab.platypus import BaseDocTemplate, Frame, PageTemplate, FrameBreak
    from reportlab.pdfgen.canvas import Canvas as _BaseCanvas

    SB_X = MARGIN
    MN_X = MARGIN + SIDEBAR_W + 6
    PH   = PAGE_H - 2 * MARGIN  # usable page height

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


# ═════════════════════════════════════════════════════════════════════════════
# TEMPLATE 1 — Default Professional
# Layout: single-col, centered header, blue HR dividers, pill chips for skills
# ═════════════════════════════════════════════════════════════════════════════
def render_template_default_professional(session_state, profile_img_bytes=None):
    C = dict(
        H=colors.HexColor('#1e3a5f'), A=colors.HexColor('#3b82f6'),
        T=colors.HexColor('#1f2937'), M=colors.HexColor('#6b7280'),
        PB=colors.HexColor('#dbeafe'), PD=colors.HexColor('#93c5fd'),
    )
    buf = BytesIO(); ss = session_state; W = PAGE_W - 2*MARGIN
    doc = _new_doc(buf)
    NM = ParagraphStyle('nm', fontName='Helvetica-Bold',   fontSize=22, textColor=C['H'], alignment=TA_CENTER, leading=28)
    JT = ParagraphStyle('jt', fontName='Helvetica-Oblique',fontSize=13, textColor=C['A'], alignment=TA_CENTER, leading=17, spaceAfter=2)
    CO = ParagraphStyle('co', fontName='Helvetica',        fontSize=9,  textColor=C['M'], alignment=TA_CENTER, leading=13)
    SH = ParagraphStyle('sh', fontName='Helvetica-Bold',   fontSize=11, textColor=C['H'], leading=16, spaceBefore=10, spaceAfter=3)
    PN = ParagraphStyle('pn', fontName='Helvetica',        fontSize=10, textColor=C['T'], leading=14, spaceAfter=2)
    PB = ParagraphStyle('pb', fontName='Helvetica',        fontSize=10, textColor=C['T'], leading=14)
    BD = ParagraphStyle('bd', fontName='Helvetica-Bold',   fontSize=10, textColor=C['H'], leading=14)
    MU = ParagraphStyle('mu', fontName='Helvetica',        fontSize=9,  textColor=C['M'], leading=13)
    AC = ParagraphStyle('ac', fontName='Helvetica-Bold',   fontSize=9,  textColor=C['A'], leading=13)

    story = []
    iv = _img(profile_img_bytes)
    if iv: story += [iv, Spacer(1,4)]
    story.append(Paragraph(_get(ss,'name') or 'Your Name', NM))
    if _get(ss,'job_title'): story.append(Paragraph(_get(ss,'job_title'), JT))
    cp = [_get(ss,k) for k in ['email','phone','location','linkedin','github','portfolio'] if _get(ss,k)]
    if cp: story.append(Paragraph(' | '.join(cp), CO))
    story.append(HRFlowable(width=W, thickness=2, color=C['A'], spaceBefore=6, spaceAfter=8))

    def sec(title):
        story.append(Paragraph(title, SH))
        story.append(HRFlowable(width=W, thickness=0.5, color=C['A'], spaceAfter=4))

    sm = _get(ss,'summary')
    if sm:
        sec("Professional Summary")
        for f in _bullets(sm, PN, PB, C['A']): story.append(f)

    exps = [e for e in _entries(ss,'experience_entries') if e.get('company') or e.get('title')]
    if exps:
        sec("Work Experience")
        for e in exps:
            story.append(_row2(Paragraph(f"{e.get('company','')} — {e.get('title','')}", BD), Paragraph(e.get('duration',''), AC), W))
            for f in _bullets(e.get('description',''), PN, PB, C['A']): story.append(f)
            story.append(Spacer(1,6))

    edus = [e for e in _entries(ss,'education_entries') if e.get('institution') or e.get('degree')]
    if edus:
        sec("Education")
        for e in edus:
            story.append(_row2(Paragraph(f"{e.get('institution','')} — {_deg(e)}", BD), Paragraph(e.get('year',''), AC), W))
            if e.get('details'): story.append(Paragraph(e['details'], MU))
            story.append(Spacer(1,4))

    for field, label in [('skills','Technical Skills'),('Softskills','Soft Skills'),('languages','Languages'),('interests','Interests')]:
        v = _get(ss, field)
        if v:
            sec(label)
            story.extend(_pills(v, C['PB'], C['H'], C['PD'], W))

    projs = [p for p in _entries(ss,'project_entries') if p.get('title')]
    proj_links = _entries(ss,'project_links')
    if projs:
        sec("Projects")
        for i, p in enumerate(projs):
            lnk = proj_links[i] if i < len(proj_links) else ''
            t = _link(lnk, p.get('title',''), '#3b82f6') if lnk else p.get('title','')
            story.append(Paragraph(t, BD))
            if p.get('tech'): story.extend(_pills(p['tech'], C['PB'], C['A'], C['PD'], W))
            for f in _bullets(p.get('description',''), PN, PB, C['A']): story.append(f)
            story.append(Spacer(1,6))

    certs = [c for c in _entries(ss,'certificate_links') if c.get('name')]
    if certs:
        sec("Certifications")
        for c in certs:
            nm = _link(c.get('link',''), c.get('name',''), '#3b82f6') if c.get('link') else c.get('name','')
            story.append(_row2(Paragraph(nm, BD), Paragraph(c.get('duration',''), AC), W))
            if c.get('description'): story.append(Paragraph(c['description'], MU))
            story.append(Spacer(1,4))

    doc.build(story); buf.seek(0); return buf


# ═════════════════════════════════════════════════════════════════════════════
# TEMPLATE 2 — Modern Minimal
# Layout: left-aligned, thick teal top-bar, UPPERCASE spaced section labels,
#         NO divider lines — pure whitespace rhythm, skills as plain text tags
# ═════════════════════════════════════════════════════════════════════════════
def render_template_modern_minimal(session_state, profile_img_bytes=None):
    C = dict(
        A=colors.HexColor('#0d9488'), T=colors.HexColor('#1f2937'),
        M=colors.HexColor('#6b7280'), LT=colors.HexColor('#f0fdfa'),
        BD=colors.HexColor('#ccfbf1'),
    )
    buf = BytesIO(); ss = session_state; W = PAGE_W - 2*MARGIN
    doc = _new_doc(buf)
    NM = ParagraphStyle('nm', fontName='Helvetica-Bold',   fontSize=26, textColor=C['T'],  leading=32)
    JT = ParagraphStyle('jt', fontName='Helvetica',        fontSize=13, textColor=C['A'],  leading=18, spaceAfter=3)
    CO = ParagraphStyle('co', fontName='Helvetica',        fontSize=9,  textColor=C['M'],  leading=13)
    # Section header: UPPERCASE, letterspacing via word spacing trick, teal colour
    SH = ParagraphStyle('sh', fontName='Helvetica-Bold',   fontSize=9,  textColor=C['A'],  leading=14, spaceBefore=16, spaceAfter=6, wordSpace=3)
    PN = ParagraphStyle('pn', fontName='Helvetica',        fontSize=10, textColor=C['T'],  leading=14, spaceAfter=2)
    PB = ParagraphStyle('pb', fontName='Helvetica',        fontSize=10, textColor=C['T'],  leading=14)
    BD = ParagraphStyle('bd', fontName='Helvetica-Bold',   fontSize=10, textColor=C['T'],  leading=14)
    MU = ParagraphStyle('mu', fontName='Helvetica',        fontSize=9,  textColor=C['M'],  leading=13)
    AC = ParagraphStyle('ac', fontName='Helvetica',        fontSize=9,  textColor=C['A'],  leading=13)
    TG = ParagraphStyle('tg', fontName='Helvetica',        fontSize=9,  textColor=C['A'],  leading=13)

    story = []
    # Photo + name side by side if photo present
    name_txt = _get(ss,'name') or 'Your Name'
    jt = _get(ss,'job_title')
    cp = [_get(ss,k) for k in ['email','phone','location','linkedin','github','portfolio'] if _get(ss,k)]
    iv = _img(profile_img_bytes, 80)
    if iv:
        hdr = [Paragraph(name_txt, NM)]
        if jt: hdr.append(Paragraph(jt, JT))
        if cp: hdr.append(Paragraph('  ·  '.join(cp), CO))
        row = Table([[hdr, iv]], colWidths=[W-88, 88])
        row.setStyle(TableStyle([('VALIGN',(0,0),(-1,-1),'TOP'),('LEFTPADDING',(0,0),(-1,-1),0),('RIGHTPADDING',(0,0),(-1,-1),0)]))
        story.append(row)
    else:
        story.append(Paragraph(name_txt, NM))
        if jt: story.append(Paragraph(jt, JT))
        if cp: story.append(Paragraph('  ·  '.join(cp), CO))

    story.append(HRFlowable(width=W, thickness=4, color=C['A'], spaceBefore=10, spaceAfter=14))

    def sec(title):
        story.append(Paragraph(title.upper(), SH))

    def skills_inline(raw):
        items = _skills_list(raw)
        if not items: return
        story.append(Paragraph('  /  '.join(items), TG))
        story.append(Spacer(1, 4))

    sm = _get(ss,'summary')
    if sm:
        sec("Summary")
        for f in _bullets(sm, PN, PB, C['A']): story.append(f)

    exps = [e for e in _entries(ss,'experience_entries') if e.get('company') or e.get('title')]
    if exps:
        sec("Experience")
        for e in exps:
            story.append(_row2(Paragraph(f"<b>{e.get('company','')}</b>  {e.get('title','')}", PN), Paragraph(e.get('duration',''), AC), W))
            for f in _bullets(e.get('description',''), PN, PB, C['A']): story.append(f)
            story.append(Spacer(1,8))

    edus = [e for e in _entries(ss,'education_entries') if e.get('institution') or e.get('degree')]
    if edus:
        sec("Education")
        for e in edus:
            story.append(_row2(Paragraph(f"<b>{e.get('institution','')}</b>  {_deg(e)}", PN), Paragraph(e.get('year',''), AC), W))
            if e.get('details'): story.append(Paragraph(e['details'], MU))
            story.append(Spacer(1,6))

    if _get(ss,'skills'):    sec("Skills");     skills_inline(_get(ss,'skills'))
    if _get(ss,'Softskills'):sec("Soft Skills");skills_inline(_get(ss,'Softskills'))
    if _get(ss,'languages'): sec("Languages");  skills_inline(_get(ss,'languages'))
    if _get(ss,'interests'): sec("Interests");  skills_inline(_get(ss,'interests'))

    projs = [p for p in _entries(ss,'project_entries') if p.get('title')]
    proj_links = _entries(ss,'project_links')
    if projs:
        sec("Projects")
        for i, p in enumerate(projs):
            lnk = proj_links[i] if i < len(proj_links) else ''
            t = _link(lnk, p.get('title',''), '#0d9488') if lnk else p.get('title','')
            story.append(Paragraph(f"<b>{t}</b>", PN))
            if p.get('tech'): story.append(Paragraph(p['tech'], TG))
            for f in _bullets(p.get('description',''), PN, PB, C['A']): story.append(f)
            story.append(Spacer(1,8))

    certs = [c for c in _entries(ss,'certificate_links') if c.get('name')]
    if certs:
        sec("Certifications")
        for c in certs:
            nm = _link(c.get('link',''), c.get('name',''), '#0d9488') if c.get('link') else c.get('name','')
            story.append(_row2(Paragraph(nm, BD), Paragraph(c.get('duration',''), AC), W))
            if c.get('description'): story.append(Paragraph(c['description'], MU))
            story.append(Spacer(1,4))

    doc.build(story); buf.seek(0); return buf


# ═════════════════════════════════════════════════════════════════════════════
# TEMPLATE 3 — Elegant Sidebar
# Layout: TWO-COL purple sidebar (name + contact + all skills as vertical pills),
#         main: large name header + section underlines in purple
# ═════════════════════════════════════════════════════════════════════════════
def render_template_elegant_sidebar(session_state, profile_img_bytes=None):
    SB  = colors.HexColor('#7c3aed')
    SBL = colors.HexColor('#ede9fe')
    SBD = colors.HexColor('#a78bfa')
    WHT = colors.white
    TXT = colors.HexColor('#1f2937')
    MUT = colors.HexColor('#6b7280')

    buf = BytesIO(); ss = session_state

    sbN = ParagraphStyle('sbN', fontName='Helvetica-Bold',   fontSize=13, textColor=WHT, alignment=TA_CENTER, leading=18, spaceAfter=2)
    sbT = ParagraphStyle('sbT', fontName='Helvetica-Oblique',fontSize=10, textColor=SBL, alignment=TA_CENTER, leading=13, spaceAfter=6)
    sbS = ParagraphStyle('sbS', fontName='Helvetica-Bold',   fontSize=8,  textColor=SBL, leading=12, spaceBefore=10, spaceAfter=2)
    sbI = ParagraphStyle('sbI', fontName='Helvetica',        fontSize=9,  textColor=colors.HexColor('#f5f3ff'), leading=13, spaceAfter=2)
    sbP = ParagraphStyle('sbP', fontName='Helvetica',        fontSize=9,  textColor=SB,  alignment=TA_CENTER, leading=12)
    mN  = ParagraphStyle('mN',  fontName='Helvetica-Bold',   fontSize=20, textColor=SB,  leading=26)
    mH  = ParagraphStyle('mH',  fontName='Helvetica-Bold',   fontSize=11, textColor=SB,  leading=16, spaceBefore=10, spaceAfter=2)
    mN2 = ParagraphStyle('mN2', fontName='Helvetica',        fontSize=10, textColor=TXT, leading=14, spaceAfter=2)
    mB2 = ParagraphStyle('mB2', fontName='Helvetica',        fontSize=10, textColor=TXT, leading=14)
    mBD = ParagraphStyle('mBD', fontName='Helvetica-Bold',   fontSize=10, textColor=TXT, leading=14)
    mMU = ParagraphStyle('mMU', fontName='Helvetica',        fontSize=9,  textColor=MUT, leading=13)
    mAC = ParagraphStyle('mAC', fontName='Helvetica-Bold',   fontSize=9,  textColor=SB,  leading=13)

    SW = SIDEBAR_W - 18  # pill width inside sidebar

    def sb_pill(text):
        t = Table([[Paragraph(text, sbP)]], colWidths=[SW])
        t.setStyle(TableStyle([('BACKGROUND',(0,0),(-1,-1),SBL),
                                ('BOX',(0,0),(-1,-1),0.4,SBD),
                                ('TOPPADDING',(0,0),(-1,-1),2),('BOTTOMPADDING',(0,0),(-1,-1),2),
                                ('LEFTPADDING',(0,0),(-1,-1),4),('RIGHTPADDING',(0,0),(-1,-1),4)]))
        return t

    def sb_sec(title, sb):
        sb.append(HRFlowable(width=SW, thickness=0.4, color=SBD, spaceAfter=2))
        sb.append(Paragraph(title.upper(), sbS))

    sidebar = []
    iv = _img(profile_img_bytes, 80)
    if iv: sidebar += [iv, Spacer(1,6)]
    sidebar.append(Paragraph(_get(ss,'name') or 'Your Name', sbN))
    if _get(ss,'job_title'): sidebar.append(Paragraph(_get(ss,'job_title'), sbT))
    for k,lbl in [('email','Email'),('phone','Phone'),('location','Location'),
                  ('linkedin','LinkedIn'),('github','GitHub'),('portfolio','Portfolio')]:
        v = _get(ss,k)
        if v: sb_sec(lbl,sidebar); sidebar.append(Paragraph(v, sbI))
    for field,lbl in [('skills','Skills'),('Softskills','Soft Skills'),('languages','Languages'),('interests','Interests')]:
        v = _get(ss,field)
        if v:
            sb_sec(lbl, sidebar)
            for item in _skills_list(v):
                sidebar.append(sb_pill(item)); sidebar.append(Spacer(1,3))

    main = []
    main.append(Paragraph(_get(ss,'name') or 'Your Name', mN))
    main.append(HRFlowable(width=MAIN_W-12, thickness=2, color=SB, spaceBefore=4, spaceAfter=8))

    def m_sec(title):
        main.append(Paragraph(title, mH))
        main.append(HRFlowable(width=MAIN_W-12, thickness=0.5, color=SBD, spaceAfter=4))

    MW = MAIN_W - 12

    sm = _get(ss,'summary')
    if sm:
        m_sec("Professional Summary")
        for f in _bullets(sm, mN2, mB2, SB): main.append(f)

    exps = [e for e in _entries(ss,'experience_entries') if e.get('company') or e.get('title')]
    if exps:
        m_sec("Work Experience")
        for e in exps:
            main.append(_row2(Paragraph(f"<b>{e.get('company','')}</b> — {e.get('title','')}", mBD), Paragraph(e.get('duration',''), mAC), MW))
            for f in _bullets(e.get('description',''), mN2, mB2, SB): main.append(f)
            main.append(Spacer(1,6))

    edus = [e for e in _entries(ss,'education_entries') if e.get('institution') or e.get('degree')]
    if edus:
        m_sec("Education")
        for e in edus:
            main.append(_row2(Paragraph(f"<b>{e.get('institution','')}</b> — {_deg(e)}", mBD), Paragraph(e.get('year',''), mAC), MW))
            if e.get('details'): main.append(Paragraph(e['details'], mMU))
            main.append(Spacer(1,4))

    projs = [p for p in _entries(ss,'project_entries') if p.get('title')]
    proj_links = _entries(ss,'project_links')
    if projs:
        m_sec("Projects")
        for i, p in enumerate(projs):
            lnk = proj_links[i] if i < len(proj_links) else ''
            t = _link(lnk, p.get('title',''), '#7c3aed') if lnk else p.get('title','')
            main.append(Paragraph(f"<b>{t}</b>", mBD))
            if p.get('tech'): main.append(Paragraph(p['tech'], mMU))
            for f in _bullets(p.get('description',''), mN2, mB2, SB): main.append(f)
            main.append(Spacer(1,6))

    certs = [c for c in _entries(ss,'certificate_links') if c.get('name')]
    if certs:
        m_sec("Certifications")
        for c in certs:
            nm = _link(c.get('link',''), c.get('name',''), '#7c3aed') if c.get('link') else c.get('name','')
            main.append(_row2(Paragraph(nm, mBD), Paragraph(c.get('duration',''), mAC), MW))
            if c.get('description'): main.append(Paragraph(c['description'], mMU))
            main.append(Spacer(1,4))

    _two_col(buf, sidebar, main, SB, SBD); buf.seek(0); return buf


# ═════════════════════════════════════════════════════════════════════════════
# TEMPLATE 4 — Classic Clean
# Layout: single-col, ALL-CAPS section headings (no color), hairline under heading,
#         NO pill chips — skills listed as plain comma-separated text, monochrome
# ═════════════════════════════════════════════════════════════════════════════
def render_template_classic_clean(session_state, profile_img_bytes=None):
    BLK = colors.HexColor('#111111')
    MUT = colors.HexColor('#555555')
    LGT = colors.HexColor('#999999')

    buf = BytesIO(); ss = session_state; W = PAGE_W - 2*MARGIN
    doc = _new_doc(buf)
    NM = ParagraphStyle('nm', fontName='Helvetica-Bold',  fontSize=20, textColor=BLK, alignment=TA_CENTER, leading=26)
    JT = ParagraphStyle('jt', fontName='Helvetica',       fontSize=12, textColor=MUT, alignment=TA_CENTER, leading=16, spaceAfter=3)
    CO = ParagraphStyle('co', fontName='Helvetica',       fontSize=9,  textColor=LGT, alignment=TA_CENTER, leading=13)
    SH = ParagraphStyle('sh', fontName='Helvetica-Bold',  fontSize=10, textColor=BLK, leading=14, spaceBefore=12, spaceAfter=2)
    PN = ParagraphStyle('pn', fontName='Helvetica',       fontSize=10, textColor=BLK, leading=14, spaceAfter=2)
    PB = ParagraphStyle('pb', fontName='Helvetica',       fontSize=10, textColor=BLK, leading=14)
    BD = ParagraphStyle('bd', fontName='Helvetica-Bold',  fontSize=10, textColor=BLK, leading=14)
    MU = ParagraphStyle('mu', fontName='Helvetica',       fontSize=9,  textColor=MUT, leading=13)
    DT = ParagraphStyle('dt', fontName='Helvetica',       fontSize=9,  textColor=MUT, leading=13)
    SK = ParagraphStyle('sk', fontName='Helvetica',       fontSize=10, textColor=BLK, leading=14, spaceAfter=3)

    story = []
    iv = _img(profile_img_bytes, 64)
    if iv: story += [iv, Spacer(1,4)]
    story.append(Paragraph(_get(ss,'name') or 'Your Name', NM))
    if _get(ss,'job_title'): story.append(Paragraph(_get(ss,'job_title'), JT))
    cp = [_get(ss,k) for k in ['email','phone','location','linkedin','github','portfolio'] if _get(ss,k)]
    if cp: story.append(Paragraph(' | '.join(cp), CO))
    story.append(HRFlowable(width=W, thickness=1.5, color=BLK, spaceBefore=6, spaceAfter=6))

    def sec(title):
        story.append(Paragraph(title.upper(), SH))
        story.append(HRFlowable(width=W, thickness=0.4, color=MUT, spaceAfter=4))

    sm = _get(ss,'summary')
    if sm:
        sec("Professional Summary")
        for f in _bullets(sm, PN, PB, BLK): story.append(f)

    exps = [e for e in _entries(ss,'experience_entries') if e.get('company') or e.get('title')]
    if exps:
        sec("Work Experience")
        for e in exps:
            story.append(_row2(Paragraph(f"<b>{e.get('company','')}</b>, {e.get('title','')}", BD), Paragraph(e.get('duration',''), DT), W))
            for f in _bullets(e.get('description',''), PN, PB, BLK): story.append(f)
            story.append(Spacer(1,6))

    edus = [e for e in _entries(ss,'education_entries') if e.get('institution') or e.get('degree')]
    if edus:
        sec("Education")
        for e in edus:
            story.append(_row2(Paragraph(f"<b>{e.get('institution','')}</b>, {_deg(e)}", BD), Paragraph(e.get('year',''), DT), W))
            if e.get('details'): story.append(Paragraph(e['details'], MU))
            story.append(Spacer(1,4))

    # Skills as plain comma list — no pills
    for field, label in [('skills','Technical Skills'),('Softskills','Soft Skills'),('languages','Languages'),('interests','Interests')]:
        v = _get(ss,field)
        if v:
            sec(label)
            story.append(Paragraph(v, SK))

    projs = [p for p in _entries(ss,'project_entries') if p.get('title')]
    proj_links = _entries(ss,'project_links')
    if projs:
        sec("Projects")
        for i, p in enumerate(projs):
            lnk = proj_links[i] if i < len(proj_links) else ''
            t = _link(lnk, p.get('title',''), '#111111') if lnk else p.get('title','')
            story.append(Paragraph(f"<b>{t}</b>  |  {p.get('tech','')}", BD))
            for f in _bullets(p.get('description',''), PN, PB, BLK): story.append(f)
            story.append(Spacer(1,6))

    certs = [c for c in _entries(ss,'certificate_links') if c.get('name')]
    if certs:
        sec("Certifications")
        for c in certs:
            nm = _link(c.get('link',''), c.get('name',''), '#111111') if c.get('link') else c.get('name','')
            story.append(_row2(Paragraph(nm, BD), Paragraph(c.get('duration',''), DT), W))
            if c.get('description'): story.append(Paragraph(c['description'], MU))
            story.append(Spacer(1,4))

    doc.build(story); buf.seek(0); return buf


# ═════════════════════════════════════════════════════════════════════════════
# TEMPLATE 5 — Executive
# Layout: single-col, double-rule header (thick navy + thin gold), justified body,
#         star (★) bullets for skills, company name BIG + title below it small
# ═════════════════════════════════════════════════════════════════════════════
def render_template_executive(session_state, profile_img_bytes=None):
    NAV = colors.HexColor('#1e3a5f')
    GLD = colors.HexColor('#b7791f')
    TXT = colors.HexColor('#1a202c')
    MUT = colors.HexColor('#718096')

    buf = BytesIO(); ss = session_state; W = PAGE_W - 2*MARGIN
    doc = _new_doc(buf)
    NM = ParagraphStyle('nm', fontName='Helvetica-Bold',   fontSize=26, textColor=NAV, alignment=TA_CENTER, leading=32)
    JT = ParagraphStyle('jt', fontName='Helvetica-Oblique',fontSize=14, textColor=GLD, alignment=TA_CENTER, leading=19, spaceAfter=4)
    CO = ParagraphStyle('co', fontName='Helvetica',        fontSize=9,  textColor=MUT, alignment=TA_CENTER, leading=13)
    SH = ParagraphStyle('sh', fontName='Helvetica-Bold',   fontSize=12, textColor=NAV, leading=17, spaceBefore=12, spaceAfter=4)
    PN = ParagraphStyle('pn', fontName='Helvetica',        fontSize=10, textColor=TXT, leading=15, spaceAfter=3, alignment=TA_JUSTIFY)
    PB = ParagraphStyle('pb', fontName='Helvetica',        fontSize=10, textColor=TXT, leading=15)
    CO2= ParagraphStyle('co2',fontName='Helvetica-Bold',   fontSize=11, textColor=NAV, leading=15)
    TI = ParagraphStyle('ti', fontName='Helvetica-Oblique',fontSize=10, textColor=MUT, leading=14, spaceAfter=2)
    DT = ParagraphStyle('dt', fontName='Helvetica-Bold',   fontSize=9,  textColor=GLD, leading=13)
    MU = ParagraphStyle('mu', fontName='Helvetica',        fontSize=9,  textColor=MUT, leading=13)
    SK = ParagraphStyle('sk', fontName='Helvetica',        fontSize=10, textColor=TXT, leading=14)

    story = []
    iv = _img(profile_img_bytes, 80)
    if iv: story += [iv, Spacer(1,4)]
    story.append(Paragraph(_get(ss,'name') or 'Your Name', NM))
    if _get(ss,'job_title'): story.append(Paragraph(_get(ss,'job_title'), JT))
    cp = [_get(ss,k) for k in ['email','phone','location','linkedin','github','portfolio'] if _get(ss,k)]
    if cp: story.append(Paragraph(' | '.join(cp), CO))
    story.append(HRFlowable(width=W, thickness=2.5, color=NAV, spaceBefore=8, spaceAfter=3))
    story.append(HRFlowable(width=W, thickness=0.8, color=GLD, spaceBefore=0, spaceAfter=10))

    def sec(title):
        story.append(Paragraph(title, SH))
        story.append(HRFlowable(width=W, thickness=1, color=NAV, spaceAfter=6))

    def star_skills(raw):
        items = _skills_list(raw)
        if not items: return
        # render as two-column star-bullet list
        left_items = items[::2]; right_items = items[1::2]
        rows = []
        for i in range(max(len(left_items), len(right_items))):
            l = f"★  {left_items[i]}" if i < len(left_items) else ''
            r = f"★  {right_items[i]}" if i < len(right_items) else ''
            rows.append([Paragraph(l, SK), Paragraph(r, SK)])
        if rows:
            t = Table(rows, colWidths=[W/2, W/2])
            t.setStyle(TableStyle([('LEFTPADDING',(0,0),(-1,-1),0),('RIGHTPADDING',(0,0),(-1,-1),0),
                                    ('TOPPADDING',(0,0),(-1,-1),1),('BOTTOMPADDING',(0,0),(-1,-1),1)]))
            story.append(t)
            story.append(Spacer(1,4))

    sm = _get(ss,'summary')
    if sm:
        sec("Executive Summary")
        for f in _bullets(sm, PN, PB, NAV): story.append(f)

    exps = [e for e in _entries(ss,'experience_entries') if e.get('company') or e.get('title')]
    if exps:
        sec("Professional Experience")
        for e in exps:
            # Company big, then title small below, date right-aligned
            t = Table([[Paragraph(e.get('company',''), CO2), Paragraph(e.get('duration',''), DT)]], colWidths=[W*0.75, W*0.25])
            t.setStyle(TableStyle([('ALIGN',(1,0),(1,0),'RIGHT'),('VALIGN',(0,0),(-1,-1),'TOP'),
                                    ('LEFTPADDING',(0,0),(-1,-1),0),('RIGHTPADDING',(0,0),(-1,-1),0),
                                    ('TOPPADDING',(0,0),(-1,-1),0),('BOTTOMPADDING',(0,0),(-1,-1),0)]))
            story.append(t)
            if e.get('title'): story.append(Paragraph(e['title'], TI))
            for f in _bullets(e.get('description',''), PN, PB, NAV): story.append(f)
            story.append(Spacer(1,8))

    edus = [e for e in _entries(ss,'education_entries') if e.get('institution') or e.get('degree')]
    if edus:
        sec("Education")
        for e in edus:
            story.append(_row2(Paragraph(f"<b>{e.get('institution','')}</b> — {_deg(e)}", CO2), Paragraph(e.get('year',''), DT), W))
            if e.get('details'): story.append(Paragraph(e['details'], MU))
            story.append(Spacer(1,6))

    if _get(ss,'skills'):    sec("Core Competencies");       star_skills(_get(ss,'skills'))
    if _get(ss,'Softskills'):sec("Leadership & Soft Skills");star_skills(_get(ss,'Softskills'))
    if _get(ss,'languages'): sec("Languages");               star_skills(_get(ss,'languages'))
    if _get(ss,'interests'): sec("Interests");               story.append(Paragraph(_get(ss,'interests'), SK))

    projs = [p for p in _entries(ss,'project_entries') if p.get('title')]
    proj_links = _entries(ss,'project_links')
    if projs:
        sec("Key Projects")
        for i, p in enumerate(projs):
            lnk = proj_links[i] if i < len(proj_links) else ''
            t = _link(lnk, p.get('title',''), '#1e3a5f') if lnk else p.get('title','')
            story.append(Paragraph(f"<b>{t}</b>  |  {p.get('tech','')}", CO2))
            for f in _bullets(p.get('description',''), PN, PB, NAV): story.append(f)
            story.append(Spacer(1,6))

    certs = [c for c in _entries(ss,'certificate_links') if c.get('name')]
    if certs:
        sec("Certifications & Awards")
        for c in certs:
            nm = _link(c.get('link',''), c.get('name',''), '#1e3a5f') if c.get('link') else c.get('name','')
            story.append(_row2(Paragraph(nm, CO2), Paragraph(c.get('duration',''), DT), W))
            if c.get('description'): story.append(Paragraph(c['description'], MU))
            story.append(Spacer(1,4))

    doc.build(story); buf.seek(0); return buf


# ═════════════════════════════════════════════════════════════════════════════
# TEMPLATE 6 — Timeline
# Layout: left-margin amber dot-spine, each entry gets ●── prefix in a 2-col
#         Table (dot | content). Section labels ALL-CAPS amber, no dividers.
# ═════════════════════════════════════════════════════════════════════════════
def render_template_timeline(session_state, profile_img_bytes=None):
    AMB = colors.HexColor('#b45309')
    DOT = colors.HexColor('#f59e0b')
    TXT = colors.HexColor('#374151')
    MUT = colors.HexColor('#9ca3af')

    buf = BytesIO(); ss = session_state; W = PAGE_W - 2*MARGIN
    doc = _new_doc(buf)
    NM = ParagraphStyle('nm', fontName='Helvetica-Bold',   fontSize=22, textColor=AMB, leading=28)
    JT = ParagraphStyle('jt', fontName='Helvetica-Oblique',fontSize=13, textColor=TXT, leading=17, spaceAfter=3)
    CO = ParagraphStyle('co', fontName='Helvetica',        fontSize=9,  textColor=MUT, leading=13)
    SH = ParagraphStyle('sh', fontName='Helvetica-Bold',   fontSize=9,  textColor=AMB, leading=14, spaceBefore=14, spaceAfter=4, wordSpace=3)
    PN = ParagraphStyle('pn', fontName='Helvetica',        fontSize=10, textColor=TXT, leading=14, spaceAfter=2)
    PB = ParagraphStyle('pb', fontName='Helvetica',        fontSize=10, textColor=TXT, leading=14)
    BD = ParagraphStyle('bd', fontName='Helvetica-Bold',   fontSize=10, textColor=AMB, leading=14)
    MU = ParagraphStyle('mu', fontName='Helvetica',        fontSize=9,  textColor=MUT, leading=13)
    DT = ParagraphStyle('dt', fontName='Helvetica-Bold',   fontSize=9,  textColor=DOT, leading=13)
    PS = ParagraphStyle('ps', fontName='Helvetica-Bold',   fontSize=14, textColor=DOT, leading=18)

    story = []
    story.append(Paragraph(_get(ss,'name') or 'Your Name', NM))
    if _get(ss,'job_title'): story.append(Paragraph(_get(ss,'job_title'), JT))
    cp = [_get(ss,k) for k in ['email','phone','location','linkedin','github','portfolio'] if _get(ss,k)]
    if cp: story.append(Paragraph(' | '.join(cp), CO))
    story.append(HRFlowable(width=W, thickness=2.5, color=AMB, spaceBefore=6, spaceAfter=10))

    def sec(title):
        story.append(Paragraph(title.upper(), SH))

    def tl_entry(title, sub, dur, desc):
        dot_para = Paragraph('●', PS)
        content = [Paragraph(f'<b>{title}</b>', BD)]
        if sub:  content.append(Paragraph(sub, MU))
        if dur:  content.append(Paragraph(dur, DT))
        if desc:
            for f in _bullets(desc, PN, PB, AMB): content.append(f)
        content.append(Spacer(1,4))
        row = Table([[dot_para, content]], colWidths=[22, W-22])
        row.setStyle(TableStyle([('VALIGN',(0,0),(-1,-1),'TOP'),
                                  ('LEFTPADDING',(0,0),(-1,-1),0),('RIGHTPADDING',(0,0),(-1,-1),0),
                                  ('TOPPADDING',(0,0),(-1,-1),2),('BOTTOMPADDING',(0,0),(-1,-1),4)]))
        story.append(row)

    sm = _get(ss,'summary')
    if sm:
        sec("Profile")
        for f in _bullets(sm, PN, PB, AMB): story.append(f)
        story.append(Spacer(1,4))

    exps = [e for e in _entries(ss,'experience_entries') if e.get('company') or e.get('title')]
    if exps:
        sec("Work Experience")
        for e in exps:
            tl_entry(e.get('company',''), e.get('title',''), e.get('duration',''), e.get('description',''))

    edus = [e for e in _entries(ss,'education_entries') if e.get('institution') or e.get('degree')]
    if edus:
        sec("Education")
        for e in edus:
            tl_entry(e.get('institution',''), _deg(e), e.get('year',''), e.get('details',''))

    SK = ParagraphStyle('sk', fontName='Helvetica', fontSize=10, textColor=TXT, leading=14)
    for field,lbl in [('skills','Skills'),('Softskills','Soft Skills'),('languages','Languages'),('interests','Interests')]:
        v = _get(ss,field)
        if v:
            sec(lbl)
            story.extend(_pills(v, colors.HexColor('#fef3c7'), AMB, colors.HexColor('#fcd34d'), W))

    projs = [p for p in _entries(ss,'project_entries') if p.get('title')]
    proj_links = _entries(ss,'project_links')
    if projs:
        sec("Projects")
        for i, p in enumerate(projs):
            lnk = proj_links[i] if i < len(proj_links) else ''
            t = _link(lnk, p.get('title',''), '#b45309') if lnk else p.get('title','')
            tl_entry(t, p.get('tech',''), p.get('duration',''), p.get('description',''))

    certs = [c for c in _entries(ss,'certificate_links') if c.get('name')]
    if certs:
        sec("Certifications")
        for c in certs:
            nm = _link(c.get('link',''), c.get('name',''), '#b45309') if c.get('link') else c.get('name','')
            tl_entry(nm, c.get('description',''), c.get('duration',''), '')

    doc.build(story); buf.seek(0); return buf


# ═════════════════════════════════════════════════════════════════════════════
# TEMPLATE 7 — Corporate Blue
# Layout: TWO-COL navy sidebar, main section headings in a full-width navy box,
#         white text on navy for section labels, pill chips in sidebar (2-col)
# ═════════════════════════════════════════════════════════════════════════════
def render_template_corporate_blue(session_state, profile_img_bytes=None):
    NAV = colors.HexColor('#1d4ed8')
    LBL = colors.HexColor('#dbeafe')
    BDR = colors.HexColor('#93c5fd')
    WHT = colors.white
    TXT = colors.HexColor('#1e293b')
    MUT = colors.HexColor('#64748b')

    buf = BytesIO(); ss = session_state

    sbN = ParagraphStyle('sbN', fontName='Helvetica-Bold',   fontSize=13, textColor=WHT, alignment=TA_CENTER, leading=18, spaceAfter=2)
    sbT = ParagraphStyle('sbT', fontName='Helvetica-Oblique',fontSize=10, textColor=LBL, alignment=TA_CENTER, leading=13, spaceAfter=6)
    sbS = ParagraphStyle('sbS', fontName='Helvetica-Bold',   fontSize=8,  textColor=LBL, leading=12, spaceBefore=10, spaceAfter=2)
    sbI = ParagraphStyle('sbI', fontName='Helvetica',        fontSize=9,  textColor=colors.HexColor('#bfdbfe'), leading=13, spaceAfter=2)
    sbP = ParagraphStyle('sbP', fontName='Helvetica',        fontSize=8,  textColor=NAV, alignment=TA_CENTER, leading=12)
    # Main: section header = white-on-navy box
    mBX = ParagraphStyle('mBX', fontName='Helvetica-Bold',   fontSize=10, textColor=WHT, leading=14, spaceBefore=10)
    mN  = ParagraphStyle('mN',  fontName='Helvetica',        fontSize=10, textColor=TXT, leading=14, spaceAfter=2)
    mB  = ParagraphStyle('mB',  fontName='Helvetica',        fontSize=10, textColor=TXT, leading=14)
    mBD = ParagraphStyle('mBD', fontName='Helvetica-Bold',   fontSize=10, textColor=TXT, leading=14)
    mMU = ParagraphStyle('mMU', fontName='Helvetica',        fontSize=9,  textColor=MUT, leading=13)
    mAC = ParagraphStyle('mAC', fontName='Helvetica-Bold',   fontSize=9,  textColor=NAV, leading=13)

    SW = SIDEBAR_W - 18

    def sb_pill(text):
        t = Table([[Paragraph(text, sbP)]], colWidths=[SW])
        t.setStyle(TableStyle([('BACKGROUND',(0,0),(-1,-1),LBL),('BOX',(0,0),(-1,-1),0.4,BDR),
                                ('TOPPADDING',(0,0),(-1,-1),2),('BOTTOMPADDING',(0,0),(-1,-1),2),
                                ('LEFTPADDING',(0,0),(-1,-1),3),('RIGHTPADDING',(0,0),(-1,-1),3)]))
        return t

    def sb_sec(title, sb):
        sb.append(HRFlowable(width=SW, thickness=0.4, color=BDR, spaceAfter=2))
        sb.append(Paragraph(title.upper(), sbS))

    sidebar = []
    iv = _img(profile_img_bytes, 80)
    if iv: sidebar += [iv, Spacer(1,6)]
    sidebar.append(Paragraph(_get(ss,'name') or 'Your Name', sbN))
    if _get(ss,'job_title'): sidebar.append(Paragraph(_get(ss,'job_title'), sbT))
    for k,lbl in [('email','Email'),('phone','Phone'),('location','Location'),
                  ('linkedin','LinkedIn'),('github','GitHub'),('portfolio','Portfolio')]:
        v = _get(ss,k)
        if v: sb_sec(lbl,sidebar); sidebar.append(Paragraph(v, sbI))
    for field,lbl in [('skills','Skills'),('Softskills','Soft Skills'),('languages','Languages'),('interests','Interests')]:
        v = _get(ss,field)
        if v:
            sb_sec(lbl, sidebar)
            for item in _skills_list(v):
                sidebar.append(sb_pill(item)); sidebar.append(Spacer(1,3))

    MW = MAIN_W - 12
    main = []

    def box_sec(title):
        # Section label = white text on navy background box
        bx = Table([[Paragraph(f'  {title}', mBX)]], colWidths=[MW])
        bx.setStyle(TableStyle([('BACKGROUND',(0,0),(-1,-1),NAV),
                                 ('TOPPADDING',(0,0),(-1,-1),3),('BOTTOMPADDING',(0,0),(-1,-1),3),
                                 ('LEFTPADDING',(0,0),(-1,-1),4),('RIGHTPADDING',(0,0),(-1,-1),4)]))
        main.append(bx)
        main.append(Spacer(1,4))

    sm = _get(ss,'summary')
    if sm:
        box_sec("Professional Summary")
        for f in _bullets(sm, mN, mB, NAV): main.append(f)

    exps = [e for e in _entries(ss,'experience_entries') if e.get('company') or e.get('title')]
    if exps:
        box_sec("Work Experience")
        for e in exps:
            main.append(_row2(Paragraph(f"<b>{e.get('company','')}</b> — {e.get('title','')}", mBD), Paragraph(e.get('duration',''), mAC), MW))
            for f in _bullets(e.get('description',''), mN, mB, NAV): main.append(f)
            main.append(Spacer(1,6))

    edus = [e for e in _entries(ss,'education_entries') if e.get('institution') or e.get('degree')]
    if edus:
        box_sec("Education")
        for e in edus:
            main.append(_row2(Paragraph(f"<b>{e.get('institution','')}</b> — {_deg(e)}", mBD), Paragraph(e.get('year',''), mAC), MW))
            if e.get('details'): main.append(Paragraph(e['details'], mMU))
            main.append(Spacer(1,4))

    projs = [p for p in _entries(ss,'project_entries') if p.get('title')]
    proj_links = _entries(ss,'project_links')
    if projs:
        box_sec("Projects")
        for i, p in enumerate(projs):
            lnk = proj_links[i] if i < len(proj_links) else ''
            t = _link(lnk, p.get('title',''), '#1d4ed8') if lnk else p.get('title','')
            main.append(Paragraph(f"<b>{t}</b>  |  {p.get('tech','')}", mBD))
            for f in _bullets(p.get('description',''), mN, mB, NAV): main.append(f)
            main.append(Spacer(1,6))

    certs = [c for c in _entries(ss,'certificate_links') if c.get('name')]
    if certs:
        box_sec("Certifications")
        for c in certs:
            nm = _link(c.get('link',''), c.get('name',''), '#1d4ed8') if c.get('link') else c.get('name','')
            main.append(_row2(Paragraph(nm, mBD), Paragraph(c.get('duration',''), mAC), MW))
            if c.get('description'): main.append(Paragraph(c['description'], mMU))
            main.append(Spacer(1,4))

    _two_col(buf, sidebar, main, NAV, BDR); buf.seek(0); return buf


# ═════════════════════════════════════════════════════════════════════════════
# TEMPLATE 8 — Creative Green
# Layout: TWO-COL forest-green sidebar. Main: each section separated by a
#         short left-aligned colored bar (not full-width) for visual rhythm.
# ═════════════════════════════════════════════════════════════════════════════
def render_template_creative_green(session_state, profile_img_bytes=None):
    GRN = colors.HexColor('#166534')
    LGN = colors.HexColor('#dcfce7')
    BGD = colors.HexColor('#86efac')
    WHT = colors.white
    TXT = colors.HexColor('#1a2e1a')
    MUT = colors.HexColor('#6b7280')

    buf = BytesIO(); ss = session_state

    sbN = ParagraphStyle('sbN', fontName='Helvetica-Bold',   fontSize=13, textColor=WHT, alignment=TA_CENTER, leading=18, spaceAfter=2)
    sbT = ParagraphStyle('sbT', fontName='Helvetica-Oblique',fontSize=10, textColor=LGN, alignment=TA_CENTER, leading=13, spaceAfter=6)
    sbS = ParagraphStyle('sbS', fontName='Helvetica-Bold',   fontSize=8,  textColor=LGN, leading=12, spaceBefore=10, spaceAfter=2)
    sbI = ParagraphStyle('sbI', fontName='Helvetica',        fontSize=9,  textColor=colors.HexColor('#d1fae5'), leading=13, spaceAfter=2)
    sbP = ParagraphStyle('sbP', fontName='Helvetica',        fontSize=9,  textColor=GRN, alignment=TA_CENTER, leading=12)
    mH  = ParagraphStyle('mH',  fontName='Helvetica-Bold',   fontSize=11, textColor=GRN, leading=16, spaceBefore=10, spaceAfter=2)
    mN  = ParagraphStyle('mN',  fontName='Helvetica',        fontSize=10, textColor=TXT, leading=14, spaceAfter=2)
    mB  = ParagraphStyle('mB',  fontName='Helvetica',        fontSize=10, textColor=TXT, leading=14)
    mBD = ParagraphStyle('mBD', fontName='Helvetica-Bold',   fontSize=10, textColor=TXT, leading=14)
    mMU = ParagraphStyle('mMU', fontName='Helvetica',        fontSize=9,  textColor=MUT, leading=13)
    mAC = ParagraphStyle('mAC', fontName='Helvetica-Bold',   fontSize=9,  textColor=GRN, leading=13)

    SW = SIDEBAR_W - 18

    def sb_pill(text):
        t = Table([[Paragraph(text, sbP)]], colWidths=[SW])
        t.setStyle(TableStyle([('BACKGROUND',(0,0),(-1,-1),LGN),('BOX',(0,0),(-1,-1),0.4,BGD),
                                ('TOPPADDING',(0,0),(-1,-1),2),('BOTTOMPADDING',(0,0),(-1,-1),2),
                                ('LEFTPADDING',(0,0),(-1,-1),3),('RIGHTPADDING',(0,0),(-1,-1),3)]))
        return t

    def sb_sec(title, sb):
        sb.append(HRFlowable(width=SW, thickness=0.4, color=BGD, spaceAfter=2))
        sb.append(Paragraph(title.upper(), sbS))

    sidebar = []
    iv = _img(profile_img_bytes, 80)
    if iv: sidebar += [iv, Spacer(1,6)]
    sidebar.append(Paragraph(_get(ss,'name') or 'Your Name', sbN))
    if _get(ss,'job_title'): sidebar.append(Paragraph(_get(ss,'job_title'), sbT))
    for k,lbl in [('email','Email'),('phone','Phone'),('location','Location'),
                  ('linkedin','LinkedIn'),('github','GitHub'),('portfolio','Portfolio')]:
        v = _get(ss,k)
        if v: sb_sec(lbl,sidebar); sidebar.append(Paragraph(v, sbI))
    for field,lbl in [('skills','Skills'),('Softskills','Soft Skills'),('languages','Languages'),('interests','Interests')]:
        v = _get(ss,field)
        if v:
            sb_sec(lbl, sidebar)
            for item in _skills_list(v):
                sidebar.append(sb_pill(item)); sidebar.append(Spacer(1,3))

    MW = MAIN_W - 12
    main = []

    def m_sec(title):
        # Short left bar + title
        bar_row = Table([[Paragraph('', mH), Paragraph(title, mH)]], colWidths=[6, MW-6])
        bar_row.setStyle(TableStyle([('BACKGROUND',(0,0),(0,-1),GRN),
                                      ('LEFTPADDING',(0,0),(-1,-1),0),('RIGHTPADDING',(0,0),(-1,-1),0),
                                      ('TOPPADDING',(0,0),(-1,-1),0),('BOTTOMPADDING',(0,0),(-1,-1),0),
                                      ('LEFTPADDING',(1,0),(1,-1),6),
                                      ('VALIGN',(0,0),(-1,-1),'MIDDLE')]))
        main.append(bar_row)
        main.append(HRFlowable(width=MW, thickness=0.4, color=BGD, spaceAfter=4))

    sm = _get(ss,'summary')
    if sm:
        m_sec("Profile")
        for f in _bullets(sm, mN, mB, GRN): main.append(f)

    exps = [e for e in _entries(ss,'experience_entries') if e.get('company') or e.get('title')]
    if exps:
        m_sec("Work Experience")
        for e in exps:
            main.append(_row2(Paragraph(f"<b>{e.get('company','')}</b> — {e.get('title','')}", mBD), Paragraph(e.get('duration',''), mAC), MW))
            for f in _bullets(e.get('description',''), mN, mB, GRN): main.append(f)
            main.append(Spacer(1,6))

    edus = [e for e in _entries(ss,'education_entries') if e.get('institution') or e.get('degree')]
    if edus:
        m_sec("Education")
        for e in edus:
            main.append(_row2(Paragraph(f"<b>{e.get('institution','')}</b> — {_deg(e)}", mBD), Paragraph(e.get('year',''), mAC), MW))
            if e.get('details'): main.append(Paragraph(e['details'], mMU))
            main.append(Spacer(1,4))

    projs = [p for p in _entries(ss,'project_entries') if p.get('title')]
    proj_links = _entries(ss,'project_links')
    if projs:
        m_sec("Projects")
        for i, p in enumerate(projs):
            lnk = proj_links[i] if i < len(proj_links) else ''
            t = _link(lnk, p.get('title',''), '#166534') if lnk else p.get('title','')
            main.append(Paragraph(f"<b>{t}</b>  |  {p.get('tech','')}", mBD))
            for f in _bullets(p.get('description',''), mN, mB, GRN): main.append(f)
            main.append(Spacer(1,6))

    certs = [c for c in _entries(ss,'certificate_links') if c.get('name')]
    if certs:
        m_sec("Certifications")
        for c in certs:
            nm = _link(c.get('link',''), c.get('name',''), '#166534') if c.get('link') else c.get('name','')
            main.append(_row2(Paragraph(nm, mBD), Paragraph(c.get('duration',''), mAC), MW))
            if c.get('description'): main.append(Paragraph(c['description'], mMU))
            main.append(Spacer(1,4))

    _two_col(buf, sidebar, main, GRN, BGD); buf.seek(0); return buf


# ═════════════════════════════════════════════════════════════════════════════
# TEMPLATE 9 — Warm Terracotta
# Layout: TWO-COL terracotta sidebar. Main: each experience entry in a
#         BOXED card (Table with all-side border) — distinct from all others.
# ═════════════════════════════════════════════════════════════════════════════
def render_template_warm_terracotta(session_state, profile_img_bytes=None):
    TER = colors.HexColor('#c2410c')
    LTR = colors.HexColor('#ffedd5')
    BDR = colors.HexColor('#fdba74')
    WHT = colors.white
    TXT = colors.HexColor('#1c1917')
    MUT = colors.HexColor('#78716c')

    buf = BytesIO(); ss = session_state

    sbN = ParagraphStyle('sbN', fontName='Helvetica-Bold',   fontSize=13, textColor=WHT, alignment=TA_CENTER, leading=18, spaceAfter=2)
    sbT = ParagraphStyle('sbT', fontName='Helvetica-Oblique',fontSize=10, textColor=LTR, alignment=TA_CENTER, leading=13, spaceAfter=6)
    sbS = ParagraphStyle('sbS', fontName='Helvetica-Bold',   fontSize=8,  textColor=LTR, leading=12, spaceBefore=10, spaceAfter=2)
    sbI = ParagraphStyle('sbI', fontName='Helvetica',        fontSize=9,  textColor=colors.HexColor('#fed7aa'), leading=13, spaceAfter=2)
    sbP = ParagraphStyle('sbP', fontName='Helvetica',        fontSize=9,  textColor=TER, alignment=TA_CENTER, leading=12)
    mH  = ParagraphStyle('mH',  fontName='Helvetica-Bold',   fontSize=11, textColor=TER, leading=16, spaceBefore=10, spaceAfter=3)
    mN  = ParagraphStyle('mN',  fontName='Helvetica',        fontSize=10, textColor=TXT, leading=14, spaceAfter=2)
    mB  = ParagraphStyle('mB',  fontName='Helvetica',        fontSize=10, textColor=TXT, leading=14)
    mBD = ParagraphStyle('mBD', fontName='Helvetica-Bold',   fontSize=10, textColor=TER, leading=14)
    mMU = ParagraphStyle('mMU', fontName='Helvetica',        fontSize=9,  textColor=MUT, leading=13)
    mAC = ParagraphStyle('mAC', fontName='Helvetica-Bold',   fontSize=9,  textColor=TER, leading=13)
    mNM = ParagraphStyle('mNM', fontName='Helvetica',        fontSize=10, textColor=TXT, leading=14)

    SW = SIDEBAR_W - 18

    def sb_pill(text):
        t = Table([[Paragraph(text, sbP)]], colWidths=[SW])
        t.setStyle(TableStyle([('BACKGROUND',(0,0),(-1,-1),LTR),('BOX',(0,0),(-1,-1),0.4,BDR),
                                ('TOPPADDING',(0,0),(-1,-1),2),('BOTTOMPADDING',(0,0),(-1,-1),2),
                                ('LEFTPADDING',(0,0),(-1,-1),3),('RIGHTPADDING',(0,0),(-1,-1),3)]))
        return t

    def sb_sec(title, sb):
        sb.append(HRFlowable(width=SW, thickness=0.4, color=BDR, spaceAfter=2))
        sb.append(Paragraph(title.upper(), sbS))

    sidebar = []
    iv = _img(profile_img_bytes, 80)
    if iv: sidebar += [iv, Spacer(1,6)]
    sidebar.append(Paragraph(_get(ss,'name') or 'Your Name', sbN))
    if _get(ss,'job_title'): sidebar.append(Paragraph(_get(ss,'job_title'), sbT))
    for k,lbl in [('email','Email'),('phone','Phone'),('location','Location'),
                  ('linkedin','LinkedIn'),('github','GitHub'),('portfolio','Portfolio')]:
        v = _get(ss,k)
        if v: sb_sec(lbl,sidebar); sidebar.append(Paragraph(v, sbI))
    for field,lbl in [('skills','Skills'),('Softskills','Soft Skills'),('languages','Languages'),('interests','Interests')]:
        v = _get(ss,field)
        if v:
            sb_sec(lbl, sidebar)
            for item in _skills_list(v):
                sidebar.append(sb_pill(item)); sidebar.append(Spacer(1,3))

    MW = MAIN_W - 12
    main = []

    def m_sec(title):
        main.append(Paragraph(title, mH))
        main.append(HRFlowable(width=MW, thickness=1.5, color=TER, spaceAfter=4))

    def card(inner_flowables):
        # Wrap content in a boxed card
        inner_table = Table([[inner_flowables]], colWidths=[MW-12])
        inner_table.setStyle(TableStyle([
            ('BOX',(0,0),(-1,-1),0.7,BDR),
            ('BACKGROUND',(0,0),(-1,-1),colors.HexColor('#fffbf8')),
            ('TOPPADDING',(0,0),(-1,-1),5),('BOTTOMPADDING',(0,0),(-1,-1),5),
            ('LEFTPADDING',(0,0),(-1,-1),8),('RIGHTPADDING',(0,0),(-1,-1),6),
        ]))
        main.append(inner_table)
        main.append(Spacer(1,6))

    sm = _get(ss,'summary')
    if sm:
        m_sec("Summary")
        for f in _bullets(sm, mN, mB, TER): main.append(f)

    exps = [e for e in _entries(ss,'experience_entries') if e.get('company') or e.get('title')]
    if exps:
        m_sec("Work Experience")
        for e in exps:
            inner = [_row2(Paragraph(f"<b>{e.get('company','')}</b> — {e.get('title','')}", mBD),
                           Paragraph(e.get('duration',''), mAC), MW-12)]
            inner += _bullets(e.get('description',''), mNM, mNM, TER)
            card(inner)

    edus = [e for e in _entries(ss,'education_entries') if e.get('institution') or e.get('degree')]
    if edus:
        m_sec("Education")
        for e in edus:
            inner = [_row2(Paragraph(f"<b>{e.get('institution','')}</b> — {_deg(e)}", mBD),
                           Paragraph(e.get('year',''), mAC), MW-12)]
            if e.get('details'): inner.append(Paragraph(e['details'], mMU))
            card(inner)

    projs = [p for p in _entries(ss,'project_entries') if p.get('title')]
    proj_links = _entries(ss,'project_links')
    if projs:
        m_sec("Projects")
        for i, p in enumerate(projs):
            lnk = proj_links[i] if i < len(proj_links) else ''
            t = _link(lnk, p.get('title',''), '#c2410c') if lnk else p.get('title','')
            inner = [Paragraph(f"<b>{t}</b>  |  {p.get('tech','')}", mBD)]
            inner += _bullets(p.get('description',''), mNM, mNM, TER)
            card(inner)

    certs = [c for c in _entries(ss,'certificate_links') if c.get('name')]
    if certs:
        m_sec("Certifications")
        for c in certs:
            nm = _link(c.get('link',''), c.get('name',''), '#c2410c') if c.get('link') else c.get('name','')
            inner = [_row2(Paragraph(nm, mBD), Paragraph(c.get('duration',''), mAC), MW-12)]
            if c.get('description'): inner.append(Paragraph(c['description'], mMU))
            card(inner)

    _two_col(buf, sidebar, main, TER, BDR); buf.seek(0); return buf


# ═════════════════════════════════════════════════════════════════════════════
# TEMPLATE 10 — Navy Prestige
# Layout: TWO-COL navy sidebar. Main: GOLD section text + double-underline
#         (thick navy + thin gold). Contact shown as icon-label pairs.
# ═════════════════════════════════════════════════════════════════════════════
def render_template_navy_prestige(session_state, profile_img_bytes=None):
    NAV = colors.HexColor('#1e3a5f')
    GLD = colors.HexColor('#f59e0b')
    LBL = colors.HexColor('#e2e8f0')
    BDR = colors.HexColor('#3b82f6')
    WHT = colors.white
    TXT = colors.HexColor('#1e293b')
    MUT = colors.HexColor('#64748b')

    buf = BytesIO(); ss = session_state

    sbN = ParagraphStyle('sbN', fontName='Helvetica-Bold',   fontSize=13, textColor=WHT, alignment=TA_CENTER, leading=18, spaceAfter=2)
    sbT = ParagraphStyle('sbT', fontName='Helvetica-Oblique',fontSize=10, textColor=GLD, alignment=TA_CENTER, leading=13, spaceAfter=6)
    sbS = ParagraphStyle('sbS', fontName='Helvetica-Bold',   fontSize=8,  textColor=GLD, leading=12, spaceBefore=10, spaceAfter=2)
    sbI = ParagraphStyle('sbI', fontName='Helvetica',        fontSize=9,  textColor=LBL, leading=13, spaceAfter=2)
    sbP = ParagraphStyle('sbP', fontName='Helvetica',        fontSize=9,  textColor=NAV, alignment=TA_CENTER, leading=12)
    mH  = ParagraphStyle('mH',  fontName='Helvetica-Bold',   fontSize=12, textColor=GLD, leading=16, spaceBefore=12, spaceAfter=2)
    mN  = ParagraphStyle('mN',  fontName='Helvetica',        fontSize=10, textColor=TXT, leading=14, spaceAfter=2)
    mB  = ParagraphStyle('mB',  fontName='Helvetica',        fontSize=10, textColor=TXT, leading=14)
    mBD = ParagraphStyle('mBD', fontName='Helvetica-Bold',   fontSize=10, textColor=NAV, leading=14)
    mMU = ParagraphStyle('mMU', fontName='Helvetica',        fontSize=9,  textColor=MUT, leading=13)
    mAC = ParagraphStyle('mAC', fontName='Helvetica-Bold',   fontSize=9,  textColor=GLD, leading=13)

    SW = SIDEBAR_W - 18

    def sb_pill(text):
        t = Table([[Paragraph(text, sbP)]], colWidths=[SW])
        t.setStyle(TableStyle([('BACKGROUND',(0,0),(-1,-1),colors.HexColor('#eff6ff')),
                                ('BOX',(0,0),(-1,-1),0.4,BDR),
                                ('TOPPADDING',(0,0),(-1,-1),2),('BOTTOMPADDING',(0,0),(-1,-1),2),
                                ('LEFTPADDING',(0,0),(-1,-1),3),('RIGHTPADDING',(0,0),(-1,-1),3)]))
        return t

    def sb_sec(title, sb):
        sb.append(HRFlowable(width=SW, thickness=0.4, color=GLD, spaceAfter=2))
        sb.append(Paragraph(title.upper(), sbS))

    sidebar = []
    iv = _img(profile_img_bytes, 80)
    if iv: sidebar += [iv, Spacer(1,6)]
    sidebar.append(Paragraph(_get(ss,'name') or 'Your Name', sbN))
    if _get(ss,'job_title'): sidebar.append(Paragraph(_get(ss,'job_title'), sbT))
    for k,lbl in [('email','Email'),('phone','Phone'),('location','Location'),
                  ('linkedin','LinkedIn'),('github','GitHub'),('portfolio','Portfolio')]:
        v = _get(ss,k)
        if v: sb_sec(lbl,sidebar); sidebar.append(Paragraph(v, sbI))
    for field,lbl in [('skills','Skills'),('Softskills','Soft Skills'),('languages','Languages'),('interests','Interests')]:
        v = _get(ss,field)
        if v:
            sb_sec(lbl, sidebar)
            for item in _skills_list(v):
                sidebar.append(sb_pill(item)); sidebar.append(Spacer(1,3))

    MW = MAIN_W - 12
    main = []

    def m_sec(title):
        main.append(Paragraph(title, mH))
        main.append(HRFlowable(width=MW, thickness=1.5, color=NAV, spaceAfter=2))
        main.append(HRFlowable(width=MW, thickness=0.6, color=GLD, spaceAfter=4))

    sm = _get(ss,'summary')
    if sm:
        m_sec("Professional Summary")
        for f in _bullets(sm, mN, mB, GLD): main.append(f)

    exps = [e for e in _entries(ss,'experience_entries') if e.get('company') or e.get('title')]
    if exps:
        m_sec("Work Experience")
        for e in exps:
            main.append(_row2(Paragraph(f"<b>{e.get('company','')}</b> — {e.get('title','')}", mBD),
                              Paragraph(e.get('duration',''), mAC), MW))
            for f in _bullets(e.get('description',''), mN, mB, GLD): main.append(f)
            main.append(Spacer(1,6))

    edus = [e for e in _entries(ss,'education_entries') if e.get('institution') or e.get('degree')]
    if edus:
        m_sec("Education")
        for e in edus:
            main.append(_row2(Paragraph(f"<b>{e.get('institution','')}</b> — {_deg(e)}", mBD),
                              Paragraph(e.get('year',''), mAC), MW))
            if e.get('details'): main.append(Paragraph(e['details'], mMU))
            main.append(Spacer(1,4))

    projs = [p for p in _entries(ss,'project_entries') if p.get('title')]
    proj_links = _entries(ss,'project_links')
    if projs:
        m_sec("Projects")
        for i, p in enumerate(projs):
            lnk = proj_links[i] if i < len(proj_links) else ''
            t = _link(lnk, p.get('title',''), '#1e3a5f') if lnk else p.get('title','')
            main.append(Paragraph(f"<b>{t}</b>  |  {p.get('tech','')}", mBD))
            for f in _bullets(p.get('description',''), mN, mB, GLD): main.append(f)
            main.append(Spacer(1,6))

    certs = [c for c in _entries(ss,'certificate_links') if c.get('name')]
    if certs:
        m_sec("Certifications")
        for c in certs:
            nm = _link(c.get('link',''), c.get('name',''), '#1e3a5f') if c.get('link') else c.get('name','')
            main.append(_row2(Paragraph(nm, mBD), Paragraph(c.get('duration',''), mAC), MW))
            if c.get('description'): main.append(Paragraph(c['description'], mMU))
            main.append(Spacer(1,4))

    _two_col(buf, sidebar, main, NAV, BDR); buf.seek(0); return buf


# ═════════════════════════════════════════════════════════════════════════════
# TEMPLATE 11 — Slate Gray
# Layout: single-col. Full-width GRAY BAND header (Table cell with bg),
#         white name/title on gray. Light gray section dividers. Subdued palette.
# ═════════════════════════════════════════════════════════════════════════════
def render_template_slate_gray(session_state, profile_img_bytes=None):
    SLT = colors.HexColor('#334155')
    LGY = colors.HexColor('#f1f5f9')
    BDR = colors.HexColor('#cbd5e1')
    WHT = colors.white
    TXT = colors.HexColor('#334155')
    MUT = colors.HexColor('#94a3b8')
    ACC = colors.HexColor('#475569')

    buf = BytesIO(); ss = session_state; W = PAGE_W - 2*MARGIN
    doc = _new_doc(buf)

    # Header band styles
    hN = ParagraphStyle('hN', fontName='Helvetica-Bold',   fontSize=22, textColor=WHT, leading=28)
    hT = ParagraphStyle('hT', fontName='Helvetica-Oblique',fontSize=12, textColor=colors.HexColor('#94a3b8'), leading=16, spaceAfter=2)
    hC = ParagraphStyle('hC', fontName='Helvetica',        fontSize=9,  textColor=colors.HexColor('#cbd5e1'), leading=13)
    SH = ParagraphStyle('SH', fontName='Helvetica-Bold',   fontSize=10, textColor=SLT, leading=14, spaceBefore=12, spaceAfter=3)
    PN = ParagraphStyle('PN', fontName='Helvetica',        fontSize=10, textColor=TXT, leading=14, spaceAfter=2)
    PB = ParagraphStyle('PB', fontName='Helvetica',        fontSize=10, textColor=TXT, leading=14)
    BD = ParagraphStyle('BD', fontName='Helvetica-Bold',   fontSize=10, textColor=SLT, leading=14)
    MU = ParagraphStyle('MU', fontName='Helvetica',        fontSize=9,  textColor=MUT, leading=13)
    AC = ParagraphStyle('AC', fontName='Helvetica-Bold',   fontSize=9,  textColor=ACC, leading=13)

    story = []

    # Full-width gray header band
    hdr_content = [Paragraph(_get(ss,'name') or 'Your Name', hN)]
    if _get(ss,'job_title'): hdr_content.append(Paragraph(_get(ss,'job_title'), hT))
    cp = [_get(ss,k) for k in ['email','phone','location','linkedin','github','portfolio'] if _get(ss,k)]
    if cp: hdr_content.append(Paragraph('  |  '.join(cp), hC))

    if profile_img_bytes:
        iv = _img(profile_img_bytes, 72)
        if iv:
            hdr_tbl = Table([[hdr_content, iv]], colWidths=[W-80, 80])
            hdr_tbl.setStyle(TableStyle([('VALIGN',(0,0),(-1,-1),'MIDDLE'),
                                          ('LEFTPADDING',(0,0),(-1,-1),0),('RIGHTPADDING',(0,0),(-1,-1),0)]))
            hdr_content = [hdr_tbl]

    band = Table([[hdr_content]], colWidths=[W])
    band.setStyle(TableStyle([('BACKGROUND',(0,0),(-1,-1),SLT),
                               ('TOPPADDING',(0,0),(-1,-1),12),('BOTTOMPADDING',(0,0),(-1,-1),12),
                               ('LEFTPADDING',(0,0),(-1,-1),14),('RIGHTPADDING',(0,0),(-1,-1),14)]))
    story.append(band)
    story.append(Spacer(1, 8))

    def sec(title):
        story.append(Paragraph(title, SH))
        story.append(HRFlowable(width=W, thickness=0.5, color=BDR, spaceAfter=4))

    sm = _get(ss,'summary')
    if sm:
        sec("Summary")
        for f in _bullets(sm, PN, PB, ACC): story.append(f)

    exps = [e for e in _entries(ss,'experience_entries') if e.get('company') or e.get('title')]
    if exps:
        sec("Experience")
        for e in exps:
            story.append(_row2(Paragraph(f"<b>{e.get('company','')}</b> — {e.get('title','')}", BD),
                               Paragraph(e.get('duration',''), AC), W))
            for f in _bullets(e.get('description',''), PN, PB, ACC): story.append(f)
            story.append(Spacer(1,6))

    edus = [e for e in _entries(ss,'education_entries') if e.get('institution') or e.get('degree')]
    if edus:
        sec("Education")
        for e in edus:
            story.append(_row2(Paragraph(f"<b>{e.get('institution','')}</b> — {_deg(e)}", BD),
                               Paragraph(e.get('year',''), AC), W))
            if e.get('details'): story.append(Paragraph(e['details'], MU))
            story.append(Spacer(1,4))

    for field,lbl in [('skills','Skills'),('Softskills','Soft Skills'),('languages','Languages'),('interests','Interests')]:
        v = _get(ss,field)
        if v:
            sec(lbl)
            story.extend(_pills(v, LGY, SLT, BDR, W))

    projs = [p for p in _entries(ss,'project_entries') if p.get('title')]
    proj_links = _entries(ss,'project_links')
    if projs:
        sec("Projects")
        for i, p in enumerate(projs):
            lnk = proj_links[i] if i < len(proj_links) else ''
            t = _link(lnk, p.get('title',''), '#334155') if lnk else p.get('title','')
            story.append(Paragraph(f"<b>{t}</b>  |  {p.get('tech','')}", BD))
            for f in _bullets(p.get('description',''), PN, PB, ACC): story.append(f)
            story.append(Spacer(1,6))

    certs = [c for c in _entries(ss,'certificate_links') if c.get('name')]
    if certs:
        sec("Certifications")
        for c in certs:
            nm = _link(c.get('link',''), c.get('name',''), '#334155') if c.get('link') else c.get('name','')
            story.append(_row2(Paragraph(nm, BD), Paragraph(c.get('duration',''), AC), W))
            if c.get('description'): story.append(Paragraph(c['description'], MU))
            story.append(Spacer(1,4))

    doc.build(story); buf.seek(0); return buf


# ═════════════════════════════════════════════════════════════════════════════
# TEMPLATE 12 — Teal Impact
# Layout: TWO-COL teal sidebar. Main: each section has a vertical LEFT accent
#         bar rendered as a narrow colored Table cell beside content.
# ═════════════════════════════════════════════════════════════════════════════
def render_template_teal_impact(session_state, profile_img_bytes=None):
    TEA = colors.HexColor('#0f766e')
    LTE = colors.HexColor('#ccfbf1')
    BDR = colors.HexColor('#5eead4')
    WHT = colors.white
    TXT = colors.HexColor('#1a2e2e')
    MUT = colors.HexColor('#6b7280')
    ACC = colors.HexColor('#0d9488')

    buf = BytesIO(); ss = session_state

    sbN = ParagraphStyle('sbN', fontName='Helvetica-Bold',   fontSize=13, textColor=WHT, alignment=TA_CENTER, leading=18, spaceAfter=2)
    sbT = ParagraphStyle('sbT', fontName='Helvetica-Oblique',fontSize=10, textColor=LTE, alignment=TA_CENTER, leading=13, spaceAfter=6)
    sbS = ParagraphStyle('sbS', fontName='Helvetica-Bold',   fontSize=8,  textColor=LTE, leading=12, spaceBefore=10, spaceAfter=2)
    sbI = ParagraphStyle('sbI', fontName='Helvetica',        fontSize=9,  textColor=colors.HexColor('#99f6e4'), leading=13, spaceAfter=2)
    sbP = ParagraphStyle('sbP', fontName='Helvetica',        fontSize=9,  textColor=TEA, alignment=TA_CENTER, leading=12)
    mH  = ParagraphStyle('mH',  fontName='Helvetica-Bold',   fontSize=11, textColor=TEA, leading=16)
    mN  = ParagraphStyle('mN',  fontName='Helvetica',        fontSize=10, textColor=TXT, leading=14, spaceAfter=2)
    mB  = ParagraphStyle('mB',  fontName='Helvetica',        fontSize=10, textColor=TXT, leading=14)
    mBD = ParagraphStyle('mBD', fontName='Helvetica-Bold',   fontSize=10, textColor=TXT, leading=14)
    mMU = ParagraphStyle('mMU', fontName='Helvetica',        fontSize=9,  textColor=MUT, leading=13)
    mAC = ParagraphStyle('mAC', fontName='Helvetica-Bold',   fontSize=9,  textColor=ACC, leading=13)

    SW = SIDEBAR_W - 18

    def sb_pill(text):
        t = Table([[Paragraph(text, sbP)]], colWidths=[SW])
        t.setStyle(TableStyle([('BACKGROUND',(0,0),(-1,-1),LTE),('BOX',(0,0),(-1,-1),0.4,BDR),
                                ('TOPPADDING',(0,0),(-1,-1),2),('BOTTOMPADDING',(0,0),(-1,-1),2),
                                ('LEFTPADDING',(0,0),(-1,-1),3),('RIGHTPADDING',(0,0),(-1,-1),3)]))
        return t

    def sb_sec(title, sb):
        sb.append(HRFlowable(width=SW, thickness=0.4, color=BDR, spaceAfter=2))
        sb.append(Paragraph(title.upper(), sbS))

    sidebar = []
    iv = _img(profile_img_bytes, 80)
    if iv: sidebar += [iv, Spacer(1,6)]
    sidebar.append(Paragraph(_get(ss,'name') or 'Your Name', sbN))
    if _get(ss,'job_title'): sidebar.append(Paragraph(_get(ss,'job_title'), sbT))
    for k,lbl in [('email','Email'),('phone','Phone'),('location','Location'),
                  ('linkedin','LinkedIn'),('github','GitHub'),('portfolio','Portfolio')]:
        v = _get(ss,k)
        if v: sb_sec(lbl,sidebar); sidebar.append(Paragraph(v, sbI))
    for field,lbl in [('skills','Skills'),('Softskills','Soft Skills'),('languages','Languages'),('interests','Interests')]:
        v = _get(ss,field)
        if v:
            sb_sec(lbl, sidebar)
            for item in _skills_list(v):
                sidebar.append(sb_pill(item)); sidebar.append(Spacer(1,3))

    MW = MAIN_W - 12
    main = []

    def m_sec(title, content_flowables):
        # Vertical teal bar | section title + content
        title_cell = [Paragraph(title, mH), Spacer(1,3)] + content_flowables
        bar_tbl = Table([[Paragraph('', mH), title_cell]], colWidths=[5, MW-5])
        bar_tbl.setStyle(TableStyle([
            ('BACKGROUND',(0,0),(0,-1),TEA),
            ('VALIGN',(0,0),(-1,-1),'TOP'),
            ('LEFTPADDING',(0,0),(-1,-1),0),('RIGHTPADDING',(0,0),(-1,-1),0),
            ('TOPPADDING',(0,0),(-1,-1),0),('BOTTOMPADDING',(0,0),(-1,-1),0),
            ('LEFTPADDING',(1,0),(1,-1),8),
        ]))
        main.append(Spacer(1,10))
        main.append(bar_tbl)
        main.append(Spacer(1,4))

    sm_flowables = _bullets(_get(ss,'summary'), mN, mB, TEA) if _get(ss,'summary') else []
    if sm_flowables: m_sec("Professional Summary", sm_flowables)

    exps = [e for e in _entries(ss,'experience_entries') if e.get('company') or e.get('title')]
    if exps:
        exp_content = []
        for e in exps:
            exp_content.append(_row2(Paragraph(f"<b>{e.get('company','')}</b> — {e.get('title','')}", mBD),
                                     Paragraph(e.get('duration',''), mAC), MW-8))
            for f in _bullets(e.get('description',''), mN, mB, TEA): exp_content.append(f)
            exp_content.append(Spacer(1,6))
        m_sec("Work Experience", exp_content)

    edus = [e for e in _entries(ss,'education_entries') if e.get('institution') or e.get('degree')]
    if edus:
        edu_content = []
        for e in edus:
            edu_content.append(_row2(Paragraph(f"<b>{e.get('institution','')}</b> — {_deg(e)}", mBD),
                                     Paragraph(e.get('year',''), mAC), MW-8))
            if e.get('details'): edu_content.append(Paragraph(e['details'], mMU))
            edu_content.append(Spacer(1,4))
        m_sec("Education", edu_content)

    for field,lbl in [('skills','Skills'),('Softskills','Soft Skills'),('languages','Languages'),('interests','Interests')]:
        v = _get(ss,field)
        if v:
            m_sec(lbl, list(_pills(v, LTE, TEA, BDR, MW-8)))

    projs = [p for p in _entries(ss,'project_entries') if p.get('title')]
    proj_links = _entries(ss,'project_links')
    if projs:
        proj_content = []
        for i, p in enumerate(projs):
            lnk = proj_links[i] if i < len(proj_links) else ''
            t = _link(lnk, p.get('title',''), '#0f766e') if lnk else p.get('title','')
            proj_content.append(Paragraph(f"<b>{t}</b>  |  {p.get('tech','')}", mBD))
            for f in _bullets(p.get('description',''), mN, mB, TEA): proj_content.append(f)
            proj_content.append(Spacer(1,6))
        m_sec("Projects", proj_content)

    certs = [c for c in _entries(ss,'certificate_links') if c.get('name')]
    if certs:
        cert_content = []
        for c in certs:
            nm = _link(c.get('link',''), c.get('name',''), '#0f766e') if c.get('link') else c.get('name','')
            cert_content.append(_row2(Paragraph(nm, mBD), Paragraph(c.get('duration',''), mAC), MW-8))
            if c.get('description'): cert_content.append(Paragraph(c['description'], mMU))
            cert_content.append(Spacer(1,4))
        m_sec("Certifications", cert_content)

    _two_col(buf, sidebar, main, TEA, BDR); buf.seek(0); return buf


# ═════════════════════════════════════════════════════════════════════════════
# TEMPLATE 13 — Burgundy Classic
# Layout: single-col. Name ALL-CAPS centered, short decorative rule below name,
#         NO pill chips — skills as 2-col bullet table, burgundy dividers.
# ═════════════════════════════════════════════════════════════════════════════
def render_template_burgundy_classic(session_state, profile_img_bytes=None):
    BUR = colors.HexColor('#881337')
    LBR = colors.HexColor('#fff1f2')
    BDR = colors.HexColor('#fda4af')
    TXT = colors.HexColor('#1a0a0a')
    MUT = colors.HexColor('#78716c')

    buf = BytesIO(); ss = session_state; W = PAGE_W - 2*MARGIN
    doc = _new_doc(buf)
    NM = ParagraphStyle('NM', fontName='Helvetica-Bold',   fontSize=20, textColor=BUR, alignment=TA_CENTER, leading=26, letterSpacing=2)
    JT = ParagraphStyle('JT', fontName='Helvetica-Oblique',fontSize=12, textColor=TXT, alignment=TA_CENTER, leading=16, spaceAfter=3)
    CO = ParagraphStyle('CO', fontName='Helvetica',        fontSize=9,  textColor=MUT, alignment=TA_CENTER, leading=13)
    SH = ParagraphStyle('SH', fontName='Helvetica-Bold',   fontSize=11, textColor=BUR, leading=16, spaceBefore=10, spaceAfter=3)
    PN = ParagraphStyle('PN', fontName='Helvetica',        fontSize=10, textColor=TXT, leading=14, spaceAfter=2)
    PB = ParagraphStyle('PB', fontName='Helvetica',        fontSize=10, textColor=TXT, leading=14)
    BD = ParagraphStyle('BD', fontName='Helvetica-Bold',   fontSize=10, textColor=BUR, leading=14)
    MU = ParagraphStyle('MU', fontName='Helvetica',        fontSize=9,  textColor=MUT, leading=13)
    DT = ParagraphStyle('DT', fontName='Helvetica-Bold',   fontSize=9,  textColor=BUR, leading=13)
    SK = ParagraphStyle('SK', fontName='Helvetica',        fontSize=10, textColor=TXT, leading=14)

    story = []
    iv = _img(profile_img_bytes, 68)
    if iv: story += [iv, Spacer(1,4)]
    # Name in uppercase
    story.append(Paragraph((_get(ss,'name') or 'YOUR NAME').upper(), NM))
    # Short decorative rule centered
    story.append(HRFlowable(width=W*0.35, thickness=2, color=BUR, spaceAfter=2, spaceBefore=2,
                             hAlign='CENTER'))
    if _get(ss,'job_title'): story.append(Paragraph(_get(ss,'job_title'), JT))
    cp = [_get(ss,k) for k in ['email','phone','location','linkedin','github','portfolio'] if _get(ss,k)]
    if cp: story.append(Paragraph(' | '.join(cp), CO))
    story.append(HRFlowable(width=W, thickness=1.5, color=BUR, spaceBefore=6, spaceAfter=8))

    def sec(title):
        story.append(Paragraph(title, SH))
        story.append(HRFlowable(width=W*0.25, thickness=1, color=BDR, spaceAfter=4))

    def skill_2col(raw):
        items = _skills_list(raw)
        if not items: return
        rows, row = [], []
        for item in items:
            row.append(Paragraph(f'• {item}', SK))
            if len(row) == 2: rows.append(row); row = []
        if row:
            while len(row) < 2: row.append(Paragraph('', SK))
            rows.append(row)
        t = Table(rows, colWidths=[W/2, W/2])
        t.setStyle(TableStyle([('LEFTPADDING',(0,0),(-1,-1),0),('RIGHTPADDING',(0,0),(-1,-1),0),
                                ('TOPPADDING',(0,0),(-1,-1),1),('BOTTOMPADDING',(0,0),(-1,-1),1)]))
        story.append(t); story.append(Spacer(1,4))

    sm = _get(ss,'summary')
    if sm:
        sec("Professional Summary")
        for f in _bullets(sm, PN, PB, BUR): story.append(f)

    exps = [e for e in _entries(ss,'experience_entries') if e.get('company') or e.get('title')]
    if exps:
        sec("Work Experience")
        for e in exps:
            story.append(_row2(Paragraph(f"<b>{e.get('company','')}</b> — {e.get('title','')}", BD),
                               Paragraph(e.get('duration',''), DT), W))
            for f in _bullets(e.get('description',''), PN, PB, BUR): story.append(f)
            story.append(Spacer(1,6))

    edus = [e for e in _entries(ss,'education_entries') if e.get('institution') or e.get('degree')]
    if edus:
        sec("Education")
        for e in edus:
            story.append(_row2(Paragraph(f"<b>{e.get('institution','')}</b> — {_deg(e)}", BD),
                               Paragraph(e.get('year',''), DT), W))
            if e.get('details'): story.append(Paragraph(e['details'], MU))
            story.append(Spacer(1,4))

    if _get(ss,'skills'):    sec("Technical Skills"); skill_2col(_get(ss,'skills'))
    if _get(ss,'Softskills'):sec("Soft Skills");      skill_2col(_get(ss,'Softskills'))
    if _get(ss,'languages'): sec("Languages");        skill_2col(_get(ss,'languages'))
    if _get(ss,'interests'): sec("Interests");        story.append(Paragraph(_get(ss,'interests'), SK)); story.append(Spacer(1,4))

    projs = [p for p in _entries(ss,'project_entries') if p.get('title')]
    proj_links = _entries(ss,'project_links')
    if projs:
        sec("Projects")
        for i, p in enumerate(projs):
            lnk = proj_links[i] if i < len(proj_links) else ''
            t = _link(lnk, p.get('title',''), '#881337') if lnk else p.get('title','')
            story.append(Paragraph(f"<b>{t}</b>  |  {p.get('tech','')}", BD))
            for f in _bullets(p.get('description',''), PN, PB, BUR): story.append(f)
            story.append(Spacer(1,6))

    certs = [c for c in _entries(ss,'certificate_links') if c.get('name')]
    if certs:
        sec("Certifications")
        for c in certs:
            nm = _link(c.get('link',''), c.get('name',''), '#881337') if c.get('link') else c.get('name','')
            story.append(_row2(Paragraph(nm, BD), Paragraph(c.get('duration',''), DT), W))
            if c.get('description'): story.append(Paragraph(c['description'], MU))
            story.append(Spacer(1,4))

    doc.build(story); buf.seek(0); return buf


# ═════════════════════════════════════════════════════════════════════════════
# TEMPLATE 14 — Indigo Tech
# Layout: TWO-COL indigo sidebar. Main: code-style section labels in
#         monospaced-look (Helvetica-Bold), tech tags shown as inline #hashtag
#         style text, skills chips with square (not rounded) look.
# ═════════════════════════════════════════════════════════════════════════════
def render_template_indigo_tech(session_state, profile_img_bytes=None):
    IND = colors.HexColor('#4338ca')
    LIN = colors.HexColor('#e0e7ff')
    BDR = colors.HexColor('#a5b4fc')
    WHT = colors.white
    TXT = colors.HexColor('#1e1b4b')
    MUT = colors.HexColor('#6b7280')
    ACC = colors.HexColor('#4f46e5')

    buf = BytesIO(); ss = session_state

    sbN = ParagraphStyle('sbN', fontName='Helvetica-Bold',   fontSize=13, textColor=WHT, alignment=TA_CENTER, leading=18, spaceAfter=2)
    sbT = ParagraphStyle('sbT', fontName='Helvetica-Oblique',fontSize=10, textColor=LIN, alignment=TA_CENTER, leading=13, spaceAfter=6)
    sbS = ParagraphStyle('sbS', fontName='Helvetica-Bold',   fontSize=8,  textColor=LIN, leading=12, spaceBefore=10, spaceAfter=2)
    sbI = ParagraphStyle('sbI', fontName='Helvetica',        fontSize=9,  textColor=colors.HexColor('#c7d2fe'), leading=13, spaceAfter=2)
    sbP = ParagraphStyle('sbP', fontName='Helvetica-Bold',   fontSize=9,  textColor=IND, alignment=TA_CENTER, leading=12)
    # code-look: Helvetica-Bold, slightly smaller
    mH  = ParagraphStyle('mH',  fontName='Helvetica-Bold',   fontSize=10, textColor=IND, leading=14, spaceBefore=12, spaceAfter=2)
    mN  = ParagraphStyle('mN',  fontName='Helvetica',        fontSize=10, textColor=TXT, leading=14, spaceAfter=2)
    mB  = ParagraphStyle('mB',  fontName='Helvetica',        fontSize=10, textColor=TXT, leading=14)
    mBD = ParagraphStyle('mBD', fontName='Helvetica-Bold',   fontSize=10, textColor=TXT, leading=14)
    mMU = ParagraphStyle('mMU', fontName='Helvetica',        fontSize=9,  textColor=MUT, leading=13)
    mAC = ParagraphStyle('mAC', fontName='Helvetica-Bold',   fontSize=9,  textColor=ACC, leading=13)
    mTG = ParagraphStyle('mTG', fontName='Helvetica',        fontSize=9,  textColor=IND, leading=13)

    SW = SIDEBAR_W - 18

    def sb_pill(text):
        # Square chips: no BOX roundedness (reportlab has none), just background + border
        t = Table([[Paragraph(f'#{text}', sbP)]], colWidths=[SW])
        t.setStyle(TableStyle([('BACKGROUND',(0,0),(-1,-1),LIN),('BOX',(0,0),(-1,-1),0.6,BDR),
                                ('TOPPADDING',(0,0),(-1,-1),2),('BOTTOMPADDING',(0,0),(-1,-1),2),
                                ('LEFTPADDING',(0,0),(-1,-1),4),('RIGHTPADDING',(0,0),(-1,-1),4)]))
        return t

    def sb_sec(title, sb):
        sb.append(HRFlowable(width=SW, thickness=0.4, color=BDR, spaceAfter=2))
        sb.append(Paragraph(f'// {title}', sbS))

    sidebar = []
    iv = _img(profile_img_bytes, 80)
    if iv: sidebar += [iv, Spacer(1,6)]
    sidebar.append(Paragraph(_get(ss,'name') or 'Your Name', sbN))
    if _get(ss,'job_title'): sidebar.append(Paragraph(_get(ss,'job_title'), sbT))
    for k,lbl in [('email','Email'),('phone','Phone'),('location','Location'),
                  ('linkedin','LinkedIn'),('github','GitHub'),('portfolio','Portfolio')]:
        v = _get(ss,k)
        if v: sb_sec(lbl,sidebar); sidebar.append(Paragraph(v, sbI))
    for field,lbl in [('skills','Skills'),('Softskills','Soft Skills'),('languages','Languages'),('interests','Interests')]:
        v = _get(ss,field)
        if v:
            sb_sec(lbl, sidebar)
            for item in _skills_list(v):
                sidebar.append(sb_pill(item)); sidebar.append(Spacer(1,3))

    MW = MAIN_W - 12
    main = []

    def m_sec(title):
        main.append(Paragraph(f'> {title}', mH))
        main.append(HRFlowable(width=MW, thickness=0.5, color=BDR, spaceAfter=4))

    sm = _get(ss,'summary')
    if sm:
        m_sec("Profile")
        for f in _bullets(sm, mN, mB, IND): main.append(f)

    exps = [e for e in _entries(ss,'experience_entries') if e.get('company') or e.get('title')]
    if exps:
        m_sec("Experience")
        for e in exps:
            main.append(_row2(Paragraph(f"<b>{e.get('company','')}</b> — {e.get('title','')}", mBD),
                              Paragraph(e.get('duration',''), mAC), MW))
            for f in _bullets(e.get('description',''), mN, mB, IND): main.append(f)
            main.append(Spacer(1,6))

    edus = [e for e in _entries(ss,'education_entries') if e.get('institution') or e.get('degree')]
    if edus:
        m_sec("Education")
        for e in edus:
            main.append(_row2(Paragraph(f"<b>{e.get('institution','')}</b> — {_deg(e)}", mBD),
                              Paragraph(e.get('year',''), mAC), MW))
            if e.get('details'): main.append(Paragraph(e['details'], mMU))
            main.append(Spacer(1,4))

    projs = [p for p in _entries(ss,'project_entries') if p.get('title')]
    proj_links = _entries(ss,'project_links')
    if projs:
        m_sec("Projects")
        for i, p in enumerate(projs):
            lnk = proj_links[i] if i < len(proj_links) else ''
            t = _link(lnk, p.get('title',''), '#4338ca') if lnk else p.get('title','')
            main.append(Paragraph(f"<b>{t}</b>", mBD))
            if p.get('tech'):
                # hashtag style tech tags
                tags = '  '.join([f'#{x}' for x in _skills_list(p['tech'])])
                main.append(Paragraph(tags, mTG))
            for f in _bullets(p.get('description',''), mN, mB, IND): main.append(f)
            main.append(Spacer(1,6))

    certs = [c for c in _entries(ss,'certificate_links') if c.get('name')]
    if certs:
        m_sec("Certifications")
        for c in certs:
            nm = _link(c.get('link',''), c.get('name',''), '#4338ca') if c.get('link') else c.get('name','')
            main.append(_row2(Paragraph(nm, mBD), Paragraph(c.get('duration',''), mAC), MW))
            if c.get('description'): main.append(Paragraph(c['description'], mMU))
            main.append(Spacer(1,4))

    _two_col(buf, sidebar, main, IND, BDR); buf.seek(0); return buf


# ═════════════════════════════════════════════════════════════════════════════
# TEMPLATE 15 — Forest Green
# Layout: single-col. Section headers are FULL-WIDTH banner rows
#         (Table cell with green bg + white text spanning full width).
# ═════════════════════════════════════════════════════════════════════════════
def render_template_forest_green(session_state, profile_img_bytes=None):
    FOR = colors.HexColor('#14532d')
    LFG = colors.HexColor('#f0fdf4')
    BDR = colors.HexColor('#86efac')
    ACC = colors.HexColor('#15803d')
    WHT = colors.white
    TXT = colors.HexColor('#1a2e1a')
    MUT = colors.HexColor('#6b7280')

    buf = BytesIO(); ss = session_state; W = PAGE_W - 2*MARGIN
    doc = _new_doc(buf)
    NM = ParagraphStyle('NM', fontName='Helvetica-Bold',   fontSize=22, textColor=FOR, leading=28)
    JT = ParagraphStyle('JT', fontName='Helvetica-Oblique',fontSize=12, textColor=ACC, leading=16, spaceAfter=3)
    CO = ParagraphStyle('CO', fontName='Helvetica',        fontSize=9,  textColor=MUT, leading=13)
    # Banner section header — white on green
    SH = ParagraphStyle('SH', fontName='Helvetica-Bold',   fontSize=10, textColor=WHT, leading=14)
    PN = ParagraphStyle('PN', fontName='Helvetica',        fontSize=10, textColor=TXT, leading=14, spaceAfter=2)
    PB = ParagraphStyle('PB', fontName='Helvetica',        fontSize=10, textColor=TXT, leading=14)
    BD = ParagraphStyle('BD', fontName='Helvetica-Bold',   fontSize=10, textColor=FOR, leading=14)
    MU = ParagraphStyle('MU', fontName='Helvetica',        fontSize=9,  textColor=MUT, leading=13)
    DT = ParagraphStyle('DT', fontName='Helvetica-Bold',   fontSize=9,  textColor=ACC, leading=13)

    story = []
    # Header: name left, photo right
    name_block = [Paragraph(_get(ss,'name') or 'Your Name', NM)]
    if _get(ss,'job_title'): name_block.append(Paragraph(_get(ss,'job_title'), JT))
    cp = [_get(ss,k) for k in ['email','phone','location','linkedin','github','portfolio'] if _get(ss,k)]
    if cp: name_block.append(Paragraph('  |  '.join(cp), CO))
    iv = _img(profile_img_bytes, 72)
    if iv:
        hdr = Table([[name_block, iv]], colWidths=[W-80, 80])
        hdr.setStyle(TableStyle([('VALIGN',(0,0),(-1,-1),'TOP'),
                                  ('LEFTPADDING',(0,0),(-1,-1),0),('RIGHTPADDING',(0,0),(-1,-1),0)]))
        story.append(hdr)
    else:
        for fl in name_block: story.append(fl)
    story.append(HRFlowable(width=W, thickness=2.5, color=FOR, spaceBefore=6, spaceAfter=8))

    def banner_sec(title):
        bx = Table([[Paragraph(f'  {title}  ', SH)]], colWidths=[W])
        bx.setStyle(TableStyle([('BACKGROUND',(0,0),(-1,-1),FOR),
                                  ('TOPPADDING',(0,0),(-1,-1),4),('BOTTOMPADDING',(0,0),(-1,-1),4),
                                  ('LEFTPADDING',(0,0),(-1,-1),6),('RIGHTPADDING',(0,0),(-1,-1),6)]))
        story.append(bx)
        story.append(Spacer(1,5))

    sm = _get(ss,'summary')
    if sm:
        banner_sec("About Me")
        for f in _bullets(sm, PN, PB, ACC): story.append(f)

    exps = [e for e in _entries(ss,'experience_entries') if e.get('company') or e.get('title')]
    if exps:
        banner_sec("Work Experience")
        for e in exps:
            story.append(_row2(Paragraph(f"<b>{e.get('company','')}</b> — {e.get('title','')}", BD),
                               Paragraph(e.get('duration',''), DT), W))
            for f in _bullets(e.get('description',''), PN, PB, ACC): story.append(f)
            story.append(Spacer(1,6))

    edus = [e for e in _entries(ss,'education_entries') if e.get('institution') or e.get('degree')]
    if edus:
        banner_sec("Education")
        for e in edus:
            story.append(_row2(Paragraph(f"<b>{e.get('institution','')}</b> — {_deg(e)}", BD),
                               Paragraph(e.get('year',''), DT), W))
            if e.get('details'): story.append(Paragraph(e['details'], MU))
            story.append(Spacer(1,4))

    for field,lbl in [('skills','Skills'),('Softskills','Soft Skills'),('languages','Languages'),('interests','Interests')]:
        v = _get(ss,field)
        if v:
            banner_sec(lbl)
            story.extend(_pills(v, LFG, FOR, BDR, W))

    projs = [p for p in _entries(ss,'project_entries') if p.get('title')]
    proj_links = _entries(ss,'project_links')
    if projs:
        banner_sec("Projects")
        for i, p in enumerate(projs):
            lnk = proj_links[i] if i < len(proj_links) else ''
            t = _link(lnk, p.get('title',''), '#14532d') if lnk else p.get('title','')
            story.append(Paragraph(f"<b>{t}</b>  |  {p.get('tech','')}", BD))
            for f in _bullets(p.get('description',''), PN, PB, ACC): story.append(f)
            story.append(Spacer(1,6))

    certs = [c for c in _entries(ss,'certificate_links') if c.get('name')]
    if certs:
        banner_sec("Certifications")
        for c in certs:
            nm = _link(c.get('link',''), c.get('name',''), '#14532d') if c.get('link') else c.get('name','')
            story.append(_row2(Paragraph(nm, BD), Paragraph(c.get('duration',''), DT), W))
            if c.get('description'): story.append(Paragraph(c['description'], MU))
            story.append(Spacer(1,4))

    doc.build(story); buf.seek(0); return buf


# ═════════════════════════════════════════════════════════════════════════════
# TEMPLATE 16 — Pure White
# Layout: ultra-minimal single-col. Huge 28pt name, everything in very light
#         gray, only hairline rules, lots of breathing room, no decorations.
# ═════════════════════════════════════════════════════════════════════════════
def render_template_pure_white(session_state, profile_img_bytes=None):
    BLK = colors.HexColor('#111111')
    DGY = colors.HexColor('#374151')
    LGY = colors.HexColor('#9ca3af')
    XLG = colors.HexColor('#e5e7eb')
    WHT = colors.HexColor('#f9fafb')

    buf = BytesIO(); ss = session_state; W = PAGE_W - 2*MARGIN
    doc = _new_doc(buf)
    NM = ParagraphStyle('NM', fontName='Helvetica-Bold',   fontSize=28, textColor=BLK, leading=34)
    JT = ParagraphStyle('JT', fontName='Helvetica',        fontSize=12, textColor=DGY, leading=16, spaceAfter=4)
    CO = ParagraphStyle('CO', fontName='Helvetica',        fontSize=9,  textColor=LGY, leading=13)
    SH = ParagraphStyle('SH', fontName='Helvetica-Bold',   fontSize=10, textColor=DGY, leading=14, spaceBefore=16, spaceAfter=4, letterSpacing=1)
    PN = ParagraphStyle('PN', fontName='Helvetica',        fontSize=10, textColor=DGY, leading=15, spaceAfter=2)
    PB = ParagraphStyle('PB', fontName='Helvetica',        fontSize=10, textColor=DGY, leading=15)
    BD = ParagraphStyle('BD', fontName='Helvetica-Bold',   fontSize=10, textColor=BLK, leading=14)
    MU = ParagraphStyle('MU', fontName='Helvetica',        fontSize=9,  textColor=LGY, leading=13)
    DT = ParagraphStyle('DT', fontName='Helvetica',        fontSize=9,  textColor=LGY, leading=13)
    SK = ParagraphStyle('SK', fontName='Helvetica',        fontSize=10, textColor=DGY, leading=14)

    story = []
    iv = _img(profile_img_bytes, 64)
    if iv:
        hdr = Table([[Paragraph(_get(ss,'name') or 'Your Name', NM), iv]], colWidths=[W-72,72])
        hdr.setStyle(TableStyle([('VALIGN',(0,0),(-1,-1),'BOTTOM'),
                                  ('LEFTPADDING',(0,0),(-1,-1),0),('RIGHTPADDING',(0,0),(-1,-1),0)]))
        story.append(hdr)
    else:
        story.append(Paragraph(_get(ss,'name') or 'Your Name', NM))
    if _get(ss,'job_title'): story.append(Paragraph(_get(ss,'job_title'), JT))
    cp = [_get(ss,k) for k in ['email','phone','location','linkedin','github','portfolio'] if _get(ss,k)]
    if cp: story.append(Paragraph('  ·  '.join(cp), CO))
    story.append(HRFlowable(width=W, thickness=0.5, color=XLG, spaceBefore=10, spaceAfter=10))

    def sec(title):
        story.append(Paragraph(title.upper(), SH))
        story.append(HRFlowable(width=W, thickness=0.3, color=XLG, spaceAfter=5))

    sm = _get(ss,'summary')
    if sm:
        sec("Summary")
        for f in _bullets(sm, PN, PB, DGY): story.append(f)

    exps = [e for e in _entries(ss,'experience_entries') if e.get('company') or e.get('title')]
    if exps:
        sec("Experience")
        for e in exps:
            story.append(_row2(Paragraph(f"<b>{e.get('company','')}</b>  {e.get('title','')}", BD),
                               Paragraph(e.get('duration',''), DT), W))
            for f in _bullets(e.get('description',''), PN, PB, DGY): story.append(f)
            story.append(Spacer(1,8))

    edus = [e for e in _entries(ss,'education_entries') if e.get('institution') or e.get('degree')]
    if edus:
        sec("Education")
        for e in edus:
            story.append(_row2(Paragraph(f"<b>{e.get('institution','')}</b>  {_deg(e)}", BD),
                               Paragraph(e.get('year',''), DT), W))
            if e.get('details'): story.append(Paragraph(e['details'], MU))
            story.append(Spacer(1,6))

    for field,lbl in [('skills','Skills'),('Softskills','Soft Skills'),('languages','Languages'),('interests','Interests')]:
        v = _get(ss,field)
        if v:
            sec(lbl)
            story.append(Paragraph(v, SK)); story.append(Spacer(1,4))

    projs = [p for p in _entries(ss,'project_entries') if p.get('title')]
    proj_links = _entries(ss,'project_links')
    if projs:
        sec("Projects")
        for i, p in enumerate(projs):
            lnk = proj_links[i] if i < len(proj_links) else ''
            t = _link(lnk, p.get('title',''), '#374151') if lnk else p.get('title','')
            story.append(Paragraph(f"<b>{t}</b>  {p.get('tech','')}", BD))
            for f in _bullets(p.get('description',''), PN, PB, DGY): story.append(f)
            story.append(Spacer(1,8))

    certs = [c for c in _entries(ss,'certificate_links') if c.get('name')]
    if certs:
        sec("Certifications")
        for c in certs:
            nm = _link(c.get('link',''), c.get('name',''), '#374151') if c.get('link') else c.get('name','')
            story.append(_row2(Paragraph(nm, BD), Paragraph(c.get('duration',''), DT), W))
            if c.get('description'): story.append(Paragraph(c['description'], MU))
            story.append(Spacer(1,4))

    doc.build(story); buf.seek(0); return buf


# ═════════════════════════════════════════════════════════════════════════════
# TEMPLATE 17 — Midnight Black
# Layout: single-col. Full-width DARK header band (black bg, gold name),
#         rest of page on white with gold accent dividers. Left-aligned.
# ═════════════════════════════════════════════════════════════════════════════
def render_template_midnight_black(session_state, profile_img_bytes=None):
    BLK = colors.HexColor('#111827')
    GLD = colors.HexColor('#f59e0b')
    LGD = colors.HexColor('#fbbf24')
    TXT = colors.HexColor('#e5e7eb')
    DGY = colors.HexColor('#374151')
    MUT = colors.HexColor('#9ca3af')
    WHT = colors.white

    buf = BytesIO(); ss = session_state; W = PAGE_W - 2*MARGIN
    doc = _new_doc(buf)
    hN = ParagraphStyle('hN', fontName='Helvetica-Bold',   fontSize=24, textColor=GLD, leading=30)
    hT = ParagraphStyle('hT', fontName='Helvetica-Oblique',fontSize=12, textColor=LGD, leading=16, spaceAfter=3)
    hC = ParagraphStyle('hC', fontName='Helvetica',        fontSize=9,  textColor=MUT, leading=13)
    SH = ParagraphStyle('SH', fontName='Helvetica-Bold',   fontSize=11, textColor=GLD, leading=15, spaceBefore=12, spaceAfter=3)
    PN = ParagraphStyle('PN', fontName='Helvetica',        fontSize=10, textColor=DGY, leading=14, spaceAfter=2)
    PB = ParagraphStyle('PB', fontName='Helvetica',        fontSize=10, textColor=DGY, leading=14)
    BD = ParagraphStyle('BD', fontName='Helvetica-Bold',   fontSize=10, textColor=BLK, leading=14)
    MU = ParagraphStyle('MU', fontName='Helvetica',        fontSize=9,  textColor=MUT, leading=13)
    DT = ParagraphStyle('DT', fontName='Helvetica-Bold',   fontSize=9,  textColor=GLD, leading=13)
    PL = ParagraphStyle('PL', fontName='Helvetica',        fontSize=9,  textColor=BLK, alignment=TA_CENTER, leading=12)

    story = []
    # Dark header band
    hdr_items = [Paragraph(_get(ss,'name') or 'Your Name', hN)]
    if _get(ss,'job_title'): hdr_items.append(Paragraph(_get(ss,'job_title'), hT))
    cp = [_get(ss,k) for k in ['email','phone','location','linkedin','github','portfolio'] if _get(ss,k)]
    if cp: hdr_items.append(Paragraph('  |  '.join(cp), hC))
    iv = _img(profile_img_bytes, 72)
    if iv:
        inner = Table([[hdr_items, iv]], colWidths=[W-80, 80])
        inner.setStyle(TableStyle([('VALIGN',(0,0),(-1,-1),'MIDDLE'),
                                    ('LEFTPADDING',(0,0),(-1,-1),0),('RIGHTPADDING',(0,0),(-1,-1),0)]))
        hdr_items = [inner]
    band = Table([[hdr_items]], colWidths=[W])
    band.setStyle(TableStyle([('BACKGROUND',(0,0),(-1,-1),BLK),
                               ('TOPPADDING',(0,0),(-1,-1),14),('BOTTOMPADDING',(0,0),(-1,-1),14),
                               ('LEFTPADDING',(0,0),(-1,-1),14),('RIGHTPADDING',(0,0),(-1,-1),14)]))
    story.append(band)
    story.append(Spacer(1,10))

    def sec(title):
        story.append(Paragraph(title, SH))
        story.append(HRFlowable(width=W, thickness=0.8, color=GLD, spaceAfter=4))

    sm = _get(ss,'summary')
    if sm:
        sec("Professional Summary")
        for f in _bullets(sm, PN, PB, GLD): story.append(f)

    exps = [e for e in _entries(ss,'experience_entries') if e.get('company') or e.get('title')]
    if exps:
        sec("Work Experience")
        for e in exps:
            story.append(_row2(Paragraph(f"<b>{e.get('company','')}</b> — {e.get('title','')}", BD),
                               Paragraph(e.get('duration',''), DT), W))
            for f in _bullets(e.get('description',''), PN, PB, GLD): story.append(f)
            story.append(Spacer(1,6))

    edus = [e for e in _entries(ss,'education_entries') if e.get('institution') or e.get('degree')]
    if edus:
        sec("Education")
        for e in edus:
            story.append(_row2(Paragraph(f"<b>{e.get('institution','')}</b> — {_deg(e)}", BD),
                               Paragraph(e.get('year',''), DT), W))
            if e.get('details'): story.append(Paragraph(e['details'], MU))
            story.append(Spacer(1,4))

    for field,lbl in [('skills','Skills'),('Softskills','Soft Skills'),('languages','Languages'),('interests','Interests')]:
        v = _get(ss,field)
        if v:
            sec(lbl)
            story.extend(_pills(v, colors.HexColor('#1f2937'), GLD, colors.HexColor('#374151'), W))

    projs = [p for p in _entries(ss,'project_entries') if p.get('title')]
    proj_links = _entries(ss,'project_links')
    if projs:
        sec("Projects")
        for i, p in enumerate(projs):
            lnk = proj_links[i] if i < len(proj_links) else ''
            t = _link(lnk, p.get('title',''), '#f59e0b') if lnk else p.get('title','')
            story.append(Paragraph(f"<b>{t}</b>  |  {p.get('tech','')}", BD))
            for f in _bullets(p.get('description',''), PN, PB, GLD): story.append(f)
            story.append(Spacer(1,6))

    certs = [c for c in _entries(ss,'certificate_links') if c.get('name')]
    if certs:
        sec("Certifications")
        for c in certs:
            nm = _link(c.get('link',''), c.get('name',''), '#f59e0b') if c.get('link') else c.get('name','')
            story.append(_row2(Paragraph(nm, BD), Paragraph(c.get('duration',''), DT), W))
            if c.get('description'): story.append(Paragraph(c['description'], MU))
            story.append(Spacer(1,4))

    doc.build(story); buf.seek(0); return buf


# ═════════════════════════════════════════════════════════════════════════════
# TEMPLATE 18 — Soft Lavender
# Layout: single-col. Lavender background header BLOCK (not full-width band —
#         a padded table with lavender bg). Section labels in ITALIC lavender.
# ═════════════════════════════════════════════════════════════════════════════
def render_template_soft_lavender(session_state, profile_img_bytes=None):
    LAV = colors.HexColor('#6366f1')
    LLV = colors.HexColor('#f5f3ff')
    BDR = colors.HexColor('#ddd6fe')
    DLV = colors.HexColor('#7c3aed')
    TXT = colors.HexColor('#374151')
    MUT = colors.HexColor('#9ca3af')

    buf = BytesIO(); ss = session_state; W = PAGE_W - 2*MARGIN
    doc = _new_doc(buf)
    hN = ParagraphStyle('hN', fontName='Helvetica-Bold',   fontSize=22, textColor=DLV, leading=28)
    hT = ParagraphStyle('hT', fontName='Helvetica-Oblique',fontSize=12, textColor=LAV, leading=16, spaceAfter=2)
    hC = ParagraphStyle('hC', fontName='Helvetica',        fontSize=9,  textColor=MUT, leading=13)
    SH = ParagraphStyle('SH', fontName='Helvetica-Oblique',fontSize=12, textColor=LAV, leading=16, spaceBefore=12, spaceAfter=2)
    PN = ParagraphStyle('PN', fontName='Helvetica',        fontSize=10, textColor=TXT, leading=14, spaceAfter=2)
    PB = ParagraphStyle('PB', fontName='Helvetica',        fontSize=10, textColor=TXT, leading=14)
    BD = ParagraphStyle('BD', fontName='Helvetica-Bold',   fontSize=10, textColor=DLV, leading=14)
    MU = ParagraphStyle('MU', fontName='Helvetica',        fontSize=9,  textColor=MUT, leading=13)
    DT = ParagraphStyle('DT', fontName='Helvetica-Bold',   fontSize=9,  textColor=LAV, leading=13)

    story = []
    # Lavender background header block (padded, not full-width band — floated center)
    hdr_items = [Paragraph(_get(ss,'name') or 'Your Name', hN)]
    if _get(ss,'job_title'): hdr_items.append(Paragraph(_get(ss,'job_title'), hT))
    cp = [_get(ss,k) for k in ['email','phone','location','linkedin','github','portfolio'] if _get(ss,k)]
    if cp: hdr_items.append(Paragraph('  ·  '.join(cp), hC))
    iv = _img(profile_img_bytes, 70)
    if iv:
        row = Table([[hdr_items, iv]], colWidths=[W*0.72, W*0.28])
        row.setStyle(TableStyle([('VALIGN',(0,0),(-1,-1),'MIDDLE'),
                                  ('LEFTPADDING',(0,0),(-1,-1),0),('RIGHTPADDING',(0,0),(-1,-1),0)]))
        hdr_items = [row]
    block = Table([[hdr_items]], colWidths=[W])
    block.setStyle(TableStyle([('BACKGROUND',(0,0),(-1,-1),LLV),
                                ('BOX',(0,0),(-1,-1),0.6,BDR),
                                ('TOPPADDING',(0,0),(-1,-1),12),('BOTTOMPADDING',(0,0),(-1,-1),12),
                                ('LEFTPADDING',(0,0),(-1,-1),14),('RIGHTPADDING',(0,0),(-1,-1),14)]))
    story.append(block)
    story.append(Spacer(1,8))

    def sec(title):
        story.append(Paragraph(title, SH))
        story.append(HRFlowable(width=W, thickness=0.5, color=BDR, spaceAfter=4))

    sm = _get(ss,'summary')
    if sm:
        sec("Summary")
        for f in _bullets(sm, PN, PB, LAV): story.append(f)

    exps = [e for e in _entries(ss,'experience_entries') if e.get('company') or e.get('title')]
    if exps:
        sec("Experience")
        for e in exps:
            story.append(_row2(Paragraph(f"<b>{e.get('company','')}</b> — {e.get('title','')}", BD),
                               Paragraph(e.get('duration',''), DT), W))
            for f in _bullets(e.get('description',''), PN, PB, LAV): story.append(f)
            story.append(Spacer(1,6))

    edus = [e for e in _entries(ss,'education_entries') if e.get('institution') or e.get('degree')]
    if edus:
        sec("Education")
        for e in edus:
            story.append(_row2(Paragraph(f"<b>{e.get('institution','')}</b> — {_deg(e)}", BD),
                               Paragraph(e.get('year',''), DT), W))
            if e.get('details'): story.append(Paragraph(e['details'], MU))
            story.append(Spacer(1,4))

    for field,lbl in [('skills','Skills'),('Softskills','Soft Skills'),('languages','Languages'),('interests','Interests')]:
        v = _get(ss,field)
        if v:
            sec(lbl)
            story.extend(_pills(v, LLV, DLV, BDR, W))

    projs = [p for p in _entries(ss,'project_entries') if p.get('title')]
    proj_links = _entries(ss,'project_links')
    if projs:
        sec("Projects")
        for i, p in enumerate(projs):
            lnk = proj_links[i] if i < len(proj_links) else ''
            t = _link(lnk, p.get('title',''), '#6366f1') if lnk else p.get('title','')
            story.append(Paragraph(f"<b>{t}</b>  |  {p.get('tech','')}", BD))
            for f in _bullets(p.get('description',''), PN, PB, LAV): story.append(f)
            story.append(Spacer(1,6))

    certs = [c for c in _entries(ss,'certificate_links') if c.get('name')]
    if certs:
        sec("Certifications")
        for c in certs:
            nm = _link(c.get('link',''), c.get('name',''), '#6366f1') if c.get('link') else c.get('name','')
            story.append(_row2(Paragraph(nm, BD), Paragraph(c.get('duration',''), DT), W))
            if c.get('description'): story.append(Paragraph(c['description'], MU))
            story.append(Spacer(1,4))

    doc.build(story); buf.seek(0); return buf


# ═════════════════════════════════════════════════════════════════════════════
# TEMPLATE 19 — Warm Sand
# Layout: single-col, warm amber palette. Section labels rendered as LARGE
#         LIGHT background text in a separate row above content (gives an
#         airy magazine feel). Justified body text.
# ═════════════════════════════════════════════════════════════════════════════
def render_template_warm_sand(session_state, profile_img_bytes=None):
    SND = colors.HexColor('#92400e')
    LSN = colors.HexColor('#fef3c7')
    BDR = colors.HexColor('#fcd34d')
    ACC = colors.HexColor('#b45309')
    TXT = colors.HexColor('#44403c')
    MUT = colors.HexColor('#a8a29e')

    buf = BytesIO(); ss = session_state; W = PAGE_W - 2*MARGIN
    doc = _new_doc(buf)
    NM = ParagraphStyle('NM', fontName='Helvetica-Bold',   fontSize=22, textColor=SND, leading=28)
    JT = ParagraphStyle('JT', fontName='Helvetica-Oblique',fontSize=12, textColor=ACC, leading=16, spaceAfter=3)
    CO = ParagraphStyle('CO', fontName='Helvetica',        fontSize=9,  textColor=MUT, leading=13)
    # Section label: large, light-colored, appears as background-style watermark row
    SL = ParagraphStyle('SL', fontName='Helvetica-Bold',   fontSize=18, textColor=BDR, leading=22)
    SH = ParagraphStyle('SH', fontName='Helvetica-Bold',   fontSize=11, textColor=SND, leading=14, spaceAfter=3)
    PN = ParagraphStyle('PN', fontName='Helvetica',        fontSize=10, textColor=TXT, leading=15, spaceAfter=2, alignment=TA_JUSTIFY)
    PB = ParagraphStyle('PB', fontName='Helvetica',        fontSize=10, textColor=TXT, leading=15)
    BD = ParagraphStyle('BD', fontName='Helvetica-Bold',   fontSize=10, textColor=SND, leading=14)
    MU = ParagraphStyle('MU', fontName='Helvetica',        fontSize=9,  textColor=MUT, leading=13)
    DT = ParagraphStyle('DT', fontName='Helvetica-Bold',   fontSize=9,  textColor=ACC, leading=13)

    story = []
    iv = _img(profile_img_bytes, 68)
    if iv:
        row = Table([[Paragraph(_get(ss,'name') or 'Your Name', NM), iv]], colWidths=[W-76, 76])
        row.setStyle(TableStyle([('VALIGN',(0,0),(-1,-1),'BOTTOM'),
                                  ('LEFTPADDING',(0,0),(-1,-1),0),('RIGHTPADDING',(0,0),(-1,-1),0)]))
        story.append(row)
    else:
        story.append(Paragraph(_get(ss,'name') or 'Your Name', NM))
    if _get(ss,'job_title'): story.append(Paragraph(_get(ss,'job_title'), JT))
    cp = [_get(ss,k) for k in ['email','phone','location','linkedin','github','portfolio'] if _get(ss,k)]
    if cp: story.append(Paragraph('  |  '.join(cp), CO))
    story.append(HRFlowable(width=W, thickness=2, color=ACC, spaceBefore=6, spaceAfter=10))

    def sec(title):
        # Large watermark label row, then actual bold label below it
        story.append(Paragraph(title.upper(), SL))
        story.append(HRFlowable(width=W*0.4, thickness=1, color=BDR, spaceAfter=4))

    sm = _get(ss,'summary')
    if sm:
        sec("Summary")
        for f in _bullets(sm, PN, PB, ACC): story.append(f)

    exps = [e for e in _entries(ss,'experience_entries') if e.get('company') or e.get('title')]
    if exps:
        sec("Experience")
        for e in exps:
            story.append(_row2(Paragraph(f"<b>{e.get('company','')}</b> — {e.get('title','')}", BD),
                               Paragraph(e.get('duration',''), DT), W))
            for f in _bullets(e.get('description',''), PN, PB, ACC): story.append(f)
            story.append(Spacer(1,6))

    edus = [e for e in _entries(ss,'education_entries') if e.get('institution') or e.get('degree')]
    if edus:
        sec("Education")
        for e in edus:
            story.append(_row2(Paragraph(f"<b>{e.get('institution','')}</b> — {_deg(e)}", BD),
                               Paragraph(e.get('year',''), DT), W))
            if e.get('details'): story.append(Paragraph(e['details'], MU))
            story.append(Spacer(1,4))

    for field,lbl in [('skills','Skills'),('Softskills','Soft Skills'),('languages','Languages'),('interests','Interests')]:
        v = _get(ss,field)
        if v:
            sec(lbl)
            story.extend(_pills(v, LSN, SND, BDR, W))

    projs = [p for p in _entries(ss,'project_entries') if p.get('title')]
    proj_links = _entries(ss,'project_links')
    if projs:
        sec("Projects")
        for i, p in enumerate(projs):
            lnk = proj_links[i] if i < len(proj_links) else ''
            t = _link(lnk, p.get('title',''), '#92400e') if lnk else p.get('title','')
            story.append(Paragraph(f"<b>{t}</b>  |  {p.get('tech','')}", BD))
            for f in _bullets(p.get('description',''), PN, PB, ACC): story.append(f)
            story.append(Spacer(1,6))

    certs = [c for c in _entries(ss,'certificate_links') if c.get('name')]
    if certs:
        sec("Certifications")
        for c in certs:
            nm = _link(c.get('link',''), c.get('name',''), '#92400e') if c.get('link') else c.get('name','')
            story.append(_row2(Paragraph(nm, BD), Paragraph(c.get('duration',''), DT), W))
            if c.get('description'): story.append(Paragraph(c['description'], MU))
            story.append(Spacer(1,4))

    doc.build(story); buf.seek(0); return buf


# ═════════════════════════════════════════════════════════════════════════════
# TEMPLATE 20 — Ice Blue
# Layout: single-col. Contact line uses text-icon symbols (✉ ☎ 📍 🔗).
#         Each section label has a LEFT blue vertical bar via Table.
# ═════════════════════════════════════════════════════════════════════════════
def render_template_ice_blue(session_state, profile_img_bytes=None):
    ICE = colors.HexColor('#0369a1')
    LIC = colors.HexColor('#f0f9ff')
    BDR = colors.HexColor('#bae6fd')
    ACC = colors.HexColor('#0ea5e9')
    TXT = colors.HexColor('#0c4a6e')
    MUT = colors.HexColor('#64748b')

    buf = BytesIO(); ss = session_state; W = PAGE_W - 2*MARGIN
    doc = _new_doc(buf)
    NM = ParagraphStyle('NM', fontName='Helvetica-Bold',   fontSize=22, textColor=ICE, leading=28)
    JT = ParagraphStyle('JT', fontName='Helvetica',        fontSize=12, textColor=ACC, leading=16, spaceAfter=3)
    CO = ParagraphStyle('CO', fontName='Helvetica',        fontSize=9,  textColor=MUT, leading=13)
    SH = ParagraphStyle('SH', fontName='Helvetica-Bold',   fontSize=11, textColor=ICE, leading=15)
    PN = ParagraphStyle('PN', fontName='Helvetica',        fontSize=10, textColor=TXT, leading=14, spaceAfter=2)
    PB = ParagraphStyle('PB', fontName='Helvetica',        fontSize=10, textColor=TXT, leading=14)
    BD = ParagraphStyle('BD', fontName='Helvetica-Bold',   fontSize=10, textColor=ICE, leading=14)
    MU = ParagraphStyle('MU', fontName='Helvetica',        fontSize=9,  textColor=MUT, leading=13)
    DT = ParagraphStyle('DT', fontName='Helvetica-Bold',   fontSize=9,  textColor=ACC, leading=13)

    ICONS = {'email': '✉ ', 'phone': '☎ ', 'location': '⊙ ', 'linkedin': '⊡ ', 'github': '⊞ ', 'portfolio': '⊕ '}

    story = []
    iv = _img(profile_img_bytes, 72)
    if iv:
        row = Table([[Paragraph(_get(ss,'name') or 'Your Name', NM), iv]], colWidths=[W-80, 80])
        row.setStyle(TableStyle([('VALIGN',(0,0),(-1,-1),'TOP'),
                                  ('LEFTPADDING',(0,0),(-1,-1),0),('RIGHTPADDING',(0,0),(-1,-1),0)]))
        story.append(row)
    else:
        story.append(Paragraph(_get(ss,'name') or 'Your Name', NM))
    if _get(ss,'job_title'): story.append(Paragraph(_get(ss,'job_title'), JT))
    # Icon contact line
    cp = []
    for k in ['email','phone','location','linkedin','github','portfolio']:
        v = _get(ss,k)
        if v: cp.append(f"{ICONS.get(k,'')}{v}")
    if cp: story.append(Paragraph('  '.join(cp), CO))
    story.append(HRFlowable(width=W, thickness=2, color=ICE, spaceBefore=6, spaceAfter=8))

    def sec(title):
        # Left blue bar | title
        bar = Table([[Paragraph('', SH), Paragraph(title, SH)]], colWidths=[5, W-5])
        bar.setStyle(TableStyle([
            ('BACKGROUND',(0,0),(0,-1),ICE),
            ('VALIGN',(0,0),(-1,-1),'MIDDLE'),
            ('LEFTPADDING',(0,0),(-1,-1),0),('RIGHTPADDING',(0,0),(-1,-1),0),
            ('TOPPADDING',(0,0),(-1,-1),2),('BOTTOMPADDING',(0,0),(-1,-1),2),
            ('LEFTPADDING',(1,0),(1,-1),8),
        ]))
        story.append(Spacer(1,8))
        story.append(bar)
        story.append(Spacer(1,4))

    sm = _get(ss,'summary')
    if sm:
        sec("Professional Summary")
        for f in _bullets(sm, PN, PB, ICE): story.append(f)

    exps = [e for e in _entries(ss,'experience_entries') if e.get('company') or e.get('title')]
    if exps:
        sec("Work Experience")
        for e in exps:
            story.append(_row2(Paragraph(f"<b>{e.get('company','')}</b> — {e.get('title','')}", BD),
                               Paragraph(e.get('duration',''), DT), W))
            for f in _bullets(e.get('description',''), PN, PB, ICE): story.append(f)
            story.append(Spacer(1,6))

    edus = [e for e in _entries(ss,'education_entries') if e.get('institution') or e.get('degree')]
    if edus:
        sec("Education")
        for e in edus:
            story.append(_row2(Paragraph(f"<b>{e.get('institution','')}</b> — {_deg(e)}", BD),
                               Paragraph(e.get('year',''), DT), W))
            if e.get('details'): story.append(Paragraph(e['details'], MU))
            story.append(Spacer(1,4))

    for field,lbl in [('skills','Skills'),('Softskills','Soft Skills'),('languages','Languages'),('interests','Interests')]:
        v = _get(ss,field)
        if v:
            sec(lbl)
            story.extend(_pills(v, LIC, ICE, BDR, W))

    projs = [p for p in _entries(ss,'project_entries') if p.get('title')]
    proj_links = _entries(ss,'project_links')
    if projs:
        sec("Projects")
        for i, p in enumerate(projs):
            lnk = proj_links[i] if i < len(proj_links) else ''
            t = _link(lnk, p.get('title',''), '#0369a1') if lnk else p.get('title','')
            story.append(Paragraph(f"<b>{t}</b>  |  {p.get('tech','')}", BD))
            for f in _bullets(p.get('description',''), PN, PB, ICE): story.append(f)
            story.append(Spacer(1,6))

    certs = [c for c in _entries(ss,'certificate_links') if c.get('name')]
    if certs:
        sec("Certifications")
        for c in certs:
            nm = _link(c.get('link',''), c.get('name',''), '#0369a1') if c.get('link') else c.get('name','')
            story.append(_row2(Paragraph(nm, BD), Paragraph(c.get('duration',''), DT), W))
            if c.get('description'): story.append(Paragraph(c['description'], MU))
            story.append(Spacer(1,4))

    doc.build(story); buf.seek(0); return buf


# ═════════════════════════════════════════════════════════════════════════════
# TEMPLATE 21 — Rose Gold
# Layout: single-col. Two-cell gradient-feel header (pink left | lighter right),
#         italic job title, pink-gold accent chips. Feminine, editorial look.
# ═════════════════════════════════════════════════════════════════════════════
def render_template_rose_gold(session_state, profile_img_bytes=None):
    ROS = colors.HexColor('#be185d')
    LRS = colors.HexColor('#fdf2f8')
    BDR = colors.HexColor('#f0abfc')
    PNK = colors.HexColor('#db2777')
    TXT = colors.HexColor('#4a044e')
    MUT = colors.HexColor('#9ca3af')
    WHT = colors.white
    MDP = colors.HexColor('#fce7f3')

    buf = BytesIO(); ss = session_state; W = PAGE_W - 2*MARGIN
    doc = _new_doc(buf)
    hN = ParagraphStyle('hN', fontName='Helvetica-Bold',   fontSize=22, textColor=WHT, leading=28)
    hT = ParagraphStyle('hT', fontName='Helvetica-Oblique',fontSize=12, textColor=MDP, leading=16, spaceAfter=2)
    hC = ParagraphStyle('hC', fontName='Helvetica',        fontSize=9,  textColor=MDP, leading=13)
    hR = ParagraphStyle('hR', fontName='Helvetica-Bold',   fontSize=22, textColor=ROS, leading=28)  # right cell name echo
    SH = ParagraphStyle('SH', fontName='Helvetica-Bold',   fontSize=11, textColor=ROS, leading=15, spaceBefore=10, spaceAfter=3)
    PN = ParagraphStyle('PN', fontName='Helvetica',        fontSize=10, textColor=TXT, leading=14, spaceAfter=2)
    PB = ParagraphStyle('PB', fontName='Helvetica',        fontSize=10, textColor=TXT, leading=14)
    BD = ParagraphStyle('BD', fontName='Helvetica-Bold',   fontSize=10, textColor=ROS, leading=14)
    MU = ParagraphStyle('MU', fontName='Helvetica',        fontSize=9,  textColor=MUT, leading=13)
    DT = ParagraphStyle('DT', fontName='Helvetica-Bold',   fontSize=9,  textColor=PNK, leading=13)

    story = []
    # Two-cell header: left=deep pink, right=light pink — gradient feel
    name = _get(ss,'name') or 'Your Name'
    jt   = _get(ss,'job_title')
    cp   = [_get(ss,k) for k in ['email','phone','location','linkedin','github','portfolio'] if _get(ss,k)]
    iv   = _img(profile_img_bytes, 72)

    left_cell  = [Paragraph(name, hN)]
    if jt: left_cell.append(Paragraph(jt, hT))
    if cp: left_cell.append(Paragraph('  ·  '.join(cp), hC))
    right_items = [Spacer(1,8)]
    if iv: right_items.append(iv)

    hdr = Table([[left_cell, right_items]], colWidths=[W*0.62, W*0.38])
    hdr.setStyle(TableStyle([
        ('BACKGROUND',(0,0),(0,-1),ROS),
        ('BACKGROUND',(1,0),(1,-1),MDP),
        ('VALIGN',(0,0),(-1,-1),'MIDDLE'),
        ('TOPPADDING',(0,0),(-1,-1),14),('BOTTOMPADDING',(0,0),(-1,-1),14),
        ('LEFTPADDING',(0,0),(0,-1),14),('RIGHTPADDING',(0,0),(0,-1),10),
        ('LEFTPADDING',(1,0),(1,-1),10),('RIGHTPADDING',(1,0),(1,-1),10),
        ('ALIGN',(1,0),(1,-1),'CENTER'),
    ]))
    story.append(hdr)
    story.append(Spacer(1,8))

    def sec(title):
        story.append(Paragraph(title, SH))
        story.append(HRFlowable(width=W, thickness=1.2, color=BDR, spaceAfter=4))

    sm = _get(ss,'summary')
    if sm:
        sec("Professional Summary")
        for f in _bullets(sm, PN, PB, ROS): story.append(f)

    exps = [e for e in _entries(ss,'experience_entries') if e.get('company') or e.get('title')]
    if exps:
        sec("Work Experience")
        for e in exps:
            story.append(_row2(Paragraph(f"<b>{e.get('company','')}</b> — {e.get('title','')}", BD),
                               Paragraph(e.get('duration',''), DT), W))
            for f in _bullets(e.get('description',''), PN, PB, ROS): story.append(f)
            story.append(Spacer(1,6))

    edus = [e for e in _entries(ss,'education_entries') if e.get('institution') or e.get('degree')]
    if edus:
        sec("Education")
        for e in edus:
            story.append(_row2(Paragraph(f"<b>{e.get('institution','')}</b> — {_deg(e)}", BD),
                               Paragraph(e.get('year',''), DT), W))
            if e.get('details'): story.append(Paragraph(e['details'], MU))
            story.append(Spacer(1,4))

    for field,lbl in [('skills','Skills'),('Softskills','Soft Skills'),('languages','Languages'),('interests','Interests')]:
        v = _get(ss,field)
        if v:
            sec(lbl)
            story.extend(_pills(v, LRS, ROS, BDR, W))

    projs = [p for p in _entries(ss,'project_entries') if p.get('title')]
    proj_links = _entries(ss,'project_links')
    if projs:
        sec("Projects")
        for i, p in enumerate(projs):
            lnk = proj_links[i] if i < len(proj_links) else ''
            t = _link(lnk, p.get('title',''), '#be185d') if lnk else p.get('title','')
            story.append(Paragraph(f"<b>{t}</b>  |  {p.get('tech','')}", BD))
            for f in _bullets(p.get('description',''), PN, PB, ROS): story.append(f)
            story.append(Spacer(1,6))

    certs = [c for c in _entries(ss,'certificate_links') if c.get('name')]
    if certs:
        sec("Certifications")
        for c in certs:
            nm = _link(c.get('link',''), c.get('name',''), '#be185d') if c.get('link') else c.get('name','')
            story.append(_row2(Paragraph(nm, BD), Paragraph(c.get('duration',''), DT), W))
            if c.get('description'): story.append(Paragraph(c['description'], MU))
            story.append(Spacer(1,4))

    doc.build(story); buf.seek(0); return buf


# ── Registry ──────────────────────────────────────────────────────────────────
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

def render_resume(template_name, session_state, profile_img_bytes=None):
    """Dispatch to named template. Returns BytesIO PDF."""
    fn = RESUME_TEMPLATES.get(template_name, render_template_default_professional)
    return fn(session_state, profile_img_bytes)

# HTML-compat shims kept for any legacy imports
def _fmt_desc(text, **kw): return text or ""
def _cert_name_html(cert, link_style, span_style=""): return cert.get('name','')
