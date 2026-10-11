# Copyright 2026 Chronos Ledger Contributors
# Licensed under the Apache License, Version 2.0
"""The registry an operator administers: issuers, their keys, their map, links.

Everything here is ORG_ADMIN, and the reason is in the routes: an issuer is
organization-wide and its map can place somebody in any unit, so a unit admin
is the wrong scope for it. These routes answer whether or not the feature flag
is set, because an operator has to register an issuer and a key before turning
the exchange on.
"""

from datetime import UTC, datetime, timedelta

import pytest
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey
from cryptography.hazmat.primitives.asymmetric.rsa import generate_private_key

from app.core.security import hash_password
from app.models.db import (
    AuditRecord,
    FederatedIdentity,
    FederatedIssuer,
    FederatedIssuerKey,
    FederatedRoleMap,
    InstitutionalRole,
    User,
)
from tests.conftest import ADMIN_PASSWORD, login

FEDERATION = "/api/v1/federation"
UNIT_ADMIN_PASSWORD = "UnitAdminPass123!"


def _pem(key=None) -> str:
    key = key or Ed25519PrivateKey.generate()
    return (
        key.public_key()
        .public_bytes(
            encoding=serialization.Encoding.PEM,
            format=serialization.PublicFormat.SubjectPublicKeyInfo,
        )
        .decode()
    )


@pytest.fixture()
def admin(client, seed_users):
    return login(client, "admin@test.internal", ADMIN_PASSWORD)


@pytest.fixture()
def unit_admin(client, db, seed_users):
    db.add(
        User(
            id="UAD001",
            full_name="Unit Admin One",
            email_address="cse.admin@test.internal",
            credential_secure_hash=hash_password(UNIT_ADMIN_PASSWORD),
            role_type=InstitutionalRole.UNIT_ADMIN,
            unit_code="CSE",
            initial_login_state=False,
        )
    )
    db.commit()
    return login(client, "cse.admin@test.internal", UNIT_ADMIN_PASSWORD)


def _issuer(client, headers, issuer="https://sso.example.internal", **overrides):
    body = {
        "issuer": issuer,
        "display_name": "Example SSO",
        "audience": "chronos-ledger",
        **overrides,
    }
    res = client.post(f"{FEDERATION}/issuers", json=body, headers=headers)
    assert res.status_code == 201, res.text
    return res.json()


# --------------------------------------------------------------------------
# The walk the contract asks for: register, key it, retire it, link, unlink.
# --------------------------------------------------------------------------


def test_an_admin_walks_the_whole_registry(client, admin, db):
    """One test for the sequence, because the sequence is the feature.

    Registering an issuer that cannot be keyed, or a key that cannot be
    retired, would each pass its own test and still leave an operator unable to
    turn the feature on.
    """
    issuer = _issuer(client, admin)
    assert issuer["enabled"] is True, "an issuer is on unless it is registered off"

    added = client.post(
        f"{FEDERATION}/issuers/{issuer['id']}/keys",
        json={"kid": "2026-key-a", "public_key": _pem()},
        headers=admin,
    )
    assert added.status_code == 201, added.text
    key = added.json()
    assert key["not_before"] is not None, "a key with no window given starts now"
    assert key["not_after"] is None

    retired = client.patch(
        f"{FEDERATION}/issuers/{issuer['id']}/keys/{key['id']}",
        json={"not_after": (datetime.now(UTC) + timedelta(days=1)).isoformat()},
        headers=admin,
    )
    assert retired.status_code == 200, retired.text
    assert retired.json()["not_after"] is not None

    linked = client.post(
        f"{FEDERATION}/links",
        json={"issuer_id": issuer["id"], "subject": "u-4417", "user_id": "FAC001"},
        headers=admin,
    )
    assert linked.status_code == 201, linked.text
    link = linked.json()

    listed = client.get(f"{FEDERATION}/links", headers=admin)
    assert [one["id"] for one in listed.json()] == [link["id"]]

    assert client.delete(f"{FEDERATION}/links/{link['id']}", headers=admin).status_code == 204
    assert client.get(f"{FEDERATION}/links", headers=admin).json() == []

    assert client.delete(f"{FEDERATION}/issuers/{issuer['id']}", headers=admin).status_code == 204
    assert client.get(f"{FEDERATION}/issuers", headers=admin).json() == []


def test_the_registry_answers_while_the_feature_is_off(client, admin, monkeypatch):
    """The flag gates the exchange, not the administration of it.

    An operator has to register an issuer and a key before turning the exchange
    on, so gating these routes on the flag would leave SQL as the only way in.
    """
    from app.core.config import get_settings

    monkeypatch.setenv("FEDERATED_IDENTITY_ENABLED", "false")
    get_settings.cache_clear()
    try:
        assert get_settings().federated_identity_enabled is False
        assert client.get(f"{FEDERATION}/issuers", headers=admin).status_code == 200
        _issuer(client, admin)
    finally:
        get_settings.cache_clear()


def test_an_update_leaves_out_what_it_does_not_mention(client, admin):
    issuer = _issuer(client, admin)

    res = client.patch(
        f"{FEDERATION}/issuers/{issuer['id']}",
        json={"enabled": False},
        headers=admin,
    )

    assert res.status_code == 200, res.text
    assert res.json()["enabled"] is False
    assert res.json()["display_name"] == "Example SSO"
    assert res.json()["issuer"] == issuer["issuer"], "the value notes carry is not editable"


# --------------------------------------------------------------------------
# Who may administer it, which is one role and not three.
# --------------------------------------------------------------------------

# Every route, with ids and bodies that would never get past validation. The
# role check is a dependency, and FastAPI runs dependencies before it validates
# a body, so a refusal here is the role check and not the empty json. A 422
# anywhere below would mean that ordering had changed.
EVERY_ROUTE = [
    ("post", f"{FEDERATION}/issuers"),
    ("get", f"{FEDERATION}/issuers"),
    ("patch", f"{FEDERATION}/issuers/1"),
    ("delete", f"{FEDERATION}/issuers/1"),
    ("post", f"{FEDERATION}/issuers/1/keys"),
    ("get", f"{FEDERATION}/issuers/1/keys"),
    ("patch", f"{FEDERATION}/issuers/1/keys/1"),
    ("delete", f"{FEDERATION}/issuers/1/keys/1"),
    ("post", f"{FEDERATION}/issuers/1/role-map"),
    ("get", f"{FEDERATION}/issuers/1/role-map"),
    ("delete", f"{FEDERATION}/issuers/1/role-map/1"),
    ("post", f"{FEDERATION}/links"),
    ("get", f"{FEDERATION}/links"),
    ("delete", f"{FEDERATION}/links/1"),
]


@pytest.mark.parametrize(("method", "path"), EVERY_ROUTE)
def test_a_unit_admin_is_refused_everywhere(client, unit_admin, method, path):
    res = client.request(method.upper(), path, json={}, headers=unit_admin)

    assert res.status_code == 403, f"{method.upper()} {path} answered {res.status_code}"
    assert res.json()["detail"] == "Insufficient permissions"


@pytest.mark.parametrize(("method", "path"), EVERY_ROUTE)
def test_nobody_signed_out_reaches_it(client, seed_users, method, path):
    assert client.request(method.upper(), path, json={}).status_code == 401


def test_a_staff_key_does_not_open_the_registry(client, admin, kiosk_key):
    """A key carries its account's role, and the kiosk's is a MEMBER.

    Worth stating on this surface in particular: the scopes federation:read and
    federation:write derive from the path with nothing registered, so a wildcard
    key would hold them, and the role check is what stops it.
    """
    assert client.get(f"{FEDERATION}/issuers", headers=kiosk_key).status_code == 403


# --------------------------------------------------------------------------
# What the registry refuses, and why each refusal is worth its code.
# --------------------------------------------------------------------------


def test_the_same_issuer_twice_is_a_conflict(client, admin):
    _issuer(client, admin)

    res = client.post(
        f"{FEDERATION}/issuers",
        json={
            "issuer": "https://sso.example.internal",
            "display_name": "A Second Registration",
            "audience": "chronos-ledger",
        },
        headers=admin,
    )

    assert res.status_code == 409
    assert "already registered" in res.json()["detail"]


def test_a_key_that_could_never_verify_a_note_is_refused_at_registration(client, admin):
    """A mistyped PEM is a 422 here rather than a 401 on every note later.

    The refusal at sign-in says the note could not be verified, which is true
    and useless: nothing in it points at the registration that is at fault.
    """
    issuer = _issuer(client, admin)

    res = client.post(
        f"{FEDERATION}/issuers/{issuer['id']}/keys",
        json={"kid": "typo", "public_key": "-----BEGIN PUBLIC KEY-----\nnope\n"},
        headers=admin,
    )

    assert res.status_code == 422
    assert "not a PEM public key" in res.json()["detail"]


def test_a_real_key_of_the_wrong_kind_is_refused(client, admin):
    """Notes are EdDSA only, so an RSA key is a registration that cannot work."""
    issuer = _issuer(client, admin)
    rsa_pem = (
        generate_private_key(public_exponent=65537, key_size=2048)
        .public_key()
        .public_bytes(
            encoding=serialization.Encoding.PEM,
            format=serialization.PublicFormat.SubjectPublicKeyInfo,
        )
        .decode()
    )

    res = client.post(
        f"{FEDERATION}/issuers/{issuer['id']}/keys",
        json={"kid": "rsa", "public_key": rsa_pem},
        headers=admin,
    )

    assert res.status_code == 422
    assert "Ed25519" in res.json()["detail"]


def test_the_same_kid_twice_at_one_issuer_is_a_conflict(client, admin):
    issuer = _issuer(client, admin)
    body = {"kid": "2026-key-a", "public_key": _pem()}
    assert client.post(f"{FEDERATION}/issuers/{issuer['id']}/keys", json=body, headers=admin)

    res = client.post(
        f"{FEDERATION}/issuers/{issuer['id']}/keys",
        json={"kid": "2026-key-a", "public_key": _pem()},
        headers=admin,
    )

    assert res.status_code == 409


def test_the_same_kid_at_a_second_issuer_is_fine(client, admin):
    """kid is unique inside its issuer, because two institutions do not confer.

    Both calling their key `default` is not a collision anybody should have to
    resolve.
    """
    first = _issuer(client, admin)
    second = _issuer(client, admin, issuer="https://sso.other.internal")
    body = {"kid": "default", "public_key": _pem()}

    assert (
        client.post(
            f"{FEDERATION}/issuers/{first['id']}/keys", json=body, headers=admin
        ).status_code
        == 201
    )
    assert (
        client.post(
            f"{FEDERATION}/issuers/{second['id']}/keys", json=body, headers=admin
        ).status_code
        == 201
    )


def test_a_window_that_closes_before_it_opens_is_refused(client, admin):
    issuer = _issuer(client, admin)
    opens = datetime.now(UTC)

    res = client.post(
        f"{FEDERATION}/issuers/{issuer['id']}/keys",
        json={
            "kid": "backwards",
            "public_key": _pem(),
            "not_before": opens.isoformat(),
            "not_after": (opens - timedelta(seconds=1)).isoformat(),
        },
        headers=admin,
    )

    assert res.status_code == 422
    assert "never be valid" in res.json()["detail"]


def test_retiring_a_key_in_the_past_is_allowed(client, admin, db):
    """This is how a leaked key is stopped now rather than at the next restart.

    A future moment is the overlap a planned rotation wants; a past one is the
    emergency. Refusing the past would leave deletion as the only fast answer,
    and deletion loses the record that the key existed.
    """
    issuer = _issuer(client, admin)
    key = client.post(
        f"{FEDERATION}/issuers/{issuer['id']}/keys",
        json={
            "kid": "leaked",
            "public_key": _pem(),
            "not_before": (datetime.now(UTC) - timedelta(days=30)).isoformat(),
        },
        headers=admin,
    ).json()
    stop = datetime.now(UTC) - timedelta(minutes=5)

    res = client.patch(
        f"{FEDERATION}/issuers/{issuer['id']}/keys/{key['id']}",
        json={"not_after": stop.isoformat()},
        headers=admin,
    )

    assert res.status_code == 200, res.text
    db.expire_all()
    assert db.query(FederatedIssuerKey).one().not_after is not None


# --------------------------------------------------------------------------
# The map, where the one rule that matters is the one about admin roles.
# --------------------------------------------------------------------------


@pytest.mark.parametrize("role", ["ORG_ADMIN", "UNIT_ADMIN"])
def test_no_issuer_can_be_given_an_admin_role_to_assert(client, admin, db, role):
    """The refusal the threat model rests on.

    A leaked signing key buys accounts at the level the operator chose, and it
    is only true while neither admin role can be mapped. The schema refuses it
    with a 422 naming the field, and ck_federated_role_map_no_admin refuses it
    again underneath, so SQL is no way round it either.
    """
    issuer = _issuer(client, admin)

    res = client.post(
        f"{FEDERATION}/issuers/{issuer['id']}/role-map",
        json={"group_claim_value": "it-admins", "role_type": role, "unit_code": "CSE"},
        headers=admin,
    )

    assert res.status_code == 422
    assert db.query(FederatedRoleMap).count() == 0


def test_the_same_group_twice_is_a_conflict(client, admin):
    """One group means one thing, so changing it is a delete and an add.

    Overwriting silently would leave no moment where an administrator sees what
    the group used to grant.
    """
    issuer = _issuer(client, admin)
    body = {"group_claim_value": "library-staff", "role_type": "STAFF", "unit_code": "LIB"}
    assert (
        client.post(
            f"{FEDERATION}/issuers/{issuer['id']}/role-map", json=body, headers=admin
        ).status_code
        == 201
    )

    res = client.post(f"{FEDERATION}/issuers/{issuer['id']}/role-map", json=body, headers=admin)

    assert res.status_code == 409
    assert "already maps group" in res.json()["detail"]


def test_two_groups_may_name_two_units(client, admin):
    """The pair an earlier draft of the design said would be refused at write.

    It is the ordinary case: a library and a lab each mapping their own staff
    group. Somebody in both is not a misconfiguration, so the map takes it and
    the tie is broken at sign-in by entry age.
    """
    issuer = _issuer(client, admin)

    for group, unit in (("library-staff", "LIB"), ("lab-staff", "LAB")):
        res = client.post(
            f"{FEDERATION}/issuers/{issuer['id']}/role-map",
            json={"group_claim_value": group, "role_type": "STAFF", "unit_code": unit},
            headers=admin,
        )
        assert res.status_code == 201, res.text

    listed = client.get(f"{FEDERATION}/issuers/{issuer['id']}/role-map", headers=admin).json()
    assert [one["unit_code"] for one in listed] == ["LIB", "LAB"], (
        "oldest first, which decides ties"
    )


def test_an_entry_with_no_unit_is_allowed(client, admin):
    """A role without a unit is a real answer: staff of the organization.

    There is no units table to check a code against, so refusing a missing one
    would be inventing a requirement the rest of the system does not have.
    """
    issuer = _issuer(client, admin)

    res = client.post(
        f"{FEDERATION}/issuers/{issuer['id']}/role-map",
        json={"group_claim_value": "everyone", "role_type": "MEMBER"},
        headers=admin,
    )

    assert res.status_code == 201, res.text
    assert res.json()["unit_code"] is None


# --------------------------------------------------------------------------
# Links, where the identity lives.
# --------------------------------------------------------------------------


def _link(client, headers, issuer_id, subject="u-4417", user_id="FAC001"):
    return client.post(
        f"{FEDERATION}/links",
        json={"issuer_id": issuer_id, "subject": subject, "user_id": user_id},
        headers=headers,
    )


def test_a_pair_that_is_already_linked_is_a_conflict(client, admin):
    """The contract's own done-when, and the refusal that keeps the pair unique.

    Two accounts reachable by one note would mean sign-in picking one.
    """
    issuer = _issuer(client, admin)
    assert _link(client, admin, issuer["id"]).status_code == 201

    res = _link(client, admin, issuer["id"], user_id="STU001")

    assert res.status_code == 409
    assert "already linked" in res.json()["detail"]


@pytest.mark.parametrize("who", ["ADM001", "UAD001"])
def test_no_issuer_may_hold_a_route_to_an_admin_account(client, admin, unit_admin, who):
    """The same rule as the map's, from the other direction.

    The map cannot grant either admin role, so a leaked key buys accounts at
    the level the operator chose. A link to an admin account would be a way
    round that, and the refusal here is what makes the map's exclusion hold in
    fact rather than on paper.
    """
    issuer = _issuer(client, admin)

    res = _link(client, admin, issuer["id"], user_id=who)

    assert res.status_code == 409
    assert "cannot be linked" in res.json()["detail"]


def test_a_deactivated_account_can_still_be_linked(client, admin, db):
    """A deliberate divergence from api_keys.py, which refuses one with a 409.

    A key for a deactivated account is dead on arrival. A link outlives the
    deactivation and works again on reactivation, so refusing here would force
    an administrator to reactivate somebody in order to prepare their access.
    Sign-in refuses the account itself while it is deactivated, which is where
    that check belongs.
    """
    issuer = _issuer(client, admin)
    db.query(User).filter(User.id == "FAC001").one().deactivated_at = datetime.now(UTC)
    db.commit()

    assert _link(client, admin, issuer["id"]).status_code == 201


def test_one_account_may_arrive_through_two_issuers(client, admin):
    first = _issuer(client, admin)
    second = _issuer(client, admin, issuer="https://sso.other.internal")

    assert _link(client, admin, first["id"]).status_code == 201
    assert _link(client, admin, second["id"], subject="other-99").status_code == 201

    listed = client.get(f"{FEDERATION}/links?user_id=FAC001", headers=admin).json()
    assert len(listed) == 2


def test_the_link_list_filters_by_issuer_and_by_account(client, admin):
    first = _issuer(client, admin)
    second = _issuer(client, admin, issuer="https://sso.other.internal")
    _link(client, admin, first["id"], user_id="FAC001")
    _link(client, admin, second["id"], subject="s-2", user_id="STU001")

    by_issuer = client.get(f"{FEDERATION}/links?issuer_id={first['id']}", headers=admin).json()
    by_user = client.get(f"{FEDERATION}/links?user_id=STU001", headers=admin).json()
    both = client.get(
        f"{FEDERATION}/links?issuer_id={first['id']}&user_id=STU001", headers=admin
    ).json()

    assert [one["user_id"] for one in by_issuer] == ["FAC001"]
    assert [one["issuer_id"] for one in by_user] == [second["id"]]
    assert both == [], "the filters narrow together rather than either one matching"


def test_linking_a_stranger_or_an_unregistered_issuer_is_a_404(client, admin):
    issuer = _issuer(client, admin)

    assert _link(client, admin, issuer["id"], user_id="NOBODY").status_code == 404
    assert _link(client, admin, 9999).status_code == 404


def test_unlinking_leaves_the_account_alone(client, admin, db):
    issuer = _issuer(client, admin)
    link = _link(client, admin, issuer["id"]).json()

    assert client.delete(f"{FEDERATION}/links/{link['id']}", headers=admin).status_code == 204

    db.expire_all()
    assert db.query(FederatedIdentity).count() == 0
    staff = db.query(User).filter(User.id == "FAC001").one()
    assert staff.role_type is InstitutionalRole.STAFF
    assert staff.deactivated_at is None, "unlinking is not deactivating"


# --------------------------------------------------------------------------
# What deleting a registration takes with it.
# --------------------------------------------------------------------------


def test_deleting_an_issuer_takes_its_keys_and_its_map(client, admin, db):
    """Exercised, because these two are ORM relationships with a cascade.

    An entry left behind would grant a role at an issuer nobody can reach, and
    a key left behind would be a public key on file for nothing.
    """
    issuer = _issuer(client, admin)
    client.post(
        f"{FEDERATION}/issuers/{issuer['id']}/keys",
        json={"kid": "a", "public_key": _pem()},
        headers=admin,
    )
    client.post(
        f"{FEDERATION}/issuers/{issuer['id']}/role-map",
        json={"group_claim_value": "students", "role_type": "MEMBER"},
        headers=admin,
    )

    assert client.delete(f"{FEDERATION}/issuers/{issuer['id']}", headers=admin).status_code == 204

    db.expire_all()
    assert db.query(FederatedIssuerKey).count() == 0
    assert db.query(FederatedRoleMap).count() == 0
    assert db.query(FederatedIssuer).count() == 0


def test_the_link_is_declared_to_go_with_its_issuer(client, admin, db):
    """Checked as a declaration, because nothing here exercises it.

    There is no ORM relationship from the issuer to its links, and these tests
    run on SQLite with foreign keys off, so deleting the registration in this
    process leaves the link row behind. The enforcement lives in migration 028
    on Postgres, and what is worth pinning is that the column says CASCADE: a
    link pointing at a deleted issuer would refuse that person forever.
    """
    issuer_fk = next(iter(FederatedIdentity.__table__.c.issuer_id.foreign_keys))

    assert issuer_fk.ondelete == "CASCADE"


def test_the_accounts_outlive_the_registration(client, admin, db):
    """The registration is the route in, and the account is the person.

    Deleting an issuer has to leave the people who arrived through it, with
    their history, so an administrator can hand them a password instead.
    """
    issuer = _issuer(client, admin)
    _link(client, admin, issuer["id"])

    client.delete(f"{FEDERATION}/issuers/{issuer['id']}", headers=admin)

    db.expire_all()
    assert db.query(User).filter(User.id == "FAC001").one().role_type is InstitutionalRole.STAFF


# --------------------------------------------------------------------------
# The audit trail, which the middleware writes with no help from these routes.
# --------------------------------------------------------------------------


def _records(db, path):
    db.expire_all()
    return db.query(AuditRecord).filter(AuditRecord.path == path).all()


def test_every_write_on_this_surface_lands_an_audit_record(client, admin, db):
    """One record each for the create, the retire and the delete.

    Nothing in these routes writes a record; core/audit.py audits every
    non-read method under /api/v1/. So this is a test that the new surface sits
    under that prefix, which is the only way it could fail.
    """
    issuer = _issuer(client, admin)
    keys = f"{FEDERATION}/issuers/{issuer['id']}/keys"
    key = client.post(keys, json={"kid": "a", "public_key": _pem()}, headers=admin).json()
    one_key = f"{keys}/{key['id']}"
    client.patch(
        one_key,
        json={"not_after": (datetime.now(UTC) + timedelta(days=1)).isoformat()},
        headers=admin,
    )
    client.delete(one_key, headers=admin)

    [created] = _records(db, f"{FEDERATION}/issuers")
    assert (created.method, created.status_code, created.actor_id) == ("POST", 201, "ADM001")
    [added] = _records(db, keys)
    assert (added.method, added.status_code) == ("POST", 201)
    retired, deleted = sorted(_records(db, one_key), key=lambda r: r.id)
    assert (retired.method, retired.status_code) == ("PATCH", 200)
    assert (deleted.method, deleted.status_code) == ("DELETE", 204)


def test_a_refusal_is_recorded_too(client, unit_admin, db):
    """A unit admin trying the registry is exactly what an audit trail is for."""
    client.request("POST", f"{FEDERATION}/issuers", json={}, headers=unit_admin)

    [record] = _records(db, f"{FEDERATION}/issuers")
    assert (record.status_code, record.actor_id) == (403, "UAD001")


def test_a_read_is_not_recorded(client, admin, db):
    client.get(f"{FEDERATION}/issuers", headers=admin)

    assert _records(db, f"{FEDERATION}/issuers") == []
