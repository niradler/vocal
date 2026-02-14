import pytest
from vocal_core import ModelRegistry


@pytest.mark.asyncio
async def test_model_registry_init():
    """Test that ModelRegistry initializes correctly"""
    registry = ModelRegistry()
    assert registry is not None
    assert registry.storage_path.exists()


@pytest.mark.asyncio
async def test_list_models():
    """Test listing models from HuggingFace provider"""
    registry = ModelRegistry()
    models = await registry.list_models(task="stt")

    assert len(models) > 0
    assert all(m.task.value == "stt" for m in models)

    whisper_models = [m for m in models if "whisper" in m.id.lower()]
    assert len(whisper_models) > 0


@pytest.mark.asyncio
async def test_get_model_info():
    """Test getting specific model info"""
    registry = ModelRegistry()
    model = await registry.get_model("openai/whisper-tiny")

    assert model is not None
    assert model.id == "openai/whisper-tiny"
    assert model.task.value == "stt"
    assert model.provider.value == "huggingface"


@pytest.mark.asyncio
async def test_model_registry_providers():
    """Test that registry has providers configured"""
    registry = ModelRegistry()
    assert "huggingface" in registry.providers
    assert registry.providers["huggingface"] is not None
