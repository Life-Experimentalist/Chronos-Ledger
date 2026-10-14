# Copyright 2026 Chronos Ledger Contributors
# Licensed under the Apache License, Version 2.0
"""Resource requirements on a real PostgreSQL, where a race over a child is settled.

A booking holds what its resource requires inside its own transaction. Two
bookings of different rooms that need the same crew for the same hour are
decided by the row locks the walk takes on the crew and, behind them, by the
exclusion constraint on reservations. SQLite takes neither lock, so only this
file can show that one of them wins and the other is refused with nothing
left behind.

Skipped without TEST_DATABASE_URL, the same as the other *_pg.py files.
"""

import asyncio
import datetime
import os
import uuid
from contextlib import contextmanager

import httpx
import pytest
from sqlalchemy import create_engine, delete, text
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.core.database import get_db, get_session_opener
from app.core.schema import ensure_schema
from app.core.security import hash_password
from app.main import app
from app.models.db import (
    InstitutionalRole,
    RequirementEnforcement,
    RequirementOwner,
    Reservation,
    ReservationStatus,
    Resource,
    ResourceMode,
    ResourceRequirement,
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
CALLERS = 8


@pytest.fixture(scope="module")
def engine():
    built = create_engine(DATABASE_URL, pool_size=CALLERS + 2, max_overflow=5)
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


def _resource(db, code, mode=ResourceMode.EXCLUSIVE, capacity=None):
    resource = Resource(code=code, label=code, mode=mode, capacity=capacity)
    db.add(resource)
    db.commit()
    return resource


def _hold(resource, start, end, key, parent_id=None):
    return Reservation(
        resource_id=resource.id,
        reserved_date=DAY,
        time_window_start=datetime.time(start),
        time_window_end=datetime.time(end),
        purpose="Surgery",
        idempotency_key=key,
        request_fingerprint="0" * 64,
        mode=resource.mode,
        status=ReservationStatus.HELD,
        parent_reservation_id=parent_id,
    )


def test_a_child_hold_is_inside_the_exclusion_constraints_reach(db):
    room = _resource(db, "PG-REQ-ROOM")
    crew = _resource(db, "PG-REQ-CREW")
    parent = _hold(room, 9, 10, "pg-req-parent")
    db.add(parent)
    db.commit()
    db.add(_hold(crew, 9, 11, "pg-req-child-1", parent_id=parent.id))
    db.commit()

    db.add(_hold(crew, 10, 12, "pg-req-child-2", parent_id=parent.id))
    with pytest.raises(IntegrityError) as refused:
        db.commit()
    assert "ex_reservations_no_overlap" in str(refused.value.orig)


def test_a_requirement_with_two_targets_is_refused_by_the_database(db):
    room = _resource(db, "PG-REQ-OWNER")
    crew = _resource(db, "PG-REQ-TARGET")
    db.add(
        ResourceRequirement(
            owner_kind=RequirementOwner.RESOURCE,
            owner_id=room.id,
            target_resource_id=crew.id,
            target_kind=ResourceType.PERSON,
        )
    )
    with pytest.raises(IntegrityError) as refused:
        db.commit()
    assert "ck_resource_requirements_one_target" in str(refused.value.orig)


def test_the_requirements_table_is_on_the_database(db):
    found = db.execute(text("SELECT to_regclass('resource_requirements') IS NOT NULL")).scalar()
    assert found is True


@pytest.fixture()
def crowd(engine):
    """An admin, one crew and a room per caller, really committed, and removed afterwards."""
    run = uuid.uuid4().hex[:8]
    admin_id = f"PGQ{run}"
    email = f"pg-requirements-{run}@test.internal"
    with Session(engine) as session:
        session.add(
            User(
                id=admin_id,
                full_name="Postgres Admin",
                email_address=email,
                credential_secure_hash=hash_password(ADMIN_PASSWORD),
                role_type=InstitutionalRole.ORG_ADMIN,
                initial_login_state=False,
            )
        )
        crew = Resource(code=f"PG-CREW-{run}", label="Crew")
        rooms = [Resource(code=f"PG-OR-{run}-{n}", label=f"Room {n}") for n in range(CALLERS)]
        session.add(crew)
        session.add_all(rooms)
        session.commit()
        session.add_all(
            ResourceRequirement(
                owner_kind=RequirementOwner.RESOURCE,
                owner_id=room.id,
                target_resource_id=crew.id,
                enforcement=RequirementEnforcement.REQUIRED,
            )
            for room in rooms
        )
        session.commit()
        made = (crew.id, [room.id for room in rooms], admin_id, email)
    try:
        yield made
    finally:
        crew_id, room_ids, user_id, _ = made
        everything = [crew_id, *room_ids]
        with Session(engine) as session:
            # Children first: parent_reservation_id is a foreign key.
            session.execute(
                delete(Reservation).where(
                    Reservation.resource_id.in_(everything),
                    Reservation.parent_reservation_id.is_not(None),
                )
            )
            session.execute(delete(Reservation).where(Reservation.resource_id.in_(everything)))
            session.execute(
                delete(ResourceRequirement).where(ResourceRequirement.owner_id.in_(room_ids))
            )
            session.execute(delete(Resource).where(Resource.id.in_(everything)))
            session.execute(delete(User).where(User.id == user_id))
            session.commit()


async def _crowd(email: str, room_ids: list[int]) -> list[httpx.Response]:
    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://testserver") as client:
        token = await client.post(
            "/api/v1/auth/login", json={"email_address": email, "password": ADMIN_PASSWORD}
        )
        assert token.status_code == 200, token.text
        bearer = {"Authorization": f"Bearer {token.json()['access_token']}"}

        def book(n: int, room_id: int):
            return client.post(
                f"/api/v1/resources/{room_id}/reservations",
                headers={**bearer, "Idempotency-Key": f"pg-req-{n:04d}"},
                json={
                    "date": DAY.isoformat(),
                    "start": "09:00:00",
                    "end": "10:00:00",
                    "purpose": f"Surgery {n}",
                },
            )

        return await asyncio.gather(*(book(n, room_id) for n, room_id in enumerate(room_ids)))


def test_callers_at_once_for_one_crew_leave_exactly_one_booking(engine, crowd):
    """Eight rooms, each needing the same crew for the same hour, booked together.

    One booking wins the crew. The rest are refused with
    REQUIREMENT_UNSATISFIED, and a refused booking leaves no room hold behind,
    because the room hold and the crew hold are one transaction.
    """
    crew_id, room_ids, _, email = crowd

    def own_session():
        session = Session(engine)
        try:
            yield session
        finally:
            session.close()

    @contextmanager
    def own_open_session():
        with Session(engine) as session:
            yield session

    app.dependency_overrides[get_db] = own_session
    app.dependency_overrides[get_session_opener] = lambda: own_open_session
    try:
        answers = asyncio.run(_crowd(email, room_ids))
    finally:
        app.dependency_overrides.clear()

    codes = sorted(answer.status_code for answer in answers)
    assert codes.count(201) == 1, [a.text for a in answers if a.status_code >= 500]
    assert codes.count(409) == CALLERS - 1
    refused = [answer.json() for answer in answers if answer.status_code == 409]
    assert {body["code"] for body in refused} == {"REQUIREMENT_UNSATISFIED"}

    with Session(engine) as check:
        held = (
            check.query(Reservation)
            .filter(
                Reservation.resource_id.in_([crew_id, *room_ids]),
                Reservation.status == ReservationStatus.HELD,
            )
            .all()
        )
    assert len(held) == 2
    assert {row.resource_id for row in held} - {crew_id} <= set(room_ids)
    (child,) = [row for row in held if row.resource_id == crew_id]
    (parent,) = [row for row in held if row.resource_id != crew_id]
    assert child.parent_reservation_id == parent.id
