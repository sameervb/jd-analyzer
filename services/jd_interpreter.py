"""
services/jd_interpreter.py — Parse raw JD text into structured data.
Extracted from Soul Spark career_jd_interpreter.py.
"""
from __future__ import annotations

import re
from typing import Any

from services.career_common import (
    collect_skill_mentions,
    infer_domains,
    infer_role_families,
    infer_seniority,
    normalize_whitespace,
    slugify,
    split_lines,
)


def _section_slice(text: str, heading_patterns: tuple[str, ...]) -> str:
    pattern = r"|".join(re.escape(p) for p in heading_patterns)
    match = re.search(
        rf"(?:^|\n)\s*(?:{pattern})\s*:?\s*\n(?P<body>[\s\S]*?)(?=\n\s*(?:responsibilities|requirements|preferred|nice to have|about you|about the role|benefits|location|work mode)\s*:?\s*\n|\Z)",
        text,
        re.I,
    )
    return normalize_whitespace(match.group("body")) if match else ""


def interpret_jd(jd_text: str) -> dict[str, Any]:
    """Parse a raw job description string into a structured dict."""
    text = str(jd_text or "")
    lines = split_lines(text)
    title = lines[0] if lines else ""
    title = re.sub(r"\s*\|\s*.*$", "", title)

    must_have_section = _section_slice(text, ("requirements", "must have", "what you bring", "about you"))
    nice_to_have_section = _section_slice(text, ("nice to have", "preferred qualifications", "bonus"))
    responsibilities_section = _section_slice(text, ("responsibilities", "what you will do", "what you'll do"))

    must_have_skills = collect_skill_mentions(must_have_section or text[:2000])
    nice_to_have_skills = [s for s in collect_skill_mentions(nice_to_have_section) if s not in must_have_skills]
    keywords = list(dict.fromkeys(
        collect_skill_mentions(text)
        + [w for w in re.findall(r"\b[A-Za-z][A-Za-z0-9+#.-]{3,}\b", text)[:20]]
    ))

    seniority = infer_seniority(titles=[title], years_experience=0.0)
    role_families = infer_role_families([title, must_have_section, responsibilities_section])
    domains = infer_domains([title, must_have_section, responsibilities_section])

    lower = text.lower()
    if "hybrid" in lower:
        work_mode = "hybrid"
    elif "remote" in lower:
        work_mode = "remote"
    elif "on-site" in lower or "onsite" in lower or "office" in lower:
        work_mode = "onsite"
    else:
        work_mode = ""

    location_match = re.search(r"(?:location|based in)\s*:?\s*([A-Za-z ,/-]{3,80})", text, re.I)
    compensation_match = re.search(r"([$€£]\s?\d[\d,.\-kK ]+)", text)
    experience_requirements = re.findall(r"\b\d+\+?\s+years?[^.\n]{0,80}", text, re.I)
    education_requirements = re.findall(r"\b(?:bachelor|master|mba|phd|degree|certification)[^.\n]{0,80}", text, re.I)

    responsibilities = []
    if responsibilities_section:
        responsibilities = [l for l in re.split(r"[\n•\-]+", responsibilities_section) if normalize_whitespace(l)]

    return {
        "jd_id": slugify(title or "job-description", prefix="jd"),
        "target_role": title,
        "seniority": seniority,
        "role_family": role_families[0] if role_families else "",
        "role_families": role_families,
        "must_have_skills": must_have_skills,
        "nice_to_have_skills": nice_to_have_skills,
        "responsibilities": responsibilities[:12],
        "domain_context": domains[:4],
        "experience_requirements": experience_requirements[:6],
        "education_requirements": education_requirements[:4],
        "location": normalize_whitespace(location_match.group(1)) if location_match else "",
        "work_mode": work_mode,
        "compensation": compensation_match.group(1) if compensation_match else "",
        "keywords": keywords[:30],
        "raw_text": text,
        "confidence": 0.85 if title and (must_have_skills or responsibilities) else 0.6,
    }
