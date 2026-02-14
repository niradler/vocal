from pathlib import Path

import typer
from rich.console import Console
from rich.table import Table

from vocal_sdk import VocalSDK

app = typer.Typer(
    name="vocal",
    help="Vocal - Generic Speech AI Platform CLI",
    no_args_is_help=True,
)

models_app = typer.Typer(help="Model management commands")
app.add_typer(models_app, name="models")

console = Console()


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
        client = VocalSDK(base_url=api_url)

        console.print("Transcribing audio...")

        result = client.audio.transcribe(
            file=str(audio_file),
            model=model,
            language=language,
            response_format="json",
        )

        if output_format == "text":
            console.print(result["text"])
        elif output_format == "json":
            import json

            console.print_json(json.dumps(result))
        elif output_format == "srt":
            for seg in result.get("segments", []):
                console.print(f"{seg['id'] + 1}")
                start = _format_timestamp(seg["start"])
                end = _format_timestamp(seg["end"])
                console.print(f"{start} --> {end}")
                console.print(seg["text"])
                console.print()
        elif output_format == "vtt":
            console.print("WEBVTT\n")
            for seg in result.get("segments", []):
                start = _format_timestamp(seg["start"], use_comma=False)
                end = _format_timestamp(seg["end"], use_comma=False)
                console.print(f"{start} --> {end}")
                console.print(seg["text"])
                console.print()

    except Exception as e:
        console.print(f"[red]Error:[/red] {str(e)}")
        raise typer.Exit(1)


@models_app.command("list")
def models_list(
    status: str | None = typer.Option(
        None,
        "--status",
        "-s",
        help="Filter by status: available, downloading, not_downloaded",
    ),
    task: str | None = typer.Option(None, "--task", "-t", help="Filter by task: stt, tts"),
    api_url: str = typer.Option("http://localhost:8000", "--api-url", help="Vocal API URL"),
):
    """List all available models"""
    try:
        client = VocalSDK(base_url=api_url)
        response = client.models.list(status=status, task=task)

        table = Table(title="Vocal Models")
        table.add_column("Model ID", style="cyan")
        table.add_column("Task", style="magenta")
        table.add_column("Status", style="green")
        table.add_column("Size", style="yellow")

        for model in response["models"]:
            status_color = {
                "available": "green",
                "downloading": "yellow",
                "not_downloaded": "red",
            }.get(model["status"], "white")

            table.add_row(
                model["id"],
                model.get("task", "N/A"),
                f"[{status_color}]{model['status']}[/{status_color}]",
                str(model.get("size", "N/A")),
            )

        console.print(table)
        console.print(f"\nTotal models: {response['total']}")

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
        client = VocalSDK(base_url=api_url)

        console.print(f"Downloading {model_id}...")

        result = client.models.download(model_id)

        console.print(f"[green]Successfully downloaded:[/green] {model_id}")
        console.print(f"Status: {result.get('status', 'unknown')}")

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
        client = VocalSDK(base_url=api_url)
        client.models.delete(model_id)

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
        uvicorn.run(
            "vocal_api.main:app",
            host=host,
            port=port,
            reload=reload,
        )
    except KeyboardInterrupt:
        console.print("\n[yellow]Server stopped[/yellow]")
    except Exception as e:
        console.print(f"[red]Error:[/red] {str(e)}")
        raise typer.Exit(1)


def _format_timestamp(seconds: float, use_comma: bool = True) -> str:
    """Format timestamp for SRT/VTT output"""
    hours = int(seconds // 3600)
    minutes = int((seconds % 3600) // 60)
    secs = seconds % 60

    if use_comma:
        return f"{hours:02d}:{minutes:02d}:{secs:06.3f}".replace(".", ",")
    else:
        return f"{hours:02d}:{minutes:02d}:{secs:06.3f}"


if __name__ == "__main__":
    app()
