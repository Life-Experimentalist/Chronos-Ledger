# Copyright 2026 Chronos Ledger Contributors
# Licensed under the Apache License, Version 2.0
"""API keys

External systems (an HR export, a room-panel display, a sync script) need a
credential that survives longer than a fifteen-minute JWT and can be revoked
without changing anyone's password. A key is bound to an ordinary user row,
usually a service account, and is stored hashed like a refresh token: a
database leak leaks no credentials.

Revision ID: 005
Revises: 004
Create Date: 2026-09-07 00:00:00.000000
"""

import sqlalchemy as sa

from alembic import op

revision = "005"
down_revision = "004"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "api_keys",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("key_hash", sa.String(64), nullable=False),
        sa.Column("key_prefix", sa.String(12), nullable=False),
        sa.Column("label", sa.String(100), nullable=False),
        sa.Column(
            "user_id",
            sa.String(50),
            sa.ForeignKey("users.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.create_index("ix_api_keys_key_hash", "api_keys", ["key_hash"], unique=True)
    op.create_index("ix_api_keys_user_id", "api_keys", ["user_id"])


def downgrade() -> None:
    op.drop_index("ix_api_keys_user_id", table_name="api_keys")
    op.drop_index("ix_api_keys_key_hash", table_name="api_keys")
    op.drop_table("api_keys")
