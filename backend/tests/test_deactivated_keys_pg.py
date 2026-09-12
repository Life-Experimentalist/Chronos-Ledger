# Copyright 2026 Chronos Ledger Contributors
# Licensed under the Apache License, Version 2.0
"""The test for migration 019, which needs a real PostgreSQL.

The rest of the suite builds its schema with create_all and never runs a
migration, so one whose whole job is to delete rows has to be run for real
to be seen doing it.

Point TEST_DATABASE_URL at an empty database:

    TEST_DATABASE_URL=postgresql://user:pass@localhost:5432/chronos_test \\
        pytest tests/test_deactivated_keys_pg.py
"""

import contextlib
import os
from datetime import UTC, datetime

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import Session

from alembic import command
from app.core.security import generate_api_key, hash_api_key
from app.models.db import ApiKey, InstitutionalRole, User
from tests.test_admin_rotation_pg import _alembic

DATABASE_URL = os.environ.get("TEST_DATABASE_URL")

pytestmark = pytest.mark.skipif(
    not DATABASE_URL,
    reason="needs a real PostgreSQL: set TEST_DATABASE_URL",
)

LEFT = "PG019-LEFT"
STAYED = "PG019-STAYED"


@pytest.fixture(scope="module")
def engine():
    with _alembic() as config:
        command.upgrade(config, "head")
    built = create_engine(DATABASE_URL)
    yield built
    built.dispose()


@contextlib.contextmanager
def _accounts_holding_keys(engine):
    """Two service accounts with a key each, one of them deactivated.

    Committed for real and removed afterwards. Alembic runs on its own
    connection and cannot see a savepoint, so the rows it is meant to find
    have to be in the database, and this is somebody's test database rather
    than a fresh file per test, so the cleanup in the finally is what makes
    the file safe to run twice.
    """
    with Session(engine) as session:
        for user_id, left in ((LEFT, True), (STAYED, False)):
            session.add(
                User(
                    id=user_id,
                    full_name=user_id,
                    email_address=f"{user_id.lower()}@test.internal",
                    credential_secure_hash="not-a-real-hash",
                    role_type=InstitutionalRole.MEMBER,
                    deactivated_at=datetime.now(UTC) if left else None,
                )
            )
        session.flush()
        for user_id in (LEFT, STAYED):
            raw = generate_api_key()
            session.add(
                ApiKey(
                    key_hash=hash_api_key(raw), key_prefix=raw[:12], label=user_id, user_id=user_id
                )
            )
        session.commit()
    try:
        yield
    finally:
        with Session(engine) as session:
            session.query(ApiKey).filter(ApiKey.user_id.in_((LEFT, STAYED))).delete()
            session.query(User).filter(User.id.in_((LEFT, STAYED))).delete()
            session.commit()


def _keys_held_by(engine, user_id):
    with Session(engine) as session:
        return session.query(ApiKey).filter(ApiKey.user_id == user_id).count()


def test_a_key_already_held_by_a_deactivated_account_is_deleted(engine):
    """Step back over 019 and forward through it, with a key on each account.

    Its downgrade is empty, so stepping back only moves the version alembic
    reads, and the upgrade then finds the keys planted just before.
    """
    with _accounts_holding_keys(engine):
        with _alembic() as config:
            command.downgrade(config, "018")
            command.upgrade(config, "head")
        assert _keys_held_by(engine, LEFT) == 0
        # An account still in use keeps its key.
        assert _keys_held_by(engine, STAYED) == 1
