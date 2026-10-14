from enum import StrEnum


class UnmetRequirementEnforcement(StrEnum):
    ADVISORY = "ADVISORY"
    REQUIRED = "REQUIRED"

    def __str__(self) -> str:
        return str(self.value)
