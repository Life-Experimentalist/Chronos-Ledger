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
from dataclasses import dataclass
from datetime import UTC, datetime

import jwt
import redis
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.core.redis_client import get_redis
from app.models.db import FederatedIssuer, FederatedIssuerKey

log = logging.getLogger(__name__)

# One algorithm, and not a setting. Ed25519 has one curve, one key size and no
# padding mode, so there is nothing about it for an operator to misconfigure,
# and a second permitted algorithm is a second way to be wrong.
SIGNING_ALGORITHM = "EdDSA"

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
        raise NoteRefused(f"key {kid!r} is not in use yet")
    if key.not_after is not None and now >= _as_utc(key.not_after):
        raise NoteRefused(f"key {kid!r} was retired")
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
        raise NoteRefused("the note carries no jti")
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
