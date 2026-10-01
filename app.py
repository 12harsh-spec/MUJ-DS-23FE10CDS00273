from __future__ import annotations

import html
import os
from datetime import date
from pathlib import Path

import streamlit as st
import yaml
from dotenv import load_dotenv

from src.exporters import to_ics, to_markdown
from src.demo_extractor import extract_demo
from src.extractor import extract
from src.llm_client import create_llm_client

ROOT = Path(__file__).resolve().parent

st.set_page_config(
    page_title="Notice Action Extractor",
    page_icon=":material/auto_awesome:",
    layout="wide",
    initial_sidebar_state="collapsed",
)

load_dotenv(ROOT / ".env")
st.session_state.setdefault("input_mode", "Paste text")
CONFIG = yaml.safe_load((ROOT / "config.yaml").read_text(encoding="utf-8"))
LLM_CONFIG = CONFIG["llm"]
PROVIDER = LLM_CONFIG.get("provider", "gemini").strip().lower()
GEMINI_API_KEY = os.environ.get("GEMINI_API_KEY", "").strip()
GEMINI_FORCE_DEMO = st.session_state.get("gemini_force_demo", False)
DEMO_MODE = PROVIDER != "gemini" or not GEMINI_API_KEY or GEMINI_FORCE_DEMO

if DEMO_MODE:
  MODE_LABEL = "Demo Mode • Local extraction"
  if GEMINI_FORCE_DEMO:
    MODE_EXPLANATION = "Gemini could not analyze the last notice. This result uses deterministic local extraction, not an LLM."
  elif PROVIDER == "gemini" and not GEMINI_API_KEY:
    MODE_EXPLANATION = "GEMINI_API_KEY is not configured. Demo Mode uses deterministic local extraction, not an LLM."
  else:
    MODE_EXPLANATION = f"Unsupported provider '{PROVIDER}'. Demo Mode uses deterministic local extraction, not an LLM."
else:
  MODE_LABEL = "AI Mode • Gemini"
  MODE_EXPLANATION = f"Using {LLM_CONFIG['model']} through the Gemini API. Your key stays on the server."


def load_sample(filename: str) -> None:
    st.session_state["input_mode"] = "Paste text"
    st.session_state["notice_text"] = (ROOT / "samples" / filename).read_text(encoding="utf-8")
    st.session_state.pop("notice_result", None)
    st.session_state.pop("gemini_force_demo", None)
    st.session_state.pop("gemini_failure", None)


def clear_notice() -> None:
    st.session_state["notice_text"] = ""
    st.session_state.pop("notice_result", None)
    st.session_state.pop("gemini_force_demo", None)
    st.session_state.pop("gemini_failure", None)


st.html(
  """
    <style>
    @keyframes ambient-drift {
      0%, 100% { transform: translate3d(-2%, -1%, 0) scale(1); }
      50% { transform: translate3d(2%, 1%, 0) scale(1.06); }
    }
    @keyframes signal-pulse {
      0%, 100% { box-shadow: 0 0 0 0 rgba(111, 206, 176, .34); }
      50% { box-shadow: 0 0 0 7px rgba(111, 206, 176, 0); }
    }
    @keyframes orbit-spin { to { transform: rotate(360deg); } }
    @keyframes appear { from { opacity: 0; transform: translateY(9px); } to { opacity: 1; transform: translateY(0); } }

    .stApp {
      background: #0a1011;
      color: #e8efed;
    }
    .stApp::before, .stApp::after {
      content: "";
      position: fixed;
      inset: -12%;
      z-index: 0;
      pointer-events: none;
    }
    .stApp::before {
      background:
        radial-gradient(ellipse at 12% 17%, rgba(29, 103, 87, .26), transparent 35%),
        radial-gradient(ellipse at 82% 18%, rgba(97, 98, 62, .16), transparent 30%),
        radial-gradient(ellipse at 75% 82%, rgba(34, 88, 106, .19), transparent 35%),
        radial-gradient(ellipse at 15% 85%, rgba(106, 74, 48, .11), transparent 30%);
      filter: blur(34px);
      animation: ambient-drift 34s ease-in-out infinite;
    }
    .stApp::after {
      inset: 0;
      opacity: .13;
      background-image:
        radial-gradient(1px 1px at 23px 37px, #d4e9df 98%, transparent),
        radial-gradient(1px 1px at 119px 163px, #d4e9df 98%, transparent),
        radial-gradient(1px 1px at 211px 71px, #d4e9df 98%, transparent),
        radial-gradient(1px 1px at 74px 244px, #d4e9df 98%, transparent);
      background-size: 280px 280px;
      mask-image: linear-gradient(to bottom, black, transparent 88%);
    }
    [data-testid="stHeader"] { background: transparent; }
    [data-testid="stMain"] { position: relative; z-index: 1; }
    .block-container { max-width: 1120px; padding-top: 1.15rem; padding-bottom: 4rem; }

    .topbar {
      display: flex;
      align-items: center;
      justify-content: space-between;
      padding: .35rem 0 1.25rem;
      border-bottom: 1px solid rgba(202, 224, 216, .11);
      margin-bottom: 2.8rem;
    }
    .brand { display: flex; align-items: center; gap: .72rem; color: #e8efed; font-size: .94rem; font-weight: 650; }
    .brand-mark {
      display: grid;
      place-items: center;
      width: 34px;
      height: 34px;
      border: 1px solid rgba(127, 204, 177, .36);
      border-radius: 10px;
      color: #91d4ba;
      background: linear-gradient(145deg, rgba(62, 130, 106, .27), rgba(21, 39, 36, .5));
    }
    .system-status { display: flex; align-items: center; gap: .55rem; color: #a8d9bd; font-size: .78rem; letter-spacing: .01em; }
    .system-status.demo { color: #dbc89f; }
    .status-dot { width: 7px; height: 7px; border-radius: 50%; background: #83d1ad; animation: signal-pulse 3s ease-out infinite; }
    .hero {
      position: relative;
      display: grid;
      grid-template-columns: minmax(0, 1fr) 128px;
      gap: 2rem;
      align-items: center;
      margin: 0 0 2.2rem;
      animation: appear .55s ease-out both;
    }
    .eyebrow { color: #9bc8b5; text-transform: uppercase; font-size: .7rem; font-weight: 650; letter-spacing: .13em; }
    .hero h1 { margin: .65rem 0 .7rem; color: #f0f4f1; font-size: clamp(2rem, 4vw, 3.25rem); line-height: 1.08; font-weight: 620; }
    .hero-copy { max-width: 660px; color: #aebbb7; font-size: 1.03rem; line-height: 1.7; }
    .hero-orbit { position: relative; display: grid; place-items: center; width: 112px; height: 112px; justify-self: center; }
    .orbit-ring { position: absolute; inset: 7px; border: 1px solid rgba(135, 204, 177, .23); border-radius: 50%; }
    .orbit-ring::after { content: ""; position: absolute; top: 13px; left: 12px; width: 6px; height: 6px; border-radius: 50%; background: #a2dfc4; box-shadow: 0 0 16px rgba(129, 226, 187, .8); }
    .orbit-ring.outer { inset: -3px; border-style: dashed; border-color: rgba(165, 181, 131, .22); animation: orbit-spin 44s linear infinite; }
    .orbit-core { display: grid; place-items: center; width: 54px; height: 54px; border: 1px solid rgba(137, 204, 177, .28); border-radius: 17px; color: #a3dbc1; background: linear-gradient(145deg, rgba(49, 101, 85, .45), rgba(17, 37, 34, .8)); box-shadow: 0 0 36px rgba(74, 157, 126, .13); }
    .section-heading { margin: 0 0 .3rem; color: #e5ece8; font-size: 1.16rem; font-weight: 620; }
    .section-note { margin: 0 0 1.1rem; color: #9caaa5; font-size: .87rem; }
    .mode-note { margin: -1.3rem 0 1.8rem; color: #aab7b0; font-size: .78rem; }
    .st-key-input-panel {
      padding: clamp(1rem, 3vw, 1.65rem);
      border: 1px solid rgba(185, 216, 203, .16);
      border-radius: 15px;
      background: linear-gradient(145deg, rgba(21, 33, 32, .81), rgba(15, 24, 25, .78));
      box-shadow: 0 20px 60px rgba(0, 0, 0, .17), inset 0 1px rgba(255, 255, 255, .025);
      backdrop-filter: blur(16px);
    }
    .st-key-input-panel [data-testid="stFileUploaderDropzone"] {
      border: 1px dashed rgba(146, 197, 174, .35);
      border-radius: 11px;
      background: rgba(39, 67, 58, .22);
      transition: background .2s ease, border-color .2s ease;
    }
    .st-key-input-panel [data-testid="stFileUploaderDropzone"]:hover {
      border-color: rgba(146, 221, 187, .7);
      background: rgba(49, 86, 70, .28);
    }
    [class*="st-key-action-card-"] {
      padding: 1.15rem 1.25rem;
      border: 1px solid rgba(186, 211, 201, .14);
      border-radius: 13px;
      background: linear-gradient(140deg, rgba(23, 36, 34, .85), rgba(15, 24, 25, .78));
      box-shadow: 0 10px 30px rgba(0, 0, 0, .13);
      animation: appear .38s ease-out both;
      transition: transform .2s ease, border-color .2s ease, background .2s ease;
    }
    [class*="st-key-action-card-"]:hover { transform: translateY(-2px); border-color: rgba(151, 205, 179, .29); }
    .stButton button, .stFormSubmitButton button, .stDownloadButton button {
      border-radius: 8px;
      transition: transform .18s ease, filter .18s ease, border-color .18s ease;
    }
    .stButton button:hover, .stFormSubmitButton button:hover, .stDownloadButton button:hover { transform: translateY(-1px); filter: brightness(1.09); }
    :focus-visible { outline: 2px solid #9edfc0 !important; outline-offset: 3px; }
    .result-title { color: #eef3f0; font-size: 1.55rem; font-weight: 630; margin: 0; }
    .result-summary { color: #aebbb6; font-size: .94rem; line-height: 1.65; }
    .result-meta { color: #99aaa3; font-size: .8rem; }
    .empty-state { padding: 1.2rem 1.3rem; border-left: 2px solid rgba(130, 194, 165, .56); color: #b3c1ba; background: rgba(23, 39, 35, .43); border-radius: 0 9px 9px 0; }
    [data-testid="stMetric"] { padding: .9rem 1rem; border: 1px solid rgba(184, 211, 199, .12); border-radius: 11px; background: rgba(21, 34, 32, .58); }
    [data-testid="stMetricLabel"] { color: #9caaa5; }
    [data-testid="stMetricValue"] { color: #e8efed; }
    @media (max-width: 700px) {
      .block-container { padding-top: .75rem; }
      .topbar { margin-bottom: 2rem; }
      .hero { grid-template-columns: 1fr; gap: .8rem; }
      .hero-orbit { width: 72px; height: 72px; justify-self: start; order: -1; margin-left: 4px; }
      .orbit-core { width: 39px; height: 39px; border-radius: 13px; }
      .hero h1 { font-size: 2.15rem; }
      .system-status { font-size: .71rem; }
      [class*="st-key-action-card-"] { padding: .95rem; }
    }
    @media (prefers-reduced-motion: reduce) {
      *, *::before, *::after { scroll-behavior: auto !important; animation-duration: .01ms !important; animation-iteration-count: 1 !important; transition-duration: .01ms !important; }
    }
    .stApp { background: #10161d; color: #e9edf0; }
    .stApp::before {
      background:
        radial-gradient(ellipse at 12% 17%, rgba(28, 101, 136, .26), transparent 35%),
        radial-gradient(ellipse at 82% 18%, rgba(170, 106, 49, .17), transparent 30%),
        radial-gradient(ellipse at 75% 82%, rgba(62, 83, 133, .2), transparent 35%),
        radial-gradient(ellipse at 15% 85%, rgba(126, 76, 57, .13), transparent 30%);
    }
    .stApp::after {
      background-image:
        radial-gradient(1px 1px at 23px 37px, #d8e5f2 98%, transparent),
        radial-gradient(1px 1px at 119px 163px, #d8e5f2 98%, transparent),
        radial-gradient(1px 1px at 211px 71px, #d8e5f2 98%, transparent),
        radial-gradient(1px 1px at 74px 244px, #d8e5f2 98%, transparent);
    }
    section[data-testid="stSidebar"] { background: rgba(13, 19, 26, .94); border-right: 1px solid rgba(166, 190, 210, .13); }
    section[data-testid="stSidebar"] > div { padding-top: 1.2rem; }
    .block-container { max-width: 1200px; }
    .topbar { border-color: rgba(202, 218, 230, .12); margin-bottom: 2.2rem; }
    .brand { color: #e9edf0; }
    .brand-mark { position: relative; display: block; flex: 0 0 44px; width: 44px; height: 44px; overflow: visible; border: 0; border-radius: 50%; background: transparent; box-shadow: none; }
    .brand-orbit { position: absolute; inset: 0; border: 1px solid rgba(84, 184, 204, .45); border-radius: 50%; }
    .brand-orbit.outer { inset: -7px; border-color: rgba(197, 137, 76, .48); border-style: dashed; }
    .brand-core { position: absolute; inset: 8px; display: grid; place-items: center; border: 1px solid rgba(74, 154, 180, .72); border-radius: 12px; color: #8de0eb; background: linear-gradient(145deg, #1b3541, #172833); box-shadow: 0 0 20px rgba(52, 156, 182, .12); }
    .brand-spark { font-size: 15px; line-height: 1; }
    .brand-dot { position: absolute; z-index: 1; width: 5px; height: 5px; border-radius: 50%; background: #f1b86f; box-shadow: 0 0 9px rgba(241, 184, 111, .45); }
    .brand-dot.first { top: 2px; left: 3px; }
    .brand-dot.second { right: -4px; bottom: 4px; }
    .workspace-label { display: flex; align-items: center; gap: .55rem; color: #8294a4; font-size: .68rem; font-weight: 650; letter-spacing: .12em; }
    .workspace-label::before { content: ""; width: 6px; height: 6px; border-radius: 50%; background: #efb46d; box-shadow: 0 0 10px rgba(239, 180, 109, .45); }
    .system-status { color: #8edce8; }
    .system-status.demo { color: #f2bf79; }
    .status-dot { background: #63d4e2; }
    .eyebrow { color: #75ccdc; }
    .hero h1 { color: #f0f3f5; }
    .hero-copy { max-width: 700px; color: #b2bdc7; }
    .orbit-ring { border-color: rgba(97, 201, 223, .25); }
    .orbit-ring::after { background: #f1b86f; box-shadow: 0 0 16px rgba(241, 184, 111, .7); }
    .orbit-ring.outer { border-color: rgba(242, 177, 103, .23); }
    .orbit-core { border-color: rgba(103, 200, 219, .3); border-radius: 14px; color: #9be0ea; background: linear-gradient(145deg, rgba(42, 108, 135, .44), rgba(20, 34, 48, .86)); box-shadow: 0 0 36px rgba(68, 169, 192, .14); }
    .section-heading { color: #e5ebef; }
    .section-note, .mode-note { color: #a5b1bc; }
    .st-key-input-panel { border-color: rgba(170, 194, 211, .17); border-radius: 11px; background: linear-gradient(145deg, rgba(27, 39, 50, .86), rgba(17, 26, 36, .86)); }
    .st-key-input-panel [data-testid="stFileUploaderDropzone"] { border-color: rgba(95, 193, 214, .36); border-radius: 8px; background: rgba(34, 74, 91, .24); }
    .st-key-input-panel [data-testid="stFileUploaderDropzone"]:hover { border-color: rgba(108, 216, 232, .78); background: rgba(43, 97, 117, .32); }
    [class*="st-key-sample-card-"] { padding: 1rem 1.05rem; border: 1px solid rgba(170, 194, 211, .13); border-radius: 9px; background: rgba(26, 38, 49, .74); transition: transform .2s ease, border-color .2s ease, background .2s ease; }
    [class*="st-key-sample-card-"]:hover { transform: translateY(-2px); border-color: rgba(101, 204, 224, .34); background: rgba(32, 49, 62, .88); }
    .sample-title { color: #e7edf1; font-size: .9rem; font-weight: 620; }
    .sample-description { color: #9eacb7; font-size: .78rem; line-height: 1.5; }
    .rail-label { margin: 1.5rem 0 .65rem; color: #6f8495; font-size: .65rem; font-weight: 700; letter-spacing: .15em; text-transform: uppercase; }
    .rail-row { display: flex; align-items: center; justify-content: space-between; gap: .5rem; padding: .45rem 0; color: #c7d0d7; font-size: .78rem; border-bottom: 1px solid rgba(173, 194, 209, .08); }
    .rail-dot { width: 6px; height: 6px; border-radius: 50%; background: #61cfe0; box-shadow: 0 0 10px rgba(97, 207, 224, .35); }
    .rail-value { color: #8498a8; font-size: .7rem; text-align: right; }
    .pipeline { display: grid; gap: .48rem; margin-top: .4rem; }
    .pipeline-step { display: flex; align-items: center; gap: .55rem; color: #a8b4bd; font-size: .75rem; }
    .pipeline-number { display: grid; place-items: center; width: 20px; height: 20px; border: 1px solid rgba(104, 192, 212, .25); border-radius: 6px; color: #7acddc; font-size: .65rem; }
    :focus-visible { outline-color: #f0b56d !important; }
    .result-title { color: #eef2f5; }
    .result-summary { color: #aeb9c2; }
    .result-meta { color: #94a4b1; }
    .empty-state { border-left-color: rgba(98, 199, 218, .62); color: #b7c2ca; background: rgba(29, 48, 61, .55); }
    [data-testid="stMetric"] { border-color: rgba(172, 195, 210, .13); border-radius: 9px; background: rgba(25, 39, 51, .72); }
    [data-testid="stMetricLabel"] { color: #9eacb7; }
    [data-testid="stMetricValue"] { color: #e9edf0; }
    @media (max-width: 700px) { .orbit-core { border-radius: 12px; } }
    </style>
    """
)

st.html(
    f"""
    <div class="topbar" role="banner">
      <div class="workspace-label">STUDENT SERVICES / NOTICE ANALYSIS</div>
      <div class="system-status {'demo' if DEMO_MODE else ''}"><span class="status-dot" aria-hidden="true"></span>{html.escape(MODE_LABEL)}</div>
    </div>
    <section class="hero" aria-labelledby="page-title">
      <div>
        <div class="eyebrow">AI-powered campus intelligence</div>
        <h1 id="page-title">Make every notice<br>actionable.</h1>
        <p class="hero-copy">Extract student actions, deadlines, event times, and requirements from college notices in seconds.</p>
      </div>
      <div class="hero-orbit" aria-hidden="true"><span class="orbit-ring"></span><span class="orbit-ring outer"></span><span class="orbit-core">✳</span></div>
    </section>
    """
)

with st.sidebar:
    st.markdown(
      '<div class="brand"><span class="brand-mark" role="img" aria-label="Notice Action Extractor logo">'
      '<span class="brand-orbit outer"></span><span class="brand-orbit"></span>'
      '<span class="brand-dot first"></span><span class="brand-dot second"></span>'
      '<span class="brand-core"><span class="brand-spark" aria-hidden="true">✳</span></span></span>'
      '<span>Notice Action<br>Extractor</span></div>',
      unsafe_allow_html=True,
    )
    st.markdown(f'<p class="mode-note">{html.escape(MODE_LABEL)}</p>', unsafe_allow_html=True)
    st.markdown('<p class="rail-label">Analysis modules</p>', unsafe_allow_html=True)
    for module in ("Notice understanding", "Action extraction", "Deadline & time", "Priority grading"):
      st.markdown(
        f'<div class="rail-row"><span><i class="rail-dot"></i> {module}</span>'
        '<span class="rail-value">READY</span></div>',
        unsafe_allow_html=True,
      )
    st.markdown('<p class="rail-label">System stack</p>', unsafe_allow_html=True)
    stack = (
      ("Extraction", "Local rules" if DEMO_MODE else "Google Gemini API"),
      ("Validation", "Pydantic · JSON"),
      ("Instructions", "YAML prompt"),
      ("Deliverables", "Checklist · Calendar"),
    )
    for label, value in stack:
      st.markdown(
        f'<div class="rail-row"><span>{label}</span><span class="rail-value">{value}</span></div>',
        unsafe_allow_html=True,
      )
    st.markdown('<p class="rail-label">Processing pipeline</p>', unsafe_allow_html=True)
    st.markdown(
      '<div class="pipeline">'
      '<div class="pipeline-step"><span class="pipeline-number">01</span>Notice input</div>'
      '<div class="pipeline-step"><span class="pipeline-number">02</span>NLP analysis</div>'
      '<div class="pipeline-step"><span class="pipeline-number">03</span>Action items</div>'
      '<div class="pipeline-step"><span class="pipeline-number">04</span>Deadlines & exports</div>'
      '</div>',
      unsafe_allow_html=True,
    )

st.markdown(
  f'<p class="mode-note" role="status"><strong>{html.escape(MODE_LABEL)}</strong> · {html.escape(MODE_EXPLANATION)}</p>',
  unsafe_allow_html=True,
)
if st.session_state.get("gemini_failure"):
    st.warning(st.session_state["gemini_failure"], icon=":material/cloud_off:")

st.markdown('<h2 class="section-heading">Analyze a college notice</h2>', unsafe_allow_html=True)
st.markdown('<p class="section-note">Load a real sample or add a notice of your own to the analysis console.</p>', unsafe_allow_html=True)

with st.container(key="input-panel"):
  st.markdown('<p class="rail-label">Try a sample notice</p>', unsafe_allow_html=True)
  sample_columns = st.columns(2)
  samples = (
    ("exam_form.txt", "Exam form", "Registration, payment, and attendance requirements."),
    ("scholarship.txt", "Merit scholarship", "Eligibility, documents, and online submission."),
  )
  for index, (column, (filename, title, description)) in enumerate(zip(sample_columns, samples)):
    with column.container(key=f"sample-card-{index}"):
      st.markdown(f'<div class="sample-title">{title}</div>', unsafe_allow_html=True)
      st.markdown(f'<p class="sample-description">{description}</p>', unsafe_allow_html=True)
      st.button(
        "Load sample",
        key=f"load-sample-{index}",
        on_click=load_sample,
        args=(filename,),
        icon=":material/arrow_forward:",
        width="stretch",
      )

  input_mode = st.segmented_control(
    "Analysis console input",
    options=["Paste text", "Upload .txt"],
    key="input_mode",
  )
  with st.form("notice_form", border=False):
    notice_text = ""
    uploaded_file = None
    if input_mode == "Upload .txt":
      uploaded_file = st.file_uploader(
        "Drop your notice here or browse files",
        type=["txt"],
        max_upload_size=5,
        help="Plain-text notices only. For a PDF, paste its text into the other input mode.",
        key="notice_upload",
      )
    else:
      notice_text = st.text_area(
        "Notice text",
        placeholder="Paste the full notice here…\n\nInclude dates, fees, eligibility, documents, and contact details if they appear.",
        height=180,
        key="notice_text",
      )
    reference_date = st.date_input(
      "Resolve relative dates from",
      value=date.today(),
      help="Used to interpret phrases like ‘next Friday’ or ‘within seven days’.",
      key="reference_date",
    )
    submitted = st.form_submit_button(
      "Analyze notice",
      type="primary",
      icon=":material/auto_awesome:",
      width="stretch",
      key="extract_notice",
    )
  st.button("Clear notice", key="clear_notice", on_click=clear_notice, icon=":material/delete_sweep:")

if submitted:
  try:
    if uploaded_file is not None:
      notice_text = uploaded_file.getvalue().decode("utf-8-sig")
    if not notice_text.strip():
      raise ValueError("Add notice text or choose a .txt file before extracting.")
    with st.status("Reading your notice…", expanded=True) as status:
      if DEMO_MODE:
        status.write("Using deterministic local extraction rules. This is Demo Mode, not an LLM.")
        result = extract_demo(notice_text, reference_date)
      else:
        status.write("Sending the notice to Gemini for structured NLP analysis.")
        prompts_path = ROOT / CONFIG["prompts_file"]
        prompts = yaml.safe_load(prompts_path.read_text(encoding="utf-8"))
        client = create_llm_client(CONFIG)
        try:
          result = extract(
            notice_text,
            client,
            prompts,
            reference_date,
            CONFIG["max_notice_chars"],
            CONFIG["max_repairs"],
          )
        except RuntimeError:
          st.session_state["gemini_force_demo"] = True
          st.session_state["gemini_failure"] = (
            "Gemini could not complete the request. The results below use Demo Mode. "
            "Check your key, connection, or quota before retrying."
          )
          result = extract_demo(notice_text, reference_date)
          status.update(label="Gemini unavailable · Demo Mode used", state="complete", expanded=False)
          client.close()
          st.session_state["notice_result"] = result
          st.rerun()
        else:
          client.close()
      st.session_state["notice_result"] = result
      status.update(label="Notice analyzed", state="complete", expanded=False)
  except UnicodeDecodeError:
    st.error("That file could not be read as plain text. Save or export the notice as a UTF-8 .txt file and try again.")
  except (ValueError, RuntimeError) as error:
    st.error(str(error))
  except Exception:
    st.error("We couldn’t process this notice. Check your connection, API key, and Gemini quota, then try again.")

result = st.session_state.get("notice_result")
if result is not None:
    st.markdown("## Extracted actions")
    st.markdown('<p class="section-note">Review the deadlines and details below. Low-confidence items and unclear information are called out.</p>', unsafe_allow_html=True)

    high_priority_count = sum(action.priority == "high" for action in result.actions)
    dated_action_count = sum(action.deadline is not None for action in result.actions)
    metric_columns = st.columns(3)
    metric_columns[0].metric("Actions found", len(result.actions))
    metric_columns[1].metric("High priority", high_priority_count)
    metric_columns[2].metric("With a deadline", dated_action_count)

    issuer = f" · {html.escape(result.issued_by)}" if result.issued_by else ""
    st.markdown(
        f'<p class="result-meta">{html.escape(result.category.replace("_", " ").title())}{issuer}</p>'
        f'<h3 class="result-title">{html.escape(result.title)}</h3>'
        f'<p class="result-summary">{html.escape(result.summary)}</p>',
        unsafe_allow_html=True,
    )

    if result.actions:
        for index, action in enumerate(result.actions):
            with st.container(key=f"action-card-{index}"):
                title_column, priority_column = st.columns([5, 1], vertical_alignment="center")
                title_column.markdown(f"### {html.escape(action.task)}")
                priority_color = {"high": "red", "medium": "orange", "low": "green"}[action.priority]
                priority_column.badge(action.priority.title(), color=priority_color)
                if action.description:
                  st.markdown(f'<p class="result-summary">{html.escape(action.description)}</p>', unsafe_allow_html=True)

                details = st.columns(2)
                if action.deadline:
                    deadline_label = action.deadline.strftime("%A, %d %B %Y")
                    if action.deadline_text and action.deadline_text.casefold() not in deadline_label.casefold():
                        deadline_label += f" · {action.deadline_text}"
                    details[0].markdown(f"**Deadline**  \n{html.escape(deadline_label)}")
                else:
                    details[0].markdown("**Deadline**  \nNo fixed date")
                details[1].markdown(f"**Applies to**  \n{html.escape(action.applies_to)}")
                if action.event_date:
                  event_label = action.event_date.strftime("%A, %d %B %Y")
                  if action.event_date_text and action.event_date_text.casefold() not in event_label.casefold():
                    event_label += f" · {action.event_date_text}"
                  if action.time:
                    event_label += f" · {action.time}"
                  st.markdown(f"**Event date / time**  \n{html.escape(event_label)}")
                elif action.time:
                  st.markdown(f"**Time**  \n{html.escape(action.time)}")

                extras = []
                if action.fee:
                    extras.append(f"**Fee:** {html.escape(action.fee)}")
                if action.required_documents:
                    documents = ", ".join(html.escape(item) for item in action.required_documents)
                    extras.append(f"**Bring:** {documents}")
                if action.where_or_contact:
                    extras.append(f"**Where / contact:** {html.escape(action.where_or_contact)}")
                if extras:
                    st.markdown("  ·  ".join(extras))
                st.caption(f"Category: {result.category.replace('_', ' ').title()}  ·  Confidence: {action.confidence:.0%}")
                if action.confidence < 0.6:
                    st.warning("This action may be unclear in the original notice. Verify it before acting.", icon=":material/visibility:")
    else:
        st.markdown('<div class="empty-state">No action items were identified in this notice.</div>', unsafe_allow_html=True)

    if result.ambiguities:
        with st.expander("Details to verify", icon=":material/info:"):
            for ambiguity in result.ambiguities:
                st.markdown(f"- {html.escape(ambiguity)}")

    st.markdown("#### Take these details with you")
    export_columns = st.columns(2)
    export_columns[0].download_button(
        "Download checklist",
        data=to_markdown(result),
        file_name="notice-checklist.md",
        mime="text/markdown",
        icon=":material/description:",
        width="stretch",
    )
    export_columns[1].download_button(
        "Add deadlines to calendar",
        data=to_ics([result]),
        file_name="notice-deadlines.ics",
        mime="text/calendar",
        icon=":material/calendar_add_on:",
        width="stretch",
    )
else:
    st.markdown('<div class="empty-state">Your action list will appear here once you analyze a notice.</div>', unsafe_allow_html=True)