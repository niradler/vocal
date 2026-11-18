from enum import StrEnum


class ModelTask(StrEnum):
    STT = "stt"
    TTS = "tts"

    def __str__(self) -> str:
        return str(self.value)
