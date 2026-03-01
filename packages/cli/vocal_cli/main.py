import json
from pathlib import Path

import httpx
import typer
from rich.console import Console
from rich.table import Table

from vocal_sdk import VocalClient
from vocal_sdk.api.models import (
    delete_model_v1_models_model_id_delete,
    download_model_v1_models_model_id_download_post,
    list_models_v1_models_get,
)
from vocal_sdk.api.transcription import create_transcription_v1_audio_transcriptions_post
from vocal_sdk.models import BodyCreateTranscriptionV1AudioTranscriptionsPost, TranscriptionFormat
from vocal_sdk.types import UNSET, File, Unset

app = typer.Typer(
    name="vocal",
    help="Vocal - Generic Speech AI Platform CLI",
    no_args_is_help=True,
)

models_app = typer.Typer(help="Model management commands")
app.add_typer(models_app, name="models")

console = Console()


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


def _format_timestamp(seconds: float, use_comma: bool = True) -> str:
    hours = int(seconds // 3600)
    minutes = int((seconds % 3600) // 60)
    secs = seconds % 60
    if use_comma:
        return f"{hours:02d}:{minutes:02d}:{secs:06.3f}".replace(".", ",")
    return f"{hours:02d}:{minutes:02d}:{secs:06.3f}"


if __name__ == "__main__":
    app()
