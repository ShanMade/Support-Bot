"""Microphone and file-upload controls.

Streamlit's ``st.audio_input`` records in the browser and hands over one finished
WAV clip when recording stops, so the transcript arrives right after you stop
rather than word by word. The interface states that plainly.
"""

from __future__ import annotations

from dataclasses import dataclass

import streamlit as st

from services.audio import EXTENSION_MIME

UPLOAD_TYPES = sorted(suffix.lstrip(".") for suffix in EXTENSION_MIME)


@dataclass
class Capture:
    data: bytes
    filename: str
    source: str  # "microphone" | "upload"


def source_switch() -> str:
    """Small segmented control; returns the chosen source label."""
    return (
        st.segmented_control(
            "Audio source",
            options=["Record", "Upload"],
            default="Record",
            key="source_mode",
            label_visibility="collapsed",
            width="content",
        )
        or "Record"
    )


def render_input(mode: str, *, nonce: int, max_upload_mb: int) -> Capture | None:
    """Render the input widget for ``mode`` and return a fresh clip if provided."""
    capture: Capture | None = None

    if mode == "Upload":
        uploaded = st.file_uploader(
            "Drop an audio file",
            type=UPLOAD_TYPES,
            key=f"uploader_{nonce}",
            help=f"WAV, MP3, M4A, WebM, OGG, OPUS, FLAC or AAC - up to {max_upload_mb} MB.",
        )
        if uploaded is not None:
            capture = Capture(
                data=uploaded.getvalue(),
                filename=uploaded.name or "upload.wav",
                source="upload",
            )
        return capture

    # Centred recorder: the widget itself is compact, so give it a middle column.
    _, middle, _ = st.columns([1, 1.05, 1])
    with middle:
        audio = st.audio_input(
            "Start recording",
            sample_rate=16000,
            key=f"mic_{nonce}",
            help="Your browser asks for microphone permission the first time.",
            label_visibility="collapsed",
        )
    st.markdown(
        '<div class="vn-empty" style="text-align:center;padding-top:0.1rem">'
        "Tap the microphone, speak, then press stop &mdash; the clip is transcribed straight after."
        "</div>",
        unsafe_allow_html=True,
    )
    if audio is not None:
        capture = Capture(
            data=audio.getvalue(),
            filename=getattr(audio, "name", None) or "recording.wav",
            source="microphone",
        )
    return capture
