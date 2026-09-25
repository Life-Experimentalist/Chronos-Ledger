# Copyright 2026 Chronos Ledger Contributors
# Licensed under the Apache License, Version 2.0

import logging
import uuid
from datetime import UTC, datetime, timedelta

from fastapi import APIRouter, Depends, HTTPException, Request, status
from sqlalchemy.exc import IntegrityError
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
    FederatedTokenRequest,
    LoginRequest,
    RefreshRequest,
    TokenResponse,
)
from app.services import federated_identity

settings = get_settings()
router = APIRouter()
logger = logging.getLogger(__name__)

# How long after its use a refresh token can come back without that counting
# as reuse. The web client keeps one refresh token per browser, shared by its
# tabs, and a tab that refreshes a moment after another presents the token the
# first has just spent. Treating that as theft would end the session the first
# tab has just renewed. The window is short because it is also where reuse goes
# unnoticed: a thief who spends a token first, followed by its owner inside the
# window, keeps the session.
REUSE_GRACE = timedelta(seconds=10)


def _as_utc(moment: datetime) -> datetime:
    # SQLite hands naive datetimes back; Postgres keeps the timezone.
    return moment if moment.tzinfo else moment.replace(tzinfo=UTC)


def _mint_refresh_token(db: Session, user_id: str, family_id: str | None = None) -> str:
    """The caller gets the raw token; the database keeps only its hash.

    A sign-in starts a new family; a refresh passes the family of the token
    it replaces.
    """
    raw = generate_refresh_token()
    db.add(
        RefreshToken(
            token_hash=hash_refresh_token(raw),
            user_id=user_id,
            family_id=family_id or str(uuid.uuid4()),
            expires_at=datetime.now(UTC) + timedelta(days=settings.jwt_refresh_token_expire_days),
        )
    )
    return raw


@router.post("/login", operation_id="auth.login", response_model=TokenResponse)
def login(request: Request, payload: LoginRequest, db: Session = Depends(get_db)):
    # Read at call time rather than off the module-level binding above, so
    # that changing a limit does not need a restart to take effect anywhere
    # the settings cache is cleared.
    limits = get_settings()
    address = rate_limit.caller_address(request)
    account = payload.email_address.lower()
    window = rate_limit.LOGIN_WINDOW_SECONDS
    per_address = limits.rate_limit_login_per_ip
    per_account = limits.rate_limit_login_per_email
    # Checked before the lookup and the bcrypt, so a flood costs the server
    # a Redis round trip rather than three hundred milliseconds of hashing.
    rate_limit.guard("login-ip", address, per_address, window, "sign-in attempts from this address")
    rate_limit.guard(
        "login-email", account, per_account, window, "sign-in attempts for this account"
    )

    user = db.query(User).filter(User.email_address == payload.email_address).first()
    # An address that matches no account still pays for a bcrypt comparison,
    # against a hash of a string nobody holds. `not user` comes second so the
    # comparison actually runs; short-circuiting past it is the leak. A
    # deactivated account gets the same answer after the same comparison.
    stored = user.credential_secure_hash if user else ABSENT_ACCOUNT_HASH
    if not verify_password(payload.password, stored) or not user or user.deactivated_at is not None:
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


def _issue(note: federated_identity.VerifiedNote, db: Session) -> tuple[User, str]:
    """The account a verified note belongs to, and a refresh token for it.

    Committed here, before any token is minted, so a note that could not be
    turned into a session does not hand one out. A failed commit therefore
    burns the note: its jti was spent during verification and the same note
    cannot be sent again. That is deliberate and it is the safe direction, so
    the commit does not belong any later than this.

    The second attempt is for two first-time notes for the same subject in
    flight together, which one double-click on a sign-in button produces. Both
    find no link, both insert, and the loser meets a unique constraint at the
    flush inside `account_for` or at the commit, depending on the database.
    Running the whole thing again finds the row the winner committed, and
    answers with a session or a 409 rather than with a 500. Once is enough,
    because what the second attempt would collide with is committed by then.
    """
    for last in (False, True):
        try:
            user = federated_identity.account_for(note, db)
            raw = _mint_refresh_token(db, user.id)
            db.commit()
            return user, raw
        except IntegrityError:
            db.rollback()
            if last:
                raise


@router.post("/federated", operation_id="auth.federated", response_model=TokenResponse)
def federated(request: Request, payload: FederatedTokenRequest, db: Session = Depends(get_db)):
    """Trade a note from an outside issuer for a session here.

    The note is verified, the account it names is found or created, and the
    answer is the same `TokenResponse` a password sign-in gives, so nothing in
    a client changes about holding a session. Every decision about whether a
    note is acceptable lives in `services/federated_identity.py`; this maps
    the answers onto status codes.

    Off is a 404 and not a 403, because whether an instance has an integration
    at all is not something probing it should reveal. Every verification
    failure is one 401 carrying one message, so the response cannot be used to
    find out which part of a forged note was wrong; the reason goes to the log
    instead. The two refusals that are not about the note get their own
    answers: 409 when the address it carries already belongs to an account,
    and 422 when a first-time subject arrives with no address to create one
    from, which is a note that verified and then could not be acted on.

    There is no rate budget here, unlike `/auth/login`. A note is signed by a
    key an operator registered, so guessing one is not the attack this route
    has; replay and lifetime are, and the cache and the cap answer those.
    """
    try:
        note = federated_identity.verify_note(payload.token, db)
    except federated_identity.FederationDisabled:
        # Not logged as a refusal, because nothing was wrong with the request.
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Not Found") from None
    except federated_identity.ReplayCacheDown as unreachable:
        # Logged already, where it happened, by the code that knows why.
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Federated sign-in is temporarily unavailable",
        ) from unreachable
    except federated_identity.NoteRefused as refused:
        # The reason names the issuer, and the kid wherever the kid is the part
        # that was wrong. The note itself never reaches the log.
        logger.warning("federated sign-in refused: %s", refused)
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid federated token"
        ) from refused

    try:
        user, refresh_token = _issue(note, db)
    except federated_identity.NoEmailToProvisionWith as unusable:
        logger.warning("federated sign-in could not become an account: %s", unusable)
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
            detail="This note carries no email address an account can be created from",
        ) from unusable
    except federated_identity.EmailAlreadyTaken as taken:
        # The address stays out of the log: it is a claim out of the note, and
        # which issuer vouched for which subject is enough to find the clash.
        logger.warning(
            "federated sign-in refused, that address is already an account: %s vouched for %s",
            note.issuer.issuer,
            note.subject,
        )
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="The address in this note already belongs to an account",
        ) from taken
    except federated_identity.NoteRefused as refused:
        # A deactivated account and a link pointing at nothing land here, and
        # the caller is told the same thing as for any other refusal.
        logger.warning("federated sign-in refused: %s", refused)
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid federated token"
        ) from refused

    # Read by `core/audit.py` once the response has gone out, so the record
    # names who got the session; on a first sign-in it reads as the account
    # having been created by its own arrival, which is what happened. Password
    # sign-in sets nothing here and its records name nobody, which is a gap
    # there rather than a convention to follow.
    request.state.actor_id = user.id
    token = create_access_token(subject=user.id, extra={"role": user.role_type.value})
    return TokenResponse(
        access_token=token,
        refresh_token=refresh_token,
        user_id=user.id,
        role=user.role_type.value,
        full_name=user.full_name,
        initial_login_state=user.initial_login_state,
    )


@router.post("/refresh", operation_id="auth.refresh", response_model=TokenResponse)
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

    now = datetime.now(UTC)
    if row.consumed_at is not None:
        if now - _as_utc(row.consumed_at) > REUSE_GRACE:
            # Two parties hold one token and nothing here says which is the
            # thief, so every token from that sign-in goes and both have to
            # sign in again, which only the owner can.
            user_id, family_id = row.user_id, row.family_id
            db.query(RefreshToken).filter(RefreshToken.family_id == family_id).delete(
                synchronize_session=False
            )
            db.commit()
            logger.warning(
                "A used refresh token for user %s was presented again. "
                "Every session from that sign-in has been ended.",
                user_id,
            )
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Refresh token reused; sign in again",
            )
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED, detail="Refresh token already used"
        )

    if _as_utc(row.expires_at) < now:
        db.delete(row)
        db.commit()
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED, detail="Refresh token expired"
        )

    # Spent by a conditional update rather than by setting the attribute, so
    # that two requests carrying the same token at once cannot both get past
    # the check above and fork the family into two live sessions. The one that
    # finds nothing left to update arrived second.
    spent = (
        db.query(RefreshToken)
        .filter(RefreshToken.id == row.id, RefreshToken.consumed_at.is_(None))
        .update({RefreshToken.consumed_at: now}, synchronize_session=False)
    )
    if not spent:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED, detail="Refresh token already used"
        )

    user = db.get(User, row.user_id)
    if user is None or user.deactivated_at is not None:
        db.commit()
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid refresh token"
        )

    new_refresh = _mint_refresh_token(db, user.id, row.family_id)
    db.commit()
    return TokenResponse(
        access_token=create_access_token(subject=user.id, extra={"role": user.role_type.value}),
        refresh_token=new_refresh,
        user_id=user.id,
        role=user.role_type.value,
        full_name=user.full_name,
        initial_login_state=user.initial_login_state,
    )


@router.post("/logout", operation_id="auth.logout")
def logout(payload: RefreshRequest, db: Session = Depends(get_db)):
    # The refresh token is the only credential this takes. Holding it is a
    # stronger claim than holding an access token, and asking for an access
    # token as well would fail the sign-out of whoever comes back to an idle
    # tab, whose access token lapsed long ago.
    row = (
        db.query(RefreshToken)
        .filter(RefreshToken.token_hash == hash_refresh_token(payload.refresh_token))
        .first()
    )
    if row is not None:
        # The family rather than the row, so the used tokens it replaced go too.
        db.query(RefreshToken).filter(RefreshToken.family_id == row.family_id).delete(
            synchronize_session=False
        )
        db.commit()
    return {"message": "Logged out"}


@router.post(
    "/change-password", operation_id="auth.changePassword", response_model=ChangePasswordResponse
)
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


@router.get("/me", operation_id="auth.getMe")
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
