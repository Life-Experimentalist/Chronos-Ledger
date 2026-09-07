# Copyright 2026 Chronos Ledger Contributors
# Licensed under the Apache License, Version 2.0
"""Per-user calendar feed tokens

Feed URLs were keyed by the plain user id, which made every user's schedule
readable by anyone who could guess an id. Each user now gets an unguessable
random token; the feed route only answers to it.

Revision ID: 002
Revises: 001
Create Date: 2026-09-07 00:00:00.000000
"""

import secrets

import sqlalchemy as sa
from sqlalchemy import text

from alembic import op

revision = "002"
down_revision = "001"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("users", sa.Column("calendar_feed_token", sa.String(64), nullable=True))
    op.create_index("ix_users_calendar_feed_token", "users", ["calendar_feed_token"], unique=True)

    conn = op.get_bind()
    for (user_id,) in conn.execute(text("SELECT id FROM users")):
        conn.execute(
            text("UPDATE users SET calendar_feed_token = :token WHERE id = :user_id"),
            {"token": secrets.token_urlsafe(32), "user_id": user_id},
        )


def downgrade() -> None:
    op.drop_index("ix_users_calendar_feed_token", table_name="users")
    op.drop_column("users", "calendar_feed_token")
