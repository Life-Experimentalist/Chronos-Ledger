from enum import StrEnum


class ReservationResponseStatus(StrEnum):
    CANCELLED = "CANCELLED"
    HELD = "HELD"

    def __str__(self) -> str:
        return str(self.value)
