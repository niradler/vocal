import logging
import subprocess
import tempfile
import wave
from pathlib import Path
from typing import Annotated, Literal

from fastapi import APIRouter, Depends, File, Form, HTTPException, Response, UploadFile
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, Field, field_validator

from vocal_core.config import vocal_settings

from ..config import settings
from ..dependencies import get_tts_service
from ..services.tts_service import TTSService

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/v1/audio", tags=["audio"])

AudioFormat = Literal["mp3", "opus", "aac", "flac", "wav", "pcm"]

_MEDIA_TYPES: dict[str, str] = {
    "mp3": "audio/mpeg",
    "opus": "audio/opus",
    "aac": "audio/aac",
    "flac": "audio/flac",
    "wav": "audio/wav",
    "pcm": "audio/pcm",
}
_CLONE_AUDIO_EXTENSIONS = {".wav", ".mp3", ".m4a", ".aac", ".flac", ".opus", ".ogg"}
_CLONE_MIN_SECONDS = 3.0
_CLONE_MAX_SECONDS = 30.0


def _probe_reference_audio_duration(path: Path) -> float:
    if path.suffix.lower() == ".wav":
        try:
            with wave.open(str(path), "rb") as wav_file:
                frames = wav_file.getnframes()
                sample_rate = wav_file.getframerate()
        except wave.Error as exc:
            raise ValueError("reference_audio must be a valid WAV/MP3/M4A recording.") from exc
        if sample_rate <= 0:
            raise ValueError("Reference audio has an invalid sample rate.")
        return frames / float(sample_rate)

    try:
        probe = subprocess.run(
            [
                "ffprobe",
                "-v",
                "quiet",
                "-show_entries",
                "format=duration",
                "-of",
                "default=noprint_wrappers=1:nokey=1",
                str(path),
            ],
            check=True,
            capture_output=True,
            text=True,
            timeout=10,
        )
    except FileNotFoundError as exc:
        raise ValueError("ffprobe is required to validate non-WAV reference audio.") from exc
    except subprocess.CalledProcessError as exc:
        raise ValueError("Unable to inspect reference audio. Provide a valid WAV/MP3/M4A recording.") from exc

    try:
        return float(probe.stdout.strip())
    except ValueError as exc:
        raise ValueError("Unable to determine reference audio duration.") from exc


async def _prepare_reference_audio_for_clone(reference_audio: UploadFile, model: str, service: TTSService) -> Path:
    suffix = Path(reference_audio.filename or "ref.wav").suffix.lower() or ".wav"
    if suffix not in _CLONE_AUDIO_EXTENSIONS:
        raise HTTPException(
            status_code=422,
            detail=f"Unsupported reference audio format '{suffix}'. Supported formats: {', '.join(sorted(_CLONE_AUDIO_EXTENSIONS))}",
        )

    with tempfile.NamedTemporaryFile(delete=False, suffix=suffix) as tmp:
        ref_path = Path(tmp.name)

    content = await reference_audio.read()
    if not content:
        ref_path.unlink(missing_ok=True)
        raise HTTPException(status_code=422, detail="reference_audio must not be empty.")

    if len(content) > settings.MAX_UPLOAD_SIZE:
        ref_path.unlink(missing_ok=True)
        raise HTTPException(
            status_code=422,
            detail=f"reference_audio too large. Max {settings.MAX_UPLOAD_SIZE // (1024 * 1024)}MB.",
        )

    ref_path.write_bytes(content)

    try:
        duration = _probe_reference_audio_duration(ref_path)
        if duration < _CLONE_MIN_SECONDS or duration > _CLONE_MAX_SECONDS:
            raise HTTPException(
                status_code=422,
                detail=f"reference_audio must be between {_CLONE_MIN_SECONDS:g} and {_CLONE_MAX_SECONDS:g} seconds.",
            )

        return ref_path
    except Exception:
        ref_path.unlink(missing_ok=True)
        raise


class TTSRequest(BaseModel):
    """Text-to-Speech request (OpenAI-compatible)"""

    model: str = Field(..., description="TTS model to use (e.g., 'hexgrad/Kokoro-82M', 'pyttsx3')")
    input: str = Field(..., min_length=1, description="The text to synthesize")
    voice: str | None = Field(None, description="Voice ID to use (model-specific, see /v1/audio/voices)")
    speed: float = Field(1.0, ge=0.25, le=4.0, description="Speech speed multiplier")
    response_format: AudioFormat = Field("mp3", description="Audio format: mp3, opus, aac, flac, wav, pcm")
    stream: bool = Field(False, description="Stream audio chunks as they are generated")

    @field_validator("input")
    @classmethod
    def input_not_blank(cls, v: str) -> str:
        if not v.strip():
            raise ValueError("input text must not be blank or whitespace-only")
        return v


class VoiceInfo(BaseModel):
    """Voice information"""

    id: str
    name: str
    language: str
    gender: str | None = None


class VoicesResponse(BaseModel):
    """Response containing list of voices"""

    voices: list[VoiceInfo]
    total: int


class CloneResponse(BaseModel):
    """Voice clone synthesis response metadata"""

    model: str
    duration: float
    sample_rate: int
    format: str


@router.post(
    "/speech",
    response_class=Response,
    responses={
        200: {"content": {"audio/mpeg": {}}, "description": "Audio file in the requested format"},
        503: {"description": "Model or required dependency not available on this server"},
    },
)
async def text_to_speech(request: TTSRequest, service: TTSService = Depends(get_tts_service)):
    """
    Generate speech from text (OpenAI-compatible endpoint).

    - **model**: TTS model (e.g., 'hexgrad/Kokoro-82M', 'pyttsx3')
    - **input**: Text to convert to speech
    - **voice**: Optional voice ID (use /v1/audio/voices to list available voices)
    - **speed**: Speech speed multiplier (0.25 to 4.0, default: 1.0)
    - **response_format**: Audio format (mp3, opus, aac, flac, wav, pcm)
    - **stream**: Stream audio chunks as they are generated
    """
    fmt = request.response_format
    media_type = _MEDIA_TYPES.get(fmt, f"audio/{fmt}")
    ext = fmt if fmt != "pcm" else "raw"

    try:
        if request.stream:
            generator = service.synthesize_stream(
                model_id=request.model,
                text=request.input,
                voice=request.voice,
                speed=request.speed,
                output_format=fmt,
            )
            return StreamingResponse(
                generator,
                media_type=media_type,
                headers={"Content-Disposition": f"attachment; filename=speech.{ext}"},
            )

        result = await service.synthesize(
            model_id=request.model,
            text=request.input,
            voice=request.voice,
            speed=request.speed,
            output_format=fmt,
        )

        return Response(
            content=result.audio_data,
            media_type=media_type,
            headers={
                "Content-Disposition": f"attachment; filename=speech.{ext}",
                "X-Duration": str(result.duration),
                "X-Sample-Rate": str(result.sample_rate),
            },
        )

    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except ImportError as e:
        raise HTTPException(status_code=503, detail=str(e))
    except Exception as e:
        logger.exception("TTS synthesis failed")
        raise HTTPException(status_code=500, detail=f"TTS error: {str(e)}")


@router.get("/voices", response_model=VoicesResponse)
async def list_voices(model: str | None = None, service: TTSService = Depends(get_tts_service)):
    """
    List available TTS voices.

    - **model**: Optional model ID to list voices for a specific model
    """
    try:
        voices = await service.get_voices(model_id=model)
        voice_infos = [VoiceInfo(id=v.id, name=v.name, language=v.language, gender=v.gender) for v in voices]
        return VoicesResponse(voices=voice_infos, total=len(voice_infos))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to list voices: {str(e)}")


@router.post(
    "/clone",
    response_class=Response,
    responses={
        200: {"content": {"audio/wav": {}}, "description": "Synthesized audio using cloned voice"},
        503: {"description": "Model or required dependency not available on this server"},
    },
    summary="Voice cloning synthesis",
)
async def voice_clone(
    reference_audio: Annotated[UploadFile, File(description="Reference audio recording for voice cloning (wav/mp3/m4a, 3-30s recommended)")],
    text: Annotated[str, Form(description="Text to synthesize in the cloned voice")],
    model: Annotated[str, Form(description="TTS model to use for voice cloning (must support cloning, e.g. Qwen3-TTS base variants)")] = vocal_settings.TTS_DEFAULT_CLONE_MODEL,
    reference_text: Annotated[str | None, Form(description="Optional transcript of the reference audio")] = None,
    language: Annotated[str, Form(description="Target language code (e.g. 'en', 'zh')")] = "en",
    response_format: Annotated[AudioFormat, Form(description="Output format")] = "wav",
    service: TTSService = Depends(get_tts_service),
):
    """
    Clone a voice from a reference recording and synthesize text with it.

    Upload a short audio recording of the speaker (3–30 seconds) and the text you want
    synthesized. The model generates speech that matches the voice characteristics of the
    provided reference.

    **Supported models:** Qwen3-TTS base variants (require CUDA). Use `/v1/models` to see
    available cloning-capable models.

    **Reference audio:** wav, mp3, m4a recommended. 3–30 seconds of clean speech.

    **Note:** Voice cloning is hardware-intensive. Ensure the model is downloaded first
    via `POST /v1/models/{model_id}/download`.
    """
    if not text.strip():
        raise HTTPException(status_code=422, detail="text must not be empty.")

    fmt = response_format
    media_type = _MEDIA_TYPES.get(fmt, f"audio/{fmt}")
    ext = fmt if fmt != "pcm" else "raw"

    ref_path: Path | None = None
    try:
        ref_path = await _prepare_reference_audio_for_clone(reference_audio, model, service)
        capabilities = await service.get_capabilities(model_id=model)
        if not capabilities.supports_voice_clone:
            raise HTTPException(status_code=400, detail=f"Model {model} does not support reference-audio voice cloning.")

        result = await service.clone_synthesize(
            model_id=model,
            text=text,
            output_format=fmt,
            language=language,
            reference_audio_path=str(ref_path),
            reference_text=reference_text,
        )

        return Response(
            content=result.audio_data,
            media_type=media_type,
            headers={
                "Content-Disposition": f"attachment; filename=clone.{ext}",
                "X-Duration": str(result.duration),
                "X-Sample-Rate": str(result.sample_rate),
            },
        )

    except HTTPException:
        raise
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except ImportError as e:
        raise HTTPException(status_code=503, detail=str(e))
    except RuntimeError as e:
        raise HTTPException(status_code=503, detail=str(e))
    except Exception as e:
        logger.exception("Voice clone synthesis failed")
        raise HTTPException(status_code=500, detail=f"Voice clone error: {str(e)}")
    finally:
        if ref_path:
            ref_path.unlink(missing_ok=True)


tts_router = router
