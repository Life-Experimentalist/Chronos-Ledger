from enum import StrEnum


class InstitutionalRole(StrEnum):
    MEMBER = "MEMBER"
    STAFF = "STAFF"
    SUPER_ADMIN = "SUPER_ADMIN"
    UNIT_ADMIN = "UNIT_ADMIN"

    def __str__(self) -> str:
        return str(self.value)
