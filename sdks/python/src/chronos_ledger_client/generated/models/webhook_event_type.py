from enum import StrEnum


class WebhookEventType(StrEnum):
    RESERVATION_CREATED = "reservation.created"
    RESERVATION_UPDATED = "reservation.updated"
    RESOURCE_CREATED = "resource.created"
    RESOURCE_UPDATED = "resource.updated"

    def __str__(self) -> str:
        return str(self.value)
