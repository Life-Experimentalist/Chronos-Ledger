# Copyright 2026 Chronos Ledger Contributors
# Licensed under the Apache License, Version 2.0
"""The tests for migration 014, which cannot run on SQLite.

The rest of the suite builds its schema with create_all, which does not run the
migrations at all, so a test written the usual way would prove nothing about a
migration whose entire job is to change one row that create_all never inserts.

These run against a real PostgreSQL and skip when there is not one. Point
TEST_DATABASE_URL at an empty database:

    TEST_DATABASE_URL=postgresql://user:pass@localhost:5432/chronos_test \\
        pytest tests/test_admin_rotation_pg.py

Both tests plant a hash on the seeded row and re-run 014 over it, because a
database freshly upgraded to head has already been through 014 once and 001 no
longer seeds anything for it to find. The leave-alone case is the one that
matters more: rotating a password an operator chose would lock them out of
their own instance, which is worse than the exposure being fixed.
"""

import contextlib
import os

import bcrypt
import pytest
from alembic.config import Config
from sqlalchemy import create_engine, text

from alembic import command

DATABASE_URL = os.environ.get("TEST_DATABASE_URL")

pytestmark = pytest.mark.skipif(
    not DATABASE_URL,
    reason="needs a real PostgreSQL: set TEST_DATABASE_URL",
)

# What 001 used to seed, and what 014 looks for.
PUBLISHED = "ChronosAdmin2026!"
CHOSEN = "TheOperatorChoseThis1!"
SEEDED_ADMIN_ID = "ADMIN001"


@contextlib.contextmanager
def _alembic():
    """An alembic Config pointed at the test database, and only for a moment.

    env.py reads DATABASE_URL and lets it win over anything the config carries,
    so a developer whose own DATABASE_URL points somewhere real would otherwise
    have these migrations run against that database.
    """
    previous = os.environ.get("DATABASE_URL")
    os.environ["DATABASE_URL"] = DATABASE_URL
    try:
        config = Config("alembic.ini")
        config.set_main_option("sqlalchemy.url", DATABASE_URL)
        yield config
    finally:
        if previous is None:
            os.environ.pop("DATABASE_URL", None)
        else:
            os.environ["DATABASE_URL"] = previous


@pytest.fixture(scope="module")
def engine():
    with _alembic() as config:
        command.upgrade(config, "head")
    built = create_engine(DATABASE_URL)
    yield built
    built.dispose()


def _hash(password: str) -> str:
    return bcrypt.hashpw(password.encode("utf-8"), bcrypt.gensalt()).decode("utf-8")


def _read_admin(engine) -> tuple[str, bool]:
    with engine.connect() as conn:
        row = conn.execute(
            text("SELECT credential_secure_hash, initial_login_state FROM users WHERE id = :uid"),
            {"uid": SEEDED_ADMIN_ID},
        ).one()
    return row[0], row[1]


@contextlib.contextmanager
def _admin_holding(engine, password: str, unused: bool):
    """Put the seeded row into a known state, and put it back afterwards.

    These commit for real. Alembic runs on its own connection and cannot see a
    savepoint the way the other Postgres tests here rely on, and this is
    somebody's database rather than a fresh file per test, so the restore in the
    finally is what makes the file safe to run twice.
    """
    before = _read_admin(engine)
    with engine.begin() as conn:
        conn.execute(
            text(
                "UPDATE users SET credential_secure_hash = :hash, "
                "initial_login_state = :unused WHERE id = :uid"
            ),
            {"hash": _hash(password), "unused": unused, "uid": SEEDED_ADMIN_ID},
        )
    try:
        yield
    finally:
        with engine.begin() as conn:
            conn.execute(
                text(
                    "UPDATE users SET credential_secure_hash = :hash, "
                    "initial_login_state = :unused WHERE id = :uid"
                ),
                {"hash": before[0], "unused": before[1], "uid": SEEDED_ADMIN_ID},
            )


def _run_014_again():
    """Step back over 014 and forward through it.

    Its downgrade is empty on purpose, so stepping back changes nothing but the
    version alembic thinks it is at, which is exactly what is wanted: the row
    planted just before this stays planted and the upgrade sees it.
    """
    with _alembic() as config:
        command.downgrade(config, "013")
        command.upgrade(config, "014")


def test_the_published_password_is_rotated_away(engine):
    with _admin_holding(engine, PUBLISHED, unused=True):
        _run_014_again()

        stored, unused = _read_admin(engine)
        assert not bcrypt.checkpw(PUBLISHED.encode("utf-8"), stored.encode("utf-8"))
        # Left in the state a fresh install is in, so the way back in is the
        # same on both: set INITIAL_ADMIN_PASSWORD and restart.
        assert unused is True


def test_a_password_the_operator_chose_is_untouched(engine):
    """The case that decides the condition is the hash and not the flag.

    A password reset sets initial_login_state back to true, so this state is
    reachable with a password only the operator knows. Rotating here would be
    locking somebody out of their own instance to fix an exposure they had
    already fixed.
    """
    with _admin_holding(engine, CHOSEN, unused=True):
        before, _ = _read_admin(engine)
        _run_014_again()

        stored, unused = _read_admin(engine)
        assert stored == before
        assert unused is True
        assert bcrypt.checkpw(CHOSEN.encode("utf-8"), stored.encode("utf-8"))
