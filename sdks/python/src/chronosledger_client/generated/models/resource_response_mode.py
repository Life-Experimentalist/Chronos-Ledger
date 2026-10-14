from enum import StrEnum


class ResourceResponseMode(StrEnum):
    EXCLUSIVE = "EXCLUSIVE"
    POOLED = "POOLED"
    SHARED = "SHARED"

    def __str__(self) -> str:
        return str(self.value)
