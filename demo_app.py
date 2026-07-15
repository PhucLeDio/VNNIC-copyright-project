# ╔══════════════════════════════════════════════════════════════════╗
# ║  KSCAN — Full Demo Application                           ║
# ║  Chạy: streamlit run demo_app.py                               ║
# ╚══════════════════════════════════════════════════════════════════╝

import os
import json
import glob
import time
import threading
import pandas as pd
from PIL import Image
import streamlit as st

# ─────────────────────────────────────────────
# PAGE CONFIG (must be first Streamlit call)
# ─────────────────────────────────────────────
st.set_page_config(
    page_title="KSCAN — AI Copyright Detection Demo",
    page_icon="🛡️",
    layout="wide",
    initial_sidebar_state="expanded",
)

from pipeline_runner import (
    normalize_domain,
    find_cached_result,
    list_all_cached_domains,
    start_pipeline_thread,
    PipelineState,
    PIPELINE_STEPS,
    LOGS_BASE,
)

# ─────────────────────────────────────────────
# GLOBAL CSS
# ─────────────────────────────────────────────
st.markdown("""
<style>
  @import url('https://fonts.googleapis.com/css2?family=Inter:wght@300;400;500;600;700;800&display=swap');

  /* ── Global dark theme override ── */
  html, body, [class*="css"] {
    font-family: 'Inter', sans-serif;
    color: #e2e8f0 !important;
  }

  /* Hide Streamlit top toolbar & footer */
  header[data-testid="stHeader"] { background: #0d1117 !important; }
  header[data-testid="stHeader"]::before { background: #0d1117 !important; }
  #MainMenu, footer, [data-testid="stToolbar"] { visibility: hidden !important; }
  [data-testid="stDecoration"] { display: none !important; }

  /* Force dark background on entire app */
  .stApp {
    background-color: #0d1117 !important;
  }

  /* Main content area */
  section[data-testid="stMain"] > div,
  .main .block-container {
    background-color: #0d1117 !important;
    color: #e2e8f0 !important;
  }

  /* All text elements */
  p, span, div, label, li, td, th, h1, h2, h3, h4, h5, h6 {
    color: #e2e8f0 !important;
  }

  /* Headings - extra bright */
  h1, h2, h3 { color: #f1f5f9 !important; font-weight: 700 !important; }
  h4, h5     { color: #e2e8f0 !important; font-weight: 600 !important; }

  /* Streamlit markdown text */
  .stMarkdown p, .stMarkdown span, .stMarkdown div { color: #e2e8f0 !important; }

  /* Tab labels */
  .stTabs [data-baseweb="tab"] {
    font-weight: 600;
    font-size: 0.9rem;
    color: #94a3b8 !important;
  }
  .stTabs [aria-selected="true"] {
    color: #818cf8 !important;
  }

  /* Input fields */
  .stTextInput input {
    background: #1e293b !important;
    color: #f1f5f9 !important;
    border-color: rgba(99,102,241,0.4) !important;
    font-size: 0.95rem !important;
  }
  .stTextInput input::placeholder { color: #64748b !important; }
  .stTextInput label { color: #cbd5e1 !important; font-weight: 500 !important; }

  /* Selectbox */
  .stSelectbox div[data-baseweb="select"] > div {
    background: #1e293b !important;
    color: #f1f5f9 !important;
    border-color: rgba(71,85,105,0.6) !important;
  }
  .stSelectbox label { color: #cbd5e1 !important; }

  /* Checkbox */
  .stCheckbox label { color: #cbd5e1 !important; font-weight: 500 !important; }
  .stCheckbox span  { color: #cbd5e1 !important; }

  /* Caption / small text */
  .stCaption, small, caption { color: #94a3b8 !important; }

  /* Expander */
  .streamlit-expanderHeader { 
    color: #cbd5e1 !important;
    font-weight: 600 !important;
    background: rgba(30,41,59,0.7) !important;
  }
  .streamlit-expanderContent {
    background: rgba(15,23,42,0.8) !important;
    border-color: rgba(51,65,85,0.6) !important;
  }

  /* Metric component */
  [data-testid="metric-container"] label { color: #94a3b8 !important; }
  [data-testid="metric-container"] [data-testid="stMetricValue"] {
    color: #f1f5f9 !important;
    font-weight: 700 !important;
  }

  /* Dataframe */
  .stDataFrame { color: #e2e8f0 !important; }
  [data-testid="stDataFrame"] th { color: #94a3b8 !important; }
  [data-testid="stDataFrame"] td { color: #e2e8f0 !important; }

  /* Alert boxes - override default */
  .stAlert > div { color: #e2e8f0 !important; }
  [data-baseweb="notification"] { color: #e2e8f0 !important; }

  /* Progress bar */
  .stProgress > div > div { background: linear-gradient(90deg, #6366f1, #818cf8) !important; }

  /* Button */
  .stButton > button {
    font-weight: 600 !important;
    letter-spacing: 0.02em !important;
  }

  /* Sidebar */
  div[data-testid="stSidebarContent"] {
    background: linear-gradient(180deg, #0a0f1e 0%, #0f172a 100%) !important;
    color: #e2e8f0 !important;
  }
  div[data-testid="stSidebarContent"] p,
  div[data-testid="stSidebarContent"] span,
  div[data-testid="stSidebarContent"] div,
  div[data-testid="stSidebarContent"] label {
    color: #e2e8f0 !important;
  }

  /* ── Hero header ── */
  .hero-header {
    background: linear-gradient(135deg, #0f172a 0%, #1e1b4b 50%, #0f172a 100%);
    border: 1px solid rgba(99,102,241,0.35);
    border-radius: 16px;
    padding: 28px 32px;
    margin-bottom: 24px;
    position: relative;
    overflow: hidden;
  }
  .hero-header::before {
    content: '';
    position: absolute;
    top: -50%; left: -50%;
    width: 200%; height: 200%;
    background: radial-gradient(circle at 60% 40%, rgba(99,102,241,0.15) 0%, transparent 60%);
    pointer-events: none;
  }
  .hero-title {
    font-size: 2rem;
    font-weight: 800;
    background: linear-gradient(90deg, #818cf8, #c084fc, #38bdf8);
    -webkit-background-clip: text;
    -webkit-text-fill-color: transparent;
    margin: 0; line-height: 1.2;
  }
  .hero-sub {
    color: #cbd5e1 !important;
    font-size: 0.95rem;
    margin-top: 6px;
  }
  .version-badge {
    display: inline-block;
    background: rgba(99,102,241,0.2);
    color: #818cf8 !important;
    border: 1px solid rgba(99,102,241,0.4);
    border-radius: 999px;
    padding: 2px 12px;
    font-size: 0.75rem;
    font-weight: 600;
    letter-spacing: 0.05em;
    margin-left: 12px;
    vertical-align: middle;
  }

  /* ── URL input wrapper ── */
  .url-input-wrapper {
    background: rgba(30,41,59,0.6);
    border: 1.5px solid rgba(99,102,241,0.35);
    border-radius: 14px;
    padding: 20px 24px;
    margin-bottom: 18px;
  }

  /* ── Step pipeline cards ── */
  .step-card {
    border-radius: 12px;
    padding: 14px 18px;
    margin-bottom: 10px;
    border: 1px solid;
    transition: all 0.3s ease;
    display: flex;
    align-items: center;
    gap: 12px;
  }
  .step-pending { background: rgba(15,23,42,0.8); border-color: rgba(71,85,105,0.5); }
  .step-pending .step-label { color: #94a3b8 !important; }
  .step-pending .step-desc  { color: #64748b !important; }
  .step-running {
    background: rgba(59,130,246,0.1);
    border-color: rgba(59,130,246,0.6);
    box-shadow: 0 0 20px rgba(59,130,246,0.18);
    animation: pulse-blue 1.5s infinite;
  }
  .step-running .step-label { color: #93c5fd !important; }
  .step-running .step-desc  { color: #7dd3fc !important; }
  .step-done { background: rgba(16,185,129,0.08); border-color: rgba(16,185,129,0.45); }
  .step-done .step-label { color: #6ee7b7 !important; }
  .step-done .step-desc  { color: #34d399 !important; }
  .step-error { background: rgba(239,68,68,0.08); border-color: rgba(239,68,68,0.45); }
  .step-error .step-label { color: #fca5a5 !important; }

  @keyframes pulse-blue {
    0%,100% { box-shadow: 0 0 12px rgba(59,130,246,0.15); }
    50%      { box-shadow: 0 0 28px rgba(59,130,246,0.35); }
  }
  .step-icon { font-size: 1.3rem; min-width: 28px; }
  .step-label { font-weight: 600; font-size: 0.9rem; }
  .step-desc  { font-size: 0.78rem; margin-top: 2px; }
  .step-status-badge {
    margin-left: auto;
    font-size: 0.75rem;
    font-weight: 600;
    padding: 3px 11px;
    border-radius: 999px;
    white-space: nowrap;
  }
  .badge-pending { background: rgba(71,85,105,0.35); color: #94a3b8 !important; }
  .badge-running { background: rgba(59,130,246,0.25); color: #93c5fd !important; }
  .badge-done    { background: rgba(16,185,129,0.22); color: #6ee7b7 !important; }
  .badge-error   { background: rgba(239,68,68,0.22); color: #fca5a5 !important; }

  /* ── Log terminal ── */
  .log-terminal {
    background: #060d17;
    border: 1px solid #1e293b;
    border-radius: 10px;
    padding: 14px 16px;
    font-family: 'Courier New', monospace;
    font-size: 0.78rem;
    color: #7dd3fc;
    max-height: 280px;
    overflow-y: auto;
    line-height: 1.65;
  }
  .log-line-error { color: #fca5a5 !important; }
  .log-line-warn  { color: #fde68a !important; }
  .log-line-ok    { color: #6ee7b7 !important; }

  /* ── Verdict banners ── */
  .verdict-vi-pham {
    background: linear-gradient(135deg, rgba(239,68,68,0.18), rgba(220,38,38,0.08));
    border: 1.5px solid rgba(239,68,68,0.5);
    border-radius: 14px;
    padding: 22px 28px;
    text-align: center;
  }
  .verdict-an-toan {
    background: linear-gradient(135deg, rgba(16,185,129,0.15), rgba(5,150,105,0.07));
    border: 1.5px solid rgba(16,185,129,0.45);
    border-radius: 14px;
    padding: 22px 28px;
    text-align: center;
  }
  .verdict-title {
    font-size: 1.55rem;
    font-weight: 800;
    margin-bottom: 6px;
  }
  .verdict-conf { font-size: 0.92rem; color: #cbd5e1 !important; }

  /* ── Metric cards ── */
  .metric-grid {
    display: grid;
    grid-template-columns: repeat(auto-fit, minmax(130px, 1fr));
    gap: 12px;
    margin: 16px 0;
  }
  .metric-card {
    background: rgba(30,41,59,0.85);
    border: 1px solid rgba(51,65,85,0.9);
    border-radius: 12px;
    padding: 16px;
    text-align: center;
    transition: transform 0.2s, border-color 0.2s;
  }
  .metric-card:hover { transform: translateY(-2px); border-color: rgba(99,102,241,0.5); }
  .metric-value { font-size: 1.5rem; font-weight: 700; color: #f8fafc !important; }
  .metric-label { font-size: 0.75rem; color: #94a3b8 !important; margin-top: 4px; }

  /* ── Signal cards ── */
  .signal-card { padding: 12px 16px; border-radius: 10px; margin-bottom: 8px; border-left: 4px solid; }
  .sig-high   { background: rgba(239,68,68,0.1);  border-left-color: #ef4444; }
  .sig-medium { background: rgba(245,158,11,0.1); border-left-color: #f59e0b; }
  .sig-low    { background: rgba(59,130,246,0.1); border-left-color: #3b82f6; }
  .sig-weight { font-size: 0.72rem; font-weight: 700; letter-spacing: 0.05em; opacity: 0.9; }
  .sig-text   { font-size: 0.88rem; margin-top: 4px; color: #e2e8f0 !important; }

  /* ── Banner evidence cards ── */
  .evidence-card {
    background: rgba(15,23,42,0.95);
    border: 1px solid rgba(51,65,85,0.7);
    border-radius: 12px;
    padding: 14px;
    margin-bottom: 14px;
    transition: transform 0.2s, border-color 0.2s;
  }
  .evidence-card:hover { transform: translateY(-2px); border-color: rgba(99,102,241,0.4); }

  /* ── Quick select chips ── */
  .chip-container { display: flex; flex-wrap: wrap; gap: 8px; margin: 10px 0; }
  .chip {
    display: inline-block;
    background: rgba(30,41,59,0.9);
    border: 1px solid rgba(71,85,105,0.7);
    border-radius: 999px;
    padding: 5px 16px;
    font-size: 0.82rem;
    color: #cbd5e1 !important;
    cursor: pointer;
    transition: all 0.2s;
    font-weight: 500;
  }
  .chip:hover { background: rgba(99,102,241,0.2); border-color: rgba(99,102,241,0.6); color: #818cf8 !important; }
  .chip-vp { border-color: rgba(239,68,68,0.5); color: #fca5a5 !important; }
  .chip-at { border-color: rgba(16,185,129,0.5); color: #6ee7b7 !important; }

  /* Domain history rows */
  .domain-row {
    display: flex; align-items: center; padding: 10px 14px;
    border-radius: 10px; margin-bottom: 6px;
    border: 1px solid rgba(51,65,85,0.7);
    background: rgba(15,23,42,0.8);
    transition: background 0.2s, border-color 0.2s;
    gap: 12px;
  }
  .domain-row:hover { background: rgba(30,41,59,0.9); border-color: rgba(99,102,241,0.4); }
  .domain-name { font-weight: 600; color: #f1f5f9 !important; font-size: 0.92rem; flex: 1; }
  .badge-vp { background: rgba(239,68,68,0.2); color: #fca5a5 !important; border-radius: 999px; padding: 2px 10px; font-size: 0.72rem; font-weight: 700; }
  .badge-at { background: rgba(16,185,129,0.2); color: #6ee7b7 !important; border-radius: 999px; padding: 2px 10px; font-size: 0.72rem; font-weight: 700; }

  /* Custom link */
  a.clink { color: #38bdf8 !important; text-decoration: none; font-weight: 500; }
  a.clink:hover { text-decoration: underline; }

  /* Horizontal rule */
  hr { border-color: rgba(51,65,85,0.6) !important; }
</style>
""", unsafe_allow_html=True)


# ─────────────────────────────────────────────
# SESSION STATE INIT
# ─────────────────────────────────────────────
def _init_state():
    defaults = {
        "active_tab":       0,
        "pipeline_state":   None,
        "pipeline_thread":  None,
        "scan_result":      None,
        "input_url":        "",
        "force_rescan":     False,
        "analysis_started": False,
        "selected_history": None,
        "auto_refresh":     False,
    }
    for k, v in defaults.items():
        if k not in st.session_state:
            st.session_state[k] = v

_init_state()


# ─────────────────────────────────────────────
# SIDEBAR
# ─────────────────────────────────────────────
with st.sidebar:
    st.markdown("""
    <div style="text-align:center; padding: 12px 0 24px;">
      <div style="font-size:2.5rem;">🛡️</div>
      <div style="font-weight:800; font-size:1.1rem; color:#818cf8; letter-spacing:.03em;">KSCAN</div>
      <div style="font-size:0.75rem; color:#475569; margin-top:2px;">AI Copyright Detection System</div>
    </div>
    """, unsafe_allow_html=True)

    st.markdown("---")
    st.markdown("#### 🔬 Thành phần hệ thống")

    components = [
        ("🗂️", "Domain Model", "PhoBERT + 12 features"),
        ("🖥️", "Browser Engine",  "Playwright Stealth"),
        ("🎯", "YOLO Filter",     "Banner detection"),
        ("🔎", "OCR Engine",      "EasyOCR 3-tier"),
        ("🧠", "Content Model",   "PhoBERT fine-tuned"),
        ("✨", "AI Synthesis",    "Gemini 2.5 Flash"),
    ]
    for icon, name, detail in components:
        st.markdown(
            f"<div style='display:flex;align-items:center;gap:8px;padding:5px 0;"
            f"border-bottom:1px solid rgba(30,41,59,0.6);'>"
            f"<span style='font-size:1rem;'>{icon}</span>"
            f"<div><div style='font-size:0.82rem;font-weight:600;color:#e2e8f0;'>{name}</div>"
            f"<div style='font-size:0.72rem;color:#64748b;'>{detail}</div></div></div>",
            unsafe_allow_html=True
        )

    st.markdown("---")

    # API Key status
    gemini_key = os.environ.get("GEMINI_API_KEY", "")
    if gemini_key:
        st.success("🔑 Gemini API: Đã kết nối")
    else:
        st.warning("⚠️ GEMINI_API_KEY chưa set\n\nStep 4 sẽ bị bỏ qua khi scan mới")

    # Recent scans count
    cached = list_all_cached_domains()
    st.markdown("---")
    st.markdown(
        f"<div style='text-align:center;'>"
        f"<div style='font-size:1.8rem;font-weight:800;color:#818cf8;'>{len(cached)}</div>"
        f"<div style='font-size:0.78rem;color:#64748b;'>Domains đã quét</div>"
        f"</div>",
        unsafe_allow_html=True
    )

    vp_count = sum(1 for d in cached if d["verdict"] == "VI_PHAM")
    at_count  = sum(1 for d in cached if d["verdict"] == "AN_TOAN")
    st.markdown(
        f"<div style='display:flex;gap:8px;justify-content:center;margin-top:8px;'>"
        f"<span class='badge-vp' style='padding:4px 12px;border-radius:999px;background:rgba(239,68,68,.2);color:#f87171;font-size:.78rem;font-weight:700;'>🔴 {vp_count} VI PHẠM</span>"
        f"<span class='badge-at' style='padding:4px 12px;border-radius:999px;background:rgba(16,185,129,.2);color:#34d399;font-size:.78rem;font-weight:700;'>🟢 {at_count} AN TOÀN</span>"
        f"</div>",
        unsafe_allow_html=True
    )

    st.markdown("---")
    st.markdown("<div style='font-size:0.7rem;color:#334155;text-align:center;'>v1.0.4.1 · VNNIC Demo 2026</div>", unsafe_allow_html=True)


# ─────────────────────────────────────────────
# HERO HEADER
# ─────────────────────────────────────────────
st.markdown("""
<div class="hero-header">
  <div>
    <span class="hero-title">🛡️ KSCAN</span>
    <span class="version-badge">v1.0.4.1</span>
  </div>
  <div class="hero-sub">
    Hệ thống phát hiện sớm vi phạm bản quyền số & quảng cáo trái phép — AI-powered · VNNIC 2026
  </div>
</div>
""", unsafe_allow_html=True)


# ─────────────────────────────────────────────
# MAIN TABS
# ─────────────────────────────────────────────
tab1, tab2, tab3, tab4 = st.tabs([
    "🔍  Scan Input",
    "⚙️  Processing",
    "📊  Report",
    "📁  History",
])


# ══════════════════════════════════════════════
# TAB 1 — SCAN INPUT
# ══════════════════════════════════════════════
with tab1:
    st.markdown("### Nhập URL / Domain cần kiểm tra")

    # Quick-select chips from cached domains
    cached_domains = list_all_cached_domains()
    if cached_domains:
        st.markdown("**⚡ Chọn nhanh từ kết quả đã quét:**")
        chip_html = "<div class='chip-container'>"
        for d in cached_domains[:12]:
            css_cls = "chip chip-vp" if d["verdict"] == "VI_PHAM" else "chip chip-at"
            chip_html += f"<span class='{css_cls}'>{d['domain']}</span>"
        chip_html += "</div>"
        st.markdown(chip_html, unsafe_allow_html=True)
        st.caption("💡 Click vào domain bên trên để xem báo cáo, hoặc nhập URL mới bên dưới để phân tích.")

    st.markdown("---")

    # URL Input
    with st.container():
        st.markdown("<div class='url-input-wrapper'>", unsafe_allow_html=True)
        col_input, col_btn = st.columns([4, 1])

        with col_input:
            url_val = st.text_input(
                label="URL hoặc Domain",
                placeholder="Ví dụ: animevietsub.meme  hoặc  https://phimmoie.fm",
                value=st.session_state.input_url,
                key="url_text_input",
                label_visibility="collapsed",
            )
            st.session_state.input_url = url_val

        with col_btn:
            scan_clicked = st.button(
                "🚀 Phân tích",
                use_container_width=True,
                type="primary",
            )

        st.markdown("</div>", unsafe_allow_html=True)

    # Options row
    col_opt1, col_opt2, col_opt3 = st.columns(3)
    with col_opt1:
        force_rescan = st.checkbox(
            "🔄 Buộc quét lại (bỏ qua cache)",
            value=st.session_state.force_rescan,
        )
        st.session_state.force_rescan = force_rescan
    with col_opt2:
        st.markdown(
            "<div style='padding-top:6px;font-size:0.83rem;color:#64748b;'>"
            "✅ Nếu đã có cache → load ngay (< 1 giây)"
            "</div>",
            unsafe_allow_html=True
        )
    with col_opt3:
        st.markdown(
            "<div style='padding-top:6px;font-size:0.83rem;color:#64748b;'>"
            "🔄 Nếu chưa có → chạy pipeline thực (~3–5 phút)"
            "</div>",
            unsafe_allow_html=True
        )

    # Handle scan button click
    if scan_clicked and url_val.strip():
        domain = normalize_domain(url_val.strip())
        if not domain:
            st.error("❌ URL/Domain không hợp lệ. Vui lòng kiểm tra lại.")
        else:
            # Check cache first
            cached_result = None if force_rescan else find_cached_result(domain)

            if cached_result:
                # Load from cache instantly
                st.session_state.scan_result = cached_result
                state = PipelineState()
                state.status   = "done"
                state.progress = 100
                state.completed_steps = [s["id"] for s in PIPELINE_STEPS]
                state.result   = cached_result
                state.logs     = [
                    f"[{time.strftime('%H:%M:%S')}] Tìm thấy kết quả trong cache",
                    f"[{time.strftime('%H:%M:%S')}] Domain: {domain}",
                    f"[{time.strftime('%H:%M:%S')}] Báo cáo từ: {cached_result.get('scanned_at', 'N/A')}",
                    f"[{time.strftime('%H:%M:%S')}] ✅ Load hoàn tất — chuyển đến tab Report",
                ]
                st.session_state.pipeline_state = state
                st.session_state.analysis_started = True
                st.success(f"✅ Tìm thấy kết quả cache cho **{domain}**. Chuyển sang tab **📊 Report** để xem!")
                st.balloons()
            else:
                # Start live pipeline
                state = PipelineState()
                st.session_state.pipeline_state = state
                st.session_state.analysis_started = True
                st.session_state.scan_result = None
                thread = start_pipeline_thread(url_val.strip(), state)
                st.session_state.pipeline_thread = thread
                st.info(f"🚀 Đang bắt đầu phân tích **{domain}**... Chuyển sang tab **⚙️ Processing** để theo dõi tiến trình.")

    elif scan_clicked and not url_val.strip():
        st.warning("⚠️ Vui lòng nhập URL hoặc domain trước khi phân tích.")

    # ── Pipeline info diagram ──
    st.markdown("---")
    st.markdown("### 🏗️ Kiến trúc Pipeline Phát Hiện")

    flow_cols = st.columns(6)
    step_colors = ["#6366f1","#3b82f6","#06b6d4","#f59e0b","#8b5cf6","#ec4899"]
    for i, (col, step) in enumerate(zip(flow_cols, PIPELINE_STEPS)):
        with col:
            st.markdown(
                f"<div style='text-align:center;background:rgba(30,41,59,.7);"
                f"border:1px solid {step_colors[i]}44;border-radius:12px;padding:14px 8px;"
                f"border-top:3px solid {step_colors[i]};'>"
                f"<div style='font-size:1.6rem;'>{step['icon']}</div>"
                f"<div style='font-size:0.75rem;font-weight:700;color:{step_colors[i]};margin:6px 0 4px;'>"
                f"{step['label'].split('—')[0].strip()}</div>"
                f"<div style='font-size:0.67rem;color:#64748b;line-height:1.4;'>{step['desc'][:60]}...</div>"
                f"</div>",
                unsafe_allow_html=True
            )

    # Show flow image if available
    flow_img_path = os.path.join(os.path.dirname(__file__), "flow_v4.1.png")
    if os.path.exists(flow_img_path):
        st.markdown("---")
        with st.expander("📐 Xem sơ đồ kiến trúc đầy đủ (v4.1)"):
            st.image(flow_img_path, use_container_width=True,
                     caption="KSCAN v4.1 — Kiến trúc hệ thống phát hiện vi phạm")


# ══════════════════════════════════════════════
# TAB 2 — PROCESSING
# ══════════════════════════════════════════════
with tab2:
    state: PipelineState = st.session_state.get("pipeline_state")

    if not state:
        st.markdown("""
        <div style="text-align:center;padding:60px 20px;color:#475569;">
          <div style="font-size:3rem;margin-bottom:16px;">⚙️</div>
          <div style="font-size:1.1rem;font-weight:600;color:#64748b;">Chưa có phân tích nào đang chạy</div>
          <div style="font-size:0.85rem;margin-top:8px;">Nhập URL ở tab <strong>🔍 Scan Input</strong> và nhấn Phân tích</div>
        </div>
        """, unsafe_allow_html=True)
    else:
        # Header
        st.markdown("### ⚙️ Tiến trình phân tích Pipeline")

        # Status & progress bar
        prog_val = state.progress / 100
        prog_color = "#10b981" if state.status == "done" else "#3b82f6" if state.status == "running" else "#ef4444"

        if state.status == "done":
            st.success(f"✅ Phân tích hoàn tất — {state.progress}%")
        elif state.status == "error":
            st.error(f"❌ Lỗi pipeline: {state.error}")
        elif state.status == "running":
            st.info(f"🔄 Đang phân tích... {state.progress}%")
            st.toast("Pipeline đang chạy — tự động cập nhật mỗi 3 giây", icon="⚙️")

        st.progress(prog_val)

        st.markdown("---")

        # Step cards
        col_steps, col_logs = st.columns([1, 1])

        with col_steps:
            st.markdown("#### 📋 Các bước thực hiện")
            for step in PIPELINE_STEPS:
                sid = step["id"]
                if sid in state.completed_steps:
                    card_cls   = "step-done"
                    badge_cls  = "badge-done"
                    badge_text = "✅ Hoàn thành"
                    status_icon = "✅"
                elif sid == state.current_step_id:
                    card_cls   = "step-running"
                    badge_cls  = "badge-running"
                    badge_text = "⏳ Đang chạy..."
                    status_icon = "⏳"
                else:
                    card_cls   = "step-pending"
                    badge_cls  = "badge-pending"
                    badge_text = "⏸ Chờ"
                    status_icon = "○"

                st.markdown(f"""
                <div class="step-card {card_cls}">
                  <span class="step-icon">{step['icon']}</span>
                  <div style="flex:1;">
                    <div class="step-label">{step['label']}</div>
                    <div class="step-desc">{step['desc']}</div>
                  </div>
                  <span class="step-status-badge {badge_cls}">{badge_text}</span>
                </div>
                """, unsafe_allow_html=True)

        with col_logs:
            st.markdown("#### 📟 Live Log")
            log_lines = state.logs[-40:]  # last 40 lines

            log_html = "<div class='log-terminal'>"
            for line in log_lines:
                cls = "log-line-ok" if any(k in line for k in ["✅","hoàn thành","Đã lưu","load"]) else \
                      "log-line-error" if "[ERROR]" in line else \
                      "log-line-warn"  if "[WARN]" in line else ""
                log_html += f"<div class='{cls}'>{line}</div>"
            log_html += "</div>"

            st.markdown(log_html, unsafe_allow_html=True)

        # Auto refresh while running
        if state.status == "running":
            st.markdown("---")
            placeholder = st.empty()
            placeholder.caption("🔄 Tự động làm mới sau 3 giây...")
            time.sleep(3)
            # Check if done and update result
            if state.status == "done" and state.result:
                st.session_state.scan_result = state.result
            st.rerun()

        # If done, show result summary and prompt to Report tab
        if state.status == "done" and state.result:
            st.session_state.scan_result = state.result
            st.markdown("---")
            res = state.result
            rdata = res.get("report_data", {})
            verdict = rdata.get("verdict", "N/A")
            conf    = rdata.get("confidence", 0)

            if verdict == "VI_PHAM":
                st.error(f"🚨 **KẾT QUẢ: VI PHẠM BẢN QUYỀN** — Confidence: {conf*100:.0f}%")
            elif verdict == "AN_TOAN":
                st.success(f"✅ **KẾT QUẢ: AN TOÀN** — Confidence: {conf*100:.0f}%")
            else:
                st.info(f"ℹ️ **KẾT QUẢ: {verdict}**")

            st.info("📊 Chuyển sang tab **📊 Report** để xem báo cáo chi tiết đầy đủ.")


# ══════════════════════════════════════════════
# TAB 3 — REPORT OUTPUT
# ══════════════════════════════════════════════
with tab3:
    result = st.session_state.get("scan_result")
    # Also check history selection
    if not result and st.session_state.get("selected_history"):
        result = st.session_state.selected_history

    if not result:
        st.markdown("""
        <div style="text-align:center;padding:60px 20px;color:#475569;">
          <div style="font-size:3rem;margin-bottom:16px;">📊</div>
          <div style="font-size:1.1rem;font-weight:600;color:#64748b;">Chưa có báo cáo nào</div>
          <div style="font-size:0.85rem;margin-top:8px;">
            Quét một domain từ tab <strong>🔍 Scan Input</strong>,
            hoặc chọn từ lịch sử ở tab <strong>📁 History</strong>
          </div>
        </div>
        """, unsafe_allow_html=True)
    else:
        report_data = result.get("report_data") or {}
        final_data  = result.get("final_data")  or {}
        found_dir   = result.get("found_dir", "")

        domain      = report_data.get("domain", result.get("domain", "N/A"))
        verdict     = report_data.get("verdict", "N/A")
        confidence  = report_data.get("confidence", 0)
        analyzed_at = report_data.get("analyzed_at", "N/A")
        viol_types  = report_data.get("violation_types", [])
        rec_action  = report_data.get("recommended_action", "N/A")
        key_signals = report_data.get("key_signals", [])
        input_sum   = report_data.get("input_summary", {})
        supplemental = report_data.get("supplemental", {})

        ocr_count   = input_sum.get("ocr_banner_count", 0)
        ocr_flagged = input_sum.get("ocr_flagged_count", 0)
        risk_score  = input_sum.get("risk_score", "N/A")

        # ── Verdict Banner ──
        if verdict == "VI_PHAM":
            st.markdown(f"""
            <div class="verdict-vi-pham">
              <div class="verdict-title">🚨 VI PHẠM BẢN QUYỀN & QUẢNG CÁO TRÁI PHÉP</div>
              <div class="verdict-conf">Hành động khuyến nghị: <strong>{rec_action}</strong> · Confidence: <strong>{confidence*100:.0f}%</strong></div>
            </div>
            """, unsafe_allow_html=True)
        elif verdict == "AN_TOAN":
            st.markdown(f"""
            <div class="verdict-an-toan">
              <div class="verdict-title" style="color:#34d399;">✅ AN TOÀN — Không phát hiện vi phạm</div>
              <div class="verdict-conf">Hành động: <strong>{rec_action}</strong> · Confidence: <strong>{confidence*100:.0f}%</strong></div>
            </div>
            """, unsafe_allow_html=True)
        else:
            st.info(f"ℹ️ **Phán quyết: {verdict}** | Hành động: {rec_action}")

        st.markdown(f"<div style='color:#64748b;font-size:0.8rem;text-align:center;margin:6px 0 16px;'>🕐 Phân tích lúc: {analyzed_at} · 🌐 Domain: <strong style='color:#818cf8;'>{domain}</strong></div>", unsafe_allow_html=True)

        # ── Metrics ──
        st.markdown(f"""
        <div class="metric-grid">
          <div class="metric-card">
            <div class="metric-value">{confidence*100:.0f}%</div>
            <div class="metric-label">Độ Tin Cậy</div>
          </div>
          <div class="metric-card">
            <div class="metric-value" style="color:#f59e0b;">{risk_score}</div>
            <div class="metric-label">Điểm Rủi Ro</div>
          </div>
          <div class="metric-card">
            <div class="metric-value" style="color:#ef4444;">{ocr_flagged}</div>
            <div class="metric-label">Banner Vi Phạm</div>
          </div>
          <div class="metric-card">
            <div class="metric-value">{ocr_count}</div>
            <div class="metric-label">Tổng Banner OCR</div>
          </div>
          <div class="metric-card">
            <div class="metric-value">{len(viol_types)}</div>
            <div class="metric-label">Loại Vi Phạm</div>
          </div>
          <div class="metric-card">
            <div class="metric-value">{len(key_signals)}</div>
            <div class="metric-label">Tín Hiệu Phát Hiện</div>
          </div>
        </div>
        """, unsafe_allow_html=True)

        # ── Summary ──
        summary_vi = report_data.get("summary_vi", "")
        if summary_vi:
            st.info(f"📝 **Tóm tắt:** {summary_vi}")

        st.markdown("---")

        # ── Two column: signals + violations ──
        col_l, col_r = st.columns([1.2, 1])

        with col_l:
            st.markdown("#### ⚠️ Tín Hiệu Phát Hiện")
            if not key_signals:
                st.markdown("<div style='color:#64748b;font-size:0.85rem;'>Không phát hiện tín hiệu bất thường.</div>", unsafe_allow_html=True)
            else:
                for sig in key_signals:
                    weight = sig.get("weight", "MEDIUM")
                    layer  = sig.get("layer", "N/A")
                    text   = sig.get("signal", "")
                    cls    = "sig-high" if weight == "HIGH" else "sig-medium" if weight == "MEDIUM" else "sig-low"
                    emoji  = "🔴" if weight == "HIGH" else "🟡" if weight == "MEDIUM" else "🔵"
                    st.markdown(f"""
                    <div class="signal-card {cls}">
                      <div class="sig-weight">{emoji} {weight} · Tầng {layer}</div>
                      <div class="sig-text">{text}</div>
                    </div>
                    """, unsafe_allow_html=True)

        with col_r:
            st.markdown("#### 🏷️ Phân loại vi phạm")
            if viol_types:
                for vt in viol_types:
                    st.markdown(f"<div style='padding:6px 0;border-bottom:1px solid rgba(30,41,59,.8);color:#e2e8f0;font-size:0.9rem;'>⚡ {vt}</div>", unsafe_allow_html=True)
            else:
                st.markdown("<div style='color:#64748b;font-size:0.85rem;'>Không ghi nhận vi phạm cụ thể.</div>", unsafe_allow_html=True)

            st.markdown("#### 💡 Ghi chú phân tích")
            note = report_data.get("analysis_note", "Không có ghi chú.")
            st.markdown(f"<div style='font-size:0.85rem;color:#94a3b8;font-style:italic;padding:8px 0;'>{note}</div>", unsafe_allow_html=True)

        st.markdown("---")

        # ── Banner Evidence ──
        st.markdown("#### 📸 Bằng Chứng Banner Vi Phạm (OCR)")

        flagged_banners = []
        step3_ev = final_data.get("step3_evidence", {})
        branch1  = step3_ev.get("branch1_ocr", {}) if step3_ev else {}
        ocr_res  = (branch1.get("results") or []) if branch1 else []
        flagged_banners = [b for b in ocr_res if b.get("matched")]

        if not flagged_banners and ocr_flagged > 0:
            step2_ev = final_data.get("step2_evidence", {})
            all_banners_raw = (step2_ev.get("banners") or []) if step2_ev else []
            flagged_banners = all_banners_raw[:ocr_flagged]

        if flagged_banners:
            st.markdown(f"Đã trích xuất **{len(flagged_banners)}** banner vi phạm:")
            banner_cols = st.columns(2)
            for idx, banner in enumerate(flagged_banners):
                col = banner_cols[idx % 2]
                with col:
                    st.markdown("<div class='evidence-card'>", unsafe_allow_html=True)

                    json_path   = banner.get("path") or banner.get("local_path")
                    img_loaded  = False

                    if json_path and found_dir:
                        fname      = os.path.basename(json_path)
                        local_path = os.path.join(found_dir, "banners", fname)
                        if os.path.exists(local_path):
                            try:
                                img = Image.open(local_path)
                                st.image(img, caption=f"Banner #{idx+1}", use_container_width=True)
                                img_loaded = True
                            except Exception:
                                pass

                    if not img_loaded and banner.get("src_url"):
                        try:
                            st.image(banner["src_url"], caption=f"Banner #{idx+1} (remote)", use_container_width=True)
                            img_loaded = True
                        except Exception:
                            pass

                    if not img_loaded:
                        st.markdown(
                            f"<div style='background:rgba(30,41,59,.7);border-radius:8px;padding:20px;"
                            f"text-align:center;color:#ef4444;font-size:0.8rem;margin-bottom:8px;'>"
                            f"🖼️ Không tải được ảnh banner<br><span style='color:#64748b'>{os.path.basename(json_path or '')}</span></div>",
                            unsafe_allow_html=True
                        )

                    field   = banner.get("field", "Vi phạm")
                    keyword = banner.get("keyword", "N/A")
                    tier    = banner.get("tier_hit", "?")
                    href    = banner.get("link_href", "")
                    ocr_txt = banner.get("ocr_raw") or banner.get("ocr_norm", "")

                    st.markdown(
                        f"<div style='margin-top:8px;'>"
                        f"<span style='color:#f87171;font-size:0.82rem;font-weight:600;'>⚡ {field}</span>"
                        f"&nbsp;·&nbsp;"
                        f"<span style='color:#fde68a;font-size:0.78rem;'>🔑 \"{keyword}\" (Tier {tier})</span>"
                        f"</div>",
                        unsafe_allow_html=True
                    )
                    if href:
                        st.markdown(f"<div style='font-size:0.75rem;margin-top:4px;'>🔗 <a href='{href}' target='_blank' class='clink'>{href[:60]}{'...' if len(href)>60 else ''}</a></div>", unsafe_allow_html=True)
                    if ocr_txt:
                        with st.expander("📝 OCR text"):
                            st.code(ocr_txt[:500])

                    st.markdown("</div>", unsafe_allow_html=True)
        else:
            st.info("Không có banner vi phạm được trích xuất.")

        st.markdown("---")

        # ── Technical tabs ──
        st.markdown("#### ⚙️ Thông tin kỹ thuật chi tiết")
        ttech, tredirect, tall, traw = st.tabs([
            "🖥️ Hạ tầng & DNS",
            "🔄 Redirect Chain",
            "🖼️ Tất cả Banner",
            "📄 Raw JSON",
        ])

        with ttech:
            c1, c2 = st.columns(2)
            with c1:
                st.markdown("##### Bản ghi DNS")
                dns = final_data.get("dns_records", {})
                if dns:
                    for rtype, records in dns.items():
                        if records:
                            st.write(f"**{rtype}:**")
                            st.code("\n".join(records))
                else:
                    ips = supplemental.get("resolved_ips", [])
                    if ips:
                        st.write("**A records:**")
                        st.code("\n".join(ips))

                st.markdown("##### Thông tin ASN / Hosting")
                asn = supplemental.get("asn", {})
                cdn = supplemental.get("cdn_providers", [])
                st.markdown(f"- **ASN:** {asn.get('description', 'N/A') if asn else 'N/A'}")
                st.markdown(f"- **CDN:** {', '.join(cdn) if cdn else 'Không'}")

            with c2:
                st.markdown("##### HTTP Headers")
                headers = final_data.get("http_headers", {})
                if headers:
                    st.json(headers)
                else:
                    st.caption("Không có dữ liệu.")

                st.markdown("##### Tín hiệu hợp lệ")
                leg_sigs = final_data.get("legitimate_signals", {}) or input_sum.get("legitimate_signals", {})
                if leg_sigs:
                    ls_df = pd.DataFrame([
                        {"Tín hiệu": k, "Trạng thái": "✅ Có" if v else "❌ Không"}
                        for k, v in leg_sigs.items() if k != "total_signals"
                    ])
                    st.dataframe(ls_df, hide_index=True, use_container_width=True)

        with tredirect:
            st.markdown("##### Lịch sử Redirect")
            redirects = supplemental.get("redirect_chain", []) or final_data.get("redirect_history", [])
            if redirects:
                for i, u in enumerate(redirects):
                    arrow = "→" if i < len(redirects)-1 else "🎯"
                    st.markdown(f"**{i+1}.** `{u}` {arrow}")
                redirect_info = final_data.get("redirect_info", {})
                if redirect_info:
                    hop = redirect_info.get("domain_hopping", False)
                    depth = redirect_info.get("redirect_depth", len(redirects))
                    st.markdown(f"\n**Domain Hopping:** {'⚠️ Phát hiện nhảy domain' if hop else '✅ Không'}")
                    st.markdown(f"**Độ sâu redirect:** {depth}")
            else:
                st.info("Không phát hiện chuỗi chuyển hướng.")

        with tall:
            st.markdown("##### Tất cả Banner đã thu thập")
            step2_ev = final_data.get("step2_evidence", {})
            all_bans = (step2_ev.get("banners") or []) if step2_ev else []
            st.write(f"Tổng số banner thu thập: **{len(all_bans)}**")
            if all_bans:
                rows = []
                for idx, b in enumerate(all_bans):
                    matched_s = "⚠️ Vi phạm" if any(
                        os.path.basename(ob.get("path","")) == os.path.basename(b.get("local_path","") or b.get("path",""))
                        for ob in ocr_res if ob.get("matched")
                    ) else "✅ Bình thường"
                    rows.append({
                        "STT":    idx+1,
                        "Alt":    b.get("alt", "")[:40],
                        "Size":   f"{b.get('width','?')}×{b.get('height','?')}",
                        "Trạng thái": matched_s,
                        "Href":   (b.get("link_href") or "")[:50],
                    })
                st.dataframe(pd.DataFrame(rows), hide_index=True, use_container_width=True)

        with traw:
            c1, c2 = st.columns(2)
            with c1:
                st.write("**Report JSON**")
                st.json(report_data)
            with c2:
                st.write("**Final JSON (truncated)**")
                # Show without massive banners list
                if final_data:
                    slim = {k: v for k, v in final_data.items() if k not in ("step2_evidence",)}
                    st.json(slim)


# ══════════════════════════════════════════════
# TAB 4 — HISTORY / LOG BROWSER
# ══════════════════════════════════════════════
with tab4:
    st.markdown("### 📁 Lịch sử các domain đã quét")

    all_domains = list_all_cached_domains()

    if not all_domains:
        st.markdown("""
        <div style="text-align:center;padding:60px 20px;color:#475569;">
          <div style="font-size:3rem;margin-bottom:16px;">📂</div>
          <div style="font-size:1.1rem;font-weight:600;color:#64748b;">Chưa có kết quả nào</div>
          <div style="font-size:0.85rem;margin-top:8px;">Bắt đầu quét domain đầu tiên từ tab <strong>🔍 Scan Input</strong></div>
        </div>
        """, unsafe_allow_html=True)
    else:
        # Summary stats
        vp   = [d for d in all_domains if d["verdict"] == "VI_PHAM"]
        at_d = [d for d in all_domains if d["verdict"] == "AN_TOAN"]

        m1, m2, m3, m4 = st.columns(4)
        with m1:
            st.metric("Tổng domains", len(all_domains))
        with m2:
            st.metric("🔴 Vi phạm", len(vp))
        with m3:
            st.metric("🟢 An toàn", len(at_d))
        with m4:
            avg_conf = sum(d["confidence"] for d in all_domains) / len(all_domains)
            st.metric("Avg Confidence", f"{avg_conf*100:.0f}%")

        st.markdown("---")

        # Filter
        col_f1, col_f2, col_f3 = st.columns([2, 1, 1])
        with col_f1:
            search_q = st.text_input("🔍 Tìm kiếm domain:", placeholder="Nhập tên domain...", key="hist_search")
        with col_f2:
            filter_verdict = st.selectbox("Lọc phán quyết:", ["Tất cả", "VI_PHAM", "AN_TOAN"])
        with col_f3:
            sort_by = st.selectbox("Sắp xếp:", ["Tên domain", "Thời gian", "Confidence"])

        # Apply filters
        filtered = all_domains
        if search_q:
            filtered = [d for d in filtered if search_q.lower() in d["domain"].lower()]
        if filter_verdict != "Tất cả":
            filtered = [d for d in filtered if d["verdict"] == filter_verdict]

        # Sort
        if sort_by == "Thời gian":
            filtered = sorted(filtered, key=lambda x: x["analyzed_at"], reverse=True)
        elif sort_by == "Confidence":
            filtered = sorted(filtered, key=lambda x: x["confidence"], reverse=True)
        else:
            filtered = sorted(filtered, key=lambda x: x["domain"])

        st.markdown(f"<div style='color:#64748b;font-size:0.8rem;margin-bottom:12px;'>Hiển thị {len(filtered)}/{len(all_domains)} kết quả</div>", unsafe_allow_html=True)

        # Domain list
        for d in filtered:
            verdict_badge = (
                "<span style='background:rgba(239,68,68,.2);color:#f87171;border-radius:999px;"
                "padding:2px 10px;font-size:.72rem;font-weight:700;'>🔴 VI PHẠM</span>"
                if d["verdict"] == "VI_PHAM"
                else
                "<span style='background:rgba(16,185,129,.2);color:#34d399;border-radius:999px;"
                "padding:2px 10px;font-size:.72rem;font-weight:700;'>🟢 AN TOÀN</span>"
            )
            violations_str = ", ".join(d["violations"][:2]) if d["violations"] else "—"
            if len(d["violations"]) > 2:
                violations_str += f" +{len(d['violations'])-2}"

            col_dom, col_info = st.columns([2, 3])
            with col_dom:
                st.markdown(
                    f"<div style='padding:10px 0;'>"
                    f"<div style='font-weight:700;color:#e2e8f0;font-size:.95rem;'>{d['domain']}</div>"
                    f"<div style='font-size:.75rem;color:#64748b;margin-top:2px;'>🕐 {d['analyzed_at']}</div>"
                    f"</div>",
                    unsafe_allow_html=True
                )
            with col_info:
                c1, c2, c3, c4 = st.columns(4)
                with c1:
                    st.markdown(verdict_badge, unsafe_allow_html=True)
                with c2:
                    st.markdown(f"<div style='font-size:.78rem;color:#94a3b8;padding-top:4px;'>📊 {d['confidence']*100:.0f}%</div>", unsafe_allow_html=True)
                with c3:
                    st.markdown(f"<div style='font-size:.78rem;color:#fde68a;padding-top:4px;'>⚠️ {d['ocr_flagged']}/{d['ocr_banners']} banner</div>", unsafe_allow_html=True)
                with c4:
                    if st.button("👁 Xem", key=f"view_{d['domain']}", use_container_width=True):
                        # Load and display in Report tab
                        from pipeline_runner import find_cached_result
                        res = find_cached_result(d["domain"])
                        if res:
                            st.session_state.scan_result    = res
                            st.session_state.selected_history = res
                            st.success(f"✅ Đã tải báo cáo cho {d['domain']}. Chuyển sang tab **📊 Report**.")
                            st.rerun()

            st.markdown("<hr style='border-color:rgba(30,41,59,.8);margin:2px 0;'>", unsafe_allow_html=True)

        # Dataframe summary view
        st.markdown("---")
        with st.expander("📋 Xem dạng bảng tổng hợp"):
            df = pd.DataFrame([{
                "Domain": d["domain"],
                "Phán quyết": "🔴 VI PHẠM" if d["verdict"] == "VI_PHAM" else "🟢 AN TOÀN",
                "Confidence": f"{d['confidence']*100:.0f}%",
                "Điểm rủi ro": d["risk_score"],
                "Banner vi phạm": f"{d['ocr_flagged']}/{d['ocr_banners']}",
                "Loại vi phạm": ", ".join(d["violations"]),
                "Hành động": d["action"],
                "Thời gian": d["analyzed_at"],
            } for d in filtered])
            st.dataframe(df, hide_index=True, use_container_width=True)
