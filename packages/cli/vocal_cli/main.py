import asyncio
import base64
import io
import json
import queue
import sys
import threading
import time
import wave
from pathlib import Path

import httpx
import numpy as np
import sounddevice as sd
import typer
import websockets
from rich.console import Console
from rich.table import Table

from vocal_core.config import vocal_settings
from vocal_sdk import VocalClient
from vocal_sdk.api.audio import voice_clone_v1_audio_clone_post
from vocal_sdk.api.models import (
    delete_model_v1_models_model_id_delete,
    list_models_v1_models_get,
)
from vocal_sdk.api.transcription import (
    create_transcription_v1_audio_transcriptions_post,
    create_translation_v1_audio_translations_post,
)
from vocal_sdk.models import (
    BodyCreateTranscriptionV1AudioTranscriptionsPost,
    BodyCreateTranslationV1AudioTranslationsPost,
    BodyVoiceCloneV1AudioClonePost,
    TranscriptionFormat,
)
from vocal_sdk.types import UNSET, File, Unset

app = typer.Typer(
    name="vocal",
    help="Vocal - Generic Speech AI Platform CLI",
    no_args_is_help=True,
)

models_app = typer.Typer(help="Model management commands")
app.add_typer(models_app, name="models")

console = Console()

_SAMPLE_RATE = vocal_settings.STT_SAMPLE_RATE
_FRAME_SIZE = vocal_settings.AUDIO_FRAME_SIZE
_CHANNELS = vocal_settings.AUDIO_CHANNELS
_PLAYBACK_COOLDOWN = vocal_settings.PLAYBACK_COOLDOWN
_CALIB_FRAMES = 15

_print_lock = threading.Lock()


def _get_device_rate(device_idx: int | None) -> int:
    dev = sd.query_devices(device_idx if device_idx is not None else sd.default.device[0])
    return int(dev["default_samplerate"])


def _resample_frame(frame: np.ndarray, from_rate: int, to_rate: int) -> np.ndarray:
    if from_rate == to_rate:
        return frame
    col = frame[:, 0] if frame.ndim > 1 else frame
    n_out = int(len(col) * to_rate / from_rate)
    if n_out == 0:
        return np.zeros((0, 1), dtype=frame.dtype) if frame.ndim > 1 else np.zeros(0, dtype=frame.dtype)
    resampled = np.interp(np.linspace(0, len(col) - 1, n_out), np.arange(len(col)), col.astype(np.float32)).astype(np.int16)
    return resampled.reshape(-1, 1) if frame.ndim > 1 else resampled


def _make_client(api_url: str) -> VocalClient:
    return VocalClient(base_url=api_url, timeout=httpx.Timeout(300.0), raise_on_unexpected_status=True)


@app.command("transcribe")
def transcribe(
    audio_file: Path = typer.Argument(..., help="Path to audio file to transcribe"),
    model: str = typer.Option(
        vocal_settings.STT_DEFAULT_MODEL,
        "--model",
        "-m",
        help="STT model to use",
    ),
    language: str | None = typer.Option(None, "--language", "-l", help="Language code (e.g., 'en', 'es')"),
    output_format: str = typer.Option("text", "--format", "-f", help="Output format: text, json, srt, vtt"),
    api_url: str = typer.Option("http://localhost:8000", "--api-url", envvar="VOCAL_API_URL", help="Vocal API URL"),
):
    """Transcribe an audio file to text"""
    if not audio_file.exists():
        console.print(f"[red]Error:[/red] File not found: {audio_file}")
        raise typer.Exit(1)

    try:
        vc = _make_client(api_url)
        console.print("Transcribing audio...")

        with open(audio_file, "rb") as fobj:
            body = BodyCreateTranscriptionV1AudioTranscriptionsPost(
                file=File(payload=fobj, file_name=audio_file.name),
                model=model,
                language=language if language is not None else UNSET,
                response_format=TranscriptionFormat.JSON,
            )
            result = create_transcription_v1_audio_transcriptions_post.sync(client=vc, body=body)

        if result is None:
            console.print("[red]Error:[/red] Transcription failed - no response")
            raise typer.Exit(1)

        if output_format == "text":
            console.print(result.text)
        elif output_format == "json":
            console.print_json(json.dumps(result.to_dict()))
        elif output_format in ("srt", "vtt"):
            segs = [] if isinstance(result.segments, Unset) or result.segments is None else result.segments
            if output_format == "vtt":
                console.print("WEBVTT\n")
            for seg in segs:
                if output_format == "srt":
                    console.print(f"{seg.id + 1}")
                    console.print(f"{_format_timestamp(seg.start)} --> {_format_timestamp(seg.end)}")
                else:
                    console.print(f"{_format_timestamp(seg.start, use_comma=False)} --> {_format_timestamp(seg.end, use_comma=False)}")
                console.print(seg.text)
                console.print()

    except Exception as e:
        console.print(f"[red]Error:[/red] {str(e)}")
        raise typer.Exit(1)


@models_app.command("list")
def models_list(
    task: str | None = typer.Option(None, "--task", "-t", help="Filter by task: stt, tts"),
    api_url: str = typer.Option("http://localhost:8000", "--api-url", envvar="VOCAL_API_URL", help="Vocal API URL"),
):
    """List all available models"""
    try:
        vc = _make_client(api_url)
        response = list_models_v1_models_get.sync(client=vc, task=task if task is not None else UNSET)

        if response is None:
            console.print("[red]Error:[/red] Failed to list models")
            raise typer.Exit(1)

        table = Table(title="Vocal Models")
        table.add_column("Model ID", style="cyan")
        table.add_column("Task", style="magenta")
        table.add_column("Status", style="green")
        table.add_column("Size", style="yellow")

        for m in response.models:
            status_val = m.status.value
            status_color = {
                "available": "green",
                "downloading": "yellow",
                "not_downloaded": "red",
            }.get(status_val, "white")
            size = str(m.size_readable) if not isinstance(m.size_readable, Unset) else "N/A"
            table.add_row(
                m.id,
                m.task.value,
                f"[{status_color}]{status_val}[/{status_color}]",
                size,
            )

        console.print(table)
        console.print(f"\nTotal models: {response.total}")

    except Exception as e:
        console.print(f"[red]Error:[/red] {str(e)}")
        raise typer.Exit(1)


def _pull_stream(pull_url: str, model_id: str) -> queue.SimpleQueue:
    q: queue.SimpleQueue = queue.SimpleQueue()

    def _reader():
        try:
            with httpx.stream("POST", pull_url, json={"model": model_id}, timeout=None) as resp:
                resp.raise_for_status()
                for line in resp.iter_lines():
                    if line:
                        q.put(json.loads(line))
        except Exception as e:
            q.put({"status": "error", "message": str(e)})
        finally:
            q.put(None)

    threading.Thread(target=_reader, daemon=True).start()
    return q


@models_app.command("pull")
def models_pull(
    model_id: str = typer.Argument(..., help="Model ID to download"),
    api_url: str = typer.Option("http://localhost:8000", "--api-url", envvar="VOCAL_API_URL", help="Vocal API URL"),
):
    """Download a model (Ollama-style pull)"""
    try:
        q = _pull_stream(f"{api_url}/v1/models/pull", model_id)
        with console.status(f"[cyan]Pulling {model_id}...[/cyan]"):
            while True:
                try:
                    data = q.get(timeout=0.2)
                except queue.Empty:
                    continue
                if data is None:
                    break
                s = data.get("status", "")
                if s == "available":
                    break
                if s == "error":
                    console.print(f"[red]Error:[/red] {data.get('message')}")
                    raise typer.Exit(1)
        console.print(f"[green]Successfully pulled:[/green] {model_id}")
    except typer.Exit:
        raise
    except Exception as e:
        console.print(f"[red]Error:[/red] {str(e)}")
        raise typer.Exit(1)


@models_app.command("delete")
def models_delete(
    model_id: str = typer.Argument(..., help="Model ID to delete"),
    api_url: str = typer.Option("http://localhost:8000", "--api-url", envvar="VOCAL_API_URL", help="Vocal API URL"),
    force: bool = typer.Option(False, "--force", "-f", help="Skip confirmation prompt"),
):
    """Delete a downloaded model"""
    if not force:
        confirm = typer.confirm(f"Are you sure you want to delete {model_id}?")
        if not confirm:
            console.print("Cancelled")
            raise typer.Exit(0)

    try:
        vc = _make_client(api_url)
        delete_model_v1_models_model_id_delete.sync(model_id=model_id, client=vc)
        console.print(f"[green]Successfully deleted:[/green] {model_id}")
    except Exception as e:
        console.print(f"[red]Error:[/red] {str(e)}")
        raise typer.Exit(1)


@app.command()
def clone(
    text: str = typer.Argument(..., help="Text to synthesize in the cloned voice"),
    reference: Path = typer.Option(..., "--reference", "-r", help="Reference audio file (wav/mp3/m4a, 3-30s recommended)"),
    output: Path | None = typer.Option(None, "--output", "-o", help="Output file path (default: stdout binary)"),
    model: str = typer.Option(
        vocal_settings.TTS_DEFAULT_CLONE_MODEL,
        "--model",
        "-m",
        help="TTS model to use for voice cloning (must support cloning)",
    ),
    reference_text: str | None = typer.Option(None, "--reference-text", help="Optional transcript of the reference audio"),
    language: str = typer.Option("en", "--language", "-l", help="Target language code (e.g. 'en', 'zh')"),
    response_format: str = typer.Option("wav", "--format", "-f", help="Output audio format: wav, mp3, flac, pcm"),
    api_url: str = typer.Option("http://localhost:8000", "--api-url", envvar="VOCAL_API_URL", help="Vocal API URL"),
) -> None:
    """Clone a voice from a reference recording and synthesize text with it"""
    if not reference.exists():
        console.print(f"[red]Error:[/red] Reference file not found: {reference}")
        raise typer.Exit(1)

    try:
        vc = _make_client(api_url)
        console.print(f"[dim]Cloning voice from [cyan]{reference.name}[/cyan]...[/dim]")

        with open(reference, "rb") as fobj:
            body = BodyVoiceCloneV1AudioClonePost(
                reference_audio=File(payload=fobj, file_name=reference.name),
                text=text,
                model=model,
                reference_text=reference_text if reference_text is not None else UNSET,
                language=language,
            )
            resp = voice_clone_v1_audio_clone_post.sync_detailed(client=vc, body=body)

        if resp.status_code != 200:
            console.print(f"[red]Error:[/red] Server returned {resp.status_code}")
            raise typer.Exit(1)

        audio_bytes = resp.content
        if output:
            output.write_bytes(audio_bytes)
            console.print(f"[green]Saved[/green] {len(audio_bytes):,} bytes → [cyan]{output}[/cyan]")
        else:
            sys.stdout.buffer.write(audio_bytes)

    except typer.Exit:
        raise
    except Exception as e:
        console.print(f"[red]Error:[/red] {e}")
        raise typer.Exit(1)


@app.command()
def serve(
    host: str = typer.Option("0.0.0.0", "--host", "-h", help="Host to bind to"),
    port: int = typer.Option(8000, "--port", "-p", help="Port to bind to"),
    reload: bool = typer.Option(False, "--reload", help="Enable auto-reload"),
):
    """Start the Vocal API server"""
    import uvicorn

    console.print("[green]Starting Vocal API server...[/green]")
    console.print(f"API: http://{host}:{port}")
    console.print(f"Docs: http://{host}:{port}/docs")

    try:
        uvicorn.run("vocal_api.main:app", host=host, port=port, reload=reload)
    except KeyboardInterrupt:
        console.print("\n[yellow]Server stopped[/yellow]")
    except Exception as e:
        console.print(f"[red]Error:[/red] {str(e)}")
        raise typer.Exit(1)


def _input_devices() -> list[dict]:
    """Return all input-capable audio devices with their index, name, channels, host API, and default flag."""
    default_idx = sd.default.device[0]
    host_apis = sd.query_hostapis()
    devices = []
    for idx, dev in enumerate(sd.query_devices()):
        if dev["max_input_channels"] > 0:
            api_name = host_apis[dev["hostapi"]]["name"]
            devices.append(
                {
                    "index": idx,
                    "name": dev["name"],
                    "channels": dev["max_input_channels"],
                    "sample_rate": int(dev["default_samplerate"]),
                    "api": api_name,
                    "is_default": idx == default_idx,
                }
            )
    return devices


def _resolve_device(device: str | None) -> int | None:
    """Resolve --device value to a sounddevice index (int) or None for OS default."""
    if device is None:
        return None
    if device.isdigit():
        return int(device)
    for dev in _input_devices():
        if device.lower() in dev["name"].lower():
            return dev["index"]
    raise ValueError(f"No input device matching '{device}'. Run `vocal devices` to list available inputs.")


def _print_devices_table() -> None:
    devs = _input_devices()
    if not devs:
        console.print("[red]No input devices found.[/red]")
        return
    table = Table(title="Available Input Devices")
    table.add_column("#", style="cyan", justify="right")
    table.add_column("Name", style="white")
    table.add_column("API", style="dim")
    table.add_column("Ch", justify="right")
    table.add_column("Rate", justify="right", style="yellow")
    table.add_column("", style="green")
    for dev in devs:
        table.add_row(
            str(dev["index"]),
            dev["name"],
            dev["api"],
            str(dev["channels"]),
            f"{dev['sample_rate']} Hz",
            "* default" if dev["is_default"] else "",
        )
    console.print(table)
    console.print('\nOn Windows, prefer [cyan]WASAPI[/cyan] entries for best quality.')
    console.print('Use [cyan]--device <#>[/cyan] or [cyan]--device "name"[/cyan] to select.')


@app.command()
def devices(
    output: bool = typer.Option(False, "--output", help="List output devices instead of input devices"),
) -> None:
    """List available audio input devices (use --output for playback devices)"""
    if output:
        _print_output_devices_table()
    else:
        _print_devices_table()


def _pcm_to_wav(frames: list) -> io.BytesIO:
    buf = io.BytesIO()
    with wave.open(buf, "wb") as wf:
        wf.setnchannels(_CHANNELS)
        wf.setsampwidth(2)
        wf.setframerate(_SAMPLE_RATE)
        wf.writeframes(np.concatenate(frames, axis=0).tobytes())
    buf.seek(0)
    return buf


def _rms_energy(frame) -> float:
    return float(np.sqrt(np.mean(frame.astype(np.float32) ** 2)))


def _calibrate_from_frames(frames: list) -> float:
    energies = [_rms_energy(f) for f in frames]
    noise_floor = float(np.mean(energies)) if energies else 0.0
    return max(noise_floor * 4.0, 50.0)


def _status_line(energy: float, threshold: float) -> str:
    width = 20
    filled = min(int(width * energy / max(threshold * 2, 1)), width)
    bar = "█" * filled + "░" * (width - filled)
    state = "speaking" if energy >= threshold else "silent "
    return f"\r  [{bar}] {energy:6.0f} / {threshold:.0f}  {state}  "


def _schedule_flush(
    frames: list,
    has_speech: bool,
    vc,
    model: str,
    language: str | None,
    task: str,
    verbose: bool,
) -> threading.Thread:
    t = threading.Thread(target=_flush_buffer, args=(frames, has_speech, vc, model, language, task, verbose), daemon=True)
    t.start()
    return t


def _await_pending(pending: threading.Thread | None, timeout: float = 5.0) -> None:
    if pending and pending.is_alive():
        pending.join(timeout=timeout)


def _run_stream(
    q: queue.SimpleQueue,
    silence_frames_needed: int,
    max_chunk_duration: float,
    user_threshold: float | None,
    vc,
    model: str,
    language: str | None,
    task: str,
    verbose: bool,
) -> None:
    calib_buf: list = []
    threshold = user_threshold or 0.0
    calibrated = user_threshold is not None
    buffer: list = []
    silence_count = 0
    has_speech = False
    pending: threading.Thread | None = None

    try:
        while True:
            try:
                frame = q.get(timeout=0.2)
            except queue.Empty:
                continue

            if not calibrated:
                calib_buf.append(frame)
                sys.stdout.write(f"\r  Calibrating mic... {len(calib_buf)}/{_CALIB_FRAMES} frames  ")
                sys.stdout.flush()
                if len(calib_buf) >= _CALIB_FRAMES:
                    threshold = _calibrate_from_frames(calib_buf)
                    calibrated = True
                    sys.stdout.write(f"\r  Threshold set: {threshold:.0f}  (speak now)               \n")
                    sys.stdout.flush()
                continue

            buffer.append(frame)
            energy = _rms_energy(frame)
            total_duration = len(buffer) * _FRAME_SIZE / _SAMPLE_RATE

            with _print_lock:
                sys.stdout.write(_status_line(energy, threshold))
                sys.stdout.flush()

            if energy >= threshold:
                has_speech = True
                silence_count = 0
            else:
                silence_count += 1

            chunk_done = total_duration >= max_chunk_duration or (has_speech and silence_count >= silence_frames_needed)
            if chunk_done:
                with _print_lock:
                    sys.stdout.write("\r" + " " * 60 + "\r")
                    sys.stdout.flush()
                pending = _schedule_flush(buffer, has_speech, vc, model, language, task, verbose)
                buffer, silence_count, has_speech = [], 0, False

    except KeyboardInterrupt:
        with _print_lock:
            sys.stdout.write("\r" + " " * 60 + "\r")
            sys.stdout.flush()
        _await_pending(pending, timeout=5.0)
        raise


def _flush_buffer(
    frames: list,
    has_speech: bool,
    vc: VocalClient,
    model: str,
    language: str | None,
    task: str,
    verbose: bool,
) -> None:
    if not frames or not has_speech:
        return
    audio_secs = len(frames) * _FRAME_SIZE / _SAMPLE_RATE
    with _print_lock:
        sys.stdout.write("\r" + " " * 60 + "\r")
        sys.stdout.write(f"  [dim]→ {audio_secs:.1f}s[/dim]  ")
        sys.stdout.flush()
    wav_buf = _pcm_to_wav(frames)
    t0 = time.monotonic()
    try:
        if task == "translate":
            body = BodyCreateTranslationV1AudioTranslationsPost(
                file=File(payload=wav_buf, file_name="mic.wav", mime_type="audio/wav"),
                model=model,
            )
            result = create_translation_v1_audio_translations_post.sync(client=vc, body=body)
        else:
            body = BodyCreateTranscriptionV1AudioTranscriptionsPost(
                file=File(payload=wav_buf, file_name="mic.wav", mime_type="audio/wav"),
                model=model,
                language=language if language is not None else UNSET,
                response_format=TranscriptionFormat.JSON,
            )
            result = create_transcription_v1_audio_transcriptions_post.sync(client=vc, body=body)
        elapsed = time.monotonic() - t0
        with _print_lock:
            sys.stdout.write("\r" + " " * 60 + "\r")
            sys.stdout.flush()
            if result is None:
                console.print(f"[red]error[/red] after {elapsed:.1f}s: server returned an error (run with --verbose or check server logs)")
            elif result.text.strip():
                suffix = f"  [dim]({elapsed:.1f}s)[/dim]" if verbose else ""
                console.print(f"[cyan]>[/cyan] {result.text.strip()}{suffix}")
    except Exception as e:
        elapsed = time.monotonic() - t0
        with _print_lock:
            sys.stdout.write("\r" + " " * 60 + "\r")
            sys.stdout.flush()
            console.print(f"[red]error[/red] after {elapsed:.1f}s: {e}")


def _device_wizard() -> str | None:
    devs = _input_devices()
    if not devs:
        console.print("[red]No input devices found.[/red]")
        return None
    console.print("\n[bold]Select input device:[/bold]")
    console.print("[dim]Same device may appear multiple times for different audio APIs — WASAPI is recommended on Windows.[/dim]\n")
    default_pos = next((i for i, d in enumerate(devs) if d["is_default"]), 0)
    for i, dev in enumerate(devs):
        markers = []
        if dev["is_default"]:
            markers.append("[green]default[/green]")
        if "wasapi" in dev["api"].lower():
            markers.append("[cyan]recommended[/cyan]")
        suffix = f"  [{', '.join(markers)}]" if markers else ""
        console.print(f"  [cyan]{i}[/cyan]  {dev['name']}  [dim]{dev['api']} · {dev['sample_rate']} Hz[/dim]{suffix}")
    raw = typer.prompt("\nDevice", default=str(default_pos))
    if raw.isdigit():
        pos = int(raw)
        if 0 <= pos < len(devs):
            return str(devs[pos]["index"])
    for dev in devs:
        if raw.lower() in dev["name"].lower():
            return str(dev["index"])
    console.print("[red]Invalid selection.[/red]")
    return None


def _model_wizard(api_url: str) -> str | None:
    try:
        probe = VocalClient(base_url=api_url, timeout=httpx.Timeout(5.0), raise_on_unexpected_status=False)
        result = list_models_v1_models_get.sync(client=probe, task="stt")
    except Exception as e:
        console.print(f"[red]Could not reach API:[/red] {e}")
        return None

    if result is None:
        console.print("[red]No response from API.[/red]")
        return None

    models = [m for m in result.models if str(m.status).lower().endswith("available")]
    if not models:
        console.print("[yellow]No downloaded STT models found.[/yellow] Run [cyan]vocal models pull <id>[/cyan] first.")
        return None

    default_model = vocal_settings.STT_DEFAULT_MODEL
    default_pos = next((i for i, m in enumerate(models) if m.id == default_model), 0)

    console.print("\n[bold]Select STT model:[/bold]")
    console.print("[dim]Only downloaded (available) models are shown.[/dim]\n")
    for i, m in enumerate(models):
        size = f"  [dim]{m.size_readable}[/dim]" if not isinstance(m.size_readable, Unset) else ""
        backend = f"  [dim]{m.backend.value}[/dim]" if not isinstance(m.backend, Unset) else ""
        is_default = m.id == default_model
        marker = "  [green]default[/green]" if is_default else ""
        console.print(f"  [cyan]{i}[/cyan]  {m.id}{size}{backend}{marker}")

    raw = typer.prompt("\nModel", default=str(default_pos))
    if raw.isdigit():
        pos = int(raw)
        if 0 <= pos < len(models):
            return models[pos].id
    for m in models:
        if raw.lower() in m.id.lower():
            return m.id
    console.print("[red]Invalid selection.[/red]")
    return None


def _listen_stream(device_idx: int | None, model: str, task: str, language: str | None, api_url: str, verbose: bool) -> None:
    ws_url = api_url.replace("http://", "ws://").replace("https://", "wss://")
    params = f"model={model}&task={task}"
    if language:
        params += f"&language={language}"
    endpoint = f"{ws_url}/v1/audio/stream?{params}"
    active_device = sd.query_devices(device_idx if device_idx is not None else sd.default.device[0])
    device_label = f"[dim]{active_device['name']}[/dim]"
    console.print(f"[green]Streaming...[/green] model=[cyan]{model}[/cyan] task=[cyan]{task}[/cyan] device={device_label}  Ctrl+C to stop\n")
    try:
        asyncio.run(_live_async(endpoint, device_idx, verbose))
    except KeyboardInterrupt:
        console.print("\n[yellow]Stopped.[/yellow]")
    except Exception as e:
        console.print(f"[red]Error:[/red] {e}")
        raise typer.Exit(1)


def _check_model_ready(api_url: str, model: str) -> None:
    probe = VocalClient(base_url=api_url, timeout=httpx.Timeout(5.0), raise_on_unexpected_status=False)
    console.print("[dim]Checking model status...[/dim]", end=" ")
    try:
        models_result = list_models_v1_models_get.sync(client=probe)
        model_info = next((m for m in (models_result.models if models_result else []) if m.id == model), None)
        if model_info is None:
            console.print(f"[red]not found[/red]\nRun `vocal models pull {model}` first.")
            raise typer.Exit(1)
        status = str(model_info.status).lower()
        if "available" in status:
            console.print("[green]ready[/green]")
        else:
            console.print(f"[yellow]{status}[/yellow] — first transcription may be slow")
    except typer.Exit:
        raise
    except Exception:
        console.print("[red]unreachable[/red]")
        console.print("API server is not running. Start it with: [cyan]vocal serve[/cyan]")
        raise typer.Exit(1)


def _listen_vad(
    device_idx: int | None,
    model: str,
    task: str,
    language: str | None,
    api_url: str,
    silence_threshold: float | None,
    silence_duration: float,
    max_chunk_duration: float,
    verbose: bool,
) -> None:
    active_device = sd.query_devices(device_idx if device_idx is not None else sd.default.device[0])
    device_label = f"[dim]{active_device['name']}[/dim]"
    silence_frames_needed = int(silence_duration * _SAMPLE_RATE / _FRAME_SIZE)
    _check_model_ready(api_url, model)
    vc = VocalClient(base_url=api_url, timeout=httpx.Timeout(60.0), raise_on_unexpected_status=True)
    threshold_hint = f"threshold=[cyan]{silence_threshold:.0f}[/cyan]" if silence_threshold is not None else "threshold=[cyan]auto[/cyan]"
    console.print(f"[green]Listening...[/green] model=[cyan]{model}[/cyan] task=[cyan]{task}[/cyan] device={device_label}  {threshold_hint}  Ctrl+C to stop\n")
    audio_queue: queue.SimpleQueue = queue.SimpleQueue()
    native_rate = _get_device_rate(device_idx)
    native_blocksize = int(_FRAME_SIZE * native_rate / _SAMPLE_RATE)

    def _audio_callback(indata, _frames, _ts, _status):
        audio_queue.put(_resample_frame(indata, native_rate, _SAMPLE_RATE).copy())

    try:
        with sd.InputStream(
            samplerate=native_rate,
            channels=_CHANNELS,
            dtype="int16",
            blocksize=native_blocksize,
            device=device_idx,
            callback=_audio_callback,
        ):
            _run_stream(audio_queue, silence_frames_needed, max_chunk_duration, silence_threshold, vc, model, language, task, verbose)
    except KeyboardInterrupt:
        console.print("\n[yellow]Stopped.[/yellow]")
    except Exception as e:
        console.print(f"[red]Error:[/red] {e}")
        raise typer.Exit(1)


@app.command()
def listen(
    model: str = typer.Option(vocal_settings.STT_DEFAULT_MODEL, "--model", "-m", help="STT model to use"),
    language: str | None = typer.Option(None, "--language", "-l", help="Language code (e.g. 'en'). Auto-detects if omitted."),
    task: str = typer.Option("transcribe", "--task", help="'transcribe' (default) or 'translate' to English"),
    device: str | None = typer.Option(None, "--device", "-d", help="Input device index or name. Use --devices to pick interactively."),
    devices: bool = typer.Option(False, "--devices", help="Show a device picker and select your input source before starting"),
    models: bool = typer.Option(False, "--models", help="Show a model picker from downloaded STT models before starting"),
    stream: bool = typer.Option(False, "--stream", help="Low-latency mode (~200ms) that streams audio over WebSocket. Default mode waits for a pause in speech before sending."),
    silence_threshold: float | None = typer.Option(None, "--silence-threshold", help="Mic sensitivity level. Auto-set from ambient noise at startup. Ignored with --stream."),
    silence_duration: float = typer.Option(1.5, "--silence-duration", help="Seconds of quiet that trigger a transcription. Ignored with --stream."),
    max_chunk_duration: float = typer.Option(10.0, "--max-chunk-duration", help="Max recording length (seconds) before forcing a send. Ignored with --stream."),
    api_url: str = typer.Option("http://localhost:8000", "--api-url", envvar="VOCAL_API_URL", help="Vocal API URL"),
    verbose: bool = typer.Option(False, "--verbose", "-v", help="Show latency and timing info on each transcription"),
):
    """Transcribe microphone audio in real-time.

    By default, audio is sent after each pause in speech (good accuracy, ~1-2s delay).
    Use --stream for continuous low-latency output (~200ms) over WebSocket.
    """
    if devices:
        selected = _device_wizard()
        if selected is None:
            raise typer.Exit(1)
        device = selected
    if models:
        selected_model = _model_wizard(api_url)
        if selected_model is None:
            raise typer.Exit(1)
        model = selected_model
    try:
        device_idx = _resolve_device(device)
    except ValueError as e:
        console.print(f"[red]Error:[/red] {e}")
        raise typer.Exit(1)
    if stream:
        _listen_stream(device_idx, model, task, language, api_url, verbose)
    else:
        _listen_vad(device_idx, model, task, language, api_url, silence_threshold, silence_duration, max_chunk_duration, verbose)


_DEFAULT_SYSTEM_PROMPT = vocal_settings.CHAT_SYSTEM_PROMPT


def _output_devices() -> list[dict]:
    seen: set[str] = set()
    devices = []
    default_idx = sd.default.device[1]
    for idx, dev in enumerate(sd.query_devices()):
        if dev["max_output_channels"] > 0 and dev["name"] not in seen:
            seen.add(dev["name"])
            devices.append(
                {
                    "index": idx,
                    "name": dev["name"],
                    "channels": dev["max_output_channels"],
                    "sample_rate": int(dev["default_samplerate"]),
                    "is_default": idx == default_idx,
                }
            )
    return devices


def _resolve_output_device(device: str | None) -> int | None:
    if device is None:
        return None
    if device.isdigit():
        return int(device)
    for dev in _output_devices():
        if device.lower() in dev["name"].lower():
            return dev["index"]
    raise ValueError(f"No output device matching '{device}'. Run `vocal devices --output` to list available outputs.")


def _print_output_devices_table() -> None:
    devs = _output_devices()
    if not devs:
        console.print("[red]No output devices found.[/red]")
        return
    table = Table(title="Available Output Devices")
    table.add_column("#", style="cyan", justify="right")
    table.add_column("Name", style="white")
    table.add_column("Ch", justify="right")
    table.add_column("Default Rate", justify="right", style="yellow")
    table.add_column("", style="green")
    for dev in devs:
        table.add_row(str(dev["index"]), dev["name"], str(dev["channels"]), f"{dev['sample_rate']} Hz", "* default" if dev["is_default"] else "")
    console.print(table)
    console.print('\nUse [cyan]--output-device <#>[/cyan] or [cyan]--output-device "name"[/cyan] to select.')


@app.command()
def chat(
    model: str = typer.Option(
        "Systran/faster-whisper-tiny",
        "--model",
        "-m",
        help="STT model to use for transcription",
    ),
    device: str | None = typer.Option(None, "--device", "-d", help="Input device index or name substring. Run `vocal devices` to list."),
    output_device: str | None = typer.Option(None, "--output-device", "-o", help="Output device index or name. Run `vocal output-devices` to list."),
    language: str | None = typer.Option(None, "--language", "-l", help="Language code (e.g. 'en'). Auto-detect if omitted."),
    system_prompt: str = typer.Option(_DEFAULT_SYSTEM_PROMPT, "--system-prompt", "-s", help="System prompt sent to the LLM."),
    api_url: str = typer.Option("http://localhost:8000", "--api-url", envvar="VOCAL_API_URL", help="Vocal API URL"),
    verbose: bool = typer.Option(False, "--verbose", "-v", help="Show transcription and LLM response text"),
) -> None:
    """Voice chat: speak to the AI and hear it respond (STT -> LLM -> TTS loop via /v1/realtime)"""
    try:
        device_idx = _resolve_device(device)
        output_device_idx = _resolve_output_device(output_device)
    except ValueError as e:
        console.print(f"[red]Error:[/red] {e}")
        raise typer.Exit(1)

    ws_url = api_url.replace("http://", "ws://").replace("https://", "wss://")
    active_device = sd.query_devices(device_idx if device_idx is not None else sd.default.device[0])
    device_label = f"[dim]{active_device['name']}[/dim]"

    console.print(f"[green]Voice chat started[/green] model=[cyan]{model}[/cyan] device={device_label}  Ctrl+C to stop\n")
    console.print("[dim]Speak — I'll transcribe, think, and respond with audio.[/dim]\n")

    try:
        asyncio.run(_chat_async(ws_url, device_idx, output_device_idx, model, language, system_prompt, verbose))
    except KeyboardInterrupt:
        console.print("\n[yellow]Stopped.[/yellow]")
    except Exception as e:
        console.print(f"[red]Error:[/red] {e}")
        raise typer.Exit(1)


def _play_pcm16(pcm_bytes: bytes, sample_rate: int = 24000, device: int | None = None) -> None:
    if not pcm_bytes:
        return
    arr = np.frombuffer(pcm_bytes, dtype=np.int16).astype(np.float32) / 32768.0
    sd.play(arr, samplerate=sample_rate, device=device)
    sd.wait()


_TRACE_SKIP = {"response.output_audio_transcript.delta", "conversation.item.input_audio_transcription.delta"}


def _chat_trace(etype: str, event: dict, state: dict) -> None:
    if etype in _TRACE_SKIP:
        return
    extra = ""
    if etype == "response.output_audio.delta":
        extra = f" ({len(event.get('delta', ''))} b64 chars)"
    elif etype == "response.output_audio.done":
        extra = f" (chunks={len(state['audio'])})"
    console.print(f"[dim]  [{etype}{extra}][/dim]", markup=False)


async def _chat_handle_delta(etype: str, event: dict, state: dict, verbose: bool, playing: asyncio.Event) -> None:
    if etype == "conversation.item.input_audio_transcription.delta":
        state["transcript"].append(event.get("delta", ""))
    elif etype == "response.output_audio_transcript.delta":
        delta = event.get("delta", "")
        state["text"].append(delta)
        sys.stdout.write(delta)
        sys.stdout.flush()
    elif etype == "response.output_audio.delta":
        playing.set()
        try:
            state["audio"].append(base64.b64decode(event.get("delta", "")))
        except Exception:
            pass


async def _chat_handle_done(
    etype: str,
    event: dict,
    state: dict,
    verbose: bool,
    loop: asyncio.AbstractEventLoop,
    output_device_idx: int | None,
    playing: asyncio.Event,
) -> None:
    if etype == "conversation.item.input_audio_transcription.completed":
        transcript = event.get("transcript", "").strip() or " ".join(state["transcript"]).strip()
        state["transcript"] = []
        sys.stdout.write("\r" + " " * 60 + "\r")
        if transcript:
            console.print(f"You: {transcript}")
    elif etype == "response.output_audio.done":
        if state["text"]:
            sys.stdout.write("\n")
            sys.stdout.flush()
        if state["audio"]:
            pcm = b"".join(state["audio"])
            await loop.run_in_executor(None, _play_pcm16, pcm, 24000, output_device_idx)
        state["audio"] = []
        state["text"] = []
        await asyncio.sleep(_PLAYBACK_COOLDOWN)
        playing.clear()


async def _chat_receiver(ws, output_device_idx: int | None, verbose: bool, loop: asyncio.AbstractEventLoop, stop_event: asyncio.Event, playing: asyncio.Event) -> None:
    state: dict = {"audio": [], "text": [], "transcript": []}

    async for msg in ws:
        if stop_event.is_set():
            break
        event = json.loads(msg)
        etype = event.get("type", "")

        if verbose:
            _chat_trace(etype, event, state)

        if "delta" in etype:
            await _chat_handle_delta(etype, event, state, verbose, playing)
        elif "done" in etype or "completed" in etype:
            await _chat_handle_done(etype, event, state, verbose, loop, output_device_idx, playing)
        elif etype == "input_audio_buffer.speech_started":
            sys.stdout.write("\r[detecting speech...]     \r")
            sys.stdout.flush()
        elif etype == "response.done":
            sys.stdout.write("[listening...]\r")
            sys.stdout.flush()
        elif etype == "error":
            console.print(f"\n[red]error:[/red] {event.get('error', {}).get('message', 'unknown')}")


async def _chat_async(ws_url: str, device_idx: int | None, output_device_idx: int | None, model: str, language: str | None, system_prompt: str, verbose: bool) -> None:
    audio_q: queue.SimpleQueue = queue.SimpleQueue()
    loop = asyncio.get_running_loop()
    stop_event = asyncio.Event()
    playing = asyncio.Event()
    native_rate = _get_device_rate(device_idx)
    native_blocksize = int(_FRAME_SIZE * native_rate / _SAMPLE_RATE)

    def _audio_callback(indata, _frames, _ts, _status) -> None:
        audio_q.put_nowait(_resample_frame(indata, native_rate, _SAMPLE_RATE).copy().tobytes())

    async def _sender(ws) -> None:
        while not stop_event.is_set():
            try:
                frame = await loop.run_in_executor(None, audio_q.get, True, 0.1)
                if playing.is_set():
                    continue
                b64 = base64.b64encode(frame).decode()
                await ws.send(json.dumps({"type": "input_audio_buffer.append", "audio": b64}))
            except queue.Empty:
                continue
            except Exception:
                break

    async with websockets.connect(f"{ws_url}/v1/realtime", open_timeout=10) as ws:
        await asyncio.wait_for(ws.recv(), timeout=5.0)

        session_cfg: dict = {
            "type": "realtime",
            "model": model,
            "input_sample_rate": _SAMPLE_RATE,
            "system_prompt": system_prompt,
        }
        if language:
            session_cfg["language"] = language
        await ws.send(json.dumps({"type": "session.update", "session": session_cfg}))
        await asyncio.wait_for(ws.recv(), timeout=5.0)

        sys.stdout.write("[listening...]  \r")
        sys.stdout.flush()

        with sd.InputStream(samplerate=native_rate, channels=_CHANNELS, dtype="int16", blocksize=native_blocksize, device=device_idx, callback=_audio_callback):
            sender_task = asyncio.create_task(_sender(ws))
            receiver_task = asyncio.create_task(_chat_receiver(ws, output_device_idx, verbose, loop, stop_event, playing))
            try:
                await asyncio.gather(sender_task, receiver_task)
            except (KeyboardInterrupt, asyncio.CancelledError):
                stop_event.set()
                sender_task.cancel()
                receiver_task.cancel()
                raise KeyboardInterrupt



async def _ws_sender(ws, audio_q: queue.SimpleQueue, stop_event: asyncio.Event, loop: asyncio.AbstractEventLoop) -> None:
    while not stop_event.is_set():
        try:
            frame = await loop.run_in_executor(None, audio_q.get, True, 0.1)
            await ws.send(frame)
        except queue.Empty:
            continue
        except Exception:
            break


async def _ws_receiver(ws, verbose: bool) -> None:
    current_line = ""
    t_start = time.monotonic()
    async for msg in ws:
        event = json.loads(msg)
        etype = event.get("type", "")
        if etype == "transcript.delta":
            current_line = current_line + event.get("text", "") + " "
            sys.stdout.write(f"\r> {current_line}  ")
            sys.stdout.flush()
        elif etype == "transcript.done":
            full = event.get("text", "").strip()
            elapsed = time.monotonic() - t_start
            suffix = f"  ({elapsed:.1f}s)" if verbose else ""
            sys.stdout.write("\r" + " " * 80 + "\r")
            sys.stdout.flush()
            if full:
                console.print(f"[cyan]>[/cyan] {full}{suffix}")
            current_line = ""
            t_start = time.monotonic()
        elif etype == "error":
            console.print(f"\n[red]error:[/red] {event.get('message', 'unknown')}")


async def _live_async(endpoint: str, device_idx: int | None, verbose: bool) -> None:
    audio_q: queue.SimpleQueue = queue.SimpleQueue()
    loop = asyncio.get_running_loop()
    stop_event = asyncio.Event()
    native_rate = _get_device_rate(device_idx)
    native_blocksize = int(_FRAME_SIZE * native_rate / _SAMPLE_RATE)

    def _audio_callback(indata, _frames, _ts, _status) -> None:
        audio_q.put_nowait(_resample_frame(indata, native_rate, _SAMPLE_RATE).copy().tobytes())

    async with websockets.connect(endpoint) as ws:
        with sd.InputStream(samplerate=native_rate, channels=_CHANNELS, dtype="int16", blocksize=native_blocksize, device=device_idx, callback=_audio_callback):
            sender_task = asyncio.create_task(_ws_sender(ws, audio_q, stop_event, loop))
            receiver_task = asyncio.create_task(_ws_receiver(ws, verbose))
            try:
                await asyncio.gather(sender_task, receiver_task)
            except (KeyboardInterrupt, asyncio.CancelledError):
                stop_event.set()
                sender_task.cancel()
                receiver_task.cancel()
                raise KeyboardInterrupt


def _format_timestamp(seconds: float, use_comma: bool = True) -> str:
    hours = int(seconds // 3600)
    minutes = int((seconds % 3600) // 60)
    secs = seconds % 60
    if use_comma:
        return f"{hours:02d}:{minutes:02d}:{secs:06.3f}".replace(".", ",")
    return f"{hours:02d}:{minutes:02d}:{secs:06.3f}"


if __name__ == "__main__":
    app()
