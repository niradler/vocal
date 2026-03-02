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
from rich.console import Console
from rich.table import Table

from vocal_sdk import VocalClient
from vocal_sdk.api.models import (
    delete_model_v1_models_model_id_delete,
    download_model_v1_models_model_id_download_post,
    list_models_v1_models_get,
)
from vocal_sdk.api.transcription import (
    create_transcription_v1_audio_transcriptions_post,
    create_translation_v1_audio_translations_post,
)
from vocal_sdk.models import (
    BodyCreateTranscriptionV1AudioTranscriptionsPost,
    BodyCreateTranslationV1AudioTranslationsPost,
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

_SAMPLE_RATE = 16000
_FRAME_SIZE = 1600
_CHANNELS = 1
_CALIB_FRAMES = 15

_print_lock = threading.Lock()


def _make_client(api_url: str) -> VocalClient:
    return VocalClient(base_url=api_url, timeout=httpx.Timeout(300.0), raise_on_unexpected_status=True)


@app.command()
def run(
    audio_file: Path = typer.Argument(..., help="Path to audio file to transcribe"),
    model: str = typer.Option(
        "Systran/faster-whisper-tiny",
        "--model",
        "-m",
        help="Model to use for transcription",
    ),
    language: str | None = typer.Option(None, "--language", "-l", help="Language code (e.g., 'en', 'es')"),
    output_format: str = typer.Option("text", "--format", "-f", help="Output format: text, json, srt, vtt"),
    api_url: str = typer.Option("http://localhost:8000", "--api-url", help="Vocal API URL"),
):
    """Transcribe audio file to text"""
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
    api_url: str = typer.Option("http://localhost:8000", "--api-url", help="Vocal API URL"),
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


@models_app.command("pull")
def models_pull(
    model_id: str = typer.Argument(..., help="Model ID to download"),
    api_url: str = typer.Option("http://localhost:8000", "--api-url", help="Vocal API URL"),
):
    """Download a model (Ollama-style pull)"""
    try:
        vc = _make_client(api_url)
        console.print(f"Downloading {model_id}...")
        result = download_model_v1_models_model_id_download_post.sync(model_id=model_id, client=vc)
        console.print(f"[green]Successfully downloaded:[/green] {model_id}")
        if result is not None:
            console.print(f"Status: {result.status.value}")
    except Exception as e:
        console.print(f"[red]Error:[/red] {str(e)}")
        raise typer.Exit(1)


@models_app.command("delete")
def models_delete(
    model_id: str = typer.Argument(..., help="Model ID to delete"),
    api_url: str = typer.Option("http://localhost:8000", "--api-url", help="Vocal API URL"),
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
    """Return all input-capable audio devices with their index, name, channels, and default flag."""
    default_idx = sd.default.device[0]
    devices = []
    for idx, dev in enumerate(sd.query_devices()):
        if dev["max_input_channels"] > 0:
            devices.append(
                {
                    "index": idx,
                    "name": dev["name"],
                    "channels": dev["max_input_channels"],
                    "sample_rate": int(dev["default_samplerate"]),
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
    table.add_column("Ch", justify="right")
    table.add_column("Default Rate", justify="right", style="yellow")
    table.add_column("", style="green")
    for dev in devs:
        table.add_row(
            str(dev["index"]),
            dev["name"],
            str(dev["channels"]),
            f"{dev['sample_rate']} Hz",
            "* default" if dev["is_default"] else "",
        )
    console.print(table)
    console.print("\nUse [cyan]--device <#>[/cyan] or [cyan]--device \"name\"[/cyan] to select.")


@app.command()
def devices() -> None:
    """List available audio input devices"""
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
            if result and result.text.strip():
                suffix = f"  [dim]({elapsed:.1f}s)[/dim]" if verbose else ""
                console.print(f"[cyan]>[/cyan] {result.text.strip()}{suffix}")
    except Exception as e:
        elapsed = time.monotonic() - t0
        with _print_lock:
            sys.stdout.write("\r" + " " * 60 + "\r")
            sys.stdout.flush()
            console.print(f"[red]error[/red] after {elapsed:.1f}s: {e}")


@app.command()
def listen(
    model: str = typer.Option(
        "Systran/faster-whisper-tiny",
        "--model",
        "-m",
        help="STT model to use",
    ),
    language: str | None = typer.Option(None, "--language", "-l", help="Language code (e.g. 'en'). Auto-detect if omitted."),
    task: str = typer.Option("transcribe", "--task", help="'transcribe' or 'translate' (translate any language to English)"),
    device: str | None = typer.Option(None, "--device", "-d", help="Input device index or name substring. Run `vocal devices` to list."),
    list_devices: bool = typer.Option(False, "--list-devices", help="List available input devices and exit"),
    silence_threshold: float | None = typer.Option(None, "--silence-threshold", help="RMS energy threshold. Auto-calibrated from mic noise floor if omitted."),
    silence_duration: float = typer.Option(1.5, "--silence-duration", help="Seconds of silence that triggers chunk send"),
    max_chunk_duration: float = typer.Option(10.0, "--max-chunk-duration", help="Max seconds of audio before forced send"),
    api_url: str = typer.Option("http://localhost:8000", "--api-url", help="Vocal API URL"),
    verbose: bool = typer.Option(False, "--verbose", "-v", help="Show chunk send timing and API latency"),
):
    """Listen to the microphone and transcribe speech in real-time (ASR streaming mode)"""
    if list_devices:
        _print_devices_table()
        raise typer.Exit(0)

    try:
        device_idx = _resolve_device(device)
    except ValueError as e:
        console.print(f"[red]Error:[/red] {e}")
        raise typer.Exit(1)

    active_device = sd.query_devices(device_idx if device_idx is not None else sd.default.device[0])
    device_label = f"[dim]{active_device['name']}[/dim]"
    silence_frames_needed = int(silence_duration * _SAMPLE_RATE / _FRAME_SIZE)

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

    vc = VocalClient(base_url=api_url, timeout=httpx.Timeout(60.0), raise_on_unexpected_status=False)
    threshold_hint = f"threshold=[cyan]{silence_threshold:.0f}[/cyan]" if silence_threshold is not None else "threshold=[cyan]auto[/cyan]"
    console.print(
        f"[green]Listening...[/green] model=[cyan]{model}[/cyan] task=[cyan]{task}[/cyan] "
        f"device={device_label}  {threshold_hint}  Ctrl+C to stop\n"
    )

    audio_queue: queue.SimpleQueue = queue.SimpleQueue()

    def _audio_callback(indata, _frames, _ts, _status):
        audio_queue.put(indata.copy())

    try:
        with sd.InputStream(
            samplerate=_SAMPLE_RATE,
            channels=_CHANNELS,
            dtype="int16",
            blocksize=_FRAME_SIZE,
            device=device_idx,
            callback=_audio_callback,
        ):
            _run_stream(audio_queue, silence_frames_needed, max_chunk_duration, silence_threshold, vc, model, language, task, verbose)
    except KeyboardInterrupt:
        console.print("\n[yellow]Stopped.[/yellow]")
    except Exception as e:
        console.print(f"[red]Error:[/red] {e}")
        raise typer.Exit(1)


def _format_timestamp(seconds: float, use_comma: bool = True) -> str:
    hours = int(seconds // 3600)
    minutes = int((seconds % 3600) // 60)
    secs = seconds % 60
    if use_comma:
        return f"{hours:02d}:{minutes:02d}:{secs:06.3f}".replace(".", ",")
    return f"{hours:02d}:{minutes:02d}:{secs:06.3f}"


if __name__ == "__main__":
    app()
