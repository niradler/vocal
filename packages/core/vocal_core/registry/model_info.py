from enum import Enum

from pydantic import BaseModel, Field, HttpUrl


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
    KOKORO = "kokoro"
    FASTER_QWEN3_TTS = "faster_qwen3_tts"
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
    description: str | None = None
    size: int = Field(description="Model size in bytes", default=0)
    size_readable: str = Field(description="Human-readable size (e.g., '3.1GB')", default="Unknown")
    parameters: str = Field(description="Number of parameters (e.g., '1.5B')", default="Unknown")
    languages: list[str] = Field(description="Supported languages", default_factory=list)
    backend: ModelBackend = Field(description="Inference backend")
    status: ModelStatus = Field(description="Current model status", default=ModelStatus.NOT_DOWNLOADED)
    source_url: HttpUrl | None = None
    license: str | None = None
    recommended_vram: str | None = Field(None, description="Recommended VRAM (e.g., '6GB+')")
    task: ModelTask = Field(description="Task type: 'stt' or 'tts'")
    local_path: str | None = Field(None, description="Local filesystem path if downloaded")
    modified_at: str | None = Field(None, description="Last modified date on HuggingFace")
    downloaded_at: str | None = Field(None, description="Date when downloaded locally")
    author: str | None = Field(None, description="Model author/organization on HuggingFace")
    tags: list[str] = Field(default_factory=list, description="HuggingFace tags")
    downloads: int | None = Field(None, description="Total download count on HuggingFace")
    likes: int | None = Field(None, description="Total likes on HuggingFace")
    sha: str | None = Field(None, description="Git commit SHA on HuggingFace")
    files: list[dict] | None = Field(None, description="List of model files")

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
                "task": "stt",
            }
        }
    }


def format_bytes(size: int) -> str:
    """Format bytes to human-readable size"""
    for unit in ["B", "KB", "MB", "GB", "TB"]:
        if size < 1024.0:
            return f"{size:.1f}{unit}"
        size /= 1024.0
    return f"{size:.1f}PB"
