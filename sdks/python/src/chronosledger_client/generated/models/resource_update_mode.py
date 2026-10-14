from enum import StrEnum


class ResourceUpdateMode(StrEnum):
    EXCLUSIVE = "EXCLUSIVE"
    POOLED = "POOLED"
    SHARED = "SHARED"

    def __str__(self) -> str:
        return str(self.value)
