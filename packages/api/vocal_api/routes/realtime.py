import base64
import json
import logging
import tempfile
import time
import uuid
import wave
from dataclasses import dataclass, field
from pathlib import Path

import httpx
import numpy as np
from fastapi import APIRouter, WebSocket, WebSocketDisconnect

from vocal_core.config import vocal_settings

from ..dependencies import get_transcription_service, get_tts_service

router = APIRouter(tags=["realtime"])
logger = logging.getLogger(__name__)

_INPUT_SAMPLE_RATE = 24000
_STT_SAMPLE_RATE = 16000
_VAD_THRESHOLD = 300.0
_SILENCE_FRAMES_NEEDED = 15
_MAX_BUFFER_FRAMES = 150


@dataclass
class _Session:
    session_id: str = field(default_factory=lambda: f"sess_{uuid.uuid4().hex[:16]}")
    session_type: str = "transcription"
    model: str = field(default_factory=lambda: vocal_settings.STT_DEFAULT_MODEL)
    language: str | None = field(default_factory=lambda: vocal_settings.STT_DEFAULT_LANGUAGE)
    input_sample_rate: int = _INPUT_SAMPLE_RATE
    vad_threshold: float = _VAD_THRESHOLD
    audio_buffer: bytearray = field(default_factory=bytearray)
    speech_started: bool = False
    silence_count: int = 0
    has_speech: bool = False
    current_item_id: str = field(default_factory=lambda: f"item_{uuid.uuid4().hex[:16]}")
    system_prompt: str = "You are a helpful voice assistant. Keep answers short and conversational, 1-2 sentences max."
    conversation_history: list = field(default_factory=list)
    created_at: float = field(default_factory=time.time)


def _make_event(event_type: str, **kwargs) -> str:
    return json.dumps({"type": event_type, "event_id": f"evt_{uuid.uuid4().hex[:16]}", **kwargs})


def _session_config(session: _Session) -> dict:
    return {
        "id": session.session_id,
        "object": "realtime.session",
        "type": session.session_type,
        "model": session.model,
        "input_audio_format": "pcm16",
        "output_audio_format": "pcm16",
        "turn_detection": {
            "type": "server_vad",
            "threshold": session.vad_threshold / 32768.0,
            "silence_duration_ms": int(_SILENCE_FRAMES_NEEDED * 1000 * 2 / session.input_sample_rate),
        },
        "transcription": {"language": session.language},
        "created_at": session.created_at,
    }


def _rms(pcm_bytes: bytes | bytearray) -> float:
    if not pcm_bytes:
        return 0.0
    arr = np.frombuffer(bytes(pcm_bytes), dtype=np.int16).astype(np.float32)
    return float(np.sqrt(np.mean(arr**2))) if arr.size > 0 else 0.0


def _resample_pcm16(pcm_bytes: bytes | bytearray, from_rate: int, to_rate: int) -> bytes:
    if from_rate == to_rate:
        return bytes(pcm_bytes)
    arr = np.frombuffer(bytes(pcm_bytes), dtype=np.int16).astype(np.float32)
    if arr.size == 0:
        return b""
    new_len = int(len(arr) * to_rate / from_rate)
    indices = np.linspace(0, len(arr) - 1, new_len)
    resampled = np.interp(indices, np.arange(len(arr)), arr).astype(np.int16)
    return resampled.tobytes()


async def _transcribe_buffer(ws: WebSocket, session: _Session, transcription_service) -> str:
    item_id = session.current_item_id
    resampled = _resample_pcm16(session.audio_buffer, session.input_sample_rate, _STT_SAMPLE_RATE)
    tmp_path = None
    try:
        with tempfile.NamedTemporaryFile(suffix=".wav", delete=False) as tmp:
            tmp_path = tmp.name
        with wave.open(tmp_path, "wb") as wf:
            wf.setnchannels(1)
            wf.setsampwidth(2)
            wf.setframerate(_STT_SAMPLE_RATE)
            wf.writeframes(resampled)

        full_parts: list[str] = []
        async for seg in transcription_service.transcribe_stream_path(tmp_path, session.model, session.language):
            text = seg.text.strip()
            if text:
                await ws.send_text(
                    _make_event(
                        "conversation.item.input_audio_transcription.delta",
                        item_id=item_id,
                        content_index=0,
                        delta=text,
                    )
                )
                full_parts.append(text)

        transcript = " ".join(full_parts).strip()
        await ws.send_text(
            _make_event(
                "conversation.item.input_audio_transcription.completed",
                item_id=item_id,
                content_index=0,
                transcript=transcript,
            )
        )
        return transcript
    except Exception as exc:
        logger.exception("Transcription error in realtime handler")
        await ws.send_text(_make_event("error", error={"code": "transcription_failed", "message": str(exc)}))
        return ""
    finally:
        if tmp_path:
            Path(tmp_path).unlink(missing_ok=True)


async def _run_voice_agent(ws: WebSocket, session: _Session, user_text: str, tts_service) -> None:
    if not user_text:
        return
    response_id = f"resp_{uuid.uuid4().hex[:16]}"
    item_id = f"item_{uuid.uuid4().hex[:16]}"
    await ws.send_text(_make_event("response.created", response={"id": response_id, "status": "in_progress"}))

    full_response = ""
    sys_msg = [{"role": "system", "content": session.system_prompt}] if session.system_prompt else []
    messages = sys_msg + session.conversation_history + [{"role": "user", "content": user_text}]
    try:
        async with httpx.AsyncClient(timeout=60.0) as client:
            async with client.stream(
                "POST",
                f"{vocal_settings.LLM_BASE_URL}/chat/completions",
                headers={"Authorization": f"Bearer {vocal_settings.LLM_API_KEY}", "Content-Type": "application/json"},
                json={"model": vocal_settings.LLM_MODEL, "messages": messages, "stream": True},
            ) as resp:
                async for line in resp.aiter_lines():
                    if line.startswith("data: ") and "[DONE]" not in line:
                        try:
                            chunk = json.loads(line[6:])
                            delta = (chunk.get("choices") or [{}])[0].get("delta", {}).get("content") or ""
                            if delta:
                                full_response += delta
                                await ws.send_text(
                                    _make_event(
                                        "response.output_audio_transcript.delta",
                                        response_id=response_id,
                                        item_id=item_id,
                                        delta=delta,
                                    )
                                )
                        except (json.JSONDecodeError, KeyError, IndexError):
                            pass
    except Exception as exc:
        logger.warning("LLM call failed: %s", exc)

    if full_response:
        session.conversation_history.append({"role": "user", "content": user_text})
        session.conversation_history.append({"role": "assistant", "content": full_response})

    try:
        tts_result = await tts_service.synthesize("pyttsx3", full_response or "...", output_format="pcm")
        pcm_bytes = tts_result.audio_data
        output_sample_rate = tts_result.sample_rate or 22050
        audio_24k = _resample_pcm16(pcm_bytes, output_sample_rate, 24000)
        logger.info("TTS: %d raw PCM bytes @ %dHz -> %d bytes @ 24kHz", len(pcm_bytes), output_sample_rate, len(audio_24k))
        chunk_size = 4800
        for i in range(0, len(audio_24k), chunk_size):
            chunk = audio_24k[i : i + chunk_size]
            encoded = base64.b64encode(chunk).decode()
            await ws.send_text(_make_event("response.output_audio.delta", response_id=response_id, item_id=item_id, delta=encoded))
    except Exception as exc:
        logger.exception("TTS failed in voice agent: %s", exc)

    await ws.send_text(_make_event("response.output_audio_transcript.done", response_id=response_id, item_id=item_id, transcript=full_response))
    await ws.send_text(_make_event("response.output_audio.done", response_id=response_id, item_id=item_id))
    await ws.send_text(_make_event("response.done", response={"id": response_id, "status": "completed"}))


async def _commit_and_process(ws: WebSocket, session: _Session, transcription_service, tts_service) -> None:
    item_id = session.current_item_id
    await ws.send_text(_make_event("input_audio_buffer.committed", item_id=item_id, previous_item_id=None))

    transcript = await _transcribe_buffer(ws, session, transcription_service)

    session.audio_buffer = bytearray()
    session.has_speech = False
    session.silence_count = 0
    session.current_item_id = f"item_{uuid.uuid4().hex[:16]}"

    if session.session_type == "realtime" and transcript:
        await _run_voice_agent(ws, session, transcript, tts_service)


async def _handle_session_update(ws: WebSocket, session: _Session, event: dict, event_type: str) -> None:
    sess_cfg = event.get("session", {})
    if "type" in sess_cfg:
        session.session_type = sess_cfg["type"]
    if "model" in sess_cfg:
        session.model = sess_cfg["model"]
    if "language" in sess_cfg:
        session.language = sess_cfg["language"] or None
    if "input_sample_rate" in sess_cfg:
        session.input_sample_rate = int(sess_cfg["input_sample_rate"])
    if "system_prompt" in sess_cfg:
        session.system_prompt = sess_cfg["system_prompt"]
    td = sess_cfg.get("turn_detection") or {}
    if "threshold" in td:
        session.vad_threshold = float(td["threshold"]) * 32768.0
    ack_type = "transcription_session.updated" if event_type == "transcription_session.update" else "session.updated"
    await ws.send_text(_make_event(ack_type, session=_session_config(session)))


async def _handle_audio_append(ws: WebSocket, session: _Session, event: dict, transcription_service, tts_service) -> None:
    audio_b64 = event.get("audio", "")
    try:
        pcm_bytes = base64.b64decode(audio_b64)
    except Exception:
        await ws.send_text(_make_event("error", error={"code": "invalid_audio", "message": "Failed to decode base64 audio"}))
        return

    session.audio_buffer.extend(pcm_bytes)
    energy = _rms(pcm_bytes)
    frame_count = len(session.audio_buffer) // 2

    if energy >= session.vad_threshold:
        if not session.speech_started:
            session.speech_started = True
            session.has_speech = True
            session.silence_count = 0
            audio_start_ms = int((frame_count / session.input_sample_rate) * 1000)
            await ws.send_text(_make_event("input_audio_buffer.speech_started", audio_start_ms=audio_start_ms, item_id=session.current_item_id))
        session.silence_count = 0
    elif session.speech_started:
        session.silence_count += 1
        if session.silence_count >= _SILENCE_FRAMES_NEEDED or frame_count >= _MAX_BUFFER_FRAMES * session.input_sample_rate:
            audio_end_ms = int((len(session.audio_buffer) / 2 / session.input_sample_rate) * 1000)
            await ws.send_text(_make_event("input_audio_buffer.speech_stopped", audio_end_ms=audio_end_ms, item_id=session.current_item_id))
            session.speech_started = False
            await _commit_and_process(ws, session, transcription_service, tts_service)


async def _dispatch_event(ws: WebSocket, session: _Session, event: dict, transcription_service, tts_service) -> None:
    event_type = event.get("type", "")

    if event_type in ("session.update", "transcription_session.update"):
        await _handle_session_update(ws, session, event, event_type)
    elif event_type == "input_audio_buffer.append":
        await _handle_audio_append(ws, session, event, transcription_service, tts_service)
    elif event_type == "input_audio_buffer.commit":
        if not session.audio_buffer:
            await ws.send_text(_make_event("error", error={"code": "buffer_empty", "message": "Input audio buffer is empty"}))
        else:
            session.speech_started = False
            await _commit_and_process(ws, session, transcription_service, tts_service)
    elif event_type == "input_audio_buffer.clear":
        session.audio_buffer = bytearray()
        session.speech_started = False
        session.silence_count = 0
        session.has_speech = False
        await ws.send_text(_make_event("input_audio_buffer.cleared"))
    else:
        await ws.send_text(_make_event("error", error={"code": "unknown_event", "message": f"Unknown event type: {event_type}"}))


@router.websocket("/v1/realtime")
async def realtime_endpoint(websocket: WebSocket, model: str | None = None) -> None:
    await websocket.accept()
    session = _Session()
    if model:
        session.model = model

    transcription_service = get_transcription_service()
    tts_service = get_tts_service()

    await websocket.send_text(_make_event("session.created", session=_session_config(session)))

    try:
        while True:
            raw = await websocket.receive_text()
            try:
                event = json.loads(raw)
            except json.JSONDecodeError:
                await websocket.send_text(_make_event("error", error={"code": "invalid_json", "message": "Could not parse JSON"}))
                continue

            await _dispatch_event(websocket, session, event, transcription_service, tts_service)

    except WebSocketDisconnect:
        pass
    except Exception:
        logger.exception("Realtime WebSocket error")
        try:
            await websocket.send_text(_make_event("error", error={"code": "server_error", "message": "Internal server error"}))
        except Exception:
            pass
