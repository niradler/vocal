from enum import StrEnum


class ModelProvider(StrEnum):
    CUSTOM = "custom"
    HUGGINGFACE = "huggingface"
    LOCAL = "local"

    def __str__(self) -> str:
        return str(self.value)
