# Copyright 2026 Chronos Ledger Contributors
# Licensed under the Apache License, Version 2.0
"""An admin can decide a visit

Only the person a visitor came to see could let them in, so a visit waited at
the door when that person was in theatre or had gone home. With
GUEST_ADMIN_CAN_DECIDE on, an admin decides those too, and once more than one
account can decide, the row has to say which one did.

decided_by_id is written at the decision whoever makes it. Null is a check-in
nobody has decided yet, or one decided before this column existed, so every
existing row keeps behaving exactly as it did. SET NULL rather than the CASCADE
on target_staff_id: deleting the account that decided must not delete the
visitor record it decided.

Revision ID: 026
Revises: 025
"""

import sqlalchemy as sa

from alembic import op

revision = "026"
down_revision = "025"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "guest_gate_registry",
        sa.Column(
            "decided_by_id",
            sa.String(50),
            sa.ForeignKey("users.id", ondelete="SET NULL"),
            nullable=True,
        ),
    )


def downgrade() -> None:
    op.drop_column("guest_gate_registry", "decided_by_id")
