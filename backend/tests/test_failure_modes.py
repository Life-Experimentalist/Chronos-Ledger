# Copyright 2026 Chronos Ledger Contributors
# Licensed under the Apache License, Version 2.0
"""What a caller sees when something underneath fails, case by case.

docs/failure-modes.md is the page these hold up. Each failure is made by
fault injection (an engine that cannot connect, a commit that raises, a
settle step that never runs, a clock set back), never by stopping a real
service. The one exception is the embedded child process, which is this
test's own child and is killed for real, because what the host sees then
is the thing being checked. The PostgreSQL cases, a connection terminated
by the server in the middle of a transaction, are in test_failure_modes_pg.py.
"""

import time
from contextlib import contextmanager
from datetime import UTC, datetime, timedelta

import httpx
import pytest
from fastapi.testclient import TestClient
from sqlalchemy.exc import OperationalError
from sqlalchemy.orm import sessionmaker

from app.core import clock, idempotency
from app.core.database import Base, get_db, get_session_opener, sqlite_engine
from app.main import app
from app.models.db import IdempotencyRecord, InstitutionalRole, Resource, User
from tests.conftest import ADMIN_PASSWORD, login

REPLAYED = "Idempotency-Replayed"


def _create_room(client, headers, key, code="LH-201"):
    return client.post(
        "/api/v1/resources/", json={"code": code}, headers={**headers, "Idempotency-Key": key}
    )


def _assert_database_unavailable(res):
    assert res.status_code == 503, res.text
    assert res.json() == {
        "detail": "Database unavailable, try again shortly.",
        "code": "DATABASE_UNAVAILABLE",
    }
    assert res.headers["Retry-After"] == "1"


# -- The database is down -----------------------------------------------------


def test_a_database_that_cannot_be_reached_is_a_503_with_a_code(client, db, seed_users, tmp_path):
    """Down at connect: a read and a keyed write both get 503, and the retry runs once."""
    admin = login(client, "admin@test.internal", ADMIN_PASSWORD)
    # No such directory, so the driver cannot open the file: the same
    # OperationalError a refused PostgreSQL connection raises.
    unreachable = sqlite_engine(f"sqlite:///{(tmp_path / 'missing' / 'x.db').as_posix()}")
    Unreachable = sessionmaker(bind=unreachable)

    def down():
        with Unreachable() as session:
            yield session

    app.dependency_overrides[get_db] = down
    try:
        _assert_database_unavailable(client.get("/api/v1/resources/", headers=admin))
        _assert_database_unavailable(_create_room(client, admin, "outage-1"))
    finally:
        unreachable.dispose()

    def up():
        yield db

    app.dependency_overrides[get_db] = up
    assert db.query(IdempotencyRecord).count() == 0

    retry = _create_room(client, admin, "outage-1")
    assert retry.status_code == 201, retry.text
    assert REPLAYED not in retry.headers
    assert db.query(Resource).count() == 1


@pytest.fixture()
def file_client(tmp_path, seed_users):
    """A client on a SQLite file with a session per request, as in production.

    The shared in-memory session would carry a failed request's transaction
    into the next one, which a real request never does.
    """
    engine = sqlite_engine(f"sqlite:///{(tmp_path / 'drop.db').as_posix()}")
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
    drops = []

    def own_session():
        with Session() as session:
            if drops:
                drops.pop()

                def dropped():
                    # What psycopg raises when the server goes away under a
                    # transaction. Nothing reached the database.
                    raise OperationalError(
                        "COMMIT", None, Exception("server closed the connection unexpectedly")
                    )

                session.commit = dropped
            yield session

    @contextmanager
    def open_session():
        with Session() as session:
            yield session

    app.dependency_overrides[get_db] = own_session
    app.dependency_overrides[get_session_opener] = lambda: open_session
    try:
        yield TestClient(app), Session, drops
    finally:
        app.dependency_overrides.clear()
        engine.dispose()


def test_a_connection_dropped_mid_transaction_commits_nothing(file_client):
    """The commit fails: 503, no room, no claim, and the retry runs as new."""
    client, Session, drops = file_client
    admin = login(client, "admin@test.internal", ADMIN_PASSWORD)

    drops.append(True)
    _assert_database_unavailable(_create_room(client, admin, "drop-1"))
    with Session() as session:
        assert session.query(Resource).count() == 0
        assert session.query(IdempotencyRecord).count() == 0

    retry = _create_room(client, admin, "drop-1")
    assert retry.status_code == 201, retry.text
    assert REPLAYED not in retry.headers
    with Session() as session:
        assert session.query(Resource).count() == 1


# -- The process stopped between the commit and the recorded response --------


def test_a_write_committed_just_before_the_process_died_answers_409(
    client, db, seed_users, monkeypatch
):
    """The claim committed with the room; the response was never recorded.

    _settle not running is what a process killed in that window looks like.
    The retry is refused rather than run twice, until the key expires, and
    the caller learns the outcome by reading the room.
    """
    admin = login(client, "admin@test.internal", ADMIN_PASSWORD)
    with monkeypatch.context() as patch:
        patch.setattr(idempotency, "_settle", lambda *_args: None)
        first = _create_room(client, admin, "died-1")
    assert first.status_code == 201, first.text

    retry = _create_room(client, admin, "died-1")
    assert retry.status_code == 409
    assert retry.json()["code"] == "IDEMPOTENCY_KEY_IN_PROGRESS"
    assert retry.headers["Retry-After"] == "1"
    assert db.query(Resource).count() == 1

    listed = client.get("/api/v1/resources/", headers=admin)
    assert [room["code"] for room in listed.json()] == ["LH-201"]


def test_an_embedded_process_killed_and_restarted_keeps_what_it_committed(
    tmp_path, embedded_process
):
    """Killed outright: the host sees the connection go, starts it again, loses nothing."""
    headers = {
        "Authorization": f"Host {'h' * 40}",
        "X-Chronos-Actor": "H-1",
        "X-Chronos-Actor-Role": "ORG_ADMIN",
    }
    child = embedded_process("--data-dir", str(tmp_path), "--port", "0")
    base = f"http://127.0.0.1:{child.ready()['port']}"
    with httpx.Client(base_url=base, headers=headers, timeout=60) as api:
        first = _create_room(api, {}, "killed-1")
        assert first.status_code == 201, first.text
        # Until the response is recorded the key answers 409; wait for the
        # replay, so the kill below lands after it.
        for _ in range(50):
            again = _create_room(api, {}, "killed-1")
            if again.status_code != 409:
                break
            time.sleep(0.1)
        assert again.headers.get(REPLAYED) == "true", again.text

    child.kill()
    with pytest.raises(httpx.TransportError):
        httpx.get(f"{base}/api/v1/config", headers=headers, timeout=5)

    restarted = embedded_process("--data-dir", str(tmp_path), "--port", "0")
    base = f"http://127.0.0.1:{restarted.ready()['port']}"
    with httpx.Client(base_url=base, headers=headers, timeout=60) as api:
        assert [room["code"] for room in api.get("/api/v1/resources/").json()] == ["LH-201"]
        retry = _create_room(api, {}, "killed-1")
        assert retry.status_code == 201
        assert retry.headers[REPLAYED] == "true"
        assert retry.content == first.content
    assert restarted.leave() == 0


# -- The system clock steps backwards -----------------------------------------


class _SteppedClock:
    """A system clock somebody set back. Not a HostClock: nothing refuses the step."""

    def __init__(self, instant: datetime) -> None:
        self.instant = instant

    def now(self) -> datetime:
        return self.instant


def test_a_system_clock_set_back_loses_no_replay_and_refuses_nothing(client, db, seed_users):
    admin = login(client, "admin@test.internal", ADMIN_PASSWORD)
    stepped = _SteppedClock(datetime(2026, 9, 7, 12, 0, tzinfo=UTC))
    clock.install(stepped)
    try:
        assert not clock.is_host()
        first = _create_room(client, admin, "stepped-1")
        assert first.status_code == 201, first.text

        stepped.instant -= timedelta(hours=2)
        retry = _create_room(client, admin, "stepped-1")
        assert retry.status_code == 201
        assert retry.headers[REPLAYED] == "true"
        assert retry.content == first.content

        fresh = _create_room(client, admin, "stepped-2", code="LH-202")
        assert fresh.status_code == 201, fresh.text
        assert REPLAYED not in fresh.headers
    finally:
        clock.reset()
    assert db.query(Resource).count() == 2
