from enum import Enum


class TranscriptionFormat(str, Enum):
    JSON = "json"
    SRT = "srt"
    TEXT = "text"
    VERBOSE_JSON = "verbose_json"
    VTT = "vtt"

    def __str__(self) -> str:
        return str(self.value)
