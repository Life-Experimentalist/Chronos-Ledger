# Copyright 2026 Chronos Ledger Contributors
# Licensed under the Apache License, Version 2.0
"""Every write through the API is recorded

One row per request that could change something: when, the account, the API
key if one was used, the method, the path and the status code. Nothing points
at users or api_keys with a foreign key, so deleting an account or revoking a
key leaves the history of what they did in place.
"""

import sqlalchemy as sa

from alembic import op

revision = "021"
down_revision = "020"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "audit_records",
        sa.Column("id", sa.BigInteger(), primary_key=True, autoincrement=True),
        sa.Column("at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("actor_id", sa.String(50), nullable=True),
        sa.Column("api_key_id", sa.Integer(), nullable=True),
        sa.Column("method", sa.String(10), nullable=False),
        sa.Column("path", sa.String(500), nullable=False),
        sa.Column("status_code", sa.Integer(), nullable=False),
    )
    op.create_index("ix_audit_records_at", "audit_records", ["at"])
    op.create_index("ix_audit_records_actor_id", "audit_records", ["actor_id"])


def downgrade() -> None:
    op.drop_index("ix_audit_records_actor_id", table_name="audit_records")
    op.drop_index("ix_audit_records_at", table_name="audit_records")
    op.drop_table("audit_records")
