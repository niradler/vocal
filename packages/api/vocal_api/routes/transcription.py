from typing import Annotated

from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile
from fastapi.responses import PlainTextResponse, Response

from vocal_core.config import vocal_settings

from ..config import settings
from ..dependencies import get_transcription_service
from ..models.transcription import (
    TranscriptionFormat,
    TranscriptionRequest,
    TranscriptionResponse,
    TranscriptionSegment,
)
from ..services import TranscriptionService

router = APIRouter(prefix="/v1/audio", tags=["transcription"])


def _srt_timestamp(seconds: float) -> str:
    ms = int(round(max(0.0, seconds) * 1000))
    hours, rem = divmod(ms, 3_600_000)
    minutes, rem = divmod(rem, 60_000)
    secs, millis = divmod(rem, 1000)
    return f"{hours:02d}:{minutes:02d}:{secs:02d},{millis:03d}"


def _vtt_timestamp(seconds: float) -> str:
    return _srt_timestamp(seconds).replace(",", ".")


def _render_subtitles(result: TranscriptionResponse, fmt: TranscriptionFormat) -> str:
    """Render segments as SRT/VTT, falling back to one cue for the whole clip."""
    segments = result.segments or [TranscriptionSegment(id=0, start=0.0, end=result.duration, text=result.text)]
    lines: list[str] = []
    if fmt is TranscriptionFormat.VTT:
        lines.append("WEBVTT")
        lines.append("")
        stamp = _vtt_timestamp
        for index, segment in enumerate(segments, start=1):
            lines.append(str(index))
            lines.append(f"{stamp(segment.start)} --> {stamp(segment.end)}")
            lines.append(segment.text.strip())
            lines.append("")
    else:
        stamp = _srt_timestamp
        for index, segment in enumerate(segments, start=1):
            lines.append(str(index))
            lines.append(f"{stamp(segment.start)} --> {stamp(segment.end)}")
            lines.append(segment.text.strip())
            lines.append("")
    return "\n".join(lines)


@router.post(
    "/transcriptions",
    response_model=TranscriptionResponse,
    responses={
        200: {
            "description": "JSON, plain text or subtitles, depending on `response_format`",
            "content": {
                "application/json": {"schema": {"$ref": "#/components/schemas/TranscriptionResponse"}},
                "text/plain": {"schema": {"type": "string"}},
                "text/vtt": {"schema": {"type": "string"}},
            },
        }
    },
    summary="Transcribe audio",
    description="Transcribe audio file to text using specified model",
)
async def create_transcription(
    file: Annotated[UploadFile, File(description="Audio file to transcribe")],
    model: Annotated[str, Form(description="Model ID")] = vocal_settings.STT_DEFAULT_MODEL,
    language: Annotated[str | None, Form(description="Language code")] = None,
    prompt: Annotated[str | None, Form(description="Style prompt")] = None,
    response_format: Annotated[TranscriptionFormat, Form(description="Output format")] = TranscriptionFormat.JSON,
    temperature: Annotated[float, Form(ge=0.0, le=1.0)] = 0.0,
    service: TranscriptionService = Depends(get_transcription_service),
) -> Response:
    """
    Transcribe an audio file.

    **Supported formats:** mp3, mp4, wav, m4a, flac, ogg, webm
    **Max file size:** 25MB

    `response_format=text` returns `text/plain`, `srt`/`vtt` return subtitles,
    and `json`/`verbose_json` return the JSON schema (OpenAI-compatible).
    """
    file.file.seek(0, 2)
    size = file.file.tell()
    file.file.seek(0)

    if size > settings.MAX_UPLOAD_SIZE:
        raise HTTPException(400, f"File too large. Max {settings.MAX_UPLOAD_SIZE // (1024 * 1024)}MB.")

    request = TranscriptionRequest(
        model=model,
        language=language,
        prompt=prompt,
        response_format=response_format,
        temperature=temperature,
    )

    try:
        result = await service.transcribe(file, request)
        if response_format is TranscriptionFormat.TEXT:
            return PlainTextResponse(result.text, media_type="text/plain; charset=utf-8")
        if response_format in (TranscriptionFormat.SRT, TranscriptionFormat.VTT):
            media_type = "text/vtt; charset=utf-8" if response_format is TranscriptionFormat.VTT else "text/plain; charset=utf-8"
            return Response(_render_subtitles(result, response_format), media_type=media_type)
        return result
    except ValueError as e:
        raise HTTPException(400, str(e))
    except Exception as e:
        raise HTTPException(500, f"Transcription failed: {str(e)}")


@router.post(
    "/translations",
    response_model=TranscriptionResponse,
    summary="Translate audio to English",
    description="Translate audio to English text",
)
async def create_translation(
    file: Annotated[UploadFile, File()],
    model: Annotated[str, Form()] = vocal_settings.STT_DEFAULT_MODEL,
    service: TranscriptionService = Depends(get_transcription_service),
) -> TranscriptionResponse:
    """Translate audio to English."""
    try:
        return await service.translate(file, model)
    except ValueError as e:
        raise HTTPException(400, str(e))
    except Exception as e:
        raise HTTPException(500, f"Translation failed: {str(e)}")
