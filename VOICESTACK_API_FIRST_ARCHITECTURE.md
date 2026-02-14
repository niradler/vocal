# Vocal: API-First Architecture
## Generic Speech AI Platform (STT + TTS)
### Monorepo with Auto-Generated OpenAPI & SDKs

---

## 🎯 Architecture Philosophy

**API is the Source of Truth:**
- API defines all schemas, types, and contracts
- OpenAPI spec auto-generated from FastAPI
- SDK auto-generated from OpenAPI spec
- CLI is thin wrapper around SDK
- Type safety everywhere (Pydantic models)

**Generic & Extensible:**
- Registry-based model management (HuggingFace, local, custom providers)
- Supports STT (Speech-to-Text) now, TTS (Text-to-Speech) later
- Pluggable adapters for any model backend
- Provider-agnostic storage and caching

---

## 📁 Monorepo Structure

```
vocal/
├── pyproject.toml              # Root uv workspace config ⏳ TODO
├── uv.lock                     # uv lockfile ⏳ TODO
├── README.md                   ⏳ TODO
├── LICENSE (AGPL-3.0)          ⏳ TODO
│
├── packages/
│   ├── api/                    # 🔥 FastAPI Server (Source of Truth)
│   │   ├── vocal_api/          ⏳ TODO
│   │   │   ├── __init__.py
│   │   │   ├── main.py         # FastAPI app
│   │   │   ├── models/         # Pydantic models (schemas)
│   │   │   │   ├── __init__.py
│   │   │   │   ├── transcription.py    # STT models
│   │   │   │   └── model.py            # Model registry models
│   │   │   ├── routes/         # API endpoints by domain
│   │   │   │   ├── __init__.py
│   │   │   │   ├── transcription.py    # STT endpoints
│   │   │   │   └── models.py           # Model management
│   │   │   ├── services/       # Business logic
│   │   │   │   ├── __init__.py
│   │   │   │   ├── transcription_service.py
│   │   │   │   └── model_service.py
│   │   │   ├── dependencies.py # FastAPI dependencies
│   │   │   └── config.py       # Settings
│   │   ├── pyproject.toml
│   │   └── tests/
│   │
│   ├── core/                   # 🧩 Shared Core Logic
│   │   ├── vocal_core/         ⏳ TODO
│   │   │   ├── __init__.py
│   │   │   ├── registry/       # Generic model registry
│   │   │   │   ├── __init__.py
│   │   │   │   ├── base.py             # Base registry interface
│   │   │   │   ├── model_info.py       # Model metadata
│   │   │   │   └── providers/          # Model providers
│   │   │   │       ├── __init__.py
│   │   │   │       ├── base.py         # Provider interface
│   │   │   │       ├── huggingface.py  # HF provider
│   │   │   │       └── local.py        # Local models
│   │   │   ├── adapters/       # Model adapters (STT/TTS)
│   │   │   │   ├── __init__.py
│   │   │   │   ├── base.py             # Base adapter
│   │   │   │   └── stt/                # STT adapters
│   │   │   │       ├── __init__.py
│   │   │   │       ├── whisper.py
│   │   │   │       ├── faster_whisper.py
│   │   │   │       └── canary.py
│   │   │   ├── storage/        # Model storage & cache
│   │   │   │   ├── __init__.py
│   │   │   │   ├── model_store.py      # Generic storage
│   │   │   │   └── cache.py            # Model caching
│   │   │   └── utils/
│   │   ├── pyproject.toml
│   │   └── tests/
│   │
│   ├── sdk/                    # 📦 Auto-Generated Python SDK
│   │   ├── vocal_sdk/          ⏳ TODO (Generate after API)
│   │   │   ├── __init__.py
│   │   │   ├── client.py       # Main SDK client
│   │   │   ├── models/         # Generated from OpenAPI
│   │   │   ├── api/            # Generated API methods
│   │   │   └── exceptions.py
│   │   ├── pyproject.toml
│   │   ├── openapi-generator-config.yaml
│   │   └── scripts/
│   │       └── generate.sh     # Generate from OpenAPI spec
│   │
│   └── cli/                    # 💻 CLI (Thin wrapper around SDK)
│       ├── vocal_cli/          ⏳ TODO (After SDK)
│       │   ├── __init__.py
│       │   ├── main.py         # Typer CLI app
│       │   ├── commands/       # CLI commands
│       │   │   ├── __init__.py
│       │   │   ├── run.py      # vocal run (transcribe)
│       │   │   ├── models.py   # vocal models list/pull/rm
│       │   │   └── serve.py    # vocal serve (start API)
│       │   ├── ui/             # Rich terminal UI
│       │   │   ├── __init__.py
│       │   │   ├── progress.py
│       │   │   └── tables.py
│       │   └── config.py
│       ├── pyproject.toml
│       └── tests/
│
├── scripts/
│   ├── setup-dev.sh            # Development setup ⏳ TODO
│   ├── generate-sdk.sh         # Generate SDK from OpenAPI ⏳ TODO
│   └── build-all.sh            # Build all packages ⏳ TODO
│
└── docs/
    ├── api/                    # API documentation ⏳ TODO
    ├── sdk/                    # SDK documentation ⏳ TODO
    └── cli/                    # CLI documentation ⏳ TODO
```

---

## 🔥 Phase 1: API (Source of Truth)

### Implementation Status: ⏳ TODO (Start here!)

### 1.1 Core Models (Pydantic Schemas)

**packages/api/vocal_api/models/transcription.py:** ⏳ TODO
```python
from pydantic import BaseModel, Field, field_validator
from typing import Optional, Literal
from enum import Enum

class TranscriptionFormat(str, Enum):
    """Output format for transcription"""
    JSON = "json"
    TEXT = "text"
    SRT = "srt"
    VTT = "vtt"
    VERBOSE_JSON = "verbose_json"

class TranscriptionRequest(BaseModel):
    """Request schema for transcription"""
    model: str = Field(
        description="Model ID to use for transcription",
        examples=["whisper-large-v3", "voxtral-24b"]
    )
    language: Optional[str] = Field(
        None,
        description="Language code (ISO 639-1). Auto-detect if not provided.",
        examples=["en", "es", "fr"]
    )
    prompt: Optional[str] = Field(
        None,
        description="Optional text to guide the model's style",
        max_length=224
    )
    response_format: TranscriptionFormat = Field(
        TranscriptionFormat.JSON,
        description="Format of the transcription output"
    )
    temperature: float = Field(
        0.0,
        ge=0.0,
        le=1.0,
        description="Sampling temperature"
    )
    timestamp_granularities: list[Literal["word", "segment"]] = Field(
        default_factory=lambda: ["segment"],
        description="Timestamp granularity"
    )
    
    @field_validator("language")
    @classmethod
    def validate_language(cls, v: Optional[str]) -> Optional[str]:
        if v and len(v) != 2:
            raise ValueError("Language must be 2-letter ISO 639-1 code")
        return v

class TranscriptionSegment(BaseModel):
    """A segment of transcribed text with timing"""
    id: int
    start: float = Field(description="Start time in seconds")
    end: float = Field(description="End time in seconds")
    text: str = Field(description="Transcribed text")
    tokens: Optional[list[int]] = None
    temperature: Optional[float] = None
    avg_logprob: Optional[float] = None
    compression_ratio: Optional[float] = None
    no_speech_prob: Optional[float] = None

class TranscriptionWord(BaseModel):
    """Word-level timestamp"""
    word: str
    start: float
    end: float
    probability: Optional[float] = None

class TranscriptionResponse(BaseModel):
    """Response schema for transcription"""
    text: str = Field(description="Full transcribed text")
    language: str = Field(description="Detected or specified language")
    duration: float = Field(description="Audio duration in seconds")
    segments: Optional[list[TranscriptionSegment]] = None
    words: Optional[list[TranscriptionWord]] = None
    
    class Config:
        json_schema_extra = {
            "example": {
                "text": "Hello, how are you today?",
                "language": "en",
                "duration": 2.5,
                "segments": [
                    {
                        "id": 0,
                        "start": 0.0,
                        "end": 2.5,
                        "text": "Hello, how are you today?"
                    }
                ]
            }
        }
```

**packages/api/vocal_api/models/model.py:** ⏳ TODO
```python
from pydantic import BaseModel, Field, HttpUrl
from typing import Optional, Literal
from datetime import datetime
from enum import Enum

class ModelStatus(str, Enum):
    """Model download/availability status"""
    AVAILABLE = "available"
    DOWNLOADING = "downloading"
    NOT_DOWNLOADED = "not_downloaded"
    ERROR = "error"

class ModelBackend(str, Enum):
    """Model inference backend"""
    FASTER_WHISPER = "faster_whisper"
    TRANSFORMERS = "transformers"
    CTRANSLATE2 = "ctranslate2"
    NEMO = "nemo"
    ONNX = "onnx"
    CUSTOM = "custom"

class ModelProvider(str, Enum):
    """Model provider/source"""
    HUGGINGFACE = "huggingface"
    LOCAL = "local"
    CUSTOM = "custom"

class ModelInfo(BaseModel):
    """Model information schema"""
    id: str = Field(description="Unique model identifier")
    name: str = Field(description="Human-readable model name")
    provider: ModelProvider = Field(description="Model provider")
    description: Optional[str] = None
    size: int = Field(description="Model size in bytes")
    size_readable: str = Field(description="Human-readable size (e.g., '3.1GB')")
    parameters: str = Field(description="Number of parameters (e.g., '1.5B')")
    languages: list[str] = Field(description="Supported languages")
    backend: ModelBackend = Field(description="Inference backend")
    status: ModelStatus = Field(description="Current model status")
    source_url: Optional[HttpUrl] = None
    license: Optional[str] = None
    recommended_vram: Optional[str] = Field(
        None,
        description="Recommended VRAM (e.g., '6GB+')"
    )
    task: str = Field(description="Task type: 'stt' or 'tts'")
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None
    
    class Config:
        json_schema_extra = {
            "example": {
                "id": "openai/whisper-large-v3",
                "name": "OpenAI Whisper Large V3",
                "provider": "huggingface",
                "size": 3100000000,
                "size_readable": "3.1GB",
                "parameters": "1.5B",
                "languages": ["en", "es", "fr", "de", "..."],
                "backend": "faster_whisper",
                "status": "available",
                "recommended_vram": "6GB+",
                "task": "stt"
            }
        }

class ModelListResponse(BaseModel):
    """List of available models"""
    models: list[ModelInfo]
    total: int

class ModelDownloadRequest(BaseModel):
    """Request to download a model"""
    model_id: str
    quantization: Optional[Literal["int8", "int8_float16", "float16", "float32"]] = None
    provider: Optional[ModelProvider] = ModelProvider.HUGGINGFACE

class ModelDownloadProgress(BaseModel):
    """Model download progress"""
    model_id: str
    status: Literal["downloading", "completed", "error"]
    progress: float = Field(ge=0.0, le=1.0)
    downloaded_bytes: int
    total_bytes: int
    speed_mbps: Optional[float] = None
    eta_seconds: Optional[int] = None
```

---

### 1.2 API Routes (FastAPI Endpoints)

**packages/api/vocal_api/routes/transcription.py:** ⏳ TODO
```python
from fastapi import APIRouter, UploadFile, File, Form, Depends, HTTPException
from typing import Annotated, Optional
from ..models.transcription import (
    TranscriptionRequest,
    TranscriptionResponse,
    TranscriptionFormat
)
from ..services.transcription_service import TranscriptionService
from ..dependencies import get_transcription_service

router = APIRouter(prefix="/v1/audio", tags=["transcription"])

@router.post(
    "/transcriptions",
    response_model=TranscriptionResponse,
    summary="Transcribe audio",
    description="Transcribe audio file to text using specified model"
)
async def create_transcription(
    file: Annotated[UploadFile, File(description="Audio file to transcribe")],
    model: Annotated[str, Form(description="Model ID")] = "openai/whisper-large-v3",
    language: Annotated[Optional[str], Form(description="Language code")] = None,
    prompt: Annotated[Optional[str], Form(description="Style prompt")] = None,
    response_format: Annotated[
        TranscriptionFormat,
        Form(description="Output format")
    ] = TranscriptionFormat.JSON,
    temperature: Annotated[float, Form(ge=0.0, le=1.0)] = 0.0,
    service: TranscriptionService = Depends(get_transcription_service)
) -> TranscriptionResponse:
    """
    Transcribe an audio file.
    
    **Supported formats:** mp3, mp4, wav, m4a, flac, ogg, webm
    **Max file size:** 25MB
    
    Returns transcription with optional word/segment timestamps.
    """
    file.file.seek(0, 2)
    size = file.file.tell()
    file.file.seek(0)
    
    if size > 25 * 1024 * 1024:
        raise HTTPException(400, "File too large. Max 25MB.")
    
    request = TranscriptionRequest(
        model=model,
        language=language,
        prompt=prompt,
        response_format=response_format,
        temperature=temperature
    )
    
    result = await service.transcribe(file, request)
    return result

@router.post(
    "/translations",
    response_model=TranscriptionResponse,
    summary="Translate audio to English",
    description="Translate audio to English text"
)
async def create_translation(
    file: Annotated[UploadFile, File()],
    model: Annotated[str, Form()] = "openai/whisper-large-v3",
    service: TranscriptionService = Depends(get_transcription_service)
) -> TranscriptionResponse:
    """Translate audio to English."""
    return await service.translate(file, model)
```

**packages/api/vocal_api/routes/models.py:** ⏳ TODO
```python
from fastapi import APIRouter, Depends, HTTPException, BackgroundTasks
from typing import Optional
from ..models.model import (
    ModelInfo,
    ModelListResponse,
    ModelDownloadRequest,
    ModelDownloadProgress
)
from ..services.model_service import ModelService
from ..dependencies import get_model_service

router = APIRouter(prefix="/v1/models", tags=["models"])

@router.get(
    "",
    response_model=ModelListResponse,
    summary="List models",
    description="List all available models"
)
async def list_models(
    status: Optional[str] = None,
    service: ModelService = Depends(get_model_service)
) -> ModelListResponse:
    """
    List all available models.
    
    **Query params:**
    - status: Filter by status (available, downloading, not_downloaded)
    """
    models = await service.list_models(status_filter=status)
    return ModelListResponse(models=models, total=len(models))

@router.get(
    "/{model_id}",
    response_model=ModelInfo,
    summary="Get model info",
    description="Get detailed information about a specific model"
)
async def get_model(
    model_id: str,
    service: ModelService = Depends(get_model_service)
) -> ModelInfo:
    """Get detailed model information."""
    model = await service.get_model(model_id)
    if not model:
        raise HTTPException(404, f"Model {model_id} not found")
    return model

@router.post(
    "/{model_id}/download",
    response_model=ModelDownloadProgress,
    summary="Download model",
    description="Download a model for local use"
)
async def download_model(
    model_id: str,
    background_tasks: BackgroundTasks,
    request: Optional[ModelDownloadRequest] = None,
    service: ModelService = Depends(get_model_service)
) -> ModelDownloadProgress:
    """
    Start downloading a model.
    
    Returns immediately with initial progress.
    Use GET /models/{model_id}/download/status to check progress.
    """
    background_tasks.add_task(
        service.download_model,
        model_id,
        request.quantization if request else None
    )
    
    return ModelDownloadProgress(
        model_id=model_id,
        status="downloading",
        progress=0.0,
        downloaded_bytes=0,
        total_bytes=0
    )

@router.get(
    "/{model_id}/download/status",
    response_model=ModelDownloadProgress,
    summary="Get download status"
)
async def get_download_status(
    model_id: str,
    service: ModelService = Depends(get_model_service)
) -> ModelDownloadProgress:
    """Check model download progress."""
    status = await service.get_download_status(model_id)
    if not status:
        raise HTTPException(404, "No active download for this model")
    return status

@router.delete(
    "/{model_id}",
    summary="Delete model",
    description="Remove a downloaded model"
)
async def delete_model(
    model_id: str,
    service: ModelService = Depends(get_model_service)
):
    """Delete a downloaded model."""
    await service.delete_model(model_id)
    return {"status": "deleted", "model_id": model_id}
```

**packages/api/vocal_api/main.py:** ⏳ TODO
```python
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.openapi.utils import get_openapi
from .routes import transcription, models
from .config import settings

app = FastAPI(
    title="Vocal API",
    description="Generic Speech AI Platform (STT + TTS)",
    version="0.1.0",
    docs_url="/docs",
    redoc_url="/redoc"
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.CORS_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(transcription.router)
app.include_router(models.router)

@app.get("/", tags=["health"])
async def root():
    """API health check"""
    return {
        "status": "ok",
        "message": "Vocal API",
        "version": "0.1.0"
    }

@app.get("/health", tags=["health"])
async def health():
    """Detailed health check"""
    return {
        "status": "healthy",
        "api_version": "0.1.0",
        "models_loaded": True
    }

def custom_openapi():
    if app.openapi_schema:
        return app.openapi_schema
    
    openapi_schema = get_openapi(
        title="Vocal API",
        version="0.1.0",
        description="Generic Speech AI Platform (STT + TTS)",
        routes=app.routes,
    )
    
    app.openapi_schema = openapi_schema
    return app.openapi_schema

app.openapi = custom_openapi
```

---

## 📦 Phase 2: Auto-Generated SDK

### Implementation Status: ⏳ TODO (Generate after API is ready)

### 2.1 SDK Generation Script

**packages/sdk/scripts/generate.sh:** ⏳ TODO
```bash
#!/bin/bash
set -e

echo "🔄 Generating Python SDK from OpenAPI spec..."

cd ../api
uv run uvicorn vocal_api.main:app --port 8000 &
API_PID=$!

sleep 3

curl http://localhost:8000/openapi.json -o ../sdk/openapi.json

kill $API_PID

cd ../sdk
openapi-generator-cli generate \
  -i openapi.json \
  -g python \
  -o . \
  -c openapi-generator-config.yaml \
  --additional-properties=packageName=vocal_sdk

echo "✅ SDK generated successfully!"
echo "📝 Installing generated SDK..."
uv pip install -e .

echo "🎉 Done! SDK ready to use."
```

**packages/sdk/openapi-generator-config.yaml:** ⏳ TODO
```yaml
packageName: vocal_sdk
projectName: vocal-sdk
packageVersion: 0.1.0
packageUrl: https://github.com/vocal/vocal
generateSourceCodeOnly: false
library: urllib3
```

### 2.2 SDK Client Wrapper

**packages/sdk/vocal_sdk/client.py:** ⏳ TODO
**packages/sdk/vocal_sdk/client.py:** ⏳ TODO
```python
"""Vocal SDK Client - High-level wrapper"""
from typing import Optional, BinaryIO, Union
from pathlib import Path
from .api.transcription_api import TranscriptionApi
from .api.models_api import ModelsApi
from .models import (
    TranscriptionResponse,
    ModelInfo,
    ModelListResponse
)
from .configuration import Configuration
from .api_client import ApiClient

class Vocal:
    """
    Vocal SDK Client
    
    Example:
        >>> client = Vocal()
        >>> result = client.transcribe("audio.mp3")
        >>> print(result.text)
    """
    
    def __init__(
        self,
        base_url: str = "http://localhost:11435"
    ):
        """
        Initialize Vocal client
        
        Args:
            base_url: API base URL (default: http://localhost:11435)
        """
        config = Configuration(host=base_url)
        
        self._client = ApiClient(config)
        self._transcription = TranscriptionApi(self._client)
        self._models = ModelsApi(self._client)
    
    def transcribe(
        self,
        file: Union[str, Path, BinaryIO],
        model: str = "openai/whisper-large-v3",
        language: Optional[str] = None,
        **kwargs
    ) -> TranscriptionResponse:
        """
        Transcribe audio file
        
        Args:
            file: Path to audio file or file-like object
            model: Model ID to use
            language: Language code (auto-detect if None)
            **kwargs: Additional parameters
        
        Returns:
            TranscriptionResponse with text and metadata
            
        Example:
            >>> result = client.transcribe("audio.mp3")
            >>> print(result.text)
            "Hello, how are you today?"
        """
        if isinstance(file, (str, Path)):
            with open(file, 'rb') as f:
                return self._transcription.create_transcription(
                    file=f,
                    model=model,
                    language=language,
                    **kwargs
                )
        else:
            return self._transcription.create_transcription(
                file=file,
                model=model,
                language=language,
                **kwargs
            )
    
    def list_models(self, status: Optional[str] = None) -> ModelListResponse:
        """
        List available models
        
        Args:
            status: Filter by status (available, downloading, etc.)
            
        Returns:
            ModelListResponse with list of models
            
        Example:
            >>> models = client.list_models()
            >>> for model in models.models:
            ...     print(f"{model.id}: {model.size_readable}")
        """
        return self._models.list_models(status=status)
    
    def get_model(self, model_id: str) -> ModelInfo:
        """Get model information"""
        return self._models.get_model(model_id)
    
    def download_model(
        self,
        model_id: str,
        quantization: Optional[str] = None
    ):
        """Download a model"""
        return self._models.download_model(
            model_id,
            quantization=quantization
        )
    
    def delete_model(self, model_id: str):
        """Delete a downloaded model"""
        return self._models.delete_model(model_id)
```

---

## 💻 Phase 3: CLI (Using SDK)

### Implementation Status: ⏳ TODO (After SDK is ready)

**packages/cli/vocal_cli/main.py:** ⏳ TODO
**packages/cli/vocal_cli/main.py:** ⏳ TODO
```python
import typer
from rich.console import Console
from typing import Optional
from .commands import models, run, serve

app = typer.Typer(
    name="vocal",
    help="Generic Speech AI Platform (STT + TTS)",
    add_completion=False
)
console = Console()

app.add_typer(models.app, name="models")
app.command()(run.run_command)
app.command()(serve.serve_command)

@app.callback()
def main(
    version: bool = typer.Option(
        False,
        "--version",
        "-v",
        help="Show version"
    )
):
    """Vocal CLI"""
    if version:
        console.print("vocal v0.1.0")
        raise typer.Exit()

if __name__ == "__main__":
    app()
```

**packages/cli/vocal_cli/commands/run.py:** ⏳ TODO
**packages/cli/vocal_cli/commands/run.py:** ⏳ TODO
```python
import typer
from pathlib import Path
from rich.console import Console
from rich.progress import Progress, SpinnerColumn, TextColumn
from vocal_sdk import Vocal
from vocal_sdk.exceptions import ApiException

console = Console()

def run_command(
    audio_file: Path = typer.Argument(
        ...,
        help="Audio file to transcribe"
    ),
    model: str = typer.Option(
        "openai/whisper-large-v3",
        "--model",
        "-m",
        help="Model to use"
    ),
    language: Optional[str] = typer.Option(
        None,
        "--language",
        "-l",
        help="Language code (auto-detect if not specified)"
    ),
    output: Optional[Path] = typer.Option(
        None,
        "--output",
        "-o",
        help="Output file (default: stdout)"
    ),
    format: str = typer.Option(
        "text",
        "--format",
        "-f",
        help="Output format: text, json, srt, vtt"
    ),
    base_url: str = typer.Option(
        "http://localhost:11435",
        "--url",
        help="API base URL"
    )
):
    """
    Transcribe an audio file
    
    Examples:
    
        vocal run audio.mp3
        
        vocal run audio.mp3 --model openai/whisper-large-v3 --language es
        
        vocal run audio.mp3 --output transcript.srt --format srt
    """
    
    if not audio_file.exists():
        console.print(f"[red]Error:[/red] File not found: {audio_file}")
        raise typer.Exit(1)
    
    client = Vocal(base_url=base_url)
    
    with Progress(
        SpinnerColumn(),
        TextColumn("[progress.description]{task.description}"),
        console=console
    ) as progress:
        task = progress.add_task(
            f"Transcribing {audio_file.name}...",
            total=None
        )
        
        try:
            result = client.transcribe(
                file=audio_file,
                model=model,
                language=language,
                response_format=format
            )
            
            progress.update(task, completed=True)
            
        except ApiException as e:
            progress.stop()
            console.print(f"[red]Error:[/red] {e}")
            raise typer.Exit(1)
    
    if output:
        output.write_text(result.text)
        console.print(f"[green]✓[/green] Saved to {output}")
    else:
        console.print("\n" + result.text)
    
    console.print(f"\n[dim]Language: {result.language} | Duration: {result.duration:.1f}s[/dim]")
```

**packages/cli/vocal_cli/commands/models.py:** ⏳ TODO
**packages/cli/vocal_cli/commands/models.py:** ⏳ TODO
```python
import typer
from rich.console import Console
from rich.table import Table
from vocal_sdk import Vocal

app = typer.Typer(help="Manage models")
console = Console()

@app.command("list")
def list_models(
    status: Optional[str] = typer.Option(None, "--status", "-s")
):
    """List available models"""
    client = Vocal()
    
    try:
        response = client.list_models(status=status)
        
        table = Table(title="Available Models")
        table.add_column("ID", style="cyan")
        table.add_column("Name", style="white")
        table.add_column("Size", style="yellow")
        table.add_column("Status", style="green")
        
        for model in response.models:
            status_color = {
                "available": "green",
                "downloading": "yellow",
                "not_downloaded": "dim"
            }.get(model.status, "white")
            
            table.add_row(
                model.id,
                model.name,
                model.size_readable,
                f"[{status_color}]{model.status}[/{status_color}]"
            )
        
        console.print(table)
        
    except Exception as e:
        console.print(f"[red]Error:[/red] {e}")
        raise typer.Exit(1)

@app.command("pull")
def pull_model(
    model_id: str = typer.Argument(..., help="Model ID to download"),
    quantization: Optional[str] = typer.Option(None, "--quantize", "-q")
):
    """Download a model"""
    client = Vocal()
    
    console.print(f"📥 Downloading {model_id}...")
    
    try:
        progress = client.download_model(model_id, quantization)
        
        console.print(f"[green]✓[/green] Downloaded {model_id}")
        
    except Exception as e:
        console.print(f"[red]Error:[/red] {e}")
        raise typer.Exit(1)

@app.command("show")
def show_model(
    model_id: str = typer.Argument(...)
):
    """Show model details"""
    client = Vocal()
    
    try:
        model = client.get_model(model_id)
        
        console.print(f"\n[bold]{model.name}[/bold]")
        console.print(f"ID: {model.id}")
        console.print(f"Provider: {model.provider}")
        console.print(f"Size: {model.size_readable}")
        console.print(f"Parameters: {model.parameters}")
        console.print(f"Languages: {', '.join(model.languages[:10])}")
        console.print(f"Backend: {model.backend}")
        console.print(f"Status: {model.status}")
        
        if model.description:
            console.print(f"\n{model.description}")
        
    except Exception as e:
        console.print(f"[red]Error:[/red] {e}")
        raise typer.Exit(1)
```

---

## 🏗️ Development Workflow

### Step 1: Start with Core Registry ⏳ TODO
```bash
# 1. Build generic model registry with HuggingFace provider
cd packages/core/vocal_core/registry
# Implement: base.py, model_info.py, providers/huggingface.py

# 2. Build model adapters (start with faster-whisper)
cd ../adapters/stt
# Implement: base.py, faster_whisper.py

# 3. Build storage layer
cd ../../storage
# Implement: model_store.py, cache.py

# 4. Test core functionality
uv run pytest
```

### Step 2: Build API on top of Core ⏳ TODO
```bash
# 1. Create API schemas (Pydantic models)
cd packages/api/vocal_api/models
# Edit transcription.py, model.py

# 2. Create routes
cd ../routes
# Edit transcription.py, models.py

# 3. Run API
uv run uvicorn vocal_api.main:app --reload

# 4. Check OpenAPI docs
# Visit http://localhost:8000/docs
```

### Step 3: Generate SDK ⏳ TODO
```bash
# Generate SDK from OpenAPI spec
cd packages/sdk
./scripts/generate.sh

# SDK is now ready at packages/sdk/vocal_sdk/
```

### Step 4: Build CLI using SDK ⏳ TODO
```bash
# Install SDK
cd packages/sdk
uv pip install -e .

# Build CLI
cd packages/cli
# CLI commands use SDK client

# Test CLI
vocal models list
vocal run audio.mp3
```

---

## ✅ Benefits of This Architecture

1. **Type Safety Everywhere**
   - Pydantic models validate at API
   - SDK has full type hints
   - CLI gets type safety from SDK

2. **Single Source of Truth**
   - API defines all contracts
   - OpenAPI spec auto-generated
   - SDK auto-generated from spec
   - No schema drift

3. **Generic & Extensible**
   - Registry-based model management
   - Provider-agnostic (HuggingFace, local, custom)
   - Supports STT now, TTS later
   - Pluggable adapters for any backend

4. **Easy Testing**
   - Test API directly
   - Mock SDK for CLI tests
   - OpenAPI spec = automatic client tests

5. **Multi-Language Support**
   - Same OpenAPI spec
   - Generate JS/TS SDK: `openapi-generator-cli generate -g typescript-axios`
   - Generate Go SDK: `openapi-generator-cli generate -g go`

6. **Clean Separation**
   - Core = model management & inference
   - API = business logic & HTTP interface
   - SDK = client library
   - CLI = user interface
   - Each can be versioned independently

---

## 🚀 Getting Started

```bash
# 1. Create monorepo with uv
mkdir vocal && cd vocal
uv init

# 2. Set up workspace structure
mkdir -p packages/{api,core,sdk,cli}

# 3. Start with Core (registry + adapters)
cd packages/core
# Build generic registry with HuggingFace provider
# Build adapters (faster-whisper, etc.)

# 4. Build API on top of Core
cd packages/api
# Create models, routes, services

# 5. Run API
uv run uvicorn vocal_api.main:app --reload

# 6. Generate SDK
cd packages/sdk
./scripts/generate.sh

# 7. Build CLI
cd packages/cli
# Implement commands using SDK

# 8. Test end-to-end
vocal run audio.mp3
```

---

## 📦 Package Dependencies (uv workspace)

**Root pyproject.toml:** ⏳ TODO
```toml
[project]
name = "vocal"
version = "0.1.0"
requires-python = ">=3.11"

[tool.uv.workspace]
members = [
    "packages/core",
    "packages/api",
    "packages/sdk",
    "packages/cli"
]
```

**packages/core/pyproject.toml:** ⏳ TODO
```toml
[project]
name = "vocal-core"
version = "0.1.0"
requires-python = ">=3.11"
dependencies = [
    "faster-whisper>=1.0.0",
    "huggingface-hub>=0.20.0",
    "torch>=2.1.0",
    "pydantic>=2.5.0",
]
```

**packages/api/pyproject.toml:** ⏳ TODO
```toml
[project]
name = "vocal-api"
version = "0.1.0"
requires-python = ">=3.11"
dependencies = [
    "fastapi>=0.109.0",
    "uvicorn[standard]>=0.27.0",
    "pydantic>=2.5.0",
    "python-multipart>=0.0.6",
    "vocal-core",
]
```

**packages/sdk/pyproject.toml:** ⏳ TODO (Generated)
```toml
[project]
name = "vocal-sdk"
version = "0.1.0"
requires-python = ">=3.11"
dependencies = [
    "urllib3>=2.0.0",
    "python-dateutil>=2.8.0",
    "pydantic>=2.5.0",
]
```

**packages/cli/pyproject.toml:** ⏳ TODO
```toml
[project]
name = "vocal"
version = "0.1.0"
requires-python = ">=3.11"
dependencies = [
    "typer>=0.9.0",
    "rich>=13.7.0",
    "vocal-sdk",
]

[project.scripts]
vocal = "vocal_cli.main:app"
```

---

## 🎯 Implementation Priority

### Phase 0: Core Foundation (START HERE) ✅ DONE
1. ✅ Generic model registry interface
2. ✅ HuggingFace provider implementation
3. ✅ Model storage & caching layer
4. ✅ Base adapter interface
5. ✅ faster-whisper adapter (first STT model)

### Phase 1: API Layer ✅ DONE
1. ✅ Pydantic models (transcription.py)
2. ✅ API routes (transcription.py)
3. ✅ Services (transcription_service.py)
4. ✅ FastAPI app setup with CORS and health endpoints

### Phase 2: SDK Generation ✅ DONE
1. ✅ OpenAPI spec auto-generation
2. ✅ Python SDK with clean interface
3. ✅ SDK documentation

### Phase 3: CLI ⏳ TODO
1. CLI commands (run, models, serve)
2. Rich UI components
3. End-to-end testing

---

## 🔑 Key Design Decisions

1. **HuggingFace as Primary Provider**
   - ✅ Best ecosystem for OSS models
   - ✅ Built-in caching & download management
   - ✅ Easy to extend with custom providers

2. **faster-whisper as Default Backend**
   - ✅ 4x faster than OpenAI Whisper
   - ✅ Same accuracy
   - ✅ Lower memory usage
   - ✅ CTranslate2 optimizations

3. **Registry Pattern for Models**
   - ✅ Supports multiple providers (HF, local, custom)
   - ✅ Easy to add new model types (TTS later)
   - ✅ Centralized model metadata & discovery

4. **API-First Architecture**
   - ✅ Auto-generated SDK & docs
   - ✅ Type-safe everywhere
   - ✅ Easy to build clients in any language

5. **No Auth for POC**
   - Can be added later via middleware
   - Not critical for local/self-hosted deployment

---

This architecture is **generic, extensible, and production-ready**! 🎯
