"""Unit tests verifying all new model catalog entries load and resolve correctly."""

import json
from pathlib import Path

import pytest

from vocal_core.registry.capabilities import supported_model_records_from_mapping
from vocal_core.registry.model_info import ModelBackend

CATALOG_PATH = Path(__file__).parent.parent.parent / "packages" / "core" / "vocal_core" / "registry" / "supported_models.json"


def _load_catalog():
    with open(CATALOG_PATH, encoding="utf-8") as f:
        return json.load(f)


def _models_by_backend(backend: str):
    data = _load_catalog()
    return [m for m in data["models"] if m.get("backend") == backend]


def test_catalog_json_is_valid():
    data = _load_catalog()
    assert "models" in data
    assert len(data["models"]) > 0


def test_all_catalog_entries_parse_without_error():
    data = _load_catalog()
    records = supported_model_records_from_mapping(data)
    assert len(records) == len(data["models"])


def test_all_catalog_backends_are_known_enum_values():
    data = _load_catalog()
    known = {b.value for b in ModelBackend}
    unknown = {m["backend"] for m in data["models"] if m.get("backend") not in known}
    assert unknown == set(), f"Unknown backends in catalog: {unknown}"


@pytest.mark.parametrize(
    "alias",
    [
        "whisper-tiny",
        "whisper-base",
        "whisper-small",
        "whisper-medium",
        "whisper-large-v2",
        "whisper-large-v3",
        "whisper-tiny-en",
        "whisper-base-en",
        "whisper-small-en",
        "whisper-medium-en",
        "distil-whisper-small-en",
        "distil-whisper-medium-en",
        "distil-whisper-large-v2",
        "distil-whisper-large-v3",
        "whisper-large-v3-turbo",
        "whisperx-large-v3",
        "whisperx-large-v3-turbo",
        "whisperx-distil-large-v3",
        "parakeet-tdt",
        "parakeet-tdt-v2",
        "canary-qwen",
        "chatterbox",
        "chatterbox-turbo",
        "xtts-v2",
        "fish-speech",
        "orpheus-3b",
        "dia-1.6b",
        "dia2-2b",
    ],
)
def test_alias_exists_in_catalog(alias):
    data = _load_catalog()
    aliases = {m.get("alias") for m in data["models"]}
    assert alias in aliases, f"Alias '{alias}' not found in catalog"


def test_faster_whisper_models_count():
    assert len(_models_by_backend("faster_whisper")) >= 15


def test_whisperx_models_have_hf_repo_id():
    models = _models_by_backend("whisperx")
    assert len(models) >= 3
    for m in models:
        assert m.get("hf_repo_id"), f"WhisperX model {m['id']} missing hf_repo_id"


def test_nemo_models_have_requires_gpu():
    models = _models_by_backend("nemo")
    assert len(models) >= 2
    for m in models:
        assert m.get("requires_gpu") is True, f"NeMo model {m['id']} should require GPU"


def test_chatterbox_models_have_voice_clone():
    models = _models_by_backend("chatterbox")
    assert len(models) >= 2
    for m in models:
        assert m.get("supports_voice_clone") is True, f"Chatterbox model {m['id']} should support voice clone"


def test_xtts_model_multilingual():
    models = _models_by_backend("xtts")
    assert len(models) >= 1
    assert len(models[0].get("languages", [])) >= 10, "XTTS-v2 should list 10+ languages"


def test_dia_models_present():
    models = _models_by_backend("dia")
    assert len(models) >= 2


def test_tts_models_have_task_tts():
    data = _load_catalog()
    tts_backends = {"kokoro", "faster_qwen3_tts", "piper", "chatterbox", "xtts", "fish_speech", "orpheus", "dia"}
    for m in data["models"]:
        if m.get("backend") in tts_backends:
            assert m.get("task") == "tts", f"Model {m['id']} has wrong task"


def test_stt_models_have_task_stt():
    data = _load_catalog()
    stt_backends = {"faster_whisper", "whisperx", "nemo", "transformers"}
    for m in data["models"]:
        if m.get("backend") in stt_backends:
            assert m.get("task") == "stt", f"Model {m['id']} has wrong task"
