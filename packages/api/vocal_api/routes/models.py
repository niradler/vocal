import json

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException
from fastapi.responses import StreamingResponse

from ..dependencies import get_model_service
from ..models.model import (
    ModelDownloadProgress,
    ModelInfo,
    ModelListResponse,
    ModelPullRequest,
    ModelShowRequest,
)
from ..services import ModelService

router = APIRouter(prefix="/v1/models", tags=["models"])


@router.get(
    "",
    response_model=ModelListResponse,
    response_model_exclude_none=True,
    summary="List models",
    description="List downloaded models (Ollama-style)",
)
async def list_models(
    task: str | None = None,
    service: ModelService = Depends(get_model_service),
) -> ModelListResponse:
    models = await service.list_models(status_filter="available", task=task)
    return ModelListResponse(models=models, total=len(models))


@router.get(
    "/catalog",
    response_model=ModelListResponse,
    response_model_exclude_none=True,
    summary="List catalog models",
    description="List all curated models with metadata (downloaded or not)",
)
async def list_catalog(
    task: str | None = None,
    service: ModelService = Depends(get_model_service),
) -> ModelListResponse:
    models = await service.list_catalog(task=task)
    return ModelListResponse(models=models, total=len(models))


@router.get(
    "/{model_id:path}",
    response_model=ModelInfo,
    response_model_exclude_none=True,
    summary="Get model info",
    description="Get detailed information about a specific model",
)
async def get_model(model_id: str, service: ModelService = Depends(get_model_service)) -> ModelInfo:
    """Get detailed model information"""
    model = await service.get_model(model_id)
    if not model:
        raise HTTPException(404, f"Model {model_id} not found")
    return model


@router.post(
    "/{model_id:path}/download",
    response_model=ModelDownloadProgress,
    summary="Download model",
    description="Download a model for local use (Ollama-style pull)",
)
async def download_model(
    model_id: str,
    background_tasks: BackgroundTasks,
    service: ModelService = Depends(get_model_service),
) -> ModelDownloadProgress:
    """
    Start downloading a model

    Returns immediately with initial status.
    Check progress with GET /models/{model_id}/download/status
    """
    async def download_task():
        async for progress in service.download_model(model_id):
            pass

    background_tasks.add_task(download_task)

    return ModelDownloadProgress(
        model_id=model_id,
        status="downloading",
        progress=0.0,
        downloaded_bytes=0,
        total_bytes=0,
        message="Starting download...",
    )


@router.get(
    "/{model_id:path}/download/status",
    response_model=ModelDownloadProgress,
    summary="Get download status",
)
async def get_download_status(model_id: str, service: ModelService = Depends(get_model_service)) -> ModelDownloadProgress:
    """Check model download progress"""
    status = await service.get_download_status(model_id)
    if not status:
        model = await service.get_model(model_id)
        if not model:
            raise HTTPException(404, f"Model {model_id} not found")

        if str(model.status).lower() == "available":
            size = model.size or 0
            if size == 0 and model.local_path:
                from pathlib import Path
                size = sum(f.stat().st_size for f in Path(model.local_path).rglob("*") if f.is_file())
            return ModelDownloadProgress(
                model_id=model_id,
                status="available",
                progress=1.0,
                downloaded_bytes=size,
                total_bytes=size,
                message="Model already downloaded",
            )

        raise HTTPException(404, "No active download for this model")

    return status


@router.delete("/{model_id:path}", summary="Delete model", description="Remove a downloaded model")
async def delete_model(model_id: str, service: ModelService = Depends(get_model_service)):
    """Delete a downloaded model"""
    success = await service.delete_model(model_id)
    if not success:
        raise HTTPException(404, f"Model {model_id} not found or not downloaded")

    return {"status": "deleted", "model_id": model_id}


@router.post(
    "/show",
    response_model=ModelInfo,
    response_model_exclude_none=True,
    summary="Show model details",
    description="Get detailed model information (Ollama-style)",
)
async def show_model(
    request: ModelShowRequest,
    service: ModelService = Depends(get_model_service),
) -> ModelInfo:
    model = await service.show_model(request.model)
    if not model:
        raise HTTPException(404, f"Model {request.model} not found")
    return model


@router.post(
    "/pull",
    summary="Pull model",
    description="Stream download progress as newline-delimited JSON",
)
async def pull_model(
    request: ModelPullRequest,
    service: ModelService = Depends(get_model_service),
) -> StreamingResponse:
    async def _stream():
        async for progress in service.download_model(request.model):
            yield json.dumps(progress.model_dump()) + "\n"

    return StreamingResponse(_stream(), media_type="application/x-ndjson")
