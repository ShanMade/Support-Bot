"""Configuration loading.

Precedence (highest first):
1. Keys typed into the sidebar for the current browser session (never written to disk).
2. ``.env`` file / real environment variables (local development).
3. Streamlit secrets (``.streamlit/secrets.toml`` locally, the Secrets editor on
   Streamlit Community Cloud).

Secret values are never logged and never shown in the UI - only whether a value exists.
"""

from __future__ import annotations

import os
from dataclasses import dataclass, replace
from pathlib import Path

from dotenv import load_dotenv

from .errors import MissingKeyError

ENV_FILE = Path(__file__).resolve().parent.parent / ".env"
_ENV_LOADED = False

GROQ_MODELS = ["whisper-large-v3-turbo", "whisper-large-v3"]
TRANSCRIPTION_ENGINES = {
    "gemini": "Gemini (transcript + speakers)",
    "groq": "Groq Whisper (transcript; speakers via Gemini)",
}
DIARIZATION_MODES = {
    "auto": "Automatic (recommended)",
    "off": "Off (single speaker)",
}

DEFAULT_GEMINI_MODEL = "gemini-2.5-flash"
DEFAULT_GROQ_MODEL = "whisper-large-v3-turbo"


def load_env() -> None:
    """Load ``.env`` once per process. Safe when the file is absent."""
    global _ENV_LOADED
    if not _ENV_LOADED:
        if ENV_FILE.exists():
            load_dotenv(ENV_FILE, override=False)
        load_dotenv(override=False)  # also picks up a .env in the working directory
        _ENV_LOADED = True


def _streamlit_secret(name: str) -> str | None:
    """Read a secret from Streamlit, tolerating the "no secrets file" case."""
    try:
        import streamlit as st

        secrets = st.secrets  # may raise StreamlitSecretNotFoundError
    except Exception:
        return None
    for container in ("keys", "api", "general"):
        try:
            section = secrets.get(container)
            if section and name in section:
                return str(section[name]).strip() or None
        except Exception:
            continue
    try:
        if name in secrets:
            return str(secrets[name]).strip() or None
    except Exception:
        pass
    return None


def get_setting(name: str, default: str | None = None) -> str | None:
    """Environment first, then Streamlit secrets."""
    load_env()
    value = os.environ.get(name)
    if value is None or str(value).strip() == "":
        value = _streamlit_secret(name)
    if value is None or str(value).strip() == "":
        return default
    return str(value).strip()


def _as_int(value: str | None, default: int) -> int:
    try:
        return int(str(value))
    except (TypeError, ValueError):
        return default


@dataclass
class Settings:
    """Everything the pipeline needs to talk to a provider."""

    groq_api_key: str = ""
    gemini_api_key: str = ""
    groq_model: str = DEFAULT_GROQ_MODEL
    gemini_model: str = DEFAULT_GEMINI_MODEL
    transcription_engine: str = "gemini"      # "gemini" | "groq"
    diarization: str = "auto"                  # "auto" | "off"
    language: str = "auto"                     # "auto" or ISO-639-1 code
    max_upload_mb: int = 200
    max_audio_seconds: int = 3600
    stt_timeout: int = 120                     # seconds, per STT request
    llm_timeout: int = 180                     # seconds, per LLM request

    # ----- construction -------------------------------------------------
    @classmethod
    def load(cls, overrides: dict[str, str] | None = None) -> Settings:
        load_env()
        overrides = {k: v for k, v in (overrides or {}).items() if v}
        gemini_key = overrides.get("GEMINI_API_KEY") or get_setting("GEMINI_API_KEY") \
            or get_setting("GOOGLE_API_KEY") or ""
        groq_key = overrides.get("GROQ_API_KEY") or get_setting("GROQ_API_KEY") or ""

        engine = (get_setting("TRANSCRIPTION_ENGINE", "gemini") or "gemini").lower()
        if engine not in TRANSCRIPTION_ENGINES:
            engine = "gemini"
        diarization = (get_setting("DIARIZATION", "auto") or "auto").lower()
        if diarization not in DIARIZATION_MODES:
            diarization = "auto"

        groq_model = get_setting("GROQ_MODEL", DEFAULT_GROQ_MODEL) or DEFAULT_GROQ_MODEL
        if groq_model not in GROQ_MODELS:
            groq_model = DEFAULT_GROQ_MODEL

        return cls(
            groq_api_key=groq_key.strip(),
            gemini_api_key=gemini_key.strip(),
            groq_model=groq_model,
            gemini_model=get_setting("GEMINI_MODEL", DEFAULT_GEMINI_MODEL) or DEFAULT_GEMINI_MODEL,
            transcription_engine=engine,
            diarization=diarization,
            language=(get_setting("LANGUAGE", "auto") or "auto").lower(),
            max_upload_mb=_as_int(get_setting("MAX_UPLOAD_MB"), 200),
            max_audio_seconds=_as_int(get_setting("MAX_AUDIO_SECONDS"), 3600),
            stt_timeout=_as_int(get_setting("STT_TIMEOUT"), 120),
            llm_timeout=_as_int(get_setting("LLM_TIMEOUT"), 180),
        )

    # ----- helpers ------------------------------------------------------
    def with_changes(self, **kwargs: object) -> Settings:
        return replace(self, **kwargs)  # type: ignore[arg-type]

    @property
    def has_groq(self) -> bool:
        return bool(self.groq_api_key)

    @property
    def has_gemini(self) -> bool:
        return bool(self.gemini_api_key)

    def require_gemini(self) -> str:
        if not self.gemini_api_key:
            raise MissingKeyError(
                "No Google Gemini API key is configured.",
                hint=(
                    "Add GEMINI_API_KEY to your .env file (local) or to the app secrets "
                    "(Streamlit Cloud), or paste a key in the sidebar. Get one at "
                    "https://aistudio.google.com/apikey - the free tier is enough for a demo."
                ),
            )
        return self.gemini_api_key

    def require_groq(self) -> str:
        if not self.groq_api_key:
            raise MissingKeyError(
                "No Groq API key is configured.",
                hint=(
                    "Add GROQ_API_KEY to your .env file (local) or to the app secrets "
                    "(Streamlit Cloud), or paste a key in the sidebar. Get one at "
                    "https://console.groq.com/keys - a free account is enough for a demo."
                ),
            )
        return self.groq_api_key

    @property
    def effective_engine(self) -> str:
        """Engine actually used, downgraded if its key is missing."""
        if self.transcription_engine == "groq" and not self.has_groq and self.has_gemini:
            return "gemini"
        if self.transcription_engine == "gemini" and not self.has_gemini and self.has_groq:
            return "groq"
        return self.transcription_engine

    def engine_signature(self) -> str:
        """Changes whenever a different transcription result would be produced."""
        return "|".join(
            [
                self.effective_engine,
                self.groq_model,
                self.gemini_model,
                self.language,
                self.diarization,
            ]
        )


@dataclass
class Integration:
    name: str
    configured: bool
    detail: str


def integration_status(settings: Settings) -> list[Integration]:
    """Describe configured integrations without ever exposing a secret."""
    import shutil

    from .audio import ffmpeg_path

    gemini_detail = f"model: {settings.gemini_model}" if settings.has_gemini else "no API key"
    groq_detail = f"model: {settings.groq_model}" if settings.has_groq else "no API key"
    try:
        ff = ffmpeg_path()
    except Exception:  # pragma: no cover - defensive
        ff = shutil.which("ffmpeg")
    return [
        Integration("Google Gemini", settings.has_gemini, gemini_detail),
        Integration("Groq Whisper", settings.has_groq, groq_detail),
        Integration("Audio converter (ffmpeg)", bool(ff), "bundled" if ff else "not available"),
        Integration(
            "Diarization",
            settings.diarization != "off" and settings.has_gemini,
            "Gemini audio (post-recording)" if settings.has_gemini else "needs Gemini key",
        ),
    ]
