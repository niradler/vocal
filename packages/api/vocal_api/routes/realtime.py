import asyncio
import base64
import json
import logging
import time
import uuid
from dataclasses import dataclass, field

import httpx
import numpy as np
from fastapi import APIRouter, WebSocket, WebSocketDisconnect

from vocal_core.adapters.vad import VADAdapter, create_vad_adapter
from vocal_core.config import vocal_settings

from ..dependencies import get_transcription_service, get_tts_service

router = APIRouter(tags=["realtime"])
logger = logging.getLogger(__name__)

_INPUT_SAMPLE_RATE = vocal_settings.REALTIME_DEFAULT_INPUT_RATE
_STT_SAMPLE_RATE = vocal_settings.STT_SAMPLE_RATE
_SILENCE_FRAMES_NEEDED = vocal_settings.VAD_SILENCE_FRAMES
_MAX_BUFFER_FRAMES = vocal_settings.VAD_MAX_BUFFER_FRAMES
_SPEECH_ONSET_FRAMES = vocal_settings.VAD_SPEECH_ONSET_FRAMES
_MIN_SPEECH_FRAMES = vocal_settings.VAD_MIN_SPEECH_FRAMES
_KEEPALIVE_S = vocal_settings.REALTIME_KEEPALIVE_S
_SESSION_TTL_S = vocal_settings.REALTIME_SESSION_TTL_S

_session_store: dict[str, "_Session"] = {}


def _evict_stale_sessions() -> None:
    cutoff = time.time() - _SESSION_TTL_S
    stale = [sid for sid, s in _session_store.items() if s.last_active < cutoff]
    for sid in stale:
        del _session_store[sid]
        logger.debug("Evicted stale session %s", sid)


async def _safe_send(ws: WebSocket, text: str) -> bool:
    try:
        await ws.send_text(text)
        return True
    except (RuntimeError, WebSocketDisconnect):
        return False


@dataclass
class _Session:
    session_id: str = field(default_factory=lambda: f"sess_{uuid.uuid4().hex[:16]}")
    session_type: str = "transcription"
    model: str = field(default_factory=lambda: vocal_settings.STT_DEFAULT_MODEL)
    language: str | None = field(default_factory=lambda: vocal_settings.STT_DEFAULT_LANGUAGE)
    input_sample_rate: int = _INPUT_SAMPLE_RATE
    speech_threshold: float = field(default_factory=lambda: vocal_settings.VAD_SPEECH_THRESHOLD)
    audio_buffer: bytearray = field(default_factory=bytearray)
    speech_started: bool = False
    silence_count: int = 0
    has_speech: bool = False
    speech_onset_count: int = 0
    speech_frames_count: int = 0
    current_item_id: str = field(default_factory=lambda: f"item_{uuid.uuid4().hex[:16]}")
    system_prompt: str = field(default_factory=lambda: vocal_settings.CHAT_SYSTEM_PROMPT)
    conversation_history: list = field(default_factory=list)
    created_at: float = field(default_factory=time.time)
    last_active: float = field(default_factory=time.time)
    vad: VADAdapter = field(default_factory=create_vad_adapter)

    def touch(self) -> None:
        self.last_active = time.time()


def _make_event(event_type: str, **kwargs) -> str:
    return json.dumps({"type": event_type, "event_id": f"evt_{uuid.uuid4().hex[:16]}", **kwargs})


def _session_config(session: _Session) -> dict:
    from vocal_core.adapters.vad import SILERO_AVAILABLE

    return {
        "id": session.session_id,
        "session_id": session.session_id,
        "object": "realtime.session",
        "type": session.session_type,
        "model": session.model,
        "input_audio_format": "pcm16",
        "output_audio_format": "pcm16",
        "turn_detection": {
            "type": "server_vad",
            "backend": "silero" if SILERO_AVAILABLE else "rms",
            "threshold": session.speech_threshold,
            "silence_duration_ms": int(_SILENCE_FRAMES_NEEDED * 1000 * 2 / session.input_sample_rate),
        },
        "transcription": {"language": session.language},
        "created_at": session.created_at,
    }


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

    async def _single_chunk_gen():
        yield resampled

    try:
        full_parts: list[str] = []
        async for seg in transcription_service.transcribe_live_stream(_single_chunk_gen(), session.model, _STT_SAMPLE_RATE, session.language):
            text = seg.text.strip()
            if text:
                ok = await _safe_send(
                    ws,
                    _make_event(
                        "conversation.item.input_audio_transcription.delta",
                        item_id=item_id,
                        content_index=0,
                        delta=text,
                    ),
                )
                if not ok:
                    return ""
                full_parts.append(text)

        transcript = " ".join(full_parts).strip()
        await _safe_send(
            ws,
            _make_event(
                "conversation.item.input_audio_transcription.completed",
                item_id=item_id,
                content_index=0,
                transcript=transcript,
            ),
        )
        return transcript
    except Exception as exc:
        logger.exception("Transcription error in realtime handler")
        await _safe_send(ws, _make_event("error", error={"code": "transcription_failed", "message": str(exc)}))
        return ""


async def _stream_llm(ws: WebSocket, messages: list, response_id: str, item_id: str) -> str:
    full_response = ""
    try:
        async with httpx.AsyncClient(timeout=60.0) as client:
            async with client.stream(
                "POST",
                f"{vocal_settings.LLM_BASE_URL}/chat/completions",
                headers={"Authorization": f"Bearer {vocal_settings.LLM_API_KEY}", "Content-Type": "application/json"},
                json={"model": vocal_settings.LLM_MODEL, "messages": messages, "stream": True},
            ) as resp:
                async for line in resp.aiter_lines():
                    if not (line.startswith("data: ") and "[DONE]" not in line):
                        continue
                    try:
                        chunk = json.loads(line[6:])
                        delta = (chunk.get("choices") or [{}])[0].get("delta", {}).get("content") or ""
                    except (json.JSONDecodeError, KeyError, IndexError):
                        continue
                    if delta:
                        full_response += delta
                        if not await _safe_send(ws, _make_event("response.output_audio_transcript.delta", response_id=response_id, item_id=item_id, delta=delta)):
                            return full_response
    except Exception as exc:
        logger.warning("LLM call failed: %s", exc)
    return full_response


async def _send_tts_audio(ws: WebSocket, tts_service, text: str, response_id: str, item_id: str) -> None:
    try:
        tts_result = await tts_service.synthesize(vocal_settings.TTS_DEFAULT_MODEL, text, voice=vocal_settings.TTS_DEFAULT_VOICE, output_format="pcm")
        pcm_bytes = tts_result.audio_data
        output_sample_rate = tts_result.sample_rate or 22050
        audio_24k = _resample_pcm16(pcm_bytes, output_sample_rate, 24000)
        logger.info("TTS: %d raw PCM bytes @ %dHz -> %d bytes @ 24kHz", len(pcm_bytes), output_sample_rate, len(audio_24k))
        for i in range(0, len(audio_24k), 4800):
            encoded = base64.b64encode(audio_24k[i : i + 4800]).decode()
            if not await _safe_send(ws, _make_event("response.output_audio.delta", response_id=response_id, item_id=item_id, delta=encoded)):
                return
    except Exception as exc:
        logger.exception("TTS failed in voice agent: %s", exc)


async def _run_voice_agent(ws: WebSocket, session: _Session, user_text: str, tts_service) -> None:
    if not user_text:
        return
    response_id = f"resp_{uuid.uuid4().hex[:16]}"
    item_id = f"item_{uuid.uuid4().hex[:16]}"
    if not await _safe_send(ws, _make_event("response.created", response={"id": response_id, "status": "in_progress"})):
        return

    sys_msg = [{"role": "system", "content": session.system_prompt}] if session.system_prompt else []
    messages = sys_msg + session.conversation_history + [{"role": "user", "content": user_text}]
    full_response = await _stream_llm(ws, messages, response_id, item_id)

    if full_response:
        session.conversation_history.append({"role": "user", "content": user_text})
        session.conversation_history.append({"role": "assistant", "content": full_response})

    await _send_tts_audio(ws, tts_service, full_response or "...", response_id, item_id)
    await _safe_send(ws, _make_event("response.output_audio_transcript.done", response_id=response_id, item_id=item_id, transcript=full_response))
    await _safe_send(ws, _make_event("response.output_audio.done", response_id=response_id, item_id=item_id))
    await _safe_send(ws, _make_event("response.done", response={"id": response_id, "status": "completed"}))


async def _commit_and_process(ws: WebSocket, session: _Session, transcription_service, tts_service) -> None:
    item_id = session.current_item_id
    if not await _safe_send(ws, _make_event("input_audio_buffer.committed", item_id=item_id, previous_item_id=None)):
        return

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
        session.speech_threshold = float(td["threshold"])
    ack_type = "transcription_session.updated" if event_type == "transcription_session.update" else "session.updated"
    await _safe_send(ws, _make_event(ack_type, session=_session_config(session)))


async def _handle_audio_append(ws: WebSocket, session: _Session, event: dict) -> bool:
    """Process one audio chunk. Returns True when an utterance is ready to commit+process."""
    audio_b64 = event.get("audio", "")
    try:
        pcm_bytes = base64.b64decode(audio_b64)
    except Exception:
        await _safe_send(ws, _make_event("error", error={"code": "invalid_audio", "message": "Failed to decode base64 audio"}))
        return False

    session.audio_buffer.extend(pcm_bytes)
    frame_count = len(session.audio_buffer) // 2
    # Silero VAD only supports 8000/16000 Hz — resample if input rate differs
    if session.input_sample_rate != _STT_SAMPLE_RATE:
        vad_pcm = _resample_pcm16(bytearray(pcm_bytes), session.input_sample_rate, _STT_SAMPLE_RATE)
    else:
        vad_pcm = pcm_bytes
    is_speech = session.vad.is_speech(vad_pcm, _STT_SAMPLE_RATE, session.speech_threshold)

    if is_speech:
        session.speech_onset_count += 1
        if session.speech_started:
            session.speech_frames_count += 1
            session.silence_count = 0
        elif session.speech_onset_count >= _SPEECH_ONSET_FRAMES:
            session.speech_started = True
            session.has_speech = True
            session.silence_count = 0
            session.speech_frames_count = 1
            audio_start_ms = int((frame_count / session.input_sample_rate) * 1000)
            await _safe_send(ws, _make_event("input_audio_buffer.speech_started", audio_start_ms=audio_start_ms, item_id=session.current_item_id))
    else:
        session.speech_onset_count = 0
        if session.speech_started:
            session.silence_count += 1
            if session.silence_count >= _SILENCE_FRAMES_NEEDED or frame_count >= _MAX_BUFFER_FRAMES * session.input_sample_rate:
                if session.speech_frames_count >= _MIN_SPEECH_FRAMES:
                    audio_end_ms = int((len(session.audio_buffer) / 2 / session.input_sample_rate) * 1000)
                    await _safe_send(ws, _make_event("input_audio_buffer.speech_stopped", audio_end_ms=audio_end_ms, item_id=session.current_item_id))
                    session.speech_started = False
                    session.vad.reset()
                    return True
                else:
                    session.speech_started = False
                    session.speech_frames_count = 0
                    session.silence_count = 0
                    session.audio_buffer = bytearray()
                    session.vad.reset()
    return False


async def _dispatch_event(ws: WebSocket, session: _Session, event: dict) -> bool:
    """Handle one client event. Returns True when _commit_and_process should be scheduled."""
    event_type = event.get("type", "")

    if event_type in ("session.update", "transcription_session.update"):
        await _handle_session_update(ws, session, event, event_type)
    elif event_type == "input_audio_buffer.append":
        return await _handle_audio_append(ws, session, event)
    elif event_type == "input_audio_buffer.commit":
        if not session.audio_buffer:
            await ws.send_text(_make_event("error", error={"code": "buffer_empty", "message": "Input audio buffer is empty"}))
        else:
            session.speech_started = False
            return True
    elif event_type == "input_audio_buffer.clear":
        session.audio_buffer = bytearray()
        session.speech_started = False
        session.silence_count = 0
        session.has_speech = False
        session.speech_onset_count = 0
        session.speech_frames_count = 0
        await _safe_send(ws, _make_event("input_audio_buffer.cleared"))
    else:
        await _safe_send(ws, _make_event("error", error={"code": "unknown_event", "message": f"Unknown event type: {event_type}"}))
    return False


@router.websocket("/v1/realtime")
async def realtime_endpoint(  # noqa: C901
    websocket: WebSocket,
    model: str | None = None,
    session_id: str | None = None,
) -> None:
    await websocket.accept()

    _evict_stale_sessions()

    resumed = session_id and session_id in _session_store
    if resumed:
        session = _session_store[session_id]
        session.touch()
        logger.info("Resumed session %s", session.session_id)
    else:
        session = _Session()
        if model:
            session.model = model
        _session_store[session.session_id] = session

    transcription_service = get_transcription_service()
    tts_service = get_tts_service()

    init_event = "session.resumed" if resumed else "session.created"
    await websocket.send_text(_make_event(init_event, session=_session_config(session)))

    try:
        while True:
            try:
                raw = await asyncio.wait_for(
                    websocket.receive_text(),
                    timeout=float(_KEEPALIVE_S),
                )
            except TimeoutError:
                if not await _safe_send(websocket, _make_event("ping")):
                    break
                session.touch()
                continue

            session.touch()
            try:
                event = json.loads(raw)
            except json.JSONDecodeError:
                await _safe_send(websocket, _make_event("error", error={"code": "invalid_json", "message": "Could not parse JSON"}))
                continue

            if event.get("type") == "pong":
                continue

            should_commit = await _dispatch_event(websocket, session, event)
            if should_commit:
                # Run STT→LLM→TTS as a background task so receive_text() keeps
                # spinning. The pipeline takes 15–45 s; awaiting it inline stalls
                # Starlette's receive loop and lets the client's ping_timeout fire
                # → "no close frame received or sent".
                _task = asyncio.create_task(_commit_and_process(websocket, session, transcription_service, tts_service))
                _task.add_done_callback(lambda t: logger.error("Commit pipeline failed: %s", t.exception()) if not t.cancelled() and t.exception() else None)

    except WebSocketDisconnect:
        pass
    except Exception:
        logger.exception("Realtime WebSocket error")
        await _safe_send(websocket, _make_event("error", error={"code": "server_error", "message": "Internal server error"}))
