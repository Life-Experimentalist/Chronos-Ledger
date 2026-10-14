from enum import StrEnum


class UnmetRequirementOwnerKind(StrEnum):
    ACTIVITY = "ACTIVITY"
    RESOURCE = "RESOURCE"

    def __str__(self) -> str:
        return str(self.value)
