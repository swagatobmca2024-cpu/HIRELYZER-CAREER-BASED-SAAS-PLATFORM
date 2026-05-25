# resume_builder.py — 21 premium resume templates
# 15 Single-Column + 6 Double-Column
# ReportLab-only, no heavy CSS, proper pills, proper two-column rendering

from io import BytesIO
from reportlab.lib.pagesizes import A4
from reportlab.lib import colors
from reportlab.lib.units import mm
from reportlab.lib.styles import ParagraphStyle
from reportlab.lib.enums import TA_LEFT, TA_CENTER, TA_RIGHT
from reportlab.platypus import (
    SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle,
    HRFlowable, ListFlowable, ListItem, Image, KeepTogether,
    BaseDocTemplate, Frame, PageTemplate, FrameBreak,
)
from reportlab.pdfgen.canvas import Canvas as RLCanvas

PAGE_W, PAGE_H = A4
MARGIN  = 14 * mm
SB_W    = 155   # sidebar width points

# ─────────────────────────────────────────────────────────────────────────────
# HELPERS
# ─────────────────────────────────────────────────────────────────────────────

def _get(ss, key, default=""):
    if isinstance(ss, dict):
        return ss.get(key, default) or default
    return getattr(ss, key, default) or default

def _entries(ss, key, default=None):
    if default is None: default = []
    if isinstance(ss, dict): return ss.get(key, default) or default
    return getattr(ss, key, default) or default

def _skills_list(raw):
    return [i.strip() for i in str(raw).replace('\n',',').split(',') if i.strip()]

def _contact_line(ss, sep=' | '):
    return sep.join([_get(ss,k) for k in ['email','phone','location','linkedin','github','portfolio'] if _get(ss,k)])

def _deg(e):
    d = e.get('degree','')
    return ', '.join(d) if isinstance(d, list) else d

def _img(b, size=72):
    if not b:
        return None
    try:
        return Image(BytesIO(b), width=size, height=size)
    except Exception:
        return None

def _link(url, label, css):
    if not url: return label
    if not url.startswith('http'): url = 'https://' + url
    return f'<link href="{url}"><font color="{css}">{label}</font></link>'

def _hr(w, color, thick=0.7, before=0, after=5):
    return HRFlowable(width=w, thickness=thick, color=color, spaceBefore=before, spaceAfter=after)

def _row2(lp, rp, w, lw=0.68):
    t = Table([[lp, rp]], colWidths=[w*lw, w*(1-lw)])
    t.setStyle(TableStyle([
        ('ALIGN',(1,0),(1,0),'RIGHT'), ('VALIGN',(0,0),(-1,-1),'TOP'),
        ('LEFTPADDING',(0,0),(-1,-1),0), ('RIGHTPADDING',(0,0),(-1,-1),0),
        ('TOPPADDING',(0,0),(-1,-1),0),  ('BOTTOMPADDING',(0,0),(-1,-1),0),
    ]))
    return t

def _new_doc(buf, lm=MARGIN, rm=MARGIN, tm=MARGIN, bm=MARGIN):
    return SimpleDocTemplate(buf, pagesize=A4,
                             leftMargin=lm, rightMargin=rm,
                             topMargin=tm, bottomMargin=bm)

# ── PROPER PILLS ─────────────────────────────────────────────────────────────
# Each skill gets its own mini single-cell table (pill). Pills are collected
# into a flow and stacked in rows using a wrapping Table approach:
# we build rows of 4 pills max, each pill as a Paragraph in a styled cell.

def _pill_items(raw, bg, fg, border_col, max_per_row=4):
    """Return a Table of pills — each pill is a styled box. Proper wrapping."""
    items = _skills_list(raw)
    if not items:
        return []
    ps = ParagraphStyle('pill_txt', fontName='Helvetica', fontSize=8.5,
                         textColor=fg, alignment=TA_CENTER, leading=11)
    rows = []
    row  = []
    for item in items:
        cell = Paragraph(item, ps)
        row.append(cell)
        if len(row) == max_per_row:
            rows.append(row)
            row = []
    if row:
        # pad last row so colWidths are consistent
        while len(row) < max_per_row:
            row.append(Paragraph('', ps))
        rows.append(row)
    if not rows:
        return []
    # Each pill column is equal width
    return rows, max_per_row

def _pills(raw, bg, fg, border_col, total_w, max_per_row=4):
    """Build a proper pill grid. Returns list of flowables."""
    items = _skills_list(raw)
    if not items:
        return []
    ps = ParagraphStyle('pltxt', fontName='Helvetica', fontSize=8.5,
                         textColor=fg, alignment=TA_CENTER, leading=11)
    rows = []
    row  = []
    for item in items:
        row.append(Paragraph(item, ps))
        if len(row) == max_per_row:
            rows.append(list(row)); row = []
    if row:
        while len(row) < max_per_row:
            row.append(Paragraph('', ps))
        rows.append(row)

    cw = total_w / max_per_row
    t = Table(rows, colWidths=[cw]*max_per_row,
              rowHeights=[18]*len(rows))

    cmd = [
        ('BACKGROUND',  (0,0),(-1,-1), bg),
        ('TOPPADDING',  (0,0),(-1,-1), 3),
        ('BOTTOMPADDING',(0,0),(-1,-1),3),
        ('LEFTPADDING', (0,0),(-1,-1), 4),
        ('RIGHTPADDING',(0,0),(-1,-1), 4),
        ('VALIGN',      (0,0),(-1,-1),'MIDDLE'),
        ('ROWBACKGROUNDS',(0,0),(-1,-1),[bg]),
    ]
    # Draw individual pill box for each non-empty cell
    for ri, rw in enumerate(rows):
        for ci, cell in enumerate(rw):
            if cell.text.strip():
                cmd.append(('BOX', (ci,ri),(ci,ri), 0.6, border_col))
                # inner bg already set by BACKGROUND
    t.setStyle(TableStyle(cmd))
    return [t, Spacer(1,5)]

def _pills_sb(raw, fg, bg_cell, border_col, sb_inner_w, max_per_row=2):
    """Sidebar-friendly pills — 2 per row, smaller."""
    items = _skills_list(raw)
    if not items:
        return []
    ps = ParagraphStyle('sbpltxt', fontName='Helvetica', fontSize=7.5,
                         textColor=fg, alignment=TA_CENTER, leading=10)
    rows = []
    row  = []
    for item in items:
        row.append(Paragraph(item, ps))
        if len(row) == max_per_row:
            rows.append(list(row)); row = []
    if row:
        while len(row) < max_per_row:
            row.append(Paragraph('', ps))
        rows.append(row)

    cw = sb_inner_w / max_per_row
    t = Table(rows, colWidths=[cw]*max_per_row,
              rowHeights=[15]*len(rows))
    cmd = [
        ('BACKGROUND',   (0,0),(-1,-1), bg_cell),
        ('TOPPADDING',   (0,0),(-1,-1), 2),
        ('BOTTOMPADDING',(0,0),(-1,-1), 2),
        ('LEFTPADDING',  (0,0),(-1,-1), 3),
        ('RIGHTPADDING', (0,0),(-1,-1), 3),
        ('VALIGN',       (0,0),(-1,-1),'MIDDLE'),
    ]
    for ri, rw in enumerate(rows):
        for ci, cell in enumerate(rw):
            if cell.text.strip():
                cmd.append(('BOX',(ci,ri),(ci,ri),0.5,border_col))
    t.setStyle(TableStyle(cmd))
    return [t, Spacer(1,3)]

def _bullets(text, normal_st, bullet_st, bc=None):
    """Parse text lines into bullet/paragraph flowables."""
    if not text or not text.strip():
        return []
    PREFIXES = ("-","•","*","·",">","–","—","★")
    out, buf = [], []
    def flush():
        if buf:
            out.append(ListFlowable(
                [ListItem(Paragraph(t, bullet_st), leftIndent=10,
                          bulletColor=bc or colors.HexColor('#555555')) for t in buf],
                bulletType='bullet', start='•', leftIndent=6, bulletFontSize=6.5))
            buf.clear()
    for line in str(text).replace('\r\n','\n').split('\n'):
        s = line.strip()
        if not s: continue
        is_b = False
        for p in PREFIXES:
            if s.startswith(p):
                s = s[len(p):].strip(); is_b = True; break
        if is_b: buf.append(s)
        else:    flush(); out.append(Paragraph(s, normal_st))
    flush()
    return out

# ── PROPER TWO-COLUMN via onFirstPage/onLaterPages background ────────────────
def _build_two_col(buf, sb_items, mn_items, sb_bg_color,
                   sb_w=SB_W, mg=MARGIN):
    """
    Correct two-column PDF:
    - Sidebar background drawn BEFORE content via onPage callback
    - FrameBreak switches from sidebar frame to main frame
    """
    MN_X = mg + sb_w + 8
    MN_W = PAGE_W - MN_X - mg
    PH   = PAGE_H - 2*mg

    sb_frame = Frame(mg,    mg, sb_w, PH,
                     leftPadding=8, rightPadding=6,
                     topPadding=8,  bottomPadding=6, id='sb')
    mn_frame = Frame(MN_X,  mg, MN_W, PH,
                     leftPadding=6, rightPadding=4,
                     topPadding=8,  bottomPadding=6, id='mn')

    sb_hex = sb_bg_color

    def _draw_bg(canvas, doc):
        canvas.saveState()
        canvas.setFillColor(sb_hex)
        canvas.rect(0, 0, mg + sb_w + 4, PAGE_H, fill=1, stroke=0)
        canvas.restoreState()

    pt = PageTemplate(id='twocol',
                      frames=[sb_frame, mn_frame],
                      onPage=_draw_bg,
                      pagesize=A4)
    doc = BaseDocTemplate(buf, pagesize=A4,
                          leftMargin=mg, rightMargin=mg,
                          topMargin=mg,  bottomMargin=mg)
    doc.addPageTemplates([pt])
    doc.build(list(sb_items) + [FrameBreak()] + list(mn_items))


# ═════════════════════════════════════════════════════════════════════════════
# SINGLE-COLUMN TEMPLATES  (15)
# ═════════════════════════════════════════════════════════════════════════════

def _single_template(ss, img_bytes, colors_cfg, layout_cfg):
    """
    Generic single-column builder driven by config dicts.
    colors_cfg: dict of color keys
    layout_cfg: dict of layout options
    """
    C  = colors_cfg
    L  = layout_cfg
    W  = PAGE_W - 2*MARGIN
    buf = BytesIO()
    doc = _new_doc(buf)

    PRIMARY   = C['primary']
    ACCENT    = C['accent']
    LIGHT     = C['light']
    BORDER    = C['border']
    DARK      = C.get('dark',  colors.HexColor('#111827'))
    MID       = C.get('mid',   colors.HexColor('#6b7280'))
    HDR_TEXT  = C.get('hdr_text', colors.white)
    HDR_BG    = C.get('hdr_bg', None)

    NM = ParagraphStyle('nm', fontName='Helvetica-Bold',
                         fontSize=L.get('name_size', 23),
                         textColor=C.get('name_col', PRIMARY),
                         leading=L.get('name_size',23)+6,
                         alignment=L.get('name_align', TA_LEFT))
    JT = ParagraphStyle('jt', fontName='Helvetica-Oblique',
                         fontSize=12, textColor=ACCENT, leading=16,
                         spaceAfter=2,
                         alignment=L.get('name_align', TA_LEFT))
    CO = ParagraphStyle('co', fontName='Helvetica',
                         fontSize=8.5, textColor=MID, leading=12,
                         alignment=L.get('name_align', TA_LEFT))
    SH = ParagraphStyle('sh', fontName='Helvetica-Bold',
                         fontSize=9.5, textColor=C.get('sec_col', PRIMARY),
                         leading=13, spaceBefore=14, spaceAfter=2)
    PN = ParagraphStyle('pn', fontName='Helvetica',
                         fontSize=10, textColor=DARK, leading=14, spaceAfter=2)
    PB = ParagraphStyle('pb', fontName='Helvetica',
                         fontSize=10, textColor=DARK, leading=14)
    BD = ParagraphStyle('bd', fontName='Helvetica-Bold',
                         fontSize=10, textColor=DARK, leading=14)
    MU = ParagraphStyle('mu', fontName='Helvetica',
                         fontSize=9, textColor=MID, leading=13)
    AC = ParagraphStyle('ac', fontName='Helvetica-Bold',
                         fontSize=9, textColor=ACCENT, leading=13,
                         alignment=TA_RIGHT)

    story = []
    iv = _img(img_bytes, 70)

    # ── Header ──────────────────────────────────────────────────────────────
    name_content = [Paragraph(_get(ss,'name') or 'Your Name', NM)]
    jt = _get(ss,'job_title')
    if jt: name_content.append(Paragraph(jt, JT))
    cp = _contact_line(ss, '  ·  ')
    if cp:
        co_style = CO
        if HDR_BG:
            co_style = ParagraphStyle('co2', parent=CO,
                                      textColor=C.get('hdr_contact_col', MID),
                                      alignment=L.get('name_align', TA_LEFT))
        name_content.append(Paragraph(cp, co_style))

    if HDR_BG:
        # Filled header band
        nm2 = ParagraphStyle('nm2', parent=NM, textColor=HDR_TEXT)
        jt2 = ParagraphStyle('jt2', parent=JT,
                              textColor=C.get('hdr_sub_col', colors.HexColor('#cbd5e1')))
        co2 = ParagraphStyle('co2', parent=CO,
                              textColor=C.get('hdr_contact_col', colors.HexColor('#94a3b8')))
        hdr_cells = [Paragraph(_get(ss,'name') or 'Your Name', nm2)]
        if jt: hdr_cells.append(Paragraph(jt, jt2))
        if cp: hdr_cells.append(Paragraph(cp, co2))
        if iv:
            ht = Table([[hdr_cells, iv]], colWidths=[W-76, 76])
        else:
            ht = Table([[hdr_cells]], colWidths=[W])
        ht.setStyle(TableStyle([
            ('BACKGROUND',(0,0),(-1,-1), HDR_BG),
            ('VALIGN',(0,0),(-1,-1),'MIDDLE'),
            ('TOPPADDING',(0,0),(-1,-1),12),
            ('BOTTOMPADDING',(0,0),(-1,-1),12),
            ('LEFTPADDING',(0,0),(-1,-1),14),
            ('RIGHTPADDING',(0,0),(-1,-1),8),
        ]))
        story.append(ht)
        story.append(_hr(W, ACCENT, thick=L.get('hdr_bar_thick',3), before=0, after=10))
    else:
        # Plain header
        if iv:
            ht = Table([[name_content, iv]], colWidths=[W-78, 78])
            ht.setStyle(TableStyle([
                ('VALIGN',(0,0),(-1,-1),'MIDDLE'),
                ('LEFTPADDING',(0,0),(-1,-1),0),
                ('RIGHTPADDING',(0,0),(-1,-1),0),
                ('TOPPADDING',(0,0),(-1,-1),0),
                ('BOTTOMPADDING',(0,0),(-1,-1),0),
            ]))
            story.append(ht)
        else:
            for b in name_content: story.append(b)
        story.append(_hr(W, PRIMARY, thick=L.get('hdr_bar_thick',2), before=6, after=10))

    # ── Section header function ──────────────────────────────────────────────
    sec_style = L.get('sec_style', 'underline')

    def sec(title):
        if sec_style == 'filled_box':
            bx = Table([[Paragraph(title.upper(), ParagraphStyle(
                'shb', fontName='Helvetica-Bold', fontSize=9,
                textColor=colors.white, leading=13))]], colWidths=[W])
            bx.setStyle(TableStyle([
                ('BACKGROUND',(0,0),(-1,-1), PRIMARY),
                ('TOPPADDING',(0,0),(-1,-1),4),  ('BOTTOMPADDING',(0,0),(-1,-1),4),
                ('LEFTPADDING',(0,0),(-1,-1),8), ('RIGHTPADDING',(0,0),(-1,-1),8),
            ]))
            story.append(Spacer(1,10)); story.append(bx); story.append(Spacer(1,6))
        elif sec_style == 'light_box':
            bx = Table([[Paragraph(title.upper(), ParagraphStyle(
                'shb2', fontName='Helvetica-Bold', fontSize=9,
                textColor=PRIMARY, leading=13))]], colWidths=[W])
            bx.setStyle(TableStyle([
                ('BACKGROUND',(0,0),(-1,-1), LIGHT),
                ('TOPPADDING',(0,0),(-1,-1),4),  ('BOTTOMPADDING',(0,0),(-1,-1),4),
                ('LEFTPADDING',(0,0),(-1,-1),8), ('RIGHTPADDING',(0,0),(-1,-1),8),
                ('BOX',(0,0),(-1,-1),0.5, BORDER),
            ]))
            story.append(Spacer(1,10)); story.append(bx); story.append(Spacer(1,6))
        elif sec_style == 'left_bar':
            # Simple 2-column table: thin colored bar cell | title cell
            sh2 = ParagraphStyle('sh_lb', parent=SH, spaceBefore=0, spaceAfter=0)
            bar = Table([['', Paragraph(title.upper(), sh2)]], colWidths=[5, W-5])
            bar.setStyle(TableStyle([
                ('BACKGROUND',(0,0),(0,0), PRIMARY),
                ('VALIGN',(0,0),(-1,-1),'MIDDLE'),
                ('LEFTPADDING',(0,0),(-1,-1),0),
                ('RIGHTPADDING',(0,0),(-1,-1),0),
                ('TOPPADDING',(0,0),(-1,-1),12),
                ('BOTTOMPADDING',(0,0),(-1,-1),2),
                ('LEFTPADDING',(1,0),(1,0),6),
            ]))
            story.append(bar)
            story.append(_hr(W, BORDER, thick=0.5, before=2, after=5))
        else:  # underline (default)
            story.append(Paragraph(title.upper(), SH))
            story.append(_hr(W, BORDER, thick=L.get('sec_rule_thick',0.8), before=0, after=5))

    # ── Content sections ─────────────────────────────────────────────────────
    sm = _get(ss,'summary')
    if sm:
        sec("Summary")
        for f in _bullets(sm, PN, PB, ACCENT): story.append(f)
        story.append(Spacer(1,4))

    exps = [e for e in _entries(ss,'experience_entries') if e.get('company') or e.get('title')]
    if exps:
        sec("Work Experience")
        for e in exps:
            story.append(_row2(
                Paragraph(f"<b>{e.get('title','')}</b>  ·  {e.get('company','')}", BD),
                Paragraph(e.get('duration',''), AC), W))
            for f in _bullets(e.get('description',''), PN, PB, ACCENT): story.append(f)
            story.append(Spacer(1,7))

    edus = [e for e in _entries(ss,'education_entries') if e.get('institution') or e.get('degree')]
    if edus:
        sec("Education")
        for e in edus:
            story.append(_row2(
                Paragraph(f"<b>{_deg(e)}</b>  ·  {e.get('institution','')}", BD),
                Paragraph(e.get('year',''), AC), W))
            if e.get('details'): story.append(Paragraph(e['details'], MU))
            story.append(Spacer(1,5))

    for field, label in [('skills','Technical Skills'),('Softskills','Soft Skills'),
                          ('languages','Languages'),('interests','Interests')]:
        v = _get(ss, field)
        if v:
            sec(label)
            story.extend(_pills(v, LIGHT, C.get('pill_fg', PRIMARY), BORDER, W, max_per_row=4))

    projs = [p for p in _entries(ss,'project_entries') if p.get('title')]
    proj_links = _entries(ss,'project_links')
    if projs:
        sec("Projects")
        for i, p in enumerate(projs):
            lnk = proj_links[i] if i < len(proj_links) else ''
            t   = _link(lnk, p.get('title',''), ACCENT.hexval() if hasattr(ACCENT,'hexval') else '#2563eb') if lnk else p.get('title','')
            story.append(Paragraph(f"<b>{t}</b>  ·  <font color='#6b7280'>{p.get('tech','')}</font>", PN))
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

    doc.build(story)
    buf.seek(0)
    return buf


# ── SIDEBAR TEMPLATE BUILDER ──────────────────────────────────────────────────
def _sidebar_template(ss, img_bytes, sb_bg, sb_accent, mn_primary, mn_accent,
                       mn_light, mn_border):
    """
    Generic two-column sidebar builder.
    Sidebar: name, title, contact, skills/languages/interests/softskills
    Main:    summary, experience, education, projects, certs
    """
    buf   = BytesIO()
    SW    = SB_W
    MG    = MARGIN
    MN_X  = MG + SW + 8
    MN_W  = PAGE_W - MN_X - MG
    SB_IW = SW - 16   # inner width for sidebar content

    WHT   = colors.white
    SB_MID = colors.HexColor('#d1d5db') if sb_bg.hexval() < '#888888' else colors.HexColor('#374151')

    # Sidebar styles
    sbN = ParagraphStyle('sbN', fontName='Helvetica-Bold', fontSize=13,
                          textColor=WHT, leading=17, alignment=TA_CENTER, spaceAfter=3)
    sbT = ParagraphStyle('sbT', fontName='Helvetica', fontSize=9,
                          textColor=sb_accent, leading=13, alignment=TA_CENTER, spaceAfter=5)
    sbS = ParagraphStyle('sbS', fontName='Helvetica-Bold', fontSize=8,
                          textColor=sb_accent, leading=11, spaceBefore=10, spaceAfter=4)
    sbI = ParagraphStyle('sbI', fontName='Helvetica', fontSize=8,
                          textColor=colors.HexColor('#e2e8f0'), leading=12, spaceAfter=2)

    # Main styles
    DARK = colors.HexColor('#111827')
    MID  = colors.HexColor('#6b7280')
    mSH  = ParagraphStyle('mSH', fontName='Helvetica-Bold', fontSize=10.5,
                           textColor=mn_primary, leading=14, spaceBefore=12, spaceAfter=3)
    mPN  = ParagraphStyle('mPN', fontName='Helvetica', fontSize=10,
                           textColor=DARK, leading=14, spaceAfter=2)
    mPB  = ParagraphStyle('mPB', fontName='Helvetica', fontSize=10,
                           textColor=DARK, leading=14)
    mBD  = ParagraphStyle('mBD', fontName='Helvetica-Bold', fontSize=10,
                           textColor=DARK, leading=14)
    mMU  = ParagraphStyle('mMU', fontName='Helvetica', fontSize=9,
                           textColor=MID, leading=13)
    mAC  = ParagraphStyle('mAC', fontName='Helvetica-Bold', fontSize=9,
                           textColor=mn_accent, leading=13, alignment=TA_RIGHT)

    sb, mn = [], []

    # ── Sidebar ───────────────────────────────────────────────────────────────
    iv = _img(img_bytes, 76)
    if iv:
        it = Table([[iv]], colWidths=[SB_IW])
        it.setStyle(TableStyle([('ALIGN',(0,0),(0,0),'CENTER'),
                                  ('TOPPADDING',(0,0),(-1,-1),2),
                                  ('BOTTOMPADDING',(0,0),(-1,-1),6)]))
        sb.append(it)

    sb.append(Paragraph(_get(ss,'name') or 'Your Name', sbN))
    jt = _get(ss,'job_title')
    if jt: sb.append(Paragraph(jt, sbT))
    sb.append(HRFlowable(width=SB_IW, thickness=0.7, color=sb_accent,
                           spaceBefore=4, spaceAfter=8))

    # Contact
    sb.append(Paragraph("CONTACT", sbS))
    for k,lbl in [('email',''),('phone',''),('location',''),
                  ('linkedin',''),('github',''),('portfolio','')]:
        v = _get(ss,k)
        if v: sb.append(Paragraph(v, sbI))

    # Skills sections in sidebar
    for field, label in [('skills','SKILLS'),('languages','LANGUAGES'),
                          ('Softskills','SOFT SKILLS'),('interests','INTERESTS')]:
        v = _get(ss, field)
        if v:
            sb.append(Paragraph(label, sbS))
            # Use sidebar pills
            items = _skills_list(v)
            if items:
                ps2 = ParagraphStyle('sbpill', fontName='Helvetica', fontSize=7.5,
                                      textColor=sb_bg, alignment=TA_CENTER, leading=10)
                # build rows of 2
                rows2 = []
                row2  = []
                for item in items:
                    row2.append(Paragraph(item, ps2))
                    if len(row2) == 2:
                        rows2.append(list(row2)); row2 = []
                if row2:
                    while len(row2) < 2:
                        row2.append(Paragraph('', ps2))
                    rows2.append(row2)
                cw2 = SB_IW / 2
                t2  = Table(rows2, colWidths=[cw2,cw2], rowHeights=[14]*len(rows2))
                cmd2 = [
                    ('BACKGROUND',(0,0),(-1,-1), sb_accent),
                    ('TOPPADDING',(0,0),(-1,-1),2),
                    ('BOTTOMPADDING',(0,0),(-1,-1),2),
                    ('LEFTPADDING',(0,0),(-1,-1),2),
                    ('RIGHTPADDING',(0,0),(-1,-1),2),
                    ('VALIGN',(0,0),(-1,-1),'MIDDLE'),
                ]
                for ri2, rw2 in enumerate(rows2):
                    for ci2, cell2 in enumerate(rw2):
                        if cell2.text.strip():
                            cmd2.append(('BOX',(ci2,ri2),(ci2,ri2),0.4,sb_bg))
                t2.setStyle(TableStyle(cmd2))
                sb.append(t2)
                sb.append(Spacer(1,4))

    # ── Main ──────────────────────────────────────────────────────────────────
    def mn_sec(title):
        mn.append(Paragraph(title, mSH))
        mn.append(HRFlowable(width=MN_W, thickness=1.5, color=mn_accent,
                              spaceAfter=5))

    sm = _get(ss,'summary')
    if sm:
        mn_sec("Professional Summary")
        for f in _bullets(sm, mPN, mPB, mn_accent): mn.append(f)
        mn.append(Spacer(1,4))

    exps = [e for e in _entries(ss,'experience_entries') if e.get('company') or e.get('title')]
    if exps:
        mn_sec("Work Experience")
        for e in exps:
            mn.append(_row2(
                Paragraph(f"<b>{e.get('title','')}</b>  ·  {e.get('company','')}", mBD),
                Paragraph(e.get('duration',''), mAC), MN_W))
            for f in _bullets(e.get('description',''), mPN, mPB, mn_accent): mn.append(f)
            mn.append(Spacer(1,7))

    edus = [e for e in _entries(ss,'education_entries') if e.get('institution') or e.get('degree')]
    if edus:
        mn_sec("Education")
        for e in edus:
            mn.append(_row2(
                Paragraph(f"<b>{_deg(e)}</b>  ·  {e.get('institution','')}", mBD),
                Paragraph(e.get('year',''), mAC), MN_W))
            if e.get('details'): mn.append(Paragraph(e['details'], mMU))
            mn.append(Spacer(1,5))

    projs = [p for p in _entries(ss,'project_entries') if p.get('title')]
    pl    = _entries(ss,'project_links')
    if projs:
        mn_sec("Projects")
        for i, p in enumerate(projs):
            lnk = pl[i] if i < len(pl) else ''
            t2  = _link(lnk, p.get('title',''), '#2563eb') if lnk else p.get('title','')
            mn.append(Paragraph(f"<b>{t2}</b>  ·  <font color='#6b7280'>{p.get('tech','')}</font>", mPN))
            for f in _bullets(p.get('description',''), mPN, mPB, mn_accent): mn.append(f)
            mn.append(Spacer(1,6))

    certs = [c for c in _entries(ss,'certificate_links') if c.get('name')]
    if certs:
        mn_sec("Certifications")
        for c in certs:
            nm2 = _link(c.get('link',''), c.get('name',''), '#2563eb') if c.get('link') else c.get('name','')
            mn.append(_row2(Paragraph(nm2, mBD), Paragraph(c.get('duration',''), mAC), MN_W))
            if c.get('description'): mn.append(Paragraph(c['description'], mMU))
            mn.append(Spacer(1,4))

    _build_two_col(buf, sb, mn, sb_bg)
    buf.seek(0)
    return buf


# ═════════════════════════════════════════════════════════════════════════════
# 15 SINGLE-COLUMN TEMPLATES
# ═════════════════════════════════════════════════════════════════════════════

def render_template_cobalt_executive(ss, img=None):
    return _single_template(ss, img,
        colors_cfg=dict(
            primary=colors.HexColor('#1b3a6b'),
            accent= colors.HexColor('#2563eb'),
            light=  colors.HexColor('#dbeafe'),
            border= colors.HexColor('#93c5fd'),
            hdr_bg= colors.HexColor('#1b3a6b'),
            hdr_text=colors.white,
            hdr_sub_col=colors.HexColor('#93c5fd'),
            hdr_contact_col=colors.HexColor('#94a3b8'),
            sec_col=colors.HexColor('#1b3a6b'),
            pill_fg=colors.HexColor('#1b3a6b'),
        ),
        layout_cfg=dict(name_size=24, hdr_bar_thick=3, sec_style='underline'))

def render_template_emerald_clean(ss, img=None):
    return _single_template(ss, img,
        colors_cfg=dict(
            primary=colors.HexColor('#065f46'),
            accent= colors.HexColor('#059669'),
            light=  colors.HexColor('#d1fae5'),
            border= colors.HexColor('#6ee7b7'),
            sec_col=colors.HexColor('#065f46'),
            pill_fg=colors.HexColor('#065f46'),
        ),
        layout_cfg=dict(name_size=25, sec_style='left_bar', sec_rule_thick=0.4))

def render_template_charcoal_impact(ss, img=None):
    return _single_template(ss, img,
        colors_cfg=dict(
            primary=colors.HexColor('#1c1c1e'),
            accent= colors.HexColor('#ea580c'),
            light=  colors.HexColor('#fff7ed'),
            border= colors.HexColor('#fdba74'),
            hdr_bg= colors.HexColor('#1c1c1e'),
            hdr_text=colors.white,
            hdr_sub_col=colors.HexColor('#fdba74'),
            hdr_contact_col=colors.HexColor('#9ca3af'),
            sec_col=colors.HexColor('#1c1c1e'),
            pill_fg=colors.HexColor('#1c1c1e'),
        ),
        layout_cfg=dict(name_size=24, hdr_bar_thick=3, sec_style='underline',
                        sec_rule_thick=1.5))

def render_template_arctic_minimal(ss, img=None):
    return _single_template(ss, img,
        colors_cfg=dict(
            primary=colors.HexColor('#0891b2'),
            accent= colors.HexColor('#0891b2'),
            light=  colors.HexColor('#ecfeff'),
            border= colors.HexColor('#a5f3fc'),
            sec_col=colors.HexColor('#0891b2'),
            pill_fg=colors.HexColor('#0e7490'),
        ),
        layout_cfg=dict(name_size=23, sec_style='underline', sec_rule_thick=0.6,
                        hdr_bar_thick=1.5))

def render_template_ruby_professional(ss, img=None):
    return _single_template(ss, img,
        colors_cfg=dict(
            primary=colors.HexColor('#9f1239'),
            accent= colors.HexColor('#e11d48'),
            light=  colors.HexColor('#fff1f2'),
            border= colors.HexColor('#fda4af'),
            sec_col=colors.HexColor('#9f1239'),
            pill_fg=colors.HexColor('#9f1239'),
            name_col=colors.HexColor('#9f1239'),
        ),
        layout_cfg=dict(name_size=25, name_align=TA_CENTER,
                        sec_style='underline', hdr_bar_thick=2))

def render_template_slate_modern(ss, img=None):
    return _single_template(ss, img,
        colors_cfg=dict(
            primary=colors.HexColor('#334155'),
            accent= colors.HexColor('#7c3aed'),
            light=  colors.HexColor('#f1f5f9'),
            border= colors.HexColor('#94a3b8'),
            hdr_bg= colors.HexColor('#334155'),
            hdr_text=colors.white,
            hdr_sub_col=colors.HexColor('#94a3b8'),
            hdr_contact_col=colors.HexColor('#64748b'),
            sec_col=colors.HexColor('#334155'),
            pill_fg=colors.HexColor('#334155'),
        ),
        layout_cfg=dict(name_size=23, hdr_bar_thick=3, sec_style='underline'))

def render_template_golden_classic(ss, img=None):
    return _single_template(ss, img,
        colors_cfg=dict(
            primary=colors.HexColor('#b45309'),
            accent= colors.HexColor('#d97706'),
            light=  colors.HexColor('#fef3c7'),
            border= colors.HexColor('#fcd34d'),
            sec_col=colors.HexColor('#92400e'),
            pill_fg=colors.HexColor('#78350f'),
            name_col=colors.HexColor('#1c1917'),
        ),
        layout_cfg=dict(name_size=26, name_align=TA_CENTER,
                        sec_style='underline', hdr_bar_thick=2.5))

def render_template_navy_prestige(ss, img=None):
    return _single_template(ss, img,
        colors_cfg=dict(
            primary=colors.HexColor('#0f2d4f'),
            accent= colors.HexColor('#c9972b'),
            light=  colors.HexColor('#fdf8f0'),
            border= colors.HexColor('#e8d5a3'),
            hdr_bg= colors.HexColor('#0f2d4f'),
            hdr_text=colors.white,
            hdr_sub_col=colors.HexColor('#c9972b'),
            hdr_contact_col=colors.HexColor('#94a3b8'),
            sec_col=colors.HexColor('#0f2d4f'),
            pill_fg=colors.HexColor('#0f2d4f'),
        ),
        layout_cfg=dict(name_size=22, hdr_bar_thick=3, sec_style='underline'))

def render_template_coral_creative(ss, img=None):
    return _single_template(ss, img,
        colors_cfg=dict(
            primary=colors.HexColor('#e11d48'),
            accent= colors.HexColor('#be123c'),
            light=  colors.HexColor('#fff1f2'),
            border= colors.HexColor('#fda4af'),
            sec_col=colors.HexColor('#e11d48'),
            pill_fg=colors.HexColor('#9f1239'),
        ),
        layout_cfg=dict(name_size=25, sec_style='filled_box', hdr_bar_thick=2))

def render_template_monochrome_ats(ss, img=None):
    return _single_template(ss, img,
        colors_cfg=dict(
            primary=colors.HexColor('#111827'),
            accent= colors.HexColor('#374151'),
            light=  colors.HexColor('#f3f4f6'),
            border= colors.HexColor('#9ca3af'),
            sec_col=colors.HexColor('#111827'),
            pill_fg=colors.HexColor('#111827'),
        ),
        layout_cfg=dict(name_size=22, sec_style='underline',
                        sec_rule_thick=1, hdr_bar_thick=1.5))

def render_template_indigo_tech(ss, img=None):
    return _single_template(ss, img,
        colors_cfg=dict(
            primary=colors.HexColor('#3730a3'),
            accent= colors.HexColor('#4f46e5'),
            light=  colors.HexColor('#eef2ff'),
            border= colors.HexColor('#a5b4fc'),
            sec_col=colors.HexColor('#3730a3'),
            pill_fg=colors.HexColor('#3730a3'),
        ),
        layout_cfg=dict(name_size=24, sec_style='light_box', hdr_bar_thick=2.5))

def render_template_forest_executive(ss, img=None):
    return _single_template(ss, img,
        colors_cfg=dict(
            primary=colors.HexColor('#14532d'),
            accent= colors.HexColor('#16a34a'),
            light=  colors.HexColor('#dcfce7'),
            border= colors.HexColor('#86efac'),
            hdr_bg= colors.HexColor('#14532d'),
            hdr_text=colors.white,
            hdr_sub_col=colors.HexColor('#86efac'),
            hdr_contact_col=colors.HexColor('#6b7280'),
            sec_col=colors.HexColor('#14532d'),
            pill_fg=colors.HexColor('#14532d'),
        ),
        layout_cfg=dict(name_size=23, hdr_bar_thick=3, sec_style='underline'))

def render_template_plum_elegant(ss, img=None):
    return _single_template(ss, img,
        colors_cfg=dict(
            primary=colors.HexColor('#6b21a8'),
            accent= colors.HexColor('#9333ea'),
            light=  colors.HexColor('#f5f3ff'),
            border= colors.HexColor('#d8b4fe'),
            sec_col=colors.HexColor('#6b21a8'),
            pill_fg=colors.HexColor('#581c87'),
            name_col=colors.HexColor('#6b21a8'),
        ),
        layout_cfg=dict(name_size=25, name_align=TA_CENTER,
                        sec_style='underline', hdr_bar_thick=2))

def render_template_copper_warm(ss, img=None):
    return _single_template(ss, img,
        colors_cfg=dict(
            primary=colors.HexColor('#92400e'),
            accent= colors.HexColor('#c2410c'),
            light=  colors.HexColor('#fef3c7'),
            border= colors.HexColor('#fbbf24'),
            sec_col=colors.HexColor('#92400e'),
            pill_fg=colors.HexColor('#78350f'),
        ),
        layout_cfg=dict(name_size=24, sec_style='left_bar', hdr_bar_thick=2.5))

def render_template_sky_corporate(ss, img=None):
    return _single_template(ss, img,
        colors_cfg=dict(
            primary=colors.HexColor('#0284c7'),
            accent= colors.HexColor('#0369a1'),
            light=  colors.HexColor('#e0f2fe'),
            border= colors.HexColor('#7dd3fc'),
            hdr_bg= colors.HexColor('#e0f2fe'),
            hdr_text=colors.HexColor('#0c2340'),
            hdr_sub_col=colors.HexColor('#0284c7'),
            hdr_contact_col=colors.HexColor('#64748b'),
            sec_col=colors.HexColor('#0c2340'),
            pill_fg=colors.HexColor('#0c2340'),
            name_col=colors.HexColor('#0c2340'),
        ),
        layout_cfg=dict(name_size=22, hdr_bar_thick=3, sec_style='underline'))


# ═════════════════════════════════════════════════════════════════════════════
# 6 DOUBLE-COLUMN / SIDEBAR TEMPLATES
# ═════════════════════════════════════════════════════════════════════════════

def render_template_midnight_sidebar(ss, img=None):
    return _sidebar_template(ss, img,
        sb_bg=     colors.HexColor('#0f172a'),
        sb_accent= colors.HexColor('#38bdf8'),
        mn_primary=colors.HexColor('#0f172a'),
        mn_accent= colors.HexColor('#0284c7'),
        mn_light=  colors.HexColor('#e0f2fe'),
        mn_border= colors.HexColor('#7dd3fc'))

def render_template_sage_sidebar(ss, img=None):
    return _sidebar_template(ss, img,
        sb_bg=     colors.HexColor('#1a4731'),
        sb_accent= colors.HexColor('#86efac'),
        mn_primary=colors.HexColor('#14532d'),
        mn_accent= colors.HexColor('#16a34a'),
        mn_light=  colors.HexColor('#dcfce7'),
        mn_border= colors.HexColor('#86efac'))

def render_template_royal_sidebar(ss, img=None):
    return _sidebar_template(ss, img,
        sb_bg=     colors.HexColor('#1e3a8a'),
        sb_accent= colors.HexColor('#fbbf24'),
        mn_primary=colors.HexColor('#1e3a8a'),
        mn_accent= colors.HexColor('#d97706'),
        mn_light=  colors.HexColor('#eff6ff'),
        mn_border= colors.HexColor('#93c5fd'))

def render_template_crimson_sidebar(ss, img=None):
    return _sidebar_template(ss, img,
        sb_bg=     colors.HexColor('#7f1d1d'),
        sb_accent= colors.HexColor('#fca5a5'),
        mn_primary=colors.HexColor('#991b1b'),
        mn_accent= colors.HexColor('#dc2626'),
        mn_light=  colors.HexColor('#fff5f5'),
        mn_border= colors.HexColor('#fca5a5'))

def render_template_charcoal_sidebar(ss, img=None):
    return _sidebar_template(ss, img,
        sb_bg=     colors.HexColor('#18181b'),
        sb_accent= colors.HexColor('#22d3ee'),
        mn_primary=colors.HexColor('#18181b'),
        mn_accent= colors.HexColor('#06b6d4'),
        mn_light=  colors.HexColor('#ecfeff'),
        mn_border= colors.HexColor('#a5f3fc'))

def render_template_amber_sidebar(ss, img=None):
    return _sidebar_template(ss, img,
        sb_bg=     colors.HexColor('#78350f'),
        sb_accent= colors.HexColor('#fcd34d'),
        mn_primary=colors.HexColor('#92400e'),
        mn_accent= colors.HexColor('#d97706'),
        mn_light=  colors.HexColor('#fef3c7'),
        mn_border= colors.HexColor('#fcd34d'))


# ═════════════════════════════════════════════════════════════════════════════
# REGISTRY
# ═════════════════════════════════════════════════════════════════════════════

RESUME_TEMPLATES = {
    # Single-column (15)
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
    # Double-column (6)
    "Midnight Sidebar":   render_template_midnight_sidebar,
    "Sage Sidebar":       render_template_sage_sidebar,
    "Royal Sidebar":      render_template_royal_sidebar,
    "Crimson Sidebar":    render_template_crimson_sidebar,
    "Charcoal Sidebar":   render_template_charcoal_sidebar,
    "Amber Sidebar":      render_template_amber_sidebar,
}

SINGLE_COLUMN_TEMPLATES = list(RESUME_TEMPLATES.keys())[:15]
DOUBLE_COLUMN_TEMPLATES = list(RESUME_TEMPLATES.keys())[15:]

def render_resume(template_name, session_state, profile_img_bytes=None):
    fn = RESUME_TEMPLATES.get(template_name, render_template_cobalt_executive)
    return fn(session_state, profile_img_bytes)

# Legacy aliases
def _fmt_desc(text, **kw): return text or ""
def _cert_name_html(cert, link_style, span_style=""): return cert.get('name','')

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
