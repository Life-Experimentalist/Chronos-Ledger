# Copyright 2026 Chronos Ledger Contributors
# Licensed under the Apache License, Version 2.0
"""A visitor can follow their own check-in

A check-in now comes with a code the visitor is shown at the kiosk, and
GET /guest/visit/{code} answers with that one check-in's status. Only the
code's SHA-256 is stored, as with API keys and refresh tokens, so the table
holding it hands nobody a way in.

Check-ins made before this have no code and get none: there is nobody left
at the kiosk to show one to.
"""

import sqlalchemy as sa

from alembic import op

revision = "020"
down_revision = "019"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("guest_gate_registry", sa.Column("visit_code_hash", sa.String(64), nullable=True))
    op.create_index(
        "ix_guest_gate_registry_visit_code_hash",
        "guest_gate_registry",
        ["visit_code_hash"],
        unique=True,
    )


def downgrade() -> None:
    op.drop_index("ix_guest_gate_registry_visit_code_hash", table_name="guest_gate_registry")
    op.drop_column("guest_gate_registry", "visit_code_hash")
