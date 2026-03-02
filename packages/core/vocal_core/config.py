from pydantic_settings import BaseSettings


class VocalSettings(BaseSettings):
    LLM_BASE_URL: str = "http://localhost:11434/v1"
    LLM_MODEL: str = "gemma3n:latest"
    LLM_API_KEY: str = "ollama"

    STT_DEFAULT_MODEL: str = "Systran/faster-whisper-tiny"
    STT_DEFAULT_LANGUAGE: str | None = None
    STT_SAMPLE_RATE: int = 16000

    model_config = {"env_file": ".env", "case_sensitive": True, "extra": "ignore"}


vocal_settings = VocalSettings()
