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


IMPLEMENTED_BACKENDS = {
    "faster_whisper",
    "whisperx",
    "transformers",
    "nemo",
    "kokoro",
    "faster_qwen3_tts",
    "piper",
    "chatterbox",
    "voxtral_stt",
    "voxtral_tts",
    "omnivoice",
    "supertonic",
    "voxcpm",
    "phonon",
}


def test_in_process_models_use_an_implemented_backend():
    data = _load_catalog()
    broken = [m["id"] for m in data["models"] if m.get("runtime", "in_process") == "in_process" and m["backend"] not in IMPLEMENTED_BACKENDS]
    assert broken == [], f"In-process models without a working adapter: {broken}"


def test_external_models_explain_their_runtime():
    data = _load_catalog()
    external = [m for m in data["models"] if m.get("runtime") == "external"]
    assert external, "expected at least one external-runtime entry (Higgs, Drama 3, Ming)"
    for m in external:
        assert m.get("runtime_note"), f"External model {m['id']} must document its runtime in runtime_note"


def test_every_model_declares_license_and_commercial_use():
    data = _load_catalog()
    for m in data["models"]:
        assert m.get("license"), f"Model {m['id']} is missing a license"
        assert isinstance(m.get("commercial_use"), bool), f"Model {m['id']} is missing commercial_use"
        assert m.get("maintenance_status") in {"active", "retired", "deprecated"}, f"Model {m['id']} has an invalid maintenance_status"


def test_non_commercial_licenses_are_flagged():
    data = _load_catalog()
    for m in data["models"]:
        if m["license"].startswith(("cc-by-nc", "coqui-public", "fish-audio", "boson-")):
            assert m["commercial_use"] is False, f"{m['id']} has a non-commercial license but commercial_use is true"


def test_pruned_backends_have_no_catalog_entries():
    data = _load_catalog()
    retired = {"xtts", "fish_speech", "orpheus", "dia"}
    leftovers = [m["id"] for m in data["models"] if m.get("backend") in retired]
    assert leftovers == [], f"Catalog still lists models for removed backends: {leftovers}"


def test_phonon_exposes_voice_list_without_cloning():
    models = _models_by_backend("phonon")
    assert len(models) == 1
    model = models[0]
    assert model["supports_voice_list"] is True
    assert model["supports_voice_clone"] is False
    assert model["requires_gpu"] is False


def test_chatterbox_is_marked_retired():
    models = _models_by_backend("chatterbox")
    assert models
    for m in models:
        assert m["maintenance_status"] == "retired"


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
        "chatterbox-multilingual-v3",
        "qwen3-tts-1.7b-design",
        "supertonic-3",
        "voxcpm2",
        "cohere-transcribe",
        "granite-speech-5.0-2b",
        "granite-speech-turboctc",
        "nemotron-3.5-asr",
        "phonon-31m",
        "ming-3.0-tts",
        "higgs-tts-3",
        "fish-drama-3",
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


def test_tts_models_have_task_tts():
    data = _load_catalog()
    tts_backends = {"kokoro", "faster_qwen3_tts", "piper", "chatterbox", "omnivoice", "supertonic", "voxcpm", "phonon"}
    for m in data["models"]:
        if m.get("backend") in tts_backends:
            assert m.get("task") == "tts", f"Model {m['id']} has wrong task"


@pytest.mark.asyncio
async def test_onnx_directory_without_config_json_verifies(tmp_path):
    from vocal_core.registry.providers.huggingface import HuggingFaceProvider

    onnx_dir = tmp_path / "onnx"
    onnx_dir.mkdir()
    (onnx_dir / "vocoder.onnx").write_bytes(b"onnx")
    provider = HuggingFaceProvider()
    assert await provider.verify_model("Supertone/supertonic-3", tmp_path) is True


@pytest.mark.asyncio
async def test_incomplete_download_does_not_verify(tmp_path):
    from vocal_core.registry.providers.huggingface import HuggingFaceProvider

    (tmp_path / "config.json").write_text("{}", encoding="utf-8")
    (tmp_path / "model.safetensors.incomplete").write_bytes(b"partial")
    provider = HuggingFaceProvider()
    assert await provider.verify_model("openbmb/VoxCPM2", tmp_path) is False


def test_stt_models_have_task_stt():
    data = _load_catalog()
    stt_backends = {"faster_whisper", "whisperx", "nemo", "transformers"}
    for m in data["models"]:
        if m.get("backend") in stt_backends:
            assert m.get("task") == "stt", f"Model {m['id']} has wrong task"
