"""
services/career_common.py — Shared parsing utilities for JD Analyzer.
Extracted from Soul Spark career_common.py (no external dependencies).
"""
from __future__ import annotations

import math
import re
from datetime import UTC, datetime
from typing import Any


_DATE_PATTERNS = (
    "%Y-%m-%d",
    "%d-%m-%Y",
    "%d/%m/%Y",
    "%m/%d/%Y",
    "%b %Y",
    "%B %Y",
    "%Y/%m/%d",
    "%Y.%m.%d",
    "%Y",
)

_MONTH_MAP = {
    "jan": 1, "feb": 2, "mar": 3, "apr": 4, "may": 5, "jun": 6,
    "jul": 7, "aug": 8, "sep": 9, "sept": 9, "oct": 10, "nov": 11, "dec": 12,
}

SKILL_CANONICAL_ALIASES: dict[str, tuple[str, ...]] = {
    "Python": ("python", "py"),
    "SQL": ("sql", "postgresql", "mysql", "tsql", "t-sql"),
    "AWS": ("aws", "amazon web services"),
    "Azure": ("azure", "microsoft azure"),
    "GCP": ("gcp", "google cloud", "google cloud platform"),
    "Snowflake": ("snowflake",),
    "Databricks": ("databricks",),
    "dbt": ("dbt", "data build tool"),
    "Airflow": ("airflow", "apache airflow"),
    "Looker": ("looker",),
    "Tableau": ("tableau",),
    "Power BI": ("power bi", "powerbi"),
    "Excel": ("excel", "microsoft excel"),
    "Streamlit": ("streamlit",),
    "Pandas": ("pandas",),
    "NumPy": ("numpy",),
    "Scikit-learn": ("scikit-learn", "sklearn"),
    "TensorFlow": ("tensorflow",),
    "PyTorch": ("pytorch",),
    "Machine Learning": ("machine learning", "ml"),
    "Generative AI": ("generative ai", "genai", "llm", "large language models"),
    "Data Engineering": ("data engineering", "etl", "elt", "data pipelines"),
    "Business Intelligence": ("business intelligence", "bi"),
    "Analytics Engineering": ("analytics engineering",),
    "Data Visualization": ("data visualization", "dashboarding", "dashboards"),
    "Product Analytics": ("product analytics",),
    "Experimentation": ("a/b testing", "ab testing", "experimentation"),
    "Stakeholder Management": ("stakeholder management", "stakeholder engagement"),
    "Project Management": ("project management", "program management"),
    "Leadership": ("leadership", "team leadership", "people leadership"),
    "Mentoring": ("mentoring", "coaching"),
    "Roadmapping": ("roadmap", "roadmapping"),
    "API Design": ("api", "apis", "api design", "rest api"),
    "Docker": ("docker",),
    "Kubernetes": ("kubernetes", "k8s"),
    "Git": ("git", "github", "gitlab"),
    "Jira": ("jira",),
}

SKILL_CLUSTER_MAP: dict[str, str] = {
    "Python": "Programming & Automation",
    "SQL": "Programming & Automation",
    "Pandas": "Programming & Automation",
    "NumPy": "Programming & Automation",
    "Git": "Engineering Workflow",
    "Docker": "Cloud & Infrastructure",
    "Kubernetes": "Cloud & Infrastructure",
    "AWS": "Cloud & Infrastructure",
    "Azure": "Cloud & Infrastructure",
    "GCP": "Cloud & Infrastructure",
    "Snowflake": "Data Platforms",
    "Databricks": "Data Platforms",
    "dbt": "Data Platforms",
    "Airflow": "Data Platforms",
    "Looker": "BI & Reporting",
    "Tableau": "BI & Reporting",
    "Power BI": "BI & Reporting",
    "Excel": "BI & Reporting",
    "Business Intelligence": "BI & Reporting",
    "Data Visualization": "BI & Reporting",
    "Machine Learning": "AI & Modeling",
    "Generative AI": "AI & Modeling",
    "Scikit-learn": "AI & Modeling",
    "TensorFlow": "AI & Modeling",
    "PyTorch": "AI & Modeling",
    "Data Engineering": "Data Strategy & Analytics",
    "Analytics Engineering": "Data Strategy & Analytics",
    "Product Analytics": "Data Strategy & Analytics",
    "Experimentation": "Data Strategy & Analytics",
    "Stakeholder Management": "Leadership & Delivery",
    "Project Management": "Leadership & Delivery",
    "Leadership": "Leadership & Delivery",
    "Mentoring": "Leadership & Delivery",
    "Roadmapping": "Leadership & Delivery",
    "Jira": "Leadership & Delivery",
    "API Design": "Product & Architecture",
}

ROLE_FAMILY_KEYWORDS: dict[str, tuple[str, ...]] = {
    "analytics": ("analyst", "analytics", "business intelligence", "bi", "insights"),
    "data_engineering": ("data engineer", "etl", "pipeline", "warehouse", "analytics engineer"),
    "data_science": ("data scientist", "machine learning", "ml", "modeling", "ai"),
    "product": ("product", "roadmap", "growth", "customer"),
    "engineering": ("engineer", "software", "platform", "backend", "frontend", "full stack"),
    "leadership": ("manager", "head", "director", "lead", "principal"),
    "program_delivery": ("program", "project", "delivery", "operations"),
}

SENIORITY_KEYWORDS: dict[str, tuple[str, ...]] = {
    "executive": ("vp", "vice president", "chief", "cto", "ceo", "cdo"),
    "director": ("director", "head of"),
    "manager": ("manager", "lead", "team lead", "people manager"),
    "principal": ("principal", "staff", "architect"),
    "senior": ("senior", "sr", "lead"),
    "mid": ("associate", "specialist", "analyst", "engineer"),
    "junior": ("junior", "intern", "trainee", "entry"),
}

LEADERSHIP_KEYWORDS = (
    "led", "managed", "mentored", "hired", "owned", "launched",
    "drove", "headed", "coached", "influenced",
)

DOMAIN_KEYWORDS: dict[str, tuple[str, ...]] = {
    "ecommerce": ("ecommerce", "marketplace", "retail"),
    "finance": ("finance", "fintech", "risk", "banking", "payments"),
    "cloud": ("cloud", "aws", "azure", "gcp"),
    "ai": ("ai", "machine learning", "llm", "nlp"),
    "analytics": ("analytics", "dashboard", "bi", "reporting"),
    "operations": ("operations", "supply chain", "logistics", "planning"),
}

SENIORITY_ORDER = ["junior", "mid", "senior", "principal", "manager", "director", "executive"]


def normalize_whitespace(value: Any) -> str:
    text = str(value or "")
    text = text.replace("\ufeff", "").replace("\xa0", " ")
    return re.sub(r"\s+", " ", text).strip()


def slugify(value: Any, *, prefix: str = "") -> str:
    text = normalize_whitespace(value).lower()
    text = re.sub(r"[^a-z0-9]+", "-", text).strip("-")
    if prefix:
        return f"{prefix}-{text or 'item'}"
    return text or "item"


def clean_line(line: Any) -> str:
    text = normalize_whitespace(line)
    return text.strip(" -\u2022\u2023\u25E6*")


def split_lines(text: Any) -> list[str]:
    return [clean_line(line) for line in str(text or "").splitlines() if clean_line(line)]


def parse_fuzzy_date(value: Any) -> datetime | None:
    if value is None:
        return None
    if isinstance(value, datetime):
        return value
    text = normalize_whitespace(value)
    if not text:
        return None
    lower = text.lower()
    if lower in {"present", "current", "now", "ongoing"}:
        return datetime.now(UTC).replace(tzinfo=None)
    for pattern in _DATE_PATTERNS:
        try:
            dt = datetime.strptime(text, pattern)
            if pattern == "%Y":
                return datetime(dt.year, 1, 1)
            return dt
        except Exception:
            continue
    match = re.search(r"\b([A-Za-z]{3,9})\s+(\d{4})\b", text)
    if match:
        month = _MONTH_MAP.get(match.group(1)[:3].lower(), 1)
        return datetime(int(match.group(2)), month, 1)
    match = re.search(r"\b(\d{1,2})[/-](\d{4})\b", text)
    if match:
        month = max(1, min(12, int(match.group(1))))
        return datetime(int(match.group(2)), month, 1)
    return None


def iso_date(value: Any) -> str:
    dt = parse_fuzzy_date(value)
    return dt.date().isoformat() if dt else ""


def months_between(start_value: Any, end_value: Any) -> int | None:
    start = parse_fuzzy_date(start_value)
    end = parse_fuzzy_date(end_value)
    if not start or not end:
        return None
    return max(0, (end.year - start.year) * 12 + (end.month - start.month))


def extract_numeric_markers(text: Any) -> list[str]:
    raw = str(text or "")
    return re.findall(
        r"(?:[$€£]\s?\d[\d,.]*[kKmMbB]?|\d+(?:\.\d+)?%|\d+\+?\s+(?:years?|months?|days?|people|stakeholders|countries|users|projects|teams))",
        raw,
    )


def has_quantified_evidence(text: Any) -> bool:
    return bool(extract_numeric_markers(text))


def clamp(value: float, low: float = 0.0, high: float = 1.0) -> float:
    return max(low, min(high, value))


def mean(values: list[float]) -> float:
    if not values:
        return 0.0
    return float(sum(values) / len(values))


def normalize_skill_name(value: Any) -> str:
    raw = normalize_whitespace(value)
    if not raw:
        return ""
    lower = raw.lower()
    for canonical, aliases in SKILL_CANONICAL_ALIASES.items():
        if lower == canonical.lower() or lower in aliases:
            return canonical
    for canonical, aliases in SKILL_CANONICAL_ALIASES.items():
        if any(alias in lower for alias in aliases):
            return canonical
    return raw.title() if raw.islower() else raw


def infer_skill_cluster(skill_name: Any) -> str:
    canonical = normalize_skill_name(skill_name)
    return SKILL_CLUSTER_MAP.get(canonical, "General Capability")


def collect_skill_mentions(text: Any) -> list[str]:
    haystack = str(text or "")
    found: list[str] = []
    lower = haystack.lower()
    for canonical, aliases in SKILL_CANONICAL_ALIASES.items():
        alias_set = (canonical.lower(),) + aliases
        if any(alias in lower for alias in alias_set):
            found.append(canonical)
    return list(dict.fromkeys(found))


def infer_role_families(texts: list[str]) -> list[str]:
    corpus = " ".join(normalize_whitespace(text) for text in texts if text).lower()
    scored: list[tuple[str, int]] = []
    for family, keywords in ROLE_FAMILY_KEYWORDS.items():
        score = sum(1 for keyword in keywords if keyword in corpus)
        if score:
            scored.append((family, score))
    scored.sort(key=lambda item: (-item[1], item[0]))
    return [name for name, _score in scored[:4]]


def infer_seniority(*, titles: list[str], years_experience: float = 0.0) -> str:
    joined = " ".join(normalize_whitespace(title) for title in titles if title).lower()
    for seniority, keywords in SENIORITY_KEYWORDS.items():
        if any(keyword in joined for keyword in keywords):
            return seniority
    if years_experience >= 12:
        return "principal"
    if years_experience >= 8:
        return "senior"
    if years_experience >= 4:
        return "mid"
    return "junior"


def infer_domains(texts: list[str]) -> list[dict[str, Any]]:
    corpus = " ".join(normalize_whitespace(text) for text in texts if text).lower()
    scored: list[dict[str, Any]] = []
    for domain, keywords in DOMAIN_KEYWORDS.items():
        hits = [keyword for keyword in keywords if keyword in corpus]
        if hits:
            scored.append({"domain": domain, "score": len(hits), "evidence_terms": hits[:5]})
    scored.sort(key=lambda item: (-item["score"], item["domain"]))
    return scored


def infer_management_orientation(texts: list[str]) -> str:
    corpus = " ".join(normalize_whitespace(text) for text in texts if text).lower()
    leadership_hits = sum(1 for keyword in LEADERSHIP_KEYWORDS if keyword in corpus)
    if leadership_hits >= 4:
        return "management_or_hybrid"
    if leadership_hits >= 2:
        return "hybrid"
    return "individual_contributor"


def safe_int(value: Any, default: int = 0) -> int:
    try:
        if value is None:
            return default
        if isinstance(value, float) and math.isnan(value):
            return default
        return int(float(value))
    except Exception:
        return default


def safe_float(value: Any, default: float = 0.0) -> float:
    try:
        if value is None:
            return default
        if isinstance(value, float) and math.isnan(value):
            return default
        return float(value)
    except Exception:
        return default
