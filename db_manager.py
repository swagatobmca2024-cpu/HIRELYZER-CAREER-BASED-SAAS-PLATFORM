"""
Enhanced Database Manager for Resume Analysis System
Migrated from SQLite to Supabase PostgreSQL (psycopg2)

FIXES vs previous version:
  1. FIXED: _get_fresh_cursor() liveness check now does a real SELECT 1 round-trip
            (old code read conn.isolation_level — a pure Python attr, never touched the socket)
  2. FIXED: Reconnect no longer calls st.cache_resource.clear() — that nuked ALL cached
            resources app-wide, killing llm_manager and user_login connections simultaneously.
            Now uses an isolated module-level connection holder with its own lock.
  3. FIXED: _read_df() no longer commits after a SELECT (was closing open transactions on
            the shared singleton connection, risking mid-transaction corruption).
  4. FIXED: detect_domain_llm() / detect_domain_with_confidence() are safe to call with
            session=None (call_llm now handles None gracefully).
"""

import psycopg2
import psycopg2.extras
import pandas as pd
from datetime import datetime
import pytz
import threading
from collections import defaultdict
from contextlib import contextmanager
from typing import Optional, List, Tuple, Dict, Any
import logging
import streamlit as st
from threading import Lock
from llm_manager import call_llm

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


# ── Connection management (isolated — never touches other modules' connections) ─
# FIX 2: replaced st.cache_resource singleton + .clear() with a module-level holder.
# st.cache_resource.clear() nuked ALL cached resources app-wide, which killed
# llm_manager and user_login connections whenever a DB hiccup occurred here.

_db_conn_holder: dict = {"conn": None}
_db_reconnect_lock = threading.Lock()


def _make_db_connection():
    """Open a fresh psycopg2 connection for DatabaseManager operations."""
    conn = psycopg2.connect(
        host=st.secrets["SUPABASE_HOST"],
        dbname=st.secrets["SUPABASE_DB"],
        user=st.secrets["SUPABASE_USER"],
        password=st.secrets["SUPABASE_PASSWORD"],
        port=st.secrets["SUPABASE_PORT"],
        connect_timeout=30,
        keepalives=1,
        keepalives_idle=30,
        keepalives_interval=10,
        keepalives_count=5,
    )
    conn.autocommit = False
    logger.info("New Supabase PostgreSQL connection established for db_manager.")
    return conn


def _get_fresh_cursor():
    """
    Return a live psycopg2 connection.

    FIX 1: Liveness check is a real SELECT 1 round-trip — the old code read
            conn.isolation_level which is a pure Python attribute and never
            touches the socket, so stale connections passed silently.
    FIX 2: Reconnect only replaces THIS module's connection; does NOT call
            st.cache_resource.clear() which would destroy all other connections.
    """
    with _db_reconnect_lock:
        conn = _db_conn_holder.get("conn")
        need_reconnect = False

        if conn is None:
            need_reconnect = True
        else:
            try:
                with conn.cursor() as cur:
                    cur.execute("SELECT 1")
                conn.rollback()  # close implicit transaction opened by SELECT 1
            except Exception:
                need_reconnect = True
                try:
                    conn.close()
                except Exception:
                    pass

        if need_reconnect:
            _db_conn_holder["conn"] = _make_db_connection()

        return _db_conn_holder["conn"]


class DatabaseManager:
    """
    Enhanced Database Manager backed by Supabase PostgreSQL.
    Public API is identical to the original SQLite version.
    """

    def __init__(self):
        self._pool_lock = Lock()
        self._initialize_database()

    # ── Internal helpers ─────────────────────────────────────────────────────

    @contextmanager
    def get_connection(self):
        """
        Context manager that yields a psycopg2 connection.
        Commits on success, rolls back on error.
        The underlying connection is the module-level singleton.
        """
        conn = _get_fresh_cursor()
        try:
            yield conn
            conn.commit()
        except Exception as e:
            try:
                conn.rollback()
            except Exception:
                pass
            logger.error(f"Database error: {e}")
            raise

    def _execute(self, sql: str, params=None, fetch: str = "none"):
        """
        Run a single statement and optionally return rows.
        fetch: 'one' | 'all' | 'none'
        """
        with self.get_connection() as conn:
            with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
                cur.execute(sql, params)
                if fetch == "one":
                    return cur.fetchone()
                if fetch == "all":
                    return cur.fetchall()
                return None

    def _read_df(self, sql: str, params=None) -> pd.DataFrame:
        """
        Execute a SELECT and return a pandas DataFrame.

        FIX 3: Uses a cursor directly instead of routing through get_connection()
                context manager — get_connection() calls conn.commit() on every exit,
                which is harmless for writes but can interrupt in-flight transactions
                on the shared singleton if called concurrently.
        """
        conn = _get_fresh_cursor()
        try:
            with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
                cur.execute(sql, params)
                rows = cur.fetchall()
            # No commit needed for SELECT; do not close any outer transaction.
            return pd.DataFrame([dict(r) for r in rows]) if rows else pd.DataFrame()
        except Exception as e:
            logger.error(f"read_df error: {e}")
            try:
                conn.rollback()
            except Exception:
                pass
            return pd.DataFrame()

    # ── Schema initialisation ─────────────────────────────────────────────────

    def _initialize_database(self):
        """Create tables and indexes if they don't already exist."""
        ddl = """
        CREATE TABLE IF NOT EXISTS candidates (
            id            SERIAL PRIMARY KEY,
            resume_name   TEXT NOT NULL,
            candidate_name TEXT NOT NULL,
            ats_score     INTEGER NOT NULL CHECK (ats_score BETWEEN 0 AND 100),
            edu_score     INTEGER NOT NULL CHECK (edu_score BETWEEN 0 AND 100),
            exp_score     INTEGER NOT NULL CHECK (exp_score BETWEEN 0 AND 100),
            skills_score  INTEGER NOT NULL CHECK (skills_score BETWEEN 0 AND 100),
            lang_score    INTEGER NOT NULL CHECK (lang_score BETWEEN 0 AND 100),
            keyword_score INTEGER NOT NULL CHECK (keyword_score BETWEEN 0 AND 100),
            format_score  INTEGER NOT NULL DEFAULT 0 CHECK (format_score BETWEEN 0 AND 100),
            bias_score    REAL    NOT NULL CHECK (bias_score BETWEEN 0.0 AND 1.0),
            domain        TEXT NOT NULL,
            timestamp     TIMESTAMP NOT NULL DEFAULT NOW()
        );
        ALTER TABLE candidates ADD COLUMN IF NOT EXISTS
            format_score INTEGER NOT NULL DEFAULT 0;
        CREATE INDEX IF NOT EXISTS idx_candidates_domain     ON candidates(domain);
        CREATE INDEX IF NOT EXISTS idx_candidates_ats_score  ON candidates(ats_score);
        CREATE INDEX IF NOT EXISTS idx_candidates_timestamp  ON candidates(timestamp);
        CREATE INDEX IF NOT EXISTS idx_candidates_bias_score ON candidates(bias_score);
        CREATE INDEX IF NOT EXISTS idx_candidates_domain_ats ON candidates(domain, ats_score);
        CREATE INDEX IF NOT EXISTS idx_candidates_ts_domain  ON candidates(timestamp, domain);
        """
        try:
            with self.get_connection() as conn:
                with conn.cursor() as cur:
                    cur.execute(ddl)
            logger.info("Database initialised with optimized schema and indexes.")
        except Exception as e:
            logger.error(f"Schema init error: {e}")

    # ── Domain detection ──────────────────────────────────────────────────────

    VALID_DOMAINS = [
        "Data Science", "AI/Machine Learning", "UI/UX Design", "Mobile Development",
        "Frontend Development", "Backend Development", "Full Stack Development", "Cybersecurity",
        "Cloud Engineering", "DevOps/Infrastructure", "Quality Assurance", "Game Development",
        "Blockchain Development", "Embedded Systems", "System Architecture", "Database Management",
        "Networking", "Site Reliability Engineering", "Product Management", "Project Management",
        "Business Analysis", "Technical Writing", "Digital Marketing", "E-commerce", "Fintech",
        "Healthcare Tech", "EdTech", "IoT Development", "AR/VR Development", "Technical Sales",
        "Agile Coaching", "Software Engineering", "Unclassified",
    ]

    def detect_domain_llm(self, job_title: str, job_description: str, session=None) -> str:
        _domain_list = ", ".join(self.VALID_DOMAINS)
        prompt = f"""You are an expert technical recruiter with 15+ years of experience classifying job descriptions and resumes across all industries and levels.

Your ONLY job: identify the PRIMARY professional domain from the input below.

════════════════════════════════════════════════════════
STEP 1 — READ THE JOB TITLE FIRST (strongest signal)
════════════════════════════════════════════════════════

Job Title: {job_title}

If the title explicitly names a domain, use it directly:
  "Backend Developer" → "Backend Development"
  "Data Analyst" / "Data Scientist" → "Data Science"
  "ML Engineer" / "AI Engineer" → "AI/Machine Learning"
  "DevOps Engineer" / "Platform Engineer" → "DevOps/Infrastructure"
  "Cloud Engineer" / "Cloud Architect" → "Cloud Engineering"
  "QA Engineer" / "SDET" / "Test Engineer" → "Quality Assurance"
  "Mobile Developer" / "Android" / "iOS" / "Flutter" → "Mobile Development"
  "Full Stack Developer" → "Full Stack Development"
  "Frontend Developer" → "Frontend Development"
  "UX Designer" / "UI Designer" → "UI/UX Design"
  "Security Engineer" / "Security Analyst" → "Cybersecurity"
  "SRE" / "Site Reliability Engineer" → "Site Reliability Engineering"
  "Blockchain Developer" / "Web3 Developer" → "Blockchain Development"
  "Game Developer" → "Game Development"
  "Embedded Engineer" / "Firmware Engineer" → "Embedded Systems"
  "IoT Engineer" → "IoT Development"
  "Network Engineer" → "Networking"
  "Database Administrator" / "DBA" → "Database Management"
  "Product Manager" → "Product Management"
  "Project Manager" / "Program Manager" → "Project Management"
  "Business Analyst" → "Business Analysis"
  "Scrum Master" / "Agile Coach" → "Agile Coaching"
  "Technical Writer" → "Technical Writing"
  "Sales Engineer" / "Pre-Sales" → "Technical Sales"
  "Solution Architect" / "Enterprise Architect" → "System Architecture"

════════════════════════════════════════════════════════
STEP 2 — IF TITLE IS AMBIGUOUS, ANALYSE THE TEXT
════════════════════════════════════════════════════════

Job / Resume Text:
{job_description[:3000]}

Key classification rules:
  • Backend: backend framework (Django/Flask/Spring/Express/FastAPI) + database + API work required
  • Frontend: React/Vue/Angular/HTML+CSS+JS + UI work required
  • Full Stack: BOTH frontend AND backend tech explicitly required
  • Data Science: pandas/numpy/Tableau/Power BI + analysis or visualization work
  • AI/ML: TensorFlow/PyTorch/scikit-learn/LLM/NLP/model training required
  • DevOps: Docker/Kubernetes/CI-CD/Terraform/Jenkins required
  • Cloud: specific AWS/Azure/GCP services required (not just the word "cloud")
  • Cybersecurity: pentesting/OWASP/SIEM/SOC/security tools required
  • Mobile: Android/iOS/Flutter/React Native explicitly required
  • UI/UX: Figma/wireframes/prototyping/user research as primary duty
  • DO NOT classify as Full Stack if only backend framework + "website" — frontend tech must be explicit
  • DO NOT classify as Data Science from SQL alone — analytics work must be described
  • If truly mixed with no dominant domain → "Software Engineering"

════════════════════════════════════════════════════════
STEP 3 — RETURN ANSWER
════════════════════════════════════════════════════════

Return ONLY one domain from this list, nothing else:
{_domain_list}
"""
        try:
            result = call_llm(prompt, session=session, model="llama-3.1-8b-instant").strip()
            if result in self.VALID_DOMAINS:
                return result
            logger.warning(f"LLM returned invalid domain '{result}' — falling back to keyword detection")
            return self.detect_domain_from_title_and_description(job_title, job_description)
        except Exception as e:
            logger.error(f"LLM domain detection failed: {e}")
            return self.detect_domain_from_title_and_description(job_title, job_description)

    def detect_domain_with_confidence(self, job_title: str, job_description: str, session=None) -> Dict[str, Any]:
        """
        Two-stage domain detection with confidence scoring.

        Runs both LLM and keyword detection independently, then compares:
          - Agreement    → high confidence, use the agreed domain
          - Disagreement → low confidence, prefer LLM but flag for review
          - LLM failure  → keyword result with low confidence

        Returns a dict:
          {
            "domain":      str,   — final domain label
            "confidence":  str,   — "high" | "medium" | "low"
            "llm_domain":  str,   — raw LLM result (or None if failed)
            "kw_domain":   str,   — keyword result
            "agreed":      bool,  — whether both methods agreed
          }
        """
        kw_domain = self.detect_domain_from_title_and_description(job_title, job_description)

        llm_domain = None
        llm_failed = False
        try:
            _domain_list = ", ".join(self.VALID_DOMAINS)
            prompt = f"""You are an expert technical recruiter with 15+ years of experience classifying job descriptions and resumes across all industries and levels.

Your ONLY job: identify the PRIMARY professional domain from the input below.

════════════════════════════════════════════════════════
STEP 1 — READ THE JOB TITLE FIRST (strongest signal)
════════════════════════════════════════════════════════

Job Title: {job_title}

If the title explicitly names a domain, use it directly:
  "Backend Developer" → "Backend Development"
  "Data Analyst" / "Data Scientist" → "Data Science"
  "ML Engineer" / "AI Engineer" → "AI/Machine Learning"
  "DevOps Engineer" / "Platform Engineer" → "DevOps/Infrastructure"
  "Cloud Engineer" / "Cloud Architect" → "Cloud Engineering"
  "QA Engineer" / "SDET" / "Test Engineer" → "Quality Assurance"
  "Mobile Developer" / "Android" / "iOS" / "Flutter" → "Mobile Development"
  "Full Stack Developer" → "Full Stack Development"
  "Frontend Developer" → "Frontend Development"
  "UX Designer" / "UI Designer" → "UI/UX Design"
  "Security Engineer" / "Security Analyst" → "Cybersecurity"
  "SRE" / "Site Reliability Engineer" → "Site Reliability Engineering"
  "Blockchain Developer" / "Web3 Developer" → "Blockchain Development"
  "Game Developer" → "Game Development"
  "Embedded Engineer" / "Firmware Engineer" → "Embedded Systems"
  "IoT Engineer" → "IoT Development"
  "Network Engineer" → "Networking"
  "Database Administrator" / "DBA" → "Database Management"
  "Product Manager" → "Product Management"
  "Project Manager" / "Program Manager" → "Project Management"
  "Business Analyst" → "Business Analysis"
  "Scrum Master" / "Agile Coach" → "Agile Coaching"
  "Technical Writer" → "Technical Writing"
  "Sales Engineer" / "Pre-Sales" → "Technical Sales"
  "Solution Architect" / "Enterprise Architect" → "System Architecture"

════════════════════════════════════════════════════════
STEP 2 — IF TITLE IS AMBIGUOUS, ANALYSE THE TEXT
════════════════════════════════════════════════════════

Job / Resume Text:
{job_description[:3000]}

Key classification rules:
  • Backend: backend framework (Django/Flask/Spring/Express/FastAPI) + database + API work required
  • Frontend: React/Vue/Angular/HTML+CSS+JS + UI work required
  • Full Stack: BOTH frontend AND backend tech explicitly required
  • Data Science: pandas/numpy/Tableau/Power BI + analysis or visualization work
  • AI/ML: TensorFlow/PyTorch/scikit-learn/LLM/NLP/model training required
  • DevOps: Docker/Kubernetes/CI-CD/Terraform/Jenkins required
  • Cloud: specific AWS/Azure/GCP services required (not just the word "cloud")
  • Cybersecurity: pentesting/OWASP/SIEM/SOC/security tools required
  • Mobile: Android/iOS/Flutter/React Native explicitly required
  • UI/UX: Figma/wireframes/prototyping/user research as primary duty
  • DO NOT classify as Full Stack if only backend framework + "website" — frontend tech must be explicit
  • DO NOT classify as Data Science from SQL alone — analytics work must be described
  • If truly mixed with no dominant domain → "Software Engineering"

════════════════════════════════════════════════════════
STEP 3 — RETURN ANSWER
════════════════════════════════════════════════════════

Return ONLY one domain from this list, nothing else:
{_domain_list}
"""
            raw = call_llm(prompt, session=session, model="llama-3.1-8b-instant").strip()
            llm_domain = raw if raw in self.VALID_DOMAINS else None
            if llm_domain is None:
                logger.warning(f"LLM returned invalid domain '{raw}' in two-stage detection")
                llm_failed = True
        except Exception as e:
            logger.error(f"LLM failed in two-stage detection: {e}")
            llm_failed = True

        if llm_failed or llm_domain is None:
            return {
                "domain":     kw_domain,
                "confidence": "low",
                "llm_domain": None,
                "kw_domain":  kw_domain,
                "agreed":     False,
            }

        agreed = (llm_domain.lower() == kw_domain.lower())

        if agreed:
            return {
                "domain":     llm_domain,
                "confidence": "high",
                "llm_domain": llm_domain,
                "kw_domain":  kw_domain,
                "agreed":     True,
            }

        if kw_domain == "Unclassified":
            return {
                "domain":     llm_domain,
                "confidence": "high",
                "llm_domain": llm_domain,
                "kw_domain":  kw_domain,
                "agreed":     False,
            }

        return {
            "domain":     llm_domain,
            "confidence": "medium",
            "llm_domain": llm_domain,
            "kw_domain":  kw_domain,
            "agreed":     False,
        }

    def detect_domain_from_title_and_description(self, job_title: str, job_description: str) -> str:
        title = job_title.lower().strip()
        desc = job_description.lower().strip()

        replacements = {
            # Security
            "cyber security": "cybersecurity", "security engineer": "cybersecurity",
            "information security": "cybersecurity", "infosec engineer": "cybersecurity",
            "application security": "cybersecurity", "appsec": "cybersecurity",
            # AI / ML
            "ai engineer": "machine learning", "ml engineer": "machine learning",
            "nlp engineer": "machine learning", "computer vision engineer": "machine learning",
            "research scientist": "machine learning", "ml ops engineer": "machine learning",
            "mlops engineer": "machine learning", "ai researcher": "machine learning",
            "deep learning engineer": "machine learning",
            # Data
            "data engineer": "data science", "analytics engineer": "data science",
            "data architect": "data science", "bi developer": "data science",
            "business intelligence developer": "data science",
            # Software
            "software developer": "software engineer",
            # Frontend / Backend / Full Stack
            "frontend developer": "frontend", "front end developer": "frontend",
            "backend developer": "backend", "back end developer": "backend",
            "fullstack developer": "full stack", "full stack developer": "full stack",
            "full-stack developer": "full stack",
            # DevOps / Infra
            "devops engineer": "devops", "platform engineer": "devops",
            "infrastructure engineer": "devops", "site reliability engineer": "devops",
            "release engineer": "devops", "build engineer": "devops",
            # Cloud
            "cloud engineer": "cloud", "cloud architect": "cloud",
            "cloud infrastructure engineer": "cloud",
            # QA
            "qa engineer": "quality assurance", "test engineer": "quality assurance",
            "sdet": "quality assurance", "automation engineer": "quality assurance",
            "qa automation engineer": "quality assurance",
            # SRE
            "sre": "site reliability engineering",
            # Blockchain
            "blockchain developer": "blockchain", "web3 developer": "blockchain",
            "smart contract developer": "blockchain",
            # Game
            "game developer": "game development", "game engineer": "game development",
            # Embedded / IoT
            "embedded engineer": "embedded systems", "firmware engineer": "embedded systems",
            "iot engineer": "iot development",
            # Networking
            "network engineer": "networking", "network administrator": "networking",
            "network architect": "networking",
            # Database
            "database administrator": "database management", "dba": "database management",
            "database engineer": "database management",
            # Management / Business
            "business analyst": "business analysis", "product manager": "product management",
            "project manager": "project management", "scrum master": "agile coaching",
            "agile coach": "agile coaching", "program manager": "project management",
            # Other
            "technical writer": "technical writing", "sales engineer": "technical sales",
            "solution architect": "system architecture",
            "enterprise architect": "system architecture",
            "mobile developer": "mobile development", "android developer": "mobile development",
            "ios developer": "mobile development", "react native developer": "mobile development",
            "flutter developer": "mobile development",
        }
        for old, new in replacements.items():
            title = title.replace(old, new)
            desc = desc.replace(old, new)

        domain_scores = defaultdict(int)
        WEIGHTS = {
            "Data Science": 4, "AI/Machine Learning": 4, "UI/UX Design": 3,
            "Mobile Development": 3, "Frontend Development": 3, "Backend Development": 3,
            "Full Stack Development": 4, "Cybersecurity": 4, "Cloud Engineering": 3,
            "DevOps/Infrastructure": 3, "Quality Assurance": 3, "Game Development": 3,
            "Blockchain Development": 3, "Embedded Systems": 3, "System Architecture": 4,
            "Database Management": 3, "Networking": 3, "Site Reliability Engineering": 3,
            "Product Management": 3, "Project Management": 3, "Business Analysis": 3,
            "Technical Writing": 2, "Digital Marketing": 3, "E-commerce": 3, "Fintech": 3,
            "Healthcare Tech": 3, "EdTech": 3, "IoT Development": 3, "AR/VR Development": 3,
            "Technical Sales": 2, "Agile Coaching": 2, "Software Engineering": 2,
        }

        keywords = {
            "Data Science": [
                "data analyst","data scientist","data science","eda","pandas","numpy",
                "data analysis","statistics","data visualization","matplotlib","seaborn",
                "power bi","tableau","looker","kpi","sql","excel","dashboards","insights",
                "hypothesis testing","a/b testing","business intelligence","data wrangling",
                "feature engineering","data storytelling","exploratory analysis","data mining",
                "statistical modeling","time series","forecasting","predictive analytics",
                "analytics engineer","r programming","jupyter","databricks","spark","hadoop",
                "etl","data pipeline","data warehouse","olap","oltp","dimensional modeling",
                "data governance","data engineer","data architecture","dbt","airflow",
                "data quality","data catalog","data lake","data mesh","data observability",
                "cohort analysis","funnel analysis","retention analysis","churn prediction",
                "looker studio","metabase","superset","google analytics","mixpanel","amplitude"
            ],
            "AI/Machine Learning": [
                "machine learning","deep learning","neural network","nlp",
                "computer vision","scikit-learn","tensorflow","pytorch","llm",
                "huggingface","xgboost","lightgbm","classification","regression",
                "reinforcement learning","transfer learning","model training","bert","gpt",
                "yolo","transformer","autoencoder","fine-tuning","zero-shot",
                "one-shot","mistral","llama","openai","langchain","vector embeddings",
                "prompt engineering","mlops","model deployment","feature store",
                "model monitoring","hyperparameter tuning","ensemble methods",
                "gradient boosting","random forest","svm","clustering","pca",
                "natural language processing","text classification","named entity recognition",
                "sentiment analysis","object detection","image segmentation","generative ai",
                "diffusion models","stable diffusion","rag","retrieval augmented generation",
                "vector database","pinecone","weaviate","chroma","faiss","onnx","triton",
                "kubeflow","mlflow","weights and biases","model quantization","distillation",
                "research scientist","nlp engineer","computer vision engineer","ai researcher"
            ],
            "UI/UX Design": [
                "figma","adobe xd","sketch","wireframe","prototyping","user interface",
                "user experience","usability testing","interaction design","design system",
                "visual design","responsive design","material design","user research",
                "usability","accessibility","human-centered design","affinity diagram",
                "journey mapping","heuristic evaluation","persona","mobile-first","ux audit",
                "design tokens","design thinking","information architecture","card sorting",
                "tree testing","user testing","a/b testing design","design sprint",
                "atomic design","design ops","brand design","motion design","micro-interactions",
                "zeplin","invision","principle","framer","hotjar","maze","optimal workshop",
                "wcag","aria","color theory","typography","grid system","ui design",
                "ux research","ux writing","content design","service design"
            ],
            "Mobile Development": [
                "android","ios","flutter","kotlin","swift","mobile app","react native",
                "mobile application","play store","app store","firebase","mobile sdk",
                "xcode","android studio","cross-platform","native mobile","push notifications",
                "in-app purchases","mobile ui","mobile ux","apk","ipa","expo","capacitor",
                "cordova","xamarin","ionic","phonegap","mobile testing","app optimization",
                "mobile security","offline functionality","mobile analytics","app monetization",
                "mobile performance","jetpack compose","swiftui","kotlin multiplatform",
                "mobile ci/cd","fastlane","detox","espresso","xctest","app store optimization",
                "deep linking","mobile architecture","mvvm android","clean architecture mobile",
                "android developer","ios developer","flutter developer","react native developer"
            ],
            "Frontend Development": [
                "frontend","html","css","javascript","react","angular","vue","typescript",
                "next.js","webpack","bootstrap","tailwind","sass","es6","responsive design",
                "web accessibility","dom","jquery","redux","vite","zustand","framer motion",
                "storybook","eslint","pwa","single page application","csr","ssr",
                "hydration","component-based ui","web components","micro frontends","bundler",
                "transpiler","polyfill","css grid","flexbox","css animations","web performance",
                "lighthouse","core web vitals","nuxt.js","svelte","solid.js","astro",
                "graphql client","apollo client","react query","swr","emotion","styled components",
                "testing library","playwright","vitest","web vitals","accessibility testing",
                "design tokens implementation","component library","front end"
            ],
            "Backend Development": [
                "backend","node.js","django","flask","express","api development","nosql",
                "server-side","mysql","postgresql","mongodb","rest api","graphql","java",
                "spring boot","authentication","authorization","mvc","business logic","orm",
                "database schema","asp.net","laravel","go","fastapi","nest.js","microservices",
                "websockets","rabbitmq","message broker","cron jobs","redis","elasticsearch",
                "kafka","grpc","soap","middleware","caching","load balancing","rate limiting",
                "api gateway","serverless","lambda functions","backend developer",
                "back end","python backend","ruby on rails","php","scala","rust backend",
                "celery","dramatiq","background jobs","database optimization","query optimization",
                "connection pooling","database indexing","api versioning","oauth","jwt",
                "session management","backend architecture","hexagonal architecture"
            ],
            "Full Stack Development": [
                "full stack","fullstack","mern","mean","mevn","lamp","jamstack",
                "frontend and backend","end-to-end development","full stack developer",
                "api integration","rest api","graphql","monolith","microservices",
                "serverless architecture","integrated app","web application",
                "cross-functional development","component-based architecture",
                "database design","middleware","mvc","mvvm","authentication","authorization",
                "session management","cloud deployment","responsive ui","performance tuning",
                "state management","redux","context api","axios","fetch api","isomorphic",
                "universal rendering","headless cms","api-first development",
                "full-stack","t3 stack","blitz.js","remix","trpc"
            ],
            "Cybersecurity": [
                "cybersecurity","security analyst","penetration testing","ethical hacking",
                "owasp","vulnerability","threat analysis","infosec","red team","blue team",
                "incident response","firewall","ids","ips","malware","encryption",
                "cyber threat","security operations","siem","zero-day","cyber attack",
                "kali linux","burp suite","nmap","wireshark","cve","forensics","security audit",
                "information security","compliance","ransomware","threat hunting",
                "security architecture","identity management","pki","security governance",
                "risk assessment","vulnerability management","soc","security engineer",
                "application security","appsec","devsecops","pentesting","ctf","metasploit",
                "reverse engineering","malware analysis","threat intelligence","osint",
                "zero trust","iam security","privileged access","dlp","endpoint security",
                "security monitoring","log analysis","security automation","soar"
            ],
            "Cloud Engineering": [
                "cloud","aws","azure","gcp","cloud engineer","cloud computing",
                "cloud infrastructure","cloud security","s3","ec2","cloud formation",
                "load balancer","auto scaling","cloud storage","cloud native","cloud migration",
                "eks","aks","terraform","cloudwatch","cloudtrail","iam","rds","elb","lambda",
                "azure functions","cloud functions","serverless","containers",
                "cloud architecture","multi-cloud","hybrid cloud","cloud cost optimization",
                "cloud architect","google cloud","digitalocean","cloud deployment",
                "vpc","subnet","cdn","route53","cloudfront","azure ad","gke","fargate",
                "cloud security posture","finops","well-architected framework",
                "cloud networking","transit gateway","direct connect","expressroute"
            ],
            "DevOps/Infrastructure": [
                "devops","docker","kubernetes","ci/cd","jenkins","ansible",
                "infrastructure as code","terraform","monitoring","prometheus","grafana",
                "deployment","automation","pipeline","build and release","scripting","bash",
                "shell script","site reliability","argocd","helm","fluxcd","aws cli",
                "linux administration","log aggregation","observability","splunk","gitlab ci",
                "github actions","azure devops","puppet","chef","vagrant",
                "infrastructure monitoring","alerting","incident management","chaos engineering",
                "platform engineer","infrastructure engineer","platform engineering",
                "pagerduty","datadog","new relic","elk stack","fluentd","logstash",
                "continuous delivery","continuous deployment","gitops","k8s","openshift",
                "vault","consul","service mesh","istio","linkerd","release management"
            ],
            "Quality Assurance": [
                "quality assurance","testing","test automation","selenium","cypress",
                "test cases","test planning","bug tracking","regression testing",
                "performance testing","load testing","stress testing","api testing",
                "ui testing","unit testing","integration testing","system testing",
                "acceptance testing","test driven development","behavior driven development",
                "cucumber","jest","mocha","junit","testng","postman","jmeter","appium",
                "test management","defect management","sdet","manual testing",
                "exploratory testing","smoke testing","sanity testing","end-to-end testing",
                "playwright","k6","gatling","locust","test strategy","test coverage",
                "quality engineer","software tester","qa automation","test framework",
                "accessibility testing","cross-browser testing","mobile testing"
            ],
            "Game Development": [
                "game development","unity","unreal engine","game design",
                "game programming","animation","shader programming",
                "physics engine","game mechanics","level design","game testing","multiplayer",
                "mobile games","console games","pc games","vr games","ar games",
                "game optimization","performance profiling","game analytics","monetization",
                "godot","cocos2d","opengl","directx","vulkan","game engine",
                "procedural generation","pathfinding","ai for games","game ui",
                "loot systems","inventory system","save system","game backend",
                "steam","unity3d","unreal blueprint","c++ games","c# unity"
            ],
            "Blockchain Development": [
                "blockchain","cryptocurrency","smart contracts","solidity","ethereum","bitcoin",
                "defi","nft","web3","dapp","consensus algorithms","cryptography",
                "distributed ledger","mining","staking","tokenomics","metamask","truffle",
                "hardhat","ipfs","polygon","binance smart chain","hyperledger","chainlink",
                "oracles","dao","yield farming","blockchain developer","web3 developer",
                "evm","layer 2","zk-rollups","optimism","arbitrum","solana","rust blockchain",
                "anchor framework","token standards","erc20","erc721","defi protocol",
                "liquidity pool","amm","cross-chain","bridge","wallet integration"
            ],
            "Embedded Systems": [
                "embedded systems","microcontroller","firmware","assembly",
                "real-time systems","rtos","arduino","raspberry pi","arm","pic","embedded c",
                "hardware programming","sensor integration","iot devices","low-level programming",
                "device drivers","bootloader","embedded linux","fpga","verilog","vhdl",
                "pcb design","circuit design","firmware engineer","embedded engineer",
                "freertos","zephyr","bare metal","stm32","esp32","avr","msp430",
                "can bus","spi","i2c","uart","modbus","embedded testing","hardware abstraction",
                "cross compilation","jtag","debugging embedded","power management ic"
            ],
            "System Architecture": [
                "system architecture","solution architect","enterprise architecture",
                "microservices","distributed systems","scalability","high availability",
                "fault tolerance","system design","architecture patterns","design patterns",
                "load balancing","caching strategies","database sharding",
                "event-driven architecture","message queues","api design","service mesh",
                "containerization","orchestration","cloud architecture","enterprise architect",
                "technical architecture","domain driven design","ddd","cqrs","event sourcing",
                "saga pattern","strangler fig","hexagonal architecture","clean architecture",
                "architect","system design interview","cap theorem","consistency","availability",
                "partition tolerance","technical roadmap","architecture review","adr"
            ],
            "Database Management": [
                "database administrator","database design","sql optimization",
                "database performance","backup and recovery","replication","clustering",
                "data modeling","normalization","indexing","stored procedures","triggers",
                "database security","mysql","postgresql","oracle","sql server","mongodb",
                "cassandra","redis","elasticsearch","data warehouse","etl","olap",
                "database engineer","database management","dba","database tuning",
                "query optimization","execution plan","partitioning","sharding",
                "cockroachdb","tidb","yugabyte","vitess","pgbouncer","connection pooling",
                "database migration","flyway","liquibase","schema design","er diagram",
                "database monitoring","slow query","index strategy","database backup"
            ],
            "Networking": [
                "network engineer","network administration","cisco","routing","switching",
                "tcp/ip","dns","dhcp","vpn","firewall","network security","network monitoring",
                "network troubleshooting","wan","lan","vlan","bgp","ospf","mpls","sd-wan",
                "network automation","network protocols","network administrator","network architect",
                "juniper","arista","palo alto","fortinet","f5","load balancer networking",
                "network design","ip addressing","subnetting","nat","acl","qos",
                "wireless networking","wifi","802.11","lte","5g","network virtualization",
                "nfv","sdn","openflow","network observability","netflow","packet analysis"
            ],
            "Site Reliability Engineering": [
                "site reliability","system reliability","incident management",
                "post-mortem","error budgets","sli","slo","monitoring","alerting",
                "capacity planning","performance optimization","chaos engineering",
                "disaster recovery","high availability","fault tolerance","observability",
                "site reliability engineer","reliability engineering","sre practices",
                "toil reduction","on-call","runbook","playbook","mean time to recovery",
                "mttr","mtbf","golden signals","latency","traffic","errors","saturation",
                "distributed tracing","jaeger","zipkin","opentelemetry","service level"
            ],
            "Product Management": [
                "product manager","product management","product strategy","roadmap",
                "user stories","requirements gathering","stakeholder management","agile",
                "scrum","kanban","product analytics","a/b testing","user research",
                "market research","competitive analysis","go-to-market","product launch",
                "feature prioritization","backlog management","kpi","metrics",
                "product owner","product lead","product director","product vision",
                "okr","north star metric","product discovery","customer interviews",
                "jobs to be done","jtbd","product market fit","mvp","product roadmap",
                "prioritization framework","rice scoring","moscow method","product operations",
                "growth product","platform product","b2b product","b2c product"
            ],
            "Project Management": [
                "project manager","project management","pmp","agile","scrum master","kanban",
                "waterfall","risk management","resource planning","timeline","milestone",
                "deliverables","stakeholder communication","budget management",
                "team coordination","project planning","project execution","project closure",
                "change management","jira","confluence","ms project","program manager",
                "portfolio management","prince2","pmbok","earned value management",
                "critical path","gantt chart","project charter","work breakdown structure",
                "wbs","resource allocation","project governance","project tracking",
                "asana","monday.com","smartsheet","basecamp","trello"
            ],
            "Business Analysis": [
                "business analyst","requirements analysis","process improvement","workflow",
                "business process","stakeholder analysis","gap analysis","use cases",
                "functional requirements","non-functional requirements","documentation",
                "process mapping","business rules","acceptance criteria",
                "user acceptance testing","change management","business intelligence",
                "data analysis","reporting","business analysis","bpmn","uml use cases",
                "requirements elicitation","as-is process","to-be process","business case",
                "cost benefit analysis","feasibility study","business requirements document",
                "brd","functional specification","user stories","epics","wireframes ba",
                "visio","lucidchart","process automation","rpa analysis"
            ],
            "Technical Writing": [
                "technical writer","documentation","api documentation","user manuals",
                "technical communication","content strategy","information architecture",
                "style guide","editing","proofreading","markdown","confluence","gitbook",
                "sphinx","doxygen","technical blogging","knowledge base","technical writing",
                "developer documentation","sdk documentation","release notes","changelog",
                "readme","swagger","openapi documentation","docs as code","docusaurus",
                "readthedocs","vale","technical content","developer relations","devrel",
                "tutorials","how-to guides","reference documentation","conceptual documentation"
            ],
            "Digital Marketing": [
                "digital marketing","seo","sem","social media marketing","content marketing",
                "email marketing","ppc","google ads","facebook ads","analytics",
                "conversion optimization","marketing automation","lead generation",
                "brand management","influencer marketing","affiliate marketing","growth hacking",
                "marketing analytics","google analytics","hubspot","marketo","mailchimp",
                "content creation","copywriting","ad campaigns","performance marketing",
                "cpa","cpc","ctr","roas","marketing funnel","customer acquisition",
                "retention marketing","crm marketing","social ads","tiktok ads"
            ],
            "E-commerce": [
                "e-commerce","online retail","shopify","magento","woocommerce","payment gateway",
                "inventory management","order management","shipping","customer service",
                "marketplace","dropshipping","conversion rate optimization","product catalog",
                "shopping cart","checkout optimization","amazon fba","ecommerce",
                "bigcommerce","prestashop","opencart","wix ecommerce","squarespace",
                "product feed","google merchant","amazon seller","ebay seller",
                "fulfillment","logistics","returns management","customer lifetime value",
                "clv","average order value","aov","cart abandonment","upsell ecommerce"
            ],
            "Fintech": [
                "fintech","financial technology","payment processing","banking software",
                "trading systems","risk management","compliance","regulatory","kyc","aml",
                "blockchain finance","cryptocurrency","robo-advisor","insurtech",
                "lending platform","credit scoring","fraud detection","financial analytics",
                "payment gateway","swift","iso 20022","open banking","plaid","stripe",
                "braintree","adyen","neobank","digital banking","core banking",
                "algorithmic trading","quantitative finance","fixed income","derivatives",
                "options trading","portfolio management","asset management","wealth tech",
                "regtech","psd2","gdpr finance","financial modeling","risk modeling",
                "anti-money laundering","know your customer","transaction monitoring"
            ],
            "Healthcare Tech": [
                "healthcare technology","healthtech","medical software","ehr","emr",
                "telemedicine","medical devices","hipaa","healthcare analytics","clinical trials",
                "medical imaging","bioinformatics","health informatics","patient management",
                "healthcare compliance","medical ai","digital health","hl7","fhir",
                "healthcare interoperability","clinical data","medical records",
                "hospital information system","his","laboratory information system","lis",
                "radiology information system","ris","pacs","dicom","icd codes","cpt codes",
                "telehealth","remote patient monitoring","wearable health","health api",
                "clinical decision support","population health","care coordination",
                "pharmacy management","drug interaction","medical billing","rcm"
            ],
            "EdTech": [
                "edtech","educational technology","e-learning","lms","learning management",
                "online education","educational software","student information system",
                "assessment tools","educational analytics","adaptive learning","gamification",
                "virtual classroom","educational content","curriculum development",
                "moodle","canvas","blackboard","scorm","xapi","tin can api",
                "courseware","instructional design","learning experience design","lxd",
                "tutoring platform","online course","mooc","microlearning","blended learning",
                "student engagement","learning outcomes","educational games","school management",
                "university management","grade tracking","attendance system"
            ],
            "IoT Development": [
                "iot","internet of things","connected devices","sensor networks","edge computing",
                "mqtt","coap","zigbee","bluetooth","wifi","device management",
                "iot platform","industrial iot","smart home","smart city","wearables",
                "asset tracking","predictive maintenance","iot engineer",
                "aws iot","azure iot","google cloud iot","thingsboard","node-red",
                "lorawan","nb-iot","lte-m","5g iot","iot security","ota updates",
                "digital twin","industry 4.0","iiot","scada","plc","hmi","opc-ua",
                "time series database","influxdb","iot analytics","fleet management"
            ],
            "AR/VR Development": [
                "augmented reality","virtual reality","mixed reality","xr","unity 3d",
                "unreal engine","oculus","hololens","arkit","arcore","3d modeling",
                "spatial computing","immersive experience","360 video","haptic feedback",
                "motion tracking","computer vision","3d graphics","metaverse",
                "openxr","webxr","a-frame","babylon.js","three.js vr","vr developer",
                "ar developer","spatial audio","6dof","room-scale","hand tracking",
                "eye tracking","mixed reality toolkit","mrtk","vuforia","spark ar",
                "lens studio","snap ar","instagram ar","webgl","3d web"
            ],
            "Technical Sales": [
                "technical sales","sales engineer","solution selling","pre-sales",
                "technical consulting","customer success","account management",
                "product demonstration","technical presentation","proposal writing",
                "client relationship","revenue generation","sales process","crm",
                "b2b sales","saas sales","enterprise sales","technical account manager",
                "tam","demo","proof of concept","poc sales","rfp","rfi","deal closure",
                "pipeline management","quota","upsell","cross-sell","renewal",
                "salesforce","hubspot crm","solution architect sales","value selling",
                "roi analysis","business case selling","partner sales","channel sales"
            ],
            "Agile Coaching": [
                "agile coach","scrum master","agile transformation","team facilitation",
                "retrospectives","sprint planning","daily standups","agile ceremonies",
                "continuous improvement","change management","team dynamics","agile metrics",
                "coaching","mentoring","organizational change","kanban","velocity",
                "burndown chart","backlog refinement","product owner coaching","sprint review",
                "story points","definition of done","definition of ready","scaled agile",
                "safe","less","nexus","scrum of scrums","agile at scale","lean agile",
                "obeya","value stream mapping","flow metrics","cycle time","lead time",
                "agile mindset","psychological safety","team health","mob programming"
            ],
            "Software Engineering": [
                "software engineer","web developer","programmer","object oriented",
                "design patterns","agile","scrum","git","version control","unit testing",
                "integration testing","debugging","code review","system design","tdd","bdd",
                "pair programming","refactoring","uml","dev environment","ide","algorithms",
                "data structures","software architecture","clean code","software development",
                "developer","coding","programming","github","gitlab","bitbucket",
                "pull request","merge request","continuous integration","solid principles",
                "dry principle","kiss principle","software lifecycle","sdlc","api","sdk"
            ],
        }

        import re as _re
        def _kw_hit(kw, text):
            return bool(_re.search(r'(?<![a-z])' + _re.escape(kw) + r'(?![a-z])', text))

        for domain, kws in keywords.items():
            title_hits = sum(1 for kw in kws if _kw_hit(kw, title))
            desc_hits  = sum(1 for kw in kws if _kw_hit(kw, desc))
            domain_scores[domain] = (4 * title_hits + 1 * desc_hits) * WEIGHTS[domain]

        # ── Boost 1: explicit full-stack signals ──────────────────────────────
        frontend_hits = sum(1 for kw in keywords["Frontend Development"] if _kw_hit(kw, title) or _kw_hit(kw, desc))
        backend_hits  = sum(1 for kw in keywords["Backend Development"]  if _kw_hit(kw, title) or _kw_hit(kw, desc))
        fullstack_mentioned = any(_kw_hit(t, title) or _kw_hit(t, desc) for t in ["full stack", "fullstack", "full-stack"])
        if fullstack_mentioned:
            domain_scores["Full Stack Development"] += 15
        if frontend_hits >= 4 and backend_hits >= 4:
            domain_scores["Full Stack Development"] += 12

        # ── Boost 2: EVIDENCE-GATED WEB APP RULE ─────────────────────────────
        # Only boost Full Stack when EXPLICIT frontend tech is present alongside
        # a backend framework. "website" + "Django" alone is Backend, not Full Stack
        # — the word "website" does not prove a frontend was built by this candidate.
        web_app_terms    = ["website", "web app", "web application", "web portal", "web platform"]
        backend_fw_terms = ["django", "flask", "laravel", "express", "node.js", "spring boot",
                            "fastapi", "nestjs", "rails", "asp.net", "sinatra", "gin", "fiber"]
        # Frontend must be EXPLICITLY named — not just implied by "website"
        frontend_explicit_terms = [
            "html", "css", "javascript", "react", "vue", "angular", "bootstrap",
            "jquery", "next.js", "tailwind", "sass", "typescript", "svelte",
            "nuxt", "vite", "webpack", "jsx", "tsx"
        ]
        is_web_app              = any(_kw_hit(t, title) or _kw_hit(t, desc) for t in web_app_terms)
        has_backend_fw          = any(_kw_hit(t, title) or _kw_hit(t, desc) for t in backend_fw_terms)
        frontend_explicit_hits  = sum(1 for kw in frontend_explicit_terms if _kw_hit(kw, title) or _kw_hit(kw, desc))

        if is_web_app and has_backend_fw and frontend_explicit_hits >= 2:
            # Both frontend AND backend explicitly present → Full Stack boost
            domain_scores["Full Stack Development"] += 10
            domain_scores["Backend Development"]    = max(0, domain_scores["Backend Development"] - 5)
        elif is_web_app and has_backend_fw and frontend_explicit_hits < 2:
            # Backend framework + "website" but NO explicit frontend → Backend boost
            domain_scores["Backend Development"]    += 6
            domain_scores["Full Stack Development"] = max(0, domain_scores["Full Stack Development"] - 3)

        # ── Boost 3: domain keyword boosts ────────────────────────────────────
        domain_boosts = {
            "AI/Machine Learning":    ["ai", "ml", "machine learning", "artificial intelligence", "deep learning", "llm", "nlp"],
            "Cybersecurity":          ["security", "cyber", "infosec", "pentesting", "ethical hacking", "soc"],
            "Cloud Engineering":      ["cloud", "aws", "azure", "gcp", "cloud engineer"],
            "Mobile Development":     ["mobile", "android", "ios", "flutter", "react native", "kotlin", "swift"],
            "Game Development":       ["game", "unity", "unreal", "godot"],
            "Blockchain Development": ["blockchain", "crypto", "web3", "defi", "solidity", "smart contract"],
            "IoT Development":        ["iot", "sensor", "mqtt", "raspberry pi", "arduino iot"],
            "AR/VR Development":      ["ar", "vr", "augmented reality", "virtual reality", "arkit", "arcore", "oculus"],
            "Quality Assurance":      ["qa", "quality assurance", "test automation", "sdet", "selenium", "cypress"],
            "Site Reliability Engineering": ["sre", "site reliability", "error budget", "slo", "sli", "on-call"],
            "Data Science":           ["data analyst", "data scientist", "business intelligence", "tableau", "power bi"],
            "UI/UX Design":           ["ux", "ui design", "figma", "user experience", "user interface design", "wireframe"],
            "Digital Marketing":      ["seo", "sem", "ppc", "social media marketing", "content marketing", "google ads"],
            "Fintech":                ["fintech", "payment", "banking", "trading", "kyc", "aml"],
            "Healthcare Tech":        ["healthtech", "ehr", "emr", "hipaa", "medical software", "clinical"],
            "EdTech":                 ["edtech", "e-learning", "lms", "learning platform", "educational technology"],
        }
        for domain, boost_terms in domain_boosts.items():
            if any(_kw_hit(t, title) for t in boost_terms):
                domain_scores[domain] += 8
            if any(_kw_hit(t, desc) for t in boost_terms):
                domain_scores[domain] += 3

        # ── Boost 4: Sparse description guard ─────────────────────────────────
        # If description is very short, reduce noise from weak desc keyword hits
        if len(desc.split()) < 8:
            strong_keywords = ["full stack developer", "mobile developer", "android developer",
                               "ios developer", "flutter developer", "react native developer"]
            if not any(_kw_hit(k, title) or _kw_hit(k, desc) for k in strong_keywords):
                for domain in domain_scores:
                    desc_hits = sum(1 for kw in keywords[domain] if _kw_hit(kw, desc))
                    domain_scores[domain] = max(0, domain_scores[domain] - (desc_hits * WEIGHTS[domain] * 0.5))

        # ── Final selection ────────────────────────────────────────────────────
        if domain_scores:
            top_domain = max(domain_scores, key=domain_scores.get)
            top_score  = domain_scores[top_domain]
            if top_score >= 8:
                # Hard title overrides — explicit title is strongest signal
                title_overrides = [
                    ("full stack developer",         "Full Stack Development"),
                    ("full-stack developer",         "Full Stack Development"),
                    ("fullstack developer",          "Full Stack Development"),
                    ("frontend developer",           "Frontend Development"),
                    ("front end developer",          "Frontend Development"),
                    ("backend developer",            "Backend Development"),
                    ("back end developer",           "Backend Development"),
                    ("mobile developer",             "Mobile Development"),
                    ("android developer",            "Mobile Development"),
                    ("ios developer",                "Mobile Development"),
                    ("flutter developer",            "Mobile Development"),
                    ("react native developer",       "Mobile Development"),
                    ("data analyst",                 "Data Science"),
                    ("data scientist",               "Data Science"),
                    ("ml engineer",                  "AI/Machine Learning"),
                    ("ai engineer",                  "AI/Machine Learning"),
                    ("qa engineer",                  "Quality Assurance"),
                    ("test engineer",                "Quality Assurance"),
                    ("sdet",                         "Quality Assurance"),
                    ("devops engineer",              "DevOps/Infrastructure"),
                    ("cloud engineer",               "Cloud Engineering"),
                    ("sre",                          "Site Reliability Engineering"),
                    ("site reliability engineer",    "Site Reliability Engineering"),
                    ("security engineer",            "Cybersecurity"),
                    ("security analyst",             "Cybersecurity"),
                    ("penetration tester",           "Cybersecurity"),
                    ("ux designer",                  "UI/UX Design"),
                    ("ui designer",                  "UI/UX Design"),
                    ("product manager",              "Product Management"),
                    ("project manager",              "Project Management"),
                    ("business analyst",             "Business Analysis"),
                    ("scrum master",                 "Agile Coaching"),
                    ("technical writer",             "Technical Writing"),
                    ("blockchain developer",         "Blockchain Development"),
                    ("game developer",               "Game Development"),
                    ("embedded engineer",            "Embedded Systems"),
                    ("firmware engineer",            "Embedded Systems"),
                    ("iot engineer",                 "IoT Development"),
                    ("network engineer",             "Networking"),
                    ("database administrator",       "Database Management"),
                ]
                for kw, domain in title_overrides:
                    if _kw_hit(kw, title):
                        return domain
                return top_domain
        return "Unclassified"

    def get_domain_similarity(self, resume_domain: str, job_domain: str) -> float:
        resume_domain = resume_domain.strip().lower()
        job_domain    = job_domain.strip().lower()

        normalization = {
            "frontend": "frontend development", "backend": "backend development",
            "fullstack": "full stack development", "full-stack": "full stack development",
            "ui/ux": "ui/ux design", "ux/ui": "ui/ux design",
            "software developer": "software engineering",
            "mobile developer": "mobile development",
            "android developer": "mobile development",
            "ios developer": "mobile development",
            "ai": "ai/machine learning", "machine learning": "ai/machine learning",
            "ml": "ai/machine learning", "artificial intelligence": "ai/machine learning",
            "cloud": "cloud engineering", "cloud engineer": "cloud engineering",
            "devops": "devops/infrastructure", "devops engineer": "devops/infrastructure",
            "cyber security": "cybersecurity", "cybersecurity engineer": "cybersecurity",
            "security analyst": "cybersecurity", "qa": "quality assurance",
            "test engineer": "quality assurance", "sre": "site reliability engineering",
            "dba": "database management", "database administrator": "database management",
            "product manager": "product management", "project manager": "project management",
            "business analyst": "business analysis", "technical writer": "technical writing",
            "game developer": "game development", "blockchain developer": "blockchain development",
        }
        resume_domain = normalization.get(resume_domain, resume_domain)
        job_domain    = normalization.get(job_domain, job_domain)

        similarity_map = {
            ("full stack development", "frontend development"): 0.85,
            ("full stack development", "backend development"): 0.85,
            ("full stack development", "ui/ux design"): 0.70,
            ("full stack development", "mobile development"): 0.65,
            ("full stack development", "software engineering"): 0.80,
            ("frontend development", "ui/ux design"): 0.90,
            ("frontend development", "mobile development"): 0.70,
            ("frontend development", "software engineering"): 0.75,
            ("frontend development", "backend development"): 0.60,
            ("backend development", "database management"): 0.80,
            ("backend development", "cloud engineering"): 0.75,
            ("backend development", "devops/infrastructure"): 0.70,
            ("backend development", "system architecture"): 0.85,
            ("backend development", "software engineering"): 0.80,
            ("data science", "ai/machine learning"): 0.95,
            ("data science", "business analysis"): 0.70,
            ("ai/machine learning", "data science"): 0.95,
            ("ai/machine learning", "software engineering"): 0.65,
            ("cloud engineering", "devops/infrastructure"): 0.90,
            ("cloud engineering", "system architecture"): 0.80,
            ("cloud engineering", "site reliability engineering"): 0.85,
            ("devops/infrastructure", "site reliability engineering"): 0.90,
            ("devops/infrastructure", "system architecture"): 0.75,
            ("cybersecurity", "devops/infrastructure"): 0.70,
            ("cybersecurity", "cloud engineering"): 0.75,
            ("cybersecurity", "networking"): 0.80,
            ("cybersecurity", "system architecture"): 0.65,
            ("mobile development", "ui/ux design"): 0.75,
            ("mobile development", "software engineering"): 0.70,
            ("mobile development", "game development"): 0.60,
            ("quality assurance", "software engineering"): 0.75,
            ("quality assurance", "devops/infrastructure"): 0.65,
            ("quality assurance", "system architecture"): 0.60,
            ("product management", "business analysis"): 0.80,
            ("product management", "project management"): 0.75,
            ("project management", "agile coaching"): 0.85,
            ("business analysis", "data science"): 0.65,
            ("game development", "software engineering"): 0.70,
            ("blockchain development", "software engineering"): 0.70,
            ("blockchain development", "cybersecurity"): 0.65,
            ("embedded systems", "iot development"): 0.90,
            ("ar/vr development", "game development"): 0.80,
            ("ar/vr development", "mobile development"): 0.70,
            ("database management", "data science"): 0.75,
            ("database management", "system architecture"): 0.70,
            ("database management", "backend development"): 0.80,
            ("system architecture", "software engineering"): 0.85,
            ("system architecture", "cloud engineering"): 0.80,
            ("system architecture", "backend development"): 0.85,
            ("networking", "cybersecurity"): 0.80,
            ("networking", "devops/infrastructure"): 0.75,
            ("networking", "system architecture"): 0.70,
            ("fintech", "software engineering"): 0.70,
            ("fintech", "backend development"): 0.75,
            ("fintech", "cybersecurity"): 0.70,
            ("healthcare tech", "software engineering"): 0.70,
            ("edtech", "software engineering"): 0.70,
            ("e-commerce", "full stack development"): 0.80,
            ("e-commerce", "backend development"): 0.75,
            ("technical sales", "product management"): 0.65,
            ("technical writing", "business analysis"): 0.60,
            ("digital marketing", "business analysis"): 0.55,
            ("software engineering", "full stack development"): 0.80,
            ("software engineering", "frontend development"): 0.75,
            ("software engineering", "backend development"): 0.80,
            ("software engineering", "mobile development"): 0.70,
            ("software engineering", "game development"): 0.70,
            ("software engineering", "quality assurance"): 0.75,
        }

        if resume_domain == job_domain:
            return 1.0
        similarity = (similarity_map.get((resume_domain, job_domain)) or
                      similarity_map.get((job_domain, resume_domain)))
        if similarity:
            return similarity

        tech_domains           = {"software engineering","full stack development","frontend development",
                                   "backend development","mobile development","game development",
                                   "blockchain development","embedded systems","iot development"}
        data_domains           = {"data science","ai/machine learning","business analysis"}
        infrastructure_domains = {"cloud engineering","devops/infrastructure","site reliability engineering",
                                   "system architecture","database management","networking","cybersecurity"}
        management_domains     = {"product management","project management","business analysis","agile coaching"}
        design_domains         = {"ui/ux design","ar/vr development"}

        categories = [tech_domains, data_domains, infrastructure_domains, management_domains, design_domains]
        for category in categories:
            if resume_domain in category and job_domain in category:
                return 0.50
        if ((resume_domain in tech_domains and job_domain in infrastructure_domains) or
                (resume_domain in infrastructure_domains and job_domain in tech_domains)):
            return 0.45
        if ((resume_domain in data_domains and job_domain in tech_domains) or
                (resume_domain in tech_domains and job_domain in data_domains)):
            return 0.40
        return 0.25

    # ── CRUD operations ───────────────────────────────────────────────────────

    def insert_candidate(self, data: Tuple, job_title: str = "", job_description: str = "",
                         resume_text: str = "", resume_domain: str = "") -> int:
        try:
            local_tz   = pytz.timezone("Asia/Kolkata")
            local_time = datetime.now(local_tz).strftime("%Y-%m-%d %H:%M:%S")

            if resume_domain and resume_domain in self.VALID_DOMAINS:
                detected_domain = resume_domain
                logger.info(f"Domain used from pre-detected resume domain: '{detected_domain}'")
            else:
                detected_domain = self.detect_domain_from_title_and_description(
                    job_title, resume_text or job_description
                )
                logger.info(f"Domain fallback detected: '{detected_domain}'")

            if len(data) < 9:
                raise ValueError(f"Expected at least 9 data fields, got {len(data)}")

            resume_name    = data[0]
            candidate_name = data[1]
            ats_score      = data[2]
            edu_score      = data[3]
            exp_score      = data[4]
            skills_score   = data[5]
            lang_score     = data[6]
            keyword_score  = data[7]
            bias_score     = data[8]
            format_score   = int(data[9]) if len(data) >= 10 else 0

            for name, val in [
                ("ats_score", ats_score), ("edu_score", edu_score),
                ("exp_score", exp_score), ("skills_score", skills_score),
                ("lang_score", lang_score), ("keyword_score", keyword_score),
                ("format_score", format_score),
            ]:
                if not isinstance(val, (int, float)) or not (0 <= val <= 100):
                    raise ValueError(f"{name} must be between 0 and 100, got {val}")

            if not isinstance(bias_score, (int, float)) or not (0.0 <= bias_score <= 1.0):
                raise ValueError(f"Bias score must be between 0.0 and 1.0, got {bias_score}")

            sql = """
                INSERT INTO candidates (
                    resume_name, candidate_name, ats_score, edu_score, exp_score,
                    skills_score, lang_score, keyword_score, format_score, bias_score,
                    domain, timestamp
                ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                RETURNING id
            """
            params = (
                resume_name, candidate_name, ats_score, edu_score, exp_score,
                skills_score, lang_score, keyword_score, format_score, bias_score,
                detected_domain, local_time,
            )
            row          = self._execute(sql, params, fetch="one")
            candidate_id = row["id"] if row else None
            logger.info(f"Inserted candidate with ID: {candidate_id}")
            return candidate_id
        except Exception as e:
            logger.error(f"Error inserting candidate: {e}")
            raise

    def get_top_domains_by_score(self, limit: int = 5) -> List[Tuple]:
        try:
            sql = """
                SELECT domain, ROUND(AVG(ats_score)::numeric, 2) AS avg_score, COUNT(*) AS count
                FROM candidates
                GROUP BY domain
                HAVING COUNT(*) >= 1
                ORDER BY avg_score DESC
                LIMIT %s
            """
            rows = self._execute(sql, (limit,), fetch="all")
            return [(r["domain"], float(r["avg_score"]), r["count"]) for r in (rows or [])]
        except Exception as e:
            logger.error(f"Error getting top domains: {e}")
            return []

    def get_resume_count_by_day(self) -> pd.DataFrame:
        try:
            sql = """
                SELECT DATE(timestamp) AS day, COUNT(*) AS count
                FROM candidates
                GROUP BY DATE(timestamp)
                ORDER BY DATE(timestamp) DESC
                LIMIT 365
            """
            return self._read_df(sql)
        except Exception as e:
            logger.error(f"Error getting resume count by day: {e}")
            return pd.DataFrame()

    def get_average_ats_by_domain(self) -> pd.DataFrame:
        try:
            sql = """
                SELECT domain,
                       ROUND(AVG(ats_score)::numeric, 2) AS avg_ats_score,
                       COUNT(*) AS candidate_count
                FROM candidates
                GROUP BY domain
                HAVING COUNT(*) >= 1
                ORDER BY avg_ats_score DESC
            """
            return self._read_df(sql)
        except Exception as e:
            logger.error(f"Error getting average ATS by domain: {e}")
            return pd.DataFrame()

    def get_domain_distribution(self) -> pd.DataFrame:
        try:
            sql = """
                SELECT domain,
                       COUNT(*) AS count,
                       ROUND(COUNT(*) * 100.0 / (SELECT COUNT(*) FROM candidates), 2) AS percentage
                FROM candidates
                GROUP BY domain
                ORDER BY count DESC
            """
            return self._read_df(sql)
        except Exception as e:
            logger.error(f"Error getting domain distribution: {e}")
            return pd.DataFrame()

    def filter_candidates_by_date(self, start: str, end: str) -> pd.DataFrame:
        try:
            datetime.strptime(start, '%Y-%m-%d')
            datetime.strptime(end, '%Y-%m-%d')
            sql = """
                SELECT * FROM candidates
                WHERE DATE(timestamp) BETWEEN %s AND %s
                ORDER BY timestamp DESC
            """
            return self._read_df(sql, params=(start, end))
        except ValueError as e:
            logger.error(f"Invalid date format: {e}")
            return pd.DataFrame()
        except Exception as e:
            logger.error(f"Error filtering candidates by date: {e}")
            return pd.DataFrame()

    def delete_candidate_by_id(self, candidate_id: int) -> bool:
        try:
            sql = "DELETE FROM candidates WHERE id = %s"
            with self.get_connection() as conn:
                with conn.cursor() as cur:
                    cur.execute(sql, (candidate_id,))
                    deleted = cur.rowcount
            if deleted > 0:
                logger.info(f"Deleted candidate with ID: {candidate_id}")
                return True
            logger.warning(f"No candidate found with ID: {candidate_id}")
            return False
        except Exception as e:
            logger.error(f"Error deleting candidate: {e}")
            return False

    def get_all_candidates(self, bias_threshold: Optional[float] = None,
                           min_ats: Optional[int] = None,
                           limit: Optional[int] = None,
                           offset: int = 0) -> pd.DataFrame:
        try:
            sql    = "SELECT * FROM candidates WHERE 1=1"
            params: list = []
            if bias_threshold is not None:
                sql += " AND bias_score >= %s"
                params.append(bias_threshold)
            if min_ats is not None:
                sql += " AND ats_score >= %s"
                params.append(min_ats)
            sql += " ORDER BY timestamp DESC"
            if limit is not None:
                sql += " LIMIT %s OFFSET %s"
                params.extend([limit, offset])
            return self._read_df(sql, params=params if params else None)
        except Exception as e:
            logger.error(f"Error getting all candidates: {e}")
            return pd.DataFrame()

    def export_to_csv(self, filepath: str = "candidates_export.csv",
                      filters: Optional[Dict[str, Any]] = None) -> bool:
        try:
            sql    = "SELECT * FROM candidates WHERE 1=1"
            params: list = []
            if filters:
                if 'min_ats' in filters:
                    sql += " AND ats_score >= %s"
                    params.append(filters['min_ats'])
                if 'domain' in filters:
                    sql += " AND domain = %s"
                    params.append(filters['domain'])
                if 'start_date' in filters:
                    sql += " AND DATE(timestamp) >= %s"
                    params.append(filters['start_date'])
                if 'end_date' in filters:
                    sql += " AND DATE(timestamp) <= %s"
                    params.append(filters['end_date'])
            sql += " ORDER BY timestamp DESC"
            df = self._read_df(sql, params=params if params else None)
            df.to_csv(filepath, index=False)
            logger.info(f"Exported {len(df)} records to {filepath}")
            return True
        except Exception as e:
            logger.error(f"Error exporting to CSV: {e}")
            return False

    def get_candidate_by_id(self, candidate_id: int) -> pd.DataFrame:
        try:
            return self._read_df("SELECT * FROM candidates WHERE id = %s",
                                 params=(candidate_id,))
        except Exception as e:
            logger.error(f"Error getting candidate by ID: {e}")
            return pd.DataFrame()

    def get_bias_distribution(self, threshold: float = 0.6) -> pd.DataFrame:
        try:
            if not (0.0 <= threshold <= 1.0):
                raise ValueError("Threshold must be between 0.0 and 1.0")
            sql = """
                SELECT
                    CASE WHEN bias_score >= %s THEN 'Biased' ELSE 'Fair' END AS bias_category,
                    COUNT(*) AS count,
                    ROUND(COUNT(*) * 100.0 / (SELECT COUNT(*) FROM candidates), 2) AS percentage
                FROM candidates
                GROUP BY bias_category
            """
            return self._read_df(sql, params=(threshold,))
        except Exception as e:
            logger.error(f"Error getting bias distribution: {e}")
            return pd.DataFrame()

    def get_daily_ats_stats(self, days_limit: int = 90) -> pd.DataFrame:
        try:
            sql = f"""
                SELECT DATE(timestamp) AS date,
                       ROUND(AVG(ats_score)::numeric, 2) AS avg_ats,
                       COUNT(*) AS daily_count
                FROM candidates
                WHERE DATE(timestamp) >= CURRENT_DATE - INTERVAL '{days_limit} days'
                GROUP BY DATE(timestamp)
                ORDER BY DATE(timestamp)
            """
            return self._read_df(sql)
        except Exception as e:
            logger.error(f"Error getting daily ATS stats: {e}")
            return pd.DataFrame()

    def get_flagged_candidates(self, threshold: float = 0.6) -> pd.DataFrame:
        try:
            if not (0.0 <= threshold <= 1.0):
                raise ValueError("Threshold must be between 0.0 and 1.0")
            sql = """
                SELECT resume_name, candidate_name, ats_score, bias_score, domain, timestamp
                FROM candidates
                WHERE bias_score > %s
                ORDER BY bias_score DESC
            """
            return self._read_df(sql, params=(threshold,))
        except Exception as e:
            logger.error(f"Error getting flagged candidates: {e}")
            return pd.DataFrame()

    def get_domain_performance_stats(self) -> pd.DataFrame:
        try:
            sql = """
                SELECT
                    domain,
                    COUNT(*) AS total_candidates,
                    ROUND(AVG(ats_score)::numeric, 2)     AS avg_ats_score,
                    ROUND(AVG(edu_score)::numeric, 2)     AS avg_edu_score,
                    ROUND(AVG(exp_score)::numeric, 2)     AS avg_exp_score,
                    ROUND(AVG(skills_score)::numeric, 2)  AS avg_skills_score,
                    ROUND(AVG(lang_score)::numeric, 2)    AS avg_lang_score,
                    ROUND(AVG(keyword_score)::numeric, 2) AS avg_keyword_score,
                    ROUND(AVG(format_score)::numeric, 2)  AS avg_format_score,
                    ROUND(AVG(bias_score)::numeric, 3)    AS avg_bias_score,
                    MAX(ats_score) AS max_ats_score,
                    MIN(ats_score) AS min_ats_score,
                    ROUND((MAX(ats_score) - MIN(ats_score))::numeric, 2) AS score_range
                FROM candidates
                GROUP BY domain
                HAVING COUNT(*) >= 1
                ORDER BY avg_ats_score DESC
            """
            return self._read_df(sql)
        except Exception as e:
            logger.error(f"Error getting domain performance stats: {e}")
            return pd.DataFrame()

    def analyze_domain_transitions(self) -> pd.DataFrame:
        try:
            sql = """
                SELECT
                    domain,
                    COUNT(*) AS frequency,
                    ROUND(AVG(ats_score)::numeric, 2)  AS avg_performance,
                    ROUND(AVG(bias_score)::numeric, 3) AS avg_bias,
                    ROUND(COUNT(*) * 100.0 / (SELECT COUNT(*) FROM candidates), 2) AS percentage
                FROM candidates
                GROUP BY domain
                HAVING COUNT(*) >= 1
                ORDER BY frequency DESC
            """
            return self._read_df(sql)
        except Exception as e:
            logger.error(f"Error analyzing domain transitions: {e}")
            return pd.DataFrame()

    def get_database_stats(self) -> Dict[str, Any]:
        try:
            conn = _get_fresh_cursor()
            with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
                cur.execute("SELECT COUNT(*) AS cnt FROM candidates")
                total_candidates = cur.fetchone()["cnt"]

                cur.execute("""
                    SELECT
                        ROUND(AVG(ats_score)::numeric, 2)  AS avg_ats,
                        ROUND(AVG(bias_score)::numeric, 3) AS avg_bias,
                        COUNT(DISTINCT domain)             AS unique_domains
                    FROM candidates
                """)
                avg_stats = cur.fetchone()

                cur.execute("""
                    SELECT
                        MIN(DATE(timestamp)) AS earliest_date,
                        MAX(DATE(timestamp)) AS latest_date
                    FROM candidates
                """)
                date_range = cur.fetchone()
            # No commit needed for SELECT-only block
            return {
                'total_candidates': total_candidates,
                'avg_ats_score':    float(avg_stats["avg_ats"])  if avg_stats["avg_ats"]  else 0,
                'avg_bias_score':   float(avg_stats["avg_bias"]) if avg_stats["avg_bias"] else 0,
                'unique_domains':   avg_stats["unique_domains"]  if avg_stats["unique_domains"] else 0,
                'earliest_date':    str(date_range["earliest_date"]) if date_range["earliest_date"] else None,
                'latest_date':      str(date_range["latest_date"])   if date_range["latest_date"]   else None,
                'database_size_mb': 0,
            }
        except Exception as e:
            logger.error(f"Error getting database stats: {e}")
            return {}

    def cleanup_old_records(self, days_to_keep: int = 365) -> int:
        try:
            sql = f"DELETE FROM candidates WHERE DATE(timestamp) < CURRENT_DATE - INTERVAL '{days_to_keep} days'"
            with self.get_connection() as conn:
                with conn.cursor() as cur:
                    cur.execute(sql)
                    deleted = cur.rowcount
            if deleted > 0:
                logger.info(f"Cleaned up {deleted} old records")
            return deleted
        except Exception as e:
            logger.error(f"Error cleaning up old records: {e}")
            return 0

    def close_all_connections(self):
        """No-op: connection lifecycle is managed by the module-level holder."""
        logger.info("close_all_connections called — connection managed by module-level holder.")


# ── Global instance (backward compatibility) ─────────────────────────────────
db_manager = DatabaseManager()


# ── Module-level wrappers (backward compatibility) ────────────────────────────
def detect_domain_from_title_and_description(job_title: str, job_description: str) -> str:
    return db_manager.detect_domain_from_title_and_description(job_title, job_description)

def get_domain_similarity(resume_domain: str, job_domain: str) -> float:
    return db_manager.get_domain_similarity(resume_domain, job_domain)

def insert_candidate(data: tuple, job_title: str = "", job_description: str = "",
                     resume_text: str = "", resume_domain: str = ""):
    return db_manager.insert_candidate(data, job_title, job_description, resume_text, resume_domain)

def get_top_domains_by_score(limit: int = 5) -> list:
    return db_manager.get_top_domains_by_score(limit)

def get_resume_count_by_day():
    return db_manager.get_resume_count_by_day()

def get_average_ats_by_domain():
    return db_manager.get_average_ats_by_domain()

def get_domain_distribution():
    return db_manager.get_domain_distribution()

def filter_candidates_by_date(start: str, end: str):
    return db_manager.filter_candidates_by_date(start, end)

def delete_candidate_by_id(candidate_id: int):
    return db_manager.delete_candidate_by_id(candidate_id)

def get_all_candidates(bias_threshold: float = None, min_ats: int = None):
    return db_manager.get_all_candidates(bias_threshold, min_ats)

def export_to_csv(filepath: str = "candidates_export.csv"):
    return db_manager.export_to_csv(filepath)

def get_candidate_by_id(candidate_id: int):
    return db_manager.get_candidate_by_id(candidate_id)

def get_bias_distribution(threshold: float = 0.6):
    return db_manager.get_bias_distribution(threshold)

def get_daily_ats_stats(days_limit: int = 90):
    return db_manager.get_daily_ats_stats(days_limit)

def get_flagged_candidates(threshold: float = 0.6):
    return db_manager.get_flagged_candidates(threshold)

def get_domain_performance_stats():
    return db_manager.get_domain_performance_stats()

def analyze_domain_transitions():
    return db_manager.analyze_domain_transitions()

def get_database_stats():
    return db_manager.get_database_stats()

def cleanup_old_records(days_to_keep: int = 365):
    return db_manager.cleanup_old_records(days_to_keep)

def close_all_connections():
    return db_manager.close_all_connections()


if __name__ == "__main__":
    print("Database Manager (Supabase PostgreSQL) initialised successfully!")
    stats = get_database_stats()
    print(f"Database Statistics: {stats}")
