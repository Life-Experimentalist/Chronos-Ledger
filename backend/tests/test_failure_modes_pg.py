# Copyright 2026 Chronos Ledger Contributors
# Licensed under the Apache License, Version 2.0
"""PostgreSQL going away in the middle of a request, for real.

test_failure_modes.py fakes a dropped connection by making a commit raise.
This one has PostgreSQL itself end the request's backend, with
pg_terminate_backend from a second connection, while the request is inside
its transaction: the claim on the Idempotency-Key is written and the room is
about to be. That is what a restart or a failover does to a request in
flight, and it shows the claim goes with the rest of the transaction.

Skipped without a real PostgreSQL. Point TEST_DATABASE_URL at an empty
database, as for test_reservation_overlap_pg.py:

    TEST_DATABASE_URL=postgresql://user:pass@localhost:5432/chronos_test \\
        pytest tests/test_failure_modes_pg.py
"""

import os
import time
import uuid
from contextlib import contextmanager

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, event, text
from sqlalchemy.orm import sessionmaker

from app.core.database import get_db, get_session_opener
from app.core.schema import ensure_schema
from app.core.security import create_access_token
from app.main import app
from app.models.db import AuditRecord, IdempotencyRecord, InstitutionalRole, Resource, User

DATABASE_URL = os.environ.get("TEST_DATABASE_URL")

pytestmark = pytest.mark.skipif(
    not DATABASE_URL,
    reason="needs a real PostgreSQL: set TEST_DATABASE_URL",
)

REPLAYED = "Idempotency-Replayed"


@pytest.fixture(scope="module")
def engine():
    """The schema the server builds on start, on an empty PostgreSQL."""
    built = create_engine(DATABASE_URL)
    ensure_schema(built)
    yield built
    built.dispose()


@pytest.fixture()
def api(engine):
    """A client whose requests each get their own session on the real database.

    Not the savepoint-wrapped session the overlap tests use: the connection
    under the request is destroyed here, and nothing could be rolled back on
    it afterwards. Every row this makes carries a fresh suffix and is deleted
    by it at the end, so the file can run twice on the same database.
    """
    Session = sessionmaker(autocommit=False, autoflush=False, bind=engine)
    suffix = uuid.uuid4().hex[:8]
    user_id = f"PGF{suffix}"
    with Session() as session:
        session.add(
            User(
                id=user_id,
                full_name="Failure Admin",
                email_address=f"pg-failure-{suffix}@test.internal",
                credential_secure_hash="not-a-password-hash",
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
    headers = {"Authorization": f"Bearer {create_access_token(user_id, {'role': 'ORG_ADMIN'})}"}
    code = f"PGF-{suffix}"
    try:
        yield TestClient(app), Session, headers, code, user_id
    finally:
        app.dependency_overrides.clear()
        with Session() as session:
            session.query(Resource).filter(Resource.code == code).delete()
            session.query(IdempotencyRecord).filter(
                IdempotencyRecord.caller == f"user:{user_id}"
            ).delete()
            session.query(AuditRecord).filter(AuditRecord.actor_id == user_id).delete()
            session.query(User).filter(User.id == user_id).delete()
            session.commit()


def _terminate_on_insert(engine, table: str):
    """Before the first INSERT into `table`, have PostgreSQL end the backend running it."""
    fired = []

    def terminate(conn, _cursor, statement, _parameters, _context, _executemany):
        if fired or not statement.lstrip().upper().startswith(f"INSERT INTO {table.upper()}"):
            return
        fired.append(True)
        probe = conn.connection.dbapi_connection.cursor()
        probe.execute("SELECT pg_backend_pid()")
        pid = probe.fetchone()[0]
        probe.close()
        with engine.connect() as other:
            other.execute(text("SELECT pg_terminate_backend(:pid)"), {"pid": pid})
            # Termination is a signal; wait until the backend has gone, so
            # the INSERT meets a closed connection rather than racing it.
            for _ in range(50):
                gone = other.execute(
                    text("SELECT count(*) FROM pg_stat_activity WHERE pid = :pid"), {"pid": pid}
                ).scalar()
                if not gone:
                    break
                time.sleep(0.1)

    event.listen(engine, "before_cursor_execute", terminate)
    return fired, lambda: event.remove(engine, "before_cursor_execute", terminate)


def test_a_backend_terminated_mid_transaction_is_a_503_and_commits_nothing(engine, api):
    client, Session, headers, code, user_id = api
    keyed = {**headers, "Idempotency-Key": f"terminated-{code}"}

    fired, remove = _terminate_on_insert(engine, "resources")
    try:
        cut = client.post("/api/v1/resources/", json={"code": code}, headers=keyed)
    finally:
        remove()

    assert fired, "the request never reached its INSERT"
    assert cut.status_code == 503, cut.text
    assert cut.json() == {
        "detail": "Database unavailable, try again shortly.",
        "code": "DATABASE_UNAVAILABLE",
    }
    assert cut.headers["Retry-After"] == "1"
    with Session() as session:
        assert session.query(Resource).filter(Resource.code == code).count() == 0
        # The claim was in the same transaction, so it went too: the retry
        # is a first use, not a 409.
        assert (
            session.query(IdempotencyRecord)
            .filter(IdempotencyRecord.caller == f"user:{user_id}")
            .count()
            == 0
        )

    retry = client.post("/api/v1/resources/", json={"code": code}, headers=keyed)
    assert retry.status_code == 201, retry.text
    assert REPLAYED not in retry.headers
    again = client.post("/api/v1/resources/", json={"code": code}, headers=keyed)
    assert again.status_code == 201
    assert again.headers[REPLAYED] == "true"
    with Session() as session:
        assert session.query(Resource).filter(Resource.code == code).count() == 1
