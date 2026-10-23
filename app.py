"""VoiceNote AI - speaker-aware voice notes for the GenAI classroom.

Run locally:  streamlit run app.py

This file is UI only. Audio handling, transcription, diarization and note
generation live in ``services/``; reusable widgets live in ``components/``.
"""

from __future__ import annotations

import hashlib

import streamlit as st

from components import layout, notes_view, recording, styles, transcript_view
from services.audio import AudioPayload, human_duration
from services.config import (
    GROQ_MODELS,
    TRANSCRIPTION_ENGINES,
    Settings,
    integration_status,
)
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
    "keys_override": {},
}

st.set_page_config(page_title="VoiceNote AI", page_icon="🎙️", layout="wide")


# ---------------------------------------------------------------------------
# Session state helpers
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
# Sidebar: configuration + integration health
# ---------------------------------------------------------------------------
@st.cache_data(ttl=600, show_spinner=False)
def cached_models(api_key: str) -> tuple[str, ...]:
    return tuple(list_chat_models(api_key))


def render_sidebar(base: Settings) -> Settings:
    overrides: dict[str, str] = st.session_state.keys_override
    settings = base.with_changes(
        gemini_api_key=overrides.get("GEMINI_API_KEY", base.gemini_api_key),
        groq_api_key=overrides.get("GROQ_API_KEY", base.groq_api_key),
    )

    with st.sidebar:
        st.markdown("#### Configuration")
        engine_choice = st.segmented_control(
            "Transcription engine",
            options=list(TRANSCRIPTION_ENGINES),
            default=settings.effective_engine,
            format_func=lambda value: "Gemini" if value == "gemini" else "Groq Whisper",
            key="cfg_engine",
            help="Gemini returns transcript and speakers in one call. Groq Whisper is fast; "
                 "speakers are added by a second Gemini pass over the audio.",
        )
        engine = engine_choice or settings.effective_engine

        live_models = list(cached_models(settings.gemini_api_key)) if settings.has_gemini else []
        gemini_options = [settings.gemini_model]
        substituted = False
        if live_models:
            if settings.gemini_model in live_models:
                curated = [settings.gemini_model] + [m for m in live_models if m != settings.gemini_model]
            else:
                preferred = next(
                    (m for m in live_models if "flash" in m.lower() and "lite" not in m.lower()),
                    live_models[0],
                )
                curated = [preferred] + [m for m in live_models if m != preferred]
                substituted = True
            gemini_options = curated
        if st.session_state.get("cfg_gemini_model") not in gemini_options:
            st.session_state["cfg_gemini_model"] = gemini_options[0]
        gemini_model = st.selectbox(
            "Gemini model",
            options=gemini_options,
            index=0,
            key="cfg_gemini_model",
            help="Also used for diarization and note writing. The list is loaded from your API key.",
        )

        if st.session_state.get("cfg_groq_model") not in GROQ_MODELS:
            st.session_state["cfg_groq_model"] = GROQ_MODELS[0]
        if substituted:
            st.caption(
                f"`{settings.gemini_model}` is not available to this key - using "
                f"`{gemini_options[0]}`. You can change it above."
            )
        groq_model = st.selectbox(
            "Groq model",
            options=GROQ_MODELS,
            index=GROQ_MODELS.index(settings.groq_model) if settings.groq_model in GROQ_MODELS else 0,
            key="cfg_groq_model",
            disabled=not settings.has_groq,
            help="whisper-large-v3-turbo is faster; whisper-large-v3 is slightly more accurate.",
        )

        language = st.selectbox(
            "Spoken language",
            options=list(LANGUAGES),
            index=list(LANGUAGES).index(settings.language) if settings.language in LANGUAGES else 0,
            format_func=lambda code: LANGUAGES[code],
            key="cfg_language",
        )

        diarize = st.toggle(
            "Identify speakers",
            value=settings.diarization != "off",
            key="cfg_diarize",
            help="Uses Gemini's audio model to group speech into anonymous Speaker 1, Speaker 2, "
                 "… clusters. Runs after recording because the recorder sends one complete clip.",
        )
        st.caption(
            "Diarization mode: "
            + ("Gemini audio analysis" if diarize else "off")
        )

        settings = settings.with_changes(
            transcription_engine=engine,
            gemini_model=gemini_model,
            groq_model=groq_model,
            language=language,
            diarization="auto" if diarize else "off",
        )

        st.divider()
        st.markdown("#### Connections")
        for item in integration_status(settings):
            icon = "🟢" if item.configured else "⚪"
            st.markdown(
                f"{icon} **{item.name}**  \n<span style='font-size:.76rem;color:#64748b'>"
                f"{item.detail}</span>",
                unsafe_allow_html=True,
            )

        with st.expander("API keys", expanded=not (settings.has_gemini and settings.has_groq)):
            st.caption(
                "Keys come from `.env` locally or from Streamlit secrets in the cloud. "
                "You can also paste keys here: they are kept in memory for this browser "
                "session only and are never written to disk or shown again."
            )
            gemini_input = st.text_input(
                "GEMINI_API_KEY",
                type="password",
                placeholder="configured" if settings.has_gemini else "AIza...",
                key="key_gemini_input",
            )
            groq_input = st.text_input(
                "GROQ_API_KEY",
                type="password",
                placeholder="configured" if settings.has_groq else "gsk_...",
                key="key_groq_input",
            )
            col_a, col_b = st.columns(2)
            if col_a.button("Use for this session", width="stretch"):
                new_overrides = dict(st.session_state.keys_override)
                if gemini_input.strip():
                    new_overrides["GEMINI_API_KEY"] = gemini_input.strip()
                if groq_input.strip():
                    new_overrides["GROQ_API_KEY"] = groq_input.strip()
                st.session_state.keys_override = new_overrides
                st.rerun()
            if col_b.button("Clear session keys", width="stretch", disabled=not overrides):
                st.session_state.keys_override = {}
                st.rerun()

        st.divider()
        st.markdown("#### Session")
        if st.button("Clear recording & notes", width="stretch"):
            reset_results(clear_audio=True)
            st.rerun()
        st.caption(
            "Audio lives in this browser session only. Nothing is written to disk and "
            "nothing is kept after you close the tab."
        )

        with st.expander("How it works"):
            st.markdown(
                "1. The browser records one WAV clip (`st.audio_input`).\n"
                "2. The clip goes to Gemini or Groq - transcribe + speaker labels.\n"
                "3. Gemini writes structured notes from the transcript only.\n"
                "4. Edit anything, then export Markdown / TXT.\n\n"
                "Speakers are anonymous clusters (Speaker 1, Speaker 2). The app never "
                "tries to work out who somebody really is."
            )

    return settings


# ---------------------------------------------------------------------------
# Pipeline handling
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
    # Reset the recorder so the same clip is not shown twice (and cannot be
    # transcribed a second time); the audio itself is kept in session state.
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
        except MissingKeyError as exc:
            status.update(label="Missing API key", state="error", expanded=True)
            st.session_state.transcription_error = (exc.message, exc.hint)
            st.session_state.processed_signature = signature
            return
        except VoiceNoteError as exc:
            status.update(label="Transcription failed", state="error", expanded=True)
            st.session_state.transcription_error = (exc.message, exc.hint)
            st.session_state.processed_signature = signature
            return
        except Exception as exc:  # noqa: BLE001 - last-resort guard
            status.update(label="Unexpected error", state="error", expanded=True)
            st.session_state.transcription_error = (
                f"Unexpected error while transcribing: {exc}",
                "Check the app logs for details. Your recording is still available.",
            )
            st.session_state.processed_signature = signature
            return

        status.update(
            label=f"Transcript ready - {len(transcript.speakers()) or 1} speaker cluster(s), "
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
    # Refresh once so the recorder widget resets and the new sections render cleanly.
    st.rerun()


def render_transcription_error() -> None:
    message, hint = st.session_state.transcription_error
    st.error(message)
    if hint:
        st.info(hint)
    if st.button("Try transcription again", type="primary", key="retry_transcription"):
        st.session_state.transcription_error = None
        st.session_state.processed_signature = None
        st.rerun()


def maybe_transcribe(settings: Settings) -> Transcript | None:
    """Transcribe once per clip/settings combination; never re-call the API on reruns."""
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
            (
                "Groq Whisper only transcribes; the summary and notes come from Gemini. "
                "Add GEMINI_API_KEY or paste a key in the sidebar."
            ),
        )
        return
    with st.spinner(f"Gemini is writing notes with {settings.gemini_model}…"):
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
    st.toast("AI notes ready", icon="✨")


# ---------------------------------------------------------------------------
# Sections
# ---------------------------------------------------------------------------
def render_recording_section(settings: Settings) -> None:
    payload_before = current_audio()
    status_text = (
        f"clip ready · {human_duration(payload_before.duration)}" if payload_before else "waiting for audio"
    )
    with st.container(border=True):
        layout.section("Record", status_text)
        capture = recording.render_capture(
            nonce=st.session_state.rec_nonce,
            max_upload_mb=settings.max_upload_mb,
        )
        handle_capture(capture, settings)

        payload = current_audio()
        if payload is None:
            st.caption("Nothing recorded yet. Use the microphone or upload a clip.")
            return

        col_a, col_b = st.columns([3, 1])
        with col_a:
            st.audio(payload.data, format=payload.mime)
        with col_b:
            st.caption(
                f"**{st.session_state.source_label or payload.filename}**  \n"
                f"{human_duration(payload.duration)} · {payload.size_mb:.1f} MB"
            )
        if st.button("Start over", help="Discard this clip, transcript and notes"):
            reset_results(clear_audio=True)
            st.rerun()


def render_transcript_section(settings: Settings, transcript: Transcript | None) -> None:
    st.markdown("---")
    payload = current_audio()
    layout.section("Transcript")

    if transcript is None:
        st.markdown(
            '<div class="vn-empty">Record or upload audio to see the speaker-labelled '
            "transcript here.</div>",
            unsafe_allow_html=True,
        )
        return

    for warning in transcript.warnings:
        st.warning(warning, icon="⚠️")

    st.markdown(
        f'<div class="vn-note-meta">{transcript_view.meta_line(transcript)}</div>',
        unsafe_allow_html=True,
    )
    if transcript.diarized:
        transcript_view.legend(transcript)
    else:
        st.caption(
            "No speaker separation in this transcript. "
            + ("Enable Identify speakers in the sidebar." if settings.diarization != "off"
               else "Speaker identification is switched off.")
        )

    transcript_view.render_segments(transcript)

    if payload is not None:
        signature = transcription_signature(payload, settings)
        if signature != st.session_state.processed_signature:
            st.caption(
                "Transcription settings changed since this transcript was produced."
            )
            if st.button("Transcribe again with current settings"):
                st.session_state.transcript_state = None
                st.session_state.notes_state = None
                st.session_state.processed_signature = None
                st.session_state.transcription_error = None
                st.rerun()

    with st.expander("Copy & download transcript"):
        st.code(transcript_text(transcript), language=None)
        names = export_names(st.session_state.source_label or "voicenote")
        col_a, col_b = st.columns(2)
        col_a.download_button(
            "Download transcript (.md)",
            data=transcript_markdown(transcript, source=st.session_state.source_label or "Recording"),
            file_name=names["transcript_md"],
            mime="text/markdown",
            width="stretch",
        )
        col_b.download_button(
            "Download transcript (.txt)",
            data=transcript_text(transcript),
            file_name=names["transcript_txt"],
            mime="text/plain",
            width="stretch",
        )


def render_notes_section(settings: Settings, transcript: Transcript | None) -> Notes | None:
    st.markdown("---")
    layout.section("AI Notes")

    if transcript is None:
        st.markdown(
            '<div class="vn-empty">Notes are generated from the transcript once the '
            "recording has been transcribed.</div>",
            unsafe_allow_html=True,
        )
        return None

    if st.session_state.notes_error:
        message, hint = st.session_state.notes_error
        st.error(message)
        if hint:
            st.info(hint)

    notes = (
        Notes.from_dict(st.session_state.notes_state)
        if st.session_state.notes_state
        else None
    )

    if notes is None:
        st.caption(
            "Gemini will summarise only what is in the transcript: title, summary, topics, "
            "decisions, action items and open questions. Missing sections are reported as "
            "not mentioned instead of being invented."
        )
        if st.button("✨ Generate AI Notes", type="primary"):
            run_note_generation(transcript, settings)
            st.rerun()
        return None

    edited = notes_view.render(notes, st.session_state.notes_version)

    col_a, col_b = st.columns([1, 3])
    if col_a.button("Regenerate", help="Ask Gemini for a fresh set of notes"):
        st.session_state.notes_state = None
        st.session_state.notes_error = None
        run_note_generation(transcript, settings)
        st.rerun()
    col_b.caption(
        "Edits above are what gets exported. Regenerating replaces them."
    )
    return edited


def render_export_section(transcript: Transcript | None, notes: Notes | None) -> None:
    if transcript is None:
        return
    st.markdown("---")
    layout.section("Export")
    payload = current_audio()
    names = export_names(notes.title if notes and notes.title else "voicenote")

    col_a, col_b, col_c = st.columns(3)
    if notes is not None:
        col_a.download_button(
            "Notes (.md)",
            data=notes_markdown(notes, transcript),
            file_name=names["notes_md"],
            mime="text/markdown",
            width="stretch",
        )
        col_b.download_button(
            "Notes (.txt)",
            data=notes_text(notes),
            file_name=names["notes_txt"],
            mime="text/plain",
            width="stretch",
        )
        col_c.download_button(
            "Notes + transcript (.md)",
            data=combined_markdown(
                transcript, notes, source=st.session_state.source_label or "Recording"
            ),
            file_name=names["bundle_md"],
            mime="text/markdown",
            width="stretch",
        )
    else:
        st.caption("Generate the AI notes to unlock the notes exports - the transcript can already be downloaded above.")

    with st.expander("Copy notes as Markdown"):
        if notes is not None:
            st.code(notes_markdown(notes, transcript), language="markdown")
        else:
            st.caption("Generate the notes first.")

    if payload is not None:
        with st.expander("Original recording"):
            st.caption(
                "The clip exists only in this session's memory. Downloading it stores a copy "
                "on your computer - make sure the people in the recording are fine with that."
            )
            st.download_button(
                f"Download audio ({payload.mime.split('/')[-1]})",
                data=payload.data,
                file_name=payload.filename,
                mime=payload.mime,
                width="stretch",
            )


def render_setup_banner(settings: Settings) -> None:
    if settings.has_gemini and settings.has_groq:
        return
    if not settings.has_gemini and not settings.has_groq:
        st.warning(
            "No API keys are configured yet. Add `GEMINI_API_KEY` and/or `GROQ_API_KEY` to your "
            "`.env` file (local) or Streamlit secrets (cloud), or paste them under "
            "**API keys** in the sidebar.",
            icon="🔑",
        )
        return
    if not settings.has_gemini:
        st.info(
            "Groq is configured, so transcription works. Speaker identification and AI notes need "
            "a Gemini key - add `GEMINI_API_KEY` to enable them.",
            icon="ℹ️",
        )
    if not settings.has_groq and settings.transcription_engine == "groq":
        st.info(
            "The Groq engine is selected but no Groq key is configured - Gemini will be used instead.",
            icon="ℹ️",
        )


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------
def main() -> None:
    init_state()
    styles.inject()
    base = Settings.load()
    settings = render_sidebar(base)

    layout.header(integration_status(settings))
    render_setup_banner(settings)

    transcript = current_transcript()
    notes_exist = st.session_state.notes_state is not None
    active = 0 if transcript is None else (3 if notes_exist else 2)
    layout.step_bar(active)

    render_recording_section(settings)
    transcript = maybe_transcribe(settings)

    if transcript is None:
        st.markdown("---")
        layout.section("Transcript")
        st.markdown(
            '<div class="vn-empty">Your speaker-labelled transcript will appear here as soon '
            "as the recording has been transcribed. Notes and exports unlock after that.</div>",
            unsafe_allow_html=True,
        )
        render_limitations()
        layout.footer()
        return

    render_transcript_section(settings, transcript)
    notes = render_notes_section(settings, transcript)
    render_export_section(transcript, notes)

    render_limitations()
    layout.footer()


def render_limitations() -> None:
    with st.expander("Limitations & how to present this"):
        st.markdown(
            """
- **Recording is clip-based.** Streamlit's `st.audio_input` records in the browser and
  uploads one WAV file when you press stop, so transcription starts the moment you stop.
  There is no word-by-word streaming and no interim (grey) text in this build, and the UI
  never claims there is.
- **Speaker labels are anonymous clusters** produced by Gemini listening to the audio.
  They are not identities: two similar voices can be merged, and quick interruptions can
  be mis-assigned. Nothing in the app tries to guess who someone is.
- **Notes come only from the transcript.** Sections that were never discussed are
  reported as "not mentioned" rather than filled in.
- **Provider keys are required.** Gemini's free tier is enough for a classroom demo;
  Groq's free tier allows 20 requests/minute and ~28.8k audio-seconds/day per Whisper model.
- **Audio stays in this session.** It is sent to the selected provider for processing and
  is never written to the repository.
            """
        )


main()
