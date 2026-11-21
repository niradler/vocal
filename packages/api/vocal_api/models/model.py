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
    WHISPERX = "whisperx"
    ONNX = "onnx"
    KOKORO = "kokoro"
    FASTER_QWEN3_TTS = "faster_qwen3_tts"
    PIPER = "piper"
    CHATTERBOX = "chatterbox"
    VOXTRAL_STT = "voxtral_stt"
    VOXTRAL_TTS = "voxtral_tts"
    OMNIVOICE = "omnivoice"
    SUPERTONIC = "supertonic"
    VOXCPM = "voxcpm"
    PHONON = "phonon"
    QWEN3_OMNI_STT = "qwen3_omni_stt"
    QWEN3_OMNI_TTS = "qwen3_omni_tts"
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


class ModelRuntime(str, Enum):
    """How a model is executed"""

    IN_PROCESS = "in_process"
    EXTERNAL = "external"


class ModelMaintenanceStatus(str, Enum):
    """Upstream maintenance state of the model"""

    ACTIVE = "active"
    RETIRED = "retired"
    DEPRECATED = "deprecated"


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
    commercial_use: bool | None = Field(default=None, description="Whether the model weights license permits commercial use")
    runtime: ModelRuntime = Field(default=ModelRuntime.IN_PROCESS, description="'in_process' when Vocal runs the model itself, 'external' when it needs an out-of-process engine")
    runtime_note: str | None = Field(default=None, description="Engine/serving requirement outside Vocal's bundled adapters, if any")
    maintenance_status: ModelMaintenanceStatus = Field(default=ModelMaintenanceStatus.ACTIVE, description="Upstream maintenance state (active/retired/deprecated)")
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
    supports_streaming: bool = Field(default=False, description="Whether the model supports true streaming output")
    supports_live_streaming: bool = Field(default=False, description="Whether the model supports true chunk-by-chunk live audio streaming")
    supports_voice_list: bool = Field(default=False, description="Whether the model exposes selectable voices")
    supports_voice_clone: bool = Field(default=False, description="Whether the model supports reference-audio voice cloning")
    supports_voice_design: bool = Field(default=False, description="Whether the model supports prompt/instruction-based voice design")
    requires_gpu: bool = Field(default=False, description="Whether the model requires GPU acceleration")
    voice_mode: str | None = Field(default=None, description="How /v1/audio/speech interprets the voice field")
    clone_mode: str | None = Field(default=None, description="How /v1/audio/clone works for this model")
    reference_audio_min_seconds: float | None = Field(default=None, description="Recommended minimum reference audio length for cloning")
    reference_audio_max_seconds: float | None = Field(default=None, description="Recommended maximum reference audio length for cloning")
    output_formats: list[str] = Field(default_factory=list, description="Audio formats /v1/audio/speech accepts for this model (empty for STT)")


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
    progress: float = Field(ge=0.0, default=0.0)
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
