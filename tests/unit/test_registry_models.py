"""Unit tests for ModelInfo, ModelBackend, ModelTask, and format_bytes."""

from vocal_core.registry import ModelBackend, ModelInfo, ModelProvider, ModelStatus, ModelTask, format_bytes
from vocal_core.registry.capabilities import (
    capability_overrides_from_mapping,
    infer_model_capabilities,
    model_record_from_mapping,
    supported_model_records_from_mapping,
)


def test_model_backend_values():
    assert ModelBackend.FASTER_WHISPER == "faster_whisper"
    assert ModelBackend.WHISPERX == "whisperx"
    assert ModelBackend.KOKORO == "kokoro"
    assert ModelBackend.FASTER_QWEN3_TTS == "faster_qwen3_tts"
    assert ModelBackend.TRANSFORMERS == "transformers"
    assert ModelBackend.PIPER == "piper"
    assert ModelBackend.NEMO == "nemo"
    assert ModelBackend.CHATTERBOX == "chatterbox"
    assert ModelBackend.XTTS == "xtts"
    assert ModelBackend.FISH_SPEECH == "fish_speech"
    assert ModelBackend.ORPHEUS == "orpheus"
    assert ModelBackend.DIA == "dia"


def test_model_task_values():
    assert ModelTask.STT == "stt"
    assert ModelTask.TTS == "tts"


def test_model_status_values():
    assert ModelStatus.AVAILABLE == "available"
    assert ModelStatus.NOT_DOWNLOADED == "not_downloaded"
    assert ModelStatus.DOWNLOADING == "downloading"
    assert ModelStatus.ERROR == "error"


def test_format_bytes():
    assert format_bytes(0) == "0.0B"
    assert "KB" in format_bytes(2048)
    assert "MB" in format_bytes(5 * 1024 * 1024)
    assert "GB" in format_bytes(2 * 1024 * 1024 * 1024)


def test_model_info_construction():
    m = ModelInfo(
        id="Systran/faster-whisper-tiny",
        name="Faster Whisper Tiny",
        provider=ModelProvider.HUGGINGFACE,
        backend=ModelBackend.FASTER_WHISPER,
        task=ModelTask.STT,
        status=ModelStatus.NOT_DOWNLOADED,
    )
    assert m.id == "Systran/faster-whisper-tiny"
    assert m.backend == ModelBackend.FASTER_WHISPER
    assert m.task == ModelTask.STT
    assert m.status == ModelStatus.NOT_DOWNLOADED


def test_model_info_serialization():
    m = ModelInfo(
        id="hexgrad/Kokoro-82M",
        name="Kokoro 82M",
        provider=ModelProvider.HUGGINGFACE,
        backend=ModelBackend.KOKORO,
        task=ModelTask.TTS,
        supports_voice_list=True,
        voice_mode="voice_id",
    )
    d = m.model_dump()
    assert d["backend"] == "kokoro"
    assert d["task"] == "tts"
    assert d["supports_voice_list"] is True
    assert d["voice_mode"] == "voice_id"


def test_infer_kokoro_capabilities():
    capabilities = infer_model_capabilities(
        task="tts",
        backend="kokoro",
        model_id="hexgrad/Kokoro-82M",
    )
    assert capabilities["supports_streaming"] is True
    assert capabilities["supports_voice_list"] is True
    assert capabilities["supports_voice_clone"] is False
    assert capabilities["voice_mode"] == "voice_id"


def test_infer_qwen_clone_capabilities():
    capabilities = infer_model_capabilities(
        task="tts",
        backend="faster_qwen3_tts",
        model_id="Qwen/Qwen3-TTS-12Hz-0.6B-Base",
    )
    assert capabilities["supports_voice_clone"] is True
    assert capabilities["clone_mode"] == "reference_audio"
    assert capabilities["requires_gpu"] is True
    assert capabilities["reference_audio_min_seconds"] == 3.0
    assert capabilities["reference_audio_max_seconds"] == 30.0


def test_infer_qwen_custom_voice_capabilities():
    capabilities = infer_model_capabilities(
        task="tts",
        backend="faster_qwen3_tts",
        model_id="Qwen/Qwen3-TTS-12Hz-0.6B-CustomVoice",
    )
    assert capabilities["supports_voice_list"] is True
    assert capabilities["supports_voice_clone"] is False
    assert capabilities["voice_mode"] == "voice_id"


def test_capability_overrides_are_allowlisted_and_validated():
    overrides = capability_overrides_from_mapping(
        {
            "supports_voice_clone": True,
            "reference_audio_min_seconds": 4.0,
            "unknown_field": "ignored",
        }
    )
    assert overrides.supports_voice_clone is True
    assert overrides.reference_audio_min_seconds == 4.0


def test_model_record_from_mapping_requires_core_fields():
    record = model_record_from_mapping(
        {
            "id": "hexgrad/Kokoro-82M",
            "name": "Kokoro 82M",
            "provider": "huggingface",
            "task": "tts",
            "backend": "kokoro",
            "tags": ["text-to-speech"],
        }
    )
    assert record.id == "hexgrad/Kokoro-82M"
    assert record.backend == "kokoro"
    assert record.tags == ["text-to-speech"]


def test_supported_model_records_are_validated():
    records = supported_model_records_from_mapping(
        {
            "version": "1.0",
            "generated_at": "2026-03-08T00:00:00Z",
            "models": [
                {
                    "id": "Qwen/Qwen3-TTS-12Hz-0.6B-Base",
                    "name": "Qwen3 TTS 0.6B Base",
                    "alias": "qwen3-tts-0.6b",
                    "provider": "huggingface",
                    "task": "tts",
                    "backend": "faster_qwen3_tts",
                    "parameters": "915M",
                    "actual_parameter_count": 914643008,
                }
            ],
        }
    )
    assert records[0].alias == "qwen3-tts-0.6b"
    assert records[0].actual_parameter_count == 914643008


def test_hf_repo_id_is_stored_in_record():
    records = supported_model_records_from_mapping(
        {
            "models": [
                {
                    "id": "whisperx/large-v3",
                    "name": "WhisperX Large-v3",
                    "provider": "huggingface",
                    "task": "stt",
                    "backend": "whisperx",
                    "hf_repo_id": "Systran/faster-whisper-large-v3",
                }
            ]
        }
    )
    assert records[0].hf_repo_id == "Systran/faster-whisper-large-v3"
    assert records[0].backend == "whisperx"


def test_hf_repo_id_defaults_to_none():
    record = model_record_from_mapping(
        {
            "id": "Systran/faster-whisper-tiny",
            "name": "Faster Whisper Tiny",
            "provider": "huggingface",
            "task": "stt",
            "backend": "faster_whisper",
        }
    )
    assert record.hf_repo_id is None


def test_infer_nemo_capabilities():
    capabilities = infer_model_capabilities(
        task="stt",
        backend="nemo",
        model_id="nvidia/parakeet-tdt-1.1b",
    )
    assert capabilities["supports_streaming"] is False


def test_infer_whisperx_capabilities():
    capabilities = infer_model_capabilities(
        task="stt",
        backend="whisperx",
        model_id="whisperx/large-v3",
    )
    assert capabilities["supports_streaming"] is False


def test_infer_chatterbox_capabilities():
    capabilities = infer_model_capabilities(
        task="tts",
        backend="chatterbox",
        model_id="ResembleAI/chatterbox",
    )
    assert capabilities["supports_voice_clone"] is True
    assert capabilities["clone_mode"] == "reference_audio"
    assert capabilities["reference_audio_min_seconds"] == 3.0
    assert capabilities["reference_audio_max_seconds"] == 30.0


def test_infer_xtts_capabilities():
    capabilities = infer_model_capabilities(
        task="tts",
        backend="xtts",
        model_id="coqui/XTTS-v2",
    )
    assert capabilities["supports_voice_clone"] is True
    assert capabilities["clone_mode"] == "reference_audio"


def test_infer_dia_capabilities():
    capabilities = infer_model_capabilities(
        task="tts",
        backend="dia",
        model_id="nari-labs/Dia-1.6B",
    )
    assert capabilities["supports_voice_clone"] is True
