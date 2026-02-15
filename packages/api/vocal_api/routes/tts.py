from typing import Literal

from fastapi import APIRouter, Depends, HTTPException, Response
from pydantic import BaseModel, Field

from ..dependencies import get_tts_service
from ..services.tts_service import TTSService

router = APIRouter(prefix="/v1/audio", tags=["audio"])

AudioFormat = Literal["mp3", "opus", "aac", "flac", "wav", "pcm"]

# Content-Type for each supported format
_MEDIA_TYPES: dict[str, str] = {
    "mp3": "audio/mpeg",
    "opus": "audio/opus",
    "aac": "audio/aac",
    "flac": "audio/flac",
    "wav": "audio/wav",
    "pcm": "audio/pcm",
}


class TTSRequest(BaseModel):
    """Text-to-Speech request (OpenAI-compatible)"""

    model: str = Field(..., description="TTS model to use (e.g., 'hexgrad/Kokoro-82M')")
    input: str = Field(..., description="The text to synthesize")
    voice: str | None = Field(None, description="Voice ID to use")
    speed: float = Field(1.0, ge=0.25, le=4.0, description="Speech speed multiplier")
    response_format: AudioFormat = Field("mp3", description="Audio format: mp3, opus, aac, flac, wav, pcm")


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


@router.post(
    "/speech",
    response_class=Response,
    responses={200: {"content": {"audio/mpeg": {}}, "description": "Audio file in the requested format"}},
)
async def text_to_speech(request: TTSRequest, service: TTSService = Depends(get_tts_service)):
    """
    Generate speech from text (OpenAI-compatible endpoint)

    This endpoint synthesizes audio from text using the specified TTS model.

    - **model**: TTS model to use (e.g., 'hexgrad/Kokoro-82M', 'coqui/XTTS-v2')
    - **input**: The text to convert to speech
    - **voice**: Optional voice ID (use /v1/audio/voices to list available voices)
    - **speed**: Speech speed multiplier (0.25 to 4.0, default: 1.0)
    - **response_format**: Audio format (mp3, opus, aac, flac, wav, pcm)
    """
    try:
        result = await service.synthesize(
            model_id=request.model,
            text=request.input,
            voice=request.voice,
            speed=request.speed,
            output_format=request.response_format,
        )

        fmt = result.format
        media_type = _MEDIA_TYPES.get(fmt, f"audio/{fmt}")
        ext = fmt if fmt != "pcm" else "raw"

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
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"TTS error: {str(e)}")


@router.get("/voices", response_model=VoicesResponse)
async def list_voices(model: str | None = None, service: TTSService = Depends(get_tts_service)):
    """
    List available TTS voices

    Returns a list of all available voices that can be used for speech synthesis.

    - **model**: Optional model ID to list voices for a specific model
    """
    try:
        voices = await service.get_voices(model_id=model)

        voice_infos = [VoiceInfo(id=v.id, name=v.name, language=v.language, gender=v.gender) for v in voices]

        return VoicesResponse(voices=voice_infos, total=len(voice_infos))

    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to list voices: {str(e)}")


tts_router = router
