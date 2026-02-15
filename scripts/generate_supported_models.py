import argparse
import json
import sys
import time
from pathlib import Path

from huggingface_hub import ModelCard, get_safetensors_metadata
from huggingface_hub import model_info as hf_model_info
from huggingface_hub.hf_api import ModelInfo as HFModelInfo
from huggingface_hub.utils import HfHubHTTPError

KNOWN_STT_MODELS = {
    "Systran/faster-whisper-tiny": "whisper-tiny",
    "Systran/faster-whisper-base": "whisper-base",
    "Systran/faster-whisper-small": "whisper-small",
    "Systran/faster-whisper-medium": "whisper-medium",
    "Systran/faster-whisper-large-v2": "whisper-large-v2",
    "Systran/faster-whisper-large-v3": "whisper-large-v3",
}

KNOWN_TTS_MODELS = {
    "hexgrad/Kokoro-82M": "kokoro",
    "onnx-community/Kokoro-82M-ONNX": "kokoro-onnx",
    "fishaudio/fish-speech-1.5": "chatterbox",
    "coqui/XTTS-v2": "xtts-v2",
    "myshell-ai/MeloTTS-English": "melotts-en",
}

LANGUAGE_FALLBACKS = {
    "coqui/XTTS-v2": ["en", "es", "fr", "de", "it", "pt", "pl", "tr", "ru", "nl", "cs", "ar", "zh", "ja", "hu", "ko", "hi"],
}

WHISPER_LANGUAGES = [
    "en",
    "zh",
    "de",
    "es",
    "ru",
    "ko",
    "fr",
    "ja",
    "pt",
    "tr",
    "pl",
    "ca",
    "nl",
    "ar",
    "sv",
    "it",
    "id",
    "hi",
    "fi",
    "vi",
    "he",
    "uk",
    "el",
    "ms",
    "cs",
    "ro",
    "da",
    "hu",
    "ta",
    "no",
    "th",
    "ur",
    "hr",
    "bg",
    "lt",
    "la",
    "mi",
    "ml",
    "cy",
    "sk",
    "te",
    "fa",
    "lv",
    "bn",
    "sr",
    "az",
    "sl",
    "kn",
    "et",
    "mk",
    "br",
    "eu",
    "is",
    "hy",
    "ne",
    "mn",
    "bs",
    "kk",
    "sq",
    "sw",
    "gl",
    "mr",
    "pa",
    "si",
    "km",
    "sn",
    "yo",
    "so",
    "af",
    "oc",
    "ka",
    "be",
    "tg",
    "sd",
    "gu",
    "am",
    "yi",
    "lo",
    "uz",
    "fo",
    "ht",
    "ps",
    "tk",
    "nn",
    "mt",
    "sa",
    "lb",
    "my",
    "bo",
    "tl",
    "mg",
    "as",
    "tt",
    "haw",
    "ln",
    "ha",
    "ba",
    "jw",
    "su",
]

BACKEND_MAPPING = {
    "faster-whisper": "faster_whisper",
    "xtts": "custom",
    "melotts": "custom",
    "kokoro": "onnx",
}


def fetch_model_metadata(model_id: str, alias: str, task: str, retry_count: int = 3) -> dict | None:  # noqa: C901
    for attempt in range(retry_count):
        try:
            print(f"  Fetching metadata for {model_id}...")
            info: HFModelInfo = hf_model_info(model_id, files_metadata=True)

            total_size = 0
            files = []
            if info.siblings:
                for sibling in info.siblings:
                    if sibling.size:
                        total_size += sibling.size
                        files.append({"filename": sibling.rfilename, "size": sibling.size})

            actual_param_count = None
            try:
                st_meta = get_safetensors_metadata(model_id)
                actual_param_count = sum(st_meta.parameter_count.values())
                print(f"    [OK] Got parameter count: {actual_param_count:,}")
            except Exception:
                pass

            license_info = None
            languages = []
            description = None
            tags = info.tags or []
            author = info.author

            for tag in tags:
                if tag.startswith("language:"):
                    lang_code = tag.replace("language:", "")
                    if lang_code not in languages:
                        languages.append(lang_code)

            try:
                card = ModelCard.load(model_id)
                card_data = card.data.to_dict()
                license_info = card_data.get("license")

                card_languages = card_data.get("language", [])
                if isinstance(card_languages, str):
                    card_languages = [card_languages]
                for lang in card_languages:
                    if lang not in languages:
                        languages.append(lang)

                if "base_model" in card_data:
                    base_models = card_data["base_model"]
                    if isinstance(base_models, str):
                        description = f"Based on {base_models}"
                    elif isinstance(base_models, list):
                        description = f"Based on {base_models}"
            except Exception:
                pass

            if not description and info.pipeline_tag:
                description = f"{info.pipeline_tag.replace('-', ' ').title()} model"

            if task == "stt" and not languages:
                languages = WHISPER_LANGUAGES

            if model_id in LANGUAGE_FALLBACKS and not languages:
                languages = LANGUAGE_FALLBACKS[model_id]

            backend = "faster_whisper" if "whisper" in model_id.lower() else "onnx"
            if "xtts" in model_id.lower():
                backend = "custom"
            elif "melotts" in model_id.lower():
                backend = "custom"

            parameters_str = estimate_parameters(actual_param_count, model_id)
            vram = estimate_vram(total_size, parameters_str)
            size_readable = format_bytes(total_size)

            model_name = info.id.split("/")[-1]
            model_name = model_name.replace("-", " ").replace("_", " ").title()

            modified_at = str(info.last_modified) if info.last_modified else None

            metadata = {
                "id": model_id,
                "name": model_name,
                "alias": alias,
                "provider": "huggingface",
                "task": task,
                "backend": backend,
                "parameters": parameters_str,
                "size": total_size,
                "size_readable": size_readable,
                "languages": languages,
                "recommended_vram": vram,
                "source_url": f"https://huggingface.co/{model_id}",
            }

            if description:
                metadata["description"] = description
            if actual_param_count:
                metadata["actual_parameter_count"] = actual_param_count
            if license_info:
                metadata["license"] = license_info
            if modified_at:
                metadata["modified_at"] = modified_at
            if files:
                metadata["files"] = files[:10]
            if author:
                metadata["author"] = author
            if tags:
                metadata["tags"] = tags
            if info.downloads:
                metadata["downloads"] = info.downloads
            if info.likes:
                metadata["likes"] = info.likes
            if info.sha:
                metadata["sha"] = info.sha

            print(f"    [OK] Size: {size_readable}, Params: {parameters_str}, VRAM: {vram}")
            return metadata

        except HfHubHTTPError as e:
            if e.response.status_code == 404:
                print(f"    [ERROR] Model not found: {model_id}")
                return None
            elif attempt < retry_count - 1:
                wait_time = 2**attempt
                print(f"    [WARN] Rate limited, retrying in {wait_time}s...")
                time.sleep(wait_time)
            else:
                print(f"    [ERROR] Failed after {retry_count} attempts: {e}")
                return None
        except Exception as e:
            print(f"    [ERROR] Error fetching metadata: {e}")
            if attempt < retry_count - 1:
                time.sleep(2)
            else:
                return None

    return None


def format_bytes(size: int) -> str:
    for unit in ["B", "KB", "MB", "GB", "TB"]:
        if size < 1024.0:
            return f"{size:.1f} {unit}"
        size /= 1024.0
    return f"{size:.1f} PB"


def estimate_parameters(actual_count: int | None, model_id: str) -> str:  # noqa: C901
    if actual_count:
        if actual_count >= 1_000_000_000:
            return f"{actual_count / 1_000_000_000:.1f}B"
        elif actual_count >= 1_000_000:
            return f"{actual_count / 1_000_000:.0f}M"
        else:
            return f"{actual_count / 1000:.0f}K"

    model_lower = model_id.lower()
    if "tiny" in model_lower:
        return "39M"
    elif "base" in model_lower:
        return "74M"
    elif "small" in model_lower:
        return "244M"
    elif "medium" in model_lower:
        return "769M"
    elif "large" in model_lower:
        return "1.5B"
    elif "82m" in model_lower:
        return "82M"
    elif "467m" in model_lower:
        return "467M"
    elif "50m" in model_lower:
        return "~50M"

    return "Unknown"


def estimate_vram(size: int, params: str) -> str:
    if size < 100 * 1024 * 1024:
        return "1GB+"
    elif size < 300 * 1024 * 1024:
        return "2GB+"
    elif size < 800 * 1024 * 1024:
        return "4GB+"
    elif size < 2 * 1024 * 1024 * 1024:
        return "6GB+"
    else:
        return "8GB+"


def generate_supported_models(output_path: Path, force: bool = False) -> None:
    if output_path.exists() and not force:
        print(f"Output file already exists: {output_path}")
        print("Use --force to overwrite")
        sys.exit(1)

    print("Generating supported models metadata...\n")

    all_models = []

    print("Fetching STT models:")
    for model_id, alias in KNOWN_STT_MODELS.items():
        metadata = fetch_model_metadata(model_id, alias, "stt")
        if metadata:
            all_models.append(metadata)
        time.sleep(0.5)

    print("\nFetching TTS models:")
    for model_id, alias in KNOWN_TTS_MODELS.items():
        metadata = fetch_model_metadata(model_id, alias, "tts")
        if metadata:
            all_models.append(metadata)
        time.sleep(0.5)

    output_data = {"version": "1.0", "generated_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()), "models": all_models}

    output_path.parent.mkdir(parents=True, exist_ok=True)
    with open(output_path, "w") as f:
        json.dump(output_data, f, indent=2)

    print(f"\n[SUCCESS] Generated {len(all_models)} model metadata entries")
    print(f"[SUCCESS] Saved to: {output_path}")


def main():
    parser = argparse.ArgumentParser(description="Generate supported models metadata from HuggingFace")
    parser.add_argument("--output", type=Path, default=Path(__file__).parent.parent / "packages" / "core" / "vocal_core" / "registry" / "supported_models.json", help="Output path for supported_models.json")
    parser.add_argument("--force", action="store_true", help="Overwrite existing file")

    args = parser.parse_args()
    generate_supported_models(args.output, args.force)


if __name__ == "__main__":
    main()
