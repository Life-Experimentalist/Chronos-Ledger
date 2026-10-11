# Copyright 2026 Chronos Ledger Contributors
# Licensed under the Apache License, Version 2.0

from datetime import datetime

from pydantic import BaseModel, Field, field_validator

from app.models.db import InstitutionalRole


class IssuerCreate(BaseModel):
    # `issuer` is compared against the note's `iss` and never parsed, so the
    # only rule is that it is the same string the issuer actually mints.
    issuer: str = Field(min_length=1, max_length=255)
    display_name: str = Field(min_length=1, max_length=100)
    audience: str = Field(min_length=1, max_length=255)
    enabled: bool = True


class IssuerUpdate(BaseModel):
    """What can change on a registration without deleting it.

    `issuer` is not here. It is the value notes already in the wild carry, and
    editing it would silently retarget a registration rather than register a
    different issuer; that is a create and a delete.
    """

    display_name: str | None = Field(default=None, min_length=1, max_length=100)
    audience: str | None = Field(default=None, min_length=1, max_length=255)
    enabled: bool | None = None


class IssuerResponse(BaseModel):
    id: int
    issuer: str
    display_name: str
    audience: str
    enabled: bool
    created_at: datetime | None

    model_config = {"from_attributes": True}


class IssuerKeyCreate(BaseModel):
    kid: str = Field(min_length=1, max_length=100)
    public_key: str = Field(
        min_length=1,
        description=(
            "An Ed25519 public key in PEM form. Checked at registration, so a "
            "key that cannot be loaded is refused here rather than turning "
            "every note that names it into a 401 nobody can explain."
        ),
    )
    not_before: datetime | None = Field(
        default=None,
        description="When the key starts being accepted. Omitted means now.",
    )
    not_after: datetime | None = Field(
        default=None,
        description="When it stops. Omitted is a key with no planned retirement.",
    )


class IssuerKeyRetire(BaseModel):
    """Retiring a key is setting the moment it stops being accepted.

    A separate route from deleting it, because a rotation wants an overlap: the
    new key is added, the old one is given an end, and notes signed before that
    moment still verify until it passes.
    """

    not_after: datetime


class IssuerKeyResponse(BaseModel):
    id: int
    issuer_id: int
    kid: str
    # A public key. There is nothing here a leak would cost anybody, which is
    # why this route may read it back.
    public_key: str
    not_before: datetime
    not_after: datetime | None
    created_at: datetime | None

    model_config = {"from_attributes": True}


class RoleMapEntryCreate(BaseModel):
    group_claim_value: str = Field(min_length=1, max_length=200)
    role_type: InstitutionalRole = Field(
        description="`STAFF` or `MEMBER`. Neither admin role can be mapped."
    )
    unit_code: str | None = Field(default=None, max_length=50)

    @field_validator("role_type")
    @classmethod
    def _no_admin_role(cls, value: InstitutionalRole) -> InstitutionalRole:
        # The same rule as ck_federated_role_map_no_admin, here so it is a 422
        # naming the field rather than a 500 from the database. It is the one
        # rule whose failure would hand an outside system this instance.
        if value in (InstitutionalRole.ORG_ADMIN, InstitutionalRole.UNIT_ADMIN):
            raise ValueError(
                f"'{value.value}' cannot be mapped: an issuer may assert STAFF or MEMBER only"
            )
        return value


class RoleMapEntryResponse(BaseModel):
    id: int
    issuer_id: int
    group_claim_value: str
    role_type: InstitutionalRole
    unit_code: str | None

    model_config = {"from_attributes": True}


class LinkCreate(BaseModel):
    issuer_id: int
    subject: str = Field(min_length=1, max_length=255)
    user_id: str = Field(min_length=1, max_length=50)


class LinkResponse(BaseModel):
    id: int
    issuer_id: int
    subject: str
    user_id: str
    created_at: datetime | None

    model_config = {"from_attributes": True}
