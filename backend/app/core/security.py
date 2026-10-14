# Copyright 2026 Chronos Ledger Contributors
# Licensed under the Apache License, Version 2.0

import hashlib
import secrets
from datetime import UTC, timedelta
from typing import Any

import bcrypt
import jwt
from fastapi import Depends, Header, Request, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from jwt.exceptions import InvalidTokenError
from sqlalchemy.orm import Session

from app.core import clock
from app.core.config import get_settings
from app.core.database import get_db
from app.core.errors import ChronosError, ErrorCode
from app.core.idempotency import claim
from app.core.organization import use_organization
from app.models.db import IMPERSONATE_SCOPE, WILDCARD_SCOPE

settings = get_settings()
bearer_scheme = HTTPBearer(auto_error=False)


def hash_password(plain: str) -> str:
    return bcrypt.hashpw(plain.encode("utf-8"), bcrypt.gensalt()).decode("utf-8")


def verify_password(plain: str, hashed: str) -> bool:
    return bcrypt.checkpw(plain.encode("utf-8"), hashed.encode("utf-8"))


# A bcrypt hash of a random string nobody holds, built once at import. Sign-in
# verifies against it when the address matches no account, so that a sign-in
# for an account that does not exist costs the same as one for an account with
# the wrong password. Without it the difference in response times answers "does
# this person have an account here" to anyone willing to measure.
ABSENT_ACCOUNT_HASH = hash_password(secrets.token_urlsafe(32))


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
    # Real time on purpose: PyJWT checks exp against the system clock when the
    # token comes back, so a token stamped from a host clock set in the past
    # would be dead on arrival (docs/clock.md).
    expire = clock.wall_now() + timedelta(minutes=settings.jwt_access_token_expire_minutes)
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


# No 0, 1, I, L or O: a visit code is read off a screen and typed on a phone,
# and those are the characters people misread.
VISIT_CODE_ALPHABET = "23456789ABCDEFGHJKMNPQRSTUVWXYZ"
VISIT_CODE_LENGTH = 16


def generate_visit_code() -> str:
    """The code a visitor follows their check-in with, in groups of four.

    Sixteen characters from that alphabet are about 79 bits: short enough to
    type on a phone and far past guessing. The visitor is shown it once and
    the database keeps only its hash.
    """
    raw = "".join(secrets.choice(VISIT_CODE_ALPHABET) for _ in range(VISIT_CODE_LENGTH))
    return "-".join(raw[i : i + 4] for i in range(0, VISIT_CODE_LENGTH, 4))


def hash_visit_code(code: str) -> str | None:
    """The stored form of a visit code, or None when the input cannot be one.

    Case and separators do not count, so a code typed as "abcd efgh ..." finds
    the check-in the kiosk showed as "ABCD-EFGH-...". Anything that is not
    sixteen characters once they are gone is turned away before it is hashed.
    """
    cleaned = "".join(ch for ch in code if ch.isascii() and ch.isalnum()).upper()
    if len(cleaned) != VISIT_CODE_LENGTH:
        return None
    return hashlib.sha256(cleaned.encode("utf-8")).hexdigest()


def decode_token(token: str) -> dict[str, Any] | None:
    try:
        return jwt.decode(
            token, settings.jwt_secret_signing_key, algorithms=[settings.jwt_algorithm]
        )
    except InvalidTokenError:
        return None


def verify_jwt_token_string(token: str) -> dict[str, Any] | None:
    return decode_token(token)


def required_scope(method: str, path: str) -> str | None:
    """The scope a request needs, read off the request itself.

    Every route lives under /api/v1/<area>/..., and the area is the router
    prefix: schedule, resources, attendance, users, ingestion and so on. A
    scope is that area and whether the request reads or writes, so a key can
    be issued for schedule:read without anybody having to annotate two dozen
    endpoints and without a new endpoint silently defaulting to open.

    Returns None for a path with no area, which the caller refuses. A key
    that cannot be told what it is reaching should not reach it.
    """
    parts = path.strip("/").split("/")
    if len(parts) < 3 or parts[0] != "api":
        return None
    return f"{parts[2]}:{'read' if method in ('GET', 'HEAD', 'OPTIONS') else 'write'}"


def key_allows(scopes: str, needed: str | None) -> bool:
    held = {s.strip() for s in (scopes or "").split(",") if s.strip()}
    if WILDCARD_SCOPE in held:
        return True
    return needed is not None and needed in held


def key_may_impersonate(scopes: str) -> bool:
    """Whether a key was given the impersonate scope by name.

    Not key_allows: the wildcard means every area, and impersonating is a
    permission rather than an area, so a key issued as "*" does not hold it.
    """
    return IMPERSONATE_SCOPE in {s.strip() for s in (scopes or "").split(",")}


# users.id is 50 characters, and so is the longest id a header can name.
ACTING_FOR_LIMIT = 50

# Writes a key may not make while acting for someone, whatever its scopes: each
# one issues or changes a credential or a trust, and what it hands out outlives
# the request. Acting for an administrator, a key could otherwise mint itself a
# wider key, set a password it then signs in with, or trust an issuer of its
# own, and so reach more than the key and the person allow together.
ACTING_FOR_REFUSED_SCOPES = frozenset({"auth:write", "api-keys:write", "federation:write"})


def acting_for_refused(method: str, path: str) -> bool:
    """Whether a request issues or changes a credential, so a key may not make it for someone."""
    if required_scope(method, path) in ACTING_FOR_REFUSED_SCOPES:
        return True
    return method not in ("GET", "HEAD", "OPTIONS") and path.rstrip("/").endswith("/reset-password")


def _refuse_impersonation(request: Request, status_code: int, detail: str, code: ErrorCode):
    """Mark the request for the audit log, then refuse it.

    The audit log records writes, and a read refused here would otherwise
    leave nothing, so the middleware is told to keep this one.
    """
    request.state.audit_anyway = True
    return ChronosError(status_code=status_code, detail=detail, code=code)


def get_current_user_id(
    request: Request,
    credentials: HTTPAuthorizationCredentials | None = Depends(bearer_scheme),
    api_key: str | None = Header(default=None, alias="X-API-Key"),
    acting_for: str | None = Header(default=None, alias="X-Chronos-Actor"),
    db: Session = Depends(get_db),
) -> str:
    # The person a key is speaking for, when it says. The id is put on the
    # request first and as sent, so that a refusal below is audited with what
    # was asked for. Whether the header is allowed depends on the caller and
    # is decided in each branch: it is never ignored.
    if acting_for is not None:
        acting_for = acting_for.strip()
        request.state.acting_for_user_id = acting_for[:ACTING_FOR_LIMIT] or None

    if credentials is not None:
        payload = decode_token(credentials.credentials)
        if not payload or "sub" not in payload:
            raise ChronosError(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid or expired token",
                headers={"WWW-Authenticate": "Bearer"},
                code=ErrorCode.TOKEN_INVALID,
            )
        # Read by the audit log once the response has gone out.
        request.state.actor_id = payload["sub"]
        if acting_for is not None:
            # A person signed in as themselves has nobody to speak for. The
            # organization is looked up so the refusal is filed where their
            # administrator can see it.
            from app.models.db import User

            organization_id = (
                db.query(User.organization_id)
                .filter(User.id == payload["sub"])
                .execution_options(all_organizations=True)
                .scalar()
            )
            request.state.organization_id = organization_id
            raise _refuse_impersonation(
                request,
                status.HTTP_403_FORBIDDEN,
                "Only an API key with the impersonate scope can send X-Chronos-Actor",
                ErrorCode.IMPERSONATION_NOT_ALLOWED,
            )
        claim(request, db, caller_identity(request))
        return payload["sub"]

    if api_key:
        from app.models.db import ApiKey

        row = (
            db.query(ApiKey)
            .filter(ApiKey.key_hash == hash_api_key(api_key))
            .execution_options(all_organizations=True)
            .first()
        )
        if row is None:
            raise ChronosError(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid API key",
                code=ErrorCode.API_KEY_INVALID,
            )
        # Set before the expiry and scope checks, so the audit log can say
        # which key a refused write came from. Also read by get_current_user,
        # which holds a person at the first-login gate and has no reason to
        # hold a key there.
        request.state.api_key_id = row.id
        request.state.actor_id = row.user_id
        # Expiry and scope are checked here, where the key is looked up, and
        # nowhere else. A second gate somewhere further in is a gate some
        # future endpoint forgets to stand behind.
        if row.expires_at is not None:
            expires_at = (
                row.expires_at if row.expires_at.tzinfo else row.expires_at.replace(tzinfo=UTC)
            )
            if expires_at <= clock.now():
                raise ChronosError(
                    status_code=status.HTTP_401_UNAUTHORIZED,
                    detail="API key expired",
                    code=ErrorCode.API_KEY_EXPIRED,
                )
        needed = required_scope(request.method, request.url.path)
        if not key_allows(row.scopes, needed):
            raise ChronosError(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"API key is not scoped for {needed or 'this request'}",
                code=ErrorCode.SCOPE_MISSING,
            )
        if acting_for is None:
            claim(request, db, caller_identity(request))
            return row.user_id

        # The key speaks for one person. Everything below narrows: the area
        # scope above was already checked against the key, and from here the
        # request is the named person's, so get_current_user and the role
        # checks run as them. The key can never reach more than either allows.
        # Filed under the key's organization, which the person must share.
        request.state.organization_id = row.organization_id
        if not key_may_impersonate(row.scopes):
            raise _refuse_impersonation(
                request,
                status.HTTP_403_FORBIDDEN,
                "This API key does not hold the impersonate scope",
                ErrorCode.IMPERSONATION_NOT_ALLOWED,
            )
        if acting_for_refused(request.method, request.url.path):
            raise _refuse_impersonation(
                request,
                status.HTTP_403_FORBIDDEN,
                "A key acting for someone cannot issue or change credentials",
                ErrorCode.IMPERSONATION_NOT_ALLOWED,
            )
        from app.models.db import User

        person = (
            db.query(User)
            .filter(User.id == acting_for)
            .execution_options(all_organizations=True)
            .first()
            if acting_for
            else None
        )
        # One answer for an id that does not exist, one in another
        # organization and one deactivated, so the header cannot be used to
        # find out which ids exist elsewhere.
        if (
            person is None
            or person.organization_id != row.organization_id
            or person.deactivated_at is not None
        ):
            raise _refuse_impersonation(
                request,
                status.HTTP_403_FORBIDDEN,
                "That user cannot be acted for",
                ErrorCode.IMPERSONATION_REFUSED,
            )
        # actor_id, api_key_id and organization stay the key's; get_current_user
        # binds the session to the person's organization, which is the same.
        claim(request, db, caller_identity(request))
        return person.id

    raise ChronosError(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Not authenticated",
        headers={"WWW-Authenticate": "Bearer"},
        code=ErrorCode.NOT_AUTHENTICATED,
    )


def caller_identity(request: Request) -> str:
    """Who an Idempotency-Key belongs to: the API key when one was used, else the user.

    A key and the person it is bound to are separate callers, so two services
    holding keys for one service account cannot answer each other's retries.
    Read after get_current_user_id (or host_actor) has filled in the state.
    """
    api_key_id = getattr(request.state, "api_key_id", None)
    if api_key_id is not None:
        return f"key:{api_key_id}"
    return f"user:{request.state.actor_id}"


# While an admin still holds the seeded initial password, only these paths work.
_FIRST_LOGIN_EXEMPT_SUFFIXES = ("/auth/me", "/auth/change-password")


def first_login_blocks(user) -> bool:
    """Whether this account has to choose a password before doing anything else.

    True for an admin account still holding the password it was seeded with.
    get_current_user lets two paths through regardless so the change can be
    made; a websocket has no equivalent exemption, so it asks this directly.
    """
    return user.initial_login_state and user.role_type.value in ("ORG_ADMIN", "UNIT_ADMIN")


def get_current_user(
    request: Request,
    user_id: str = Depends(get_current_user_id),
    db: Session = Depends(get_db),
):
    from app.models.db import User

    # A user id is unique in the whole deployment, and the caller's
    # organization is what this lookup finds out.
    user = (
        db.query(User).filter(User.id == user_id).execution_options(all_organizations=True).first()
    )
    if not user:
        raise ChronosError(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="User not found",
            code=ErrorCode.ACCOUNT_NOT_FOUND,
        )
    # Ahead of the key check below, so a key bound to a deactivated account
    # stops working with it. Deactivating drops the refresh tokens, which
    # leaves an access token already issued as the only way in, and this is
    # where it ends.
    if user.deactivated_at is not None:
        raise ChronosError(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Account deactivated",
            code=ErrorCode.ACCOUNT_DEACTIVATED,
        )
    # The gate moves a person off a password they were handed. A key never
    # uses that password, and issuing one already took an organization admin
    # who had
    # cleared the gate, so a request made with a key is not held. Holding it
    # left a service account at an admin role with nobody to change its
    # password, and so unusable.
    by_key = getattr(request.state, "api_key_id", None) is not None
    if (
        not by_key
        and first_login_blocks(user)
        and not request.url.path.endswith(_FIRST_LOGIN_EXEMPT_SUFFIXES)
    ):
        raise ChronosError(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Change the initial password before using other endpoints",
            code=ErrorCode.PASSWORD_CHANGE_REQUIRED,
        )
    # From here the request sees only its caller's organization
    # (app/core/organization.py), and its audit record is filed there.
    use_organization(db, user.organization_id)
    request.state.organization_id = user.organization_id
    return user


def in_unit_scope(current_user, unit_code) -> bool:
    """Whether this user may act on something belonging to that unit.

    The same rule ensure_unit_scope enforces, as an answer rather than a
    refusal, for a caller that has to fold it into a larger decision and
    should not have to catch an exception of its own making to do it.
    """
    if current_user.role_type.value != "UNIT_ADMIN":
        return True
    # A unit admin with no unit of their own has no unit to act in. Left to the
    # comparison, they would match every row that has no unit either.
    return current_user.unit_code is not None and unit_code == current_user.unit_code


def ensure_unit_scope(current_user, unit_code) -> None:
    """A UNIT_ADMIN may only act inside their own unit; other roles pass."""
    if not in_unit_scope(current_user, unit_code):
        raise ChronosError(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Outside your unit",
            code=ErrorCode.OUTSIDE_UNIT,
        )


def ensure_resource_scope(current_user, resource) -> None:
    """A unit admin may use a resource their unit owns, or one nobody owns.

    A resource with no unit_code is shared by the whole organization, so it
    is open to a unit admin the way it is to anyone. One with a unit belongs
    to it, and putting a booking or a class on it is acting inside that unit.
    """
    if resource.unit_code is not None:
        ensure_unit_scope(current_user, resource.unit_code)


def require_roles(*roles: str):
    def checker(current_user=Depends(get_current_user)):
        if current_user.role_type.value not in roles:
            raise ChronosError(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Insufficient permissions",
                code=ErrorCode.INSUFFICIENT_ROLE,
            )
        return current_user

    return checker
