"""
JD Fit Analyzer — Standalone Streamlit App
Upload your resume, paste a job description, and get AI-powered fit analysis.
Powered by local parsing + Ollama AI (optional).
"""
from __future__ import annotations

import io
import json
import requests
import streamlit as st
import pandas as pd
import plotly.graph_objects as go
import plotly.express as px

from services.resume_parser import parse_resume
from services.jd_interpreter import interpret_jd
from services.fit_analyzer import compute_fit, build_ai_context

# ── Page config ────────────────────────────────────────────────────────────────
st.set_page_config(
    page_title="JD Fit Analyzer",
    page_icon="🎯",
    layout="wide",
    initial_sidebar_state="expanded",
)

# ── CSS ────────────────────────────────────────────────────────────────────────
st.markdown("""
<style>
[data-testid="stAppViewContainer"] { background: #0d1117; }
[data-testid="stSidebar"] { background: #161b22; }
h1, h2, h3 { color: #e6edf3; }
.stTabs [data-baseweb="tab-list"] { gap: 8px; }
.stTabs [data-baseweb="tab"] {
    background: #161b22;
    border-radius: 8px;
    color: #8b949e;
    border: 1px solid #30363d;
    padding: 8px 18px;
}
.stTabs [aria-selected="true"] {
    background: #1f6feb !important;
    color: #e6edf3 !important;
    border-color: #1f6feb !important;
}
.gap-card {
    border-radius: 10px;
    padding: 14px 18px;
    margin-bottom: 10px;
    border-left: 4px solid;
}
.gap-high  { background: #2d1b1b; border-color: #ef4444; }
.gap-medium { background: #2a2212; border-color: #f59e0b; }
.gap-low   { background: #162416; border-color: #22c55e; }
.strength-card {
    background: #162416;
    border: 1px solid #22c55e;
    border-radius: 10px;
    padding: 10px 16px;
    margin-bottom: 8px;
    color: #86efac;
}
.ats-badge-present {
    display: inline-block;
    background: #14532d;
    color: #86efac;
    border-radius: 6px;
    padding: 3px 10px;
    margin: 3px;
    font-size: 0.8rem;
}
.ats-badge-missing {
    display: inline-block;
    background: #2d1b1b;
    color: #fca5a5;
    border-radius: 6px;
    padding: 3px 10px;
    margin: 3px;
    font-size: 0.8rem;
    text-decoration: line-through;
}
.metric-box {
    background: #161b22;
    border: 1px solid #30363d;
    border-radius: 12px;
    padding: 18px;
    text-align: center;
}
.metric-box .num { font-size: 2rem; font-weight: 700; }
.metric-box .label { color: #8b949e; font-size: 0.85rem; margin-top: 4px; }
</style>
""", unsafe_allow_html=True)


# ── Helpers ─────────────────────────────────────────────────────────────────────

def extract_text_from_upload(uploaded_file) -> str:
    """Extract plain text from PDF, DOCX, or TXT upload."""
    name = uploaded_file.name.lower()
    if name.endswith(".txt"):
        return uploaded_file.read().decode("utf-8", errors="ignore")
    if name.endswith(".pdf"):
        try:
            import pdfplumber
            with pdfplumber.open(io.BytesIO(uploaded_file.read())) as pdf:
                return "\n".join(page.extract_text() or "" for page in pdf.pages)
        except Exception as e:
            st.error(f"PDF parse error: {e}")
            return ""
    if name.endswith(".docx"):
        try:
            from docx import Document
            doc = Document(io.BytesIO(uploaded_file.read()))
            return "\n".join(p.text for p in doc.paragraphs)
        except Exception as e:
            st.error(f"DOCX parse error: {e}")
            return ""
    return ""


@st.cache_data(ttl=600, show_spinner=False)
def cached_parse_resume(text: str) -> dict:
    return parse_resume(text)


@st.cache_data(ttl=600, show_spinner=False)
def cached_interpret_jd(text: str) -> dict:
    return interpret_jd(text)


def query_ollama(prompt: str, system: str = "") -> str:
    """Send a prompt to Ollama. Returns response string or error message."""
    base_url = st.secrets.get("OLLAMA_BASE_URL", "http://localhost:11434")
    model = st.secrets.get("OLLAMA_MODEL", "llama3")
    try:
        messages = []
        if system:
            messages.append({"role": "system", "content": system})
        messages.append({"role": "user", "content": prompt})
        resp = requests.post(
            f"{base_url.rstrip('/')}/api/chat",
            json={"model": model, "messages": messages, "stream": False},
            timeout=90,
        )
        resp.raise_for_status()
        return resp.json().get("message", {}).get("content", "No response received.")
    except requests.exceptions.ConnectionError:
        return "⚠️ Cannot reach Ollama. Make sure it's running and the tunnel URL is set correctly in secrets."
    except Exception as e:
        return f"⚠️ Ollama error: {e}"


# ── Sidebar ────────────────────────────────────────────────────────────────────

with st.sidebar:
    st.markdown("# 🎯 JD Fit Analyzer")
    st.markdown("Upload your resume and paste a JD to get a full fit report.")
    st.divider()

    resume_status = "⬜ Not uploaded"
    jd_status = "⬜ Not pasted"
    if st.session_state.get("parsed_resume"):
        p = st.session_state["parsed_resume"]["profile"]
        resume_status = f"✅ {p.get('professional_identity', 'Resume parsed')[:40]}"
    if st.session_state.get("parsed_jd"):
        jd_status = f"✅ {st.session_state['parsed_jd'].get('target_role', 'JD parsed')[:40]}"

    st.markdown(f"**Resume:** {resume_status}")
    st.markdown(f"**JD:** {jd_status}")

    if st.session_state.get("fit_result"):
        fit = st.session_state["fit_result"]
        score = fit["fit_score"]
        color = fit["fit_color"]
        st.markdown(f"**Fit Score:** <span style='color:{color};font-size:1.3rem;font-weight:700'>{score}/100 — {fit['fit_label']}</span>", unsafe_allow_html=True)

    st.divider()

    if st.button("🔄 Reset All", use_container_width=True):
        for key in ["parsed_resume", "raw_resume_text", "parsed_jd", "raw_jd_text", "fit_result", "ai_analysis", "cover_letter"]:
            st.session_state.pop(key, None)
        st.rerun()

    st.markdown("---")
    st.caption("No data is stored. Everything runs in your browser session.")
    st.caption("AI analysis requires Ollama running locally or via Cloudflare Tunnel.")


# ── Tabs ───────────────────────────────────────────────────────────────────────

tab_resume, tab_jd, tab_analysis, tab_cover = st.tabs([
    "📄 Resume", "📋 JD Fit", "🤖 AI Analysis", "✍️ Cover Letter"
])


# ══════════════════════════════════════════════════════════════════════════════
# TAB 1 — Resume
# ══════════════════════════════════════════════════════════════════════════════

with tab_resume:
    st.markdown("## Upload Your Resume")

    col_upload, col_paste = st.columns([1, 1], gap="large")

    with col_upload:
        uploaded = st.file_uploader("Upload PDF, DOCX, or TXT", type=["pdf", "docx", "txt"])
        if uploaded:
            with st.spinner("Extracting text..."):
                raw = extract_text_from_upload(uploaded)
            if raw.strip():
                st.session_state["raw_resume_text"] = raw
                st.success(f"Extracted {len(raw.split())} words from {uploaded.name}")
            else:
                st.error("Could not extract text. Try pasting it below.")

    with col_paste:
        pasted = st.text_area(
            "Or paste your resume text here",
            value=st.session_state.get("raw_resume_text", ""),
            height=220,
            placeholder="Paste your resume as plain text...",
        )
        if pasted and pasted != st.session_state.get("raw_resume_text", ""):
            st.session_state["raw_resume_text"] = pasted

    raw_text = st.session_state.get("raw_resume_text", "")

    if raw_text and st.button("📊 Parse Resume", type="primary", use_container_width=False):
        with st.spinner("Parsing resume..."):
            result = cached_parse_resume(raw_text)
            st.session_state["parsed_resume"] = result
            st.session_state.pop("fit_result", None)
        st.success("Resume parsed.")
        st.rerun()

    # ── Results ────────────────────────────────────────────────────────────────
    if st.session_state.get("parsed_resume"):
        pr = st.session_state["parsed_resume"]
        profile = pr["profile"]
        skills = pr["skills"]
        experience = pr["experience_entries"]
        diag = pr["diagnostics"]

        st.divider()

        # ── Profile header ──
        st.markdown(f"### {profile.get('professional_identity', 'Your Profile')}")
        c1, c2, c3, c4 = st.columns(4)
        with c1:
            st.markdown(f"<div class='metric-box'><div class='num'>{profile.get('years_experience', 0)}</div><div class='label'>Years Experience</div></div>", unsafe_allow_html=True)
        with c2:
            st.markdown(f"<div class='metric-box'><div class='num'>{len(skills)}</div><div class='label'>Skills Detected</div></div>", unsafe_allow_html=True)
        with c3:
            st.markdown(f"<div class='metric-box'><div class='num'>{len(experience)}</div><div class='label'>Roles Found</div></div>", unsafe_allow_html=True)
        with c4:
            completeness_pct = int(diag.get("completeness", 0) * 100)
            st.markdown(f"<div class='metric-box'><div class='num'>{completeness_pct}%</div><div class='label'>Completeness</div></div>", unsafe_allow_html=True)

        st.markdown("")

        col_left, col_right = st.columns([1, 1], gap="large")

        with col_left:
            # ── Seniority + identity ──
            st.markdown("#### Profile Summary")
            if profile.get("summary"):
                st.markdown(f"_{profile['summary'][:300]}_")
            tags = []
            if profile.get("seniority"):
                tags.append(f"🏷️ {profile['seniority'].title()}")
            if profile.get("management_orientation"):
                tags.append(f"👤 {profile['management_orientation'].replace('_', ' ').title()}")
            if profile.get("role_families"):
                tags.append(f"🎯 {', '.join(profile['role_families'][:2])}")
            if tags:
                st.markdown(" · ".join(tags))

            # ── Top achievements ──
            if profile.get("top_achievements"):
                st.markdown("#### Quantified Achievements")
                for ach in profile["top_achievements"]:
                    st.markdown(f"• {ach}")

            # ── Diagnostics ──
            if diag.get("missing_sections"):
                st.warning(f"Missing sections: {', '.join(diag['missing_sections'])} — consider adding them.")
            if not diag.get("has_quantified_achievements"):
                st.warning("Few quantified achievements detected. Add metrics (%, $, team size) to strengthen your profile.")

        with col_right:
            # ── Skills by cluster — horizontal bar chart ──
            if skills:
                st.markdown("#### Skills by Cluster")
                cluster_map: dict[str, list[str]] = {}
                for s in skills:
                    cluster = s.get("cluster", "General Capability")
                    cluster_map.setdefault(cluster, []).append(s["normalized_name"])

                chart_data = []
                for cluster, skill_list in sorted(cluster_map.items(), key=lambda x: -len(x[1])):
                    chart_data.append({"Cluster": cluster, "Skills": len(skill_list), "Names": ", ".join(skill_list[:5])})
                df = pd.DataFrame(chart_data)

                fig = px.bar(
                    df, x="Skills", y="Cluster", orientation="h",
                    text="Skills",
                    color="Skills",
                    color_continuous_scale=["#1f6feb", "#58a6ff", "#79c0ff"],
                    hover_data={"Names": True, "Skills": True},
                )
                fig.update_traces(textposition="outside")
                fig.update_layout(
                    paper_bgcolor="#0d1117", plot_bgcolor="#0d1117",
                    font_color="#e6edf3", showlegend=False,
                    coloraxis_showscale=False,
                    margin=dict(l=0, r=20, t=10, b=10),
                    height=300,
                    yaxis=dict(tickfont=dict(size=11)),
                )
                st.plotly_chart(fig, use_container_width=True)

        # ── Experience timeline ──
        if experience:
            st.divider()
            st.markdown("#### Experience")
            for exp in experience[:6]:
                dur = exp.get("duration_months", 0) or 0
                dur_str = f"{dur // 12}y {dur % 12}m" if dur >= 12 else f"{dur}m"
                is_current = "🟢 " if exp.get("is_current") else ""
                st.markdown(f"**{is_current}{exp.get('title', '?')}** · {exp.get('company', '?')} · *{exp.get('start_date', '')[:7]} → {('Present' if exp.get('is_current') else exp.get('end_date', '')[:7])}* ({dur_str})")
                if exp.get("achievements"):
                    for a in exp["achievements"][:2]:
                        st.markdown(f"  ↳ {a}")


# ══════════════════════════════════════════════════════════════════════════════
# TAB 2 — JD Fit
# ══════════════════════════════════════════════════════════════════════════════

with tab_jd:
    st.markdown("## Paste Job Description")

    if not st.session_state.get("parsed_resume"):
        st.info("Parse your resume first in the **Resume** tab to unlock fit analysis.")

    jd_text = st.text_area(
        "Paste the full job description here",
        value=st.session_state.get("raw_jd_text", ""),
        height=280,
        placeholder="Paste the full JD including requirements, responsibilities, and nice-to-haves...",
    )

    if jd_text != st.session_state.get("raw_jd_text", ""):
        st.session_state["raw_jd_text"] = jd_text
        st.session_state.pop("parsed_jd", None)
        st.session_state.pop("fit_result", None)

    analyze_disabled = not (jd_text.strip() and st.session_state.get("parsed_resume"))

    if st.button("🎯 Analyze Fit", type="primary", disabled=analyze_disabled):
        with st.spinner("Parsing JD..."):
            parsed_jd = cached_interpret_jd(jd_text)
            st.session_state["parsed_jd"] = parsed_jd
        with st.spinner("Computing fit..."):
            fit = compute_fit(parsed_jd, st.session_state["parsed_resume"])
            st.session_state["fit_result"] = fit
            st.session_state.pop("ai_analysis", None)
            st.session_state.pop("cover_letter", None)
        st.success("Fit analysis complete.")
        st.rerun()

    # ── JD preview if parsed ──
    if st.session_state.get("parsed_jd"):
        jd = st.session_state["parsed_jd"]
        with st.expander("JD Summary", expanded=False):
            meta = []
            if jd.get("target_role"):
                meta.append(f"**Role:** {jd['target_role']}")
            if jd.get("seniority"):
                meta.append(f"**Seniority:** {jd['seniority'].title()}")
            if jd.get("work_mode"):
                meta.append(f"**Mode:** {jd['work_mode'].title()}")
            if jd.get("location"):
                meta.append(f"**Location:** {jd['location']}")
            if jd.get("compensation"):
                meta.append(f"**Compensation:** {jd['compensation']}")
            st.markdown(" · ".join(meta))
            if jd.get("must_have_skills"):
                st.markdown(f"**Must-have skills detected:** {', '.join(jd['must_have_skills'])}")
            if jd.get("nice_to_have_skills"):
                st.markdown(f"**Nice-to-have:** {', '.join(jd['nice_to_have_skills'])}")

    # ── Fit results ──────────────────────────────────────────────────────────
    if st.session_state.get("fit_result"):
        fit = st.session_state["fit_result"]
        jd = st.session_state["parsed_jd"]
        st.divider()

        # ── Fit score gauge ──
        col_gauge, col_breakdown = st.columns([1, 2], gap="large")

        with col_gauge:
            score = fit["fit_score"]
            color = fit["fit_color"]
            fig_gauge = go.Figure(go.Indicator(
                mode="gauge+number",
                value=score,
                title={"text": fit["fit_label"], "font": {"color": "#e6edf3", "size": 16}},
                number={"font": {"color": color, "size": 48}, "suffix": "/100"},
                gauge={
                    "axis": {"range": [0, 100], "tickcolor": "#8b949e", "tickfont": {"color": "#8b949e"}},
                    "bar": {"color": color, "thickness": 0.25},
                    "bgcolor": "#161b22",
                    "bordercolor": "#30363d",
                    "steps": [
                        {"range": [0, 40], "color": "#2d1b1b"},
                        {"range": [40, 60], "color": "#2a2212"},
                        {"range": [60, 80], "color": "#162416"},
                        {"range": [80, 100], "color": "#14532d"},
                    ],
                    "threshold": {"line": {"color": color, "width": 3}, "thickness": 0.75, "value": score},
                },
            ))
            fig_gauge.update_layout(
                paper_bgcolor="#0d1117", font_color="#e6edf3",
                height=260, margin=dict(l=20, r=20, t=30, b=0),
            )
            st.plotly_chart(fig_gauge, use_container_width=True)

        with col_breakdown:
            st.markdown("#### Fit Breakdown")
            c1, c2, c3 = st.columns(3)
            with c1:
                sm = fit["skill_match_pct"]
                sm_col = "#22c55e" if sm >= 70 else "#f59e0b" if sm >= 40 else "#ef4444"
                st.markdown(f"<div class='metric-box'><div class='num' style='color:{sm_col}'>{sm}%</div><div class='label'>Skill Match</div></div>", unsafe_allow_html=True)
            with c2:
                ra = fit["role_alignment"]
                ra_col = "#22c55e" if ra >= 70 else "#f59e0b" if ra >= 40 else "#ef4444"
                st.markdown(f"<div class='metric-box'><div class='num' style='color:{ra_col}'>{ra}%</div><div class='label'>Role Alignment</div></div>", unsafe_allow_html=True)
            with c3:
                sg = fit["seniority_gap"]
                sg_col = "#22c55e" if sg == 0 else "#f59e0b" if sg == 1 else "#ef4444"
                st.markdown(f"<div class='metric-box'><div class='num' style='color:{sg_col}'>{sg}</div><div class='label'>Seniority Gap</div></div>", unsafe_allow_html=True)

            st.markdown("")

            # ── Skill match bar chart ──
            must_have = jd.get("must_have_skills", [])
            if must_have:
                strong_set = set(s.lower() for s in fit["strengths"])
                evidence_set = set(s.lower() for s in fit["evidence_gaps"])
                chart_rows = []
                for skill in must_have:
                    sl = skill.lower()
                    if sl in strong_set:
                        status = "Strong Match"
                        val = 3
                    elif sl in evidence_set:
                        status = "Needs Evidence"
                        val = 2
                    else:
                        status = "Missing"
                        val = 1
                    chart_rows.append({"Skill": skill, "Status": status, "Val": val})

                df_skills = pd.DataFrame(chart_rows)
                color_map = {"Strong Match": "#22c55e", "Needs Evidence": "#f59e0b", "Missing": "#ef4444"}
                fig_skills = px.bar(
                    df_skills, x="Val", y="Skill", orientation="h",
                    color="Status", color_discrete_map=color_map,
                    category_orders={"Status": ["Strong Match", "Needs Evidence", "Missing"]},
                )
                fig_skills.update_traces(width=0.6)
                fig_skills.update_layout(
                    paper_bgcolor="#0d1117", plot_bgcolor="#0d1117",
                    font_color="#e6edf3", showlegend=True,
                    legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="left", x=0),
                    xaxis=dict(visible=False),
                    height=max(200, len(must_have) * 30),
                    margin=dict(l=0, r=10, t=30, b=0),
                    yaxis=dict(tickfont=dict(size=11)),
                )
                st.plotly_chart(fig_skills, use_container_width=True)

        # ── Gap cards ──
        st.divider()
        col_gaps, col_strengths = st.columns([1, 1], gap="large")

        with col_gaps:
            st.markdown("#### Gaps to Address")
            gap_cards = fit.get("gap_cards", [])
            if gap_cards:
                for card in gap_cards:
                    sev = card["severity"]
                    css = f"gap-{sev}"
                    icon = "🔴" if sev == "high" else "🟡"
                    st.markdown(
                        f"<div class='gap-card {css}'><strong>{icon} {card['label']}</strong><br><small>{card['why']}</small></div>",
                        unsafe_allow_html=True,
                    )
            else:
                st.success("No major gaps detected!")

            if fit.get("nice_to_have_missing"):
                with st.expander(f"Nice-to-have missing ({len(fit['nice_to_have_missing'])})"):
                    for s in fit["nice_to_have_missing"]:
                        st.markdown(f"• {s}")

        with col_strengths:
            st.markdown("#### Your Strengths for This Role")
            if fit.get("strengths"):
                for s in fit["strengths"]:
                    st.markdown(f"<div class='strength-card'>✅ {s}</div>", unsafe_allow_html=True)
            else:
                st.info("No confirmed must-have skill matches found.")

        # ── ATS keyword audit ──
        st.divider()
        st.markdown("#### ATS Keyword Audit")
        st.caption("Keywords from the JD — green means found in your resume, red means missing.")
        ats_html = ""
        for kw in fit.get("ats_present", []):
            ats_html += f"<span class='ats-badge-present'>✓ {kw}</span>"
        for kw in fit.get("ats_missing", []):
            ats_html += f"<span class='ats-badge-missing'>✗ {kw}</span>"
        if ats_html:
            st.markdown(ats_html, unsafe_allow_html=True)
        else:
            st.caption("No keyword data available.")


# ══════════════════════════════════════════════════════════════════════════════
# TAB 3 — AI Analysis
# ══════════════════════════════════════════════════════════════════════════════

with tab_analysis:
    st.markdown("## AI-Powered Fit Analysis")

    if not st.session_state.get("fit_result"):
        st.info("Complete the fit analysis in the **JD Fit** tab first.")
    else:
        fit = st.session_state["fit_result"]
        jd = st.session_state["parsed_jd"]
        pr = st.session_state["parsed_resume"]

        if st.session_state.get("ai_analysis"):
            st.markdown(st.session_state["ai_analysis"])
            if st.button("🔄 Regenerate Analysis"):
                st.session_state.pop("ai_analysis", None)
                st.rerun()
        else:
            st.markdown("Get a detailed breakdown: strengths, gaps, red flags, salary range, and tailoring tips.")
            if st.button("🤖 Generate AI Analysis", type="primary"):
                context = build_ai_context(jd, pr, fit)
                system_prompt = """You are an expert career strategist and talent advisor.
You receive structured fit data comparing a candidate's resume to a job description.
Give a rigorous, honest, actionable assessment. Be specific — name skills, reference the data.
Format your response with clear sections using markdown headers."""

                user_prompt = f"""Here is the fit data:

{context}

Please provide:
## Overall Fit Assessment
One concise paragraph on whether this candidate is a strong, moderate, or weak fit and why.

## Top 5 Strengths
Bullet list of what this candidate does well relative to this specific role.

## Top 5 Gaps
Bullet list of the most critical gaps. Be specific about which skills or signals are missing.

## Red Flags
Any hard disqualifiers or risks (max 3). If none, say "No major red flags."

## Salary Negotiation Range
Based on the seniority level and any compensation signal in the JD, suggest a realistic range.

## 5 Tailoring Actions
Specific changes the candidate should make to their resume or cover letter to improve fit for THIS role.
"""
                with st.spinner("Generating AI analysis..."):
                    result = query_ollama(user_prompt, system=system_prompt)
                st.session_state["ai_analysis"] = result
                st.rerun()


# ══════════════════════════════════════════════════════════════════════════════
# TAB 4 — Cover Letter
# ══════════════════════════════════════════════════════════════════════════════

with tab_cover:
    st.markdown("## Cover Letter Generator")

    if not st.session_state.get("fit_result"):
        st.info("Complete the fit analysis in the **JD Fit** tab first.")
    else:
        fit = st.session_state["fit_result"]
        jd = st.session_state["parsed_jd"]
        pr = st.session_state["parsed_resume"]
        profile = pr["profile"]

        col_opts, col_out = st.columns([1, 2], gap="large")

        with col_opts:
            st.markdown("#### Style Options")
            tone = st.selectbox("Tone", ["Professional & concise", "Warm & conversational", "Confident & direct", "Formal"])
            word_count = st.select_slider("Target length", options=[150, 200, 250, 300, 350], value=250)
            focus = st.multiselect(
                "Emphasise",
                ["Technical skills", "Leadership", "Quantified achievements", "Domain expertise", "Growth trajectory"],
                default=["Technical skills", "Quantified achievements"],
            )

            generate_cl = st.button("✍️ Generate Cover Letter", type="primary")

        with col_out:
            if st.session_state.get("cover_letter"):
                st.markdown(st.session_state["cover_letter"])
                cl_text = st.session_state["cover_letter"]
                st.download_button(
                    "⬇️ Download as .txt",
                    data=cl_text,
                    file_name="cover_letter.txt",
                    mime="text/plain",
                )
                if st.button("🔄 Regenerate"):
                    st.session_state.pop("cover_letter", None)
                    st.rerun()
            elif not generate_cl:
                st.info("Click **Generate Cover Letter** to create a tailored draft based on your resume and this JD.")

        if generate_cl:
            context = build_ai_context(jd, pr, fit)
            emphasis_str = ", ".join(focus) if focus else "general fit"
            system_prompt = """You are an expert cover letter writer. You write compelling, human-sounding cover letters
that do NOT sound AI-generated. You draw on real data from the candidate's profile.
Never use generic phrases like 'I am writing to express my interest'. Start differently."""

            user_prompt = f"""Write a cover letter for this candidate applying to this role.

FIT DATA:
{context}

Requirements:
- Tone: {tone}
- Target length: approximately {word_count} words
- Emphasise: {emphasis_str}
- Reference at least 2 specific achievements from the candidate's profile
- Address 1-2 of the must-have requirements directly
- End with a confident, non-generic closing

Format: Plain paragraphs ready to copy. No headers. No placeholders like [Company Name] — infer from the JD if possible or use "your team".
"""
            with st.spinner("Writing cover letter..."):
                result = query_ollama(user_prompt, system=system_prompt)
            st.session_state["cover_letter"] = result
            st.rerun()
