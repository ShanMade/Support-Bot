"""Backend configuration for VoiceNote AI.

This is the one file to edit if you prefer keeping runtime settings in the codebase
instead of a ``.env`` file or Streamlit secrets.

Resolution order for every setting (first non-empty wins):
    1. environment variables / .env
    2. Streamlit secrets (Secrets editor on Streamlit Community Cloud)
    3. the constants below

Paste your own keys between the quotes to run everything from code. Anything left
empty falls back to the defaults in ``services/config.py``.
"""

from __future__ import annotations

# --- API keys ---------------------------------------------------------------
GEMINI_API_KEY = ""          # https://aistudio.google.com/apikey
GROQ_API_KEY = ""            # https://console.groq.com/keys

# --- Models -----------------------------------------------------------------
GEMINI_MODEL = ""            # e.g. "gemini-2.5-flash"; empty = built-in default
GROQ_MODEL = ""              # "whisper-large-v3-turbo" or "whisper-large-v3"

# --- Behaviour --------------------------------------------------------------
TRANSCRIPTION_ENGINE = ""    # "gemini" or "groq"; empty = "gemini"
DIARIZATION = ""             # "auto" (speaker labels) or "off"
LANGUAGE = ""                # "auto" or an ISO-639-1 code such as "en"

# --- Limits -----------------------------------------------------------------
MAX_UPLOAD_MB = ""           # empty = 200
MAX_AUDIO_SECONDS = ""       # empty = 3600
STT_TIMEOUT = ""             # empty = 120
LLM_TIMEOUT = ""             # empty = 180
