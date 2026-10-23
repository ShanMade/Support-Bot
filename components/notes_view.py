"""Notes: an editorial read view plus a plain edit view.

Read and edit are two modes of the same section (a toggle switches between them),
which keeps the page calm and avoids a fragile nested expander.
"""

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


def current_values(notes: Notes, version: int, action_rows: pd.DataFrame | None) -> Notes:
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


def edit_form(notes: Notes, version: int) -> pd.DataFrame:
    """Two-column editor; returns the action-item table."""
    prefix = f"notes_{version}_"
    left, right = st.columns(2, gap="large")

    with left:
        st.text_input("Title", value=notes.title, key=f"{prefix}title")
        st.text_area("Summary", value=notes.summary, key=f"{prefix}summary", height=150)
        st.text_area(
            "Main topics", value=_join(notes.topics), key=f"{prefix}topics", height=110,
            help="One per line.",
        )
        st.text_area(
            "Key takeaways", value=_join(notes.key_points), key=f"{prefix}keypoints", height=150,
            help="One per line.",
        )

    with right:
        st.text_area(
            "Decisions", value=_join(notes.decisions), key=f"{prefix}decisions", height=110,
            help="One per line.",
        )
        frame = pd.DataFrame(
            [{"Task": i.task, "Owner": i.owner, "Due": i.due} for i in notes.action_items],
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
                "Owner": st.column_config.TextColumn("Owner", width="small"),
                "Due": st.column_config.TextColumn("Due", width="small"),
            },
        )
        st.text_area(
            "Open questions", value=_join(notes.open_questions), key=f"{prefix}questions", height=110,
            help="One per line.",
        )

    st.text_area(
        "Cleaned transcript (Markdown)",
        value=notes.cleaned_transcript,
        key=f"{prefix}cleaned",
        height=190,
    )
    return edited_actions


def _bullets(items: list[str]) -> str:
    return "<ul>" + "".join(f"<li>{html.escape(item)}</li>" for item in items) + "</ul>"


def _block(label: str, body: str) -> str:
    return (
        f'<div class="vn-block"><div class="vn-block-label">{html.escape(label)}</div>'
        f"{body}</div>"
    )


def read_view(notes: Notes) -> None:
    meta = ""
    if notes.generated_at:
        meta = f"Generated {html.escape(notes.generated_at)}"
        if notes.model:
            meta += f" &middot; {html.escape(notes.model)}"
    st.markdown(
        f'<div class="vn-note-title">{html.escape(notes.title or "Meeting notes")}</div>'
        + (f'<div class="vn-note-meta">{meta}</div>' if meta else ""),
        unsafe_allow_html=True,
    )

    blocks: list[str] = []
    if notes.summary:
        blocks.append(f"<p>{html.escape(notes.summary)}</p>")
    if notes.topics:
        blocks.append(_block("Topics", _bullets(notes.topics)))
    if notes.key_points:
        blocks.append(_block("Key takeaways", _bullets(notes.key_points)))

    blocks.append(
        _block(
            "Decisions",
            _bullets(notes.decisions)
            if notes.decisions
            else '<div class="vn-quiet">No decisions were mentioned.</div>',
        )
    )

    if notes.action_items:
        rows = []
        for item in notes.action_items:
            tags = ""
            if item.owner:
                tags += f'<span class="vn-tag">{html.escape(item.owner)}</span>'
            if item.due:
                tags += f'<span class="vn-tag due">{html.escape(item.due)}</span>'
            tag_html = f'<div class="tags">{tags}</div>' if tags else ""
            rows.append(f'<div class="a">{html.escape(item.task)}{tag_html}</div>')
        actions_html = f'<div class="vn-actions">{"".join(rows)}</div>'
    else:
        actions_html = '<div class="vn-quiet">No action items were mentioned.</div>'
    blocks.append(_block("Action items", actions_html))

    blocks.append(
        _block(
            "Open questions",
            _bullets(notes.open_questions)
            if notes.open_questions
            else '<div class="vn-quiet">None raised.</div>',
        )
    )

    st.markdown(f'<div class="vn-notes">{"".join(blocks)}</div>', unsafe_allow_html=True)

    if notes.cleaned_transcript:
        with st.expander("Cleaned transcript"):
            st.markdown(notes.cleaned_transcript)
