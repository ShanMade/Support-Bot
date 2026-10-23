"""Speaker diarization.

Diarization here means: *which anonymous voice is speaking when*. It never tries to
work out **who** a person is.

The diarization model listens to the audio itself (Gemini multimodal audio) and
returns speaker turns with timestamps. Because Groq Whisper produces the words but
no speaker information, the turns are aligned to the Whisper segments by timestamp
overlap.
"""

from __future__ import annotations

from collections.abc import Callable

from . import gemini
from .audio import AudioPayload
from .errors import ProviderError
from .json_utils import parse_json_object
from .models import Segment, SpeakerTurn, Transcript, canonicalize_speakers

ProgressFn = Callable[[str, str], None]

GEMINI_DIARIZATION_SYSTEM = """You are an audio-only speaker diarization engine.

You listen to a recording and report WHEN each distinct voice is speaking. You do
not transcribe the words.

Return a JSON object:
{
  "speaker_count": 2,
  "turns": [
    {"start": 0.0, "end": 6.4, "speaker": 1},
    {"start": 6.9, "end": 11.2, "speaker": 2}
  ]
}

Rules:
1. Timestamps are seconds from the start of the audio, decimals with one place.
2. Turns are chronological and must not overlap.
3. A turn is a continuous stretch spoken by one voice. Split a turn when the voice
   changes, and also at long pauses (more than ~2 seconds).
4. Give each distinct voice a stable integer id starting at 1, in order of first
   appearance. The same voice must keep the same id for the whole recording.
5. Do not output silence-only spans. If only one voice is present, use id 1.
6. Never guess names, genders, ages or identities.
7. If there is no speech, return {"speaker_count": 0, "turns": []}.
8. Return JSON only - no markdown, no explanation."""


def diarize_audio(
    audio: AudioPayload,
    settings,
    *,
    progress: ProgressFn | None = None,
    expected_speakers: int | None = None,
) -> list[SpeakerTurn]:
    """Run an audio-based diarization pass and return speaker turns."""
    api_key = settings.require_gemini()
    if progress:
        progress("Detecting distinct speakers from the audio…", "running")

    hint = (
        f"There are about {expected_speakers} distinct speakers."
        if expected_speakers and expected_speakers > 1
        else "Detect the number of distinct speakers yourself."
    )
    prompt = (
        f"{hint}\nAnalyse the attached audio and return the speaker turns as JSON."
    )
    text = gemini.generate_from_audio(
        api_key=api_key,
        model=settings.gemini_model,
        audio=audio,
        prompt=prompt,
        system_instruction=GEMINI_DIARIZATION_SYSTEM,
        temperature=0.0,
        timeout_s=max(settings.stt_timeout, 240),
        json_mode=True,
    )
    return parse_turns(text)


def parse_turns(text: str) -> list[SpeakerTurn]:
    """Parse the diarization JSON into turns (pure function, unit-tested)."""
    try:
        payload = parse_json_object(text)
    except ValueError as exc:
        raise ProviderError(
            "The diarization response was not valid JSON.",
            hint="Try again, or transcribe with the Gemini engine which returns speakers directly.",
        ) from exc

    raw_turns = payload.get("turns") or payload.get("segments") or []
    if not isinstance(raw_turns, list):
        raise ProviderError("The diarization response had an unexpected format.")

    turns: list[SpeakerTurn] = []
    for item in raw_turns:
        if not isinstance(item, dict):
            continue
        try:
            start = float(item.get("start", 0) or 0)
            end = float(item.get("end", 0) or 0)
            speaker = int(float(item.get("speaker", 1)))
        except (TypeError, ValueError):
            continue
        if end <= start:
            continue
        turns.append(SpeakerTurn(start=max(start, 0.0), end=end, speaker=max(speaker, 1)))

    turns.sort(key=lambda t: t.start)

    # Drop overlapping tails so alignment stays deterministic.
    cleaned: list[SpeakerTurn] = []
    for turn in turns:
        if cleaned and turn.start < cleaned[-1].end:
            turn = SpeakerTurn(start=cleaned[-1].end, end=turn.end, speaker=turn.speaker)
        if turn.end > turn.start:
            cleaned.append(turn)
    return cleaned


def _best_speaker(segment: Segment, turns: list[SpeakerTurn], max_gap: float = 15.0) -> int | None:
    """Speaker whose turn overlaps the segment the most (nearest turn as fallback)."""
    best_id: int | None = None
    best_overlap = 0.0
    for turn in turns:
        overlap = min(segment.end, turn.end) - max(segment.start, turn.start)
        if overlap > best_overlap:
            best_overlap = overlap
            best_id = turn.speaker
    if best_id is not None:
        return best_id

    midpoint = (segment.start + segment.end) / 2
    nearest: tuple[float, int] | None = None
    for turn in turns:
        distance = min(abs(midpoint - turn.start), abs(midpoint - turn.end))
        if nearest is None or distance < nearest[0]:
            nearest = (distance, turn.speaker)
    if nearest and nearest[0] <= max_gap:
        return nearest[1]
    return None


def assign_speakers(segments: list[Segment], turns: list[SpeakerTurn]) -> int:
    """Attach speaker labels to segments; returns how many were labelled."""
    if not turns:
        return 0
    labelled = 0
    for segment in segments:
        speaker = _best_speaker(segment, turns)
        if speaker is None:
            continue
        segment.speaker = f"Speaker {speaker}"
        labelled += 1
    return labelled


def diarize_and_align(
    transcript: Transcript,
    audio: AudioPayload,
    settings,
    *,
    progress: ProgressFn | None = None,
) -> Transcript:
    """Diarize the complete recording and label an existing transcript."""
    turns = diarize_audio(audio, settings, progress=progress)
    labelled = assign_speakers(transcript.segments, turns)
    if labelled:
        canonicalize_speakers(transcript.segments)
        transcript.diarized = True
        transcript.diarization_provider = "gemini"
    else:
        transcript.warnings.append(
            "Diarization did not return usable speaker turns, so no speaker labels were added."
        )
    return transcript
