"""Runtime settings API — view and update Vocal configuration (web UI).

Settings are applied to the shared ``vocal_settings`` singleton immediately and
persisted to ``<vocal cache>/settings.env`` so they survive restarts. The file
is loaded once at API startup (see ``vocal_api.main.lifespan``).

Only the fields declared in ``SettingsPayload`` are writable through the API;
everything else in ``VocalSettings`` remains environment-only.
"""

import logging
import os
from pathlib import Path
from typing import Literal

from fastapi import APIRouter
from pydantic import BaseModel, Field

from vocal_core.config import vocal_settings

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/v1/settings", tags=["settings"])

API_KEY_MASK = "********"


class SettingsPayload(BaseModel):
    """Editable Vocal settings. Omitted (null) fields are left unchanged on update."""

    LLM_BASE_URL: str | None = Field(None, pattern=r"^https?://", description="OpenAI-compatible LLM base URL for the voice agent")
    LLM_MODEL: str | None = Field(None, min_length=1, description="LLM model used by the voice agent")
    LLM_API_KEY: str | None = Field(None, description="LLM API key; the masked value or an empty string keeps the current key")

    STT_DEFAULT_MODEL: str | None = Field(None, min_length=1, description="Default speech-to-text model")
    STT_DEFAULT_LANGUAGE: str | None = Field(None, description="Default STT language code; empty string means auto-detect")
    TTS_DEFAULT_MODEL: str | None = Field(None, min_length=1, description="Default text-to-speech model")
    TTS_DEFAULT_VOICE: str | None = Field(None, description="Default TTS voice; empty string means model default")
    TTS_DEFAULT_CLONE_MODEL: str | None = Field(None, min_length=1, description="Default model for voice cloning")
    DEFAULT_LANGUAGE: str | None = Field(None, min_length=1, description="Default language code")

    VAD_SPEECH_THRESHOLD: float | None = Field(None, ge=0.0, le=1.0, description="Silero speech probability threshold")
    VAD_THRESHOLD: float | None = Field(None, gt=0.0, description="RMS energy threshold (fallback VAD)")
    VAD_ONSET_MS: int | None = Field(None, ge=0, le=5000, description="Speech onset confirmation window")
    VAD_SILENCE_MS: int | None = Field(None, ge=100, le=10000, description="Dictation: silence before a turn commits")
    VAD_COMMIT_GRACE_MS: int | None = Field(None, ge=0, le=5000, description="Dictation: extra grace after silence")
    VAD_MIN_SPEECH_MS: int | None = Field(None, ge=0, le=5000, description="Minimum speech duration to count as a turn")
    VAD_PREROLL_MS: int | None = Field(None, ge=0, le=5000, description="Audio kept before speech onset")
    REALTIME_AGENT_SILENCE_MS: int | None = Field(None, ge=100, le=10000, description="Voice agent: silence before a turn commits")
    REALTIME_AGENT_COMMIT_GRACE_MS: int | None = Field(None, ge=0, le=5000, description="Voice agent: extra grace after silence")
    REALTIME_PARTIAL_INTERVAL_S: float | None = Field(None, ge=0.0, le=10.0, description="Live partial transcript interval; 0 disables partials")
    REALTIME_MAX_UTTERANCE_S: float | None = Field(None, ge=1.0, le=300.0, description="Maximum single utterance length")

    CHAT_SYSTEM_PROMPT: str | None = Field(None, description="Voice agent system prompt; empty string disables it")
    LOG_LEVEL: Literal["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"] | None = Field(None, description="Server log level (applies to new log records)")


class SettingsResponse(BaseModel):
    """Current effective settings. Plain types on purpose: constraints belong to
    the request (SettingsPayload); the response reports reality, and a typed
    schema gives the generated SDK real attributes instead of a dict."""

    LLM_BASE_URL: str
    LLM_MODEL: str
    LLM_API_KEY: str | None
    STT_DEFAULT_MODEL: str
    STT_DEFAULT_LANGUAGE: str | None
    TTS_DEFAULT_MODEL: str
    TTS_DEFAULT_VOICE: str | None
    TTS_DEFAULT_CLONE_MODEL: str
    DEFAULT_LANGUAGE: str
    VAD_SPEECH_THRESHOLD: float
    VAD_THRESHOLD: float
    VAD_ONSET_MS: int
    VAD_SILENCE_MS: int
    VAD_COMMIT_GRACE_MS: int
    VAD_MIN_SPEECH_MS: int
    VAD_PREROLL_MS: int
    REALTIME_AGENT_SILENCE_MS: int
    REALTIME_AGENT_COMMIT_GRACE_MS: int
    REALTIME_PARTIAL_INTERVAL_S: float
    REALTIME_MAX_UTTERANCE_S: float
    CHAT_SYSTEM_PROMPT: str
    LOG_LEVEL: str
    llm_api_key_set: bool


EDITABLE_FIELDS: tuple[str, ...] = tuple(SettingsPayload.model_fields)
# Fields where an empty string means "unset" (None) rather than a literal "".
NULLABLE_FIELDS = frozenset({"STT_DEFAULT_LANGUAGE", "TTS_DEFAULT_VOICE"})
SECRET_FIELDS = frozenset({"LLM_API_KEY"})


def settings_file_path() -> Path:
    """Persisted settings live next to the model cache (isolated per storage path)."""
    storage = os.getenv("VOCAL_MODEL_STORAGE_PATH")
    base = Path(storage).parent if storage else Path.home() / ".cache" / "vocal"
    return base / "settings.env"


def _current_values() -> dict:
    values = {}
    for key in EDITABLE_FIELDS:
        value = getattr(vocal_settings, key)
        values[key] = API_KEY_MASK if key in SECRET_FIELDS and value else value
    return values


def load_persisted_settings() -> None:
    """Apply persisted settings at startup. Invalid lines are skipped, not fatal."""
    path = settings_file_path()
    if not path.exists():
        return
    applied = []
    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, _, raw = line.partition("=")
        key = key.strip()
        if key not in EDITABLE_FIELDS:
            continue
        current = getattr(vocal_settings, key)
        try:
            if isinstance(current, int):
                value = int(raw)
            elif isinstance(current, float):
                value = float(raw)
            elif raw == "" and key in NULLABLE_FIELDS:
                value = None
            else:
                value = raw
        except ValueError:
            logger.warning("Ignoring invalid persisted setting %s", key)
            continue
        setattr(vocal_settings, key, value)
        applied.append(key)
    if applied:
        logger.info("Loaded %d persisted settings from %s", len(applied), path)


def _persist_settings() -> None:
    path = settings_file_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    lines = ["# Vocal settings — managed via the web UI (GET/PUT /v1/settings)."]
    for key in EDITABLE_FIELDS:
        value = getattr(vocal_settings, key)
        lines.append(f"{key}={'' if value is None else value}")
    tmp = path.with_suffix(".env.tmp")
    tmp.write_text("\n".join(lines) + "\n", encoding="utf-8")
    tmp.replace(path)


@router.get("", response_model=SettingsResponse, summary="Get current settings", description="Current effective settings. The LLM API key is masked.")
async def get_settings() -> dict:
    values = _current_values()
    values["llm_api_key_set"] = bool(vocal_settings.LLM_API_KEY)
    return values


@router.put("", response_model=SettingsResponse, summary="Update settings", description="Update settings, apply them immediately and persist them for future restarts.")
async def update_settings(update: SettingsPayload) -> dict:
    changed = []
    for key in EDITABLE_FIELDS:
        value = getattr(update, key)
        if value is None:
            continue
        if key in SECRET_FIELDS and value in ("", API_KEY_MASK):
            continue
        if key in NULLABLE_FIELDS and value == "":
            value = None
        setattr(vocal_settings, key, value)
        changed.append(key)

    if changed:
        _persist_settings()
        # Never log values: they may contain secrets.
        logger.info("Settings updated: %s", ", ".join(changed))

    values = _current_values()
    values["llm_api_key_set"] = bool(vocal_settings.LLM_API_KEY)
    return values


settings_router = router
