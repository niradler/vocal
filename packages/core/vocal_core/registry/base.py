import logging
from collections.abc import AsyncIterator
from pathlib import Path

from pydantic import ValidationError

from .capabilities import infer_model_capabilities, model_record_from_mapping
from .metadata_cache import ModelMetadataCache
from .model_info import ModelBackend, ModelInfo, ModelProvider, ModelStatus, ModelTask, format_bytes
from .providers.base import ModelProvider as BaseModelProvider
from .providers.huggingface import HuggingFaceProvider

logger = logging.getLogger(__name__)


class ModelRegistry:
    def __init__(self, storage_path: Path | None = None):
        self.storage_path = storage_path or Path.home() / ".cache" / "vocal" / "models"
        self.storage_path.mkdir(parents=True, exist_ok=True)

        metadata_cache_dir = self.storage_path.parent / "metadata"
        self.metadata_cache = ModelMetadataCache(metadata_cache_dir)

        self.providers: dict[str, BaseModelProvider] = {
            "huggingface": HuggingFaceProvider(cache_dir=self.storage_path / "hf"),
        }

    def add_provider(self, name: str, provider: BaseModelProvider) -> None:
        """Add a custom model provider"""
        self.providers[name] = provider

    async def list_models(
        self,
        provider: str | None = None,
        task: str | None = None,
        status_filter: str | None = None,
    ) -> list[ModelInfo]:
        all_models = []

        for model_dir in self.storage_path.iterdir():
            if not model_dir.is_dir() or model_dir.name == "hf":
                continue

            model_id = model_dir.name.replace("--", "/")

            cached_metadata = self.metadata_cache.get(model_id)
            if cached_metadata:
                try:
                    record = model_record_from_mapping(
                        cached_metadata,
                        default_id=model_id,
                        default_name=model_id.split("/")[-1],
                        default_provider="huggingface",
                        default_task="stt",
                        default_backend="transformers",
                    )
                    capabilities = infer_model_capabilities(
                        task=record.task,
                        backend=record.backend,
                        model_id=record.id,
                        tags=record.tags,
                        overrides=record,
                    )
                    model = ModelInfo(
                        id=record.id,
                        name=record.name,
                        provider=ModelProvider(record.provider),
                        description=record.description,
                        size=record.size,
                        size_readable=record.size_readable,
                        parameters=record.parameters,
                        languages=record.languages,
                        backend=ModelBackend(record.backend),
                        status=ModelStatus.AVAILABLE,
                        source_url=record.source_url,
                        license=record.license,
                        recommended_vram=record.recommended_vram,
                        task=ModelTask(record.task),
                        local_path=str(model_dir),
                        modified_at=record.modified_at,
                        downloaded_at=record.downloaded_at,
                        author=record.author,
                        tags=record.tags,
                        downloads=record.downloads,
                        likes=record.likes,
                        sha=record.sha,
                        files=[file.model_dump() for file in record.files] if record.files else None,
                        **capabilities,
                    )
                except (ValueError, ValidationError):
                    total_size = sum(f.stat().st_size for f in model_dir.rglob("*") if f.is_file())
                    capabilities = infer_model_capabilities(
                        task="stt",
                        backend="transformers",
                        model_id=model_id,
                    )
                    model = ModelInfo(
                        id=model_id,
                        name=model_id.split("/")[-1],
                        provider=ModelProvider.HUGGINGFACE,
                        size=total_size,
                        size_readable=format_bytes(total_size),
                        parameters="Unknown",
                        languages=[],
                        backend=ModelBackend.TRANSFORMERS,
                        status=ModelStatus.AVAILABLE,
                        task=ModelTask.STT,
                        local_path=str(model_dir),
                        **capabilities,
                    )
            else:
                total_size = sum(f.stat().st_size for f in model_dir.rglob("*") if f.is_file())
                capabilities = infer_model_capabilities(
                    task="stt",
                    backend="transformers",
                    model_id=model_id,
                )
                model = ModelInfo(
                    id=model_id,
                    name=model_id.split("/")[-1],
                    provider=ModelProvider.HUGGINGFACE,
                    size=total_size,
                    size_readable=format_bytes(total_size),
                    parameters="Unknown",
                    languages=[],
                    backend=ModelBackend.TRANSFORMERS,
                    status=ModelStatus.AVAILABLE,
                    task=ModelTask.STT,
                    local_path=str(model_dir),
                    **capabilities,
                )

            if task and model.task.value != task:
                continue

            all_models.append(model)

        if status_filter and status_filter != "available":
            all_models = []

        return all_models

    async def get_model(self, model_id: str) -> ModelInfo | None:
        for provider in self.providers.values():
            try:
                model = await provider.get_model_info(model_id)
                if model:
                    model_path = self._get_model_path(model_id)
                    if model_path.exists():
                        model.status = ModelStatus.AVAILABLE
                        model.local_path = str(model_path)

                        cached_metadata = self.metadata_cache.get(model_id)
                        if cached_metadata:
                            try:
                                record = model_record_from_mapping(
                                    cached_metadata,
                                    default_id=model.id,
                                    default_name=model.name,
                                    default_provider=model.provider.value,
                                    default_task=model.task.value,
                                    default_backend=model.backend.value,
                                )
                                model.size = record.size
                                model.size_readable = record.size_readable
                                model.parameters = record.parameters
                                model.modified_at = record.modified_at
                                model.downloaded_at = record.downloaded_at
                                model.author = record.author
                                model.tags = record.tags
                                model.downloads = record.downloads
                                model.likes = record.likes
                                model.sha = record.sha
                                model.files = [file.model_dump() for file in record.files] if record.files else None
                                model.supports_streaming = record.supports_streaming or model.supports_streaming
                                model.supports_voice_list = record.supports_voice_list or model.supports_voice_list
                                model.supports_voice_clone = record.supports_voice_clone or model.supports_voice_clone
                                model.supports_voice_design = record.supports_voice_design or model.supports_voice_design
                                model.requires_gpu = record.requires_gpu or model.requires_gpu
                                model.voice_mode = record.voice_mode or model.voice_mode
                                model.clone_mode = record.clone_mode or model.clone_mode
                                model.reference_audio_min_seconds = record.reference_audio_min_seconds or model.reference_audio_min_seconds
                                model.reference_audio_max_seconds = record.reference_audio_max_seconds or model.reference_audio_max_seconds
                            except (ValueError, ValidationError):
                                pass

                    return model
            except Exception as e:
                logger.error("Error getting model %s from %s: %s", model_id, provider.get_provider_name(), e)

        return None

    async def download_model(
        self,
        model_id: str,
        provider_name: str = "huggingface",
        quantization: str | None = None,
    ) -> AsyncIterator[tuple[int, int, ModelStatus]]:
        if provider_name not in self.providers:
            raise ValueError(f"Unknown provider: {provider_name}")

        provider = self.providers[provider_name]
        destination = self._get_model_path(model_id)

        try:
            yield (0, 0, ModelStatus.DOWNLOADING)

            async for downloaded, total in provider.download_model(model_id, destination, quantization):
                yield (downloaded, total, ModelStatus.DOWNLOADING)

            is_valid = await provider.verify_model(model_id, destination)

            if is_valid:
                if hasattr(provider, "fetch_metadata_from_hf"):
                    metadata = await provider.fetch_metadata_from_hf(model_id)
                    if metadata:
                        metadata["local_path"] = str(destination)
                        self.metadata_cache.set(model_id, metadata)

                yield (total, total, ModelStatus.AVAILABLE)
            else:
                yield (0, 0, ModelStatus.ERROR)

        except Exception as e:
            logger.error("Download error for model %s: %s", model_id, e)
            yield (0, 0, ModelStatus.ERROR)

    async def delete_model(self, model_id: str) -> bool:
        model_path = self._get_model_path(model_id)

        if not model_path.exists():
            return False

        try:
            import shutil

            shutil.rmtree(model_path)
            self.metadata_cache.delete(model_id)
            return True
        except Exception as e:
            logger.error("Error deleting model %s: %s", model_id, e)
            return False

    def _get_model_path(self, model_id: str) -> Path:
        """Get local storage path for a model"""
        safe_id = model_id.replace("/", "--")
        return self.storage_path / safe_id

    def get_model_path(self, model_id: str) -> Path | None:
        """Get path to downloaded model, or None if not downloaded"""
        path = self._get_model_path(model_id)
        return path if path.exists() else None
