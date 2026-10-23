"""Page furniture: brand, status, section labels, steps and footer."""

from __future__ import annotations

import html

import streamlit as st

MARK = """<svg width="17" height="17" viewBox="0 0 24 24" fill="none" stroke="currentColor"
  stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
  <path d="M12 3a2.6 2.6 0 0 0-2.6 2.6v6a2.6 2.6 0 0 0 5.2 0v-6A2.6 2.6 0 0 0 12 3z"/>
  <path d="M18.5 10.6v1a6.5 6.5 0 0 1-13 0v-1"/><line x1="12" y1="18.1" x2="12" y2="21"/>
</svg>"""


def brand() -> None:
    st.markdown(
        f"""
<div class="vn-brand">
  <div class="vn-mark">{MARK}</div>
  <div>
    <div class="vn-wordmark">VoiceNote AI</div>
    <div class="vn-tagline">Speech &rarr; transcript &rarr; notes</div>
  </div>
</div>
        """,
        unsafe_allow_html=True,
    )


def status(text: str, state: str = "ready") -> None:
    css = {"busy": "busy", "done": "done"}.get(state, "")
    st.markdown(
        f'<div class="vn-statusline"><span class="vn-dot {css}"></span>'
        f'<span class="vn-status-text">{html.escape(text)}</span></div>',
        unsafe_allow_html=True,
    )


def steps(active: int) -> None:
    """Slim progress line. ``active`` 0-3, earlier steps read as done."""
    labels = ["Capture", "Transcribe", "Notes", "Export"]
    parts: list[str] = []
    for index, label in enumerate(labels):
        css = "done" if index < active else ("active" if index == active else "")
        parts.append(f'<span class="s {css}">{label}</span>')
        if index < len(labels) - 1:
            parts.append('<span class="bar"></span>')
    st.markdown(f'<div class="vn-steps">{"".join(parts)}</div>', unsafe_allow_html=True)


def kicker(label: str, meta_html: str = "") -> None:
    """Section label with an optional right-hand metadata string."""
    meta = f'<span class="vn-section-meta">{meta_html}</span>' if meta_html else ""
    st.markdown(
        f'<div style="display:flex;align-items:baseline;justify-content:space-between;'
        f'gap:1rem;margin:0.1rem 0 0.5rem">'
        f'<span class="vn-kicker">{html.escape(label)}</span>{meta}</div>',
        unsafe_allow_html=True,
    )


def card_marker() -> None:
    """Invisible marker that lets CSS recognise a bordered card."""
    st.markdown('<span class="vn-cardsig"></span>', unsafe_allow_html=True)


def rule(space_top: str = "1.6rem") -> None:
    st.markdown(f'<div class="vn-rule" style="margin-top:{space_top}"></div>', unsafe_allow_html=True)


def footer() -> None:
    st.markdown(
        """
<div class="vn-footer">
  <span><b>VoiceNote AI</b> &middot; GenAI course demonstration</span>
  <span>Speakers are anonymous voice clusters, never identities.</span>
</div>
        """,
        unsafe_allow_html=True,
    )
