# Copyright 2026 Chronos Ledger Contributors
# Licensed under the Apache License, Version 2.0
"""The archive moves from SQLite to PostgreSQL and comes back byte for byte.

The seed is the one tests/test_portability.py uses, written to a SQLite file,
exported, imported here, and exported again from PostgreSQL. Equal bytes mean
both databases give back the same values in the same order: string keys in
bytewise order, times in UTC, numbers at their column's scale.

Point TEST_DATABASE_URL at an empty database:

    TEST_DATABASE_URL=postgresql://user:pass@localhost:5432/chronos_test \\
        pytest tests/test_portability_pg.py
"""

import datetime
import io
import os

import pytest
from sqlalchemy import create_engine, text
from sqlalchemy.orm import Session

from app import standalone
from app.core.database import sqlite_engine
from app.models.db import PlanningCycle, Resource
from app.services.portability import import_archive
from tests.test_portability import export_bytes, seed

DATABASE_URL = os.environ.get("TEST_DATABASE_URL")

pytestmark = pytest.mark.skipif(
    not DATABASE_URL,
    reason="needs a real PostgreSQL: set TEST_DATABASE_URL",
)

SCHEMA = "chronos_portable"


@pytest.fixture(autouse=True)
def _environment_restored():
    """The CLI test runs configure_environment, which writes os.environ."""
    saved = dict(os.environ)
    yield
    os.environ.clear()
    os.environ.update(saved)


@pytest.fixture(scope="module")
def archives(tmp_path_factory):
    """The SQLite seed's archive, with secrets and without."""
    path = tmp_path_factory.mktemp("sqlite") / "source.db"
    engine = sqlite_engine(f"sqlite:///{path.as_posix()}")
    try:
        seed(engine)
        return {flag: export_bytes(engine, flag) for flag in (False, True)}
    finally:
        engine.dispose()


@pytest.fixture(scope="module")
def engine():
    built = create_engine(DATABASE_URL)
    with built.begin() as connection:
        # Where the embedded tests put it: the database-wide extension the
        # exclusion constraints need, outside any one schema.
        connection.execute(text("CREATE EXTENSION IF NOT EXISTS btree_gist"))
    yield built
    built.dispose()


def test_sqlite_to_postgresql_and_back_gives_the_same_bytes(engine, archives):
    import_archive(engine, io.BytesIO(archives[True]))
    assert export_bytes(engine, True) == archives[True]
    assert export_bytes(engine, False) == archives[False]

    # The serial sequences start after the imported ids, so the next row the
    # server writes does not collide with one that came in.
    with Session(engine) as db:
        before = db.query(PlanningCycle).count()
        added = PlanningCycle(
            cycle_label="Next",
            date_bounds_start=datetime.date(2027, 1, 4),
            date_bounds_end=datetime.date(2027, 5, 28),
        )
        db.add(added)
        resource = Resource(code="R-NEW", label="New room")
        db.add(resource)
        db.flush()
        assert added.id > 2
        assert resource.id > 2
        assert db.query(PlanningCycle).count() == before + 1
        db.rollback()


def test_the_cli_imports_and_exports_inside_a_schema(engine, archives, tmp_path):
    archive = tmp_path / "in.zip"
    archive.write_bytes(archives[True])
    again = tmp_path / "out.zip"
    data_dir = tmp_path / "data"
    where = ["--data-dir", str(data_dir), "--database-url", DATABASE_URL, "--schema", SCHEMA]
    try:
        assert standalone.main(["import", *where, "--from", str(archive)]) == 0
        assert standalone.main(["export", *where, "--include-secrets", "--to", str(again)]) == 0
        assert again.read_bytes() == archives[True]
    finally:
        with engine.begin() as connection:
            connection.execute(text(f'DROP SCHEMA IF EXISTS "{SCHEMA}" CASCADE'))
