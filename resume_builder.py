# resume_builder.py — 21 premium resume templates
# 15 Single-Column + 6 Double-Column
# Inspired by Enhancv, Novoresume, Canva Resume, Resume.io, VisualCV
# Each template has a distinct layout identity and color personality.

from io import BytesIO
from reportlab.lib.pagesizes import A4
from reportlab.lib import colors
from reportlab.lib.units import mm
from reportlab.lib.styles import ParagraphStyle
from reportlab.lib.enums import TA_LEFT, TA_CENTER, TA_RIGHT, TA_JUSTIFY
from reportlab.platypus import (
    SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle,
    HRFlowable, ListFlowable, ListItem, Image, KeepTogether,
)

PAGE_W, PAGE_H = A4
MARGIN    = 14 * mm
SIDEBAR_W = 158
MAIN_W    = 382

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
                [ListItem(Paragraph(t, sb), leftIndent=12,
                          bulletColor=bc or colors.HexColor('#555555')) for t in buf],
                bulletType='bullet', start='•', leftIndent=8, bulletFontSize=7))
            buf.clear()
    for is_b, c in items:
        if is_b:
            buf.append(c)
        else:
            flush()
            out.append(Paragraph(c, sn))
    flush()
    return out

def _img(b, size=72):
    if not b:
        return None
    try:
        return Image(BytesIO(b), width=size, height=size)
    except Exception:
        return None

def _img_circle(b, size=72):
    """Return image — ReportLab doesn't support true clipping, so same as _img."""
    return _img(b, size)

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
                     ('TOPPADDING',(0,0),(-1,-1),3),
                     ('BOTTOMPADDING',(0,0),(-1,-1),3),
                     ('LEFTPADDING',(0,0),(-1,-1),4),
                     ('RIGHTPADDING',(0,0),(-1,-1),4)])
    for ri in range(len(rows)):
        for ci in range(n):
            ts.add('BOX',(ci,ri),(ci,ri),0.5,bd)
    t.setStyle(ts)
    return [t, Spacer(1,4)]

def _pills(raw, bg, fg, bd, w, n=5):
    return _pill_row(_skills_list(raw), bg, fg, bd, w, n)

def _row2(lp, rp, w, lw=0.68):
    t = Table([[lp, rp]], colWidths=[w*lw, w*(1-lw)])
    t.setStyle(TableStyle([
        ('ALIGN',(1,0),(1,0),'RIGHT'),
        ('VALIGN',(0,0),(-1,-1),'TOP'),
        ('LEFTPADDING',(0,0),(-1,-1),0),
        ('RIGHTPADDING',(0,0),(-1,-1),0),
        ('TOPPADDING',(0,0),(-1,-1),0),
        ('BOTTOMPADDING',(0,0),(-1,-1),0),
    ]))
    return t

def _row3(lp, mp, rp, w, lw=0.45, mw=0.30):
    rw = 1 - lw - mw
    t = Table([[lp, mp, rp]], colWidths=[w*lw, w*mw, w*rw])
    t.setStyle(TableStyle([
        ('ALIGN',(1,0),(1,0),'CENTER'),
        ('ALIGN',(2,0),(2,0),'RIGHT'),
        ('VALIGN',(0,0),(-1,-1),'TOP'),
        ('LEFTPADDING',(0,0),(-1,-1),0),
        ('RIGHTPADDING',(0,0),(-1,-1),0),
        ('TOPPADDING',(0,0),(-1,-1),0),
        ('BOTTOMPADDING',(0,0),(-1,-1),0),
    ]))
    return t

def _new_doc(buf, lm=None, rm=None, tm=None, bm=None):
    return SimpleDocTemplate(buf, pagesize=A4,
                             leftMargin=lm or MARGIN,
                             rightMargin=rm or MARGIN,
                             topMargin=tm or MARGIN,
                             bottomMargin=bm or MARGIN)

def _contact_line(ss, sep=' | '):
    fields = ['email','phone','location','linkedin','github','portfolio']
    return sep.join([_get(ss,k) for k in fields if _get(ss,k)])

def _two_col(buf, sidebar_items, main_items, sb_bg, sb_bd,
             sb_w=None, mn_x=None, margin=None):
    from reportlab.platypus import BaseDocTemplate, Frame, PageTemplate, FrameBreak
    from reportlab.pdfgen.canvas import Canvas as _BaseCanvas

    _mg  = margin or MARGIN
    _sbw = sb_w or SIDEBAR_W
    SB_X = _mg
    MN_X = mn_x or (_mg + _sbw + 8)
    MN_W = PAGE_W - MN_X - _mg
    PH   = PAGE_H - 2 * _mg

    def _canvas_factory(bg, bd):
        class _C(_BaseCanvas):
            def showPage(self):
                self.saveState()
                self.setFillColor(bg)
                self.rect(0, 0, SB_X + _sbw + 4, PAGE_H, fill=1, stroke=0)
                if bd and bd != bg:
                    self.setStrokeColor(bd)
                    self.setLineWidth(0.5)
                    self.line(SB_X + _sbw + 4, 0, SB_X + _sbw + 4, PAGE_H)
                self.restoreState()
                super().showPage()
        return _C

    sb_frame = Frame(SB_X, _mg, _sbw, PH, leftPadding=8, rightPadding=6,
                     topPadding=10, bottomPadding=6, id='sidebar')
    mn_frame = Frame(MN_X, _mg, MN_W, PH, leftPadding=6, rightPadding=4,
                     topPadding=10, bottomPadding=6, id='main')

    doc = BaseDocTemplate(buf, pagesize=A4,
                          leftMargin=_mg, rightMargin=_mg,
                          topMargin=_mg, bottomMargin=_mg)
    doc.addPageTemplates([PageTemplate(
        id='two_col',
        frames=[sb_frame, mn_frame],
        pagesize=A4
    )])
    flowables = list(sidebar_items) + [FrameBreak()] + list(main_items)
    doc.build(flowables, canvasmaker=_canvas_factory(sb_bg, sb_bd))

def _accent_bar(w, color, height=3, space_before=0, space_after=8):
    return HRFlowable(width=w, thickness=height, color=color,
                      spaceBefore=space_before, spaceAfter=space_after)

def _section_header_box(title, style, w, bg, fg):
    """Filled-background section header."""
    t = Table([[Paragraph(title, style)]], colWidths=[w])
    t.setStyle(TableStyle([
        ('BACKGROUND',(0,0),(-1,-1),bg),
        ('TOPPADDING',(0,0),(-1,-1),4),
        ('BOTTOMPADDING',(0,0),(-1,-1),4),
        ('LEFTPADDING',(0,0),(-1,-1),8),
        ('RIGHTPADDING',(0,0),(-1,-1),8),
    ]))
    return t

def _dot_skill_bar(label, level, w, label_style, bar_fg, bar_bg, dots=8):
    """Skill name + dot-meter row (like Enhancv/Novoresume)."""
    filled = round(level * dots)
    dot_html = ''.join([
        f'<font color="{bar_fg.hexval() if hasattr(bar_fg,"hexval") else "#333"}">●</font>' if i < filled
        else f'<font color="{bar_bg.hexval() if hasattr(bar_bg,"hexval") else "#ccc"}">●</font>'
        for i in range(dots)
    ])
    dot_style = ParagraphStyle('ds', fontName='Helvetica', fontSize=8,
                                textColor=bar_fg, alignment=TA_RIGHT, leading=12)
    t = Table([[Paragraph(label, label_style), Paragraph(dot_html, dot_style)]],
              colWidths=[w*0.55, w*0.45])
    t.setStyle(TableStyle([
        ('VALIGN',(0,0),(-1,-1),'MIDDLE'),
        ('LEFTPADDING',(0,0),(-1,-1),0),
        ('RIGHTPADDING',(0,0),(-1,-1),0),
        ('TOPPADDING',(0,0),(-1,-1),1),
        ('BOTTOMPADDING',(0,0),(-1,-1),1),
    ]))
    return t


# ═════════════════════════════════════════════════════════════════════════════
# SINGLE-COLUMN TEMPLATES  (15 total)
# ═════════════════════════════════════════════════════════════════════════════

# ─── T01 · Cobalt Executive ──────────────────────────────────────────────────
# Deep cobalt blue header band, name large left-aligned, contact right,
# bold horizontal dividers, pill chips for skills. Clean corporate look.
def render_template_cobalt_executive(session_state, profile_img_bytes=None):
    ss = session_state
    COBALT  = colors.HexColor('#1b3a6b')
    ACCENT  = colors.HexColor('#2563eb')
    LTBLUE  = colors.HexColor('#dbeafe')
    BDBLUE  = colors.HexColor('#93c5fd')
    DARK    = colors.HexColor('#111827')
    MID     = colors.HexColor('#4b5563')
    buf = BytesIO(); W = PAGE_W - 2*MARGIN
    doc = _new_doc(buf)

    NM = ParagraphStyle('nm', fontName='Helvetica-Bold',    fontSize=24, textColor=COBALT,  leading=30)
    JT = ParagraphStyle('jt', fontName='Helvetica-Oblique', fontSize=12, textColor=ACCENT,  leading=16, spaceAfter=3)
    CO = ParagraphStyle('co', fontName='Helvetica',         fontSize=9,  textColor=MID,     leading=13)
    SH = ParagraphStyle('sh', fontName='Helvetica-Bold',    fontSize=10, textColor=COBALT,  leading=14, spaceBefore=12, spaceAfter=2)
    PN = ParagraphStyle('pn', fontName='Helvetica',         fontSize=10, textColor=DARK,    leading=14, spaceAfter=2)
    PB = ParagraphStyle('pb', fontName='Helvetica',         fontSize=10, textColor=DARK,    leading=14)
    BD = ParagraphStyle('bd', fontName='Helvetica-Bold',    fontSize=10, textColor=COBALT,  leading=14)
    MU = ParagraphStyle('mu', fontName='Helvetica',         fontSize=9,  textColor=MID,     leading=13)
    AC = ParagraphStyle('ac', fontName='Helvetica-Bold',    fontSize=9,  textColor=ACCENT,  leading=13)

    story = []
    # Header row: name/title left, photo right
    iv = _img(profile_img_bytes, 72)
    name_block = [Paragraph(_get(ss,'name') or 'Your Name', NM)]
    if _get(ss,'job_title'): name_block.append(Paragraph(_get(ss,'job_title'), JT))
    cp = _contact_line(ss)
    if cp: name_block.append(Paragraph(cp, CO))

    if iv:
        hdr = Table([[name_block, iv]], colWidths=[W-80, 80])
        hdr.setStyle(TableStyle([('VALIGN',(0,0),(-1,-1),'MIDDLE'),
                                  ('LEFTPADDING',(0,0),(-1,-1),0),
                                  ('RIGHTPADDING',(0,0),(-1,-1),0)]))
        story.append(hdr)
    else:
        for b in name_block: story.append(b)

    story.append(_accent_bar(W, COBALT, height=3, space_before=8, space_after=10))

    def sec(title):
        story.append(Paragraph(title.upper(), SH))
        story.append(_accent_bar(W, BDBLUE, height=0.8, space_before=0, space_after=4))

    sm = _get(ss,'summary')
    if sm:
        sec("Professional Summary")
        for f in _bullets(sm, PN, PB, ACCENT): story.append(f)
        story.append(Spacer(1,4))

    exps = [e for e in _entries(ss,'experience_entries') if e.get('company') or e.get('title')]
    if exps:
        sec("Work Experience")
        for e in exps:
            story.append(_row2(Paragraph(f"<b>{e.get('title','')}</b>  ·  {e.get('company','')}", BD),
                               Paragraph(e.get('duration',''), AC), W))
            for f in _bullets(e.get('description',''), PN, PB, ACCENT): story.append(f)
            story.append(Spacer(1,7))

    edus = [e for e in _entries(ss,'education_entries') if e.get('institution') or e.get('degree')]
    if edus:
        sec("Education")
        for e in edus:
            story.append(_row2(Paragraph(f"<b>{_deg(e)}</b>  ·  {e.get('institution','')}", BD),
                               Paragraph(e.get('year',''), AC), W))
            if e.get('details'): story.append(Paragraph(e['details'], MU))
            story.append(Spacer(1,5))

    for field, label in [('skills','Technical Skills'),('Softskills','Soft Skills'),
                          ('languages','Languages'),('interests','Interests')]:
        v = _get(ss, field)
        if v:
            sec(label)
            story.extend(_pills(v, LTBLUE, COBALT, BDBLUE, W))

    projs = [p for p in _entries(ss,'project_entries') if p.get('title')]
    proj_links = _entries(ss,'project_links')
    if projs:
        sec("Projects")
        for i, p in enumerate(projs):
            lnk = proj_links[i] if i < len(proj_links) else ''
            t = _link(lnk, p.get('title',''), '#2563eb') if lnk else p.get('title','')
            story.append(Paragraph(f"<b>{t}</b>  |  <font color='#6b7280'>{p.get('tech','')}</font>", PN))
            for f in _bullets(p.get('description',''), PN, PB, ACCENT): story.append(f)
            story.append(Spacer(1,6))

    certs = [c for c in _entries(ss,'certificate_links') if c.get('name')]
    if certs:
        sec("Certifications")
        for c in certs:
            nm = _link(c.get('link',''), c.get('name',''), '#2563eb') if c.get('link') else c.get('name','')
            story.append(_row2(Paragraph(nm, BD), Paragraph(c.get('duration',''), AC), W))
            if c.get('description'): story.append(Paragraph(c['description'], MU))
            story.append(Spacer(1,4))

    doc.build(story); buf.seek(0); return buf


# ─── T02 · Emerald Clean ─────────────────────────────────────────────────────
# Inspired by Novoresume "Oslo" — left-aligned name, emerald accent line under
# name, uppercase letter-spaced section labels with left accent bar, minimal.
def render_template_emerald_clean(session_state, profile_img_bytes=None):
    ss = session_state
    EME   = colors.HexColor('#065f46')
    EMELT = colors.HexColor('#d1fae5')
    EMEBD = colors.HexColor('#6ee7b7')
    DARK  = colors.HexColor('#111827')
    MID   = colors.HexColor('#6b7280')
    buf = BytesIO(); W = PAGE_W - 2*MARGIN
    doc = _new_doc(buf)

    NM = ParagraphStyle('nm', fontName='Helvetica-Bold',    fontSize=26, textColor=DARK,  leading=32)
    JT = ParagraphStyle('jt', fontName='Helvetica',         fontSize=12, textColor=EME,   leading=16, spaceAfter=2)
    CO = ParagraphStyle('co', fontName='Helvetica',         fontSize=9,  textColor=MID,   leading=13)
    SH = ParagraphStyle('sh', fontName='Helvetica-Bold',    fontSize=9,  textColor=EME,   leading=14, spaceBefore=14, spaceAfter=4)
    PN = ParagraphStyle('pn', fontName='Helvetica',         fontSize=10, textColor=DARK,  leading=14, spaceAfter=2)
    PB = ParagraphStyle('pb', fontName='Helvetica',         fontSize=10, textColor=DARK,  leading=14)
    BD = ParagraphStyle('bd', fontName='Helvetica-Bold',    fontSize=10, textColor=DARK,  leading=14)
    MU = ParagraphStyle('mu', fontName='Helvetica',         fontSize=9,  textColor=MID,   leading=13)
    AC = ParagraphStyle('ac', fontName='Helvetica',         fontSize=9,  textColor=EME,   leading=13)

    story = []
    iv = _img(profile_img_bytes, 70)
    name_b = [Paragraph(_get(ss,'name') or 'Your Name', NM)]
    if _get(ss,'job_title'): name_b.append(Paragraph(_get(ss,'job_title'), JT))
    cp = _contact_line(ss, '  ·  ')
    if cp: name_b.append(Paragraph(cp, CO))

    if iv:
        hdr = Table([[name_b, iv]], colWidths=[W-78, 78])
        hdr.setStyle(TableStyle([('VALIGN',(0,0),(-1,-1),'MIDDLE'),
                                  ('LEFTPADDING',(0,0),(-1,-1),0),
                                  ('RIGHTPADDING',(0,0),(-1,-1),0)]))
        story.append(hdr)
    else:
        for b in name_b: story.append(b)

    story.append(_accent_bar(W, EME, height=2, space_before=6, space_after=10))

    def sec(title):
        # Left accent bar via table
        bar_cell = Table([[Paragraph('', ParagraphStyle('x'))]], colWidths=[3])
        bar_cell.setStyle(TableStyle([('BACKGROUND',(0,0),(0,0),EME),
                                       ('TOPPADDING',(0,0),(-1,-1),0),
                                       ('BOTTOMPADDING',(0,0),(-1,-1),0)]))
        row = Table([[bar_cell, Paragraph(title.upper(), SH)]], colWidths=[8, W-8])
        row.setStyle(TableStyle([('VALIGN',(0,0),(-1,-1),'MIDDLE'),
                                  ('LEFTPADDING',(0,0),(-1,-1),0),
                                  ('RIGHTPADDING',(0,0),(-1,-1),0),
                                  ('TOPPADDING',(0,0),(-1,-1),0),
                                  ('BOTTOMPADDING',(0,0),(-1,-1),0)]))
        story.append(row)
        story.append(HRFlowable(width=W, thickness=0.4, color=EMEBD, spaceAfter=5))

    sm = _get(ss,'summary')
    if sm:
        sec("Summary")
        for f in _bullets(sm, PN, PB, EME): story.append(f)
        story.append(Spacer(1,4))

    exps = [e for e in _entries(ss,'experience_entries') if e.get('company') or e.get('title')]
    if exps:
        sec("Experience")
        for e in exps:
            story.append(_row2(Paragraph(f"<b>{e.get('title','')}</b>", BD),
                               Paragraph(e.get('duration',''), AC), W))
            story.append(Paragraph(e.get('company',''), MU))
            for f in _bullets(e.get('description',''), PN, PB, EME): story.append(f)
            story.append(Spacer(1,7))

    edus = [e for e in _entries(ss,'education_entries') if e.get('institution') or e.get('degree')]
    if edus:
        sec("Education")
        for e in edus:
            story.append(_row2(Paragraph(f"<b>{_deg(e)}</b>", BD),
                               Paragraph(e.get('year',''), AC), W))
            story.append(Paragraph(e.get('institution',''), MU))
            if e.get('details'): story.append(Paragraph(e['details'], MU))
            story.append(Spacer(1,5))

    for field, label in [('skills','Skills'),('Softskills','Soft Skills'),
                          ('languages','Languages'),('interests','Interests')]:
        v = _get(ss, field)
        if v:
            sec(label)
            story.extend(_pills(v, EMELT, EME, EMEBD, W))

    projs = [p for p in _entries(ss,'project_entries') if p.get('title')]
    proj_links = _entries(ss,'project_links')
    if projs:
        sec("Projects")
        for i, p in enumerate(projs):
            lnk = proj_links[i] if i < len(proj_links) else ''
            t = _link(lnk, p.get('title',''), '#065f46') if lnk else p.get('title','')
            story.append(Paragraph(f"<b>{t}</b>", BD))
            if p.get('tech'): story.append(Paragraph(p['tech'], AC))
            for f in _bullets(p.get('description',''), PN, PB, EME): story.append(f)
            story.append(Spacer(1,6))

    certs = [c for c in _entries(ss,'certificate_links') if c.get('name')]
    if certs:
        sec("Certifications")
        for c in certs:
            nm = _link(c.get('link',''), c.get('name',''), '#065f46') if c.get('link') else c.get('name','')
            story.append(_row2(Paragraph(nm, BD), Paragraph(c.get('duration',''), AC), W))
            if c.get('description'): story.append(Paragraph(c['description'], MU))
            story.append(Spacer(1,4))

    doc.build(story); buf.seek(0); return buf


# ─── T03 · Charcoal Impact ───────────────────────────────────────────────────
# Inspired by Canva "Bold" — thick charcoal top bar with white name,
# orange accent color, bold section headers with underline, very readable.
def render_template_charcoal_impact(session_state, profile_img_bytes=None):
    ss = session_state
    CHAR  = colors.HexColor('#1c1c1e')
    ORG   = colors.HexColor('#ea580c')
    ORGLT = colors.HexColor('#fff7ed')
    ORGBD = colors.HexColor('#fdba74')
    LGRAY = colors.HexColor('#f3f4f6')
    MID   = colors.HexColor('#6b7280')
    DARK  = colors.HexColor('#1f2937')
    buf = BytesIO(); W = PAGE_W - 2*MARGIN
    doc = _new_doc(buf)

    NM = ParagraphStyle('nm', fontName='Helvetica-Bold',    fontSize=24, textColor=colors.white, leading=30, alignment=TA_CENTER)
    JT = ParagraphStyle('jt', fontName='Helvetica',         fontSize=12, textColor=ORGLT,        leading=16, alignment=TA_CENTER)
    CO = ParagraphStyle('co', fontName='Helvetica',         fontSize=9,  textColor=colors.HexColor('#d1d5db'), leading=13, alignment=TA_CENTER)
    SH = ParagraphStyle('sh', fontName='Helvetica-Bold',    fontSize=11, textColor=CHAR,         leading=15, spaceBefore=12, spaceAfter=3)
    PN = ParagraphStyle('pn', fontName='Helvetica',         fontSize=10, textColor=DARK,         leading=14, spaceAfter=2)
    PB = ParagraphStyle('pb', fontName='Helvetica',         fontSize=10, textColor=DARK,         leading=14)
    BD = ParagraphStyle('bd', fontName='Helvetica-Bold',    fontSize=10, textColor=CHAR,         leading=14)
    MU = ParagraphStyle('mu', fontName='Helvetica',         fontSize=9,  textColor=MID,          leading=13)
    AC = ParagraphStyle('ac', fontName='Helvetica-Bold',    fontSize=9,  textColor=ORG,          leading=13)

    story = []
    # Charcoal header band
    hdr_rows = []
    iv = _img(profile_img_bytes, 68)
    if iv:
        hdr_rows.append(iv)
        story.append(Spacer(1,2))
    hdr_rows.append(Paragraph(_get(ss,'name') or 'Your Name', NM))
    if _get(ss,'job_title'):  hdr_rows.append(Paragraph(_get(ss,'job_title'), JT))
    cp = _contact_line(ss, '  |  ')
    if cp: hdr_rows.append(Paragraph(cp, CO))

    hdr_table = Table([[cell] for cell in hdr_rows], colWidths=[W])
    styles = [('BACKGROUND',(0,0),(-1,-1),CHAR),
              ('TOPPADDING',(0,0),(-1,-1),6),
              ('BOTTOMPADDING',(0,0),(-1,-1),6),
              ('LEFTPADDING',(0,0),(-1,-1),12),
              ('RIGHTPADDING',(0,0),(-1,-1),12)]
    hdr_table.setStyle(TableStyle(styles))
    story.append(hdr_table)
    story.append(Spacer(1, 10))

    def sec(title):
        story.append(Paragraph(title, SH))
        story.append(_accent_bar(W, ORG, height=2, space_before=0, space_after=5))

    sm = _get(ss,'summary')
    if sm:
        sec("Professional Summary")
        for f in _bullets(sm, PN, PB, ORG): story.append(f)
        story.append(Spacer(1,4))

    exps = [e for e in _entries(ss,'experience_entries') if e.get('company') or e.get('title')]
    if exps:
        sec("Work Experience")
        for e in exps:
            story.append(_row2(Paragraph(f"<b>{e.get('title','')}</b>", BD),
                               Paragraph(e.get('duration',''), AC), W))
            story.append(Paragraph(f"<i>{e.get('company','')}</i>", MU))
            for f in _bullets(e.get('description',''), PN, PB, ORG): story.append(f)
            story.append(Spacer(1,7))

    edus = [e for e in _entries(ss,'education_entries') if e.get('institution') or e.get('degree')]
    if edus:
        sec("Education")
        for e in edus:
            story.append(_row2(Paragraph(f"<b>{_deg(e)}</b>", BD),
                               Paragraph(e.get('year',''), AC), W))
            story.append(Paragraph(f"<i>{e.get('institution','')}</i>", MU))
            if e.get('details'): story.append(Paragraph(e['details'], MU))
            story.append(Spacer(1,5))

    for field, label in [('skills','Technical Skills'),('Softskills','Soft Skills'),
                          ('languages','Languages'),('interests','Interests')]:
        v = _get(ss, field)
        if v:
            sec(label)
            story.extend(_pills(v, ORGLT, CHAR, ORGBD, W))

    projs = [p for p in _entries(ss,'project_entries') if p.get('title')]
    proj_links = _entries(ss,'project_links')
    if projs:
        sec("Projects")
        for i, p in enumerate(projs):
            lnk = proj_links[i] if i < len(proj_links) else ''
            t = _link(lnk, p.get('title',''), '#ea580c') if lnk else p.get('title','')
            story.append(Paragraph(f"<b>{t}</b>  ·  <font color='#6b7280'>{p.get('tech','')}</font>", PN))
            for f in _bullets(p.get('description',''), PN, PB, ORG): story.append(f)
            story.append(Spacer(1,6))

    certs = [c for c in _entries(ss,'certificate_links') if c.get('name')]
    if certs:
        sec("Certifications")
        for c in certs:
            nm = _link(c.get('link',''), c.get('name',''), '#ea580c') if c.get('link') else c.get('name','')
            story.append(_row2(Paragraph(nm, BD), Paragraph(c.get('duration',''), AC), W))
            if c.get('description'): story.append(Paragraph(c['description'], MU))
            story.append(Spacer(1,4))

    doc.build(story); buf.seek(0); return buf


# ─── T04 · Arctic Minimal ────────────────────────────────────────────────────
# Inspired by Resume.io "Stockholm" — ultra-clean white, small caps name,
# cyan-teal micro-dots as section separators, no boxes, pure typography.
def render_template_arctic_minimal(session_state, profile_img_bytes=None):
    ss = session_state
    TEAL  = colors.HexColor('#0891b2')
    TLTL  = colors.HexColor('#ecfeff')
    TLTBD = colors.HexColor('#a5f3fc')
    DARK  = colors.HexColor('#0f172a')
    MID   = colors.HexColor('#64748b')
    buf = BytesIO(); W = PAGE_W - 2*MARGIN
    doc = _new_doc(buf)

    NM = ParagraphStyle('nm', fontName='Helvetica-Bold',    fontSize=22, textColor=DARK,  leading=28)
    JT = ParagraphStyle('jt', fontName='Helvetica',         fontSize=12, textColor=TEAL,  leading=16, spaceAfter=2)
    CO = ParagraphStyle('co', fontName='Helvetica',         fontSize=9,  textColor=MID,   leading=13)
    SH = ParagraphStyle('sh', fontName='Helvetica-Bold',    fontSize=10, textColor=TEAL,  leading=14, spaceBefore=14, spaceAfter=5)
    PN = ParagraphStyle('pn', fontName='Helvetica',         fontSize=10, textColor=DARK,  leading=14, spaceAfter=2)
    PB = ParagraphStyle('pb', fontName='Helvetica',         fontSize=10, textColor=DARK,  leading=14)
    BD = ParagraphStyle('bd', fontName='Helvetica-Bold',    fontSize=10, textColor=DARK,  leading=14)
    MU = ParagraphStyle('mu', fontName='Helvetica',         fontSize=9,  textColor=MID,   leading=13)
    AC = ParagraphStyle('ac', fontName='Helvetica',         fontSize=9,  textColor=TEAL,  leading=13)

    story = []
    iv = _img(profile_img_bytes, 68)
    if iv:
        hdr = Table([[
            [Paragraph(_get(ss,'name') or 'Your Name', NM),
             Paragraph(_get(ss,'job_title') or '', JT) if _get(ss,'job_title') else Spacer(1,1),
             Paragraph(_contact_line(ss, '  ·  '), CO)],
            iv
        ]], colWidths=[W-76, 76])
        hdr.setStyle(TableStyle([('VALIGN',(0,0),(-1,-1),'MIDDLE'),
                                  ('LEFTPADDING',(0,0),(-1,-1),0),
                                  ('RIGHTPADDING',(0,0),(-1,-1),0)]))
        story.append(hdr)
    else:
        story.append(Paragraph(_get(ss,'name') or 'Your Name', NM))
        if _get(ss,'job_title'): story.append(Paragraph(_get(ss,'job_title'), JT))
        cp = _contact_line(ss,'  ·  ')
        if cp: story.append(Paragraph(cp, CO))

    story.append(_accent_bar(W, TEAL, height=1.5, space_before=8, space_after=10))

    def sec(title):
        story.append(Paragraph(title.upper(), SH))

    sm = _get(ss,'summary')
    if sm:
        sec("Summary")
        for f in _bullets(sm, PN, PB, TEAL): story.append(f)
        story.append(Spacer(1,4))

    exps = [e for e in _entries(ss,'experience_entries') if e.get('company') or e.get('title')]
    if exps:
        sec("Experience")
        for e in exps:
            story.append(_row2(Paragraph(f"<b>{e.get('title','')}</b>  ·  {e.get('company','')}", BD),
                               Paragraph(e.get('duration',''), AC), W))
            for f in _bullets(e.get('description',''), PN, PB, TEAL): story.append(f)
            story.append(Spacer(1,7))

    edus = [e for e in _entries(ss,'education_entries') if e.get('institution') or e.get('degree')]
    if edus:
        sec("Education")
        for e in edus:
            story.append(_row2(Paragraph(f"<b>{_deg(e)}</b>  ·  {e.get('institution','')}", BD),
                               Paragraph(e.get('year',''), AC), W))
            if e.get('details'): story.append(Paragraph(e['details'], MU))
            story.append(Spacer(1,5))

    for field, label in [('skills','Skills'),('Softskills','Soft Skills'),
                          ('languages','Languages'),('interests','Interests')]:
        v = _get(ss, field)
        if v:
            sec(label)
            story.extend(_pills(v, TLTL, TEAL, TLTBD, W))

    projs = [p for p in _entries(ss,'project_entries') if p.get('title')]
    proj_links = _entries(ss,'project_links')
    if projs:
        sec("Projects")
        for i, p in enumerate(projs):
            lnk = proj_links[i] if i < len(proj_links) else ''
            t = _link(lnk, p.get('title',''), '#0891b2') if lnk else p.get('title','')
            story.append(Paragraph(f"<b>{t}</b>", BD))
            if p.get('tech'): story.append(Paragraph(p['tech'], AC))
            for f in _bullets(p.get('description',''), PN, PB, TEAL): story.append(f)
            story.append(Spacer(1,6))

    certs = [c for c in _entries(ss,'certificate_links') if c.get('name')]
    if certs:
        sec("Certifications")
        for c in certs:
            nm = _link(c.get('link',''), c.get('name',''), '#0891b2') if c.get('link') else c.get('name','')
            story.append(_row2(Paragraph(nm, BD), Paragraph(c.get('duration',''), AC), W))
            if c.get('description'): story.append(Paragraph(c['description'], MU))
            story.append(Spacer(1,4))

    doc.build(story); buf.seek(0); return buf


# ─── T05 · Ruby Professional ─────────────────────────────────────────────────
# Inspired by Enhancv "London" — centered name with bold red name initial cap,
# two-tone dividers, section labels with small red square icon, warm tone.
def render_template_ruby_professional(session_state, profile_img_bytes=None):
    ss = session_state
    RUBY  = colors.HexColor('#9f1239')
    RUBLT = colors.HexColor('#fff1f2')
    RUBBD = colors.HexColor('#fda4af')
    DARK  = colors.HexColor('#1c1917')
    MID   = colors.HexColor('#78716c')
    buf = BytesIO(); W = PAGE_W - 2*MARGIN
    doc = _new_doc(buf)

    NM = ParagraphStyle('nm', fontName='Helvetica-Bold',    fontSize=24, textColor=RUBY,  leading=30, alignment=TA_CENTER)
    JT = ParagraphStyle('jt', fontName='Helvetica-Oblique', fontSize=12, textColor=DARK,  leading=16, alignment=TA_CENTER, spaceAfter=2)
    CO = ParagraphStyle('co', fontName='Helvetica',         fontSize=9,  textColor=MID,   leading=13, alignment=TA_CENTER)
    SH = ParagraphStyle('sh', fontName='Helvetica-Bold',    fontSize=10, textColor=RUBY,  leading=14, spaceBefore=12, spaceAfter=3)
    PN = ParagraphStyle('pn', fontName='Helvetica',         fontSize=10, textColor=DARK,  leading=14, spaceAfter=2)
    PB = ParagraphStyle('pb', fontName='Helvetica',         fontSize=10, textColor=DARK,  leading=14)
    BD = ParagraphStyle('bd', fontName='Helvetica-Bold',    fontSize=10, textColor=DARK,  leading=14)
    MU = ParagraphStyle('mu', fontName='Helvetica',         fontSize=9,  textColor=MID,   leading=13)
    AC = ParagraphStyle('ac', fontName='Helvetica-Bold',    fontSize=9,  textColor=RUBY,  leading=13)

    story = []
    iv = _img(profile_img_bytes, 72)
    if iv:
        story.append(Table([[iv]], colWidths=[W]))
        story[-1].setStyle(TableStyle([('ALIGN',(0,0),(0,0),'CENTER'),
                                        ('TOPPADDING',(0,0),(-1,-1),0),
                                        ('BOTTOMPADDING',(0,0),(-1,-1),4)]))
    story.append(Paragraph(_get(ss,'name') or 'Your Name', NM))
    if _get(ss,'job_title'): story.append(Paragraph(_get(ss,'job_title'), JT))
    cp = _contact_line(ss, '  |  ')
    if cp: story.append(Paragraph(cp, CO))
    story.append(_accent_bar(W, RUBY, height=2, space_before=8, space_after=10))

    def sec(title):
        row = Table([[
            Paragraph('■', ParagraphStyle('sq', fontName='Helvetica', fontSize=8, textColor=RUBY, leading=14)),
            Paragraph(f' {title.upper()}', SH)
        ]], colWidths=[12, W-12])
        row.setStyle(TableStyle([('VALIGN',(0,0),(-1,-1),'MIDDLE'),
                                  ('LEFTPADDING',(0,0),(-1,-1),0),
                                  ('RIGHTPADDING',(0,0),(-1,-1),0),
                                  ('TOPPADDING',(0,0),(-1,-1),10),
                                  ('BOTTOMPADDING',(0,0),(-1,-1),0)]))
        story.append(row)
        story.append(HRFlowable(width=W, thickness=0.5, color=RUBBD, spaceAfter=5))

    sm = _get(ss,'summary')
    if sm:
        sec("Summary")
        for f in _bullets(sm, PN, PB, RUBY): story.append(f)
        story.append(Spacer(1,4))

    exps = [e for e in _entries(ss,'experience_entries') if e.get('company') or e.get('title')]
    if exps:
        sec("Work Experience")
        for e in exps:
            story.append(_row2(Paragraph(f"<b>{e.get('title','')}</b>  ·  {e.get('company','')}", BD),
                               Paragraph(e.get('duration',''), AC), W))
            for f in _bullets(e.get('description',''), PN, PB, RUBY): story.append(f)
            story.append(Spacer(1,7))

    edus = [e for e in _entries(ss,'education_entries') if e.get('institution') or e.get('degree')]
    if edus:
        sec("Education")
        for e in edus:
            story.append(_row2(Paragraph(f"<b>{_deg(e)}</b>  ·  {e.get('institution','')}", BD),
                               Paragraph(e.get('year',''), AC), W))
            if e.get('details'): story.append(Paragraph(e['details'], MU))
            story.append(Spacer(1,5))

    for field, label in [('skills','Skills'),('Softskills','Soft Skills'),
                          ('languages','Languages'),('interests','Interests')]:
        v = _get(ss, field)
        if v:
            sec(label)
            story.extend(_pills(v, RUBLT, RUBY, RUBBD, W))

    projs = [p for p in _entries(ss,'project_entries') if p.get('title')]
    proj_links = _entries(ss,'project_links')
    if projs:
        sec("Projects")
        for i, p in enumerate(projs):
            lnk = proj_links[i] if i < len(proj_links) else ''
            t = _link(lnk, p.get('title',''), '#9f1239') if lnk else p.get('title','')
            story.append(Paragraph(f"<b>{t}</b>  ·  <font color='#78716c'>{p.get('tech','')}</font>", PN))
            for f in _bullets(p.get('description',''), PN, PB, RUBY): story.append(f)
            story.append(Spacer(1,6))

    certs = [c for c in _entries(ss,'certificate_links') if c.get('name')]
    if certs:
        sec("Certifications")
        for c in certs:
            nm = _link(c.get('link',''), c.get('name',''), '#9f1239') if c.get('link') else c.get('name','')
            story.append(_row2(Paragraph(nm, BD), Paragraph(c.get('duration',''), AC), W))
            if c.get('description'): story.append(Paragraph(c['description'], MU))
            story.append(Spacer(1,4))

    doc.build(story); buf.seek(0); return buf


# ─── T06 · Slate Modern ──────────────────────────────────────────────────────
# Inspired by VisualCV "Elegant" — dark slate header, very structured layout
# with generous whitespace, right-aligned dates in muted italic, clean.
def render_template_slate_modern(session_state, profile_img_bytes=None):
    ss = session_state
    SLATE  = colors.HexColor('#334155')
    SLLT   = colors.HexColor('#f1f5f9')
    SLBD   = colors.HexColor('#94a3b8')
    VIOLET = colors.HexColor('#7c3aed')
    DARK   = colors.HexColor('#1e293b')
    MID    = colors.HexColor('#64748b')
    buf = BytesIO(); W = PAGE_W - 2*MARGIN
    doc = _new_doc(buf)

    NM = ParagraphStyle('nm', fontName='Helvetica-Bold',    fontSize=23, textColor=colors.white, leading=29)
    JT = ParagraphStyle('jt', fontName='Helvetica',         fontSize=11, textColor=SLLT,          leading=15, spaceAfter=3)
    CO = ParagraphStyle('co', fontName='Helvetica',         fontSize=9,  textColor=colors.HexColor('#cbd5e1'), leading=13)
    SH = ParagraphStyle('sh', fontName='Helvetica-Bold',    fontSize=10, textColor=SLATE,          leading=14, spaceBefore=12, spaceAfter=3)
    PN = ParagraphStyle('pn', fontName='Helvetica',         fontSize=10, textColor=DARK,           leading=14, spaceAfter=2)
    PB = ParagraphStyle('pb', fontName='Helvetica',         fontSize=10, textColor=DARK,           leading=14)
    BD = ParagraphStyle('bd', fontName='Helvetica-Bold',    fontSize=10, textColor=DARK,           leading=14)
    MU = ParagraphStyle('mu', fontName='Helvetica-Oblique', fontSize=9,  textColor=MID,            leading=13)
    AC = ParagraphStyle('ac', fontName='Helvetica-Oblique', fontSize=9,  textColor=MID,            leading=13, alignment=TA_RIGHT)

    story = []
    # Header band
    iv = _img(profile_img_bytes, 70)
    hdr_content = [Paragraph(_get(ss,'name') or 'Your Name', NM)]
    if _get(ss,'job_title'): hdr_content.append(Paragraph(_get(ss,'job_title'), JT))
    cp = _contact_line(ss, '  ·  ')
    if cp: hdr_content.append(Paragraph(cp, CO))

    if iv:
        hdr_t = Table([[hdr_content, iv]], colWidths=[W-78, 78])
        hdr_t.setStyle(TableStyle([('BACKGROUND',(0,0),(-1,-1),SLATE),
                                    ('VALIGN',(0,0),(-1,-1),'MIDDLE'),
                                    ('LEFTPADDING',(0,0),(-1,-1),10),
                                    ('RIGHTPADDING',(0,0),(-1,-1),10),
                                    ('TOPPADDING',(0,0),(-1,-1),10),
                                    ('BOTTOMPADDING',(0,0),(-1,-1),10)]))
        story.append(hdr_t)
    else:
        hdr_t = Table([[hdr_content]], colWidths=[W])
        hdr_t.setStyle(TableStyle([('BACKGROUND',(0,0),(-1,-1),SLATE),
                                    ('TOPPADDING',(0,0),(-1,-1),12),
                                    ('BOTTOMPADDING',(0,0),(-1,-1),12),
                                    ('LEFTPADDING',(0,0),(-1,-1),12),
                                    ('RIGHTPADDING',(0,0),(-1,-1),12)]))
        story.append(hdr_t)
    story.append(Spacer(1,10))

    def sec(title):
        story.append(Paragraph(title, SH))
        story.append(HRFlowable(width=W, thickness=1.5, color=VIOLET, spaceAfter=5))

    sm = _get(ss,'summary')
    if sm:
        sec("Summary")
        for f in _bullets(sm, PN, PB, VIOLET): story.append(f)
        story.append(Spacer(1,4))

    exps = [e for e in _entries(ss,'experience_entries') if e.get('company') or e.get('title')]
    if exps:
        sec("Work Experience")
        for e in exps:
            story.append(_row2(Paragraph(f"<b>{e.get('title','')}</b>, {e.get('company','')}", BD),
                               Paragraph(e.get('duration',''), AC), W))
            for f in _bullets(e.get('description',''), PN, PB, VIOLET): story.append(f)
            story.append(Spacer(1,7))

    edus = [e for e in _entries(ss,'education_entries') if e.get('institution') or e.get('degree')]
    if edus:
        sec("Education")
        for e in edus:
            story.append(_row2(Paragraph(f"<b>{_deg(e)}</b>, {e.get('institution','')}", BD),
                               Paragraph(e.get('year',''), AC), W))
            if e.get('details'): story.append(Paragraph(e['details'], MU))
            story.append(Spacer(1,5))

    for field, label in [('skills','Technical Skills'),('Softskills','Soft Skills'),
                          ('languages','Languages'),('interests','Interests')]:
        v = _get(ss, field)
        if v:
            sec(label)
            story.extend(_pills(v, SLLT, SLATE, SLBD, W))

    projs = [p for p in _entries(ss,'project_entries') if p.get('title')]
    proj_links = _entries(ss,'project_links')
    if projs:
        sec("Projects")
        for i, p in enumerate(projs):
            lnk = proj_links[i] if i < len(proj_links) else ''
            t = _link(lnk, p.get('title',''), '#7c3aed') if lnk else p.get('title','')
            story.append(Paragraph(f"<b>{t}</b>  ·  <font color='#64748b'>{p.get('tech','')}</font>", PN))
            for f in _bullets(p.get('description',''), PN, PB, VIOLET): story.append(f)
            story.append(Spacer(1,6))

    certs = [c for c in _entries(ss,'certificate_links') if c.get('name')]
    if certs:
        sec("Certifications")
        for c in certs:
            nm = _link(c.get('link',''), c.get('name',''), '#7c3aed') if c.get('link') else c.get('name','')
            story.append(_row2(Paragraph(nm, BD), Paragraph(c.get('duration',''), AC), W))
            if c.get('description'): story.append(Paragraph(c['description'], MU))
            story.append(Spacer(1,4))

    doc.build(story); buf.seek(0); return buf


# ─── T07 · Golden Classic ────────────────────────────────────────────────────
# Inspired by Resume.io "Dublin" — gold-and-dark luxury look, serif-style bold
# name, thin gold lines as section dividers, professional feel.
def render_template_golden_classic(session_state, profile_img_bytes=None):
    ss = session_state
    GOLD   = colors.HexColor('#b45309')
    GOLDLT = colors.HexColor('#fef3c7')
    GOLDBD = colors.HexColor('#fcd34d')
    DARK   = colors.HexColor('#1c1917')
    MID    = colors.HexColor('#78716c')
    buf = BytesIO(); W = PAGE_W - 2*MARGIN
    doc = _new_doc(buf)

    NM = ParagraphStyle('nm', fontName='Helvetica-Bold',    fontSize=26, textColor=DARK,   leading=32, alignment=TA_CENTER)
    JT = ParagraphStyle('jt', fontName='Helvetica-Oblique', fontSize=12, textColor=GOLD,   leading=16, alignment=TA_CENTER, spaceAfter=2)
    CO = ParagraphStyle('co', fontName='Helvetica',         fontSize=9,  textColor=MID,    leading=13, alignment=TA_CENTER)
    SH = ParagraphStyle('sh', fontName='Helvetica-Bold',    fontSize=11, textColor=DARK,   leading=15, spaceBefore=12, spaceAfter=2)
    PN = ParagraphStyle('pn', fontName='Helvetica',         fontSize=10, textColor=DARK,   leading=14, spaceAfter=2)
    PB = ParagraphStyle('pb', fontName='Helvetica',         fontSize=10, textColor=DARK,   leading=14)
    BD = ParagraphStyle('bd', fontName='Helvetica-Bold',    fontSize=10, textColor=DARK,   leading=14)
    MU = ParagraphStyle('mu', fontName='Helvetica',         fontSize=9,  textColor=MID,    leading=13)
    AC = ParagraphStyle('ac', fontName='Helvetica-Bold',    fontSize=9,  textColor=GOLD,   leading=13)

    story = []
    iv = _img(profile_img_bytes, 72)
    if iv:
        story.append(Table([[iv]], colWidths=[W]))
        story[-1].setStyle(TableStyle([('ALIGN',(0,0),(0,0),'CENTER'),
                                        ('TOPPADDING',(0,0),(-1,-1),0),
                                        ('BOTTOMPADDING',(0,0),(-1,-1),5)]))

    story.append(Paragraph(_get(ss,'name') or 'Your Name', NM))
    if _get(ss,'job_title'): story.append(Paragraph(_get(ss,'job_title'), JT))
    cp = _contact_line(ss, '  ·  ')
    if cp: story.append(Paragraph(cp, CO))

    story.append(HRFlowable(width=W, thickness=0.5, color=GOLDBD, spaceBefore=4, spaceAfter=2))
    story.append(HRFlowable(width=W, thickness=2.5, color=GOLD, spaceBefore=0, spaceAfter=10))

    def sec(title):
        story.append(HRFlowable(width=W, thickness=1, color=GOLDBD, spaceBefore=10, spaceAfter=3))
        row = Table([[Paragraph(title.upper(), SH),
                      Paragraph('', ParagraphStyle('x'))]], colWidths=[W*0.7, W*0.3])
        row.setStyle(TableStyle([('LEFTPADDING',(0,0),(-1,-1),0),
                                  ('RIGHTPADDING',(0,0),(-1,-1),0),
                                  ('TOPPADDING',(0,0),(-1,-1),0),
                                  ('BOTTOMPADDING',(0,0),(-1,-1),3)]))
        story.append(row)

    sm = _get(ss,'summary')
    if sm:
        sec("Professional Summary")
        for f in _bullets(sm, PN, PB, GOLD): story.append(f)
        story.append(Spacer(1,4))

    exps = [e for e in _entries(ss,'experience_entries') if e.get('company') or e.get('title')]
    if exps:
        sec("Work Experience")
        for e in exps:
            story.append(_row2(Paragraph(f"<b>{e.get('title','')}</b>  ·  {e.get('company','')}", BD),
                               Paragraph(e.get('duration',''), AC), W))
            for f in _bullets(e.get('description',''), PN, PB, GOLD): story.append(f)
            story.append(Spacer(1,7))

    edus = [e for e in _entries(ss,'education_entries') if e.get('institution') or e.get('degree')]
    if edus:
        sec("Education")
        for e in edus:
            story.append(_row2(Paragraph(f"<b>{_deg(e)}</b>  ·  {e.get('institution','')}", BD),
                               Paragraph(e.get('year',''), AC), W))
            if e.get('details'): story.append(Paragraph(e['details'], MU))
            story.append(Spacer(1,5))

    for field, label in [('skills','Skills'),('Softskills','Soft Skills'),
                          ('languages','Languages'),('interests','Interests')]:
        v = _get(ss, field)
        if v:
            sec(label)
            story.extend(_pills(v, GOLDLT, DARK, GOLDBD, W))

    projs = [p for p in _entries(ss,'project_entries') if p.get('title')]
    proj_links = _entries(ss,'project_links')
    if projs:
        sec("Projects")
        for i, p in enumerate(projs):
            lnk = proj_links[i] if i < len(proj_links) else ''
            t = _link(lnk, p.get('title',''), '#b45309') if lnk else p.get('title','')
            story.append(Paragraph(f"<b>{t}</b>  ·  <font color='#78716c'>{p.get('tech','')}</font>", PN))
            for f in _bullets(p.get('description',''), PN, PB, GOLD): story.append(f)
            story.append(Spacer(1,6))

    certs = [c for c in _entries(ss,'certificate_links') if c.get('name')]
    if certs:
        sec("Certifications")
        for c in certs:
            nm = _link(c.get('link',''), c.get('name',''), '#b45309') if c.get('link') else c.get('name','')
            story.append(_row2(Paragraph(nm, BD), Paragraph(c.get('duration',''), AC), W))
            if c.get('description'): story.append(Paragraph(c['description'], MU))
            story.append(Spacer(1,4))

    doc.build(story); buf.seek(0); return buf


# ─── T08 · Navy Prestige ─────────────────────────────────────────────────────
# Deep navy with gold accent — classic prestige look. Full-width dark header,
# gold section rule lines, skill pills in navy-on-cream.
def render_template_navy_prestige(session_state, profile_img_bytes=None):
    ss = session_state
    NAVY   = colors.HexColor('#0f2d4f')
    NGOLD  = colors.HexColor('#c9972b')
    CREAM  = colors.HexColor('#fdf8f0')
    CRMBD  = colors.HexColor('#e8d5a3')
    DARK   = colors.HexColor('#0a1628')
    MID    = colors.HexColor('#6b7280')
    buf = BytesIO(); W = PAGE_W - 2*MARGIN
    doc = _new_doc(buf)

    NM = ParagraphStyle('nm', fontName='Helvetica-Bold',    fontSize=22, textColor=colors.white, leading=28)
    JT = ParagraphStyle('jt', fontName='Helvetica-Oblique', fontSize=11, textColor=CREAM,        leading=15)
    CO = ParagraphStyle('co', fontName='Helvetica',         fontSize=8,  textColor=colors.HexColor('#94a3b8'), leading=12)
    SH = ParagraphStyle('sh', fontName='Helvetica-Bold',    fontSize=10, textColor=NAVY,          leading=14, spaceBefore=12, spaceAfter=3)
    PN = ParagraphStyle('pn', fontName='Helvetica',         fontSize=10, textColor=DARK,          leading=14, spaceAfter=2)
    PB = ParagraphStyle('pb', fontName='Helvetica',         fontSize=10, textColor=DARK,          leading=14)
    BD = ParagraphStyle('bd', fontName='Helvetica-Bold',    fontSize=10, textColor=NAVY,          leading=14)
    MU = ParagraphStyle('mu', fontName='Helvetica',         fontSize=9,  textColor=MID,           leading=13)
    AC = ParagraphStyle('ac', fontName='Helvetica-Bold',    fontSize=9,  textColor=NGOLD,         leading=13)

    story = []
    iv = _img(profile_img_bytes, 68)
    hdr_text = [Paragraph(_get(ss,'name') or 'Your Name', NM)]
    if _get(ss,'job_title'): hdr_text.append(Paragraph(_get(ss,'job_title'), JT))
    cp = _contact_line(ss,'  ·  ')
    if cp: hdr_text.append(Paragraph(cp, CO))

    if iv:
        hdr_t = Table([[hdr_text, iv]], colWidths=[W-78, 78])
    else:
        hdr_t = Table([[hdr_text]], colWidths=[W])
    hdr_t.setStyle(TableStyle([('BACKGROUND',(0,0),(-1,-1),NAVY),
                                ('VALIGN',(0,0),(-1,-1),'MIDDLE'),
                                ('TOPPADDING',(0,0),(-1,-1),14),
                                ('BOTTOMPADDING',(0,0),(-1,-1),14),
                                ('LEFTPADDING',(0,0),(-1,-1),14),
                                ('RIGHTPADDING',(0,0),(-1,-1),14)]))
    story.append(hdr_t)
    story.append(HRFlowable(width=W, thickness=3, color=NGOLD, spaceBefore=0, spaceAfter=10))

    def sec(title):
        story.append(Paragraph(title.upper(), SH))
        story.append(HRFlowable(width=W, thickness=1, color=NGOLD, spaceAfter=5))

    sm = _get(ss,'summary')
    if sm:
        sec("Professional Summary")
        for f in _bullets(sm, PN, PB, NGOLD): story.append(f)
        story.append(Spacer(1,4))

    exps = [e for e in _entries(ss,'experience_entries') if e.get('company') or e.get('title')]
    if exps:
        sec("Work Experience")
        for e in exps:
            story.append(_row2(Paragraph(f"<b>{e.get('title','')}</b>  —  {e.get('company','')}", BD),
                               Paragraph(e.get('duration',''), AC), W))
            for f in _bullets(e.get('description',''), PN, PB, NGOLD): story.append(f)
            story.append(Spacer(1,7))

    edus = [e for e in _entries(ss,'education_entries') if e.get('institution') or e.get('degree')]
    if edus:
        sec("Education")
        for e in edus:
            story.append(_row2(Paragraph(f"<b>{_deg(e)}</b>  —  {e.get('institution','')}", BD),
                               Paragraph(e.get('year',''), AC), W))
            if e.get('details'): story.append(Paragraph(e['details'], MU))
            story.append(Spacer(1,5))

    for field, label in [('skills','Skills'),('Softskills','Soft Skills'),
                          ('languages','Languages'),('interests','Interests')]:
        v = _get(ss, field)
        if v:
            sec(label)
            story.extend(_pills(v, CREAM, NAVY, CRMBD, W))

    projs = [p for p in _entries(ss,'project_entries') if p.get('title')]
    proj_links = _entries(ss,'project_links')
    if projs:
        sec("Projects")
        for i, p in enumerate(projs):
            lnk = proj_links[i] if i < len(proj_links) else ''
            t = _link(lnk, p.get('title',''), '#c9972b') if lnk else p.get('title','')
            story.append(Paragraph(f"<b>{t}</b>  ·  <font color='#6b7280'>{p.get('tech','')}</font>", PN))
            for f in _bullets(p.get('description',''), PN, PB, NGOLD): story.append(f)
            story.append(Spacer(1,6))

    certs = [c for c in _entries(ss,'certificate_links') if c.get('name')]
    if certs:
        sec("Certifications")
        for c in certs:
            nm = _link(c.get('link',''), c.get('name',''), '#c9972b') if c.get('link') else c.get('name','')
            story.append(_row2(Paragraph(nm, BD), Paragraph(c.get('duration',''), AC), W))
            if c.get('description'): story.append(Paragraph(c['description'], MU))
            story.append(Spacer(1,4))

    doc.build(story); buf.seek(0); return buf


# ─── T09 · Coral Creative ────────────────────────────────────────────────────
# Vibrant coral/pink — eye-catching creative-industry look, section headers in
# filled coral boxes with white text, skills as stacked tag rows.
def render_template_coral_creative(session_state, profile_img_bytes=None):
    ss = session_state
    CORAL  = colors.HexColor('#e11d48')
    CORLT  = colors.HexColor('#fff1f2')
    CORBD  = colors.HexColor('#fda4af')
    DARK   = colors.HexColor('#18181b')
    MID    = colors.HexColor('#71717a')
    buf = BytesIO(); W = PAGE_W - 2*MARGIN
    doc = _new_doc(buf)

    NM = ParagraphStyle('nm', fontName='Helvetica-Bold',    fontSize=25, textColor=CORAL,  leading=31)
    JT = ParagraphStyle('jt', fontName='Helvetica',         fontSize=12, textColor=DARK,   leading=16, spaceAfter=2)
    CO = ParagraphStyle('co', fontName='Helvetica',         fontSize=9,  textColor=MID,    leading=13)
    SH = ParagraphStyle('sh', fontName='Helvetica-Bold',    fontSize=9,  textColor=colors.white, leading=13)
    PN = ParagraphStyle('pn', fontName='Helvetica',         fontSize=10, textColor=DARK,   leading=14, spaceAfter=2)
    PB = ParagraphStyle('pb', fontName='Helvetica',         fontSize=10, textColor=DARK,   leading=14)
    BD = ParagraphStyle('bd', fontName='Helvetica-Bold',    fontSize=10, textColor=DARK,   leading=14)
    MU = ParagraphStyle('mu', fontName='Helvetica',         fontSize=9,  textColor=MID,    leading=13)
    AC = ParagraphStyle('ac', fontName='Helvetica-Bold',    fontSize=9,  textColor=CORAL,  leading=13)

    story = []
    iv = _img(profile_img_bytes, 72)
    name_b = [Paragraph(_get(ss,'name') or 'Your Name', NM)]
    if _get(ss,'job_title'): name_b.append(Paragraph(_get(ss,'job_title'), JT))
    cp = _contact_line(ss,'  ·  ')
    if cp: name_b.append(Paragraph(cp, CO))

    if iv:
        hdr = Table([[name_b, iv]], colWidths=[W-80, 80])
        hdr.setStyle(TableStyle([('VALIGN',(0,0),(-1,-1),'MIDDLE'),
                                  ('LEFTPADDING',(0,0),(-1,-1),0),
                                  ('RIGHTPADDING',(0,0),(-1,-1),0)]))
        story.append(hdr)
    else:
        for b in name_b: story.append(b)

    story.append(_accent_bar(W, CORAL, height=3, space_before=8, space_after=10))

    def sec(title):
        t = _section_header_box(title.upper(), SH, W, CORAL, colors.white)
        story.append(t)
        story.append(Spacer(1, 6))

    sm = _get(ss,'summary')
    if sm:
        sec("Summary")
        for f in _bullets(sm, PN, PB, CORAL): story.append(f)
        story.append(Spacer(1,5))

    exps = [e for e in _entries(ss,'experience_entries') if e.get('company') or e.get('title')]
    if exps:
        sec("Work Experience")
        for e in exps:
            story.append(_row2(Paragraph(f"<b>{e.get('title','')}</b>  ·  {e.get('company','')}", BD),
                               Paragraph(e.get('duration',''), AC), W))
            for f in _bullets(e.get('description',''), PN, PB, CORAL): story.append(f)
            story.append(Spacer(1,7))

    edus = [e for e in _entries(ss,'education_entries') if e.get('institution') or e.get('degree')]
    if edus:
        sec("Education")
        for e in edus:
            story.append(_row2(Paragraph(f"<b>{_deg(e)}</b>  ·  {e.get('institution','')}", BD),
                               Paragraph(e.get('year',''), AC), W))
            if e.get('details'): story.append(Paragraph(e['details'], MU))
            story.append(Spacer(1,5))

    for field, label in [('skills','Skills'),('Softskills','Soft Skills'),
                          ('languages','Languages'),('interests','Interests')]:
        v = _get(ss, field)
        if v:
            sec(label)
            story.extend(_pills(v, CORLT, CORAL, CORBD, W))

    projs = [p for p in _entries(ss,'project_entries') if p.get('title')]
    proj_links = _entries(ss,'project_links')
    if projs:
        sec("Projects")
        for i, p in enumerate(projs):
            lnk = proj_links[i] if i < len(proj_links) else ''
            t = _link(lnk, p.get('title',''), '#e11d48') if lnk else p.get('title','')
            story.append(Paragraph(f"<b>{t}</b>  ·  <font color='#71717a'>{p.get('tech','')}</font>", PN))
            for f in _bullets(p.get('description',''), PN, PB, CORAL): story.append(f)
            story.append(Spacer(1,6))

    certs = [c for c in _entries(ss,'certificate_links') if c.get('name')]
    if certs:
        sec("Certifications")
        for c in certs:
            nm = _link(c.get('link',''), c.get('name',''), '#e11d48') if c.get('link') else c.get('name','')
            story.append(_row2(Paragraph(nm, BD), Paragraph(c.get('duration',''), AC), W))
            if c.get('description'): story.append(Paragraph(c['description'], MU))
            story.append(Spacer(1,4))

    doc.build(story); buf.seek(0); return buf


# ─── T10 · Monochrome ATS ────────────────────────────────────────────────────
# Pure black and white, ATS-optimized. No decorative elements. Maximum text
# density. Name bold 20pt, all sections left-aligned, skills as comma list.
def render_template_monochrome_ats(session_state, profile_img_bytes=None):
    ss = session_state
    BLK   = colors.HexColor('#000000')
    DRK   = colors.HexColor('#222222')
    MID   = colors.HexColor('#555555')
    buf = BytesIO(); W = PAGE_W - 2*MARGIN
    doc = _new_doc(buf)

    NM = ParagraphStyle('nm', fontName='Helvetica-Bold',    fontSize=20, textColor=BLK,  leading=26)
    JT = ParagraphStyle('jt', fontName='Helvetica',         fontSize=11, textColor=DRK,  leading=15, spaceAfter=1)
    CO = ParagraphStyle('co', fontName='Helvetica',         fontSize=9,  textColor=MID,  leading=13)
    SH = ParagraphStyle('sh', fontName='Helvetica-Bold',    fontSize=10, textColor=BLK,  leading=14, spaceBefore=10, spaceAfter=2)
    PN = ParagraphStyle('pn', fontName='Helvetica',         fontSize=10, textColor=DRK,  leading=14, spaceAfter=2)
    PB = ParagraphStyle('pb', fontName='Helvetica',         fontSize=10, textColor=DRK,  leading=14)
    BD = ParagraphStyle('bd', fontName='Helvetica-Bold',    fontSize=10, textColor=BLK,  leading=14)
    MU = ParagraphStyle('mu', fontName='Helvetica',         fontSize=9,  textColor=MID,  leading=13)
    AC = ParagraphStyle('ac', fontName='Helvetica',         fontSize=9,  textColor=MID,  leading=13, alignment=TA_RIGHT)
    SK = ParagraphStyle('sk', fontName='Helvetica',         fontSize=10, textColor=DRK,  leading=14)

    story = []
    story.append(Paragraph(_get(ss,'name') or 'Your Name', NM))
    if _get(ss,'job_title'): story.append(Paragraph(_get(ss,'job_title'), JT))
    cp = _contact_line(ss, ' | ')
    if cp: story.append(Paragraph(cp, CO))
    story.append(HRFlowable(width=W, thickness=1.5, color=BLK, spaceBefore=6, spaceAfter=8))

    def sec(title):
        story.append(Paragraph(title.upper(), SH))
        story.append(HRFlowable(width=W, thickness=0.5, color=BLK, spaceAfter=4))

    sm = _get(ss,'summary')
    if sm:
        sec("Summary")
        for f in _bullets(sm, PN, PB, BLK): story.append(f)
        story.append(Spacer(1,4))

    exps = [e for e in _entries(ss,'experience_entries') if e.get('company') or e.get('title')]
    if exps:
        sec("Work Experience")
        for e in exps:
            story.append(_row2(Paragraph(f"<b>{e.get('title','')}</b>, {e.get('company','')}", BD),
                               Paragraph(e.get('duration',''), AC), W))
            for f in _bullets(e.get('description',''), PN, PB, BLK): story.append(f)
            story.append(Spacer(1,6))

    edus = [e for e in _entries(ss,'education_entries') if e.get('institution') or e.get('degree')]
    if edus:
        sec("Education")
        for e in edus:
            story.append(_row2(Paragraph(f"<b>{_deg(e)}</b>, {e.get('institution','')}", BD),
                               Paragraph(e.get('year',''), AC), W))
            if e.get('details'): story.append(Paragraph(e['details'], MU))
            story.append(Spacer(1,4))

    for field, label in [('skills','Technical Skills'),('Softskills','Soft Skills'),
                          ('languages','Languages'),('interests','Interests')]:
        v = _get(ss, field)
        if v:
            sec(label)
            story.append(Paragraph(v, SK))
            story.append(Spacer(1,4))

    projs = [p for p in _entries(ss,'project_entries') if p.get('title')]
    proj_links = _entries(ss,'project_links')
    if projs:
        sec("Projects")
        for i, p in enumerate(projs):
            lnk = proj_links[i] if i < len(proj_links) else ''
            t = _link(lnk, p.get('title',''), '#000000') if lnk else p.get('title','')
            story.append(Paragraph(f"<b>{t}</b>  |  {p.get('tech','')}", BD))
            for f in _bullets(p.get('description',''), PN, PB, BLK): story.append(f)
            story.append(Spacer(1,5))

    certs = [c for c in _entries(ss,'certificate_links') if c.get('name')]
    if certs:
        sec("Certifications")
        for c in certs:
            nm = _link(c.get('link',''), c.get('name',''), '#000000') if c.get('link') else c.get('name','')
            story.append(_row2(Paragraph(nm, BD), Paragraph(c.get('duration',''), AC), W))
            if c.get('description'): story.append(Paragraph(c['description'], MU))
            story.append(Spacer(1,4))

    doc.build(story); buf.seek(0); return buf


# ─── T11 · Indigo Tech ───────────────────────────────────────────────────────
# Tech-focused indigo palette — inspired by Canva "Athens". Large bold name,
# indigo accent fills for section labels, skills as compact grids.
def render_template_indigo_tech(session_state, profile_img_bytes=None):
    ss = session_state
    IND   = colors.HexColor('#3730a3')
    INDLT = colors.HexColor('#eef2ff')
    INDBD = colors.HexColor('#a5b4fc')
    DARK  = colors.HexColor('#1e1b4b')
    MID   = colors.HexColor('#6b7280')
    buf = BytesIO(); W = PAGE_W - 2*MARGIN
    doc = _new_doc(buf)

    NM = ParagraphStyle('nm', fontName='Helvetica-Bold',    fontSize=24, textColor=DARK,  leading=30)
    JT = ParagraphStyle('jt', fontName='Helvetica',         fontSize=12, textColor=IND,   leading=16, spaceAfter=2)
    CO = ParagraphStyle('co', fontName='Helvetica',         fontSize=9,  textColor=MID,   leading=13)
    SH = ParagraphStyle('sh', fontName='Helvetica-Bold',    fontSize=9,  textColor=IND,   leading=13)
    PN = ParagraphStyle('pn', fontName='Helvetica',         fontSize=10, textColor=DARK,  leading=14, spaceAfter=2)
    PB = ParagraphStyle('pb', fontName='Helvetica',         fontSize=10, textColor=DARK,  leading=14)
    BD = ParagraphStyle('bd', fontName='Helvetica-Bold',    fontSize=10, textColor=DARK,  leading=14)
    MU = ParagraphStyle('mu', fontName='Helvetica',         fontSize=9,  textColor=MID,   leading=13)
    AC = ParagraphStyle('ac', fontName='Helvetica-Bold',    fontSize=9,  textColor=IND,   leading=13)

    story = []
    iv = _img(profile_img_bytes, 70)
    name_b = [Paragraph(_get(ss,'name') or 'Your Name', NM)]
    if _get(ss,'job_title'): name_b.append(Paragraph(_get(ss,'job_title'), JT))
    cp = _contact_line(ss,'  ·  ')
    if cp: name_b.append(Paragraph(cp, CO))

    if iv:
        hdr = Table([[name_b, iv]], colWidths=[W-78, 78])
        hdr.setStyle(TableStyle([('VALIGN',(0,0),(-1,-1),'MIDDLE'),
                                  ('LEFTPADDING',(0,0),(-1,-1),0),
                                  ('RIGHTPADDING',(0,0),(-1,-1),0)]))
        story.append(hdr)
    else:
        for b in name_b: story.append(b)
    story.append(_accent_bar(W, IND, height=2.5, space_before=8, space_after=10))

    def sec(title):
        t = _section_header_box(title.upper(), SH, W, INDLT, IND)
        story.append(t)
        story.append(Spacer(1, 6))

    sm = _get(ss,'summary')
    if sm:
        sec("Summary")
        for f in _bullets(sm, PN, PB, IND): story.append(f)
        story.append(Spacer(1,4))

    exps = [e for e in _entries(ss,'experience_entries') if e.get('company') or e.get('title')]
    if exps:
        sec("Work Experience")
        for e in exps:
            story.append(_row2(Paragraph(f"<b>{e.get('title','')}</b>  ·  {e.get('company','')}", BD),
                               Paragraph(e.get('duration',''), AC), W))
            for f in _bullets(e.get('description',''), PN, PB, IND): story.append(f)
            story.append(Spacer(1,7))

    edus = [e for e in _entries(ss,'education_entries') if e.get('institution') or e.get('degree')]
    if edus:
        sec("Education")
        for e in edus:
            story.append(_row2(Paragraph(f"<b>{_deg(e)}</b>  ·  {e.get('institution','')}", BD),
                               Paragraph(e.get('year',''), AC), W))
            if e.get('details'): story.append(Paragraph(e['details'], MU))
            story.append(Spacer(1,5))

    for field, label in [('skills','Technical Skills'),('Softskills','Soft Skills'),
                          ('languages','Languages'),('interests','Interests')]:
        v = _get(ss, field)
        if v:
            sec(label)
            story.extend(_pills(v, INDLT, IND, INDBD, W))

    projs = [p for p in _entries(ss,'project_entries') if p.get('title')]
    proj_links = _entries(ss,'project_links')
    if projs:
        sec("Projects")
        for i, p in enumerate(projs):
            lnk = proj_links[i] if i < len(proj_links) else ''
            t = _link(lnk, p.get('title',''), '#3730a3') if lnk else p.get('title','')
            story.append(Paragraph(f"<b>{t}</b>  ·  <font color='#6b7280'>{p.get('tech','')}</font>", PN))
            for f in _bullets(p.get('description',''), PN, PB, IND): story.append(f)
            story.append(Spacer(1,6))

    certs = [c for c in _entries(ss,'certificate_links') if c.get('name')]
    if certs:
        sec("Certifications")
        for c in certs:
            nm = _link(c.get('link',''), c.get('name',''), '#3730a3') if c.get('link') else c.get('name','')
            story.append(_row2(Paragraph(nm, BD), Paragraph(c.get('duration',''), AC), W))
            if c.get('description'): story.append(Paragraph(c['description'], MU))
            story.append(Spacer(1,4))

    doc.build(story); buf.seek(0); return buf


# ─── T12 · Forest Executive ──────────────────────────────────────────────────
# Deep forest green — eco/sustainability/finance feel. Two-tone header with
# forest banner, white name, sage accent lines, cream skill pills.
def render_template_forest_executive(session_state, profile_img_bytes=None):
    ss = session_state
    FOREST = colors.HexColor('#14532d')
    FLTG   = colors.HexColor('#dcfce7')
    FMID   = colors.HexColor('#86efac')
    DARK   = colors.HexColor('#0f1a0f')
    MID    = colors.HexColor('#4b7563')
    SAGE   = colors.HexColor('#4ade80')
    buf = BytesIO(); W = PAGE_W - 2*MARGIN
    doc = _new_doc(buf)

    NM = ParagraphStyle('nm', fontName='Helvetica-Bold',    fontSize=23, textColor=colors.white, leading=29)
    JT = ParagraphStyle('jt', fontName='Helvetica',         fontSize=11, textColor=FLTG,         leading=15)
    CO = ParagraphStyle('co', fontName='Helvetica',         fontSize=9,  textColor=colors.HexColor('#bbf7d0'), leading=13)
    SH = ParagraphStyle('sh', fontName='Helvetica-Bold',    fontSize=10, textColor=FOREST,        leading=14, spaceBefore=12, spaceAfter=3)
    PN = ParagraphStyle('pn', fontName='Helvetica',         fontSize=10, textColor=DARK,          leading=14, spaceAfter=2)
    PB = ParagraphStyle('pb', fontName='Helvetica',         fontSize=10, textColor=DARK,          leading=14)
    BD = ParagraphStyle('bd', fontName='Helvetica-Bold',    fontSize=10, textColor=FOREST,        leading=14)
    MU = ParagraphStyle('mu', fontName='Helvetica',         fontSize=9,  textColor=MID,           leading=13)
    AC = ParagraphStyle('ac', fontName='Helvetica-Bold',    fontSize=9,  textColor=FOREST,        leading=13)

    story = []
    iv = _img(profile_img_bytes, 68)
    hdr_text = [Paragraph(_get(ss,'name') or 'Your Name', NM)]
    if _get(ss,'job_title'): hdr_text.append(Paragraph(_get(ss,'job_title'), JT))
    cp = _contact_line(ss,'  ·  ')
    if cp: hdr_text.append(Paragraph(cp, CO))

    if iv:
        hdr_t = Table([[hdr_text, iv]], colWidths=[W-78, 78])
    else:
        hdr_t = Table([[hdr_text]], colWidths=[W])
    hdr_t.setStyle(TableStyle([('BACKGROUND',(0,0),(-1,-1),FOREST),
                                ('VALIGN',(0,0),(-1,-1),'MIDDLE'),
                                ('TOPPADDING',(0,0),(-1,-1),12),
                                ('BOTTOMPADDING',(0,0),(-1,-1),12),
                                ('LEFTPADDING',(0,0),(-1,-1),14),
                                ('RIGHTPADDING',(0,0),(-1,-1),14)]))
    story.append(hdr_t)
    story.append(_accent_bar(W, SAGE, height=3, space_before=0, space_after=10))

    def sec(title):
        story.append(Paragraph(title, SH))
        story.append(HRFlowable(width=W, thickness=1, color=FMID, spaceAfter=5))

    sm = _get(ss,'summary')
    if sm:
        sec("Professional Summary")
        for f in _bullets(sm, PN, PB, FOREST): story.append(f)
        story.append(Spacer(1,4))

    exps = [e for e in _entries(ss,'experience_entries') if e.get('company') or e.get('title')]
    if exps:
        sec("Work Experience")
        for e in exps:
            story.append(_row2(Paragraph(f"<b>{e.get('title','')}</b>  ·  {e.get('company','')}", BD),
                               Paragraph(e.get('duration',''), AC), W))
            for f in _bullets(e.get('description',''), PN, PB, FOREST): story.append(f)
            story.append(Spacer(1,7))

    edus = [e for e in _entries(ss,'education_entries') if e.get('institution') or e.get('degree')]
    if edus:
        sec("Education")
        for e in edus:
            story.append(_row2(Paragraph(f"<b>{_deg(e)}</b>  ·  {e.get('institution','')}", BD),
                               Paragraph(e.get('year',''), AC), W))
            if e.get('details'): story.append(Paragraph(e['details'], MU))
            story.append(Spacer(1,5))

    for field, label in [('skills','Skills'),('Softskills','Soft Skills'),
                          ('languages','Languages'),('interests','Interests')]:
        v = _get(ss, field)
        if v:
            sec(label)
            story.extend(_pills(v, FLTG, FOREST, FMID, W))

    projs = [p for p in _entries(ss,'project_entries') if p.get('title')]
    proj_links = _entries(ss,'project_links')
    if projs:
        sec("Projects")
        for i, p in enumerate(projs):
            lnk = proj_links[i] if i < len(proj_links) else ''
            t = _link(lnk, p.get('title',''), '#14532d') if lnk else p.get('title','')
            story.append(Paragraph(f"<b>{t}</b>  ·  <font color='#4b7563'>{p.get('tech','')}</font>", PN))
            for f in _bullets(p.get('description',''), PN, PB, FOREST): story.append(f)
            story.append(Spacer(1,6))

    certs = [c for c in _entries(ss,'certificate_links') if c.get('name')]
    if certs:
        sec("Certifications")
        for c in certs:
            nm = _link(c.get('link',''), c.get('name',''), '#14532d') if c.get('link') else c.get('name','')
            story.append(_row2(Paragraph(nm, BD), Paragraph(c.get('duration',''), AC), W))
            if c.get('description'): story.append(Paragraph(c['description'], MU))
            story.append(Spacer(1,4))

    doc.build(story); buf.seek(0); return buf


# ─── T13 · Plum Elegant ──────────────────────────────────────────────────────
# Muted plum-purple tone — editorial/media feel. Centered header with large
# name, double-rule dividers, clean body, skills in soft lavender pills.
def render_template_plum_elegant(session_state, profile_img_bytes=None):
    ss = session_state
    PLUM   = colors.HexColor('#6b21a8')
    PLUMLT = colors.HexColor('#f5f3ff')
    PLUMBD = colors.HexColor('#d8b4fe')
    DARK   = colors.HexColor('#1e1b4b')
    MID    = colors.HexColor('#7c7a9e')
    buf = BytesIO(); W = PAGE_W - 2*MARGIN
    doc = _new_doc(buf)

    NM = ParagraphStyle('nm', fontName='Helvetica-Bold',    fontSize=26, textColor=PLUM,  leading=32, alignment=TA_CENTER)
    JT = ParagraphStyle('jt', fontName='Helvetica-Oblique', fontSize=12, textColor=DARK,  leading=16, alignment=TA_CENTER, spaceAfter=2)
    CO = ParagraphStyle('co', fontName='Helvetica',         fontSize=9,  textColor=MID,   leading=13, alignment=TA_CENTER)
    SH = ParagraphStyle('sh', fontName='Helvetica-Bold',    fontSize=10, textColor=PLUM,  leading=14, spaceBefore=12, spaceAfter=3, alignment=TA_CENTER)
    PN = ParagraphStyle('pn', fontName='Helvetica',         fontSize=10, textColor=DARK,  leading=14, spaceAfter=2)
    PB = ParagraphStyle('pb', fontName='Helvetica',         fontSize=10, textColor=DARK,  leading=14)
    BD = ParagraphStyle('bd', fontName='Helvetica-Bold',    fontSize=10, textColor=DARK,  leading=14)
    MU = ParagraphStyle('mu', fontName='Helvetica',         fontSize=9,  textColor=MID,   leading=13)
    AC = ParagraphStyle('ac', fontName='Helvetica-Bold',    fontSize=9,  textColor=PLUM,  leading=13)

    story = []
    iv = _img(profile_img_bytes, 70)
    if iv:
        story.append(Table([[iv]], colWidths=[W]))
        story[-1].setStyle(TableStyle([('ALIGN',(0,0),(0,0),'CENTER'),
                                        ('TOPPADDING',(0,0),(-1,-1),0),
                                        ('BOTTOMPADDING',(0,0),(-1,-1),5)]))
    story.append(Paragraph(_get(ss,'name') or 'Your Name', NM))
    if _get(ss,'job_title'): story.append(Paragraph(_get(ss,'job_title'), JT))
    cp = _contact_line(ss,'  ·  ')
    if cp: story.append(Paragraph(cp, CO))
    story.append(HRFlowable(width=W, thickness=0.5, color=PLUMBD, spaceBefore=6, spaceAfter=2))
    story.append(HRFlowable(width=W, thickness=2, color=PLUM,   spaceBefore=0, spaceAfter=10))

    def sec(title):
        story.append(Paragraph(title.upper(), SH))
        story.append(HRFlowable(width=W*0.4, thickness=1.5, color=PLUM, spaceAfter=5,
                                 hAlign='CENTER'))

    sm = _get(ss,'summary')
    if sm:
        sec("Summary")
        for f in _bullets(sm, PN, PB, PLUM): story.append(f)
        story.append(Spacer(1,4))

    exps = [e for e in _entries(ss,'experience_entries') if e.get('company') or e.get('title')]
    if exps:
        sec("Work Experience")
        for e in exps:
            story.append(_row2(Paragraph(f"<b>{e.get('title','')}</b>  ·  {e.get('company','')}", BD),
                               Paragraph(e.get('duration',''), AC), W))
            for f in _bullets(e.get('description',''), PN, PB, PLUM): story.append(f)
            story.append(Spacer(1,7))

    edus = [e for e in _entries(ss,'education_entries') if e.get('institution') or e.get('degree')]
    if edus:
        sec("Education")
        for e in edus:
            story.append(_row2(Paragraph(f"<b>{_deg(e)}</b>  ·  {e.get('institution','')}", BD),
                               Paragraph(e.get('year',''), AC), W))
            if e.get('details'): story.append(Paragraph(e['details'], MU))
            story.append(Spacer(1,5))

    for field, label in [('skills','Skills'),('Softskills','Soft Skills'),
                          ('languages','Languages'),('interests','Interests')]:
        v = _get(ss, field)
        if v:
            sec(label)
            story.extend(_pills(v, PLUMLT, PLUM, PLUMBD, W))

    projs = [p for p in _entries(ss,'project_entries') if p.get('title')]
    proj_links = _entries(ss,'project_links')
    if projs:
        sec("Projects")
        for i, p in enumerate(projs):
            lnk = proj_links[i] if i < len(proj_links) else ''
            t = _link(lnk, p.get('title',''), '#6b21a8') if lnk else p.get('title','')
            story.append(Paragraph(f"<b>{t}</b>  ·  <font color='#7c7a9e'>{p.get('tech','')}</font>", PN))
            for f in _bullets(p.get('description',''), PN, PB, PLUM): story.append(f)
            story.append(Spacer(1,6))

    certs = [c for c in _entries(ss,'certificate_links') if c.get('name')]
    if certs:
        sec("Certifications")
        for c in certs:
            nm = _link(c.get('link',''), c.get('name',''), '#6b21a8') if c.get('link') else c.get('name','')
            story.append(_row2(Paragraph(nm, BD), Paragraph(c.get('duration',''), AC), W))
            if c.get('description'): story.append(Paragraph(c['description'], MU))
            story.append(Spacer(1,4))

    doc.build(story); buf.seek(0); return buf


# ─── T14 · Copper Warm ───────────────────────────────────────────────────────
# Warm copper/terracotta — hospitality/design/HR look. Warm header, copper
# dividers, skills as warm-tinted pills, cozy professional atmosphere.
def render_template_copper_warm(session_state, profile_img_bytes=None):
    ss = session_state
    COP   = colors.HexColor('#92400e')
    COPLT = colors.HexColor('#fef3c7')
    COPBD = colors.HexColor('#fbbf24')
    BRICK = colors.HexColor('#c2410c')
    DARK  = colors.HexColor('#1c1412')
    MID   = colors.HexColor('#78716c')
    buf = BytesIO(); W = PAGE_W - 2*MARGIN
    doc = _new_doc(buf)

    NM = ParagraphStyle('nm', fontName='Helvetica-Bold',    fontSize=24, textColor=COP,   leading=30)
    JT = ParagraphStyle('jt', fontName='Helvetica-Oblique', fontSize=12, textColor=BRICK, leading=16, spaceAfter=2)
    CO = ParagraphStyle('co', fontName='Helvetica',         fontSize=9,  textColor=MID,   leading=13)
    SH = ParagraphStyle('sh', fontName='Helvetica-Bold',    fontSize=10, textColor=COP,   leading=14, spaceBefore=12, spaceAfter=3)
    PN = ParagraphStyle('pn', fontName='Helvetica',         fontSize=10, textColor=DARK,  leading=14, spaceAfter=2)
    PB = ParagraphStyle('pb', fontName='Helvetica',         fontSize=10, textColor=DARK,  leading=14)
    BD = ParagraphStyle('bd', fontName='Helvetica-Bold',    fontSize=10, textColor=COP,   leading=14)
    MU = ParagraphStyle('mu', fontName='Helvetica',         fontSize=9,  textColor=MID,   leading=13)
    AC = ParagraphStyle('ac', fontName='Helvetica-Bold',    fontSize=9,  textColor=BRICK, leading=13)

    story = []
    iv = _img(profile_img_bytes, 72)
    name_b = [Paragraph(_get(ss,'name') or 'Your Name', NM)]
    if _get(ss,'job_title'): name_b.append(Paragraph(_get(ss,'job_title'), JT))
    cp = _contact_line(ss,'  ·  ')
    if cp: name_b.append(Paragraph(cp, CO))

    if iv:
        hdr = Table([[name_b, iv]], colWidths=[W-80, 80])
        hdr.setStyle(TableStyle([('VALIGN',(0,0),(-1,-1),'MIDDLE'),
                                  ('LEFTPADDING',(0,0),(-1,-1),0),
                                  ('RIGHTPADDING',(0,0),(-1,-1),0)]))
        story.append(hdr)
    else:
        for b in name_b: story.append(b)

    story.append(HRFlowable(width=W, thickness=0.5, color=COPBD, spaceBefore=6, spaceAfter=2))
    story.append(HRFlowable(width=W, thickness=2.5, color=COP,   spaceBefore=0, spaceAfter=10))

    def sec(title):
        story.append(Paragraph(title, SH))
        story.append(HRFlowable(width=W, thickness=1, color=COPBD, spaceAfter=5))

    sm = _get(ss,'summary')
    if sm:
        sec("Professional Summary")
        for f in _bullets(sm, PN, PB, COP): story.append(f)
        story.append(Spacer(1,4))

    exps = [e for e in _entries(ss,'experience_entries') if e.get('company') or e.get('title')]
    if exps:
        sec("Work Experience")
        for e in exps:
            story.append(_row2(Paragraph(f"<b>{e.get('title','')}</b>  ·  {e.get('company','')}", BD),
                               Paragraph(e.get('duration',''), AC), W))
            for f in _bullets(e.get('description',''), PN, PB, COP): story.append(f)
            story.append(Spacer(1,7))

    edus = [e for e in _entries(ss,'education_entries') if e.get('institution') or e.get('degree')]
    if edus:
        sec("Education")
        for e in edus:
            story.append(_row2(Paragraph(f"<b>{_deg(e)}</b>  ·  {e.get('institution','')}", BD),
                               Paragraph(e.get('year',''), AC), W))
            if e.get('details'): story.append(Paragraph(e['details'], MU))
            story.append(Spacer(1,5))

    for field, label in [('skills','Skills'),('Softskills','Soft Skills'),
                          ('languages','Languages'),('interests','Interests')]:
        v = _get(ss, field)
        if v:
            sec(label)
            story.extend(_pills(v, COPLT, COP, COPBD, W))

    projs = [p for p in _entries(ss,'project_entries') if p.get('title')]
    proj_links = _entries(ss,'project_links')
    if projs:
        sec("Projects")
        for i, p in enumerate(projs):
            lnk = proj_links[i] if i < len(proj_links) else ''
            t = _link(lnk, p.get('title',''), '#92400e') if lnk else p.get('title','')
            story.append(Paragraph(f"<b>{t}</b>  ·  <font color='#78716c'>{p.get('tech','')}</font>", PN))
            for f in _bullets(p.get('description',''), PN, PB, COP): story.append(f)
            story.append(Spacer(1,6))

    certs = [c for c in _entries(ss,'certificate_links') if c.get('name')]
    if certs:
        sec("Certifications")
        for c in certs:
            nm = _link(c.get('link',''), c.get('name',''), '#92400e') if c.get('link') else c.get('name','')
            story.append(_row2(Paragraph(nm, BD), Paragraph(c.get('duration',''), AC), W))
            if c.get('description'): story.append(Paragraph(c['description'], MU))
            story.append(Spacer(1,4))

    doc.build(story); buf.seek(0); return buf


# ─── T15 · Sky Corporate ─────────────────────────────────────────────────────
# Light sky blue corporate — airy, open, professional. Pale sky header strip,
# blue-gray section text, neat horizontal layout, great for finance/consulting.
def render_template_sky_corporate(session_state, profile_img_bytes=None):
    ss = session_state
    SKY   = colors.HexColor('#0284c7')
    SKYLT = colors.HexColor('#e0f2fe')
    SKYBD = colors.HexColor('#7dd3fc')
    DARK  = colors.HexColor('#0c2340')
    MID   = colors.HexColor('#64748b')
    buf = BytesIO(); W = PAGE_W - 2*MARGIN
    doc = _new_doc(buf)

    NM = ParagraphStyle('nm', fontName='Helvetica-Bold',    fontSize=22, textColor=DARK,  leading=28)
    JT = ParagraphStyle('jt', fontName='Helvetica',         fontSize=12, textColor=SKY,   leading=16, spaceAfter=2)
    CO = ParagraphStyle('co', fontName='Helvetica',         fontSize=9,  textColor=MID,   leading=13)
    SH = ParagraphStyle('sh', fontName='Helvetica-Bold',    fontSize=10, textColor=DARK,  leading=14, spaceBefore=12, spaceAfter=3)
    PN = ParagraphStyle('pn', fontName='Helvetica',         fontSize=10, textColor=DARK,  leading=14, spaceAfter=2)
    PB = ParagraphStyle('pb', fontName='Helvetica',         fontSize=10, textColor=DARK,  leading=14)
    BD = ParagraphStyle('bd', fontName='Helvetica-Bold',    fontSize=10, textColor=DARK,  leading=14)
    MU = ParagraphStyle('mu', fontName='Helvetica',         fontSize=9,  textColor=MID,   leading=13)
    AC = ParagraphStyle('ac', fontName='Helvetica-Bold',    fontSize=9,  textColor=SKY,   leading=13)

    story = []
    # Header band with sky-light background
    iv = _img(profile_img_bytes, 68)
    hdr_text = [Paragraph(_get(ss,'name') or 'Your Name', NM)]
    if _get(ss,'job_title'): hdr_text.append(Paragraph(_get(ss,'job_title'), JT))
    cp = _contact_line(ss,'  ·  ')
    if cp: hdr_text.append(Paragraph(cp, CO))

    if iv:
        hdr_t = Table([[hdr_text, iv]], colWidths=[W-78, 78])
    else:
        hdr_t = Table([[hdr_text]], colWidths=[W])
    hdr_t.setStyle(TableStyle([('BACKGROUND',(0,0),(-1,-1),SKYLT),
                                ('VALIGN',(0,0),(-1,-1),'MIDDLE'),
                                ('TOPPADDING',(0,0),(-1,-1),12),
                                ('BOTTOMPADDING',(0,0),(-1,-1),12),
                                ('LEFTPADDING',(0,0),(-1,-1),14),
                                ('RIGHTPADDING',(0,0),(-1,-1),14)]))
    story.append(hdr_t)
    story.append(_accent_bar(W, SKY, height=3, space_before=0, space_after=10))

    def sec(title):
        story.append(Paragraph(title.upper(), SH))
        story.append(HRFlowable(width=W, thickness=0.7, color=SKYBD, spaceAfter=5))

    sm = _get(ss,'summary')
    if sm:
        sec("Professional Summary")
        for f in _bullets(sm, PN, PB, SKY): story.append(f)
        story.append(Spacer(1,4))

    exps = [e for e in _entries(ss,'experience_entries') if e.get('company') or e.get('title')]
    if exps:
        sec("Work Experience")
        for e in exps:
            story.append(_row2(Paragraph(f"<b>{e.get('title','')}</b>  ·  {e.get('company','')}", BD),
                               Paragraph(e.get('duration',''), AC), W))
            for f in _bullets(e.get('description',''), PN, PB, SKY): story.append(f)
            story.append(Spacer(1,7))

    edus = [e for e in _entries(ss,'education_entries') if e.get('institution') or e.get('degree')]
    if edus:
        sec("Education")
        for e in edus:
            story.append(_row2(Paragraph(f"<b>{_deg(e)}</b>  ·  {e.get('institution','')}", BD),
                               Paragraph(e.get('year',''), AC), W))
            if e.get('details'): story.append(Paragraph(e['details'], MU))
            story.append(Spacer(1,5))

    for field, label in [('skills','Technical Skills'),('Softskills','Soft Skills'),
                          ('languages','Languages'),('interests','Interests')]:
        v = _get(ss, field)
        if v:
            sec(label)
            story.extend(_pills(v, SKYLT, DARK, SKYBD, W))

    projs = [p for p in _entries(ss,'project_entries') if p.get('title')]
    proj_links = _entries(ss,'project_links')
    if projs:
        sec("Projects")
        for i, p in enumerate(projs):
            lnk = proj_links[i] if i < len(proj_links) else ''
            t = _link(lnk, p.get('title',''), '#0284c7') if lnk else p.get('title','')
            story.append(Paragraph(f"<b>{t}</b>  ·  <font color='#64748b'>{p.get('tech','')}</font>", PN))
            for f in _bullets(p.get('description',''), PN, PB, SKY): story.append(f)
            story.append(Spacer(1,6))

    certs = [c for c in _entries(ss,'certificate_links') if c.get('name')]
    if certs:
        sec("Certifications")
        for c in certs:
            nm = _link(c.get('link',''), c.get('name',''), '#0284c7') if c.get('link') else c.get('name','')
            story.append(_row2(Paragraph(nm, BD), Paragraph(c.get('duration',''), AC), W))
            if c.get('description'): story.append(Paragraph(c['description'], MU))
            story.append(Spacer(1,4))

    doc.build(story); buf.seek(0); return buf


# ═════════════════════════════════════════════════════════════════════════════
# DOUBLE-COLUMN TEMPLATES  (6 total)
# ═════════════════════════════════════════════════════════════════════════════

# ─── D01 · Midnight Sidebar ──────────────────────────────────────────────────
# Dark midnight-blue sidebar (photo + contact + skills), white main area.
# Inspired by Enhancv "Tokyo" — striking contrast, dot-bars for skills.
def render_template_midnight_sidebar(session_state, profile_img_bytes=None):
    ss = session_state
    NIGHT = colors.HexColor('#0f172a')
    NTLT  = colors.HexColor('#1e293b')
    NTML  = colors.HexColor('#334155')
    ACC   = colors.HexColor('#38bdf8')
    DARK  = colors.HexColor('#0f172a')
    MID   = colors.HexColor('#6b7280')
    WHT   = colors.white
    buf = BytesIO()
    SW = SIDEBAR_W

    # Sidebar styles
    sbN = ParagraphStyle('sbN', fontName='Helvetica-Bold',    fontSize=13, textColor=WHT,  leading=17, alignment=TA_CENTER, spaceAfter=2)
    sbT = ParagraphStyle('sbT', fontName='Helvetica-Oblique', fontSize=9,  textColor=ACC,  leading=13, alignment=TA_CENTER, spaceAfter=4)
    sbS = ParagraphStyle('sbS', fontName='Helvetica-Bold',    fontSize=8,  textColor=ACC,  leading=12, spaceBefore=10, spaceAfter=3)
    sbI = ParagraphStyle('sbI', fontName='Helvetica',         fontSize=8,  textColor=colors.HexColor('#cbd5e1'), leading=12, spaceAfter=2)
    sbP = ParagraphStyle('sbP', fontName='Helvetica',         fontSize=8,  textColor=WHT,  alignment=TA_CENTER, leading=11)
    # Main styles
    mSH = ParagraphStyle('mSH', fontName='Helvetica-Bold',    fontSize=11, textColor=NIGHT, leading=15, spaceBefore=10, spaceAfter=3)
    mPN = ParagraphStyle('mPN', fontName='Helvetica',         fontSize=10, textColor=DARK,  leading=14, spaceAfter=2)
    mPB = ParagraphStyle('mPB', fontName='Helvetica',         fontSize=10, textColor=DARK,  leading=14)
    mBD = ParagraphStyle('mBD', fontName='Helvetica-Bold',    fontSize=10, textColor=NIGHT, leading=14)
    mMU = ParagraphStyle('mMU', fontName='Helvetica',         fontSize=9,  textColor=MID,   leading=13)
    mAC = ParagraphStyle('mAC', fontName='Helvetica-Bold',    fontSize=9,  textColor=ACC,   leading=13)
    MW = PAGE_W - MARGIN - SW - 14 - MARGIN

    sb, mn = [], []

    # — Sidebar content
    iv = _img(profile_img_bytes, 80)
    if iv:
        sb.append(Table([[iv]], colWidths=[SW-14]))
        sb[-1].setStyle(TableStyle([('ALIGN',(0,0),(0,0),'CENTER'),
                                     ('TOPPADDING',(0,0),(-1,-1),4),
                                     ('BOTTOMPADDING',(0,0),(-1,-1),6)]))
    sb.append(Paragraph(_get(ss,'name') or 'Your Name', sbN))
    if _get(ss,'job_title'): sb.append(Paragraph(_get(ss,'job_title'), sbT))
    sb.append(HRFlowable(width=SW-16, thickness=1, color=ACC, spaceBefore=4, spaceAfter=6))

    def sb_sec(title): sb.append(Paragraph(title.upper(), sbS))

    sb_sec("Contact")
    for k in ['email','phone','location','linkedin','github','portfolio']:
        v = _get(ss, k)
        if v: sb.append(Paragraph(v, sbI))

    for field, label in [('skills','Technical Skills'),('Softskills','Soft Skills'),
                          ('languages','Languages'),('interests','Interests')]:
        v = _get(ss, field)
        if v:
            sb_sec(label)
            for sk in _skills_list(v):
                pill = Table([[Paragraph(sk, sbP)]], colWidths=[SW-20])
                pill.setStyle(TableStyle([('BACKGROUND',(0,0),(0,0),NTLT),
                                           ('TOPPADDING',(0,0),(-1,-1),2),
                                           ('BOTTOMPADDING',(0,0),(-1,-1),2),
                                           ('LEFTPADDING',(0,0),(-1,-1),4),
                                           ('RIGHTPADDING',(0,0),(-1,-1),4)]))
                sb.append(pill)
                sb.append(Spacer(1,2))

    # — Main content
    def mn_sec(title):
        mn.append(Paragraph(title, mSH))
        mn.append(HRFlowable(width=MW, thickness=2, color=ACC, spaceAfter=5))

    sm = _get(ss,'summary')
    if sm:
        mn_sec("Professional Summary")
        for f in _bullets(sm, mPN, mPB, ACC): mn.append(f)
        mn.append(Spacer(1,4))

    exps = [e for e in _entries(ss,'experience_entries') if e.get('company') or e.get('title')]
    if exps:
        mn_sec("Work Experience")
        for e in exps:
            mn.append(_row2(Paragraph(f"<b>{e.get('title','')}</b>  ·  {e.get('company','')}", mBD),
                            Paragraph(e.get('duration',''), mAC), MW))
            for f in _bullets(e.get('description',''), mPN, mPB, ACC): mn.append(f)
            mn.append(Spacer(1,7))

    edus = [e for e in _entries(ss,'education_entries') if e.get('institution') or e.get('degree')]
    if edus:
        mn_sec("Education")
        for e in edus:
            mn.append(_row2(Paragraph(f"<b>{_deg(e)}</b>  ·  {e.get('institution','')}", mBD),
                            Paragraph(e.get('year',''), mAC), MW))
            if e.get('details'): mn.append(Paragraph(e['details'], mMU))
            mn.append(Spacer(1,5))

    projs = [p for p in _entries(ss,'project_entries') if p.get('title')]
    proj_links = _entries(ss,'project_links')
    if projs:
        mn_sec("Projects")
        for i, p in enumerate(projs):
            lnk = proj_links[i] if i < len(proj_links) else ''
            t = _link(lnk, p.get('title',''), '#38bdf8') if lnk else p.get('title','')
            mn.append(Paragraph(f"<b>{t}</b>  ·  <font color='#6b7280'>{p.get('tech','')}</font>", mPN))
            for f in _bullets(p.get('description',''), mPN, mPB, ACC): mn.append(f)
            mn.append(Spacer(1,6))

    certs = [c for c in _entries(ss,'certificate_links') if c.get('name')]
    if certs:
        mn_sec("Certifications")
        for c in certs:
            nm = _link(c.get('link',''), c.get('name',''), '#38bdf8') if c.get('link') else c.get('name','')
            mn.append(_row2(Paragraph(nm, mBD), Paragraph(c.get('duration',''), mAC), MW))
            if c.get('description'): mn.append(Paragraph(c['description'], mMU))
            mn.append(Spacer(1,4))

    _two_col(buf, sb, mn, NIGHT, NTML)
    buf.seek(0); return buf


# ─── D02 · Sage Sidebar ──────────────────────────────────────────────────────
# Soft sage-green sidebar (Novoresume "Prague"-inspired) — calm, professional.
# Sidebar: white text on sage. Main: clean with sage accent lines.
def render_template_sage_sidebar(session_state, profile_img_bytes=None):
    ss = session_state
    SAGE  = colors.HexColor('#4d7c60')
    SAGLT = colors.HexColor('#e8f5ee')
    SAGBD = colors.HexColor('#a7d4b8')
    DARK  = colors.HexColor('#1a2e1f')
    MID   = colors.HexColor('#6b7280')
    WHT   = colors.white
    buf = BytesIO()
    SW = SIDEBAR_W
    MW = PAGE_W - MARGIN - SW - 14 - MARGIN

    sbN = ParagraphStyle('sbN', fontName='Helvetica-Bold',    fontSize=13, textColor=WHT,  leading=17, alignment=TA_CENTER, spaceAfter=2)
    sbT = ParagraphStyle('sbT', fontName='Helvetica-Oblique', fontSize=9,  textColor=SAGLT,leading=13, alignment=TA_CENTER, spaceAfter=4)
    sbS = ParagraphStyle('sbS', fontName='Helvetica-Bold',    fontSize=8,  textColor=SAGLT,leading=12, spaceBefore=10, spaceAfter=3)
    sbI = ParagraphStyle('sbI', fontName='Helvetica',         fontSize=8,  textColor=colors.HexColor('#d1fae5'), leading=12, spaceAfter=2)
    sbP = ParagraphStyle('sbP', fontName='Helvetica',         fontSize=8,  textColor=SAGE, alignment=TA_CENTER, leading=11)
    mSH = ParagraphStyle('mSH', fontName='Helvetica-Bold',    fontSize=11, textColor=SAGE,  leading=15, spaceBefore=10, spaceAfter=3)
    mPN = ParagraphStyle('mPN', fontName='Helvetica',         fontSize=10, textColor=DARK,  leading=14, spaceAfter=2)
    mPB = ParagraphStyle('mPB', fontName='Helvetica',         fontSize=10, textColor=DARK,  leading=14)
    mBD = ParagraphStyle('mBD', fontName='Helvetica-Bold',    fontSize=10, textColor=DARK,  leading=14)
    mMU = ParagraphStyle('mMU', fontName='Helvetica',         fontSize=9,  textColor=MID,   leading=13)
    mAC = ParagraphStyle('mAC', fontName='Helvetica-Bold',    fontSize=9,  textColor=SAGE,  leading=13)

    sb, mn = [], []

    iv = _img(profile_img_bytes, 76)
    if iv:
        sb.append(Table([[iv]], colWidths=[SW-14]))
        sb[-1].setStyle(TableStyle([('ALIGN',(0,0),(0,0),'CENTER'),
                                     ('TOPPADDING',(0,0),(-1,-1),4),
                                     ('BOTTOMPADDING',(0,0),(-1,-1),6)]))
    sb.append(Paragraph(_get(ss,'name') or 'Your Name', sbN))
    if _get(ss,'job_title'): sb.append(Paragraph(_get(ss,'job_title'), sbT))
    sb.append(HRFlowable(width=SW-16, thickness=1, color=SAGLT, spaceBefore=4, spaceAfter=6))

    def sb_sec(title): sb.append(Paragraph(title.upper(), sbS))

    sb_sec("Contact")
    for k in ['email','phone','location','linkedin','github','portfolio']:
        v = _get(ss, k)
        if v: sb.append(Paragraph(v, sbI))

    for field, label in [('skills','Skills'),('Softskills','Soft Skills'),
                          ('languages','Languages'),('interests','Interests')]:
        v = _get(ss, field)
        if v:
            sb_sec(label)
            for sk in _skills_list(v):
                pill = Table([[Paragraph(sk, sbP)]], colWidths=[SW-20])
                pill.setStyle(TableStyle([('BACKGROUND',(0,0),(0,0),SAGLT),
                                           ('TOPPADDING',(0,0),(-1,-1),2),
                                           ('BOTTOMPADDING',(0,0),(-1,-1),2),
                                           ('LEFTPADDING',(0,0),(-1,-1),4),
                                           ('RIGHTPADDING',(0,0),(-1,-1),4)]))
                sb.append(pill)
                sb.append(Spacer(1,2))

    def mn_sec(title):
        mn.append(Paragraph(title, mSH))
        mn.append(HRFlowable(width=MW, thickness=1.5, color=SAGBD, spaceAfter=5))

    sm = _get(ss,'summary')
    if sm:
        mn_sec("Professional Summary")
        for f in _bullets(sm, mPN, mPB, SAGE): mn.append(f)
        mn.append(Spacer(1,4))

    exps = [e for e in _entries(ss,'experience_entries') if e.get('company') or e.get('title')]
    if exps:
        mn_sec("Work Experience")
        for e in exps:
            mn.append(_row2(Paragraph(f"<b>{e.get('title','')}</b>  ·  {e.get('company','')}", mBD),
                            Paragraph(e.get('duration',''), mAC), MW))
            for f in _bullets(e.get('description',''), mPN, mPB, SAGE): mn.append(f)
            mn.append(Spacer(1,7))

    edus = [e for e in _entries(ss,'education_entries') if e.get('institution') or e.get('degree')]
    if edus:
        mn_sec("Education")
        for e in edus:
            mn.append(_row2(Paragraph(f"<b>{_deg(e)}</b>  ·  {e.get('institution','')}", mBD),
                            Paragraph(e.get('year',''), mAC), MW))
            if e.get('details'): mn.append(Paragraph(e['details'], mMU))
            mn.append(Spacer(1,5))

    projs = [p for p in _entries(ss,'project_entries') if p.get('title')]
    proj_links = _entries(ss,'project_links')
    if projs:
        mn_sec("Projects")
        for i, p in enumerate(projs):
            lnk = proj_links[i] if i < len(proj_links) else ''
            t = _link(lnk, p.get('title',''), '#4d7c60') if lnk else p.get('title','')
            mn.append(Paragraph(f"<b>{t}</b>  ·  <font color='#6b7280'>{p.get('tech','')}</font>", mPN))
            for f in _bullets(p.get('description',''), mPN, mPB, SAGE): mn.append(f)
            mn.append(Spacer(1,6))

    certs = [c for c in _entries(ss,'certificate_links') if c.get('name')]
    if certs:
        mn_sec("Certifications")
        for c in certs:
            nm = _link(c.get('link',''), c.get('name',''), '#4d7c60') if c.get('link') else c.get('name','')
            mn.append(_row2(Paragraph(nm, mBD), Paragraph(c.get('duration',''), mAC), MW))
            if c.get('description'): mn.append(Paragraph(c['description'], mMU))
            mn.append(Spacer(1,4))

    _two_col(buf, sb, mn, SAGE, colors.HexColor('#3a6048'))
    buf.seek(0); return buf


# ─── D03 · Royal Sidebar ─────────────────────────────────────────────────────
# Deep royal blue sidebar — classic executive two-column.
# Inspired by Canva "Nova" — royal blue + gold accent for prestige.
def render_template_royal_sidebar(session_state, profile_img_bytes=None):
    ss = session_state
    ROYAL = colors.HexColor('#1e3a8a')
    GOLD  = colors.HexColor('#d97706')
    RYLT  = colors.HexColor('#eff6ff')
    RYBD  = colors.HexColor('#93c5fd')
    DARK  = colors.HexColor('#0f172a')
    MID   = colors.HexColor('#64748b')
    WHT   = colors.white
    buf = BytesIO()
    SW = SIDEBAR_W
    MW = PAGE_W - MARGIN - SW - 14 - MARGIN

    sbN = ParagraphStyle('sbN', fontName='Helvetica-Bold',    fontSize=13, textColor=WHT,  leading=17, alignment=TA_CENTER, spaceAfter=2)
    sbT = ParagraphStyle('sbT', fontName='Helvetica-Oblique', fontSize=9,  textColor=RYLT, leading=13, alignment=TA_CENTER, spaceAfter=4)
    sbS = ParagraphStyle('sbS', fontName='Helvetica-Bold',    fontSize=8,  textColor=GOLD, leading=12, spaceBefore=10, spaceAfter=3)
    sbI = ParagraphStyle('sbI', fontName='Helvetica',         fontSize=8,  textColor=colors.HexColor('#bfdbfe'), leading=12, spaceAfter=2)
    sbP = ParagraphStyle('sbP', fontName='Helvetica',         fontSize=8,  textColor=ROYAL,alignment=TA_CENTER, leading=11)
    mSH = ParagraphStyle('mSH', fontName='Helvetica-Bold',    fontSize=11, textColor=ROYAL, leading=15, spaceBefore=10, spaceAfter=3)
    mPN = ParagraphStyle('mPN', fontName='Helvetica',         fontSize=10, textColor=DARK,  leading=14, spaceAfter=2)
    mPB = ParagraphStyle('mPB', fontName='Helvetica',         fontSize=10, textColor=DARK,  leading=14)
    mBD = ParagraphStyle('mBD', fontName='Helvetica-Bold',    fontSize=10, textColor=DARK,  leading=14)
    mMU = ParagraphStyle('mMU', fontName='Helvetica',         fontSize=9,  textColor=MID,   leading=13)
    mAC = ParagraphStyle('mAC', fontName='Helvetica-Bold',    fontSize=9,  textColor=GOLD,  leading=13)

    sb, mn = [], []
    iv = _img(profile_img_bytes, 76)
    if iv:
        sb.append(Table([[iv]], colWidths=[SW-14]))
        sb[-1].setStyle(TableStyle([('ALIGN',(0,0),(0,0),'CENTER'),
                                     ('TOPPADDING',(0,0),(-1,-1),4),
                                     ('BOTTOMPADDING',(0,0),(-1,-1),6)]))
    sb.append(Paragraph(_get(ss,'name') or 'Your Name', sbN))
    if _get(ss,'job_title'): sb.append(Paragraph(_get(ss,'job_title'), sbT))
    sb.append(HRFlowable(width=SW-16, thickness=1, color=GOLD, spaceBefore=4, spaceAfter=6))

    def sb_sec(title): sb.append(Paragraph(title.upper(), sbS))

    sb_sec("Contact")
    for k in ['email','phone','location','linkedin','github','portfolio']:
        v = _get(ss, k)
        if v: sb.append(Paragraph(v, sbI))

    for field, label in [('skills','Skills'),('Softskills','Soft Skills'),
                          ('languages','Languages'),('interests','Interests')]:
        v = _get(ss, field)
        if v:
            sb_sec(label)
            for sk in _skills_list(v):
                pill = Table([[Paragraph(sk, sbP)]], colWidths=[SW-20])
                pill.setStyle(TableStyle([('BACKGROUND',(0,0),(0,0),RYLT),
                                           ('TOPPADDING',(0,0),(-1,-1),2),
                                           ('BOTTOMPADDING',(0,0),(-1,-1),2),
                                           ('LEFTPADDING',(0,0),(-1,-1),4),
                                           ('RIGHTPADDING',(0,0),(-1,-1),4)]))
                sb.append(pill)
                sb.append(Spacer(1,2))

    def mn_sec(title):
        mn.append(Paragraph(title, mSH))
        mn.append(HRFlowable(width=MW, thickness=2, color=GOLD, spaceAfter=5))

    sm = _get(ss,'summary')
    if sm:
        mn_sec("Professional Summary")
        for f in _bullets(sm, mPN, mPB, GOLD): mn.append(f)
        mn.append(Spacer(1,4))

    exps = [e for e in _entries(ss,'experience_entries') if e.get('company') or e.get('title')]
    if exps:
        mn_sec("Work Experience")
        for e in exps:
            mn.append(_row2(Paragraph(f"<b>{e.get('title','')}</b>  ·  {e.get('company','')}", mBD),
                            Paragraph(e.get('duration',''), mAC), MW))
            for f in _bullets(e.get('description',''), mPN, mPB, GOLD): mn.append(f)
            mn.append(Spacer(1,7))

    edus = [e for e in _entries(ss,'education_entries') if e.get('institution') or e.get('degree')]
    if edus:
        mn_sec("Education")
        for e in edus:
            mn.append(_row2(Paragraph(f"<b>{_deg(e)}</b>  ·  {e.get('institution','')}", mBD),
                            Paragraph(e.get('year',''), mAC), MW))
            if e.get('details'): mn.append(Paragraph(e['details'], mMU))
            mn.append(Spacer(1,5))

    projs = [p for p in _entries(ss,'project_entries') if p.get('title')]
    proj_links = _entries(ss,'project_links')
    if projs:
        mn_sec("Projects")
        for i, p in enumerate(projs):
            lnk = proj_links[i] if i < len(proj_links) else ''
            t = _link(lnk, p.get('title',''), '#1e3a8a') if lnk else p.get('title','')
            mn.append(Paragraph(f"<b>{t}</b>  ·  <font color='#64748b'>{p.get('tech','')}</font>", mPN))
            for f in _bullets(p.get('description',''), mPN, mPB, GOLD): mn.append(f)
            mn.append(Spacer(1,6))

    certs = [c for c in _entries(ss,'certificate_links') if c.get('name')]
    if certs:
        mn_sec("Certifications")
        for c in certs:
            nm = _link(c.get('link',''), c.get('name',''), '#1e3a8a') if c.get('link') else c.get('name','')
            mn.append(_row2(Paragraph(nm, mBD), Paragraph(c.get('duration',''), mAC), MW))
            if c.get('description'): mn.append(Paragraph(c['description'], mMU))
            mn.append(Spacer(1,4))

    _two_col(buf, sb, mn, ROYAL, colors.HexColor('#162d6b'))
    buf.seek(0); return buf


# ─── D04 · Crimson Sidebar ───────────────────────────────────────────────────
# Bold crimson sidebar — confident, creative, standout.
# Inspired by VisualCV "Madrid" — high contrast, energetic.
def render_template_crimson_sidebar(session_state, profile_img_bytes=None):
    ss = session_state
    CRIM  = colors.HexColor('#991b1b')
    CRMLT = colors.HexColor('#fff5f5')
    CRMBD = colors.HexColor('#fca5a5')
    DARK  = colors.HexColor('#1c1917')
    MID   = colors.HexColor('#78716c')
    WHT   = colors.white
    buf = BytesIO()
    SW = SIDEBAR_W
    MW = PAGE_W - MARGIN - SW - 14 - MARGIN

    sbN = ParagraphStyle('sbN', fontName='Helvetica-Bold',    fontSize=13, textColor=WHT,  leading=17, alignment=TA_CENTER, spaceAfter=2)
    sbT = ParagraphStyle('sbT', fontName='Helvetica-Oblique', fontSize=9,  textColor=CRMLT,leading=13, alignment=TA_CENTER, spaceAfter=4)
    sbS = ParagraphStyle('sbS', fontName='Helvetica-Bold',    fontSize=8,  textColor=CRMLT,leading=12, spaceBefore=10, spaceAfter=3)
    sbI = ParagraphStyle('sbI', fontName='Helvetica',         fontSize=8,  textColor=colors.HexColor('#fecaca'), leading=12, spaceAfter=2)
    sbP = ParagraphStyle('sbP', fontName='Helvetica',         fontSize=8,  textColor=CRIM, alignment=TA_CENTER, leading=11)
    mSH = ParagraphStyle('mSH', fontName='Helvetica-Bold',    fontSize=11, textColor=CRIM,  leading=15, spaceBefore=10, spaceAfter=3)
    mPN = ParagraphStyle('mPN', fontName='Helvetica',         fontSize=10, textColor=DARK,  leading=14, spaceAfter=2)
    mPB = ParagraphStyle('mPB', fontName='Helvetica',         fontSize=10, textColor=DARK,  leading=14)
    mBD = ParagraphStyle('mBD', fontName='Helvetica-Bold',    fontSize=10, textColor=DARK,  leading=14)
    mMU = ParagraphStyle('mMU', fontName='Helvetica',         fontSize=9,  textColor=MID,   leading=13)
    mAC = ParagraphStyle('mAC', fontName='Helvetica-Bold',    fontSize=9,  textColor=CRIM,  leading=13)

    sb, mn = [], []
    iv = _img(profile_img_bytes, 76)
    if iv:
        sb.append(Table([[iv]], colWidths=[SW-14]))
        sb[-1].setStyle(TableStyle([('ALIGN',(0,0),(0,0),'CENTER'),
                                     ('TOPPADDING',(0,0),(-1,-1),4),
                                     ('BOTTOMPADDING',(0,0),(-1,-1),6)]))
    sb.append(Paragraph(_get(ss,'name') or 'Your Name', sbN))
    if _get(ss,'job_title'): sb.append(Paragraph(_get(ss,'job_title'), sbT))
    sb.append(HRFlowable(width=SW-16, thickness=1, color=CRMLT, spaceBefore=4, spaceAfter=6))

    def sb_sec(title): sb.append(Paragraph(title.upper(), sbS))
    sb_sec("Contact")
    for k in ['email','phone','location','linkedin','github','portfolio']:
        v = _get(ss, k)
        if v: sb.append(Paragraph(v, sbI))

    for field, label in [('skills','Skills'),('Softskills','Soft Skills'),
                          ('languages','Languages'),('interests','Interests')]:
        v = _get(ss, field)
        if v:
            sb_sec(label)
            for sk in _skills_list(v):
                pill = Table([[Paragraph(sk, sbP)]], colWidths=[SW-20])
                pill.setStyle(TableStyle([('BACKGROUND',(0,0),(0,0),CRMLT),
                                           ('TOPPADDING',(0,0),(-1,-1),2),
                                           ('BOTTOMPADDING',(0,0),(-1,-1),2),
                                           ('LEFTPADDING',(0,0),(-1,-1),4),
                                           ('RIGHTPADDING',(0,0),(-1,-1),4)]))
                sb.append(pill)
                sb.append(Spacer(1,2))

    def mn_sec(title):
        mn.append(Paragraph(title, mSH))
        mn.append(HRFlowable(width=MW, thickness=2, color=CRMBD, spaceAfter=5))

    sm = _get(ss,'summary')
    if sm:
        mn_sec("Summary")
        for f in _bullets(sm, mPN, mPB, CRIM): mn.append(f)
        mn.append(Spacer(1,4))

    exps = [e for e in _entries(ss,'experience_entries') if e.get('company') or e.get('title')]
    if exps:
        mn_sec("Work Experience")
        for e in exps:
            mn.append(_row2(Paragraph(f"<b>{e.get('title','')}</b>  ·  {e.get('company','')}", mBD),
                            Paragraph(e.get('duration',''), mAC), MW))
            for f in _bullets(e.get('description',''), mPN, mPB, CRIM): mn.append(f)
            mn.append(Spacer(1,7))

    edus = [e for e in _entries(ss,'education_entries') if e.get('institution') or e.get('degree')]
    if edus:
        mn_sec("Education")
        for e in edus:
            mn.append(_row2(Paragraph(f"<b>{_deg(e)}</b>  ·  {e.get('institution','')}", mBD),
                            Paragraph(e.get('year',''), mAC), MW))
            if e.get('details'): mn.append(Paragraph(e['details'], mMU))
            mn.append(Spacer(1,5))

    projs = [p for p in _entries(ss,'project_entries') if p.get('title')]
    proj_links = _entries(ss,'project_links')
    if projs:
        mn_sec("Projects")
        for i, p in enumerate(projs):
            lnk = proj_links[i] if i < len(proj_links) else ''
            t = _link(lnk, p.get('title',''), '#991b1b') if lnk else p.get('title','')
            mn.append(Paragraph(f"<b>{t}</b>  ·  <font color='#78716c'>{p.get('tech','')}</font>", mPN))
            for f in _bullets(p.get('description',''), mPN, mPB, CRIM): mn.append(f)
            mn.append(Spacer(1,6))

    certs = [c for c in _entries(ss,'certificate_links') if c.get('name')]
    if certs:
        mn_sec("Certifications")
        for c in certs:
            nm = _link(c.get('link',''), c.get('name',''), '#991b1b') if c.get('link') else c.get('name','')
            mn.append(_row2(Paragraph(nm, mBD), Paragraph(c.get('duration',''), mAC), MW))
            if c.get('description'): mn.append(Paragraph(c['description'], mMU))
            mn.append(Spacer(1,4))

    _two_col(buf, sb, mn, CRIM, colors.HexColor('#7f1d1d'))
    buf.seek(0); return buf


# ─── D05 · Charcoal Sidebar ──────────────────────────────────────────────────
# Deep charcoal sidebar with electric cyan accents — modern tech/startup feel.
# Inspired by Enhancv "Helsinki" — dark bg, bright accent, structured main.
def render_template_charcoal_sidebar(session_state, profile_img_bytes=None):
    ss = session_state
    CHAR  = colors.HexColor('#18181b')
    CYAN  = colors.HexColor('#06b6d4')
    CYANLT= colors.HexColor('#ecfeff')
    DARK  = colors.HexColor('#09090b')
    MID   = colors.HexColor('#6b7280')
    WHT   = colors.white
    buf = BytesIO()
    SW = SIDEBAR_W
    MW = PAGE_W - MARGIN - SW - 14 - MARGIN

    sbN = ParagraphStyle('sbN', fontName='Helvetica-Bold',    fontSize=13, textColor=WHT,  leading=17, alignment=TA_CENTER, spaceAfter=2)
    sbT = ParagraphStyle('sbT', fontName='Helvetica-Oblique', fontSize=9,  textColor=CYAN, leading=13, alignment=TA_CENTER, spaceAfter=4)
    sbS = ParagraphStyle('sbS', fontName='Helvetica-Bold',    fontSize=8,  textColor=CYAN, leading=12, spaceBefore=10, spaceAfter=3)
    sbI = ParagraphStyle('sbI', fontName='Helvetica',         fontSize=8,  textColor=colors.HexColor('#a1a1aa'), leading=12, spaceAfter=2)
    sbP = ParagraphStyle('sbP', fontName='Helvetica',         fontSize=8,  textColor=CHAR, alignment=TA_CENTER, leading=11)
    mSH = ParagraphStyle('mSH', fontName='Helvetica-Bold',    fontSize=11, textColor=CHAR,  leading=15, spaceBefore=10, spaceAfter=3)
    mPN = ParagraphStyle('mPN', fontName='Helvetica',         fontSize=10, textColor=DARK,  leading=14, spaceAfter=2)
    mPB = ParagraphStyle('mPB', fontName='Helvetica',         fontSize=10, textColor=DARK,  leading=14)
    mBD = ParagraphStyle('mBD', fontName='Helvetica-Bold',    fontSize=10, textColor=DARK,  leading=14)
    mMU = ParagraphStyle('mMU', fontName='Helvetica',         fontSize=9,  textColor=MID,   leading=13)
    mAC = ParagraphStyle('mAC', fontName='Helvetica-Bold',    fontSize=9,  textColor=CYAN,  leading=13)

    sb, mn = [], []
    iv = _img(profile_img_bytes, 76)
    if iv:
        sb.append(Table([[iv]], colWidths=[SW-14]))
        sb[-1].setStyle(TableStyle([('ALIGN',(0,0),(0,0),'CENTER'),
                                     ('TOPPADDING',(0,0),(-1,-1),4),
                                     ('BOTTOMPADDING',(0,0),(-1,-1),6)]))
    sb.append(Paragraph(_get(ss,'name') or 'Your Name', sbN))
    if _get(ss,'job_title'): sb.append(Paragraph(_get(ss,'job_title'), sbT))
    sb.append(HRFlowable(width=SW-16, thickness=1, color=CYAN, spaceBefore=4, spaceAfter=6))

    def sb_sec(title): sb.append(Paragraph(title.upper(), sbS))
    sb_sec("Contact")
    for k in ['email','phone','location','linkedin','github','portfolio']:
        v = _get(ss, k)
        if v: sb.append(Paragraph(v, sbI))

    for field, label in [('skills','Skills'),('Softskills','Soft Skills'),
                          ('languages','Languages'),('interests','Interests')]:
        v = _get(ss, field)
        if v:
            sb_sec(label)
            for sk in _skills_list(v):
                pill = Table([[Paragraph(sk, sbP)]], colWidths=[SW-20])
                pill.setStyle(TableStyle([('BACKGROUND',(0,0),(0,0),CYANLT),
                                           ('TOPPADDING',(0,0),(-1,-1),2),
                                           ('BOTTOMPADDING',(0,0),(-1,-1),2),
                                           ('LEFTPADDING',(0,0),(-1,-1),4),
                                           ('RIGHTPADDING',(0,0),(-1,-1),4)]))
                sb.append(pill)
                sb.append(Spacer(1,2))

    def mn_sec(title):
        mn.append(Paragraph(title, mSH))
        mn.append(HRFlowable(width=MW, thickness=2, color=CYAN, spaceAfter=5))

    sm = _get(ss,'summary')
    if sm:
        mn_sec("Summary")
        for f in _bullets(sm, mPN, mPB, CYAN): mn.append(f)
        mn.append(Spacer(1,4))

    exps = [e for e in _entries(ss,'experience_entries') if e.get('company') or e.get('title')]
    if exps:
        mn_sec("Work Experience")
        for e in exps:
            mn.append(_row2(Paragraph(f"<b>{e.get('title','')}</b>  ·  {e.get('company','')}", mBD),
                            Paragraph(e.get('duration',''), mAC), MW))
            for f in _bullets(e.get('description',''), mPN, mPB, CYAN): mn.append(f)
            mn.append(Spacer(1,7))

    edus = [e for e in _entries(ss,'education_entries') if e.get('institution') or e.get('degree')]
    if edus:
        mn_sec("Education")
        for e in edus:
            mn.append(_row2(Paragraph(f"<b>{_deg(e)}</b>  ·  {e.get('institution','')}", mBD),
                            Paragraph(e.get('year',''), mAC), MW))
            if e.get('details'): mn.append(Paragraph(e['details'], mMU))
            mn.append(Spacer(1,5))

    projs = [p for p in _entries(ss,'project_entries') if p.get('title')]
    proj_links = _entries(ss,'project_links')
    if projs:
        mn_sec("Projects")
        for i, p in enumerate(projs):
            lnk = proj_links[i] if i < len(proj_links) else ''
            t = _link(lnk, p.get('title',''), '#06b6d4') if lnk else p.get('title','')
            mn.append(Paragraph(f"<b>{t}</b>  ·  <font color='#6b7280'>{p.get('tech','')}</font>", mPN))
            for f in _bullets(p.get('description',''), mPN, mPB, CYAN): mn.append(f)
            mn.append(Spacer(1,6))

    certs = [c for c in _entries(ss,'certificate_links') if c.get('name')]
    if certs:
        mn_sec("Certifications")
        for c in certs:
            nm = _link(c.get('link',''), c.get('name',''), '#06b6d4') if c.get('link') else c.get('name','')
            mn.append(_row2(Paragraph(nm, mBD), Paragraph(c.get('duration',''), mAC), MW))
            if c.get('description'): mn.append(Paragraph(c['description'], mMU))
            mn.append(Spacer(1,4))

    _two_col(buf, sb, mn, CHAR, colors.HexColor('#27272a'))
    buf.seek(0); return buf


# ─── D06 · Amber Sidebar ─────────────────────────────────────────────────────
# Warm amber/orange sidebar — vibrant, warm professional look.
# Inspired by Novoresume "Bucharest" — energetic and human feel.
def render_template_amber_sidebar(session_state, profile_img_bytes=None):
    ss = session_state
    AMBER = colors.HexColor('#92400e')
    AMBLT = colors.HexColor('#fef3c7')
    AMBBD = colors.HexColor('#fcd34d')
    AMBBR = colors.HexColor('#b45309')
    DARK  = colors.HexColor('#1c1412')
    MID   = colors.HexColor('#78716c')
    WHT   = colors.white
    buf = BytesIO()
    SW = SIDEBAR_W
    MW = PAGE_W - MARGIN - SW - 14 - MARGIN

    sbN = ParagraphStyle('sbN', fontName='Helvetica-Bold',    fontSize=13, textColor=WHT,  leading=17, alignment=TA_CENTER, spaceAfter=2)
    sbT = ParagraphStyle('sbT', fontName='Helvetica-Oblique', fontSize=9,  textColor=AMBLT,leading=13, alignment=TA_CENTER, spaceAfter=4)
    sbS = ParagraphStyle('sbS', fontName='Helvetica-Bold',    fontSize=8,  textColor=AMBLT,leading=12, spaceBefore=10, spaceAfter=3)
    sbI = ParagraphStyle('sbI', fontName='Helvetica',         fontSize=8,  textColor=colors.HexColor('#fde68a'), leading=12, spaceAfter=2)
    sbP = ParagraphStyle('sbP', fontName='Helvetica',         fontSize=8,  textColor=AMBER,alignment=TA_CENTER, leading=11)
    mSH = ParagraphStyle('mSH', fontName='Helvetica-Bold',    fontSize=11, textColor=AMBER, leading=15, spaceBefore=10, spaceAfter=3)
    mPN = ParagraphStyle('mPN', fontName='Helvetica',         fontSize=10, textColor=DARK,  leading=14, spaceAfter=2)
    mPB = ParagraphStyle('mPB', fontName='Helvetica',         fontSize=10, textColor=DARK,  leading=14)
    mBD = ParagraphStyle('mBD', fontName='Helvetica-Bold',    fontSize=10, textColor=DARK,  leading=14)
    mMU = ParagraphStyle('mMU', fontName='Helvetica',         fontSize=9,  textColor=MID,   leading=13)
    mAC = ParagraphStyle('mAC', fontName='Helvetica-Bold',    fontSize=9,  textColor=AMBBR, leading=13)

    sb, mn = [], []
    iv = _img(profile_img_bytes, 76)
    if iv:
        sb.append(Table([[iv]], colWidths=[SW-14]))
        sb[-1].setStyle(TableStyle([('ALIGN',(0,0),(0,0),'CENTER'),
                                     ('TOPPADDING',(0,0),(-1,-1),4),
                                     ('BOTTOMPADDING',(0,0),(-1,-1),6)]))
    sb.append(Paragraph(_get(ss,'name') or 'Your Name', sbN))
    if _get(ss,'job_title'): sb.append(Paragraph(_get(ss,'job_title'), sbT))
    sb.append(HRFlowable(width=SW-16, thickness=1, color=AMBLT, spaceBefore=4, spaceAfter=6))

    def sb_sec(title): sb.append(Paragraph(title.upper(), sbS))
    sb_sec("Contact")
    for k in ['email','phone','location','linkedin','github','portfolio']:
        v = _get(ss, k)
        if v: sb.append(Paragraph(v, sbI))

    for field, label in [('skills','Skills'),('Softskills','Soft Skills'),
                          ('languages','Languages'),('interests','Interests')]:
        v = _get(ss, field)
        if v:
            sb_sec(label)
            for sk in _skills_list(v):
                pill = Table([[Paragraph(sk, sbP)]], colWidths=[SW-20])
                pill.setStyle(TableStyle([('BACKGROUND',(0,0),(0,0),AMBLT),
                                           ('TOPPADDING',(0,0),(-1,-1),2),
                                           ('BOTTOMPADDING',(0,0),(-1,-1),2),
                                           ('LEFTPADDING',(0,0),(-1,-1),4),
                                           ('RIGHTPADDING',(0,0),(-1,-1),4)]))
                sb.append(pill)
                sb.append(Spacer(1,2))

    def mn_sec(title):
        mn.append(Paragraph(title, mSH))
        mn.append(HRFlowable(width=MW, thickness=2, color=AMBBD, spaceAfter=5))

    sm = _get(ss,'summary')
    if sm:
        mn_sec("Summary")
        for f in _bullets(sm, mPN, mPB, AMBER): mn.append(f)
        mn.append(Spacer(1,4))

    exps = [e for e in _entries(ss,'experience_entries') if e.get('company') or e.get('title')]
    if exps:
        mn_sec("Work Experience")
        for e in exps:
            mn.append(_row2(Paragraph(f"<b>{e.get('title','')}</b>  ·  {e.get('company','')}", mBD),
                            Paragraph(e.get('duration',''), mAC), MW))
            for f in _bullets(e.get('description',''), mPN, mPB, AMBER): mn.append(f)
            mn.append(Spacer(1,7))

    edus = [e for e in _entries(ss,'education_entries') if e.get('institution') or e.get('degree')]
    if edus:
        mn_sec("Education")
        for e in edus:
            mn.append(_row2(Paragraph(f"<b>{_deg(e)}</b>  ·  {e.get('institution','')}", mBD),
                            Paragraph(e.get('year',''), mAC), MW))
            if e.get('details'): mn.append(Paragraph(e['details'], mMU))
            mn.append(Spacer(1,5))

    projs = [p for p in _entries(ss,'project_entries') if p.get('title')]
    proj_links = _entries(ss,'project_links')
    if projs:
        mn_sec("Projects")
        for i, p in enumerate(projs):
            lnk = proj_links[i] if i < len(proj_links) else ''
            t = _link(lnk, p.get('title',''), '#92400e') if lnk else p.get('title','')
            mn.append(Paragraph(f"<b>{t}</b>  ·  <font color='#78716c'>{p.get('tech','')}</font>", mPN))
            for f in _bullets(p.get('description',''), mPN, mPB, AMBER): mn.append(f)
            mn.append(Spacer(1,6))

    certs = [c for c in _entries(ss,'certificate_links') if c.get('name')]
    if certs:
        mn_sec("Certifications")
        for c in certs:
            nm = _link(c.get('link',''), c.get('name',''), '#92400e') if c.get('link') else c.get('name','')
            mn.append(_row2(Paragraph(nm, mBD), Paragraph(c.get('duration',''), mAC), MW))
            if c.get('description'): mn.append(Paragraph(c['description'], mMU))
            mn.append(Spacer(1,4))

    _two_col(buf, sb, mn, AMBER, AMBBR)
    buf.seek(0); return buf


# ═════════════════════════════════════════════════════════════════════════════
# TEMPLATE REGISTRY
# ═════════════════════════════════════════════════════════════════════════════

RESUME_TEMPLATES = {
    # ── Single-Column (15) ──
    "Cobalt Executive":   render_template_cobalt_executive,
    "Emerald Clean":      render_template_emerald_clean,
    "Charcoal Impact":    render_template_charcoal_impact,
    "Arctic Minimal":     render_template_arctic_minimal,
    "Ruby Professional":  render_template_ruby_professional,
    "Slate Modern":       render_template_slate_modern,
    "Golden Classic":     render_template_golden_classic,
    "Navy Prestige":      render_template_navy_prestige,
    "Coral Creative":     render_template_coral_creative,
    "Monochrome ATS":     render_template_monochrome_ats,
    "Indigo Tech":        render_template_indigo_tech,
    "Forest Executive":   render_template_forest_executive,
    "Plum Elegant":       render_template_plum_elegant,
    "Copper Warm":        render_template_copper_warm,
    "Sky Corporate":      render_template_sky_corporate,
    # ── Double-Column (6) ──
    "Midnight Sidebar":   render_template_midnight_sidebar,
    "Sage Sidebar":       render_template_sage_sidebar,
    "Royal Sidebar":      render_template_royal_sidebar,
    "Crimson Sidebar":    render_template_crimson_sidebar,
    "Charcoal Sidebar":   render_template_charcoal_sidebar,
    "Amber Sidebar":      render_template_amber_sidebar,
}

# Categorized for UI display
SINGLE_COLUMN_TEMPLATES = [k for k in list(RESUME_TEMPLATES.keys())[:15]]
DOUBLE_COLUMN_TEMPLATES = [k for k in list(RESUME_TEMPLATES.keys())[15:]]


def render_resume(template_name, session_state, profile_img_bytes=None):
    """Dispatch to named template. Returns BytesIO PDF."""
    fn = RESUME_TEMPLATES.get(template_name, render_template_cobalt_executive)
    return fn(session_state, profile_img_bytes)


# HTML-compat shims kept for legacy imports
def _fmt_desc(text, **kw): return text or ""
def _cert_name_html(cert, link_style, span_style=""): return cert.get('name', '')

# Legacy name aliases (for any old imports)
render_template_default_professional  = render_template_cobalt_executive
render_template_modern_minimal        = render_template_emerald_clean
render_template_elegant_sidebar       = render_template_midnight_sidebar
render_template_classic_clean         = render_template_arctic_minimal
render_template_executive             = render_template_slate_modern
render_template_timeline              = render_template_golden_classic
render_template_corporate_blue        = render_template_sky_corporate
render_template_creative_green        = render_template_coral_creative
render_template_warm_terracotta       = render_template_copper_warm
render_template_slate_gray            = render_template_slate_modern
render_template_teal_impact           = render_template_arctic_minimal
render_template_burgundy_classic      = render_template_ruby_professional
render_template_forest_green          = render_template_forest_executive
render_template_pure_white            = render_template_monochrome_ats
render_template_midnight_black        = render_template_charcoal_impact
render_template_soft_lavender         = render_template_plum_elegant
render_template_warm_sand             = render_template_copper_warm
render_template_ice_blue              = render_template_sky_corporate
render_template_rose_gold             = render_template_ruby_professional
