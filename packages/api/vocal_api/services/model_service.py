from typing import Optional, AsyncIterator
from vocal_core import ModelRegistry

from ..models.model import (
    ModelInfo,
    ModelDownloadProgress,
)


class ModelService:
    """Service for managing models"""

    def __init__(self, registry: ModelRegistry):
        self.registry = registry
        self._download_status: dict[str, ModelDownloadProgress] = {}

    async def list_models(
        self, status_filter: Optional[str] = None, task: Optional[str] = None
    ) -> list[ModelInfo]:
        """List all available models"""
        models = await self.registry.list_models(task=task, status_filter=status_filter)

        return [self._convert_model_info(m) for m in models]

    async def get_model(self, model_id: str) -> Optional[ModelInfo]:
        """Get model information"""
        model = await self.registry.get_model(model_id)
        if not model:
            return None
        return self._convert_model_info(model)

    async def download_model(
        self, model_id: str, quantization: Optional[str] = None
    ) -> AsyncIterator[ModelDownloadProgress]:
        """Download a model"""
        self._download_status[model_id] = ModelDownloadProgress(
            model_id=model_id,
            status="downloading",
            progress=0.0,
            downloaded_bytes=0,
            total_bytes=0,
            message="Starting download...",
        )

        try:
            async for downloaded, total, status in self.registry.download_model(
                model_id, quantization=quantization
            ):
                progress = (downloaded / total) if total > 0 else 0.0

                self._download_status[model_id] = ModelDownloadProgress(
                    model_id=model_id,
                    status=status.value,
                    progress=progress,
                    downloaded_bytes=downloaded,
                    total_bytes=total,
                    message=f"Downloaded {downloaded}/{total} bytes",
                )

                yield self._download_status[model_id]

        except Exception as e:
            self._download_status[model_id] = ModelDownloadProgress(
                model_id=model_id,
                status="error",
                progress=0.0,
                downloaded_bytes=0,
                total_bytes=0,
                message=f"Download failed: {str(e)}",
            )
            yield self._download_status[model_id]

    async def get_download_status(
        self, model_id: str
    ) -> Optional[ModelDownloadProgress]:
        """Get download status for a model"""
        return self._download_status.get(model_id)

    async def delete_model(self, model_id: str) -> bool:
        """Delete a downloaded model"""
        return await self.registry.delete_model(model_id)

    def _convert_model_info(self, model) -> ModelInfo:
        """Convert core ModelInfo to API ModelInfo"""
        return ModelInfo(
            id=model.id,
            name=model.name,
            provider=model.provider.value,
            description=model.description,
            size=model.size,
            size_readable=model.size_readable,
            parameters=model.parameters,
            languages=model.languages,
            backend=model.backend.value,
            status=model.status.value,
            source_url=model.source_url,
            license=model.license,
            recommended_vram=model.recommended_vram,
            task=model.task.value,
            local_path=model.local_path,
            created_at=model.created_at,
            updated_at=model.updated_at,
        )
