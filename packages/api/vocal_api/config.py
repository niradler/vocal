from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    """Application settings"""

    APP_NAME: str = "Vocal API"
    VERSION: str = "0.1.0"
    DEBUG: bool = True

    CORS_ORIGINS: list[str] = ["*"]

    MAX_UPLOAD_SIZE: int = 25 * 1024 * 1024

    model_config = {
        "env_file": ".env",
        "case_sensitive": True,
    }


settings = Settings()
