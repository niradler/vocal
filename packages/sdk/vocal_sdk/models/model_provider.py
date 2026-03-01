from enum import Enum


class ModelProvider(str, Enum):
    CUSTOM = "custom"
    HUGGINGFACE = "huggingface"
    LOCAL = "local"

    def __str__(self) -> str:
        return str(self.value)
