from pydantic_settings import BaseSettings

try:
    from importlib.metadata import version as _pkg_version

    _api_version = _pkg_version("vocal-api")
except Exception:
    _api_version = "0.3.5"


class Settings(BaseSettings):
    """Application settings"""

    APP_NAME: str = "Vocal API"
    VERSION: str = _api_version
    DEBUG: bool = False

    CORS_ORIGINS: list[str] = ["*"]

    MAX_UPLOAD_SIZE: int = 25 * 1024 * 1024

    model_config = {
        "env_file": ".env",
        "case_sensitive": True,
        "extra": "ignore",
    }


settings = Settings()
