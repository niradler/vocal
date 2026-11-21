from enum import StrEnum


class BodyCreateTranscriptionV1AudioTranscriptionsPostTimestampGranularitiesType0Item(
    StrEnum
):
    SEGMENT = "segment"
    WORD = "word"

    def __str__(self) -> str:
        return str(self.value)
