import os
os.environ["STREAMLIT_WATCHDOG"] = "false"
import json
import re
import urllib.parse
import datetime
import time

import streamlit as st
import torch
from langchain_text_splitters import CharacterTextSplitter
from langchain_community.vectorstores import FAISS
from langchain_community.embeddings import HuggingFaceEmbeddings
from langchain_groq import ChatGroq
from langchain.chains import ConversationalRetrievalChain
from llm_manager import (
    call_llm, load_groq_api_keys, get_healthy_keys,
    _mem_record_failure, _mem_clear_failure,
    _mem_increment_usage, _async_mark_failure, _async_increment_usage,
    _async_clear_failure,
)
from db_manager import (
    db_manager,
    get_domain_similarity,
)

DEVICE = "cuda" if torch.cuda.is_available() else "cpu"

# ── resume_engine.py ────────────────────────────────────────────────────────
gender_words = {
    "masculine": [
        # Dominance / aggression-coded
        "active", "aggressive", "ambitious", "assertive", "autonomous", "boast", "bold",
        "challenging", "competitive", "confident", "courageous", "decisive", "determined", "dominant", "driven",
        "dynamic", "forceful", "independent", "individualistic", "intellectual", "lead", "leader", "objective",
        "outspoken", "persistent", "principled", "proactive", "resilient", "self-reliant", "self-sufficient",
        "strong", "superior", "tenacious", "guru", "tech guru", "technical guru", "visionary", "manpower",
        "strongman", "command", "assert", "headstrong", "rockstar", "superstar", "go-getter", "trailblazer",
        "results-driven", "fast-paced", "determination", "competitive spirit",
        # Additional research-backed masculine-coded terms (Gaucher et al., 2011)
        "analytical", "backbone", "challenge", "champion", "combat", "conquer", "courageous",
        "crusade", "debate", "fearless", "fight", "grit", "hustle", "impact", "ninja",
        "power", "ruthless", "self-starter", "sharp", "warrior", "win", "wrestler",
        "alpha", "beast", "brutally honest", "cutting-edge", "dominate", "edge", "elite",
        "fearless", "grind", "hardcore", "hero", "high-performance", "intense",
        "kill it", "relentless", "savage", "slayer", "tiger", "tough", "uncompromising"
    ],
    
    "feminine": [
        # Communal / warmth-coded
        "affectionate", "agreeable", "attentive", "collaborative", "committed", "compassionate", "considerate",
        "cooperative", "dependable", "dependent", "emotional", "empathetic", "enthusiastic", "friendly", "gentle",
        "honest", "inclusive", "interpersonal", "kind", "loyal", "modest", "nurturing", "pleasant", "polite",
        "sensitive", "supportive", "sympathetic", "tactful", "tender", "trustworthy", "understanding", "warm",
        "yield", "adaptable", "communal", "helpful", "dedicated", "respectful", "nurture", "sociable",
        "relationship-oriented", "team player", "people-oriented", "empathetic listener",
        "gentle communicator", "open-minded",
        # Additional research-backed feminine-coded terms
        "balance", "caring", "child-friendly", "connect", "connection", "flexible hours",
        "harmony", "heart", "humanize", "mindful", "patience", "patient", "peace",
        "personal touch", "responsive", "share", "sharing", "together", "unite",
        "welcoming", "wholesome", "connect with", "feeling", "feelings", "giving back",
        "heartfelt", "humanity", "inspire", "inspired", "passion", "passionate",
        "personable", "relate", "relatable", "soften", "soft skills", "spread",
        "thrive", "togetherness", "transparent", "uplift", "vulnerable"
    ]
}

def detect_bias(text):
    # Split into sentences using simple delimiters
    sentences = re.split(r'(?<=[.!?])\s+', text.strip())

    masc_set, fem_set = set(), set()
    masculine_found, feminine_found = [] , []

    masculine_words = sorted(gender_words["masculine"], key=len, reverse=True)
    feminine_words = sorted(gender_words["feminine"], key=len, reverse=True)

    for sent in sentences:
        sent_text = sent.strip()
        sent_lower = sent_text.lower()
        matched_spans = []

        def is_overlapping(start, end):
            return any(start < e and end > s for s, e in matched_spans)

        # 🔵 Highlight masculine words in blue
        for word in masculine_words:
            pattern = re.compile(rf'\b{re.escape(word)}\b', re.IGNORECASE)
            for match in pattern.finditer(sent_lower):
                start, end = match.span()
                if not is_overlapping(start, end):
                    matched_spans.append((start, end))
                    key = (word.lower(), sent_text)
                    if key not in masc_set:
                        masc_set.add(key)
                        highlighted = re.sub(
                            rf'\b({re.escape(word)})\b',
                            r'<span style="color:blue;">\1</span>',
                            sent_text,
                            flags=re.IGNORECASE
                        )
                        masculine_found.append({
                            "word": word,
                            "sentence": highlighted
                        })

        # 🔴 Highlight feminine words in red
        for word in feminine_words:
            pattern = re.compile(rf'\b{re.escape(word)}\b', re.IGNORECASE)
            for match in pattern.finditer(sent_lower):
                start, end = match.span()
                if not is_overlapping(start, end):
                    matched_spans.append((start, end))
                    key = (word.lower(), sent_text)
                    if key not in fem_set:
                        fem_set.add(key)
                        highlighted = re.sub(
                            rf'\b({re.escape(word)})\b',
                            r'<span style="color:red;">\1</span>',
                            sent_text,
                            flags=re.IGNORECASE
                        )
                        feminine_found.append({
                            "word": word,
                            "sentence": highlighted
                        })

    masc = len(masculine_found)
    fem = len(feminine_found)
    total = masc + fem
    bias_score = min(total / 20, 1.0) if total > 0 else 0.0

    return round(bias_score, 2), masc, fem, masculine_found, feminine_found

replacement_mapping = {
    "masculine": {
        "active": "engaged",
        "aggressive": "proactive",
        "ambitious": "motivated",
        "analytical": "detail-oriented",
        "assertive": "direct",
        "autonomous": "self-directed",
        "boast": "highlight",
        "bold": "confident",
        "challenging": "demanding",
        "competitive": "goal-oriented",
        "confident": "self-assured",
        "courageous": "bold",
        "decisive": "action-oriented",
        "determined": "focused",
        "dominant": "influential",
        "driven": "committed",
        "dynamic": "adaptable",
        "forceful": "persuasive",
        "guru": "technical expert",
        "independent": "self-sufficient",
        "individualistic": "self-motivated",
        "intellectual": "knowledgeable",
        "lead": "guide",
        "leader": "team lead",
        "objective": "unbiased",
        "outspoken": "expressive",
        "persistent": "tenacious",
        "principled": "ethical",
        "proactive": "initiative-taking",
        "resilient": "adaptable",
        "self-reliant": "resourceful",
        "self-sufficient": "capable",
        "strong": "capable",
        "superior": "exceptional",
        "tenacious": "determined",
        "technical guru": "technical expert",
        "visionary": "forward-thinking",
        "manpower": "workforce",
        "strongman": "resilient individual",
        "command": "direct",
        "assert": "state clearly",
        "headstrong": "determined",
        "rockstar": "top performer",
        "superstar": "outstanding contributor",
        "go-getter": "initiative-taker",
        "trailblazer": "innovator",
        "results-driven": "outcome-focused",
        "fast-paced": "dynamic",
        "determination": "commitment",
        "competitive spirit": "goal-oriented mindset",
        # New additions
        "ninja": "specialist",
        "warrior": "dedicated professional",
        "alpha": "senior",
        "beast": "high performer",
        "dominate": "excel in",
        "elite": "high-performing",
        "relentless": "persistent",
        "savage": "highly skilled",
        "hustle": "work efficiently",
        "grit": "resilience",
        "hardcore": "rigorous",
        "hero": "key contributor",
        "ruthless": "highly focused",
        "kill it": "excel",
        "champion": "advocate",
        "conquer": "achieve",
        "fight": "address",
        "win": "achieve success",
        "crush": "exceed targets",
        "unstoppable": "highly motivated",
        "fearless": "courageous",
        "power": "capability",
        "backbone": "core strength",
        "sharp": "perceptive"
    },
    
    "feminine": {
        "affectionate": "approachable",
        "agreeable": "cooperative",
        "attentive": "observant",
        "collaborative": "team-oriented",
        "collaborate": "team-oriented",
        "collaborated": "worked together",
        "committed": "dedicated",
        "compassionate": "caring",
        "considerate": "thoughtful",
        "cooperative": "supportive",
        "dependable": "reliable",
        "dependent": "team-oriented",
        "emotional": "passionate",
        "empathetic": "perceptive",
        "enthusiastic": "energized",
        "gentle": "respectful",
        "honest": "transparent",
        "inclusive": "open-minded",
        "interpersonal": "people-focused",
        "kind": "respectful",
        "loyal": "dedicated",
        "modest": "measured",
        "nurturing": "supportive",
        "pleasant": "professional",
        "polite": "courteous",
        "sensitive": "perceptive",
        "supportive": "enabling",
        "sympathetic": "understanding",
        "tactful": "diplomatic",
        "tender": "considerate",
        "trustworthy": "reliable",
        "understanding": "empathetic",
        "warm": "welcoming",
        "yield": "adjust",
        "adaptable": "flexible",
        "communal": "team-centered",
        "helpful": "contributive",
        "dedicated": "committed",
        "respectful": "professional",
        "nurture": "develop",
        "sociable": "collegial",
        "relationship-oriented": "team-focused",
        "team player": "collaborative member",
        "people-oriented": "stakeholder-focused",
        "empathetic listener": "active listener",
        "gentle communicator": "considerate communicator",
        "open-minded": "inclusive",
        # New additions
        "passionate": "highly motivated",
        "inspired": "driven by purpose",
        "inspire": "motivate",
        "vulnerable": "transparent",
        "heartfelt": "sincere",
        "harmony": "alignment",
        "caring": "attentive",
        "patient": "thorough",
        "wholesome": "balanced",
        "togetherness": "team cohesion",
        "soft skills": "professional competencies",
        "personal touch": "tailored approach",
        "feeling": "assessment",
        "feelings": "perspectives",
        "transparent": "accountable",
        "uplift": "elevate",
        "thrive": "excel",
        "welcoming": "inclusive",
        "relatable": "accessible",
        "connect": "engage",
        "together": "collaboratively",
        "sharing": "distributing",
        "mindful": "deliberate",
        "balance": "manage effectively"
    }
}

def rewrite_and_optimize_resume(text, replacement_mapping, user_location):
    """
    ⚡ MERGED FUNCTION — replaces rewrite_text_with_llm() + optimize_resume_to_json()
    Single LLM call that returns BOTH:
      - rewritten_text : plain-text ATS-optimised resume + job title suggestions (for UI display)
      - json_str       : strict JSON object (for DOCX generation)
    Saves 1 API key call per resume analysis (6 → 5 calls total).
    """

    formatted_mapping = "\n".join(
        [f'- "{key}" → "{value}"' for key, value in replacement_mapping.items()]
    )

    prompt = f"""You are an enterprise-grade ATS resume optimization engine and bias-removal specialist.

Your task is to process the resume below and return TWO outputs in a single response, separated by the exact delimiter shown.

════════════════════════════════════════════════════════
OUTPUT STRUCTURE (return EXACTLY this — no deviation):
════════════════════════════════════════════════════════

===REWRITTEN_RESUME_START===
<full plain-text ATS-optimised resume here>
<followed by job title suggestions block>
===REWRITTEN_RESUME_END===

===JSON_START===
<strict JSON object here — no markdown fences, no explanation>
===JSON_END===

════════════════════════════════════════════════════════
PART 1 — PLAIN TEXT REWRITE (inside REWRITTEN_RESUME tags)
════════════════════════════════════════════════════════

ABSOLUTE RULES — NEVER VIOLATE:
• DO NOT fabricate companies, job titles, degrees, institutions, or dates.
• DO NOT invent statistics or metrics not implied by the resume content.
• DO NOT add certifications, tools, or skills absent from the resume.
• DO NOT use personal pronouns ANYWHERE — not in summary, bullets, descriptions, or any section.
  BANNED WORDS/PHRASES (zero tolerance across the ENTIRE resume):
  ✗ "I", "I am", "I have", "I worked", "I built", "I led", "I developed"
  ✗ "My", "Me", "We", "Our", "Us"
  ✗ "As a [role]..." — NEVER start any sentence with "As a"
  ✗ "With a passion for...", "Passionate about...", "I am passionate..."
  ✗ "Highly motivated", "Dynamic professional", "Results-driven", "Go-getter"
  ✗ "Seasoned", "Veteran", "Proven track record", "Rockstar", "Ninja", "Guru"
  ✗ "I believe", "I feel", "I think", "In my experience"
  ✗ "Looking for", "Seeking to", "Hoping to" — in summary (use in objective only if truly fresher)
• VOICE: Write in THIRD-PERSON IMPLICIT (omit the subject entirely).
  ✓ CORRECT: "Full Stack Developer with 3 years of experience building scalable web apps."
  ✓ CORRECT: "Developed RESTful APIs using Django and PostgreSQL, reducing latency by 40%."
  ✓ CORRECT: "Aspiring Data Scientist with hands-on ML project experience in Python and TensorFlow."
  ✗ WRONG:   "As a Full Stack Developer, I have 3 years of experience..."
  ✗ WRONG:   "I developed RESTful APIs using Django..."
  ✗ WRONG:   "I am an aspiring Data Scientist..."
• DO NOT repeat the same phrase or word across multiple sections.
• EVERY section must contain unique, non-overlapping content.
• DO NOT exaggerate experience level. If the candidate has no work experience or is a fresher/student, the summary MUST use honest framing: "Aspiring", "Entry-level", "Recent graduate". NEVER use "seasoned", "veteran", "proven track record", or imply years of experience that do not exist in the resume.
• PROFESSIONAL SUMMARY must reflect ONLY what is actually present in the resume. Do not upgrade a fresher to a professional or a junior to a senior.

YOU MAY:
✓ Strengthen bullet points with stronger action verbs and tighter phrasing.
✓ Reconstruct missing sections when clear evidence exists in the resume.
✓ Consolidate skills scattered across experience/projects into the Skills section.
✓ Infer tool proficiency when strongly implied (e.g., "built Flask API" → Python, Flask).
✓ Add plausible impact framing using "~" when the role implies measurable output.

SECTION ORDER: Contact Header → Professional Summary → Core Skills →
Work Experience → Projects → Education → Certifications & Links

CONTACT HEADER: Full Name | Job Title | Email | Phone | Location | LinkedIn URL | GitHub/Portfolio URL

PROFESSIONAL SUMMARY (2–3 sentences):
  FIRST — assess the candidate's actual experience level from the resume:
  • No experience / student / fresher → use "Aspiring [Role]" or "Recent [Degree] graduate"
  • 0–2 years → "Entry-level" or "Junior"
  • 2–5 years → "Mid-level" or just state domain + years honestly
  • 5+ years → "Senior" or "Lead" only if the resume clearly supports it

  SENTENCE STRUCTURE — STRICTLY FOLLOW:
  Sentence 1: [Seniority label] + [Job Title/Domain] + ["with X years of experience in" OR "specializing in"] + [core domain/stack]
              NEVER start with "As a", "I am", "I have", or any pronoun.
              ✓ "Mid-level Full Stack Developer with 3 years of experience building scalable web applications."
              ✓ "Entry-level Python Developer specializing in backend development and RESTful API design."
              ✓ "Aspiring Data Scientist with hands-on project experience in ML pipelines and NLP."
  Sentence 2: [Top 2–3 specific technical strengths from resume — tools, frameworks, proven skills]
              Start with a strong action noun or skill cluster. Never start with "I" or "As a".
              ✓ "Proficient in React.js, Node.js, and MongoDB with demonstrated experience in full-stack deployment."
              ✓ "Skilled in LangChain, FAISS, and LLaMA with hands-on RAG pipeline development."
  Sentence 3: [Career value proposition — what they bring or are seeking]
              ✓ "Committed to building efficient, scalable solutions that drive measurable business impact."
              ✓ "Seeking to contribute strong backend expertise to a growth-focused engineering team."

CORE SKILLS: labeled lines — Technical Skills: [...] and Professional Skills: [...]

WORK EXPERIENCE (reverse chronological):
  Job Title | Company Name | MMM YYYY – MMM YYYY
  [1-sentence role scope — NO pronouns, NO "As a", starts with a noun or action word]
  • [Action Verb] + [Task] + [Technology] + [Quantified impact]
  (3–5 bullets per role)
  Strong verbs ONLY: Architected, Engineered, Developed, Implemented, Optimized, Automated,
  Spearheaded, Deployed, Designed, Reduced, Increased, Streamlined, Led, Built, Delivered, Launched.
  NEVER: helped, assisted, worked on, involved in, responsible for, I did, I built, I led.
  EVERY bullet must start with a strong past-tense action verb — NEVER with "I", "We", or "As a".

  ⚠️ ZERO EXPERIENCE / FRESHER RULE — CRITICAL:
  If the candidate has NO work experience (no jobs, no internships):
  • DO NOT write a "Work Experience" section at all — omit it entirely.
  • DO NOT write "0 years of experience", "No experience", "N/A", or any placeholder.
  • Instead, elevate the PROJECTS section — give it prominence immediately after Core Skills.
  • In the Professional Summary, use honest framing: "Aspiring [Role]" or "Recent graduate
    with hands-on project experience in [domain]" — never imply professional tenure.
  If the candidate has only internship(s) but NO full-time roles:
  • Label the section "Internship Experience" instead of "Work Experience".
  • Present internships with the same bullet format (3–5 achievement bullets each).
  • DO NOT write "0 years of full-time experience" anywhere.

PROJECTS: Name | Tech Stack | Duration
  [1-sentence purpose — starts with a noun/verb, NO pronouns, NO "As a", NO "I built"]
  • [Achievement bullet — starts with strong action verb, NO pronouns]
  (3–5 bullets)
  ✓ "Built a real-time chat application using Socket.io and React.js."
  ✗ "I built a real-time chat application..."
  ✗ "As a developer, I created..."

EDUCATION: Degree, Major | Institution | Graduation Year | CGPA/Percentage
  • YEAR EXTRACTION (CRITICAL — scan the ENTIRE education block, not just the degree line):
    - Year can appear ANYWHERE in the education block: above, below, beside, or after the degree/institution
    - Accept ANY of these formats: "Oct 2021 – Jul 2024", "2021-2024", "October 2021 - July 2024",
      "Batch: 2024", "Passout: 2024", "Expected: 2025", "graduating 2025", "2024", "May 2023",
      right-aligned dates, dates below GPA line, dates on a separate line entirely
    - If only one year found → use it as graduation year
    - If a range found → preserve the full range as written (e.g. "October 2021 - July 2024")
    - NEVER leave year blank if ANY date pattern exists anywhere near the education block
  • CGPA/Percentage (preserve exactly as written — e.g. "CGPA: 8.5/10", "7.0 GPA", "78.3%", "8.44" — NEVER convert between the two, NEVER relabel)
  • Include honors, distinctions, or relevant coursework if mentioned in the original resume.
CERTIFICATIONS: • Name | Issuing Body | MMM YYYY

ATS FORMATTING:
• Single-column structure — no tables, columns, text boxes.
• Bullet points: "•" only. Section headings: ALL CAPS.
• No emojis, no personal pronouns.

BIAS REPLACEMENT RULES — APPLY EXACTLY:
{formatted_mapping}

MANDATORY JOB TITLE SUGGESTIONS (append after the resume text):

### 🎯 Suggested Job Titles (Based on Resume)

Provide EXACTLY 5 job titles suited for a candidate in {user_location}.
FORMAT:
1. **[Job Title]** — [Specific reason tied to resume evidence]
🔗 https://www.linkedin.com/jobs/search/?keywords=[URL+encoded+title]&location={urllib.parse.quote(user_location)}

════════════════════════════════════════════════════════
PART 2 — JSON OBJECT (inside JSON tags)
════════════════════════════════════════════════════════

Return ONLY valid JSON. No preamble, no explanation, no markdown fences.

CONTENT REWRITING — same ATS rules as Part 1 apply to all bullet fields.
Strong verbs only. Quantified impact. No pronouns. No repetition across sections.

RETURN ONLY THIS EXACT JSON STRUCTURE:
{{
  "contact": {{
    "name": "",
    "title": "",
    "email": "",
    "phone": "",
    "location": "",
    "linkedin": "",
    "github": "",
    "portfolio": ""
  }},
  "summary": "",
  "skills": [],
  "soft_skills": [],
  "languages": [],
  "interests": [],
  "experience": [
    {{
      "role": "",
      "company": "",
      "duration": "",
      "description": "",
      "bullets": []
    }}
  ],
  "projects": [
    {{
      "name": "",
      "duration": "",
      "tech_stack": "",
      "url": "",
      "description": "",
      "bullets": []
    }}
  ],
  "education": [
    {{
      "degree": "",
      "institution": "",
      "year": "",
      "cgpa": "",
      "bullets": []
    }}
  ],
  "certifications": [
    {{
      "name": "",
      "issuer": "",
      "duration": ""
    }}
  ],
  "additional": [
    {{
      "name": "",
      "description": "",
      "duration": ""
    }}
  ]
}}

FIELD RULES:

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
GOLDEN RULE — APPLIES TO EVERY FIELD IN EVERY SECTION:
  • NEVER fabricate names, companies, degrees, institutions, skills, URLs, or metrics.
  • NEVER write "[Not Provided]", "N/A", "Unknown" anywhere — use "" for missing text, [] for missing arrays.
  • NEVER invent a date with zero context — if no clue exists anywhere → store "".
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
3-TIER DATE INFERENCE RULE — APPLIES TO ALL duration/year FIELDS:

  TIER 1 — EXPLICIT (highest priority):
    Date is clearly written in the resume near this entry.
    → Extract and store EXACTLY as written. Never reformat.
    → Examples: "Aug 2021 – Dec 2024", "October 2021 - July 2024", "Jul 2025", "2023", "45 days"

  TIER 2 — INFERRED FROM CONTEXT (use ONLY when strong evidence exists):
    Date is NOT written for this entry BUT can be confidently derived from surrounding resume context.
    Strong context signals (ALL must be true to infer):
      ✓ Project is explicitly described as part of an internship/job role that HAS dates → use those dates
      ✓ Project description mentions the company/internship period → use that period
      ✓ Certification is clearly tied to a dated training program mentioned elsewhere
      ✓ Education year can be derived from a "Batch of YYYY" or "Passout YYYY" written elsewhere
    → Store with "~" prefix to signal inference: e.g. "~Aug 2022 – Dec 2023"
    → NEVER infer just because two entries are near each other on the page.
    → NEVER infer from education dates for a project unless project explicitly says "college project" + education has clear dates.

  TIER 3 — UNKNOWN (no context at all):
    No date written, no strong context to infer from.
    → Store "" (empty string). The DOCX template will silently skip it.
    → NEVER guess. NEVER copy a random date from elsewhere.
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

── CONTACT ──
- "contact.*" = extract exactly as written. Use "" not null for missing fields. Never invent email, phone, or URLs.

── SUMMARY ──
- "summary" = 2–3 sentences, max 80 words, NO pronouns anywhere. Must be COMPLETE — do NOT truncate mid-sentence.
  Must match the Professional Summary written in Part 1 exactly.
  MUST reflect actual experience level: freshers → "Aspiring/Entry-level", never fabricate years of experience.
  MUST follow third-person implicit voice — no "I", "My", "As a", "I am", "I have" anywhere.
  ✓ "Mid-level Full Stack Developer with 3 years of experience..."
  ✗ "As a mid-level Full Stack Developer, I have 3 years..."
  ✗ "I am an entry-level developer with..."

── SKILLS ──
- "skills" = flat array of individual skill strings. Minimum 8. No duplicates. Only extract skills actually present in resume.
- "soft_skills" = professional competency phrases. Must NOT duplicate items in "skills".

── EXPERIENCE ──
- "experience" = if NO work experience AND no internships → set to [] (empty array). Never populate with placeholder roles.
  If only internships exist → include them with role/company/duration/bullets. Label role accurately (e.g. "Intern").
- "experience[].role" = exact job title as written. Never upgrade title (e.g. do NOT change "Intern" to "Developer").
- "experience[].company" = exact company name as written.
- "experience[].duration" = Apply 3-TIER DATE INFERENCE RULE.
    SCAN THE ENTIRE EXPERIENCE BLOCK for date patterns near this role (dates can appear above, below, or beside).
    Accepted formats: "Aug 2021 – Dec 2024", "August 2021 - December 2024", "Jan 2023 – Present",
    "2022–2023", "Feb 2024 - Nov 2025", month+year ranges, standalone years.
    If end date says "Present" / "present" / "current" / "Ongoing" → store as written (e.g. "Dec 2024 – Present").
    Tier 1: date found → store exactly. Tier 2: infer with "~" prefix. Tier 3: store "".
- "experience[].description" = 1-sentence role scope, unique from bullets. NO pronouns. NO "As a". NO "I".
    ✓ "Full-stack role focused on building responsive web applications using React.js and Node.js."
    ✗ "As a developer, I was responsible for building web applications."
- "experience[].bullets" = 3–5 bullets each. Strong past-tense verb + task + tech + quantified impact. NO pronouns. NO "I". NO "As a".

── PROJECTS ──
- "projects[].name" = exact project name as written.
- "projects[].duration" = Apply 3-TIER DATE INFERENCE RULE.
    SCAN THE ENTIRE PROJECT BLOCK for any date/time pattern near this project.
    Accepted formats: "Mar 2025 – Aug 2025", "October 2021 – December 2021", "3 months", "45 days",
    "Jan 2024", standalone year "2023", any time range written near the project.
    Tier 1: date found → store exactly as written (e.g. "October 2021 – December 2021").
    Tier 2: project is explicitly described as part of a dated internship/job → infer with "~" prefix
            e.g. project says "built during internship at XYZ (Aug 2022–Dec 2023)" → "~Aug 2022 – Dec 2023"
    Tier 3: no date, no context → store "".
- "projects[].tech_stack" = comma-separated technologies mentioned for this project.
- "projects[].url" = project URL/GitHub link if present. Use "" if not present.
- "projects[].description" = 1-sentence project purpose. NO pronouns. NO "I built". NO "As a". Unique, not repeated in bullets.
    ✓ "Real-time food delivery platform built with React.js, Node.js, and MongoDB."
    ✗ "I built a food delivery platform..."
- "projects[].bullets" = 3–5 bullets. Must NOT restate experience bullets. Strong past-tense verb + task + tech + impact. NO pronouns.

── EDUCATION ──
- "education[].degree" = extract the FULL degree name including type AND major/subject.
    If degree type and subject are on separate lines → combine them (e.g. "B.SC" + "Computer Science" → "B.SC Computer Science").
    NEVER leave blank if any degree-related text exists in the education block.
- "education[].institution" = university/college name exactly as written. Full name, not abbreviation.
- "education[].year" = Apply 3-TIER DATE INFERENCE RULE.
    SCAN THE ENTIRE EDUCATION BLOCK — year can appear ANYWHERE (above, below, beside, far from degree line).
    Accepted formats: "October 2021 - July 2024", "2021–2024", "Oct 2021 – Jul 2024",
    "Batch: 2024", "Passout: 2024", "Expected: 2025", "graduating 2025", standalone "2024", "May 2023",
    dates below CGPA line, dates to the right of institution, dates on completely separate lines.
    Tier 1: date found → store FULL range exactly as written (e.g. "October 2021 - July 2024").
    Tier 2: "Batch YYYY" or "Passout YYYY" found elsewhere in resume clearly tied to this degree → infer with "~" prefix.
    Tier 3: absolutely zero date/year exists anywhere → store "".
- "education[].cgpa" = Apply 3-TIER DATE INFERENCE RULE for grade (Tier 1 only — NEVER infer grades).
    SCAN THE ENTIRE EDUCATION BLOCK for any grade/score pattern.
    Accepted formats: "7.0 GPA", "CGPA: 8.5", "8.5/10", "GPA: 3.9/4.0", "78.3%", "87%", "87.4 percent", "8.44".
    Store EXACTLY as written. NEVER convert percentage to CGPA or vice versa. NEVER relabel. Use "" if not present.
- "education[].bullets" = honors, distinctions, relevant coursework, or industrial training if mentioned. Use [] if none.

── CERTIFICATIONS ──
- "certifications[].name" = exact certification name as written.
- "certifications[].issuer" = issuing organization as written. Use "" if not present.
- "certifications[].duration" = Apply 3-TIER DATE INFERENCE RULE.
    SCAN THE ENTIRE CERTIFICATION BLOCK for any date near this certification.
    Accepted formats: "July 2025 – October 2025", "Oct 2024", "2023", month+year, date ranges.
    Tier 1: date found → store exactly as written (full range if present).
    Tier 2: certification is explicitly tied to a dated training/internship program → infer with "~" prefix.
    Tier 3: no date, no context → store "".

── ADDITIONAL ──
- "additional" items MUST use object format: {{"name":"","description":"","duration":""}}.
- "additional[].duration" = Apply 3-TIER DATE INFERENCE RULE. Use "" if no context exists.

RESUME TEXT:
\"\"\"{text[:8000]}\"\"\"
"""

    # ── Smart throttle: if only 1 admin key is healthy, give it breathing room ──
    try:
        from llm_manager import load_groq_api_keys, get_healthy_keys
        _all_keys = load_groq_api_keys()
        _healthy  = get_healthy_keys(_all_keys)
        if len(_healthy) <= 1:
            time.sleep(3)   # 3-second pause to let the per-minute window recover
    except Exception:
        pass

    raw_response = call_llm(prompt, session=st.session_state)

    # ── Parse the two sections out of the combined response ──────────────
    rewritten_text = ""
    json_str = ""

    rewrite_match = re.search(
        r"===REWRITTEN_RESUME_START===(.*?)===REWRITTEN_RESUME_END===",
        raw_response, re.DOTALL
    )
    json_match = re.search(
        r"===JSON_START===(.*?)===JSON_END===",
        raw_response, re.DOTALL
    )

    if rewrite_match:
        rewritten_text = rewrite_match.group(1).strip()
    else:
        # fallback: use everything before JSON block
        rewritten_text = raw_response.split("===JSON_START===")[0].strip()

    if json_match:
        json_str = json_match.group(1).strip()
    else:
        # fallback: try to extract JSON object from anywhere in the response
        json_fallback = re.search(r'\{[\s\S]*\}', raw_response)
        json_str = json_fallback.group(0).strip() if json_fallback else ""

    return rewritten_text, json_str


# ── Thin compatibility wrappers — keep callers working without changes ────────

def rewrite_text_with_llm(text, replacement_mapping, user_location):
    """Compatibility wrapper — calls merged rewrite_and_optimize_resume()."""
    rewritten_text, _ = rewrite_and_optimize_resume(text, replacement_mapping, user_location)
    return rewritten_text


def optimize_resume_to_json(raw_text: str) -> str:
    """Compatibility wrapper — calls merged rewrite_and_optimize_resume()."""
    _, json_str = rewrite_and_optimize_resume(raw_text, {}, "")
    return json_str


def _salvage_additional_str(s):
    """
    Extract name/description/duration from a leaked dict/JSON string.
    Handles JSON double-quoted, Python single-quoted, and mixed formats.
    Returns a clean dict or None.
    """
    import json as _j, re as _r
    if not s or not s.strip():
        return None
    s = s.strip()
    # Attempt 1: valid JSON double-quoted keys
    try:
        sub = _j.loads(s)
        if isinstance(sub, dict):
            n = str(sub.get("name", "") or "").strip()
            d = str(sub.get("description", "") or "").strip()
            r = str(sub.get("duration", "") or "").strip()
            if n or d:
                return {"name": n, "description": d, "duration": r}
    except Exception:
        pass
    # Attempt 2: replace single quotes -> double quotes and try JSON parse
    try:
        # Preserve escaped single quotes, swap bare ones to double quotes
        converted = s.replace("\\'", "\x01").replace("'", '"').replace("\x01", "\\'")
        sub = _j.loads(converted)
        if isinstance(sub, dict):
            n = str(sub.get("name", "") or "").strip()
            d = str(sub.get("description", "") or "").strip()
            r = str(sub.get("duration", "") or "").strip()
            if n or d:
                return {"name": n, "description": d, "duration": r}
    except Exception:
        pass
    # Attempt 3: brute-force regex — key can be single OR double quoted
    def _extract(key, text):
        for q in ('"', "'"):
            pat = q + key + q + r"\s*:\s*" + q + r"(.*?)" + q + r'(?=\s*,\s*[\'"{]|\s*\})'
            m = _r.search(pat, text, _r.DOTALL)
            if m:
                return m.group(1).strip()
        return ""
    n = _extract("name", s)
    d = _extract("description", s)
    r = _extract("duration", s)
    if n or d:
        return {"name": n, "description": d, "duration": r}
    return None



def extract_resume_json(llm_response: str) -> dict:
    """
    Safely extracts and parses JSON from LLM response.
    Handles markdown fences, leading/trailing text, and partial JSON.
    Returns a dict. Falls back to empty skeleton on any parse failure.
    """
    EMPTY = {
        "contact": {
            "name": "", "title": "", "email": "", "phone": "",
            "location": "", "linkedin": "", "github": "", "portfolio": ""
        },
        "summary": "",
        "skills": [],
        "soft_skills": [],
        "languages": [],
        "interests": [],
        "experience": [],
        "projects": [],
        "education": [],
        "certifications": [],
        "additional": [],
    }
    CONTACT_DEFAULTS = {
        "name": "", "title": "", "email": "", "phone": "",
        "location": "", "linkedin": "", "github": "", "portfolio": ""
    }
    if not llm_response:
        return EMPTY
    text = llm_response.strip()
    # Strip markdown fences
    text = re.sub(r'^```(?:json)?\s*', '', text, flags=re.IGNORECASE)
    text = re.sub(r'\s*```$', '', text)
    text = text.strip()
    # Find first { and last }
    start = text.find('{')
    end = text.rfind('}')
    if start == -1 or end == -1:
        return EMPTY
    text = text[start:end + 1]
    try:
        data = json.loads(text)
        # Ensure all top-level keys exist
        for key in EMPTY:
            if key not in data:
                data[key] = EMPTY[key]
        if not isinstance(data.get("contact"), dict):
            data["contact"] = CONTACT_DEFAULTS.copy()
        for field, default in CONTACT_DEFAULTS.items():
            if field not in data["contact"]:
                data["contact"][field] = default

        # ── Contact field rescue: fix all LLM inconsistencies ───────────────
        ct = data["contact"]

        # 1. Null/None/"null"/"undefined" → empty string for ALL contact fields
        for field in list(ct.keys()):
            v = ct[field]
            if v is None or str(v).strip() in ("null", "None", "undefined", "N/A", "n/a"):
                ct[field] = ""

        # 2. LLM put location/linkedin/github at top level instead of inside contact
        for top_key, contact_key in [
            ("location",  "location"),
            ("linkedin",  "linkedin"),
            ("github",    "github"),
            ("portfolio", "portfolio"),
            ("github_url","github"),
            ("linkedin_url","linkedin"),
            ("profile",   "linkedin"),
            ("website",   "portfolio"),
        ]:
            top_val = data.get(top_key, "") or ""
            if top_val and not ct.get(contact_key):
                ct[contact_key] = str(top_val).strip()

        # 3. LLM used alternate key names inside contact block
        ALT_KEYS = {
            "linkedin": ["linkedin_url", "linkedin_profile", "linkedin_profile_url",
                         "linkedIn", "linked_in", "profile_url", "profile"],
            "github":   ["github_url", "github_profile", "github_link",
                         "portfolio_url", "portfolio", "website", "repo"],
            "location": ["city", "address", "city_country", "current_location"],
        }
        for canonical, alts in ALT_KEYS.items():
            if not ct.get(canonical):
                for alt in alts:
                    v = ct.get(alt, "") or ""
                    if v and str(v).strip():
                        ct[canonical] = str(v).strip()
                        break

        # 4. Final null/empty cleanup — ensure every field is a string
        for field in CONTACT_DEFAULTS:
            if not isinstance(ct.get(field), str) or ct[field] is None:
                ct[field] = ""
        # Backfill missing experience fields
        _ZERO_EXP_PHRASES = re.compile(
            r'\b0\s*years?\s*(of\s*)?(experience|exp)?\b'
            r'|\bno\s+(work\s+)?experience\b'
            r'|\bN/?A\b'
            r'|\bnone\b',
            re.IGNORECASE,
        )
        for exp in data.get("experience", []):
            for f in ["role", "company", "duration", "description"]:
                if f not in exp:
                    exp[f] = ""
                # Scrub "0 years of experience" / "N/A" / "No experience" from any field
                if isinstance(exp[f], str) and _ZERO_EXP_PHRASES.search(exp[f]):
                    exp[f] = ""
            if "bullets" not in exp:
                exp["bullets"] = []
            # Scrub zero-exp phrases from bullets too
            exp["bullets"] = [
                b for b in exp["bullets"]
                if isinstance(b, str) and b.strip()
                and not _ZERO_EXP_PHRASES.search(b)
            ]
        # Drop experience entries that became entirely empty after scrubbing
        data["experience"] = [
            e for e in data.get("experience", [])
            if (e.get("role") and e["role"] not in ("", "[Not Provided]"))
            or (e.get("company") and e["company"] not in ("", "[Not Provided]"))
            or e.get("bullets")
        ]
        # Backfill missing project fields
        for proj in data.get("projects", []):
            for f in ["name", "duration", "tech_stack", "url", "description"]:
                if f not in proj:
                    proj[f] = ""
            if "bullets" not in proj:
                proj["bullets"] = []
        # Backfill missing education fields
        for edu in data.get("education", []):
            for f in ["degree", "institution", "year", "cgpa"]:
                if f not in edu:
                    edu[f] = ""
            if "bullets" not in edu:
                edu["bullets"] = []
        # Normalise additional — accept dicts, strings, or malformed objects
        raw_add = data.get("additional", [])
        norm_add = []
        for item in raw_add:
            if isinstance(item, dict):
                name = str(item.get("name", "") or "").strip()
                desc = str(item.get("description", "") or "").strip()
                dur  = str(item.get("duration", "") or "").strip()
                if not name and not desc:
                    continue
                norm_add.append({"name": name, "description": desc, "duration": dur})
            elif isinstance(item, str):
                s = item.strip()
                if not s or s in ("[Not Provided]",):
                    continue
                # If it looks like a leaked dict/JSON string, try to parse or salvage it
                if s.startswith("{") or ("name" in s and "description" in s):
                    salvaged = _salvage_additional_str(s)
                    if salvaged:
                        norm_add.append(salvaged)
                    # else discard entirely — do NOT render raw string
                else:
                    norm_add.append({"name": s, "description": "", "duration": ""})
        data["additional"] = norm_add

        # Normalise certifications — accept both flat strings and objects
        raw_certs = data.get("certifications", [])
        norm_certs = []
        for c in raw_certs:
            if isinstance(c, dict):
                norm_certs.append({
                    "name":     c.get("name", ""),
                    "issuer":   c.get("issuer", ""),
                    "duration": c.get("duration", ""),
                })
            elif isinstance(c, str) and c.strip():
                norm_certs.append({"name": c.strip(), "issuer": "", "duration": ""})
        data["certifications"] = norm_certs
        return data
    except (json.JSONDecodeError, ValueError):
        return EMPTY



def rewrite_and_highlight(text, replacement_mapping, user_location):
    highlighted_text = text
    masculine_count, feminine_count = 0, 0
    detected_masculine_words, detected_feminine_words = [], []
    matched_spans = []

    masculine_words = sorted(gender_words["masculine"], key=len, reverse=True)
    feminine_words = sorted(gender_words["feminine"], key=len, reverse=True)

    def span_overlaps(start, end):
        return any(s < end and e > start for s, e in matched_spans)

    # Highlight and count masculine words
    for word in masculine_words:
        pattern = re.compile(rf'\b{re.escape(word)}\b', re.IGNORECASE)
        for match in pattern.finditer(highlighted_text):
            start, end = match.span()
            if span_overlaps(start, end):
                continue

            word_match = match.group(0)
            colored = f"<span style='color:blue;'>{word_match}</span>"

            # Replace word in the highlighted text
            highlighted_text = highlighted_text[:start] + colored + highlighted_text[end:]
            shift = len(colored) - len(word_match)
            matched_spans = [(s if s < start else s + shift, e if s < start else e + shift) for s, e in matched_spans]
            matched_spans.append((start, start + len(colored)))

            masculine_count += 1

            # Get sentence context and highlight
            sentence_match = re.search(r'([^.]*?\b' + re.escape(word_match) + r'\b[^.]*\.)', text, re.IGNORECASE)
            if sentence_match:
                sentence = sentence_match.group(1).strip()
                colored_sentence = re.sub(
                    rf'\b({re.escape(word_match)})\b',
                    r"<span style='color:blue;'>\1</span>",
                    sentence,
                    flags=re.IGNORECASE
                )
                detected_masculine_words.append({
                    "word": word_match,
                    "sentence": colored_sentence
                })
            break  # Only one match per word

    # Highlight and count feminine words
    for word in feminine_words:
        pattern = re.compile(rf'\b{re.escape(word)}\b', re.IGNORECASE)
        for match in pattern.finditer(highlighted_text):
            start, end = match.span()
            if span_overlaps(start, end):
                continue

            word_match = match.group(0)
            colored = f"<span style='color:red;'>{word_match}</span>"

            # Replace word in the highlighted text
            highlighted_text = highlighted_text[:start] + colored + highlighted_text[end:]
            shift = len(colored) - len(word_match)
            matched_spans = [(s if s < start else s + shift, e if s < start else e + shift) for s, e in matched_spans]
            matched_spans.append((start, start + len(colored)))

            feminine_count += 1

            # Get sentence context and highlight
            sentence_match = re.search(r'([^.]*?\b' + re.escape(word_match) + r'\b[^.]*\.)', text, re.IGNORECASE)
            if sentence_match:
                sentence = sentence_match.group(1).strip()
                colored_sentence = re.sub(
                    rf'\b({re.escape(word_match)})\b',
                    r"<span style='color:red;'>\1</span>",
                    sentence,
                    flags=re.IGNORECASE
                )
                detected_feminine_words.append({
                    "word": word_match,
                    "sentence": colored_sentence
                })
            break  # Only one match per word

    # ⚡ Single LLM call — returns BOTH plain-text rewrite (for UI) AND JSON (for DOCX)
    # Replaces the old rewrite_text_with_llm call which discarded the JSON half.
    rewritten_text, json_str = rewrite_and_optimize_resume(
        text,
        replacement_mapping["masculine"] | replacement_mapping["feminine"],
        user_location
    )

    # Return json_str as 7th value so the caller can reuse it directly
    # without triggering a second optimize_resume_to_json() LLM call.
    return highlighted_text, rewritten_text, masculine_count, feminine_count, detected_masculine_words, detected_feminine_words, json_str

# ✅ Enhanced Grammar evaluation using LLM with suggestions
def get_grammar_score_with_llm(text, max_score=5):
    grammar_prompt = f"""
You are a senior HR language quality specialist and professional resume reviewer with 15+ years of experience evaluating resumes for Fortune 500 companies.

Analyze the following resume text across FIVE dimensions and provide an overall language quality score:

**EVALUATION DIMENSIONS:**
1. **Grammar & Mechanics** — Correct grammar, punctuation, subject-verb agreement, tense consistency
2. **Clarity & Conciseness** — Ideas expressed directly; no filler words or redundancy
3. **Professional Tone** — Appropriate formality, no informal slang or casual phrasing
4. **Action Verb Usage** — Starts bullet points with strong, quantifiable action verbs (e.g., "Led", "Engineered", "Reduced")
5. **ATS Language Alignment** — Industry-standard terminology, keyword density, no keyword stuffing

**SCORING SCALE (out of {max_score}):**
- {max_score}: Exceptional — Flawless grammar, powerful action verbs, crystal-clear and professional throughout
- {max_score-1}: Very Good — Minor stylistic issues; highly professional and readable
- {max_score-2}: Good — Some grammar or clarity issues but largely professional and effective
- {max_score-3}: Fair — Noticeable grammar, tone, or clarity problems that could affect readability
- {max_score-4}: Poor — Multiple errors affecting professional impression; needs significant editing
- 0-1: Very Poor — Significant language issues that would cause ATS rejection or recruiter dismissal

**IMPORTANT:** Be balanced — a technically competent resume with minor grammar issues should not be harshly penalized. Focus on overall professional impression.

Return EXACTLY in this format (no extra text):

Score: <number>
Feedback: <single sentence summarizing overall language quality and tone>
Suggestions:
- <Actionable suggestion 1 with example if helpful>
- <Actionable suggestion 2 with example if helpful>
- <Actionable suggestion 3 with example if helpful>
- <Actionable suggestion 4 with example if helpful>
- <Actionable suggestion 5 with example if helpful>

---
{text}
---
"""

    response = call_llm(grammar_prompt, session=st.session_state).strip()
    score_match = re.search(r"Score:\s*(\d+)", response)
    feedback_match = re.search(r"Feedback:\s*(.+)", response)
    suggestions = re.findall(r"- (.+)", response)

    score = int(score_match.group(1)) if score_match else max(0, min(max_score, max(3, max_score - 2)))  # Generous default, clamped to max_score
    feedback = feedback_match.group(1).strip() if feedback_match else "Language quality appears adequate for professional communication."
    return score, feedback, suggestions

# ✅ Main ATS Evaluation Function
def ats_percentage_score(
    resume_text,
    job_description,
    job_title="Unknown",
    logic_profile_score=None,
    edu_weight=20,
    exp_weight=35,
    skills_weight=30,
    lang_weight=5,
    keyword_weight=10,
    format_data=None,       # pass pre-computed format check result
    resume_domain=None,     # FIX: accept pre-detected domain from main thread
    job_domain=None,        # FIX: accept pre-detected domain from main thread
):
    import datetime

    _valid_domains = [
        "Data Science", "AI/Machine Learning", "UI/UX Design", "Mobile Development",
        "Frontend Development", "Backend Development", "Full Stack Development", "Cybersecurity",
        "Cloud Engineering", "DevOps/Infrastructure", "Quality Assurance", "Game Development",
        "Blockchain Development", "Embedded Systems", "System Architecture", "Database Management",
        "Networking", "Site Reliability Engineering", "Product Management", "Project Management",
        "Business Analysis", "Technical Writing", "Digital Marketing", "E-commerce", "Fintech",
        "Healthcare Tech", "EdTech", "IoT Development", "AR/VR Development", "Technical Sales",
        "Agile Coaching", "Software Engineering"
    ]
    _domain_list = ", ".join(_valid_domains)

    # FIX: use pre-detected value if passed in, only call LLM if not already set
    # When called from the parallel thread, resume_domain is set by the main thread
    # so no LLM call fires inside the thread (thread-safe).
    _resume_cache_key = f"resume_domain_{hash(resume_text[:500])}"
    if resume_domain is None and _resume_cache_key not in st.session_state:
        _resume_domain_prompt = f"""You are a senior technical recruiter with 15+ years of experience classifying candidate profiles across ALL levels and ALL industries — freshers, students, mid-level, senior professionals, non-tech roles, design, management, marketing, finance, healthcare, and more.

Your ONLY job: identify the candidate's PRIMARY professional domain from their resume text below.

════════════════════════════════════════════════════════
STEP 1 — DETERMINE CANDIDATE LEVEL
════════════════════════════════════════════════════════

LEVEL A — Pure Fresher / Student with NO specialization evidence:
  • Still studying OR just graduated with ONLY basic CS fundamentals listed (Java, C, C++, Python, HTML, SQL in isolation)
  • No internship OR only 1 internship with zero description of work done
  • Projects listed as bare names only — no tech stack, no description
  → DEFAULT to "Software Engineering". Do not over-classify.
  → EXAMPLE: Only Java + MySQL + DBMS skills, no projects described → "Software Engineering"

LEVEL B — Fresher / Student WITH at least ONE specialization signal:
  • Has at least one of:
    - 1 internship with a described role or technology stack
    - 1 project with a description mentioning domain-specific technologies
    - Skills showing a clear non-trivial technology stack beyond basic CS
  → Classify into the MOST EVIDENCED specific domain using STEP 2 rules

LEVEL C — Experienced Professional (1+ years full-time work):
  → ALWAYS classify into a specific domain. Use job titles + tech stack + years as primary signals.
  → Only fall back to "Software Engineering" if domain is genuinely mixed with no clear winner.

════════════════════════════════════════════════════════
STEP 2 — DOMAIN CLASSIFICATION RULES
════════════════════════════════════════════════════════

RULE A — NEVER over-classify from basic skills alone:
  ✗ Java + MySQL alone → NOT "Backend Development"
  ✗ HTML + CSS alone → NOT "Frontend Development"
  ✗ Python alone → NOT "AI/Machine Learning" or "Data Science"
  ✗ SQL alone → NOT "Database Management"
  ✗ C / C++ alone → NOT "Embedded Systems"
  ✓ Basic CS languages + no described projects/frameworks → "Software Engineering"

RULE B — TRUE EVIDENCE BAR per domain (must satisfy BOTH sub-conditions):

  → Frontend Development:
     MUST have: HTML+CSS+JS PLUS one of (React/Vue/Angular/Bootstrap/jQuery/Svelte/Next.js)
     AND: at least 1 described project or internship explicitly about web UI / frontend

  → Backend Development:
     MUST have: A backend framework (Django/Flask/Spring Boot/Laravel/Express/Node.js/FastAPI/NestJS/Rails)
     AND: database integration described in a project or internship
     ⚠ "website" or "web application" in project name does NOT imply Full Stack.
     Django + database + "Travel Management website" with NO frontend tech mentioned = Backend Development.
     Only classify as Full Stack if HTML/CSS/JS or a frontend framework is EXPLICITLY mentioned.

  → Full Stack Development:
     MUST have: frontend technologies (HTML+CSS+JS or React/Vue/Angular/Bootstrap/jQuery/Svelte/Next.js)
     AND: backend framework (Django/Flask/Spring Boot/Laravel/Express/Node.js/FastAPI)
     AND: database — ALL THREE explicitly present in the same project or internship description
     OR: candidate explicitly self-identifies as "full stack" / "front-end and back-end" in summary/title
     ⚠ "website" + backend framework alone is NOT Full Stack — frontend tech must be named explicitly.

  → Mobile Development:
     MUST have: Android/iOS/Flutter/React Native/Kotlin/Swift/Xamarin
     AND: at least 1 described mobile app project or internship

  → Data Science:
     MUST have: pandas/numpy/matplotlib/seaborn/Tableau/Power BI/Looker/R/SPSS/Excel analytics
     AND: actual data analysis, reporting, or visualization project described
     NOT: SQL or Excel listed as a lone skill with no analytical work described

  → AI/Machine Learning:
     MUST have: TensorFlow/PyTorch/scikit-learn/Keras/HuggingFace/OpenAI/LangChain/NLP/Computer Vision/LLM
     AND: model training, fine-tuning, or ML pipeline described in a project

  → Cybersecurity:
     MUST have: security tools (Kali Linux/Burp Suite/Wireshark/Metasploit/Nmap) OR concepts (pentesting/OWASP/CTF/ethical hacking/SOC)
     AND: security internship or project described
     NOTE: "Cybersecurity virtual internship" with no tools/work described = weak signal only

  → DevOps/Infrastructure:
     MUST have: Docker/Kubernetes/CI-CD/Jenkins/Terraform/Ansible/Helm/ArgoCD
     AND: deployment, pipeline, or infrastructure project described

  → Cloud Engineering:
     MUST have: specific AWS/Azure/GCP service names (not just the word "cloud")
     AND: cloud deployment or architecture described in a project or role

  → UI/UX Design:
     MUST have: Figma/Adobe XD/Sketch/InVision/Framer/Zeplin
     AND: wireframes, prototypes, or user research described

  → Database Management:
     MUST have: DBA title OR database optimization/administration/replication/tuning as PRIMARY focus
     NOT: SQL listed as one skill among many

  → Quality Assurance:
     MUST have: testing frameworks (Selenium/Cypress/JUnit/pytest/Postman/JMeter/Appium) OR QA role title
     AND: test planning, test cases, or automation described

  → Game Development:
     MUST have: Unity/Unreal Engine/Godot/game mechanics/shader programming
     AND: at least 1 described game project

  → Blockchain Development:
     MUST have: Solidity/Web3/Smart Contracts/Ethereum/DeFi/NFT/Hardhat/Truffle
     AND: blockchain project described

  → Embedded Systems:
     MUST have: microcontroller/RTOS/firmware/Arduino/STM32/ESP32/ARM/assembly/hardware programming
     AND: hardware or embedded project described

  → IoT Development:
     MUST have: IoT devices/sensors/MQTT/CoAP/Raspberry Pi in IoT context/hardware integration
     AND: IoT project or deployment described

  → AR/VR Development:
     MUST have: ARKit/ARCore/Unity3D VR/Unreal VR/Oculus/HoloLens/WebXR
     AND: AR/VR project described

  → System Architecture:
     MUST have: architect-level title (Solution Architect/Enterprise Architect/System Architect) OR
     explicit work on distributed systems design, microservices architecture, system design

  → Networking:
     MUST have: network engineer/admin title OR Cisco/routing/switching/BGP/OSPF/VPN/network protocols
     AND: network configuration or administration work described

  → Site Reliability Engineering:
     MUST have: SRE title OR SLI/SLO/error budgets/on-call/toil reduction
     AND: reliability engineering work described

  → Product Management:
     MUST have: product ownership, roadmaps, PRDs, stakeholder management, feature prioritization
     NOT: just Agile/Scrum keywords

  → Project Management:
     MUST have: managing teams/timelines/deliverables, PMP/Prince2/program manager experience
     NOT: just "worked in agile team"

  → Business Analysis:
     MUST have: requirements gathering, process mapping, BRD/FRD writing, stakeholder analysis
     AND: BA role or described BA work

  → Digital Marketing:
     MUST have: SEO/SEM/PPC/social media campaigns/content marketing/Google Ads/Meta Ads
     AND: actual marketing work or results described

  → Technical Writing:
     MUST have: documentation, API docs, user manuals, technical communication as PRIMARY work
     AND: writing samples, tools (Confluence/GitBook/Sphinx) or writing role described

  → E-commerce:
     MUST have: Shopify/Magento/WooCommerce/marketplace/order management/product catalog
     AND: e-commerce work described

  → Fintech:
     MUST have: payment processing/banking software/trading systems/KYC/AML/financial technology
     AND: fintech role or project described

  → Healthcare Tech:
     MUST have: EHR/EMR/HIPAA/telemedicine/medical software/healthcare data/clinical systems
     AND: healthcare context described

  → EdTech:
     MUST have: e-learning/LMS/educational platform/curriculum technology/learning analytics
     AND: education tech context described

  → Technical Sales:
     MUST have: sales engineer/pre-sales/solution selling/demo/RFP/customer technical support
     AND: sales engineering role described

  → Agile Coaching:
     MUST have: Scrum Master/Agile Coach/SAFe/team facilitation/sprint ceremonies as PRIMARY role
     NOT: just "worked in agile" or "familiar with scrum"

RULE C — MIXED SIGNALS → dominant domain wins:
  • Count evidence per domain: (tech keywords in described work) + (project descriptions) + (job/internship titles)
  • Domain with MOST evidence wins
  • Tie between frontend+backend → "Full Stack Development"
  • Tie between unrelated domains → "Software Engineering"
  • 1 weak signal (e.g. 1 virtual internship, no described work) vs 3 strong signals → strong side wins
  ⚠ INTERNSHIP TITLE CONFLICT RULE (critical for Level B):
    If internship title suggests Domain A BUT skills + projects have 3+ strong signals for Domain B
    AND Domain B is more specific than Domain A → Domain B wins over the internship title.
    EXAMPLE: "Full Stack Developer Intern" + LangChain/LLaMA/RAG/FAISS/LLMs in skills+projects
             → "AI/Machine Learning" wins, NOT "Full Stack Development"
    EXAMPLE: "Full Stack Developer Intern" + only HTML/CSS/React/Node projects, no AI tools
             → "Full Stack Development" wins correctly
    EXAMPLE: "Android Developer Intern" + Flutter/Kotlin projects → "Mobile Development" wins correctly

RULE D — NON-TECH / HYBRID profiles:
  • Pure non-tech background (marketing, finance, HR, design) + no tech projects → classify by their actual domain
  • Career switcher: old domain + new tech projects/certs → classify by NEW tech domain if evidence is substantial

RULE E — RESEARCH / ACADEMIC profiles:
  • Research at university/NIT/IIT/ISRO/DRDO/labs → classify by RESEARCH TOPIC
  • AI/NLP/CV research → "AI/Machine Learning"
  • Security research → "Cybersecurity"
  • Hardware/systems research → "Embedded Systems"
  • Generic CS research → "Software Engineering"

RULE F — JOB TITLE as strong signal (Level C only):
  • ONLY applies to Level C (1+ years full-time work experience)
  • For Level C: explicit job title is the STRONGEST single signal
  • "Backend Developer" title → "Backend Development"
  • "Data Analyst" title → "Data Science"
  • "QA Engineer" title → "Quality Assurance"
  • Title + matching tech stack → confirm that domain immediately
  ⚠ For Level B (freshers/students): internship title is ONE signal among many.
    It can be OVERRIDDEN if skills + projects show 3+ strong signals for a different domain.
    Do NOT blindly use internship title for Level B — apply Rule C conflict check first.

════════════════════════════════════════════════════════
STEP 3 — TIEBREAKERS (apply in order)
════════════════════════════════════════════════════════

T1. If self-identified domain in summary/objective → use that domain (if it exists in the valid list)
T2. If internship title names a domain AND no conflict with Rule C → use that domain
    ⚠ If conflict exists (skills+projects strongly point elsewhere) → skip T2, go to T3
T3. If tech stack strongly maps to exactly 1 domain → use that domain
T4. If still tied → "Software Engineering" as safe fallback

════════════════════════════════════════════════════════
STEP 4 — FINAL SANITY CHECK
════════════════════════════════════════════════════════

Before answering, verify:
1. Did I correctly determine the level (A/B/C)?
2. If Level A → am I returning "Software Engineering"? (If not, reconsider)
3. Does my chosen domain meet the TRUE EVIDENCE BAR from Rule B?
4. For Full Stack: are frontend tech + backend framework + database ALL explicitly mentioned? If any is missing → not Full Stack.
5. If Level B: did I check Rule C conflict? Is the internship title conflicting with skills+projects?
   If yes → did I correctly let skills+projects override the internship title?
6. If Level C: is there a job title that confirms my domain (Rule F)?
7. Is this the domain with the MOST evidence overall?

════════════════════════════════════════════════════════
Resume Text:
{resume_text[:2500]}
════════════════════════════════════════════════════════

Return ONLY one domain from this list, nothing else:
{_domain_list}
"""
        try:
            _r = call_llm(_resume_domain_prompt, session=st.session_state).strip()
            if _r in _valid_domains:
                st.session_state[_resume_cache_key] = _r
            else:
                # LLM returned invalid domain — fall back to keyword detection
                _kw_fallback = db_manager.detect_domain_from_title_and_description("", resume_text[:3000])
                st.session_state[_resume_cache_key] = _kw_fallback if _kw_fallback != "Unclassified" else "Software Engineering"
        except Exception:
            # LLM failed entirely — fall back to keyword detection
            try:
                _kw_fallback = db_manager.detect_domain_from_title_and_description("", resume_text[:3000])
                st.session_state[_resume_cache_key] = _kw_fallback if _kw_fallback != "Unclassified" else "Software Engineering"
            except Exception:
                st.session_state[_resume_cache_key] = "Software Engineering"

    # Use passed-in value if provided, otherwise use session state value
    if resume_domain is None:
        resume_domain = st.session_state.get(_resume_cache_key, "Software Engineering")

    # ── JOB DOMAIN: use pre-detected value if passed in, else detect here ──
    _jd_cache_key = f"jd_domain_{hash(job_description[:500])}"
    if job_domain is None and _jd_cache_key not in st.session_state:
        _jd_domain_prompt = f"""You are an expert technical recruiter with 15+ years of experience classifying job descriptions across all industries and levels.

Your ONLY job: identify the PRIMARY professional domain this job description is hiring for.

════════════════════════════════════════════════════════
STEP 1 — READ THE JOB TITLE FIRST (strongest signal)
════════════════════════════════════════════════════════

Job Title: {job_title}

If the job title EXPLICITLY names a domain (e.g. "Backend Developer", "Data Scientist", "DevOps Engineer", "UX Designer"), use that domain directly — do not over-analyse the description.

Title override examples:
  "Backend Developer" → "Backend Development"
  "Data Analyst" → "Data Science"
  "ML Engineer" / "AI Engineer" → "AI/Machine Learning"
  "DevOps Engineer" / "Platform Engineer" → "DevOps/Infrastructure"
  "Cloud Architect" / "Cloud Engineer" → "Cloud Engineering"
  "QA Engineer" / "SDET" / "Test Engineer" → "Quality Assurance"
  "Mobile Developer" / "Android" / "iOS" / "Flutter" → "Mobile Development"
  "Full Stack Developer" → "Full Stack Development"
  "Frontend Developer" / "Front End" → "Frontend Development"
  "UX Designer" / "UI Designer" / "Product Designer" → "UI/UX Design"
  "Security Engineer" / "Security Analyst" / "Penetration Tester" → "Cybersecurity"
  "SRE" / "Site Reliability Engineer" → "Site Reliability Engineering"
  "Blockchain Developer" / "Web3 Developer" → "Blockchain Development"
  "Game Developer" / "Game Engineer" → "Game Development"
  "Embedded Engineer" / "Firmware Engineer" → "Embedded Systems"
  "IoT Engineer" → "IoT Development"
  "Network Engineer" / "Network Admin" → "Networking"
  "Database Administrator" / "DBA" → "Database Management"
  "Product Manager" → "Product Management"
  "Project Manager" / "Program Manager" → "Project Management"
  "Business Analyst" → "Business Analysis"
  "Scrum Master" / "Agile Coach" → "Agile Coaching"
  "Technical Writer" → "Technical Writing"
  "Sales Engineer" / "Pre-Sales" → "Technical Sales"
  "Solution Architect" / "Enterprise Architect" → "System Architecture"

════════════════════════════════════════════════════════
STEP 2 — IF TITLE IS AMBIGUOUS, ANALYSE THE JD BELOW
════════════════════════════════════════════════════════

Job Description:
{job_description[:2000]}

Classification rules:
  • Backend: Node.js/Django/Spring Boot/FastAPI + database + API work
  • Frontend: React/Vue/Angular/HTML+CSS+JS + UI work
  • Full Stack: Both frontend AND backend tech explicitly required
  • Data Science: SQL/Python analytics + pandas/numpy/Tableau/Power BI + analysis work
  • AI/ML: TensorFlow/PyTorch/scikit-learn/LLM/NLP/model training required
  • DevOps: Docker/Kubernetes/CI-CD/Terraform/Jenkins required
  • Cloud: AWS/Azure/GCP services explicitly required (not just "cloud" mentioned)
  • Cybersecurity: pentesting/OWASP/SIEM/SOC/security tools required
  • Mobile: Android/iOS/Flutter/React Native explicitly required
  • UI/UX: Figma/wireframes/prototyping/user research required
  • Product Management: roadmap/PRD/stakeholder management (not just Agile)
  • Project Management: team delivery/PMP/programme management
  • Business Analysis: requirements/BRD/process mapping as primary duty
  • Quality Assurance: test automation/test planning as primary duty
  • Fintech: payment/banking/trading/KYC/AML systems
  • Healthcare Tech: EHR/EMR/HIPAA/clinical systems
  • EdTech: LMS/e-learning/educational platform
  • Game Development: Unity/Unreal/game mechanics explicitly required
  • Blockchain: Solidity/Web3/smart contracts explicitly required
  • Embedded: firmware/RTOS/microcontroller/hardware explicitly required

════════════════════════════════════════════════════════
STEP 3 — FINAL CHECK
════════════════════════════════════════════════════════

1. Did the job title directly name a domain? → Use that.
2. If not, which domain has the MOST required skills/responsibilities in the JD?
3. If truly unclear → "Software Engineering"

Return ONLY one domain from this list, nothing else:
{_domain_list}
"""
        try:
            _j = call_llm(_jd_domain_prompt, session=st.session_state).strip()
            if _j in _valid_domains:
                st.session_state[_jd_cache_key] = _j
            else:
                # LLM returned invalid — fall back to keyword detection
                _jd_kw = db_manager.detect_domain_from_title_and_description(job_title, job_description[:3000])
                st.session_state[_jd_cache_key] = _jd_kw if _jd_kw != "Unclassified" else "Software Engineering"
        except Exception:
            # LLM failed — fall back to keyword detection
            try:
                _jd_kw = db_manager.detect_domain_from_title_and_description(job_title, job_description[:3000])
                st.session_state[_jd_cache_key] = _jd_kw if _jd_kw != "Unclassified" else "Software Engineering"
            except Exception:
                st.session_state[_jd_cache_key] = "Software Engineering"

    # Use passed-in value if provided, otherwise use session state value
    if job_domain is None:
        job_domain = st.session_state.get(_jd_cache_key, "Software Engineering")

    similarity_score = get_domain_similarity(resume_domain, job_domain)

    # Grammar defaults — overwritten by values parsed from the ATS prompt response below
    grammar_score       = 0          # stays 0 if LLM section fails to parse — no phantom score
    grammar_feedback    = "Language quality appears adequate for professional communication."
    grammar_suggestions = []

    # ✅ Balanced domain penalty
    MAX_DOMAIN_PENALTY = 15
    domain_penalty = round((1 - similarity_score) * MAX_DOMAIN_PENALTY)

    # ✅ Optional profile score note
    logic_score_note = (
        f"\n\nOptional Note: The system also calculated a logic-based profile score of {logic_profile_score}/100 "
        f"based on resume length, experience, and skills."
        if logic_profile_score else ""
    )

    # ✅ FIXED: Stable education scoring with 2025 cutoff
    current_year = datetime.datetime.now().year

    current_month = datetime.datetime.now().month

    # ✅ UPDATED: Stable education scoring with priority degrees minimum
    prompt = f"""
You are a senior ATS (Applicant Tracking System) Evaluator and Technical Recruiter with 15+ years of experience at top-tier tech firms.
Your evaluation must be rigorous, consistent, evidence-based, and match industry-standard hiring benchmarks.

You specialize in: AI/ML, Blockchain, Cloud Computing, Data Engineering, Software Development, DevOps, and Cybersecurity roles.

═══════════════════════════════════════════════════
🎯 EVALUATION PHILOSOPHY
═══════════════════════════════════════════════════
- Score based on EVIDENCE found in the resume — not assumptions
- Reward quantified achievements (numbers, percentages, scale)
- Credit projects, GitHub, hackathons, Kaggle, open-source contributions, certifications
- Penalize vague claims without evidence ("good communication skills")
- Recognize career stage: entry-level vs senior vs lead
- Prioritize recency: skills/experience from the last 3 years matter most
- Be encouraging but calibrated: do not inflate scores without evidence

═══════════════════════════════════════════════════
📐 SCORING FRAMEWORK
═══════════════════════════════════════════════════

**🎓 Education Score ({edu_weight} points max):**

PRIORITY RULE — Minimum {int(edu_weight * 0.75)} pts for these degrees (completed OR pursuing):
  • BSc/MSc Computer Science or Mathematics
  • MCA (Master of Computer Applications)  
  • BE/BTech Computer Science or IT
  • BCA + MCA combination

DATE PARSING (STRICT — Non-negotiable):
  • End year < 2025 → ✅ COMPLETED (hardcoded cutoff)
  • End year = 2025 → ✅ COMPLETED
  • End year > 2025 → 🔄 ONGOING
  • Keywords "pursuing", "in progress", "currently enrolled" → 🔄 ONGOING
  • Keywords "graduated", "completed", "finished" → ✅ COMPLETED
  • If end year < 2025, ALWAYS mark completed regardless of text

Scoring bands:
  • {int(edu_weight * 0.90)}–{edu_weight}: Outstanding — completed highly relevant degree + exceptional academic record
  • {int(edu_weight * 0.75)}–{int(edu_weight * 0.85)}: Excellent — priority degree (completed or ongoing), good standing
  • {int(edu_weight * 0.60)}–{int(edu_weight * 0.70)}: Very Good — related STEM/technical degree
  • {int(edu_weight * 0.45)}–{int(edu_weight * 0.55)}: Good — partially related degree with transferable foundation
  • {int(edu_weight * 0.30)}–{int(edu_weight * 0.40)}: Fair — unrelated degree with relevant self-learning evidence
  • {int(edu_weight * 0.15)}–{int(edu_weight * 0.25)}: Basic — minimal or no degree information
  • 0–{int(edu_weight * 0.10)}: Insufficient — no education details at all

**💼 Experience Score ({exp_weight} points max):**

Evaluate: years of relevant experience, role seniority, domain fit, impact, leadership, quantification.

  • {int(exp_weight * 0.91)}–{exp_weight}: Exceptional — exceeds requirements; strong leadership; quantified high-impact results
  • {int(exp_weight * 0.80)}–{int(exp_weight * 0.89)}: Excellent — meets/exceeds years; strong domain fit; clear achievements
  • {int(exp_weight * 0.69)}–{int(exp_weight * 0.77)}: Very Good — adequate years; good domain fit; solid responsibilities
  • {int(exp_weight * 0.57)}–{int(exp_weight * 0.66)}: Good — reasonable experience; relevant domain; some achievements
  • {int(exp_weight * 0.43)}–{int(exp_weight * 0.54)}: Fair — some gaps but shows clear potential and transferable skills
  • {int(exp_weight * 0.29)}–{int(exp_weight * 0.40)}: Basic — limited experience but relevant direction shown
  • {int(exp_weight * 0.14)}–{int(exp_weight * 0.26)}: Entry Level — minimal experience; strong potential only
  • 0–{int(exp_weight * 0.11)}: Insufficient — major gaps; no transferable evidence

NOTE: Internships, freelance projects, and open-source contributions count as valid experience.

**🛠️ Skills Score ({skills_weight} points max):**

Match each listed skill against job description requirements. Reward:
  • Hard skills: programming languages, frameworks, tools, platforms
  • Certifications: AWS, GCP, Azure, Kubernetes, Terraform, etc.
  • Emerging skills: LLMs, GenAI, Vector DBs, Web3, MLOps, DeFi, Smart Contracts

  • {int(skills_weight * 0.93)}–{skills_weight}: Outstanding — 90%+ required skills; expert proficiency; recent hands-on usage
  • {int(skills_weight * 0.80)}–{int(skills_weight * 0.90)}: Excellent — 80%+ required skills; advanced proficiency
  • {int(skills_weight * 0.67)}–{int(skills_weight * 0.77)}: Very Good — 70%+ required skills; competent usage
  • {int(skills_weight * 0.53)}–{int(skills_weight * 0.63)}: Good — 60%+ required skills; working knowledge
  • {int(skills_weight * 0.40)}–{int(skills_weight * 0.50)}: Fair — 50%+ skills OR strong foundational skills
  • {int(skills_weight * 0.27)}–{int(skills_weight * 0.37)}: Basic — 40%+ skills; clear learning trajectory
  • {int(skills_weight * 0.13)}–{int(skills_weight * 0.23)}: Limited — 30%+ skills; self-learning evident
  • 0–{int(skills_weight * 0.10)}: Insufficient — fewer than 30% required skills

**🔑 Keyword Score ({keyword_weight} points max):**

Systematically extract ALL critical terms from the job description:
technical tools, frameworks, methodologies, role titles, industry terms, certification names.
Compare against resume. Credit synonyms and equivalent terms.

  • {int(keyword_weight * 0.90)}–{keyword_weight}: Excellent — 85%+ critical terms; strong industry vocabulary
  • {int(keyword_weight * 0.80)}: Very Good — 75%+ critical terms
  • {int(keyword_weight * 0.60)}–{int(keyword_weight * 0.70)}: Good — 65%+ critical terms
  • {int(keyword_weight * 0.40)}–{int(keyword_weight * 0.50)}: Fair — 50%+ critical terms
  • {int(keyword_weight * 0.20)}–{int(keyword_weight * 0.30)}: Basic — 35%+ critical terms
  • {int(keyword_weight * 0.10)}: Limited — 20%+ critical terms
  • 0: Poor — fewer than 20% critical terms

═══════════════════════════════════════════════════
📋 REQUIRED OUTPUT FORMAT
═══════════════════════════════════════════════════

Follow this EXACT structure. Do not skip any section:

### 🏷️ Candidate Name
<Copy the candidate's full name EXACTLY as it appears in the resume — character by character. Do NOT correct spelling, do NOT infer from context, do NOT paraphrase. Look at the very top of the resume (header/contact section). Output ONLY the name, nothing else. If you cannot find a name, write: Not Found>

### 🏫 Education Analysis
**Score:** <0–{edu_weight}> / {edu_weight}

**Scoring Rationale:**
- Degree Level & Relevance: <Does it qualify for minimum {int(edu_weight * 0.75)}-pt rule? Which degree?>
- Completion Status: <Apply strict 2025 cutoff rule; state year and final status>
- Academic Quality Indicators: <GPA, honors, relevant coursework if mentioned>
- **Score Justification:** <Explain exact score with evidence from resume>

### 💼 Experience Analysis
**Score:** <0–{exp_weight}> / {exp_weight}

**Experience Breakdown:**
- Total Years of Relevant Experience: <X years — include internships, freelance, open-source>
- Role Progression & Seniority: <Entry → Mid → Senior trajectory>
- Domain Alignment: <How well does background match job domain?>
- Quantified Achievements: <List metrics found: % improvement, $ savings, users served, etc.>
- Leadership & Ownership Evidence: <Managed teams? Led projects? Mentored?>
- Technology Currency: <Are skills/tools recent and relevant (last 3 years)?>
- **Score Justification:** <Explain score with specific resume evidence>

### 🛠 Skills Analysis
**Score:** <0–{skills_weight}> / {skills_weight}

**Skills Assessment:**
- Core Technical Skills Matched: <List matched skills with evidence>
- Emerging/Cutting-Edge Skills: <LLMs, GenAI, Web3, MLOps, Cloud, etc.>
- Certifications Detected: <List any certifications found>
- Soft Skills with Evidence: <Only count if backed by concrete examples>
- Proficiency Depth: <Surface knowledge vs. demonstrated project usage>

**Skills Gaps (Development Opportunities):**
- <Gap 1 — specific missing skill from job description>
- <Gap 2 — specific missing skill>
- <Gap 3 — specific missing skill>
- <Gap 4 — specific missing skill>
- <Gap 5 — specific missing skill>

**Score Justification:** <Explain with matched vs. required skills ratio>

### 🗣 Language Quality Analysis
**Score:** <evaluate and provide a score 0–{lang_weight}> / {lang_weight}
**Grammar & Professional Tone:** <single sentence summarising overall language quality>
**Suggestions:**
- <Actionable suggestion 1>
- <Actionable suggestion 2>
- <Actionable suggestion 3>
- <Actionable suggestion 4>
- <Actionable suggestion 5>
**Assessment:** <Specific feedback on action verb usage, clarity, tense consistency, and ATS language>

SCORING SCALE for language ({lang_weight} pts max):
- {lang_weight}: Exceptional — Flawless grammar, powerful action verbs, crystal-clear and professional throughout
- {lang_weight-1}: Very Good — Minor stylistic issues; highly professional and readable
- {lang_weight-2}: Good — Some grammar or clarity issues but largely professional
- {lang_weight-3}: Fair — Noticeable grammar or clarity problems
- 0-1: Poor — Significant language issues

### 🔑 Keyword Analysis
**Score:** <0–{keyword_weight}> / {keyword_weight}

**Keyword Assessment:**
- Industry Terminology Match: <Percentage and specific matches found>
- Role-Specific Keywords Present: <List matched keywords>
- Technical Vocabulary: <Tools, frameworks, platforms found in both>
- Keyword Density Quality: <Natural integration vs. stuffing>

**Keyword Enhancement Opportunities:**
- <Critical keyword 1 from job description — not in resume>
- <Critical keyword 2>
- <Critical keyword 3>
- <Critical keyword 4>
- <Critical keyword 5>
- <Critical keyword 6>
- <Critical keyword 7>
- <Critical keyword 8>

**Score Justification:** <Evidence-based explanation>

### 📐 Format & ATS Compatibility Analysis
**Format Score:** {format_data.get("format_score", "N/A") if format_data else "N/A"} / 100  
**Format Grade:** {format_data.get("letter_grade", "N/A") if format_data else "N/A"} — {format_data.get("label", "") if format_data else ""}

⚠️ IMPORTANT: The Format Score and Format Grade above are SYSTEM-COMPUTED and LOCKED. Do NOT change these numbers. Only fill in the narrative fields below.

**Structural Assessment:**
- Section Completeness: <narrative only — do NOT include a score>
- Contact Block: <narrative only>
- Resume Length: {f"{format_data.get('word_count', 'N/A')} words — " + ("Optimal" if 300 <= (format_data.get('word_count') or 0) <= 1000 else "Too short" if (format_data.get('word_count') or 0) < 300 else "Too long") if format_data else "N/A"}
- Action Verb Strength: <narrative only>
- Quantification Quality: <narrative only>
- ATS Red Flags: <narrative only>

**Format Issues Detected:**
{chr(10).join(f"- {issue}" for issue in (format_data.get("issues", []) or ["No issues detected"])) if format_data else "- Format data not available"}

**Format Strengths:**
{chr(10).join(f"- {p}" for p in (format_data.get("passes", []) or ["No specific passes noted"])) if format_data else "- Format data not available"}

**Improvement Recommendations:**
- <Top format fix 1 — specific and actionable>
- <Top format fix 2>
- <Top format fix 3>

### ✅ Final Assessment

**Overall Evaluation:**
<5–7 sentences covering: candidate's unique value proposition, strongest evidence-backed qualifications, key gaps, culture/team fit signals, and a clear hire/interview recommendation>

**Top 3 Strengths (with evidence):**
1. <Strength 1 — backed by resume evidence>
2. <Strength 2 — backed by resume evidence>
3. <Strength 3 — backed by resume evidence>

**Top 3 Development Areas:**
1. <Gap 1 framed as a growth opportunity>
2. <Gap 2 framed as a growth opportunity>
3. <Gap 3 framed as a growth opportunity>

**Hiring Recommendation:** <Strongly Recommend / Recommend / Recommend with Reservations / Do Not Recommend> — <2-sentence reasoning>

---

**EVALUATION CONTEXT:**
- Current Date: {datetime.datetime.now().strftime('%B %Y')} (Year: {current_year}, Month: {current_month})
- Resume Domain Detected: {resume_domain}
- Target Job Domain: {job_domain}
- Domain Similarity Score: {similarity_score:.2f}/1.0
- Domain Mismatch Penalty Applied: {domain_penalty}/{MAX_DOMAIN_PENALTY} pts

---

📄 **JOB DESCRIPTION:**
{job_description[:4000]}

📄 **RESUME TEXT:**
{resume_text[:5000]}

{logic_score_note}
"""
   
   
    ats_result = call_llm(prompt, session=st.session_state).strip()

    # ── CRITICAL: Overwrite any LLM-modified Format Score/Grade lines ────
    # The LLM sometimes rewrites these despite instructions. Force the true
    # system-computed values back in so UI and narrative always match.
    _true_fmt_score = format_data.get("format_score", 75) if format_data else 75
    _true_fmt_grade = format_data.get("letter_grade", "N/A") if format_data else "N/A"
    _true_fmt_label = format_data.get("label", "") if format_data else ""

    ats_result = re.sub(
        r'\*\*Format Score:\*\*.*',
        f'**Format Score:** {_true_fmt_score} / 100',
        ats_result
    )
    ats_result = re.sub(
        r'\*\*Format Grade:\*\*.*',
        f'**Format Grade:** {_true_fmt_grade} — {_true_fmt_label}',
        ats_result
    )
    # ─────────────────────────────────────────────────────────────────────

    def extract_section(pattern, text, default="N/A"):
        match = re.search(pattern, text, re.DOTALL)
        return match.group(1).strip() if match else default

    def extract_score(pattern, text, default=0):
        match = re.search(pattern, text)
        return int(match.group(1)) if match else default

    # Extract key sections
    _raw_name = extract_section(r"### 🏷️ Candidate Name(.*?)###", ats_result, "")
    candidate_name = re.sub(r"[*_`#\[\]<>]", "", _raw_name).strip()
    candidate_name = " ".join(candidate_name.split())
    _placeholder_values = {
        "not found", "n/a", "unknown", "none", "",
        "extract full name from resume header or contact section",
        "copy the candidate's full name exactly as it appears in the resume",
        "copy the candidates full name exactly as it appears in the resume",
        "name not found", "candidate name not found",
    }
    if candidate_name.lower() in _placeholder_values:
        candidate_name = "Not Found"
    edu_analysis = extract_section(r"### 🏫 Education Analysis(.*?)###", ats_result)
    exp_analysis = extract_section(r"### 💼 Experience Analysis(.*?)###", ats_result)
    skills_analysis = extract_section(r"### 🛠 Skills Analysis(.*?)###", ats_result)
    lang_analysis = extract_section(r"### 🗣 Language Quality Analysis(.*?)###", ats_result)
    keyword_analysis = extract_section(r"### 🔑 Keyword Analysis(.*?)###", ats_result)
    format_analysis = extract_section(r"### 📐 Format & ATS Compatibility Analysis(.*?)###", ats_result)
    final_thoughts = extract_section(r"### ✅ Final Assessment(.*)", ats_result)

    # Extract scores with improved patterns (LLM now scores directly using sidebar weights)
    edu_score     = extract_score(r"\*\*Score:\*\*\s*(\d+)", edu_analysis)
    exp_score     = extract_score(r"\*\*Score:\*\*\s*(\d+)", exp_analysis)
    skills_score  = extract_score(r"\*\*Score:\*\*\s*(\d+)", skills_analysis)
    keyword_score = extract_score(r"\*\*Score:\*\*\s*(\d+)", keyword_analysis)
    # ⚡ Parse grammar score + feedback from ATS result (no separate LLM call needed)
    _grammar_score_match    = re.search(r"\*\*Score:\*\*\s*<evaluate.*?(\d+)>|Score.*?(\d+)\s*/\s*" + str(lang_weight), lang_analysis)
    _grammar_score_match2   = re.search(r"\*\*Score:\*\*\s*(\d+)", lang_analysis)
    _grammar_feedback_match = re.search(r"\*\*Grammar & Professional Tone:\*\*\s*(.+)", lang_analysis)
    _grammar_sugg_raw       = re.findall(r"^- (.+)", lang_analysis, re.MULTILINE)

    if _grammar_score_match2:
        grammar_score = int(_grammar_score_match2.group(1))
    # else keep the safe default already set above

    if _grammar_feedback_match:
        grammar_feedback = _grammar_feedback_match.group(1).strip()

    if _grammar_sugg_raw:
        grammar_suggestions = _grammar_sugg_raw

    lang_score = grammar_score  # use value parsed from ATS result

    # ── Clamp every score: min floor + hard upper cap to its own weight ──
    # Upper cap prevents LLM hallucinating over-max scores (e.g. 25/20)
    # which would silently push content_score above 100.
    edu_score     = max(int(edu_weight * 0.15),     min(edu_score,     edu_weight))
    exp_score     = max(int(exp_weight * 0.15),     min(exp_score,     exp_weight))
    skills_score  = max(int(skills_weight * 0.15),  min(skills_score,  skills_weight))
    keyword_score = max(int(keyword_weight * 0.10), min(keyword_score, keyword_weight))
    lang_score    = max(0,                          min(lang_score,    lang_weight))

    # Extract missing items with better parsing - now called "opportunities"
    missing_keywords_section = extract_section(r"\*\*Keyword Enhancement Opportunities:\*\*(.*?)(?:\*\*|###|\Z)", keyword_analysis)
    missing_skills_section = extract_section(r"\*\*Skills Gaps \(Development Opportunities\):\*\*(.*?)(?:\*\*|###|\Z)", skills_analysis)

    # Fallback to old patterns if new ones don't match
    if not missing_keywords_section.strip():
        missing_keywords_section = extract_section(r"\*\*Missing Critical Keywords:\*\*(.*?)(?:\*\*|###|\Z)", keyword_analysis)
    if not missing_skills_section.strip():
        missing_skills_section = extract_section(r"\*\*Skills Gaps \(Opportunities for Growth\):\*\*(.*?)(?:\*\*|###|\Z)", skills_analysis)
    if not missing_skills_section.strip():
        missing_skills_section = extract_section(r"\*\*Missing Critical Skills:\*\*(.*?)(?:\*\*|###|\Z)", skills_analysis)
    
    # Improved extraction - handle multiple formats and get all items
    def extract_list_items(text):
        if not text.strip():
            return "None identified"
        
        # Find all bullet points with various formats
        items = []
        lines = text.strip().split('\n')
        
        for line in lines:
            line = line.strip()
            if not line:
                continue
                
            # Remove various bullet point formats
            cleaned_line = re.sub(r'^[-•*]\s*', '', line)  # Remove -, •, * bullets
            cleaned_line = re.sub(r'^\d+\.\s*', '', cleaned_line)  # Remove numbered lists
            cleaned_line = cleaned_line.strip()
            
            if cleaned_line and len(cleaned_line) > 2:  # Avoid empty or very short items
                items.append(cleaned_line)
        
        return ', '.join(items) if items else "None identified"
    
    missing_keywords = extract_list_items(missing_keywords_section)
    missing_skills = extract_list_items(missing_skills_section)

    # ── Score assembly — fully deterministic integer arithmetic ──────────
    # Step 1: sum the five LLM-scored components (clamped to their individual weights)
    content_score = edu_score + exp_score + skills_score + lang_score + keyword_score

    # Normalise LLM components to 90-pt scale (format takes the remaining 10 pts)
    # This keeps total = 100 while giving format meaningful, visible weight.
    weight_total = edu_weight + exp_weight + skills_weight + lang_weight + keyword_weight
    # weight_total should always be > 0 here because the sidebar hard blocks evaluation
    # when total != 90 (min slider values are all >= 2). Guard kept as last-resort safety.
    if weight_total > 0:
        content_score = round(content_score / weight_total * 90)
    else:
        content_score = 0  # should never reach here after sidebar guard
    content_score = max(0, min(90, content_score))

    # Step 2: format score (0–100) contributes a fixed 10-pt component
    # Scaled proportionally: 100 format → 10 pts, 0 format → 0 pts
    fmt_score_raw = format_data.get("format_score", 75) if format_data else 75
    fmt_score_raw = max(0, min(100, int(fmt_score_raw)))
    FORMAT_WEIGHT = 10
    format_component = round(fmt_score_raw / 100 * FORMAT_WEIGHT)

    # Step 3: combine content + format → pre-penalty total (0–100)
    pre_penalty_score = content_score + format_component
    pre_penalty_score = max(0, min(100, pre_penalty_score))

    # Step 4: subtract domain mismatch penalty ONCE — straight subtraction
    total_score = pre_penalty_score - domain_penalty

    # Step 5: clamp final result 15–100
    total_score = max(15, min(100, total_score))

    # ✅ Industry-standard score labels with clear hiring signal
    formatted_score = (
        "Exceptional Match — Top 10% Candidate"    if total_score >= 85 else
        "Strong Match — Recommend for Interview"    if total_score >= 70 else
        "Good Potential — Competitive Candidate"    if total_score >= 55 else
        "Fair Match — Needs Resume Optimization"    if total_score >= 40 else
        "Developing — Significant Skill Gaps"       if total_score >= 25 else
        "Poor Match — Major Role Misalignment"
    )

    # ✅ Format suggestions nicely
    suggestions_html = ""
    if grammar_suggestions:
        suggestions_html = "<ul>" + "".join([f"<li>{s}</li>" for s in grammar_suggestions]) + "</ul>"

    # Convert LLM markdown to HTML so asterisks don't render literally
    # (lang_analysis is raw markdown; the appended content is already HTML)
    _lang_html = re.sub(r'\*\*(.+?)\*\*', r'<b>\1</b>', lang_analysis)   # **bold**
    _lang_html = re.sub(r'\*(.+?)\*',     r'<i>\1</i>', _lang_html)       # *italic*
    _lang_html = re.sub(r'^- ',           '• ',          _lang_html, flags=re.MULTILINE)  # bullet dash
    _lang_html = _lang_html.replace('\n', '<br>')

    updated_lang_analysis = (
        f"{_lang_html}"
        f"<br><b>LLM Feedback Summary:</b> {grammar_feedback}"
        f"<br><b>Improvement Suggestions:</b> {suggestions_html}"
    )

    # Enhanced final thoughts with domain analysis and industry benchmarks
    final_thoughts += f"""

**Technical Evaluation Details:**
- Content Score (LLM components, 90-pt scale): {content_score}/90
- Format Component (10-pt scale): {format_component}/10 (Format Score: {fmt_score_raw}/100)
- Pre-Penalty Score: {pre_penalty_score}/100
- Domain Penalty Applied: -{domain_penalty} pts (out of max -{MAX_DOMAIN_PENALTY} pts)
- Final ATS Score: {total_score}/100
- Domain Similarity: {similarity_score:.2f}/1.0 ({int(similarity_score * 100)}% alignment)
- Resume Domain Detected: {resume_domain}
- Target Job Domain: {job_domain}
- Language Pre-Score: {grammar_score}/{lang_weight}

**Score Interpretation (Industry Benchmarks):**
- 85–100: Top 10% candidates — Strong interview recommendation
- 70–84: Above average — Likely to advance past ATS screening
- 55–69: Competitive — May advance with strong cover letter
- 40–54: Below average — Needs resume optimization before applying
- 25–39: Significant gaps — Upskilling recommended
- 0–24: Major misalignment — Not suitable for this specific role

**ATS Scoring Notes:**
- Scoring model: LLM components (90 pts) + Format (10 pts) − Domain penalty
- Format score is a real 10-pt component (not a delta) — poor formatting meaningfully lowers the score
- Domain penalty subtracted once as a flat deduction (max {MAX_DOMAIN_PENALTY} pts)
- Format checker v2: uses PDF block-coordinate multi-column detection, tiered deductions, bonus credits
- Transferable skills, projects, and open-source contributions were credited
- Career stage (entry/mid/senior) considered in experience scoring
"""

    return ats_result, {
        "Candidate Name": candidate_name,
        "Education Score": edu_score,
        "Experience Score": exp_score,
        "Skills Score": skills_score,
        "Language Score": lang_score,
        "Keyword Score": keyword_score,
        "Format Score": fmt_score_raw,
        "Format Grade": format_data.get("letter_grade", "N/A") if format_data else "N/A",
        "Format Label": format_data.get("label", "") if format_data else "",
        "Format Issues": format_data.get("issues", []) if format_data else [],
        "Format Passes": format_data.get("passes", []) if format_data else [],
        "ATS Match %": total_score,
        "Formatted Score": formatted_score,
        "Education Analysis": edu_analysis,
        "Experience Analysis": exp_analysis,
        "Skills Analysis": skills_analysis,
        "Language Analysis": updated_lang_analysis,
        "Keyword Analysis": keyword_analysis,
        "Format Analysis": format_analysis,
        "Final Thoughts": final_thoughts,
        "Missing Keywords": missing_keywords,
        "Missing Skills": missing_skills,
        "Resume Domain": resume_domain,
        "Job Domain": job_domain,
        "Domain Penalty": domain_penalty,
        "Domain Similarity Score": similarity_score
    }

# Setup Vector DB
def setup_vectorstore(documents):
    embeddings = HuggingFaceEmbeddings(model_name="sentence-transformers/all-MiniLM-L6-v2")
    if DEVICE == "cuda":
        embeddings.model = embeddings.model.to(torch.device("cuda"))
    text_splitter = CharacterTextSplitter(chunk_size=500, chunk_overlap=100)
    doc_chunks = text_splitter.split_text("\n".join(documents))
    return FAISS.from_texts(doc_chunks, embeddings)

# Create Conversational Chain
def create_chain(vectorstore):
    # ✅ Use get_healthy_keys() so dead/quota keys are skipped (reads key_failures
    #    and key_usage from Supabase — same tables that call_llm() maintains).
    all_keys    = load_groq_api_keys()
    healthy     = get_healthy_keys(all_keys)
    if not healthy:
        raise ValueError("❌ No healthy Groq API keys available for chat chain.")
    # healthy list is already shuffled by get_healthy_keys — just take the first
    groq_api_key = healthy[0]
    # ✅ FIX: do NOT increment usage before the call — only after success

    # ✅ Create the ChatGroq object
    llm = ChatGroq(model="llama-3.3-70b-versatile", temperature=0, groq_api_key=groq_api_key)

    # ✅ Build the chain — report failures back so llm_manager skips this key next time
    try:
        chain = ConversationalRetrievalChain.from_llm(
            llm=llm,
            retriever=vectorstore.as_retriever(),
            return_source_documents=True
        )
        # Update in-memory usage instantly; flush to Supabase in background thread
        _mem_increment_usage(groq_api_key)
        _async_increment_usage(groq_api_key)
        _mem_clear_failure(groq_api_key)
        _async_clear_failure(groq_api_key)
        return chain
    except Exception as e:
        err_str = str(e).lower()
        if any(w in err_str for w in ["quota", "rate limit", "429", "too many requests"]):
            _mem_record_failure(groq_api_key, "quota")
            _async_mark_failure(groq_api_key, "quota")
        elif any(w in err_str for w in ["invalid api key", "unauthorized", "401", "403", "authentication"]):
            _mem_record_failure(groq_api_key, "error")
            _async_mark_failure(groq_api_key, "error")
        # transient errors (network blip, 500) — don't mark the key failed at all
        raise
