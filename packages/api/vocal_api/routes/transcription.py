from fastapi import APIRouter, UploadFile, File, Form, Depends, HTTPException
from typing import Annotated, Optional

from ..models.transcription import (
    TranscriptionRequest,
    TranscriptionResponse,
    TranscriptionFormat
)
from ..services import TranscriptionService
from ..dependencies import get_transcription_service
from ..config import settings

router = APIRouter(prefix="/v1/audio", tags=["transcription"])


@router.post(
    "/transcriptions",
    response_model=TranscriptionResponse,
    summary="Transcribe audio",
    description="Transcribe audio file to text using specified model"
)
async def create_transcription(
    file: Annotated[UploadFile, File(description="Audio file to transcribe")],
    model: Annotated[str, Form(description="Model ID")] = "openai/whisper-tiny",
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
    
    if size > settings.MAX_UPLOAD_SIZE:
        raise HTTPException(400, f"File too large. Max {settings.MAX_UPLOAD_SIZE // (1024*1024)}MB.")
    
    request = TranscriptionRequest(
        model=model,
        language=language,
        prompt=prompt,
        response_format=response_format,
        temperature=temperature
    )
    
    try:
        result = await service.transcribe(file, request)
        return result
    except ValueError as e:
        raise HTTPException(400, str(e))
    except Exception as e:
        raise HTTPException(500, f"Transcription failed: {str(e)}")


@router.post(
    "/translations",
    response_model=TranscriptionResponse,
    summary="Translate audio to English",
    description="Translate audio to English text"
)
async def create_translation(
    file: Annotated[UploadFile, File()],
    model: Annotated[str, Form()] = "openai/whisper-tiny",
    service: TranscriptionService = Depends(get_transcription_service)
) -> TranscriptionResponse:
    """Translate audio to English."""
    try:
        return await service.translate(file, model)
    except ValueError as e:
        raise HTTPException(400, str(e))
    except Exception as e:
        raise HTTPException(500, f"Translation failed: {str(e)}")
