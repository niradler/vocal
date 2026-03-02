from pydantic_settings import BaseSettings


class VocalSettings(BaseSettings):
    LLM_BASE_URL: str = "http://localhost:11434/v1"
    LLM_MODEL: str = "gemma3n:latest"
    LLM_API_KEY: str = "ollama"

    STT_DEFAULT_MODEL: str = "Systran/faster-whisper-tiny"
    STT_DEFAULT_LANGUAGE: str | None = None
    STT_SAMPLE_RATE: int = 16000

    VAD_THRESHOLD: float = 400.0
    VAD_SILENCE_FRAMES: int = 15
    VAD_MAX_BUFFER_FRAMES: int = 150
    VAD_SPEECH_ONSET_FRAMES: int = 3
    VAD_MIN_SPEECH_FRAMES: int = 4
    VAD_SILENCE_DURATION_S: float = 1.5

    REALTIME_DEFAULT_INPUT_RATE: int = 24000

    AUDIO_FRAME_SIZE: int = 1600
    AUDIO_CHANNELS: int = 1
    PLAYBACK_COOLDOWN: float = 0.5

    CHAT_SYSTEM_PROMPT: str = "You are a helpful voice assistant. Keep answers short and conversational, 1 sentence max, no symbols or punctuation."

    model_config = {"env_file": ".env", "case_sensitive": True, "extra": "ignore"}


vocal_settings = VocalSettings()
