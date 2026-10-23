"""Transcript rendering: speaker legend, filter and readable rows."""

from __future__ import annotations

import html

import streamlit as st

from services.audio import human_duration
from services.models import Transcript, format_timestamp

from .styles import speaker_palette


def meta_html(transcript: Transcript) -> str:
    bits: list[str] = []
    speakers = transcript.speakers()
    if transcript.diarized and len(speakers) > 1:
        bits.append(f"<b>{len(speakers)} speakers</b>")
    if transcript.duration:
        bits.append(human_duration(transcript.duration))
    if transcript.language:
        bits.append(html.escape(transcript.language.upper()))
    bits.append(f"{transcript.word_count()} words")
    return " &middot; ".join(bits)


def legend(transcript: Transcript) -> None:
    speakers = transcript.speakers()
    if not speakers:
        return
    chips = []
    for speaker in speakers:
        color, _tint = speaker_palette(speaker)
        first = next((s for s in transcript.segments if s.speaker == speaker), None)
        start = format_timestamp(first.start) if first else "--:--"
        chips.append(
            f'<span class="vn-chip" style="color:{color}">{html.escape(speaker)}'
            f" <span>&middot; {start}</span></span>"
        )
    st.markdown(f'<div class="vn-legend">{"".join(chips)}</div>', unsafe_allow_html=True)


def speaker_filter(speakers: list[str]) -> list[str]:
    """Optional filter, only shown when there is more than one speaker."""
    if len(speakers) < 2:
        return speakers
    selected = st.pills(
        "Filter by speaker",
        options=speakers,
        selection_mode="multi",
        default=speakers,
        label_visibility="collapsed",
    )
    return list(selected) if selected else speakers


def render_segments(transcript: Transcript, visible_speakers: list[str] | None = None) -> None:
    segments = transcript.grouped_segments()
    if visible_speakers is not None:
        segments = [
            segment
            for segment in segments
            if segment.speaker is None or segment.speaker in visible_speakers
        ]

    rows: list[str] = []
    for segment in segments:
        text = html.escape(segment.text).replace("\n", " ")
        if not text:
            continue
        color, _tint = speaker_palette(segment.speaker)
        speaker = segment.speaker or "Speaker"
        rows.append(
            '<div class="vn-trow">'
            '<div class="vn-tmeta">'
            f'<span class="vn-spk" style="color:{color}">{html.escape(speaker)}</span>'
            f'<span class="vn-ts">{format_timestamp(segment.start)}</span>'
            "</div>"
            f'<div class="vn-tt">{text}</div>'
            "</div>"
        )

    if not rows:
        st.markdown(
            '<div class="vn-empty">Nothing to show for this filter.</div>',
            unsafe_allow_html=True,
        )
        return

    st.markdown(f'<div class="vn-tlist">{"".join(rows)}</div>', unsafe_allow_html=True)
