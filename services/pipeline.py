"""End-to-end audio -> transcript pipeline (no UI code)."""

from __future__ import annotations

from collections.abc import Callable

from .audio import AudioPayload, probe_duration, validate_audio
from .errors import AudioError
from .models import Transcript
from .transcription import transcribe

ProgressFn = Callable[[str, str], None]


def build_payload(
    filename: str,
    data: bytes,
    *,
    max_mb: int = 200,
    max_seconds: int = 3600,
) -> AudioPayload:
    """Validate raw audio and return a payload with the measured duration."""
    mime = validate_audio(filename, data, max_mb=max_mb)
    duration = probe_duration(data, mime, suffix=_suffix_for(filename, mime))
    if duration and duration > max_seconds:
        raise AudioError(
            f"This recording is {duration / 60:.0f} minutes long; the limit is {max_seconds // 60} minutes.",
            hint="Record or upload a shorter clip, or raise MAX_AUDIO_SECONDS in your configuration.",
        )
    return AudioPayload(data=data, mime=mime, filename=filename, duration=duration)


def _suffix_for(filename: str, mime: str) -> str:
    dot = filename.rfind(".")
    if dot != -1:
        return filename[dot:].lower()
    return ".wav" if "wav" in mime else ".bin"


def process_audio(
    payload: AudioPayload,
    settings,
    *,
    progress: ProgressFn | None = None,
) -> Transcript:
    """Transcribe and (when configured) diarize a validated audio payload."""
    return transcribe(payload, settings, progress=progress)


def transcription_signature(payload: AudioPayload, settings) -> str:
    """Fingerprint used to avoid repeating expensive provider calls on reruns."""
    return f"{payload.sha256}:{settings.engine_signature()}"
