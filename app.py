"""VoiceNote AI - speaker-aware voice notes for the GenAI classroom.

Run locally:  streamlit run app.py

This file is layout only. Audio, transcription, diarization and note generation
live in ``services/``; widgets live in ``components/``. Backend settings,
including API keys, live in ``services/credentials.py``, ``.env`` or Streamlit
secrets - never in the interface.
"""

from __future__ import annotations

import hashlib
import html

import streamlit as st

from components import layout, notes_view, recording, styles, transcript_view
from services.audio import AudioPayload, human_duration
from services.config import GROQ_MODELS, TRANSCRIPTION_ENGINES, Settings
from services.errors import AudioError, MissingKeyError, VoiceNoteError
from services.export import (
    combined_markdown,
    export_names,
    notes_markdown,
    notes_text,
    transcript_markdown,
    transcript_text,
)
from services.gemini import list_chat_models
from services.models import Notes, Transcript
from services.note_generator import generate_notes
from services.pipeline import build_payload, process_audio, transcription_signature

LANGUAGES = {
    "auto": "Auto-detect",
    "en": "English",
    "ur": "Urdu",
    "hi": "Hindi",
    "ar": "Arabic",
    "es": "Spanish",
    "fr": "French",
    "de": "German",
    "pt": "Portuguese",
    "zh": "Chinese",
    "id": "Indonesian",
}

STATE_DEFAULTS = {
    "audio_state": None,
    "audio_sha": None,
    "source_label": "",
    "transcript_state": None,
    "processed_signature": None,
    "transcription_error": None,
    "notes_state": None,
    "notes_version": 0,
    "notes_error": None,
    "notes_edit": False,
    "rec_nonce": 0,
}

st.set_page_config(
    page_title="VoiceNote AI",
    page_icon="🎙️",
    layout="wide",
    initial_sidebar_state="collapsed",
)


# ---------------------------------------------------------------------------
# Session state
# ---------------------------------------------------------------------------
def init_state() -> None:
    for key, value in STATE_DEFAULTS.items():
        if key not in st.session_state:
            st.session_state[key] = value


def reset_results(*, clear_audio: bool = True) -> None:
    st.session_state.transcript_state = None
    st.session_state.notes_state = None
    st.session_state.notes_error = None
    st.session_state.notes_edit = False
    st.session_state.transcription_error = None
    st.session_state.processed_signature = None
    if clear_audio:
        st.session_state.audio_state = None
        st.session_state.audio_sha = None
        st.session_state.source_label = ""
        st.session_state.rec_nonce += 1


def current_audio() -> AudioPayload | None:
    return AudioPayload.from_state(st.session_state.audio_state)


def current_transcript() -> Transcript | None:
    state = st.session_state.transcript_state
    return Transcript.from_dict(state) if state else None


def show_error(exc: Exception) -> None:
    message = getattr(exc, "message", str(exc))
    hint = getattr(exc, "hint", None)
    if isinstance(exc, MissingKeyError):
        st.warning(message)
    else:
        st.error(message)
    if hint:
        st.caption(hint)


def right_aligned() -> st.delta_generator.DeltaGenerator:
    return st.container(horizontal=True, horizontal_alignment="right", gap="small")


# ---------------------------------------------------------------------------
# Settings (backend stays invisible; these are behavioural choices only)
# ---------------------------------------------------------------------------
@st.cache_data(ttl=600, show_spinner=False)
def cached_models(api_key: str) -> tuple[str, ...]:
    return tuple(list_chat_models(api_key))


def gemini_model_options(settings: Settings) -> list[str]:
    live = list(cached_models(settings.gemini_api_key)) if settings.has_gemini else []
    if not live:
        return [settings.gemini_model]
    if settings.gemini_model in live:
        return [settings.gemini_model] + [m for m in live if m != settings.gemini_model]
    preferred = next(
        (m for m in live if "flash" in m.lower() and "lite" not in m.lower()), live[0]
    )
    return [preferred] + [m for m in live if m != preferred]


def settings_popover(base: Settings) -> Settings:
    with st.popover("Settings", width="content"):
        st.markdown("##### Transcription")
        engine = st.segmented_control(
            "Provider",
            options=list(TRANSCRIPTION_ENGINES),
            default=base.effective_engine,
            format_func=lambda value: "Gemini" if value == "gemini" else "Whisper",
            key="cfg_engine",
            width="stretch",
            help="Gemini returns the transcript and speaker labels together. Whisper is fast; "
            "speakers are added by a second pass over the same audio.",
        ) or base.effective_engine

        model_options = gemini_model_options(base)
        if st.session_state.get("cfg_gemini_model") not in model_options:
            st.session_state["cfg_gemini_model"] = model_options[0]
        gemini_model = st.selectbox(
            "Gemini model", options=model_options, index=0, key="cfg_gemini_model"
        )

        if st.session_state.get("cfg_groq_model") not in GROQ_MODELS:
            st.session_state["cfg_groq_model"] = GROQ_MODELS[0]
        groq_model = st.selectbox(
            "Whisper model", options=GROQ_MODELS, key="cfg_groq_model",
            help="large-v3-turbo is faster; large-v3 is slightly more accurate.",
        )

        st.markdown("##### Speakers & language")
        diarize = st.toggle(
            "Identify speakers",
            value=base.diarization != "off",
            key="cfg_diarize",
            help="Groups the audio into anonymous Speaker 1, Speaker 2, ... clusters.",
        )
        language = st.selectbox(
            "Spoken language",
            options=list(LANGUAGES),
            index=list(LANGUAGES).index(base.language) if base.language in LANGUAGES else 0,
            format_func=lambda code: LANGUAGES[code],
            key="cfg_language",
        )

    return base.with_changes(
        transcription_engine=engine,
        gemini_model=gemini_model,
        groq_model=groq_model,
        diarization="auto" if diarize else "off",
        language=language,
    )


# ---------------------------------------------------------------------------
# Top bar
# ---------------------------------------------------------------------------
def pipeline_state() -> tuple[str, str, int]:
    transcript = current_transcript()
    notes = st.session_state.notes_state is not None
    if st.session_state.transcription_error:
        return "Needs attention", "busy", 1
    if transcript is None:
        if current_audio() is not None:
            return "Transcribing", "busy", 1
        return "Ready", "ready", 0
    if notes:
        return "Notes ready", "done", 3
    return "Transcript ready", "done", 2


def render_topbar(base: Settings) -> Settings:
    label, state, _step = pipeline_state()
    brand_col, status_col, action_col = st.columns([3.2, 1.4, 1.6], vertical_alignment="center")
    with brand_col:
        layout.brand()
    with status_col:
        layout.status(label, state)
    with action_col:
        with right_aligned():
            settings = settings_popover(base)
            if st.button("New session", width="content", help="Clear this session"):
                reset_results(clear_audio=True)
                st.rerun()
    return settings


# ---------------------------------------------------------------------------
# Pipeline
# ---------------------------------------------------------------------------
def handle_capture(capture: recording.Capture | None, settings: Settings) -> None:
    """Store a new clip and drop results that belong to the previous one."""
    if capture is None:
        return
    digest = hashlib.sha256(capture.data).hexdigest()
    if digest == st.session_state.audio_sha:
        return
    try:
        payload = build_payload(
            capture.filename,
            capture.data,
            max_mb=settings.max_upload_mb,
            max_seconds=settings.max_audio_seconds,
        )
    except AudioError as exc:
        show_error(exc)
        return

    st.session_state.audio_state = payload.to_state()
    st.session_state.audio_sha = digest
    st.session_state.source_label = (
        "Microphone recording" if capture.source == "microphone" else payload.filename
    )
    st.session_state.transcript_state = None
    st.session_state.notes_state = None
    st.session_state.notes_error = None
    st.session_state.notes_edit = False
    st.session_state.transcription_error = None
    st.session_state.processed_signature = None
    st.session_state.rec_nonce += 1


def run_transcription(payload: AudioPayload, settings: Settings) -> None:
    signature = transcription_signature(payload, settings)
    with st.status("Preparing audio…", expanded=True) as status:
        try:
            transcript = process_audio(
                payload,
                settings,
                progress=lambda message, _state="running": status.update(label=message),
            )
        except (MissingKeyError, VoiceNoteError) as exc:
            status.update(label="Transcription failed", state="error", expanded=True)
            st.session_state.transcription_error = (exc.message, exc.hint)
            st.session_state.processed_signature = signature
            return
        except Exception as exc:  # noqa: BLE001 - last-resort guard
            status.update(label="Unexpected error", state="error", expanded=True)
            st.session_state.transcription_error = (
                f"Unexpected error while transcribing: {exc}",
                "Your recording is still available - try again.",
            )
            st.session_state.processed_signature = signature
            return

        status.update(
            label=f"Transcript ready - {len(transcript.speakers()) or 1} speaker(s), "
            f"{transcript.word_count()} words",
            state="complete",
            expanded=False,
        )

    st.session_state.transcript_state = transcript.to_dict()
    st.session_state.processed_signature = signature
    st.session_state.transcription_error = None
    st.session_state.notes_state = None
    st.session_state.notes_error = None
    st.toast("Transcript ready")
    st.rerun()


def render_transcription_error() -> None:
    message, hint = st.session_state.transcription_error
    st.error(message)
    if hint:
        st.caption(hint)
    if st.button("Try again", type="primary", key="retry_transcription"):
        st.session_state.transcription_error = None
        st.session_state.processed_signature = None
        st.rerun()


def maybe_transcribe(settings: Settings) -> Transcript | None:
    """Transcribe once per clip/settings combination; never repeat on a plain rerun."""
    payload = current_audio()
    transcript = current_transcript()
    if payload is None:
        return transcript
    if st.session_state.transcription_error:
        render_transcription_error()
        return transcript
    if transcript is None:
        run_transcription(payload, settings)
        if st.session_state.transcription_error:
            render_transcription_error()
        return current_transcript()
    return transcript


def run_note_generation(transcript: Transcript, settings: Settings) -> None:
    if not settings.has_gemini:
        st.session_state.notes_error = (
            "Note generation needs a Gemini API key.",
            "Add GEMINI_API_KEY in the backend configuration, then press Generate again.",
        )
        return
    with st.spinner("Writing notes…"):
        try:
            notes = generate_notes(transcript, settings)
        except VoiceNoteError as exc:
            st.session_state.notes_error = (exc.message, exc.hint)
            return
        except Exception as exc:  # noqa: BLE001
            st.session_state.notes_error = (
                f"Unexpected error while generating notes: {exc}",
                "The transcript is still available - you can export it or try again.",
            )
            return
    st.session_state.notes_state = notes.to_dict()
    st.session_state.notes_version += 1
    st.session_state.notes_error = None
    st.session_state.notes_edit = False
    st.toast("Notes ready")


# ---------------------------------------------------------------------------
# Sections
# ---------------------------------------------------------------------------
def render_capture(settings: Settings) -> None:
    payload = current_audio()

    meta = ""
    if payload is not None:
        label = st.session_state.source_label or payload.filename
        if len(label) > 30:
            label = f"{label[:27]}…"
        meta = (
            f'<b>{html.escape(label)}</b> &middot; '
            f'<span class="vn-mono">{human_duration(payload.duration)}</span> &middot; '
            f"{payload.size_mb:.1f} MB"
        )
    layout.kicker("Capture", meta)

    with st.container(border=True):
        layout.card_marker()
        mode = recording.source_switch()
        capture = recording.render_input(
            mode, nonce=st.session_state.rec_nonce, max_upload_mb=settings.max_upload_mb
        )
        handle_capture(capture, settings)

        payload = current_audio()
        if payload is None:
            return

        st.markdown('<div class="vn-rule" style="margin:0.9rem 0 0.6rem"></div>',
                    unsafe_allow_html=True)
        player_col, action_col = st.columns([4, 1], vertical_alignment="center")
        with player_col:
            st.audio(payload.data, format=payload.mime)
        with action_col:
            if st.button("Start over", width="stretch"):
                reset_results(clear_audio=True)
                st.rerun()


def render_intro() -> None:
    st.markdown(
        """
<div class="vn-intro">
  <h2>Turn a recording into notes you can send.</h2>
  <p>Record or upload a conversation above. VoiceNote AI separates the voices, timestamps
     every line, then writes the summary, decisions and action items - only from what was
     actually said.</p>
</div>
        """,
        unsafe_allow_html=True,
    )


def render_transcript_section(settings: Settings, transcript: Transcript) -> None:
    layout.rule()
    payload = current_audio()
    stale = (
        payload is not None
        and transcription_signature(payload, settings) != st.session_state.processed_signature
    )
    actions = layout.section("Transcript", transcript_view.meta_html(transcript))
    with actions, right_aligned():
        with st.popover("Copy transcript", width="content"):
            st.caption("Speaker labels, timestamps, plain text.")
            st.code(transcript_text(transcript), language=None)
        if stale and st.button("Re-transcribe", width="content"):
            st.session_state.transcript_state = None
            st.session_state.notes_state = None
            st.session_state.processed_signature = None
            st.session_state.transcription_error = None
            st.rerun()

    with st.container(border=True):
        layout.card_marker()

        for warning in transcript.warnings:
            st.warning(warning)

        if transcript.diarized:
            legend_col, filter_col = st.columns([1.4, 1], vertical_alignment="center")
            with legend_col:
                transcript_view.legend(transcript)
            with filter_col:
                visible = transcript_view.speaker_filter(transcript.speakers())
        else:
            visible = None
            st.caption("Speaker labels are off for this transcript.")

        transcript_view.render_segments(transcript, visible)


def render_notes_section(settings: Settings, transcript: Transcript) -> Notes | None:
    layout.rule()
    state = st.session_state.notes_state
    notes = Notes.from_dict(state) if state else None
    editing = bool(st.session_state.notes_edit and notes is not None)

    meta = ""
    if notes is not None:
        bits = [bit for bit in (notes.generated_at, notes.model) if bit]
        if bits:
            meta = " &middot; ".join(html.escape(bit) for bit in bits)

    actions = layout.section("Notes", meta)

    if st.session_state.notes_error:
        message, hint = st.session_state.notes_error
        st.error(message)
        if hint:
            st.caption(hint)

    if notes is None:
        with actions, right_aligned():
            if st.button("Generate notes", type="primary", width="content"):
                run_note_generation(transcript, settings)
                st.rerun()
        with st.container(border=True):
            layout.card_marker()
            st.markdown(
                '<div class="vn-empty" style="padding:0.3rem 0 0.1rem">'
                "No notes yet &mdash; generate them from the transcript above.</div>",
                unsafe_allow_html=True,
            )
        return None

    if editing:
        with actions, right_aligned():
            if st.button("Done editing", type="primary", width="content"):
                st.session_state.notes_edit = False
                st.rerun()
        with st.container(border=True):
            layout.card_marker()
            action_rows = notes_view.edit_form(notes, st.session_state.notes_version)
        edited = notes_view.current_values(notes, st.session_state.notes_version, action_rows)
        # Persist edits as they happen, so the read view and every export use them.
        st.session_state.notes_state = edited.to_dict()
    else:
        with actions, right_aligned():
            with st.popover("Copy notes", width="content"):
                st.caption("Markdown, including your edits.")
                st.code(notes_markdown(notes, transcript), language="markdown")
            if st.button("Edit", width="content"):
                st.session_state.notes_edit = True
                st.rerun()
            if st.button("Regenerate", width="content", help="Your edits are replaced."):
                st.session_state.notes_state = None
                st.session_state.notes_error = None
                run_note_generation(transcript, settings)
                st.rerun()
        with st.container(border=True):
            layout.card_marker()
            notes_view.read_view(notes)
        edited = notes

    return edited


def render_export_section(transcript: Transcript | None, notes: Notes | None) -> None:
    if transcript is None:
        return
    payload = current_audio()
    names = export_names(notes.title if notes and notes.title else "voicenote")
    source = st.session_state.source_label or "Recording"

    layout.rule()
    layout.kicker("Export", "your edits are included")

    downloads: list[tuple[str, bytes, str, str]] = []
    if notes is not None:
        downloads.append(
            ("Notes .md", notes_markdown(notes, transcript).encode(), names["notes_md"], "text/markdown")
        )
        downloads.append(("Notes .txt", notes_text(notes).encode(), names["notes_txt"], "text/plain"))
        downloads.append(
            (
                "Everything .md",
                combined_markdown(transcript, notes, source=source).encode(),
                names["bundle_md"],
                "text/markdown",
            )
        )
    else:
        downloads.append(
            (
                "Transcript .md",
                transcript_markdown(transcript, source=source).encode(),
                names["transcript_md"],
                "text/markdown",
            )
        )
        downloads.append(
            ("Transcript .txt", transcript_text(transcript).encode(), names["transcript_txt"], "text/plain")
        )
    if payload is not None:
        downloads.append(("Audio clip", payload.data, payload.filename, payload.mime))

    with st.container(horizontal=True, gap="small", wrap=True):
        for label, data, file_name, mime in downloads:
            st.download_button(label, data=data, file_name=file_name, mime=mime, width="content")

    if notes is None:
        st.caption("Generate the notes to unlock the notes exports.")
    if payload is not None:
        st.caption(
            "Audio stays in this session only and is never stored by the app - "
            "downloading saves a copy to your computer."
        )


# ---------------------------------------------------------------------------
# Page
# ---------------------------------------------------------------------------
def main() -> None:
    init_state()
    styles.inject()

    base = Settings.load()
    settings = render_topbar(base)

    _label, _state, active = pipeline_state()
    layout.steps(active)
    layout.rule("0.65rem")

    if current_audio() is None and current_transcript() is None:
        render_intro()

    render_capture(settings)
    transcript = maybe_transcribe(settings)

    if transcript is not None:
        render_transcript_section(settings, transcript)
        notes = render_notes_section(settings, transcript)
        render_export_section(transcript, notes)

    with st.expander("About this demo"):
        st.markdown(
            """
Recording is clip-based: transcription starts when you press stop, not word by word.
Speakers are anonymous voice clusters (Speaker 1, Speaker 2) - never identities. Notes
contain only what was said, and sections that were not discussed say so.
            """
        )

    layout.footer()


main()
