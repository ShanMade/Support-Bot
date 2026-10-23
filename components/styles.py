"""Minimal custom CSS.

Streamlit's theme (see ``.streamlit/config.toml``) provides the palette; this module
only adds the few touches the theme cannot express: the compact header, the status
pills, the speaker chips and the transcript rows.
"""

from __future__ import annotations

import streamlit as st

SPEAKER_COLORS = [
    "#4f46e5",  # indigo
    "#0f766e",  # teal
    "#b45309",  # amber-700
    "#be123c",  # rose-700
    "#1d4ed8",  # blue-700
    "#6d28d9",  # violet-700
]


def speaker_color(speaker: str | None) -> str:
    if not speaker:
        return "#64748b"
    digits = "".join(ch for ch in speaker if ch.isdigit())
    index = (int(digits) - 1) if digits else 0
    return SPEAKER_COLORS[index % len(SPEAKER_COLORS)]


def inject() -> None:
    st.markdown(
        """
<style>
  /* Layout ------------------------------------------------------------ */
  .block-container { padding-top: 2.1rem; padding-bottom: 1.5rem; max-width: 1180px; }
  [data-testid="stHeader"] { background: transparent; }
  footer, #MainMenu { visibility: hidden; }

  /* Header ------------------------------------------------------------ */
  .vn-header {
      display: flex; align-items: center; gap: 0.7rem;
      padding: 0.2rem 0 0.9rem 0; border-bottom: 1px solid #e6e9f0; margin-bottom: 1.1rem;
  }
  .vn-logo {
      width: 38px; height: 38px; border-radius: 10px; background: #eef2ff;
      display: flex; align-items: center; justify-content: center; color: #4f46e5;
      flex: 0 0 auto;
  }
  .vn-title { font-size: 1.32rem; font-weight: 650; color: #0f172a; line-height: 1.15; letter-spacing: -0.01em; }
  .vn-sub { font-size: 0.8rem; color: #64748b; margin-top: 2px; }
  .vn-header-right { margin-left: auto; display: flex; gap: 0.4rem; flex-wrap: wrap; }

  /* Pills ------------------------------------------------------------- */
  .vn-pill {
      display: inline-flex; align-items: center; gap: 0.35rem;
      font-size: 0.74rem; font-weight: 550; padding: 0.2rem 0.55rem;
      border-radius: 999px; border: 1px solid #e2e8f0; background: #fff; color: #475569;
      white-space: nowrap;
  }
  .vn-pill .dot { width: 7px; height: 7px; border-radius: 50%; background: #cbd5e1; }
  .vn-pill.ok .dot { background: #16a34a; }
  .vn-pill.warn .dot { background: #d97706; }
  .vn-pill.off .dot { background: #cbd5e1; }
  .vn-pill.ok { border-color: #bbf7d0; background: #f0fdf4; color: #166534; }
  .vn-pill.warn { border-color: #fde68a; background: #fffbeb; color: #92400e; }

  /* Step bar ---------------------------------------------------------- */
  .vn-steps { display: flex; gap: 0.45rem; flex-wrap: wrap; margin: 0.1rem 0 1rem 0; }
  .vn-step {
      font-size: 0.76rem; padding: 0.26rem 0.6rem; border-radius: 8px;
      background: #f8fafc; border: 1px solid #e8ecf3; color: #64748b;
  }
  .vn-step strong { color: #334155; font-weight: 600; }
  .vn-step.active { background: #eef2ff; border-color: #c7d2fe; color: #4338ca; }
  .vn-step.active strong { color: #3730a3; }
  .vn-step.done { background: #f0fdf4; border-color: #bbf7d0; color: #15803d; }
  .vn-step.done strong { color: #166534; }

  /* Section headings -------------------------------------------------- */
  .vn-section {
      font-size: 0.95rem; font-weight: 620; color: #0f172a; margin: 0.15rem 0 0.55rem 0;
      display: flex; align-items: center; gap: 0.45rem;
  }
  .vn-section .count { font-size: 0.72rem; font-weight: 500; color: #64748b; }

  /* Transcript -------------------------------------------------------- */
  .vn-transcript { display: flex; flex-direction: column; gap: 0.55rem; margin-top: 0.2rem; }
  .vn-seg {
      display: grid; grid-template-columns: 96px 1fr; gap: 0.65rem;
      padding: 0.5rem 0.65rem; border-radius: 9px; background: #fbfcfe;
      border: 1px solid #eef1f6;
  }
  .vn-seg-meta { display: flex; flex-direction: column; gap: 2px; padding-top: 1px; }
  .vn-spk { font-size: 0.72rem; font-weight: 650; }
  .vn-time { font-size: 0.68rem; color: #94a3b8; font-variant-numeric: tabular-nums; }
  .vn-text { font-size: 0.9rem; line-height: 1.5; color: #1e293b; }
  .vn-empty { color: #64748b; font-size: 0.86rem; padding: 0.5rem 0; }

  /* Legend ------------------------------------------------------------ */
  .vn-legend { display: flex; gap: 0.4rem; flex-wrap: wrap; margin: 0.25rem 0 0.75rem 0; }
  .vn-chip {
      font-size: 0.72rem; padding: 0.18rem 0.5rem; border-radius: 999px;
      border: 1px solid currentColor; background: #fff; font-weight: 550;
  }

  /* Notes ------------------------------------------------------------- */
  .vn-note-title { font-size: 1.02rem; font-weight: 650; color: #0f172a; margin-bottom: 0.15rem; }
  .vn-note-meta { font-size: 0.72rem; color: #94a3b8; margin-bottom: 0.6rem; }
  .vn-notes-text { font-size: 0.9rem; line-height: 1.55; color: #1e293b; }

  /* Footer ------------------------------------------------------------ */
  .vn-footer {
      margin-top: 2rem; padding-top: 0.8rem; border-top: 1px solid #e6e9f0;
      font-size: 0.74rem; color: #94a3b8; display: flex; justify-content: space-between;
      gap: 1rem; flex-wrap: wrap;
  }
  .vn-footer a { color: #64748b; text-decoration: none; }

  /* Widgets ----------------------------------------------------------- */
  div[data-testid="stVerticalBlockBorderWrapper"] { border-radius: 12px; }
  .stButton > button { border-radius: 8px; font-weight: 550; }
  .stDownloadButton > button { border-radius: 8px; }
  [data-testid="stAudioInput"] { margin-bottom: 0.25rem; }

  @media (max-width: 900px) {
    .vn-seg { grid-template-columns: 1fr; gap: 0.15rem; }
    .vn-seg-meta { flex-direction: row; gap: 0.5rem; align-items: center; }
  }
</style>
        """,
        unsafe_allow_html=True,
    )
