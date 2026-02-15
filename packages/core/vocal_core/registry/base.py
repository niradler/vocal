from collections.abc import AsyncIterator
from pathlib import Path

from .metadata_cache import ModelMetadataCache
from .model_info import ModelBackend, ModelInfo, ModelProvider, ModelStatus, ModelTask, format_bytes
from .providers.base import ModelProvider as BaseModelProvider
from .providers.huggingface import HuggingFaceProvider


class ModelRegistry:
    def __init__(self, storage_path: Path | None = None):
        self.storage_path = storage_path or Path.home() / ".cache" / "vocal" / "models"
        self.storage_path.mkdir(parents=True, exist_ok=True)

        metadata_cache_dir = self.storage_path.parent / "metadata"
        self.metadata_cache = ModelMetadataCache(metadata_cache_dir)

        self.providers: dict[str, BaseModelProvider] = {
            "huggingface": HuggingFaceProvider(cache_dir=self.storage_path / "hf"),
        }

        self._local_models: dict[str, ModelInfo] = {}

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
                model = ModelInfo(
                    id=model_id,
                    name=cached_metadata.get("name", model_id.split("/")[-1]),
                    provider=ModelProvider(cached_metadata.get("provider", "huggingface")),
                    description=cached_metadata.get("description"),
                    size=cached_metadata.get("size", 0),
                    size_readable=cached_metadata.get("size_readable", "Unknown"),
                    parameters=cached_metadata.get("parameters", "Unknown"),
                    languages=cached_metadata.get("languages", []),
                    backend=ModelBackend(cached_metadata.get("backend", "transformers")),
                    status=ModelStatus.AVAILABLE,
                    source_url=cached_metadata.get("source_url"),
                    license=cached_metadata.get("license"),
                    recommended_vram=cached_metadata.get("recommended_vram"),
                    task=ModelTask(cached_metadata.get("task", "stt")),
                    local_path=str(model_dir),
                    modified_at=cached_metadata.get("modified_at"),
                    downloaded_at=cached_metadata.get("downloaded_at"),
                )
            else:
                total_size = sum(f.stat().st_size for f in model_dir.rglob("*") if f.is_file())
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
                            model.size = cached_metadata.get("size", model.size)
                            model.size_readable = cached_metadata.get("size_readable", model.size_readable)
                            if actual_params := cached_metadata.get("actual_parameter_count"):
                                model.parameters = f"{actual_params:,}"

                    return model
            except Exception as e:
                print(f"Error getting model {model_id} from {provider.get_provider_name()}: {e}")

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
            print(f"Download error: {e}")
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
            print(f"Error deleting model {model_id}: {e}")
            return False

    def _get_model_path(self, model_id: str) -> Path:
        """Get local storage path for a model"""
        safe_id = model_id.replace("/", "--")
        return self.storage_path / safe_id

    def get_model_path(self, model_id: str) -> Path | None:
        """Get path to downloaded model, or None if not downloaded"""
        path = self._get_model_path(model_id)
        return path if path.exists() else None
