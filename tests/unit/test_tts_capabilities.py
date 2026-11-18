from pathlib import Path

import pytest

from vocal_core.adapters.tts import (
    CHATTERBOX_AVAILABLE,
    ChatterboxTTSAdapter,
    FasterQwen3TTSAdapter,
    KokoroTTSAdapter,
    OmniVoiceTTSAdapter,
    PiperTTSAdapter,
    SimpleTTSAdapter,
    SupertonicTTSAdapter,
    VoxCPMTTSAdapter,
)
from vocal_core.adapters.tts.chatterbox import chatterbox_kind


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


def test_chatterbox_kind_selects_multilingual_v3():
    assert chatterbox_kind(Path("ResembleAI--chatterbox-multilingual-v3")) == "multilingual_v3"
    assert chatterbox_kind(Path("ResembleAI--chatterbox")) == "default"


def test_supertonic_capabilities():
    capabilities = SupertonicTTSAdapter().get_capabilities()
    assert capabilities.supports_voice_list is True
    assert capabilities.supports_voice_clone is False
    assert capabilities.requires_gpu is False
    assert capabilities.voice_mode == "voice_id"


def test_voxcpm_capabilities():
    capabilities = VoxCPMTTSAdapter().get_capabilities()
    assert capabilities.supports_voice_clone is True
    assert capabilities.supports_voice_design is True
    assert capabilities.voice_mode == "instruction"
    assert capabilities.requires_gpu is True


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


class TestOutputFormatInference:
    """Registry-level output_formats must match what adapters actually accept."""

    def test_wav_only_backends(self):
        from vocal_core.registry.capabilities import infer_model_capabilities

        for backend in ("chatterbox", "voxcpm", "supertonic", "omnivoice"):
            caps = infer_model_capabilities(task="tts", backend=backend, model_id=f"org/{backend}-model")
            assert caps["output_formats"] == ["wav"], backend

    def test_phonon_wav_and_pcm(self):
        from vocal_core.registry.capabilities import infer_model_capabilities

        caps = infer_model_capabilities(task="tts", backend="phonon", model_id="gradium/phonon-31m-en")
        assert caps["output_formats"] == ["wav", "pcm"]

    def test_converting_backends_accept_all_formats(self):
        from vocal_core.registry.capabilities import ALL_AUDIO_FORMATS, infer_model_capabilities

        for backend in ("kokoro", "piper", "faster_qwen3_tts", "voxtral_tts"):
            caps = infer_model_capabilities(task="tts", backend=backend, model_id=f"org/{backend}-model")
            assert caps["output_formats"] == ALL_AUDIO_FORMATS, backend

    def test_stt_has_no_output_formats(self):
        from vocal_core.registry.capabilities import infer_model_capabilities

        caps = infer_model_capabilities(task="stt", backend="faster_whisper", model_id="Systran/faster-whisper-tiny")
        assert caps["output_formats"] == []

    def test_curated_override_wins(self):
        from vocal_core.registry.capabilities import CapabilityOverrides, infer_model_capabilities

        caps = infer_model_capabilities(
            task="tts",
            backend="kokoro",
            model_id="org/kokoro-custom",
            overrides=CapabilityOverrides(output_formats=["wav"]),
        )
        assert caps["output_formats"] == ["wav"]
