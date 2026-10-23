"""Visual system for VoiceNote AI.

The palette, radii, borders and fonts come from Streamlit's own theme
(``.streamlit/config.toml``), so the app keeps its identity even if custom CSS
is stripped. This module only adds what the theme cannot express: editorial
type for the wordmark and notes, hairline section rules, speaker colours and
the transcript / notes markup.
"""

from __future__ import annotations

import streamlit as st

# (text colour, tint) — anonymous speaker clusters, never identities.
SPEAKER_COLORS = [
    ("#1e5eff", "#ecefff"),
    ("#0f766e", "#e6f5f1"),
    ("#b45309", "#fbf1e2"),
    ("#be123c", "#fceaee"),
    ("#6d28d9", "#f1ecff"),
    ("#475569", "#eef1f5"),
]


def speaker_palette(speaker: str | None) -> tuple[str, str]:
    if not speaker:
        return "#8a8f9c", "#f2f1ec"
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
    --vn-paper: #fbfaf8;
    --vn-surface: #ffffff;
    --vn-ink: #14161a;
    --vn-body: #3b4150;
    --vn-muted: #8a8f9c;
    --vn-line: #e3dfd4;
    --vn-line-soft: #efece4;
    --vn-accent: #1e5eff;
    --vn-accent-ink: #1849d6;
    --vn-accent-soft: #ecefff;
    --vn-serif: "Iowan Old Style", "Palatino Linotype", Palatino, "Book Antiqua", Georgia, serif;
    --vn-mono: ui-monospace, SFMono-Regular, "SF Mono", Menlo, Consolas, monospace;
  }

  /* Canvas ------------------------------------------------------------- */
  .stApp { background: var(--vn-paper); }
  [data-testid="stHeader"], [data-testid="stToolbar"] { display: none; }
  [data-testid="stSidebar"], [data-testid="stSidebarCollapsedControl"] { display: none; }
  .block-container {
    max-width: 1060px;
    padding: 1.6rem 2rem 3.5rem;
  }
  html, body, .stApp {
    font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, "Helvetica Neue",
                 Arial, sans-serif;
    -webkit-font-smoothing: antialiased;
  }

  /* Top bar ------------------------------------------------------------ */
  .vn-brand { display: flex; align-items: center; gap: 0.62rem; }
  .vn-mark {
    width: 34px; height: 34px; border-radius: 10px; background: var(--vn-ink);
    color: #fff; display: grid; place-items: center; flex: 0 0 auto;
  }
  .vn-wordmark {
    font-family: var(--vn-serif); font-size: 1.24rem; font-weight: 600;
    letter-spacing: -0.015em; color: var(--vn-ink); line-height: 1.05;
  }
  .vn-tagline {
    font-size: 0.7rem; letter-spacing: 0.06em; text-transform: uppercase;
    color: var(--vn-muted); margin-top: 3px;
  }
  .vn-statusline { display: flex; align-items: center; gap: 0.4rem; justify-content: flex-end; }
  .vn-dot { width: 6px; height: 6px; border-radius: 50%; background: #16a34a; display: inline-block; }
  .vn-dot.busy { background: #d97706; }
  .vn-dot.done { background: var(--vn-accent); }
  .vn-status-text { font-size: 0.78rem; color: var(--vn-body); }

  .vn-rule { height: 1px; background: var(--vn-line); margin: 1rem 0 0; }

  /* Section labels ------------------------------------------------------ */
  .vn-kicker {
    display: flex; align-items: center; gap: 0.5rem;
    font-size: 0.68rem; font-weight: 700; letter-spacing: 0.13em;
    text-transform: uppercase; color: var(--vn-muted);
  }
  .vn-kicker::before {
    content: ""; width: 14px; height: 1px; background: var(--vn-accent); display: inline-block;
  }
  .vn-kicker .n { color: var(--vn-ink); }
  .vn-section-meta { font-size: 0.76rem; color: var(--vn-muted); }
  .vn-section-meta b { color: var(--vn-body); font-weight: 600; }
  .vn-mono { font-family: var(--vn-mono); font-variant-numeric: tabular-nums; }

  /* Steps -------------------------------------------------------------- */
  .vn-steps { display: flex; align-items: center; gap: 0.55rem; font-size: 0.74rem; color: #a9adb8; }
  .vn-steps .s { display: inline-flex; align-items: center; gap: 0.35rem; }
  .vn-steps .s.done { color: var(--vn-muted); }
  .vn-steps .s.active { color: var(--vn-accent-ink); font-weight: 600; }
  .vn-steps .bar { width: 14px; height: 1px; background: var(--vn-line); }

  /* Cards -------------------------------------------------------------
     Streamlit draws the bordered container; this only refines spacing so the
     look survives even if a selector is skipped. */
  div[data-testid="stVerticalBlock"]:has(> div[data-testid="stElementContainer"] .vn-cardsig) {
    background: var(--vn-surface);
    border: 1px solid var(--vn-line) !important;
    border-radius: 16px !important;
    padding: 1.15rem 1.25rem 1.2rem !important;
  }

  /* Transcript --------------------------------------------------------- */
  .vn-legend { display: flex; gap: 0.3rem; flex-wrap: wrap; margin: 0.1rem 0 0.35rem; }
  .vn-chip {
    font-size: 0.7rem; padding: 0.14rem 0.46rem; border-radius: 999px;
    border: 1px solid currentColor; background: #fff; font-weight: 600;
  }
  .vn-chip span { opacity: 0.55; font-weight: 500; }
  .vn-tlist { margin: 0.15rem 0 0; }
  .vn-trow {
    display: grid; grid-template-columns: 92px 1fr; gap: 1rem;
    padding: 0.62rem 0; border-top: 1px solid var(--vn-line-soft);
  }
  .vn-trow:first-child { border-top: 0; }
  .vn-tmeta { display: flex; flex-direction: column; gap: 1px; }
  .vn-spk { font-size: 0.74rem; font-weight: 650; }
  .vn-ts { font-family: var(--vn-mono); font-size: 0.68rem; color: var(--vn-muted); }
  .vn-tt { font-size: 0.925rem; line-height: 1.62; color: var(--vn-body); }

  /* Notes -------------------------------------------------------------- */
  .vn-note-title {
    font-family: var(--vn-serif); font-size: 1.45rem; font-weight: 600;
    letter-spacing: -0.015em; color: var(--vn-ink); margin-bottom: 0.1rem;
  }
  .vn-note-meta { font-size: 0.72rem; color: var(--vn-muted); margin-bottom: 0.85rem; }
  .vn-notes { max-width: 68ch; }
  .vn-notes p { font-size: 0.94rem; line-height: 1.68; color: var(--vn-body); margin: 0 0 0.9rem; }
  .vn-block { margin-bottom: 1rem; }
  .vn-block-label {
    font-size: 0.64rem; font-weight: 700; letter-spacing: 0.12em; text-transform: uppercase;
    color: var(--vn-muted); margin-bottom: 0.3rem;
  }
  .vn-block ul { margin: 0; padding-left: 1.05rem; }
  .vn-block li { font-size: 0.92rem; line-height: 1.6; color: var(--vn-body); margin-bottom: 0.2rem; }
  .vn-block li::marker { color: #c9ccd6; }
  .vn-quiet { font-size: 0.88rem; color: var(--vn-muted); font-style: italic; }
  .vn-actions { display: flex; flex-direction: column; gap: 0.35rem; }
  .vn-actions .a { font-size: 0.9rem; line-height: 1.5; color: var(--vn-body); }
  .vn-actions .tags { display: flex; gap: 0.25rem; margin-top: 0.15rem; flex-wrap: wrap; }
  .vn-tag {
    font-size: 0.66rem; padding: 0.06rem 0.36rem; border-radius: 5px; font-weight: 600;
    background: var(--vn-accent-soft); color: var(--vn-accent-ink);
  }
  .vn-tag.due { background: #fdf1d6; color: #92400e; }

  /* Empty / intro ------------------------------------------------------ */
  .vn-intro { padding: 1.7rem 0 0.4rem; max-width: 46ch; }
  .vn-intro h2 {
    font-family: var(--vn-serif); font-size: 1.15rem; font-weight: 600; color: var(--vn-ink);
    margin: 0 0 0.3rem;
  }
  .vn-intro p { font-size: 0.9rem; line-height: 1.65; color: var(--vn-muted); margin: 0; }
  .vn-empty { font-size: 0.88rem; color: var(--vn-muted); padding: 0.4rem 0 0.2rem; }

  /* Widgets ------------------------------------------------------------ */
  [data-testid="stIconMaterial"] { display: none !important; }
  [data-testid="stExpander"] summary::after {
    content: "\\25BE"; font-size: 0.7rem; color: #b3b7c2; margin-left: 0.4rem;
  }
  [data-testid="stExpander"] details[open] > summary::after { content: "\\25B4"; }
  [data-testid="stPopover"] button::after {
    content: "\\25BE"; font-size: 0.6rem; color: #b3b7c2; margin-left: 0.3rem;
  }
  [data-testid="stPopoverBody"] [data-testid="stWidgetLabel"] p { font-size: 0.8rem; color: #5f6472; }
  [data-testid="stPopoverBody"] h5 {
    font-family: inherit; font-size: 0.66rem; font-weight: 700; letter-spacing: 0.12em;
    text-transform: uppercase; color: var(--vn-muted); margin: 0.6rem 0 0.15rem;
  }
  .stButton > button, .stDownloadButton > button {
    font-weight: 600; font-size: 0.84rem; padding: 0.34rem 0.8rem;
  }
  .stButton > button[kind="secondary"]:hover, .stDownloadButton > button:hover {
    border-color: var(--vn-accent); color: var(--vn-accent-ink);
  }
  [data-testid="stAudioInput"] { margin: 0 auto; }
  [data-testid="stFileUploaderDropzone"] {
    background: #fff; border: 1px dashed #d9d5c9; border-radius: 12px;
  }
  [data-testid="stFileUploaderDropzone"] button {
    font-size: 0.8rem; border-radius: 8px;
  }
  .stTextArea textarea, .stTextInput input { font-size: 0.9rem; line-height: 1.55; }
  [data-testid="stSegmentedControl"] button { font-size: 0.82rem; font-weight: 600; }

  /* Footer ------------------------------------------------------------- */
  .vn-footer {
    margin-top: 2.4rem; padding-top: 0.9rem; border-top: 1px solid var(--vn-line);
    display: flex; justify-content: space-between; gap: 1rem; flex-wrap: wrap;
    font-size: 0.72rem; color: #a2a7b3;
  }
  .vn-footer b { color: var(--vn-muted); font-weight: 600; }

  @media (max-width: 860px) {
    .block-container { padding: 1.1rem 1.1rem 2.4rem; }
    .vn-trow { grid-template-columns: 1fr; gap: 0.1rem; }
    .vn-tmeta { flex-direction: row; gap: 0.5rem; align-items: baseline; }
  }
</style>
        """,
        unsafe_allow_html=True,
    )
