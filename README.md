# VoiceNote AI

**Record a conversation → get a speaker-labelled transcript → get structured meeting notes.**

A small, complete GenAI project for a university / college course demo. Streamlit front end,
Google Gemini and Groq Whisper behind it, no database, no login, nothing written to disk.

```
Record ──► Transcribe + identify speakers ──► Generate AI notes ──► Edit & export
```

---

## 1. What it actually does (and what it does not)

| Feature | Reality in this build |
| --- | --- |
| Microphone recording | Browser recording through Streamlit's `st.audio_input`. One WAV clip is uploaded **when you stop**. |
| "Live" transcription | **Not word-by-word.** The widget never exposes partial audio, so transcription starts the moment you press stop (a few seconds for short clips) and the whole transcript appears at once. The UI says this explicitly; there is no fake streaming text. |
| Speaker identification | Real diarization: Gemini listens to the audio and returns speaker turns (`Speaker 1`, `Speaker 2`, …) with timestamps. Never identity, never names, never random/alternating labels. |
| Timestamps | Shown per segment from the provider (Groq segment timestamps or Gemini second-level timestamps). |
| AI notes | Gemini writes title, summary, topics, key takeaways, decisions, action items, open questions and a cleaned transcript **from the transcript only**, with explicit "not mentioned" handling instead of invention. |
| Editing / copying / export | Every notes field is editable, plus copy-to-clipboard blocks and Markdown/TXT downloads (transcript, notes, bundle) and an audio download. |
| Persistence | Everything lives in Streamlit session state. Closing the tab discards audio, transcript and notes. |

---

## 2. Architecture

```
app.py                      Streamlit UI only (layout, state, buttons, exports)
├── components/
│   ├── recording.py        microphone / upload widget -> Capture
│   ├── transcript_view.py  speaker legend + transcript rows
│   ├── notes_view.py       notes preview + inline editor + action-item table
│   ├── layout.py           brand, status chip, workflow steps, card headers, footer
│   └── styles.py           design tokens + CSS + speaker palettes
└── services/               all provider-specific code
    ├── credentials.py      optional in-code keys/settings (edit this to run from code)
    ├── config.py           .env -> secrets -> credentials.py, defaults, model lists
    ├── audio.py            validation, WAV duration, ffmpeg conversion, size limits
    ├── transcription.py    Gemini STT+diarization, Groq Whisper STT
    ├── diarization.py      Gemini speaker turns + overlap alignment to Whisper segments
    ├── note_generator.py   prompt, JSON parsing, guardrails
    ├── gemini.py           the only module that imports google-genai
    ├── pipeline.py         validate -> transcribe -> diarize
    ├── export.py           Markdown / TXT builders
    ├── models.py           Segment, Transcript, SpeakerTurn, Notes dataclasses
    ├── json_utils.py       tolerant JSON parsing
    └── errors.py           user-facing error types (message + hint)
```

**Data flow**

1. `st.audio_input` returns one clip → `services.pipeline.build_payload` validates type, size
   and duration and measures the length.
2. **Gemini engine:** one `generateContent` call with the audio inline; the prompt asks for
   `{language, segments[{start, end, speaker, text}]}` and Gemini does transcription *and*
   diarization while listening.
3. **Groq engine:** `audio.transcriptions.create` with `response_format="verbose_json"` and
   segment timestamps. Whisper has no diarization, so a second Gemini pass returns speaker
   turns, which are aligned to the Whisper segments by timestamp overlap.
4. Speakers are renumbered to `Speaker 1..N` in order of first appearance.
5. `Generate AI Notes` sends the transcript as text to Gemini with a strict JSON contract.
6. Edits happen in the Streamlit widgets; exports are built from those edited values.

Nothing is re-requested on a Streamlit rerun: each clip has a SHA-256 fingerprint plus a
settings fingerprint (`engine | model | language | diarization`), and a result is reused
until one of those changes.

---

## 3. Providers and keys

| Purpose | Provider | Model | Paid account? |
| --- | --- | --- | --- |
| Transcription + speaker diarization | Google Gemini API | any chat model your key exposes (default `gemini-2.5-flash`; the model picker lists what your key can use) | No — the free tier is enough for a class demo |
| Fast transcription (optional engine) | Groq | `whisper-large-v3-turbo` (default) or `whisper-large-v3` | No — free tier: 20 requests/min, 7.2k audio-seconds/min, 28.8k audio-seconds/day per model |
| Note generation | Google Gemini API | same Gemini model | No |

* Gemini key: <https://aistudio.google.com/apikey>
* Groq key: <https://console.groq.com/keys>

A Gemini key is required for speaker labels and for AI notes. A Groq key is optional and only
adds a second transcription engine.

**Where keys live.** All configuration is backend-only - the UI never shows keys, provider
names or environment variables. Pick whichever of these fits:

1. `services/credentials.py` - constants at the top of the file (quickest for a local demo),
2. `.env` (git-ignored) - recommended for a repo you push,
3. Streamlit **Secrets** - required on Community Cloud.

Resolution order is `.env` → Streamlit secrets → `services/credentials.py`, and nothing is
ever logged or rendered. If a key is missing, the page stays usable and only the affected
action reports what is needed.

---

## 4. Interface

One column of cards, no sidebar, no API talk - everything backend-related is behind
**Settings** or in this README.

```
┌ VoiceNote AI ────────────────────  ● Ready   [Settings] [New] ┐
│  1 Capture · 2 Transcribe · 3 Notes · 4 Export                │
│                                                               │
│  ┌ Capture ─────────────────────────────────────────────────┐ │
│  │  [Microphone | Upload]        ◉ record                    │ │
│  └───────────────────────────────────────────────────────────┘ │
│  ┌ Transcript ──────── 2 speakers · 6m 12s · 940 words ──────┐ │
│  │  [Speaker 1 · 00:00] [Speaker 2 · 00:14]   (filter)       │ │
│  │  S1  Speaker 1  00:00   Good morning everyone…             │ │
│  └───────────────────────────────────────────────────────────┘ │
│  ┌ AI Notes ──────────────┐  ┌ Export ───────────────────────┐ │
│  │  title, summary,       │  │ [Notes .md] [Notes .txt]      │ │
│  │  decisions, actions…   │  │ [Everything .md] [Audio]      │ │
│  └────────────────────────┘  └───────────────────────────────┘ │
└───────────────────────────────────────────────────────────────┘
```

Visual rules used throughout: light canvas (`#f7f8fc`), white cards with hairline borders and
one soft shadow, a single indigo accent (`#4f46e5`), 14 px card radius, compact type scale, and
speaker colours drawn from a fixed six-colour palette so a speaker keeps the same colour for the
whole transcript.

---

## 5. Run it locally (Windows PowerShell)

```powershell
# 1. Get the code
git clone https://github.com/<your-user>/Voice-To-Note.git
cd Voice-To-Note

# 2. Virtual environment (Python 3.11 or 3.12)
py -3.11 -m venv .venv
.\.venv\Scripts\Activate.ps1
# If PowerShell blocks the script, run once:
#   Set-ExecutionPolicy -Scope Process -ExecutionPolicy Bypass

# 3. Dependencies
python -m pip install --upgrade pip
pip install -r requirements.txt

# 4. Configuration - either fill in services/credentials.py,
#    or copy the template and use .env instead
Copy-Item .env.example .env
notepad .env          # paste GEMINI_API_KEY (and GROQ_API_KEY if you want Whisper)

# 5. Run
streamlit run app.py
```

The app opens at <http://localhost:8501>. `localhost` counts as a secure context, so the
microphone works without HTTPS.

macOS / Linux:

```bash
python3.11 -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env      # then edit .env
streamlit run app.py
```

ffmpeg is **not** a manual install: `imageio-ffmpeg` ships a static binary, which the app uses
to measure/compress audio. On Windows PowerShell the bundled binary works out of the box.

---

## 6. Configuration

Backend only - nothing here appears in the interface.

Read from environment variables (`.env`), then Streamlit secrets, then the constants in
`services/credentials.py`. Anything left empty falls back to the defaults below.

| Variable | Default | Meaning |
| --- | --- | --- |
| `GEMINI_API_KEY` | – | Google AI Studio key (required for diarization + notes) |
| `GEMINI_MODEL` | `gemini-2.5-flash` | Gemini model; the in-app model picker lists what your key can use |
| `GROQ_API_KEY` | – | Optional Groq key for the Whisper engine |
| `GROQ_MODEL` | `whisper-large-v3-turbo` | or `whisper-large-v3` |
| `TRANSCRIPTION_ENGINE` | `gemini` | `gemini` or `groq` |
| `DIARIZATION` | `auto` | `auto` (Gemini speaker turns) or `off` |
| `LANGUAGE` | `auto` | ISO-639-1 code (`en`, `ur`, `ar`, `hi`, …) or `auto` |
| `MAX_UPLOAD_MB` | `200` | Upload guard |
| `MAX_AUDIO_SECONDS` | `3600` | Recording length guard |
| `STT_TIMEOUT` | `120` | Seconds per transcription/diarization request |
| `LLM_TIMEOUT` | `180` | Seconds per note-generation request |

`Settings.load()` accepts a `TRANSCRIPTION_ENGINE=groq` configuration even when no Groq key is
present: it silently falls back to Gemini.

---

## 7. Deploy to Streamlit Community Cloud

1. Push this repository to GitHub (keep `.env` out of it).
2. Go to <https://share.streamlit.io> → **Create app** → pick the repo, branch `main`,
   main file `app.py`.
3. **Advanced settings → Python version: 3.11** (or 3.12). The repo also ships
   `runtime.txt` (`python-3.11`) so the runtime matches the pinned wheels.
4. **Secrets** — paste the same keys you use locally, in TOML form (no quotes around numbers):

   ```toml
   GEMINI_API_KEY = "your_gemini_api_key"
   GEMINI_MODEL = "gemini-2.5-flash"
   GROQ_API_KEY = "your_groq_api_key"
   GROQ_MODEL = "whisper-large-v3-turbo"
   TRANSCRIPTION_ENGINE = "gemini"
   DIARIZATION = "auto"
   LANGUAGE = "auto"
   ```

5. Deploy. Community Cloud serves over HTTPS, which is what the browser microphone API needs.
6. Open the app URL → allow microphone access when Chrome/Firefox/Edge asks.

Notes for the cloud:
* Everything runs in-process; the only files needed are the repo files. No local paths, no
  local models, no downloads at runtime.
* `imageio-ffmpeg` installs its binary as a normal wheel on Cloud's Linux image.
* A sleeping free app takes ~30–60 s to wake before the first click.

---

## 8. Microphone / browser notes

* Microphone capture requires a **secure context**: `https://` (Community Cloud, any tunnel)
  or `http://localhost`. Plain `http://192.168.x.x` will not work.
* Works best in Chrome, Edge, Firefox or Safari 15+. If the record button is unresponsive,
  check the browser's site permissions and that no other app has exclusive access to the mic.
* Recording stops when you press the stop button; the clip uploads immediately afterwards.
  Very long clips are compressed to mono 16 kHz MP3 before being sent, to stay inside the
  provider limits.

---

## 9. Tests

Everything below was run in the development sandbox (no real API keys available there):

```bash
pip install -r requirements-dev.txt                   # pytest + ruff (optional)
python -m compileall -q app.py services components    # syntax/import check
ruff check .                                          # lint (clean)
python -m pytest -q                                   # 28 unit + contract tests
streamlit run app.py                                  # boots, HTTP 200, /_stcore/health = ok
```

`tests/test_units.py` (24 tests) covers timestamp formatting, segment grouping, speaker renumbering,
provider JSON parsing (Gemini transcript, Groq `verbose_json`, diarization turns), overlap
alignment, note parsing (including empty sections), exports, audio validation/duration and
missing-key errors.

`tests/test_provider_contract.py` (4 tests) starts a local mock HTTP server and asserts the **real
requests** the SDKs build: inline audio part + MIME type, `responseMimeType: application/json`,
system instruction, Groq multipart fields (`model`, `verbose_json`), Gemini prompt containing
the transcript, and 403 → helpful `ProviderError`. This proves the integration code is wired
correctly; it is not a substitute for a live call.

The app was also driven headless with Streamlit's `AppTest` across the real UI states: empty,
transcript-only, and transcript + notes. Checked there: every card renders, the source switcher
toggles microphone/upload, the settings popover writes engine/model/language/diarization, the
speaker filter re-renders the transcript, editing a field updates the preview immediately, all
download buttons appear, the transcript survives reruns, "Apply new settings" only appears after
a settings change, and a failed note generation keeps the transcript intact.

**Needs your credentials / a real microphone (not testable in the sandbox):**

* Real transcription accuracy and diarization quality with live voices.
* Real note quality and latency from Gemini.
* The browser microphone permission flow and rendering of the recorder widget.
* Any provider-side rate-limit or quota behaviour.

---

## 10. Limitations (say these out loud in the demo)

1. **No word-by-word streaming.** Streamlit's audio widget uploads a finished clip; true
   streaming would need a WebRTC component and a streaming provider, which is less reliable
   for a one-day deadline. The app labels this honestly instead of faking it.
2. **Speakers are anonymous clusters.** Similar voices can merge; quick interruptions or
   crosstalk can land on the wrong label. Diarization never tells you *who* someone is.
3. **Diarization runs after recording**, because it needs the complete clip. Timestamps come
   from the provider and are second-level.
4. **Gemini's diarization is model judgement, not a dedicated diarization model.** It handles
   two to four clear speakers well; chaotic overlapping audio degrades.
5. **Groq alone cannot label speakers.** Whisper has no diarization; without a Gemini key the
   transcript appears without speaker labels (the UI says so).
6. **Transcription errors propagate** into the notes. The prompt forbids invention and the
   transcript stays visible so the class can sanity-check.
7. **Free-tier limits** apply. A 25 MB Groq cap and a 20 MB Gemini inline-request cap are
   handled by compressing audio; extremely long recordings should be split.

---

## 11. Troubleshooting

| Symptom | Fix |
| --- | --- |
| "No Google Gemini API key is configured" | Put `GEMINI_API_KEY=...` in `.env` (local), in Streamlit Secrets (cloud) or in `services/credentials.py`, then restart Streamlit. |
| "No Groq API key is configured" | Only needed for the Whisper engine; add `GROQ_API_KEY` or switch to Gemini. |
| Errors on a specific `gemini-…` model | That model is not available to your key. Reload the page; the model picker (Settings) only lists what the key exposes. |
| Record button shows nothing / disabled | Site needs HTTPS or `localhost`, browser permission must be granted, and the mic must not be used by another app. |
| "This audio file could not be decoded" | Convert to WAV/MP3/M4A; ffmpeg may be missing if `imageio-ffmpeg` did not install. Re-run `pip install -r requirements.txt`. |
| Gemini 429 / Groq 429 | Free-tier rate limit. Wait a minute, shorten the clip, or switch engines. |
| Groq 413 / size errors | Lower bitrate happens automatically; for very long audio, split the recording. |
| Speaker labels look wrong | Expected limitation: similar voices or overlapping speech. Try a cleaner recording, or switch the transcription engine to Gemini (one-pass diarization). |
| Notes keep failing | The transcript is preserved. Retry with another Gemini model, or export the transcript. |
| App sleeps on Cloud | First request after idle can take 30–60 s. Open it once before class starts. |

---

## 12. Privacy and secrets

* Audio is sent to the selected provider (Gemini and/or Groq) for processing. Nothing else
  leaves the machine.
* Recordings live in memory/session state; nothing is written to the repository or to disk
  (only short-lived temp files during ffmpeg conversion, deleted immediately).
* `.gitignore` excludes `.env`, `.streamlit/secrets.toml`, keys and audio files.
* No API key is ever logged, displayed or included in an error message.
* **Keep keys out of committed code.** `services/credentials.py` is handy for a private local
  run, but if you push the repo the file goes with it - a key in a public repo is scraped within
  minutes. Preferred: `.env` locally and Secrets on Cloud; both are already ignored by git.

---

## 13. A 20-second explanation for class

> "VoiceNote AI is a Streamlit app that turns a recorded conversation into structured notes.
> The browser records one audio clip. It goes to Google Gemini's multimodal audio model, which
> returns the transcript with timestamps and, because it actually listens to the voices, groups
> speech into anonymous speakers — Speaker 1, Speaker 2. Alternatively, Groq's Whisper models
> do the transcription, and Gemini then aligns speaker turns to those segments. Finally, the
> transcript is passed as text to Gemini with a strict JSON schema: summary, topics, decisions,
> action items, open questions. The prompt forbids inventing anything, so if nobody agreed an
> action item, the notes say 'not mentioned'. Everything is editable and exportable as
> Markdown. The honest limitation is that this is clip-based, not word-by-word streaming: the
> recorder uploads when you stop, and I chose a reliable fallback over a fragile streaming
> demo."

Likely questions and short answers:

* *Why not Whisper locally?* Too slow and heavy for Streamlit Cloud, and no diarization.
* *Why Groq at all?* It is much faster and free, and shows a second real STT provider.
* *Is the speaker labelling random?* No — it comes from an audio model analysing voice
  characteristics, then re-numbered by first appearance.
* *What if a key is missing?* The app names the missing variable and keeps every result it
  already has; the transcript is never lost because of a notes failure.

---

## 14. Fastest end-to-end check before class

1. `pip install -r requirements.txt`, put the Gemini key in `.env` (or `services/credentials.py`),
   then `streamlit run app.py`.
2. Click the microphone, say two sentences in one voice, then two in another voice (or ask a
   classmate), and press stop.
3. Within a few seconds: transcript with `Speaker 1` / `Speaker 2` chips, timestamps and a
   speaker filter.
4. Press **Generate notes**; check the summary, decisions and action items.
5. Open **Edit notes**, change a decision or an action item - the preview updates immediately -
   then download `*.md` and confirm the edit is in the file.
6. Reload once: nothing is re-sent to the API and nothing already generated is lost (a reload
   starts a fresh session, which is expected).

Typical timing for a 60-second clip with Gemini: 5–15 s for transcription + diarization, 5–15 s
for notes.
