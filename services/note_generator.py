"""AI note generation from a transcript (Gemini text model).

The model is instructed to work strictly from the transcript. Empty sections are
allowed and are shown to the user as "not mentioned" - nothing is fabricated.
"""

from __future__ import annotations

from datetime import UTC, datetime

from . import gemini
from .errors import NoteGenerationError
from .json_utils import as_list, parse_json_object
from .models import ActionItem, Notes, Transcript

SYSTEM_INSTRUCTION = """You are a meticulous meeting-notes assistant.

You receive a transcript of a conversation, produced automatically by speech
recognition. Write structured notes about it and return ONE JSON object with
exactly these keys:

{
  "title": "short descriptive title, at most 8 words",
  "summary": "3-5 sentence executive summary of what was discussed",
  "topics": ["main topic", "..."],
  "key_points": ["important takeaway", "..."],
  "decisions": ["decision actually made in the conversation", "..."],
  "action_items": [{"task": "...", "owner": "...", "due": "..."}],
  "open_questions": ["question raised but not resolved", "..."],
  "cleaned_transcript": "readable transcript organised by speaker"
}

Hard rules:
1. Use ONLY information present in the transcript. Never invent names, numbers,
   dates, owners, deadlines or decisions. If something is unknown, leave the field
   as an empty string.
2. If no decisions were made, return an empty "decisions" list. If no action items
   were agreed, return an empty "action_items" list. Never pad the notes.
3. Use an empty string for "owner" or "due" when the transcript does not state them.
4. "topics" should have 2-6 items; "key_points" 3-8 items; "open_questions" may be
   empty.
5. "cleaned_transcript" keeps the SAME speaker labels as the transcript, in the same
   order. You may remove filler words, stutters and repetitions, fix punctuation and
   capitalisation, and merge consecutive lines from the same speaker. Do not add
   content, do not summarise inside it, and keep roughly the original wording.
6. Automatic transcription may contain errors; if a passage is clearly garbled,
   leave it out rather than guessing a meaning.
7. Return JSON only - no markdown fences, no commentary."""


def build_prompt(transcript: Transcript) -> str:
    speakers = transcript.speakers()
    metadata = [
        f"Speakers detected: {', '.join(speakers) if speakers else 'unknown'}",
        f"Audio length: {int(transcript.duration)} seconds",
        f"Transcript language: {transcript.language or 'unknown'}",
        f"Word count: {transcript.word_count()}",
    ]
    body = transcript.as_prompt_text()
    return (
        "Write the notes for the following transcript.\n\n"
        + "\n".join(metadata)
        + "\n\n--- BEGIN TRANSCRIPT ---\n"
        + body
        + "\n--- END TRANSCRIPT ---"
    )


def parse_notes(text: str, *, model: str = "") -> Notes:
    """Turn the model JSON into :class:`Notes` (pure function, unit-tested)."""
    try:
        payload = parse_json_object(text)
    except ValueError as exc:
        raise NoteGenerationError(
            "The AI response could not be read as structured notes.",
            hint=f"Details: {exc}. Press Generate AI Notes again - the transcript is still intact.",
        ) from exc

    cleaned = payload.get("cleaned_transcript") or ""
    if isinstance(cleaned, list):
        lines = []
        for item in cleaned:
            if isinstance(item, dict):
                speaker = str(item.get("speaker") or "Speaker").strip()
                chunk = str(item.get("text") or item.get("content") or "").strip()
                if chunk:
                    lines.append(f"**{speaker}:** {chunk}")
            else:
                lines.append(str(item))
        cleaned = "\n\n".join(lines)
    elif not isinstance(cleaned, str):
        cleaned = ""

    notes = Notes(
        title=str(payload.get("title") or "").strip(),
        summary=str(payload.get("summary") or "").strip(),
        topics=as_list(payload.get("topics")),
        key_points=as_list(payload.get("key_points")),
        decisions=as_list(payload.get("decisions")),
        action_items=[
            item
            for item in (ActionItem.from_dict(a) for a in (payload.get("action_items") or []))
            if item is not None
        ],
        open_questions=as_list(payload.get("open_questions")),
        cleaned_transcript=cleaned.strip(),
        model=model,
        generated_at=datetime.now(UTC).strftime("%Y-%m-%d %H:%M UTC"),
    )
    if not notes.title:
        notes.title = "Meeting notes"
    return notes


def generate_notes(transcript: Transcript, settings) -> Notes:
    """Call Gemini and return structured notes. Raises on failure (transcript is kept)."""
    if transcript.is_empty:
        raise NoteGenerationError(
            "There is no transcript text to summarise yet.",
            hint="Record or upload audio, wait for the transcript, then generate notes.",
        )
    api_key = settings.require_gemini()
    text = gemini.generate_text(
        api_key=api_key,
        model=settings.gemini_model,
        prompt=build_prompt(transcript),
        system_instruction=SYSTEM_INSTRUCTION,
        temperature=0.2,
        timeout_s=settings.llm_timeout,
        json_mode=True,
    )
    return parse_notes(text, model=settings.gemini_model)
