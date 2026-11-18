"""Refresh supported_models.json metadata from Hugging Face.

The catalog itself (ids, aliases, backends, licenses, capabilities) is curated by hand in
`packages/core/vocal_core/registry/supported_models.json`. This script only refreshes the
facts that Hugging Face knows better: sizes, parameter counts, languages, tags, download/like
counts, commit sha, file listings and last-modified dates.

Usage:
    uv run python scripts/generate_supported_models.py [--output PATH] [--force]
"""

import argparse
import json
import sys
import time
from pathlib import Path
from typing import Any

from huggingface_hub import ModelCard, get_safetensors_metadata
from huggingface_hub import model_info as hf_model_info
from huggingface_hub.hf_api import ModelInfo as HFModelInfo
from huggingface_hub.utils import HfHubHTTPError

DEFAULT_OUTPUT = Path(__file__).parent.parent / "packages" / "core" / "vocal_core" / "registry" / "supported_models.json"

# Fields we never overwrite: humans decide these.
CURATED_FIELDS = (
    "id",
    "name",
    "alias",
    "provider",
    "task",
    "backend",
    "description",
    "license",
    "commercial_use",
    "runtime",
    "runtime_note",
    "maintenance_status",
    "requires_gpu",
    "supports_streaming",
    "supports_live_streaming",
    "supports_voice_list",
    "supports_voice_clone",
    "supports_voice_design",
    "voice_mode",
    "clone_mode",
    "reference_audio_min_seconds",
    "reference_audio_max_seconds",
    "recommended_vram",
    "tags",
)

# Facts refreshed from Hugging Face.
DERIVED_FIELDS = ("size", "size_readable", "parameters", "actual_parameter_count", "languages", "modified_at", "files", "author", "downloads", "likes", "sha")


def load_catalog(path: Path) -> dict[str, Any]:
    if not path.exists():
        print(f"Catalog not found: {path}")
        sys.exit(1)
    with open(path, encoding="utf-8") as f:
        data = json.load(f)
    if not isinstance(data.get("models"), list):
        print("Catalog is missing a 'models' list.")
        sys.exit(1)
    return data


def fetch_model_metadata(entry: dict[str, Any], retry_count: int = 3) -> dict[str, Any] | None:  # noqa: C901
    model_id = entry["id"]
    task = entry.get("task", "stt")

    for attempt in range(retry_count):
        try:
            print(f"  Fetching metadata for {model_id}...")
            info: HFModelInfo = hf_model_info(model_id, files_metadata=True)

            total_size = 0
            files: list[dict[str, Any]] = []
            for sibling in info.siblings or []:
                if sibling.size:
                    total_size += sibling.size
                    files.append({"filename": sibling.rfilename, "size": sibling.size})

            actual_param_count = None
            try:
                st_meta = get_safetensors_metadata(model_id)
                actual_param_count = sum(st_meta.parameter_count.values())
            except Exception:
                pass

            languages: list[str] = []
            for tag in info.tags or []:
                if tag.startswith("language:"):
                    lang_code = tag.replace("language:", "")
                    if lang_code not in languages:
                        languages.append(lang_code)

            card_license = None
            try:
                card = ModelCard.load(model_id)
                card_data = card.data.to_dict()
                card_license = card_data.get("license")
                card_languages = card_data.get("language", [])
                if isinstance(card_languages, str):
                    card_languages = [card_languages]
                for lang in card_languages:
                    if lang not in languages:
                        languages.append(lang)
            except Exception:
                pass

            if not languages:
                languages = list(entry.get("languages", []))
            if not languages and task == "stt":
                languages = list(entry.get("languages", []))

            parameters_str = estimate_parameters(actual_param_count, model_id)
            size_readable = format_bytes(total_size)

            derived: dict[str, Any] = {
                "size": total_size,
                "size_readable": size_readable,
                "parameters": parameters_str,
                "languages": languages,
            }
            if actual_param_count:
                derived["actual_parameter_count"] = actual_param_count
            if info.last_modified:
                derived["modified_at"] = str(info.last_modified)
            if files:
                derived["files"] = files[:10]
            if info.author:
                derived["author"] = info.author
            if info.downloads:
                derived["downloads"] = info.downloads
            if info.likes:
                derived["likes"] = info.likes
            if info.sha:
                derived["sha"] = info.sha

            print(f"    [OK] Size: {size_readable}, Params: {parameters_str}")
            if card_license and str(card_license).lower() != str(entry.get("license", "")).lower():
                print(f"    [WARN] HF card license '{card_license}' differs from curated '{entry.get('license')}' (curated value kept)")
            return derived

        except HfHubHTTPError as e:
            if e.response.status_code in (401, 403):
                print(f"    [WARN] {model_id} is gated or private ({e.response.status_code}); keeping existing metadata")
                return None
            if e.response.status_code == 404:
                print(f"    [ERROR] Model not found: {model_id}")
                return None
            if attempt < retry_count - 1:
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
        if actual_count >= 1_000_000:
            return f"{actual_count / 1_000_000:.0f}M"
        return f"{actual_count / 1000:.0f}K"

    model_lower = model_id.lower()
    for marker, label in (("tiny", "39M"), ("base", "74M"), ("small", "244M"), ("medium", "769M"), ("large", "1.5B")):
        if marker in model_lower:
            return label
    return "Unknown"


def refresh_catalog(catalog_path: Path, force: bool = False) -> None:
    data = load_catalog(catalog_path)
    models = data["models"]

    if models and not force:
        answer = input(f"Refresh metadata for {len(models)} catalog models and overwrite {catalog_path.name}? [y/N] ")
        if answer.strip().lower() not in {"y", "yes"}:
            print("Aborted.")
            sys.exit(1)

    refreshed: list[dict[str, Any]] = []
    updated = 0
    for entry in models:
        curated = {key: entry[key] for key in CURATED_FIELDS if key in entry}
        derived = fetch_model_metadata(entry)
        if derived is None:
            refreshed.append(entry)
        else:
            merged = {**entry}
            for key in DERIVED_FIELDS:
                merged.pop(key, None)
            # Keep curated order first, then derived facts, so diffs stay readable.
            merged = {**{k: v for k, v in curated.items()}, **{k: v for k, v in entry.items() if k not in curated and k not in DERIVED_FIELDS}, **derived}
            refreshed.append(merged)
            updated += 1
        time.sleep(0.3)

    data["models"] = refreshed
    data["generated_at"] = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())

    with open(catalog_path, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2)
        f.write("\n")

    print(f"\n[SUCCESS] Refreshed {updated}/{len(models)} entries")
    print(f"[SUCCESS] Saved to: {catalog_path}")


def main() -> None:
    parser = argparse.ArgumentParser(description="Refresh supported_models.json metadata from Hugging Face")
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT, help="Path to supported_models.json")
    parser.add_argument("--force", action="store_true", help="Skip the confirmation prompt")
    args = parser.parse_args()
    refresh_catalog(args.output, args.force)


if __name__ == "__main__":
    main()
