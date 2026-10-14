from enum import StrEnum


class LogVerificationState(StrEnum):
    PENDING_VERIFICATION = "PENDING_VERIFICATION"
    VERIFIED_APPROVED = "VERIFIED_APPROVED"
    VERIFIED_DENIED = "VERIFIED_DENIED"

    def __str__(self) -> str:
        return str(self.value)
