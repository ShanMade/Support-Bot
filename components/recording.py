"""Microphone capture / file upload controls.

Streamlit's ``st.audio_input`` records in the browser and hands over one finished WAV
clip when recording stops, so the transcript arrives right after you stop rather than
word by word. The UI states that plainly instead of imitating a live stream.
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


def render_capture(*, nonce: int, max_upload_mb: int) -> Capture | None:
    """Render the input controls and return whatever clip the user just provided."""
    switcher, _spacer = st.columns([1.6, 4.2])
    with switcher:
        mode = st.segmented_control(
            "Audio source",
            options=["Microphone", "Upload"],
            default="Microphone",
            key="source_mode",
            label_visibility="collapsed",
            width="stretch",
        )
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
    else:
        audio = st.audio_input(
            "Start recording",
            sample_rate=16000,
            key=f"mic_{nonce}",
            help="Your browser asks for microphone permission the first time.",
        )
        st.markdown(
            '<div class="vn-meta" style="margin-top:-0.35rem">'
            "Tap the microphone, speak, then press stop. The clip is transcribed "
            "immediately afterwards."
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
