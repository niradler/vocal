from pydantic import BaseModel, Field, HttpUrl
from typing import Optional
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
    id: str = Field(description="Unique model identifier")
    name: str = Field(description="Human-readable model name")
    provider: ModelProvider = Field(description="Model provider")
    description: Optional[str] = None
    size: int = Field(description="Model size in bytes", default=0)
    size_readable: str = Field(description="Human-readable size", default="Unknown")
    parameters: str = Field(description="Number of parameters", default="Unknown")
    languages: list[str] = Field(description="Supported languages", default_factory=list)
    backend: ModelBackend = Field(description="Inference backend")
    status: ModelStatus = Field(description="Current model status")
    source_url: Optional[HttpUrl] = None
    license: Optional[str] = None
    recommended_vram: Optional[str] = None
    task: ModelTask = Field(description="Task type")
    local_path: Optional[str] = None
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None


class ModelListResponse(BaseModel):
    """List of available models"""
    models: list[ModelInfo]
    total: int


class ModelDownloadRequest(BaseModel):
    """Request to download a model"""
    model_id: str
    quantization: Optional[str] = None
    provider: Optional[str] = "huggingface"


class ModelDownloadProgress(BaseModel):
    """Model download progress"""
    model_id: str
    status: str
    progress: float = Field(ge=0.0, le=1.0, default=0.0)
    downloaded_bytes: int = 0
    total_bytes: int = 0
    message: Optional[str] = None
