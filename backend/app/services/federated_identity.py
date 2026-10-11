# Copyright 2026 Chronos Ledger Contributors
# Licensed under the Apache License, Version 2.0

"""Deciding whether a note from an outside issuer is worth acting on.

A note is a short-lived JWT, signed with Ed25519 by a key an operator
registered, saying that the person holding it is a particular subject at a
particular issuer. This module answers one question about one note: is it
acceptable. It issues nothing, writes no account and returns no session; the
route above it does that, and only for a note this said yes to.

Three rules here are worth stating because getting any of them wrong is the
whole vulnerability:

The algorithm is ours, not the note's. `EdDSA` is passed to the verifier and
the header's `alg` is never consulted, because a verifier that believes the
header can be told `none`, or told to read an RSA public key as an HMAC
secret, both of which have produced forged tokens in real systems.

The key is named, not guessed. The header's `kid` picks exactly one registered
key and a note that names none, or names one the registration does not know,
is refused. Trying every key in turn would make a rotation window a period in
which a retired key still works, which is the opposite of what retiring it
was for.

The replay cache fails closed. `rate_limit.py` fails open on purpose, and the
difference matters: a limiter that cannot reach Redis should still let people
sign in, while a replay cache that cannot reach Redis has stopped being a
replay cache, and carrying on without it turns every note into a bearer token
anybody who reads it once can reuse. Unreachable Redis raises, and the route
answers 503. Password sign-in is untouched, so nobody is locked out; only the
shortcut is.

The refusals are deliberately indistinguishable to the caller. Each one
carries a reason, for the log and for whoever is reading it, and the route
turns every one of them into the same 401.

docs/federated-identity.md is the design, threat model first.
"""

import hashlib
import logging
import secrets
from dataclasses import dataclass
from datetime import UTC, datetime

import jwt
import redis
from sqlalchemy import func
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.core.emails import normalize_email
from app.core.redis_client import get_redis
from app.core.security import hash_password
from app.models.db import (
    FederatedIdentity,
    FederatedIssuer,
    FederatedIssuerKey,
    FederatedRoleMap,
    InstitutionalRole,
    User,
)

log = logging.getLogger(__name__)

# No issuer may hold a route to an admin account. `POST /federation/links`
# refuses to create one and `account_for` refuses to spend one, so the tuple
# lives here rather than in either of them.
ADMIN_ROLES = (InstitutionalRole.ORG_ADMIN, InstitutionalRole.UNIT_ADMIN)

# One algorithm, and not a setting. Ed25519 has one curve, one key size and no
# padding mode, so there is nothing about it for an operator to misconfigure,
# and a second permitted algorithm is a second way to be wrong.
SIGNING_ALGORITHM = "EdDSA"

# What `users.full_name` and `users.email_address` hold. A claim longer than
# the column is not a reason to raise an IntegrityError from inside a sign-in:
# the name is cut to fit and an unusable address is refused before any write.
NAME_COLUMN_LIMIT = 120
EMAIL_COLUMN_LIMIT = 120

# What a note must say. `aud` and `iss` are also checked by value below; they
# are named here so a note missing them fails as a missing claim rather than
# as a mismatch against nothing.
REQUIRED_CLAIMS = ["iss", "aud", "sub", "jti", "iat", "exp"]


class FederationDisabled(Exception):
    """Federated sign-in is off on this instance.

    Separate from a refusal because the answer is different: off means the
    route is not there at all, and says 404 rather than 403. Whether an
    instance has an integration is not something probing it should reveal.
    """


class NoteRefused(Exception):
    """The note is not acceptable, for a reason the caller is not told.

    One message reaches the caller for every refusal, so the response cannot
    be used to find out which part of a forged note was wrong. The reason is
    for the log.
    """


class ReplayCacheDown(Exception):
    """Redis could not be reached, so replay cannot be ruled out."""


@dataclass(frozen=True)
class VerifiedNote:
    """What a note turned out to say, once it was worth believing."""

    issuer: FederatedIssuer
    subject: str
    email: str | None
    full_name: str | None
    groups: list[str]


def _as_utc(moment: datetime) -> datetime:
    """Read a stored timestamp as UTC whether or not it came back aware.

    Postgres hands these back with a timezone and SQLite, which the tests run
    on, does not.
    """
    return moment if moment.tzinfo else moment.replace(tzinfo=UTC)


def _replay_key(issuer: str, jti: str) -> str:
    # Hashed for the reason `rate_limit._bucket_key` hashes its subject: a jti
    # is part of a credential and does not belong in a keyspace an operator
    # reads with KEYS. The issuer goes into the digest too, so two issuers that
    # happen to mint the same jti do not collide and neither can spend the
    # other's.
    digest = hashlib.sha256(f"{issuer}\x00{jti}".encode()).hexdigest()[:32]
    return f"fed:jti:{digest}"


def _groups_from(claim: object) -> list[str]:
    """The groups a note asserts, as a list.

    A bare string is one group and not a mistake: issuers differ on whether a
    single membership is a list, and refusing the string form would refuse a
    note that is saying something perfectly clear.
    """
    if isinstance(claim, str):
        return [claim]
    if isinstance(claim, list):
        return [g for g in claim if isinstance(g, str)]
    return []


def _registered_issuer(name: object, db: Session) -> FederatedIssuer:
    """The registration that answers for this `iss`, or a refusal.

    `name` is read out of a note nobody has verified yet, so it is used as a
    lookup key and nothing else. What makes it true is that the verified
    decode below is given this registration's own issuer to check against, so
    a note that names one issuer and is signed by another gets nowhere.
    """
    if not isinstance(name, str) or not name:
        raise NoteRefused("the note names no issuer")
    row = db.query(FederatedIssuer).filter(FederatedIssuer.issuer == name).first()
    if row is None:
        raise NoteRefused(f"no issuer is registered as {name!r}")
    if not row.enabled:
        raise NoteRefused(f"issuer {name!r} is registered but disabled")
    return row


def _key_for(kid: object, issuer: FederatedIssuer, now: datetime, db: Session) -> str:
    """The one registered key this note names, if it is current."""
    if not isinstance(kid, str) or not kid:
        raise NoteRefused(f"the note from {issuer.issuer!r} names no kid")
    key = (
        db.query(FederatedIssuerKey)
        .filter(
            FederatedIssuerKey.issuer_id == issuer.id,
            FederatedIssuerKey.kid == kid,
        )
        .first()
    )
    if key is None:
        raise NoteRefused(f"issuer {issuer.issuer!r} has no key {kid!r}")
    if now < _as_utc(key.not_before):
        raise NoteRefused(f"key {kid!r} of {issuer.issuer!r} is not in use yet")
    if key.not_after is not None and now >= _as_utc(key.not_after):
        raise NoteRefused(f"key {kid!r} of {issuer.issuer!r} was retired")
    return key.public_key


def _spend_jti(issuer: str, jti: object, ttl: int) -> None:
    """Record this note as used, or refuse it as already used.

    SET NX is the whole mechanism: two copies of one note racing each other
    both try to write the same key and exactly one of them gets to. The TTL is
    how long the note could still be worth replaying, so a record never
    outlives the note it is about and never expires while the note is alive.

    Last of the checks on purpose. A note that was going to be refused anyway
    must not consume the jti of the real note it was copied from.
    """
    if not isinstance(jti, str) or not jti:
        raise NoteRefused(f"the note from {issuer!r} carries no jti")
    try:
        first = get_redis().set(_replay_key(issuer, jti), "1", nx=True, ex=ttl)
    except redis.RedisError as unreachable:
        # Not a refusal: the note may be perfectly good and there is no way to
        # tell. 503 is the honest answer and password sign-in still works.
        log.warning("federated sign-in refused, replay cache unreachable: %s", unreachable)
        raise ReplayCacheDown(str(unreachable)) from unreachable
    if not first:
        raise NoteRefused(f"the note from {issuer!r} was already used")


def verify_note(token: str, db: Session) -> VerifiedNote:
    """Verify one note and return what it says, or raise.

    The order of the checks is deliberate. The key's own validity window comes
    before the signature, so a retired key cannot be exercised at all. The
    lifetime cap comes after the signature, because it is a judgement about a
    note that has already proved it came from the issuer. The jti comes last,
    so nothing that was going to be refused spends one.
    """
    settings = get_settings()
    if not settings.federated_identity_enabled:
        raise FederationDisabled()

    skew = settings.federated_clock_skew_seconds
    cap = settings.federated_token_max_lifetime_seconds
    now = datetime.now(UTC)

    try:
        header = jwt.get_unverified_header(token)
        unverified = jwt.decode(token, options={"verify_signature": False})
    except jwt.PyJWTError as unreadable:
        raise NoteRefused(f"the note could not be read: {unreadable}") from unreadable

    issuer = _registered_issuer(unverified.get("iss"), db)
    public_key = _key_for(header.get("kid"), issuer, now, db)

    try:
        # One leeway covers exp, nbf and iat, which is the asymmetry the design
        # asks for: exp may be that far in the past and iat and nbf that far in
        # the future. There is no lower bound on iat, because how old a note may
        # be is already answered by exp and by the cap below, and bounding its
        # age here as well would refuse a two-minute note ninety seconds into
        # its life.
        claims = jwt.decode(
            token,
            public_key,
            algorithms=[SIGNING_ALGORITHM],
            audience=issuer.audience,
            issuer=issuer.issuer,
            leeway=skew,
            options={"require": REQUIRED_CLAIMS},
        )
    except jwt.PyJWTError as bad:
        raise NoteRefused(f"the note from {issuer.issuer!r} did not verify: {bad}") from bad

    # exp is the issuer's opinion about how long this should work, so it is
    # checked and then second-guessed: an issuer that sets it a year out has
    # minted a bearer token for a year. No skew is added here, and the replay
    # record's TTL is this cap plus the skew for that reason: a note accepted
    # at the cap is still valid for the skew beyond it.
    if int(claims["exp"]) - int(now.timestamp()) > cap:
        raise NoteRefused(f"the note from {issuer.issuer!r} is minted to live longer than {cap}s")

    _spend_jti(issuer.issuer, claims.get("jti"), cap + skew)

    subject = str(claims["sub"])
    email = claims.get("email")
    name = claims.get("name")
    return VerifiedNote(
        issuer=issuer,
        subject=subject,
        email=email if isinstance(email, str) and email else None,
        full_name=name if isinstance(name, str) and name else None,
        groups=_groups_from(claims.get("groups")),
    )


class NoEmailToProvisionWith(Exception):
    """The note verified, and then could not be turned into an account.

    A different thing from a bad note and worth a different answer: the route
    says 422, because nothing the caller can do to the note fixes it. An
    operator has to add the claim to what the issuer sends, or create the
    account and link it by hand.
    """


class LinkedAccountIsAdmin(Exception):
    """The link is sound and the account behind it has become an admin.

    Not a bad note, so not a 401: the note verified and the link is the one
    an operator created. What changed is the account, and the person holding
    the note can do nothing about it, so the route says 403 and says why.
    An administrator has a password; this closes a route, it does not close
    them out.
    """


class EmailAlreadyTaken(Exception):
    """A first-time subject arrived with an address that is already somebody's.

    Never linked, always refused, and this is the refusal the whole design
    turns on. Linking on a matching address would let an issuer that never
    checked the address it asserts take over any account whose address it can
    guess, an administrator's included. The route says 409, and an
    administrator who wants that person on the shortcut links them
    deliberately through the registry.
    """


def resolve_role(
    issuer: FederatedIssuer, groups: list[str], db: Session
) -> tuple[InstitutionalRole, str | None]:
    """What the groups a note asserts mean here.

    No match is `MEMBER` with no unit, which is the least this instance can
    grant and the right answer for an issuer that asserts nothing useful.

    Several entries can match and only two roles are reachable, so the rule is
    short: `STAFF` beats `MEMBER`, and among the rows of the winning role the
    oldest entry supplies the unit. That tie-break is the whole answer to two
    `STAFF` rows with different units, which the design once said a write-time
    validator would refuse. It does not, and cannot: refusing two `STAFF` rows
    with different units would forbid a library and a lab mapping their own
    staff groups, which is what the map is for. So the pair is allowed, the
    oldest entry wins, and the ordering below is what makes the answer
    independent of how the issuer happened to order its list.
    """
    if not groups:
        return InstitutionalRole.MEMBER, None
    matches = (
        db.query(FederatedRoleMap)
        .filter(
            FederatedRoleMap.issuer_id == issuer.id,
            FederatedRoleMap.group_claim_value.in_(groups),
        )
        .order_by(FederatedRoleMap.id)
        .all()
    )
    for row in matches:
        if row.role_type == InstitutionalRole.STAFF:
            return InstitutionalRole.STAFF, row.unit_code
    if matches:
        return InstitutionalRole.MEMBER, matches[0].unit_code
    return InstitutionalRole.MEMBER, None


def _mint_user_id() -> str:
    """An account id for somebody nobody typed in.

    Every other way an account appears takes its id from outside: an
    administrator fills it in, or a CSV column carries it. A note carries no
    id anyone here agreed to, and the subject is not a candidate, since it is
    an opaque string from another system that would end up in this system's
    URLs and audit records.

    So: a random id behind a prefix, in the shape the existing ids already
    have. The prefix reveals only what the link table says plainly anyway, and
    it earns its keep in an administrator's user list, where it answers at a
    glance why an account has no password. Sixty-four bits against a primary
    key, which is how `generate_feed_token` already treats a unique column.
    """
    return f"FED-{secrets.token_hex(8).upper()}"


def account_for(note: VerifiedNote, db: Session) -> User:
    """The account this note belongs to, provisioning one the first time.

    `(issuer, subject)` is identity and the address is convenience. A note
    whose pair is in the link table is that account, whatever address the note
    now carries; a note whose pair is not is a stranger, whatever address it
    carries.

    The role of an account that already exists is never read back into it. An
    upstream demotion does not reach Chronos, which is stated in the design
    rather than hidden: re-syncing on every sign-in would silently undo an
    administrator's own change. `deactivated_at` is the lever, and it is
    checked here.

    The role is read for one thing, which is to refuse. `POST /federation/links`
    will not link an admin account, because no issuer may hold a route to one,
    and an account can reach an admin role in the ordinary way after it was
    linked. Checking only at link time would leave that route open for anybody
    who holds the issuer's key, so the same refusal is made here. It refuses
    the sign-in and leaves the role alone: demoting somebody an administrator
    promoted is the thing the paragraph above rules out.
    """
    link = (
        db.query(FederatedIdentity)
        .filter(
            FederatedIdentity.issuer_id == note.issuer.id,
            FederatedIdentity.subject == note.subject,
        )
        .first()
    )
    if link is not None:
        user = db.get(User, link.user_id)
        if user is None:
            # The cascade should have taken the link with the account, so this
            # is a database somebody edited by hand. Refusing beats provisioning
            # a second account for a person an administrator deleted.
            raise NoteRefused(
                f"the link from {note.issuer.issuer!r} for {note.subject!r} points at no account"
            )
        if user.deactivated_at is not None:
            # The same answer password sign-in gives a deactivated account, and
            # deliberately not a re-provision: signing in again upstream does
            # not resurrect an account somebody here switched off.
            raise NoteRefused(
                f"account {user.id!r}, linked from {note.issuer.issuer!r}, is deactivated"
            )
        if user.role_type in ADMIN_ROLES:
            raise LinkedAccountIsAdmin(
                f"account {user.id!r}, linked from {note.issuer.issuer!r}, "
                f"is {user.role_type.value}"
            )
        return user

    email = normalize_email(note.email or "")
    if not email or len(email) > EMAIL_COLUMN_LIMIT:
        raise NoEmailToProvisionWith(
            f"{note.issuer.issuer!r} vouched for {note.subject!r} with no usable email claim"
        )
    # Compared without case, the same way every other reader of this column
    # compares. Matching exactly would let an issuer walk past this refusal by
    # choosing the case and land a second account whose address reads the same
    # as somebody else's. The index this uses is the one 029 adds.
    taken = db.query(User.id).filter(func.lower(User.email_address) == email).first() is not None
    if taken:
        raise EmailAlreadyTaken(f"{email} already belongs to an account")

    role, unit_code = resolve_role(note.issuer, note.groups, db)
    user = User(
        id=_mint_user_id(),
        # The note's name if it sent one, and the part before the @ if it did
        # not. The column is NOT NULL and there is nobody to ask, so a readable
        # placeholder an administrator can correct beats refusing a note that
        # is otherwise complete.
        full_name=(note.full_name or email.split("@")[0])[:NAME_COLUMN_LIMIT],
        email_address=email,
        # A bcrypt hash of a string nobody holds, which can never match a
        # submitted password. Generated per account rather than shared, so a
        # database dump does not pick the federated rows out by an identical
        # hash. The link table is the record of federation; this column is not.
        credential_secure_hash=hash_password(secrets.token_urlsafe(32)),
        role_type=role,
        unit_code=unit_code,
        # There is no initial password to move off. `first_login_blocks` only
        # holds the two admin roles and neither is reachable from outside, so
        # this is about the field meaning what it says.
        initial_login_state=False,
    )
    db.add(user)
    db.add(
        FederatedIdentity(
            issuer_id=note.issuer.id,
            subject=note.subject,
            user_id=user.id,
        )
    )
    db.flush()
    return user
