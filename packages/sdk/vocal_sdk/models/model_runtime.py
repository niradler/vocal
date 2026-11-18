from enum import StrEnum


class ModelRuntime(StrEnum):
    EXTERNAL = "external"
    IN_PROCESS = "in_process"

    def __str__(self) -> str:
        return str(self.value)
