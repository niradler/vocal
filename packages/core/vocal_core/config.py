from pydantic_settings import BaseSettings


class VocalSettings(BaseSettings):
    LLM_BASE_URL: str = "http://localhost:11434/v1"
    LLM_MODEL: str = "gemma3n:latest"
    LLM_API_KEY: str = "ollama"

    STT_DEFAULT_MODEL: str = "Systran/faster-whisper-tiny"
    STT_DEFAULT_LANGUAGE: str | None = None
    STT_SAMPLE_RATE: int = 16000

    TTS_DEFAULT_MODEL: str = "pyttsx3"
    TTS_DEFAULT_VOICE: str | None = None
    TTS_DEFAULT_CLONE_MODEL: str = "Qwen/Qwen3-TTS-12Hz-0.6B-Base"

    DEFAULT_LANGUAGE: str = "en"

    WHISPERX_BATCH_SIZE: int = 16
    CHATTERBOX_EXAGGERATION: float = 0.5
    CHATTERBOX_CFG_WEIGHT: float = 0.5
    NEMO_DEFAULT_LANGUAGE: str = "en"

    VAD_BACKEND: str = "silero"
    VAD_SPEECH_THRESHOLD: float = 0.5
    VAD_THRESHOLD: float = 400.0
    # Turn detection is millisecond-based so it is independent of chunk size.
    VAD_ONSET_MS: int = 180
    # Dictation: commit shortly after speech stops.
    VAD_SILENCE_MS: int = 600
    VAD_COMMIT_GRACE_MS: int = 0
    # Voice agent: natural pauses inside one sentence reach ~1 s, so wait a
    # little longer before committing a turn instead of splitting it.
    REALTIME_AGENT_SILENCE_MS: int = 700
    REALTIME_AGENT_COMMIT_GRACE_MS: int = 400
    VAD_MIN_SPEECH_MS: int = 180
    VAD_PREROLL_MS: int = 300
    # Legacy frame counts kept for callers that still pass them.
    VAD_SILENCE_FRAMES: int = 15
    VAD_MAX_BUFFER_FRAMES: int = 150
    VAD_SPEECH_ONSET_FRAMES: int = 3
    VAD_MIN_SPEECH_FRAMES: int = 4
    VAD_SILENCE_DURATION_S: float = 0.8

    REALTIME_DEFAULT_INPUT_RATE: int = 24000
    REALTIME_OUTPUT_SAMPLE_RATE: int = 24000
    REALTIME_KEEPALIVE_S: int = 20
    REALTIME_SESSION_TTL_S: int = 1800
    REALTIME_MAX_UTTERANCE_S: float = 30.0
    # Live partial transcripts: how often to re-decode, the warm-up audio
    # needed before the first pass, and how much context each pass uses.
    REALTIME_PARTIAL_INTERVAL_S: float = 0.4
    REALTIME_PARTIAL_MIN_AUDIO_S: float = 0.8
    REALTIME_PARTIAL_WINDOW_S: float = 15.0
    # Sentence pipelining for LLM -> TTS.
    REALTIME_SENTENCE_MIN_CHARS: int = 12
    REALTIME_SENTENCE_MAX_CHARS: int = 220

    AUDIO_FRAME_SIZE: int = 1600
    AUDIO_CHANNELS: int = 1
    PLAYBACK_COOLDOWN: float = 0.5

    CHAT_SYSTEM_PROMPT: str = "You are a helpful voice assistant. Keep answers short and conversational, 1 sentence max, no symbols or punctuation."

    LOG_LEVEL: str = "INFO"
    LOG_FORMAT: str = "%(asctime)s %(name)-30s %(levelname)-8s %(message)s"

    model_config = {"env_file": ".env", "case_sensitive": True, "extra": "ignore"}


vocal_settings = VocalSettings()


def optional_dependency_install_hint(extra_name: str, package_name: str | None = None) -> str:
    pkg = package_name or extra_name
    return f'Missing optional dependency \'{pkg}\'. Install with: uvx --from "vocal-ai[{extra_name}]" vocal <command> or pip install "vocal-ai[{extra_name}]" (project dev: uv add {pkg}).'
