import asyncio
import base64
import json
import logging
import time
import uuid
from dataclasses import dataclass, field

import httpx
from fastapi import APIRouter, WebSocket, WebSocketDisconnect

from vocal_core.adapters.vad import VADAdapter, create_vad_adapter
from vocal_core.audio import PCM16Resampler, SentenceChunker, StreamingVADGate, resample_pcm16
from vocal_core.config import vocal_settings

from ..dependencies import get_transcription_service, get_tts_service

router = APIRouter(tags=["realtime"])
logger = logging.getLogger(__name__)

_INPUT_SAMPLE_RATE = vocal_settings.REALTIME_DEFAULT_INPUT_RATE
_STT_SAMPLE_RATE = vocal_settings.STT_SAMPLE_RATE
_OUTPUT_SAMPLE_RATE = vocal_settings.REALTIME_OUTPUT_SAMPLE_RATE
_KEEPALIVE_S = vocal_settings.REALTIME_KEEPALIVE_S
_SESSION_TTL_S = vocal_settings.REALTIME_SESSION_TTL_S
_PARTIAL_INTERVAL_S = vocal_settings.REALTIME_PARTIAL_INTERVAL_S
_PARTIAL_MIN_AUDIO_S = vocal_settings.REALTIME_PARTIAL_MIN_AUDIO_S
_PARTIAL_WINDOW_S = vocal_settings.REALTIME_PARTIAL_WINDOW_S

_session_store: dict[str, "_Session"] = {}


def _evict_stale_sessions() -> None:
    cutoff = time.time() - _SESSION_TTL_S
    stale = [sid for sid, s in _session_store.items() if s.last_active < cutoff]
    for sid in stale:
        del _session_store[sid]
        logger.debug("Evicted stale session %s", sid)


@dataclass
class _Session:
    session_id: str = field(default_factory=lambda: f"sess_{uuid.uuid4().hex[:16]}")
    session_type: str = "transcription"
    model: str = field(default_factory=lambda: vocal_settings.STT_DEFAULT_MODEL)
    language: str | None = field(default_factory=lambda: vocal_settings.STT_DEFAULT_LANGUAGE)
    input_sample_rate: int = _INPUT_SAMPLE_RATE
    speech_threshold: float = field(default_factory=lambda: vocal_settings.VAD_SPEECH_THRESHOLD)
    current_item_id: str = field(default_factory=lambda: f"item_{uuid.uuid4().hex[:16]}")
    tts_model: str = field(default_factory=lambda: vocal_settings.TTS_DEFAULT_MODEL)
    tts_voice: str | None = field(default_factory=lambda: vocal_settings.TTS_DEFAULT_VOICE)
    system_prompt: str = field(default_factory=lambda: vocal_settings.CHAT_SYSTEM_PROMPT)
    conversation_history: list = field(default_factory=list)
    created_at: float = field(default_factory=time.time)
    last_active: float = field(default_factory=time.time)
    vad: VADAdapter = field(default_factory=create_vad_adapter)
    gate: StreamingVADGate | None = None
    send_lock: asyncio.Lock = field(default_factory=asyncio.Lock)
    stt_lock: asyncio.Lock = field(default_factory=asyncio.Lock)
    partial_task: asyncio.Task | None = None
    response_task: asyncio.Task | None = None
    response_cancel: asyncio.Event | None = None
    last_partial_text: str = ""
    last_stt_ms: float = 0.0
    manual_buffer: bytearray = field(default_factory=bytearray)
    tts_ready: set[str] = field(default_factory=set)
    tts_warm_tasks: dict[str, asyncio.Task] = field(default_factory=dict)

    def __post_init__(self) -> None:
        if self.gate is None:
            self.gate = StreamingVADGate(
                self.vad,
                sample_rate=_STT_SAMPLE_RATE,
                threshold=self.speech_threshold,
                onset_ms=vocal_settings.VAD_ONSET_MS,
                silence_ms=vocal_settings.VAD_SILENCE_MS,
                min_speech_ms=vocal_settings.VAD_MIN_SPEECH_MS,
                preroll_ms=vocal_settings.VAD_PREROLL_MS,
                max_utterance_s=vocal_settings.REALTIME_MAX_UTTERANCE_S,
                commit_grace_ms=vocal_settings.VAD_COMMIT_GRACE_MS,
            )

    def apply_mode_defaults(self) -> None:
        """Pick endpointing that matches the session's job.

        Dictation wants the fastest possible final transcript; a voice agent
        must not cut a sentence at a natural pause.
        """
        if self.gate is None:
            return
        if self.session_type == "realtime":
            self.gate.configure(
                silence_ms=vocal_settings.REALTIME_AGENT_SILENCE_MS,
                commit_grace_ms=vocal_settings.REALTIME_AGENT_COMMIT_GRACE_MS,
            )
        else:
            self.gate.configure(
                silence_ms=vocal_settings.VAD_SILENCE_MS,
                commit_grace_ms=vocal_settings.VAD_COMMIT_GRACE_MS,
            )

    @property
    def is_responding(self) -> bool:
        return self.response_task is not None and not self.response_task.done()

    def touch(self) -> None:
        self.last_active = time.time()

    def new_item(self) -> str:
        self.current_item_id = f"item_{uuid.uuid4().hex[:16]}"
        self.last_partial_text = ""
        return self.current_item_id


def _make_event(event_type: str, **kwargs) -> str:
    return json.dumps({"type": event_type, "event_id": f"evt_{uuid.uuid4().hex[:16]}", **kwargs})


async def _send(ws: WebSocket, sess: _Session, text: str) -> bool:
    """Serialize writes: several tasks may produce events concurrently."""
    async with sess.send_lock:
        try:
            await ws.send_text(text)
            return True
        except (RuntimeError, WebSocketDisconnect):
            return False


async def _emit(ws: WebSocket, sess: _Session, event_type: str, **kwargs) -> bool:
    return await _send(ws, sess, _make_event(event_type, **kwargs))


async def _warm_tts(session: _Session, tts_service, model: str) -> None:
    try:
        await tts_service.ensure_ready(model)
        session.tts_ready.add(model)
    except Exception:
        logger.warning("TTS warm-up failed for %s", model, exc_info=True)
    finally:
        session.tts_warm_tasks.pop(model, None)


def _schedule_tts_warm(session: _Session, tts_service) -> None:
    """Load the TTS backend in the background while the user is talking.

    A cold Kokoro load takes seconds; without this the first reply pays for it
    after the turn already ended.
    """
    model = session.tts_model
    if not model or model in session.tts_ready or model in session.tts_warm_tasks:
        return
    session.tts_warm_tasks[model] = asyncio.create_task(_warm_tts(session, tts_service, model))


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
            "prefix_padding_ms": vocal_settings.VAD_PREROLL_MS,
            "silence_duration_ms": session.gate.silence_ms if session.gate else vocal_settings.VAD_SILENCE_MS,
            "commit_grace_ms": session.gate.commit_grace_ms if session.gate else 0,
        },
        "transcription": {"language": session.language},
        "created_at": session.created_at,
    }


async def _transcribe_pcm(service, session: _Session, pcm: bytes) -> str:
    """Transcribe one buffered PCM16 utterance with the configured model."""

    async def _single_chunk_gen():
        yield pcm

    parts: list[str] = []
    async with session.stt_lock:
        async for seg in service.transcribe_live_stream(_single_chunk_gen(), session.model, _STT_SAMPLE_RATE, session.language):
            text = seg.text.strip()
            if text:
                parts.append(text)
    return " ".join(parts).strip()


async def _partial_transcription_loop(ws: WebSocket, session: _Session, service) -> None:  # noqa: C901
    """Re-decode the growing utterance while the user is still speaking."""
    interval = max(0.15, _PARTIAL_INTERVAL_S)
    while True:
        await asyncio.sleep(interval)
        gate = session.gate
        if gate is None or not gate.is_speaking:
            return
        pcm = gate.utterance_pcm
        if len(pcm) / 2 / _STT_SAMPLE_RATE < _PARTIAL_MIN_AUDIO_S:
            continue
        # Partial passes only need recent context, so long utterances keep a
        # flat decode cost.
        max_bytes = int(_PARTIAL_WINDOW_S * _STT_SAMPLE_RATE) * 2
        if len(pcm) > max_bytes:
            pcm = pcm[-max_bytes:]
        started = time.perf_counter()
        try:
            text = await _transcribe_pcm(service, session, pcm)
        except asyncio.CancelledError:
            raise
        except Exception:
            logger.debug("Partial transcription failed", exc_info=True)
            continue
        # If decoding took longer than the interval, back off instead of
        # queueing another pass immediately (keeps the GPU from thrashing and
        # leaves headroom for the authoritative decode).
        interval = max(max(0.15, _PARTIAL_INTERVAL_S), time.perf_counter() - started)
        if not text:
            continue
        gate = session.gate
        if gate is None or not gate.is_speaking:
            return
        # Emit only the new suffix so append-only clients stay correct, and
        # include the full hypothesis for clients that replace instead.
        previous = session.last_partial_text
        prefix = 0
        limit = min(len(previous), len(text))
        while prefix < limit and previous[prefix] == text[prefix]:
            prefix += 1
        delta = text[prefix:]
        session.last_partial_text = text
        if not delta:
            continue
        ok = await _emit(
            ws,
            session,
            "conversation.item.input_audio_transcription.delta",
            item_id=session.current_item_id,
            content_index=0,
            delta=delta,
            partial=True,
            partial_transcript=text,
        )
        if not ok:
            return


async def _stream_llm(session: _Session, cancel: asyncio.Event):
    """Yield LLM text deltas over the OpenAI-compatible chat completions API."""
    messages = ([{"role": "system", "content": session.system_prompt}] if session.system_prompt else []) + session.conversation_history
    async with httpx.AsyncClient(timeout=60.0) as client:
        async with client.stream(
            "POST",
            f"{vocal_settings.LLM_BASE_URL}/chat/completions",
            headers={"Authorization": f"Bearer {vocal_settings.LLM_API_KEY}", "Content-Type": "application/json"},
            json={"model": vocal_settings.LLM_MODEL, "messages": messages, "stream": True},
        ) as resp:
            async for line in resp.aiter_lines():
                if cancel.is_set():
                    return
                if not (line.startswith("data: ") and "[DONE]" not in line):
                    continue
                try:
                    chunk = json.loads(line[6:])
                    delta = (chunk.get("choices") or [{}])[0].get("delta", {}).get("content") or ""
                except (json.JSONDecodeError, KeyError, IndexError):
                    continue
                if delta:
                    yield delta


async def _speak_sentences(  # noqa: C901
    ws: WebSocket,
    session: _Session,
    text_queue: asyncio.Queue,
    tts_service,
    response_id: str,
    item_id: str,
    cancel: asyncio.Event,
    timings: dict,
) -> None:
    """Synthesize queued sentences and stream audio as soon as each chunk exists."""
    resampler: PCM16Resampler | None = None
    first_audio_at: float | None = None
    while True:
        sentence = await text_queue.get()
        if sentence is None:
            return
        if cancel.is_set():
            return
        if resampler is None:
            try:
                source_rate = await tts_service.get_sample_rate(session.tts_model)
            except Exception:
                source_rate = None
            resampler = PCM16Resampler(source_rate or _OUTPUT_SAMPLE_RATE, _OUTPUT_SAMPLE_RATE)
        try:
            async for chunk in tts_service.synthesize_stream(
                model_id=session.tts_model,
                text=sentence,
                voice=session.tts_voice,
                output_format="pcm",
            ):
                if cancel.is_set():
                    return
                pcm = resampler.process(chunk)
                if not pcm:
                    continue
                if first_audio_at is None:
                    first_audio_at = time.perf_counter()
                    timings["tts_first_chunk_ms"] = round((first_audio_at - timings["speech_end"]) * 1000, 1)
                for i in range(0, len(pcm), 4800):
                    encoded = base64.b64encode(pcm[i : i + 4800]).decode()
                    if not await _emit(
                        ws,
                        session,
                        "response.output_audio.delta",
                        response_id=response_id,
                        item_id=item_id,
                        delta=encoded,
                        sample_rate=_OUTPUT_SAMPLE_RATE,
                    ):
                        cancel.set()
                        return
        except asyncio.CancelledError:
            raise
        except Exception:
            logger.exception("TTS failed in voice agent")


async def _run_voice_agent(  # noqa: C901
    ws: WebSocket,
    session: _Session,
    user_text: str,
    tts_service,
    speech_end: float,
) -> None:
    """LLM -> sentence-pipelined TTS with barge-in support."""
    response_id = f"resp_{uuid.uuid4().hex[:16]}"
    item_id = session.new_item()
    cancel = asyncio.Event()
    session.response_cancel = cancel
    timings: dict = {"speech_end": speech_end, "stt_ms": round(session.last_stt_ms, 1)}

    try:
        if not await _emit(ws, session, "response.created", response={"id": response_id, "status": "in_progress"}):
            return

        # Unbounded on purpose: the LLM already throttles production, and a
        # bounded queue can deadlock the producer when the consumer is cancelled.
        text_queue: asyncio.Queue[str | None] = asyncio.Queue()
        chunker = SentenceChunker(
            min_chars=vocal_settings.REALTIME_SENTENCE_MIN_CHARS,
            max_chars=vocal_settings.REALTIME_SENTENCE_MAX_CHARS,
        )
        full_response: list[str] = []

        async def producer() -> None:
            try:
                first_token_at: float | None = None
                async for delta in _stream_llm(session, cancel):
                    if cancel.is_set():
                        return
                    if first_token_at is None:
                        first_token_at = time.perf_counter()
                        timings["llm_first_token_ms"] = round((first_token_at - speech_end) * 1000, 1)
                    full_response.append(delta)
                    if not await _emit(
                        ws,
                        session,
                        "response.output_audio_transcript.delta",
                        response_id=response_id,
                        item_id=item_id,
                        delta=delta,
                    ):
                        cancel.set()
                        return
                    for sentence in chunker.push(delta):
                        text_queue.put_nowait(sentence)
                tail = chunker.flush()
                if tail and not cancel.is_set():
                    text_queue.put_nowait(tail)
            finally:
                text_queue.put_nowait(None)

        speaker = asyncio.create_task(_speak_sentences(ws, session, text_queue, tts_service, response_id, item_id, cancel, timings))
        await producer()
        await speaker

        if cancel.is_set():
            return

        answer = "".join(full_response).strip()
        if answer:
            session.conversation_history.append({"role": "user", "content": user_text})
            session.conversation_history.append({"role": "assistant", "content": answer})

        await _emit(ws, session, "response.output_audio_transcript.done", response_id=response_id, item_id=item_id, transcript=answer)
        await _emit(ws, session, "response.output_audio.done", response_id=response_id, item_id=item_id, sample_rate=_OUTPUT_SAMPLE_RATE)
        timings.setdefault("tts_first_chunk_ms", -1)
        timings["ttfa_ms"] = timings["tts_first_chunk_ms"]
        timings["response_total_ms"] = round((time.perf_counter() - speech_end) * 1000, 1)
        await _emit(ws, session, "response.metrics", response_id=response_id, metrics=timings)
        await _emit(ws, session, "response.done", response={"id": response_id, "status": "completed"})
    except asyncio.CancelledError:
        raise
    except Exception:
        logger.exception("Voice agent failed")
        await _emit(ws, session, "error", error={"code": "response_failed", "message": "Voice response failed"})
    finally:
        if session.response_cancel is cancel:
            session.response_cancel = None


async def _process_utterance(  # noqa: C901
    ws: WebSocket,
    session: _Session,
    pcm: bytes,
    item_id: str,
    transcription_service,
    tts_service,
    speech_end: float | None = None,
) -> None:
    speech_end = speech_end if speech_end is not None else time.time()

    if session.partial_task is not None and not session.partial_task.done():
        # Let an in-flight decode finish rather than cancelling the thread mid
        # inference; the final pass would just contend for the same GPU.
        try:
            await asyncio.wait_for(session.partial_task, timeout=2.0)
        except (TimeoutError, asyncio.CancelledError):
            session.partial_task.cancel()
        except Exception:
            pass
        if not session.partial_task.done():
            session.partial_task.cancel()
    session.partial_task = None

    if not await _emit(ws, session, "input_audio_buffer.committed", item_id=item_id, previous_item_id=None):
        return

    transcript = ""
    stt_started = time.perf_counter()
    if pcm:
        try:
            transcript = await _transcribe_pcm(transcription_service, session, pcm)
        except asyncio.CancelledError:
            raise
        except Exception as exc:
            logger.exception("Transcription error in realtime handler")
            await _emit(ws, session, "error", error={"code": "transcription_failed", "message": str(exc)})
    session.last_stt_ms = (time.perf_counter() - stt_started) * 1000

    await _emit(
        ws,
        session,
        "conversation.item.input_audio_transcription.completed",
        item_id=item_id,
        content_index=0,
        transcript=transcript,
        duration_ms=round((time.perf_counter() - speech_end) * 1000, 1),
    )

    if session.session_type == "realtime" and transcript:
        if session.is_responding:
            # A new turn always supersedes an in-flight response.
            await _cancel_active_response(ws, session)
        session.response_task = asyncio.create_task(_run_voice_agent(ws, session, transcript, tts_service, speech_end))
        session.response_task.add_done_callback(lambda t: logger.error("Response pipeline failed: %s", t.exception()) if not t.cancelled() and t.exception() else None)
    else:
        session.new_item()


async def _cancel_active_response(ws: WebSocket, session: _Session, reason: str = "speech_started") -> None:
    task = session.response_task
    cancel = session.response_cancel
    if cancel is not None:
        cancel.set()
    if task is not None and not task.done():
        task.cancel()
        try:
            await task
        except asyncio.CancelledError:
            pass
        except Exception:
            pass
    session.response_task = None
    session.response_cancel = None
    await _emit(ws, session, "response.cancelled", reason=reason)


async def _handle_session_update(ws: WebSocket, session: _Session, event: dict, event_type: str, tts_service=None) -> None:  # noqa: C901
    sess_cfg = event.get("session", {})
    previous_type = session.session_type
    if "type" in sess_cfg:
        session.session_type = sess_cfg["type"]
        if session.session_type != previous_type:
            session.apply_mode_defaults()
    if "model" in sess_cfg:
        session.model = sess_cfg["model"]
    if "language" in sess_cfg:
        session.language = sess_cfg["language"] or None
    if "input_sample_rate" in sess_cfg:
        session.input_sample_rate = int(sess_cfg["input_sample_rate"])
    if "system_prompt" in sess_cfg:
        session.system_prompt = sess_cfg["system_prompt"]
    if "tts_model" in sess_cfg:
        session.tts_model = sess_cfg["tts_model"]
    if "tts_voice" in sess_cfg:
        session.tts_voice = sess_cfg["tts_voice"] or None
    td = sess_cfg.get("turn_detection") or {}
    if session.gate is not None:
        session.gate.configure(
            threshold=td.get("threshold"),
            silence_ms=td.get("silence_duration_ms"),
            preroll_ms=td.get("prefix_padding_ms"),
            onset_ms=td.get("onset_ms"),
            commit_grace_ms=td.get("commit_grace_ms"),
        )
    if session.gate is not None:
        session.speech_threshold = session.gate.threshold
    if "language" in (sess_cfg.get("transcription") or {}):
        session.language = sess_cfg["transcription"]["language"] or None
    if session.session_type == "realtime" and tts_service is not None:
        _schedule_tts_warm(session, tts_service)
    ack_type = "transcription_session.updated" if event_type == "transcription_session.update" else "session.updated"
    await _emit(ws, session, ack_type, session=_session_config(session))


async def _handle_audio_append(ws: WebSocket, session: _Session, event: dict, transcription_service, tts_service) -> None:  # noqa: C901
    audio_b64 = event.get("audio", "")
    try:
        pcm_bytes = base64.b64decode(audio_b64)
    except Exception:
        await _emit(ws, session, "error", error={"code": "invalid_audio", "message": "Failed to decode base64 audio"})
        return
    if not pcm_bytes:
        return

    # The gate always runs at the STT rate so the utterance buffer can go
    # straight to the recognizer.
    if session.input_sample_rate != _STT_SAMPLE_RATE:
        pcm_bytes = resample_pcm16(pcm_bytes, session.input_sample_rate, _STT_SAMPLE_RATE)

    # Keep a rolling copy for clients that commit manually (OpenAI semantics:
    # commit flushes everything appended, even if VAD never fired).
    session.manual_buffer.extend(pcm_bytes)
    if len(session.manual_buffer) > _STT_SAMPLE_RATE * 2 * 60:
        del session.manual_buffer[: len(session.manual_buffer) - _STT_SAMPLE_RATE * 2 * 60]

    gate = session.gate
    if gate is None:
        return
    turn_stopped = False
    stop_pcm = b""
    stop_item = ""
    for boundary in gate.feed(pcm_bytes):
        if boundary.kind == "speech_started":
            if session.is_responding:
                await _cancel_active_response(ws, session)
            session.manual_buffer.clear()
            session.new_item()
            # Warm the TTS backend during the utterance (it can take seconds).
            _schedule_tts_warm(session, tts_service)
            await _emit(
                ws,
                session,
                "input_audio_buffer.speech_started",
                audio_start_ms=max(0, boundary.audio_ms - vocal_settings.VAD_PREROLL_MS),
                item_id=session.current_item_id,
            )
            if _PARTIAL_INTERVAL_S > 0 and (session.partial_task is None or session.partial_task.done()):
                session.partial_task = asyncio.create_task(_partial_transcription_loop(ws, session, transcription_service))
        elif boundary.kind == "speech_stopped":
            turn_stopped = True
            # Snapshot and reset inline: the task may not run before the next
            # microphone frames arrive, and they must not join this utterance.
            stop_item = session.current_item_id
            stop_pcm = gate.take_utterance()
            gate.reset()
            session.manual_buffer.clear()
            await _emit(
                ws,
                session,
                "input_audio_buffer.speech_stopped",
                audio_end_ms=boundary.audio_ms,
                item_id=stop_item,
            )

    if turn_stopped:
        # Run the turn as a task so microphone ingest keeps flowing.
        asyncio.create_task(_process_utterance(ws, session, stop_pcm, stop_item, transcription_service, tts_service, time.time()))


async def _dispatch_event(ws: WebSocket, session: _Session, event: dict, transcription_service, tts_service) -> None:
    event_type = event.get("type", "")

    if event_type in ("session.update", "transcription_session.update"):
        await _handle_session_update(ws, session, event, event_type, tts_service)
    elif event_type == "input_audio_buffer.append":
        await _handle_audio_append(ws, session, event, transcription_service, tts_service)
    elif event_type == "input_audio_buffer.commit":
        gate = session.gate
        manual = bytes(session.manual_buffer)
        session.manual_buffer.clear()
        pcm = manual or (gate.take_utterance() if gate is not None else b"")
        if gate is not None:
            gate.reset()
        if not pcm:
            await _emit(ws, session, "error", error={"code": "buffer_empty", "message": "Input audio buffer is empty"})
        else:
            asyncio.create_task(_process_utterance(ws, session, pcm, session.current_item_id, transcription_service, tts_service))
    elif event_type == "input_audio_buffer.clear":
        if session.partial_task is not None and not session.partial_task.done():
            session.partial_task.cancel()
        session.partial_task = None
        if session.gate is not None:
            session.gate.reset()
        session.manual_buffer.clear()
        session.new_item()
        await _emit(ws, session, "input_audio_buffer.cleared")
    elif event_type == "response.cancel":
        await _cancel_active_response(ws, session, reason="client_cancelled")
    else:
        await _emit(ws, session, "error", error={"code": "unknown_event", "message": f"Unknown event type: {event_type}"})


@router.websocket("/v1/realtime")
async def realtime_endpoint(  # noqa: C901
    websocket: WebSocket,
    model: str | None = None,
    session_id: str | None = None,
) -> None:
    await websocket.accept()

    _evict_stale_sessions()

    resumed = bool(session_id and session_id in _session_store)
    if resumed and session_id is not None:
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
    await _send(websocket, session, _make_event(init_event, session=_session_config(session)))

    try:
        while True:
            try:
                raw = await asyncio.wait_for(
                    websocket.receive_text(),
                    timeout=float(_KEEPALIVE_S),
                )
            except TimeoutError:
                if not await _emit(websocket, session, "ping"):
                    break
                session.touch()
                continue

            session.touch()
            try:
                event = json.loads(raw)
            except json.JSONDecodeError:
                await _emit(websocket, session, "error", error={"code": "invalid_json", "message": "Could not parse JSON"})
                continue

            if event.get("type") == "pong":
                continue

            # Dispatch inline: audio ingest and VAD must keep pace with the mic.
            # Recognition and response work runs in its own tasks.
            await _dispatch_event(websocket, session, event, transcription_service, tts_service)

    except WebSocketDisconnect:
        pass
    except Exception:
        logger.exception("Realtime WebSocket error")
        await _emit(websocket, session, "error", error={"code": "server_error", "message": "Internal server error"})
    finally:
        for task in (session.partial_task, session.response_task, *session.tts_warm_tasks.values()):
            if task is not None and not task.done():
                task.cancel()
        session.partial_task = None
        session.response_task = None
        session.tts_warm_tasks.clear()
