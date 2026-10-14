# Copyright 2026 Chronos Ledger Contributors
# Licensed under the Apache License, Version 2.0
"""The schema step the server runs on start, on SQLite.

The rest of the suite builds its tables with create_all straight from the
metadata and never runs ensure_schema, so this is where the step itself is
checked: it builds, it seeds one administrator, and running it again changes
nothing. What it leaves on PostgreSQL is test_schema_pg's business.
"""

import os
import subprocess
import sys
from pathlib import Path

import pytest
from sqlalchemy import func, inspect, select, text

from app.core.bootstrap import SEEDED_ADMIN_ID
from app.core.database import Base, sqlite_engine
from app.core.schema import SCHEMA_VERSION, _refuse_pre_015_database, ensure_schema
from app.models.db import InstitutionalRole, User

BACKEND = Path(__file__).resolve().parents[1]


def _url(tmp_path) -> str:
    return f"sqlite:///{(tmp_path / 'schema.db').as_posix()}"


def _administrators(engine) -> list[User]:
    with engine.connect() as connection:
        rows = connection.execute(
            select(User.role_type, User.initial_login_state).where(User.id == SEEDED_ADMIN_ID)
        ).all()
        total = connection.execute(select(func.count()).select_from(User)).scalar()
    assert total == len(rows)
    return rows


def test_an_empty_database_is_built_and_seeded_once(tmp_path):
    engine = sqlite_engine(_url(tmp_path))
    try:
        assert ensure_schema(engine) == "created"
        (admin,) = _administrators(engine)
        assert admin.role_type == InstitutionalRole.ORG_ADMIN.value
        assert admin.initial_login_state

        # The same step on every start: nothing to build, nothing to seed.
        assert ensure_schema(engine) == "current"
        assert len(_administrators(engine)) == 1
    finally:
        engine.dispose()


def _alembic_version(engine) -> None:
    with engine.begin() as connection:
        connection.execute(text("CREATE TABLE alembic_version (version_num VARCHAR(32) NOT NULL)"))
        connection.execute(text("INSERT INTO alembic_version VALUES ('030')"))


def test_a_database_made_by_0_14_is_refused(tmp_path):
    """Its Alembic history sits beside Chronos's tables; 0.15 will not touch it."""
    engine = sqlite_engine(_url(tmp_path))
    try:
        Base.metadata.create_all(engine)
        _alembic_version(engine)
        with pytest.raises(RuntimeError, match="Chronos 0.14 or earlier"):
            ensure_schema(engine)
        # Refused before anything was seeded.
        assert _administrators(engine) == []
    finally:
        engine.dispose()


def test_a_host_programs_own_alembic_version_is_not_refused(tmp_path):
    """The embedded flavour shares a database; alembic_version alone proves nothing."""
    engine = sqlite_engine(_url(tmp_path))
    try:
        _alembic_version(engine)
        assert ensure_schema(engine) == "created"
        assert inspect(engine).has_table("alembic_version")
        assert len(_administrators(engine)) == 1
    finally:
        engine.dispose()


def test_a_host_table_called_reservations_is_not_a_0_14_database(tmp_path):
    engine = sqlite_engine(_url(tmp_path))
    try:
        _alembic_version(engine)
        with engine.begin() as connection:
            connection.execute(text("CREATE TABLE reservations (id INTEGER PRIMARY KEY)"))
        # Only one marker table is the host's, so it is not a 0.14 database.
        with engine.begin() as connection:
            _refuse_pre_015_database(connection)
    finally:
        engine.dispose()


def _drop_column(engine, table: str, column: str) -> None:
    with engine.begin() as connection:
        connection.execute(text(f"ALTER TABLE {table} DROP COLUMN {column}"))


def test_a_table_missing_a_model_column_is_refused(tmp_path):
    """create_all never adds a column, so an older 0.15 database would start and then fail."""
    engine = sqlite_engine(_url(tmp_path))
    try:
        Base.metadata.create_all(engine)
        _drop_column(engine, "structural_master_slots", "retired_at")
        _drop_column(engine, "activities", "retired_at")
        with pytest.raises(RuntimeError, match="does not upgrade a database in place") as refused:
            ensure_schema(engine)
        assert "activities.retired_at, structural_master_slots.retired_at" in str(refused.value)
        # Refused before anything was seeded.
        assert _administrators(engine) == []
    finally:
        engine.dispose()


def test_a_database_with_an_extra_column_still_starts(tmp_path):
    engine = sqlite_engine(_url(tmp_path))
    try:
        Base.metadata.create_all(engine)
        with engine.begin() as connection:
            connection.execute(text("ALTER TABLE reservations ADD COLUMN host_note VARCHAR(20)"))
        assert ensure_schema(engine) == "current"
        assert len(_administrators(engine)) == 1
    finally:
        engine.dispose()


def test_health_reports_the_schema_version(client):
    body = client.get("/health").json()
    assert body["schema_version"] == SCHEMA_VERSION
    assert "migration_revision" not in body


def test_the_module_builds_the_schema_from_the_command_line(tmp_path):
    """What the container runs before uvicorn: python -m app.core.schema."""
    env = {**os.environ, "DATABASE_URL": _url(tmp_path)}
    run = subprocess.run(
        [sys.executable, "-m", "app.core.schema"],
        cwd=BACKEND,
        env=env,
        capture_output=True,
        text=True,
        timeout=120,
    )
    assert run.returncode == 0, run.stderr
    assert f"Schema {SCHEMA_VERSION}: created" in run.stdout
