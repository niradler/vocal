import asyncio
import json
import logging
import tempfile
import wave
from pathlib import Path

from fastapi import APIRouter, WebSocket, WebSocketDisconnect

from vocal_core.adapters.vad import create_vad_adapter
from vocal_core.audio import StreamingVADGate
from vocal_core.config import vocal_settings

from ..dependencies import get_transcription_service

router = APIRouter(tags=["stream"])
logger = logging.getLogger(__name__)

_SILENCE_DURATION_S = vocal_settings.VAD_SILENCE_DURATION_S
_MAX_CHUNK_DURATION_S = 10.0
_PARTIAL_INTERVAL_S = vocal_settings.REALTIME_PARTIAL_INTERVAL_S
_PARTIAL_MIN_AUDIO_S = vocal_settings.REALTIME_PARTIAL_MIN_AUDIO_S
_PARTIAL_WINDOW_S = vocal_settings.REALTIME_PARTIAL_WINDOW_S


def _estimate_frame_seconds(pcm_bytes: bytes, sample_rate: int) -> float:
    return len(pcm_bytes) / 2 / sample_rate


def _write_wav(pcm_data: bytes, sample_rate: int) -> str:
    tmp = tempfile.NamedTemporaryFile(suffix=".wav", delete=False)
    tmp.close()
    with wave.open(tmp.name, "wb") as wf:
        wf.setnchannels(1)
        wf.setsampwidth(2)
        wf.setframerate(sample_rate)
        wf.writeframes(pcm_data)
    return tmp.name


async def _transcribe_pcm(service, pcm: bytes, model: str, language: str | None, task: str, sample_rate: int) -> str:
    async def _single_chunk_gen():
        yield pcm

    parts: list[str] = []
    async for seg in service.transcribe_live_stream(_single_chunk_gen(), model, sample_rate, language):
        text = seg.text.strip()
        if text:
            parts.append(text)
    return " ".join(parts).strip()


async def _flush_pcm(websocket: WebSocket, pcm_data: bytes, model: str, language: str | None, task: str, sample_rate: int, service) -> None:
    tmp_path = None
    try:
        tmp_path = _write_wav(pcm_data, sample_rate)
        full_text: list[str] = []
        async for seg in service.transcribe_stream_path(tmp_path, model, language, task):
            text = seg.text.strip()
            if text:
                await websocket.send_text(json.dumps({"type": "transcript.delta", "text": text}))
                full_text.append(text)

        await websocket.send_text(json.dumps({"type": "transcript.done", "text": " ".join(full_text).strip()}))
    except Exception as exc:
        logger.exception("Stream transcription error")
        await websocket.send_text(json.dumps({"type": "error", "message": str(exc)}))
    finally:
        if tmp_path:
            Path(tmp_path).unlink(missing_ok=True)


async def _live_stream_utterance(
    websocket: WebSocket,
    chunk_q: asyncio.Queue,
    model: str,
    language: str | None,
    sample_rate: int,
    service,
) -> None:
    """Transcribe one VAD-delimited utterance via transcribe_live_stream."""

    async def _chunk_gen():
        while True:
            item = await chunk_q.get()
            if item is None:
                return
            yield item

    try:
        full_text: list[str] = []
        async for seg in service.transcribe_live_stream(_chunk_gen(), model, sample_rate, language):
            text = seg.text.strip()
            if text:
                await websocket.send_text(json.dumps({"type": "transcript.delta", "text": text}))
                full_text.append(text)
        await websocket.send_text(json.dumps({"type": "transcript.done", "text": " ".join(full_text).strip()}))
    except Exception as exc:
        logger.exception("Live stream transcription error")
        try:
            await websocket.send_text(json.dumps({"type": "error", "message": str(exc)}))
        except Exception:
            pass


async def _partial_loop(websocket: WebSocket, gate: StreamingVADGate, model: str, language: str | None, task: str, sample_rate: int, service, state: dict) -> None:
    """Emit provisional transcripts while the utterance is still in progress."""
    last_emitted = ""
    while gate.is_speaking:
        await asyncio.sleep(max(0.15, _PARTIAL_INTERVAL_S))
        if not gate.is_speaking:
            return
        pcm = gate.utterance_pcm
        if len(pcm) / 2 / sample_rate < _PARTIAL_MIN_AUDIO_S:
            continue
        max_bytes = int(_PARTIAL_WINDOW_S * sample_rate) * 2
        if len(pcm) > max_bytes:
            pcm = pcm[-max_bytes:]
        try:
            text = await _transcribe_pcm(service, pcm, model, language, task, sample_rate)
        except asyncio.CancelledError:
            raise
        except Exception:
            logger.debug("Partial decode failed", exc_info=True)
            continue
        if not text or text == last_emitted:
            continue
        last_emitted = text
        if not gate.is_speaking:
            return
        try:
            await websocket.send_text(json.dumps({"type": "transcript.delta", "text": text, "partial": True}))
        except Exception:
            return
    state["last_partial"] = last_emitted


def _make_gate(vad, sample_rate: int, speech_threshold: float, silence_s: float) -> StreamingVADGate:
    return StreamingVADGate(
        vad,
        sample_rate=sample_rate,
        threshold=speech_threshold,
        onset_ms=vocal_settings.VAD_ONSET_MS,
        silence_ms=int(max(0.2, silence_s) * 1000),
        min_speech_ms=vocal_settings.VAD_MIN_SPEECH_MS,
        preroll_ms=vocal_settings.VAD_PREROLL_MS,
        max_utterance_s=max(_MAX_CHUNK_DURATION_S, silence_s * 4),
        commit_grace_ms=vocal_settings.VAD_COMMIT_GRACE_MS,
    )


async def _run_live_stream_loop(
    websocket: WebSocket,
    service,
    model: str,
    language: str | None,
    sample_rate: int,
    vad,
    silence_duration: float,
    max_chunk_duration: float,
    speech_threshold: float,
) -> None:
    """Receive loop for models that support native live streaming (e.g. Voxtral)."""
    gate = _make_gate(vad, sample_rate, speech_threshold, silence_duration)
    gate.max_utterance_s = max_chunk_duration
    chunk_q: asyncio.Queue | None = None
    stream_task: asyncio.Task | None = None

    while True:
        data = await websocket.receive_bytes()
        for boundary in gate.feed(data):
            if boundary.kind == "speech_started" and chunk_q is None:
                chunk_q = asyncio.Queue()
                stream_task = asyncio.create_task(_live_stream_utterance(websocket, chunk_q, model, language, sample_rate, service))
                stream_task.add_done_callback(lambda t: logger.error("Live stream task failed: %s", t.exception()) if not t.cancelled() and t.exception() else None)
            elif boundary.kind == "speech_stopped" and chunk_q is not None:
                await chunk_q.put(None)  # sentinel -> generator ends -> adapter finishes
                chunk_q = None
                gate.reset()
        if chunk_q is not None:
            await chunk_q.put(data)


async def _run_buffered_loop(
    websocket: WebSocket,
    service,
    model: str,
    language: str | None,
    task: str,
    sample_rate: int,
    vad,
    silence_duration: float,
    max_chunk_duration: float,
    speech_threshold: float,
) -> None:
    """Receive loop for models that buffer an utterance and transcribe on silence."""
    gate = _make_gate(vad, sample_rate, speech_threshold, silence_duration)
    gate.max_utterance_s = max_chunk_duration
    partial_task: asyncio.Task | None = None
    state: dict = {}

    while True:
        data = await websocket.receive_bytes()
        for boundary in gate.feed(data):
            if boundary.kind == "speech_started":
                state.clear()
                if _PARTIAL_INTERVAL_S > 0:
                    partial_task = asyncio.create_task(_partial_loop(websocket, gate, model, language, task, sample_rate, service, state))
            elif boundary.kind == "speech_stopped":
                pcm = gate.take_utterance()
                gate.reset()
                if partial_task is not None and not partial_task.done():
                    partial_task.cancel()
                partial_task = None
                flush_task = asyncio.create_task(_flush_pcm(websocket, pcm, model, language, task, sample_rate, service))
                flush_task.add_done_callback(lambda t: logger.error("Flush task failed: %s", t.exception()) if not t.cancelled() and t.exception() else None)


@router.websocket("/v1/audio/stream")
async def audio_stream(
    websocket: WebSocket,
    model: str = vocal_settings.STT_DEFAULT_MODEL,
    language: str | None = vocal_settings.STT_DEFAULT_LANGUAGE,
    task: str = "transcribe",
    silence_duration: float = _SILENCE_DURATION_S,
    max_chunk_duration: float = _MAX_CHUNK_DURATION_S,
    threshold: float | None = None,
) -> None:
    await websocket.accept()
    service = get_transcription_service()
    sample_rate = vocal_settings.STT_SAMPLE_RATE
    speech_threshold = threshold if threshold is not None else vocal_settings.VAD_SPEECH_THRESHOLD
    vad = create_vad_adapter()

    try:
        model_info = await service.registry.get_model(model)
        use_live_streaming = bool(model_info and model_info.supports_live_streaming)
    except Exception:
        logger.warning("Failed to check supports_live_streaming for model %s", model, exc_info=True)
        use_live_streaming = False

    try:
        if use_live_streaming:
            await _run_live_stream_loop(websocket, service, model, language, sample_rate, vad, silence_duration, max_chunk_duration, speech_threshold)
        else:
            await _run_buffered_loop(websocket, service, model, language, task, sample_rate, vad, silence_duration, max_chunk_duration, speech_threshold)
    except WebSocketDisconnect:
        pass
    except Exception:
        logger.exception("WebSocket stream error")
        try:
            await websocket.send_text(json.dumps({"type": "error", "message": "Internal server error"}))
        except Exception:
            pass
