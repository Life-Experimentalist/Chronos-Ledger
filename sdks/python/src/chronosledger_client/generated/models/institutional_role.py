from enum import StrEnum


class InstitutionalRole(StrEnum):
    MEMBER = "MEMBER"
    ORG_ADMIN = "ORG_ADMIN"
    STAFF = "STAFF"
    UNIT_ADMIN = "UNIT_ADMIN"

    def __str__(self) -> str:
        return str(self.value)
