# Copyright 2026 Chronos Ledger Contributors
# Licensed under the Apache License, Version 2.0
"""The app refuses a database migrated by a newer release, and /health says
which version and migration it is running."""

import os
import subprocess
import sys
from pathlib import Path

import pytest
from sqlalchemy import create_engine, text

from app.core.migrations import _scripts, unknown_revision_message
from app.main import app

BACKEND = Path(__file__).resolve().parents[1]


def _stamped(tmp_path, revision):
    url = f"sqlite:///{(tmp_path / 'stamped.db').as_posix()}"
    engine = create_engine(url)
    if revision:
        with engine.begin() as connection:
            connection.execute(text("CREATE TABLE alembic_version (version_num VARCHAR(32))"))
            connection.execute(text("INSERT INTO alembic_version VALUES (:r)"), {"r": revision})
    return engine, url


def test_a_database_with_no_migrations_may_start(tmp_path):
    engine, _ = _stamped(tmp_path, None)
    assert unknown_revision_message(engine) is None


def test_a_database_at_the_code_head_may_start(tmp_path):
    engine, _ = _stamped(tmp_path, _scripts().get_current_head())
    assert unknown_revision_message(engine) is None


def test_a_database_at_an_unknown_revision_is_named_in_the_refusal(tmp_path):
    engine, _ = _stamped(tmp_path, "999")
    message = unknown_revision_message(engine)
    assert message and "999" in message and _scripts().get_current_head() in message


@pytest.mark.parametrize("revision, code", [("999", 1), (None, 0)])
def test_the_start_check_exits_non_zero_only_on_an_unknown_revision(tmp_path, revision, code):
    _, url = _stamped(tmp_path, revision)
    env = {**os.environ, "DATABASE_URL": url}
    result = subprocess.run(
        [sys.executable, "-m", "app.core.migrations"],
        cwd=BACKEND,
        env=env,
        capture_output=True,
        text=True,
        timeout=60,
    )
    assert result.returncode == code, result.stderr
    assert ("does not know" in result.stderr) == (code == 1)


def test_health_reports_the_version(client):
    body = client.get("/health").json()
    assert body["status"] == "healthy"
    assert body["version"] == app.version
    assert "migration_revision" in body
