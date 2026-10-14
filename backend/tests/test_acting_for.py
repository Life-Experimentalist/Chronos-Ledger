# Copyright 2026 Chronos Ledger Contributors
# Licensed under the Apache License, Version 2.0
"""One service account speaking for many people: X-Chronos-Actor on an API key.

A key holding the impersonate scope may name a user in its own organization,
and the request then runs as that user. It only ever narrows. The key's area
scopes and the named user's role both have to allow a request, and every
refusal, including a refused attempt to use the header, leaves an audit record
holding the key's own account and the id that was asked for.
"""

import datetime

import pytest

from app.core import rate_limit
from app.core.organization import DEFAULT_ORGANIZATION_ID
from app.core.security import hash_api_key, hash_password
from app.models.db import ApiKey, AuditRecord, InstitutionalRole, Organization, User
from tests.conftest import ADMIN_PASSWORD, login

ME = "/api/v1/auth/me"
USERS = "/api/v1/users/"
CYCLES = "/api/v1/schedule/cycles"
AUDIT = "/api/v1/audit/"
CHECK_IN = "/api/v1/guest/register-checkin"
ACTING_FOR = "X-Chronos-Actor"
OTHER_ORGANIZATION = "elsewhere"

SERVICE = "SVC001"
KEYS = {
    "narrow": "ck_test_acting_for_narrow_key_000001",
    "impersonate_only": "ck_test_acting_for_all_areas_000002",
    "wildcard": "ck_test_acting_for_wildcard_key_0003",
    "no_scope": "ck_test_acting_for_without_scope_04",
    "everything": "ck_test_acting_for_star_and_scope05",
}


def _user(user_id, role, **extra):
    return User(
        id=user_id,
        full_name=user_id,
        email_address=f"{user_id.lower()}@test.internal",
        credential_secure_hash=hash_password("Unused-Password-1"),
        role_type=role,
        initial_login_state=False,
        **extra,
    )


def _key(db, name, scopes, user_id=SERVICE):
    row = ApiKey(
        key_hash=hash_api_key(KEYS[name]),
        key_prefix=KEYS[name][:12],
        label=name,
        user_id=user_id,
        scopes=scopes,
    )
    db.add(row)
    db.commit()
    return row


def _as(name, acting_for=None):
    headers = {"X-API-Key": KEYS[name]}
    if acting_for is not None:
        headers[ACTING_FOR] = acting_for
    return headers


@pytest.fixture()
def world(db, seed_users):
    """A service account, a second administrator, a disabled account and a stranger.

    The service account is a MEMBER on purpose: whatever the key may do while
    acting for somebody has to come from that person and from the key's scopes,
    never from the account the key happens to be bound to.
    """
    db.add(Organization(id=OTHER_ORGANIZATION, name="Elsewhere"))
    db.add_all(
        [
            _user(SERVICE, InstitutionalRole.MEMBER),
            _user("ADM002", InstitutionalRole.ORG_ADMIN),
            _user(
                "GONE01",
                InstitutionalRole.STAFF,
                deactivated_at=datetime.datetime.now(datetime.UTC),
            ),
            _user("OUT001", InstitutionalRole.ORG_ADMIN, organization_id=OTHER_ORGANIZATION),
        ]
    )
    db.commit()
    keys = {
        "narrow": _key(db, "narrow", "auth:read,impersonate"),
        "users": _key(db, "impersonate_only", "auth:read,users:read,guest:write,impersonate"),
        "wildcard": _key(db, "wildcard", "*"),
        "no_scope": _key(db, "no_scope", "auth:read,users:read"),
        "everything": _key(db, "everything", "*,impersonate"),
    }
    return keys


def _cycle(label="Acting for"):
    today = datetime.date.today()
    return {
        "cycle_label": label,
        "date_bounds_start": str(today),
        "date_bounds_end": str(today + datetime.timedelta(days=30)),
    }


def _audit_rows(db, path=None):
    db.expire_all()
    q = db.query(AuditRecord)
    if path is not None:
        q = q.filter(AuditRecord.path == path)
    return q.order_by(AuditRecord.id).all()


# --- acting as the named person ------------------------------------------------


def test_the_request_runs_as_the_named_user(client, world):
    res = client.get(ME, headers=_as("narrow", "FAC001"))
    assert res.status_code == 200, res.text
    assert res.json()["id"] == "FAC001"

    res = client.get(ME, headers=_as("narrow", "STU001"))
    assert res.json()["id"] == "STU001"


def test_without_the_header_the_key_is_still_the_account_it_is_bound_to(client, world):
    res = client.get(ME, headers=_as("narrow"))
    assert res.status_code == 200
    assert res.json()["id"] == SERVICE


def test_the_header_is_trimmed(client, world):
    res = client.get(ME, headers=_as("narrow", "  FAC001 "))
    assert res.status_code == 200
    assert res.json()["id"] == "FAC001"


# --- who may send it -------------------------------------------------------------


def test_a_key_without_the_scope_is_refused(client, world):
    res = client.get(ME, headers=_as("no_scope", "FAC001"))
    assert res.status_code == 403
    assert res.json()["code"] == "IMPERSONATION_NOT_ALLOWED"


def test_the_wildcard_scope_does_not_carry_it(client, world):
    res = client.get(ME, headers=_as("wildcard", "FAC001"))
    assert res.status_code == 403
    assert res.json()["code"] == "IMPERSONATION_NOT_ALLOWED"


def test_a_key_naming_both_the_wildcard_and_the_scope_may(client, world):
    res = client.get(ME, headers=_as("everything", "FAC001"))
    assert res.status_code == 200
    assert res.json()["id"] == "FAC001"


def test_a_signed_in_person_is_refused(client, world):
    headers = login(client, "admin@test.internal", ADMIN_PASSWORD)
    res = client.get(ME, headers={**headers, ACTING_FOR: "FAC001"})
    assert res.status_code == 403
    assert res.json()["code"] == "IMPERSONATION_NOT_ALLOWED"


def test_an_empty_header_is_refused_and_not_ignored(client, world):
    res = client.get(ME, headers=_as("narrow", ""))
    assert res.status_code == 403
    assert res.json()["code"] == "IMPERSONATION_REFUSED"


def test_a_key_can_only_be_given_the_scope_by_naming_it(client, db, seed_users):
    headers = login(client, "admin@test.internal", ADMIN_PASSWORD)
    plain = client.post(
        "/api/v1/api-keys/", headers=headers, json={"label": "plain", "user_id": "ADM001"}
    )
    assert plain.json()["scopes"] == "*"
    named = client.post(
        "/api/v1/api-keys/",
        headers=headers,
        json={"label": "named", "user_id": "ADM001", "scopes": ["users:read", "impersonate"]},
    )
    assert named.status_code == 201
    assert named.json()["scopes"] == "impersonate,users:read"


def test_a_misspelt_scope_is_still_refused_at_creation(client, db, seed_users):
    headers = login(client, "admin@test.internal", ADMIN_PASSWORD)
    res = client.post(
        "/api/v1/api-keys/",
        headers=headers,
        json={"label": "typo", "user_id": "ADM001", "scopes": ["impersonation"]},
    )
    assert res.status_code == 422


# --- who may be named --------------------------------------------------------------


def test_an_unknown_id_and_another_organizations_id_are_refused_alike(client, world):
    unknown = client.get(ME, headers=_as("narrow", "NOBODY"))
    elsewhere = client.get(ME, headers=_as("narrow", "OUT001"))
    assert unknown.status_code == elsewhere.status_code == 403
    assert unknown.json() == elsewhere.json()
    assert unknown.json()["code"] == "IMPERSONATION_REFUSED"


def test_a_deactivated_account_is_refused_with_the_same_answer(client, world):
    gone = client.get(ME, headers=_as("narrow", "GONE01"))
    unknown = client.get(ME, headers=_as("narrow", "NOBODY"))
    assert gone.status_code == 403
    assert gone.json() == unknown.json()


def test_an_id_longer_than_any_account_is_refused(client, world):
    res = client.get(ME, headers=_as("narrow", "X" * 80))
    assert res.status_code == 403
    assert res.json()["code"] == "IMPERSONATION_REFUSED"


# --- narrow only ---------------------------------------------------------------------


def test_the_user_may_but_the_key_may_not(client, world):
    """ADM001 can list users. The key holds no users scope, so it cannot."""
    res = client.get(USERS, headers=_as("narrow", "ADM001"))
    assert res.status_code == 403
    assert res.json()["code"] == "SCOPE_MISSING"


def test_the_key_may_but_the_user_may_not(client, world):
    """The key holds users:read. A member cannot list users, so it cannot."""
    res = client.get(USERS, headers=_as("impersonate_only", "STU001"))
    assert res.status_code == 403
    assert res.json()["code"] == "INSUFFICIENT_ROLE"


def test_when_both_allow_the_request_goes_through(client, world):
    res = client.get(USERS, headers=_as("impersonate_only", "ADM001"))
    assert res.status_code == 200
    assert {u["id"] for u in res.json()} >= {"ADM001", "FAC001"}


def test_the_service_accounts_own_role_grants_nothing(client, world):
    """Bound to a MEMBER, acting for an administrator: the administrator's role applies, not the member's."""
    assert client.get(USERS, headers=_as("impersonate_only")).status_code == 403
    assert client.get(USERS, headers=_as("impersonate_only", "ADM002")).status_code == 200


@pytest.mark.parametrize(
    ("method", "path", "body"),
    [
        ("post", "/api/v1/api-keys/", {"label": "wider", "user_id": "ADM002", "scopes": ["*"]}),
        (
            "post",
            "/api/v1/auth/change-password",
            {"current_password": "Unused-Password-1", "new_password": "Another-Password-2"},
        ),
        ("post", "/api/v1/users/FAC001/reset-password", None),
        ("post", "/api/v1/federation/issuers", {}),
    ],
)
def test_a_key_acting_for_an_administrator_cannot_touch_credentials(
    client, db, world, method, path, body
):
    """Every scope and an administrator to act for, and still no key, password or issuer."""
    keys_before = db.query(ApiKey).count()
    res = getattr(client, method)(path, json=body, headers=_as("everything", "ADM002"))
    assert res.status_code == 403, res.text
    assert res.json()["code"] == "IMPERSONATION_NOT_ALLOWED"
    db.expire_all()
    assert db.query(ApiKey).count() == keys_before
    rows = _audit_rows(db, path)
    assert rows and rows[-1].acting_for_user_id == "ADM002"


def test_reads_in_the_credential_areas_still_work_for_someone(client, world):
    res = client.get("/api/v1/api-keys/", headers=_as("everything", "ADM002"))
    assert res.status_code == 200, res.text


def test_without_the_header_the_refusal_is_the_ordinary_one(client, world):
    """The refusal is about acting for someone, not about the scope itself."""
    res = client.post(
        "/api/v1/api-keys/",
        json={"label": "plain", "user_id": "STU001", "scopes": ["schedule:read"]},
        headers={"X-API-Key": KEYS["everything"]},
    )
    # Bound to a MEMBER, so the role check refuses it, not the acting-for rule.
    assert res.status_code == 403
    assert res.json()["code"] == "INSUFFICIENT_ROLE"


# --- the caller stays the key ----------------------------------------------------------


def test_the_audit_record_holds_both_identities(client, db, world):
    key = world["everything"]
    res = client.post(CYCLES, headers=_as("everything", "ADM002"), json=_cycle())
    assert res.status_code == 200, res.text
    [record] = _audit_rows(db, CYCLES)
    assert record.actor_id == SERVICE
    assert record.api_key_id == key.id
    assert record.acting_for_user_id == "ADM002"
    assert (record.method, record.status_code) == ("POST", 200)
    assert record.organization_id == DEFAULT_ORGANIZATION_ID


def test_a_write_without_the_header_leaves_the_field_empty(client, db, world):
    # The service account is a MEMBER, so this is refused, and a refused write
    # is recorded all the same.
    assert client.post(CYCLES, headers=_as("everything"), json=_cycle()).status_code == 403
    [record] = _audit_rows(db, CYCLES)
    assert record.actor_id == SERVICE
    assert record.acting_for_user_id is None


def test_a_refused_attempt_is_recorded_with_the_id_asked_for(client, db, world):
    key = world["no_scope"]
    res = client.get(ME, headers=_as("no_scope", "FAC001"))
    assert res.status_code == 403
    [record] = _audit_rows(db, ME)
    assert record.actor_id == SERVICE
    assert record.api_key_id == key.id
    assert record.acting_for_user_id == "FAC001"
    assert record.status_code == 403
    assert record.organization_id == DEFAULT_ORGANIZATION_ID


def test_a_refused_name_is_recorded_whether_or_not_it_exists(client, db, world):
    client.get(ME, headers=_as("narrow", "NOBODY"))
    client.get(ME, headers=_as("narrow", "OUT001"))
    rows = _audit_rows(db, ME)
    assert [r.acting_for_user_id for r in rows] == ["NOBODY", "OUT001"]
    assert {r.status_code for r in rows} == {403}


def test_an_overlong_id_is_recorded_cut_to_the_column(client, db, world):
    client.get(ME, headers=_as("narrow", "X" * 80))
    [record] = _audit_rows(db, ME)
    assert record.acting_for_user_id == "X" * 50


def test_a_signed_in_persons_refused_attempt_is_recorded(client, db, world):
    headers = login(client, "admin@test.internal", ADMIN_PASSWORD)
    client.post(CYCLES, headers={**headers, ACTING_FOR: "FAC001"}, json=_cycle())
    [record] = _audit_rows(db, CYCLES)
    assert (record.actor_id, record.api_key_id) == ("ADM001", None)
    assert (record.acting_for_user_id, record.status_code) == ("FAC001", 403)
    assert record.organization_id == DEFAULT_ORGANIZATION_ID


def test_a_read_that_works_is_not_recorded_even_when_acting_for_someone(client, db, world):
    assert client.get(ME, headers=_as("narrow", "FAC001")).status_code == 200
    assert _audit_rows(db) == []


def test_a_refused_write_is_recorded_once(client, db, world):
    client.post(CYCLES, headers=_as("no_scope", "ADM002"), json=_cycle())
    assert len(_audit_rows(db, CYCLES)) == 1


def test_the_audit_list_shows_the_field(client, db, world):
    client.post(CYCLES, headers=_as("everything", "ADM002"), json=_cycle())
    headers = login(client, "admin@test.internal", ADMIN_PASSWORD)
    rows = client.get(AUDIT, headers=headers).json()
    [row] = [r for r in rows if r["path"] == CYCLES]
    assert (row["actor_id"], row["acting_for_user_id"]) == (SERVICE, "ADM002")


def test_a_refused_attempt_shows_in_the_organizations_audit_list(client, db, world):
    client.get(ME, headers=_as("no_scope", "FAC001"))
    headers = login(client, "admin@test.internal", ADMIN_PASSWORD)
    rows = client.get(AUDIT, headers=headers).json()
    [row] = [r for r in rows if r["path"] == ME]
    assert (row["acting_for_user_id"], row["status_code"]) == ("FAC001", 403)


# --- rate limits and idempotency follow the key ----------------------------------------


def test_the_visitor_rate_limit_counts_the_key_and_not_the_named_user(client, world, monkeypatch):
    counted = []
    monkeypatch.setattr(rate_limit, "guard", lambda bucket, subject, *a: counted.append(subject))
    monkeypatch.setattr(rate_limit, "spend", lambda bucket, subject, *a: counted.append(subject))
    body = {
        "guest_name": "Visitor One",
        "contact_phone": "+1 555 0100 100",
        "originating_body": "A supplier",
        "target_staff_id": "FAC001",
        "visitation_intent": "Deliver the monthly supplies",
    }
    for person in ("STU001", "ADM002"):
        res = client.post(CHECK_IN, headers=_as("impersonate_only", person), json=body)
        assert res.status_code == 200, res.text
    assert counted == [SERVICE] * 4


def test_an_idempotency_key_belongs_to_the_key_and_the_person_it_was_sent_for(client, db, world):
    headers = {**_as("everything", "ADM001"), "Idempotency-Key": "once-0001"}
    first = client.post(CYCLES, headers=headers, json=_cycle())
    again = client.post(CYCLES, headers=headers, json=_cycle())
    assert first.status_code == again.status_code == 200
    assert again.headers["Idempotency-Replayed"] == "true"
    assert again.json() == first.json()

    # The same key and body for somebody else is not a retry, and does not
    # replay the first person's response.
    other = client.post(CYCLES, headers={**headers, ACTING_FOR: "ADM002"}, json=_cycle())
    assert other.status_code == 422
    assert other.json()["code"] == "IDEMPOTENCY_KEY_REUSED"

    from app.models.db import IdempotencyRecord

    db.expire_all()
    [stored] = db.query(IdempotencyRecord).all()
    assert stored.caller.startswith("key:")
