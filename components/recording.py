"""Microphone capture / audio upload widget.

Streamlit's ``st.audio_input`` records in the browser and uploads one WAV clip when
recording stops. That is why VoiceNote AI transcribes right after you stop rather
than word-by-word: the widget never exposes partial audio while the microphone is
open. The UI says so explicitly instead of pretending otherwise.
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
    """Render the input controls and return a newly provided clip (if any)."""
    mode = st.segmented_control(
        "Audio source",
        options=["Microphone", "Upload file"],
        default="Microphone",
        key="source_mode",
        label_visibility="collapsed",
    )
    capture: Capture | None = None

    if mode == "Upload file":
        uploaded = st.file_uploader(
            "Choose an audio file",
            type=UPLOAD_TYPES,
            key=f"uploader_{nonce}",
            help=f"Up to {max_upload_mb} MB. WAV, MP3, M4A, WebM, OGG, OPUS, FLAC or AAC.",
        )
        if uploaded is not None:
            capture = Capture(
                data=uploaded.getvalue(),
                filename=uploaded.name or "upload.wav",
                source="upload",
            )
    else:
        audio = st.audio_input(
            "Record a conversation",
            sample_rate=16000,
            key=f"mic_{nonce}",
            help="Your browser asks for microphone permission the first time.",
        )
        st.caption(
            "Click the microphone, speak, then press the stop button. Transcription starts "
            "the moment the clip is sent - this widget does not stream partial audio."
        )
        if audio is not None:
            capture = Capture(
                data=audio.getvalue(),
                filename=getattr(audio, "name", None) or "recording.wav",
                source="microphone",
            )

    return capture
