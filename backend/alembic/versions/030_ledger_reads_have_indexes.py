# Copyright 2026 Chronos Ledger Contributors
# Licensed under the Apache License, Version 2.0
"""Ledger reads by room and by person have indexes of their own

The ledger is read by range two ways. Availability and the room calendar ask
for one room across some days; a staff member's schedule and the location
resolver ask for one person's days. Each had a single-column index on the
date and another on the room, so PostgreSQL either walked every room's rows
for those dates or every date's rows for that room. These two put the room or
the person first and the date second, which is the shape of both questions.

The exclusion constraint from migration 013 does not serve these reads. It is
a GiST index over a time range, partial on rows that have a room and both
times, and the reads filter by date and want rows without either.

The first migration written to run on SQLite as well as PostgreSQL: plain
create_index, nothing either dialect lacks. The standalone profile builds new
files from the models and upgrades existing ones with these scripts, so every
migration from here on has to keep to that.

Revision ID: 030
Revises: 029
"""

from alembic import op

revision = "030"
down_revision = "029"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_index("ix_daily_ledger_resource_date", "daily_ledger", ["resource_id", "target_date"])
    op.create_index("ix_daily_ledger_lead_date", "daily_ledger", ["active_lead_id", "target_date"])


def downgrade() -> None:
    op.drop_index("ix_daily_ledger_lead_date", table_name="daily_ledger")
    op.drop_index("ix_daily_ledger_resource_date", table_name="daily_ledger")
