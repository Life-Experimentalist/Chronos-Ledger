from enum import StrEnum


class RequirementCreateTargetKind(StrEnum):
    PERSON = "PERSON"
    ROOM = "ROOM"

    def __str__(self) -> str:
        return str(self.value)
