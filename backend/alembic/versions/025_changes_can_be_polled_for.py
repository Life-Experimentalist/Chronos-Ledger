# Copyright 2026 Chronos Ledger Contributors
# Licensed under the Apache License, Version 2.0
"""A change can be polled for

change_markers is one row per change to a resource or a reservation, so a
system holding its own copy of them can ask what moved instead of reading the
whole building on a timer. The table stays empty until CHANGE_FEED_ENABLED is
set, which is why this migration is safe to run on an instance that has no
integrator.

No foreign keys, as with audit_records: a marker outlives what it points at.

Revision ID: 025
Revises: 024
"""

import sqlalchemy as sa

from alembic import op

revision = "025"
down_revision = "024"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "change_markers",
        sa.Column("id", sa.BigInteger(), primary_key=True, autoincrement=True),
        sa.Column("entity_kind", sa.String(length=20), nullable=False),
        sa.Column("entity_id", sa.Integer(), nullable=False),
        sa.Column("change_kind", sa.String(length=10), nullable=False),
        sa.Column("at", sa.DateTime(timezone=True), nullable=False),
    )


def downgrade() -> None:
    op.drop_table("change_markers")
