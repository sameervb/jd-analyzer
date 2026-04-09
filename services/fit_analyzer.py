"""
services/fit_analyzer.py — Compare parsed resume vs parsed JD.
Produces fit score, skill gaps, strengths, ATS keyword audit.
"""
from __future__ import annotations

from typing import Any

from services.career_common import SENIORITY_ORDER


def compute_fit(jd: dict[str, Any], parsed_resume: dict[str, Any]) -> dict[str, Any]:
    """
    Compare JD against resume profile.

    Args:
        jd: output of interpret_jd()
        parsed_resume: output of parse_resume()

    Returns dict with:
        fit_score (0-100), skill_gaps, evidence_gaps, strengths,
        nice_to_have_missing, ats_present, ats_missing,
        role_alignment (0-100), seniority_gap (int), summary
    """
    profile = parsed_resume.get("profile", {})
    skills = parsed_resume.get("skills", [])

    profile_skills_lower = {s["normalized_name"].lower() for s in skills}
    strong_skills = {
        s["normalized_name"].lower()
        for s in skills
        if len(s.get("evidence_refs", [])) >= 2 or s.get("inferred_proficiency") == "strong"
    }

    must_have = jd.get("must_have_skills", [])
    nice_to_have = jd.get("nice_to_have_skills", [])

    skill_gaps = []       # completely missing from profile
    evidence_gaps = []    # present but thin/no evidence
    strengths = []        # present with solid evidence

    for skill in must_have:
        lower = skill.lower()
        if lower in strong_skills:
            strengths.append(skill)
        elif lower in profile_skills_lower:
            evidence_gaps.append(skill)
        else:
            skill_gaps.append(skill)

    nice_to_have_missing = [s for s in nice_to_have if s.lower() not in profile_skills_lower]

    # ── Role family alignment ─────────────────────────────────────────────────
    jd_families = set(jd.get("role_families", []))
    profile_families = set(profile.get("role_families", []))
    if jd_families:
        alignment = len(jd_families & profile_families) / len(jd_families)
    else:
        alignment = 0.5

    # ── Seniority gap ────────────────────────────────────────────────────────
    jd_seniority = jd.get("seniority", "mid")
    profile_seniority = profile.get("seniority", "mid")

    def seniority_idx(s: str) -> int:
        try:
            return SENIORITY_ORDER.index(s)
        except ValueError:
            return 2  # default to mid

    seniority_gap = max(0, seniority_idx(jd_seniority) - seniority_idx(profile_seniority))

    # ── Fit score ────────────────────────────────────────────────────────────
    total_must = len(must_have) or 1
    skill_match_score = ((len(strengths) + len(evidence_gaps) * 0.6) / total_must) * 100
    alignment_score = alignment * 100
    seniority_score = max(0, 100 - seniority_gap * 20)

    fit_score = round(
        skill_match_score * 0.50
        + alignment_score * 0.30
        + seniority_score * 0.20
    )
    fit_score = max(0, min(100, fit_score))

    # ── ATS keyword audit ────────────────────────────────────────────────────
    resume_text_lower = " ".join([
        profile.get("summary", ""),
        " ".join(s["normalized_name"] for s in skills),
        " ".join(e.get("title", "") for e in parsed_resume.get("experience_entries", [])),
    ]).lower()

    jd_keywords = [k.lower() for k in jd.get("keywords", [])]
    ats_present = [k for k in jd_keywords if k in resume_text_lower or k in profile_skills_lower]
    ats_missing = [k for k in jd_keywords if k not in ats_present]

    # ── Gap severity cards ────────────────────────────────────────────────────
    gap_cards = []
    for skill in skill_gaps:
        gap_cards.append({
            "label": skill,
            "type": "skill_gap",
            "severity": "high",
            "why": f"'{skill}' appears in must-have requirements but is absent from your profile.",
        })
    for skill in evidence_gaps:
        gap_cards.append({
            "label": skill,
            "type": "evidence_gap",
            "severity": "medium",
            "why": f"'{skill}' is on your profile but lacks strong evidence (projects, quantified bullets).",
        })
    if seniority_gap >= 2:
        gap_cards.append({
            "label": f"Seniority mismatch ({profile_seniority} → {jd_seniority})",
            "type": "seniority_gap",
            "severity": "high",
            "why": "The role targets a significantly higher seniority level than your current profile signals.",
        })
    elif seniority_gap == 1:
        gap_cards.append({
            "label": f"Seniority stretch ({profile_seniority} → {jd_seniority})",
            "type": "seniority_gap",
            "severity": "medium",
            "why": "The role is one level above your current seniority — achievable but requires strong positioning.",
        })
    if alignment < 0.4 and jd_families:
        gap_cards.append({
            "label": "Role family misalignment",
            "type": "domain_gap",
            "severity": "medium",
            "why": f"Your profile targets {list(profile_families)[:2]} but this role requires {list(jd_families)[:2]}.",
        })

    # ── Fit label ─────────────────────────────────────────────────────────────
    if fit_score >= 80:
        fit_label = "Strong Fit"
        fit_color = "#22c55e"
    elif fit_score >= 60:
        fit_label = "Good Fit"
        fit_color = "#84cc16"
    elif fit_score >= 40:
        fit_label = "Partial Fit"
        fit_color = "#f59e0b"
    else:
        fit_label = "Weak Fit"
        fit_color = "#ef4444"

    return {
        "fit_score": fit_score,
        "fit_label": fit_label,
        "fit_color": fit_color,
        "strengths": strengths,
        "skill_gaps": skill_gaps,
        "evidence_gaps": evidence_gaps,
        "nice_to_have_missing": nice_to_have_missing,
        "gap_cards": gap_cards,
        "role_alignment": round(alignment * 100),
        "seniority_gap": seniority_gap,
        "jd_seniority": jd_seniority,
        "profile_seniority": profile_seniority,
        "ats_present": ats_present,
        "ats_missing": ats_missing,
        "skill_match_pct": round(skill_match_score),
    }


def build_ai_context(jd: dict[str, Any], parsed_resume: dict[str, Any], fit: dict[str, Any]) -> str:
    """Build a compact context string for the Ollama prompt."""
    profile = parsed_resume.get("profile", {})
    lines = [
        f"ROLE: {jd.get('target_role', 'Unknown')} | Seniority: {jd.get('seniority', 'n/a')} | Mode: {jd.get('work_mode', 'n/a')}",
        f"CANDIDATE: {profile.get('professional_identity', 'n/a')} | {profile.get('years_experience', 0)} yrs | {profile.get('seniority', 'n/a')}",
        f"FIT SCORE: {fit['fit_score']}/100 ({fit['fit_label']})",
        f"SKILL MATCH: {fit['skill_match_pct']}% | ROLE ALIGNMENT: {fit['role_alignment']}%",
        f"STRENGTHS (must-have confirmed): {', '.join(fit['strengths'][:6]) or 'none'}",
        f"SKILL GAPS (missing must-have): {', '.join(fit['skill_gaps'][:6]) or 'none'}",
        f"EVIDENCE GAPS (present but thin): {', '.join(fit['evidence_gaps'][:4]) or 'none'}",
        f"NICE-TO-HAVE MISSING: {', '.join(fit['nice_to_have_missing'][:4]) or 'none'}",
        f"ATS KEYWORDS MISSING: {', '.join(fit['ats_missing'][:8]) or 'none'}",
    ]
    if profile.get("summary"):
        lines.append(f"CANDIDATE SUMMARY: {profile['summary'][:300]}")
    exp = parsed_resume.get("experience_entries", [])
    if exp:
        lines.append(f"RECENT ROLE: {exp[0].get('title', '')} at {exp[0].get('company', '')} ({exp[0].get('duration_months', 0) // 12} yrs)")
    if profile.get("top_achievements"):
        lines.append(f"TOP ACHIEVEMENTS: {' | '.join(profile['top_achievements'][:3])}")
    if jd.get("compensation"):
        lines.append(f"JD COMPENSATION SIGNAL: {jd['compensation']}")
    return "\n".join(lines)
