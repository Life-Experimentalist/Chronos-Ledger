# Copyright 2026 Chronos Ledger Contributors
# Licensed under the Apache License, Version 2.0

"""Administering the federated identity registry.

Everything here is `ORG_ADMIN`. An issuer is organization-wide and a role map
can place somebody in any unit, so a unit admin is the wrong scope for it.

These routes work whether or not `FEDERATED_IDENTITY_ENABLED` is set. An
operator has to register an issuer and a key before the exchange is worth
turning on, and the exchange route is the one that answers 404 while the
feature is off.

Nothing here is a secret. The keys are public keys, which is why they can be
read back.
"""

from datetime import UTC, datetime

from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PublicKey
from cryptography.hazmat.primitives.serialization import load_pem_public_key
from fastapi import APIRouter, Depends, status
from sqlalchemy.orm import Session

from app.core import clock
from app.core.database import get_db
from app.core.errors import ChronosError, ErrorCode
from app.core.security import require_roles
from app.models.db import (
    FederatedIdentity,
    FederatedIssuer,
    FederatedIssuerKey,
    FederatedRoleMap,
    User,
)
from app.schemas.federation import (
    IssuerCreate,
    IssuerKeyCreate,
    IssuerKeyResponse,
    IssuerKeyRetire,
    IssuerResponse,
    IssuerUpdate,
    LinkCreate,
    LinkResponse,
    RoleMapEntryCreate,
    RoleMapEntryResponse,
)
from app.services.federated_identity import ADMIN_ROLES

router = APIRouter()


def _as_utc(moment: datetime) -> datetime:
    """A naive datetime is read as UTC, the way the rest of the API reads one."""
    return moment if moment.tzinfo is not None else moment.replace(tzinfo=UTC)


def _issuer_or_404(issuer_id: int, db: Session) -> FederatedIssuer:
    row = db.query(FederatedIssuer).filter(FederatedIssuer.id == issuer_id).first()
    if row is None:
        raise ChronosError(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Issuer {issuer_id} not found",
            code=ErrorCode.NOT_FOUND,
        )
    return row


def _key_or_404(issuer_id: int, key_id: int, db: Session) -> FederatedIssuerKey:
    issuer = _issuer_or_404(issuer_id, db)
    row = (
        db.query(FederatedIssuerKey)
        .filter(FederatedIssuerKey.issuer_id == issuer.id, FederatedIssuerKey.id == key_id)
        .first()
    )
    if row is None:
        raise ChronosError(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Issuer {issuer.id} has no key {key_id}",
            code=ErrorCode.NOT_FOUND,
        )
    return row


def _load_ed25519(pem: str) -> None:
    """Refuse a key that could never verify anything.

    The same loader the verification path uses underneath, so a key that
    registers here is a key that will load there. Without this, a mistyped PEM
    is a 401 on every note that names it, with nothing in the refusal to say
    the registration is at fault.
    """
    try:
        loaded = load_pem_public_key(pem.encode())
    except Exception as exc:
        raise ChronosError(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
            detail=f"public_key is not a PEM public key: {exc}",
            code=ErrorCode.INVALID_VALUE,
        ) from exc
    if not isinstance(loaded, Ed25519PublicKey):
        raise ChronosError(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
            detail="public_key is not an Ed25519 key; notes are signed with EdDSA only",
            code=ErrorCode.INVALID_VALUE,
        )


# ──────────────────────────── issuers ────────────────────────────


@router.post(
    "/issuers",
    operation_id="federation.createIssuer",
    response_model=IssuerResponse,
    status_code=status.HTTP_201_CREATED,
)
def create_issuer(
    payload: IssuerCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_roles("ORG_ADMIN")),
):
    # An issuer name is unique in the whole deployment: the exchange has no
    # signed-in caller, and the name is how it finds the organization.
    taken = (
        db.query(FederatedIssuer)
        .filter(FederatedIssuer.issuer == payload.issuer)
        .execution_options(all_organizations=True)
        .first()
    )
    if taken is not None:
        # Another organization's issuer id is not this caller's to learn.
        where = (
            f" as issuer {taken.id}"
            if taken.organization_id == current_user.organization_id
            else ""
        )
        raise ChronosError(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"'{payload.issuer}' is already registered{where}",
            code=ErrorCode.ALREADY_EXISTS,
        )
    row = FederatedIssuer(
        issuer=payload.issuer,
        display_name=payload.display_name,
        audience=payload.audience,
        enabled=payload.enabled,
    )
    db.add(row)
    db.commit()
    db.refresh(row)
    return row


@router.get("/issuers", operation_id="federation.listIssuers", response_model=list[IssuerResponse])
def list_issuers(
    db: Session = Depends(get_db),
    current_user: User = Depends(require_roles("ORG_ADMIN")),
):
    return db.query(FederatedIssuer).order_by(FederatedIssuer.id).all()


@router.patch(
    "/issuers/{issuer_id}",
    operation_id="federation.updateIssuer",
    response_model=IssuerResponse,
)
def update_issuer(
    issuer_id: int,
    payload: IssuerUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_roles("ORG_ADMIN")),
):
    row = _issuer_or_404(issuer_id, db)
    for field, value in payload.model_dump(exclude_unset=True).items():
        if value is not None:
            setattr(row, field, value)
    db.commit()
    db.refresh(row)
    return row


@router.delete(
    "/issuers/{issuer_id}",
    operation_id="federation.deleteIssuer",
    status_code=status.HTTP_204_NO_CONTENT,
)
def delete_issuer(
    issuer_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_roles("ORG_ADMIN")),
):
    """Deleting a registration takes its keys, its map and its links with it.

    The accounts stay. Somebody who signed in through this issuer keeps their
    account and their history; what they lose is the shortcut, and an
    administrator can give them a password or link them to a new registration.
    """
    row = _issuer_or_404(issuer_id, db)
    db.delete(row)
    db.commit()


# ──────────────────────────── keys ────────────────────────────


@router.post(
    "/issuers/{issuer_id}/keys",
    operation_id="federation.addKey",
    response_model=IssuerKeyResponse,
    status_code=status.HTTP_201_CREATED,
)
def add_key(
    issuer_id: int,
    payload: IssuerKeyCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_roles("ORG_ADMIN")),
):
    issuer = _issuer_or_404(issuer_id, db)
    _load_ed25519(payload.public_key)
    taken = (
        db.query(FederatedIssuerKey)
        .filter(
            FederatedIssuerKey.issuer_id == issuer.id,
            FederatedIssuerKey.kid == payload.kid,
        )
        .first()
    )
    if taken is not None:
        raise ChronosError(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"Issuer {issuer.id} already has a key with kid '{payload.kid}'",
            code=ErrorCode.ALREADY_EXISTS,
        )
    # Normalised before the comparison below, so the window this check passed
    # is the window stored.
    # Real time, like the verification in services/federated_identity.py that
    # reads this window: the issuer's notes carry real-time claims.
    not_before = _as_utc(payload.not_before) if payload.not_before else clock.wall_now()
    not_after = _as_utc(payload.not_after) if payload.not_after else None
    if not_after is not None and not_after <= not_before:
        raise ChronosError(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
            detail="not_after is not after not_before; the key would never be valid",
            code=ErrorCode.INVALID_VALUE,
        )
    row = FederatedIssuerKey(
        issuer_id=issuer.id,
        kid=payload.kid,
        public_key=payload.public_key,
        not_before=not_before,
        not_after=not_after,
    )
    db.add(row)
    db.commit()
    db.refresh(row)
    return row


@router.get(
    "/issuers/{issuer_id}/keys",
    operation_id="federation.listKeys",
    response_model=list[IssuerKeyResponse],
)
def list_keys(
    issuer_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_roles("ORG_ADMIN")),
):
    issuer = _issuer_or_404(issuer_id, db)
    return (
        db.query(FederatedIssuerKey)
        .filter(FederatedIssuerKey.issuer_id == issuer.id)
        .order_by(FederatedIssuerKey.id)
        .all()
    )


@router.patch(
    "/issuers/{issuer_id}/keys/{key_id}",
    operation_id="federation.retireKey",
    response_model=IssuerKeyResponse,
)
def retire_key(
    issuer_id: int,
    key_id: int,
    payload: IssuerKeyRetire,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_roles("ORG_ADMIN")),
):
    """Give a key an end without taking it away yet.

    A moment in the past is allowed and is how a leaked key is stopped now: the
    next note naming it is refused. The overlap a rotation wants is a moment in
    the future.
    """
    row = _key_or_404(issuer_id, key_id, db)
    not_after = _as_utc(payload.not_after)
    if not_after <= _as_utc(row.not_before):
        raise ChronosError(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
            detail="not_after is not after not_before; delete the key instead",
            code=ErrorCode.INVALID_VALUE,
        )
    row.not_after = not_after
    db.commit()
    db.refresh(row)
    return row


@router.delete(
    "/issuers/{issuer_id}/keys/{key_id}",
    operation_id="federation.deleteKey",
    status_code=status.HTTP_204_NO_CONTENT,
)
def delete_key(
    issuer_id: int,
    key_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_roles("ORG_ADMIN")),
):
    db.delete(_key_or_404(issuer_id, key_id, db))
    db.commit()


# ──────────────────────────── the role map ────────────────────────────


@router.post(
    "/issuers/{issuer_id}/role-map",
    operation_id="federation.addRoleMapEntry",
    response_model=RoleMapEntryResponse,
    status_code=status.HTTP_201_CREATED,
)
def add_role_map_entry(
    issuer_id: int,
    payload: RoleMapEntryCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_roles("ORG_ADMIN")),
):
    """What a group this issuer asserts means here.

    Neither admin role can be mapped; the schema refuses one with a 422 and the
    database refuses it again. Nothing stops two groups mapping to different
    units: that is the ordinary case, a library and a lab. A note asserting
    both gets the older entry's unit, which `resolve_role` documents.
    """
    issuer = _issuer_or_404(issuer_id, db)
    taken = (
        db.query(FederatedRoleMap)
        .filter(
            FederatedRoleMap.issuer_id == issuer.id,
            FederatedRoleMap.group_claim_value == payload.group_claim_value,
        )
        .first()
    )
    if taken is not None:
        raise ChronosError(
            status_code=status.HTTP_409_CONFLICT,
            detail=(
                f"Issuer {issuer.id} already maps group '{payload.group_claim_value}'; "
                f"delete entry {taken.id} to change it"
            ),
            code=ErrorCode.ALREADY_EXISTS,
        )
    row = FederatedRoleMap(
        issuer_id=issuer.id,
        group_claim_value=payload.group_claim_value,
        role_type=payload.role_type,
        unit_code=payload.unit_code,
    )
    db.add(row)
    db.commit()
    db.refresh(row)
    return row


@router.get(
    "/issuers/{issuer_id}/role-map",
    operation_id="federation.listRoleMap",
    response_model=list[RoleMapEntryResponse],
)
def list_role_map(
    issuer_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_roles("ORG_ADMIN")),
):
    issuer = _issuer_or_404(issuer_id, db)
    return (
        db.query(FederatedRoleMap)
        .filter(FederatedRoleMap.issuer_id == issuer.id)
        .order_by(FederatedRoleMap.id)
        .all()
    )


@router.delete(
    "/issuers/{issuer_id}/role-map/{entry_id}",
    operation_id="federation.deleteRoleMapEntry",
    status_code=status.HTTP_204_NO_CONTENT,
)
def delete_role_map_entry(
    issuer_id: int,
    entry_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_roles("ORG_ADMIN")),
):
    """Removing an entry does not change anybody who already signed in.

    Roles are read once, when the account is provisioned. What this changes is
    what the next first-time subject in that group gets.
    """
    issuer = _issuer_or_404(issuer_id, db)
    row = (
        db.query(FederatedRoleMap)
        .filter(FederatedRoleMap.issuer_id == issuer.id, FederatedRoleMap.id == entry_id)
        .first()
    )
    if row is None:
        raise ChronosError(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Issuer {issuer.id} has no role map entry {entry_id}",
            code=ErrorCode.NOT_FOUND,
        )
    db.delete(row)
    db.commit()


# ──────────────────────────── links ────────────────────────────


@router.post(
    "/links",
    operation_id="federation.createLink",
    response_model=LinkResponse,
    status_code=status.HTTP_201_CREATED,
)
def create_link(
    payload: LinkCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_roles("ORG_ADMIN")),
):
    """Let an account that already exists use the shortcut.

    This is the only way it happens. The exchange never links on a matching
    address, because an issuer that never verified the address it asserts could
    otherwise name anybody's and be handed their account.

    An admin account is refused. The map cannot grant either admin role, and
    the threat model's answer to a leaked signing key rests on that: a leaked
    key buys accounts at the level the operator chose. A link to an admin
    account would be a way around it, so it is the same refusal from the other
    direction.

    A deactivated account can be linked, unlike an API key's bound user. A key
    for a deactivated account is dead on arrival, while a link outlives a
    deactivation and works again on reactivation, and refusing would force an
    administrator to reactivate before linking. Sign-in refuses the account
    itself while it is deactivated.

    One account may hold several links, at one issuer or several. That is a
    person with more than one upstream identity, and deciding it is a mistake
    is not this route's call to make.
    """
    issuer = _issuer_or_404(payload.issuer_id, db)
    user = db.query(User).filter(User.id == payload.user_id).first()
    if user is None:
        raise ChronosError(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"User '{payload.user_id}' not found",
            code=ErrorCode.NOT_FOUND,
        )
    if user.role_type in ADMIN_ROLES:
        raise ChronosError(
            status_code=status.HTTP_409_CONFLICT,
            detail=(
                f"'{user.id}' is {user.role_type.value} and cannot be linked: no issuer "
                "may hold a route to an admin account"
            ),
            code=ErrorCode.STATE_CONFLICT,
        )
    taken = (
        db.query(FederatedIdentity)
        .filter(
            FederatedIdentity.issuer_id == issuer.id,
            FederatedIdentity.subject == payload.subject,
        )
        .first()
    )
    if taken is not None:
        raise ChronosError(
            status_code=status.HTTP_409_CONFLICT,
            detail=(
                f"Subject '{payload.subject}' at issuer {issuer.id} is already linked "
                f"to '{taken.user_id}'"
            ),
            code=ErrorCode.ALREADY_EXISTS,
        )
    row = FederatedIdentity(issuer_id=issuer.id, subject=payload.subject, user_id=user.id)
    db.add(row)
    db.commit()
    db.refresh(row)
    return row


@router.get("/links", operation_id="federation.listLinks", response_model=list[LinkResponse])
def list_links(
    issuer_id: int | None = None,
    user_id: str | None = None,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_roles("ORG_ADMIN")),
):
    """Which accounts reach this instance through which issuer.

    Not in the contract's list of routes for this item, and added because the
    rest of it is unusable without one: a link created by a first sign-in has
    an id nobody was ever told, so unlinking would mean reading it out of the
    database by hand.
    """
    q = db.query(FederatedIdentity)
    if issuer_id is not None:
        q = q.filter(FederatedIdentity.issuer_id == issuer_id)
    if user_id is not None:
        q = q.filter(FederatedIdentity.user_id == user_id)
    return q.order_by(FederatedIdentity.id).all()


@router.delete(
    "/links/{link_id}",
    operation_id="federation.deleteLink",
    status_code=status.HTTP_204_NO_CONTENT,
)
def delete_link(
    link_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_roles("ORG_ADMIN")),
):
    """Take the shortcut away and leave the account alone.

    The next note for that subject is a stranger, so it is refused if the
    address on the account is still theirs and provisions a second account if
    it is not. Unlinking is not deactivating: do both if the intent is that the
    person loses access.
    """
    row = db.query(FederatedIdentity).filter(FederatedIdentity.id == link_id).first()
    if row is None:
        raise ChronosError(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Link {link_id} not found",
            code=ErrorCode.NOT_FOUND,
        )
    db.delete(row)
    db.commit()
