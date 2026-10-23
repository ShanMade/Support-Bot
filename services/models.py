"""Plain data models shared by the whole application.

These are intentionally dependency-free (no Streamlit, no SDK objects) so they can
be unit-tested and serialised into ``st.session_state`` safely.
"""

from __future__ import annotations

from collections.abc import Iterable
from dataclasses import asdict, dataclass, field
from typing import Any


def format_timestamp(seconds: float | None) -> str:
    """Return ``MM:SS`` (or ``HH:MM:SS`` for long audio)."""
    if seconds is None:
        return "--:--"
    try:
        total = max(0, int(round(float(seconds))))
    except (TypeError, ValueError):
        return "--:--"
    hours, rem = divmod(total, 3600)
    minutes, secs = divmod(rem, 60)
    if hours:
        return f"{hours:02d}:{minutes:02d}:{secs:02d}"
    return f"{minutes:02d}:{secs:02d}"


def _coerce_float(value: Any, default: float = 0.0) -> float:
    try:
        return float(value)
    except (TypeError, ValueError):
        return default


@dataclass
class Segment:
    """One contiguous piece of speech attributed to a single speaker."""

    start: float
    end: float
    text: str
    speaker: str | None = None

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> Segment:
        return cls(
            start=_coerce_float(data.get("start")),
            end=_coerce_float(data.get("end")),
            text=str(data.get("text", "")).strip(),
            speaker=(str(data["speaker"]).strip() if data.get("speaker") else None),
        )

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass
class SpeakerTurn:
    """A diarization span: ``start``-``end`` belongs to one speaker."""

    start: float
    end: float
    speaker: int

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> SpeakerTurn:
        return cls(
            start=_coerce_float(data.get("start")),
            end=_coerce_float(data.get("end")),
            speaker=int(_coerce_float(data.get("speaker"), 1)),
        )


@dataclass
class Transcript:
    """Result of transcription (and, when available, diarization)."""

    segments: list[Segment] = field(default_factory=list)
    language: str | None = None
    duration: float = 0.0
    stt_provider: str = ""
    stt_model: str = ""
    diarization_provider: str | None = None
    diarized: bool = False
    warnings: list[str] = field(default_factory=list)

    # ----- construction -------------------------------------------------
    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> Transcript:
        return cls(
            segments=[Segment.from_dict(s) for s in data.get("segments", [])],
            language=data.get("language"),
            duration=_coerce_float(data.get("duration")),
            stt_provider=data.get("stt_provider", ""),
            stt_model=data.get("stt_model", ""),
            diarization_provider=data.get("diarization_provider"),
            diarized=bool(data.get("diarized", False)),
            warnings=list(data.get("warnings", [])),
        )

    def to_dict(self) -> dict[str, Any]:
        return {
            "segments": [s.to_dict() for s in self.segments],
            "language": self.language,
            "duration": self.duration,
            "stt_provider": self.stt_provider,
            "stt_model": self.stt_model,
            "diarization_provider": self.diarization_provider,
            "diarized": self.diarized,
            "warnings": list(self.warnings),
        }

    # ----- inspection ---------------------------------------------------
    @property
    def is_empty(self) -> bool:
        return not any(s.text.strip() for s in self.segments)

    def speakers(self) -> list[str]:
        seen: list[str] = []
        for seg in self.segments:
            if seg.speaker and seg.speaker not in seen:
                seen.append(seg.speaker)
        return seen

    def word_count(self) -> int:
        return sum(len(s.text.split()) for s in self.segments)

    # ----- rendering ----------------------------------------------------
    def grouped_segments(self) -> list[Segment]:
        """Merge consecutive segments that share the same speaker.

        This keeps the transcript readable while preserving the first timestamp.
        """
        grouped: list[Segment] = []
        for seg in self.segments:
            if not seg.text.strip():
                continue
            if grouped and grouped[-1].speaker == seg.speaker and seg.speaker is not None:
                grouped[-1].text = f"{grouped[-1].text} {seg.text}".strip()
                grouped[-1].end = max(grouped[-1].end, seg.end)
            else:
                grouped.append(Segment(seg.start, seg.end, seg.text, seg.speaker))
        return grouped

    def as_markdown(self, *, include_timestamps: bool = True, grouped: bool = True) -> str:
        rows = self.grouped_segments() if grouped else self.segments
        lines: list[str] = []
        for seg in rows:
            if not seg.text.strip():
                continue
            stamp = f"`[{format_timestamp(seg.start)}]` " if include_timestamps else ""
            speaker = seg.speaker or "Speaker"
            lines.append(f"**{speaker}** {stamp}{seg.text.strip()}  ")
        return "\n".join(lines)

    def as_plain_text(self, *, include_timestamps: bool = True) -> str:
        lines: list[str] = []
        for seg in self.grouped_segments():
            parts: list[str] = []
            if include_timestamps:
                parts.append(f"[{format_timestamp(seg.start)}]")
            parts.append(f"{seg.speaker or 'Speaker'}:")
            parts.append(seg.text.strip())
            lines.append(" ".join(parts))
        return "\n".join(lines)

    def as_prompt_text(self, *, max_chars: int = 60_000) -> str:
        """Compact representation handed to the LLM."""
        lines = [
            f"[{format_timestamp(seg.start)}] {seg.speaker or 'Speaker 1'}: {seg.text.strip()}"
            for seg in self.grouped_segments()
        ]
        text = "\n".join(lines)
        if len(text) > max_chars:
            text = text[:max_chars] + "\n[... transcript truncated ...]"
        return text


@dataclass
class ActionItem:
    task: str
    owner: str = ""
    due: str = ""

    @classmethod
    def from_dict(cls, data: Any) -> ActionItem | None:
        if isinstance(data, str):
            text = data.strip()
            return cls(task=text) if text else None
        if isinstance(data, dict):
            task = str(data.get("task") or data.get("item") or data.get("action") or "").strip()
            if not task:
                return None
            owner = str(data.get("owner") or "").strip()
            due = str(data.get("due") or data.get("deadline") or "").strip()
            return cls(task=task, owner=owner, due=due)
        return None


@dataclass
class Notes:
    title: str = ""
    summary: str = ""
    topics: list[str] = field(default_factory=list)
    key_points: list[str] = field(default_factory=list)
    decisions: list[str] = field(default_factory=list)
    action_items: list[ActionItem] = field(default_factory=list)
    open_questions: list[str] = field(default_factory=list)
    cleaned_transcript: str = ""
    model: str = ""
    generated_at: str = ""

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> Notes:
        items = [ActionItem.from_dict(a) for a in data.get("action_items", [])]
        return cls(
            title=data.get("title", "") or "",
            summary=data.get("summary", "") or "",
            topics=[str(t) for t in data.get("topics", []) if str(t).strip()],
            key_points=[str(t) for t in data.get("key_points", []) if str(t).strip()],
            decisions=[str(t) for t in data.get("decisions", []) if str(t).strip()],
            action_items=[a for a in items if a is not None],
            open_questions=[str(t) for t in data.get("open_questions", []) if str(t).strip()],
            cleaned_transcript=data.get("cleaned_transcript", "") or "",
            model=data.get("model", "") or "",
            generated_at=data.get("generated_at", "") or "",
        )

    def to_dict(self) -> dict[str, Any]:
        data = asdict(self)
        return data

    def is_empty(self) -> bool:
        return not any(
            [self.title, self.summary, self.topics, self.key_points, self.decisions,
             self.action_items, self.open_questions]
        )


def join_bullets(items: Iterable[str]) -> str:
    return "\n".join(f"- {item}" for item in items)


def canonicalize_speakers(segments: list[Segment]) -> None:
    """Relabel speakers to ``Speaker 1..N`` in order of first appearance.

    This keeps labels stable across providers and guarantees we never surface a
    guessed real-world name, only an anonymous speaker index.
    """
    mapping: dict[str, str] = {}
    for seg in segments:
        if not seg.speaker:
            continue
        key = str(seg.speaker).strip().lower()
        if key not in mapping:
            mapping[key] = f"Speaker {len(mapping) + 1}"
        seg.speaker = mapping[key]
