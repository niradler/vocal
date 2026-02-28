from enum import Enum

from pydantic import BaseModel, ConfigDict, Field, HttpUrl


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

    model_config = ConfigDict(exclude_none=True)

    id: str = Field(description="Unique model identifier")
    name: str = Field(description="Human-readable model name")
    provider: ModelProvider = Field(description="Model provider")
    description: str | None = Field(default=None, description="Model description from HuggingFace")
    size: int = Field(description="Model size in bytes", default=0)
    size_readable: str = Field(description="Human-readable size", default="Unknown")
    parameters: str = Field(description="Number of parameters", default="Unknown")
    languages: list[str] = Field(description="Supported languages", default_factory=list)
    backend: ModelBackend = Field(description="Inference backend")
    status: ModelStatus = Field(description="Current model status")
    source_url: HttpUrl | None = None
    license: str | None = None
    recommended_vram: str | None = None
    task: ModelTask = Field(description="Task type")
    local_path: str | None = None
    modified_at: str | None = Field(default=None, description="Last modified date on HuggingFace")
    downloaded_at: str | None = Field(default=None, description="Date when model was downloaded locally")
    author: str | None = Field(default=None, description="Model author/organization")
    tags: list[str] = Field(default_factory=list, description="HuggingFace tags")
    downloads: int | None = Field(default=None, description="Download count on HuggingFace")
    likes: int | None = Field(default=None, description="Likes on HuggingFace")
    sha: str | None = Field(default=None, description="Git commit SHA")
    files: list[dict] | None = Field(default=None, description="List of model files")


class ModelListResponse(BaseModel):
    """List of available models"""

    models: list[ModelInfo]
    total: int


class ModelDownloadRequest(BaseModel):
    """Request to download a model"""

    model_id: str
    quantization: str | None = None
    provider: str | None = "huggingface"


class ModelDownloadProgress(BaseModel):
    """Model download progress"""

    model_id: str
    status: str
    progress: float = Field(ge=0.0, le=1.0, default=0.0)
    downloaded_bytes: int = 0
    total_bytes: int = 0
    message: str | None = None


class ModelShowRequest(BaseModel):
    """Request to show model details (Ollama-style)"""

    model: str
    verbose: bool = False


class ModelPullRequest(BaseModel):
    """Request to download/pull a model (Ollama-style)"""

    model: str
    stream: bool = True
