"""Header, step indicator, status pills and footer."""

from __future__ import annotations

import html

import streamlit as st

from services.config import Integration

MIC_ICON = """<svg width="20" height="20" viewBox="0 0 24 24" fill="none"
  stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
  <path d="M12 2a3 3 0 0 0-3 3v7a3 3 0 0 0 6 0V5a3 3 0 0 0-3-3z"/>
  <path d="M19 10v2a7 7 0 0 1-14 0v-2"/><line x1="12" y1="19" x2="12" y2="22"/>
</svg>"""


def pill(text: str, state: str = "off") -> str:
    return f'<span class="vn-pill {state}"><span class="dot"></span>{html.escape(text)}</span>'


def header(integrations: list[Integration]) -> None:
    pills = []
    for item in integrations:
        if item.name.startswith("Diarization"):
            state = "ok" if item.configured else "off"
            pills.append(pill("Diarization on" if item.configured else "Diarization off", state))
        elif item.name.startswith(("Google", "Groq")):
            state = "ok" if item.configured else "warn"
            label = item.name if item.configured else f"{item.name}: no key"
            pills.append(pill(label, state))

    st.markdown(
        f"""
<div class="vn-header">
  <div class="vn-logo">{MIC_ICON}</div>
  <div>
    <div class="vn-title">VoiceNote AI</div>
    <div class="vn-sub">Record a conversation &middot; get a speaker-labelled transcript &middot; get structured notes</div>
  </div>
  <div class="vn-header-right">{''.join(pills)}</div>
</div>
        """,
        unsafe_allow_html=True,
    )


def step_bar(active: int) -> None:
    """Four-step progress hint. ``active`` is 0-4 (4 = all complete)."""
    labels = [("1", "Record"), ("2", "Transcribe &amp; identify speakers"),
              ("3", "Generate notes"), ("4", "Export")]
    chunks = []
    for index, (number, label) in enumerate(labels):
        if index < active:
            css = "done"
        elif index == active:
            css = "active"
        else:
            css = ""
        chunks.append(f'<span class="vn-step {css}"><strong>{number}</strong> {label}</span>')
    st.markdown(f'<div class="vn-steps">{"".join(chunks)}</div>', unsafe_allow_html=True)


def section(title: str, count: str | None = None) -> None:
    suffix = f'<span class="count">{html.escape(count)}</span>' if count else ""
    st.markdown(f'<div class="vn-section">{html.escape(title)} {suffix}</div>', unsafe_allow_html=True)


def footer() -> None:
    st.markdown(
        """
<div class="vn-footer">
  <span><strong>VoiceNote AI</strong> &middot; GenAI course demonstration project.</span>
  <span>Speakers are anonymous voice clusters, not identities. Audio stays in this session only.</span>
</div>
        """,
        unsafe_allow_html=True,
    )
