# resume_builder.py
# ══════════════════════════════════════════════════════════════════════════════
# RESUME TEMPLATES — 15 industry-standard HTML resume templates
# Shared helpers: _fmt_desc, _cert_name_html
# Imported by main.py:
#   from resume_builder import (
#       render_template_default, render_template_modern, render_template_sidebar,
#       render_template_classic, render_template_executive, render_template_timeline,
#       render_template_corporate, render_template_creative_green,
#       render_template_terracotta, render_template_navy_prestige,
#       render_template_slate_gray, render_template_teal_impact,
#       render_template_burgundy_classic, render_template_indigo_tech,
#       render_template_forest_green, RESUME_TEMPLATES, render_resume,
#   )
# ══════════════════════════════════════════════════════════════════════════════

from collections import Counter as _Counter

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

def _cert_name_html(cert, link_style, span_style=""):
    """
    Returns cert name as a clickable <a> if a link is provided,
    otherwise as a plain <span> — prevents href='' resolving to the host site.
    """
    name = cert.get('name', '')
    link = cert.get('link', '').strip()
    if link:
        return f"<a href='{link}' target='_blank' style='{link_style}'>{name}</a>"
    else:
        return f"<span style='{span_style or link_style}'>{name}</span>"


def render_template_default(session_state, profile_img_html=""):
    """Default professional template — compact sidebar layout, grey/dark colour scheme"""
    import re as _re_def

    # ── helpers ──────────────────────────────────────────────────────────────
    def _badge(item, bg="rgba(255,255,255,0.18)", color="#ffffff"):
        return (f"<span style='display:inline-block;background:{bg};color:{color};border-radius:4px;"
                f"padding:3px 10px;margin:3px 3px 3px 0;font-size:12px;font-weight:600;"
                f"border:1px solid rgba(255,255,255,0.3);'>{item.strip()}</span>")

    def _badges(items_str, bg="rgba(255,255,255,0.18)", color="#ffffff"):
        return "".join(_badge(s, bg, color) for s in items_str.split(',') if s.strip())

    def _side_sec(title, body):
        return (f"<div style='margin-bottom:24px;'>"
                f"<h3 style='font-size:11px;letter-spacing:2px;text-transform:uppercase;color:#ffffff;"
                f"font-weight:800;border-bottom:1px solid rgba(255,255,255,0.35);padding-bottom:6px;margin-bottom:12px;'>{title}</h3>"
                f"{body}</div>")

    def _main_sec(title, body):
        return (f"<div style='margin-bottom:26px;'>"
                f"<h3 style='font-size:13px;letter-spacing:2px;text-transform:uppercase;font-weight:700;"
                f"color:#374151;border-bottom:2px solid #9ca3af;padding-bottom:5px;margin-bottom:14px;'>{title}</h3>"
                f"{body}</div>")

    # ── profile image ─────────────────────────────────────────────────────────
    fixed_img = ""
    if profile_img_html:
        m = _re_def.search(r'<img[^>]*>', profile_img_html)
        if m:
            tag = _re_def.sub(r"style=['\"][^'\"]*['\"]", "", m.group(0))
            tag = tag.replace("<img ", "<img style='width:108px;height:108px;border-radius:50%;"
                              "object-fit:cover;object-position:center;border:3px solid rgba(255,255,255,0.5);"
                              "display:block;margin:0 auto;' ")
            fixed_img = tag

    # ── SVG icons ─────────────────────────────────────────────────────────────
    SVG = {
        'email':    '<svg xmlns="http://www.w3.org/2000/svg" width="13" height="13" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M4 4h16c1.1 0 2 .9 2 2v12c0 1.1-.9 2-2 2H4c-1.1 0-2-.9-2-2V6c0-1.1.9-2 2-2z"/><polyline points="22,6 12,13 2,6"/></svg>',
        'phone':    '<svg xmlns="http://www.w3.org/2000/svg" width="13" height="13" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M22 16.92v3a2 2 0 0 1-2.18 2 19.79 19.79 0 0 1-8.63-3.07A19.5 19.5 0 0 1 4.69 12 19.79 19.79 0 0 1 1.65 3.37 2 2 0 0 1 3.64 1h3a2 2 0 0 1 2 1.72c.127.96.361 1.903.7 2.81a2 2 0 0 1-.45 2.11L7.91 8.8a16 16 0 0 0 6.29 6.29l.98-.98a2 2 0 0 1 2.11-.45c.907.339 1.85.573 2.81.7A2 2 0 0 1 22 16.92z"/></svg>',
        'location': '<svg xmlns="http://www.w3.org/2000/svg" width="13" height="13" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M21 10c0 7-9 13-9 13s-9-6-9-13a9 9 0 0 1 18 0z"/><circle cx="12" cy="10" r="3"/></svg>',
        'linkedin': '<svg xmlns="http://www.w3.org/2000/svg" width="13" height="13" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M16 8a6 6 0 0 1 6 6v7h-4v-7a2 2 0 0 0-2-2 2 2 0 0 0-2 2v7h-4v-7a6 6 0 0 1 6-6z"/><rect x="2" y="9" width="4" height="12"/><circle cx="4" cy="4" r="2"/></svg>',
        'portfolio': '<svg xmlns="http://www.w3.org/2000/svg" width="13" height="13" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><circle cx="12" cy="12" r="10"/><line x1="2" y1="12" x2="22" y2="12"/><path d="M12 2a15.3 15.3 0 0 1 4 10 15.3 15.3 0 0 1-4 10 15.3 15.3 0 0 1-4-10 15.3 15.3 0 0 1 4-10z"/></svg>',
    }

    # ── contact ───────────────────────────────────────────────────────────────
    contact_html = ""
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
        contact_html += (
            f"<div style='margin-bottom:9px;font-size:13px;color:#ffffff;"
            f"display:flex;align-items:center;gap:8px;'>"
            f"<span style='flex-shrink:0;opacity:0.9;'>{SVG.get(_key,'')}</span>{val_html}</div>"
        )

    # ── certificates sidebar ──────────────────────────────────────────────────
    cert_html = ""
    for cert in (getattr(session_state, 'certificate_links', None) or []):
        if cert.get('name'):
            cert_html += (
                f"<div style='margin-bottom:10px;padding:8px;background:rgba(255,255,255,0.1);"
                f"border-radius:6px;border:1px solid rgba(255,255,255,0.2);'>"
                f"{_cert_name_html(cert, 'color:#ffffff;font-size:13px;font-weight:600;text-decoration:none;')}"
                f"<div style='font-size:11px;color:rgba(255,255,255,0.8);'>{cert.get('duration','')}</div></div>"
            )

    # ── project links sidebar ─────────────────────────────────────────────────
    proj_links_html = ""
    if getattr(session_state, 'project_links', None):
        proj_links_html = "".join(
            f"<div style='margin-bottom:6px;'><a href='{lnk}' target='_blank' "
            f"style='color:#ffffff;font-size:12px;font-weight:600;'>&#128279; Project {i+1}</a></div>"
            for i, lnk in enumerate(getattr(session_state, 'project_links', []) or [])
        )

    # ── experience ────────────────────────────────────────────────────────────
    exp_html = ""
    for exp in session_state.experience_entries:
        if exp.get('company') or exp.get('title'):
            desc = _fmt_desc(exp.get('description', ''), font_size='13px', color='#374151', line_height='1.75')
            exp_html += (
                f"<div style='margin-bottom:20px;border-left:3px solid #9ca3af;padding-left:14px;'>"
                f"<div style='display:flex;justify-content:space-between;align-items:baseline;flex-wrap:wrap;gap:6px;'>"
                f"<strong style='font-size:15px;color:#1f2937;'>{exp.get('company','')}</strong>"
                f"<span style='font-size:12px;color:#6b7280;background:#f3f4f6;padding:2px 8px;border-radius:8px;'>{exp.get('duration','')}</span>"
                f"</div>"
                f"<div style='font-size:13px;color:#4b5563;font-weight:700;margin-bottom:5px;'>{exp.get('title','')}</div>"
                f"<div style='font-size:13px;color:#374151;line-height:1.7;'>{desc}</div></div>"
                f"<div style='border-bottom:1px dashed #d1d5db;margin-bottom:12px;'></div>"
            )

    # ── education ─────────────────────────────────────────────────────────────
    edu_html = ""
    for edu in session_state.education_entries:
        if edu.get('institution'):
            degree_val = edu.get('degree', '')
            if isinstance(degree_val, list):
                degree_val = ", ".join(degree_val)
            edu_html += (
                f"<div style='margin-bottom:14px;border-left:3px solid #9ca3af;padding-left:12px;'>"
                f"<strong style='font-size:14px;color:#1f2937;'>{edu.get('institution','')}</strong>"
                f"<span style='float:right;font-size:12px;color:#6b7280;'>{edu.get('year','')}</span>"
                f"<div style='clear:both;font-size:13px;color:#4b5563;font-style:italic;font-weight:600;'>{degree_val}</div>"
                f"<div style='font-size:12px;color:#6b7280;'>{edu.get('details','')}</div></div>"
            )

    # ── projects ──────────────────────────────────────────────────────────────
    proj_html = ""
    proj_links_all = getattr(session_state, 'project_links', []) or []
    for idx, proj in enumerate(session_state.project_entries):
        if proj.get('title'):
            desc = _fmt_desc(proj.get('description', ''), font_size='13px', color='#374151', line_height='1.75')
            proj_link_html = ""
            if idx < len(proj_links_all) and proj_links_all[idx]:
                proj_link_html = (f"<div style='margin-top:5px;'><a href='{proj_links_all[idx]}' target='_blank' "
                                  f"style='color:#374151;font-size:12px;font-weight:600;'>&#128279; View Project / GitHub</a></div>")
            proj_html += (
                f"<div style='margin-bottom:14px;padding:12px 14px;background:#f9fafb;"
                f"border-radius:6px;border-left:3px solid #9ca3af;'>"
                f"<div style='display:flex;justify-content:space-between;flex-wrap:wrap;gap:4px;'>"
                f"<strong style='font-size:14px;color:#1f2937;'>{proj.get('title','')}</strong>"
                f"<span style='font-size:12px;color:#6b7280;'>{proj.get('duration','')}</span>"
                f"</div>"
                f"<div style='font-size:12px;color:#4b5563;font-weight:600;margin-bottom:4px;'>{proj.get('tech','')}</div>"
                f"<div style='font-size:13px;color:#374151;'>{desc}</div>"
                f"{proj_link_html}</div>"
            )

    # ── summary ───────────────────────────────────────────────────────────────
    summary_html = _fmt_desc(session_state.get('summary', ''), font_size='13px', color='#374151', line_height='1.8')

    html_content = f"""<!DOCTYPE html>
<html lang='en'>
<head><meta charset='UTF-8'><meta name='viewport' content='width=device-width,initial-scale=1'><title>{session_state.get('name','')} - Professional Resume</title>
<style>* {{ box-sizing:border-box; margin:0; padding:0; }} body {{ font-family:'Segoe UI',sans-serif; background:#fff; }}</style>
</head>
<body>
<table role='presentation' style='width:100%;min-height:100vh;border-collapse:collapse;table-layout:fixed;'>
<tr>
  <td style='width:300px;background:linear-gradient(180deg,#374151,#4b5563);color:#ffffff;padding:36px 24px;vertical-align:top;'>
    {'<div style="margin:0 auto 14px;text-align:center;">' + fixed_img + '</div>' if fixed_img else ''}
    <h1 style='font-size:21px;font-weight:800;color:#ffffff;text-align:center;margin-bottom:4px;'>{session_state.get('name','')}</h1>
    <div style='font-size:13px;color:#e5e7eb;text-align:center;margin-bottom:24px;font-weight:600;letter-spacing:1px;text-transform:uppercase;'>{session_state.get('job_title','')}</div>
    {_side_sec("Contact", contact_html)}
    {_side_sec("Skills", _badges(session_state.get('skills',''))) if session_state.get('skills') else ''}
    {_side_sec("Soft Skills", _badges(session_state.get('Softskills',''))) if session_state.get('Softskills') else ''}
    {_side_sec("Languages", _badges(session_state.get('languages',''))) if session_state.get('languages') else ''}
    {_side_sec("Interests", _badges(session_state.get('interests',''))) if session_state.get('interests') else ''}
    {_side_sec("Certifications", cert_html) if cert_html else ''}
    {_side_sec("Project Links", proj_links_html) if proj_links_html else ''}
  </td>
  <td style='padding:40px 44px;background:#fff;vertical-align:top;'>
    {_main_sec("Professional Summary", summary_html) if summary_html else ''}
    {_main_sec("Work Experience", exp_html) if exp_html else ''}
    {_main_sec("Education", edu_html) if edu_html else ''}
    {_main_sec("Projects", proj_html) if proj_html else ''}
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
    for cert in (getattr(session_state, 'certificate_links', None) or []):
        if cert.get('name'):
            cert_desc = _fmt_desc(cert.get('description', ''), font_size='13px', color='#1f2937', line_height='1.7')
            cert_html += (
                f"<div style='margin-bottom:14px;padding:12px 14px;border-left:3px solid #2563eb;"
                f"background:#f8faff;border-radius:0 8px 8px 0;'>"
                f"<div style='display:flex;justify-content:space-between;align-items:baseline;flex-wrap:wrap;gap:6px;margin-bottom:4px;'>"
                f"{_cert_name_html(cert, 'font-size:14px;font-weight:700;color:#1e3a8a;text-decoration:none;')}"
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
<meta charset="UTF-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>{session_state.get('name', '')} - Resume</title>
</head>
<body style="font-family:'Segoe UI',Arial,Helvetica,sans-serif;line-height:1.6;color:#1f2937;background:#ffffff;max-width:794px;margin:0 auto;padding:36px 32px;">

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
    skills_list     = [s.strip() for s in session_state.get('skills',     '').split(',') if s.strip()]
    languages_list  = [l.strip() for l in session_state.get('languages',  '').split(',') if l.strip()]
    interests_list  = [i.strip() for i in session_state.get('interests',  '').split(',') if i.strip()]
    softskills_list = [s.strip() for s in session_state.get('Softskills', '').split(',') if s.strip()]
    
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
    for cert in (getattr(session_state, 'certificate_links', None) or []):
        if cert.get('name'):
            cert_sb_html += (
                f"<div style='margin-bottom:10px;padding:8px;background:rgba(255,255,255,0.1);border-radius:6px;border:1px solid rgba(56,189,248,0.3);'>"
                f"{_cert_name_html(cert, 'color:#ffffff;font-size:13px;font-weight:600;text-decoration:none;')}"
                f"<div style='font-size:11px;color:rgba(255,255,255,0.8);'>{cert.get('duration','')}</div></div>"
            )

    proj_links_sb = ""
    if getattr(session_state, 'project_links', None):
        proj_links_sb = "".join(
            f"<div style='margin-bottom:6px;'><a href='{lnk}' target='_blank' style='color:#ffffff;font-size:12px;font-weight:600;'>&#128279; Project {i+1}</a></div>"
            for i, lnk in enumerate(getattr(session_state, 'project_links', []) or [])
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
<head><meta charset='UTF-8'><meta name='viewport' content='width=device-width,initial-scale=1'><title>{session_state.get('name','')} - Resume</title>
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
    for cert in (getattr(session_state, 'certificate_links', None) or []):
        if cert.get("name"):
            desc = _fmt_desc(cert.get('description',''), font_size='13px', color='#444', line_height='1.7')
            cert_html += f"""
            <div style='margin-bottom:12px;'>
                <div style='display:flex;justify-content:space-between;'>
                    {_cert_name_html(cert, 'font-weight:600;color:#1e3a5f;font-size:15px;text-decoration:none;')}
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
<head><meta charset='UTF-8'><meta name='viewport' content='width=device-width,initial-scale=1'><title>{session_state.get('name','')} - Resume</title>
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
    for cert in (getattr(session_state, 'certificate_links', None) or []):
        if cert.get("name"):
            cert_html += f"""
            <div style='margin-bottom:10px;'>
                {_cert_name_html(cert, 'font-weight:600;font-size:15px;color:#3730a3;text-decoration:none;')}
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
<head><meta charset='UTF-8'><meta name='viewport' content='width=device-width,initial-scale=1'><title>{session_state.get('name','')} - Executive Resume</title>
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
        f"{_cert_name_html(c, 'font-weight:600;color:#0d9488;font-size:14px;text-decoration:none;')}"
        f"<span style='font-size:12px;color:#64748b;'>· {c.get('duration','')}</span></div>"
        for c in (getattr(session_state, 'certificate_links', None) or []) if c.get('name')
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
<head><meta charset='UTF-8'><meta name='viewport' content='width=device-width,initial-scale=1'><title>{session_state.get('name','')} - Timeline Resume</title>
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
    for cert in (getattr(session_state, 'certificate_links', None) or []):
        if cert.get('name'):
            cert_sidebar += f"""
            <div style='margin-bottom:10px;padding:8px;background:rgba(255,255,255,0.1);border-radius:6px;'>
                {_cert_name_html(cert, 'color:#93c5fd;font-size:13px;font-weight:600;text-decoration:none;')}
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
<head><meta charset='UTF-8'><meta name='viewport' content='width=device-width,initial-scale=1'><title>{session_state.get('name','')} - Corporate Resume</title>
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
    for cert in (getattr(session_state, 'certificate_links', None) or []):
        if cert.get('name'):
            cert_html += (f"<div style='margin-bottom:8px;'>"
                          f"{_cert_name_html(cert, 'color:#059669;font-size:13px;font-weight:600;text-decoration:none;')}"
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
<head><meta charset='UTF-8'><meta name='viewport' content='width=device-width,initial-scale=1'><title>{session_state.get('name','')} - Creative Resume</title>
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
    for cert in (getattr(session_state, 'certificate_links', None) or []):
        if cert.get('name'):
            cert_html += f"<div style='margin-bottom:9px;padding:8px;background:rgba(255,255,255,0.1);border-radius:5px;'>{_cert_name_html(cert, 'color:#fde68a;font-size:12px;font-weight:600;text-decoration:none;')}<div style='font-size:11px;color:#d4b896;'>{cert.get('duration','')}</div></div>"

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
<head><meta charset='UTF-8'><meta name='viewport' content='width=device-width,initial-scale=1'><title>{session_state.get('name','')} - Terracotta Resume</title>
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


# ─────────────────────────────────────────────────────────────────────────────
# TEMPLATE 10 — Navy Prestige (Two Column)
# ─────────────────────────────────────────────────────────────────────────────
def render_template_navy_prestige(session_state, profile_img_html=""):
    """Navy Prestige — two-column, deep navy sidebar, gold accents, ATS-friendly."""
    import re as _renp

    fixed_img = ""
    if profile_img_html:
        m = _renp.search(r'<img[^>]*>', profile_img_html)
        if m:
            tag = _renp.sub(r"style=['\"][^'\"]*['\"]", "", m.group(0))
            tag = tag.replace("<img ", "<img style='width:108px;height:108px;border-radius:50%;"
                              "object-fit:cover;object-position:center;border:3px solid #b8972a;"
                              "display:block;margin:0 auto;' ")
            fixed_img = tag

    def _badge_np(item):
        return (f"<span style='display:inline-block;background:rgba(184,151,42,0.20);color:#f5e6b2;"
                f"border:1px solid rgba(184,151,42,0.45);border-radius:4px;padding:3px 10px;"
                f"margin:3px 3px 3px 0;font-size:12px;font-weight:600;'>{item.strip()}</span>")

    def _badges_np(s):
        return "".join(_badge_np(x) for x in s.split(',') if x.strip())

    def _side_np(title, body):
        return (f"<div style='margin-bottom:22px;'>"
                f"<h3 style='font-size:10px;letter-spacing:2px;text-transform:uppercase;"
                f"color:#b8972a;font-weight:800;border-bottom:1px solid rgba(184,151,42,0.4);"
                f"padding-bottom:5px;margin-bottom:10px;'>{title}</h3>"
                f"{body}</div>")

    def _main_np(title, body):
        return (f"<div style='margin-bottom:26px;'>"
                f"<h3 style='font-size:13px;letter-spacing:1.5px;text-transform:uppercase;"
                f"font-weight:700;color:#0d1b3e;border-bottom:2px solid #b8972a;"
                f"padding-bottom:5px;margin-bottom:14px;'>{title}</h3>"
                f"{body}</div>")

    SVG_NP = {
        'email':    '<svg xmlns="http://www.w3.org/2000/svg" width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M4 4h16c1.1 0 2 .9 2 2v12c0 1.1-.9 2-2 2H4c-1.1 0-2-.9-2-2V6c0-1.1.9-2 2-2z"/><polyline points="22,6 12,13 2,6"/></svg>',
        'phone':    '<svg xmlns="http://www.w3.org/2000/svg" width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M22 16.92v3a2 2 0 0 1-2.18 2 19.79 19.79 0 0 1-8.63-3.07A19.5 19.5 0 0 1 4.69 12 19.79 19.79 0 0 1 1.65 3.37 2 2 0 0 1 3.64 1h3a2 2 0 0 1 2 1.72c.127.96.361 1.903.7 2.81a2 2 0 0 1-.45 2.11L7.91 8.8a16 16 0 0 0 6.29 6.29l.98-.98a2 2 0 0 1 2.11-.45c.907.339 1.85.573 2.81.7A2 2 0 0 1 22 16.92z"/></svg>',
        'location': '<svg xmlns="http://www.w3.org/2000/svg" width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M21 10c0 7-9 13-9 13s-9-6-9-13a9 9 0 0 1 18 0z"/><circle cx="12" cy="10" r="3"/></svg>',
        'linkedin': '<svg xmlns="http://www.w3.org/2000/svg" width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M16 8a6 6 0 0 1 6 6v7h-4v-7a2 2 0 0 0-2-2 2 2 0 0 0-2 2v7h-4v-7a6 6 0 0 1 6-6z"/><rect x="2" y="9" width="4" height="12"/><circle cx="4" cy="4" r="2"/></svg>',
        'portfolio':'<svg xmlns="http://www.w3.org/2000/svg" width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><circle cx="12" cy="12" r="10"/><line x1="2" y1="12" x2="22" y2="12"/><path d="M12 2a15.3 15.3 0 0 1 4 10 15.3 15.3 0 0 1-4 10 15.3 15.3 0 0 1-4-10 15.3 15.3 0 0 1 4-10z"/></svg>',
    }
    contact_html_np = ""
    for _key in ['location', 'phone', 'email', 'linkedin', 'portfolio']:
        val = session_state.get(_key, '')
        if not val:
            continue
        if _key == 'email':
            v = f"<a href='mailto:{val}' style='color:#f5e6b2;text-decoration:none;font-weight:500;word-break:break-all;'>{val}</a>"
        elif _key in ('linkedin', 'portfolio'):
            href = val if val.startswith('http') else f"https://{val}"
            v = f"<a href='{href}' target='_blank' style='color:#f5e6b2;text-decoration:none;font-weight:500;word-break:break-all;'>{val}</a>"
        else:
            v = f"<span style='color:#f5e6b2;word-break:break-all;'>{val}</span>"
        contact_html_np += (f"<div style='margin-bottom:8px;font-size:12px;color:#f5e6b2;display:flex;align-items:center;gap:7px;'>"
                            f"<span style='opacity:0.85;flex-shrink:0;'>{SVG_NP.get(_key,'')}</span>{v}</div>")

    cert_html_np = ""
    for cert in (getattr(session_state, 'certificate_links', None) or []):
        if cert.get('name'):
            cert_html_np += (f"<div style='margin-bottom:9px;padding:7px 9px;background:rgba(184,151,42,0.12);"
                             f"border-radius:5px;border:1px solid rgba(184,151,42,0.3);'>"
                             f"{_cert_name_html(cert, 'color:#f5e6b2;font-size:12px;font-weight:700;text-decoration:none;')}"
                             f"<div style='font-size:11px;color:rgba(245,230,178,0.75);'>{cert.get('duration','')}</div></div>")

    proj_links_html_np = ""
    if getattr(session_state, 'project_links', None):
        proj_links_html_np = "".join(
            f"<div style='margin-bottom:5px;'><a href='{lnk}' target='_blank' style='color:#f5e6b2;font-size:12px;font-weight:600;'>&#128279; Project {i+1}</a></div>"
            for i, lnk in enumerate(getattr(session_state, 'project_links', []) or []))

    exp_html_np = ""
    for exp in session_state.experience_entries:
        if exp.get('company') or exp.get('title'):
            desc = _fmt_desc(exp.get('description', ''), font_size='13px', color='#1f2937', line_height='1.75')
            exp_html_np += (
                f"<div style='margin-bottom:18px;padding-left:12px;border-left:3px solid #b8972a;'>"
                f"<div style='display:flex;justify-content:space-between;align-items:baseline;flex-wrap:wrap;gap:4px;'>"
                f"<strong style='font-size:14px;color:#0d1b3e;'>{exp.get('company','')}</strong>"
                f"<span style='font-size:12px;color:#6b7280;background:#fef9ec;padding:2px 8px;border-radius:6px;border:1px solid #e8d58a;'>{exp.get('duration','')}</span>"
                f"</div>"
                f"<div style='font-size:13px;color:#374151;font-weight:700;margin-bottom:4px;'>{exp.get('title','')}</div>"
                f"<div>{desc}</div></div>"
                f"<div style='border-bottom:1px dashed #d1d5db;margin-bottom:10px;'></div>"
            )

    edu_html_np = ""
    for edu in session_state.education_entries:
        if edu.get('institution'):
            dv = edu.get('degree', '')
            if isinstance(dv, list):
                dv = ", ".join(dv)
            edu_html_np += (
                f"<div style='margin-bottom:12px;padding-left:12px;border-left:3px solid #b8972a;'>"
                f"<strong style='font-size:13px;color:#0d1b3e;'>{edu.get('institution','')}</strong>"
                f"<span style='float:right;font-size:12px;color:#6b7280;'>{edu.get('year','')}</span>"
                f"<div style='clear:both;font-size:13px;color:#374151;font-style:italic;font-weight:600;'>{dv}</div>"
                f"<div style='font-size:12px;color:#6b7280;'>{edu.get('details','')}</div></div>"
            )

    proj_html_np = ""
    proj_links_all_np = getattr(session_state, 'project_links', []) or []
    for idx, proj in enumerate(session_state.project_entries):
        if proj.get('title'):
            desc = _fmt_desc(proj.get('description', ''), font_size='13px', color='#1f2937', line_height='1.75')
            pl = ""
            if idx < len(proj_links_all_np) and proj_links_all_np[idx]:
                pl = (f"<div style='margin-top:4px;'><a href='{proj_links_all_np[idx]}' target='_blank' "
                      f"style='color:#b8972a;font-size:12px;font-weight:600;'>&#128279; View Project</a></div>")
            proj_html_np += (
                f"<div style='margin-bottom:14px;padding:10px 12px;background:#fffdf4;"
                f"border-radius:6px;border-left:3px solid #b8972a;'>"
                f"<div style='display:flex;justify-content:space-between;flex-wrap:wrap;gap:4px;'>"
                f"<strong style='font-size:13px;color:#0d1b3e;'>{proj.get('title','')}</strong>"
                f"<span style='font-size:12px;color:#6b7280;'>{proj.get('duration','')}</span>"
                f"</div>"
                f"<div style='font-size:12px;color:#374151;font-weight:600;margin-bottom:3px;'>{proj.get('tech','')}</div>"
                f"<div>{desc}</div>{pl}</div>"
            )

    summary_html_np = _fmt_desc(session_state.get('summary', ''), font_size='13px', color='#1f2937', line_height='1.8')

    html_content = f"""<!DOCTYPE html>
<html lang='en'>
<head><meta charset='UTF-8'><meta name='viewport' content='width=device-width,initial-scale=1'><title>{session_state.get('name','')} - Resume</title>
<style>* {{ box-sizing:border-box; margin:0; padding:0; }} body {{ font-family:'Segoe UI',sans-serif; background:#fff; }}</style>
</head>
<body>
<table role='presentation' style='width:100%;min-height:100vh;border-collapse:collapse;table-layout:fixed;'>
<tr>
  <td style='width:290px;background:linear-gradient(180deg,#0d1b3e,#1a2f6b);color:#f5e6b2;padding:34px 22px;vertical-align:top;'>
    {'<div style="margin:0 auto 12px;text-align:center;">' + fixed_img + '</div>' if fixed_img else ''}
    <h1 style='font-size:20px;font-weight:800;color:#f5e6b2;text-align:center;margin-bottom:3px;'>{session_state.get('name','')}</h1>
    <div style='font-size:12px;color:#b8972a;text-align:center;margin-bottom:22px;font-weight:700;letter-spacing:1.2px;text-transform:uppercase;'>{session_state.get('job_title','')}</div>
    {_side_np("Contact", contact_html_np)}
    {_side_np("Technical Skills", _badges_np(session_state.get('skills',''))) if session_state.get('skills') else ''}
    {_side_np("Soft Skills", _badges_np(session_state.get('Softskills',''))) if session_state.get('Softskills') else ''}
    {_side_np("Languages", _badges_np(session_state.get('languages',''))) if session_state.get('languages') else ''}
    {_side_np("Interests", _badges_np(session_state.get('interests',''))) if session_state.get('interests') else ''}
    {_side_np("Certifications", cert_html_np) if cert_html_np else ''}
    {_side_np("Project Links", proj_links_html_np) if proj_links_html_np else ''}
  </td>
  <td style='padding:38px 42px;background:#ffffff;vertical-align:top;'>
    {_main_np("Professional Summary", summary_html_np) if summary_html_np else ''}
    {_main_np("Work Experience", exp_html_np) if exp_html_np else ''}
    {_main_np("Education", edu_html_np) if edu_html_np else ''}
    {_main_np("Projects", proj_html_np) if proj_html_np else ''}
  </td>
</tr>
</table>
</body></html>"""

    return html_content


# ─────────────────────────────────────────────────────────────────────────────
# TEMPLATE 11 — Slate Gray (Single Column)
# Layout standardized to match Classic Clean Single Column
# ─────────────────────────────────────────────────────────────────────────────
def render_template_slate_gray(session_state, profile_img_html=""):
    """Slate Gray — single-column, ATS-friendly, high-contrast text throughout.
    All body text ≥ #1e293b (near-black) for maximum readability and ATS parsing."""
    import re as _resg

    # Colour tokens — ALL contrast-tested against white (#ffffff)
    # Primary text  : #0f172a  (~18:1)  — headings, company names, candidate name
    # Secondary text: #1e293b  (~14:1)  — job titles, degree, body copy
    # Muted text    : #374151  (~10:1)  — dates, durations, details (replaces #64748b/#94a3b8)
    # Accent line   : #475569           — decorative only, never carries text
    C_PRIMARY   = "#0f172a"
    C_SECONDARY = "#1e293b"
    C_MUTED     = "#374151"   # replaces all former #64748b / #94a3b8 / #475569 text uses
    C_BODY      = "#1e293b"
    C_ACCENT    = "#475569"   # used ONLY for borders / decorative lines, not text

    # ── image ──────────────────────────────────────────────────────────────────
    def _fix_img(html, size=88):
        if not html:
            return ""
        img_match = _resg.search(r'<img[^>]*>', html)
        if not img_match:
            return ""
        img_tag = img_match.group(0)
        img_tag = _resg.sub(r"style=['\"][^'\"]*['\"]", "", img_tag)
        img_tag = img_tag.replace("<img ", f"<img style='width:{size}px;height:{size}px;border-radius:50%;"
                                  f"object-fit:cover;object-position:center;display:block;margin:0 auto 10px;"
                                  f"border:2px solid {C_ACCENT};' ")
        return img_tag

    # ── section header ─────────────────────────────────────────────────────────
    def section(title, content):
        return f"""
        <div style='margin-bottom:24px;'>
            <h2 style='font-size:14px;font-weight:800;letter-spacing:2px;text-transform:uppercase;
                color:{C_PRIMARY};border-bottom:2px solid {C_ACCENT};padding-bottom:5px;margin-bottom:14px;'>{title}</h2>
            {content}
        </div>"""

    # ── skill / tag pills ─────────────────────────────────────────────────────
    def pills(s, bg="#f1f5f9", color=None, border="#94a3b8"):
        _color = color if color else C_PRIMARY
        return "".join(
            f"<span style='display:inline-block;background:{bg};color:{_color};border:1px solid {border};"
            f"border-radius:4px;padding:4px 12px;margin:4px 4px 4px 0;font-size:13px;font-weight:700;'>{x.strip()}</span>"
            for x in s.split(',') if x.strip())

    # ── contact line ───────────────────────────────────────────────────────────
    def _contact_link(key, val):
        if key == 'email':
            return f"<a href='mailto:{val}' style='color:{C_PRIMARY};text-decoration:none;font-weight:500;'>{val}</a>"
        elif key in ('linkedin', 'portfolio', 'github'):
            href = val if val.startswith('http') else f"https://{val}"
            return f"<a href='{href}' target='_blank' style='color:{C_PRIMARY};text-decoration:none;font-weight:500;'>{val}</a>"
        else:
            return f"<span style='color:{C_PRIMARY};'>{val}</span>"

    contact_parts = []
    for key in ['email', 'phone', 'location', 'linkedin', 'portfolio', 'github']:
        val = session_state.get(key, '')
        if val:
            contact_parts.append(_contact_link(key, val))
    contact_line = " &nbsp;|&nbsp; ".join(contact_parts)

    # ── experience ────────────────────────────────────────────────────────────
    experience_html = ""
    for exp in session_state.experience_entries:
        if exp.get('company') or exp.get('title'):
            desc = _fmt_desc(exp.get('description', ''), font_size='14px', color=C_BODY, line_height='1.75')
            experience_html += f"""
            <div style='margin-bottom:18px;'>
                <div style='display:flex;justify-content:space-between;align-items:baseline;flex-wrap:wrap;gap:6px;'>
                    <strong style='font-size:16px;color:{C_PRIMARY};'>{exp.get('company','')}</strong>
                    <span style='font-size:13px;color:{C_MUTED};font-weight:600;background:#f1f5f9;
                          padding:2px 8px;border-radius:4px;border:1px solid #cbd5e1;'>{exp.get('duration','')}</span>
                </div>
                <div style='font-size:14px;color:{C_SECONDARY};font-weight:700;margin:4px 0 6px 0;'>{exp.get('title','')}</div>
                <div style='font-size:14px;color:{C_BODY};line-height:1.75;'>{desc}</div>
            </div>
            <hr style='border:none;border-top:1px solid #e2e8f0;margin:12px 0;'>"""

    # ── education ─────────────────────────────────────────────────────────────
    education_html = ""
    for edu in session_state.education_entries:
        if edu.get('institution') or edu.get('degree'):
            dv = edu.get('degree', '')
            if isinstance(dv, list):
                dv = ", ".join(dv)
            education_html += f"""
            <div style='margin-bottom:16px;'>
                <div style='display:flex;justify-content:space-between;flex-wrap:wrap;gap:6px;'>
                    <strong style='font-size:15px;color:{C_PRIMARY};'>{edu.get('institution','')}</strong>
                    <span style='font-size:13px;color:{C_MUTED};font-weight:600;background:#f1f5f9;
                          padding:2px 8px;border-radius:4px;border:1px solid #cbd5e1;'>{edu.get('year','')}</span>
                </div>
                <div style='font-size:14px;color:{C_SECONDARY};font-weight:600;font-style:italic;margin-top:3px;'>{dv}</div>
                <div style='font-size:13px;color:{C_MUTED};margin-top:3px;font-weight:500;'>{edu.get('details','')}</div>
            </div>"""

    # ── projects ──────────────────────────────────────────────────────────────
    projects_html = ""
    proj_links = getattr(session_state, 'project_links', []) or []
    for idx, proj in enumerate(session_state.project_entries):
        if proj.get('title'):
            desc = _fmt_desc(proj.get('description', ''), font_size='14px', color=C_BODY, line_height='1.75')
            proj_link_html = ""
            if idx < len(proj_links) and proj_links[idx]:
                proj_link_html = (f"<div style='margin-top:5px;font-size:13px;'>"
                                  f"<a href='{proj_links[idx]}' target='_blank' "
                                  f"style='color:{C_PRIMARY};font-weight:700;text-decoration:underline;'>"
                                  f"&#128279; View Project / GitHub</a></div>")
            projects_html += f"""
            <div style='margin-bottom:18px;padding:12px 14px;background:#f8fafc;
                        border-left:3px solid {C_ACCENT};border-radius:0 6px 6px 0;'>
                <div style='display:flex;justify-content:space-between;flex-wrap:wrap;gap:6px;'>
                    <strong style='font-size:15px;color:{C_PRIMARY};'>{proj.get('title','')}</strong>
                    <span style='font-size:13px;color:{C_MUTED};font-weight:600;'>{proj.get('duration','')}</span>
                </div>
                <div style='font-size:13px;color:{C_SECONDARY};font-weight:700;margin:4px 0;'>Tech Stack: {proj.get('tech','')}</div>
                <div style='font-size:14px;color:{C_BODY};line-height:1.75;'>{desc}</div>
                {proj_link_html}
            </div>"""

    # ── all project links ─────────────────────────────────────────────────────
    all_links_html = ""
    proj_links_all = getattr(session_state, 'project_links', []) or []
    if proj_links_all:
        all_links_html = "".join(
            f"<div style='margin-bottom:6px;'><a href='{lnk}' target='_blank' "
            f"style='color:{C_PRIMARY};font-weight:700;font-size:14px;text-decoration:underline;'>"
            f"&#128279; Project {i+1}: {lnk}</a></div>"
            for i, lnk in enumerate(proj_links_all) if lnk)

    # ── certifications ────────────────────────────────────────────────────────
    cert_html = ""
    for cert in (getattr(session_state, 'certificate_links', None) or []):
        if cert.get('name'):
            desc = _fmt_desc(cert.get('description', ''), font_size='13px', color=C_MUTED, line_height='1.7')
            cert_html += f"""
            <div style='margin-bottom:14px;padding:10px 12px;background:#f8fafc;
                        border-left:3px solid {C_ACCENT};border-radius:0 6px 6px 0;'>
                <div style='display:flex;justify-content:space-between;flex-wrap:wrap;gap:6px;'>
                    {_cert_name_html(cert, f'font-weight:700;color:{C_PRIMARY};font-size:15px;text-decoration:none;')}
                    <span style='font-size:13px;color:{C_MUTED};font-weight:600;background:#f1f5f9;
                          padding:2px 8px;border-radius:4px;border:1px solid #cbd5e1;'>{cert.get("duration","")}</span>
                </div>
                <div style='font-size:13px;color:{C_MUTED};margin-top:4px;'>{desc}</div>
            </div>"""

    summary_html = _fmt_desc(session_state.get('summary', ''), font_size='14px', color=C_BODY, line_height='1.8')
    fixed_img = _fix_img(profile_img_html)
    job_title_line = (f"<div style='font-size:16px;color:{C_SECONDARY};font-weight:700;margin-top:5px;letter-spacing:0.5px;'>"
                      f"{session_state.get('job_title','')}</div>") if session_state.get('job_title', '') else ""

    html_content = f"""<!DOCTYPE html>
<html lang='en'>
<head><meta charset='UTF-8'><meta name='viewport' content='width=device-width,initial-scale=1'><title>{session_state.get('name','')} - Resume</title>
<style>
  * {{ box-sizing:border-box; margin:0; padding:0; }}
  body {{ font-family:'Segoe UI',Arial,sans-serif; color:{C_PRIMARY}; background:#ffffff; padding:40px 60px; line-height:1.6; }}
  a {{ color:{C_PRIMARY}; }}
</style>
</head>
<body>
  <!-- HEADER -->
  <div style='text-align:center;margin-bottom:8px;'>
    {fixed_img}
    <h1 style='font-size:32px;font-weight:800;letter-spacing:1px;color:{C_PRIMARY};'>{session_state.get('name','')}</h1>
    {job_title_line}
    <div style='font-size:13px;color:{C_PRIMARY};margin-top:8px;font-weight:500;'>{contact_line}</div>
  </div>
  <hr style='border:none;border-top:3px solid {C_ACCENT};margin:16px 0 24px 0;'>

  {section("Professional Summary", summary_html) if summary_html else ''}
  {section("Work Experience", experience_html) if experience_html else ''}
  {section("Education", education_html) if education_html else ''}
  {section("Technical Skills", pills(session_state.get('skills',''))) if session_state.get('skills') else ''}
  {section("Core Competencies", pills(session_state.get('Softskills',''), bg='#f0f9ff', color='#0c4a6e', border='#7dd3fc')) if session_state.get('Softskills') else ''}
  {section("Languages", pills(session_state.get('languages',''), bg='#f0fdf4', color='#14532d', border='#86efac')) if session_state.get('languages') else ''}
  {section("Interests", pills(session_state.get('interests',''), bg='#fdf4ff', color='#581c87', border='#d8b4fe')) if session_state.get('interests') else ''}
  {section("Projects", projects_html) if projects_html else ''}
  {section("Project Links", all_links_html) if all_links_html else ''}
  {section("Certifications", cert_html) if cert_html else ''}
</body></html>"""

    return html_content


# ─────────────────────────────────────────────────────────────────────────────
# TEMPLATE 12 — Teal Impact (Two Column)
# ─────────────────────────────────────────────────────────────────────────────
def render_template_teal_impact(session_state, profile_img_html=""):
    """Teal Impact — two-column, teal sidebar, clean white main panel, ATS-friendly."""
    import re as _reti

    fixed_img = ""
    if profile_img_html:
        m = _reti.search(r'<img[^>]*>', profile_img_html)
        if m:
            tag = _reti.sub(r"style=['\"][^'\"]*['\"]", "", m.group(0))
            tag = tag.replace("<img ", "<img style='width:108px;height:108px;border-radius:50%;"
                              "object-fit:cover;object-position:center;border:3px solid rgba(255,255,255,0.5);"
                              "display:block;margin:0 auto;' ")
            fixed_img = tag

    def _badge_ti(item):
        return (f"<span style='display:inline-block;background:rgba(255,255,255,0.18);color:#ffffff;"
                f"border:1px solid rgba(255,255,255,0.35);border-radius:4px;padding:3px 10px;"
                f"margin:3px 3px 3px 0;font-size:12px;font-weight:600;'>{item.strip()}</span>")

    def _badges_ti(s):
        return "".join(_badge_ti(x) for x in s.split(',') if x.strip())

    def _side_ti(title, body):
        return (f"<div style='margin-bottom:22px;'>"
                f"<h3 style='font-size:10px;letter-spacing:2px;text-transform:uppercase;"
                f"color:#ffffff;font-weight:800;border-bottom:1px solid rgba(255,255,255,0.35);"
                f"padding-bottom:5px;margin-bottom:10px;'>{title}</h3>"
                f"{body}</div>")

    def _main_ti(title, body):
        return (f"<div style='margin-bottom:26px;'>"
                f"<h3 style='font-size:13px;letter-spacing:1.5px;text-transform:uppercase;"
                f"font-weight:700;color:#0f4c4c;border-bottom:2px solid #0d9488;"
                f"padding-bottom:5px;margin-bottom:14px;'>{title}</h3>"
                f"{body}</div>")

    SVG_TI = {
        'email':    '<svg xmlns="http://www.w3.org/2000/svg" width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M4 4h16c1.1 0 2 .9 2 2v12c0 1.1-.9 2-2 2H4c-1.1 0-2-.9-2-2V6c0-1.1.9-2 2-2z"/><polyline points="22,6 12,13 2,6"/></svg>',
        'phone':    '<svg xmlns="http://www.w3.org/2000/svg" width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M22 16.92v3a2 2 0 0 1-2.18 2 19.79 19.79 0 0 1-8.63-3.07A19.5 19.5 0 0 1 4.69 12 19.79 19.79 0 0 1 1.65 3.37 2 2 0 0 1 3.64 1h3a2 2 0 0 1 2 1.72c.127.96.361 1.903.7 2.81a2 2 0 0 1-.45 2.11L7.91 8.8a16 16 0 0 0 6.29 6.29l.98-.98a2 2 0 0 1 2.11-.45c.907.339 1.85.573 2.81.7A2 2 0 0 1 22 16.92z"/></svg>',
        'location': '<svg xmlns="http://www.w3.org/2000/svg" width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M21 10c0 7-9 13-9 13s-9-6-9-13a9 9 0 0 1 18 0z"/><circle cx="12" cy="10" r="3"/></svg>',
        'linkedin': '<svg xmlns="http://www.w3.org/2000/svg" width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M16 8a6 6 0 0 1 6 6v7h-4v-7a2 2 0 0 0-2-2 2 2 0 0 0-2 2v7h-4v-7a6 6 0 0 1 6-6z"/><rect x="2" y="9" width="4" height="12"/><circle cx="4" cy="4" r="2"/></svg>',
        'portfolio':'<svg xmlns="http://www.w3.org/2000/svg" width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><circle cx="12" cy="12" r="10"/><line x1="2" y1="12" x2="22" y2="12"/><path d="M12 2a15.3 15.3 0 0 1 4 10 15.3 15.3 0 0 1-4 10 15.3 15.3 0 0 1-4-10 15.3 15.3 0 0 1 4-10z"/></svg>',
    }
    contact_html_ti = ""
    for _key in ['location', 'phone', 'email', 'linkedin', 'portfolio']:
        val = session_state.get(_key, '')
        if not val:
            continue
        if _key == 'email':
            v = f"<a href='mailto:{val}' style='color:#ccfbf1;text-decoration:none;font-weight:500;word-break:break-all;'>{val}</a>"
        elif _key in ('linkedin', 'portfolio'):
            href = val if val.startswith('http') else f"https://{val}"
            v = f"<a href='{href}' target='_blank' style='color:#ccfbf1;text-decoration:none;font-weight:500;word-break:break-all;'>{val}</a>"
        else:
            v = f"<span style='color:#ccfbf1;word-break:break-all;'>{val}</span>"
        contact_html_ti += (f"<div style='margin-bottom:8px;font-size:12px;color:#ccfbf1;display:flex;align-items:center;gap:7px;'>"
                            f"<span style='opacity:0.85;flex-shrink:0;'>{SVG_TI.get(_key,'')}</span>{v}</div>")

    cert_html_ti = ""
    for cert in (getattr(session_state, 'certificate_links', None) or []):
        if cert.get('name'):
            cert_html_ti += (f"<div style='margin-bottom:9px;padding:7px 9px;background:rgba(255,255,255,0.1);"
                             f"border-radius:5px;border:1px solid rgba(255,255,255,0.2);'>"
                             f"{_cert_name_html(cert, 'color:#ccfbf1;font-size:12px;font-weight:700;text-decoration:none;')}"
                             f"<div style='font-size:11px;color:rgba(204,251,241,0.75);'>{cert.get('duration','')}</div></div>")

    proj_links_html_ti = ""
    if getattr(session_state, 'project_links', None):
        proj_links_html_ti = "".join(
            f"<div style='margin-bottom:5px;'><a href='{lnk}' target='_blank' style='color:#ccfbf1;font-size:12px;font-weight:600;'>&#128279; Project {i+1}</a></div>"
            for i, lnk in enumerate(getattr(session_state, 'project_links', []) or []))

    exp_html_ti = ""
    for exp in session_state.experience_entries:
        if exp.get('company') or exp.get('title'):
            desc = _fmt_desc(exp.get('description',''), font_size='13px', color='#1f2937', line_height='1.75')
            exp_html_ti += (
                f"<div style='margin-bottom:18px;padding-left:12px;border-left:3px solid #0d9488;'>"
                f"<div style='display:flex;justify-content:space-between;align-items:baseline;flex-wrap:wrap;gap:4px;'>"
                f"<strong style='font-size:14px;color:#0f4c4c;'>{exp.get('company','')}</strong>"
                f"<span style='font-size:12px;color:#6b7280;background:#f0fdfa;padding:2px 8px;border-radius:6px;border:1px solid #99f6e4;'>{exp.get('duration','')}</span>"
                f"</div>"
                f"<div style='font-size:13px;color:#374151;font-weight:700;margin-bottom:4px;'>{exp.get('title','')}</div>"
                f"<div>{desc}</div></div>"
                f"<div style='border-bottom:1px dashed #d1fae5;margin-bottom:10px;'></div>"
            )

    edu_html_ti = ""
    for edu in session_state.education_entries:
        if edu.get('institution'):
            dv = edu.get('degree','')
            if isinstance(dv, list):
                dv = ", ".join(dv)
            edu_html_ti += (
                f"<div style='margin-bottom:12px;padding-left:12px;border-left:3px solid #0d9488;'>"
                f"<strong style='font-size:13px;color:#0f4c4c;'>{edu.get('institution','')}</strong>"
                f"<span style='float:right;font-size:12px;color:#6b7280;'>{edu.get('year','')}</span>"
                f"<div style='clear:both;font-size:13px;color:#374151;font-style:italic;font-weight:600;'>{dv}</div>"
                f"<div style='font-size:12px;color:#6b7280;'>{edu.get('details','')}</div></div>"
            )

    proj_html_ti = ""
    proj_links_all_ti = getattr(session_state, 'project_links', []) or []
    for idx, proj in enumerate(session_state.project_entries):
        if proj.get('title'):
            desc = _fmt_desc(proj.get('description',''), font_size='13px', color='#1f2937', line_height='1.75')
            pl = ""
            if idx < len(proj_links_all_ti) and proj_links_all_ti[idx]:
                pl = (f"<div style='margin-top:4px;'><a href='{proj_links_all_ti[idx]}' target='_blank' "
                      f"style='color:#0d9488;font-size:12px;font-weight:600;'>&#128279; View Project</a></div>")
            proj_html_ti += (
                f"<div style='margin-bottom:14px;padding:10px 12px;background:#f0fdfa;"
                f"border-radius:6px;border-left:3px solid #0d9488;'>"
                f"<div style='display:flex;justify-content:space-between;flex-wrap:wrap;gap:4px;'>"
                f"<strong style='font-size:13px;color:#0f4c4c;'>{proj.get('title','')}</strong>"
                f"<span style='font-size:12px;color:#6b7280;'>{proj.get('duration','')}</span>"
                f"</div>"
                f"<div style='font-size:12px;color:#374151;font-weight:600;margin-bottom:3px;'>{proj.get('tech','')}</div>"
                f"<div>{desc}</div>{pl}</div>"
            )

    summary_html_ti = _fmt_desc(session_state.get('summary',''), font_size='13px', color='#1f2937', line_height='1.8')

    html_content = f"""<!DOCTYPE html>
<html lang='en'>
<head><meta charset='UTF-8'><meta name='viewport' content='width=device-width,initial-scale=1'><title>{session_state.get('name','')} - Resume</title>
<style>* {{ box-sizing:border-box; margin:0; padding:0; }} body {{ font-family:'Segoe UI',sans-serif; background:#fff; }}</style>
</head>
<body>
<table role='presentation' style='width:100%;min-height:100vh;border-collapse:collapse;table-layout:fixed;'>
<tr>
  <td style='width:290px;background:linear-gradient(180deg,#0f766e,#0d9488);color:#ccfbf1;padding:34px 22px;vertical-align:top;'>
    {'<div style="margin:0 auto 12px;text-align:center;">' + fixed_img + '</div>' if fixed_img else ''}
    <h1 style='font-size:20px;font-weight:800;color:#ffffff;text-align:center;margin-bottom:3px;'>{session_state.get('name','')}</h1>
    <div style='font-size:12px;color:#ccfbf1;text-align:center;margin-bottom:22px;font-weight:700;letter-spacing:1.2px;text-transform:uppercase;'>{session_state.get('job_title','')}</div>
    {_side_ti("Contact", contact_html_ti)}
    {_side_ti("Technical Skills", _badges_ti(session_state.get('skills',''))) if session_state.get('skills') else ''}
    {_side_ti("Soft Skills", _badges_ti(session_state.get('Softskills',''))) if session_state.get('Softskills') else ''}
    {_side_ti("Languages", _badges_ti(session_state.get('languages',''))) if session_state.get('languages') else ''}
    {_side_ti("Interests", _badges_ti(session_state.get('interests',''))) if session_state.get('interests') else ''}
    {_side_ti("Certifications", cert_html_ti) if cert_html_ti else ''}
    {_side_ti("Project Links", proj_links_html_ti) if proj_links_html_ti else ''}
  </td>
  <td style='padding:38px 42px;background:#ffffff;vertical-align:top;'>
    {_main_ti("Professional Summary", summary_html_ti) if summary_html_ti else ''}
    {_main_ti("Work Experience", exp_html_ti) if exp_html_ti else ''}
    {_main_ti("Education", edu_html_ti) if edu_html_ti else ''}
    {_main_ti("Projects", proj_html_ti) if proj_html_ti else ''}
  </td>
</tr>
</table>
</body></html>"""

    return html_content


# ─────────────────────────────────────────────────────────────────────────────
# TEMPLATE 13 — Burgundy Classic (Single Column)
# Layout standardized to match Classic Clean Single Column
# ─────────────────────────────────────────────────────────────────────────────
def render_template_burgundy_classic(session_state, profile_img_html=""):
    """Burgundy Classic — single-column, deep burgundy headers, ivory background.
    Layout matches Classic Clean Single Column for consistency."""
    import re as _rebc

    # ── image (same size/approach as Classic Clean) ───────────────────────────
    def _fix_img(html, size=88):
        if not html:
            return ""
        img_match = _rebc.search(r'<img[^>]*>', html)
        if not img_match:
            return ""
        img_tag = img_match.group(0)
        img_tag = _rebc.sub(r"style=['\"][^'\"]*['\"]", "", img_tag)
        img_tag = img_tag.replace("<img ", f"<img style='width:{size}px;height:{size}px;border-radius:50%;"
                                  f"object-fit:cover;object-position:center;display:block;margin:0 auto 10px;"
                                  f"border:2px solid #7f1d1d;' ")
        return img_tag

    # ── section — Burgundy colour identity, Classic Clean structure ───────────
    def section(title, content):
        return f"""
        <div style='margin-bottom:24px;'>
            <h2 style='font-size:14px;font-weight:700;letter-spacing:2px;text-transform:uppercase;
                color:#7f1d1d;border-bottom:2px solid #991b1b;padding-bottom:4px;margin-bottom:14px;
                font-family:"Georgia",serif;'>{title}</h2>
            {content}
        </div>"""

    # ── skill pills — Burgundy palette ────────────────────────────────────────
    def pills(s, bg="#fef2f2", color="#7f1d1d", border="#fecaca"):
        return "".join(
            f"<span style='display:inline-block;background:{bg};color:{color};border:1px solid {border};"
            f"border-radius:4px;padding:4px 12px;margin:4px 4px 4px 0;font-size:13px;font-weight:600;'>{x.strip()}</span>"
            for x in s.split(',') if x.strip())

    # ── contact line — identical structure to Classic Clean ───────────────────
    def _contact_link(key, val):
        if key == 'email':
            return f"<a href='mailto:{val}' style='color:#7f1d1d;text-decoration:none;'>{val}</a>"
        elif key in ('linkedin', 'portfolio', 'github'):
            href = val if val.startswith('http') else f"https://{val}"
            return f"<a href='{href}' target='_blank' style='color:#7f1d1d;text-decoration:none;'>{val}</a>"
        else:
            return val

    contact_parts = []
    for key in ['email', 'phone', 'location', 'linkedin', 'portfolio', 'github']:
        val = session_state.get(key, '')
        if val:
            contact_parts.append(_contact_link(key, val))
    contact_line = " &nbsp;|&nbsp; ".join(contact_parts)

    # ── experience ────────────────────────────────────────────────────────────
    experience_html = ""
    for exp in session_state.experience_entries:
        if exp.get('company') or exp.get('title'):
            desc = _fmt_desc(exp.get('description', ''), font_size='14px', color='#1c1c1c', line_height='1.75')
            experience_html += f"""
            <div style='margin-bottom:18px;'>
                <div style='display:flex;justify-content:space-between;align-items:baseline;'>
                    <strong style='font-size:16px;color:#1c1c1c;'>{exp.get('company','')}</strong>
                    <span style='font-size:13px;color:#6b7280;'>{exp.get('duration','')}</span>
                </div>
                <div style='font-size:14px;color:#7f1d1d;font-weight:600;font-style:italic;margin-bottom:6px;'>{exp.get('title','')}</div>
                <div style='font-size:14px;color:#1c1c1c;line-height:1.7;'>{desc}</div>
            </div>
            <hr style='border:none;border-top:1px solid #fde8e8;margin:12px 0;'>"""

    # ── education ─────────────────────────────────────────────────────────────
    education_html = ""
    for edu in session_state.education_entries:
        if edu.get('institution') or edu.get('degree'):
            dv = edu.get('degree', '')
            if isinstance(dv, list):
                dv = ", ".join(dv)
            education_html += f"""
            <div style='margin-bottom:14px;'>
                <div style='display:flex;justify-content:space-between;'>
                    <strong style='font-size:15px;color:#1c1c1c;'>{edu.get('institution','')}</strong>
                    <span style='font-size:13px;color:#6b7280;'>{edu.get('year','')}</span>
                </div>
                <div style='font-size:14px;color:#6b7280;font-style:italic;'>{dv}</div>
                <div style='font-size:13px;color:#9ca3af;'>{edu.get('details','')}</div>
            </div>"""

    # ── projects ──────────────────────────────────────────────────────────────
    projects_html = ""
    proj_links = getattr(session_state, 'project_links', []) or []
    for idx, proj in enumerate(session_state.project_entries):
        if proj.get('title'):
            desc = _fmt_desc(proj.get('description', ''), font_size='14px', color='#1c1c1c', line_height='1.75')
            proj_link_html = ""
            if idx < len(proj_links) and proj_links[idx]:
                proj_link_html = (f"<div style='margin-top:5px;font-size:13px;'>"
                                  f"<a href='{proj_links[idx]}' target='_blank' style='color:#991b1b;font-weight:600;'>&#128279; View Project / GitHub</a></div>")
            projects_html += f"""
            <div style='margin-bottom:16px;'>
                <div style='display:flex;justify-content:space-between;'>
                    <strong style='font-size:15px;color:#7f1d1d;'>{proj.get('title','')}</strong>
                    <span style='font-size:13px;color:#6b7280;'>{proj.get('duration','')}</span>
                </div>
                <div style='font-size:13px;color:#6b7280;margin-bottom:4px;'><b>Tech:</b> {proj.get('tech','')}</div>
                <div style='font-size:14px;color:#1c1c1c;line-height:1.6;'>{desc}</div>
                {proj_link_html}
            </div>"""

    # ── all project links ─────────────────────────────────────────────────────
    all_links_html = ""
    proj_links_all = getattr(session_state, 'project_links', []) or []
    if proj_links_all:
        all_links_html = "".join(
            f"<div style='margin-bottom:6px;'><a href='{lnk}' target='_blank' style='color:#991b1b;font-weight:600;font-size:14px;'>&#128279; Project {i+1}: {lnk}</a></div>"
            for i, lnk in enumerate(proj_links_all) if lnk)

    # ── certifications ────────────────────────────────────────────────────────
    cert_html = ""
    for cert in (getattr(session_state, 'certificate_links', None) or []):
        if cert.get('name'):
            desc = _fmt_desc(cert.get('description', ''), font_size='13px', color='#6b7280', line_height='1.7')
            cert_html += f"""
            <div style='margin-bottom:12px;'>
                <div style='display:flex;justify-content:space-between;'>
                    {_cert_name_html(cert, 'font-weight:600;color:#7f1d1d;font-size:15px;text-decoration:none;')}
                    <span style='font-size:13px;color:#6b7280;'>{cert.get("duration","")}</span>
                </div>
                <div style='font-size:13px;color:#6b7280;'>{desc}</div>
            </div>"""

    summary_html = _fmt_desc(session_state.get('summary', ''), font_size='14px', color='#1c1c1c', line_height='1.8')
    fixed_img = _fix_img(profile_img_html)
    job_title_line = (f"<div style='font-size:16px;color:#7f1d1d;font-weight:600;margin-top:4px;"
                      f"letter-spacing:0.5px;'>{session_state.get('job_title','')}</div>") if session_state.get('job_title', '') else ""

    html_content = f"""<!DOCTYPE html>
<html lang='en'>
<head><meta charset='UTF-8'><meta name='viewport' content='width=device-width,initial-scale=1'><title>{session_state.get('name','')} - Resume</title>
<style>
  * {{ box-sizing:border-box; margin:0; padding:0; }}
  body {{ font-family:'Georgia',serif; color:#1c1c1c; background:#fffafa; padding:40px 60px; line-height:1.6; }}
  a {{ color:#7f1d1d; }}
</style>
</head>
<body>
  <div style='text-align:center;margin-bottom:6px;'>
    {fixed_img}
    <h1 style='font-size:32px;font-weight:700;letter-spacing:1px;color:#7f1d1d;font-family:"Georgia",serif;'>{session_state.get('name','')}</h1>
    {job_title_line}
    <div style='font-size:13px;color:#6b7280;margin-top:6px;'>{contact_line}</div>
  </div>
  <hr style='border:none;border-top:3px double #991b1b;margin:16px 0 24px 0;'>

  {section("Professional Summary", summary_html) if summary_html else ''}
  {section("Work Experience", experience_html) if experience_html else ''}
  {section("Education", education_html) if education_html else ''}
  {section("Technical Skills", pills(session_state.get('skills',''))) if session_state.get('skills') else ''}
  {section("Core Competencies", pills(session_state.get('Softskills',''),'#fff7ed','#78350f','#fed7aa')) if session_state.get('Softskills') else ''}
  {section("Languages", pills(session_state.get('languages',''),'#f0fdf4','#14532d','#bbf7d0')) if session_state.get('languages') else ''}
  {section("Interests", pills(session_state.get('interests',''),'#fdf4ff','#581c87','#e9d5ff')) if session_state.get('interests') else ''}
  {section("Projects", projects_html) if projects_html else ''}
  {section("Project Links", all_links_html) if all_links_html else ''}
  {section("Certifications", cert_html) if cert_html else ''}
</body></html>"""

    return html_content


# ─────────────────────────────────────────────────────────────────────────────
# TEMPLATE 14 — Indigo Tech (Two Column)
# ─────────────────────────────────────────────────────────────────────────────
def render_template_indigo_tech(session_state, profile_img_html=""):
    """Indigo Tech — two-column, dark indigo sidebar with cyan accents, modern tech feel, ATS-friendly."""
    import re as _reit

    fixed_img = ""
    if profile_img_html:
        m = _reit.search(r'<img[^>]*>', profile_img_html)
        if m:
            tag = _reit.sub(r"style=['\"][^'\"]*['\"]", "", m.group(0))
            tag = tag.replace("<img ", "<img style='width:108px;height:108px;border-radius:50%;"
                              "object-fit:cover;object-position:center;border:3px solid #22d3ee;"
                              "display:block;margin:0 auto;' ")
            fixed_img = tag

    def _badge_it(item):
        return (f"<span style='display:inline-block;background:rgba(34,211,238,0.18);color:#a5f3fc;"
                f"border:1px solid rgba(34,211,238,0.4);border-radius:4px;padding:3px 10px;"
                f"margin:3px 3px 3px 0;font-size:12px;font-weight:600;'>{item.strip()}</span>")

    def _badges_it(s):
        return "".join(_badge_it(x) for x in s.split(',') if x.strip())

    def _side_it(title, body):
        return (f"<div style='margin-bottom:22px;'>"
                f"<h3 style='font-size:10px;letter-spacing:2px;text-transform:uppercase;"
                f"color:#22d3ee;font-weight:800;border-bottom:1px solid rgba(34,211,238,0.35);"
                f"padding-bottom:5px;margin-bottom:10px;'>{title}</h3>"
                f"{body}</div>")

    def _main_it(title, body):
        return (f"<div style='margin-bottom:26px;'>"
                f"<h3 style='font-size:13px;letter-spacing:1.5px;text-transform:uppercase;"
                f"font-weight:700;color:#1e1b4b;border-bottom:2px solid #4f46e5;"
                f"padding-bottom:5px;margin-bottom:14px;'>{title}</h3>"
                f"{body}</div>")

    SVG_IT = {
        'email':    '<svg xmlns="http://www.w3.org/2000/svg" width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M4 4h16c1.1 0 2 .9 2 2v12c0 1.1-.9 2-2 2H4c-1.1 0-2-.9-2-2V6c0-1.1.9-2 2-2z"/><polyline points="22,6 12,13 2,6"/></svg>',
        'phone':    '<svg xmlns="http://www.w3.org/2000/svg" width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M22 16.92v3a2 2 0 0 1-2.18 2 19.79 19.79 0 0 1-8.63-3.07A19.5 19.5 0 0 1 4.69 12 19.79 19.79 0 0 1 1.65 3.37 2 2 0 0 1 3.64 1h3a2 2 0 0 1 2 1.72c.127.96.361 1.903.7 2.81a2 2 0 0 1-.45 2.11L7.91 8.8a16 16 0 0 0 6.29 6.29l.98-.98a2 2 0 0 1 2.11-.45c.907.339 1.85.573 2.81.7A2 2 0 0 1 22 16.92z"/></svg>',
        'location': '<svg xmlns="http://www.w3.org/2000/svg" width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M21 10c0 7-9 13-9 13s-9-6-9-13a9 9 0 0 1 18 0z"/><circle cx="12" cy="10" r="3"/></svg>',
        'linkedin': '<svg xmlns="http://www.w3.org/2000/svg" width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M16 8a6 6 0 0 1 6 6v7h-4v-7a2 2 0 0 0-2-2 2 2 0 0 0-2 2v7h-4v-7a6 6 0 0 1 6-6z"/><rect x="2" y="9" width="4" height="12"/><circle cx="4" cy="4" r="2"/></svg>',
        'portfolio':'<svg xmlns="http://www.w3.org/2000/svg" width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><circle cx="12" cy="12" r="10"/><line x1="2" y1="12" x2="22" y2="12"/><path d="M12 2a15.3 15.3 0 0 1 4 10 15.3 15.3 0 0 1-4 10 15.3 15.3 0 0 1-4-10 15.3 15.3 0 0 1 4-10z"/></svg>',
    }
    contact_html_it = ""
    for _key in ['location', 'phone', 'email', 'linkedin', 'portfolio']:
        val = session_state.get(_key, '')
        if not val:
            continue
        if _key == 'email':
            v = f"<a href='mailto:{val}' style='color:#a5f3fc;text-decoration:none;font-weight:500;word-break:break-all;'>{val}</a>"
        elif _key in ('linkedin', 'portfolio'):
            href = val if val.startswith('http') else f"https://{val}"
            v = f"<a href='{href}' target='_blank' style='color:#a5f3fc;text-decoration:none;font-weight:500;word-break:break-all;'>{val}</a>"
        else:
            v = f"<span style='color:#a5f3fc;word-break:break-all;'>{val}</span>"
        contact_html_it += (f"<div style='margin-bottom:8px;font-size:12px;color:#a5f3fc;display:flex;align-items:center;gap:7px;'>"
                            f"<span style='opacity:0.85;flex-shrink:0;'>{SVG_IT.get(_key,'')}</span>{v}</div>")

    cert_html_it = ""
    for cert in (getattr(session_state, 'certificate_links', None) or []):
        if cert.get('name'):
            cert_html_it += (f"<div style='margin-bottom:9px;padding:7px 9px;background:rgba(34,211,238,0.1);"
                             f"border-radius:5px;border:1px solid rgba(34,211,238,0.3);'>"
                             f"{_cert_name_html(cert, 'color:#a5f3fc;font-size:12px;font-weight:700;text-decoration:none;')}"
                             f"<div style='font-size:11px;color:rgba(165,243,252,0.75);'>{cert.get('duration','')}</div></div>")

    proj_links_html_it = ""
    if getattr(session_state, 'project_links', None):
        proj_links_html_it = "".join(
            f"<div style='margin-bottom:5px;'><a href='{lnk}' target='_blank' style='color:#a5f3fc;font-size:12px;font-weight:600;'>&#128279; Project {i+1}</a></div>"
            for i, lnk in enumerate(getattr(session_state, 'project_links', []) or []))

    exp_html_it = ""
    for exp in session_state.experience_entries:
        if exp.get('company') or exp.get('title'):
            desc = _fmt_desc(exp.get('description',''), font_size='13px', color='#1f2937', line_height='1.75')
            exp_html_it += (
                f"<div style='margin-bottom:18px;padding-left:12px;border-left:3px solid #4f46e5;'>"
                f"<div style='display:flex;justify-content:space-between;align-items:baseline;flex-wrap:wrap;gap:4px;'>"
                f"<strong style='font-size:14px;color:#1e1b4b;'>{exp.get('company','')}</strong>"
                f"<span style='font-size:12px;color:#6b7280;background:#eef2ff;padding:2px 8px;border-radius:6px;border:1px solid #c7d2fe;'>{exp.get('duration','')}</span>"
                f"</div>"
                f"<div style='font-size:13px;color:#374151;font-weight:700;margin-bottom:4px;'>{exp.get('title','')}</div>"
                f"<div>{desc}</div></div>"
                f"<div style='border-bottom:1px dashed #e0e7ff;margin-bottom:10px;'></div>"
            )

    edu_html_it = ""
    for edu in session_state.education_entries:
        if edu.get('institution'):
            dv = edu.get('degree','')
            if isinstance(dv, list):
                dv = ", ".join(dv)
            edu_html_it += (
                f"<div style='margin-bottom:12px;padding-left:12px;border-left:3px solid #4f46e5;'>"
                f"<strong style='font-size:13px;color:#1e1b4b;'>{edu.get('institution','')}</strong>"
                f"<span style='float:right;font-size:12px;color:#6b7280;'>{edu.get('year','')}</span>"
                f"<div style='clear:both;font-size:13px;color:#374151;font-style:italic;font-weight:600;'>{dv}</div>"
                f"<div style='font-size:12px;color:#6b7280;'>{edu.get('details','')}</div></div>"
            )

    proj_html_it = ""
    proj_links_all_it = getattr(session_state, 'project_links', []) or []
    for idx, proj in enumerate(session_state.project_entries):
        if proj.get('title'):
            desc = _fmt_desc(proj.get('description',''), font_size='13px', color='#1f2937', line_height='1.75')
            pl = ""
            if idx < len(proj_links_all_it) and proj_links_all_it[idx]:
                pl = (f"<div style='margin-top:4px;'><a href='{proj_links_all_it[idx]}' target='_blank' "
                      f"style='color:#4f46e5;font-size:12px;font-weight:600;'>&#128279; View Project</a></div>")
            proj_html_it += (
                f"<div style='margin-bottom:14px;padding:10px 12px;background:#eef2ff;"
                f"border-radius:6px;border-left:3px solid #4f46e5;'>"
                f"<div style='display:flex;justify-content:space-between;flex-wrap:wrap;gap:4px;'>"
                f"<strong style='font-size:13px;color:#1e1b4b;'>{proj.get('title','')}</strong>"
                f"<span style='font-size:12px;color:#6b7280;'>{proj.get('duration','')}</span>"
                f"</div>"
                f"<div style='font-size:12px;color:#374151;font-weight:600;margin-bottom:3px;'>{proj.get('tech','')}</div>"
                f"<div>{desc}</div>{pl}</div>"
            )

    summary_html_it = _fmt_desc(session_state.get('summary',''), font_size='13px', color='#1f2937', line_height='1.8')

    html_content = f"""<!DOCTYPE html>
<html lang='en'>
<head><meta charset='UTF-8'><meta name='viewport' content='width=device-width,initial-scale=1'><title>{session_state.get('name','')} - Resume</title>
<style>* {{ box-sizing:border-box; margin:0; padding:0; }} body {{ font-family:'Segoe UI',sans-serif; background:#fff; }}</style>
</head>
<body>
<table role='presentation' style='width:100%;min-height:100vh;border-collapse:collapse;table-layout:fixed;'>
<tr>
  <td style='width:290px;background:linear-gradient(180deg,#1e1b4b,#312e81);color:#a5f3fc;padding:34px 22px;vertical-align:top;'>
    {'<div style="margin:0 auto 12px;text-align:center;">' + fixed_img + '</div>' if fixed_img else ''}
    <h1 style='font-size:20px;font-weight:800;color:#ffffff;text-align:center;margin-bottom:3px;'>{session_state.get('name','')}</h1>
    <div style='font-size:12px;color:#22d3ee;text-align:center;margin-bottom:22px;font-weight:700;letter-spacing:1.2px;text-transform:uppercase;'>{session_state.get('job_title','')}</div>
    {_side_it("Contact", contact_html_it)}
    {_side_it("Technical Skills", _badges_it(session_state.get('skills',''))) if session_state.get('skills') else ''}
    {_side_it("Soft Skills", _badges_it(session_state.get('Softskills',''))) if session_state.get('Softskills') else ''}
    {_side_it("Languages", _badges_it(session_state.get('languages',''))) if session_state.get('languages') else ''}
    {_side_it("Interests", _badges_it(session_state.get('interests',''))) if session_state.get('interests') else ''}
    {_side_it("Certifications", cert_html_it) if cert_html_it else ''}
    {_side_it("Project Links", proj_links_html_it) if proj_links_html_it else ''}
  </td>
  <td style='padding:38px 42px;background:#ffffff;vertical-align:top;'>
    {_main_it("Professional Summary", summary_html_it) if summary_html_it else ''}
    {_main_it("Work Experience", exp_html_it) if exp_html_it else ''}
    {_main_it("Education", edu_html_it) if edu_html_it else ''}
    {_main_it("Projects", proj_html_it) if proj_html_it else ''}
  </td>
</tr>
</table>
</body></html>"""

    return html_content


# ─────────────────────────────────────────────────────────────────────────────
# TEMPLATE 15 — Forest Green (Single Column)
# ─────────────────────────────────────────────────────────────────────────────
def render_template_forest_green(session_state, profile_img_html=""):
    """Forest Green — single-column, deep forest green headings, cream background, ATS-friendly."""
    import re as _refg

    fixed_img = ""
    if profile_img_html:
        m = _refg.search(r'<img[^>]*>', profile_img_html)
        if m:
            tag = _refg.sub(r"style=['\"][^'\"]*['\"]", "", m.group(0))
            tag = tag.replace("<img ", "<img style='width:96px;height:96px;border-radius:50%;"
                              "object-fit:cover;object-position:center;border:3px solid #166534;"
                              "display:block;margin:0 auto 12px;' ")
            fixed_img = tag

    def _sec_fg(title, body):
        return (f"<div style='margin-bottom:26px;'>"
                f"<h3 style='font-size:14px;font-weight:700;color:#14532d;text-transform:uppercase;"
                f"letter-spacing:2px;border-bottom:2px solid #166534;padding-bottom:5px;margin-bottom:14px;'>{title}</h3>"
                f"{body}</div>")

    def _tags_fg(s, bg="#f0fdf4", color="#14532d", border="#bbf7d0"):
        return "".join(
            f"<span style='display:inline-block;background:{bg};color:{color};border:1px solid {border};"
            f"border-radius:4px;padding:4px 11px;margin:3px 4px 3px 0;font-size:12px;font-weight:600;'>{x.strip()}</span>"
            for x in s.split(',') if x.strip())

    contact_parts_fg = []
    for key, label in [('location',''),('phone',''),('email',''),('linkedin','LinkedIn'),('portfolio','Portfolio')]:
        val = session_state.get(key, '')
        if not val:
            continue
        if key == 'email':
            contact_parts_fg.append(f"<a href='mailto:{val}' style='color:#14532d;text-decoration:none;font-weight:500;'>{val}</a>")
        elif key in ('linkedin','portfolio'):
            href = val if val.startswith('http') else f"https://{val}"
            contact_parts_fg.append(f"<a href='{href}' target='_blank' style='color:#14532d;text-decoration:none;font-weight:500;'>{label}: {val}</a>")
        else:
            contact_parts_fg.append(f"<span style='color:#1a3328;'>{val}</span>")
    contact_html_fg = " &nbsp;|&nbsp; ".join(contact_parts_fg)

    exp_html_fg = ""
    for exp in session_state.experience_entries:
        if exp.get('company') or exp.get('title'):
            desc = _fmt_desc(exp.get('description',''), font_size='13px', color='#1c1c1c', line_height='1.75')
            exp_html_fg += (
                f"<div style='margin-bottom:18px;padding-left:12px;border-left:3px solid #16a34a;'>"
                f"<div style='display:flex;justify-content:space-between;align-items:baseline;flex-wrap:wrap;gap:4px;'>"
                f"<strong style='font-size:14px;color:#14532d;'>{exp.get('title','')}</strong>"
                f"<span style='font-size:12px;color:#6b7280;background:#f0fdf4;padding:2px 8px;border-radius:5px;border:1px solid #bbf7d0;'>{exp.get('duration','')}</span>"
                f"</div>"
                f"<div style='font-size:13px;color:#374151;font-weight:600;margin-bottom:5px;'>{exp.get('company','')}</div>"
                f"<div>{desc}</div></div>"
                f"<div style='border-bottom:1px solid #dcfce7;margin-bottom:10px;'></div>"
            )

    edu_html_fg = ""
    for edu in session_state.education_entries:
        if edu.get('institution'):
            dv = edu.get('degree','')
            if isinstance(dv, list):
                dv = ", ".join(dv)
            edu_html_fg += (
                f"<div style='margin-bottom:12px;padding-left:12px;border-left:3px solid #16a34a;'>"
                f"<div style='display:flex;justify-content:space-between;align-items:baseline;flex-wrap:wrap;gap:4px;'>"
                f"<strong style='font-size:13px;color:#14532d;'>{edu.get('institution','')}</strong>"
                f"<span style='font-size:12px;color:#6b7280;'>{edu.get('year','')}</span>"
                f"</div>"
                f"<div style='font-size:13px;color:#374151;font-style:italic;font-weight:600;'>{dv}</div>"
                f"<div style='font-size:12px;color:#6b7280;'>{edu.get('details','')}</div></div>"
            )

    proj_html_fg = ""
    proj_links_all_fg = getattr(session_state, 'project_links', []) or []
    for idx, proj in enumerate(session_state.project_entries):
        if proj.get('title'):
            desc = _fmt_desc(proj.get('description',''), font_size='13px', color='#1c1c1c', line_height='1.75')
            pl = ""
            if idx < len(proj_links_all_fg) and proj_links_all_fg[idx]:
                pl = (f"<div style='margin-top:4px;'><a href='{proj_links_all_fg[idx]}' target='_blank' "
                      f"style='color:#16a34a;font-size:12px;font-weight:600;'>&#128279; View Project</a></div>")
            proj_html_fg += (
                f"<div style='margin-bottom:14px;padding:10px 12px;background:#f0fdf4;"
                f"border-radius:6px;border:1px solid #bbf7d0;'>"
                f"<div style='display:flex;justify-content:space-between;flex-wrap:wrap;gap:4px;'>"
                f"<strong style='font-size:13px;color:#14532d;'>{proj.get('title','')}</strong>"
                f"<span style='font-size:12px;color:#6b7280;'>{proj.get('duration','')}</span>"
                f"</div>"
                f"<div style='font-size:12px;color:#374151;font-weight:600;margin-bottom:3px;'>Tech: {proj.get('tech','')}</div>"
                f"<div>{desc}</div>{pl}</div>"
            )

    cert_html_fg = ""
    for cert in (getattr(session_state, 'certificate_links', None) or []):
        if cert.get('name'):
            cert_html_fg += (
                f"<div style='margin-bottom:10px;padding-left:10px;border-left:2px solid #86efac;'>"
                f"{_cert_name_html(cert, 'font-size:13px;font-weight:700;color:#14532d;text-decoration:none;')}"
                f"<span style='font-size:12px;color:#6b7280;'> — {cert.get('duration','')}</span></div>"
            )

    proj_links_sec_fg = ""
    if getattr(session_state, 'project_links', None):
        proj_links_sec_fg = "".join(
            f"<div style='margin-bottom:5px;'><a href='{lnk}' target='_blank' style='color:#16a34a;font-size:13px;font-weight:600;'>&#128279; Project {i+1}</a></div>"
            for i, lnk in enumerate(getattr(session_state, 'project_links', []) or []) if lnk)

    summary_html_fg = _fmt_desc(session_state.get('summary',''), font_size='13px', color='#1c1c1c', line_height='1.8')

    html_content = f"""<!DOCTYPE html>
<html lang='en'>
<head><meta charset='UTF-8'><meta name='viewport' content='width=device-width,initial-scale=1'><title>{session_state.get('name','')} - Resume</title></head>
<body style="font-family:'Segoe UI',Arial,sans-serif;line-height:1.6;color:#1c1c1c;background:#fafff7;max-width:794px;margin:0 auto;padding:36px 40px;">
  {fixed_img if fixed_img else ''}
  <div style="text-align:center;margin-bottom:28px;padding-bottom:18px;border-bottom:3px solid #166534;">
    <h1 style="font-size:28px;font-weight:800;color:#14532d;margin-bottom:4px;">{session_state.get('name','')}</h1>
    <div style="font-size:15px;color:#374151;font-weight:600;margin-bottom:10px;letter-spacing:1px;">{session_state.get('job_title','')}</div>
    <div style="font-size:12px;color:#1a3328;line-height:2;">{contact_html_fg}</div>
  </div>
  {_sec_fg("Professional Summary", f"<div style='font-size:13px;color:#1c1c1c;line-height:1.8;padding:12px 14px;background:#f0fdf4;border-radius:6px;border:1px solid #bbf7d0;'>{summary_html_fg}</div>") if summary_html_fg else ''}
  {_sec_fg("Work Experience", exp_html_fg) if exp_html_fg else ''}
  {_sec_fg("Education", edu_html_fg) if edu_html_fg else ''}
  {_sec_fg("Projects", proj_html_fg) if proj_html_fg else ''}
  {_sec_fg("Technical Skills", f"<div style='padding:6px 0;'>{_tags_fg(session_state.get('skills',''))}</div>") if session_state.get('skills','').strip() else ''}
  {_sec_fg("Core Competencies", f"<div style='padding:6px 0;'>{_tags_fg(session_state.get('Softskills',''),'#fefce8','#713f12','#fde68a')}</div>") if session_state.get('Softskills','').strip() else ''}
  {_sec_fg("Languages", f"<div style='padding:6px 0;'>{_tags_fg(session_state.get('languages',''),'#eff6ff','#1e3a8a','#bfdbfe')}</div>") if session_state.get('languages','').strip() else ''}
  {_sec_fg("Interests", f"<div style='padding:6px 0;'>{_tags_fg(session_state.get('interests',''),'#fdf4ff','#581c87','#e9d5ff')}</div>") if session_state.get('interests','').strip() else ''}
  {_sec_fg("Certifications", cert_html_fg) if cert_html_fg else ''}
  {_sec_fg("Project Links", proj_links_sec_fg) if proj_links_sec_fg else ''}
</body></html>"""

    return html_content


# ── Resume template registry ──────────────────────────────────────────────────
RESUME_TEMPLATES = {
    "Default (Professional)":           render_template_default,
    "Modern Minimal":                   render_template_modern,
    "Elegant Sidebar":                  render_template_sidebar,
    "Classic Clean (Single Column)":    render_template_classic,
    "Executive (Single Column)":        render_template_executive,
    "Timeline (Single Column)":         render_template_timeline,
    "Corporate Blue (Two Column)":      render_template_corporate,
    "Creative Green (Two Column)":      render_template_creative_green,
    "Warm Terracotta (Two Column)":     render_template_terracotta,
    "Navy Prestige (Two Column)":       render_template_navy_prestige,
    "Slate Gray (Single Column)":       render_template_slate_gray,
    "Teal Impact (Two Column)":         render_template_teal_impact,
    "Burgundy Classic (Single Column)": render_template_burgundy_classic,
    "Indigo Tech (Two Column)":         render_template_indigo_tech,
    "Forest Green (Single Column)":     render_template_forest_green,
}


def render_resume(template_name, session_state, profile_img_html=""):
    """
    Render a resume from a named template.

    Args:
        template_name (str): One of the keys in RESUME_TEMPLATES.
        session_state: Streamlit session_state (or any dict-like object).
        profile_img_html (str): Optional HTML <img> string for profile photo.

    Returns:
        str: Full HTML string for the resume.
    """
    fn = RESUME_TEMPLATES.get(template_name)
    if fn is None:
        fn = render_template_default
    return fn(session_state, profile_img_html)
