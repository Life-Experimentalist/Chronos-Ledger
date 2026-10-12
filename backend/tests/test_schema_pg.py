# Copyright 2026 Chronos Ledger Contributors
# Licensed under the Apache License, Version 2.0
"""What create_all leaves on an empty PostgreSQL, which SQLite cannot show.

There are no migrations: the models are the schema, and ensure_schema builds
it with create_all on every start. The two exclusion constraints and the
btree_gist extension they need are declared for PostgreSQL only, so the
SQLite suite builds the same models and never sees them. This is the one
place that asks the catalog whether they arrived, and then proves the point
of one of them by having the database refuse two holds on one room.

Point TEST_DATABASE_URL at an empty database:

    TEST_DATABASE_URL=postgresql://user:pass@localhost:5432/chronos_test \\
        pytest tests/test_schema_pg.py
"""

import datetime
import os

import pytest
from sqlalchemy import create_engine, func, select, text
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.core.bootstrap import SEEDED_ADMIN_ID
from app.core.schema import ensure_schema
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

EXCLUSION_CONSTRAINTS = {"ex_reservations_no_overlap", "ex_daily_ledger_no_overlap"}


@pytest.fixture(scope="module")
def engine():
    built = create_engine(DATABASE_URL)
    yield built
    built.dispose()


@pytest.fixture(scope="module")
def built(engine):
    """ensure_schema's answer on the database as the module found it."""
    return ensure_schema(engine)


@pytest.fixture()
def db(engine, built):
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


def test_the_exclusion_constraints_are_on_the_tables(db):
    found = set(db.execute(text("SELECT conname FROM pg_constraint WHERE contype = 'x'")).scalars())
    assert found == EXCLUSION_CONSTRAINTS


def test_the_extension_the_constraints_need_is_installed(db):
    found = db.execute(text("SELECT 1 FROM pg_extension WHERE extname = 'btree_gist'")).scalar()
    assert found == 1


def test_two_overlapping_holds_on_one_room_are_refused_by_the_database(db):
    room = Resource(code="PG-SCHEMA-1", label="Schema Lab", resource_type=ResourceType.ROOM)
    db.add(room)
    db.flush()

    def hold(start: int, end: int, key: str) -> Reservation:
        return Reservation(
            resource_id=room.id,
            reserved_date=datetime.date(2031, 3, 4),
            time_window_start=datetime.time(start),
            time_window_end=datetime.time(end),
            purpose="Overlap check",
            idempotency_key=key,
            request_fingerprint="0" * 64,
            status=ReservationStatus.HELD,
        )

    db.add(hold(9, 11, "pg-schema-first"))
    db.flush()
    db.add(hold(10, 12, "pg-schema-second"))
    with pytest.raises(IntegrityError) as refused:
        db.flush()
    assert "ex_reservations_no_overlap" in str(refused.value.orig)


def test_the_schema_is_built_once_and_the_administrator_seeded_once(engine, built):
    assert built in {"created", "current"}
    assert ensure_schema(engine) == "current"

    with Session(engine) as session:
        admins = session.execute(
            select(func.count()).select_from(User).where(User.id == SEEDED_ADMIN_ID)
        ).scalar()
        admin = session.get(User, SEEDED_ADMIN_ID)
    assert admins == 1
    assert admin.role_type == InstitutionalRole.ORG_ADMIN
    assert admin.initial_login_state
