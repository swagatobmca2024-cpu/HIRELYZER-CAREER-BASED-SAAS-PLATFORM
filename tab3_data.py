# =============================================================
# tab3_data.py
# Static data constants and pure helper functions for Tab 3.
# No Streamlit, no DB, no API — zero side-effects on import.
# =============================================================

import re

JOB_TITLES = [
    "Software Engineering",
    "Full Stack Development",
    "Frontend Development",
    "Backend Development",
    "Mobile Development",
    "Game Development",
    "Data Science",
    "AI / Machine Learning",
    "Data Engineering",
    "Business Intelligence",
    "Analytics Engineering",
    "Cloud Engineering",
    "DevOps / Infrastructure",
    "Site Reliability Engineering",
    "System Architecture",
    "Platform Engineering",
    "Cybersecurity",
    "Application Security",
    "Network Security",
    "Ethical Hacking",
    "Product Management",
    "Project Management",
    "Agile Coaching",
    "Business Analysis",
    "Technical Program Management",
    "UI/UX Design",
    "Product Design",
    "Interaction Design",
    "Blockchain Development",
    "IoT Development",
    "AR / VR Development",
    "Embedded Systems",
    "Database Management",
    "Networking",
    "Quality Assurance / Testing",
    "Fintech",
    "Healthcare Tech",
    "EdTech",
    "E-commerce",
    "Digital Marketing",
    "Technical Sales",
    "Technical Writing"
]

LOCATIONS = [
    "Bangalore",
    "Hyderabad",
    "Mumbai",
    "Delhi NCR",
    "Pune",
    "Chennai",
    "Kolkata",
    "Ahmedabad",
    "Jaipur",
    "Chandigarh",
    "Coimbatore",
    "Indore",
    "Bhubaneswar",
    "Noida",
    "Gurgaon",
    "Thiruvananthapuram",
    "Visakhapatnam",
    "Remote (India)"
]

FEATURED_COMPANIES = {
    "tech": [
        {
            "name": "Google",
            "logo_url": "https://upload.wikimedia.org/wikipedia/commons/2/2f/Google_2015_logo.svg",
            "color": "#4285F4",
            "careers_url": "https://careers.google.com",
            "description": "Leading technology company known for search, cloud, and innovation",
            "categories": ["Software", "AI/ML", "Cloud", "Data Science"]
        },
        {
            "name": "Microsoft",
            "logo_url": "https://upload.wikimedia.org/wikipedia/commons/4/44/Microsoft_logo.svg",
            "color": "#00A4EF",
            "careers_url": "https://careers.microsoft.com",
            "description": "Global leader in software, cloud, and enterprise solutions",
            "categories": ["Software", "Cloud", "Gaming", "Enterprise"]
        },
        {
            "name": "Amazon",
            "logo_url": "https://upload.wikimedia.org/wikipedia/commons/a/a9/Amazon_logo.svg",
            "color": "#FF9900",
            "careers_url": "https://www.amazon.jobs",
            "description": "E-commerce and cloud computing giant",
            "categories": ["Software", "Operations", "Cloud", "Retail"]
        },
        {
            "name": "Apple",
            "logo_url": "https://upload.wikimedia.org/wikipedia/commons/f/fa/Apple_logo_black.svg",
            "color": "#555555",
            "careers_url": "https://www.apple.com/careers",
            "description": "Innovation leader in consumer technology",
            "categories": ["Software", "Hardware", "Design", "AI/ML"]
        },
        {
            "name": "Facebook",
            "logo_url": "https://upload.wikimedia.org/wikipedia/commons/0/05/Facebook_Logo_%282019%29.png",
            "color": "#1877F2",
            "careers_url": "https://www.metacareers.com/",
            "description": "Social media and technology company",
            "categories": ["Software", "Marketing", "Networking", "AI/ML"]
        },
        {
            "name": "Netflix",
            "logo_url": "https://upload.wikimedia.org/wikipedia/commons/0/08/Netflix_2015_logo.svg",
            "color": "#E50914",
            "careers_url": "https://explore.jobs.netflix.net/careers",
            "description": "Streaming media company",
            "categories": ["Software", "Marketing", "Design", "Service"],
            "website": "https://jobs.netflix.com/",
            "industry": "Entertainment & Technology"
        }
    ],
    "indian_tech": [
        {
            "name": "TCS",
            "logo_url": "data:image/svg+xml;charset=utf-8,%3Csvg xmlns='http://www.w3.org/2000/svg' viewBox='0 0 200 60'%3E%3Crect width='200' height='60' fill='%230070C0' rx='6'/%3E%3Ctext x='50%25' y='50%25' dominant-baseline='middle' text-anchor='middle' font-family='Arial,sans-serif' font-size='26' font-weight='900' fill='white' letter-spacing='3'%3ETCS%3C/text%3E%3C/svg%3E",
            "color": "#0070C0",
            "careers_url": "https://www.tcs.com/careers",
            "description": "India's largest IT services company",
            "categories": ["IT Services", "Consulting", "Digital"]
        },
        {
            "name": "Infosys",
            "logo_url": "data:image/svg+xml;charset=utf-8,%3Csvg xmlns='http://www.w3.org/2000/svg' viewBox='0 0 240 60'%3E%3Crect width='240' height='60' fill='%23007CC3' rx='6'/%3E%3Ctext x='50%25' y='50%25' dominant-baseline='middle' text-anchor='middle' font-family='Arial,sans-serif' font-size='22' font-weight='700' fill='white' letter-spacing='1'%3EInfosys%3C/text%3E%3C/svg%3E",
            "color": "#007CC3",
            "careers_url": "https://www.infosys.com/careers",
            "description": "Global leader in digital services and consulting",
            "categories": ["IT Services", "Consulting", "Digital"]
        },
        {
            "name": "Wipro",
            "logo_url": "data:image/svg+xml;charset=utf-8,%3Csvg xmlns='http://www.w3.org/2000/svg' viewBox='0 0 220 60'%3E%3Crect width='220' height='60' fill='%23341F65' rx='6'/%3E%3Ccircle cx='28' cy='30' r='16' fill='%2300BFFF' opacity='0.9'/%3E%3Ccircle cx='28' cy='30' r='10' fill='%23341F65'/%3E%3Ccircle cx='28' cy='30' r='5' fill='%2300BFFF' opacity='0.7'/%3E%3Ctext x='118' y='50%25' dominant-baseline='middle' text-anchor='middle' font-family='Arial,sans-serif' font-size='22' font-weight='700' fill='white'%3EWipro%3C/text%3E%3C/svg%3E",
            "color": "#341F65",
            "careers_url": "https://careers.wipro.com",
            "description": "Leading global information technology company",
            "categories": ["IT Services", "Consulting", "Digital"]
        },
        {
            "name": "HCLTech",
            "logo_url": "data:image/svg+xml;charset=utf-8,%3Csvg xmlns='http://www.w3.org/2000/svg' viewBox='0 0 220 60'%3E%3Crect width='220' height='60' fill='%230075C9' rx='6'/%3E%3Ctext x='50%25' y='50%25' dominant-baseline='middle' text-anchor='middle' font-family='Arial,sans-serif' font-size='22' font-weight='900' fill='white' letter-spacing='1'%3EHCLTech%3C/text%3E%3C/svg%3E",
            "color": "#0075C9",
            "careers_url": "https://www.hcltech.com/careers",
            "description": "Global technology company",
            "categories": ["IT Services", "Engineering", "Digital"]
        }
    ],
    "global_corps": [
        {
            "name": "IBM",
            "logo_url": "https://upload.wikimedia.org/wikipedia/commons/5/51/IBM_logo.svg",
            "color": "#1F70C1",
            "careers_url": "https://www.ibm.com/careers",
            "description": "Global leader in technology and consulting",
            "categories": ["Software", "Consulting", "AI/ML", "Cloud"],
            "website": "https://www.ibm.com/careers/",
            "industry": "Technology & Consulting"
        },
        {
            "name": "Accenture",
            "logo_url": "data:image/svg+xml;charset=utf-8,%3Csvg xmlns='http://www.w3.org/2000/svg' viewBox='0 0 240 60'%3E%3Crect width='240' height='60' fill='%23111' rx='6'/%3E%3Cpolygon points='22,10 38,30 22,50 30,50 46,30 30,10' fill='%23A100FF'/%3E%3Ctext x='135' y='50%25' dominant-baseline='middle' text-anchor='middle' font-family='Arial,sans-serif' font-size='19' font-weight='700' fill='white' letter-spacing='0.5'%3EAccenture%3C/text%3E%3C/svg%3E",
            "color": "#A100FF",
            "careers_url": "https://www.accenture.com/careers",
            "description": "Global professional services company",
            "categories": ["Consulting", "Technology", "Digital"]
        },
        {
            "name": "Cognizant",
            "logo_url": "data:image/svg+xml;charset=utf-8,%3Csvg xmlns='http://www.w3.org/2000/svg' viewBox='0 0 260 60'%3E%3Crect width='260' height='60' fill='%231299D8' rx='6'/%3E%3Ccircle cx='22' cy='30' r='14' fill='white' opacity='0.15'/%3E%3Ccircle cx='22' cy='30' r='8' fill='white' opacity='0.9'/%3E%3Ctext x='148' y='50%25' dominant-baseline='middle' text-anchor='middle' font-family='Arial,sans-serif' font-size='19' font-weight='700' fill='white'%3ECognizant%3C/text%3E%3C/svg%3E",
            "color": "#1299D8",
            "careers_url": "https://careers.cognizant.com",
            "description": "Leading professional services company",
            "categories": ["IT Services", "Consulting", "Digital"]
        }
    ]
}


JOB_MARKET_INSIGHTS = {
    "trending_skills": [
        {"name": "Artificial Intelligence", "growth": "+45%", "icon": "fas fa-brain"},
        {"name": "Cloud Computing", "growth": "+38%", "icon": "fas fa-cloud"},
        {"name": "Data Science", "growth": "+35%", "icon": "fas fa-chart-line"},
        {"name": "Cybersecurity", "growth": "+32%", "icon": "fas fa-shield-alt"},
        {"name": "DevOps", "growth": "+30%", "icon": "fas fa-code-branch"},
        {"name": "Machine Learning", "growth": "+28%", "icon": "fas fa-robot"},
        {"name": "Blockchain", "growth": "+25%", "icon": "fas fa-lock"},
        {"name": "Big Data", "growth": "+23%", "icon": "fas fa-database"},
        {"name": "Internet of Things", "growth": "+21%", "icon": "fas fa-wifi"}
    ],
    "top_locations": [
        {"name": "Bangalore", "jobs": "50,000+", "icon": "fas fa-city"},
        {"name": "Mumbai", "jobs": "35,000+", "icon": "fas fa-city"},
        {"name": "Delhi NCR", "jobs": "30,000+", "icon": "fas fa-city"},
        {"name": "Hyderabad", "jobs": "25,000+", "icon": "fas fa-city"},
        {"name": "Pune", "jobs": "20,000+", "icon": "fas fa-city"},
        {"name": "Chennai", "jobs": "15,000+", "icon": "fas fa-city"},
        {"name": "Noida", "jobs": "10,000+", "icon": "fas fa-city"},
        {"name": "Vadodara", "jobs": "7,000+", "icon": "fas fa-city"},
        {"name": "Ahmedabad", "jobs": "6,000+", "icon": "fas fa-city"},
        {"name": "Remote", "jobs": "3,000+", "icon": "fas fa-globe-americas"},
    ],
    "salary_insights": [
        {"role": "Machine Learning Engineer", "range": "10-35 LPA", "experience": "0-5 years"},
        {"role": "Big Data Engineer", "range": "8-30 LPA", "experience": "0-5 years"},
        {"role": "Software Engineer", "range": "5-25 LPA", "experience": "0-5 years"},
        {"role": "Data Scientist", "range": "8-30 LPA", "experience": "0-5 years"},
        {"role": "DevOps Engineer", "range": "6-28 LPA", "experience": "0-5 years"},
        {"role": "UI/UX Designer", "range": "5-25 LPA", "experience": "0-5 years"},
        {"role": "Full Stack Developer", "range": "8-30 LPA", "experience": "0-5 years"},
        {"role": "C++/C#/Python/Java Developer", "range": "6-26 LPA", "experience": "0-5 years"},
        {"role": "Django Developer", "range": "7-27 LPA", "experience": "0-5 years"},
        {"role": "Cloud Engineer", "range": "6-26 LPA", "experience": "0-5 years"},
        {"role": "Google Cloud/AWS/Azure Engineer", "range": "6-26 LPA", "experience": "0-5 years"},
        {"role": "Salesforce Engineer", "range": "6-26 LPA", "experience": "0-5 years"},
    ]
}


# ── Pure helper functions ─────────────────────────────────────

def get_featured_companies(category=None):
    """Get featured companies with original logos, optionally filtered by category"""
    def has_valid_logo(company):
        url = company.get("logo_url", "")
        return url.startswith("https://") or url.startswith("data:image/")

    if category and category in FEATURED_COMPANIES:
        return [company for company in FEATURED_COMPANIES[category] if has_valid_logo(company)]

    return [
        company for companies in FEATURED_COMPANIES.values()
        for company in companies if has_valid_logo(company)
    ]


def get_market_insights():
    """Get job market insights"""
    return JOB_MARKET_INSIGHTS


def get_company_info(company_name):
    """Get company information by name"""
    for companies in FEATURED_COMPANIES.values():
        for company in companies:
            if company["name"] == company_name:
                return company
    return None


def get_companies_by_industry(industry):
    """Get list of companies by industry"""
    companies = []
    for companies_list in FEATURED_COMPANIES.values():
        for company in companies_list:
            if "industry" in company and company["industry"] == industry:
                companies.append(company)
    return companies


def match_job_title_to_tab3(resume_domain: str):
    """
    Maps a resume-analysis domain (e.g. from db_manager.VALID_DOMAINS, like
    "AI/Machine Learning" or "DevOps/Infrastructure") to the closest matching
    entry in JOB_TITLES for Tab 3's search dropdown.

    The two lists use slightly different spacing/naming conventions
    (e.g. "AI/Machine Learning" vs "AI / Machine Learning"), so this
    normalizes both sides before comparing. Returns None if no reasonable
    match is found — callers should treat that as "don't pre-fill".
    """
    if not resume_domain or resume_domain == "Unknown":
        return None

    def _norm(s):
        return re.sub(r'\s*/\s*', '/', s).strip().lower()

    target = _norm(resume_domain)

    # Exact normalized match first
    for title in JOB_TITLES:
        if _norm(title) == target:
            return title

    # Fallback: containment match (e.g. "Quality Assurance" -> "Quality Assurance / Testing")
    for title in JOB_TITLES:
        norm_title = _norm(title)
        if target in norm_title or norm_title in target:
            return title

    return None


def match_location_to_tab3(free_text_location: str):
    """
    Maps a free-text location string (e.g. "Kolkata, West Bengal" from the
    Resume Builder's location field) to the closest matching entry in
    LOCATIONS, via case-insensitive substring matching. Returns None if no
    reasonable match is found.
    """
    if not free_text_location or not free_text_location.strip():
        return None

    target = free_text_location.strip().lower()

    for loc in LOCATIONS:
        if loc.lower() in target:
            return loc

    return None
