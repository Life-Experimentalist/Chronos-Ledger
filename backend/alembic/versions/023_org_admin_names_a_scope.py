# Copyright 2026 Chronos Ledger Contributors
# Licensed under the Apache License, Version 2.0
"""Rename the SUPER_ADMIN role to ORG_ADMIN

The other three roles name a thing or a scope: a MEMBER is enrolled, a STAFF
member leads sessions, a UNIT_ADMIN administers one unit. SUPER_ADMIN named a
position on a power ladder instead, which invites the next role to be called
something louder still. ORG_ADMIN says what the role actually is, the
administrator for the whole organization, and pairs with UNIT_ADMIN on the one
axis that distinguishes them, which is scope.

Stored data is untouched. The enum value is renamed in place, so every row
already holding it follows automatically.

Revision ID: 023
Revises: 022
"""

from alembic import op

revision = "023"
down_revision = "022"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # SQLite, which the tests run on, stores the value as a plain string and
    # has no type to alter. Same reasoning as migration 004.
    if op.get_bind().dialect.name == "postgresql":
        op.execute("ALTER TYPE institutional_role RENAME VALUE 'SUPER_ADMIN' TO 'ORG_ADMIN'")


def downgrade() -> None:
    if op.get_bind().dialect.name == "postgresql":
        op.execute("ALTER TYPE institutional_role RENAME VALUE 'ORG_ADMIN' TO 'SUPER_ADMIN'")
