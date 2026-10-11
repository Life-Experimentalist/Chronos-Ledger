from enum import StrEnum


class RoleMapEntryResponseRoleType(StrEnum):
    MEMBER = "MEMBER"
    STAFF = "STAFF"

    def __str__(self) -> str:
        return str(self.value)
