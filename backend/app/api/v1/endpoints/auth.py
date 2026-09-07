# Copyright 2026 Chronos Ledger Contributors
# Licensed under the Apache License, Version 2.0

from datetime import UTC, datetime, timedelta

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.core.database import get_db
from app.core.security import (
    create_access_token,
    generate_refresh_token,
    get_current_user,
    hash_password,
    hash_refresh_token,
    verify_password,
)
from app.models.db import RefreshToken, User, generate_feed_token
from app.schemas.auth import ChangePasswordRequest, LoginRequest, RefreshRequest, TokenResponse

settings = get_settings()
router = APIRouter()


def _mint_refresh_token(db: Session, user_id: str) -> str:
    """The caller gets the raw token; the database keeps only its hash."""
    raw = generate_refresh_token()
    db.add(
        RefreshToken(
            token_hash=hash_refresh_token(raw),
            user_id=user_id,
            expires_at=datetime.now(UTC) + timedelta(days=settings.jwt_refresh_token_expire_days),
        )
    )
    return raw


@router.post("/login", response_model=TokenResponse)
def login(payload: LoginRequest, db: Session = Depends(get_db)):
    user = db.query(User).filter(User.email_address == payload.email).first()
    if not user or not verify_password(payload.password, user.credential_secure_hash):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid credentials")

    refresh_token = _mint_refresh_token(db, user.id)
    db.commit()
    token = create_access_token(subject=user.id, extra={"role": user.role_type.value})
    return TokenResponse(
        access_token=token,
        refresh_token=refresh_token,
        user_id=user.id,
        role=user.role_type.value,
        full_name=user.full_name,
        initial_login_state=user.initial_login_state,
    )


@router.post("/refresh", response_model=TokenResponse)
def refresh(payload: RefreshRequest, db: Session = Depends(get_db)):
    row = (
        db.query(RefreshToken)
        .filter(RefreshToken.token_hash == hash_refresh_token(payload.refresh_token))
        .first()
    )
    if row is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid refresh token"
        )

    # SQLite hands naive datetimes back; Postgres keeps the timezone.
    expires_at = row.expires_at if row.expires_at.tzinfo else row.expires_at.replace(tzinfo=UTC)
    if expires_at < datetime.now(UTC):
        db.delete(row)
        db.commit()
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED, detail="Refresh token expired"
        )

    user = db.get(User, row.user_id)
    db.delete(row)  # single use: a refresh token works exactly once
    if user is None:
        db.commit()
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid refresh token"
        )

    new_refresh = _mint_refresh_token(db, user.id)
    db.commit()
    return TokenResponse(
        access_token=create_access_token(subject=user.id, extra={"role": user.role_type.value}),
        refresh_token=new_refresh,
        user_id=user.id,
        role=user.role_type.value,
        full_name=user.full_name,
        initial_login_state=user.initial_login_state,
    )


@router.post("/logout")
def logout(payload: RefreshRequest, db: Session = Depends(get_db)):
    row = (
        db.query(RefreshToken)
        .filter(RefreshToken.token_hash == hash_refresh_token(payload.refresh_token))
        .first()
    )
    if row is not None:
        db.delete(row)
        db.commit()
    return {"message": "Logged out"}


@router.post("/change-password")
def change_password(
    payload: ChangePasswordRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    if not verify_password(payload.current_password, current_user.credential_secure_hash):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST, detail="Current password is incorrect"
        )

    current_user.credential_secure_hash = hash_password(payload.new_password)
    current_user.initial_login_state = False
    # A password change also invalidates the shareable calendar feed URL.
    current_user.calendar_feed_token = generate_feed_token()
    # A password change signs out every device: all refresh tokens die with it.
    db.query(RefreshToken).filter(RefreshToken.user_id == current_user.id).delete()
    db.commit()
    return {"message": "Password updated successfully"}


@router.get("/me")
def get_me(current_user: User = Depends(get_current_user)):
    return {
        "id": current_user.id,
        "full_name": current_user.full_name,
        "email_address": current_user.email_address,
        "role_type": current_user.role_type.value,
        "unit_code": current_user.unit_code,
        "current_occupancy_index": current_user.current_occupancy_index.value,
        "initial_login_state": current_user.initial_login_state,
    }
