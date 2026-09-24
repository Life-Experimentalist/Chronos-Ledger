# Copyright 2026 Chronos Ledger Contributors
# Licensed under the Apache License, Version 2.0
"""A visit code can stop working

A visit code is the visitor's only credential and they are shown it once, so
until now a code handed out at a front desk went on opening the status lookup
for as long as the row survived, which with GUEST_RETENTION_DAYS at 0 is
forever.

visit_code_expires_at is when it stops. Null means it does not, so every
existing check-in keeps behaving exactly as it did, and new ones only get a
value when GUEST_VISIT_CODE_TTL_MINUTES is set above 0.

Revision ID: 024
Revises: 023
"""

import sqlalchemy as sa

from alembic import op

revision = "024"
down_revision = "023"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "guest_gate_registry",
        sa.Column("visit_code_expires_at", sa.DateTime(timezone=True), nullable=True),
    )


def downgrade() -> None:
    op.drop_column("guest_gate_registry", "visit_code_expires_at")
