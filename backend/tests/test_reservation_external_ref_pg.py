# Copyright 2026 Chronos Ledger Contributors
# Licensed under the Apache License, Version 2.0
"""uq_reservations_requester_ref on a real PostgreSQL.

SQLite enforces the unique constraint too, and the suite tests it there. What
it cannot say is that PostgreSQL treats nulls the same way, which is the whole
reason the column may be left unset on any number of rows, or that the name
the endpoint's race branch reads off a refusal is the name PostgreSQL gives.

Skipped unless TEST_DATABASE_URL points at an empty database:

    TEST_DATABASE_URL=postgresql://user:pass@localhost:5432/chronos_test \\
        pytest tests/test_reservation_external_ref_pg.py
"""

import datetime
import os
from contextlib import contextmanager

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.api.v1.endpoints import resources
from app.core.database import get_db, get_session_opener
from app.core.schema import ensure_schema
from app.core.security import hash_password
from app.main import app
from app.models.db import (
    InstitutionalRole,
    Reservation,
    ReservationStatus,
    Resource,
    ResourceType,
    User,
)

DATABASE_URL = os.environ.get("TEST_DATABASE_URL")

pytestmark = pytest.mark.skipif(
    not DATABASE_URL,
    reason="needs a real PostgreSQL: set TEST_DATABASE_URL",
)

ADMIN_PASSWORD = "AdminPass123!"
DAY = datetime.date(2026, 4, 6)


@pytest.fixture(scope="module")
def engine():
    built = create_engine(DATABASE_URL)
    ensure_schema(built)
    yield built
    built.dispose()


@pytest.fixture()
def db(engine):
    """A session whose work is rolled back when the test ends, the same as in
    test_reservation_overlap_pg.py, so these can run twice on one database."""
    connection = engine.connect()
    transaction = connection.begin()
    session = Session(bind=connection, join_transaction_mode="create_savepoint")
    try:
        yield session
    finally:
        session.close()
        transaction.rollback()
        connection.close()


@pytest.fixture()
def admin(db):
    user = User(
        id="PGREF",
        full_name="Postgres Admin",
        email_address="pg-ref@test.internal",
        credential_secure_hash=hash_password(ADMIN_PASSWORD),
        role_type=InstitutionalRole.ORG_ADMIN,
        initial_login_state=False,
    )
    db.add(user)
    db.commit()
    return user


@pytest.fixture()
def resource(db):
    room = Resource(code="PG-REF-1", label="Reference Lab", resource_type=ResourceType.ROOM)
    db.add(room)
    db.commit()
    return room


def _hold(resource_id: int, hour: int, key: str, ref: str | None, requester: str = "PGREF"):
    return Reservation(
        resource_id=resource_id,
        reserved_date=DAY,
        time_window_start=datetime.time(hour, 0),
        time_window_end=datetime.time(hour + 1, 0),
        purpose="Ward round",
        requested_by_id=requester,
        idempotency_key=key,
        request_fingerprint="0" * 64,
        external_ref=ref,
        status=ReservationStatus.HELD,
    )


def test_any_number_of_rows_may_leave_the_reference_unset(db, admin, resource):
    db.add_all(_hold(resource.id, 8 + n, f"no-ref-{n}", None) for n in range(3))
    db.commit()

    held = db.query(Reservation).filter(Reservation.resource_id == resource.id).count()
    assert held == 3


def test_one_requester_cannot_use_a_reference_twice(db, admin, resource):
    db.add(_hold(resource.id, 9, "first", "ext-001"))
    db.commit()

    db.add(_hold(resource.id, 11, "second", "ext-001"))
    with pytest.raises(IntegrityError) as refused:
        db.commit()
    assert "uq_reservations_requester_ref" in str(refused.value.orig)


def test_two_requesters_may_share_a_reference(db, admin, resource):
    db.add(
        User(
            id="PGREF2",
            full_name="Second Admin",
            email_address="pg-ref-2@test.internal",
            credential_secure_hash=hash_password(ADMIN_PASSWORD),
            role_type=InstitutionalRole.ORG_ADMIN,
            initial_login_state=False,
        )
    )
    db.commit()
    db.add(_hold(resource.id, 9, "mine", "ext-001"))
    db.add(_hold(resource.id, 11, "theirs", "ext-001", requester="PGREF2"))
    db.commit()


def test_the_loser_of_a_race_for_a_reference_is_told_who_won(db, admin, resource, monkeypatch):
    """The endpoint's race branch against the constraint PostgreSQL raises.

    Blinding the reference check once puts the endpoint where the loser of a
    race is. The refusal has to be read as a taken reference and answered
    with the winner's id, not as a reused key.
    """
    winner = _hold(resource.id, 9, "already-held", "ext-001")
    db.add(winner)
    db.commit()

    def override_get_db():
        yield db

    @contextmanager
    def override_open_session():
        yield db

    app.dependency_overrides[get_db] = override_get_db
    app.dependency_overrides[get_session_opener] = lambda: override_open_session
    try:
        client = TestClient(app)
        token = client.post(
            "/api/v1/auth/login",
            json={"email_address": "pg-ref@test.internal", "password": ADMIN_PASSWORD},
        )
        assert token.status_code == 200, token.text
        headers = {
            "Authorization": f"Bearer {token.json()['access_token']}",
            "Idempotency-Key": "a-ref-key-never-used",
        }

        honest = resources._by_ref
        seen = []

        def blind_once(*args, **kwargs):
            seen.append(1)
            return None if len(seen) == 1 else honest(*args, **kwargs)

        monkeypatch.setattr(resources, "_by_ref", blind_once)
        loser = client.post(
            f"/api/v1/resources/{resource.id}/reservations",
            headers=headers,
            json={
                "date": DAY.isoformat(),
                "start": "14:00:00",
                "end": "15:00:00",
                "purpose": "Second ward round",
                "external_ref": "ext-001",
            },
        )
    finally:
        app.dependency_overrides.clear()

    assert loser.status_code == 409, loser.text
    assert loser.json()["code"] == "RESERVATION_EXTERNAL_REF_TAKEN"
    assert loser.json()["detail"]["reservation_id"] == winner.id
    assert len(seen) == 2
