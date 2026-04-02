import asyncio
import json
import logging
import tempfile
import wave
from pathlib import Path

from fastapi import APIRouter, WebSocket, WebSocketDisconnect

from vocal_core.adapters.vad import create_vad_adapter
from vocal_core.config import vocal_settings

from ..dependencies import get_transcription_service

router = APIRouter(tags=["stream"])
logger = logging.getLogger(__name__)

_SILENCE_DURATION_S = vocal_settings.VAD_SILENCE_DURATION_S
_MAX_CHUNK_DURATION_S = 10.0


def _estimate_frame_seconds(pcm_bytes: bytes, sample_rate: int) -> float:
    return len(pcm_bytes) / 2 / sample_rate


async def _flush_pcm(websocket: WebSocket, pcm_frames: list[bytes], model: str, language: str | None, task: str, sample_rate: int, service) -> None:
    pcm_data = b"".join(pcm_frames)
    tmp_path = None
    try:
        with tempfile.NamedTemporaryFile(suffix=".wav", delete=False) as tmp:
            tmp_path = tmp.name
        with wave.open(tmp_path, "wb") as wf:
            wf.setnchannels(1)
            wf.setsampwidth(2)
            wf.setframerate(sample_rate)
            wf.writeframes(pcm_data)

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
    chunk_q: asyncio.Queue | None = None
    silence_count = 0
    has_speech = False
    total_duration = 0.0

    while True:
        data = await websocket.receive_bytes()
        frame_secs = _estimate_frame_seconds(data, sample_rate)
        total_duration += frame_secs
        is_speech = vad.is_speech(data, sample_rate, speech_threshold)

        if is_speech:
            has_speech = True
            silence_count = 0
            if chunk_q is None:
                chunk_q = asyncio.Queue()
                task = asyncio.create_task(_live_stream_utterance(websocket, chunk_q, model, language, sample_rate, service))
                task.add_done_callback(
                    lambda t: logger.error("Live stream task failed: %s", t.exception())
                    if not t.cancelled() and t.exception()
                    else None
                )
            await chunk_q.put(data)
        else:
            silence_count += 1

        silence_secs = silence_count * frame_secs
        should_flush = (has_speech and silence_secs >= silence_duration) or total_duration >= max_chunk_duration

        if should_flush and chunk_q is not None:
            await chunk_q.put(None)  # sentinel → chunk_gen stops → adapter finishes
            # Do NOT await the task here — that would block receive_bytes(),
            # starving Starlette of the receive() calls it needs to respond to WebSocket
            # pings. Model load + inference can take >20 s, exceeding the client's
            # ping_timeout and dropping the connection with "no close frame received".
            vad.reset()
            chunk_q = None
            silence_count = 0
            has_speech = False
            total_duration = 0.0


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
    """Receive loop for models that buffer audio and transcribe on silence."""
    buffer: list[bytes] = []
    silence_count = 0
    has_speech = False
    total_duration = 0.0

    while True:
        data = await websocket.receive_bytes()
        frame_secs = _estimate_frame_seconds(data, sample_rate)
        total_duration += frame_secs
        is_speech = vad.is_speech(data, sample_rate, speech_threshold)

        buffer.append(data)
        if is_speech:
            has_speech = True
            silence_count = 0
        else:
            silence_count += 1

        silence_secs = silence_count * frame_secs
        should_flush = (has_speech and silence_secs >= silence_duration) or total_duration >= max_chunk_duration

        if should_flush:
            if has_speech:
                await _flush_pcm(websocket, buffer, model, language, task, sample_rate, service)
            vad.reset()
            buffer = []
            silence_count = 0
            has_speech = False
            total_duration = 0.0


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
