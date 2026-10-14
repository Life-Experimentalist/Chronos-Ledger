from enum import StrEnum


class ReadinessDatabase(StrEnum):
    OK = "ok"
    UNAVAILABLE = "unavailable"

    def __str__(self) -> str:
        return str(self.value)
