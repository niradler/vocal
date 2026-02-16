import json
from collections.abc import AsyncIterator
from pathlib import Path

from vocal_core import ModelRegistry

from ..models.model import (
    ModelDownloadProgress,
    ModelInfo,
)


class ModelService:
    def __init__(self, registry: ModelRegistry):
        self.registry = registry
        self._download_status: dict[str, ModelDownloadProgress] = {}
        self._supported_models: list[ModelInfo] | None = None

    def _load_supported_models_json(self) -> list[dict]:
        supported_path = Path(__file__).parent.parent.parent.parent / "core" / "vocal_core" / "registry" / "supported_models.json"

        if not supported_path.exists():
            return []

        try:
            with open(supported_path) as f:
                data = json.load(f)
            return data.get("models", [])
        except Exception as e:
            print(f"Error loading supported models: {e}")
            return []

    async def list_supported_models(self) -> list[ModelInfo]:
        models_data = self._load_supported_models_json()
        models = []

        for model_dict in models_data:
            models.append(
                ModelInfo(
                    id=model_dict["id"],
                    name=model_dict["name"],
                    provider=model_dict.get("provider", "huggingface"),
                    description=model_dict.get("description"),
                    size=model_dict.get("size", 0),
                    size_readable=model_dict.get("size_readable", "Unknown"),
                    parameters=model_dict.get("parameters", "Unknown"),
                    languages=model_dict.get("languages", []),
                    backend=model_dict.get("backend", "transformers"),
                    status="not_downloaded",
                    source_url=model_dict.get("source_url"),
                    license=model_dict.get("license"),
                    recommended_vram=model_dict.get("recommended_vram"),
                    task=model_dict.get("task", "stt"),
                    modified_at=model_dict.get("modified_at"),
                    author=model_dict.get("author"),
                    tags=model_dict.get("tags", []),
                    downloads=model_dict.get("downloads"),
                    likes=model_dict.get("likes"),
                    sha=model_dict.get("sha"),
                    files=model_dict.get("files"),
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
        )
