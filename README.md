# JD Fit Analyzer

A public Streamlit app that parses your resume and any job description, then gives you a structured fit report — skill gaps, ATS keyword audit, and AI-powered analysis — all without storing a byte of your data.

## Features

- **Resume Parser** — Upload PDF, DOCX, or paste text. Extracts skills by cluster, experience timeline, quantified achievements, and a completeness score
- **JD Fit Analysis** — Paste any JD. Get a fit score (0–100), skill match chart, gap cards by severity, and ATS keyword audit
- **AI Analysis** — Full Ollama-powered report: strengths, gaps, red flags, salary negotiation range, and 5 tailoring actions
- **Cover Letter Generator** — AI-written cover letter with tone, length, and emphasis controls. Downloadable as .txt

## Tech Stack

![Streamlit](https://img.shields.io/badge/Streamlit-FF4B4B?style=flat&logo=streamlit&logoColor=white)
![Python](https://img.shields.io/badge/Python-3776AB?style=flat&logo=python&logoColor=white)
![Plotly](https://img.shields.io/badge/Charts-Plotly-3F4F75?style=flat&logo=plotly)
![Ollama](https://img.shields.io/badge/LLM-Ollama-black)

- **Parsing**: Pure Python regex-based resume and JD parser (no external NLP dependencies)
- **Visualizations**: Plotly gauge chart, skill match bars, cluster breakdown
- **AI**: Ollama local LLM via Cloudflare Tunnel for cloud deployment
- **No login. No database. No data stored.**

## Local Setup

```bash
git clone https://github.com/YOUR_USERNAME/jd-analyzer
cd jd-analyzer
pip install -r requirements.txt

cp .streamlit/secrets.toml.example .streamlit/secrets.toml
# Edit secrets.toml with your Ollama URL

streamlit run app.py
```

## Streamlit Cloud Deployment

1. Push repo to GitHub
2. Go to [share.streamlit.io](https://share.streamlit.io) → New app → select repo
3. **Advanced settings → Secrets**:
```toml
OLLAMA_BASE_URL = "https://your-tunnel.trycloudflare.com"
OLLAMA_MODEL = "llama3"
```
4. Deploy

## Cloudflare Tunnel for AI Features

```bash
# Run on your local machine (with Ollama running)
cloudflared tunnel --url http://localhost:11434
```

Paste the generated URL into Streamlit Cloud secrets as `OLLAMA_BASE_URL`.

> The fit scoring and all parsing works without Ollama. AI analysis and cover letter generation require a live Ollama instance.

## How It Works

```
Browser → Streamlit Cloud
           ├── Resume text → Pure Python parser → Skills / Experience / Profile
           ├── JD text → Pure Python parser → Must-haves / Keywords / Seniority
           ├── Fit engine → Gap cards / Score / ATS audit
           └── [Optional] Cloudflare Tunnel → Ollama → AI Analysis / Cover Letter
```

Skills are matched using a canonical alias map (e.g. `py`, `python3` → `Python`).
Fit score is weighted: 50% skill match, 30% role family alignment, 20% seniority match.

---

Built as part of a standalone portfolio series extracted from [Soul Spark](https://soulspark.me) — a local-first personal intelligence platform.
