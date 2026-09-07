# Copyright 2026 Chronos Ledger Contributors
# Licensed under the Apache License, Version 2.0

from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.security import generate_api_key, hash_api_key, require_roles
from app.models.db import ApiKey, User

router = APIRouter()


class ApiKeyCreate(BaseModel):
    label: str = Field(min_length=1, max_length=100)
    user_id: str = Field(min_length=1, max_length=50)


class ApiKeyResponse(BaseModel):
    id: int
    key_prefix: str
    label: str
    user_id: str
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
    raw = generate_api_key()
    row = ApiKey(
        key_hash=hash_api_key(raw),
        key_prefix=raw[:12],
        label=payload.label,
        user_id=bound_user.id,
    )
    db.add(row)
    db.commit()
    db.refresh(row)
    return ApiKeyCreated(
        id=row.id,
        key_prefix=row.key_prefix,
        label=row.label,
        user_id=row.user_id,
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
