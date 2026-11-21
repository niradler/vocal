"""Unit tests: registry get_model size reporting (issue #19)."""

import pytest

from vocal_core.registry.base import ModelRegistry
from vocal_core.registry.model_info import ModelBackend, ModelInfo, ModelProvider, ModelStatus, ModelTask


class _StubProvider:
    """Returns a catalog-style record with size 0, like stale HF metadata."""

    def get_provider_name(self):
        return "stub"

    async def get_model_info(self, model_id):
        if model_id != "org/test-model":
            return None
        return ModelInfo(
            id=model_id,
            name="Test Model",
            provider=ModelProvider.HUGGINGFACE,
            size=0,
            size_readable="Unknown",
            backend=ModelBackend.TRANSFORMERS,
            status=ModelStatus.NOT_DOWNLOADED,
            task=ModelTask.STT,
        )


@pytest.mark.asyncio
async def test_get_model_fills_size_from_disk(tmp_path):
    storage = tmp_path / "models"
    model_dir = storage / "org--test-model"
    model_dir.mkdir(parents=True)
    (model_dir / "model.safetensors").write_bytes(b"\x00" * 4096)
    (model_dir / "config.json").write_text("{}", encoding="utf-8")

    registry = ModelRegistry(storage_path=storage)
    registry.providers = {"stub": _StubProvider()}

    model = await registry.get_model("org/test-model")

    assert model is not None
    assert model.status == ModelStatus.AVAILABLE
    assert model.size == 4096 + 2  # weights + config, derived from disk
    assert model.size_readable != "Unknown"


@pytest.mark.asyncio
async def test_get_model_keeps_known_catalog_size(tmp_path):
    storage = tmp_path / "models"
    model_dir = storage / "org--test-model"
    model_dir.mkdir(parents=True)
    (model_dir / "model.safetensors").write_bytes(b"\x00" * 4096)

    registry = ModelRegistry(storage_path=storage)
    registry.providers = {"stub": _StubProvider()}
    registry.metadata_cache.set(
        "org/test-model",
        {
            "id": "org/test-model",
            "name": "Test Model",
            "provider": "huggingface",
            "task": "stt",
            "backend": "transformers",
            "size": 123456,
            "size_readable": "120.6 KB",
        },
    )

    model = await registry.get_model("org/test-model")

    assert model.size == 123456  # trusted metadata wins over disk scan
    assert model.size_readable == "120.6 KB"
