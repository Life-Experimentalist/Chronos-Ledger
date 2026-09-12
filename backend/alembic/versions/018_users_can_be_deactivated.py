# Copyright 2026 Chronos Ledger Contributors
# Licensed under the Apache License, Version 2.0
"""Users can be deactivated instead of deleted

Somebody who left had two outcomes: keep an account that works, or be
deleted. Deleting took their attendance with them, because
verification_ledger.member_id cascaded, and every figure worked out from
those rows changed after the fact. users.deactivated_at is the third
outcome: the account stops working and drops out of the lists staff are
picked from, and everything recorded against it stays.

The cascade becomes RESTRICT, so deleting a user who has attendance on file
now fails instead of taking the attendance with it.

The constraint is found by the column it covers, not by name. 001 created
it unnamed while the column was still student_id, and 004 renamed the column
and left the constraint alone, so its name is whatever PostgreSQL chose at
the time. verification_ledger has a second foreign key to users, on
authorizing_agent_id, which this leaves as it is.

SQLite cannot alter a constraint in place, and the test suite builds its
schema from the models anyway, so the swap only runs on PostgreSQL.
"""

import sqlalchemy as sa

from alembic import op

revision = "018"
down_revision = "017"
branch_labels = None
depends_on = None


def _member_fk_ondelete(ondelete: str) -> None:
    bind = op.get_bind()
    if bind.dialect.name != "postgresql":
        return
    current = next(
        fk["name"]
        for fk in sa.inspect(bind).get_foreign_keys("verification_ledger")
        if fk["constrained_columns"] == ["member_id"]
    )
    op.drop_constraint(current, "verification_ledger", type_="foreignkey")
    op.create_foreign_key(
        "verification_ledger_member_id_fkey",
        "verification_ledger",
        "users",
        ["member_id"],
        ["id"],
        ondelete=ondelete,
    )


def upgrade() -> None:
    op.add_column("users", sa.Column("deactivated_at", sa.DateTime(timezone=True), nullable=True))
    _member_fk_ondelete("RESTRICT")


def downgrade() -> None:
    _member_fk_ondelete("CASCADE")
    op.drop_column("users", "deactivated_at")
