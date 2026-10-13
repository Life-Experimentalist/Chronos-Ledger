# Copyright 2026 Chronos Ledger Contributors
# Licensed under the Apache License, Version 2.0
"""Identity asserted by a host program, for the embedded flavour.

When Chronos runs as a hidden child process of another program
(app.embedded), nobody signs in to Chronos. The host already knows who its
user is, and it says so on every request:

    Authorization: Host <secret>          the host's own secret, checked here
    X-Chronos-Actor: <id>                 the host's stable id for the person
    X-Chronos-Actor-Role: <role>          an InstitutionalRole name
    X-Chronos-Actor-Name: <name>          optional
    X-Chronos-Actor-Email: <address>      optional
    X-Chronos-Actor-Unit: <unit code>     optional; empty clears, absent leaves it

The secret is checked by HostSecretMiddleware on every request but the health
checks, including routes that need no account. host_actor replaces
app.core.security.get_current_user_id, so everything built on it (the
current-user lookup, the role and unit checks, the audit record) runs
unchanged, and a JWT or an API key is never looked at: there is no code path
left that reads one.

The actor id is the Chronos user id. No link table: the host's ids are
stable by contract, an account is made the first time an id is seen, and
the host is authoritative for the role, the name and the unit, which are
brought up to date on every request. The federated-identity mapping was not reused because
it does the opposite on each count: it refuses administrators, never changes
a role after the first sign-in, and needs an email address.

The id `system` is reserved for the host itself. seed_system_account makes
that account, an ORG_ADMIN, when the database is prepared.
"""

import hmac
import secrets

from fastapi import Depends, Header, Request, status
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session
from starlette.responses import JSONResponse

from app.core.database import get_db
from app.core.emails import normalize_email
from app.core.errors import ChronosError, ErrorCode, error_body
from app.core.security import hash_password
from app.models.db import InstitutionalRole, User

HOST_SECRET_ENV = "CHRONOS_HOST_SECRET"
MINIMUM_HOST_SECRET_LENGTH = 32
SYSTEM_ACTOR_ID = "system"
# users.id, users.full_name, users.email_address and users.unit_code column
# widths. The unit limit is checked here because SQLite does not enforce it.
ACTOR_ID_LIMIT = 50
NAME_LIMIT = 120
EMAIL_LIMIT = 120
UNIT_LIMIT = 50
# A domain that can never receive mail (RFC 2606), for accounts the host
# names without an address. The column is NOT NULL and unique.
PLACEHOLDER_EMAIL_DOMAIN = "host.invalid"
HEALTH_PREFIX = "/health"


def check_host_secret(secret: str | None) -> str:
    """The secret as the server keeps it, or a ValueError saying what is wrong."""
    if secret is None or len(secret) < MINIMUM_HOST_SECRET_LENGTH:
        raise ValueError(
            f"a host secret of at least {MINIMUM_HOST_SECRET_LENGTH} characters is required: "
            f"set {HOST_SECRET_ENV}, or pass --secret-from-stdin and write it as the first line"
        )
    return secret


class HostSecretMiddleware:
    """401 for any request that does not carry the host's secret.

    A plain ASGI middleware rather than a dependency, for the same reason
    app.core.audit is one: a route cannot be added without being covered,
    and the public routes (the labels, a guest's own visit) need it too. The
    health checks are the one exception, so a host can poll them while
    waiting for the ready line.
    """

    def __init__(self, app, secret: str):
        self.app = app
        self._expected = f"Host {check_host_secret(secret)}".encode()

    async def __call__(self, scope, receive, send):
        if scope["type"] != "http" or scope["path"].startswith(HEALTH_PREFIX):
            await self.app(scope, receive, send)
            return
        presented = next(
            (value for name, value in scope["headers"] if name == b"authorization"), b""
        )
        if not hmac.compare_digest(presented, self._expected):
            response = JSONResponse(
                status_code=status.HTTP_401_UNAUTHORIZED,
                content=error_body(ErrorCode.NOT_AUTHENTICATED, "Not authenticated"),
                headers={"WWW-Authenticate": "Host"},
            )
            await response(scope, receive, send)
            return
        await self.app(scope, receive, send)


def host_actor(
    request: Request,
    actor_id: str | None = Header(default=None, alias="X-Chronos-Actor"),
    role: str | None = Header(default=None, alias="X-Chronos-Actor-Role"),
    name: str | None = Header(default=None, alias="X-Chronos-Actor-Name"),
    email: str | None = Header(default=None, alias="X-Chronos-Actor-Email"),
    unit: str | None = Header(default=None, alias="X-Chronos-Actor-Unit"),
    db: Session = Depends(get_db),
) -> str:
    """The account the host says is calling, made or brought up to date.

    Stands in for app.core.security.get_current_user_id in the embedded app.
    Returns the user id and puts it on the request state for the audit log,
    exactly as the original does.
    """
    actor_id = (actor_id or "").strip()
    if not actor_id or len(actor_id) > ACTOR_ID_LIMIT:
        raise ChronosError(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=f"X-Chronos-Actor is required, at most {ACTOR_ID_LIMIT} characters",
            code=ErrorCode.NOT_AUTHENTICATED,
        )
    if actor_id == SYSTEM_ACTOR_ID:
        # The host itself: the seeded administrator, whatever role or unit
        # it sends.
        role_type = InstitutionalRole.ORG_ADMIN
        unit = None
    else:
        try:
            role_type = InstitutionalRole((role or "").strip())
        except ValueError:
            names = ", ".join(member.value for member in InstitutionalRole)
            raise ChronosError(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"X-Chronos-Actor-Role must be one of {names}",
                code=ErrorCode.INVALID_VALUE,
            ) from None
    if email is not None:
        email = normalize_email(email)
        if not email or len(email) > EMAIL_LIMIT:
            raise ChronosError(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"X-Chronos-Actor-Email must be an address of at most {EMAIL_LIMIT} characters",
                code=ErrorCode.INVALID_VALUE,
            )
    name = (name or "").strip()[:NAME_LIMIT] or None
    # Three states: absent leaves the unit as it is, so a host that sets it
    # through the users API keeps working; empty clears it; a code sets it.
    if unit is not None:
        unit = unit.strip()
        if len(unit) > UNIT_LIMIT:
            raise ChronosError(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"X-Chronos-Actor-Unit must be a unit code of at most {UNIT_LIMIT} characters",
                code=ErrorCode.INVALID_VALUE,
            )

    user = db.get(User, actor_id)
    if user is None:
        _provision(db, actor_id, role_type, name, email, unit)
    elif _bring_up_to_date(user, role_type, name, email, unit):
        _save(db)
    request.state.actor_id = actor_id
    return actor_id


def _provision(db: Session, actor_id: str, role_type: InstitutionalRole, name, email, unit) -> None:
    """The account for an id seen for the first time."""
    db.add(
        User(
            id=actor_id,
            full_name=name or actor_id,
            email_address=email or f"{actor_id}@{PLACEHOLDER_EMAIL_DOMAIN}",
            # Nobody signs in with it. Hashed all the same, so a database
            # later served by the standalone or container flavour holds a
            # password that fails to verify rather than one that fails to parse.
            credential_secure_hash=hash_password(secrets.token_urlsafe(32)),
            role_type=role_type,
            unit_code=unit or None,
            initial_login_state=False,
        )
    )
    try:
        db.commit()
    except IntegrityError:
        db.rollback()
        # Two first-sight requests for one id can arrive together: both found
        # no account, both inserted, and the later insert is refused on the
        # primary key. The account is there now, so this request carries on
        # as one for a known actor, which may still find the email taken.
        # Only when the account is still absent was the refusal about the
        # email in the first place.
        user = db.get(User, actor_id)
        if user is None:
            raise _email_taken() from None
        if _bring_up_to_date(user, role_type, name, email, unit):
            _save(db)


def _bring_up_to_date(user: User, role_type: InstitutionalRole, name, email, unit) -> bool:
    """Apply what the host asserts. True when something changed.

    Only then does the request commit: on the SQLite profile every commit
    takes the one write lock, and most requests change nothing here.
    """
    changed = False
    if user.role_type != role_type:
        user.role_type = role_type
        changed = True
    if name and user.full_name != name:
        user.full_name = name
        changed = True
    if email and user.email_address != email:
        user.email_address = email
        changed = True
    if unit is not None and user.unit_code != (unit or None):
        user.unit_code = unit or None
        changed = True
    # The first-login gate in get_current_user is for Chronos-issued
    # passwords, which no account here has. Also clears it for an account
    # the standalone flavour seeded, should a host assert its id.
    if user.initial_login_state:
        user.initial_login_state = False
        changed = True
    return changed


def _save(db: Session) -> None:
    try:
        db.commit()
    except IntegrityError:
        db.rollback()
        raise _email_taken() from None


def _email_taken() -> ChronosError:
    return ChronosError(
        status_code=status.HTTP_409_CONFLICT,
        detail="X-Chronos-Actor-Email already belongs to another account",
        code=ErrorCode.EMAIL_TAKEN,
    )


def seed_system_account(db: Session) -> None:
    """The account the host acts as itself, made once. Nothing if it is there."""
    if db.get(User, SYSTEM_ACTOR_ID) is not None:
        return
    db.add(
        User(
            id=SYSTEM_ACTOR_ID,
            full_name="Host system",
            email_address=f"{SYSTEM_ACTOR_ID}@{PLACEHOLDER_EMAIL_DOMAIN}",
            credential_secure_hash=hash_password(secrets.token_urlsafe(32)),
            role_type=InstitutionalRole.ORG_ADMIN,
            initial_login_state=False,
        )
    )
    db.commit()
