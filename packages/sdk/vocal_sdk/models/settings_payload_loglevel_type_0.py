from enum import StrEnum


class SettingsPayloadLOGLEVELType0(StrEnum):
    CRITICAL = "CRITICAL"
    DEBUG = "DEBUG"
    ERROR = "ERROR"
    INFO = "INFO"
    WARNING = "WARNING"

    def __str__(self) -> str:
        return str(self.value)
