"""Unit tests for the provider-independent logic.

Run with:  python -m pytest -q

These tests use stubbed provider payloads only - they never call an API and never
pretend that an API call happened.
"""

from __future__ import annotations

import io
import json
import wave

import pytest

from services import diarization, note_generator, transcription
from services.audio import probe_duration, sniff_mime, validate_audio
from services.config import Settings
from services.errors import AudioError, MissingKeyError, NoteGenerationError, ProviderError
from services.export import export_names, notes_markdown, transcript_markdown
from services.json_utils import parse_json_object
from services.models import (
    Notes,
    Segment,
    SpeakerTurn,
    Transcript,
    canonicalize_speakers,
    format_timestamp,
)


# ---------------------------------------------------------------------------
# Models
# ---------------------------------------------------------------------------
def test_format_timestamp():
    assert format_timestamp(0) == "00:00"
    assert format_timestamp(65.4) == "01:05"
    assert format_timestamp(3725) == "01:02:05"
    assert format_timestamp(None) == "--:--"


def test_grouped_segments_merge_same_speaker():
    transcript = Transcript(
        segments=[
            Segment(0, 2, "Hello", "Speaker 1"),
            Segment(2, 4, "there", "Speaker 1"),
            Segment(4, 6, "Hi", "Speaker 2"),
        ]
    )
    grouped = transcript.grouped_segments()
    assert len(grouped) == 2
    assert grouped[0].text == "Hello there"
    assert grouped[0].end == 4
    assert grouped[1].speaker == "Speaker 2"


def test_canonicalize_speakers_renumbers_in_order():
    segments = [Segment(0, 1, "a", "speaker 7"), Segment(1, 2, "b", "Speaker 3"),
                Segment(2, 3, "c", "Speaker 7")]
    canonicalize_speakers(segments)
    assert [s.speaker for s in segments] == ["Speaker 1", "Speaker 2", "Speaker 1"]


# ---------------------------------------------------------------------------
# JSON handling
# ---------------------------------------------------------------------------
def test_parse_json_object_handles_fences_and_chatter():
    assert parse_json_object('```json\n{"a": 1}\n```') == {"a": 1}
    assert parse_json_object('Sure! {"a": 2} hope that helps') == {"a": 2}
    with pytest.raises(ValueError):
        parse_json_object("not json at all")


# ---------------------------------------------------------------------------
# Transcription parsing
# ---------------------------------------------------------------------------
def test_parse_gemini_transcript_orders_and_labels():
    payload = {
        "language": "en",
        "segments": [
            {"start": 6.0, "end": 9.2, "speaker": "Speaker 2", "text": " Sounds good."},
            {"start": 0.0, "end": 3.4, "speaker": "Speaker 1", "text": "Let's start."},
            {"start": 3.5, "end": 6.0, "speaker": "Speaker 1", "text": " First item: budget."},
            {"start": 9.3, "end": 9.5, "speaker": "Speaker 2", "text": "   "},
        ],
    }
    transcript = transcription.parse_gemini_transcript(json.dumps(payload), duration=10.0, model="m")
    assert [s.text for s in transcript.segments] == [
        "Let's start.", "First item: budget.", "Sounds good."
    ]
    assert transcript.speakers() == ["Speaker 1", "Speaker 2"]
    assert transcript.diarized is True
    assert transcript.language == "en"
    assert transcript.word_count() == 7


def test_parse_gemini_transcript_without_diarization_drops_labels():
    payload = {"segments": [{"start": 0, "end": 1, "speaker": "Speaker 1", "text": "hi"}]}
    transcript = transcription.parse_gemini_transcript(json.dumps(payload), diarize=False)
    assert transcript.segments[0].speaker is None
    assert transcript.diarized is False


def test_parse_gemini_transcript_rejects_bad_json():
    with pytest.raises(ProviderError):
        transcription.parse_gemini_transcript("this is not json")


class _FakeGroqResponse:
    def __init__(self, text, language="en", duration=5.0, segments=None):
        self.text = text
        self.language = language
        self.duration = duration
        self.segments = segments or []


def test_parse_groq_response_uses_segments_and_timestamps():
    response = _FakeGroqResponse(
        text="Hello world",
        segments=[
            {"start": 0.0, "end": 2.0, "text": "Hello"},
            {"start": 2.0, "end": 4.5, "text": "world"},
        ],
    )
    transcript = transcription.parse_groq_response(response, fallback_duration=5.0, model="whisper")
    assert len(transcript.segments) == 2
    assert transcript.segments[1].end == 4.5
    assert transcript.diarized is False
    assert transcript.duration == 5.0


def test_parse_groq_response_without_segments_warns():
    transcript = transcription.parse_groq_response(
        _FakeGroqResponse(text="Just one line", segments=[], duration=3.0),
        fallback_duration=3.0,
    )
    assert len(transcript.segments) == 1
    assert transcript.segments[0].end == 3.0
    assert transcript.warnings


# ---------------------------------------------------------------------------
# Diarization
# ---------------------------------------------------------------------------
def test_parse_turns_sorts_and_trims_overlaps():
    payload = {
        "speaker_count": 2,
        "turns": [
            {"start": 5.0, "end": 9.0, "speaker": 2},
            {"start": 0.0, "end": 6.0, "speaker": 1},
            {"start": 9.5, "end": 9.0, "speaker": 2},  # invalid, dropped
        ],
    }
    turns = diarization.parse_turns(json.dumps(payload))
    assert [(t.start, t.end, t.speaker) for t in turns] == [(0.0, 6.0, 1), (6.0, 9.0, 2)]


def test_parse_turns_rejects_bad_json():
    with pytest.raises(ProviderError):
        diarization.parse_turns("nope")


def test_assign_speakers_uses_overlap_not_alternation():
    turns = [SpeakerTurn(0, 2, 1), SpeakerTurn(2, 10, 2)]
    segments = [
        Segment(0.5, 1.5, "short greeting"),
        Segment(2.5, 8.0, "long explanation"),
        Segment(8.0, 9.5, "still the second voice"),
    ]
    assert diarization.assign_speakers(segments, turns) == 3
    assert [s.speaker for s in segments] == ["Speaker 1", "Speaker 2", "Speaker 2"]


def test_assign_speakers_returns_zero_without_turns():
    segments = [Segment(0, 1, "hello")]
    assert diarization.assign_speakers(segments, []) == 0
    assert segments[0].speaker is None


# ---------------------------------------------------------------------------
# Notes
# ---------------------------------------------------------------------------
GOOD_NOTES = {
    "title": "Budget review",
    "summary": "The team reviewed the Q3 budget and agreed to cut travel spend.",
    "topics": ["Q3 budget", "Travel spend"],
    "key_points": ["Travel is 20% over plan"],
    "decisions": ["Cut travel spend by 10%"],
    "action_items": [{"task": "Send revised budget", "owner": "Sana", "due": "Friday"}],
    "open_questions": ["Do we keep the conference trip?"],
    "cleaned_transcript": "Speaker 1: Let's review the budget.",
}


def test_parse_notes_valid_payload():
    notes = note_generator.parse_notes(json.dumps(GOOD_NOTES), model="test-model")
    assert notes.title == "Budget review"
    assert notes.decisions == ["Cut travel spend by 10%"]
    assert notes.action_items[0].owner == "Sana"
    assert notes.model == "test-model"


def test_parse_notes_accepts_empty_sections():
    payload = {"title": "Standup", "summary": "Short sync.", "decisions": [],
               "action_items": [], "cleaned_transcript": ["Speaker 1: hi"]}
    notes = note_generator.parse_notes(json.dumps(payload))
    assert notes.decisions == []
    assert notes.action_items == []
    assert "Speaker 1" in notes.cleaned_transcript


def test_parse_notes_rejects_garbage():
    with pytest.raises(NoteGenerationError):
        note_generator.parse_notes("I could not write notes.")


def test_notes_markdown_marks_missing_sections():
    notes = Notes(title="Standup", summary="Short sync.")
    markdown = notes_markdown(notes, Transcript(segments=[Segment(0, 1, "hi", "Speaker 1")]))
    assert "No decisions were mentioned" in markdown
    assert "No action items were mentioned" in markdown
    assert "Speaker legend" in markdown


# ---------------------------------------------------------------------------
# Audio helpers
# ---------------------------------------------------------------------------
def _wav_bytes(seconds: float = 1.0, rate: int = 16000) -> bytes:
    buffer = io.BytesIO()
    with wave.open(buffer, "wb") as handle:
        handle.setnchannels(1)
        handle.setsampwidth(2)
        handle.setframerate(rate)
        handle.writeframes(b"\x00\x00" * int(rate * seconds))
    return buffer.getvalue()


def test_sniff_and_validate_wav():
    data = _wav_bytes(0.5)
    mime = validate_audio("recording.wav", data, max_mb=10)
    assert mime == "audio/wav"
    assert sniff_mime("whatever.bin", data) == "audio/wav"


def test_probe_duration_for_wav():
    assert probe_duration(_wav_bytes(2.0), "audio/wav") == pytest.approx(2.0, rel=0.01)


def test_validate_rejects_unsupported_extension():
    with pytest.raises(AudioError):
        validate_audio("notes.pdf", b"%PDF-1.4")


def test_validate_rejects_empty_and_huge():
    with pytest.raises(AudioError):
        validate_audio("a.wav", b"")
    with pytest.raises(AudioError):
        validate_audio("a.wav", b"RIFF" + b"0" * (2 * 1024 * 1024), max_mb=1)


# ---------------------------------------------------------------------------
# Exports
# ---------------------------------------------------------------------------
def test_exports_contain_content():
    transcript = Transcript(
        segments=[Segment(0, 2, "Hello team", "Speaker 1"), Segment(2, 4, "Hi", "Speaker 2")],
        duration=4.0,
        stt_provider="gemini",
        stt_model="gemini-x",
        diarized=True,
    )
    markdown = transcript_markdown(transcript, source="Recording")
    assert "**Speaker 1**" in markdown and "**Speaker 2**" in markdown
    assert "00:00" in markdown
    assert export_names("My Meeting / 2026")["bundle_md"] == "My-Meeting-2026-voicenote.md"


# ---------------------------------------------------------------------------
# Settings
# ---------------------------------------------------------------------------
def test_settings_missing_keys_raise_helpful_errors(monkeypatch):
    monkeypatch.setenv("GEMINI_API_KEY", "")
    monkeypatch.setenv("GROQ_API_KEY", "")
    monkeypatch.setattr("services.config._streamlit_secret", lambda name: None)
    settings = Settings.load()
    with pytest.raises(MissingKeyError) as gem_error:
        settings.require_gemini()
    assert "aistudio.google.com" in (gem_error.value.hint or "")
    with pytest.raises(MissingKeyError):
        settings.require_groq()


def test_engine_falls_back_when_key_missing(monkeypatch):
    settings = Settings(transcription_engine="groq", gemini_api_key="g", groq_api_key="")
    assert settings.effective_engine == "gemini"
