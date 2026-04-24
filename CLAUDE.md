# JD Analyzer — Project Context

> Global context: ~/.claude/CLAUDE.md (sameer-brain repo)

## What It Does
Resume-JD fit scorer. Parses PDF/DOCX resume, scores against any job description
(0-100: 50% skill match, 30% role family, 20% seniority). ATS keyword audit,
skill gap analysis, tailored cover letter generation.

## Stack
Python, Streamlit, Ollama, Plotly

## Structure
- app.py — main app, 5 tabs: Resume / JD Fit / AI Analysis / Cover Letter / About
- services/resume_parser.py — PDF/DOCX parsing
- services/fit_analyzer.py — scoring logic
- services/jd_interpreter.py — JD parsing
- services/career_common.py — shared utilities

## Key Conventions
- Model selector: format_func=_model_label (smart inference, not bare lambda)
- inject_tab_bg_switcher() — full-screen tab background switcher
- Tab backgrounds: career, career2, career3, hero, career
- Footer: sameerbhalerao.com · Soul Spark · GitHub
- About tab: Portfolio button (amber #f59e0b) first, then LinkedIn / GitHub / Soul Spark

## Deployment
Streamlit Cloud — auto-deploys on push to main (github.com/sameervb/jd-analyzer)

## Recent Changes (Apr 2026)
- Added sameerbhalerao.com to footer and About tab
- _model_label() added for smart model descriptions
