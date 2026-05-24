# cover_letter.py
# ══════════════════════════════════════════════════════════════════════════════
# 10 premium HTML cover letter templates — rebuilt from scratch
# Inspired by Enhancv, Novoresume, Resume.io, Canva Cover Letters
#
# Imports:
#   from cover_letter import (
#       render_cover_letter_cobalt, render_cover_letter_emerald,
#       render_cover_letter_executive_dark, render_cover_letter_creative_coral,
#       render_cover_letter_minimal_mono, render_cover_letter_slate,
#       render_cover_letter_golden, render_cover_letter_entry_level,
#       render_cover_letter_ats_clean, render_cover_letter_sidebar_accent,
#       COVER_LETTER_TEMPLATES, render_cover_letter,
#       generate_cover_letter_from_resume_builder,
#   )
# ══════════════════════════════════════════════════════════════════════════════

# ─────────────────────────────────────────────────────────────────────────────
# SHARED HELPER
# ─────────────────────────────────────────────────────────────────────────────

def _contact_row(data, link_color="#1e3a5f", sep=" &nbsp;|&nbsp; "):
    """Build the contact info HTML string from data dict."""
    parts = []
    email    = data.get("email", "")
    phone    = data.get("phone", "")
    location = data.get("location", "")
    linkedin = data.get("linkedin", "")
    portfolio= data.get("portfolio", "")
    if email:
        parts.append(f"<a href='mailto:{email}' style='color:{link_color};text-decoration:none;'>{email}</a>")
    if phone:
        parts.append(f"<span>{phone}</span>")
    if location:
        parts.append(f"<span>{location}</span>")
    if linkedin:
        href = linkedin if linkedin.startswith("http") else f"https://{linkedin}"
        parts.append(f"<a href='{href}' target='_blank' style='color:{link_color};text-decoration:none;'>{linkedin}</a>")
    if portfolio:
        href = portfolio if portfolio.startswith("http") else f"https://{portfolio}"
        parts.append(f"<a href='{href}' target='_blank' style='color:{link_color};text-decoration:none;'>{portfolio}</a>")
    return sep.join(parts)

def _paras_html(paragraphs, style="margin-bottom:16px;font-size:14px;color:#1f2937;line-height:1.85;"):
    return "".join(f"<p style='{style}'>{p}</p>" for p in paragraphs)

def _default_paras():
    return [
        "I am writing to express my strong interest in the [Role] position at [Company]. "
        "With my background in [Field] and a consistent track record of [Achievement], "
        "I am confident I can make an immediate and meaningful contribution to your team.",
        "In my previous role at [Previous Company], I successfully [Key Achievement], "
        "which resulted in [Measurable Outcome]. This experience has strengthened my expertise in "
        "[Skill 1], [Skill 2], and [Skill 3] — all of which are directly relevant to this opportunity.",
        "I am particularly drawn to [Company] because of [Specific Reason]. "
        "I am excited about the prospect of bringing my skills and enthusiasm to your organization "
        "and helping achieve [Company Goal]. I look forward to the opportunity to discuss my application.",
    ]


# ══════════════════════════════════════════════════════════════════════════════
# TEMPLATE 1 — Cobalt Professional
# Deep cobalt blue header band, white name, clean body.
# Best for: Finance, Consulting, Banking, Law, Corporate roles.
# ══════════════════════════════════════════════════════════════════════════════
def render_cover_letter_cobalt(data):
    name           = data.get("name", "Your Name")
    job_title      = data.get("job_title", "")
    company        = data.get("company", "Hiring Company")
    hiring_manager = data.get("hiring_manager", "Hiring Manager")
    role           = data.get("role", "the position")
    date_str       = data.get("date", "")
    paragraphs     = data.get("body_paragraphs", _default_paras())

    contact = _contact_row(data, link_color="#93c5fd", sep=" &nbsp;·&nbsp; ")
    body    = _paras_html(paragraphs, "margin-bottom:16px;font-size:14px;color:#1a1a1a;line-height:1.85;text-align:justify;")

    return f"""<!DOCTYPE html>
<html lang='en'>
<head><meta charset='UTF-8'><title>Cover Letter — {name}</title>
<style>
* {{ box-sizing:border-box; margin:0; padding:0; }}
body {{ font-family:'Segoe UI',Arial,sans-serif; background:#fff; color:#1a1a1a; padding:0; line-height:1.6; }}
</style></head>
<body>
<div>
  <!-- COBALT HEADER BAND -->
  <div style='background:#1b3a6b;padding:36px 60px 28px;'>
    <h1 style='font-size:30px;font-weight:800;color:#ffffff;letter-spacing:0.5px;margin-bottom:4px;'>{name}</h1>
    {f"<div style='font-size:14px;color:#93c5fd;font-weight:600;margin-bottom:10px;'>{job_title}</div>" if job_title else ""}
    <div style='font-size:12px;color:rgba(255,255,255,0.75);'>{contact}</div>
  </div>
  <div style='height:4px;background:#2563eb;'></div>

  <!-- BODY -->
  <div style='padding:40px 60px;'>
    {f"<p style='font-size:13px;color:#6b7280;margin-bottom:20px;'>{date_str}</p>" if date_str else ""}
    <div style='margin-bottom:22px;'>
      <p style='font-size:14px;font-weight:700;color:#1b3a6b;'>{hiring_manager}</p>
      <p style='font-size:14px;color:#374151;'>{company}</p>
    </div>
    <p style='font-size:14px;margin-bottom:18px;'>Dear {hiring_manager},</p>
    {body}
    <p style='font-size:14px;color:#374151;margin-bottom:34px;'>
      I would welcome the opportunity to discuss how my experience aligns with the needs of {company}.
      Thank you for your time and consideration.
    </p>
    <p style='font-size:14px;'>Sincerely,</p>
    <p style='font-size:16px;font-weight:800;color:#1b3a6b;margin-top:12px;'>{name}</p>
    {f"<p style='font-size:13px;color:#2563eb;margin-top:3px;'>{job_title}</p>" if job_title else ""}
  </div>
</div>
</body></html>"""


# ══════════════════════════════════════════════════════════════════════════════
# TEMPLATE 2 — Emerald Minimal
# Left accent bar, emerald green, ultra-clean body.
# Best for: Tech, Product, Engineering, Startups.
# ══════════════════════════════════════════════════════════════════════════════
def render_cover_letter_emerald(data):
    name           = data.get("name", "Your Name")
    job_title      = data.get("job_title", "")
    company        = data.get("company", "Company Name")
    hiring_manager = data.get("hiring_manager", "Hiring Manager")
    role           = data.get("role", "the position")
    date_str       = data.get("date", "")
    paragraphs     = data.get("body_paragraphs", _default_paras())

    contact = _contact_row(data, link_color="#065f46", sep=" &nbsp;·&nbsp; ")
    body    = _paras_html(paragraphs, "margin-bottom:16px;font-size:14px;color:#1f2937;line-height:1.85;")

    return f"""<!DOCTYPE html>
<html lang='en'>
<head><meta charset='UTF-8'><title>Cover Letter — {name}</title>
<style>
* {{ box-sizing:border-box; margin:0; padding:0; }}
body {{ font-family:'Segoe UI',Arial,sans-serif; background:#fff; color:#111827; padding:48px 64px; line-height:1.6; }}
</style></head>
<body>
<div>
  <!-- NAME + LEFT BAR -->
  <div style='display:flex;align-items:stretch;margin-bottom:28px;'>
    <div style='width:5px;background:#065f46;border-radius:3px;margin-right:20px;flex-shrink:0;'></div>
    <div>
      <h1 style='font-size:28px;font-weight:800;color:#0f172a;margin-bottom:3px;'>{name}</h1>
      {f"<div style='font-size:14px;color:#065f46;font-weight:600;margin-bottom:6px;'>{job_title}</div>" if job_title else ""}
      <div style='font-size:12px;color:#6b7280;'>{contact}</div>
    </div>
  </div>
  <div style='height:1px;background:#d1fae5;margin-bottom:28px;'></div>

  {f"<p style='font-size:13px;color:#9ca3af;margin-bottom:18px;'>{date_str}</p>" if date_str else ""}
  <div style='margin-bottom:22px;'>
    <p style='font-size:14px;font-weight:700;color:#065f46;'>{hiring_manager}</p>
    <p style='font-size:14px;color:#6b7280;'>{company}</p>
  </div>
  <p style='font-size:14px;margin-bottom:18px;'>Dear {hiring_manager},</p>
  {body}
  <p style='font-size:14px;color:#374151;margin-bottom:32px;'>
    I'd love the chance to discuss how I can contribute to {company}. Thank you for considering my application.
  </p>
  <p style='font-size:14px;'>Best regards,</p>
  <div style='margin-top:12px;padding-top:10px;border-top:2px solid #6ee7b7;display:inline-block;'>
    <p style='font-size:16px;font-weight:800;color:#0f172a;'>{name}</p>
    {f"<p style='font-size:13px;color:#065f46;'>{job_title}</p>" if job_title else ""}
  </div>
</div>
</body></html>"""


# ══════════════════════════════════════════════════════════════════════════════
# TEMPLATE 3 — Executive Dark
# Midnight-navy gradient header, gold accent bar. C-suite / Director feel.
# Best for: C-Suite, VP, Director, Senior Leadership.
# ══════════════════════════════════════════════════════════════════════════════
def render_cover_letter_executive_dark(data):
    name           = data.get("name", "Your Name")
    job_title      = data.get("job_title", "")
    company        = data.get("company", "Company Name")
    hiring_manager = data.get("hiring_manager", "Search Committee")
    role           = data.get("role", "the position")
    date_str       = data.get("date", "")
    paragraphs     = data.get("body_paragraphs", _default_paras())

    contact = _contact_row(data, link_color="#d4af37", sep=" &nbsp;|&nbsp; ")
    body    = _paras_html(paragraphs, "margin-bottom:16px;font-size:14px;color:#1a1a1a;line-height:1.9;text-align:justify;")

    return f"""<!DOCTYPE html>
<html lang='en'>
<head><meta charset='UTF-8'><title>Cover Letter — {name}</title>
<style>
* {{ box-sizing:border-box; margin:0; padding:0; }}
body {{ font-family:'Georgia',serif; background:#fff; color:#1a1a1a; padding:0; line-height:1.6; }}
</style></head>
<body>
<div>
  <!-- EXECUTIVE DARK HEADER -->
  <div style='background:linear-gradient(135deg,#0d1b2a 0%,#1a2f4c 100%);padding:44px 64px 34px;'>
    <h1 style='font-size:30px;font-weight:700;color:#ffffff;letter-spacing:2px;margin-bottom:5px;font-family:"Georgia",serif;'>{name}</h1>
    {f"<div style='font-size:13px;color:#d4af37;font-weight:600;letter-spacing:2px;text-transform:uppercase;margin-bottom:12px;'>{job_title}</div>" if job_title else ""}
    <div style='font-size:12px;color:#adb5bd;'>{contact}</div>
  </div>
  <div style='height:4px;background:linear-gradient(90deg,#d4af37,#b8860b);'></div>

  <!-- BODY -->
  <div style='padding:44px 64px;'>
    {f"<p style='font-size:13px;color:#6b7280;margin-bottom:24px;'>{date_str}</p>" if date_str else ""}
    <div style='margin-bottom:24px;'>
      <p style='font-size:14px;font-weight:700;color:#0d1b2a;'>{hiring_manager}</p>
      <p style='font-size:14px;color:#374151;'>{company}</p>
    </div>
    <p style='font-size:14px;margin-bottom:20px;'>Dear {hiring_manager},</p>
    {body}
    <p style='font-size:14px;color:#374151;margin-bottom:36px;'>
      I welcome the opportunity to explore this further at your convenience.
      Please find my resume enclosed for your review.
    </p>
    <p style='font-size:14px;'>Respectfully yours,</p>
    <p style='font-size:18px;font-weight:700;color:#0d1b2a;margin-top:14px;font-family:"Georgia",serif;'>{name}</p>
    {f"<p style='font-size:13px;color:#d4af37;font-weight:600;margin-top:4px;'>{job_title}</p>" if job_title else ""}
  </div>
</div>
</body></html>"""


# ══════════════════════════════════════════════════════════════════════════════
# TEMPLATE 4 — Coral Creative
# Full-bleed vivid coral/red header, bold name, white text.
# Best for: Design, Marketing, Content, Media, Creative Agencies.
# ══════════════════════════════════════════════════════════════════════════════
def render_cover_letter_creative_coral(data):
    name           = data.get("name", "Your Name")
    job_title      = data.get("job_title", "")
    company        = data.get("company", "Company Name")
    hiring_manager = data.get("hiring_manager", "Hiring Team")
    role           = data.get("role", "the position")
    date_str       = data.get("date", "")
    accent         = data.get("accent_color", "#e11d48")
    paragraphs     = data.get("body_paragraphs", _default_paras())

    contact = _contact_row(data, link_color="white", sep=" &nbsp;•&nbsp; ")
    # Override contact link color to white since header is vivid
    contact = contact.replace("color:#e11d48", "color:white").replace("color:#065f46","color:white")
    body    = _paras_html(paragraphs, "margin-bottom:16px;font-size:14px;color:#1f2937;line-height:1.85;")

    return f"""<!DOCTYPE html>
<html lang='en'>
<head><meta charset='UTF-8'><title>Cover Letter — {name}</title>
<style>
* {{ box-sizing:border-box; margin:0; padding:0; }}
body {{ font-family:'Segoe UI',Arial,sans-serif; background:#fff; color:#1f2937; padding:0; line-height:1.6; }}
</style></head>
<body>
<div>
  <!-- VIVID CREATIVE HEADER -->
  <div style='background:{accent};padding:40px 56px 32px;'>
    <h1 style='font-size:34px;font-weight:900;color:#ffffff;letter-spacing:0.5px;margin-bottom:4px;'>{name}</h1>
    {f"<div style='font-size:15px;color:rgba(255,255,255,0.85);font-weight:600;margin-bottom:12px;'>{job_title}</div>" if job_title else ""}
    <div style='font-size:12px;color:rgba(255,255,255,0.8);'>{contact}</div>
  </div>

  <!-- BODY -->
  <div style='padding:40px 56px;'>
    {f"<p style='font-size:13px;color:#9ca3af;margin-bottom:18px;'>{date_str}</p>" if date_str else ""}
    <div style='margin-bottom:22px;'>
      <p style='font-size:14px;font-weight:700;color:#1f2937;'>{hiring_manager}</p>
      <p style='font-size:14px;color:#6b7280;'>{company}</p>
    </div>
    <p style='font-size:14px;margin-bottom:18px;'>Dear {hiring_manager},</p>
    {body}
    <p style='font-size:14px;color:#374151;margin-bottom:34px;'>
      I would be thrilled to discuss this further. Thank you for your time — I look forward to hearing from you.
    </p>
    <p style='font-size:14px;'>Warmly,</p>
    <p style='font-size:18px;font-weight:900;color:{accent};margin-top:12px;'>{name}</p>
    {f"<p style='font-size:13px;color:#6b7280;margin-top:3px;'>{job_title}</p>" if job_title else ""}
  </div>
</div>
</body></html>"""


# ══════════════════════════════════════════════════════════════════════════════
# TEMPLATE 5 — Minimal Monochrome
# Pure black/white typography-first design. No header bands, no color.
# Best for: ATS, Conservative industries, Academia, Law.
# ══════════════════════════════════════════════════════════════════════════════
def render_cover_letter_minimal_mono(data):
    name           = data.get("name", "Your Name")
    job_title      = data.get("job_title", "")
    company        = data.get("company", "Company Name")
    hiring_manager = data.get("hiring_manager", "Hiring Manager")
    role           = data.get("role", "the position")
    date_str       = data.get("date", "")
    paragraphs     = data.get("body_paragraphs", _default_paras())

    contact = _contact_row(data, link_color="#111827", sep=" | ")
    body    = _paras_html(paragraphs, "margin-bottom:16px;font-size:14px;color:#1a1a1a;line-height:1.9;text-align:justify;")

    return f"""<!DOCTYPE html>
<html lang='en'>
<head><meta charset='UTF-8'><title>Cover Letter — {name}</title>
<style>
* {{ box-sizing:border-box; margin:0; padding:0; }}
body {{ font-family:'Georgia',serif; background:#fff; color:#1a1a1a; padding:52px 70px; line-height:1.6; }}
</style></head>
<body>
<div>
  <!-- MINIMAL HEADER -->
  <div style='border-bottom:2px solid #111827;padding-bottom:16px;margin-bottom:28px;'>
    <h1 style='font-size:28px;font-weight:700;color:#111827;margin-bottom:4px;letter-spacing:0.5px;'>{name}</h1>
    {f"<div style='font-size:14px;color:#374151;margin-bottom:6px;'>{job_title}</div>" if job_title else ""}
    <div style='font-size:12px;color:#6b7280;'>{contact}</div>
  </div>

  {f"<p style='font-size:14px;color:#374151;margin-bottom:20px;'>{date_str}</p>" if date_str else ""}
  <div style='margin-bottom:22px;'>
    <p style='font-size:14px;font-weight:600;color:#1a1a1a;'>{hiring_manager}</p>
    <p style='font-size:14px;color:#374151;'>{company}</p>
  </div>
  <p style='font-size:14px;margin-bottom:20px;'>Dear {hiring_manager},</p>
  {body}
  <p style='font-size:14px;color:#374151;margin-bottom:32px;'>
    I would welcome the opportunity to discuss my application at your convenience.
    Thank you for your time and consideration.
  </p>
  <p style='font-size:14px;'>Yours sincerely,</p>
  <p style='font-size:16px;font-weight:700;color:#111827;margin-top:14px;'>{name}</p>
  {f"<p style='font-size:13px;color:#6b7280;margin-top:3px;'>{job_title}</p>" if job_title else ""}
</div>
</body></html>"""


# ══════════════════════════════════════════════════════════════════════════════
# TEMPLATE 6 — Slate Two-Tone
# Dark slate header with violet accent rule. Structured, refined.
# Best for: Product Management, Strategy, Operations, Mid-Senior roles.
# ══════════════════════════════════════════════════════════════════════════════
def render_cover_letter_slate(data):
    name           = data.get("name", "Your Name")
    job_title      = data.get("job_title", "")
    company        = data.get("company", "Company Name")
    hiring_manager = data.get("hiring_manager", "Hiring Manager")
    role           = data.get("role", "the position")
    date_str       = data.get("date", "")
    paragraphs     = data.get("body_paragraphs", _default_paras())

    contact = _contact_row(data, link_color="#cbd5e1", sep=" &nbsp;·&nbsp; ")
    body    = _paras_html(paragraphs, "margin-bottom:16px;font-size:14px;color:#1e293b;line-height:1.85;")

    return f"""<!DOCTYPE html>
<html lang='en'>
<head><meta charset='UTF-8'><title>Cover Letter — {name}</title>
<style>
* {{ box-sizing:border-box; margin:0; padding:0; }}
body {{ font-family:'Segoe UI',Arial,sans-serif; background:#fff; color:#1e293b; padding:0; line-height:1.6; }}
</style></head>
<body>
<div>
  <!-- SLATE HEADER -->
  <div style='background:#334155;padding:38px 60px 30px;display:flex;justify-content:space-between;align-items:flex-end;flex-wrap:wrap;gap:16px;'>
    <div>
      <h1 style='font-size:28px;font-weight:800;color:#ffffff;margin-bottom:4px;'>{name}</h1>
      {f"<div style='font-size:13px;color:#94a3b8;font-weight:500;'>{job_title}</div>" if job_title else ""}
    </div>
    <div style='text-align:right;font-size:12px;color:#94a3b8;line-height:1.9;'>{contact}</div>
  </div>
  <div style='height:3px;background:#7c3aed;'></div>

  <!-- BODY -->
  <div style='padding:40px 60px;'>
    {f"<p style='font-size:13px;color:#9ca3af;margin-bottom:20px;'>{date_str}</p>" if date_str else ""}
    <div style='margin-bottom:22px;'>
      <p style='font-size:14px;font-weight:700;color:#334155;'>{hiring_manager}</p>
      <p style='font-size:14px;color:#64748b;'>{company}</p>
    </div>
    <p style='font-size:14px;margin-bottom:18px;'>Dear {hiring_manager},</p>
    {body}
    <p style='font-size:14px;color:#475569;margin-bottom:34px;'>
      I look forward to the opportunity to further discuss how I can contribute to {company}.
      Thank you for your consideration.
    </p>
    <p style='font-size:14px;'>Best regards,</p>
    <p style='font-size:16px;font-weight:800;color:#334155;margin-top:12px;'>{name}</p>
    {f"<p style='font-size:13px;color:#7c3aed;margin-top:3px;'>{job_title}</p>" if job_title else ""}
  </div>
</div>
</body></html>"""


# ══════════════════════════════════════════════════════════════════════════════
# TEMPLATE 7 — Golden Prestige
# Warm cream background, gold double-rule, serif typography.
# Best for: Legal, Finance, Academia, Traditional Professional roles.
# ══════════════════════════════════════════════════════════════════════════════
def render_cover_letter_golden(data):
    name           = data.get("name", "Your Name")
    job_title      = data.get("job_title", "")
    company        = data.get("company", "Company Name")
    hiring_manager = data.get("hiring_manager", "Hiring Manager")
    role           = data.get("role", "the position")
    date_str       = data.get("date", "")
    paragraphs     = data.get("body_paragraphs", _default_paras())

    contact = _contact_row(data, link_color="#b45309", sep=" &nbsp;|&nbsp; ")
    body    = _paras_html(paragraphs, "margin-bottom:16px;font-size:14px;color:#1c1917;line-height:1.9;text-align:justify;")

    return f"""<!DOCTYPE html>
<html lang='en'>
<head><meta charset='UTF-8'><title>Cover Letter — {name}</title>
<style>
* {{ box-sizing:border-box; margin:0; padding:0; }}
body {{ font-family:'Georgia',serif; background:#fdf8f0; color:#1c1917; padding:52px 68px; line-height:1.6; }}
</style></head>
<body>
<div>
  <!-- GOLDEN HEADER -->
  <div style='text-align:center;margin-bottom:6px;'>
    <h1 style='font-size:30px;font-weight:700;color:#1c1917;letter-spacing:1px;margin-bottom:4px;'>{name}</h1>
    {f"<div style='font-size:14px;color:#b45309;font-style:italic;margin-bottom:8px;'>{job_title}</div>" if job_title else ""}
    <div style='font-size:12px;color:#78716c;'>{contact}</div>
  </div>
  <div style='height:1px;background:#fcd34d;margin:10px 0 3px;'></div>
  <div style='height:2.5px;background:#b45309;margin-bottom:28px;'></div>

  {f"<p style='font-size:14px;color:#78716c;margin-bottom:20px;'>{date_str}</p>" if date_str else ""}
  <div style='margin-bottom:22px;'>
    <p style='font-size:14px;font-weight:700;color:#1c1917;'>{hiring_manager}</p>
    <p style='font-size:14px;color:#78716c;'>{company}</p>
  </div>
  <p style='font-size:14px;margin-bottom:20px;'>Dear {hiring_manager},</p>
  {body}
  <p style='font-size:14px;color:#44403c;margin-bottom:32px;'>
    I would be delighted to discuss this opportunity further at your earliest convenience.
    Thank you for your time and consideration.
  </p>
  <div style='height:1px;background:#fcd34d;margin:0 0 3px;'></div>
  <div style='height:2px;background:#b45309;margin-bottom:14px;'></div>
  <p style='font-size:14px;'>Yours faithfully,</p>
  <p style='font-size:17px;font-weight:700;color:#1c1917;margin-top:12px;font-family:"Georgia",serif;'>{name}</p>
  {f"<p style='font-size:13px;color:#b45309;font-style:italic;margin-top:3px;'>{job_title}</p>" if job_title else ""}
</div>
</body></html>"""


# ══════════════════════════════════════════════════════════════════════════════
# TEMPLATE 8 — Entry-Level / Fresher
# Bright blue left-border box header. Energetic, approachable, clear.
# Best for: Fresh Graduates, Interns, Junior Roles, First Job.
# ══════════════════════════════════════════════════════════════════════════════
def render_cover_letter_entry_level(data):
    name           = data.get("name", "Your Name")
    job_title      = data.get("job_title", "")
    company        = data.get("company", "Company Name")
    hiring_manager = data.get("hiring_manager", "Hiring Manager")
    role           = data.get("role", "the position")
    date_str       = data.get("date", "")
    paragraphs     = data.get("body_paragraphs", [
        "I am a recent graduate in [Field] from [University] and I am excited to apply for the "
        "[Role] opportunity at [Company]. My academic training and hands-on project work have "
        "prepared me to contribute meaningfully from day one.",
        "During my studies, I developed strong skills in [Skill 1], [Skill 2], and [Skill 3]. "
        "My final-year project on [Topic] gave me practical exposure to [Technology/Process], "
        "and I achieved [Result/Grade/Recognition].",
        "I am eager to grow within a company like [Company] that values [Culture Value]. "
        "I am a fast learner, highly motivated, and committed to quality work. "
        "I look forward to contributing to your team.",
    ])

    contact = _contact_row(data, link_color="#1d4ed8", sep=" &nbsp;|&nbsp; ")
    body    = _paras_html(paragraphs, "margin-bottom:16px;font-size:14px;color:#374151;line-height:1.85;")

    return f"""<!DOCTYPE html>
<html lang='en'>
<head><meta charset='UTF-8'><title>Cover Letter — {name}</title>
<style>
* {{ box-sizing:border-box; margin:0; padding:0; }}
body {{ font-family:'Segoe UI',Arial,sans-serif; background:#fff; color:#1f2937; padding:48px 62px; line-height:1.6; }}
</style></head>
<body>
<div>
  <!-- ENTRY-LEVEL HEADER BOX -->
  <div style='background:#eff6ff;border-left:5px solid #1d4ed8;padding:22px 28px;margin-bottom:30px;border-radius:0 8px 8px 0;'>
    <h1 style='font-size:26px;font-weight:800;color:#1e3a8a;margin-bottom:3px;'>{name}</h1>
    {f"<div style='font-size:14px;color:#3b82f6;font-weight:600;margin-bottom:6px;'>{job_title}</div>" if job_title else ""}
    <div style='font-size:12px;color:#6b7280;'>{contact}</div>
  </div>

  {f"<p style='font-size:13px;color:#9ca3af;margin-bottom:18px;'>{date_str}</p>" if date_str else ""}
  <div style='margin-bottom:22px;'>
    <p style='font-size:14px;font-weight:600;color:#1f2937;'>{hiring_manager}</p>
    <p style='font-size:14px;color:#6b7280;'>{company}</p>
  </div>
  <p style='font-size:14px;margin-bottom:18px;'>Dear {hiring_manager},</p>
  {body}
  <p style='font-size:14px;color:#374151;margin-bottom:30px;'>
    I would be grateful for the opportunity to interview and learn more about this role.
    Thank you for your time and consideration.
  </p>
  <p style='font-size:14px;'>Sincerely,</p>
  <p style='font-size:16px;font-weight:700;color:#1e3a8a;margin-top:12px;'>{name}</p>
  {f"<p style='font-size:13px;color:#6b7280;margin-top:3px;'>{job_title}</p>" if job_title else ""}
</div>
</body></html>"""


# ══════════════════════════════════════════════════════════════════════════════
# TEMPLATE 9 — ATS Clean Technical
# Pure plain text, no images, no color blocks. Maximum keyword visibility.
# Best for: Software Engineers, Data Scientists, any ATS-heavy pipeline.
# ══════════════════════════════════════════════════════════════════════════════
def render_cover_letter_ats_clean(data):
    name           = data.get("name", "Your Name")
    job_title      = data.get("job_title", "")
    company        = data.get("company", "Company Name")
    hiring_manager = data.get("hiring_manager", "Hiring Manager")
    role           = data.get("role", "the position")
    date_str       = data.get("date", "")
    key_skills     = data.get("key_skills", "")
    paragraphs     = data.get("body_paragraphs", _default_paras())

    # ATS: plain text contact, no links
    parts = []
    for k in ["email","phone","location","linkedin","portfolio"]:
        v = data.get(k,"")
        if v: parts.append(v)
    contact_plain = " | ".join(parts)

    name_line = f"{name} | {job_title}" if job_title else name
    body    = _paras_html(paragraphs, "margin-bottom:14px;font-size:14px;color:#111827;line-height:1.85;")

    skills_block = ""
    if key_skills:
        skills_block = f"<p style='margin-bottom:14px;font-size:14px;color:#111827;line-height:1.85;'><strong>Core Skills:</strong> {key_skills}</p>"

    return f"""<!DOCTYPE html>
<html lang='en'>
<head><meta charset='UTF-8'><title>Cover Letter — {name}</title>
<style>
* {{ box-sizing:border-box; margin:0; padding:0; }}
body {{ font-family:Arial,Helvetica,sans-serif; background:#fff; color:#111827; padding:50px 66px; line-height:1.6; font-size:14px; }}
hr {{ border:none; border-top:1px solid #d1d5db; margin:16px 0; }}
</style></head>
<body>
<div>
  <p style='font-size:22px;font-weight:700;'>{name_line}</p>
  <p style='font-size:13px;color:#374151;margin-top:4px;margin-bottom:4px;'>{contact_plain}</p>
  <hr>
  {f"<p style='margin-bottom:16px;color:#374151;'>{date_str}</p>" if date_str else ""}
  <div style='margin-bottom:20px;'>
    <p style='font-weight:600;'>{hiring_manager}</p>
    <p style='color:#374151;'>{company}</p>
  </div>
  <p style='font-weight:700;margin-bottom:18px;'>Re: Application for {role} — {name}</p>
  <p style='margin-bottom:18px;'>Dear {hiring_manager},</p>
  {body}
  {skills_block}
  <p style='margin-bottom:28px;color:#374151;'>
    I have attached my resume for your review and am available for an interview at your earliest convenience.
  </p>
  <p>Sincerely,</p>
  <p style='font-weight:700;font-size:15px;margin-top:12px;'>{name}</p>
  {f"<p style='color:#374151;margin-top:3px;'>{job_title}</p>" if job_title else ""}
</div>
</body></html>"""


# ══════════════════════════════════════════════════════════════════════════════
# TEMPLATE 10 — Sidebar Accent
# Left accent sidebar strip (thin colored column), main content right.
# Inspired by Novoresume "Bucharest" cover letter layout.
# Best for: Tech Leads, Product Designers, Creative Professionals.
# ══════════════════════════════════════════════════════════════════════════════
def render_cover_letter_sidebar_accent(data):
    name           = data.get("name", "Your Name")
    job_title      = data.get("job_title", "")
    company        = data.get("company", "Company Name")
    hiring_manager = data.get("hiring_manager", "Hiring Manager")
    role           = data.get("role", "the position")
    date_str       = data.get("date", "")
    accent         = data.get("accent_color", "#0891b2")
    paragraphs     = data.get("body_paragraphs", _default_paras())

    contact = _contact_row(data, link_color=accent, sep=" &nbsp;·&nbsp; ")
    body    = _paras_html(paragraphs, "margin-bottom:16px;font-size:14px;color:#1f2937;line-height:1.85;")

    return f"""<!DOCTYPE html>
<html lang='en'>
<head><meta charset='UTF-8'><title>Cover Letter — {name}</title>
<style>
* {{ box-sizing:border-box; margin:0; padding:0; }}
body {{ font-family:'Segoe UI',Arial,sans-serif; background:#fff; color:#1f2937; padding:0; line-height:1.6; }}
</style></head>
<body>
<div style='display:flex;min-height:100%;'>
  <!-- LEFT ACCENT SIDEBAR -->
  <div style='width:8px;background:{accent};flex-shrink:0;'></div>

  <!-- MAIN CONTENT -->
  <div style='flex:1;padding:48px 56px;'>
    <!-- HEADER -->
    <div style='border-bottom:1px solid #e5e7eb;padding-bottom:18px;margin-bottom:26px;display:flex;justify-content:space-between;align-items:flex-end;flex-wrap:wrap;gap:12px;'>
      <div>
        <h1 style='font-size:28px;font-weight:800;color:#0f172a;margin-bottom:3px;'>{name}</h1>
        {f"<div style='font-size:14px;color:{accent};font-weight:600;'>{job_title}</div>" if job_title else ""}
      </div>
      <div style='text-align:right;font-size:12px;color:#6b7280;line-height:1.9;'>{contact}</div>
    </div>

    {f"<p style='font-size:13px;color:#9ca3af;margin-bottom:18px;'>{date_str}</p>" if date_str else ""}
    <div style='margin-bottom:22px;'>
      <p style='font-size:14px;font-weight:700;color:#0f172a;'>{hiring_manager}</p>
      <p style='font-size:14px;color:#6b7280;'>{company}</p>
    </div>
    <p style='font-size:14px;margin-bottom:18px;'>Dear {hiring_manager},</p>
    {body}
    <p style='font-size:14px;color:#374151;margin-bottom:32px;'>
      I'd love the opportunity to discuss how I can contribute to {company}.
      Thank you for considering my application.
    </p>
    <p style='font-size:14px;'>Best regards,</p>
    <p style='font-size:17px;font-weight:800;color:#0f172a;margin-top:12px;'>{name}</p>
    {f"<p style='font-size:13px;color:{accent};margin-top:3px;'>{job_title}</p>" if job_title else ""}
  </div>
</div>
</body></html>"""


# ══════════════════════════════════════════════════════════════════════════════
# REGISTRY
# ══════════════════════════════════════════════════════════════════════════════

COVER_LETTER_TEMPLATES = {
    "Cobalt Professional":      render_cover_letter_cobalt,
    "Emerald Minimal":          render_cover_letter_emerald,
    "Executive Dark":           render_cover_letter_executive_dark,
    "Coral Creative":           render_cover_letter_creative_coral,
    "Minimal Monochrome":       render_cover_letter_minimal_mono,
    "Slate Two-Tone":           render_cover_letter_slate,
    "Golden Prestige":          render_cover_letter_golden,
    "Entry-Level / Fresher":    render_cover_letter_entry_level,
    "ATS Clean":                render_cover_letter_ats_clean,
    "Sidebar Accent":           render_cover_letter_sidebar_accent,
}

# Industry-fit hints shown in the UI next to each template
COVER_LETTER_META = {
    "Cobalt Professional":   ("🔵", "Finance, Banking, Consulting"),
    "Emerald Minimal":       ("🟢", "Tech, Product, Engineering"),
    "Executive Dark":        ("⚫", "C-Suite, VP, Directors"),
    "Coral Creative":        ("🔴", "Design, Marketing, Media"),
    "Minimal Monochrome":    ("⬜", "ATS, Conservative, Academia"),
    "Slate Two-Tone":        ("🟣", "Product Mgmt, Strategy, Ops"),
    "Golden Prestige":       ("🟡", "Legal, Finance, Traditional"),
    "Entry-Level / Fresher": ("🔷", "Graduates, Interns, Junior"),
    "ATS Clean":             ("📄", "Software Eng, Data, Technical"),
    "Sidebar Accent":        ("🔹", "Tech Leads, Designers, Creative"),
}


def render_cover_letter(template_name, data):
    """Dispatch to named cover letter template. Returns HTML string."""
    fn = COVER_LETTER_TEMPLATES.get(template_name, render_cover_letter_cobalt)
    return fn(data)


# Legacy aliases for any old imports
render_cover_letter_professional = render_cover_letter_cobalt
render_cover_letter_modern       = render_cover_letter_emerald
render_cover_letter_creative     = render_cover_letter_creative_coral
render_cover_letter_executive    = render_cover_letter_executive_dark
render_cover_letter_ats          = render_cover_letter_ats_clean


# ══════════════════════════════════════════════════════════════════════════════
# STREAMLIT GENERATOR — generate_cover_letter_from_resume_builder()
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

    # ── Template selector CSS ────────────────────────────────────────────────
    st.markdown("""
    <style>
    .cl-meta-hint { font-size:11px; color:#9ca3af; margin-top:2px; }
    </style>
    """, unsafe_allow_html=True)

    with st.form(key="cover_letter_form"):
        st.markdown(
            "<div style='font-size:14px;font-weight:600;color:#93c5fd;margin-bottom:10px;'>"
            "🎨 Choose Cover Letter Template</div>",
            unsafe_allow_html=True,
        )

        # Build template option labels with industry hints
        _tpl_options = list(COVER_LETTER_TEMPLATES.keys())
        _tpl_display = {
            k: f"{COVER_LETTER_META[k][0]}  {k}  —  {COVER_LETTER_META[k][1]}"
            for k in _tpl_options
        }

        cover_letter_template = st.selectbox(
            "Template",
            options=_tpl_options,
            format_func=lambda k: _tpl_display[k],
            index=0,
            key="cover_letter_template_select",
            label_visibility="collapsed",
        )

        # Show industry hint for selected template
        _hint_icon, _hint_text = COVER_LETTER_META.get(cover_letter_template, ("",""))
        st.markdown(
            f"<div class='cl-meta-hint'>Best for: <strong>{_hint_text}</strong></div>",
            unsafe_allow_html=True,
        )

        # Accent color — only relevant for Coral Creative and Sidebar Accent templates
        _show_accent = cover_letter_template in ("Coral Creative", "Sidebar Accent")
        accent_color = st.color_picker(
            "🎨 Accent Color (for Coral Creative / Sidebar Accent templates)",
            value="#e11d48" if cover_letter_template == "Coral Creative" else "#0891b2",
            key="cl_accent_color",
            disabled=not _show_accent,
        )
        if not _show_accent:
            accent_color = "#003366"  # neutral fallback

        st.markdown("<div style='height:8px;'></div>", unsafe_allow_html=True)

        company  = st.text_input("🏢 Target Company", placeholder="e.g., Google, Infosys, McKinsey")
        linkedin = st.text_input("🔗 LinkedIn URL", placeholder="e.g., https://linkedin.com/in/yourname",
                                  value=st.session_state.get("linkedin",""))
        email    = st.text_input("📧 Email", placeholder="e.g., you@example.com",
                                  value=st.session_state.get("email",""))
        mobile   = st.text_input("📞 Mobile", placeholder="e.g., +91 9876543210",
                                  value=st.session_state.get("phone",""))

        submitted_cl = st.form_submit_button("✉️ Generate Cover Letter", use_container_width=True, type="primary")

    if submitted_cl:
        if not all([name, job_title, summary, skills, company, email, mobile]):
            st.warning("⚠️ Please fill in all fields (name, job title, summary, skills, company, email, mobile) before generating.")
            return

        prompt = f"""You are a professional cover letter writer.

Write ONLY the 3 body paragraphs of a cover letter for the candidate below.
Do NOT include: date, recipient address, salutation ("Dear ..."), closing ("Sincerely"), or the candidate's name at the end.
The template adds all of those automatically — provide ONLY the 3 body paragraphs.

Output exactly 3 paragraphs separated by a blank line (double newline).
Each paragraph: 2–4 sentences. Plain text only, no HTML tags.

Candidate:
- Name: {name}
- Job Title: {job_title}
- Target Company: {company}
- Location: {location}
- Summary: {summary}
- Skills: {skills}

Rules:
- Do NOT start with "Dear" or any greeting.
- Do NOT end with "Sincerely", the name, or a sign-off.
- No HTML tags.
- Separate paragraphs with a blank line.
- Return 3 body paragraphs ONLY.
"""
        with st.spinner("✉️ Crafting your cover letter…"):
            try:
                from llm_manager import call_llm
                cover_letter_raw = call_llm(prompt, session=st.session_state).strip()
            except Exception as _e:
                st.error(f"LLM error: {_e}")
                return

        # Strip boilerplate the LLM may add despite instructions
        def _strip_boilerplate(text):
            lines = text.split('\n')
            cleaned = []
            skip_re = [
                _re.compile(p, _re.IGNORECASE) for p in [
                    r'^\s*(january|february|march|april|may|june|july|august|september|october|november|december)\s+\d',
                    r'^\s*\d{1,2}[\/\-]\d{1,2}[\/\-]\d{2,4}',
                    r'^\s*dear\b',
                    r'^\s*(sincerely|regards|best regards|yours truly|warm regards|respectfully)\b',
                    r'^\s*hiring manager[,.]?\s*$',
                ]
            ]
            closing_idx = None
            for i, ln in enumerate(lines):
                if _re.match(r'^\s*(sincerely|regards|best|yours|warm|respectfully)', ln, _re.I):
                    closing_idx = i
            for i, ln in enumerate(lines):
                if any(r.match(ln) for r in skip_re):
                    continue
                if closing_idx is not None and i > closing_idx and ln.strip().lower() in (name.lower(), job_title.lower(), ''):
                    continue
                cleaned.append(ln)
            return '\n'.join(cleaned).strip()

        cover_letter_body = _strip_boilerplate(cover_letter_raw)
        st.session_state["cover_letter"] = cover_letter_body

        # Split into paragraphs robustly
        normalised   = _re.sub(r'\n{3,}', '\n\n', cover_letter_body)
        raw_paras    = normalised.split('\n\n')
        if len(raw_paras) <= 1:
            raw_paras = normalised.split('\n')
        body_paragraphs = [p.strip() for p in raw_paras if p.strip()]

        cl_data = {
            "name":            name,
            "job_title":       job_title,
            "email":           email,
            "phone":           mobile,
            "location":        location,
            "linkedin":        linkedin,
            "portfolio":       st.session_state.get("portfolio", ""),
            "company":         company,
            "hiring_manager":  "Hiring Manager",
            "role":            job_title,
            "date":            today_date,
            "body_paragraphs": body_paragraphs,
            "key_skills":      skills,
            "accent_color":    accent_color,
        }

        cover_letter_html = render_cover_letter(cover_letter_template, cl_data)
        st.session_state["cover_letter_html"] = cover_letter_html

        # Generate PDF
        try:
            from taab2 import html_to_pdf_bytes as _h2pdf
        except ImportError:
            try:
                from main import html_to_pdf_bytes as _h2pdf
            except ImportError:
                _h2pdf = None

        if _h2pdf is not None:
            try:
                _pdf_buf = _h2pdf(cover_letter_html)
                st.session_state["cover_letter_pdf"] = _pdf_buf.read()
            except Exception:
                st.session_state["cover_letter_pdf"] = None
        else:
            st.session_state["cover_letter_pdf"] = None

        # Preview
        import streamlit.components.v1 as _cl_components
        st.success("✅ Cover letter generated successfully!")
        st.markdown(
            "<p style='color:#555;font-size:13px;margin-top:8px;'>📄 Cover Letter Preview (scroll to explore):</p>",
            unsafe_allow_html=True,
        )
        _cl_components.html(cover_letter_html, height=700, scrolling=True)

        # Download buttons
        _safe_name = name.replace(" ", "_")
        _dl1, _dl2, _dl3 = st.columns(3)

        with _dl1:
            st.download_button(
                label="📥 Download (HTML)",
                data=cover_letter_html.encode("utf-8"),
                file_name=f"{_safe_name}_Cover_Letter.html",
                mime="text/html",
                key="download_cl_html_inline",
            )
        with _dl2:
            if st.session_state.get("cover_letter_pdf"):
                st.download_button(
                    label="📥 Download (PDF)",
                    data=st.session_state["cover_letter_pdf"],
                    file_name=f"{_safe_name}_Cover_Letter.pdf",
                    mime="application/pdf",
                    key="download_cl_pdf_inline",
                )
        with _dl3:
            try:
                from docx import Document as _DocxDoc
                _docx_bio = __import__('io').BytesIO()
                _docx = _DocxDoc()
                _docx.add_heading("Cover Letter", 0)
                for _line in cover_letter_body.split("\n"):
                    _docx.add_paragraph(_line if _line.strip() else "")
                _docx.save(_docx_bio)
                _docx_bio.seek(0)
                st.download_button(
                    label="📥 Download (.docx)",
                    data=_docx_bio,
                    file_name=f"{_safe_name}_Cover_Letter.docx",
                    mime="application/vnd.openxmlformats-officedocument.wordprocessingml.document",
                    key="download_cl_docx_inline",
                )
            except ImportError:
                st.info("Install python-docx for DOCX download.")
