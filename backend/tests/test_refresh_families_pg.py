# Copyright 2026 Chronos Ledger Contributors
# Licensed under the Apache License, Version 2.0
"""The tests for migration 016, which cannot run on SQLite.

Same arrangement as test_admin_rotation_pg.py: the rest of the suite builds its
schema with create_all, so only a real PostgreSQL shows what 016 does to rows
that were there before it. Skipped unless TEST_DATABASE_URL names an empty
database.

The upgrade case is the one that matters to anybody upgrading: a row left
without a family would fail the NOT NULL, and rows lumped into one family would
let the first reuse anywhere sign every device out.
"""

import uuid
from datetime import UTC, datetime, timedelta

import pytest
from sqlalchemy import create_engine, text

from alembic import command
from tests.test_admin_rotation_pg import DATABASE_URL, _alembic

pytestmark = pytest.mark.skipif(
    not DATABASE_URL,
    reason="needs a real PostgreSQL: set TEST_DATABASE_URL",
)

SEEDED_ADMIN_ID = "ADMIN001"
PLANTED = ("planted-a", "planted-b")


@pytest.fixture(scope="module")
def engine():
    with _alembic() as config:
        command.upgrade(config, "head")
    built = create_engine(DATABASE_URL)
    yield built
    built.dispose()


@pytest.fixture
def planted(engine):
    """Removes the planted rows and puts the schema back at head, pass or fail."""
    yield
    with engine.begin() as conn:
        conn.execute(
            text("DELETE FROM refresh_tokens WHERE token_hash = ANY(:hashes)"),
            {"hashes": list(PLANTED)},
        )
    with _alembic() as config:
        command.upgrade(config, "head")


def _planted_rows(engine):
    with engine.connect() as conn:
        return (
            conn.execute(
                text("SELECT * FROM refresh_tokens WHERE token_hash = ANY(:hashes)"),
                {"hashes": list(PLANTED)},
            )
            .mappings()
            .all()
        )


def test_rows_from_before_016_each_become_a_family_of_their_own(engine, planted):
    with _alembic() as config:
        command.downgrade(config, "015")
    with engine.begin() as conn:
        for token_hash in PLANTED:
            conn.execute(
                text(
                    "INSERT INTO refresh_tokens (token_hash, user_id, expires_at) "
                    "VALUES (:token_hash, :user_id, :expires_at)"
                ),
                {
                    "token_hash": token_hash,
                    "user_id": SEEDED_ADMIN_ID,
                    "expires_at": datetime.now(UTC) + timedelta(days=1),
                },
            )

    with _alembic() as config:
        command.upgrade(config, "016")

    rows = _planted_rows(engine)
    assert len(rows) == 2
    assert all(row["consumed_at"] is None for row in rows)
    families = {row["family_id"] for row in rows}
    assert len(families) == 2
    for family in families:
        uuid.UUID(family)


def test_going_down_drops_the_used_rows_the_old_code_would_accept(engine, planted):
    family = str(uuid.uuid4())
    used, current = PLANTED
    with engine.begin() as conn:
        for token_hash, consumed_at in ((used, datetime.now(UTC)), (current, None)):
            conn.execute(
                text(
                    "INSERT INTO refresh_tokens "
                    "(token_hash, user_id, family_id, expires_at, consumed_at) "
                    "VALUES (:token_hash, :user_id, :family_id, :expires_at, :consumed_at)"
                ),
                {
                    "token_hash": token_hash,
                    "user_id": SEEDED_ADMIN_ID,
                    "family_id": family,
                    "expires_at": datetime.now(UTC) + timedelta(days=1),
                    "consumed_at": consumed_at,
                },
            )

    with _alembic() as config:
        command.downgrade(config, "015")

    assert [row["token_hash"] for row in _planted_rows(engine)] == [current]
