from enum import StrEnum


class RequirementCreateEnforcement(StrEnum):
    ADVISORY = "ADVISORY"
    REQUIRED = "REQUIRED"

    def __str__(self) -> str:
        return str(self.value)
