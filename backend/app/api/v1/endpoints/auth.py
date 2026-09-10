# Copyright 2026 Chronos Ledger Contributors
# Licensed under the Apache License, Version 2.0

from datetime import UTC, datetime, timedelta

from fastapi import APIRouter, Depends, HTTPException, Request, status
from sqlalchemy.orm import Session

from app.core import rate_limit
from app.core.config import get_settings
from app.core.database import get_db
from app.core.security import (
    ABSENT_ACCOUNT_HASH,
    create_access_token,
    generate_refresh_token,
    get_current_user,
    hash_password,
    hash_refresh_token,
    verify_password,
)
from app.models.db import RefreshToken, User, generate_feed_token
from app.schemas.auth import (
    ChangePasswordRequest,
    ChangePasswordResponse,
    LoginRequest,
    RefreshRequest,
    TokenResponse,
)

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
def login(request: Request, payload: LoginRequest, db: Session = Depends(get_db)):
    # Read at call time rather than off the module-level binding above, so
    # that changing a limit does not need a restart to take effect anywhere
    # the settings cache is cleared.
    limits = get_settings()
    address = rate_limit.caller_address(request)
    account = payload.email.lower()
    window = rate_limit.LOGIN_WINDOW_SECONDS
    per_address = limits.rate_limit_login_per_ip
    per_account = limits.rate_limit_login_per_email
    # Checked before the lookup and the bcrypt, so a flood costs the server
    # a Redis round trip rather than three hundred milliseconds of hashing.
    rate_limit.guard("login-ip", address, per_address, window, "sign-in attempts from this address")
    rate_limit.guard(
        "login-email", account, per_account, window, "sign-in attempts for this account"
    )

    user = db.query(User).filter(User.email_address == payload.email).first()
    # An address that matches no account still pays for a bcrypt comparison,
    # against a hash of a string nobody holds. `not user` comes second so the
    # comparison actually runs; short-circuiting past it is the leak.
    stored = user.credential_secure_hash if user else ABSENT_ACCOUNT_HASH
    if not verify_password(payload.password, stored) or not user:
        # Counted on the way out, so that getting your own password right
        # never costs you a slice of your own budget. The account budget is
        # spent whether or not the account exists, because a 429 that only
        # ever arrives for real addresses is the same oracle by a slower route.
        rate_limit.spend("login-ip", address, per_address, window)
        rate_limit.spend("login-email", account, per_account, window)
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


@router.post("/change-password", response_model=ChangePasswordResponse)
def change_password(
    payload: ChangePasswordRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    if not verify_password(payload.current_password, current_user.credential_secure_hash):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST, detail="Current password is incorrect"
        )
    # The first-login gate exists to get the account off the password it was
    # handed. Setting it back to itself satisfies the flag and changes nothing.
    if payload.new_password == payload.current_password:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="The new password is the one you already have",
        )

    current_user.credential_secure_hash = hash_password(payload.new_password)
    current_user.initial_login_state = False
    # A password change also invalidates the shareable calendar feed URL.
    current_user.calendar_feed_token = generate_feed_token()
    # A password change signs out every device. Including this one would be
    # a fifteen-minute delayed bounce to the sign-in page for whoever just
    # changed their password, so the calling session is handed a replacement
    # in the response and every other session stops at its next refresh.
    db.query(RefreshToken).filter(RefreshToken.user_id == current_user.id).delete()
    refresh_token = _mint_refresh_token(db, current_user.id)
    db.commit()
    return ChangePasswordResponse(
        message="Password updated successfully", refresh_token=refresh_token
    )


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
