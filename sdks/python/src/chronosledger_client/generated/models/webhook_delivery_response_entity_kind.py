from enum import StrEnum


class WebhookDeliveryResponseEntityKind(StrEnum):
    RESERVATION = "reservation"
    RESOURCE = "resource"

    def __str__(self) -> str:
        return str(self.value)
