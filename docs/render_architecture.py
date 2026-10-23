"""Render docs/architecture.png — VoiceNote AI system diagram.

Styled like the reference README diagram: pale-yellow group boxes, lavender nodes,
thin grey connectors with small labels, dashed lines for conditional paths.

Every connector is routed in its own channel so nothing crosses.
Usage:  python docs/render_architecture.py     (dev only, needs matplotlib)
"""

from __future__ import annotations

from pathlib import Path

import matplotlib

matplotlib.use("Agg")

import matplotlib.pyplot as plt
from matplotlib.patches import FancyArrowPatch, FancyBboxPatch

BG = "#ffffff"
GROUP_FILL = "#fffceb"
GROUP_EDGE = "#e5dfb6"
NODE_FILL = "#eef0fe"
NODE_EDGE = "#c9c6f2"
ALT_FILL = "#e9f5ee"
ALT_EDGE = "#bcd8c8"
GREY_FILL = "#f7f7f8"
GREY_EDGE = "#d8d8dc"
TEXT = "#1f2937"
SUB = "#4b5563"
MUTED = "#6b7280"
EDGE = "#8c9199"
GROUP_LABEL = "#7a7648"

W, H = 15.6, 9.9
fig, ax = plt.subplots(figsize=(W, H), dpi=200)
fig.patch.set_facecolor(BG)
ax.set_facecolor(BG)
ax.set_xlim(0, W)
ax.set_ylim(0, H)
ax.set_aspect("equal")
ax.axis("off")


# ------------------------------------------------------------------ helpers --
def group(x, y, w, h, label):
    ax.add_patch(
        FancyBboxPatch(
            (x, y), w, h, boxstyle="round,pad=0,rounding_size=0.07",
            facecolor=GROUP_FILL, edgecolor=GROUP_EDGE, linewidth=1.1, zorder=1,
        )
    )
    ax.text(x + 0.13, y + h - 0.17, label, fontsize=6.9, color=GROUP_LABEL,
            ha="left", va="center", zorder=2)


def node(x, y, w, h, lines, *, fill=NODE_FILL, edge=NODE_EDGE, size=7.3):
    ax.add_patch(
        FancyBboxPatch(
            (x, y), w, h, boxstyle="round,pad=0,rounding_size=0.05",
            facecolor=fill, edgecolor=edge, linewidth=1.0, zorder=3,
        )
    )
    gap = 0.168
    top = y + h / 2 + (len(lines) - 1) * gap / 2
    for index, line in enumerate(lines):
        ax.text(
            x + w / 2, top - index * gap, line,
            fontsize=size + 0.5 if index == 0 else size - 0.35,
            fontweight="bold" if index == 0 else "normal",
            color=TEXT if index == 0 else SUB,
            ha="center", va="center", zorder=4,
        )


def flow(points, *, label=None, label_at=None, dashed=False, both=False, rotate=0,
         size=6.2):
    """Orthogonal polyline; arrowhead on the last segment; label optional."""
    style = (0, (3.2, 2.6)) if dashed else "solid"
    xs = [p[0] for p in points]
    ys = [p[1] for p in points]
    if len(points) > 2:
        ax.plot(xs[:-1], ys[:-1], color=EDGE, lw=0.9, zorder=5, linestyle=style,
                solid_capstyle="butt")
    ax.add_patch(
        FancyArrowPatch(
            points[-2], points[-1],
            arrowstyle="<|-|>,head_width=2.4,head_length=4.0" if both
            else "-|>,head_width=2.4,head_length=4.0",
            color=EDGE, lw=0.9, zorder=6, shrinkA=0, shrinkB=0.4,
            linestyle=style, mutation_scale=1.0,
        )
    )
    if label:
        lx, ly = label_at
        ax.text(lx, ly, label, fontsize=size, color=MUTED,
                ha="center", va="center", rotation=rotate, zorder=9,
                bbox=dict(boxstyle="round,pad=0.18", fc=BG, ec="none", alpha=0.95))


# -------------------------------------------------------------------- title --
ax.text(0.55, 9.52, "VoiceNote AI — system architecture", fontsize=13.2,
        fontweight="bold", color=TEXT, ha="left", va="center")
ax.text(0.57, 9.20, "one Streamlit process  ·  audio stays in session memory  ·  "
                    "only the clip is sent to the provider you select",
        fontsize=7.6, color=MUTED, ha="left", va="center")

# --------------------------------------------------------------------- grid --
BROWSER = (0.55, 8.55, 2.85, 0.60)
APP = (5.95, 8.55, 4.55, 0.60)
node(*BROWSER, ["Browser", "microphone · file upload"], fill=GREY_FILL, edge=GREY_EDGE)
node(*APP, ["app.py · Streamlit UI", "session state · actions · exports"])

PIPE = (4.55, 4.05, 7.95, 4.15)
group(*PIPE, "Pipeline — services/")
PIPELINE = (7.25, 7.35, 3.50, 0.60)
AUDIO = (4.95, 5.95, 3.15, 0.78)
TRANS = (8.55, 5.95, 3.55, 0.78)
DIA = (4.95, 4.35, 3.15, 0.78)
NOTES = (8.55, 4.35, 3.55, 0.78)
node(*PIPELINE, ["pipeline.py", "validate · measure · route"])
node(*AUDIO, ["audio.py", "MIME sniff · size + length limits", "ffmpeg → 16 kHz MP3"])
node(*TRANS, ["transcription.py", "engine adapter · response parsing"])
node(*DIA, ["diarization.py", "speaker turns · overlap alignment"])
node(*NOTES, ["note_generator.py", "strict JSON contract · no invention"])

PROV = (4.55, 1.45, 7.95, 1.85)
group(*PROV, "Providers")
FF = (4.85, 1.70, 2.05, 0.75)
GEM = (7.35, 1.62, 2.75, 0.95)
GROQ = (10.30, 1.70, 1.95, 0.75)
node(*FF, ["ffmpeg", "bundled binary"], fill=ALT_FILL, edge=ALT_EDGE)
node(*GEM, ["Gemini API", "audio understanding", "JSON chat · diarization"], fill=ALT_FILL, edge=ALT_EDGE)
node(*GROQ, ["Groq API", "whisper-large-v3"], fill=ALT_FILL, edge=ALT_EDGE)

STATE = (0.55, 1.20, 3.55, 2.10)
group(*STATE, "Session state — app.py")
ST1 = (0.72, 2.36, 3.20, 0.40)
ST2 = (0.72, 1.88, 3.20, 0.40)
ST3 = (0.72, 1.40, 3.20, 0.40)
node(*ST1, ["audio clip"], size=7.0)
node(*ST2, ["transcript + speakers"], size=7.0)
node(*ST3, ["notes (edited)"], size=7.0)

CONF = (12.70, 7.45, 2.60, 1.90)
group(*CONF, "Configuration")
CF1 = (12.86, 8.52, 2.28, 0.38)
CF2 = (12.86, 8.02, 2.28, 0.38)
CF3 = (12.86, 7.56, 2.28, 0.38)
node(*CF1, ["credentials.py"], size=6.8)
node(*CF2, [".env"], size=6.8)
node(*CF3, ["Streamlit secrets"], size=6.8)

# ------------------------------------------------------------------ edges ----
# browser -> app
flow([(BROWSER[0] + BROWSER[2], 8.85), (APP[0], 8.85)],
     label="WAV clip", label_at=(4.68, 9.02))

# app -> pipeline.py
flow([(8.95, APP[1]), (8.95, PIPELINE[1] + PIPELINE[3])],
     label="audio bytes", label_at=(9.80, 8.24))

# pipeline.py -> audio.py
flow([(PIPELINE[0] + 0.55, PIPELINE[1]), (PIPELINE[0] + 0.55, 7.12),
      (AUDIO[0] + AUDIO[2] - 0.55, 7.12), (AUDIO[0] + AUDIO[2] - 0.55, AUDIO[1] + AUDIO[3])],
     label="clip", label_at=(6.55, 7.28))

# audio.py -> transcription.py
flow([(AUDIO[0] + AUDIO[2], 6.34), (TRANS[0], 6.34)],
     label="prepared audio", label_at=(8.32, 6.50))

# transcription.py -> diarization.py
flow([(TRANS[0] + 0.42, TRANS[1]), (TRANS[0] + 0.42, 5.58),
      (DIA[0] + DIA[2] - 0.42, 5.58), (DIA[0] + DIA[2] - 0.42, DIA[1] + DIA[3])],
     label="if engine = groq", label_at=(8.05, 5.74), dashed=True)

# app -> note_generator.py (right channel)
flow([(APP[0] + APP[2], 8.72), (12.60, 8.72), (12.60, 4.74), (NOTES[0] + NOTES[2], 4.74)],
     label="transcript text", label_at=(12.60, 6.75), rotate=90, dashed=True)

# pipeline results -> app (left channel)
flow([(5.05, PIPELINE[1] + PIPELINE[3]), (5.05, APP[1])],
     label="transcript + notes", label_at=(5.05, 6.90), rotate=90)

# app <-> session state (far left channel)
flow([(APP[0], 8.68), (3.78, 8.68), (3.78, 2.08), (ST2[0] + ST2[2], 2.08)],
     label="read / write", label_at=(3.78, 5.20), rotate=90, dashed=True, both=True)

# provider gap rows (each connector owns one height)
flow([(DIA[0] + 0.45, DIA[1]), (DIA[0] + 0.45, 3.82), (GEM[0] + 0.35, 3.82),
      (GEM[0] + 0.35, GEM[1] + GEM[3])],
     label="audio, once more", label_at=(6.30, 3.98))
flow([(NOTES[0] + 0.55, NOTES[1]), (NOTES[0] + 0.55, 3.58), (GEM[0] + 1.75, 3.58),
      (GEM[0] + 1.75, GEM[1] + GEM[3])],
     label="transcript", label_at=(9.55, 3.74), dashed=True)
flow([(TRANS[0] + TRANS[2] - 0.55, TRANS[1]), (TRANS[0] + TRANS[2] - 0.55, 3.34),
      (GROQ[0] + GROQ[2] / 2, 3.34), (GROQ[0] + GROQ[2] / 2, GROQ[1] + GROQ[3])],
     label="whisper-large-v3", label_at=(10.85, 3.50))
flow([(AUDIO[0] + 0.55, AUDIO[1]), (AUDIO[0] + 0.55, 3.10), (FF[0] + FF[2] / 2, 3.10),
      (FF[0] + FF[2] / 2, FF[1] + FF[3])],
     label="transcode if large", label_at=(5.65, 3.26))

# configuration -> pipeline (right channel, dashed)
flow([(13.10, CONF[1]), (13.10, 6.95), (PIPE[0] + PIPE[2], 6.95)],
     label="keys · models", label_at=(13.10, 7.02), rotate=90, dashed=True)

fig.savefig(Path(__file__).resolve().parent / "architecture.png", dpi=200,
            facecolor=BG, bbox_inches="tight", pad_inches=0.22)
print("saved docs/architecture.png")


# =============================================================================
# Slide-ready strip: docs/request-lifecycle.png
# =============================================================================
STEPS = [
    ("1  record", "browser clip", "audio_input\nor upload"),
    ("2  validate", "type · size · time", "sniff MIME\nprobe duration"),
    ("3  prepare", "fit API limits", "mono 16 kHz MP3\nonly if large"),
    ("4  transcribe", "speech → text", "Gemini audio\nor Groq Whisper"),
    ("5  diarize", "who spoke when", "audio-based turns\naligned by overlap"),
    ("6  transcript", "speaker + time", "cards · filter\ncopy · export"),
    ("7  notes", "transcript only", "summary, decisions\nactions, questions"),
    ("8  export", "your edited copy", ".md · .txt\nbundle"),
]

FW, FH = 15.6, 3.3
fig2, ax2 = plt.subplots(figsize=(FW, FH), dpi=200)
fig2.patch.set_facecolor(BG)
ax2.set_facecolor(BG)
ax2.set_xlim(0, FW)
ax2.set_ylim(0, FH)
ax2.set_aspect("equal")
ax2.axis("off")

ax2.text(0.55, 2.92, "VoiceNote AI — request lifecycle", fontsize=12.6, fontweight="bold",
         color=TEXT, va="center", ha="left")
ax2.text(0.57, 2.62, "one recording, eight steps, three external services", fontsize=7.6,
         color=MUTED, va="center", ha="left")

STEP_W, STEP_GAP, STEP_Y, STEP_H = 1.72, 0.15, 1.22, 1.02
for index, (title, claim, detail) in enumerate(STEPS):
    x = 0.55 + index * (STEP_W + STEP_GAP)
    ax2.add_patch(
        FancyBboxPatch((x, STEP_Y), STEP_W, STEP_H,
                       boxstyle="round,pad=0,rounding_size=0.05",
                       facecolor=NODE_FILL, edgecolor=NODE_EDGE, linewidth=1.0, zorder=3)
    )
    ax2.text(x + 0.12, STEP_Y + STEP_H - 0.18, title, fontsize=6.5, color=MUTED,
             va="center", ha="left", zorder=4)
    ax2.text(x + 0.12, STEP_Y + STEP_H - 0.42, claim, fontsize=7.6, fontweight="bold",
             color=TEXT, va="center", ha="left", zorder=4)
    ax2.text(x + 0.12, STEP_Y + 0.22, detail, fontsize=6.4, color=SUB, va="center",
             ha="left", zorder=4, linespacing=1.45)
    if index < len(STEPS) - 1:
        ax2.add_patch(
            FancyArrowPatch((x + STEP_W + 0.02, STEP_Y + STEP_H / 2),
                            (x + STEP_W + STEP_GAP - 0.02, STEP_Y + STEP_H / 2),
                            arrowstyle="-|>,head_width=2.2,head_length=3.6",
                            color=EDGE, lw=0.9, shrinkA=0, shrinkB=0, zorder=6)
        )

ax2.text(0.55, 0.66,
         "Gemini does steps 4–5 in one audio call; with Whisper, step 4 comes from Groq and step 5 "
         "reuses the same clip.", fontsize=7.2, color=MUTED, va="center", ha="left")

fig2.savefig(Path(__file__).resolve().parent / "request-lifecycle.png", dpi=200,
             facecolor=BG, bbox_inches="tight", pad_inches=0.2)
print("saved docs/request-lifecycle.png")
