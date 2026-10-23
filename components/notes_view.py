"""AI notes: a clean preview plus an inline editor that keeps every field editable."""

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
    """Widget values merged over the generated notes."""
    prefix = f"notes_{version}_"

    items: list[ActionItem] = []
    if action_rows is not None:
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
    else:
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
    st.text_area("Executive summary", value=notes.summary, key=f"{prefix}summary", height=120)
    st.text_area(
        "Main topics (one per line)", value=_join(notes.topics), key=f"{prefix}topics", height=100
    )
    st.text_area(
        "Key takeaways (one per line)",
        value=_join(notes.key_points),
        key=f"{prefix}keypoints",
        height=120,
    )
    st.text_area(
        "Decisions (one per line)", value=_join(notes.decisions), key=f"{prefix}decisions", height=96
    )
    st.caption("Action items - edit the cells, or add rows for anything you agreed to.")
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
        height=96,
    )
    st.text_area(
        "Cleaned transcript (Markdown)",
        value=notes.cleaned_transcript,
        key=f"{prefix}cleaned",
        height=200,
    )
    return edited_actions


def _bullets(items: list[str]) -> str:
    return "<ul>" + "".join(f"<li>{html.escape(item)}</li>" for item in items) + "</ul>"


def _block(label: str, body_html: str) -> str:
    return (
        '<div class="vn-block">'
        f'<div class="vn-block-label">{html.escape(label)}</div>{body_html}</div>'
    )


def _preview(notes: Notes) -> None:
    if notes.generated_at:
        meta = f"Generated {notes.generated_at}"
        if notes.model:
            meta += f" &middot; {notes.model}"
        st.markdown(f'<div class="vn-note-meta">{html.escape(meta)}</div>', unsafe_allow_html=True)

    blocks: list[str] = []
    if notes.summary:
        blocks.append(_block("Summary", f'<p>{html.escape(notes.summary)}</p>'))
    if notes.topics:
        blocks.append(_block("Main topics", _bullets(notes.topics)))
    if notes.key_points:
        blocks.append(_block("Key takeaways", _bullets(notes.key_points)))

    decisions = (
        _bullets(notes.decisions)
        if notes.decisions
        else '<div class="vn-faint-line">No decisions were mentioned.</div>'
    )
    blocks.append(_block("Decisions", decisions))

    if notes.action_items:
        cards = []
        for item in notes.action_items:
            tags = ""
            if item.owner:
                tags += f'<span class="vn-tag">{html.escape(item.owner)}</span>'
            if item.due:
                tags += f'<span class="vn-tag due">{html.escape(item.due)}</span>'
            tags_html = f'<div class="vn-tags">{tags}</div>' if tags else ""
            cards.append(
                '<div class="vn-action"><div class="box"></div><div>'
                f'<div class="task">{html.escape(item.task)}</div>{tags_html}'
                "</div></div>"
            )
        actions_html = "".join(cards)
    else:
        actions_html = '<div class="vn-faint-line">No action items were mentioned.</div>'
    blocks.append(_block("Action items", actions_html))

    questions = (
        _bullets(notes.open_questions)
        if notes.open_questions
        else '<div class="vn-faint-line">No open questions.</div>'
    )
    blocks.append(_block("Open questions", questions))

    st.markdown("".join(blocks), unsafe_allow_html=True)

    if notes.cleaned_transcript:
        with st.expander("Cleaned transcript"):
            st.markdown(notes.cleaned_transcript)


def render(notes: Notes, version: int) -> Notes:
    """Preview the notes, offer inline editing, and return the current values."""
    preview_slot = st.container()
    with st.expander("Edit notes"):
        action_rows = _editor(notes, version)

    edited = _build_from_state(notes, version, action_rows)
    with preview_slot:
        st.markdown(
            f'<div class="vn-note-title">{html.escape(edited.title or "Meeting notes")}</div>',
            unsafe_allow_html=True,
        )
        _preview(edited)
    return edited
