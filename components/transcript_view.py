"""Read-only transcript rendering."""

from __future__ import annotations

import html

import streamlit as st

from services.audio import human_duration
from services.models import Transcript, format_timestamp

from .styles import speaker_color


def legend(transcript: Transcript) -> None:
    speakers = transcript.speakers()
    if not speakers:
        return
    chips = []
    for speaker in speakers:
        color = speaker_color(speaker)
        first = next((s for s in transcript.segments if s.speaker == speaker), None)
        start = format_timestamp(first.start) if first else "--:--"
        chips.append(
            f'<span class="vn-chip" style="color:{color}">{html.escape(speaker)}'
            f' <span style="opacity:.65">&middot; from {start}</span></span>'
        )
    st.markdown(f'<div class="vn-legend">{"".join(chips)}</div>', unsafe_allow_html=True)


def meta_line(transcript: Transcript) -> str:
    speakers = transcript.speakers()
    bits = []
    if transcript.stt_provider:
        model = f" {transcript.stt_model}" if transcript.stt_model else ""
        bits.append(f"{transcript.stt_provider.capitalize()}{model}")
    if transcript.diarized:
        bits.append(f"{len(speakers)} speakers detected")
    else:
        bits.append("no speaker detection")
    if transcript.duration:
        bits.append(human_duration(transcript.duration))
    if transcript.language:
        bits.append(f"language: {transcript.language}")
    bits.append(f"{transcript.word_count()} words")
    return " &middot; ".join(html.escape(bit) for bit in bits)


def render_segments(transcript: Transcript, *, show_timestamps: bool = True) -> None:
    rows: list[str] = []
    for segment in transcript.grouped_segments():
        text = html.escape(segment.text).replace("\n", "<br>")
        if not text:
            continue
        speaker = segment.speaker or "Speaker"
        color = speaker_color(segment.speaker)
        time_html = (
            f'<span class="vn-time">{format_timestamp(segment.start)}</span>'
            if show_timestamps
            else ""
        )
        rows.append(
            f'<div class="vn-seg">'
            f'<div class="vn-seg-meta"><span class="vn-spk" style="color:{color}">'
            f"{html.escape(speaker)}</span>{time_html}</div>"
            f'<div class="vn-text">{text}</div>'
            f"</div>"
        )
    if not rows:
        st.markdown(
            '<div class="vn-empty">No speech detected in this recording.</div>',
            unsafe_allow_html=True,
        )
        return
    st.markdown(
        f'<div class="vn-transcript">{"".join(rows)}</div>',
        unsafe_allow_html=True,
    )
