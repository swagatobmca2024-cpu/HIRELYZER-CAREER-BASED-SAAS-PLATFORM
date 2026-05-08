# cover_letter.py
# ══════════════════════════════════════════════════════════════════════════════
# COVER LETTER TEMPLATES — 6 industry-standard HTML cover letter templates
# + generate_cover_letter_from_resume_builder() Streamlit UI function
#
# Imported by main.py:
#   from cover_letter import (
#       render_cover_letter_professional, render_cover_letter_modern,
#       render_cover_letter_creative, render_cover_letter_executive,
#       render_cover_letter_entry_level, render_cover_letter_ats,
#       COVER_LETTER_TEMPLATES, render_cover_letter,
#       generate_cover_letter_from_resume_builder,
#   )
# ══════════════════════════════════════════════════════════════════════════════

def render_cover_letter_professional(data):
    """
    Cover Letter Template 1 — Professional / Corporate
    Clean, formal, navy accents. Ideal for finance, law, consulting, banking.
    data keys: name, job_title, email, phone, location, linkedin,
               company, hiring_manager, role, date, body_paragraphs (list of str)
    """
    name          = data.get("name", "Your Name")
    job_title     = data.get("job_title", "")
    email         = data.get("email", "")
    phone         = data.get("phone", "")
    location      = data.get("location", "")
    linkedin      = data.get("linkedin", "")
    company       = data.get("company", "Hiring Company")
    hiring_manager= data.get("hiring_manager", "Hiring Manager")
    role          = data.get("role", "the position")
    date_str      = data.get("date", "")
    paragraphs    = data.get("body_paragraphs", [
        "I am writing to express my strong interest in the [Role] position at [Company]. With my background in [Field], I am confident that I can make a meaningful contribution to your team.",
        "Throughout my career, I have developed expertise in [Key Skills]. In my previous role at [Previous Company], I successfully [Key Achievement], which demonstrates my ability to deliver results in a fast-paced environment.",
        "I am particularly drawn to [Company] because of [Specific Reason]. I am excited about the opportunity to bring my skills in [Relevant Skills] to your organization and help achieve [Company Goal].",
    ])

    contact_parts = []
    if email:    contact_parts.append(f"<a href='mailto:{email}' style='color:#1e3a5f;text-decoration:none;'>{email}</a>")
    if phone:    contact_parts.append(f"<span>{phone}</span>")
    if location: contact_parts.append(f"<span>{location}</span>")
    if linkedin:
        href = linkedin if linkedin.startswith('http') else f"https://{linkedin}"
        contact_parts.append(f"<a href='{href}' target='_blank' style='color:#1e3a5f;text-decoration:none;'>{linkedin}</a>")
    contact_line = " &nbsp;|&nbsp; ".join(contact_parts)

    paras_html = "".join(
        f"<p style='margin-bottom:16px;font-size:14px;color:#1a1a1a;line-height:1.8;text-align:justify;'>{p}</p>"
        for p in paragraphs
    )

    return f"""<!DOCTYPE html>
<html lang='en'>
<head><meta charset='UTF-8'><meta name='viewport' content='width=device-width,initial-scale=1'><title>Cover Letter — {name}</title>
<style>
  * {{ box-sizing:border-box; margin:0; padding:0; }}
  body {{ font-family:'Georgia',serif; background:#fff; color:#1a1a1a; padding:50px 70px; line-height:1.6; }}
</style>
</head>
<body>
<div style='max-width:794px;margin:0 auto;'>
  <!-- HEADER -->
  <div style='border-bottom:3px solid #1e3a5f;padding-bottom:18px;margin-bottom:28px;'>
    <h1 style='font-size:30px;font-weight:700;color:#1e3a5f;letter-spacing:1px;margin-bottom:4px;'>{name}</h1>
    {f"<div style='font-size:15px;color:#374151;font-weight:600;margin-bottom:8px;'>{job_title}</div>" if job_title else ''}
    <div style='font-size:13px;color:#555;'>{contact_line}</div>
  </div>

  <!-- DATE -->
  {f"<p style='font-size:14px;color:#374151;margin-bottom:20px;'>{date_str}</p>" if date_str else ''}

  <!-- RECIPIENT -->
  <div style='margin-bottom:24px;'>
    <p style='font-size:14px;font-weight:600;color:#1a1a1a;'>{hiring_manager}</p>
    <p style='font-size:14px;color:#374151;'>{company}</p>
  </div>

  <!-- GREETING -->
  <p style='font-size:14px;color:#1a1a1a;margin-bottom:20px;'>Dear {hiring_manager},</p>

  <!-- BODY -->
  {paras_html}

  <!-- CLOSING -->
  <p style='font-size:14px;color:#1a1a1a;margin-bottom:6px;'>I would welcome the opportunity to discuss how my experience aligns with the needs of {company}. Thank you for your time and consideration.</p>
  <p style='font-size:14px;color:#1a1a1a;margin-top:28px;'>Sincerely,</p>
  <p style='font-size:15px;font-weight:700;color:#1e3a5f;margin-top:8px;'>{name}</p>
  {f"<p style='font-size:13px;color:#555;margin-top:4px;'>{job_title}</p>" if job_title else ''}
</div>
</body></html>"""


def render_cover_letter_modern(data):
    """
    Cover Letter Template 2 — Modern Minimal
    Clean white layout with teal accent line. Ideal for startups, tech, design roles.
    """
    name          = data.get("name", "Your Name")
    job_title     = data.get("job_title", "")
    email         = data.get("email", "")
    phone         = data.get("phone", "")
    location      = data.get("location", "")
    linkedin      = data.get("linkedin", "")
    company       = data.get("company", "Company Name")
    hiring_manager= data.get("hiring_manager", "Hiring Manager")
    role          = data.get("role", "the position")
    date_str      = data.get("date", "")
    paragraphs    = data.get("body_paragraphs", [
        "I'm excited to apply for the [Role] role at [Company]. My background in [Field] and passion for [Domain] make me a strong match for this position.",
        "In my most recent role, I [Key Achievement], which led to [Quantified Result]. I thrive in environments that value [Culture Trait] and I'm ready to bring that energy to [Company].",
        "What excites me most about [Company] is [Specific Reason]. I'd love to explore how my skills in [Relevant Skills] can help your team reach its next milestone.",
    ])

    contact_items = []
    if email:    contact_items.append(f"<a href='mailto:{email}' style='color:#0d9488;text-decoration:none;'>{email}</a>")
    if phone:    contact_items.append(phone)
    if location: contact_items.append(location)
    if linkedin:
        href = linkedin if linkedin.startswith('http') else f"https://{linkedin}"
        contact_items.append(f"<a href='{href}' target='_blank' style='color:#0d9488;text-decoration:none;'>{linkedin}</a>")
    contact_line = " &nbsp;&middot;&nbsp; ".join(contact_items)

    paras_html = "".join(
        f"<p style='margin-bottom:14px;font-size:14px;color:#374151;line-height:1.8;'>{p}</p>"
        for p in paragraphs
    )

    return f"""<!DOCTYPE html>
<html lang='en'>
<head><meta charset='UTF-8'><meta name='viewport' content='width=device-width,initial-scale=1'><title>Cover Letter — {name}</title>
<style>
  * {{ box-sizing:border-box; margin:0; padding:0; }}
  body {{ font-family:'Segoe UI',Arial,sans-serif; background:#fff; color:#1f2937; padding:48px 64px; line-height:1.6; }}
</style>
</head>
<body>
<div style='max-width:794px;margin:0 auto;'>
  <!-- HEADER BAND -->
  <div style='display:flex;justify-content:space-between;align-items:flex-end;border-bottom:4px solid #0d9488;padding-bottom:16px;margin-bottom:32px;'>
    <div>
      <h1 style='font-size:28px;font-weight:800;color:#0f172a;letter-spacing:0.5px;margin-bottom:2px;'>{name}</h1>
      {f"<div style='font-size:14px;color:#0d9488;font-weight:600;'>{job_title}</div>" if job_title else ''}
    </div>
    <div style='text-align:right;font-size:12px;color:#6b7280;line-height:1.9;'>{contact_line}</div>
  </div>

  <!-- DATE + RECIPIENT -->
  {f"<p style='font-size:13px;color:#6b7280;margin-bottom:16px;'>{date_str}</p>" if date_str else ''}
  <div style='margin-bottom:20px;'>
    <p style='font-size:14px;font-weight:600;color:#1f2937;'>{hiring_manager}</p>
    <p style='font-size:14px;color:#6b7280;'>{company}</p>
  </div>

  <!-- GREETING -->
  <p style='font-size:14px;margin-bottom:18px;'>Dear {hiring_manager},</p>

  <!-- BODY -->
  {paras_html}

  <!-- CLOSING -->
  <p style='font-size:14px;color:#374151;margin-bottom:30px;'>I'd love the chance to chat about how I can contribute to {company}. Thank you for considering my application.</p>
  <p style='font-size:14px;'>Best regards,</p>
  <div style='margin-top:10px;padding-top:10px;border-top:2px solid #0d9488;display:inline-block;'>
    <p style='font-size:16px;font-weight:700;color:#0f172a;'>{name}</p>
    {f"<p style='font-size:13px;color:#0d9488;'>{job_title}</p>" if job_title else ''}
  </div>
</body></html>"""


def render_cover_letter_creative(data):
    """
    Cover Letter Template 3 — Creative
    Bold header with accent colour bar. Ideal for design, marketing, media, content roles.
    """
    name          = data.get("name", "Your Name")
    job_title     = data.get("job_title", "")
    email         = data.get("email", "")
    phone         = data.get("phone", "")
    location      = data.get("location", "")
    linkedin      = data.get("linkedin", "")
    portfolio     = data.get("portfolio", "")
    company       = data.get("company", "Company Name")
    hiring_manager= data.get("hiring_manager", "Hiring Team")
    role          = data.get("role", "the position")
    date_str      = data.get("date", "")
    accent        = data.get("accent_color", "#7c3aed")
    paragraphs    = data.get("body_paragraphs", [
        "Great design solves real problems — and that's exactly the philosophy I bring to every project. I'm applying for [Role] at [Company] because I believe your team's work embodies this principle.",
        "My background in [Field] has equipped me with [Skills]. At [Previous Company], I led [Project] which resulted in [Outcome]. I'm proud of the process as much as the product.",
        "I'm inspired by [Company]'s approach to [Specific Work/Campaign/Product]. I would love to contribute my skills in [Creative Skills] to your upcoming projects.",
    ])

    contact_items = []
    if email:     contact_items.append(f"<a href='mailto:{email}' style='color:white;text-decoration:none;'>{email}</a>")
    if phone:     contact_items.append(f"<span style='color:rgba(255,255,255,0.85);'>{phone}</span>")
    if location:  contact_items.append(f"<span style='color:rgba(255,255,255,0.85);'>{location}</span>")
    if linkedin:
        href = linkedin if linkedin.startswith('http') else f"https://{linkedin}"
        contact_items.append(f"<a href='{href}' target='_blank' style='color:white;text-decoration:none;'>{linkedin}</a>")
    if portfolio:
        href = portfolio if portfolio.startswith('http') else f"https://{portfolio}"
        contact_items.append(f"<a href='{href}' target='_blank' style='color:white;text-decoration:none;'>{portfolio}</a>")
    contact_line = " &nbsp;&bull;&nbsp; ".join(contact_items)

    paras_html = "".join(
        f"<p style='margin-bottom:16px;font-size:14px;color:#1f2937;line-height:1.85;'>{p}</p>"
        for p in paragraphs
    )

    return f"""<!DOCTYPE html>
<html lang='en'>
<head><meta charset='UTF-8'><meta name='viewport' content='width=device-width,initial-scale=1'><title>Cover Letter — {name}</title>
<style>
  * {{ box-sizing:border-box; margin:0; padding:0; }}
  body {{ font-family:'Segoe UI',Arial,sans-serif; background:#fff; color:#1f2937; padding:0; line-height:1.6; }}
</style>
</head>
<body>
<div style='max-width:794px;margin:0 auto;'>
  <!-- CREATIVE HEADER BAND -->
  <div style='background:{accent};padding:36px 56px 28px;'>
    <h1 style='font-size:32px;font-weight:800;color:#ffffff;letter-spacing:1px;margin-bottom:4px;'>{name}</h1>
    {f"<div style='font-size:15px;color:rgba(255,255,255,0.85);font-weight:600;margin-bottom:12px;'>{job_title}</div>" if job_title else ''}
    <div style='font-size:12px;'>{contact_line}</div>
  </div>

  <!-- BODY AREA -->
  <div style='padding:40px 56px;'>
    {f"<p style='font-size:13px;color:#9ca3af;margin-bottom:18px;'>{date_str}</p>" if date_str else ''}

    <div style='margin-bottom:22px;'>
      <p style='font-size:14px;font-weight:700;color:#1f2937;'>{hiring_manager}</p>
      <p style='font-size:14px;color:#6b7280;'>{company}</p>
    </div>

    <p style='font-size:14px;margin-bottom:18px;'>Dear {hiring_manager},</p>

    {paras_html}

    <p style='font-size:14px;color:#374151;margin-bottom:32px;'>I would be thrilled to discuss this further. Thank you for your time — I look forward to hearing from you.</p>

    <p style='font-size:14px;'>Warmly,</p>
    <p style='font-size:17px;font-weight:800;color:{accent};margin-top:10px;'>{name}</p>
    {f"<p style='font-size:13px;color:#6b7280;'>{job_title}</p>" if job_title else ''}
  </div>
</body></html>"""


def render_cover_letter_executive(data):
    """
    Cover Letter Template 4 — Executive
    Sophisticated dark-header layout. Ideal for C-suite, VP, Director-level applications.
    """
    name          = data.get("name", "Your Name")
    job_title     = data.get("job_title", "")
    email         = data.get("email", "")
    phone         = data.get("phone", "")
    location      = data.get("location", "")
    linkedin      = data.get("linkedin", "")
    company       = data.get("company", "Company Name")
    hiring_manager= data.get("hiring_manager", "Board / Search Committee")
    role          = data.get("role", "the position")
    date_str      = data.get("date", "")
    paragraphs    = data.get("body_paragraphs", [
        "With over [X] years leading [Function/Division] in [Industry], I bring a track record of driving strategic growth and operational excellence. I am writing to express my interest in the [Role] position at [Company].",
        "At [Previous Organization], I spearheaded [Initiative], resulting in [Revenue/Efficiency/Growth Outcome]. This experience has sharpened my ability to align cross-functional teams around ambitious goals while maintaining fiscal discipline.",
        "I am drawn to [Company] because of its [Specific Initiative, Vision, or Market Position]. I am confident that my leadership philosophy — centred on [Value 1], [Value 2], and [Value 3] — aligns with your organizational culture.",
    ])

    contact_items = []
    if email:    contact_items.append(f"<a href='mailto:{email}' style='color:#d4af37;text-decoration:none;'>{email}</a>")
    if phone:    contact_items.append(f"<span>{phone}</span>")
    if location: contact_items.append(f"<span>{location}</span>")
    if linkedin:
        href = linkedin if linkedin.startswith('http') else f"https://{linkedin}"
        contact_items.append(f"<a href='{href}' target='_blank' style='color:#d4af37;text-decoration:none;'>{linkedin}</a>")
    contact_line = " &nbsp;|&nbsp; ".join(contact_items)

    paras_html = "".join(
        f"<p style='margin-bottom:16px;font-size:14px;color:#1a1a1a;line-height:1.85;text-align:justify;'>{p}</p>"
        for p in paragraphs
    )

    return f"""<!DOCTYPE html>
<html lang='en'>
<head><meta charset='UTF-8'><meta name='viewport' content='width=device-width,initial-scale=1'><title>Cover Letter — {name}</title>
<style>
  * {{ box-sizing:border-box; margin:0; padding:0; }}
  body {{ font-family:'Georgia',serif; background:#fff; color:#1a1a1a; padding:0; line-height:1.6; }}
</style>
</head>
<body>
<div style='max-width:794px;margin:0 auto;'>
  <!-- EXECUTIVE DARK HEADER -->
  <div style='background:linear-gradient(135deg,#0d1b2a,#1a2f4c);padding:40px 64px 32px;'>
    <h1 style='font-size:30px;font-weight:700;color:#ffffff;letter-spacing:2px;margin-bottom:4px;font-family:"Georgia",serif;'>{name}</h1>
    {f"<div style='font-size:14px;color:#d4af37;font-weight:600;letter-spacing:1.5px;text-transform:uppercase;margin-bottom:12px;'>{job_title}</div>" if job_title else ''}
    <div style='font-size:12px;color:#adb5bd;'>{contact_line}</div>
  </div>
  <div style='height:4px;background:linear-gradient(90deg,#d4af37,#b8860b);'></div>

  <!-- BODY -->
  <div style='padding:42px 64px;'>
    {f"<p style='font-size:13px;color:#6b7280;margin-bottom:22px;'>{date_str}</p>" if date_str else ''}

    <div style='margin-bottom:24px;'>
      <p style='font-size:14px;font-weight:700;color:#0d1b2a;'>{hiring_manager}</p>
      <p style='font-size:14px;color:#374151;'>{company}</p>
    </div>

    <p style='font-size:14px;margin-bottom:20px;'>Dear {hiring_manager},</p>

    {paras_html}

    <p style='font-size:14px;color:#374151;margin-bottom:34px;'>I welcome the opportunity to explore this further at your convenience. Please find my resume enclosed for your review.</p>

    <p style='font-size:14px;'>Respectfully yours,</p>
    <p style='font-size:18px;font-weight:700;color:#0d1b2a;margin-top:12px;font-family:"Georgia",serif;'>{name}</p>
    {f"<p style='font-size:13px;color:#d4af37;font-weight:600;margin-top:4px;'>{job_title}</p>" if job_title else ''}
  </div>
</body></html>"""


def render_cover_letter_entry_level(data):
    """
    Cover Letter Template 5 — Entry-Level / Fresher
    Bright, approachable layout with blue accents. Ideal for recent graduates, interns.
    """
    name          = data.get("name", "Your Name")
    job_title     = data.get("job_title", "")
    email         = data.get("email", "")
    phone         = data.get("phone", "")
    location      = data.get("location", "")
    linkedin      = data.get("linkedin", "")
    company       = data.get("company", "Company Name")
    hiring_manager= data.get("hiring_manager", "Hiring Manager")
    role          = data.get("role", "the position")
    date_str      = data.get("date", "")
    paragraphs    = data.get("body_paragraphs", [
        "I am a recent graduate in [Field] from [University] and am excited to apply for the [Role] opportunity at [Company]. My academic training and hands-on project experience have prepared me to contribute meaningfully from day one.",
        "During my studies, I developed strong skills in [Skill 1], [Skill 2], and [Skill 3]. My final-year project on [Project Topic] gave me practical exposure to [Relevant Technology/Process], and I achieved [Result/Grade/Recognition].",
        "I am eager to grow within a company like [Company] that values [Culture Value]. I am a quick learner, highly motivated, and committed to delivering quality work. I look forward to contributing to your team.",
    ])

    contact_items = []
    if email:    contact_items.append(f"<a href='mailto:{email}' style='color:#1d4ed8;text-decoration:none;'>{email}</a>")
    if phone:    contact_items.append(phone)
    if location: contact_items.append(location)
    if linkedin:
        href = linkedin if linkedin.startswith('http') else f"https://{linkedin}"
        contact_items.append(f"<a href='{href}' target='_blank' style='color:#1d4ed8;text-decoration:none;'>{linkedin}</a>")
    contact_line = " &nbsp;|&nbsp; ".join(contact_items)

    paras_html = "".join(
        f"<p style='margin-bottom:16px;font-size:14px;color:#374151;line-height:1.8;'>{p}</p>"
        for p in paragraphs
    )

    return f"""<!DOCTYPE html>
<html lang='en'>
<head><meta charset='UTF-8'><meta name='viewport' content='width=device-width,initial-scale=1'><title>Cover Letter — {name}</title>
<style>
  * {{ box-sizing:border-box; margin:0; padding:0; }}
  body {{ font-family:'Segoe UI',Arial,sans-serif; background:#fff; color:#1f2937; padding:48px 64px; line-height:1.6; }}
</style>
</head>
<body>
<div style='max-width:794px;margin:0 auto;'>
  <!-- HEADER -->
  <div style='background:#eff6ff;border-left:5px solid #1d4ed8;padding:22px 28px;margin-bottom:30px;border-radius:0 8px 8px 0;'>
    <h1 style='font-size:26px;font-weight:800;color:#1e3a8a;margin-bottom:2px;'>{name}</h1>
    {f"<div style='font-size:14px;color:#3b82f6;font-weight:600;margin-bottom:8px;'>{job_title}</div>" if job_title else ''}
    <div style='font-size:12px;color:#6b7280;'>{contact_line}</div>
  </div>

  <!-- DATE + RECIPIENT -->
  {f"<p style='font-size:13px;color:#9ca3af;margin-bottom:18px;'>{date_str}</p>" if date_str else ''}
  <div style='margin-bottom:22px;'>
    <p style='font-size:14px;font-weight:600;color:#1f2937;'>{hiring_manager}</p>
    <p style='font-size:14px;color:#6b7280;'>{company}</p>
  </div>

  <!-- GREETING -->
  <p style='font-size:14px;margin-bottom:18px;'>Dear {hiring_manager},</p>

  <!-- BODY -->
  {paras_html}

  <!-- CLOSING -->
  <p style='font-size:14px;color:#374151;margin-bottom:28px;'>I would be grateful for the opportunity to interview and learn more about this role. Thank you for your time and consideration.</p>
  <p style='font-size:14px;'>Sincerely,</p>
  <p style='font-size:16px;font-weight:700;color:#1e3a8a;margin-top:10px;'>{name}</p>
  {f"<p style='font-size:13px;color:#6b7280;'>{job_title}</p>" if job_title else ''}
</div>
</body></html>"""


def render_cover_letter_ats(data):
    """
    Cover Letter Template 6 — Technical / ATS-Optimized
    Plain, fully text-based, high keyword density. Zero graphics — maximum ATS parse rate.
    Ideal for software engineers, data scientists, technical roles with ATS screening.
    """
    name          = data.get("name", "Your Name")
    job_title     = data.get("job_title", "")
    email         = data.get("email", "")
    phone         = data.get("phone", "")
    location      = data.get("location", "")
    linkedin      = data.get("linkedin", "")
    portfolio     = data.get("portfolio", "")
    company       = data.get("company", "Company Name")
    hiring_manager= data.get("hiring_manager", "Hiring Manager")
    role          = data.get("role", "the position")
    date_str      = data.get("date", "")
    key_skills    = data.get("key_skills", "Python, Machine Learning, SQL, Cloud Infrastructure, Agile")
    paragraphs    = data.get("body_paragraphs", [
        "I am applying for the [Role] position at [Company]. My technical background includes [Key Skills] with [X] years of hands-on industry experience across [Domain 1] and [Domain 2].",
        "In my current role at [Company], I [Specific Technical Achievement] using [Technologies], which resulted in [Measurable Outcome — e.g., 40% reduction in processing time]. I also led [Another Contribution] that improved [System/Process] reliability by [Metric].",
        "I am particularly interested in [Company]'s work on [Product/Project/Technology Stack]. My experience with [Relevant Tool/Framework] and my understanding of [Technical Domain] position me to add immediate value to your engineering team.",
    ])

    if job_title: contact_parts_line = f"{name} | {job_title}"
    else:         contact_parts_line = name

    details = []
    if email:    details.append(email)
    if phone:    details.append(phone)
    if location: details.append(location)
    if linkedin: details.append(linkedin)
    if portfolio:details.append(portfolio)
    details_line = " | ".join(details)

    paras_html = "".join(
        f"<p style='margin-bottom:14px;font-size:14px;color:#111827;line-height:1.8;'>{p}</p>"
        for p in paragraphs
    )

    return f"""<!DOCTYPE html>
<html lang='en'>
<head><meta charset='UTF-8'><meta name='viewport' content='width=device-width,initial-scale=1'><title>Cover Letter — {name}</title>
<style>
  * {{ box-sizing:border-box; margin:0; padding:0; }}
  body {{ font-family:Arial,Helvetica,sans-serif; background:#fff; color:#111827; padding:48px 64px; line-height:1.6; font-size:14px; }}
  hr {{ border:none; border-top:1px solid #d1d5db; margin:18px 0; }}
</style>
</head>
<body>
<div style='max-width:794px;margin:0 auto;'>
  <!-- ATS HEADER — plain text, no images -->
  <div style='margin-bottom:6px;'>
    <p style='font-size:22px;font-weight:700;color:#111827;'>{contact_parts_line}</p>
    <p style='font-size:13px;color:#374151;margin-top:4px;'>{details_line}</p>
  </div>
  <hr>

  <!-- DATE -->
  {f"<p style='margin-bottom:16px;color:#374151;'>{date_str}</p>" if date_str else ''}

  <!-- RECIPIENT -->
  <div style='margin-bottom:20px;'>
    <p style='font-weight:600;color:#111827;'>{hiring_manager}</p>
    <p style='color:#374151;'>{company}</p>
  </div>

  <!-- SUBJECT LINE (ATS-friendly) -->
  <p style='font-weight:700;margin-bottom:18px;'>Re: Application for {role} — {name}</p>

  <!-- GREETING -->
  <p style='margin-bottom:18px;'>Dear {hiring_manager},</p>

  <!-- BODY -->
  {paras_html}

  <!-- KEY SKILLS MENTION (ATS keyword boost) -->
  <p style='margin-bottom:14px;font-size:14px;color:#111827;line-height:1.8;'>
    <strong>Core Technical Skills:</strong> {key_skills}
  </p>

  <!-- CLOSING -->
  <p style='margin-bottom:28px;color:#374151;'>I have attached my resume for your review. I am available for an interview at your earliest convenience and can be reached at {email or phone or "the contact details above"}.</p>
  <p>Sincerely,</p>
  <p style='font-weight:700;font-size:15px;margin-top:10px;'>{name}</p>
  {f"<p style='color:#374151;margin-top:2px;'>{job_title}</p>" if job_title else ''}
</div>
</body></html>"""


# ── Cover Letter template registry ────────────────────────────────────────────
COVER_LETTER_TEMPLATES = {
    "Professional / Corporate":     render_cover_letter_professional,
    "Modern Minimal":               render_cover_letter_modern,
    "Creative":                     render_cover_letter_creative,
    "Executive":                    render_cover_letter_executive,
    "Entry-Level / Fresher":        render_cover_letter_entry_level,
    "Technical / ATS-Optimized":    render_cover_letter_ats,
}

def render_cover_letter(template_name, data):
    """
    Render a cover letter from a named template.

    Args:
        template_name (str): One of the keys in COVER_LETTER_TEMPLATES.
        data (dict): Cover letter data. Common keys:
            name, job_title, email, phone, location, linkedin, portfolio,
            company, hiring_manager, role, date, body_paragraphs (list[str]),
            key_skills (str, ATS template only), accent_color (str, Creative only).

    Returns:
        str: Full HTML string for the cover letter.
    """
    fn = COVER_LETTER_TEMPLATES.get(template_name)
    if fn is None:
        fn = render_cover_letter_professional
    return fn(data)


def generate_cover_letter_from_resume_builder():
    import streamlit as st
    from datetime import datetime
    import re
    import time
    from llm_manager import call_llm  # Ensure you import this

    name = st.session_state.get("name", "")
    job_title = st.session_state.get("job_title", "")
    summary = st.session_state.get("summary", "")
    skills = st.session_state.get("skills", "")
    location = st.session_state.get("location", "")
    from datetime import timezone, timedelta
    IST = timezone(timedelta(hours=5, minutes=30))
    today_date = datetime.now(IST).strftime("%B %d, %Y")

    # Wrap all inputs + submit in a form so Streamlit only reruns on submit,
    # not on every keystroke (which was causing the page-reload flicker).
    with st.form(key="cover_letter_form"):
        # ✅ FIX 1 — Template selector dropdown
        cover_letter_template = st.selectbox(
            "🎨 Choose Cover Letter Template",
            options=list(COVER_LETTER_TEMPLATES.keys()),
            index=0,
            key="cover_letter_template_select",
            help="Select the style/format for your cover letter"
        )

        # ✅ FIX 3 — Accent color picker (only relevant for Creative template)
        accent_color = st.color_picker("🎨 Choose Accent Color (Creative template only)", value="#7c3aed", key="cl_accent_color")

        # ✅ Input boxes for contact info
        company = st.text_input("🏢 Target Company", placeholder="e.g., Google")
        linkedin = st.text_input("🔗 LinkedIn URL", placeholder="e.g., https://linkedin.com/in/username")
        email = st.text_input("📧 Email", placeholder="e.g., you@example.com")
        mobile = st.text_input("📞 Mobile Number", placeholder="e.g., +91 9876543210")

        submitted_cl = st.form_submit_button("✉️ Generate Cover Letter")

    # Resolve accent color: only use picked color for Creative, else default
    if cover_letter_template != "Creative":
        accent_color = "#003366"

    if submitted_cl:
        # ✅ Validate input before generating
        if not all([name, job_title, summary, skills, company, linkedin, email, mobile]):
            st.warning("⚠️ Please fill in all fields including LinkedIn, email, and mobile.")
            return

        prompt = f"""
You are a professional cover letter writer.

Write ONLY the body paragraphs of a cover letter for the candidate below.
Do NOT include: date, recipient address, salutation ("Dear ..."), closing ("Sincerely"), or the candidate's name at the end.
The template will add all of those automatically — your job is only the 3 body paragraphs.

Output exactly 3 paragraphs separated by a blank line (double newline).
Each paragraph should be 2-4 sentences.

### Candidate Info:
- Name: {name}
- Job Title: {job_title}
- Target Company: {company}
- Location: {location}
- Summary: {summary}
- Skills: {skills}

### Instructions:
- Do NOT include the date, header, salutation, or sign-off.
- Do NOT start with "Dear Hiring Manager" or any greeting.
- Do NOT end with "Sincerely" or the candidate's name.
- Do not use HTML tags.
- Separate each paragraph with a blank line (double newline).
- Return plain text body paragraphs ONLY.
"""

        # ✅ Call LLM
        with st.spinner("✉️ Crafting your cover letter... please wait"):
            cover_letter_raw = call_llm(prompt, session=st.session_state).strip()

        # ✅ Strip any header/salutation/closing lines the LLM may have added despite instructions
        import re as _cl_re

        def _strip_letter_boilerplate(text):
            """Remove date lines, salutation, closing and name sign-off from LLM output."""
            lines = text.split('\n')
            cleaned = []
            # Patterns to strip
            skip_patterns = [
                r'^\s*(january|february|march|april|may|june|july|august|september|october|november|december)\s+\d',  # date lines
                r'^\s*\d{1,2}[\/\-]\d{1,2}[\/\-]\d{2,4}',       # numeric date
                r'^\s*dear\b',                                      # salutation
                r'^\s*(sincerely|regards|best regards|yours truly|warm regards|respectfully)',  # closing
                r'^\s*hiring manager[,.]?\s*$',                    # bare "Hiring Manager"
                r'^\s*[a-z ]+,\s*(kolkata|mumbai|delhi|bangalore|hyderabad|chennai|pune)',  # "Company, City"
            ]
            skip_re = [_cl_re.compile(p, _cl_re.IGNORECASE) for p in skip_patterns]
            # Also skip the last 1-2 lines if they look like a name sign-off (short line after closing)
            # Find closing line index
            closing_idx = None
            for i, line in enumerate(lines):
                if any(r.match(line) for r in skip_re[4:5]):  # closing words
                    closing_idx = i
            for i, line in enumerate(lines):
                if any(r.match(line) for r in skip_re):
                    continue
                # Skip lines that are just the candidate name (after a closing)
                if closing_idx is not None and i > closing_idx and line.strip().lower() in (name.lower(), job_title.lower(), ''):
                    continue
                cleaned.append(line)
            return '\n'.join(cleaned).strip()

        cover_letter_body = _strip_letter_boilerplate(cover_letter_raw)

        # ✅ Store plain text (full body only, no boilerplate)
        st.session_state["cover_letter"] = cover_letter_body

        # ✅ Robust paragraph splitting (handles \n\n and single \n)
        normalised  = _cl_re.sub(r'\n{3,}', '\n\n', cover_letter_body)
        raw_paras   = normalised.split('\n\n')
        if len(raw_paras) <= 1:          # fallback: LLM used single newlines only
            raw_paras = normalised.split('\n')
        body_paragraphs = [p.strip() for p in raw_paras if p.strip()]

        # ✅ Build structured data dict for all template renderers
        cl_data = {
            "name":            name,
            "job_title":       job_title,
            "email":           email,
            "phone":           mobile,
            "location":        location,
            "linkedin":        linkedin,
            "portfolio":       "",
            "company":         company,
            "hiring_manager":  "Hiring Manager",
            "role":            job_title,
            "date":            today_date,
            "body_paragraphs": body_paragraphs,
            "key_skills":      skills,       # used by ATS template
            "accent_color":    accent_color, # FIX 3 — user-picked color for Creative
        }

        # ✅ FIX 1 — Render using the chosen template
        cover_letter_html = render_cover_letter(cover_letter_template, cl_data)

        st.session_state["cover_letter_html"] = cover_letter_html

        # ✅ Show cover letter in an iframe so the full HTML template renders correctly
        # (st.markdown cannot render full <!DOCTYPE html> documents — it leaks raw tags)
        import streamlit.components.v1 as _cl_components
        st.success("✅ Cover letter generated successfully!")
        st.markdown(
            "<p style='color:#555; font-size:13px; margin-top:8px;'>"
            "📄 Cover Letter Preview (scroll to explore):</p>",
            unsafe_allow_html=True,
        )
        _cl_components.html(
            cover_letter_html,
            height=700,
            scrolling=True,
        )
