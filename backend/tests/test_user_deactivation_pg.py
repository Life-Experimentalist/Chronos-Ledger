# Copyright 2026 Chronos Ledger Contributors
# Licensed under the Apache License, Version 2.0
"""The tests for migration 018 that need a real PostgreSQL.

The suite's SQLite database does not enforce foreign keys, and the migration
only swaps the key on PostgreSQL, so whether deleting a user with attendance
on file is really refused, and whether a downgrade puts the cascade back, can
only be seen here.

Point TEST_DATABASE_URL at an empty database:

    TEST_DATABASE_URL=postgresql://user:pass@localhost:5432/chronos_test \\
        pytest tests/test_user_deactivation_pg.py
"""

import datetime
import os

import pytest
from sqlalchemy import create_engine, delete, inspect
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from alembic import command
from app.models.db import (
    Activity,
    DailyLedger,
    InstitutionalRole,
    PlanningCycle,
    User,
    VerificationLedger,
    VerificationMetric,
)
from tests.test_admin_rotation_pg import _alembic

DATABASE_URL = os.environ.get("TEST_DATABASE_URL")

pytestmark = pytest.mark.skipif(
    not DATABASE_URL,
    reason="needs a real PostgreSQL: set TEST_DATABASE_URL",
)

FK = "verification_ledger_member_id_fkey"

# Years away, like the other PostgreSQL tests, so nothing already in a shared
# test database lands on it.
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


def _key_on(engine, column):
    return next(
        fk
        for fk in inspect(engine).get_foreign_keys("verification_ledger")
        if fk["constrained_columns"] == [column]
    )


def _user_columns(engine):
    return {c["name"] for c in inspect(engine).get_columns("users")}


def _user(db, user_id):
    db.add(
        User(
            id=user_id,
            full_name=user_id,
            email_address=f"{user_id.lower()}@test.internal",
            credential_secure_hash="not-a-real-hash",
            role_type=InstitutionalRole.MEMBER,
            unit_code="CSE",
        )
    )
    db.flush()


def _mark_present(db, user_id):
    cycle = PlanningCycle(
        cycle_label=user_id,
        date_bounds_start=datetime.date(2031, 1, 1),
        date_bounds_end=datetime.date(2031, 12, 31),
        operational_status=True,
    )
    db.add(cycle)
    db.flush()
    activity = Activity(
        activity_code=user_id, activity_title=user_id, unit_code="CSE", cycle_id=cycle.id
    )
    db.add(activity)
    db.flush()
    ledger = DailyLedger(target_date=DAY, activity_id=activity.id)
    db.add(ledger)
    db.flush()
    db.add(
        VerificationLedger(
            ledger_instance_id=ledger.id,
            member_id=user_id,
            marking_status=VerificationMetric.PRESENT,
        )
    )
    db.flush()


def test_the_key_restricts_and_the_column_is_there(engine):
    """Every other test here is only meaningful if this one passes."""
    member = _key_on(engine, "member_id")
    assert member["name"] == FK
    assert member["options"].get("ondelete") == "RESTRICT"
    # The table's other key to users is not the one 018 changes.
    assert _key_on(engine, "authorizing_agent_id")["options"].get("ondelete") is None
    assert "deactivated_at" in _user_columns(engine)


def test_a_user_with_attendance_on_file_cannot_be_deleted(db):
    _user(db, "PG018-MARKED")
    _mark_present(db, "PG018-MARKED")

    with pytest.raises(IntegrityError) as refused:
        db.execute(delete(User).where(User.id == "PG018-MARKED"))
    assert FK in str(refused.value.orig)


def test_a_user_with_no_attendance_can_still_be_deleted(db):
    _user(db, "PG018-UNMARKED")
    db.execute(delete(User).where(User.id == "PG018-UNMARKED"))
    assert db.query(User).filter(User.id == "PG018-UNMARKED").first() is None


def test_the_downgrade_puts_the_cascade_back(engine):
    with _alembic() as config:
        command.downgrade(config, "017")
        try:
            assert _key_on(engine, "member_id")["options"].get("ondelete") == "CASCADE"
            assert "deactivated_at" not in _user_columns(engine)
        finally:
            command.upgrade(config, "head")
    member = _key_on(engine, "member_id")
    assert member["name"] == FK
    assert member["options"].get("ondelete") == "RESTRICT"
