# Copyright 2026 Chronos Ledger Contributors
# Licensed under the Apache License, Version 2.0
"""A reused refresh token looked the same as an expired one

A refresh token worked once and its row was deleted on use. That made it
single use, but it also threw away the only evidence that a token had been
used before: a second presentation of the same token found no row and got the
same 401 as a typo. Whoever presented a stolen token first kept the session,
the real owner was signed out at their next refresh, and nothing recorded that
one token had been spent twice.

Rows are now kept after use, marked with consumed_at, and every token minted by
rotation carries the family_id of the sign-in it descends from. Presenting a
used token again ends that whole family. See
app/api/v1/endpoints/auth.py::refresh.

Existing rows each become a family of their own. Every row in the table today
is the current token of one session, because its predecessors were deleted, so
one row per family is exactly what they are. Nobody is signed out by this
migration.

The downgrade deletes the used rows before dropping the columns. The code that
goes with it treats any row it finds as live, so a used row left behind would
work a second time.
"""

import sqlalchemy as sa

from alembic import op

revision = "016"
down_revision = "015"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("refresh_tokens", sa.Column("family_id", sa.String(36), nullable=True))
    op.add_column(
        "refresh_tokens", sa.Column("consumed_at", sa.DateTime(timezone=True), nullable=True)
    )
    # gen_random_uuid() is built into Postgres from 13 on.
    op.execute("UPDATE refresh_tokens SET family_id = gen_random_uuid()::text")
    op.alter_column("refresh_tokens", "family_id", existing_type=sa.String(36), nullable=False)
    op.create_index("ix_refresh_tokens_family_id", "refresh_tokens", ["family_id"])


def downgrade() -> None:
    op.execute("DELETE FROM refresh_tokens WHERE consumed_at IS NOT NULL")
    op.drop_index("ix_refresh_tokens_family_id", table_name="refresh_tokens")
    op.drop_column("refresh_tokens", "consumed_at")
    op.drop_column("refresh_tokens", "family_id")
