from fastapi import APIRouter, Depends, HTTPException, BackgroundTasks
from typing import Optional

from ..models.model import (
    ModelInfo,
    ModelListResponse,
    ModelDownloadRequest,
    ModelDownloadProgress,
)
from ..services import ModelService
from ..dependencies import get_model_service

router = APIRouter(prefix="/v1/models", tags=["models"])


@router.get(
    "",
    response_model=ModelListResponse,
    summary="List models",
    description="List all available models (Ollama-style)"
)
async def list_models(
    status: Optional[str] = None,
    task: Optional[str] = None,
    service: ModelService = Depends(get_model_service)
) -> ModelListResponse:
    """
    List all available models
    
    Query params:
    - status: Filter by status (available, downloading, not_downloaded)
    - task: Filter by task (stt, tts)
    """
    models = await service.list_models(status_filter=status, task=task)
    return ModelListResponse(models=models, total=len(models))


@router.get(
    "/{model_id:path}",
    response_model=ModelInfo,
    summary="Get model info",
    description="Get detailed information about a specific model"
)
async def get_model(
    model_id: str,
    service: ModelService = Depends(get_model_service)
) -> ModelInfo:
    """Get detailed model information"""
    model = await service.get_model(model_id)
    if not model:
        raise HTTPException(404, f"Model {model_id} not found")
    return model


@router.post(
    "/{model_id:path}/download",
    response_model=ModelDownloadProgress,
    summary="Download model",
    description="Download a model for local use (Ollama-style pull)"
)
async def download_model(
    model_id: str,
    background_tasks: BackgroundTasks,
    service: ModelService = Depends(get_model_service)
) -> ModelDownloadProgress:
    """
    Start downloading a model
    
    Returns immediately with initial status.
    Check progress with GET /models/{model_id}/download/status
    """
    model = await service.get_model(model_id)
    if not model:
        raise HTTPException(404, f"Model {model_id} not found")
    
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
        message="Starting download..."
    )


@router.get(
    "/{model_id:path}/download/status",
    response_model=ModelDownloadProgress,
    summary="Get download status"
)
async def get_download_status(
    model_id: str,
    service: ModelService = Depends(get_model_service)
) -> ModelDownloadProgress:
    """Check model download progress"""
    status = await service.get_download_status(model_id)
    if not status:
        model = await service.get_model(model_id)
        if not model:
            raise HTTPException(404, f"Model {model_id} not found")
        
        if model.status == "available":
            return ModelDownloadProgress(
                model_id=model_id,
                status="available",
                progress=1.0,
                downloaded_bytes=model.size,
                total_bytes=model.size,
                message="Model already downloaded"
            )
        
        raise HTTPException(404, "No active download for this model")
    
    return status


@router.delete(
    "/{model_id:path}",
    summary="Delete model",
    description="Remove a downloaded model"
)
async def delete_model(
    model_id: str,
    service: ModelService = Depends(get_model_service)
):
    """Delete a downloaded model"""
    success = await service.delete_model(model_id)
    if not success:
        raise HTTPException(404, f"Model {model_id} not found or not downloaded")
    
    return {"status": "deleted", "model_id": model_id}
