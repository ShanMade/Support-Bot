"""VoiceNote AI - speaker-aware voice notes for the GenAI classroom.

Run locally:  streamlit run app.py

This file is UI only. Audio handling, transcription, diarization and note generation
live in ``services/``; reusable widgets live in ``components/``. Backend settings
(including API keys) live in ``services/credentials.py``, ``.env`` or Streamlit secrets.
"""

from __future__ import annotations

import hashlib

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
        st.warning(message, icon="🔑")
    else:
        st.error(message)
    if hint:
        st.info(hint)


# ---------------------------------------------------------------------------
# Header: brand, status, settings, new session
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
    with st.popover("Settings", icon=":material/tune:", width="stretch"):
        st.markdown("##### Transcription")
        options = list(TRANSCRIPTION_ENGINES)
        engine = st.segmented_control(
            "Provider",
            options=options,
            default=base.effective_engine,
            format_func=lambda value: "Gemini" if value == "gemini" else "Whisper",
            key="cfg_engine",
            label_visibility="visible",
            width="stretch",
            help="Gemini returns the transcript and speaker labels together. Whisper is fast; "
            "speakers are added by a second pass over the same audio.",
        ) or base.effective_engine

        model_options = gemini_model_options(base)
        if st.session_state.get("cfg_gemini_model") not in model_options:
            st.session_state["cfg_gemini_model"] = model_options[0]
        gemini_model = st.selectbox(
            "Gemini model",
            options=model_options,
            index=0,
            key="cfg_gemini_model",
            help="Listed from your API key.",
        )

        if st.session_state.get("cfg_groq_model") not in GROQ_MODELS:
            st.session_state["cfg_groq_model"] = GROQ_MODELS[0]
        groq_model = st.selectbox(
            "Whisper model",
            options=GROQ_MODELS,
            key="cfg_groq_model",
            help="whisper-large-v3-turbo is faster; whisper-large-v3 is slightly more accurate.",
        )

        st.markdown("##### Speakers")
        diarize = st.toggle(
            "Identify speakers",
            value=base.diarization != "off",
            key="cfg_diarize",
            help="Groups the audio into anonymous Speaker 1, Speaker 2, ... clusters.",
        )

        st.markdown("##### Language")
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


def pipeline_state() -> tuple[str, str, int]:
    """Return (status label, status css state, active workflow step)."""
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


def render_header(base: Settings) -> Settings:
    label, state, _step = pipeline_state()
    brand_col, status_col, settings_col, new_col = st.columns(
        [5.2, 2.0, 1.15, 0.9], vertical_alignment="center"
    )
    with brand_col:
        layout.brand()
    with status_col:
        layout.status_chip(label, state)
    with settings_col:
        settings = settings_popover(base)
    with new_col:
        if st.button("New", icon=":material/add:", width="stretch", help="Clear this session"):
            reset_results(clear_audio=True)
            st.rerun()
    st.markdown('<div class="vn-rule"></div>', unsafe_allow_html=True)
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
    st.session_state.transcription_error = None
    st.session_state.processed_signature = None
    # Reset the recorder widget so the same clip is never processed twice.
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
    st.toast("Transcript ready", icon="✅")
    st.rerun()


def render_transcription_error() -> None:
    message, hint = st.session_state.transcription_error
    st.error(message)
    if hint:
        st.info(hint)
    if st.button("Try again", type="primary", icon=":material/refresh:", key="retry_transcription"):
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
    st.toast("Notes ready", icon="✨")


# ---------------------------------------------------------------------------
# Capture card
# ---------------------------------------------------------------------------
def render_capture_card(settings: Settings) -> None:
    with st.container(border=False):
        payload = current_audio()
        meta = ""
        if payload is not None:
            meta = (
                f"{st.session_state.source_label or payload.filename} &middot; "
                f"{human_duration(payload.duration)} &middot; {payload.size_mb:.1f} MB"
            )
        layout.card_head("Capture", meta)

        capture = recording.render_capture(
            nonce=st.session_state.rec_nonce, max_upload_mb=settings.max_upload_mb
        )
        handle_capture(capture, settings)

        payload = current_audio()
        if payload is None:
            return

        st.markdown('<div class="vn-divider"></div>', unsafe_allow_html=True)
        player_col, action_col = st.columns([4, 1], vertical_alignment="center")
        with player_col:
            st.audio(payload.data, format=payload.mime)
        with action_col:
            if st.button("Start over", icon=":material/restart_alt:", width="stretch"):
                reset_results(clear_audio=True)
                st.rerun()


# ---------------------------------------------------------------------------
# Results
# ---------------------------------------------------------------------------
def render_empty_hint() -> None:
    with st.container(border=False):
        st.markdown(
            f"""
<div class="vn-empty">
  <div class="icon">{layout.WAVE_ICON}</div>
  <div class="title">Your transcript will appear here</div>
  <div class="sub">Record a conversation above. Speaker labels, timestamps and
     structured notes follow automatically.</div>
  <div class="vn-feature-strip">
    <span class="vn-feature">Speaker labels</span>
    <span class="vn-feature">Timestamps</span>
    <span class="vn-feature">AI notes</span>
    <span class="vn-feature">Markdown export</span>
  </div>
</div>
            """,
            unsafe_allow_html=True,
        )


def render_transcript_card(settings: Settings, transcript: Transcript) -> None:
    with st.container(border=False):
        layout.card_head("Transcript", transcript_view.meta_html(transcript))

        for warning in transcript.warnings:
            st.warning(warning, icon="⚠️")

        if transcript.diarized:
            transcript_view.legend(transcript)
            visible = transcript_view.speaker_filter(transcript.speakers())
        else:
            visible = None
            st.markdown(
                '<div class="vn-meta" style="margin-bottom:.4rem">'
                "Speaker labels are off for this transcript.</div>",
                unsafe_allow_html=True,
            )

        transcript_view.render_segments(transcript, visible)

        st.markdown('<div class="vn-divider"></div>', unsafe_allow_html=True)
        actions_left, actions_right = st.columns([1.2, 1.4], vertical_alignment="center")
        with actions_left:
            with st.popover("Copy", icon=":material/content_copy:", width="stretch"):
                st.caption("Plain text with speaker labels and timestamps.")
                st.code(transcript_text(transcript), language=None)
        with actions_right:
            payload = current_audio()
            if payload is not None:
                stale = transcription_signature(payload, settings) != st.session_state.processed_signature
                if stale and st.button(
                    "Apply new settings",
                    icon=":material/refresh:",
                    width="stretch",
                    help="Re-run transcription with the current engine, model and language.",
                ):
                    st.session_state.transcript_state = None
                    st.session_state.notes_state = None
                    st.session_state.processed_signature = None
                    st.session_state.transcription_error = None
                    st.rerun()


def render_notes_card(settings: Settings, transcript: Transcript) -> Notes | None:
    with st.container(border=False):
        layout.card_head("AI Notes")
        if st.session_state.notes_error:
            message, hint = st.session_state.notes_error
            st.error(message)
            if hint:
                st.info(hint)

        notes_state = st.session_state.notes_state
        if not notes_state:
            st.markdown(
                f"""
<div class="vn-empty">
  <div class="icon">{layout.SPARK_ICON}</div>
  <div class="title">Turn this conversation into notes</div>
  <div class="sub">Summary, decisions, action items and open questions - written
     only from what was actually said.</div>
</div>
                """,
                unsafe_allow_html=True,
            )
            if st.button(
                "Generate notes",
                type="primary",
                icon=":material/auto_awesome:",
                width="stretch",
            ):
                run_note_generation(transcript, settings)
                st.rerun()
            return None

        notes = Notes.from_dict(notes_state)
        edited = notes_view.render(notes, st.session_state.notes_version)

        st.markdown('<div class="vn-divider"></div>', unsafe_allow_html=True)
        regenerate_col, copy_col = st.columns([1, 1], vertical_alignment="center")
        with regenerate_col:
            if st.button(
                "Regenerate",
                icon=":material/refresh:",
                width="stretch",
                help="Ask for a fresh set of notes. Your edits are replaced.",
            ):
                st.session_state.notes_state = None
                st.session_state.notes_error = None
                run_note_generation(transcript, settings)
                st.rerun()
        with copy_col:
            with st.popover("Copy", icon=":material/content_copy:", width="stretch"):
                st.caption("Notes as Markdown, including your edits.")
                st.code(notes_markdown(edited, transcript), language="markdown")
        return edited


def render_export_card(transcript: Transcript | None, notes: Notes | None) -> None:
    if transcript is None:
        return
    payload = current_audio()
    names = export_names(notes.title if notes and notes.title else "voicenote")

    with st.container(border=False):
        layout.card_head("Export", "Markdown or plain text - your edits are included")
        columns = st.columns(4, vertical_alignment="center")
        if notes is not None:
            columns[0].download_button(
                "Notes .md",
                data=notes_markdown(notes, transcript),
                file_name=names["notes_md"],
                mime="text/markdown",
                icon=":material/description:",
                width="stretch",
            )
            columns[1].download_button(
                "Notes .txt",
                data=notes_text(notes),
                file_name=names["notes_txt"],
                mime="text/plain",
                icon=":material/description:",
                width="stretch",
            )
            columns[2].download_button(
                "Everything .md",
                data=combined_markdown(
                    transcript, notes, source=st.session_state.source_label or "Recording"
                ),
                file_name=names["bundle_md"],
                mime="text/markdown",
                icon=":material/download:",
                width="stretch",
            )
            last = columns[3]
        else:
            columns[0].download_button(
                "Transcript .md",
                data=transcript_markdown(
                    transcript, source=st.session_state.source_label or "Recording"
                ),
                file_name=names["transcript_md"],
                mime="text/markdown",
                icon=":material/description:",
                width="stretch",
            )
            columns[1].download_button(
                "Transcript .txt",
                data=transcript_text(transcript),
                file_name=names["transcript_txt"],
                mime="text/plain",
                icon=":material/description:",
                width="stretch",
            )
            last = columns[3]
            last.caption("Generate notes to unlock the notes exports.")

        if payload is not None:
            last.download_button(
                "Audio",
                data=payload.data,
                file_name=payload.filename,
                mime=payload.mime,
                icon=":material/graphic_eq:",
                width="stretch",
            )


# ---------------------------------------------------------------------------
# Page
# ---------------------------------------------------------------------------
def main() -> None:
    init_state()
    styles.inject()

    base = Settings.load()
    settings = render_header(base)
    _label, _state, active = pipeline_state()
    layout.steps(active)

    render_capture_card(settings)
    transcript = maybe_transcribe(settings)

    if transcript is None:
        st.write("")
        render_empty_hint()
    else:
        st.write("")
        left, right = st.columns([1.15, 1], gap="medium")
        with left:
            render_transcript_card(settings, transcript)
        with right:
            notes = render_notes_card(settings, transcript)
        st.write("")
        render_export_card(transcript, notes)

    with st.expander("About this demo", icon=":material/info:"):
        st.markdown(
            """
**How it works.** The browser records one clip. It goes to a speech model that returns
the transcript with timestamps and speaker turns; a language model then writes the notes
from that transcript only.

**Good to know.**
- Recording is clip-based: transcription starts when you press stop, not word by word.
- Speakers are anonymous voice clusters (Speaker 1, Speaker 2) - never identities.
- Notes contain only what was said. Sections that were never discussed say so.
- Audio is processed for this session only and is never stored in the app.
            """
        )

    layout.footer()


main()
