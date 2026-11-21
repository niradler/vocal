#!/usr/bin/env python3
"""Voice-stack benchmark for a running Vocal server.

Measures the numbers that decide whether a local voice agent feels live:

* **VAD onset** - first speech frame to ``input_audio_buffer.speech_started``
* **Endpoint** - last speech frame to ``input_audio_buffer.speech_stopped``
* **Final transcript** - last speech frame to the final transcription
* **TTFA** - last speech frame to the first response audio byte
* **Live partials** - transcript deltas emitted while the user is speaking
* **TTS** - time to first audio and real-time factor for a sentence
* **HTTP STT** - latency and word error rate for a whole clip

Usage::

    # 16 kHz mono PCM WAV, ~10 s of speech
    python scripts/bench_voice.py --audio test_assets/audio/jfk.wav

    # json only, for CI or before/after comparisons
    python scripts/bench_voice.py --audio clip.wav --json out.json --only realtime

The default reference transcript matches whisper.cpp's ``jfk.wav`` sample. Use
``--reference`` (or a ``<audio>.txt`` sibling) for other clips.
"""

from __future__ import annotations

import argparse
import asyncio
import base64
import io
import json
import statistics
import sys
import time
import wave
from pathlib import Path
from typing import Any

import httpx
import numpy as np
import websockets

FRAME_MS = 100
LEAD_S = 1.5
TAIL_S = 3.0
DEFAULT_REFERENCE = "and so my fellow americans ask not what your country can do for you ask what you can do for your country"
DEFAULT_TEXT = "The sun was setting slowly, casting long shadows across the empty field."


# --------------------------------------------------------------------- audio
def read_wav(path: Path) -> tuple[np.ndarray, int]:
    with wave.open(str(path), "rb") as handle:
        if handle.getnchannels() != 1 or handle.getsampwidth() != 2:
            raise SystemExit(f"{path}: expected mono 16-bit PCM WAV (got {handle.getnchannels()} ch, {handle.getsampwidth() * 8} bit)")
        rate = handle.getframerate()
        pcm = np.frombuffer(handle.readframes(handle.getnframes()), dtype=np.int16)
    return pcm, rate


def trim_silence(pcm: np.ndarray, rate: int, threshold: int = 300, pad_ms: int = 100) -> np.ndarray:
    loud = np.flatnonzero(np.abs(pcm) > threshold)
    if loud.size == 0:
        return pcm
    pad = int(rate * pad_ms / 1000)
    return pcm[max(0, loud[0] - pad) : min(len(pcm), loud[-1] + pad)]


def wav_bytes(pcm: np.ndarray, rate: int) -> bytes:
    buffer = io.BytesIO()
    with wave.open(buffer, "wb") as handle:
        handle.setnchannels(1)
        handle.setsampwidth(2)
        handle.setframerate(rate)
        handle.writeframes(pcm.tobytes())
    return buffer.getvalue()


# -------------------------------------------------------------------- metrics
def words(text: str) -> list[str]:
    import re

    return [w for w in re.sub(r"[^a-z0-9'\s]", " ", text.lower()).split() if w]


def wer(reference: str, hypothesis: str) -> float:
    ref, hyp = words(reference), words(hypothesis)
    rows = len(ref) + 1
    cols = len(hyp) + 1
    dp = [[0] * cols for _ in range(rows)]
    for i in range(rows):
        dp[i][0] = i
    for j in range(cols):
        dp[0][j] = j
    for i in range(1, rows):
        for j in range(1, cols):
            dp[i][j] = min(
                dp[i - 1][j] + 1,
                dp[i][j - 1] + 1,
                dp[i - 1][j - 1] + (ref[i - 1] != hyp[j - 1]),
            )
    return dp[-1][-1] / max(1, len(ref))


def stats(values: list[float]) -> dict[str, float]:
    if not values:
        return {"count": 0}
    return {
        "count": len(values),
        "mean_ms": round(statistics.mean(values), 1),
        "p50_ms": round(statistics.median(values), 1),
        "p95_ms": round(sorted(values)[int(0.95 * (len(values) - 1))], 1),
        "max_ms": round(max(values), 1),
    }


# ------------------------------------------------------------------ benchmarks
async def bench_http_stt(client: httpx.AsyncClient, pcm: np.ndarray, rate: int, model: str, reference: str, runs: int = 3) -> dict[str, Any]:
    payload = wav_bytes(pcm, rate)
    latencies: list[float] = []
    text = ""
    for _ in range(runs):
        started = time.perf_counter()
        response = await client.post(
            "/v1/audio/transcriptions",
            files={"file": ("clip.wav", payload, "audio/wav")},
            data={"model": model, "response_format": "json"},
        )
        response.raise_for_status()
        latencies.append((time.perf_counter() - started) * 1000)
        text = response.json()["text"]
    audio_seconds = len(pcm) / rate
    return {
        "latency_ms": stats(latencies),
        "audio_seconds": round(audio_seconds, 2),
        "realtime_factor": round(latencies[0] / 1000 / audio_seconds, 3),
        "wer": round(wer(reference, text), 4),
        "text": text.strip(),
    }


async def bench_tts(client: httpx.AsyncClient, model: str, text: str, runs: int = 3) -> dict[str, Any]:
    first_byte: list[float] = []
    total: list[float] = []
    audio_seconds = 0.0
    rate = 24000
    for _ in range(runs):
        started = time.perf_counter()
        first = -1.0
        size = 0
        async with client.stream(
            "POST",
            "/v1/audio/speech",
            json={"model": model, "input": text, "response_format": "pcm", "stream": True},
        ) as response:
            response.raise_for_status()
            rate = int(response.headers.get("x-sample-rate", rate))
            async for chunk in response.aiter_bytes():
                if not chunk:
                    continue
                if first < 0:
                    first = (time.perf_counter() - started) * 1000
                size += len(chunk)
        total.append((time.perf_counter() - started) * 1000)
        first_byte.append(first if first >= 0 else total[-1])
        audio_seconds = size / 2 / rate
    return {
        "first_audio_ms": stats(first_byte),
        "total_ms": stats(total),
        "audio_seconds": round(audio_seconds, 2),
        "realtime_factor": round(statistics.mean(first_byte) / 1000 / audio_seconds, 3) if audio_seconds else 0.0,
    }


async def bench_realtime(  # noqa: C901
    ws_base: str, pcm: np.ndarray, rate: int, model: str, tts_model: str, reference: str, session_type: str = "realtime"
) -> dict[str, Any]:
    frame = int(rate * FRAME_MS / 1000)
    lead = np.zeros(int(rate * LEAD_S), dtype=np.int16)
    tail = np.zeros(int(rate * TAIL_S), dtype=np.int16)
    stream = np.concatenate([lead, pcm, tail])

    events: list[tuple[float, dict]] = []
    first_speech = -1.0
    last_speech = -1.0

    async with websockets.connect(f"{ws_base}/v1/realtime?model={model}", max_size=None, ping_interval=None) as socket:
        await socket.recv()  # session.created
        await socket.send(
            json.dumps(
                {
                    "type": "session.update",
                    "session": {
                        "type": session_type,
                        "model": model,
                        "input_sample_rate": rate,
                        "tts_model": tts_model,
                        "language": "en",
                    },
                }
            )
        )
        await socket.recv()  # session.updated

        async def reader() -> None:
            while True:
                try:
                    raw = await asyncio.wait_for(socket.recv(), timeout=45)
                except (TimeoutError, websockets.ConnectionClosed):
                    return
                events.append((time.perf_counter(), json.loads(raw)))

        reader_task = asyncio.create_task(reader())

        for offset in range(0, len(stream), frame):
            chunk = stream[offset : offset + frame]
            await socket.send(json.dumps({"type": "input_audio_buffer.append", "audio": base64.b64encode(chunk.tobytes()).decode()}))
            now = time.perf_counter()
            if offset >= lead.size and bool(np.any(np.abs(chunk.astype(np.int32)) > 300)):
                if first_speech < 0:
                    first_speech = now
                last_speech = now
            await asyncio.sleep(FRAME_MS / 1000)

        deadline = time.perf_counter() + 60
        while time.perf_counter() < deadline:
            completed = [at for at, event in events if event.get("type") == "conversation.item.input_audio_transcription.completed"]
            if session_type == "realtime":
                if any(event.get("type") == "response.done" for _, event in events):
                    break
            elif completed and time.perf_counter() > max(completed[-1], last_speech) + 1.5:
                # Dictation commits every pause, so wait for the final turn
                # instead of the first one.
                break
            await asyncio.sleep(0.05)
        reader_task.cancel()

    def matching(kind: str) -> list[tuple[float, dict]]:
        return [(at, event) for at, event in events if event.get("type") == kind]

    started = matching("input_audio_buffer.speech_started")
    stopped = matching("input_audio_buffer.speech_stopped")
    finals = matching("conversation.item.input_audio_transcription.completed")
    audio = matching("response.output_audio.delta")
    partials = [at for at, _ in matching("conversation.item.input_audio_transcription.delta")]

    def delta_ms(at: float | None, base: float) -> float:
        return round((at - base) * 1000, 1) if at is not None and base > 0 else -1.0

    # Use the last turn: dictation commits at every pause, and the final turn
    # is the one that ends after the last speech frame.
    first_onset = started[0][0] if started else None
    last_stop = stopped[-1][0] if stopped else None
    last_final = finals[-1][0] if finals else None
    transcript = " ".join((event.get("transcript") or "").strip() for _, event in finals if (event.get("transcript") or "").strip())
    return {
        "session_type": session_type,
        "speech_seconds": round(len(pcm) / rate, 2),
        "turns": len(finals),
        "vad_onset_ms": delta_ms(first_onset, first_speech),
        "endpoint_ms": delta_ms(last_stop, last_speech),
        "final_transcript_ms": delta_ms(last_final, last_speech),
        "final_transcript_after_endpoint_ms": delta_ms(last_final, last_stop) if last_stop else -1.0,
        "ttfa_ms": delta_ms(audio[0][0] if audio else None, last_speech),
        "partials": len(partials),
        "partials_while_speaking": sum(1 for at in partials if last_speech > 0 and at < last_speech),
        "first_partial_ms": delta_ms(partials[0] if partials else None, first_speech),
        "barge_in": any(event.get("type") == "response.cancelled" for _, event in events),
        "transcript": transcript,
        "wer": round(wer(reference, transcript), 4),
    }


async def run(args: argparse.Namespace) -> dict[str, Any]:
    audio = Path(args.audio)
    if not audio.exists():
        raise SystemExit(f"{audio} not found. Point --audio at a 16 kHz mono WAV (e.g. whisper.cpp's samples/jfk.wav).")

    pcm, rate = read_wav(audio)
    pcm = trim_silence(pcm, rate)
    reference = args.reference
    if reference is None:
        sibling = audio.with_suffix(audio.suffix + ".txt")
        reference = sibling.read_text(encoding="utf-8") if sibling.exists() else DEFAULT_REFERENCE

    ws_base = args.api.replace("http://", "ws://").replace("https://", "wss://")
    results: dict[str, Any] = {
        "harness": "vocal",
        "api": args.api,
        "audio": str(audio),
        "audio_seconds": round(len(pcm) / rate, 2),
    }
    only = set(args.only)

    async with httpx.AsyncClient(base_url=args.api, timeout=300) as client:
        if "stt" in only:
            results["http_stt"] = await bench_http_stt(client, pcm, rate, args.model, reference)
        if "tts" in only:
            results["tts"] = await bench_tts(client, args.tts_model, args.text)
        if "realtime" in only:
            results["realtime"] = await bench_realtime(ws_base, pcm, rate, args.model, args.tts_model, reference, "realtime")
        if "dictation" in only:
            results["dictation"] = await bench_realtime(ws_base, pcm, rate, args.model, args.tts_model, reference, "transcription")
    return results


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--api", default="http://127.0.0.1:8000", help="Vocal base URL")
    parser.add_argument("--audio", default="test_assets/audio/jfk.wav", help="16 kHz mono PCM WAV")
    parser.add_argument("--reference", default=None, help="Reference transcript for WER (default: <audio>.txt or the jfk text)")
    parser.add_argument("--model", default="Systran/faster-whisper-base", help="STT model id")
    parser.add_argument("--tts-model", default="hexgrad/Kokoro-82M", help="TTS model id")
    parser.add_argument("--text", default=DEFAULT_TEXT, help="Sentence to synthesize for the TTS benchmark")
    parser.add_argument(
        "--only",
        nargs="+",
        default=["stt", "tts", "realtime", "dictation"],
        choices=["stt", "tts", "realtime", "dictation"],
        help="Which benchmarks to run",
    )
    parser.add_argument("--json", default=None, help="Write results to this path")
    args = parser.parse_args()

    results = asyncio.run(run(args))
    payload = json.dumps(results, indent=2)
    print(payload)
    if args.json:
        Path(args.json).write_text(payload, encoding="utf-8")
    return 0


if __name__ == "__main__":
    sys.exit(main())
