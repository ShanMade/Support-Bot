"""Contract tests for the provider calls, using a local mock HTTP server.

We cannot call the real APIs without credentials, so these tests check the exact
request our code sends (model, audio part, JSON mode, multipart fields) and that the
response parsing works. Replace the mock with real keys and the same code path talks
to the real service.

Run with:  python -m pytest -q
"""

from __future__ import annotations

import io
import json
import threading
import wave
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import urlparse

import pytest

from services import gemini, transcription
from services.audio import AudioPayload
from services.config import Settings

GEMINI_RESPONSE = {
    "language": "en",
    "segments": [
        {"start": 0.0, "end": 2.4, "speaker": "Speaker 1", "text": "Good morning everyone."},
        {"start": 2.5, "end": 5.1, "speaker": "Speaker 2", "text": "Morning. Let's start."},
    ],
}

GROQ_RESPONSE = {
    "text": "Good morning everyone. Morning.",
    "language": "en",
    "duration": 5.1,
    "segments": [
        {"id": 0, "start": 0.0, "end": 2.4, "text": "Good morning everyone."},
        {"id": 1, "start": 2.5, "end": 5.1, "text": "Morning."},
    ],
}


class _Recorder(BaseHTTPRequestHandler):
    requests: list[dict] = []
    reply: dict = {}

    def do_POST(self):  # noqa: N802 - http.server API
        length = int(self.headers.get("Content-Length", 0))
        body = self.rfile.read(length)
        _Recorder.requests.append(
            {
                "path": urlparse(self.path).path,
                "content_type": self.headers.get("Content-Type", ""),
                "body": body,
            }
        )
        payload = json.dumps(_Recorder.reply).encode()
        self.send_response(200)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(payload)))
        self.end_headers()
        self.wfile.write(payload)

    def do_GET(self):  # noqa: N802
        payload = json.dumps({"models": []}).encode()
        self.send_response(200)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(payload)))
        self.end_headers()
        self.wfile.write(payload)

    def log_message(self, *_args):  # silence the test output
        return


@pytest.fixture()
def mock_server():
    _Recorder.requests = []
    server = ThreadingHTTPServer(("127.0.0.1", 0), _Recorder)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        yield f"http://127.0.0.1:{server.server_address[1]}"
    finally:
        server.shutdown()
        server.server_close()


def _wav(seconds: float = 2.0, rate: int = 16000) -> bytes:
    buffer = io.BytesIO()
    with wave.open(buffer, "wb") as handle:
        handle.setnchannels(1)
        handle.setsampwidth(2)
        handle.setframerate(rate)
        handle.writeframes(b"\x01\x00" * int(rate * seconds))
    return buffer.getvalue()


def _payload(seconds: float = 2.0) -> AudioPayload:
    data = _wav(seconds)
    return AudioPayload(data=data, mime="audio/wav", filename="recording.wav", duration=seconds)


def test_gemini_request_shape_and_parsing(mock_server, monkeypatch):
    from google import genai
    from google.genai import types

    def fake_client(api_key: str, timeout_s: int):
        return genai.Client(
            api_key=api_key,
            http_options=types.HttpOptions(base_url=mock_server, timeout=timeout_s * 1000),
        )

    monkeypatch.setattr(gemini, "get_client", fake_client)
    _Recorder.reply = {
        "candidates": [
            {"content": {"role": "model", "parts": [{"text": json.dumps(GEMINI_RESPONSE)}]},
             "finishReason": "STOP"}
        ],
        "usageMetadata": {"promptTokenCount": 10, "candidatesTokenCount": 20, "totalTokenCount": 30},
    }

    settings = Settings(gemini_api_key="test-key", gemini_model="gemini-test")
    transcript = transcription.transcribe(_payload(), settings)

    request = _Recorder.requests[-1]
    assert request["path"].endswith(":generateContent")
    body = json.loads(request["body"])
    parts = body["contents"][0]["parts"]
    inline = next(part for part in parts if "inlineData" in part)["inlineData"]
    # The SDK serialises the part as audio bytes + MIME type (snake_case field).
    assert (inline.get("mimeType") or inline.get("mime_type")) == "audio/wav"
    assert inline["data"]
    assert body["generationConfig"]["responseMimeType"] == "application/json"
    assert body["systemInstruction"]

    assert [s.speaker for s in transcript.segments] == ["Speaker 1", "Speaker 2"]
    assert transcript.diarized is True
    assert transcript.language == "en"


def test_gemini_diarization_pass_when_using_groq(mock_server, monkeypatch):
    """Groq transcription + Gemini speaker turns must be aligned end to end."""
    import groq as groq_module
    from google import genai
    from google.genai import types

    def fake_client(api_key: str, timeout_s: int):
        return genai.Client(
            api_key=api_key,
            http_options=types.HttpOptions(base_url=mock_server, timeout=timeout_s * 1000),
        )

    real_groq = groq_module.Groq

    def fake_groq(**kwargs):
        return real_groq(api_key=kwargs["api_key"], base_url=f"{mock_server}/openai/v1",
                         timeout=kwargs.get("timeout"))

    monkeypatch.setattr(gemini, "get_client", fake_client)
    monkeypatch.setattr(groq_module, "Groq", fake_groq)

    settings = Settings(
        gemini_api_key="test-key",
        groq_api_key="test-key",
        transcription_engine="groq",
        gemini_model="gemini-test",
        groq_model="whisper-large-v3-turbo",
    )

    _Recorder.reply = GROQ_RESPONSE
    groq_transcript = transcription._groq_transcribe(_payload(5.0), settings, lambda *_: None)
    assert groq_transcript.stt_provider == "groq"
    assert len(groq_transcript.segments) == 2
    body = _Recorder.requests[-1]["body"]
    assert b"whisper-large-v3-turbo" in body
    assert b"verbose_json" in body

    from services.diarization import diarize_and_align

    _Recorder.reply = {
        "candidates": [
            {"content": {"parts": [{"text": json.dumps(
                {"speaker_count": 2,
                 "turns": [{"start": 0.0, "end": 2.45, "speaker": 1},
                           {"start": 2.45, "end": 5.1, "speaker": 2}]}
            )}]}, "finishReason": "STOP"}
        ]
    }
    transcript = diarize_and_align(groq_transcript, _payload(5.0), settings)
    assert transcript.diarized is True
    assert [s.speaker for s in transcript.segments] == ["Speaker 1", "Speaker 2"]


def test_note_generation_request_and_parsing(mock_server, monkeypatch):
    from google import genai
    from google.genai import types

    def fake_client(api_key: str, timeout_s: int):
        return genai.Client(
            api_key=api_key,
            http_options=types.HttpOptions(base_url=mock_server, timeout=timeout_s * 1000),
        )

    monkeypatch.setattr(gemini, "get_client", fake_client)
    notes_payload = {
        "title": "Budget review",
        "summary": "Travel spend was reviewed.",
        "topics": ["Budget"],
        "key_points": ["Travel is over plan"],
        "decisions": ["Cut travel by 10%"],
        "action_items": [{"task": "Send revised plan", "owner": "Sana", "due": "Friday"}],
        "open_questions": [],
        "cleaned_transcript": "**Speaker 1:** Let's review the budget.",
    }
    _Recorder.reply = {
        "candidates": [
            {"content": {"parts": [{"text": json.dumps(notes_payload)}]}, "finishReason": "STOP"}
        ]
    }

    from services.models import Segment, Transcript
    from services.note_generator import generate_notes

    transcript = Transcript(
        segments=[Segment(0, 2, "Let's review the budget.", "Speaker 1")],
        duration=2.0,
        diarized=True,
    )
    settings = Settings(gemini_api_key="test-key", gemini_model="gemini-test")
    notes = generate_notes(transcript, settings)

    body = json.loads(_Recorder.requests[-1]["body"])
    prompt = body["contents"][0]["parts"][0]["text"]
    assert "Let's review the budget." in prompt
    assert "[00:00] Speaker 1" in prompt
    assert body["generationConfig"]["responseMimeType"] == "application/json"
    assert "never invent" in body["systemInstruction"]["parts"][0]["text"].lower()

    assert notes.title == "Budget review"
    assert notes.action_items[0].owner == "Sana"
    assert notes.decisions == ["Cut travel by 10%"]


def test_gemini_error_is_mapped_to_helpful_provider_error(monkeypatch):
    custom_reply = {"error": {"code": 403, "message": "API key not valid", "status": "PERMISSION_DENIED"}}

    class _ErrorServer(_Recorder):
        def do_POST(self):  # noqa: N802
            payload = json.dumps(custom_reply).encode()
            self.send_response(403)
            self.send_header("Content-Type", "application/json")
            self.send_header("Content-Length", str(len(payload)))
            self.end_headers()
            self.wfile.write(payload)

    server = ThreadingHTTPServer(("127.0.0.1", 0), _ErrorServer)
    threading.Thread(target=server.serve_forever, daemon=True).start()
    base = f"http://127.0.0.1:{server.server_address[1]}"

    from google import genai
    from google.genai import types

    monkeypatch.setattr(
        gemini,
        "get_client",
        lambda api_key, timeout_s: genai.Client(
            api_key=api_key, http_options=types.HttpOptions(base_url=base, timeout=timeout_s * 1000)
        ),
    )

    from services.errors import ProviderError

    with pytest.raises(ProviderError) as error:
        gemini.generate_text("bad-key", "gemini-test", "prompt", timeout_s=5)
    assert error.value.hint and "aistudio.google.com" in error.value.hint

    server.shutdown()
    server.server_close()
