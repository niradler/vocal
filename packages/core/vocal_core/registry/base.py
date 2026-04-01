import logging
import os
from collections.abc import AsyncIterator
from pathlib import Path

from pydantic import ValidationError

from .capabilities import infer_model_capabilities, model_record_from_mapping
from .metadata_cache import ModelMetadataCache
from .model_info import ModelBackend, ModelInfo, ModelProvider, ModelStatus, ModelTask, format_bytes
from .providers.base import WEIGHT_NAMES, WEIGHT_SUFFIXES
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

    def _resolve_model_id(self, model_id: str) -> str:
        """Resolve alias to canonical model ID using any registered provider."""
        hf = self.providers.get("huggingface")
        if hf and hasattr(hf, "resolve_alias"):
            return hf.resolve_alias(model_id)
        return model_id

    def _enrich_from_cache(self, model: ModelInfo, canonical_id: str, dir_model_id: str) -> None:
        cached = self.metadata_cache.get(canonical_id) or self.metadata_cache.get(dir_model_id)
        if not cached:
            return
        try:
            record = model_record_from_mapping(
                cached,
                default_id=canonical_id,
                default_name=model.name,
                default_provider=model.provider.value,
                default_task=model.task.value,
                default_backend=model.backend.value,
            )
            if record.size:
                model.size = record.size
                model.size_readable = record.size_readable
            if record.parameters and record.parameters != "Unknown":
                model.parameters = record.parameters
            if record.languages:
                model.languages = record.languages
            if record.description:
                model.description = record.description
            if record.author:
                model.author = record.author
            if record.license:
                model.license = record.license
            if record.tags:
                model.tags = record.tags
            model.downloaded_at = record.downloaded_at or model.downloaded_at
            model.modified_at = record.modified_at or model.modified_at
        except (ValueError, ValidationError):
            pass

    def _fill_local_size(self, model: ModelInfo, model_dir: Path) -> None:
        if not model.size:
            model.size = sum(f.stat().st_size for f in model_dir.rglob("*") if f.is_file())
            model.size_readable = format_bytes(model.size)

    def _model_from_dir(self, model_dir: Path, canonical_id: str, dir_model_id: str) -> ModelInfo:
        total_size = sum(f.stat().st_size for f in model_dir.rglob("*") if f.is_file())
        cached = self.metadata_cache.get(canonical_id) or self.metadata_cache.get(dir_model_id)
        if cached:
            try:
                record = model_record_from_mapping(
                    cached,
                    default_id=canonical_id,
                    default_name=canonical_id.split("/")[-1],
                    default_provider="huggingface",
                    default_task="stt",
                    default_backend="transformers",
                )
                caps = infer_model_capabilities(task=record.task, backend=record.backend, model_id=record.id, tags=record.tags, overrides=record)
                return ModelInfo(
                    id=record.id,
                    name=record.name,
                    provider=ModelProvider(record.provider),
                    description=record.description,
                    size=record.size or total_size,
                    size_readable=record.size_readable or format_bytes(total_size),
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
                    files=[f.model_dump() for f in record.files] if record.files else None,
                    **caps,
                )
            except (ValueError, ValidationError):
                pass
        caps = infer_model_capabilities(task="stt", backend="transformers", model_id=canonical_id)
        return ModelInfo(
            id=canonical_id,
            name=canonical_id.split("/")[-1],
            provider=ModelProvider.HUGGINGFACE,
            size=total_size,
            size_readable=format_bytes(total_size),
            parameters="Unknown",
            languages=[],
            backend=ModelBackend.TRANSFORMERS,
            status=ModelStatus.AVAILABLE,
            task=ModelTask.STT,
            local_path=str(model_dir),
            **caps,
        )

    async def list_models(
        self,
        provider: str | None = None,
        task: str | None = None,
        status_filter: str | None = None,
    ) -> list[ModelInfo]:
        if status_filter and status_filter != "available":
            return []

        hf_provider = self.providers.get("huggingface")
        all_models: list[ModelInfo] = []
        seen_canonical_ids: set[str] = set()

        local_dirs = [d for d in self.storage_path.iterdir() if d.is_dir() and d.name != "hf"]

        for model_dir in local_dirs:
            dir_model_id = model_dir.name.replace("--", "/")
            canonical_id = self._resolve_model_id(dir_model_id)

            if canonical_id in seen_canonical_ids:
                continue

            if canonical_id != dir_model_id:
                canonical_dir = self.storage_path / canonical_id.replace("/", "--")
                if canonical_dir.exists():
                    continue

            seen_canonical_ids.add(canonical_id)

            model: ModelInfo | None = None
            if hf_provider:
                try:
                    model = await hf_provider.get_model_info(canonical_id)
                except Exception:
                    model = None

            if not self._has_model_weights(model_dir):
                continue

            if model:
                model.status = ModelStatus.AVAILABLE
                model.local_path = str(model_dir)
                self._enrich_from_cache(model, canonical_id, dir_model_id)
                self._fill_local_size(model, model_dir)
            else:
                model = self._model_from_dir(model_dir, canonical_id, dir_model_id)

            if task and model.task.value != task:
                continue

            all_models.append(model)

        return all_models

    async def get_model(self, model_id: str) -> ModelInfo | None:
        canonical_id = self._resolve_model_id(model_id)

        for provider in self.providers.values():
            try:
                model = await provider.get_model_info(canonical_id)
                if model:
                    model_path = self._get_model_path(model.id)
                    if model_path.exists() and self._has_model_weights(model_path):
                        model.status = ModelStatus.AVAILABLE
                        model.local_path = str(model_path)

                        cached_metadata = self.metadata_cache.get(model.id)
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

        model_path = self._get_model_path(canonical_id)
        if model_path.exists():
            return self._model_from_dir(model_path, canonical_id, model_id)

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
        canonical_id = self._resolve_model_id(model_id)
        destination = self._get_model_path(canonical_id)

        try:
            async for downloaded, total in provider.download_model(model_id, destination, quantization):
                yield (downloaded, total, ModelStatus.DOWNLOADING)

            is_valid = await provider.verify_model(model_id, destination)

            if is_valid:
                if hasattr(provider, "fetch_metadata_from_hf"):
                    metadata = await provider.fetch_metadata_from_hf(canonical_id)
                    if metadata:
                        metadata["local_path"] = str(destination)
                        self.metadata_cache.set(canonical_id, metadata)

                total_size = sum(f.stat().st_size for f in destination.rglob("*") if f.is_file())
                yield (total_size, total_size, ModelStatus.AVAILABLE)
            else:
                yield (0, 0, ModelStatus.ERROR)

        except Exception as e:
            logger.error("Download error for model %s: %s", model_id, e)
            yield (0, 0, ModelStatus.ERROR)

    async def delete_model(self, model_id: str) -> bool:
        canonical_id = self._resolve_model_id(model_id)
        model_path = self._get_model_path(canonical_id)

        if not model_path.exists():
            return False

        try:
            import shutil

            shutil.rmtree(model_path)
            self.metadata_cache.delete(canonical_id)
            return True
        except Exception as e:
            logger.error("Error deleting model %s: %s", model_id, e)
            return False

    def _get_model_path(self, model_id: str) -> Path:
        safe_id = model_id.replace("/", "--")
        return self.storage_path / safe_id

    @staticmethod
    def _has_model_weights(path: Path) -> bool:
        """Return True if path contains actual model weight files (not just configs)."""
        for _root, _dirs, files in os.walk(path):
            for name in files:
                if name in WEIGHT_NAMES or Path(name).suffix in WEIGHT_SUFFIXES:
                    return True
        return False

    def get_model_path(self, model_id: str) -> Path | None:
        """Get path to downloaded model, or None if not downloaded or weights missing"""
        canonical_id = self._resolve_model_id(model_id)
        path = self._get_model_path(canonical_id)
        if not path.exists():
            return None
        return path if self._has_model_weights(path) else None
