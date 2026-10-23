"""Design system for VoiceNote AI.

Streamlit supplies the controls; this module supplies the look: a light canvas,
white cards with hairline borders, one indigo accent, and compact typography.
"""

from __future__ import annotations

import streamlit as st

SPEAKER_COLORS = [
    ("#4f46e5", "#eef1ff"),  # indigo
    ("#0f766e", "#e7f6f3"),  # teal
    ("#b45309", "#fdf4e3"),  # amber
    ("#be123c", "#fdeef1"),  # rose
    ("#1d4ed8", "#eaf0ff"),  # blue
    ("#6d28d9", "#f2edff"),  # violet
]


def speaker_palette(speaker: str | None) -> tuple[str, str]:
    """Return ``(text_colour, background)`` for an anonymous speaker label."""
    if not speaker:
        return "#64748b", "#f1f3f8"
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
    --vn-bg: #f7f8fc;
    --vn-card: #ffffff;
    --vn-border: #e9ebf2;
    --vn-border-strong: #dfe3ee;
    --vn-text: #111827;
    --vn-body: #273043;
    --vn-muted: #6b7280;
    --vn-faint: #8b93a7;
    --vn-accent: #4f46e5;
    --vn-accent-strong: #4338ca;
    --vn-accent-soft: #eef1ff;
    --vn-radius: 14px;
  }

  /* Canvas ------------------------------------------------------------- */
  .stApp { background: var(--vn-bg); }
  [data-testid="stHeader"] { display: none; }
  [data-testid="stToolbar"] { display: none; }
  .block-container {
    max-width: 1180px;
    padding: 1.6rem 2rem 3rem 2rem;
  }
  html, body, .stApp, [class*="st-"] {
    font-family: ui-sans-serif, -apple-system, BlinkMacSystemFont, "Segoe UI",
                 Roboto, "Helvetica Neue", Arial, sans-serif;
  }
  [data-testid="stSidebar"], [data-testid="stSidebarCollapsedControl"] { display: none; }

  /* Header ------------------------------------------------------------- */
  .vn-brand { display: flex; align-items: center; gap: 0.7rem; }
  .vn-mark {
    width: 40px; height: 40px; border-radius: 12px; background: var(--vn-accent);
    color: #fff; display: grid; place-items: center; flex: 0 0 auto;
    box-shadow: 0 10px 20px -12px rgba(79, 70, 229, 0.9);
  }
  .vn-name {
    font-size: 1.22rem; font-weight: 700; letter-spacing: -0.02em;
    color: var(--vn-text); line-height: 1.1;
  }
  .vn-tagline { font-size: 0.78rem; color: var(--vn-muted); margin-top: 3px; }
  .vn-rule { height: 1px; background: var(--vn-border); margin: 0.9rem 0 1rem; }

  /* Status chip -------------------------------------------------------- */
  .vn-status {
    display: inline-flex; align-items: center; gap: 0.42rem;
    padding: 0.28rem 0.62rem; border-radius: 999px; background: #fff;
    border: 1px solid var(--vn-border); font-size: 0.74rem; font-weight: 600;
    color: #566076; white-space: nowrap;
  }
  .vn-status .dot {
    width: 7px; height: 7px; border-radius: 50%; background: #16a34a;
    box-shadow: 0 0 0 3px rgba(22, 163, 74, 0.12);
  }
  .vn-status.busy .dot { background: #d97706; box-shadow: 0 0 0 3px rgba(217, 119, 6, 0.14); }
  .vn-status.done .dot { background: #4f46e5; box-shadow: 0 0 0 3px rgba(79, 70, 229, 0.12); }

  /* Workflow steps ----------------------------------------------------- */
  .vn-steps { display: flex; align-items: center; gap: 0.3rem; flex-wrap: wrap; margin: 0.15rem 0 1.15rem; }
  .vn-step {
    display: inline-flex; align-items: center; gap: 0.42rem; padding: 0.32rem 0.58rem;
    border-radius: 9px; font-size: 0.75rem; font-weight: 550; color: #6b7280;
    border: 1px solid transparent;
  }
  .vn-step .idx {
    width: 18px; height: 18px; border-radius: 50%; background: #eceff6;
    color: #7b8297; display: grid; place-items: center; font-size: 0.65rem; font-weight: 700;
  }
  .vn-step.active { background: #fff; border-color: #dcdefb; color: #3730a3; box-shadow: 0 1px 2px rgba(16, 24, 40, 0.04); }
  .vn-step.active .idx { background: var(--vn-accent); color: #fff; }
  .vn-step.done { color: #15803d; }
  .vn-step.done .idx { background: #dcfce7; color: #15803d; }
  .vn-sep { width: 18px; height: 1px; background: #e2e5ee; }

  /* Cards --------------------------------------------------------------
     Each card is a plain vertical block whose first element carries a marker
     class (.vn-card-head / .vn-empty), so the styling never depends on
     Streamlit-internal class names. */
  div[data-testid="stVerticalBlock"]:has(> div[data-testid="stElementContainer"] .vn-card-head),
  div[data-testid="stVerticalBlock"]:has(> div[data-testid="stElementContainer"] .vn-empty) {
    background: var(--vn-card);
    border: 1px solid var(--vn-border);
    border-radius: var(--vn-radius);
    box-shadow: 0 1px 2px rgba(16, 24, 40, 0.03), 0 18px 44px -34px rgba(16, 24, 40, 0.4);
    padding: 1rem 1.05rem 0.95rem;
  }
  .vn-card-head {
    display: flex; align-items: center; justify-content: space-between;
    gap: 0.6rem; margin-bottom: 0.55rem;
  }
  .vn-card-title {
    display: flex; align-items: center; gap: 0.45rem;
    font-size: 0.95rem; font-weight: 660; color: var(--vn-text); letter-spacing: -0.01em;
  }
  .vn-card-title .badge {
    font-size: 0.66rem; font-weight: 700; padding: 0.1rem 0.36rem; border-radius: 6px;
    background: var(--vn-accent-soft); color: #4338ca; letter-spacing: 0.02em;
  }
  .vn-meta { font-size: 0.73rem; color: var(--vn-faint); }
  .vn-meta strong { color: #5b6478; font-weight: 600; }

  /* Transcript --------------------------------------------------------- */
  .vn-legend { display: flex; gap: 0.35rem; flex-wrap: wrap; margin: 0.15rem 0 0.55rem; }
  .vn-chip {
    font-size: 0.71rem; padding: 0.16rem 0.5rem; border-radius: 999px;
    border: 1px solid currentColor; background: #fff; font-weight: 600;
  }
  .vn-chip span { opacity: 0.6; font-weight: 500; }
  .vn-tlist { margin-top: 0.15rem; }
  .vn-trow {
    display: grid; grid-template-columns: 32px 1fr; gap: 0.65rem;
    padding: 0.5rem 0.55rem; border-radius: 10px;
  }
  .vn-trow:hover { background: #fafbff; }
  .vn-avatar {
    width: 30px; height: 30px; border-radius: 9px; display: grid; place-items: center;
    font-size: 0.66rem; font-weight: 700; letter-spacing: 0.02em;
  }
  .vn-thead { display: flex; align-items: baseline; gap: 0.5rem; margin-bottom: 0.08rem; }
  .vn-name { font-size: 0.75rem; font-weight: 660; }
  .vn-ts { font-size: 0.69rem; color: var(--vn-faint); font-variant-numeric: tabular-nums; }
  .vn-tt { font-size: 0.885rem; line-height: 1.55; color: var(--vn-body); }
  .vn-divider { height: 1px; background: #f0f2f7; margin: 0.55rem 0; }

  /* Notes -------------------------------------------------------------- */
  .vn-note-title { font-size: 1.04rem; font-weight: 700; letter-spacing: -0.015em; color: var(--vn-text); }
  .vn-note-meta { font-size: 0.71rem; color: var(--vn-faint); margin: 0.1rem 0 0.6rem; }
  .vn-block { margin-bottom: 0.85rem; }
  .vn-block-label {
    font-size: 0.68rem; text-transform: uppercase; letter-spacing: 0.07em;
    font-weight: 700; color: #8b91a7; margin-bottom: 0.3rem;
  }
  .vn-block ul { margin: 0; padding-left: 1.05rem; }
  .vn-block li { font-size: 0.875rem; line-height: 1.55; color: var(--vn-body); margin-bottom: 0.18rem; }
  .vn-block p { font-size: 0.885rem; line-height: 1.6; color: var(--vn-body); margin: 0; }
  .vn-faint-line { font-size: 0.83rem; color: var(--vn-faint); font-style: italic; }
  .vn-action {
    display: flex; gap: 0.55rem; align-items: flex-start;
    padding: 0.5rem 0.6rem; border: 1px solid #eef0f7; border-radius: 10px;
    background: #fbfcff; margin-bottom: 0.35rem;
  }
  .vn-action .box {
    width: 15px; height: 15px; border-radius: 4px; border: 1.5px solid #c9cee2;
    margin-top: 2px; flex: 0 0 auto;
  }
  .vn-action .task { font-size: 0.865rem; line-height: 1.45; color: var(--vn-body); }
  .vn-tags { display: flex; gap: 0.25rem; margin-top: 0.25rem; flex-wrap: wrap; }
  .vn-tag {
    font-size: 0.66rem; padding: 0.07rem 0.38rem; border-radius: 5px;
    background: var(--vn-accent-soft); color: #4338ca; font-weight: 600;
  }
  .vn-tag.due { background: #fef3c7; color: #92400e; }

  /* Empty states ------------------------------------------------------- */
  .vn-empty { text-align: center; padding: 1.5rem 0.6rem 1.2rem; }
  .vn-empty .icon {
    width: 42px; height: 42px; border-radius: 12px; background: #f1f3fa;
    display: grid; place-items: center; margin: 0 auto 0.65rem; color: #9aa1b4;
  }
  .vn-empty .title { font-size: 0.9rem; font-weight: 620; color: #4b5568; margin-bottom: 0.2rem; }
  .vn-empty .sub { font-size: 0.79rem; color: var(--vn-faint); line-height: 1.5; }
  .vn-feature-strip { display: flex; gap: 0.4rem; justify-content: center; flex-wrap: wrap; margin-top: 0.75rem; }
  .vn-feature {
    font-size: 0.7rem; font-weight: 600; color: #6b7387; background: #fff;
    border: 1px solid var(--vn-border); border-radius: 999px; padding: 0.2rem 0.55rem;
  }

  /* Widgets ------------------------------------------------------------ */
  .stButton > button, .stDownloadButton > button {
    border-radius: 10px; font-weight: 600; border: 1px solid var(--vn-border-strong);
    transition: background 0.15s ease, border-color 0.15s ease, color 0.15s ease;
  }
  .stButton > button:hover, .stDownloadButton > button:hover {
    border-color: #c9cdfa; color: var(--vn-accent-strong); background: #f8f9ff;
  }
  [data-testid="stBaseButton-primary"] {
    background: var(--vn-accent); border-color: var(--vn-accent); color: #fff;
    box-shadow: 0 8px 18px -12px rgba(79, 70, 229, 0.95);
  }
  [data-testid="stBaseButton-primary"]:hover {
    background: var(--vn-accent-strong); border-color: var(--vn-accent-strong); color: #fff;
  }
  [data-testid="stAudioInput"] { max-width: 560px; }
  [data-testid="stFileUploaderDropzone"] {
    border-radius: 12px; border: 1px dashed #d6dae8; background: #fbfcff;
  }
  [data-testid="stPopover"] button { border-radius: 10px; font-weight: 600; }
  [data-testid="stPopoverBody"] { padding: 0.35rem 0.15rem 0.1rem; }
  [data-testid="stExpander"] details {
    border: 1px solid var(--vn-border); border-radius: 12px; background: #fff;
  }
  [data-testid="stExpander"] summary { font-size: 0.83rem; font-weight: 600; color: #5b6478; }
  div[data-baseweb="select"] > div { border-radius: 10px; }
  .stTextInput input, .stTextArea textarea { border-radius: 10px; font-size: 0.88rem; }

  /* Footer ------------------------------------------------------------- */
  .vn-footer {
    margin-top: 1.8rem; padding-top: 0.85rem; border-top: 1px solid var(--vn-border);
    display: flex; justify-content: space-between; gap: 1rem; flex-wrap: wrap;
    font-size: 0.72rem; color: var(--vn-faint);
  }
  .vn-footer strong { color: #6b7387; font-weight: 650; }

  @media (max-width: 920px) {
    .block-container { padding: 1.1rem 1rem 2.2rem; }
    .vn-trow { grid-template-columns: 28px 1fr; gap: 0.5rem; }
    .vn-tagline { display: none; }
  }
</style>
        """,
        unsafe_allow_html=True,
    )
