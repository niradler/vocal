from vocal_core.adapters.tts import FasterQwen3TTSAdapter, KokoroTTSAdapter, PiperTTSAdapter, SimpleTTSAdapter


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
