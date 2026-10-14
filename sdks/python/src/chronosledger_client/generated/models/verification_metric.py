from enum import StrEnum


class VerificationMetric(StrEnum):
    ABSENT = "ABSENT"
    LATE = "LATE"
    PRESENT = "PRESENT"

    def __str__(self) -> str:
        return str(self.value)
