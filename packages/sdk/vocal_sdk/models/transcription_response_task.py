from enum import StrEnum


class TranscriptionResponseTask(StrEnum):
    TRANSCRIBE = "transcribe"
    TRANSLATE = "translate"

    def __str__(self) -> str:
        return str(self.value)
