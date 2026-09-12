# Copyright 2026 Chronos Ledger Contributors
# Licensed under the Apache License, Version 2.0
"""Migration 020 on a real PostgreSQL: the visit code column and its index.

The rest of the suite builds its schema with create_all, which reads the model
and never runs a migration, so only this proves that 020 builds what the model
describes and that its downgrade takes it away again. Set TEST_DATABASE_URL as
for tests/test_admin_rotation_pg.py.
"""

import os

import pytest
from sqlalchemy import create_engine, inspect

from alembic import command
from tests.test_admin_rotation_pg import _alembic

DATABASE_URL = os.environ.get("TEST_DATABASE_URL")

pytestmark = pytest.mark.skipif(
    not DATABASE_URL,
    reason="needs a real PostgreSQL: set TEST_DATABASE_URL",
)


def _columns(engine):
    return {column["name"] for column in inspect(engine).get_columns("guest_gate_registry")}


def _visit_code_indexes(engine):
    return [
        index
        for index in inspect(engine).get_indexes("guest_gate_registry")
        if index["column_names"] == ["visit_code_hash"]
    ]


def test_020_adds_a_unique_visit_code_hash_and_takes_it_away_again():
    engine = create_engine(DATABASE_URL)
    try:
        with _alembic() as config:
            command.upgrade(config, "head")
        assert "visit_code_hash" in _columns(engine)
        # Unique, because the lookup takes the first row it finds, and two
        # visits answering to one code would show one visitor the other's.
        assert [index["unique"] for index in _visit_code_indexes(engine)] == [True]

        with _alembic() as config:
            command.downgrade(config, "019")
        assert "visit_code_hash" not in _columns(engine)
        assert _visit_code_indexes(engine) == []
    finally:
        with _alembic() as config:
            command.upgrade(config, "head")
        engine.dispose()
