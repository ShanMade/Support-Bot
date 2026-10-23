"""Visual system for VoiceNote AI.

The palette, radii and typography come from Streamlit's own theme
(``.streamlit/config.toml``): near-white canvas, near-black ink, cool blue
accent, 12px radii, one sans stack. This module adds the few things a theme
cannot express - the wordmark, section labels, card polish, the transcript
grid and the notes layout - and nothing else, so the interface never fights
the framework.
"""

from __future__ import annotations

import streamlit as st

# (text colour, tint) - anonymous speaker clusters, never identities.
SPEAKER_COLORS = [
    ("#2563eb", "#eef3ff"),
    ("#0d9488", "#e7f7f4"),
    ("#c2410c", "#fdf0e7"),
    ("#db2777", "#fdecf4"),
    ("#7c3aed", "#f2edff"),
    ("#52627a", "#eef1f5"),
]


def speaker_palette(speaker: str | None) -> tuple[str, str]:
    if not speaker:
        return "#8b8f99", "#f2f2f5"
    digits = "".join(ch for ch in speaker if ch.isdigit())
    index = (int(digits) - 1) if digits else 0
    return SPEAKER_COLORS[index % len(SPEAKER_COLORS)]


def speaker_color(speaker: str | None) -> str:
    return speaker_palette(speaker)[0]


def inject() -> None:
    st.markdown(
        """
<style>
  :root {
    --vn-canvas: #fcfcfd;
    --vn-surface: #ffffff;
    --vn-ink: #0f1115;
    --vn-body: #3d4350;
    --vn-muted: #8b8f99;
    --vn-faint: #a8acb6;
    --vn-line: #e7e7ec;
    --vn-line-soft: #f0f0f3;
    --vn-accent: #2563eb;
    --vn-accent-soft: #eef3ff;
    --vn-shadow: 0 1px 2px rgba(15, 17, 21, 0.04), 0 8px 24px -18px rgba(15, 17, 21, 0.22);
    --vn-sans: -apple-system, BlinkMacSystemFont, "Segoe UI", Inter, Roboto,
               "Helvetica Neue", Arial, sans-serif;
    --vn-mono: ui-monospace, SFMono-Regular, "SF Mono", Menlo, Consolas, monospace;
  }

  /* Canvas ------------------------------------------------------------- */
  .stApp { background: var(--vn-canvas); }
  [data-testid="stHeader"], [data-testid="stToolbar"] { display: none; }
  [data-testid="stSidebar"], [data-testid="stSidebarCollapsedControl"] { display: none; }
  .block-container {
    max-width: 1120px;
    padding: 1.35rem 2rem 3rem;
  }
  html, body, .stApp { font-family: var(--vn-sans); -webkit-font-smoothing: antialiased; }
  h1, h2, h3, h4, h5 { letter-spacing: -0.014em; }
  p, li, label, [data-testid="stMarkdownContainer"] { color: var(--vn-body); }

  /* Top bar ------------------------------------------------------------ */
  .vn-brand { display: flex; align-items: center; gap: 0.6rem; }
  .vn-mark {
    width: 32px; height: 32px; border-radius: 9px;
    background: linear-gradient(160deg, #22252c 0%, #0f1115 100%);
    color: #fff; display: grid; place-items: center; flex: 0 0 auto;
    box-shadow: 0 1px 2px rgba(15, 17, 21, 0.24);
  }
  .vn-wordmark {
    font-size: 0.98rem; font-weight: 650; letter-spacing: -0.015em;
    color: var(--vn-ink); line-height: 1.15;
  }
  .vn-tagline { font-size: 0.75rem; color: var(--vn-muted); margin-top: 2px; }

  .vn-statusline {
    display: inline-flex; align-items: center; gap: 0.4rem;
    background: var(--vn-surface); border: 1px solid var(--vn-line);
    border-radius: 999px; padding: 0.2rem 0.6rem;
  }
  .vn-dot {
    width: 6px; height: 6px; border-radius: 50%; background: #12b76a;
    display: inline-block; box-shadow: 0 0 0 3px rgba(18, 183, 106, 0.12);
  }
  .vn-dot.busy { background: #f79009; box-shadow: 0 0 0 3px rgba(247, 144, 9, 0.14); }
  .vn-dot.done { background: var(--vn-accent); box-shadow: 0 0 0 3px rgba(37, 99, 235, 0.12); }
  .vn-status-text { font-size: 0.76rem; color: var(--vn-body); font-weight: 500; }

  /* Steps -------------------------------------------------------------- */
  .vn-steps { display: flex; align-items: center; gap: 0.5rem; font-size: 0.76rem; }
  .vn-steps .s { display: inline-flex; align-items: center; gap: 0.34rem; color: var(--vn-faint); }
  .vn-steps .s::before {
    content: ""; width: 5px; height: 5px; border-radius: 50%;
    background: currentColor; opacity: 0.55;
  }
  .vn-steps .s.done { color: #9aa0ac; }
  .vn-steps .s.done::before { opacity: 1; background: #b8bdc7; }
  .vn-steps .s.active { color: var(--vn-ink); font-weight: 600; }
  .vn-steps .s.active::before { opacity: 1; background: var(--vn-accent); }
  .vn-steps .bar { width: 18px; height: 1px; background: var(--vn-line); }

  /* Section labels ------------------------------------------------------ */
  .vn-kicker {
    font-size: 0.68rem; font-weight: 600; letter-spacing: 0.075em;
    text-transform: uppercase; color: var(--vn-muted);
  }
  .vn-section-meta { font-size: 0.76rem; color: var(--vn-muted); }
  .vn-section-meta b { color: var(--vn-body); font-weight: 600; }
  .vn-mono { font-family: var(--vn-mono); font-variant-numeric: tabular-nums; }

  /* Cards --------------------------------------------------------------
     Streamlit draws the bordered container; this only refines it. */
  div[data-testid="stVerticalBlock"]:has(> div[data-testid="stElementContainer"] .vn-cardsig) {
    background: var(--vn-surface);
    border: 1px solid var(--vn-line) !important;
    border-radius: 14px !important;
    box-shadow: var(--vn-shadow);
    padding: 1.2rem 1.35rem 1.25rem !important;
  }

  /* Transcript --------------------------------------------------------- */
  .vn-legend { display: flex; gap: 0.3rem; flex-wrap: wrap; margin: 0.05rem 0 0.3rem; }
  .vn-chip {
    font-size: 0.705rem; padding: 0.14rem 0.5rem; border-radius: 999px;
    background: var(--vn-surface); border: 1px solid var(--vn-line);
    font-weight: 600; letter-spacing: -0.005em;
  }
  .vn-chip span { color: var(--vn-muted); font-weight: 500; }
  .vn-tlist { margin: 0.1rem 0 0; }
  .vn-trow {
    display: grid; grid-template-columns: 88px 1fr; gap: 1.1rem;
    padding: 0.6rem 0; border-top: 1px solid var(--vn-line-soft);
  }
  .vn-trow:first-child { border-top: 0; padding-top: 0.15rem; }
  .vn-tmeta { display: flex; flex-direction: column; gap: 2px; }
  .vn-spk { font-size: 0.75rem; font-weight: 600; letter-spacing: -0.005em; }
  .vn-ts { font-family: var(--vn-mono); font-size: 0.685rem; color: var(--vn-faint); }
  .vn-tt { font-size: 0.925rem; line-height: 1.62; color: var(--vn-body); }

  /* Notes -------------------------------------------------------------- */
  .vn-note-title {
    font-size: 1.32rem; font-weight: 650; letter-spacing: -0.02em;
    color: var(--vn-ink); line-height: 1.28;
  }
  .vn-note-meta { font-size: 0.735rem; color: var(--vn-faint); margin-top: 0.28rem; }
  .vn-notes { max-width: 70ch; }
  .vn-note-title + .vn-note-meta + p { margin-top: 0.85rem; }
  .vn-notes > p {
    font-size: 0.935rem; line-height: 1.68; color: var(--vn-body);
    margin: 0.85rem 0 0;
  }
  .vn-block { margin-top: 1.25rem; }
  .vn-block-label {
    font-size: 0.665rem; font-weight: 600; letter-spacing: 0.075em;
    text-transform: uppercase; color: var(--vn-muted); margin-bottom: 0.42rem;
  }
  .vn-block ul { margin: 0; padding-left: 1rem; }
  .vn-block li { font-size: 0.915rem; line-height: 1.6; color: var(--vn-body); margin-bottom: 0.22rem; }
  .vn-block li::marker { color: #c4c8d0; }
  .vn-quiet { font-size: 0.885rem; color: var(--vn-faint); }

  .vn-actions { display: flex; flex-direction: column; }
  .vn-actions .a {
    font-size: 0.915rem; line-height: 1.5; color: var(--vn-body);
    padding: 0.42rem 0; border-top: 1px solid var(--vn-line-soft);
  }
  .vn-actions .a:first-child { border-top: 0; padding-top: 0; }
  .vn-actions .tags { display: flex; gap: 0.28rem; margin-top: 0.3rem; flex-wrap: wrap; }
  .vn-tag {
    font-size: 0.68rem; padding: 0.06rem 0.42rem; border-radius: 6px; font-weight: 550;
    background: var(--vn-accent-soft); color: #1d4ed8;
  }
  .vn-tag.due { background: #f4f4f6; color: #5c6270; }

  /* Intro / empty ------------------------------------------------------ */
  .vn-intro { padding: 1.5rem 0 1.1rem; max-width: 58ch; }
  .vn-intro h2 {
    font-size: 1.52rem; font-weight: 650; letter-spacing: -0.028em; line-height: 1.22;
    color: var(--vn-ink); margin: 0 0 0.42rem;
  }
  .vn-intro p { font-size: 0.945rem; line-height: 1.66; color: #6b7280; margin: 0; }
  .vn-empty { font-size: 0.88rem; color: var(--vn-faint); padding: 0.4rem 0 0.2rem; }

  /* Widgets ------------------------------------------------------------ */
  [data-testid="stIconMaterial"] { display: none !important; }
  [data-testid="stExpander"] summary::after {
    content: "\\25BE"; font-size: 0.66rem; color: #b3b7c0; margin-left: 0.4rem;
  }
  [data-testid="stExpander"] details[open] > summary::after { content: "\\25B4"; }
  [data-testid="stPopover"] button::after {
    content: "\\25BE"; font-size: 0.56rem; color: #b3b7c0; margin-left: 0.32rem;
  }
  [data-testid="stPopoverBody"] { border-radius: 14px !important; }
  [data-testid="stPopoverBody"] [data-testid="stWidgetLabel"] p { font-size: 0.78rem; color: #5c6270; }
  [data-testid="stPopoverBody"] h5 {
    font-size: 0.665rem; font-weight: 600; letter-spacing: 0.075em;
    text-transform: uppercase; color: var(--vn-muted); margin: 0.75rem 0 0.2rem;
  }
  .stButton > button, .stDownloadButton > button {
    font-weight: 550; font-size: 0.855rem; padding: 0.36rem 0.85rem;
    box-shadow: 0 1px 1px rgba(15, 17, 21, 0.04);
  }
  .stButton > button[kind="primary"] {
    background: var(--vn-ink); border-color: var(--vn-ink); color: #fff;
  }
  .stButton > button[kind="primary"]:hover {
    background: #272b33; border-color: #272b33; color: #fff;
  }
  .stButton > button[kind="secondary"] {
    background: var(--vn-surface); border-color: var(--vn-line); color: var(--vn-ink);
  }
  .stButton > button[kind="secondary"]:hover,
  .stDownloadButton > button:hover {
    border-color: #cfd3da; background: #fafafb;
  }
  .stDownloadButton > button { background: var(--vn-surface); color: var(--vn-ink); }
  [data-testid="stAudioInput"] { margin: 0 auto; }
  [data-testid="stFileUploaderDropzone"] {
    background: #fbfbfc; border: 1px dashed #dcdfe4; border-radius: 12px;
  }
  [data-testid="stFileUploaderDropzone"] button { font-size: 0.82rem; border-radius: 8px; }
  .stTextArea textarea, .stTextInput input { font-size: 0.9rem; line-height: 1.55; }
  [data-testid="stSegmentedControl"] button { font-size: 0.83rem; font-weight: 550; }
  [data-testid="stPills"] button { font-size: 0.79rem; font-weight: 550; }
  [data-testid="stDataFrame"] { border-radius: 10px; }

  /* Footer ------------------------------------------------------------- */
  .vn-footer {
    margin-top: 2.6rem; padding-top: 1rem; border-top: 1px solid var(--vn-line);
    display: flex; justify-content: space-between; gap: 1rem; flex-wrap: wrap;
    font-size: 0.745rem; color: var(--vn-faint);
  }
  .vn-footer b { color: var(--vn-muted); font-weight: 600; }

  @media (max-width: 860px) {
    .block-container { padding: 1rem 1.1rem 2.2rem; }
    .vn-trow { grid-template-columns: 1fr; gap: 0.15rem; }
    .vn-tmeta { flex-direction: row; gap: 0.5rem; align-items: baseline; }
  }
</style>
        """,
        unsafe_allow_html=True,
    )
