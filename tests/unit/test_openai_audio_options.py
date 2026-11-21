"""OpenAI-compatible audio endpoints must forward voice/language/translate options."""

import asyncio
import io
import json
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock

from fastapi import UploadFile

from vocal_core.adapters.stt.base import STTAdapter, TranscriptionResult
from vocal_core.adapters.tts.base import TTSAdapter, TTSResult

_LANGUAGE = "he"


class _RecordingSTT(STTAdapter):
    def __init__(self) -> None:
        self.calls: list[dict] = []

    async def load_model(self, model_path: Path, device: str = "auto", **kwargs) -> None:
        pass

    async def unload_model(self) -> None:
        pass

    def is_loaded(self) -> bool:
        return True

    def get_model_info(self) -> dict:
        return {"status": "loaded"}

    async def transcribe(self, audio, **kwargs) -> TranscriptionResult:
        self.calls.append(kwargs)
        return TranscriptionResult(text="hello", language=kwargs.get("language") or "en", duration=1.0)


class _RecordingTTS(TTSAdapter):
    def __init__(self) -> None:
        self.calls: list[dict] = []

    async def load_model(self, model_path: Path, device: str = "auto", **kwargs) -> None:
        pass

    async def unload_model(self) -> None:
        pass

    def is_loaded(self) -> bool:
        return True

    def get_model_info(self) -> dict:
        return {"status": "loaded"}

    async def synthesize(self, text: str, **kwargs) -> TTSResult:
        self.calls.append(kwargs)
        return TTSResult(audio_data=b"audio", sample_rate=24000, duration=1.0, format="wav")

    async def synthesize_stream(self, text: str, **kwargs):
        self.calls.append(kwargs)
        yield b"audio"

    async def get_voices(self):
        return []


def _registry():
    registry = MagicMock()
    model_info = MagicMock()
    model_info.task.value = "tts"
    registry.get_model = AsyncMock(return_value=model_info)
    registry.get_model_path = MagicMock(return_value=Path("."))
    return registry


def _upload(name: str = "audio.wav") -> UploadFile:
    return UploadFile(file=io.BytesIO(b"fake-audio"), filename=name)


def _make_transcription_service(adapter, monkeypatch):
    from vocal_api.services.transcription_service import TranscriptionService

    monkeypatch.setattr("vocal_api.services.transcription_service.assert_in_process_runtime", lambda _: None)
    service = TranscriptionService(registry=_registry())

    async def _get_or_create(*args, **kwargs):
        return adapter

    monkeypatch.setattr(service, "_get_or_create_adapter", _get_or_create)
    return service


def _make_tts_service(adapter, monkeypatch):
    from vocal_api.services.tts_service import TTSService

    monkeypatch.setattr("vocal_api.services.tts_service.assert_in_process_runtime", lambda _: None)
    service = TTSService(registry=_registry())

    async def _get_or_create(*args, **kwargs):
        return adapter

    monkeypatch.setattr(service, "_get_or_create_adapter", _get_or_create)
    return service


def test_translate_forwards_language_and_temperature(monkeypatch):
    from vocal_api.models.transcription import TranscriptionRequest

    adapter = _RecordingSTT()
    service = _make_transcription_service(adapter, monkeypatch)
    request = TranscriptionRequest(model="Systran/faster-whisper-tiny", language=_LANGUAGE, temperature=0.25)

    result = asyncio.run(service.translate(_upload(), request))

    assert result.text == "hello"
    assert result.task == "translate"
    assert adapter.calls == [{"language": _LANGUAGE, "task": "translate", "temperature": 0.25, "prompt": None}]


def test_transcribe_forwards_prompt_and_granularities(monkeypatch):
    from vocal_api.models.transcription import TranscriptionRequest

    adapter = _RecordingSTT()
    service = _make_transcription_service(adapter, monkeypatch)
    request = TranscriptionRequest(model="Systran/faster-whisper-tiny", prompt="Voice: Aria", timestamp_granularities=["word"])

    result = asyncio.run(service.transcribe(_upload(), request))

    assert result.task == "transcribe"
    assert adapter.calls[0]["prompt"] == "Voice: Aria"
    assert adapter.calls[0]["word_timestamps"] is True


def test_synthesize_forwards_language(monkeypatch):
    adapter = _RecordingTTS()
    service = _make_tts_service(adapter, monkeypatch)

    asyncio.run(service.synthesize("model", "hello", voice="v", language=_LANGUAGE))

    assert adapter.calls[0]["language"] == _LANGUAGE


def test_synthesize_stream_forwards_language(monkeypatch):
    adapter = _RecordingTTS()
    service = _make_tts_service(adapter, monkeypatch)

    async def _collect():
        return [chunk async for chunk in service.synthesize_stream("model", "hello", language=_LANGUAGE)]

    assert asyncio.run(_collect()) == [b"audio"]
    assert adapter.calls[0]["language"] == _LANGUAGE


class _FakeWebSocket:
    def __init__(self) -> None:
        self.sent: list[dict] = []

    async def send_text(self, text: str) -> None:
        self.sent.append(json.loads(text))


def _apply_session_update(event: dict) -> tuple:
    from vocal_api.routes.realtime import _handle_session_update, _Session

    session = _Session()
    ws = _FakeWebSocket()
    asyncio.run(_handle_session_update(ws, session, event, "session.update"))
    return session, ws.sent[-1]


def test_realtime_accepts_flat_voice_and_language():
    session, ack = _apply_session_update({"session": {"language": _LANGUAGE, "tts_voice": "alloy"}})

    assert session.language == _LANGUAGE
    assert session.tts_voice == "alloy"
    assert ack["session"]["audio"]["output"]["voice"] == "alloy"


def test_realtime_accepts_nested_openai_shape():
    event = {
        "session": {
            "audio": {
                "input": {"transcription": {"model": "stt-model", "language": _LANGUAGE}},
                "output": {"model": "tts-model", "voice": "alloy"},
            }
        }
    }

    session, _ = _apply_session_update(event)

    assert session.model == "stt-model"
    assert session.tts_model == "tts-model"
    assert session.language == _LANGUAGE
    assert session.tts_voice == "alloy"


def _transcription_response():
    from vocal_api.models.transcription import TranscriptionResponse, TranscriptionSegment

    return TranscriptionResponse(
        task="transcribe",
        text="Hello world",
        language="en",
        duration=2.5,
        segments=[
            TranscriptionSegment(id=0, start=0.0, end=1.25, text="Hello"),
            TranscriptionSegment(id=1, start=1.25, end=2.5, text="world"),
        ],
    )


def test_render_text_returns_plain_text():
    from fastapi import Response

    from vocal_api.models.transcription import TranscriptionFormat
    from vocal_api.routes.transcription import _render_result

    rendered = _render_result(_transcription_response(), TranscriptionFormat.TEXT)

    assert isinstance(rendered, Response)
    assert rendered.body == b"Hello world"
    assert rendered.media_type == "text/plain; charset=utf-8"


def test_render_srt_uses_comma_timestamps():
    from vocal_api.models.transcription import TranscriptionFormat
    from vocal_api.routes.transcription import _render_result

    rendered = _render_result(_transcription_response(), TranscriptionFormat.SRT)
    body = rendered.body.decode()

    assert "1\n00:00:00,000 --> 00:00:01,250\nHello" in body
    assert "2\n00:00:01,250 --> 00:00:02,500\nworld" in body


def test_render_vtt_uses_dot_timestamps():
    from vocal_api.models.transcription import TranscriptionFormat
    from vocal_api.routes.transcription import _render_result

    rendered = _render_result(_transcription_response(), TranscriptionFormat.VTT)
    body = rendered.body.decode()

    assert rendered.media_type == "text/vtt; charset=utf-8"
    assert body.startswith("WEBVTT")
    assert "00:00:00.000 --> 00:00:01.250" in body


def test_render_json_returns_structured_response():
    from vocal_api.models.transcription import TranscriptionFormat, TranscriptionResponse
    from vocal_api.routes.transcription import _render_result

    rendered = _render_result(_transcription_response(), TranscriptionFormat.VERBOSE_JSON)

    assert isinstance(rendered, TranscriptionResponse)
    assert rendered.task == "transcribe"
