"""Shared helpers for the Qwen-Omni STT and TTS adapters.

Both adapters run the same checkpoints (Qwen2.5-Omni / Qwen3-Omni) and need
the same generation detection and speaker inventory, so they live here once.
"""

from __future__ import annotations

import json
from pathlib import Path

# Built-in talker speakers per generation. Qwen3-Omni adds Aiden.
OMNI_SPEAKERS: dict[str, list[str]] = {
    "2.5": ["Ethan", "Chelsie"],
    "3": ["Ethan", "Chelsie", "Aiden"],
}

SPEAKER_GENDERS: dict[str, str] = {
    "Ethan": "male",
    "Chelsie": "female",
    "Aiden": "male",
}


def detect_omni_generation(model_path: Path) -> str:
    """Detect whether a local checkpoint is Qwen2.5-Omni ("2.5") or Qwen3-Omni ("3")."""
    cfg_file = model_path / "config.json"
    if cfg_file.exists():
        with open(cfg_file, encoding="utf-8") as f:
            model_type = json.load(f).get("model_type", "")
        if "qwen2_5_omni" in model_type:
            return "2.5"
        if "qwen3_omni" in model_type:
            return "3"
    # Fall back to the directory name for checkpoints without a config.json.
    dir_lower = str(model_path).lower()
    if "qwen2.5" in dir_lower or "qwen2_5" in dir_lower:
        return "2.5"
    return "3"
