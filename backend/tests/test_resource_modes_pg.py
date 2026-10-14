# Copyright 2026 Chronos Ledger Contributors
# Licensed under the Apache License, Version 2.0
"""Resource modes on a real PostgreSQL, where the two guarantees are made.

The exclusive rule is the exclusion constraint, now partial on
mode = 'EXCLUSIVE', so a pooled or shared hold is out of its reach and an
exclusive one is not. The pooled rule is a sum checked under the resource's
row lock (FOR UPDATE), which SQLite compiles to nothing, so the SQLite suite
cannot show that forty callers at once leave a pool of twelve with twelve.
This file can.

Skipped without TEST_DATABASE_URL, the same as the other *_pg.py files.
"""

import asyncio
import datetime
import os
import uuid
from contextlib import contextmanager

import httpx
import pytest
from sqlalchemy import create_engine, delete, text, update
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.core.database import get_db, get_session_opener
from app.core.schema import ensure_schema
from app.core.security import hash_password
from app.main import app
from app.models.db import (
    InstitutionalRole,
    Reservation,
    ReservationStatus,
    Resource,
    ResourceMode,
    User,
)

DATABASE_URL = os.environ.get("TEST_DATABASE_URL")

pytestmark = pytest.mark.skipif(
    not DATABASE_URL,
    reason="needs a real PostgreSQL: set TEST_DATABASE_URL",
)

ADMIN_PASSWORD = "AdminPass123!"
DAY = datetime.date(2026, 4, 6)
CALLERS = 40
CAPACITY = 12


@pytest.fixture(scope="module")
def engine():
    # A pool as large as the crowd, so every caller has a connection and the
    # only thing any of them waits on is the row lock.
    built = create_engine(DATABASE_URL, pool_size=CALLERS, max_overflow=5)
    ensure_schema(built)
    yield built
    built.dispose()


@pytest.fixture()
def db(engine):
    """A session whose work is thrown away when the test ends."""
    connection = engine.connect()
    transaction = connection.begin()
    session = Session(bind=connection, join_transaction_mode="create_savepoint")
    try:
        yield session
    finally:
        session.close()
        transaction.rollback()
        connection.close()


def _hold(resource: Resource, start: int, end: int, key: str) -> Reservation:
    return Reservation(
        resource_id=resource.id,
        reserved_date=DAY,
        time_window_start=datetime.time(start),
        time_window_end=datetime.time(end),
        purpose="Ward round",
        idempotency_key=key,
        request_fingerprint="0" * 64,
        mode=resource.mode,
        status=ReservationStatus.HELD,
    )


def _resource(db, code: str, mode: ResourceMode, capacity: int | None = None) -> Resource:
    resource = Resource(code=code, label=code, mode=mode, capacity=capacity)
    db.add(resource)
    db.commit()
    return resource


def test_the_constraint_is_still_on_the_table(db):
    found = db.execute(
        text(
            "SELECT contype FROM pg_constraint WHERE conname = 'ex_reservations_no_overlap'"
            " AND conrelid = 'reservations'::regclass"
        )
    ).scalar()
    assert found == "x", "create_all did not put the exclusion constraint on the table"


def test_two_exclusive_holds_still_cannot_share_an_hour(db):
    room = _resource(db, "PG-MODE-ROOM", ResourceMode.EXCLUSIVE)
    db.add(_hold(room, 9, 11, "first"))
    db.commit()

    db.add(_hold(room, 10, 12, "second"))
    with pytest.raises(IntegrityError) as refused:
        db.commit()
    assert "ex_reservations_no_overlap" in str(refused.value.orig)


def test_pooled_and_shared_holds_are_out_of_the_constraints_reach(db):
    vents = _resource(db, "PG-MODE-POOL", ResourceMode.POOLED, CAPACITY)
    lounge = _resource(db, "PG-MODE-SHARED", ResourceMode.SHARED)
    for resource in (vents, lounge):
        db.add(_hold(resource, 9, 11, f"{resource.code}-a"))
        db.add(_hold(resource, 10, 12, f"{resource.code}-b"))
    db.commit()

    held = db.query(Reservation).filter(Reservation.resource_id.in_([vents.id, lounge.id]))
    assert held.count() == 4


def test_turning_overlapping_holds_exclusive_is_refused_by_the_database(db):
    """The backstop under PATCH /resources: the mode is rewritten onto the rows."""
    vents = _resource(db, "PG-MODE-TURN", ResourceMode.POOLED, CAPACITY)
    db.add(_hold(vents, 9, 11, "a"))
    db.add(_hold(vents, 10, 12, "b"))
    db.commit()

    # The constraint is not deferred, so the UPDATE itself is refused.
    with pytest.raises(IntegrityError) as refused:
        db.execute(
            update(Reservation)
            .where(Reservation.resource_id == vents.id)
            .values(mode=ResourceMode.EXCLUSIVE)
        )
    db.rollback()
    assert "ex_reservations_no_overlap" in str(refused.value.orig)


def test_a_pool_needs_a_capacity_in_the_database_too(db):
    db.add(Resource(code="PG-MODE-NOCAP", label="No capacity", mode=ResourceMode.POOLED))
    with pytest.raises(IntegrityError) as refused:
        db.commit()
    assert "ck_resources_pool_capacity" in str(refused.value.orig)


@pytest.fixture()
def crowd(engine):
    """An admin and a pool of twelve, really committed, and removed afterwards.

    Committed because every caller below has a session of its own, and none
    of them can see into a transaction the test has open.
    """
    run = uuid.uuid4().hex[:8]
    admin_id = f"PGM{run}"
    with Session(engine) as session:
        session.add(
            User(
                id=admin_id,
                full_name="Postgres Admin",
                email_address=f"pg-modes-{run}@test.internal",
                credential_secure_hash=hash_password(ADMIN_PASSWORD),
                role_type=InstitutionalRole.ORG_ADMIN,
                initial_login_state=False,
            )
        )
        vents = Resource(
            code=f"PG-VENT-{run}", label="Ventilators", mode=ResourceMode.POOLED, capacity=CAPACITY
        )
        session.add(vents)
        session.commit()
        ids = (vents.id, admin_id, f"pg-modes-{run}@test.internal")
    try:
        yield ids
    finally:
        resource_id, user_id, _ = ids
        with Session(engine) as session:
            session.execute(delete(Reservation).where(Reservation.resource_id == resource_id))
            session.execute(delete(Resource).where(Resource.id == resource_id))
            session.execute(delete(User).where(User.id == user_id))
            session.commit()


async def _crowd(email: str, resource_id: int) -> list[httpx.Response]:
    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://testserver") as client:
        token = await client.post(
            "/api/v1/auth/login", json={"email": email, "password": ADMIN_PASSWORD}
        )
        assert token.status_code == 200, token.text
        bearer = {"Authorization": f"Bearer {token.json()['access_token']}"}

        def book(n: int):
            return client.post(
                f"/api/v1/resources/{resource_id}/reservations",
                headers={**bearer, "Idempotency-Key": f"pg-crowd-{n:04d}"},
                json={
                    "date": DAY.isoformat(),
                    "start": "09:00:00",
                    "end": "10:00:00",
                    "purpose": f"Patient {n}",
                },
            )

        return await asyncio.gather(*(book(n) for n in range(CALLERS)))


def test_forty_callers_at_once_get_exactly_twelve_of_twelve(engine, crowd):
    """Forty bookings of one unit each, on a pool of twelve, all at once.

    Every caller has its own session and its own connection, so the only
    thing that orders them is the FOR UPDATE on the resource row. Without it
    each would count the bookings committed before it started, several would
    see room for one more at the same moment, and the pool would end above
    twelve.
    """
    resource_id, _, email = crowd

    def own_session():
        session = Session(engine)
        try:
            yield session
        finally:
            session.close()

    @contextmanager
    def own_open_session():
        # AuditMiddleware writes in a session of its own; left alone it opens
        # one on the configured database_url, not this one.
        with Session(engine) as session:
            yield session

    app.dependency_overrides[get_db] = own_session
    app.dependency_overrides[get_session_opener] = lambda: own_open_session
    try:
        # One event loop for all forty, as a server has. The app's
        # ConcurrencyGate holds an asyncio.Semaphore, and a TestClient gives
        # each request a loop of its own, which that semaphore refuses. The
        # handlers still run side by side in the threadpool. ASGITransport
        # also skips the app's startup, which would connect to the configured
        # database rather than this one.
        answers = asyncio.run(_crowd(email, resource_id))
    finally:
        app.dependency_overrides.clear()

    codes = sorted(answer.status_code for answer in answers)
    assert codes.count(201) == CAPACITY, [
        answer.text for answer in answers if answer.status_code >= 500
    ]
    assert codes.count(409) == CALLERS - CAPACITY
    refused = [answer.json() for answer in answers if answer.status_code == 409]
    assert {body["code"] for body in refused} == {"RESOURCE_CAPACITY_EXCEEDED"}
    assert {body["detail"]["taken"] for body in refused} == {CAPACITY}

    with Session(engine) as check:
        held = (
            check.query(Reservation)
            .filter(
                Reservation.resource_id == resource_id,
                Reservation.status == ReservationStatus.HELD,
            )
            .count()
        )
    assert held == CAPACITY
