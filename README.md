<div align="center">

# 🎯 JD Fit Analyzer

**Upload your resume, paste any job description — get an AI-powered fit score, skill gap cards, ATS keyword audit, and a tailored cover letter. No account. No data stored.**

[![Python](https://img.shields.io/badge/Python-3.10+-3776AB?style=flat&logo=python&logoColor=white)](https://python.org)
[![Streamlit](https://img.shields.io/badge/Streamlit-1.32+-FF4B4B?style=flat&logo=streamlit&logoColor=white)](https://streamlit.io)
[![Ollama](https://img.shields.io/badge/LLM-Ollama-black?style=flat)](https://ollama.ai)
[![Plotly](https://img.shields.io/badge/Charts-Plotly-3F4F75?style=flat&logo=plotly)](https://plotly.com)
[![License](https://img.shields.io/badge/license-MIT-22c55e?style=flat)](LICENSE)

[**Portfolio**](https://sameerbhalerao.com) · [**Soul Spark**](https://soulspark.me) · [**LinkedIn**](https://linkedin.com/in/sameervb) · [**GitHub**](https://github.com/sameervb)

</div>

---

## What It Does

JD Fit Analyzer closes the loop between your resume and a job posting. Paste both in and get a structured breakdown: a 0–100 weighted fit score, colour-coded skill gap cards, an ATS keyword audit, and an Ollama-powered strategic analysis. When you're ready to apply, generate a tailored cover letter with tone and length controls — downloadable as `.txt`.

No NLP libraries. No external APIs for parsing. Everything runs in-process.

---

## Features

| Tab | What you get |
|-----|-------------|
| **📄 Resume** | Parse PDF, DOCX, or plain text. Extracts skills by cluster, experience timeline, quantified achievements, and an overall completeness score. |
| **📋 JD Fit** | Paste any JD. Weighted fit score (0–100), skill match chart, gap cards by severity (critical / partial / bonus), ATS keyword audit. |
| **🤖 AI Analysis** | Full Ollama report: strengths, critical gaps, red flags, salary negotiation range, and 5 concrete tailoring actions. |
| **✍️ Cover Letter** | AI-written cover letter with tone (formal / conversational / assertive), length, and focus controls. Downloadable as `.txt`. |
| **ℹ️ About** | Project context and links. |

---

## Fit Score Algorithm

```
Score = 50% skill match + 30% role-family alignment + 20% seniority match

Skill match:       canonical alias map — "py", "python3" → "Python"
Role-family:       JD keywords mapped to 12 families (engineering, analytics, PM, etc.)
Seniority match:   years of experience vs. JD-stated requirement
```

Gaps are ranked **Critical** (must-have skills missing) → **Partial** (partial overlap) → **Bonus** (nice-to-have). ATS audit flags exact keywords the JD expects that aren't in your resume.

---

## Tech Stack

| Layer | Technology |
|-------|-----------|
| UI & hosting | Streamlit |
| Resume parsing | Pure Python — regex + heuristics, no NLP dependencies |
| JD parsing | Pure Python — keyword extraction and role-family mapping |
| File formats | pdfplumber (PDF) · python-docx (DOCX) · plain text |
| Visualisations | Plotly gauge, skill match bars, cluster breakdown chart |
| AI | Ollama (local LLM) via Cloudflare Tunnel |
| Language | Python 3.10+ |

---

## Quick Start

```bash
git clone https://github.com/sameervb/jd-analyzer
cd jd-analyzer
pip install -r requirements.txt

cp .streamlit/secrets.toml.example .streamlit/secrets.toml
# Edit secrets.toml — Ollama URL is optional

streamlit run app.py
```

---

## Secrets

```toml
# .streamlit/secrets.toml

# Optional — enables AI Analysis and Cover Letter tabs
OLLAMA_BASE_URL = "https://your-tunnel.trycloudflare.com"
OLLAMA_MODEL    = "llama3.1:8b"
```

Ollama is **optional**. Resume parsing, JD fit scoring, and all visualisations work without it. AI tabs show a graceful "Connect AI" prompt when Ollama is unavailable.

---

## Deploying to Streamlit Cloud

1. Fork / push this repo to GitHub
2. Go to [share.streamlit.io](https://share.streamlit.io) → New App → select this repo
3. Under **Advanced settings → Secrets**, paste:

```toml
OLLAMA_BASE_URL = "https://your-cloudflare-url.trycloudflare.com"
OLLAMA_MODEL    = "llama3.1:8b"
```

### Cloudflare Tunnel — expose local Ollama to the cloud

```bash
# Run on your machine while Ollama is running on port 11434
cloudflared tunnel --url http://localhost:11434
```

Paste the generated `*.trycloudflare.com` URL as `OLLAMA_BASE_URL` in Streamlit Cloud secrets.

---

## Architecture

```
Browser → Streamlit Cloud
    │
    ├── Resume tab ──── pdfplumber / python-docx
    │               └── Pure Python parser → Skills / Experience / Profile
    │
    ├── JD Fit tab ──── Pure Python parser
    │               └── Gap cards / Fit score / ATS audit / Plotly charts
    │
    ├── AI Analysis ─── Cloudflare Tunnel ──→ Ollama (your machine)
    │                                        └── Streamed strategic report
    │
    └── Cover Letter ── Cloudflare Tunnel ──→ Ollama (your machine)
                                             └── Streamed cover letter

No user data stored. No login required.
Parsing runs entirely in-process — your resume never leaves the browser session.
```

---

## Project Context

Built as a standalone portfolio app, part of a series extracted from [Soul Spark](https://soulspark.me) — a local-first personal intelligence platform integrating finance, health, career, and growth into a unified conversational AI advisor.

**Related apps in this series:**
- [journey-planner](https://github.com/sameervb/journey-planner) — Multi-modal route optimizer and AI travel advisor
- [dota-analyzer](https://github.com/sameervb/dota-analyzer) — Dota 2 player stats and draft intelligence

---

<div align="center">

Built by [Sameer Bhalerao](https://sameerbhalerao.com) · Senior Analytics & AI Product Leader · Amazon L6 BIE · Luxembourg

</div>
