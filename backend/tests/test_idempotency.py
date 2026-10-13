# Copyright 2026 Chronos Ledger Contributors
# Licensed under the Apache License, Version 2.0
"""Idempotency-Key on every write: a retry gets the first answer, not a second effect.

The reservation route had a key of its own before this and keeps its own
answers; tests/test_reservations.py pins those. These pin the shared
mechanism in app.core.idempotency: what is replayed, what is refused, what is
never kept, whose key it is, how long it lasts, and two copies at once.
"""

import threading
from contextlib import contextmanager
from datetime import UTC, datetime, timedelta

import pytest
from fastapi.testclient import TestClient
from pydantic import ValidationError
from sqlalchemy.orm import sessionmaker

from app.api.v1.endpoints import resources as resources_endpoint
from app.core import clock
from app.core.config import Settings
from app.core.database import Base, get_db, get_session_opener, sqlite_engine
from app.core.idempotency import purge_expired, request_hash
from app.main import app
from app.models.db import ApiKey, IdempotencyRecord, InstitutionalRole, Resource, User
from tests.conftest import ADMIN_PASSWORD, MEMBER_PASSWORD, login

REPLAYED = "Idempotency-Replayed"


def _create_room(client, headers, key, code="LH-201"):
    return client.post(
        "/api/v1/resources/", json={"code": code}, headers={**headers, "Idempotency-Key": key}
    )


def _issue_key(client, headers):
    res = client.post(
        "/api/v1/api-keys/",
        json={
            "label": "Integration",
            "user_id": "ADM001",
            "scopes": ["resources:read", "resources:write"],
        },
        headers=headers,
    )
    assert res.status_code == 201, res.text
    return res.json()


def _second_admin(db, seed_users):
    # The seed admin's hash, so no second bcrypt round.
    db.add(
        User(
            id="ADM002",
            full_name="Admin Two",
            email_address="admin2@test.internal",
            credential_secure_hash=seed_users["admin"].credential_secure_hash,
            role_type=InstitutionalRole.ORG_ADMIN,
            initial_login_state=False,
        )
    )
    db.commit()


# -- Replays ------------------------------------------------------------------


def test_a_retried_post_gets_the_first_response_and_makes_one_room(client, db, seed_users):
    admin = login(client, "admin@test.internal", ADMIN_PASSWORD)

    first = _create_room(client, admin, "create-room-1")
    again = _create_room(client, admin, "create-room-1")

    assert first.status_code == 201, first.text
    assert REPLAYED not in first.headers
    assert again.status_code == 201
    assert again.headers[REPLAYED] == "true"
    assert again.content == first.content
    # Without the key the second request would have been 409, code taken.
    assert db.query(Resource).count() == 1


def test_a_retried_patch_is_answered_and_not_run_again(client, db, seed_users):
    admin = login(client, "admin@test.internal", ADMIN_PASSWORD)
    room = _create_room(client, admin, "make-it").json()
    url = f"/api/v1/resources/{room['id']}"

    first = client.patch(url, json={"label": "First"}, headers={**admin, "Idempotency-Key": "p-1"})
    # Somebody else changes it in between.
    client.patch(url, json={"label": "Second"}, headers=admin)
    again = client.patch(url, json={"label": "First"}, headers={**admin, "Idempotency-Key": "p-1"})

    assert first.status_code == 200, first.text
    assert again.headers[REPLAYED] == "true"
    assert again.content == first.content
    db.expire_all()
    # Run again, the retry would have put "First" back.
    assert db.get(Resource, room["id"]).label == "Second"


def test_a_retried_delete_is_answered_with_the_first_204(client, db, seed_users):
    admin = login(client, "admin@test.internal", ADMIN_PASSWORD)
    issued = _issue_key(client, admin)
    url = f"/api/v1/api-keys/{issued['id']}"

    first = client.delete(url, headers={**admin, "Idempotency-Key": "revoke-1"})
    again = client.delete(url, headers={**admin, "Idempotency-Key": "revoke-1"})

    assert first.status_code == 204, first.text
    assert again.status_code == 204
    assert again.headers[REPLAYED] == "true"
    assert again.content == first.content == b""
    # Run again, the key would have been gone and the answer 404.
    assert client.delete(url, headers=admin).status_code == 404
    assert db.query(ApiKey).count() == 0


def test_a_refusal_is_replayed_too(client, db, seed_users):
    """The request ran and was refused, and would be refused the same way."""
    admin = login(client, "admin@test.internal", ADMIN_PASSWORD)
    headers = {**admin, "Idempotency-Key": "missing-1"}

    first = client.patch("/api/v1/resources/999", json={"label": "X"}, headers=headers)
    again = client.patch("/api/v1/resources/999", json={"label": "X"}, headers=headers)

    assert first.status_code == 404
    assert again.status_code == 404
    assert again.headers[REPLAYED] == "true"
    assert again.content == first.content


def test_key_order_and_spacing_in_the_body_are_the_same_request():
    assert request_hash("POST", "/p", b"b=2&a=1", b'{"x": 1, "y": 2}') == request_hash(
        "POST", "/p", b"a=1&b=2", b'{"y":2,"x":1}'
    )
    assert request_hash("POST", "/p", b"a=1", b"{}") != request_hash("POST", "/p", b"a=2", b"{}")


# -- Refusals -----------------------------------------------------------------


def test_the_same_key_for_a_different_request_is_409(client, db, seed_users):
    admin = login(client, "admin@test.internal", ADMIN_PASSWORD)
    _create_room(client, admin, "confused-1", code="LH-201")

    res = _create_room(client, admin, "confused-1", code="LH-305")

    assert res.status_code == 409
    assert res.json()["code"] == "IDEMPOTENCY_KEY_REUSED"
    assert REPLAYED not in res.headers
    assert db.query(Resource).count() == 1


def test_a_retry_while_the_first_is_still_running_is_409(client, db, seed_users):
    """The claim is there and no response yet: say so, and run nothing."""
    admin = login(client, "admin@test.internal", ADMIN_PASSWORD)
    db.add(
        IdempotencyRecord(
            caller="user:ADM001",
            key="pending-1",
            request_hash=request_hash("POST", "/api/v1/resources/", b"", b'{"code": "LH-201"}'),
            created_at=clock.now(),
        )
    )
    db.commit()

    res = _create_room(client, admin, "pending-1")

    assert res.status_code == 409
    assert res.json()["code"] == "IDEMPOTENCY_KEY_IN_PROGRESS"
    assert res.headers["Retry-After"] == "1"
    assert db.query(Resource).count() == 0


@pytest.mark.parametrize("key", ["", "k" * 256])
def test_a_malformed_key_is_refused(client, db, seed_users, key):
    admin = login(client, "admin@test.internal", ADMIN_PASSWORD)

    res = _create_room(client, admin, key)

    assert res.status_code == 422
    assert res.json()["code"] == "INVALID_VALUE"
    assert db.query(Resource).count() == 0


# -- What is never kept -------------------------------------------------------


def test_a_server_error_is_not_kept_and_the_retry_runs(client, db, seed_users, monkeypatch):
    admin = login(client, "admin@test.internal", ADMIN_PASSWORD)

    def broken(**_fields):
        raise RuntimeError("the database went away")

    with monkeypatch.context() as patch:
        patch.setattr(resources_endpoint, "Resource", broken)
        failed = TestClient(app, raise_server_exceptions=False).post(
            "/api/v1/resources/",
            json={"code": "LH-201"},
            headers={**admin, "Idempotency-Key": "flaky-1"},
        )
    assert failed.status_code == 500
    assert db.query(IdempotencyRecord).count() == 0

    retry = _create_room(client, admin, "flaky-1")
    assert retry.status_code == 201, retry.text
    assert REPLAYED not in retry.headers


def test_a_forbidden_request_is_not_kept(client, db, seed_users):
    member = login(client, "member@test.internal", MEMBER_PASSWORD)

    assert _create_room(client, member, "not-mine").status_code == 403
    assert db.query(IdempotencyRecord).count() == 0


def test_an_unauthenticated_request_is_not_kept(client, db, seed_users):
    assert _create_room(client, {}, "nobody").status_code == 401
    login_res = client.post(
        "/api/v1/auth/login",
        json={"email_address": "admin@test.internal", "password": ADMIN_PASSWORD},
        headers={"Idempotency-Key": "sign-in"},
    )
    assert login_res.status_code == 200
    assert db.query(IdempotencyRecord).count() == 0


def test_a_response_carrying_a_secret_is_not_kept(client, db, seed_users):
    """A replay would hand out the same API key again, so the retry runs."""
    admin = login(client, "admin@test.internal", ADMIN_PASSWORD)
    body = {"label": "Twice", "user_id": "ADM001"}
    headers = {**admin, "Idempotency-Key": "issue-1"}

    first = client.post("/api/v1/api-keys/", json=body, headers=headers)
    again = client.post("/api/v1/api-keys/", json=body, headers=headers)

    assert first.status_code == again.status_code == 201
    assert REPLAYED not in again.headers
    assert first.json()["api_key"] != again.json()["api_key"]
    assert db.query(IdempotencyRecord).count() == 0


# -- Whose key it is ----------------------------------------------------------


def test_a_key_belongs_to_the_api_key_or_user_that_sent_it(client, db, seed_users):
    _second_admin(db, seed_users)
    admin = login(client, "admin@test.internal", ADMIN_PASSWORD)
    other_admin = login(client, "admin2@test.internal", ADMIN_PASSWORD)
    integration = {"X-API-Key": _issue_key(client, admin)["api_key"]}

    # The same key from three callers is three requests. The API key acts as
    # ADM001, and is still a caller of its own.
    for headers, code in ((admin, "LH-1"), (other_admin, "LH-2"), (integration, "LH-3")):
        res = _create_room(client, headers, "shared-key", code=code)
        assert res.status_code == 201, res.text
        assert REPLAYED not in res.headers
    assert db.query(Resource).count() == 3


def test_a_reservation_key_is_unique_per_caller(client, db, seed_users):
    _second_admin(db, seed_users)
    admin = login(client, "admin@test.internal", ADMIN_PASSWORD)
    other_admin = login(client, "admin2@test.internal", ADMIN_PASSWORD)
    room = _create_room(client, admin, "room-for-holds").json()

    for headers, start, end in ((admin, "09:00", "10:00"), (other_admin, "11:00", "12:00")):
        res = client.post(
            f"/api/v1/resources/{room['id']}/reservations",
            json={"date": "2026-01-06", "start": start, "end": end, "purpose": "Ward round"},
            headers={**headers, "Idempotency-Key": "booking-shared-0001"},
        )
        assert res.status_code == 201, res.text


# -- How long it lasts --------------------------------------------------------


def test_a_key_is_new_again_after_the_retention_window(client, db, seed_users):
    start = datetime(2026, 9, 8, 9, 0, tzinfo=UTC)
    clock.install(clock.HostClock(start))
    try:
        admin = login(client, "admin@test.internal", ADMIN_PASSWORD)
        assert _create_room(client, admin, "day-key", code="LH-1").status_code == 201

        clock.advance_to(start + timedelta(hours=23, minutes=59))
        assert _create_room(client, admin, "day-key", code="LH-2").status_code == 409

        clock.advance_to(start + timedelta(hours=24))
        res = _create_room(client, admin, "day-key", code="LH-2")
        assert res.status_code == 201, res.text
        assert REPLAYED not in res.headers
        assert db.query(IdempotencyRecord).count() == 1

        clock.advance_to(start + timedelta(hours=48, seconds=1))
        assert purge_expired(db) == 1
        assert db.query(IdempotencyRecord).count() == 0
    finally:
        clock.reset()


def test_the_window_must_be_at_least_an_hour():
    assert Settings().idempotency_retention_hours == 24
    with pytest.raises(ValidationError, match="IDEMPOTENCY_RETENTION_HOURS"):
        Settings(idempotency_retention_hours=0)


# -- Two copies at once -------------------------------------------------------


@pytest.fixture()
def file_client(tmp_path, seed_users):
    """A client on a SQLite file, so two requests really run side by side.

    The shared in-memory database has one connection and one session, which
    is what every other test wants and the one thing this test cannot have.
    """
    engine = sqlite_engine(f"sqlite:///{(tmp_path / 'race.db').as_posix()}")
    Base.metadata.create_all(bind=engine)
    Session = sessionmaker(autocommit=False, autoflush=False, bind=engine)
    with Session() as session:
        session.add(
            User(
                id="ADM001",
                full_name="Admin One",
                email_address="admin@test.internal",
                credential_secure_hash=seed_users["admin"].credential_secure_hash,
                role_type=InstitutionalRole.ORG_ADMIN,
                initial_login_state=False,
            )
        )
        session.commit()

    def own_session():
        with Session() as session:
            yield session

    @contextmanager
    def open_session():
        with Session() as session:
            yield session

    app.dependency_overrides[get_db] = own_session
    app.dependency_overrides[get_session_opener] = lambda: open_session
    try:
        yield TestClient(app), Session
    finally:
        app.dependency_overrides.clear()
        engine.dispose()


def test_two_copies_at_once_make_one_room(file_client):
    client, Session = file_client
    admin = login(client, "admin@test.internal", ADMIN_PASSWORD)
    barrier = threading.Barrier(2)
    results = []

    def send():
        barrier.wait()
        results.append(_create_room(client, admin, "race-1"))

    threads = [threading.Thread(target=send) for _ in range(2)]
    for thread in threads:
        thread.start()
    for thread in threads:
        thread.join(timeout=60)

    assert len(results) == 2
    ran = [res for res in results if REPLAYED not in res.headers and res.status_code == 201]
    assert len(ran) == 1, [(res.status_code, res.text) for res in results]
    other = next(res for res in results if res is not ran[0])
    if other.status_code == 201:
        assert other.headers[REPLAYED] == "true"
        assert other.content == ran[0].content
    else:
        assert other.status_code == 409
        assert other.json()["code"] == "IDEMPOTENCY_KEY_IN_PROGRESS"
        assert other.headers["Retry-After"] == "1"
    with Session() as session:
        assert session.query(Resource).count() == 1
        assert session.query(IdempotencyRecord).one().status_code == 201
