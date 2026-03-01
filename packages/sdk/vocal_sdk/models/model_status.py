from enum import Enum


class ModelStatus(str, Enum):
    AVAILABLE = "available"
    DOWNLOADING = "downloading"
    ERROR = "error"
    NOT_DOWNLOADED = "not_downloaded"

    def __str__(self) -> str:
        return str(self.value)
