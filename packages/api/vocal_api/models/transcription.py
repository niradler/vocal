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
        examples=["openai/whisper-large-v3", "openai/whisper-tiny"]
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
    
    model_config = {
        "json_schema_extra": {
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
    }
