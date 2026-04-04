import pytest

from vocal_core.adapters.tts import (
    CHATTERBOX_AVAILABLE,
    ChatterboxTTSAdapter,
    FasterQwen3TTSAdapter,
    KokoroTTSAdapter,
    OmniVoiceTTSAdapter,
    PiperTTSAdapter,
    SimpleTTSAdapter,
)


def test_simple_tts_capabilities():
    capabilities = SimpleTTSAdapter().get_capabilities()
    assert capabilities.supports_voice_list is True
    assert capabilities.supports_voice_clone is False
    assert capabilities.voice_mode == "voice_id"


def test_kokoro_capabilities():
    capabilities = KokoroTTSAdapter().get_capabilities()
    assert capabilities.supports_streaming is True
    assert capabilities.supports_voice_list is True
    assert capabilities.supports_voice_clone is False


def test_piper_capabilities():
    capabilities = PiperTTSAdapter().get_capabilities()
    assert capabilities.supports_voice_list is True
    assert capabilities.supports_voice_clone is False


def test_qwen_base_clone_capabilities():
    adapter = FasterQwen3TTSAdapter()
    adapter._variant = "base"
    capabilities = adapter.get_capabilities()
    assert capabilities.supports_voice_clone is True
    assert capabilities.clone_mode == "reference_audio"
    assert capabilities.requires_gpu is True


def test_qwen_custom_voice_capabilities():
    adapter = FasterQwen3TTSAdapter()
    adapter._variant = "custom_voice"
    capabilities = adapter.get_capabilities()
    assert capabilities.supports_voice_list is True
    assert capabilities.supports_voice_clone is False
    assert capabilities.voice_mode == "voice_id"


def test_qwen_voice_design_capabilities():
    adapter = FasterQwen3TTSAdapter()
    adapter._variant = "voice_design"
    capabilities = adapter.get_capabilities()
    assert capabilities.supports_voice_design is True
    assert capabilities.supports_voice_clone is False
    assert capabilities.voice_mode == "instruction"


def test_chatterbox_availability_flag_is_bool():
    assert isinstance(CHATTERBOX_AVAILABLE, bool)


def test_chatterbox_capabilities():
    adapter = ChatterboxTTSAdapter()
    capabilities = adapter.get_capabilities()
    assert capabilities.supports_voice_clone is True
    assert capabilities.clone_mode == "reference_audio"
    assert capabilities.reference_audio_min_seconds == 3.0
    assert capabilities.reference_audio_max_seconds == 30.0
    assert capabilities.supports_voice_list is False
    assert capabilities.supports_voice_design is False


def test_chatterbox_not_loaded_initially():
    adapter = ChatterboxTTSAdapter()
    assert adapter.is_loaded() is False


@pytest.mark.asyncio
async def test_chatterbox_synthesize_raises_when_not_loaded():
    adapter = ChatterboxTTSAdapter()
    with pytest.raises(RuntimeError, match="not loaded"):
        await adapter.synthesize("hello")


def test_omnivoice_capabilities():
    adapter = OmniVoiceTTSAdapter()
    capabilities = adapter.get_capabilities()
    assert capabilities.supports_voice_clone is True
    assert capabilities.supports_voice_design is True
    assert capabilities.clone_mode == "reference_audio"
    assert capabilities.voice_mode == "instruction"
    assert capabilities.requires_gpu is True
    assert capabilities.reference_audio_min_seconds == 3.0
    assert capabilities.reference_audio_max_seconds == 30.0
    assert capabilities.supports_voice_list is False
    assert capabilities.supports_streaming is False


def test_omnivoice_not_loaded_initially():
    adapter = OmniVoiceTTSAdapter()
    assert adapter.is_loaded() is False


@pytest.mark.asyncio
async def test_omnivoice_synthesize_raises_when_not_loaded():
    adapter = OmniVoiceTTSAdapter()
    with pytest.raises(RuntimeError, match="not loaded"):
        await adapter.synthesize("hello")
