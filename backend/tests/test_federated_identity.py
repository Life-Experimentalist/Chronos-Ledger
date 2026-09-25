# Copyright 2026 Chronos Ledger Contributors
# Licensed under the Apache License, Version 2.0

"""Every way a note from an outside issuer is refused, one test each.

The acceptance case is one test and the refusals are eleven, which is the right
proportion: this is a module whose job is saying no, and each no is a separate
attack that has worked somewhere else.
"""

import base64
import hashlib
import hmac
import json
from datetime import UTC, datetime, timedelta

import jwt
import pytest
import redis
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric import ed25519

from app.core.config import get_settings
from app.core.security import hash_password
from app.models.db import (
    FederatedIdentity,
    FederatedIssuer,
    FederatedIssuerKey,
    FederatedRoleMap,
    InstitutionalRole,
    User,
)
from app.services import federated_identity as svc

ISSUER = "https://sso.example.internal"
AUDIENCE = "chronos-ledger"
KID = "2026-01"
RETIRED_KID = "2025-old"


def _keypair():
    private = ed25519.Ed25519PrivateKey.generate()
    pem = (
        private.public_key()
        .public_bytes(
            encoding=serialization.Encoding.PEM,
            format=serialization.PublicFormat.SubjectPublicKeyInfo,
        )
        .decode()
    )
    return private, pem


class _FakeRedis:
    """Enough Redis to be a replay cache, and nothing else.

    Hand-written rather than a dependency, following tests/test_rate_limit.py.
    `set` honours nx and ignores ex, since no test here waits for a TTL to
    pass; what a test needs to see is that a second write of the same key
    fails, which is the whole of the replay check.
    """

    def __init__(self, broken: bool = False):
        self.keys: dict[str, str] = {}
        self.broken = broken
        self.ttls: dict[str, int] = {}

    def set(self, key, value, nx=False, ex=None):
        if self.broken:
            raise redis.ConnectionError("no route to redis")
        if nx and key in self.keys:
            return None
        self.keys[key] = value
        if ex is not None:
            self.ttls[key] = ex
        return True


@pytest.fixture()
def federation(db, monkeypatch):
    """A registered issuer with one current key and one retired one."""
    monkeypatch.setenv("FEDERATED_IDENTITY_ENABLED", "true")
    get_settings.cache_clear()

    private, pem = _keypair()
    retired_private, retired_pem = _keypair()
    row = FederatedIssuer(
        issuer=ISSUER,
        display_name="Example SSO",
        audience=AUDIENCE,
        enabled=True,
    )
    db.add(row)
    db.flush()
    now = datetime.now(UTC)
    db.add(
        FederatedIssuerKey(
            issuer_id=row.id,
            kid=KID,
            public_key=pem,
            not_before=now - timedelta(days=1),
            not_after=None,
        )
    )
    db.add(
        FederatedIssuerKey(
            issuer_id=row.id,
            kid=RETIRED_KID,
            public_key=retired_pem,
            not_before=now - timedelta(days=30),
            not_after=now - timedelta(days=1),
        )
    )
    db.commit()

    fake = _FakeRedis()
    monkeypatch.setattr(svc, "get_redis", lambda: fake)
    yield {"issuer": row, "private": private, "retired": retired_private, "redis": fake}
    get_settings.cache_clear()


def _note(private, /, algorithm="EdDSA", kid=KID, **overrides):
    """A note that is correct in every way the caller does not override."""
    now = datetime.now(UTC)
    claims = {
        "iss": ISSUER,
        "aud": AUDIENCE,
        "sub": "u-4417",
        "jti": f"note-{now.timestamp()}",
        "iat": int(now.timestamp()),
        "exp": int((now + timedelta(seconds=60)).timestamp()),
        "email": "priya@example.internal",
        "name": "Priya R",
    }
    claims.update(overrides)
    for gone in [k for k, v in claims.items() if v is None]:
        del claims[gone]
    return jwt.encode(claims, private, algorithm=algorithm, headers={"kid": kid})


def _refusal(federation, db, **overrides) -> str:
    with pytest.raises(svc.NoteRefused) as refused:
        svc.verify_note(_note(federation["private"], **overrides), db)
    return str(refused.value)


def test_a_correct_note_is_accepted(federation, db):
    verified = svc.verify_note(_note(federation["private"]), db)
    assert verified.issuer.issuer == ISSUER
    assert verified.subject == "u-4417"
    assert verified.email == "priya@example.internal"
    assert verified.full_name == "Priya R"
    assert federation["redis"].keys, "an accepted note records its jti"


def test_the_jti_record_outlives_the_note_and_not_much_more(federation, db):
    svc.verify_note(_note(federation["private"]), db)
    settings = get_settings()
    expected = settings.federated_token_max_lifetime_seconds + settings.federated_clock_skew_seconds
    assert set(federation["redis"].ttls.values()) == {expected}


def test_the_jti_is_not_in_the_key(federation, db):
    """An operator reading the keyspace must not read credentials out of it."""
    note = _note(federation["private"], jti="jti-worth-stealing")
    svc.verify_note(note, db)
    assert all("jti-worth-stealing" not in key for key in federation["redis"].keys)


def test_a_note_ninety_seconds_into_a_two_minute_life_is_accepted(federation, db):
    """The test that keeps the iat rule from drifting back into a lower bound.

    A note minted two minutes ago to live two minutes is a note doing exactly
    what it was minted to do. Bounding how old iat may be would refuse it.
    """
    minted = datetime.now(UTC) - timedelta(seconds=90)
    note = _note(
        federation["private"],
        iat=int(minted.timestamp()),
        exp=int((minted + timedelta(seconds=120)).timestamp()),
    )
    assert svc.verify_note(note, db).subject == "u-4417"


def test_a_replayed_note_is_refused(federation, db):
    note = _note(federation["private"])
    assert svc.verify_note(note, db).subject == "u-4417"
    with pytest.raises(svc.NoteRefused) as refused:
        svc.verify_note(note, db)
    assert "already used" in str(refused.value)


def _hand_built(header: dict, claims: dict, secret: bytes) -> str:
    """An HS256 note assembled by hand, because PyJWT will not mint one.

    `jwt.encode` refuses a PEM as an HMAC secret, which is PyJWT defending
    its own callers and not the check being tested here. An attacker has no
    such scruples and writes the three segments out directly, so the test
    does the same.
    """

    def part(raw: dict) -> bytes:
        return base64.urlsafe_b64encode(json.dumps(raw).encode()).rstrip(b"=")

    signing_input = part(header) + b"." + part(claims)
    signature = hmac.new(secret, signing_input, hashlib.sha256).digest()
    return (signing_input + b"." + base64.urlsafe_b64encode(signature).rstrip(b"=")).decode()


def test_a_wrong_algorithm_is_refused(federation, db):
    """A note signed with something else, however validly, is not a note.

    HS256 with the public key as the secret is the classic version of this:
    the key is public, so anybody who can read it could sign with it. A
    verifier that reads the algorithm out of the header accepts this.
    """
    now = datetime.now(UTC)
    _, pem = _keypair()
    forged = _hand_built(
        {"alg": "HS256", "typ": "JWT", "kid": KID},
        {
            "iss": ISSUER,
            "aud": AUDIENCE,
            "sub": "u-4417",
            "jti": "forged",
            "iat": int(now.timestamp()),
            "exp": int((now + timedelta(seconds=60)).timestamp()),
        },
        pem.encode(),
    )
    with pytest.raises(svc.NoteRefused) as refused:
        svc.verify_note(forged, db)
    assert "alg value is not allowed" in str(refused.value)


def test_an_unsigned_note_is_refused(federation, db):
    unsigned = jwt.encode(
        {
            "iss": ISSUER,
            "aud": AUDIENCE,
            "sub": "u-4417",
            "jti": "unsigned",
            "iat": int(datetime.now(UTC).timestamp()),
            "exp": int((datetime.now(UTC) + timedelta(seconds=60)).timestamp()),
        },
        None,
        algorithm="none",
        headers={"kid": KID},
    )
    with pytest.raises(svc.NoteRefused) as refused:
        svc.verify_note(unsigned, db)
    assert "alg value is not allowed" in str(refused.value)


def test_a_note_signed_by_the_wrong_key_is_refused(federation, db):
    """Naming a registered kid does not make an unregistered key work."""
    stranger, _ = _keypair()
    with pytest.raises(svc.NoteRefused) as refused:
        svc.verify_note(_note(stranger), db)
    assert "Signature verification failed" in str(refused.value)


def test_a_note_with_no_kid_is_refused(federation, db):
    note = jwt.encode(
        {
            "iss": ISSUER,
            "aud": AUDIENCE,
            "sub": "u-4417",
            "jti": "no-kid",
            "iat": int(datetime.now(UTC).timestamp()),
            "exp": int((datetime.now(UTC) + timedelta(seconds=60)).timestamp()),
        },
        federation["private"],
        algorithm="EdDSA",
    )
    with pytest.raises(svc.NoteRefused) as refused:
        svc.verify_note(note, db)
    assert "names no kid" in str(refused.value)


def test_an_unknown_kid_is_refused(federation, db):
    assert "has no key" in _refusal(federation, db, kid="a-kid-nobody-registered")


def test_a_retired_key_is_refused(federation, db):
    """The point of retiring a key: a note it signed correctly still fails."""
    note = _note(federation["retired"], kid=RETIRED_KID)
    with pytest.raises(svc.NoteRefused) as refused:
        svc.verify_note(note, db)
    assert "was retired" in str(refused.value)


def test_a_key_not_in_use_yet_is_refused(federation, db):
    future = FederatedIssuerKey(
        issuer_id=federation["issuer"].id,
        kid="next-year",
        public_key=_keypair()[1],
        not_before=datetime.now(UTC) + timedelta(days=30),
    )
    db.add(future)
    db.commit()
    assert "not in use yet" in _refusal(federation, db, kid="next-year")


def test_the_wrong_audience_is_refused(federation, db):
    """A note minted for another relying party does not work here."""
    assert "Audience doesn't match" in _refusal(federation, db, aud="some-other-service")


def test_an_unregistered_issuer_is_refused(federation, db):
    assert "no issuer is registered" in _refusal(federation, db, iss="https://sso.attacker.test")


def test_a_disabled_issuer_is_refused(federation, db):
    federation["issuer"].enabled = False
    db.commit()
    assert "disabled" in _refusal(federation, db)


def test_an_expired_note_is_refused(federation, db):
    """Past the clock skew, since inside it is deliberately still accepted."""
    gone = datetime.now(UTC) - timedelta(seconds=get_settings().federated_clock_skew_seconds + 30)
    assert "Signature has expired" in _refusal(federation, db, exp=int(gone.timestamp()))


def test_a_note_from_the_future_is_refused(federation, db):
    ahead = datetime.now(UTC) + timedelta(seconds=get_settings().federated_clock_skew_seconds + 30)
    assert "not yet valid (iat)" in _refusal(federation, db, iat=int(ahead.timestamp()))


def test_a_note_minted_to_live_too_long_is_refused(federation, db):
    """exp is the issuer's opinion. The cap is ours."""
    far = datetime.now(UTC) + timedelta(days=365)
    assert "longer than" in _refusal(federation, db, exp=int(far.timestamp()))


@pytest.mark.parametrize("missing", ["sub", "jti", "iat", "exp"])
def test_a_note_missing_a_required_claim_is_refused(federation, db, missing):
    assert f'missing the "{missing}" claim' in _refusal(federation, db, **{missing: None})


def test_redis_being_unreachable_refuses_rather_than_waving_it_through(federation, db, monkeypatch):
    """The one place this fails closed, and the reason it is worth a test.

    Waving a note through with no replay cache turns it into a bearer token
    anybody who reads it once can reuse, so the answer is 503 and not a
    session. Password sign-in is unaffected, which is why this is affordable.
    """
    monkeypatch.setattr(svc, "get_redis", lambda: _FakeRedis(broken=True))
    with pytest.raises(svc.ReplayCacheDown):
        svc.verify_note(_note(federation["private"]), db)


def test_the_feature_being_off_is_not_a_refusal(federation, db, monkeypatch):
    """Off is a different answer from no: the route turns it into 404."""
    monkeypatch.setenv("FEDERATED_IDENTITY_ENABLED", "false")
    get_settings.cache_clear()
    with pytest.raises(svc.FederationDisabled):
        svc.verify_note(_note(federation["private"]), db)


def test_groups_as_a_bare_string_read_as_one_group(federation, db):
    verified = svc.verify_note(_note(federation["private"], groups="staff"), db)
    assert verified.groups == ["staff"]


def test_groups_absent_reads_as_none_of_them(federation, db):
    assert svc.verify_note(_note(federation["private"]), db).groups == []


def test_an_optional_claim_left_out_is_not_a_refusal(federation, db):
    """email and name are optional here; the route decides if it needs them."""
    verified = svc.verify_note(_note(federation["private"], email=None, name=None), db)
    assert verified.email is None
    assert verified.full_name is None


def test_a_refused_note_does_not_spend_the_jti_of_the_real_one(federation, db):
    """Why the jti is spent last and not first.

    A copy of a real note, re-signed by somebody who does not have the key,
    carries the real note's jti. If that copy were recorded before the
    signature was checked, sending it first would make the real note arrive
    second and be refused as a replay, which is a denial of service anyone
    who can read one note can run.
    """
    stranger, _ = _keypair()
    with pytest.raises(svc.NoteRefused):
        svc.verify_note(_note(stranger, jti="shared"), db)
    assert not federation["redis"].keys, "a refused note recorded nothing"
    assert svc.verify_note(_note(federation["private"], jti="shared"), db).subject == "u-4417"


# --------------------------------------------------------------------------
# What the note turns into: the account, and the link that is the record of it.
# --------------------------------------------------------------------------


def _map(db, federation, group: str, role: InstitutionalRole, unit: str | None = None):
    db.add(
        FederatedRoleMap(
            issuer_id=federation["issuer"].id,
            group_claim_value=group,
            role_type=role,
            unit_code=unit,
        )
    )
    db.flush()


def _account(federation, db, **overrides):
    """Sign in the way the route will: verify the note, then resolve the account."""
    return svc.account_for(svc.verify_note(_note(federation["private"], **overrides), db), db)


def test_a_first_note_provisions_an_account(federation, db):
    user = _account(federation, db)

    assert user.email_address == "priya@example.internal"
    assert user.full_name == "Priya R"
    assert user.role_type is InstitutionalRole.MEMBER, "an issuer that asserts nothing gets nothing"
    assert user.unit_code is None
    assert user.initial_login_state is False, "there is no initial password to move off"
    assert user.deactivated_at is None
    link = db.query(FederatedIdentity).one()
    assert (link.issuer_id, link.subject, link.user_id) == (
        federation["issuer"].id,
        "u-4417",
        user.id,
    )


def test_the_provisioned_account_holds_no_usable_password(federation, db):
    """A hash of a string nobody kept, and a different one for each account.

    Two accounts with the same hash would mark both as federated in a database
    dump, which is the reason this is not one shared constant.
    """
    first = _account(federation, db)
    second = _account(federation, db, sub="u-9002", email="dev@example.internal")

    assert first.credential_secure_hash.startswith("$2b$"), "a real bcrypt hash, not a placeholder"
    assert first.credential_secure_hash != second.credential_secure_hash


def test_the_second_sign_in_reuses_the_first_account(federation, db):
    first = _account(federation, db)
    second = _account(federation, db)

    assert second.id == first.id
    assert db.query(User).count() == 1
    assert db.query(FederatedIdentity).count() == 1, "one link, not one per sign-in"


def test_the_pair_is_the_identity_and_the_address_is_not(federation, db):
    """The property the whole design rests on, from the other direction.

    The same subject arriving with a different address is still the same
    person, and the address on file does not move. If this read the address
    instead of the pair, an issuer could rename somebody into an account that
    was never theirs.
    """
    first = _account(federation, db)
    again = _account(federation, db, email="someone.else@example.internal")

    assert again.id == first.id
    assert again.email_address == "priya@example.internal"


def test_the_same_subject_at_a_second_issuer_is_a_different_person(federation, db):
    other = FederatedIssuer(
        issuer="https://sso.other.internal",
        display_name="Other SSO",
        audience=AUDIENCE,
        enabled=True,
    )
    db.add(other)
    db.flush()

    first = _account(federation, db)
    stranger = svc.account_for(
        svc.VerifiedNote(
            issuer=other,
            subject="u-4417",
            email="namesake@other.internal",
            full_name="A Namesake",
            groups=[],
        ),
        db,
    )

    assert stranger.id != first.id, "the subject is only unique inside its issuer"
    assert db.query(FederatedIdentity).count() == 2


def test_a_role_an_administrator_set_survives_the_next_sign_in(federation, db):
    """Federation never re-reads the role of an account that already exists.

    Stated in the design rather than hidden, because the alternative is worse:
    re-syncing on every sign-in would silently undo a change made here, and
    UNIT_ADMIN is a role the map cannot grant at all.
    """
    user = _account(federation, db)
    user.role_type = InstitutionalRole.UNIT_ADMIN
    user.unit_code = "LIB"
    db.flush()

    again = _account(federation, db, groups=["students"])

    assert again.role_type is InstitutionalRole.UNIT_ADMIN
    assert again.unit_code == "LIB"


def test_a_deactivated_linked_account_is_refused_and_not_provisioned_again(federation, db):
    user = _account(federation, db)
    user.deactivated_at = datetime.now(UTC)
    db.flush()

    with pytest.raises(svc.NoteRefused) as refused:
        _account(federation, db)

    assert "deactivated" in str(refused.value)
    assert db.query(User).count() == 1, "signing in upstream does not resurrect the account"


def test_a_reactivated_account_works_again(federation, db):
    user = _account(federation, db)
    user.deactivated_at = datetime.now(UTC)
    db.flush()
    with pytest.raises(svc.NoteRefused):
        _account(federation, db)

    user.deactivated_at = None
    db.flush()

    assert _account(federation, db).id == user.id


def test_an_address_that_belongs_to_an_account_is_refused_and_nothing_written(federation, db):
    """The refusal that stops an issuer taking over an account it never owned.

    Linking on a matching address would be the takeover: assert the
    administrator's address, get the administrator. So a first-time subject
    whose address is taken is refused, and refused before any write, so a
    caller cannot leave half an account behind by trying.
    """
    db.add(
        User(
            id="ADM900",
            full_name="The Administrator",
            email_address="priya@example.internal",
            credential_secure_hash=hash_password("SomethingReal123!"),
            role_type=InstitutionalRole.ORG_ADMIN,
        )
    )
    db.flush()

    with pytest.raises(svc.EmailAlreadyTaken):
        _account(federation, db)

    assert db.query(User).count() == 1
    assert db.query(FederatedIdentity).count() == 0
    assert db.get(User, "ADM900").role_type is InstitutionalRole.ORG_ADMIN


@pytest.mark.parametrize(
    ("on_file", "asserted"),
    [
        ("priya@example.internal", "Priya@Example.Internal"),
        ("Priya@Example.Internal", "priya@example.internal"),
    ],
)
def test_a_taken_address_in_a_different_case_is_still_taken(federation, db, on_file, asserted):
    """Both directions, because the issuer picks the case and the account did not.

    Every other writer in this system stores the case it was handed and
    compares exactly, so an exact match here would let an issuer step past the
    refusal by sending one capital letter, and land a second account whose
    address reads the same as an administrator's.
    """
    db.add(
        User(
            id="ADM901",
            full_name="The Administrator",
            email_address=on_file,
            credential_secure_hash=hash_password("SomethingReal123!"),
            role_type=InstitutionalRole.ORG_ADMIN,
        )
    )
    db.flush()

    with pytest.raises(svc.EmailAlreadyTaken):
        _account(federation, db, email=asserted)

    assert db.query(User).count() == 1


@pytest.mark.parametrize("unusable", [None, "", "   ", "x" * 110 + "@example.internal"])
def test_a_first_time_subject_with_no_usable_address_cannot_be_provisioned(
    federation, db, unusable
):
    """422 and not 401: the note was fine, and no note the caller sends fixes this.

    The over-long case is here because users.email_address holds 120
    characters and an IntegrityError from inside a sign-in would be a 500.
    """
    with pytest.raises(svc.NoEmailToProvisionWith):
        _account(federation, db, email=unusable)

    assert db.query(User).count() == 0


def test_a_missing_name_falls_back_to_the_part_before_the_at(federation, db):
    """full_name is NOT NULL and there is nobody to ask.

    A readable placeholder an administrator can correct beats refusing a note
    that is otherwise complete.
    """
    assert _account(federation, db, name=None).full_name == "priya"


def test_a_very_long_name_is_cut_to_the_column(federation, db):
    user = _account(federation, db, name="N" * 400)

    assert len(user.full_name) == 120


# --------------------------------------------------------------------------
# What a group means here, which the operator decides and the note does not.
# --------------------------------------------------------------------------


def test_a_mapped_group_grants_the_role_and_the_unit(federation, db):
    _map(db, federation, "library-staff", InstitutionalRole.STAFF, "LIB")

    user = _account(federation, db, groups=["library-staff"])

    assert (user.role_type, user.unit_code) == (InstitutionalRole.STAFF, "LIB")


def test_a_group_the_map_does_not_know_lands_on_member(federation, db):
    _map(db, federation, "library-staff", InstitutionalRole.STAFF, "LIB")

    user = _account(federation, db, groups=["visiting-fellows"])

    assert (user.role_type, user.unit_code) == (InstitutionalRole.MEMBER, None)


def test_a_bare_string_group_is_read_as_one_group(federation, db):
    _map(db, federation, "library-staff", InstitutionalRole.STAFF, "LIB")

    user = _account(federation, db, groups="library-staff")

    assert user.role_type is InstitutionalRole.STAFF


def test_staff_beats_member_whichever_order_the_groups_arrive_in(federation, db):
    """Several entries can match and only two roles are reachable.

    So the rule is short, and it has to be the same both ways round, or the
    role somebody gets would depend on how their issuer happened to order a
    list.
    """
    _map(db, federation, "students", InstitutionalRole.MEMBER, None)
    _map(db, federation, "library-staff", InstitutionalRole.STAFF, "LIB")

    forwards = _account(federation, db, groups=["students", "library-staff"])
    granted = (forwards.role_type, forwards.unit_code)
    db.query(FederatedIdentity).delete()
    db.query(User).delete()
    db.flush()
    backwards = _account(federation, db, groups=["library-staff", "students"])

    assert granted == (InstitutionalRole.STAFF, "LIB")
    assert (backwards.role_type, backwards.unit_code) == granted


def test_a_map_belongs_to_its_own_issuer(federation, db):
    """An entry written for one issuer grants nothing at another."""
    other = FederatedIssuer(
        issuer="https://sso.other.internal",
        display_name="Other SSO",
        audience=AUDIENCE,
        enabled=True,
    )
    db.add(other)
    db.flush()
    _map(db, federation, "library-staff", InstitutionalRole.STAFF, "LIB")

    role, unit = svc.resolve_role(other, ["library-staff"], db)

    assert (role, unit) == (InstitutionalRole.MEMBER, None)


# --------------------------------------------------------------------------
# Deleting the account.
# --------------------------------------------------------------------------


def test_the_link_is_declared_to_go_with_the_account(federation, db):
    """Checked as a declaration, because SQLite is not enforcing it here.

    These tests run on SQLite with foreign keys off, so deleting a user does
    not actually cascade in this process; the enforcement lives in migration
    028 on Postgres. What is worth pinning here is that the declaration says
    CASCADE, since a link left pointing at a deleted account would refuse that
    person forever (the test below) instead of letting them arrive as somebody
    new.
    """
    user_fk = next(iter(FederatedIdentity.__table__.c.user_id.foreign_keys))

    assert user_fk.ondelete == "CASCADE"


def test_once_the_link_is_gone_the_next_note_provisions_afresh(federation, db):
    first = _account(federation, db)
    db.query(FederatedIdentity).delete()
    db.query(User).filter(User.id == first.id).delete()
    db.flush()

    again = _account(federation, db)

    assert again.id != first.id
    assert db.query(FederatedIdentity).count() == 1


def test_a_link_pointing_at_no_account_is_refused(federation, db):
    """Only reachable through a hand-edited database, and still worth an answer.

    Refusing beats provisioning a second account for somebody an administrator
    deleted, and it beats an AttributeError on None.
    """
    first = _account(federation, db)
    db.query(User).filter(User.id == first.id).delete()
    db.flush()

    with pytest.raises(svc.NoteRefused) as refused:
        _account(federation, db)

    assert "points at no account" in str(refused.value)


def test_a_minted_id_says_where_the_account_came_from_and_is_not_reused(federation, db):
    """The one thing the contract left open, decided here.

    Every other account takes its id from outside: an administrator types it,
    or a CSV column carries it. A note carries no id anybody here agreed to,
    and the subject is not a candidate, since it is an opaque string from
    another system that would end up in this system's URLs. So: random, behind
    a prefix in the shape the existing ids already have, which earns its keep
    in a user list by answering why the account has no password.
    """
    minted = {
        _account(federation, db, sub=f"u-{n}", email=f"p{n}@example.internal").id for n in range(5)
    }

    assert len(minted) == 5
    assert all(one.startswith("FED-") and len(one) <= 50 for one in minted)
