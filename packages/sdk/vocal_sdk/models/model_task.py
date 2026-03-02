from enum import Enum


class ModelTask(str, Enum):
    STT = "stt"
    TTS = "tts"

    def __str__(self) -> str:
        return str(self.value)
