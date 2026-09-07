# Copyright 2026 Chronos Ledger Contributors
# Licensed under the Apache License, Version 2.0

import hashlib
import secrets
from datetime import UTC, datetime, timedelta
from typing import Any

import bcrypt
import jwt
from fastapi import Depends, Header, HTTPException, Request, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from jwt.exceptions import InvalidTokenError
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.core.database import get_db

settings = get_settings()
bearer_scheme = HTTPBearer(auto_error=False)


def hash_password(plain: str) -> str:
    return bcrypt.hashpw(plain.encode("utf-8"), bcrypt.gensalt()).decode("utf-8")


def verify_password(plain: str, hashed: str) -> bool:
    return bcrypt.checkpw(plain.encode("utf-8"), hashed.encode("utf-8"))


# Long enough that a generated password is not worth guessing, short enough
# that an admin can read one off a screen and hand it to somebody.
GENERATED_PASSWORD_BYTES = 12


def generate_password() -> str:
    """A random password for an account nobody has chosen one for yet.

    The raw value is handed to the caller exactly once and never stored:
    the database keeps only the bcrypt hash, as it does for every account.
    """
    return secrets.token_urlsafe(GENERATED_PASSWORD_BYTES)


def create_access_token(subject: str, extra: dict[str, Any] | None = None) -> str:
    expire = datetime.now(UTC) + timedelta(minutes=settings.jwt_access_token_expire_minutes)
    payload = {"sub": subject, "exp": expire, **(extra or {})}
    return jwt.encode(payload, settings.jwt_secret_signing_key, algorithm=settings.jwt_algorithm)


def generate_refresh_token() -> str:
    return secrets.token_urlsafe(48)


def hash_refresh_token(raw: str) -> str:
    """Refresh tokens are stored hashed, so a database leak leaks no sessions."""
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()


def generate_api_key() -> str:
    return "ck_" + secrets.token_urlsafe(36)


def hash_api_key(raw: str) -> str:
    """API keys are stored hashed, so a database leak leaks no credentials."""
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()


def decode_token(token: str) -> dict[str, Any] | None:
    try:
        return jwt.decode(
            token, settings.jwt_secret_signing_key, algorithms=[settings.jwt_algorithm]
        )
    except InvalidTokenError:
        return None


def verify_jwt_token_string(token: str) -> dict[str, Any] | None:
    return decode_token(token)


def get_current_user_id(
    credentials: HTTPAuthorizationCredentials | None = Depends(bearer_scheme),
    api_key: str | None = Header(default=None, alias="X-API-Key"),
    db: Session = Depends(get_db),
) -> str:
    if credentials is not None:
        payload = decode_token(credentials.credentials)
        if not payload or "sub" not in payload:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid or expired token",
                headers={"WWW-Authenticate": "Bearer"},
            )
        return payload["sub"]

    if api_key:
        from app.models.db import ApiKey

        row = db.query(ApiKey).filter(ApiKey.key_hash == hash_api_key(api_key)).first()
        if row is None:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid API key",
            )
        return row.user_id

    raise HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Not authenticated",
        headers={"WWW-Authenticate": "Bearer"},
    )


# While an admin still holds the seeded initial password, only these paths work.
_FIRST_LOGIN_EXEMPT_SUFFIXES = ("/auth/me", "/auth/change-password")


def get_current_user(
    request: Request,
    user_id: str = Depends(get_current_user_id),
    db: Session = Depends(get_db),
):
    from app.models.db import User

    user = db.query(User).filter(User.id == user_id).first()
    if not user:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="User not found")
    if (
        user.initial_login_state
        and user.role_type.value in ("SUPER_ADMIN", "UNIT_ADMIN")
        and not request.url.path.endswith(_FIRST_LOGIN_EXEMPT_SUFFIXES)
    ):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Change the initial password before using other endpoints",
        )
    return user


def ensure_unit_scope(current_user, unit_code) -> None:
    """A UNIT_ADMIN may only act inside their own unit; other roles pass."""
    if current_user.role_type.value == "UNIT_ADMIN" and unit_code != current_user.unit_code:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Outside your unit",
        )


def require_roles(*roles: str):
    def checker(current_user=Depends(get_current_user)):
        if current_user.role_type.value not in roles:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN, detail="Insufficient permissions"
            )
        return current_user

    return checker
