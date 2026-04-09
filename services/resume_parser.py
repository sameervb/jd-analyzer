"""
services/resume_parser.py — Parse resume text into structured profile.
Extracted from Soul Spark career_resume_parser.py.
Supports plain text input; PDF/DOCX extraction handled in app.py.
"""
from __future__ import annotations

import re
from collections import Counter, defaultdict
from typing import Any

from services.career_common import (
    clamp,
    collect_skill_mentions,
    extract_numeric_markers,
    has_quantified_evidence,
    infer_domains,
    infer_management_orientation,
    infer_role_families,
    infer_seniority,
    infer_skill_cluster,
    iso_date,
    mean,
    months_between,
    normalize_skill_name,
    normalize_whitespace,
    parse_fuzzy_date,
    slugify,
    split_lines,
)


SECTION_PATTERNS: dict[str, tuple[str, ...]] = {
    "summary": ("summary", "profile", "about", "professional summary", "objective"),
    "experience": ("experience", "work experience", "professional experience", "employment history"),
    "skills": ("skills", "technical skills", "core skills", "expertise", "technologies", "tools"),
    "education": ("education", "academic background"),
    "projects": ("projects", "key projects", "selected projects", "portfolio"),
    "certifications": ("certifications", "licenses", "credentials"),
}

TITLE_HINTS = (
    "engineer", "analyst", "scientist", "manager", "director", "lead",
    "architect", "specialist", "consultant", "product", "developer",
    "program", "business intelligence",
)
COMPANY_HINTS = ("inc", "ltd", "llc", "gmbh", "corp", "company", "technologies", "solutions", "labs")
DEGREE_HINTS = ("bachelor", "master", "mba", "phd", "b.tech", "btech", "bsc", "msc", "university", "college")
CERT_HINTS = ("certified", "certification", "certificate", "coursera", "aws", "azure", "gcp", "pmp", "scrum")

DATE_RANGE_RE = re.compile(
    r"(?P<start>(?:\d{1,2}[/-])?(?:[A-Za-z]{3,9}\s+)?\d{4})\s*(?:-|–|—|to)\s*(?P<end>Present|Current|Now|(?:\d{1,2}[/-])?(?:[A-Za-z]{3,9}\s+)?\d{4})",
    re.I,
)
URL_RE = re.compile(r"(https?://\S+|www\.\S+|github\.com/\S+|portfolio\S*)", re.I)


def _detect_sections(lines: list[str]) -> list[dict[str, Any]]:
    headings: list[dict[str, Any]] = []
    for idx, line in enumerate(lines):
        lower = line.lower().strip(": ")
        if len(lower) > 40:
            continue
        for section_type, patterns in SECTION_PATTERNS.items():
            if any(lower == p or lower.startswith(f"{p}:") for p in patterns):
                headings.append({"section_type": section_type, "heading": line, "start_line": idx, "heading_confidence": 0.95})
                break

    if not headings:
        return [{"section_id": "resume-section-all", "section_type": "unstructured", "heading": "Unstructured Resume",
                 "start_line": 0, "end_line": max(0, len(lines) - 1), "confidence": 0.4 if lines else 0.0, "text": "\n".join(lines)}]

    sections: list[dict[str, Any]] = []
    for i, heading in enumerate(headings):
        start = heading["start_line"]
        end = headings[i + 1]["start_line"] - 1 if i + 1 < len(headings) else len(lines) - 1
        body_lines = lines[start + 1: end + 1]
        sections.append({
            "section_id": slugify(f"{heading['section_type']}-{i + 1}", prefix="resume-section"),
            "section_type": heading["section_type"],
            "heading": heading["heading"],
            "start_line": start,
            "end_line": end,
            "confidence": heading["heading_confidence"],
            "text": "\n".join(body_lines),
            "line_count": len(body_lines),
        })

    first_heading = headings[0]["start_line"]
    if first_heading > 0:
        top_lines = lines[:first_heading]
        sections.insert(0, {
            "section_id": "resume-section-header",
            "section_type": "header",
            "heading": "Header",
            "start_line": 0,
            "end_line": first_heading - 1,
            "confidence": 0.8,
            "text": "\n".join(top_lines),
            "line_count": len(top_lines),
        })
    return sections


def _infer_summary(lines: list[str], sections: list[dict[str, Any]]) -> str:
    summary_section = next((s for s in sections if s["section_type"] == "summary"), None)
    if summary_section and summary_section["text"].strip():
        return normalize_whitespace(summary_section["text"])[:800]
    header = next((s for s in sections if s["section_type"] == "header"), None)
    if not header:
        return ""
    summary_lines = [
        line for line in split_lines(header["text"])
        if len(line) > 30 and not DATE_RANGE_RE.search(line) and not URL_RE.search(line)
    ]
    return normalize_whitespace(" ".join(summary_lines[:3]))[:800]


def _classify_title_company(candidates: list[str]) -> tuple[str, str]:
    title = ""
    company = ""
    for candidate in candidates:
        lower = candidate.lower()
        if not title and any(hint in lower for hint in TITLE_HINTS):
            title = candidate
            continue
        if not company and (any(hint in lower for hint in COMPANY_HINTS) or (candidate.istitle() and len(candidate.split()) <= 5)):
            company = candidate
    if not title and candidates:
        title = candidates[0]
    if not company and len(candidates) > 1:
        company = candidates[1]
    return title, company


def _extract_experience_entries(lines: list[str], sections: list[dict[str, Any]]) -> tuple[list, list, list]:
    exp_section = next((s for s in sections if s["section_type"] == "experience"), None)
    search_lines = split_lines(exp_section["text"]) if exp_section else lines
    line_offset = (exp_section or {}).get("start_line", 0) + (1 if exp_section else 0)
    date_indices = [i for i, line in enumerate(search_lines) if DATE_RANGE_RE.search(line)]

    entries, bullets, achievements = [], [], []

    for idx, start_i in enumerate(date_indices):
        end_i = date_indices[idx + 1] if idx + 1 < len(date_indices) else len(search_lines)
        chunk = search_lines[max(0, start_i - 2): end_i]
        date_line = search_lines[start_i]
        match = DATE_RANGE_RE.search(date_line)
        if not match:
            continue

        prefix = normalize_whitespace(date_line[: match.start()])
        candidates = [line for line in chunk[:3] if line and line != date_line]
        if prefix:
            candidates.insert(0, prefix)
        title, company = _classify_title_company(candidates)

        location = ""
        if "|" in date_line:
            parts = [normalize_whitespace(p) for p in date_line.split("|") if normalize_whitespace(p)]
            if len(parts) >= 2:
                location = parts[-1]

        entry_id = slugify(f"{company}-{title}-{idx + 1}", prefix="exp")
        start_text = match.group("start")
        end_text = match.group("end")
        duration_months = months_between(start_text, end_text)

        body_lines = []
        for body_line in search_lines[start_i + 1: end_i]:
            if DATE_RANGE_RE.search(body_line):
                break
            if body_line:
                body_lines.append(body_line)

        responsibilities_list, achievement_lines = [], []
        for bi, body_line in enumerate(body_lines):
            normalized = normalize_whitespace(body_line)
            if len(normalized) < 8:
                continue
            bullet_id = slugify(f"{entry_id}-{len(bullets) + 1}", prefix="bullet")
            bullet = {
                "bullet_id": bullet_id,
                "experience_entry_id": entry_id,
                "text": normalized,
                "has_quantified_evidence": has_quantified_evidence(normalized),
            }
            bullets.append(bullet)
            if bullet["has_quantified_evidence"]:
                achievement_lines.append(normalized)
                achievements.append({
                    "achievement_id": slugify(f"{entry_id}-{len(achievements) + 1}", prefix="achievement"),
                    "experience_entry_id": entry_id,
                    "summary": normalized,
                    "quantified_markers": extract_numeric_markers(normalized),
                    "source_snippet": normalized[:220],
                    "confidence": 0.9,
                })
            else:
                responsibilities_list.append(normalized)

        entries.append({
            "experience_entry_id": entry_id,
            "title": title,
            "company": company,
            "location": location,
            "start_date": iso_date(start_text),
            "end_date": iso_date(end_text),
            "is_current": end_text.lower() in {"present", "current", "now"},
            "duration_months": duration_months,
            "responsibilities": responsibilities_list[:8],
            "achievements": achievement_lines[:6],
            "confidence": clamp(mean([0.9 if title else 0.5, 0.8 if company else 0.45, 0.85 if duration_months is not None else 0.4])),
        })

    entries.sort(key=lambda e: e.get("start_date") or "", reverse=True)
    return entries, bullets, achievements


def _extract_education(lines: list[str], sections: list[dict[str, Any]]) -> list[dict[str, Any]]:
    edu_section = next((s for s in sections if s["section_type"] == "education"), None)
    search_lines = split_lines(edu_section["text"]) if edu_section else lines
    rows = []
    for i, line in enumerate(search_lines):
        if not any(h in line.lower() for h in DEGREE_HINTS):
            continue
        year_match = re.search(r"\b(19|20)\d{2}\b", line)
        rows.append({
            "degree": line,
            "institution": search_lines[i + 1] if i + 1 < len(search_lines) and len(search_lines[i + 1]) <= 120 else "",
            "graduation_year": year_match.group(0) if year_match else "",
        })
    return rows[:8]


def _extract_skill_inventory(
    lines: list[str],
    sections: list[dict[str, Any]],
    experience_entries: list[dict[str, Any]],
    projects: list[dict[str, Any]],
    bullet_evidence: list[dict[str, Any]],
) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    skill_section = next((s for s in sections if s["section_type"] == "skills"), None)
    explicit_skill_mentions: list[str] = []
    if skill_section:
        chunks = re.split(r"[,\n|/;]", skill_section["text"])
        explicit_skill_mentions = [normalize_skill_name(c) for c in chunks if normalize_skill_name(c)]

    evidence_map: dict[str, dict] = defaultdict(lambda: {"evidence_refs": [], "explicit_mentions": 0, "inferred_mentions": 0, "sources": set()})

    for skill_name, count in Counter(explicit_skill_mentions).items():
        evidence_map[skill_name]["explicit_mentions"] += count
        evidence_map[skill_name]["sources"].add("skills_section")

    for exp in experience_entries:
        text = " ".join([exp.get("title", ""), exp.get("company", "")] + list(exp.get("responsibilities", [])) + list(exp.get("achievements", [])))
        for skill_name in collect_skill_mentions(text):
            evidence_map[skill_name]["inferred_mentions"] += 1
            evidence_map[skill_name]["evidence_refs"].append(exp["experience_entry_id"])
            evidence_map[skill_name]["sources"].add("experience")

    for project in projects:
        for skill_name in list(project.get("technologies", [])) + collect_skill_mentions(project.get("name", "")):
            normalized = normalize_skill_name(skill_name)
            evidence_map[normalized]["inferred_mentions"] += 1
            evidence_map[normalized]["sources"].add("project")

    for bullet in bullet_evidence:
        for skill_name in collect_skill_mentions(bullet.get("text", "")):
            evidence_map[skill_name]["inferred_mentions"] += 1
            evidence_map[skill_name]["sources"].add("bullet")

    skills: list[dict[str, Any]] = []
    cluster_map: dict[str, list[str]] = defaultdict(list)

    for skill_name, data in sorted(evidence_map.items(), key=lambda x: (-x[1]["explicit_mentions"], -x[1]["inferred_mentions"], x[0])):
        cluster = infer_skill_cluster(skill_name)
        confidence = clamp(0.35 + (0.3 if data["explicit_mentions"] else 0.0) + min(0.35, 0.1 * len(set(data["evidence_refs"]))))
        skill_id = slugify(skill_name, prefix="skill")
        proficiency = "strong" if len(set(data["evidence_refs"])) >= 3 else "working" if data["explicit_mentions"] else "emerging"
        skills.append({
            "skill_id": skill_id,
            "normalized_name": skill_name,
            "category": cluster,
            "cluster": cluster,
            "evidence_refs": sorted(set(data["evidence_refs"]))[:8],
            "confidence": round(confidence, 3),
            "source": sorted(data["sources"]),
            "inferred_proficiency": proficiency,
        })
        cluster_map[cluster].append(skill_id)

    clusters: list[dict[str, Any]] = []
    for cluster_name, skill_ids in sorted(cluster_map.items()):
        member_skills = [s for s in skills if s["skill_id"] in skill_ids]
        clusters.append({
            "cluster_name": cluster_name,
            "skill_ids": skill_ids,
            "skill_names": [s["normalized_name"] for s in member_skills],
            "evidence_count": sum(len(s["evidence_refs"]) for s in member_skills),
            "confidence": round(mean([s["confidence"] for s in member_skills]), 3),
        })

    return skills, clusters


def parse_resume(resume_text: str) -> dict[str, Any]:
    """Parse raw resume text. Returns structured dict with profile, skills, experience."""
    text = str(resume_text or "")
    lines = split_lines(text)
    sections = _detect_sections(lines)
    summary = _infer_summary(lines, sections)
    experience_entries, bullet_evidence, achievement_evidence = _extract_experience_entries(lines, sections)
    education = _extract_education(lines, sections)

    # Simple project extraction
    projects = []
    proj_section = next((s for s in sections if s["section_type"] == "projects"), None)
    if proj_section:
        for i, line in enumerate(split_lines(proj_section["text"])):
            if URL_RE.search(line) or "project" in line.lower():
                proj_lines = split_lines(proj_section["text"])
                projects.append({
                    "project_id": slugify(f"project-{i}", prefix="project"),
                    "name": line[:120],
                    "description": proj_lines[i + 1] if i + 1 < len(proj_lines) else "",
                    "technologies": collect_skill_mentions(line),
                })

    skills, skill_clusters = _extract_skill_inventory(lines, sections, experience_entries, projects, bullet_evidence)

    titles = [e.get("title", "") for e in experience_entries if e.get("title")]
    total_months = sum(e.get("duration_months") or 0 for e in experience_entries)
    years_experience = round(total_months / 12, 1) if total_months else 0.0
    role_families = infer_role_families(titles + [summary])
    domains = infer_domains([summary] + titles)
    seniority = infer_seniority(titles=titles, years_experience=years_experience)
    management = infer_management_orientation(titles + [a.get("summary", "") for a in achievement_evidence])

    profile = {
        "professional_identity": titles[0] if titles else summary[:80],
        "summary": summary,
        "years_experience": years_experience,
        "seniority": seniority,
        "role_families": role_families,
        "domains": domains,
        "management_orientation": management,
        "top_achievements": [a["summary"] for a in achievement_evidence[:5]],
        "skill_count": len(skills),
        "experience_count": len(experience_entries),
    }

    missing_sections = [
        st for st in ("experience", "skills", "education")
        if not any(s["section_type"] == st for s in sections)
    ]

    completeness = clamp(mean([
        1.0 if summary else 0.35,
        1.0 if experience_entries else 0.25,
        1.0 if skills else 0.3,
        1.0 if education else 0.35,
        1.0 if achievement_evidence else 0.45,
    ]))

    return {
        "profile": profile,
        "skills": skills,
        "skill_clusters": skill_clusters,
        "experience_entries": experience_entries,
        "achievement_evidence": achievement_evidence,
        "bullet_evidence": bullet_evidence,
        "education": education,
        "projects": projects,
        "sections": sections,
        "diagnostics": {
            "missing_sections": missing_sections,
            "experience_count": len(experience_entries),
            "achievement_count": len(achievement_evidence),
            "skill_count": len(skills),
            "completeness": round(completeness, 2),
            "has_quantified_achievements": len(achievement_evidence) >= 2,
        },
    }
