# Copyright 2026 Chronos Ledger Contributors
# Licensed under the Apache License, Version 2.0
"""The tests for migration 017 that need a real PostgreSQL.

The key itself is checked on SQLite too, in test_ledger_generator, because
create_all builds it from the model. What SQLite cannot show is what the key
is for: two sessions writing one day at once, where the second has to wait on
the first's uncommitted row and then find it, and an upgrade meeting a table
that already has the duplicates.

Point TEST_DATABASE_URL at an empty database:

    TEST_DATABASE_URL=postgresql://user:pass@localhost:5432/chronos_test \\
        pytest tests/test_ledger_unique_pg.py
"""

import datetime
import logging
import os
import threading
import time

import pytest
from sqlalchemy import create_engine, delete, text
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from alembic import command
from app.cron.ledger_generator import generate_daily_ledger_entries
from app.models.db import Activity, DailyLedger, PlanningCycle, StructuralMasterSlot
from tests.test_admin_rotation_pg import _alembic

DATABASE_URL = os.environ.get("TEST_DATABASE_URL")

pytestmark = pytest.mark.skipif(
    not DATABASE_URL,
    reason="needs a real PostgreSQL: set TEST_DATABASE_URL",
)

KEY = "uq_daily_ledger_slot_date"

# Years away, so that no cycle a shared test database already holds covers it
# and the generator has nothing to write that day but the slot made here.
DAY = datetime.date(2031, 3, 4)


@pytest.fixture(scope="module")
def engine():
    with _alembic() as config:
        command.upgrade(config, "head")
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


def _slot(db, code):
    """A slot on DAY's weekday with no room, the case migration 013 never saw."""
    cycle = PlanningCycle(
        cycle_label=code,
        date_bounds_start=datetime.date(2031, 1, 1),
        date_bounds_end=datetime.date(2031, 12, 31),
        operational_status=True,
    )
    db.add(cycle)
    db.flush()
    activity = Activity(activity_code=code, activity_title=code, unit_code="CSE", cycle_id=cycle.id)
    db.add(activity)
    db.flush()
    slot = StructuralMasterSlot(
        day_of_week_index=DAY.isoweekday(),
        time_window_start=datetime.time(9),
        time_window_end=datetime.time(10),
        activity_id=activity.id,
    )
    db.add(slot)
    db.commit()
    return slot


@pytest.fixture()
def committed(engine):
    """A slot that is really in the table, and taken out again afterwards.

    Committed because the tests that use it open a second session or run
    alembic, and neither can see into a transaction the test has open.
    """
    with Session(engine) as session:
        slot = _slot(session, "PG-UNIQUE-COMMITTED")
        ids = (slot.id, slot.activity_id, slot.activity.cycle_id)
    try:
        yield ids[:2]
    finally:
        slot_id, activity_id, cycle_id = ids
        with Session(engine) as session:
            session.execute(delete(DailyLedger).where(DailyLedger.master_slot_id == slot_id))
            session.execute(delete(StructuralMasterSlot).where(StructuralMasterSlot.id == slot_id))
            session.execute(delete(Activity).where(Activity.id == activity_id))
            session.execute(delete(PlanningCycle).where(PlanningCycle.id == cycle_id))
            session.commit()


def _until_an_insert_is_waiting(engine, timeout=10.0):
    """Returns once some session is waiting on a lock, which is the generator."""
    deadline = time.monotonic() + timeout
    with engine.connect() as watcher:
        while time.monotonic() < deadline:
            if watcher.execute(text("SELECT count(*) FROM pg_locks WHERE NOT granted")).scalar():
                return
            time.sleep(0.05)
    pytest.fail("the generator's insert never waited on the first session")


def test_the_key_is_actually_on_the_table(db):
    """Every other test here is only meaningful if this one passes."""
    found = db.execute(
        text(
            f"SELECT contype FROM pg_constraint WHERE conname = '{KEY}'"
            " AND conrelid = 'daily_ledger'::regclass"
        )
    ).scalar()
    assert found == "u", "migration 017 did not leave a unique key behind"


def test_a_slot_with_no_room_still_gets_one_day_per_date(db):
    slot = _slot(db, "PG-UNIQUE-ROOMLESS")
    db.add(DailyLedger(target_date=DAY, master_slot_id=slot.id, activity_id=slot.activity_id))
    db.commit()

    db.add(DailyLedger(target_date=DAY, master_slot_id=slot.id, activity_id=slot.activity_id))
    with pytest.raises(IntegrityError) as refused:
        db.commit()
    assert KEY in str(refused.value.orig)


def test_days_with_no_slot_are_not_limited(db):
    """Ad-hoc days, and the days of a deleted slot. NULLs never compare equal."""
    slot = _slot(db, "PG-UNIQUE-DETACHED")
    for _ in range(2):
        db.add(DailyLedger(target_date=DAY, master_slot_id=None, activity_id=slot.activity_id))
    db.commit()

    days = db.query(DailyLedger).filter(
        DailyLedger.activity_id == slot.activity_id, DailyLedger.target_date == DAY
    )
    assert days.count() == 2


def test_two_runs_at_once_write_the_day_once_and_say_nothing(engine, committed, caplog):
    """The race the key closes.

    One session has written the day and not committed. The generator, in
    another, looks for the day, cannot see a row that is not committed, and
    inserts. Postgres holds that insert until the first session finishes and
    then refuses it. The generator has to read that as the day existing: no
    second row, and no warning, because nothing was lost.
    """
    slot_id, activity_id = committed
    caplog.set_level(logging.WARNING, logger="app.cron.ledger_generator")
    result = {}

    def second_run():
        with Session(engine) as second:
            result["created"] = generate_daily_ledger_entries(DAY, second)

    first = Session(engine)
    first.add(DailyLedger(target_date=DAY, master_slot_id=slot_id, activity_id=activity_id))
    first.flush()
    runner = threading.Thread(target=second_run)
    runner.start()
    try:
        _until_an_insert_is_waiting(engine)
    finally:
        first.commit()
        first.close()
        runner.join(timeout=30)

    assert not runner.is_alive()
    assert result.get("created") == 0
    with Session(engine) as check:
        written = check.query(DailyLedger).filter(DailyLedger.master_slot_id == slot_id)
        assert written.count() == 1
    assert "no day written" not in caplog.text


def test_the_upgrade_stops_on_a_table_that_already_has_duplicates(engine, committed):
    """What a database two instances had already raced on looks like.

    Nothing in 017 picks which of two rows to keep, because attendance may be
    marked against either, so the upgrade has to fail rather than guess.
    """
    slot_id, activity_id = committed
    with _alembic() as config:
        command.downgrade(config, "016")
        try:
            with Session(engine) as session:
                for _ in range(2):
                    session.add(
                        DailyLedger(
                            target_date=DAY, master_slot_id=slot_id, activity_id=activity_id
                        )
                    )
                session.commit()
            with pytest.raises(IntegrityError):
                command.upgrade(config, "017")
        finally:
            with Session(engine) as session:
                session.execute(delete(DailyLedger).where(DailyLedger.master_slot_id == slot_id))
                session.commit()
            command.upgrade(config, "head")
