"""
JD Fit Analyzer — Standalone Streamlit App
Upload your resume, paste a job description, and get AI-powered fit analysis.
Powered by local parsing + Ollama AI (optional).
"""
from __future__ import annotations

import io
import json
import time
import base64
import requests
import streamlit as st
import pandas as pd
import plotly.graph_objects as go
import plotly.express as px
from pathlib import Path

from services.resume_parser import parse_resume
from services.jd_interpreter import interpret_jd
from services.fit_analyzer import compute_fit, build_ai_context

st.set_page_config(
    page_title="JD Fit Analyzer",
    page_icon="🎯",
    layout="wide",
    initial_sidebar_state="expanded",
)

# ── Asset loader ───────────────────────────────────────────────────────────────
def _b64(filename: str) -> str:
    p = Path(__file__).parent / "assets" / filename
    if p.exists():
        ext = p.suffix.lstrip(".")
        mime = {"jpg": "jpeg", "jpeg": "jpeg", "png": "png", "webp": "webp", "avif": "avif"}.get(ext, "jpeg")
        return f"data:image/{mime};base64," + base64.b64encode(p.read_bytes()).decode()
    return ""

@st.cache_data(show_spinner=False)
def load_assets():
    return {
        "career":  _b64("career.jpg"),
        "career2": _b64("career_2.jpg"),
        "career3": _b64("career_3.jpg"),
        "hero":    _b64("hero.jpg"),
    }

IMG       = load_assets()
career_bg  = f"url('{IMG['career']}')"  if IMG["career"]  else "none"
career2_bg = f"url('{IMG['career2']}')" if IMG["career2"] else "none"
career3_bg = f"url('{IMG['career3']}')" if IMG["career3"] else "none"
hero_bg    = f"url('{IMG['hero']}')"    if IMG["hero"]    else "none"

# ── CSS ────────────────────────────────────────────────────────────────────────
st.markdown("""
<style>
@import url('https://fonts.googleapis.com/css2?family=Inter:wght@300;400;500;600;700;800&display=swap');
*, *::before, *::after { font-family: 'Inter', sans-serif; box-sizing: border-box; }

[data-testid="stAppViewContainer"] { background: #07090f; }
[data-testid="stSidebar"] {
    background: linear-gradient(180deg, #0a0e1a 0%, #07090f 100%);
    border-right: 1px solid #1a2236;
}

/* ── Tabs ── */
.stTabs [data-baseweb="tab-list"] {
    gap: 2px; background: #0d1120; padding: 5px;
    border-radius: 14px; border: 1px solid #1a2236;
}
.stTabs [data-baseweb="tab"] {
    background: transparent; border-radius: 10px;
    color: #4b5a7a; border: none; padding: 9px 22px;
    font-weight: 600; font-size: 0.82rem; letter-spacing: 0.02em;
    transition: all 0.2s;
}
.stTabs [aria-selected="true"] {
    background: linear-gradient(135deg, #1d6bf3 0%, #1254c0 100%) !important;
    color: #fff !important;
    box-shadow: 0 4px 16px rgba(29,107,243,0.45);
}

/* ── Section header ── */
.sec-hdr {
    display: flex; align-items: center; gap: 12px;
    margin: 28px 0 16px;
}
.sec-hdr .sec-title {
    font-size: 0.72rem; font-weight: 700; text-transform: uppercase;
    letter-spacing: 0.12em; color: #94a3b8; white-space: nowrap;
}
.sec-hdr .sec-line {
    flex: 1; height: 1px;
    background: linear-gradient(90deg, #1e2d42, transparent);
}

/* ── KPI cards ── */
.kpi-card {
    background: linear-gradient(135deg, #0f1825 0%, #131d2e 100%);
    border: 1px solid #1e2d42; border-radius: 18px;
    padding: 22px 20px 18px; position: relative; overflow: hidden;
    transition: transform 0.2s, box-shadow 0.2s;
}
.kpi-card:hover { transform: translateY(-2px); box-shadow: 0 8px 32px rgba(0,0,0,0.4); }
.kpi-card .accent-bar {
    position: absolute; top: 0; left: 0; right: 0; height: 3px;
    border-radius: 18px 18px 0 0;
}
.kpi-card .kpi-icon { font-size: 1.3rem; margin-bottom: 8px; }
.kpi-card .kpi-val { font-size: 2rem; font-weight: 800; line-height: 1.1; }
.kpi-card .kpi-lbl {
    font-size: 0.7rem; text-transform: uppercase; letter-spacing: 0.1em;
    color: #4b5a7a; font-weight: 600; margin-top: 4px;
}
.kpi-card .kpi-sub { font-size: 0.78rem; color: #64748b; margin-top: 6px; }

/* ── Gap cards ── */
.gap-card-new {
    border-radius: 14px; padding: 14px 18px; margin-bottom: 10px;
    border-left: 4px solid; position: relative; overflow: hidden;
}
.gap-card-new.high  { background: linear-gradient(135deg,#2d1b1b,#1a0f0f); border-color: #ef4444; }
.gap-card-new.medium{ background: linear-gradient(135deg,#2a2212,#1a1508); border-color: #f59e0b; }
.gap-card-new.low   { background: linear-gradient(135deg,#162416,#0f1810); border-color: #22c55e; }
.gap-card-new .gap-label { font-weight: 700; color: #f1f5f9; font-size: 0.9rem; margin-bottom: 4px; }
.gap-card-new .gap-why   { font-size: 0.78rem; color: #94a3b8; line-height: 1.5; }

/* ── Strength cards ── */
.strength-card-new {
    background: linear-gradient(135deg, #0d2518, #0a1c12);
    border: 1px solid rgba(34,197,94,0.25); border-radius: 12px;
    padding: 10px 16px; margin-bottom: 8px;
    display: flex; align-items: center; gap: 10px;
}
.strength-card-new .s-icon { color: #22c55e; font-size: 1rem; flex-shrink: 0; }
.strength-card-new .s-text { color: #86efac; font-size: 0.85rem; font-weight: 500; }

/* ── ATS badges ── */
.ats-present {
    display: inline-block;
    background: rgba(34,197,94,0.12); color: #86efac;
    border: 1px solid rgba(34,197,94,0.3);
    border-radius: 20px; padding: 4px 12px; margin: 3px;
    font-size: 0.78rem; font-weight: 600;
}
.ats-missing {
    display: inline-block;
    background: rgba(239,68,68,0.08); color: #fca5a5;
    border: 1px solid rgba(239,68,68,0.2);
    border-radius: 20px; padding: 4px 12px; margin: 3px;
    font-size: 0.78rem; text-decoration: line-through; opacity: 0.65;
}

/* ── Skill chips ── */
.skill-chip {
    display: inline-block;
    background: rgba(29,107,243,0.1); color: #93c5fd;
    border: 1px solid rgba(29,107,243,0.22);
    border-radius: 20px; padding: 3px 10px; margin: 3px;
    font-size: 0.75rem; font-weight: 500;
}

/* ── Experience cards ── */
.exp-card {
    background: linear-gradient(135deg, #0f1825, #131d2e);
    border: 1px solid #1e2d42; border-radius: 14px;
    padding: 16px 20px; margin-bottom: 10px;
    border-left: 3px solid #1d6bf3;
    transition: border-color 0.2s;
}
.exp-card.current { border-left-color: #22c55e; }
.exp-card:hover { border-color: #2a3d5a; }
.exp-card .exp-title   { font-weight: 700; color: #f1f5f9; font-size: 0.95rem; }
.exp-card .exp-company { color: #94a3b8; font-size: 0.82rem; margin-top: 2px; }
.exp-card .exp-dates   { color: #4b5a7a; font-size: 0.75rem; margin-top: 4px; }
.exp-card .exp-badge   {
    display: inline-block; background: rgba(34,197,94,0.12); color: #86efac;
    border: 1px solid rgba(34,197,94,0.25); border-radius: 20px;
    padding: 2px 8px; font-size: 0.68rem; font-weight: 600; margin-left: 8px;
}
.exp-card .exp-ach { color: #64748b; font-size: 0.78rem; margin-top: 8px; line-height: 1.7; }

/* ── AI output ── */
.ai-output {
    background: linear-gradient(135deg, #0d1520, #111d2e);
    border: 1px solid #1e2d42; border-radius: 14px;
    padding: 20px 24px; color: #cbd5e1;
    font-size: 0.88rem; line-height: 1.9;
}

/* ── Cover letter card ── */
.cl-output {
    background: linear-gradient(135deg, #0d1825, #111d2e);
    border: 1px solid #1e2d42; border-left: 4px solid #f59e0b;
    border-radius: 14px; padding: 28px 32px;
    color: #e2e8f0; font-size: 0.92rem; line-height: 2;
    white-space: pre-wrap;
}

/* ── JD meta tag ── */
.jd-tag {
    display: inline-block;
    background: rgba(139,92,246,0.1); color: #c4b5fd;
    border: 1px solid rgba(139,92,246,0.22);
    border-radius: 20px; padding: 4px 12px; margin: 3px 3px 3px 0;
    font-size: 0.78rem; font-weight: 500;
}

/* ── Step badge (sidebar) ── */
.step-badge {
    display: flex; align-items: center; gap: 12px;
    padding: 10px 14px; border-radius: 12px; margin-bottom: 8px;
    border: 1px solid #1a2236;
}
.step-badge.done    { background: rgba(34,197,94,0.08);  border-color: rgba(34,197,94,0.2); }
.step-badge.active  { background: rgba(29,107,243,0.08); border-color: rgba(29,107,243,0.2); }
.step-badge.locked  { background: transparent; opacity: 0.45; }
.step-badge .step-num {
    width: 22px; height: 22px; border-radius: 50%;
    display: flex; align-items: center; justify-content: center;
    font-size: 0.68rem; font-weight: 800; flex-shrink: 0;
}
.step-badge.done   .step-num { background: #22c55e; color: #07090f; }
.step-badge.active .step-num { background: #1d6bf3; color: #fff; }
.step-badge.locked .step-num { background: #1e2d42; color: #4b5a7a; }
.step-badge .step-label { font-size: 0.82rem; font-weight: 600; color: #cbd5e1; }
.step-badge .step-sub   { font-size: 0.7rem; color: #4b5a7a; margin-top: 1px; }

/* ── Footer ── */
.footer {
    text-align: center; padding: 32px 0 16px;
    color: #334155; font-size: 0.78rem; border-top: 1px solid #0f1825;
    margin-top: 40px; line-height: 1.8;
}
.footer a { color: #1d6bf3; text-decoration: none; }
.footer a:hover { color: #60a5fa; }

/* ── Inputs ── */
.stButton button { border-radius: 12px; font-weight: 600; font-size: 0.85rem; }
.stSelectbox > div > div {
    background: #0d1520 !important; border-color: #1a2840 !important;
    color: #cbd5e1 !important; border-radius: 10px !important;
}
[data-testid="stTextInput"] input {
    background: #0d1520 !important; border-color: #1a2840 !important;
    color: #cbd5e1 !important; border-radius: 10px !important;
}
textarea {
    background: #0d1520 !important; border-color: #1a2840 !important;
    color: #cbd5e1 !important;
}

/* ── Tab banner ── */
.tab-banner {
    border-radius: 20px; overflow: hidden; position: relative;
    margin-bottom: 28px; height: 180px;
    background-size: cover; background-position: center;
    display: flex; align-items: flex-end;
    background-color: #0f1825; border: 1px solid #1e2d42;
}
.tab-banner .banner-overlay {
    position: absolute; inset: 0;
}
.tab-banner .banner-content {
    position: relative; z-index: 1; padding: 28px 32px;
}
</style>
""", unsafe_allow_html=True)


# ── Helpers ─────────────────────────────────────────────────────────────────────

def extract_text_from_upload(uploaded_file) -> str:
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


# ── Ollama ─────────────────────────────────────────────────────────────────────

def _get_ollama_url() -> str:
    try: return st.secrets.get("OLLAMA_BASE_URL", "") or ""
    except: return ""

def _get_ollama_model() -> str:
    override = st.session_state.get("jd_selected_model")
    if override: return override
    try: return st.secrets.get("OLLAMA_MODEL", "llama3.1")
    except: return "llama3.1"

@st.cache_data(ttl=30, show_spinner=False)
def detect_ollama_models() -> list:
    base_url = _get_ollama_url()
    if not base_url: return []
    try:
        r = requests.get(f"{base_url.rstrip('/')}/api/tags", timeout=5)
        if r.ok:
            return sorted(m["name"] for m in r.json().get("models", []))
    except Exception:
        pass
    return []

@st.cache_data(ttl=15, show_spinner=False)
def detect_gpu():
    base_url = _get_ollama_url()
    if not base_url: return None
    try:
        r = requests.get(f"{base_url.rstrip('/')}/api/ps", timeout=5)
        if r.ok:
            models = r.json().get("models", [])
            if not models: return None
            return any(m.get("size_vram", 0) > 0 for m in models)
    except Exception:
        pass
    return None

def _stream_ollama(prompt: str, system: str = "", max_tokens: int = 1200, temperature: float = 0.72):
    base_url = _get_ollama_url()
    if not base_url:
        yield "⚠️ OLLAMA_BASE_URL not configured in Streamlit secrets."
        return
    try:
        msgs = ([{"role": "system", "content": system}] if system else []) + [{"role": "user", "content": prompt}]
        r = requests.post(f"{base_url.rstrip('/')}/api/chat",
            json={"model": _get_ollama_model(), "messages": msgs, "stream": True,
                  "options": {"num_predict": max_tokens, "temperature": temperature}},
            timeout=120, stream=True)
        if r.ok:
            for line in r.iter_lines():
                if line:
                    try:
                        chunk = json.loads(line)
                        token = chunk.get("message", {}).get("content", "")
                        if token: yield token
                        if chunk.get("done"): break
                    except Exception:
                        pass
        else:
            yield f"⚠️ Ollama HTTP {r.status_code}"
    except requests.Timeout:
        yield "⚠️ **Timeout** — try a faster model (mistral or phi3:mini)."
    except requests.ConnectionError:
        yield "⚠️ **Cannot reach Ollama.** Check tunnel URL in secrets."
    except Exception as e:
        yield f"⚠️ {e}"

def render_ai_output(prompt: str, system: str = "", max_tokens: int = 1200, temperature: float = 0.72) -> str:
    start_t = time.perf_counter()
    status = st.status("⚡ Generating analysis...", expanded=True)
    full_text = ""
    with status:
        full_text = st.write_stream(_stream_ollama(prompt, system, max_tokens, temperature))
        elapsed = time.perf_counter() - start_t
        st.caption(f"Generated in {elapsed:.1f}s · Model: {_get_ollama_model()}")
    status.update(label=f"✅ Done · {elapsed:.1f}s", state="complete", expanded=False)
    return full_text or ""

_ai_available = bool(_get_ollama_url())


# ── UI component helpers ────────────────────────────────────────────────────────

def sec(title: str, icon: str = ""):
    st.markdown(
        f'<div class="sec-hdr"><span class="sec-title">{icon}&nbsp;{title}</span>'
        f'<div class="sec-line"></div></div>',
        unsafe_allow_html=True,
    )

def banner(title: str, subtitle: str, accent: str = "#1d6bf3", tag: str = "JD Fit Analyzer", bg: str = "none"):
    img_style = f"background-image:{bg};" if bg != "none" else ""
    st.markdown(f"""
    <div class="tab-banner" style="{img_style}">
        <div class="banner-overlay"
             style="background:linear-gradient(to right,rgba(7,9,15,0.94) 0%,rgba(7,9,15,0.65) 55%,rgba(7,9,15,0.2) 100%)"></div>
        <div class="banner-content">
            <div style="font-size:0.68rem;font-weight:700;text-transform:uppercase;
                        letter-spacing:0.18em;color:{accent};margin-bottom:8px">{tag}</div>
            <div style="font-size:1.75rem;font-weight:800;color:#f1f5f9;line-height:1.1">{title}</div>
            <div style="color:#94a3b8;margin-top:6px;font-size:0.84rem;max-width:520px">{subtitle}</div>
        </div>
    </div>""", unsafe_allow_html=True)

def kpi(icon: str, label: str, value: str, sub: str = "", color: str = "#1d6bf3"):
    st.markdown(f"""
    <div class="kpi-card">
        <div class="accent-bar" style="background:linear-gradient(90deg,{color},transparent)"></div>
        <div class="kpi-icon">{icon}</div>
        <div class="kpi-val" style="color:{color}">{value}</div>
        <div class="kpi-lbl">{label}</div>
        {'<div class="kpi-sub">'+sub+'</div>' if sub else ''}
    </div>""", unsafe_allow_html=True)

def footer():
    st.markdown("""
    <div class="footer">
        Built by <strong>Sameer Bhalerao</strong> · Senior Analytics & AI Product Leader · Amazon L6<br>
        Part of the <a href="https://soulspark.me" target="_blank">Soul Spark</a> portfolio ·
        <a href="https://github.com/sameervb/jd-analyzer" target="_blank">GitHub</a> ·
        No data stored · No login required
    </div>""", unsafe_allow_html=True)


# ── Sidebar ─────────────────────────────────────────────────────────────────────

with st.sidebar:
    if IMG["career"]:
        st.markdown(f"""
        <div style="border-radius:16px;overflow:hidden;margin-bottom:16px;height:110px;
                    background-image:{career_bg};background-size:cover;background-position:center top">
            <div style="height:100%;background:linear-gradient(to bottom,rgba(7,9,15,0.35),rgba(7,9,15,0.88));
                        display:flex;flex-direction:column;justify-content:flex-end;padding:14px">
                <div style="font-size:0.6rem;font-weight:700;text-transform:uppercase;
                            letter-spacing:0.2em;color:#1d6bf3">AI-Powered</div>
                <div style="font-size:1.1rem;font-weight:800;color:#f1f5f9;line-height:1.2">JD Fit Analyzer</div>
                <div style="color:#4b5a7a;font-size:0.72rem;margin-top:2px">No login · No data stored</div>
            </div>
        </div>""", unsafe_allow_html=True)
    else:
        st.markdown("""
        <div style="margin-bottom:20px">
            <div style="font-size:0.65rem;font-weight:700;text-transform:uppercase;
                        letter-spacing:0.2em;color:#1d6bf3;margin-bottom:6px">AI-Powered</div>
            <div style="font-size:1.3rem;font-weight:800;color:#f1f5f9;line-height:1">JD Fit Analyzer</div>
            <div style="color:#4b5a7a;font-size:0.78rem;margin-top:4px">No login · No data stored</div>
        </div>""", unsafe_allow_html=True)

    st.markdown('<div style="height:1px;background:linear-gradient(90deg,#1e2d42,transparent);margin-bottom:16px"></div>', unsafe_allow_html=True)

    # Progress steps
    has_resume = bool(st.session_state.get("parsed_resume"))
    has_jd     = bool(st.session_state.get("fit_result"))
    has_ai     = bool(st.session_state.get("ai_analysis"))
    has_cl     = bool(st.session_state.get("cover_letter"))

    steps = [
        (1, "Resume", "Upload & parse your CV", has_resume),
        (2, "JD Fit", "Paste job description", has_jd),
        (3, "AI Analysis", "AI career strategist", has_ai),
        (4, "Cover Letter", "Tailored draft", has_cl),
    ]
    html = ""
    for num, label, sub, done in steps:
        cls = "done" if done else "active" if not done and (num == 1 or (num == 2 and has_resume) or (num == 3 and has_jd) or (num == 4 and has_jd)) else "locked"
        check = "✓" if done else str(num)
        html += f"""
        <div class="step-badge {cls}">
            <div class="step-num">{check}</div>
            <div>
                <div class="step-label">{label}</div>
                <div class="step-sub">{sub}</div>
            </div>
        </div>"""
    st.markdown(html, unsafe_allow_html=True)

    if has_jd:
        fit = st.session_state["fit_result"]
        score = fit["fit_score"]
        color = fit["fit_color"]
        st.markdown(f"""
        <div style="background:linear-gradient(135deg,#0f1825,#131d2e);border:1px solid #1e2d42;
                    border-radius:14px;padding:14px 16px;margin:12px 0;text-align:center">
            <div style="font-size:0.65rem;text-transform:uppercase;letter-spacing:0.1em;
                        color:#4b5a7a;margin-bottom:4px">Current Fit Score</div>
            <div style="font-size:2.2rem;font-weight:900;color:{color};line-height:1">{score}</div>
            <div style="font-size:0.8rem;color:{color};opacity:0.8">{fit['fit_label']}</div>
        </div>""", unsafe_allow_html=True)

    st.markdown('<div style="height:1px;background:linear-gradient(90deg,#1e2d42,transparent);margin:12px 0"></div>', unsafe_allow_html=True)

    if st.button("🔄 Reset All", use_container_width=True):
        for key in ["parsed_resume","raw_resume_text","parsed_jd","raw_jd_text","fit_result","ai_analysis","cover_letter"]:
            st.session_state.pop(key, None)
        st.rerun()

    st.markdown('<div style="height:1px;background:linear-gradient(90deg,#1e2d42,transparent);margin:12px 0"></div>', unsafe_allow_html=True)

    _MODEL_DESC = {
        "phi3:mini":    "⚡ fastest · ~5s",
        "phi3:medium":  "⚡ fast · ~10s",
        "mistral":      "⚖️ balanced · ~15s",
        "mistral:7b":   "⚖️ balanced · ~15s",
        "llama3.1:8b":  "🧠 capable · ~30s",
        "llama3.1:70b": "🧠 most capable · slow",
        "llama3:8b":    "🧠 capable · ~30s",
        "gemma:7b":     "⚖️ balanced · ~20s",
        "gemma2:9b":    "⚖️ balanced · ~20s",
        "qwen2.5:7b":   "⚖️ balanced · ~20s",
    }
    if _ai_available:
        available_models = detect_ollama_models()
        if available_models:
            gpu_status = detect_gpu()
            gpu_label = "🟩 GPU" if gpu_status is True else "🟨 CPU" if gpu_status is False else ""
            st.markdown(f'<div style="background:rgba(34,197,94,0.08);border:1px solid rgba(34,197,94,0.2);border-radius:10px;padding:8px 12px;color:#86efac;font-size:0.78rem;margin-bottom:8px">🟢 &nbsp;AI online &nbsp;{gpu_label}</div>', unsafe_allow_html=True)
            current = _get_ollama_model()
            default_idx = available_models.index(current) if current in available_models else 0
            chosen = st.selectbox(
                "Model", available_models, index=default_idx,
                label_visibility="collapsed",
                format_func=lambda m: f"{m} — {_MODEL_DESC[m]}" if m in _MODEL_DESC else m,
            )
            if chosen != st.session_state.get("jd_selected_model"):
                st.session_state["jd_selected_model"] = chosen
        else:
            st.markdown('<div style="background:rgba(34,197,94,0.08);border:1px solid rgba(34,197,94,0.2);border-radius:10px;padding:8px 12px;color:#86efac;font-size:0.78rem">🟢 &nbsp;AI online</div>', unsafe_allow_html=True)
    else:
        st.markdown('<div style="background:#0d1520;border:1px solid #1e2d42;border-radius:10px;padding:8px 12px;color:#4b5a7a;font-size:0.78rem">🔵 &nbsp;Set OLLAMA_BASE_URL in secrets</div>', unsafe_allow_html=True)
    st.markdown("")
    st.caption("AI · Ollama · Cloudflare Tunnel")


# ── Tabs ────────────────────────────────────────────────────────────────────────

tab_resume, tab_jd, tab_analysis, tab_cover, tab_about = st.tabs([
    "📄 Resume", "📋 JD Fit", "🤖 AI Analysis", "✍️ Cover Letter", "ℹ️ About"
])


# ══════════════════════════════════════════════════════════════════════════════
# TAB 1 — Resume
# ══════════════════════════════════════════════════════════════════════════════

with tab_resume:
    banner("Resume Intelligence",
           "Upload PDF, DOCX, or paste text · Skills extraction · Experience timeline · Completeness score",
           accent="#1d6bf3", bg=career_bg)

    col_upload, col_paste = st.columns([1, 1], gap="large")

    with col_upload:
        st.markdown('<div style="font-size:0.72rem;font-weight:700;text-transform:uppercase;letter-spacing:0.1em;color:#4b5a7a;margin-bottom:8px">Upload File</div>', unsafe_allow_html=True)
        uploaded = st.file_uploader("", type=["pdf", "docx", "txt"], label_visibility="collapsed")
        if uploaded:
            with st.spinner("Extracting text..."):
                raw = extract_text_from_upload(uploaded)
            if raw.strip():
                st.session_state["raw_resume_text"] = raw
                st.success(f"✅ Extracted {len(raw.split())} words from {uploaded.name}")
            else:
                st.error("Could not extract text. Try pasting below.")

    with col_paste:
        st.markdown('<div style="font-size:0.72rem;font-weight:700;text-transform:uppercase;letter-spacing:0.1em;color:#4b5a7a;margin-bottom:8px">Or Paste Text</div>', unsafe_allow_html=True)
        pasted = st.text_area("", value=st.session_state.get("raw_resume_text", ""),
                               height=200, placeholder="Paste your resume as plain text...",
                               label_visibility="collapsed")
        if pasted and pasted != st.session_state.get("raw_resume_text", ""):
            st.session_state["raw_resume_text"] = pasted

    raw_text = st.session_state.get("raw_resume_text", "")

    if raw_text:
        st.markdown("")
        if st.button("📊 Parse Resume", type="primary"):
            with st.spinner("Parsing resume..."):
                result = cached_parse_resume(raw_text)
                st.session_state["parsed_resume"] = result
                st.session_state.pop("fit_result", None)
            st.rerun()

    if st.session_state.get("parsed_resume"):
        pr = st.session_state["parsed_resume"]
        profile = pr["profile"]
        skills  = pr["skills"]
        experience = pr["experience_entries"]
        diag = pr["diagnostics"]

        # ── Profile header card ──
        completeness_pct = int(diag.get("completeness", 0) * 100)
        comp_color = "#22c55e" if completeness_pct >= 75 else "#f59e0b" if completeness_pct >= 50 else "#ef4444"
        identity = profile.get("professional_identity") or "Your Profile"
        seniority = profile.get("seniority","").title()
        role_fam = ", ".join(profile.get("role_families",[])[:2])

        st.markdown(f"""
        <div style="background:linear-gradient(135deg,#0f1825,#131d2e);border:1px solid #1e2d42;
                    border-radius:20px;padding:24px 28px;margin:20px 0;
                    border-left:4px solid #1d6bf3">
            <div style="font-size:1.3rem;font-weight:800;color:#f1f5f9">{identity}</div>
            <div style="display:flex;gap:8px;flex-wrap:wrap;margin-top:10px">
                {'<span class="jd-tag">'+seniority+'</span>' if seniority else ''}
                {'<span class="jd-tag">'+role_fam+'</span>' if role_fam else ''}
                <span style="display:inline-block;background:rgba(29,107,243,0.1);color:#93c5fd;border:1px solid rgba(29,107,243,0.22);border-radius:20px;padding:4px 12px;margin:3px 3px 3px 0;font-size:0.78rem;font-weight:500">
                    {completeness_pct}% complete
                </span>
            </div>
            {f'<div style="color:#64748b;font-size:0.82rem;margin-top:10px;font-style:italic">{profile["summary"][:250]}</div>' if profile.get("summary") else ''}
        </div>""", unsafe_allow_html=True)

        # ── KPI row ──
        k1, k2, k3, k4 = st.columns(4)
        with k1: kpi("🗓️", "Years Experience", str(profile.get("years_experience", 0)), "total career span", "#1d6bf3")
        with k2: kpi("⚡", "Skills Detected", str(len(skills)), "across all clusters", "#8b5cf6")
        with k3: kpi("🏢", "Roles Found", str(len(experience)), "in work history", "#22c55e")
        with k4: kpi("📋", "Completeness", f"{completeness_pct}%", "resume quality score", comp_color)

        # ── Diagnostics ──
        if diag.get("missing_sections"):
            st.warning(f"Missing sections: {', '.join(diag['missing_sections'])} — consider adding them.")
        if not diag.get("has_quantified_achievements"):
            st.warning("Few quantified achievements detected. Add metrics (%, $, team size) to strengthen your resume.")

        col_left, col_right = st.columns([1, 1], gap="large")

        with col_left:
            # ── Achievements ──
            if profile.get("top_achievements"):
                sec("QUANTIFIED ACHIEVEMENTS", "🏆")
                for ach in profile["top_achievements"]:
                    st.markdown(f"""
                    <div style="background:linear-gradient(135deg,#0d1825,#111d2e);border:1px solid #1e2d42;
                                border-radius:10px;padding:10px 14px;margin-bottom:6px;
                                border-left:3px solid #f59e0b">
                        <div style="color:#fbbf24;font-size:0.82rem">{ach}</div>
                    </div>""", unsafe_allow_html=True)

            # ── Skills by cluster ──
            sec("SKILLS BY CLUSTER", "⚡")
            cluster_map: dict[str, list[str]] = {}
            for s in skills:
                cluster = s.get("cluster", "General")
                cluster_map.setdefault(cluster, []).append(s["normalized_name"])

            cluster_colors = [
                "#1d6bf3","#8b5cf6","#22c55e","#f59e0b","#ef4444",
                "#ec4899","#14b8a6","#f97316","#60a5fa","#a78bfa",
            ]
            for ci, (cluster, skill_list) in enumerate(sorted(cluster_map.items(), key=lambda x: -len(x[1]))):
                cc = cluster_colors[ci % len(cluster_colors)]
                chips = "".join(
                    f'<span style="display:inline-block;background:rgba(255,255,255,0.04);'
                    f'color:#94a3b8;border:1px solid #1e2d42;border-radius:20px;'
                    f'padding:3px 10px;margin:2px;font-size:0.73rem">{s}</span>'
                    for s in skill_list[:8]
                )
                extra = f'<span style="color:#4b5a7a;font-size:0.72rem;margin:2px">+{len(skill_list)-8} more</span>' if len(skill_list) > 8 else ""
                st.markdown(f"""
                <div style="margin-bottom:12px">
                    <div style="font-size:0.68rem;font-weight:700;text-transform:uppercase;
                                letter-spacing:0.1em;color:{cc};margin-bottom:5px">{cluster}</div>
                    <div>{chips}{extra}</div>
                </div>""", unsafe_allow_html=True)

        with col_right:
            # ── Skills chart ──
            sec("SKILL DISTRIBUTION", "📊")
            if cluster_map:
                chart_data = [{"Cluster": c, "Count": len(s), "Skills": ", ".join(s[:4])}
                               for c, s in sorted(cluster_map.items(), key=lambda x: -len(x[1]))]
                df = pd.DataFrame(chart_data)
                fig = px.bar(df, x="Count", y="Cluster", orientation="h",
                              text="Count", color="Count",
                              color_continuous_scale=["#1254c0","#1d6bf3","#60a5fa"],
                              hover_data={"Skills": True})
                fig.update_traces(textposition="outside")
                fig.update_layout(
                    paper_bgcolor="#0d1520", plot_bgcolor="#0d1520",
                    font_color="#94a3b8", showlegend=False, coloraxis_showscale=False,
                    margin=dict(l=0, r=20, t=10, b=10), height=max(200, len(chart_data) * 32),
                    yaxis=dict(tickfont=dict(size=11, color="#94a3b8")),
                    xaxis=dict(gridcolor="#0f1e30", tickfont=dict(size=9)),
                )
                st.plotly_chart(fig, use_container_width=True)

        # ── Experience timeline ──
        if experience:
            sec("EXPERIENCE TIMELINE", "🏢")
            for exp in experience[:6]:
                dur = exp.get("duration_months", 0) or 0
                dur_str = f"{dur // 12}y {dur % 12}m" if dur >= 12 else f"{dur}m"
                is_current = exp.get("is_current", False)
                curr_badge = '<span class="exp-badge">CURRENT</span>' if is_current else ""
                start = exp.get("start_date","")[:7]
                end = "Present" if is_current else exp.get("end_date","")[:7]
                achs = exp.get("achievements",[])
                ach_html = "".join(f'<div style="color:#64748b;font-size:0.78rem;margin-top:4px">↳ {a}</div>' for a in achs[:2])
                st.markdown(f"""
                <div class="exp-card {'current' if is_current else ''}">
                    <div class="exp-title">{exp.get('title','?')}{curr_badge}</div>
                    <div class="exp-company">{exp.get('company','?')}</div>
                    <div class="exp-dates">{start} → {end} &nbsp;·&nbsp; {dur_str}</div>
                    {ach_html}
                </div>""", unsafe_allow_html=True)

    footer()


# ══════════════════════════════════════════════════════════════════════════════
# TAB 2 — JD Fit
# ══════════════════════════════════════════════════════════════════════════════

with tab_jd:
    banner("Job Fit Analysis",
           "Paste any JD · Fit score (0–100) · Gap cards · ATS keyword audit · Skill match chart",
           accent="#8b5cf6", bg=career2_bg)

    if not st.session_state.get("parsed_resume"):
        st.info("Parse your resume in the **Resume** tab first to unlock fit analysis.")

    st.markdown('<div style="font-size:0.72rem;font-weight:700;text-transform:uppercase;letter-spacing:0.1em;color:#4b5a7a;margin-bottom:8px">Paste Job Description</div>', unsafe_allow_html=True)
    jd_text = st.text_area("", value=st.session_state.get("raw_jd_text",""),
                             height=240,
                             placeholder="Paste the full JD including requirements, responsibilities, and nice-to-haves...",
                             label_visibility="collapsed")
    if jd_text != st.session_state.get("raw_jd_text",""):
        st.session_state["raw_jd_text"] = jd_text
        st.session_state.pop("parsed_jd", None)
        st.session_state.pop("fit_result", None)

    analyze_disabled = not (jd_text.strip() and st.session_state.get("parsed_resume"))

    if st.button("🎯 Analyze Fit", type="primary", disabled=analyze_disabled):
        with st.spinner("Parsing JD..."):
            parsed_jd = cached_interpret_jd(jd_text)
            st.session_state["parsed_jd"] = parsed_jd
        with st.spinner("Computing fit score..."):
            fit = compute_fit(parsed_jd, st.session_state["parsed_resume"])
            st.session_state["fit_result"] = fit
            st.session_state.pop("ai_analysis", None)
            st.session_state.pop("cover_letter", None)
        st.rerun()

    # JD meta tags
    if st.session_state.get("parsed_jd"):
        jd = st.session_state["parsed_jd"]
        tags = []
        if jd.get("target_role"): tags.append(f"💼 {jd['target_role']}")
        if jd.get("seniority"): tags.append(f"🏷️ {jd['seniority'].title()}")
        if jd.get("work_mode"): tags.append(f"🏠 {jd['work_mode'].title()}")
        if jd.get("location"): tags.append(f"📍 {jd['location']}")
        if jd.get("compensation"): tags.append(f"💰 {jd['compensation']}")
        if tags:
            html = "".join(f'<span class="jd-tag">{t}</span>' for t in tags)
            st.markdown(f'<div style="margin:12px 0">{html}</div>', unsafe_allow_html=True)

    if st.session_state.get("fit_result"):
        fit = st.session_state["fit_result"]
        jd  = st.session_state["parsed_jd"]

        # ── Score row ──
        sec("FIT SCORE", "🎯")
        col_gauge, col_k1, col_k2, col_k3 = st.columns([2, 1, 1, 1])

        with col_gauge:
            score = fit["fit_score"]
            color = fit["fit_color"]
            fig_gauge = go.Figure(go.Indicator(
                mode="gauge+number",
                value=score,
                title={"text": fit["fit_label"], "font": {"color": "#94a3b8", "size": 14}},
                number={"font": {"color": color, "size": 52}, "suffix": "/100"},
                gauge={
                    "axis": {"range": [0,100], "tickcolor": "#1e2d42",
                             "tickfont": {"color": "#4b5a7a"}, "tickwidth": 1},
                    "bar": {"color": color, "thickness": 0.22},
                    "bgcolor": "#0d1520",
                    "bordercolor": "#1e2d42",
                    "steps": [
                        {"range": [0,  40], "color": "rgba(239,68,68,0.08)"},
                        {"range": [40, 60], "color": "rgba(245,158,11,0.08)"},
                        {"range": [60, 80], "color": "rgba(34,197,94,0.08)"},
                        {"range": [80,100], "color": "rgba(34,197,94,0.15)"},
                    ],
                    "threshold": {"line": {"color": color, "width": 3}, "thickness": 0.75, "value": score},
                },
            ))
            fig_gauge.update_layout(
                paper_bgcolor="#0d1520", font_color="#e6edf3",
                height=240, margin=dict(l=20, r=20, t=30, b=0),
            )
            st.plotly_chart(fig_gauge, use_container_width=True)

        sm = fit["skill_match_pct"]
        ra = fit["role_alignment"]
        sg = fit["seniority_gap"]
        with col_k1: kpi("⚡", "Skill Match", f"{sm}%", "must-have skills", "#22c55e" if sm >= 70 else "#f59e0b" if sm >= 40 else "#ef4444")
        with col_k2: kpi("🎯", "Role Alignment", f"{ra}%", "role family match", "#22c55e" if ra >= 70 else "#f59e0b" if ra >= 40 else "#ef4444")
        with col_k3: kpi("📊", "Seniority Gap", str(sg), "level difference", "#22c55e" if sg == 0 else "#f59e0b" if sg == 1 else "#ef4444")

        # ── Skill match bar chart ──
        must_have = jd.get("must_have_skills", [])
        if must_have:
            sec("MUST-HAVE SKILL MATCH", "⚡")
            strong_set   = set(s.lower() for s in fit["strengths"])
            evidence_set = set(s.lower() for s in fit["evidence_gaps"])
            chart_rows = []
            for skill in must_have:
                sl = skill.lower()
                if sl in strong_set:
                    status, val = "Strong Match", 3
                elif sl in evidence_set:
                    status, val = "Needs Evidence", 2
                else:
                    status, val = "Missing", 1
                chart_rows.append({"Skill": skill, "Status": status, "Val": val})
            df_skills = pd.DataFrame(chart_rows)
            color_map = {"Strong Match": "#22c55e", "Needs Evidence": "#f59e0b", "Missing": "#ef4444"}
            fig_skills = px.bar(df_skills, x="Val", y="Skill", orientation="h",
                                 color="Status", color_discrete_map=color_map,
                                 category_orders={"Status": ["Strong Match","Needs Evidence","Missing"]})
            fig_skills.update_traces(width=0.55)
            fig_skills.update_layout(
                paper_bgcolor="#0d1520", plot_bgcolor="#0d1520",
                font_color="#94a3b8", showlegend=True,
                legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="left", x=0,
                            font=dict(color="#94a3b8", size=11)),
                xaxis=dict(visible=False),
                height=max(180, len(must_have) * 32),
                margin=dict(l=0, r=10, t=40, b=0),
                yaxis=dict(tickfont=dict(size=11, color="#94a3b8")),
            )
            st.plotly_chart(fig_skills, use_container_width=True)

        # ── Gaps & Strengths ──
        sec("GAPS & STRENGTHS", "🔍")
        col_gaps, col_str = st.columns([1, 1], gap="large")

        with col_gaps:
            st.markdown('<div style="font-weight:700;color:#f1f5f9;margin-bottom:12px">⚠️ Gaps to Address</div>', unsafe_allow_html=True)
            gap_cards = fit.get("gap_cards", [])
            if gap_cards:
                for card in gap_cards:
                    sev = card["severity"]
                    icon = "🔴" if sev == "high" else "🟡" if sev == "medium" else "🟢"
                    st.markdown(f"""
                    <div class="gap-card-new {sev}">
                        <div class="gap-label">{icon} {card['label']}</div>
                        <div class="gap-why">{card['why']}</div>
                    </div>""", unsafe_allow_html=True)
            else:
                st.markdown("""
                <div class="gap-card-new low">
                    <div class="gap-label">🟢 No major gaps detected</div>
                    <div class="gap-why">Strong alignment with this role's requirements.</div>
                </div>""", unsafe_allow_html=True)

            if fit.get("nice_to_have_missing"):
                with st.expander(f"Nice-to-have missing ({len(fit['nice_to_have_missing'])})"):
                    html = "".join(f'<span class="ats-missing">{s}</span>' for s in fit["nice_to_have_missing"])
                    st.markdown(html, unsafe_allow_html=True)

        with col_str:
            st.markdown('<div style="font-weight:700;color:#f1f5f9;margin-bottom:12px">✅ Your Strengths for This Role</div>', unsafe_allow_html=True)
            if fit.get("strengths"):
                for s in fit["strengths"]:
                    st.markdown(f"""
                    <div class="strength-card-new">
                        <div class="s-icon">✅</div>
                        <div class="s-text">{s}</div>
                    </div>""", unsafe_allow_html=True)
            else:
                st.info("No confirmed must-have skill matches found.")

        # ── ATS audit ──
        sec("ATS KEYWORD AUDIT", "🔑")
        st.markdown('<div style="color:#4b5a7a;font-size:0.78rem;margin-bottom:10px">Green = found in resume · Red strikethrough = missing from JD keywords</div>', unsafe_allow_html=True)
        ats_html = ""
        for kw in fit.get("ats_present", []):
            ats_html += f'<span class="ats-present">✓ {kw}</span>'
        for kw in fit.get("ats_missing", []):
            ats_html += f'<span class="ats-missing">✗ {kw}</span>'
        if ats_html:
            st.markdown(ats_html, unsafe_allow_html=True)
        else:
            st.caption("No keyword data available.")

    footer()


# ══════════════════════════════════════════════════════════════════════════════
# TAB 3 — AI Analysis
# ══════════════════════════════════════════════════════════════════════════════

with tab_analysis:
    banner("AI Career Strategist",
           "Strengths · critical gaps · red flags · salary range · 5 tailoring actions",
           accent="#22c55e", bg=career3_bg)

    if not st.session_state.get("fit_result"):
        st.markdown("""
        <div style="background:linear-gradient(135deg,#0f1825,#131d2e);border:1px solid #1e2d42;
                    border-radius:16px;padding:32px;text-align:center;margin:20px 0">
            <div style="font-size:2rem;margin-bottom:12px">🤖</div>
            <div style="font-weight:700;color:#f1f5f9;font-size:1.1rem;margin-bottom:8px">AI Analysis Not Yet Available</div>
            <div style="color:#64748b;font-size:0.85rem">Complete the fit analysis in the <strong style="color:#8b5cf6">JD Fit</strong> tab first.</div>
        </div>""", unsafe_allow_html=True)
    else:
        fit = st.session_state["fit_result"]
        jd  = st.session_state["parsed_jd"]
        pr  = st.session_state["parsed_resume"]

        if st.session_state.get("ai_analysis"):
            sec("AI ASSESSMENT", "🤖")
            st.markdown(f'<div class="ai-output">{st.session_state["ai_analysis"]}</div>', unsafe_allow_html=True)
            st.markdown("")
            col_dl, col_regen, _ = st.columns([1, 1, 2])
            with col_dl:
                st.download_button("⬇️ Download Analysis",
                    data=st.session_state["ai_analysis"],
                    file_name="jd_fit_analysis.md", mime="text/markdown",
                    use_container_width=True)
            with col_regen:
                if st.button("🔄 Regenerate", use_container_width=True):
                    st.session_state.pop("ai_analysis", None)
                    st.rerun()
        else:
            st.markdown("""
            <div style="background:linear-gradient(135deg,#0d1825,#111d2e);border:1px solid #1e2d42;
                        border-radius:14px;padding:20px 24px;margin-bottom:20px">
                <div style="font-weight:700;color:#f1f5f9;margin-bottom:8px">What you'll get:</div>
                <div style="display:grid;grid-template-columns:1fr 1fr;gap:8px">
                    <div style="color:#94a3b8;font-size:0.82rem">📋 Overall fit assessment</div>
                    <div style="color:#94a3b8;font-size:0.82rem">💪 Top 5 strengths</div>
                    <div style="color:#94a3b8;font-size:0.82rem">⚠️ Top 5 critical gaps</div>
                    <div style="color:#94a3b8;font-size:0.82rem">🚩 Red flags & risks</div>
                    <div style="color:#94a3b8;font-size:0.82rem">💰 Salary negotiation range</div>
                    <div style="color:#94a3b8;font-size:0.82rem">✏️ 5 tailoring actions</div>
                </div>
            </div>""", unsafe_allow_html=True)

            if not _ai_available:
                st.warning("Set `OLLAMA_BASE_URL` in Streamlit Cloud → Settings → Secrets and start your Cloudflare tunnel.")
            elif st.button("🤖 Generate AI Analysis", type="primary"):
                context = build_ai_context(jd, pr, fit)
                system_prompt = """You are an expert career strategist and talent advisor.
You receive structured fit data comparing a candidate's resume to a job description.
Give a rigorous, honest, actionable assessment. Be specific — name skills, reference the data.
Format your response with clear sections using markdown headers."""
                user_prompt = f"""Here is the fit data:\n\n{context}\n\nProvide:
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
Specific changes the candidate should make to their resume or cover letter to improve fit for THIS role."""
                result = render_ai_output(user_prompt, system=system_prompt, max_tokens=1400, temperature=0.72)
                if result and not result.startswith("⚠️"):
                    st.session_state["ai_analysis"] = result
                    st.rerun()

    footer()


# ══════════════════════════════════════════════════════════════════════════════
# TAB 4 — Cover Letter
# ══════════════════════════════════════════════════════════════════════════════

with tab_cover:
    banner("Cover Letter Generator",
           "Tone & length controls · AI-written · draws on real achievements · ready to copy",
           accent="#f59e0b", bg=hero_bg)

    if not st.session_state.get("fit_result"):
        st.markdown("""
        <div style="background:linear-gradient(135deg,#0f1825,#131d2e);border:1px solid #1e2d42;
                    border-radius:16px;padding:32px;text-align:center;margin:20px 0">
            <div style="font-size:2rem;margin-bottom:12px">✍️</div>
            <div style="font-weight:700;color:#f1f5f9;font-size:1.1rem;margin-bottom:8px">Complete Fit Analysis First</div>
            <div style="color:#64748b;font-size:0.85rem">Go to <strong style="color:#8b5cf6">JD Fit</strong> tab and run the analysis.</div>
        </div>""", unsafe_allow_html=True)
    else:
        fit = st.session_state["fit_result"]
        jd  = st.session_state["parsed_jd"]
        pr  = st.session_state["parsed_resume"]

        col_opts, col_out = st.columns([1, 2], gap="large")

        with col_opts:
            st.markdown("""
            <div style="background:linear-gradient(135deg,#0f1825,#131d2e);border:1px solid #1e2d42;
                        border-radius:16px;padding:20px 22px;margin-bottom:4px">
                <div style="font-weight:700;color:#f1f5f9;margin-bottom:16px">Style Options</div>""",
            unsafe_allow_html=True)
            tone = st.selectbox("Tone", [
                "Professional & concise", "Warm & conversational",
                "Confident & direct", "Formal"
            ])
            word_count = st.select_slider("Target length",
                options=[150, 200, 250, 300, 350], value=250)
            focus = st.multiselect("Emphasise", [
                "Technical skills", "Leadership", "Quantified achievements",
                "Domain expertise", "Growth trajectory"
            ], default=["Technical skills", "Quantified achievements"])
            st.markdown("</div>", unsafe_allow_html=True)

            if not _ai_available:
                st.warning("Set `OLLAMA_BASE_URL` in secrets to enable AI.")
            else:
                generate_cl = st.button("✍️ Generate Cover Letter", type="primary", use_container_width=True)

        with col_out:
            if st.session_state.get("cover_letter"):
                sec("YOUR COVER LETTER", "✍️")
                cl_text = st.session_state["cover_letter"]
                st.markdown(f'<div class="cl-output">{cl_text}</div>', unsafe_allow_html=True)
                st.markdown("")
                col_dl2, col_regen2 = st.columns(2)
                with col_dl2:
                    st.download_button("⬇️ Download .txt", data=cl_text,
                        file_name="cover_letter.txt", mime="text/plain",
                        use_container_width=True)
                with col_regen2:
                    if st.button("🔄 Regenerate", key="regen_cl", use_container_width=True):
                        st.session_state.pop("cover_letter", None)
                        st.rerun()
            elif not (st.session_state.get("cover_letter") or (not _ai_available)):
                st.markdown("""
                <div style="background:linear-gradient(135deg,#0f1825,#131d2e);border:1px solid #1e2d42;
                            border-radius:14px;padding:32px;text-align:center;height:300px;
                            display:flex;flex-direction:column;align-items:center;justify-content:center">
                    <div style="font-size:2rem;margin-bottom:12px">📝</div>
                    <div style="color:#4b5a7a;font-size:0.85rem">Your cover letter will appear here</div>
                </div>""", unsafe_allow_html=True)

        if _ai_available and "generate_cl" in dir() and generate_cl:
            context = build_ai_context(jd, pr, fit)
            emphasis_str = ", ".join(focus) if focus else "general fit"
            system_prompt = """You are an expert cover letter writer. Write compelling, human-sounding cover letters
that do NOT sound AI-generated. Draw on real data from the candidate's profile.
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

Format: Plain paragraphs ready to copy. No headers. No placeholders like [Company Name] — infer from the JD if possible or use "your team"."""
            result = render_ai_output(user_prompt, system=system_prompt, max_tokens=600, temperature=0.75)
            if result and not result.startswith("⚠️"):
                st.session_state["cover_letter"] = result
                st.rerun()

    footer()


# ══════════════════════════════════════════════════════════════════════════════
# TAB 5 — About
# ══════════════════════════════════════════════════════════════════════════════
with tab_about:
    st.markdown("""
    <div style="border-radius:24px;overflow:hidden;position:relative;height:260px;
                background-image:{career_bg};background-size:cover;background-position:center;
                border:1px solid #1e2d42;margin-bottom:32px">
        <div style="position:absolute;inset:0;
                    background:linear-gradient(135deg,rgba(7,9,15,0.92) 0%,rgba(7,9,15,0.6) 100%)"></div>
        <div style="position:relative;z-index:1;padding:48px;height:100%;
                    display:flex;flex-direction:column;justify-content:center;align-items:center;text-align:center">
            <div style="font-size:0.7rem;font-weight:700;text-transform:uppercase;
                        letter-spacing:0.2em;color:#1d6bf3;margin-bottom:12px">Portfolio Project</div>
            <div style="font-size:2.5rem;font-weight:900;color:#f1f5f9;line-height:1">JD Fit Analyzer</div>
            <div style="color:#64748b;margin-top:12px;max-width:520px;line-height:1.7;font-size:0.88rem">
                AI-powered resume × job description fit scorer. Upload your CV, paste a JD,
                and get a detailed gap analysis, skill match, ATS audit, and a tailored cover letter —
                all running locally with no data stored.
            </div>
        </div>
    </div>""", unsafe_allow_html=True)

    ca, cb = st.columns(2)
    with ca:
        st.markdown("""
        <div style="background:linear-gradient(135deg,#0f1825,#111d2e);border:1px solid #1e2d42;
                    border-radius:20px;padding:24px;margin-bottom:16px">
            <div style="font-weight:800;color:#f1f5f9;font-size:1rem;margin-bottom:16px">🎯 Features</div>
            <div style="color:#64748b;line-height:2.2;font-size:0.88rem">
                📄 <strong style="color:#94a3b8">Resume Parser</strong> — PDF/DOCX extraction, skills, experience<br>
                📋 <strong style="color:#94a3b8">JD Fit Score</strong> — Weighted match with ATS audit<br>
                🤖 <strong style="color:#94a3b8">AI Analysis</strong> — Career strategy, gap bridging, positioning<br>
                ✍️ <strong style="color:#94a3b8">Cover Letter</strong> — Tailored draft, tone + length control<br>
                💬 <strong style="color:#94a3b8">Follow-up Chat</strong> — Multi-turn Q&A on your fit
            </div>
        </div>
        <div style="background:linear-gradient(135deg,#0f1825,#111d2e);border:1px solid #1e2d42;
                    border-radius:20px;padding:24px">
            <div style="font-weight:800;color:#f1f5f9;font-size:1rem;margin-bottom:16px">🔒 Privacy</div>
            <div style="color:#64748b;line-height:1.8;font-size:0.88rem">
                No resume data is stored server-side. All parsing runs in-memory per session.
                AI analysis runs on a local Ollama instance via a private Cloudflare tunnel —
                nothing is sent to OpenAI or any commercial AI provider.
                Your data disappears when you close the tab.
            </div>
        </div>
        """, unsafe_allow_html=True)

    with cb:
        st.markdown("""
        <div style="background:linear-gradient(135deg,#0f1825,#111d2e);border:1px solid #1e2d42;
                    border-radius:20px;padding:24px;margin-bottom:16px">
            <div style="font-weight:800;color:#f1f5f9;font-size:1rem;margin-bottom:16px">👨‍💻 Built by</div>
            <div style="font-size:1.1rem;font-weight:700;color:#e2e8f0">Sameer Bhalerao</div>
            <div style="color:#4b5a7a;font-size:0.85rem;margin-top:2px">Senior Analytics & AI Product Leader · Amazon L6</div>
            <div style="margin-top:14px;display:flex;gap:10px;flex-wrap:wrap">
                <a href="https://www.linkedin.com/in/sameervb" target="_blank"
                   style="background:#0d1e30;border:1px solid #1a3050;border-radius:8px;padding:6px 14px;
                          color:#60a5fa;font-size:0.8rem;text-decoration:none">LinkedIn</a>
                <a href="https://github.com/sameervb" target="_blank"
                   style="background:#0d1e30;border:1px solid #1a3050;border-radius:8px;padding:6px 14px;
                          color:#94a3b8;font-size:0.8rem;text-decoration:none">GitHub</a>
                <a href="https://soulspark.me" target="_blank"
                   style="background:#0d1420;border:1px solid #1a2d42;border-radius:8px;padding:6px 14px;
                          color:#1d6bf3;font-size:0.8rem;text-decoration:none">Soul Spark</a>
            </div>
            <div style="color:#334155;font-size:0.82rem;line-height:1.7;margin-top:16px">
                This is one of 10 standalone public apps extracted from
                <a href="https://soulspark.me" style="color:#1d6bf3">Soul Spark</a> — a local-first
                personal intelligence platform built end-to-end in 8 weeks.
            </div>
        </div>
        <div style="background:linear-gradient(135deg,#0f1825,#111d2e);border:1px solid #1e2d42;
                    border-radius:20px;padding:24px">
            <div style="font-weight:800;color:#f1f5f9;font-size:1rem;margin-bottom:16px">🛠️ Tech Stack</div>
            <div style="display:flex;flex-wrap:wrap;gap:8px">
        """, unsafe_allow_html=True)
        for badge in ["Python 3.14", "Streamlit", "pdfplumber", "python-docx",
                      "Plotly", "Pandas", "Ollama (LLaMA 3.1)", "Cloudflare Tunnel",
                      "Streamlit Community Cloud"]:
            st.markdown(
                f'<span style="background:#0a1420;border:1px solid #1e3050;border-radius:20px;'
                f'padding:5px 12px;color:#94a3b8;font-size:0.75rem">{badge}</span>',
                unsafe_allow_html=True,
            )
        st.markdown("</div></div>", unsafe_allow_html=True)

    footer()
