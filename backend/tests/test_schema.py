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

from sqlalchemy import func, select

from app.core.bootstrap import SEEDED_ADMIN_ID
from app.core.database import sqlite_engine
from app.core.schema import SCHEMA_VERSION, ensure_schema
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
