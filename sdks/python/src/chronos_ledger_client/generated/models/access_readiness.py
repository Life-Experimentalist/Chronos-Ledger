from enum import StrEnum


class AccessReadiness(StrEnum):
    BUSY = "BUSY"
    CRITICAL_DO_NOT_DISTURB = "CRITICAL_DO_NOT_DISTURB"
    OPEN_AD_HOC = "OPEN_AD_HOC"
    VERY_FREE = "VERY_FREE"

    def __str__(self) -> str:
        return str(self.value)
