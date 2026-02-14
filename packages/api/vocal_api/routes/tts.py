from fastapi import APIRouter, HTTPException, Response
from pydantic import BaseModel, Field

from ..services.tts_service import TTSService

router = APIRouter(prefix="/v1/audio", tags=["audio"])
tts_service = TTSService()


class TTSRequest(BaseModel):
    """Text-to-Speech request"""

    input: str = Field(..., description="The text to synthesize")
    voice: str | None = Field(None, description="Voice ID to use")
    speed: float = Field(1.0, ge=0.25, le=4.0, description="Speech speed multiplier")
    response_format: str = Field("wav", description="Audio format (currently only 'wav' supported)")


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
    responses={200: {"content": {"audio/wav": {}}, "description": "Audio file in WAV format"}},
)
async def text_to_speech(request: TTSRequest):
    """
    Generate speech from text (OpenAI-compatible endpoint)

    This endpoint synthesizes audio from text using the configured TTS engine.

    - **input**: The text to convert to speech
    - **voice**: Optional voice ID (use /v1/audio/voices to list available voices)
    - **speed**: Speech speed multiplier (0.25 to 4.0, default: 1.0)
    - **response_format**: Audio format (currently only 'wav' supported)
    """
    try:
        result = await tts_service.synthesize(
            text=request.input,
            voice=request.voice,
            speed=request.speed,
            output_format=request.response_format,
        )

        return Response(
            content=result.audio_data,
            media_type=f"audio/{result.format}",
            headers={
                "Content-Disposition": f"attachment; filename=speech.{result.format}",
                "X-Duration": str(result.duration),
                "X-Sample-Rate": str(result.sample_rate),
            },
        )

    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"TTS error: {str(e)}")


@router.get("/voices", response_model=VoicesResponse)
async def list_voices():
    """
    List available TTS voices

    Returns a list of all available voices that can be used for speech synthesis.
    """
    try:
        voices = await tts_service.get_voices()

        voice_infos = [VoiceInfo(id=v.id, name=v.name, language=v.language, gender=v.gender) for v in voices]

        return VoicesResponse(voices=voice_infos, total=len(voice_infos))

    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to list voices: {str(e)}")


tts_router = router
