"""AI notes: readable preview plus inline editing."""

from __future__ import annotations

import html

import pandas as pd
import streamlit as st

from services.models import ActionItem, Notes


def _lines(text: str) -> list[str]:
    return [line.strip(" -•\t") for line in text.splitlines() if line.strip(" -•\t")]


def _join(items: list[str]) -> str:
    return "\n".join(items)


def _value(key: str, default: str) -> str:
    return str(st.session_state.get(key, default))


def _build_from_state(notes: Notes, version: int, action_rows: pd.DataFrame | None) -> Notes:
    """Current widget values, falling back to the generated notes."""
    prefix = f"notes_{version}_"
    items: list[ActionItem] = []
    if isinstance(action_rows, pd.DataFrame):
        for record in action_rows.to_dict("records"):
            task = str(record.get("Task") or "").strip()
            if not task:
                continue
            items.append(
                ActionItem(
                    task=task,
                    owner=str(record.get("Owner") or "").strip(),
                    due=str(record.get("Due") or "").strip(),
                )
            )
    if action_rows is None:
        items = notes.action_items

    return Notes(
        title=_value(f"{prefix}title", notes.title),
        summary=_value(f"{prefix}summary", notes.summary),
        topics=_lines(_value(f"{prefix}topics", _join(notes.topics))),
        key_points=_lines(_value(f"{prefix}keypoints", _join(notes.key_points))),
        decisions=_lines(_value(f"{prefix}decisions", _join(notes.decisions))),
        action_items=items,
        open_questions=_lines(_value(f"{prefix}questions", _join(notes.open_questions))),
        cleaned_transcript=_value(f"{prefix}cleaned", notes.cleaned_transcript),
        model=notes.model,
        generated_at=notes.generated_at,
    )


def _editor(notes: Notes, version: int) -> pd.DataFrame:
    prefix = f"notes_{version}_"
    st.text_input("Title", value=notes.title, key=f"{prefix}title")
    st.text_area("Executive summary", value=notes.summary, key=f"{prefix}summary", height=130)
    st.text_area(
        "Main topics (one per line)",
        value=_join(notes.topics),
        key=f"{prefix}topics",
        height=110,
    )
    st.text_area(
        "Key takeaways (one per line)",
        value=_join(notes.key_points),
        key=f"{prefix}keypoints",
        height=130,
    )
    st.text_area(
        "Decisions (one per line)",
        value=_join(notes.decisions),
        key=f"{prefix}decisions",
        height=100,
    )
    st.caption("Action items - edit cells, or add rows for follow-ups you agreed on.")
    frame = pd.DataFrame(
        [{"Task": item.task, "Owner": item.owner, "Due": item.due} for item in notes.action_items],
        columns=["Task", "Owner", "Due"],
    )
    edited_actions = st.data_editor(
        frame,
        key=f"{prefix}actions",
        num_rows="dynamic",
        hide_index=True,
        width="stretch",
        column_config={
            "Task": st.column_config.TextColumn("Task", width="large"),
            "Owner": st.column_config.TextColumn("Owner"),
            "Due": st.column_config.TextColumn("Due"),
        },
    )
    st.text_area(
        "Open questions (one per line)",
        value=_join(notes.open_questions),
        key=f"{prefix}questions",
        height=100,
    )
    st.text_area(
        "Cleaned transcript (Markdown)",
        value=notes.cleaned_transcript,
        key=f"{prefix}cleaned",
        height=220,
    )
    return edited_actions


def _bullets(items: list[str], empty_text: str) -> None:
    if items:
        st.markdown("\n".join(f"- {item}" for item in items))
    else:
        st.markdown(f"<span style='color:#94a3b8;font-size:.86rem'>{html.escape(empty_text)}</span>",
                    unsafe_allow_html=True)


def _preview(notes: Notes) -> None:
    title = html.escape(notes.title or "Meeting notes")
    meta = ""
    if notes.generated_at:
        meta = f"Generated {html.escape(notes.generated_at)} with {html.escape(notes.model or 'Gemini')}"
    st.markdown(f'<div class="vn-note-title">{title}</div>', unsafe_allow_html=True)
    if meta:
        st.markdown(f'<div class="vn-note-meta">{meta}</div>', unsafe_allow_html=True)

    if notes.summary:
        st.markdown(notes.summary)

    if notes.topics:
        st.markdown("**Main topics**")
        _bullets(notes.topics, "")
    if notes.key_points:
        st.markdown("**Key takeaways**")
        _bullets(notes.key_points, "")

    st.markdown("**Decisions**")
    _bullets(notes.decisions, "No decisions were mentioned in this conversation.")

    st.markdown("**Action items**")
    if notes.action_items:
        rows = ["| Task | Owner | Due |", "| --- | --- | --- |"]
        for item in notes.action_items:
            rows.append(
                f"| {item.task} | {item.owner or 'not stated'} | {item.due or 'not stated'} |"
            )
        st.markdown("\n".join(rows))
    else:
        st.markdown(
            "<span style='color:#94a3b8;font-size:.86rem'>"
            "No action items were mentioned in this conversation.</span>",
            unsafe_allow_html=True,
        )

    st.markdown("**Open questions**")
    _bullets(notes.open_questions, "None raised.")

    if notes.cleaned_transcript:
        st.markdown("**Cleaned transcript**")
        with st.container(border=True):
            st.markdown(notes.cleaned_transcript)


def render(notes: Notes, version: int) -> Notes:
    """Render the notes with an edit expander; returns the current (edited) notes."""
    preview_slot = st.container()
    with st.expander("Edit notes", expanded=False):
        action_rows = _editor(notes, version)
    edited = _build_from_state(notes, version, action_rows)
    with preview_slot:
        _preview(edited)
    return edited
