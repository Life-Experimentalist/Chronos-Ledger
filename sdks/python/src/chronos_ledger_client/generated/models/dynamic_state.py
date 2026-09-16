from enum import StrEnum


class DynamicState(StrEnum):
    ADHOC_EVENT = "ADHOC_EVENT"
    INTERNAL_MEETING = "INTERNAL_MEETING"
    LUNCH = "LUNCH"
    ON_LEAVE = "ON_LEAVE"
    PROXY_SUBSTITUTE = "PROXY_SUBSTITUTE"
    SCHEDULED = "SCHEDULED"

    def __str__(self) -> str:
        return str(self.value)
