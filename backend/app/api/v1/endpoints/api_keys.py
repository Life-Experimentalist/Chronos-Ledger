# Copyright 2026 Chronos Ledger Contributors
# Licensed under the Apache License, Version 2.0

import re
from datetime import UTC, datetime

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, Field, field_validator
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.security import generate_api_key, hash_api_key, require_roles
from app.models.db import WILDCARD_SCOPE, ApiKey, User

router = APIRouter()


SCOPE_PATTERN = re.compile(r"^(\*|[a-z][a-z-]*:(read|write))$")


class ApiKeyCreate(BaseModel):
    label: str = Field(min_length=1, max_length=100)
    user_id: str = Field(min_length=1, max_length=50)
    scopes: list[str] | None = Field(
        default=None,
        description=(
            "Areas this key may reach, as '<area>:read' or '<area>:write', "
            "where the area is the path segment after /api/v1. Omitted means "
            "'*': everything the bound user can do."
        ),
    )
    expires_at: datetime | None = None

    @field_validator("scopes")
    @classmethod
    def _known_shape(cls, value: list[str] | None) -> list[str] | None:
        if value is None:
            return None
        if not value:
            raise ValueError("scopes cannot be empty; omit the field for an unrestricted key")
        for scope in value:
            if not SCOPE_PATTERN.match(scope):
                raise ValueError(
                    f"'{scope}' is not a scope: expected '<area>:read', '<area>:write' or '*'"
                )
        return value


class ApiKeyResponse(BaseModel):
    id: int
    key_prefix: str
    label: str
    user_id: str
    scopes: str
    expires_at: datetime | None
    created_at: datetime | None

    model_config = {"from_attributes": True}


class ApiKeyCreated(ApiKeyResponse):
    # The raw key appears exactly once, in this response. Only its hash
    # is stored, so it cannot be shown again.
    api_key: str


@router.post("/", response_model=ApiKeyCreated, status_code=status.HTTP_201_CREATED)
def create_api_key(
    payload: ApiKeyCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_roles("SUPER_ADMIN")),
):
    bound_user = db.query(User).filter(User.id == payload.user_id).first()
    if bound_user is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"User '{payload.user_id}' not found",
        )
    if bound_user.deactivated_at is not None:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"User '{payload.user_id}' is deactivated",
        )
    # Normalised once and then stored, so the value the gate compares later is
    # the value this check passed, not a naive twin of it.
    expires_at = payload.expires_at
    if expires_at is not None:
        if expires_at.tzinfo is None:
            expires_at = expires_at.replace(tzinfo=UTC)
        if expires_at <= datetime.now(UTC):
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail="expires_at is in the past; the key would be dead on arrival",
            )
    raw = generate_api_key()
    row = ApiKey(
        key_hash=hash_api_key(raw),
        key_prefix=raw[:12],
        label=payload.label,
        user_id=bound_user.id,
        scopes=",".join(sorted(set(payload.scopes))) if payload.scopes else WILDCARD_SCOPE,
        expires_at=expires_at,
    )
    db.add(row)
    db.commit()
    db.refresh(row)
    return ApiKeyCreated(
        id=row.id,
        key_prefix=row.key_prefix,
        label=row.label,
        user_id=row.user_id,
        scopes=row.scopes,
        expires_at=row.expires_at,
        created_at=row.created_at,
        api_key=raw,
    )


@router.get("/", response_model=list[ApiKeyResponse])
def list_api_keys(
    db: Session = Depends(get_db),
    current_user: User = Depends(require_roles("SUPER_ADMIN")),
):
    return db.query(ApiKey).order_by(ApiKey.id).all()


@router.delete("/{key_id}", status_code=status.HTTP_204_NO_CONTENT)
def revoke_api_key(
    key_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_roles("SUPER_ADMIN")),
):
    row = db.query(ApiKey).filter(ApiKey.id == key_id).first()
    if row is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"API key {key_id} not found",
        )
    db.delete(row)
    db.commit()
