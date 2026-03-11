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


@router.websocket("/v1/audio/stream")
async def audio_stream(
    websocket: WebSocket,
    model: str = vocal_settings.STT_DEFAULT_MODEL,
    language: str | None = vocal_settings.STT_DEFAULT_LANGUAGE,
    task: str = "transcribe",
    silence_duration: float = _SILENCE_DURATION_S,
    max_chunk_duration: float = _MAX_CHUNK_DURATION_S,
) -> None:
    await websocket.accept()
    service = get_transcription_service()
    sample_rate = vocal_settings.STT_SAMPLE_RATE
    speech_threshold = vocal_settings.VAD_SPEECH_THRESHOLD

    vad = create_vad_adapter()

    buffer: list[bytes] = []
    silence_count = 0
    has_speech = False
    total_duration = 0.0

    try:
        while True:
            data = await websocket.receive_bytes()
            frame_secs = _estimate_frame_seconds(data, sample_rate)
            buffer.append(data)
            total_duration += frame_secs

            if vad.is_speech(data, sample_rate, speech_threshold):
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

    except WebSocketDisconnect:
        pass
    except Exception:
        logger.exception("WebSocket stream error")
        try:
            await websocket.send_text(json.dumps({"type": "error", "message": "Internal server error"}))
        except Exception:
            pass
