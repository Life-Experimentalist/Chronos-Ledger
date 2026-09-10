# Copyright 2026 Chronos Ledger Contributors
# Licensed under the Apache License, Version 2.0

"""An API key can be narrowed and can be made to run out

Revision ID: 008
Revises: 007
Create Date: 2026-09-09

A key was all or nothing and forever. Handing one to an integration meant
handing over everything its bound user could do, for good, with revocation
the only way back and nothing to revoke it in response to. That is a poor
thing to give an external system, and giving one to an external system is
exactly what these exist for.

scopes narrows a key to the areas it needs, expires_at makes it run out on
its own. Both are checked where the key is looked up, so no endpoint has to
opt in.

Every key that already exists is backfilled to "*" and a null expiry, which
is precisely what it was before this migration: it keeps working, and it
keeps showing up in the key list as unrestricted, which is the point.
"""

import sqlalchemy as sa

from alembic import op

revision = "008"
down_revision = "007"
branch_labels = None
depends_on = None


def upgrade():
    # server_default fills the existing rows in one statement and then goes,
    # so a key created after this migration must say what it is for rather
    # than inheriting "everything" from the schema.
    op.add_column(
        "api_keys",
        sa.Column("scopes", sa.Text(), nullable=False, server_default="*"),
    )
    op.alter_column("api_keys", "scopes", server_default=None)
    op.add_column("api_keys", sa.Column("expires_at", sa.DateTime(timezone=True), nullable=True))


def downgrade():
    op.drop_column("api_keys", "expires_at")
    op.drop_column("api_keys", "scopes")
