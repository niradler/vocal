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


class ModelTask(str, Enum):
    """Model task type"""
    STT = "stt"
    TTS = "tts"


class ModelInfo(BaseModel):
    """Model information schema"""
    id: str = Field(description="Unique model identifier (e.g., 'openai/whisper-large-v3')")
    name: str = Field(description="Human-readable model name")
    provider: ModelProvider = Field(description="Model provider")
    description: Optional[str] = None
    size: int = Field(description="Model size in bytes", default=0)
    size_readable: str = Field(description="Human-readable size (e.g., '3.1GB')", default="Unknown")
    parameters: str = Field(description="Number of parameters (e.g., '1.5B')", default="Unknown")
    languages: list[str] = Field(description="Supported languages", default_factory=list)
    backend: ModelBackend = Field(description="Inference backend")
    status: ModelStatus = Field(description="Current model status", default=ModelStatus.NOT_DOWNLOADED)
    source_url: Optional[HttpUrl] = None
    license: Optional[str] = None
    recommended_vram: Optional[str] = Field(
        None,
        description="Recommended VRAM (e.g., '6GB+')"
    )
    task: ModelTask = Field(description="Task type: 'stt' or 'tts'")
    local_path: Optional[str] = Field(
        None,
        description="Local filesystem path if downloaded"
    )
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None

    model_config = {
        "json_schema_extra": {
            "example": {
                "id": "openai/whisper-large-v3",
                "name": "OpenAI Whisper Large V3",
                "provider": "huggingface",
                "size": 3100000000,
                "size_readable": "3.1GB",
                "parameters": "1.5B",
                "languages": ["en", "es", "fr", "de"],
                "backend": "faster_whisper",
                "status": "available",
                "recommended_vram": "6GB+",
                "task": "stt"
            }
        }
    }


def format_bytes(size: int) -> str:
    """Format bytes to human-readable size"""
    for unit in ['B', 'KB', 'MB', 'GB', 'TB']:
        if size < 1024.0:
            return f"{size:.1f}{unit}"
        size /= 1024.0
    return f"{size:.1f}PB"
