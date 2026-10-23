"""Markdown / plain-text export builders."""

from __future__ import annotations

from datetime import datetime

from .audio import human_duration
from .models import Notes, Transcript, format_timestamp


def _stamp() -> str:
    return datetime.now().strftime("%Y-%m-%d %H:%M")


def _file_stem(title: str) -> str:
    safe = "".join(ch if ch.isalnum() or ch in " -_" else "" for ch in title).strip()
    safe = "-".join(safe.split())[:60]
    return safe or "voicenote"


def transcript_markdown(
    transcript: Transcript, *, source: str = "Recording", created: str | None = None
) -> str:
    speakers = transcript.speakers()
    lines = [
        "# Transcript",
        "",
        f"- Source: {source}",
        f"- Created: {created or _stamp()}",
        f"- Length: {human_duration(transcript.duration)}",
        f"- Transcription: {transcript.stt_provider or 'n/a'} {transcript.stt_model}".rstrip(),
        f"- Speakers: {', '.join(speakers) if speakers else 'not identified'}",
    ]
    if transcript.language:
        lines.append(f"- Language: {transcript.language}")
    lines += ["", "---", ""]
    lines.append(transcript.as_markdown(include_timestamps=True))
    return "\n".join(lines).strip() + "\n"


def transcript_text(transcript: Transcript) -> str:
    return transcript.as_plain_text(include_timestamps=True).strip() + "\n"


def notes_markdown(notes: Notes, transcript: Transcript | None = None) -> str:
    lines = [f"# {notes.title or 'Meeting notes'}", ""]
    if notes.generated_at:
        lines.append(f"_Generated {notes.generated_at} with {notes.model or 'Gemini'}_")
        lines.append("")
    if notes.summary:
        lines += ["## Executive summary", "", notes.summary, ""]
    if notes.topics:
        lines += ["## Main topics", ""] + [f"- {item}" for item in notes.topics] + [""]
    if notes.key_points:
        lines += ["## Key takeaways", ""] + [f"- {item}" for item in notes.key_points] + [""]

    lines += ["## Decisions", ""]
    lines += [f"- {item}" for item in notes.decisions] if notes.decisions else ["_No decisions were mentioned._"]
    lines.append("")

    lines += ["## Action items", ""]
    if notes.action_items:
        lines += ["| # | Task | Owner | Due |", "| --- | --- | --- | --- |"]
        for index, item in enumerate(notes.action_items, start=1):
            lines.append(
                f"| {index} | {item.task} | {item.owner or 'not stated'} | {item.due or 'not stated'} |"
            )
    else:
        lines.append("_No action items were mentioned._")
    lines.append("")

    lines += ["## Open questions", ""]
    lines += [f"- {item}" for item in notes.open_questions] if notes.open_questions else ["_None raised._"]
    lines.append("")

    if notes.cleaned_transcript:
        lines += ["## Cleaned transcript", "", notes.cleaned_transcript, ""]

    if transcript is not None and transcript.segments:
        lines += [
            "## Speaker legend",
            "",
            "_Speakers are anonymous voice clusters. The app does not identify who a person is._",
            "",
        ]
        for speaker in transcript.speakers() or ["Speaker"]:
            first = next((s for s in transcript.segments if s.speaker == speaker), None)
            span = format_timestamp(first.start) if first else "--:--"
            lines.append(f"- **{speaker}** - first heard at {span}")
        lines.append("")

    return "\n".join(lines).strip() + "\n"


def notes_text(notes: Notes) -> str:
    parts = [notes.title or "Meeting notes", "=" * 40, ""]
    if notes.summary:
        parts += ["SUMMARY", notes.summary, ""]
    if notes.topics:
        parts += ["TOPICS"] + [f"* {t}" for t in notes.topics] + [""]
    if notes.key_points:
        parts += ["KEY POINTS"] + [f"* {t}" for t in notes.key_points] + [""]
    parts += ["DECISIONS"] + ([f"* {d}" for d in notes.decisions] or ["* None mentioned."]) + [""]
    if notes.action_items:
        parts += ["ACTION ITEMS"]
        for item in notes.action_items:
            extra = []
            if item.owner:
                extra.append(f"owner: {item.owner}")
            if item.due:
                extra.append(f"due: {item.due}")
            suffix = f" ({', '.join(extra)})" if extra else ""
            parts.append(f"* {item.task}{suffix}")
        parts.append("")
    else:
        parts += ["ACTION ITEMS", "* None mentioned.", ""]
    parts += ["OPEN QUESTIONS"] + ([f"* {q}" for q in notes.open_questions] or ["* None raised."]) + [""]
    if notes.cleaned_transcript:
        parts += ["CLEANED TRANSCRIPT", notes.cleaned_transcript, ""]
    return "\n".join(parts).strip() + "\n"


def combined_markdown(transcript: Transcript, notes: Notes | None, *, source: str = "Recording") -> str:
    document = ""
    if notes:
        document += notes_markdown(notes, transcript) + "\n---\n\n"
    document += transcript_markdown(transcript, source=source)
    return document


def export_names(title: str) -> dict[str, str]:
    stem = _file_stem(title)
    return {
        "notes_md": f"{stem}-notes.md",
        "notes_txt": f"{stem}-notes.txt",
        "transcript_md": f"{stem}-transcript.md",
        "transcript_txt": f"{stem}-transcript.txt",
        "bundle_md": f"{stem}-voicenote.md",
    }
