from enum import StrEnum


class ExecutionMode(StrEnum):
    ONLINE_STREAM = "ONLINE_STREAM"
    PHYSICAL = "PHYSICAL"

    def __str__(self) -> str:
        return str(self.value)
