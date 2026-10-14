from enum import StrEnum


class UnmetRequirementTargetKind(StrEnum):
    PERSON = "PERSON"
    ROOM = "ROOM"

    def __str__(self) -> str:
        return str(self.value)
