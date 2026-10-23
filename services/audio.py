"""Audio validation, duration probing and format conversion.

Recordings are always handled in memory; temporary files are created only inside a
short-lived temp directory and are deleted immediately. Nothing is written to the
repository and nothing is kept after processing.
"""

from __future__ import annotations

import hashlib
import io
import re
import shutil
import subprocess
import tempfile
import wave
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path

from .errors import AudioError

# Extensions accepted from the microphone widget and the file uploader.
EXTENSION_MIME = {
    ".wav": "audio/wav",
    ".mp3": "audio/mp3",
    ".m4a": "audio/m4a",
    ".mp4": "audio/mpeg",
    ".mpeg": "audio/mpeg",
    ".mpga": "audio/mpeg",
    ".webm": "audio/webm",
    ".ogg": "audio/ogg",
    ".oga": "audio/ogg",
    ".opus": "audio/opus",
    ".flac": "audio/flac",
    ".aac": "audio/aac",
    ".aiff": "audio/aiff",
    ".aif": "audio/aiff",
}

# Gemini's documented supported audio MIME types.
GEMINI_MIME = {
    "audio/wav", "audio/mp3", "audio/aiff", "audio/aac", "audio/ogg",
    "audio/flac", "audio/mpeg", "audio/m4a", "audio/opus", "audio/webm",
    "audio/x-wav", "audio/x-m4a",
}

# Groq accepts: flac, mp3, mp4, mpeg, mpga, m4a, ogg, wav, webm.
GROQ_MIME = {
    "audio/flac", "audio/mp3", "audio/mpeg", "audio/m4a", "audio/mp4",
    "audio/ogg", "audio/wav", "audio/x-wav", "audio/webm",
}

# Keep the request well below the providers' hard caps.
GEMINI_INLINE_LIMIT_BYTES = 15 * 1024 * 1024   # documented inline cap is 20 MB total
GROQ_LIMIT_BYTES = 24 * 1024 * 1024            # documented free-tier cap is 25 MB


@lru_cache(maxsize=1)
def ffmpeg_path() -> str | None:
    """Locate a usable ffmpeg binary (bundled first, then PATH)."""
    try:
        import imageio_ffmpeg

        exe = imageio_ffmpeg.get_ffmpeg_exe()
        if exe and Path(exe).exists():
            return exe
    except Exception:
        pass
    return shutil.which("ffmpeg")


@dataclass
class AudioPayload:
    """An in-memory audio clip plus the metadata the UI needs."""

    data: bytes
    mime: str
    filename: str
    duration: float = 0.0

    @property
    def size_mb(self) -> float:
        return len(self.data) / (1024 * 1024)

    @property
    def sha256(self) -> str:
        return hashlib.sha256(self.data).hexdigest()

    def to_state(self) -> dict:
        return {
            "data": self.data,
            "mime": self.mime,
            "filename": self.filename,
            "duration": self.duration,
        }

    @classmethod
    def from_state(cls, state: dict) -> AudioPayload | None:
        if not state or not state.get("data"):
            return None
        return cls(
            data=state["data"],
            mime=state.get("mime", "audio/wav"),
            filename=state.get("filename", "recording.wav"),
            duration=float(state.get("duration") or 0.0),
        )


def _suffix(filename: str) -> str:
    return Path(filename or "").suffix.lower()


def sniff_mime(filename: str, data: bytes) -> str:
    """Prefer magic bytes, then the file extension."""
    head = data[:16]
    if head.startswith(b"RIFF") and head[8:12] == b"WAVE":
        return "audio/wav"
    if head.startswith(b"fLaC"):
        return "audio/flac"
    if head.startswith(b"OggS"):
        return "audio/ogg"
    if head.startswith(b"ID3") or head[:2] in (b"\xff\xfb", b"\xff\xf3", b"\xff\xf2"):
        return "audio/mp3"
    if head.startswith(b"\x1aE\xdf\xa3"):
        return "audio/webm"
    if head[4:8] == b"ftyp":
        return "audio/m4a"
    return EXTENSION_MIME.get(_suffix(filename), "audio/wav")


def validate_audio(filename: str, data: bytes, max_mb: int = 200) -> str:
    """Raise :class:`AudioError` when the clip cannot be processed. Returns the MIME type."""
    if not data:
        raise AudioError("The recording is empty. Record again or upload a different file.")
    suffix = _suffix(filename)
    if suffix and suffix not in EXTENSION_MIME:
        raise AudioError(
            f"Unsupported file type '{suffix}'.",
            hint=f"Supported formats: {', '.join(sorted(EXTENSION_MIME))}.",
        )
    size_mb = len(data) / (1024 * 1024)
    if size_mb > max_mb:
        raise AudioError(
            f"The audio file is {size_mb:.1f} MB, above the {max_mb} MB limit.",
            hint="Trim the clip, or raise MAX_UPLOAD_MB in your configuration.",
        )
    return sniff_mime(filename, data)


def _duration_from_wav(data: bytes) -> float | None:
    try:
        with wave.open(io.BytesIO(data), "rb") as handle:
            frames = handle.getnframes()
            rate = handle.getframerate() or 1
            return frames / float(rate)
    except Exception:
        return None


_DURATION_RE = re.compile(r"Duration:\s*(\d+):(\d+):(\d+(?:\.\d+)?)")


def probe_duration(data: bytes, mime: str, suffix: str = ".wav") -> float:
    """Duration in seconds. Returns 0.0 when it cannot be determined."""
    if mime in ("audio/wav", "audio/x-wav"):
        wav_duration = _duration_from_wav(data)
        if wav_duration is not None:
            return wav_duration

    ffmpeg = ffmpeg_path()
    if not ffmpeg:
        return 0.0
    with tempfile.TemporaryDirectory(prefix="vnai-") as tmp:
        src = Path(tmp) / f"input{suffix or '.bin'}"
        src.write_bytes(data)
        try:
            proc = subprocess.run(
                [ffmpeg, "-hide_banner", "-i", str(src)],
                capture_output=True, text=True, timeout=60, check=False,
            )
        except (OSError, subprocess.SubprocessError):
            return 0.0
        match = _DURATION_RE.search(proc.stderr or "")
        if not match:
            return 0.0
        hours, minutes, seconds = match.groups()
        return int(hours) * 3600 + int(minutes) * 60 + float(seconds)


def transcode_mp3(data: bytes, mime: str, *, bitrate: str = "64k", sample_rate: int = 16000) -> bytes:
    """Convert any supported clip to mono 16 kHz MP3, in memory."""
    ffmpeg = ffmpeg_path()
    if not ffmpeg:
        raise AudioError(
            "This audio needs conversion, but ffmpeg is not available.",
            hint="Install the dependencies from requirements.txt (imageio-ffmpeg ships a binary).",
        )
    suffix = _suffix_from_mime(mime)
    with tempfile.TemporaryDirectory(prefix="vnai-") as tmp:
        src = Path(tmp) / f"input{suffix}"
        dst = Path(tmp) / "output.mp3"
        src.write_bytes(data)
        cmd = [
            ffmpeg, "-hide_banner", "-loglevel", "error", "-y",
            "-i", str(src), "-vn", "-ac", "1", "-ar", str(sample_rate),
            "-b:a", bitrate, str(dst),
        ]
        try:
            proc = subprocess.run(cmd, capture_output=True, text=True, timeout=600, check=False)
        except (OSError, subprocess.SubprocessError) as exc:
            raise AudioError(f"Audio conversion failed: {exc}") from exc
        if proc.returncode != 0 or not dst.exists():
            detail = (proc.stderr or "").strip().splitlines()
            raise AudioError(
                "This audio file could not be decoded.",
                hint=detail[-1] if detail else "Try a WAV, MP3 or M4A file.",
            )
        return dst.read_bytes()


def _suffix_from_mime(mime: str) -> str:
    for suffix, candidate in EXTENSION_MIME.items():
        if candidate == mime:
            return suffix
    return ".bin"


def prepare_for_provider(payload: AudioPayload, provider: str) -> tuple[bytes, str, str]:
    """Return ``(data, mime, filename)`` that fits the provider's upload rules.

    Small clips are sent untouched (best quality for diarization). Larger clips are
    compressed to mono 16 kHz MP3 so the request stays inside the API limits.
    """
    limit = GEMINI_INLINE_LIMIT_BYTES if provider == "gemini" else GROQ_LIMIT_BYTES
    accepted = GEMINI_MIME if provider == "gemini" else GROQ_MIME
    mime = payload.mime
    data = payload.data
    filename = payload.filename

    if len(data) <= limit and mime in accepted:
        return data, mime, filename

    source_mime = mime
    for bitrate in ("64k", "32k", "24k", "16k"):
        data = transcode_mp3(payload.data, source_mime, bitrate=bitrate)
        if len(data) <= limit:
            return data, "audio/mp3", Path(filename).stem + ".mp3"
    raise AudioError(
        f"The audio is still {len(data) / (1024 * 1024):.1f} MB after compression.",
        hint="Split the recording into shorter parts and process them separately.",
    )


def human_duration(seconds: float) -> str:
    seconds = max(0, int(round(seconds or 0)))
    minutes, secs = divmod(seconds, 60)
    if minutes >= 60:
        hours, minutes = divmod(minutes, 60)
        return f"{hours}h {minutes}m {secs}s"
    if minutes:
        return f"{minutes}m {secs}s"
    return f"{secs}s"
