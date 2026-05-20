# cover_letter.py  — PDF-SAFE VERSION
# ══════════════════════════════════════════════════════════════════════════════
# All 6 cover letter templates rewritten to be xhtml2pdf-compatible:
#   - @page A4 rule in every template
#   - No display:flex  →  use <table> for side-by-side layouts
#   - No linear-gradient  →  solid colour fallbacks
#   - font sizes in pt not px
#   - page-break-inside:avoid on every content block
#   - body padding replaced with @page margins
# ══════════════════════════════════════════════════════════════════════════════


# ── shared PDF-safe base <style> injected into every template ─────────────────
_BASE_STYLE = """
  @page {{ size: A4 portrait; margin: 15mm 12mm 15mm 12mm; }}
  * {{ box-sizing:border-box; margin:0; padding:0; }}
  html, body {{ font-size:10pt; line-height:1.6; background:#fff; color:#1a1a1a; }}
  table {{ width:100%; border-collapse:collapse; table-layout:fixed; }}
  td {{ vertical-align:top; }}
  p  {{ margin:0 0 8pt 0; }}
  ul {{ margin:0 0 8pt 16pt; list-style-type:disc; }}
  li {{ margin-bottom:3pt; }}
  a  {{ text-decoration:none; color:inherit; }}
  hr {{ border:none; border-top:1pt solid #ccc; margin:8pt 0; }}
  .block {{ page-break-inside:avoid; }}
"""

def _contact_row(*parts):
    """Join non-empty contact parts with  ·  separator."""
    return " &nbsp;&middot;&nbsp; ".join(p for p in parts if p)


# ══════════════════════════════════════════════════════════════════════════════
# Template 1 — Professional / Corporate
# ══════════════════════════════════════════════════════════════════════════════
def render_cover_letter_professional(data):
    name           = data.get("name", "Your Name")
    job_title      = data.get("job_title", "")
    email          = data.get("email", "")
    phone          = data.get("phone", "")
    location       = data.get("location", "")
    linkedin       = data.get("linkedin", "")
    company        = data.get("company", "Hiring Company")
    hiring_manager = data.get("hiring_manager", "Hiring Manager")
    role           = data.get("role", "the position")
    date_str       = data.get("date", "")
    paragraphs     = data.get("body_paragraphs", [
        "I am writing to express my strong interest in the [Role] position at [Company].",
        "Throughout my career I have developed expertise in [Key Skills] and delivered measurable results.",
        "I am particularly drawn to [Company] and would welcome the opportunity to contribute to your team.",
    ])

    ACC = "#1e3a5f"

    contact_parts = []
    if email:    contact_parts.append(f"<a href='mailto:{email}' style='color:{ACC};'>{email}</a>")
    if phone:    contact_parts.append(phone)
    if location: contact_parts.append(location)
    if linkedin:
        href = linkedin if linkedin.startswith('http') else f"https://{linkedin}"
        contact_parts.append(f"<a href='{href}' style='color:{ACC};'>{linkedin}</a>")
    contact_line = " &nbsp;|&nbsp; ".join(contact_parts)

    paras_html = "".join(
        f"<p class='block' style='font-size:10.5pt;color:#1a1a1a;line-height:1.8;margin-bottom:10pt;text-align:justify;'>{p}</p>"
        for p in paragraphs
    )

    return f"""<!DOCTYPE html>
<html lang='en'>
<head><meta charset='UTF-8'><title>Cover Letter — {name}</title>
<style>
  {_BASE_STYLE}
  body {{ font-family:'Georgia',serif; }}
</style>
</head>
<body>
<div class='block' style='border-bottom:3pt solid {ACC};padding-bottom:12pt;margin-bottom:20pt;'>
  <div style='font-size:20pt;font-weight:700;color:{ACC};'>{name}</div>
  {'<div style="font-size:11pt;color:#374151;font-weight:600;margin-top:3pt;margin-bottom:6pt;">' + job_title + '</div>' if job_title else ''}
  <div style='font-size:9pt;color:#555;'>{contact_line}</div>
</div>

{'<p style="font-size:10pt;color:#374151;margin-bottom:14pt;">' + date_str + '</p>' if date_str else ''}

<div class='block' style='margin-bottom:18pt;'>
  <p style='font-size:10.5pt;font-weight:600;color:#1a1a1a;'>{hiring_manager}</p>
  <p style='font-size:10pt;color:#374151;'>{company}</p>
</div>

<p style='font-size:10.5pt;margin-bottom:14pt;'>Dear {hiring_manager},</p>

{paras_html}

<p class='block' style='font-size:10.5pt;color:#374151;margin-bottom:24pt;'>I would welcome the opportunity to discuss how my experience aligns with the needs of {company}. Thank you for your time and consideration.</p>

<p style='font-size:10.5pt;'>Sincerely,</p>
<p style='font-size:13pt;font-weight:700;color:{ACC};margin-top:10pt;'>{name}</p>
{'<p style="font-size:9pt;color:#555;margin-top:3pt;">' + job_title + '</p>' if job_title else ''}
</body></html>"""


# ══════════════════════════════════════════════════════════════════════════════
# Template 2 — Modern Minimal
# ══════════════════════════════════════════════════════════════════════════════
def render_cover_letter_modern(data):
    name           = data.get("name", "Your Name")
    job_title      = data.get("job_title", "")
    email          = data.get("email", "")
    phone          = data.get("phone", "")
    location       = data.get("location", "")
    linkedin       = data.get("linkedin", "")
    company        = data.get("company", "Company Name")
    hiring_manager = data.get("hiring_manager", "Hiring Manager")
    date_str       = data.get("date", "")
    paragraphs     = data.get("body_paragraphs", [
        "I'm excited to apply for the [Role] role at [Company]. My background in [Field] makes me a strong match.",
        "In my most recent role, I [Key Achievement], which led to [Result].",
        "What excites me most about [Company] is [Specific Reason].",
    ])

    ACC = "#0d9488"

    contact_parts = []
    if email:    contact_parts.append(f"<a href='mailto:{email}' style='color:{ACC};'>{email}</a>")
    if phone:    contact_parts.append(phone)
    if location: contact_parts.append(location)
    if linkedin:
        href = linkedin if linkedin.startswith('http') else f"https://{linkedin}"
        contact_parts.append(f"<a href='{href}' style='color:{ACC};'>{linkedin}</a>")
    contact_line = " &nbsp;&middot;&nbsp; ".join(contact_parts)

    paras_html = "".join(
        f"<p class='block' style='font-size:10.5pt;color:#374151;line-height:1.8;margin-bottom:10pt;'>{p}</p>"
        for p in paragraphs
    )

    # Use table for name-left / contact-right header (replaces display:flex)
    return f"""<!DOCTYPE html>
<html lang='en'>
<head><meta charset='UTF-8'><title>Cover Letter — {name}</title>
<style>
  {_BASE_STYLE}
  body {{ font-family:'Segoe UI',Arial,sans-serif; }}
</style>
</head>
<body>
<div class='block' style='border-bottom:3pt solid {ACC};padding-bottom:12pt;margin-bottom:24pt;'>
  <table>
    <tr>
      <td style='width:60%;'>
        <div style='font-size:19pt;font-weight:800;color:#0f172a;'>{name}</div>
        {'<div style="font-size:11pt;color:' + ACC + ';font-weight:600;margin-top:3pt;">' + job_title + '</div>' if job_title else ''}
      </td>
      <td style='width:40%;text-align:right;font-size:9pt;color:#6b7280;line-height:1.9;'>
        {contact_line}
      </td>
    </tr>
  </table>
</div>

{'<p style="font-size:9pt;color:#6b7280;margin-bottom:12pt;">' + date_str + '</p>' if date_str else ''}

<div class='block' style='margin-bottom:16pt;'>
  <p style='font-size:10.5pt;font-weight:600;color:#1f2937;'>{hiring_manager}</p>
  <p style='font-size:10pt;color:#6b7280;'>{company}</p>
</div>

<p style='font-size:10.5pt;margin-bottom:14pt;'>Dear {hiring_manager},</p>

{paras_html}

<p class='block' style='font-size:10.5pt;color:#374151;margin-bottom:24pt;'>I'd love the chance to chat about how I can contribute to {company}. Thank you for considering my application.</p>

<p style='font-size:10.5pt;'>Best regards,</p>
<div style='margin-top:10pt;padding-top:8pt;border-top:2pt solid {ACC};'>
  <p style='font-size:13pt;font-weight:700;color:#0f172a;'>{name}</p>
  {'<p style="font-size:9pt;color:' + ACC + ';margin-top:2pt;">' + job_title + '</p>' if job_title else ''}
</div>
</body></html>"""


# ══════════════════════════════════════════════════════════════════════════════
# Template 3 — Creative
# ══════════════════════════════════════════════════════════════════════════════
def render_cover_letter_creative(data):
    name           = data.get("name", "Your Name")
    job_title      = data.get("job_title", "")
    email          = data.get("email", "")
    phone          = data.get("phone", "")
    location       = data.get("location", "")
    linkedin       = data.get("linkedin", "")
    portfolio      = data.get("portfolio", "")
    company        = data.get("company", "Company Name")
    hiring_manager = data.get("hiring_manager", "Hiring Team")
    date_str       = data.get("date", "")
    accent         = data.get("accent_color", "#7c3aed")
    paragraphs     = data.get("body_paragraphs", [
        "Great design solves real problems — and that's exactly the philosophy I bring to every project.",
        "My background in [Field] has equipped me with [Skills]. At [Previous Company], I led [Project] which resulted in [Outcome].",
        "I'm inspired by [Company]'s approach to [Specific Work]. I would love to contribute my skills to your projects.",
    ])

    contact_parts = []
    if email:     contact_parts.append(f"<a href='mailto:{email}' style='color:#fff;'>{email}</a>")
    if phone:     contact_parts.append(f"<span style='color:rgba(255,255,255,0.85);'>{phone}</span>")
    if location:  contact_parts.append(f"<span style='color:rgba(255,255,255,0.85);'>{location}</span>")
    if linkedin:
        href = linkedin if linkedin.startswith('http') else f"https://{linkedin}"
        contact_parts.append(f"<a href='{href}' style='color:#fff;'>{linkedin}</a>")
    if portfolio:
        href = portfolio if portfolio.startswith('http') else f"https://{portfolio}"
        contact_parts.append(f"<a href='{href}' style='color:#fff;'>{portfolio}</a>")
    contact_line = " &nbsp;&bull;&nbsp; ".join(contact_parts)

    paras_html = "".join(
        f"<p class='block' style='font-size:10.5pt;color:#1f2937;line-height:1.85;margin-bottom:10pt;'>{p}</p>"
        for p in paragraphs
    )

    return f"""<!DOCTYPE html>
<html lang='en'>
<head><meta charset='UTF-8'><title>Cover Letter — {name}</title>
<style>
  {_BASE_STYLE}
  body {{ font-family:'Segoe UI',Arial,sans-serif; }}
</style>
</head>
<body>
<!-- Header band: solid colour (no gradient — xhtml2pdf safe) -->
<div class='block' style='background:{accent};padding:28pt 40pt 22pt;margin-bottom:0;'>
  <div style='font-size:22pt;font-weight:800;color:#ffffff;margin-bottom:3pt;'>{name}</div>
  {'<div style="font-size:11pt;color:rgba(255,255,255,0.85);font-weight:600;margin-bottom:8pt;">' + job_title + '</div>' if job_title else ''}
  <div style='font-size:8.5pt;color:rgba(255,255,255,0.85);'>{contact_line}</div>
</div>

<!-- Body area -->
<div style='padding:24pt 40pt 24pt;'>
  {'<p style="font-size:9pt;color:#9ca3af;margin-bottom:14pt;">' + date_str + '</p>' if date_str else ''}

  <div class='block' style='margin-bottom:16pt;'>
    <p style='font-size:10.5pt;font-weight:700;color:#1f2937;'>{hiring_manager}</p>
    <p style='font-size:10pt;color:#6b7280;'>{company}</p>
  </div>

  <p style='font-size:10.5pt;margin-bottom:14pt;'>Dear {hiring_manager},</p>

  {paras_html}

  <p class='block' style='font-size:10.5pt;color:#374151;margin-bottom:24pt;'>I would be thrilled to discuss this further. Thank you for your time.</p>

  <p style='font-size:10.5pt;'>Warmly,</p>
  <p style='font-size:14pt;font-weight:800;color:{accent};margin-top:8pt;'>{name}</p>
  {'<p style="font-size:9pt;color:#6b7280;margin-top:2pt;">' + job_title + '</p>' if job_title else ''}
</div>
</body></html>"""


# ══════════════════════════════════════════════════════════════════════════════
# Template 4 — Executive
# ══════════════════════════════════════════════════════════════════════════════
def render_cover_letter_executive(data):
    name           = data.get("name", "Your Name")
    job_title      = data.get("job_title", "")
    email          = data.get("email", "")
    phone          = data.get("phone", "")
    location       = data.get("location", "")
    linkedin       = data.get("linkedin", "")
    company        = data.get("company", "Company Name")
    hiring_manager = data.get("hiring_manager", "Board / Search Committee")
    date_str       = data.get("date", "")
    paragraphs     = data.get("body_paragraphs", [
        "With over [X] years leading [Function] in [Industry], I bring a track record of driving strategic growth.",
        "At [Previous Organization], I spearheaded [Initiative], resulting in [Revenue/Efficiency Outcome].",
        "I am drawn to [Company] because of its [Specific Initiative, Vision, or Market Position].",
    ])

    DARK  = "#0d1b2a"
    GOLD  = "#d4af37"

    contact_parts = []
    if email:    contact_parts.append(f"<a href='mailto:{email}' style='color:{GOLD};'>{email}</a>")
    if phone:    contact_parts.append(phone)
    if location: contact_parts.append(location)
    if linkedin:
        href = linkedin if linkedin.startswith('http') else f"https://{linkedin}"
        contact_parts.append(f"<a href='{href}' style='color:{GOLD};'>{linkedin}</a>")
    contact_line = " &nbsp;|&nbsp; ".join(contact_parts)

    paras_html = "".join(
        f"<p class='block' style='font-size:10.5pt;color:#1a1a1a;line-height:1.85;margin-bottom:10pt;text-align:justify;'>{p}</p>"
        for p in paragraphs
    )

    return f"""<!DOCTYPE html>
<html lang='en'>
<head><meta charset='UTF-8'><title>Cover Letter — {name}</title>
<style>
  {_BASE_STYLE}
  body {{ font-family:'Georgia',serif; }}
</style>
</head>
<body>
<!-- Dark header — solid colour (no gradient) -->
<div class='block' style='background:{DARK};padding:30pt 48pt 24pt;margin-bottom:0;'>
  <div style='font-size:20pt;font-weight:700;color:#ffffff;margin-bottom:3pt;'>{name}</div>
  {'<div style="font-size:10pt;color:' + GOLD + ';font-weight:600;margin-bottom:10pt;">' + job_title + '</div>' if job_title else ''}
  <div style='font-size:9pt;color:#adb5bd;'>{contact_line}</div>
</div>
<!-- Gold rule -->
<div style='height:3pt;background:{GOLD};margin-bottom:0;'></div>

<div style='padding:30pt 48pt;'>
  {'<p style="font-size:9.5pt;color:#6b7280;margin-bottom:18pt;">' + date_str + '</p>' if date_str else ''}

  <div class='block' style='margin-bottom:20pt;'>
    <p style='font-size:10.5pt;font-weight:700;color:{DARK};'>{hiring_manager}</p>
    <p style='font-size:10pt;color:#374151;'>{company}</p>
  </div>

  <p style='font-size:10.5pt;margin-bottom:16pt;'>Dear {hiring_manager},</p>

  {paras_html}

  <p class='block' style='font-size:10.5pt;color:#374151;margin-bottom:28pt;'>I welcome the opportunity to explore this further at your convenience. Please find my resume enclosed for your review.</p>

  <p style='font-size:10.5pt;'>Respectfully yours,</p>
  <p style='font-size:14pt;font-weight:700;color:{DARK};margin-top:10pt;'>{name}</p>
  {'<p style="font-size:9pt;color:' + GOLD + ';font-weight:600;margin-top:3pt;">' + job_title + '</p>' if job_title else ''}
</div>
</body></html>"""


# ══════════════════════════════════════════════════════════════════════════════
# Template 5 — Entry-Level / Fresher
# ══════════════════════════════════════════════════════════════════════════════
def render_cover_letter_entry_level(data):
    name           = data.get("name", "Your Name")
    job_title      = data.get("job_title", "")
    email          = data.get("email", "")
    phone          = data.get("phone", "")
    location       = data.get("location", "")
    linkedin       = data.get("linkedin", "")
    company        = data.get("company", "Company Name")
    hiring_manager = data.get("hiring_manager", "Hiring Manager")
    date_str       = data.get("date", "")
    paragraphs     = data.get("body_paragraphs", [
        "I am a recent graduate in [Field] from [University] and am excited to apply for the [Role] at [Company].",
        "During my studies, I developed strong skills in [Skill 1], [Skill 2], and [Skill 3].",
        "I am eager to grow within a company like [Company] that values [Culture Value].",
    ])

    ACC = "#1d4ed8"

    contact_parts = []
    if email:    contact_parts.append(f"<a href='mailto:{email}' style='color:{ACC};'>{email}</a>")
    if phone:    contact_parts.append(phone)
    if location: contact_parts.append(location)
    if linkedin:
        href = linkedin if linkedin.startswith('http') else f"https://{linkedin}"
        contact_parts.append(f"<a href='{href}' style='color:{ACC};'>{linkedin}</a>")
    contact_line = " &nbsp;|&nbsp; ".join(contact_parts)

    paras_html = "".join(
        f"<p class='block' style='font-size:10.5pt;color:#374151;line-height:1.8;margin-bottom:10pt;'>{p}</p>"
        for p in paragraphs
    )

    return f"""<!DOCTYPE html>
<html lang='en'>
<head><meta charset='UTF-8'><title>Cover Letter — {name}</title>
<style>
  {_BASE_STYLE}
  body {{ font-family:'Segoe UI',Arial,sans-serif; }}
</style>
</head>
<body>
<!-- Header: left border accent, light blue bg (no gradient) -->
<div class='block' style='background:#eff6ff;border-left:4pt solid {ACC};padding:16pt 20pt;margin-bottom:22pt;'>
  <div style='font-size:17pt;font-weight:800;color:#1e3a8a;margin-bottom:2pt;'>{name}</div>
  {'<div style="font-size:10.5pt;color:' + ACC + ';font-weight:600;margin-bottom:6pt;">' + job_title + '</div>' if job_title else ''}
  <div style='font-size:9pt;color:#6b7280;'>{contact_line}</div>
</div>

{'<p style="font-size:9.5pt;color:#9ca3af;margin-bottom:14pt;">' + date_str + '</p>' if date_str else ''}

<div class='block' style='margin-bottom:18pt;'>
  <p style='font-size:10.5pt;font-weight:600;color:#1f2937;'>{hiring_manager}</p>
  <p style='font-size:10pt;color:#6b7280;'>{company}</p>
</div>

<p style='font-size:10.5pt;margin-bottom:14pt;'>Dear {hiring_manager},</p>

{paras_html}

<p class='block' style='font-size:10.5pt;color:#374151;margin-bottom:22pt;'>I would be grateful for the opportunity to interview and learn more about this role. Thank you for your time and consideration.</p>

<p style='font-size:10.5pt;'>Sincerely,</p>
<p style='font-size:13pt;font-weight:700;color:#1e3a8a;margin-top:10pt;'>{name}</p>
{'<p style="font-size:9pt;color:#6b7280;margin-top:2pt;">' + job_title + '</p>' if job_title else ''}
</body></html>"""


# ══════════════════════════════════════════════════════════════════════════════
# Template 6 — Technical / ATS-Optimised
# ══════════════════════════════════════════════════════════════════════════════
def render_cover_letter_ats(data):
    name           = data.get("name", "Your Name")
    job_title      = data.get("job_title", "")
    email          = data.get("email", "")
    phone          = data.get("phone", "")
    location       = data.get("location", "")
    linkedin       = data.get("linkedin", "")
    portfolio      = data.get("portfolio", "")
    company        = data.get("company", "Company Name")
    hiring_manager = data.get("hiring_manager", "Hiring Manager")
    role           = data.get("role", "the position")
    date_str       = data.get("date", "")
    key_skills     = data.get("key_skills", "Python, Machine Learning, SQL, Agile")
    paragraphs     = data.get("body_paragraphs", [
        "I am applying for the [Role] position at [Company]. My technical background includes [Key Skills].",
        "In my current role, I [Technical Achievement] using [Technologies], resulting in [Measurable Outcome].",
        "I am particularly interested in [Company]'s work on [Product/Technology Stack].",
    ])

    header_line = f"{name} | {job_title}" if job_title else name

    details = []
    if email:    details.append(email)
    if phone:    details.append(phone)
    if location: details.append(location)
    if linkedin: details.append(linkedin)
    if portfolio:details.append(portfolio)
    details_line = " | ".join(details)

    paras_html = "".join(
        f"<p class='block' style='font-size:10.5pt;color:#111827;line-height:1.8;margin-bottom:10pt;'>{p}</p>"
        for p in paragraphs
    )

    return f"""<!DOCTYPE html>
<html lang='en'>
<head><meta charset='UTF-8'><title>Cover Letter — {name}</title>
<style>
  {_BASE_STYLE}
  body {{ font-family:Arial,Helvetica,sans-serif; }}
</style>
</head>
<body>
<!-- ATS plain text header — zero graphics -->
<div class='block' style='margin-bottom:4pt;'>
  <p style='font-size:15pt;font-weight:700;color:#111827;'>{header_line}</p>
  <p style='font-size:9.5pt;color:#374151;margin-top:3pt;'>{details_line}</p>
</div>
<hr>

{'<p style="margin-bottom:12pt;color:#374151;font-size:10pt;">' + date_str + '</p>' if date_str else ''}

<div class='block' style='margin-bottom:16pt;'>
  <p style='font-weight:600;color:#111827;font-size:10.5pt;'>{hiring_manager}</p>
  <p style='color:#374151;font-size:10pt;'>{company}</p>
</div>

<p style='font-weight:700;margin-bottom:14pt;font-size:10.5pt;'>Re: Application for {role} — {name}</p>

<p style='margin-bottom:14pt;font-size:10.5pt;'>Dear {hiring_manager},</p>

{paras_html}

<p class='block' style='font-size:10.5pt;color:#111827;line-height:1.8;margin-bottom:10pt;'>
  <strong>Core Technical Skills:</strong> {key_skills}
</p>

<p class='block' style='margin-bottom:24pt;color:#374151;font-size:10.5pt;'>I have attached my resume for your review. I am available for an interview at your earliest convenience.</p>

<p style='font-size:10.5pt;'>Sincerely,</p>
<p style='font-weight:700;font-size:12pt;margin-top:8pt;'>{name}</p>
{'<p style="color:#374151;margin-top:2pt;font-size:9.5pt;">' + job_title + '</p>' if job_title else ''}
</body></html>"""


# ── Registry ──────────────────────────────────────────────────────────────────
COVER_LETTER_TEMPLATES = {
    "Professional / Corporate":     render_cover_letter_professional,
    "Modern Minimal":               render_cover_letter_modern,
    "Creative":                     render_cover_letter_creative,
    "Executive":                    render_cover_letter_executive,
    "Entry-Level / Fresher":        render_cover_letter_entry_level,
    "Technical / ATS-Optimized":    render_cover_letter_ats,
}


def render_cover_letter(template_name, data):
    fn = COVER_LETTER_TEMPLATES.get(template_name, render_cover_letter_professional)
    return fn(data)


# ── Streamlit UI (unchanged logic, only imports updated) ──────────────────────
def generate_cover_letter_from_resume_builder():
    import streamlit as st
    from datetime import datetime, timezone, timedelta
    import re as _cl_re

    name      = st.session_state.get("name", "")
    job_title = st.session_state.get("job_title", "")
    summary   = st.session_state.get("summary", "")
    skills    = st.session_state.get("skills", "")
    location  = st.session_state.get("location", "")

    IST        = timezone(timedelta(hours=5, minutes=30))
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
        linkedin      = st.text_input("🔗 LinkedIn URL", placeholder="e.g., https://linkedin.com/in/username")
        email         = st.text_input("📧 Email", placeholder="e.g., you@example.com")
        mobile        = st.text_input("📞 Mobile Number", placeholder="e.g., +91 9876543210")
        submitted_cl  = st.form_submit_button("✉️ Generate Cover Letter")

    if cover_letter_template != "Creative":
        accent_color = "#003366"

    if submitted_cl:
        if not all([name, job_title, summary, skills, company, linkedin, email, mobile]):
            st.warning("⚠️ Please fill in all fields including LinkedIn, email, and mobile.")
            return

        from llm_manager import call_llm

        prompt = f"""You are a professional cover letter writer.

Write ONLY the body paragraphs of a cover letter for the candidate below.
Do NOT include: date, recipient address, salutation, closing, or the candidate's name.
Output exactly 3 paragraphs separated by a blank line. Each paragraph 2-4 sentences.

Candidate Info:
- Name: {name}
- Job Title: {job_title}
- Target Company: {company}
- Location: {location}
- Summary: {summary}
- Skills: {skills}

Return plain text body paragraphs ONLY — no HTML tags, no greeting, no sign-off."""

        with st.spinner("✉️ Crafting your cover letter..."):
            cover_letter_raw = call_llm(prompt, session=st.session_state).strip()

        def _strip_boilerplate(text):
            lines = text.split('\n')
            skip = [
                _cl_re.compile(p, _cl_re.IGNORECASE) for p in [
                    r'^\s*(january|february|march|april|may|june|july|august|september|october|november|december)\s+\d',
                    r'^\s*\d{1,2}[\/\-]\d{1,2}[\/\-]\d{2,4}',
                    r'^\s*dear\b',
                    r'^\s*(sincerely|regards|best regards|yours truly|warm regards|respectfully)',
                    r'^\s*hiring manager[,.]?\s*$',
                ]
            ]
            return '\n'.join(l for l in lines if not any(r.match(l) for r in skip)).strip()

        body = _strip_boilerplate(cover_letter_raw)
        st.session_state["cover_letter"] = body

        normalised   = _cl_re.sub(r'\n{3,}', '\n\n', body)
        raw_paras    = normalised.split('\n\n')
        if len(raw_paras) <= 1:
            raw_paras = normalised.split('\n')
        body_paragraphs = [p.strip() for p in raw_paras if p.strip()]

        cl_data = {
            "name": name, "job_title": job_title, "email": email,
            "phone": mobile, "location": location, "linkedin": linkedin,
            "portfolio": "", "company": company, "hiring_manager": "Hiring Manager",
            "role": job_title, "date": today_date,
            "body_paragraphs": body_paragraphs,
            "key_skills": skills, "accent_color": accent_color,
        }

        cover_letter_html = render_cover_letter(cover_letter_template, cl_data)
        st.session_state["cover_letter_html"] = cover_letter_html

        import streamlit.components.v1 as _cl_components
        st.success("✅ Cover letter generated successfully!")
        st.markdown("<p style='color:#555;font-size:13px;margin-top:8px;'>📄 Cover Letter Preview:</p>", unsafe_allow_html=True)
        _cl_components.html(cover_letter_html, height=700, scrolling=True)
