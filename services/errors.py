"""Typed errors that carry a message which is safe to show in the UI."""

from __future__ import annotations


class VoiceNoteError(Exception):
    """Base class for errors that are meant to be displayed to the user."""

    def __init__(self, message: str, *, hint: str | None = None) -> None:
        super().__init__(message)
        self.message = message
        self.hint = hint

    def __str__(self) -> str:  # pragma: no cover - trivial
        return self.message


class MissingKeyError(VoiceNoteError):
    """A required provider API key is not configured."""


class AudioError(VoiceNoteError):
    """The audio is unsupported, too large, too long, or cannot be decoded."""


class ProviderError(VoiceNoteError):
    """The remote provider returned an error or an unusable response."""


class NoteGenerationError(VoiceNoteError):
    """The LLM response could not be turned into structured notes."""
