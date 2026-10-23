"""Speech-to-text.

Two real providers are supported and both return genuine provider output:

* **Gemini** - one multimodal call returns the transcript *and* speaker labels
  (Gemini performs diarization while listening to the audio).
* **Groq Whisper** - fast Whisper transcription with segment timestamps. Whisper
  itself does not do diarization, so when it is selected we optionally run a
  second, audio-based Gemini diarization pass and align those speaker turns to the
  Whisper segments by timestamp overlap.

Neither path guesses speakers from word choice or alternates labels.
"""

from __future__ import annotations

from collections.abc import Callable
from typing import Any

from . import gemini
from .audio import AudioPayload, prepare_for_provider
from .errors import MissingKeyError, ProviderError
from .json_utils import parse_json_object
from .models import Segment, Transcript, canonicalize_speakers

ProgressFn = Callable[[str, str], None]


def _noop(_message: str, _state: str = "running") -> None:
    return


GEMINI_STT_SYSTEM = """You are a precise speech-to-text and speaker-diarization engine.

You receive one audio recording of a conversation and must return a JSON object:
{
  "language": "<ISO-639-1 code, e.g. en. Use an empty string if unknown>",
  "segments": [
    {"start": 0.0, "end": 4.6, "speaker": "Speaker 1", "text": "exact words"}
  ]
}

Rules:
1. Transcribe verbatim in the language that is spoken. Do not translate, summarise,
   correct grammar, or add commentary.
2. "start" and "end" are seconds from the beginning of the audio, as decimal numbers
   with one decimal place (for example 12.4). Segments must be chronological and
   non-overlapping.
3. Start a new segment whenever the speaker changes, and split very long monologues
   into pieces of at most about 30 seconds.
4. Detect distinct voices from the audio and label them consistently as
   "Speaker 1", "Speaker 2", ... in order of their first appearance. Never guess or
   state a real name, gender, age or identity; anonymous labels only.
5. If only one person speaks, label every segment "Speaker 1".
6. Mark unintelligible speech as [inaudible] instead of guessing.
7. If there is no speech at all, return {"language": "", "segments": []}.
8. Return JSON only - no markdown, no explanation."""


def check_transcription_ready(settings) -> None:
    """Raise a helpful error before doing any work when nothing is configured."""
    engine = settings.effective_engine
    if engine == "gemini":
        settings.require_gemini()
    elif engine == "groq":
        settings.require_groq()
    else:  # pragma: no cover - defensive
        raise MissingKeyError(
            "No transcription provider is configured.",
            hint="Add a GEMINI_API_KEY or a GROQ_API_KEY, then reload the app.",
        )


def transcribe(
    audio: AudioPayload,
    settings,
    *,
    progress: ProgressFn | None = None,
    allow_diarization: bool = True,
) -> Transcript:
    """Transcribe (and diarize) one audio clip."""
    progress = progress or _noop
    check_transcription_ready(settings)
    engine = settings.effective_engine

    if engine == "gemini":
        transcript = _gemini_transcribe(audio, settings, progress, allow_diarization)
    else:
        transcript = _groq_transcribe(audio, settings, progress)
        if allow_diarization and settings.diarization != "off" and settings.has_gemini:
            from .diarization import diarize_and_align

            progress("Identifying speakers (Gemini, post-recording)…", "running")
            transcript = diarize_and_align(transcript, audio, settings, progress=progress)
        elif settings.diarization != "off":
            transcript.warnings.append(
                "Groq Whisper does not detect speakers. Add a Gemini API key to enable "
                "post-recording speaker diarization; until then no speaker labels are shown."
            )

    canonicalize_speakers(transcript.segments)
    if not transcript.duration:
        transcript.duration = audio.duration
    return transcript


# ---------------------------------------------------------------------------
# Gemini (transcript + diarization in a single audio call)
# ---------------------------------------------------------------------------
def _gemini_transcribe(
    audio: AudioPayload,
    settings,
    progress: ProgressFn,
    allow_diarization: bool,
) -> Transcript:
    api_key = settings.require_gemini()
    language_hint = (
        f"The spoken language is '{settings.language}'."
        if settings.language and settings.language != "auto"
        else "Detect the spoken language automatically."
    )
    prompt = (
        f"{language_hint}\n"
        "Transcribe the attached audio and identify the distinct speakers, "
        "following the JSON contract exactly."
    )
    progress("Transcribing with Gemini (audio sent once, transcript + speakers)…", "running")

    text = gemini.generate_from_audio(
        api_key=api_key,
        model=settings.gemini_model,
        audio=audio,
        prompt=prompt,
        system_instruction=GEMINI_STT_SYSTEM,
        temperature=0.0,
        timeout_s=max(settings.stt_timeout, 240),
        json_mode=True,
    )
    transcript = parse_gemini_transcript(
        text,
        duration=audio.duration,
        model=settings.gemini_model,
        diarize=allow_diarization and settings.diarization != "off",
    )
    return transcript


def parse_gemini_transcript(
    text: str,
    *,
    duration: float = 0.0,
    model: str = "",
    diarize: bool = True,
) -> Transcript:
    """Turn the model's JSON into a :class:`Transcript` (pure function, unit-tested)."""
    try:
        payload = parse_json_object(text)
    except ValueError as exc:
        raise ProviderError(
            "Gemini's transcript was not valid JSON, so it could not be read.",
            hint=f"Details: {exc}. Try again; if it repeats, switch transcription engine.",
        ) from exc

    raw_segments = payload.get("segments")
    if raw_segments is None:
        raw_segments = payload.get("transcript") or []
    if not isinstance(raw_segments, list):
        raise ProviderError("Gemini returned an unexpected transcript format.")

    segments: list[Segment] = []
    for item in raw_segments:
        if not isinstance(item, dict):
            continue
        text_value = str(item.get("text") or item.get("content") or "").strip()
        if not text_value:
            continue
        speaker = str(item.get("speaker") or "").strip() if diarize else ""
        try:
            start = float(item.get("start", item.get("start_time", 0)) or 0)
            end = float(item.get("end", item.get("end_time", 0)) or 0)
        except (TypeError, ValueError):
            start, end = 0.0, 0.0
        end = max(end, start)
        segments.append(
            Segment(start=start, end=end, text=text_value, speaker=speaker or None)
        )

    segments.sort(key=lambda s: s.start)
    warnings: list[str] = []
    if not segments:
        warnings.append("No speech was detected in this recording.")

    return Transcript(
        segments=segments,
        language=(str(payload.get("language") or "").strip() or None),
        duration=duration,
        stt_provider="gemini",
        stt_model=model,
        diarization_provider="gemini" if diarize and any(s.speaker for s in segments) else None,
        diarized=bool(diarize and any(s.speaker for s in segments)),
        warnings=warnings,
    )


# ---------------------------------------------------------------------------
# Groq Whisper (transcription only)
# ---------------------------------------------------------------------------
def _groq_transcribe(audio: AudioPayload, settings, progress: ProgressFn) -> Transcript:
    api_key = settings.require_groq()
    try:
        from groq import Groq
    except ImportError as exc:  # pragma: no cover - dependency is pinned
        raise ProviderError("The Groq SDK is not installed.", hint="Run: pip install -r requirements.txt") from exc

    data, mime, filename = prepare_for_provider(audio, "groq")
    language = None if settings.language in ("", "auto") else settings.language
    progress(f"Transcribing with Groq {settings.groq_model}…", "running")

    client = Groq(api_key=api_key, timeout=settings.stt_timeout, max_retries=1)
    try:
        response = client.audio.transcriptions.create(
            model=settings.groq_model,
            file=(filename, data, mime),
            response_format="verbose_json",
            timestamp_granularities=["segment"],
            temperature=0.0,
            language=language,
        )
    except Exception as exc:  # noqa: BLE001 - normalised below
        raise _friendly_groq_error(exc) from exc

    transcript = parse_groq_response(response, fallback_duration=audio.duration, model=settings.groq_model)
    return transcript


def _friendly_groq_error(exc: Exception) -> ProviderError:
    status = getattr(exc, "status_code", None)
    name = type(exc).__name__
    if status == 401 or "Authentication" in name:
        hint = "The Groq API key is invalid. Create a new one at https://console.groq.com/keys."
    elif status == 429:
        hint = "Groq rate limit reached (free tier: 20 requests/min, 28.8k audio-seconds/day). Wait and retry, or switch engine."
    elif status == 413 or status == 400:
        hint = "Groq rejected the audio. Try a shorter clip or a different format."
    elif "Timeout" in name:
        hint = "The request timed out. Try a shorter recording or raise STT_TIMEOUT."
    elif "Connection" in name:
        hint = "Could not reach Groq. Check your internet connection."
    else:
        hint = "Check the Groq status page (https://groqstatus.com) and retry."
    return ProviderError(f"Groq transcription failed: {exc}", hint=hint)


def parse_groq_response(response: Any, *, fallback_duration: float = 0.0, model: str = "") -> Transcript:
    """Convert the Groq ``verbose_json`` response object into a :class:`Transcript`."""
    text = str(getattr(response, "text", "") or "").strip()
    language = getattr(response, "language", None)
    duration = getattr(response, "duration", None) or fallback_duration
    try:
        duration = float(duration)
    except (TypeError, ValueError):
        duration = fallback_duration

    raw_segments = getattr(response, "segments", None) or []
    segments: list[Segment] = []
    for item in raw_segments:
        if isinstance(item, dict):
            start, end, chunk = item.get("start"), item.get("end"), item.get("text")
        else:
            start = getattr(item, "start", None)
            end = getattr(item, "end", None)
            chunk = getattr(item, "text", None)
        chunk = str(chunk or "").strip()
        if not chunk:
            continue
        try:
            start_f = float(start or 0)
            end_f = float(end or 0)
        except (TypeError, ValueError):
            start_f, end_f = 0.0, 0.0
        segments.append(Segment(start=start_f, end=max(end_f, start_f), text=chunk))

    warnings: list[str] = []
    if not segments and text:
        segments = [Segment(start=0.0, end=duration, text=text)]
        warnings.append(
            "Groq did not return segment timestamps; the whole clip is shown as one segment."
        )
    if not segments:
        warnings.append("No speech was detected in this recording.")

    return Transcript(
        segments=segments,
        language=(str(language).strip() if language else None),
        duration=duration,
        stt_provider="groq",
        stt_model=model,
        diarized=False,
        warnings=warnings,
    )
