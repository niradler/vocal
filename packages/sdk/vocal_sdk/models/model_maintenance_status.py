from enum import StrEnum


class ModelMaintenanceStatus(StrEnum):
    ACTIVE = "active"
    DEPRECATED = "deprecated"
    RETIRED = "retired"

    def __str__(self) -> str:
        return str(self.value)
