"""Static page furniture: brand, status chip, workflow steps, card headers, footer."""

from __future__ import annotations

import html

import streamlit as st

MIC_ICON = """<svg width="19" height="19" viewBox="0 0 24 24" fill="none" stroke="currentColor"
  stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
  <path d="M12 2a3 3 0 0 0-3 3v7a3 3 0 0 0 6 0V5a3 3 0 0 0-3-3z"/>
  <path d="M19 10v2a7 7 0 0 1-14 0v-2"/><line x1="12" y1="19" x2="12" y2="22"/>
</svg>"""

WAVE_ICON = """<svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor"
  stroke-width="1.8" stroke-linecap="round">
  <line x1="4" y1="10" x2="4" y2="14"/><line x1="8" y1="7" x2="8" y2="17"/>
  <line x1="12" y1="4" x2="12" y2="20"/><line x1="16" y1="8" x2="16" y2="16"/>
  <line x1="20" y1="11" x2="20" y2="13"/>
</svg>"""


def brand() -> None:
    st.markdown(
        f"""
<div class="vn-brand">
  <div class="vn-mark">{MIC_ICON}</div>
  <div>
    <div class="vn-name">VoiceNote AI</div>
    <div class="vn-tagline">Meetings recorded, transcribed and summarised</div>
  </div>
</div>
        """,
        unsafe_allow_html=True,
    )


def status_chip(label: str, state: str = "ready") -> None:
    css = {"busy": "busy", "done": "done"}.get(state, "")
    st.markdown(
        f'<div class="vn-status-wrap"><span class="vn-status {css}">'
        f'<span class="dot"></span>{html.escape(label)}</span></div>',
        unsafe_allow_html=True,
    )


def steps(active: int) -> None:
    """Workflow hint. ``active`` 0-3; earlier steps are shown as completed."""
    labels = [("Capture", 0), ("Transcribe", 1), ("Notes", 2), ("Export", 3)]
    chunks: list[str] = []
    for index, (label, _order) in enumerate(labels):
        css = "done" if index < active else ("active" if index == active else "")
        chunks.append(
            f'<span class="vn-step {css}"><span class="idx">{index + 1}</span>{label}</span>'
        )
        if index < len(labels) - 1:
            chunks.append('<span class="vn-sep"></span>')
    st.markdown(f'<div class="vn-steps">{"".join(chunks)}</div>', unsafe_allow_html=True)


def card_head(title: str, meta_html: str | None = None, badge: str | None = None) -> None:
    badge_html = f'<span class="badge">{html.escape(badge)}</span>' if badge else ""
    meta = f'<span class="vn-meta">{meta_html}</span>' if meta_html else ""
    st.markdown(
        f'<div class="vn-card-head"><div class="vn-card-title">{html.escape(title)}'
        f"{badge_html}</div>{meta}</div>",
        unsafe_allow_html=True,
    )


def footer() -> None:
    st.markdown(
        """
<div class="vn-footer">
  <span><strong>VoiceNote AI</strong> &middot; GenAI course demonstration</span>
  <span>Speakers are anonymous voice clusters, never identities.</span>
</div>
        """,
        unsafe_allow_html=True,
    )


SPARK_ICON = """<svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor"
  stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round">
  <path d="M12 3l1.9 5.1L19 10l-5.1 1.9L12 17l-1.9-5.1L5 10l5.1-1.9L12 3z"/>
  <path d="M18 15l.9 2.1L21 18l-2.1.9L18 21l-.9-2.1L15 18l2.1-.9L18 15z"/>
</svg>"""
