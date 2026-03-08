import json
from collections.abc import AsyncIterator
from pathlib import Path

from vocal_core import ModelRegistry
from vocal_core.registry.capabilities import (
    infer_model_capabilities,
    supported_model_records_from_mapping,
)

from ..models.model import (
    ModelDownloadProgress,
    ModelInfo,
)


class ModelService:
    def __init__(self, registry: ModelRegistry):
        self.registry = registry
        self._download_status: dict[str, ModelDownloadProgress] = {}
        self._supported_models: list[ModelInfo] | None = None

    def _load_supported_models_json(self) -> list:
        supported_path = Path(__file__).parent.parent.parent.parent / "core" / "vocal_core" / "registry" / "supported_models.json"

        if not supported_path.exists():
            return []

        try:
            with open(supported_path, encoding="utf-8") as f:
                return supported_model_records_from_mapping(json.load(f))
        except Exception as e:
            print(f"Error loading supported models: {e}")
            return []

    async def list_supported_models(self) -> list[ModelInfo]:
        models_data = self._load_supported_models_json()
        models = []

        for record in models_data:
            capabilities = infer_model_capabilities(
                task=record.task,
                backend=record.backend,
                model_id=record.id,
                tags=record.tags,
                overrides=record,
            )
            models.append(
                ModelInfo(
                    id=record.id,
                    name=record.name,
                    provider=record.provider,
                    description=record.description,
                    size=record.size,
                    size_readable=record.size_readable,
                    parameters=record.parameters,
                    languages=record.languages,
                    backend=record.backend,
                    status="not_downloaded",
                    source_url=record.source_url,
                    license=record.license,
                    recommended_vram=record.recommended_vram,
                    task=record.task,
                    modified_at=record.modified_at,
                    author=record.author,
                    tags=record.tags,
                    downloads=record.downloads,
                    likes=record.likes,
                    sha=record.sha,
                    files=[file.model_dump() for file in record.files] if record.files else None,
                    **capabilities,
                )
            )

        return models

    async def show_model(self, model_or_alias: str) -> ModelInfo | None:
        model = await self.registry.get_model(model_or_alias)
        if model:
            return self._convert_model_info(model)
        return None

    async def list_models(self, status_filter: str | None = None, task: str | None = None) -> list[ModelInfo]:
        """List all available models"""
        models = await self.registry.list_models(task=task, status_filter=status_filter)

        return [self._convert_model_info(m) for m in models]

    async def get_model(self, model_id: str) -> ModelInfo | None:
        """Get model information"""
        model = await self.registry.get_model(model_id)
        if not model:
            return None
        return self._convert_model_info(model)

    async def download_model(self, model_id: str, quantization: str | None = None) -> AsyncIterator[ModelDownloadProgress]:
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
            async for downloaded, total, status in self.registry.download_model(model_id, quantization=quantization):
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

    async def get_download_status(self, model_id: str) -> ModelDownloadProgress | None:
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
            modified_at=model.modified_at,
            downloaded_at=model.downloaded_at,
            author=model.author,
            tags=model.tags,
            downloads=model.downloads,
            likes=model.likes,
            sha=model.sha,
            files=model.files,
            supports_streaming=model.supports_streaming,
            supports_voice_list=model.supports_voice_list,
            supports_voice_clone=model.supports_voice_clone,
            supports_voice_design=model.supports_voice_design,
            requires_gpu=model.requires_gpu,
            voice_mode=model.voice_mode,
            clone_mode=model.clone_mode,
            reference_audio_min_seconds=model.reference_audio_min_seconds,
            reference_audio_max_seconds=model.reference_audio_max_seconds,
        )
