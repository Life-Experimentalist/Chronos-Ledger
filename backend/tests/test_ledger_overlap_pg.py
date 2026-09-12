# Copyright 2026 Chronos Ledger Contributors
# Licensed under the Apache License, Version 2.0
"""The tests for migration 013, which cannot run on SQLite.

Same reason as test_reservation_overlap_pg: an exclusion constraint is a
Postgres construct, the rest of the suite builds its schema with create_all
against in-memory SQLite, and a test written the usual way would pass against
a table that has no constraint on it.

daily_ledger is the table that puts somebody at a door. Two rows naming one
room at one hour is two groups arriving at the same place, and until this
migration nothing in the database said no: the API checked the timetable and
the bookings before writing a slot, and the nightly job checked for a row it
had already written, and neither of those is the same as the room being free.

Point TEST_DATABASE_URL at an empty database and these build the schema by
running the migrations:

    TEST_DATABASE_URL=postgresql://user:pass@localhost:5432/chronos_test \\
        pytest tests/test_ledger_overlap_pg.py
"""

import datetime
import os

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, text
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.api.v1.endpoints import schedule
from app.core.database import get_db
from app.core.security import hash_password
from app.core.time import org_today
from app.cron.ledger_generator import generate_daily_ledger_entries
from app.main import app
from app.models.db import (
    Activity,
    DailyLedger,
    InstitutionalRole,
    PlanningCycle,
    Resource,
    ResourceType,
    StructuralMasterSlot,
    User,
)

DATABASE_URL = os.environ.get("TEST_DATABASE_URL")

pytestmark = pytest.mark.skipif(
    not DATABASE_URL,
    reason="needs a real PostgreSQL: set TEST_DATABASE_URL",
)

ADMIN_PASSWORD = "AdminPass123!"
CONSTRAINT = "ex_daily_ledger_no_overlap"

# A Monday, and the Tuesday after it. Everything except the endpoint test
# works on fixed dates because the constraint does not care what today is.
MONDAY = datetime.date(2026, 4, 6)
TUESDAY = datetime.date(2026, 4, 7)


def _at(hour: int) -> datetime.time:
    return datetime.time(hour, 0)


def _next_monday() -> datetime.date:
    """A Monday strictly after today.

    propagate_slot_corrections rewrites days dated after today and no others,
    so a test that wants the propagate to move a row has to put the row on a
    date that passes that filter. A fixed date would pass it for a while and
    then quietly stop.
    """
    today = org_today()
    return today + datetime.timedelta(days=(7 - today.isoweekday()) % 7 or 7)


@pytest.fixture(scope="module")
def engine():
    """A database with the migrations run against it, not create_all."""
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


@pytest.fixture()
def room(db):
    built = Resource(
        code="PG-WARD-1",
        label="Overlap Ward",
        resource_type=ResourceType.ROOM,
        capacity=30,
    )
    db.add(built)
    db.commit()
    return built


@pytest.fixture()
def cycle(db):
    built = PlanningCycle(
        cycle_label="PG Overlap Cycle",
        date_bounds_start=datetime.date(2026, 1, 1),
        date_bounds_end=datetime.date(2027, 1, 1),
        operational_status=True,
    )
    db.add(built)
    db.commit()
    return built


def _activity(db, cycle_id: int, code: str) -> Activity:
    built = Activity(
        activity_code=code,
        activity_title=f"Activity {code}",
        unit_code="CSE",
        cycle_id=cycle_id,
    )
    db.add(built)
    db.commit()
    return built


def _slot(db, activity_id: int, room_id: int, weekday: int, start: int, end: int):
    built = StructuralMasterSlot(
        day_of_week_index=weekday,
        time_window_start=_at(start),
        time_window_end=_at(end),
        activity_id=activity_id,
        resource_id=room_id,
        target_room_identifier="PG-WARD-1",
    )
    db.add(built)
    db.commit()
    return built


def _day(
    activity_id: int,
    room_id: int | None,
    date: datetime.date,
    start: int | None,
    end: int | None,
    slot_id: int | None = None,
) -> DailyLedger:
    return DailyLedger(
        target_date=date,
        time_window_start=None if start is None else _at(start),
        time_window_end=None if end is None else _at(end),
        master_slot_id=slot_id,
        activity_id=activity_id,
        resource_id=room_id,
    )


def _days_on(db, room_id: int, date: datetime.date) -> list[DailyLedger]:
    """Days on one room on one date, not every row in the table.

    TEST_DATABASE_URL can point at a database that already has rows in it, so
    counting the whole table would make these pass or fail on what somebody
    else left behind.
    """
    return (
        db.query(DailyLedger)
        .filter(DailyLedger.resource_id == room_id, DailyLedger.target_date == date)
        .order_by(DailyLedger.time_window_start)
        .all()
    )


def test_the_constraint_is_actually_on_the_table(db):
    """Every other test here is only meaningful if this one passes.

    A missing constraint turns the refusal tests into failures, which is
    noisy and obvious. It turns the acceptance tests into passes that prove
    nothing, which is neither. This one asks the catalog directly.
    """
    found = db.execute(
        text(
            f"SELECT contype FROM pg_constraint WHERE conname = '{CONSTRAINT}'"
            " AND conrelid = 'daily_ledger'::regclass"
        )
    ).scalar()
    assert found == "x", "migration 013 did not leave an exclusion constraint behind"


def test_two_days_on_one_room_cannot_share_an_hour(db, room, cycle):
    activity = _activity(db, cycle.id, "PG-CLASH-A")
    db.add(_day(activity.id, room.id, MONDAY, 9, 11))
    db.commit()

    db.add(_day(activity.id, room.id, MONDAY, 10, 12))
    with pytest.raises(IntegrityError) as refused:
        db.commit()
    assert CONSTRAINT in str(refused.value.orig)


def test_a_day_may_begin_where_another_ends(db, room, cycle):
    """Half open, the same rule everywhere else.

    Back to back is the normal shape of a teaching day and of a shift rota.
    A constraint that refused it and an application that allowed it would
    mean the nightly job dropped every second class.
    """
    activity = _activity(db, cycle.id, "PG-ADJ")
    db.add(_day(activity.id, room.id, MONDAY, 10, 11))
    db.add(_day(activity.id, room.id, MONDAY, 11, 12))
    db.commit()

    assert len(_days_on(db, room.id, MONDAY)) == 2


def test_the_same_window_on_another_date_is_not_a_clash(db, room, cycle):
    activity = _activity(db, cycle.id, "PG-DATES")
    db.add(_day(activity.id, room.id, MONDAY, 9, 11))
    db.add(_day(activity.id, room.id, TUESDAY, 9, 11))
    db.commit()

    assert len(_days_on(db, room.id, MONDAY)) == 1
    assert len(_days_on(db, room.id, TUESDAY)) == 1


def test_two_days_cannot_share_an_hour_across_midnight(db, room, cycle):
    """The CASE in the migration, which is the overnight rule a third time.

    A day running 22:00 to 06:00 finishes on the date after the one it is
    dated, so it and a day dated the next morning at five are one clash on
    two rows on two dates. window_span says so in Python and migration 010
    says so for reservations; this says so for generated days.
    """
    activity = _activity(db, cycle.id, "PG-NIGHT")
    db.add(_day(activity.id, room.id, MONDAY, 22, 6))
    db.commit()

    db.add(_day(activity.id, room.id, TUESDAY, 5, 7))
    with pytest.raises(IntegrityError) as refused:
        db.commit()
    assert CONSTRAINT in str(refused.value.orig)


def test_a_day_may_begin_where_an_overnight_one_ends(db, room, cycle):
    activity = _activity(db, cycle.id, "PG-HANDOVER")
    db.add(_day(activity.id, room.id, MONDAY, 22, 6))
    db.add(_day(activity.id, room.id, TUESDAY, 6, 14))
    db.commit()

    assert len(_days_on(db, room.id, MONDAY)) == 1
    assert len(_days_on(db, room.id, TUESDAY)) == 1


def test_days_with_no_window_do_not_occupy_anything(db, room, cycle):
    """The reason the predicate names the two time columns and not only the room.

    An ad-hoc day has no window by design, and so does every day orphaned
    before migration 012 gave the table its own times. tsrange(NULL, NULL)
    is not NULL and overlaps everything, so without the IS NOT NULL clauses
    the first such row would claim the room for all of time and the second
    would be refused:

        SELECT tsrange(NULL,NULL,'[)') && tsrange('2026-01-01','2026-01-02','[)');
        -- t
    """
    activity = _activity(db, cycle.id, "PG-ADHOC")
    db.add(_day(activity.id, room.id, MONDAY, None, None))
    db.add(_day(activity.id, room.id, MONDAY, None, None))
    db.add(_day(activity.id, room.id, MONDAY, 9, 11))
    db.commit()

    assert len(_days_on(db, room.id, MONDAY)) == 3


def test_days_with_no_room_do_not_clash_with_each_other(db, room, cycle):
    """A NULL room is exempt because = returns NULL, not because of the WHERE.

    Two online-only days at the same hour are not in a room and are not a
    clash. This is the half of the predicate Postgres handles on its own,
    and it is here so that a future edit narrowing the WHERE clause cannot
    quietly make every roomless day collide with every other.
    """
    activity = _activity(db, cycle.id, "PG-ONLINE")
    db.add(_day(activity.id, None, MONDAY, 9, 11))
    db.add(_day(activity.id, None, MONDAY, 9, 11))
    db.commit()

    kept = (
        db.query(DailyLedger)
        .filter(
            DailyLedger.activity_id == activity.id,
            DailyLedger.resource_id.is_(None),
        )
        .count()
    )
    assert kept == 2


def test_the_generator_writes_one_day_when_two_slots_want_one_room(db, room, cycle):
    """The race the constraint exists for, and what the job does about it.

    Two slots on one room at one hour is a state the API refuses to create
    and the database now refuses to materialize. Getting there needs both
    slots written straight in, which is what a closed cycle reopened, a
    direct SQL fix or an older version of this codebase leaves behind.

    Without a savepoint per row the first refusal would poison the
    transaction and the whole night would be lost. What is being proved is
    that the loser is dropped and nothing else is.
    """
    first = _activity(db, cycle.id, "PG-GEN-A")
    second = _activity(db, cycle.id, "PG-GEN-B")
    _slot(db, first.id, room.id, MONDAY.isoweekday(), 9, 11)
    _slot(db, second.id, room.id, MONDAY.isoweekday(), 10, 12)

    created = generate_daily_ledger_entries(MONDAY, db)

    assert created == 1
    days = _days_on(db, room.id, MONDAY)
    assert [(day.activity_id, day.time_window_start) for day in days] == [(first.id, _at(9))]


def test_a_refused_day_does_not_take_the_rest_of_the_night_with_it(db, room, cycle):
    """The savepoint, stated as an outcome rather than as a mechanism.

    The clash is on one room. Every other class that night is on other rooms
    and has nothing to do with it, and before the savepoint went in the
    IntegrityError from the first would have rolled all of them back.
    """
    elsewhere = Resource(
        code="PG-WARD-2",
        label="Second Ward",
        resource_type=ResourceType.ROOM,
        capacity=30,
    )
    db.add(elsewhere)
    db.commit()

    first = _activity(db, cycle.id, "PG-SURV-A")
    second = _activity(db, cycle.id, "PG-SURV-B")
    third = _activity(db, cycle.id, "PG-SURV-C")
    _slot(db, first.id, room.id, MONDAY.isoweekday(), 9, 11)
    _slot(db, second.id, room.id, MONDAY.isoweekday(), 10, 12)
    third_slot = _slot(db, third.id, elsewhere.id, MONDAY.isoweekday(), 10, 12)

    created = generate_daily_ledger_entries(MONDAY, db)

    assert created == 2
    survivors = _days_on(db, elsewhere.id, MONDAY)
    assert [day.master_slot_id for day in survivors] == [third_slot.id]


def test_rerunning_the_generator_does_not_double_the_day(db, room, cycle):
    """Two runs of the nightly job against one database.

    The job looks for a row it has already written and skips it, and that
    look is a SELECT some distance before the INSERT. Two runs overlapping
    both find nothing and both insert. The second is refused here instead of
    quietly doubling every day of the week.
    """
    activity = _activity(db, cycle.id, "PG-RERUN")
    _slot(db, activity.id, room.id, MONDAY.isoweekday(), 9, 11)

    assert generate_daily_ledger_entries(MONDAY, db) == 1
    assert generate_daily_ledger_entries(MONDAY, db) == 0
    assert len(_days_on(db, room.id, MONDAY)) == 1


def test_the_endpoint_returns_409_when_the_database_refuses_the_propagate(
    db, room, cycle, monkeypatch
):
    """The branch that exists for the race, reached without running a race.

    The reachable sequence, in full: a class in a cycle that has since been
    closed leaves behind the generated days ahead that attendance was marked
    on, because closing a cycle keeps those. _refuse_if_scheduled skips a closed cycle on purpose,
    so it reports that window free. An admin moves another class onto it,
    propagate_slot_corrections copies the new window onto every day that
    class has still to run, and the commit lands on top of the leftover.

    Blinding the day check once puts the endpoint where the loser of a real
    race is: it believes the window is free, it writes, and the database
    refuses it. What is being proved is the answer it gives. Without the
    rollback and the second ask the caller would get a stack trace and a 500
    saying nothing about which room it had lost or to what.
    """
    monday = _next_monday()
    db.add(
        User(
            id="PGLED",
            full_name="Postgres Admin",
            email_address="pg-ledger@test.internal",
            credential_secure_hash=hash_password(ADMIN_PASSWORD),
            role_type=InstitutionalRole.SUPER_ADMIN,
            initial_login_state=False,
        )
    )

    closed = PlanningCycle(
        cycle_label="PG Closed Cycle",
        date_bounds_start=datetime.date(2026, 1, 1),
        date_bounds_end=datetime.date(2027, 1, 1),
        operational_status=False,
    )
    db.add(closed)
    db.commit()

    moving = _activity(db, cycle.id, "PG-MOVING")
    leftover = _activity(db, closed.id, "PG-LEFTOVER")
    moving_slot = _slot(db, moving.id, room.id, monday.isoweekday(), 9, 11)
    leftover_slot = _slot(db, leftover.id, room.id, monday.isoweekday(), 14, 16)

    db.add(_day(moving.id, room.id, monday, 9, 11, moving_slot.id))
    db.add(_day(leftover.id, room.id, monday, 14, 16, leftover_slot.id))
    db.commit()

    def override_get_db():
        yield db

    app.dependency_overrides[get_db] = override_get_db
    try:
        client = TestClient(app)
        token = client.post(
            "/api/v1/auth/login",
            json={"email": "pg-ledger@test.internal", "password": ADMIN_PASSWORD},
        )
        assert token.status_code == 200, token.text
        headers = {"Authorization": f"Bearer {token.json()['access_token']}"}

        honest = schedule.days_against_slot
        seen = []

        def blind_once(*args, **kwargs):
            # Blind going in, honest coming back. The endpoint has to believe
            # the window is free to reach the branch at all, and then has to
            # find the day that beat it, or the caller is told it lost without
            # being told to what.
            seen.append(1)
            return [] if len(seen) == 1 else honest(*args, **kwargs)

        monkeypatch.setattr(schedule, "days_against_slot", blind_once)
        blind = client.patch(
            f"/api/v1/schedule/slots/{moving_slot.id}",
            headers=headers,
            json={"time_window_start": "14:00:00", "time_window_end": "16:00:00"},
        )
    finally:
        app.dependency_overrides.clear()

    assert blind.status_code == 409, blind.text
    detail = blind.json()["detail"]
    assert detail["message"] == schedule.ROOM_HAS_A_DAY
    assert [entry["master_slot_id"] for entry in detail["conflicts"]] == [leftover_slot.id]
    assert len(seen) == 2, "the endpoint never asked again after the database refused it"


def test_the_endpoint_refuses_the_move_before_it_writes_anything(db, room, cycle):
    """The same clash, without blinding anything.

    The check in front of the write is what turns the common case into a
    cheap 409 instead of a write, a refusal and a rollback. It is also the
    only thing standing in front of POST /schedule/slots, which has no
    commit to catch an IntegrityError from.
    """
    monday = _next_monday()
    db.add(
        User(
            id="PGLED",
            full_name="Postgres Admin",
            email_address="pg-ledger@test.internal",
            credential_secure_hash=hash_password(ADMIN_PASSWORD),
            role_type=InstitutionalRole.SUPER_ADMIN,
            initial_login_state=False,
        )
    )

    closed = PlanningCycle(
        cycle_label="PG Closed Cycle",
        date_bounds_start=datetime.date(2026, 1, 1),
        date_bounds_end=datetime.date(2027, 1, 1),
        operational_status=False,
    )
    db.add(closed)
    db.commit()

    moving = _activity(db, cycle.id, "PG-MOVING-2")
    leftover = _activity(db, closed.id, "PG-LEFTOVER-2")
    moving_slot = _slot(db, moving.id, room.id, monday.isoweekday(), 9, 11)
    leftover_slot = _slot(db, leftover.id, room.id, monday.isoweekday(), 14, 16)

    db.add(_day(moving.id, room.id, monday, 9, 11, moving_slot.id))
    db.add(_day(leftover.id, room.id, monday, 14, 16, leftover_slot.id))
    db.commit()

    def override_get_db():
        yield db

    app.dependency_overrides[get_db] = override_get_db
    try:
        client = TestClient(app)
        token = client.post(
            "/api/v1/auth/login",
            json={"email": "pg-ledger@test.internal", "password": ADMIN_PASSWORD},
        )
        assert token.status_code == 200, token.text
        headers = {"Authorization": f"Bearer {token.json()['access_token']}"}
        refused = client.patch(
            f"/api/v1/schedule/slots/{moving_slot.id}",
            headers=headers,
            json={"time_window_start": "14:00:00", "time_window_end": "16:00:00"},
        )
    finally:
        app.dependency_overrides.clear()

    assert refused.status_code == 409, refused.text
    detail = refused.json()["detail"]
    assert detail["message"] == schedule.ROOM_HAS_A_DAY
    assert [entry["master_slot_id"] for entry in detail["conflicts"]] == [leftover_slot.id]

    # Nothing moved. The slot and the day it has still to run are as they were.
    db.expire_all()
    assert moving_slot.time_window_start == _at(9)
    assert [day.time_window_start for day in _days_on(db, room.id, monday)] == [_at(9), _at(14)]
