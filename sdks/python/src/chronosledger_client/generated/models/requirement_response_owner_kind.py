from enum import StrEnum


class RequirementResponseOwnerKind(StrEnum):
    ACTIVITY = "ACTIVITY"
    RESOURCE = "RESOURCE"

    def __str__(self) -> str:
        return str(self.value)
