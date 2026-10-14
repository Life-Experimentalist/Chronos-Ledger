# Copyright 2026 Chronos Ledger Contributors
# Licensed under the Apache License, Version 2.0
"""The embedded flavour inside a host program's PostgreSQL database.

A host that already has a database lends Chronos one schema of it
(chronos-engine embedded --database-url ... --schema NAME). Everything
Chronos makes has to land in that schema and nothing of the host's may be
touched, including a host table that happens to share a name with one of
ours. This module plays the host: it makes `public.users` and loads
btree_gist into `public` before Chronos arrives, then checks the catalog.

Point TEST_DATABASE_URL at an empty database:

    TEST_DATABASE_URL=postgresql://user:pass@localhost:5432/chronos_test \\
        pytest tests/test_embedded_pg.py
"""

import datetime
import os
from types import SimpleNamespace

import pytest
from sqlalchemy import create_engine, delete, text
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.core.database import use_schema
from app.core.host_identity import SYSTEM_ACTOR_ID, host_actor
from app.embedded import prepare_database
from app.models.db import (
    InstitutionalRole,
    Reservation,
    ReservationStatus,
    Resource,
    User,
)

DATABASE_URL = os.environ.get("TEST_DATABASE_URL")

pytestmark = pytest.mark.skipif(
    not DATABASE_URL,
    reason="needs a real PostgreSQL: set TEST_DATABASE_URL",
)

SCHEMA = "chronos_test_schema"
EXCLUSION_CONSTRAINTS = {"ex_reservations_no_overlap", "ex_daily_ledger_no_overlap"}


@pytest.fixture(scope="module")
def host_tables():
    """What the host had before Chronos: its own users table, btree_gist in public."""
    host = create_engine(DATABASE_URL)
    with host.begin() as connection:
        connection.execute(text("CREATE EXTENSION IF NOT EXISTS btree_gist"))
        connection.execute(text("CREATE TABLE public.users (id text PRIMARY KEY, nickname text)"))
        connection.execute(text("INSERT INTO public.users VALUES ('host-1', 'The host')"))
    host.dispose()


@pytest.fixture(scope="module")
def engine(host_tables):
    built = create_engine(DATABASE_URL)
    use_schema(built, SCHEMA)
    yield built
    built.dispose()


@pytest.fixture(scope="module")
def built(engine):
    return prepare_database(engine, SCHEMA)


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


def _tables(db, schema):
    return set(
        db.execute(
            text("SELECT table_name FROM information_schema.tables WHERE table_schema = :schema"),
            {"schema": schema},
        ).scalars()
    )


def test_every_table_is_in_the_schema(db, built):
    assert built == "created"
    ours = _tables(db, SCHEMA)
    assert {"users", "reservations", "resources", "audit_records"} <= ours


def test_the_hosts_table_of_the_same_name_is_untouched(db):
    assert _tables(db, "public") == {"users"}
    columns = set(
        db.execute(
            text(
                "SELECT column_name FROM information_schema.columns"
                " WHERE table_schema = 'public' AND table_name = 'users'"
            )
        ).scalars()
    )
    assert columns == {"id", "nickname"}
    rows = db.execute(text("SELECT id, nickname FROM public.users")).all()
    assert rows == [("host-1", "The host")]
    # An unqualified name is ours, not theirs.
    assert db.get(User, SYSTEM_ACTOR_ID) is not None
    assert db.execute(text("SELECT count(*) FROM users WHERE id = 'host-1'")).scalar() == 0


def test_the_exclusion_constraints_are_in_the_schema(db):
    found = db.execute(
        text(
            "SELECT conname, nspname FROM pg_constraint JOIN pg_namespace"
            " ON pg_namespace.oid = connamespace WHERE contype = 'x'"
        )
    ).all()
    assert {name for name, _ in found} == EXCLUSION_CONSTRAINTS
    assert {schema for _, schema in found} == {SCHEMA}


def test_the_hosts_extension_serves_the_constraints(db):
    """btree_gist was already in public; Chronos neither moved nor duplicated it."""
    found = db.execute(
        text(
            "SELECT nspname FROM pg_extension JOIN pg_namespace"
            " ON pg_namespace.oid = extnamespace WHERE extname = 'btree_gist'"
        )
    ).scalars()
    assert list(found) == ["public"]


def test_two_overlapping_holds_are_still_refused_inside_the_schema(db):
    room = Resource(code="PG-EMBED-1", label="Embedded Lab", resource_type="ROOM")
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

    db.add(hold(9, 11, "pg-embed-first"))
    db.flush()
    db.add(hold(10, 12, "pg-embed-second"))
    with pytest.raises(IntegrityError) as refused:
        db.flush()
    assert "ex_reservations_no_overlap" in str(refused.value.orig)


def test_the_loser_of_a_first_sight_race_carries_on(engine, built, monkeypatch):
    """Two first-sight requests for one id, on PostgreSQL.

    The winner's row is committed through its own session while the loser's
    look at the account has already come back empty. The loser's insert is
    refused on the primary key; the request still succeeds, with the winner's
    row brought up to date.
    """
    winner = Session(engine)
    loser = Session(engine)
    real_get = loser.get
    seen = []

    def stale_get(entity, ident, *args, **kwargs):
        if entity is User and ident == "race-1" and not seen:
            seen.append(ident)
            return None
        return real_get(entity, ident, *args, **kwargs)

    try:
        winner.add(
            User(
                id="race-1",
                full_name="race-1",
                email_address="race-1@host.invalid",
                credential_secure_hash="not a hash",
                role_type=InstitutionalRole.MEMBER,
                initial_login_state=False,
            )
        )
        winner.commit()
        monkeypatch.setattr(loser, "get", stale_get)

        request = SimpleNamespace(state=SimpleNamespace())
        actor = host_actor(
            request,
            actor_id="race-1",
            role="STAFF",
            name="Second Sight",
            email=None,
            unit=None,
            db=loser,
        )
        assert actor == "race-1"
        assert request.state.actor_id == "race-1"
        assert seen == ["race-1"]
        winner.expire_all()
        user = winner.get(User, "race-1")
        assert user.role_type == InstitutionalRole.STAFF
        assert user.full_name == "Second Sight"
    finally:
        loser.close()
        winner.execute(delete(User).where(User.id == "race-1"))
        winner.commit()
        winner.close()


def test_the_system_account_is_seeded_once(engine, built, db):
    system = db.get(User, SYSTEM_ACTOR_ID)
    assert system.role_type == InstitutionalRole.ORG_ADMIN
    assert system.initial_login_state is False
    # Nothing to do the second time, on the same schema.
    assert prepare_database(engine, SCHEMA) == "current"


def test_the_entry_point_builds_the_schema_the_flags_name(tmp_path, host_tables, embedded_process):
    """The real entry point in a fresh interpreter, on --database-url and --schema.

    This is the case an early `app.` import breaks: the engine would be built
    from the DATABASE_URL in the environment, here a decoy SQLite file, and
    the host's database would never see a table.
    """
    schema = "chronos_subprocess_schema"
    decoy = tmp_path / "elsewhere.db"
    child = embedded_process(
        "--data-dir",
        str(tmp_path),
        "--database-url",
        DATABASE_URL,
        "--schema",
        schema,
        "--port",
        "0",
        env={"DATABASE_URL": f"sqlite:///{decoy.as_posix()}"},
    )
    catalog = create_engine(DATABASE_URL)
    try:
        assert child.ready()["chronos"] == "ready"
        with catalog.connect() as connection:
            assert {"users", "reservations", "resources", "audit_records"} <= _tables(
                connection, schema
            )
        assert not decoy.exists()
        assert child.leave() == 0
    finally:
        child.kill()
        with catalog.begin() as connection:
            connection.execute(text(f'DROP SCHEMA IF EXISTS "{schema}" CASCADE'))
        catalog.dispose()
