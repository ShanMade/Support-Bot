"""Thin wrapper around the Google Gen AI SDK (``google-genai``).

Only this module imports ``google.genai``. It handles:
* client creation with a request timeout,
* sending an audio clip inline (audio is compressed first so it always fits),
* plain text generation for the note writer,
* model discovery for the UI,
* mapping SDK exceptions to user-facing :class:`~services.errors.ProviderError`.
"""

from __future__ import annotations

import time
from functools import lru_cache

from .audio import GEMINI_INLINE_LIMIT_BYTES, AudioPayload, prepare_for_provider
from .errors import ProviderError

# Model families that are not "chat" models and must not be offered in the picker.
_NON_CHAT_HINTS = (
    "embedding", "embed", "image", "imagen", "veo", "tts", "audio", "live",
    "gemma", "aqa", "learnlm",
)


@lru_cache(maxsize=4)
def get_client(api_key: str, timeout_s: int):
    from google import genai
    from google.genai import types

    return genai.Client(
        api_key=api_key,
        http_options=types.HttpOptions(timeout=int(timeout_s) * 1000),
    )


def _friendly_google_error(exc: Exception) -> ProviderError:
    code = getattr(exc, "code", None)
    message = str(getattr(exc, "message", "") or exc)
    if code == 400:
        hint = "Check the selected model name and that the audio format is supported."
    elif code in (401, 403):
        hint = "The Gemini API key is invalid or lacks access. Create a new key at https://aistudio.google.com/apikey."
    elif code == 404:
        hint = "The selected Gemini model is not available for this key. Pick another model in the sidebar."
    elif code == 429:
        hint = "Gemini rate limit reached. Wait a minute and try again, or switch to Groq Whisper for transcription."
    elif code in (500, 502, 503, 504):
        hint = "Gemini is temporarily unavailable. Try again in a few moments."
    else:
        hint = "Check your connection and Gemini API key, then retry."
    return ProviderError(f"Gemini request failed: {message}", hint=hint)


def _with_retry(call, attempts: int = 2, delay: float = 2.0):
    last_error: Exception | None = None
    for attempt in range(attempts):
        try:
            return call()
        except Exception as exc:  # noqa: BLE001 - SDK raises many subclasses
            last_error = exc
            retryable = getattr(exc, "code", None) in (429, 500, 502, 503, 504)
            if not retryable or attempt == attempts - 1:
                break
            time.sleep(delay * (attempt + 1))
    assert last_error is not None
    raise _friendly_google_error(last_error)


def _config(system_instruction: str | None, temperature: float, json_mode: bool, timeout_s: int):
    from google.genai import types

    kwargs: dict = {"temperature": temperature, "http_options": {"timeout": timeout_s * 1000}}
    if system_instruction:
        kwargs["system_instruction"] = system_instruction
    if json_mode:
        # Plain JSON MIME type works on every Gemini model; the schema itself is
        # described in the prompt and validated by our own parser.
        kwargs["response_mime_type"] = "application/json"
    return types.GenerateContentConfig(**kwargs)


def generate_from_audio(
    api_key: str,
    model: str,
    audio: AudioPayload,
    prompt: str,
    *,
    system_instruction: str | None = None,
    temperature: float = 0.1,
    timeout_s: int = 180,
    json_mode: bool = True,
) -> str:
    """Send one audio clip plus a prompt and return the model's text response."""
    from google.genai import types

    data, mime, _ = prepare_for_provider(audio, "gemini")
    if len(data) > GEMINI_INLINE_LIMIT_BYTES:  # pragma: no cover - guarded upstream
        raise ProviderError("The audio is too large to send to Gemini in one request.")

    client = get_client(api_key, timeout_s)
    part = types.Part.from_bytes(data=data, mime_type=mime)
    contents = [prompt, part]

    def call():
        return client.models.generate_content(
            model=model,
            contents=contents,
            config=_config(system_instruction, temperature, json_mode, timeout_s),
        )

    response = _with_retry(call)
    text = getattr(response, "text", None)
    if not text:
        finish = ""
        try:
            finish = response.candidates[0].finish_reason
        except Exception:
            pass
        raise ProviderError(
            "Gemini returned an empty response.",
            hint=f"Finish reason: {finish or 'unknown'}. Try a shorter clip or another model.",
        )
    return text


def generate_text(
    api_key: str,
    model: str,
    prompt: str,
    *,
    system_instruction: str | None = None,
    temperature: float = 0.2,
    timeout_s: int = 180,
    json_mode: bool = True,
) -> str:
    """Plain text generation (used for the note writer)."""
    client = get_client(api_key, timeout_s)

    def call():
        return client.models.generate_content(
            model=model,
            contents=prompt,
            config=_config(system_instruction, temperature, json_mode, timeout_s),
        )

    response = _with_retry(call)
    text = getattr(response, "text", None)
    if not text:
        raise ProviderError("Gemini returned an empty response.", hint="Try generating the notes again.")
    return text


def list_chat_models(api_key: str, timeout_s: int = 30) -> list[str]:
    """Return usable model ids for the sidebar picker (empty list on failure)."""
    try:
        client = get_client(api_key, timeout_s)
        models: list[str] = []
        for item in client.models.list():
            name = str(getattr(item, "name", "") or "")
            if not name.startswith("models/"):
                continue
            model_id = name.split("models/", 1)[1]
            actions = getattr(item, "supported_actions", None) or getattr(item, "supported_generation_methods", None) or []
            if actions and "generateContent" not in actions:
                continue
            lowered = model_id.lower()
            if any(hint in lowered for hint in _NON_CHAT_HINTS):
                continue
            models.append(model_id)
        return sorted(set(models))
    except Exception:
        return []
