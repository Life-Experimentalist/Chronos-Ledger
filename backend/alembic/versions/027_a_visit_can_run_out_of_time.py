# Copyright 2026 Chronos Ledger Contributors
# Licensed under the Apache License, Version 2.0
"""A visit can run out of time

An approved visit had no end. A visitor let in at nine was still an approved
visitor at nine the next morning, and the desk had nothing to sort by when it
wanted to know who was still inside.

visit_expires_at is written at the decision from GUEST_VISIT_LENGTH_MINUTES.
Null is a visit nobody has approved, one approved while that setting was 0, and
every visit approved before this column existed, so an instance upgrading with
the setting left alone behaves exactly as it did. Nothing is revoked at the
moment it passes: the visit reads as overstayed, the desk is told once, and a
person decides whether to extend it or ask the visitor to leave.

overstay_notified_at is what makes that once. The sweep stamps a row when it
has announced it and skips the stamped ones; an extension clears the stamp, so
a visit that runs over a second time announces itself again.

Revision ID: 027
Revises: 026
"""

import sqlalchemy as sa

from alembic import op

revision = "027"
down_revision = "026"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "guest_gate_registry",
        sa.Column("visit_expires_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.add_column(
        "guest_gate_registry",
        sa.Column("overstay_notified_at", sa.DateTime(timezone=True), nullable=True),
    )


def downgrade() -> None:
    op.drop_column("guest_gate_registry", "overstay_notified_at")
    op.drop_column("guest_gate_registry", "visit_expires_at")
