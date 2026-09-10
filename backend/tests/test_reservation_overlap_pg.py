# Copyright 2026 Chronos Ledger Contributors
# Licensed under the Apache License, Version 2.0
"""The tests for migration 010, which cannot run on SQLite.

The rest of the suite builds its schema with create_all against an in-memory
SQLite database. That is fast and it is blind to this: an exclusion constraint
is a Postgres construct, SQLite has none, and create_all does not run
migrations anyway. A test written the usual way would pass against a table
that has no constraint on it and prove nothing.

So these run against a real PostgreSQL and skip when there is not one. Point
TEST_DATABASE_URL at an empty database and they build the schema by running
the migrations, which is also the only thing in this suite that runs them:

    TEST_DATABASE_URL=postgresql://user:pass@localhost:5432/chronos_test \\
        pytest tests/test_reservation_overlap_pg.py
"""

import datetime
import os

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, text
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.api.v1.endpoints import resources
from app.core.database import get_db
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
OTHER_DAY = datetime.date(2026, 4, 7)


def _at(hour: int) -> datetime.time:
    return datetime.time(hour, 0)


@pytest.fixture(scope="module")
def engine():
    """A database with the migrations run against it, not create_all.

    create_all would build a reservations table with no exclusion constraint
    on it, and every test here would fail for the wrong reason. The constraint
    exists only because migration 010 says so, so the migrations are what has
    to run.

    DATABASE_URL is set because alembic's env.py reads it and lets it win over
    anything the config carries. A developer with that variable already
    pointing at their own database would otherwise have these migrations run
    against that one.
    """
    from alembic.config import Config

    from alembic import command

    previous = os.environ.get("DATABASE_URL")
    os.environ["DATABASE_URL"] = DATABASE_URL
    try:
        config = Config("alembic.ini")
        config.set_main_option("sqlalchemy.url", DATABASE_URL)
        command.upgrade(config, "head")
    finally:
        if previous is None:
            os.environ.pop("DATABASE_URL", None)
        else:
            os.environ["DATABASE_URL"] = previous

    built = create_engine(DATABASE_URL)
    yield built
    built.dispose()


@pytest.fixture()
def db(engine):
    """A session whose work is thrown away when the test ends.

    Bound to a connection with a transaction already open, so a commit inside
    a test commits a savepoint rather than the outer transaction, and rolling
    that back at the end leaves the database as it was found. It matters here
    more than usual: this is somebody's real PostgreSQL, not a fresh file per
    test, and these tests have to be able to run twice.
    """
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
def resource(db):
    room = Resource(
        code="PG-LAB-1",
        label="Overlap Lab",
        resource_type=ResourceType.ROOM,
        capacity=40,
    )
    db.add(room)
    db.commit()
    return room


def _hold(resource_id: int, start: int, end: int, key: str, day: datetime.date = DAY):
    return Reservation(
        resource_id=resource_id,
        reserved_date=day,
        time_window_start=_at(start),
        time_window_end=_at(end),
        purpose="Ward round",
        idempotency_key=key,
        request_fingerprint="0" * 64,
        status=ReservationStatus.HELD,
    )


def _held_on(db, resource_id: int) -> int:
    """Holds on one resource, not every row in the table.

    TEST_DATABASE_URL can point at a database that already has rows in it, so
    counting the whole table would make these pass or fail on what somebody
    else left behind.
    """
    return (
        db.query(Reservation)
        .filter(
            Reservation.resource_id == resource_id,
            Reservation.status == ReservationStatus.HELD,
        )
        .count()
    )


def test_the_constraint_is_actually_on_the_table(db):
    """Every other test here is only meaningful if this one passes.

    A missing constraint would turn the refusal tests into failures, but it
    would turn the four acceptance tests into passes that prove nothing. This
    one asks the catalog directly, so a table that lost the constraint says so
    once and plainly.
    """
    found = db.execute(
        text(
            "SELECT contype FROM pg_constraint WHERE conname = 'ex_reservations_no_overlap'"
            " AND conrelid = 'reservations'::regclass"
        )
    ).scalar()
    assert found == "x", "migration 010 did not leave an exclusion constraint behind"


def test_two_holds_on_one_resource_cannot_share_an_hour(db, resource):
    db.add(_hold(resource.id, 9, 11, "first"))
    db.commit()

    db.add(_hold(resource.id, 10, 12, "second"))
    with pytest.raises(IntegrityError) as refused:
        db.commit()
    assert "ex_reservations_no_overlap" in str(refused.value.orig)


def test_a_hold_may_begin_where_another_ends(db, resource):
    """Half open, the same rule the application's own check uses.

    Ten to eleven and eleven to twelve are not a clash. Getting this wrong in
    the constraint and right in the application would make the database refuse
    bookings the endpoint had already accepted.
    """
    db.add(_hold(resource.id, 10, 11, "earlier"))
    db.commit()

    db.add(_hold(resource.id, 11, 12, "later"))
    db.commit()

    assert _held_on(db, resource.id) == 2


def test_a_cancelled_hold_stops_occupying_the_window(db, resource):
    let_go = _hold(resource.id, 9, 11, "released")
    let_go.status = ReservationStatus.CANCELLED
    db.add(let_go)
    db.commit()

    db.add(_hold(resource.id, 9, 11, "took-it-after"))
    db.commit()

    assert _held_on(db, resource.id) == 1


def test_the_same_window_on_another_resource_is_not_a_clash(db, resource):
    other = Resource(
        code="PG-LAB-2",
        label="Second Lab",
        resource_type=ResourceType.ROOM,
        capacity=40,
    )
    db.add(other)
    db.commit()

    db.add(_hold(resource.id, 9, 11, "here"))
    db.add(_hold(other.id, 9, 11, "there"))
    db.commit()

    assert _held_on(db, resource.id) == 1
    assert _held_on(db, other.id) == 1


def test_the_same_window_on_another_date_is_not_a_clash(db, resource):
    """The date is inside the range, not merely alongside it.

    A constraint built over the times alone would refuse this, and would
    refuse every second day of a room booked at the same hour each morning.
    """
    db.add(_hold(resource.id, 9, 11, "monday"))
    db.add(_hold(resource.id, 9, 11, "tuesday", day=OTHER_DAY))
    db.commit()

    assert _held_on(db, resource.id) == 2


def test_a_hold_may_run_past_midnight(db, resource):
    """The row migration 009's constraint refused and 011 allows.

    Worth a test of its own rather than only a step inside the overlap ones:
    if the check constraint were still >, every test below would fail for
    that reason instead of the one it was written for.
    """
    db.add(_hold(resource.id, 22, 6, "night-shift"))
    db.commit()

    assert _held_on(db, resource.id) == 1


def test_two_holds_cannot_share_an_hour_across_midnight(db, resource):
    """Migration 010's CASE, exercised by a row for the first time.

    It was written before anything could produce a window that needed it,
    which meant the expression was checked and its effect was not. A hold
    running to six and one starting at five the same morning are two rows on
    two dates, and the constraint has to see them as one clash.
    """
    db.add(_hold(resource.id, 22, 6, "night-shift"))
    db.commit()

    db.add(_hold(resource.id, 5, 7, "early-round", day=OTHER_DAY))
    with pytest.raises(IntegrityError) as refused:
        db.commit()
    assert "ex_reservations_no_overlap" in str(refused.value.orig)


def test_a_hold_may_begin_where_an_overnight_one_ends(db, resource):
    """Half open across midnight, not only within a day. A handover at six is
    how a shift rota works, and a constraint that refused it would make every
    night shift block the morning after it."""
    db.add(_hold(resource.id, 22, 6, "night-shift"))
    db.commit()

    db.add(_hold(resource.id, 6, 14, "day-shift", day=OTHER_DAY))
    db.commit()

    assert _held_on(db, resource.id) == 2


def test_the_database_refuses_an_overlap_the_endpoint_did_not_see(db, resource, monkeypatch):
    """The branch that exists for the race, reached without running a race.

    Two callers both passing the check before either inserts is the thing the
    constraint was added for, and it cannot be staged reliably from a test.
    Blinding the check to a hold that is already there puts the endpoint in
    exactly the state the loser of that race is in: it believes the window is
    free, it inserts, and the database refuses it.

    What is being proved is the answer it gives. Before the constraint existed
    this path ran into the idempotency handling and came back 422 saying the
    caller had reused a key it had never used before.
    """
    db.add(
        User(
            id="PGADM",
            full_name="Postgres Admin",
            email_address="pg-admin@test.internal",
            credential_secure_hash=hash_password(ADMIN_PASSWORD),
            role_type=InstitutionalRole.SUPER_ADMIN,
            initial_login_state=False,
        )
    )
    winner = _hold(resource.id, 9, 11, "already-held")
    db.add(winner)
    db.commit()

    def override_get_db():
        yield db

    app.dependency_overrides[get_db] = override_get_db
    try:
        client = TestClient(app)
        token = client.post(
            "/api/v1/auth/login",
            json={"email": "pg-admin@test.internal", "password": ADMIN_PASSWORD},
        )
        assert token.status_code == 200, token.text
        headers = {
            "Authorization": f"Bearer {token.json()['access_token']}",
            "Idempotency-Key": "a-key-never-used-before",
        }

        honest = resources._conflicts_for
        seen = []

        def blind_once(*args, **kwargs):
            # Blind going in, honest coming back. The endpoint has to believe
            # the window is free to reach the branch at all, and then has to
            # find the row that beat it, or the caller is told it lost without
            # being told to what.
            seen.append(1)
            return [] if len(seen) == 1 else honest(*args, **kwargs)

        monkeypatch.setattr(resources, "_conflicts_for", blind_once)
        blind = client.post(
            f"/api/v1/resources/{resource.id}/reservations",
            headers=headers,
            json={
                "date": DAY.isoformat(),
                "start": "10:00:00",
                "end": "12:00:00",
                "purpose": "Second ward round",
            },
        )
    finally:
        app.dependency_overrides.clear()

    assert blind.status_code == 409, blind.text
    detail = blind.json()["detail"]
    assert detail["message"] == resources.ALREADY_TAKEN
    assert [entry["reservation_id"] for entry in detail["conflicts"]] == [winner.id]
    assert len(seen) == 2, "the endpoint never asked again after the database refused it"


def test_the_409_for_an_overnight_loser_still_names_what_beat_it(db, resource, monkeypatch):
    """The gap the comment in the endpoint used to describe, now closed.

    While the check compared times inside one date and the constraint did
    not, a caller whose overnight booking the database refused was told 409
    with an empty list: it had lost to something the endpoint could not see
    to name. _conflicts_for now expands both dates a wrapping window touches,
    so the row that won is found on the second ask.
    """
    db.add(
        User(
            id="PGADM",
            full_name="Postgres Admin",
            email_address="pg-admin@test.internal",
            credential_secure_hash=hash_password(ADMIN_PASSWORD),
            role_type=InstitutionalRole.SUPER_ADMIN,
            initial_login_state=False,
        )
    )
    # A plain morning hold on the day after. Nothing about it crosses
    # midnight; the window being refused is the one that does.
    winner = _hold(resource.id, 5, 7, "already-held", day=OTHER_DAY)
    db.add(winner)
    db.commit()

    def override_get_db():
        yield db

    app.dependency_overrides[get_db] = override_get_db
    try:
        client = TestClient(app)
        token = client.post(
            "/api/v1/auth/login",
            json={"email": "pg-admin@test.internal", "password": ADMIN_PASSWORD},
        )
        assert token.status_code == 200, token.text
        headers = {
            "Authorization": f"Bearer {token.json()['access_token']}",
            "Idempotency-Key": "an-overnight-key-never-used",
        }

        honest = resources._conflicts_for
        seen = []

        def blind_once(*args, **kwargs):
            seen.append(1)
            return [] if len(seen) == 1 else honest(*args, **kwargs)

        monkeypatch.setattr(resources, "_conflicts_for", blind_once)
        blind = client.post(
            f"/api/v1/resources/{resource.id}/reservations",
            headers=headers,
            json={
                "date": DAY.isoformat(),
                "start": "22:00:00",
                "end": "06:00:00",
                "purpose": "Night ward round",
            },
        )
    finally:
        app.dependency_overrides.clear()

    assert blind.status_code == 409, blind.text
    detail = blind.json()["detail"]
    assert detail["message"] == resources.ALREADY_TAKEN
    assert [entry["reservation_id"] for entry in detail["conflicts"]] == [winner.id]
    assert len(seen) == 2, "the endpoint never asked again after the database refused it"
