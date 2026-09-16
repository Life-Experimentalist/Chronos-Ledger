# Copyright 2026 Chronos Ledger Contributors
# Licensed under the Apache License, Version 2.0
"""Every write through the API leaves one audit record, and nothing else does.

The record says when, which account, which key, the method, the path and the
status. It never holds a body. GET /audit reads them back for a SUPER_ADMIN.
"""

import datetime
from datetime import UTC

import pytest

from app.core.security import hash_api_key
from app.models.db import ApiKey, AuditRecord
from tests.conftest import ADMIN_PASSWORD, MEMBER_PASSWORD, login

CYCLES = "/api/v1/schedule/cycles"
AUDIT = "/api/v1/audit/"
SCOPED_KEY = "ck_test_schedule_read_only_key_000000"


def _cycle():
    today = datetime.date.today()
    return {
        "cycle_label": "Audited",
        "date_bounds_start": str(today),
        "date_bounds_end": str(today + datetime.timedelta(days=30)),
    }


def _records(db, path=CYCLES):
    db.expire_all()
    return db.query(AuditRecord).filter(AuditRecord.path == path).all()


def test_a_write_is_recorded_with_its_account_and_status(client, db, seed_users):
    headers = login(client, "admin@test.internal", ADMIN_PASSWORD)
    assert client.post(CYCLES, headers=headers, json=_cycle()).status_code == 200
    [record] = _records(db)
    assert (record.actor_id, record.api_key_id) == ("ADM001", None)
    assert (record.method, record.status_code) == ("POST", 200)


def test_a_read_is_not_recorded(client, db, seed_users):
    headers = login(client, "admin@test.internal", ADMIN_PASSWORD)
    assert client.get(CYCLES, headers=headers).status_code == 200
    assert _records(db) == []


def test_a_login_is_recorded_and_its_password_is_not(client, db, seed_users):
    login(client, "admin@test.internal", ADMIN_PASSWORD)
    [record] = _records(db, "/api/v1/auth/login")
    assert record.status_code == 200
    stored = " ".join(str(v) for v in vars(record).values())
    assert ADMIN_PASSWORD not in stored


def test_a_write_refused_for_role_is_recorded(client, db, seed_users):
    headers = login(client, "member@test.internal", MEMBER_PASSWORD)
    assert client.post(CYCLES, headers=headers, json=_cycle()).status_code == 403
    [record] = _records(db)
    assert (record.actor_id, record.status_code) == ("STU001", 403)


def test_a_write_with_no_credentials_is_recorded_without_an_account(client, db, seed_users):
    assert client.post(CYCLES, json=_cycle()).status_code == 401
    [record] = _records(db)
    assert (record.actor_id, record.status_code) == (None, 401)


def test_a_write_refused_by_key_scope_names_the_key(client, db, seed_users):
    key = ApiKey(
        key_hash=hash_api_key(SCOPED_KEY),
        key_prefix=SCOPED_KEY[:12],
        label="read only",
        user_id="ADM001",
        scopes="schedule:read",
    )
    db.add(key)
    db.commit()
    res = client.post(CYCLES, headers={"X-API-Key": SCOPED_KEY}, json=_cycle())
    assert res.status_code == 403
    [record] = _records(db)
    assert (record.actor_id, record.api_key_id, record.status_code) == ("ADM001", key.id, 403)


def test_a_failed_audit_write_does_not_fail_the_request(client, db, seed_users, monkeypatch):
    headers = login(client, "admin@test.internal", ADMIN_PASSWORD)

    def broken(*_args, **_kwargs):
        raise RuntimeError("audit table unavailable")

    monkeypatch.setattr("app.core.audit.datetime", type("Broken", (), {"now": broken}))
    assert client.post(CYCLES, headers=headers, json=_cycle()).status_code == 200
    assert _records(db) == []


@pytest.fixture()
def history(db, seed_users):
    now = datetime.datetime.now(UTC)
    rows = [
        ("ADM001", now - datetime.timedelta(days=3)),
        ("FAC001", now - datetime.timedelta(days=2)),
        ("ADM001", now - datetime.timedelta(days=1)),
    ]
    for actor, at in rows:
        db.add(
            AuditRecord(
                at=at, actor_id=actor, method="POST", path="/api/v1/seeded", status_code=200
            )
        )
    db.commit()
    return now


def _seeded(res):
    return [r for r in res.json() if r["path"] == "/api/v1/seeded"]


def test_records_come_back_newest_first(client, history):
    headers = login(client, "admin@test.internal", ADMIN_PASSWORD)
    res = client.get(AUDIT, headers=headers)
    assert res.status_code == 200
    stamps = [r["at"] for r in res.json()]
    assert stamps == sorted(stamps, reverse=True)
    assert res.headers["X-Total-Count"] == str(len(res.json()))


def test_actor_id_narrows_to_that_account(client, history):
    headers = login(client, "admin@test.internal", ADMIN_PASSWORD)
    rows = _seeded(client.get(AUDIT, headers=headers, params={"actor_id": "FAC001"}))
    assert [r["actor_id"] for r in rows] == ["FAC001"]


def test_to_before_from_is_refused(client, history):
    headers = login(client, "admin@test.internal", ADMIN_PASSWORD)
    params = {"from": "2026-01-10", "to": "2026-01-01"}
    assert client.get(AUDIT, headers=headers, params=params).status_code == 422


def test_a_date_range_leaves_out_records_outside_it(client, history):
    headers = login(client, "admin@test.internal", ADMIN_PASSWORD)
    far = {"from": "2000-01-01", "to": "2000-12-31"}
    assert _seeded(client.get(AUDIT, headers=headers, params=far)) == []
    wide = {"from": "2000-01-01", "to": "2100-12-31"}
    assert len(_seeded(client.get(AUDIT, headers=headers, params=wide))) == 3


def test_a_member_cannot_read_the_audit_log(client, history):
    headers = login(client, "member@test.internal", MEMBER_PASSWORD)
    assert client.get(AUDIT, headers=headers).status_code == 403
