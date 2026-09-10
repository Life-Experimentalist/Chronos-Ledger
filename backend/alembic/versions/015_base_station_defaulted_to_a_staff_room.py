# Copyright 2026 Chronos Ledger Contributors
# Licensed under the Apache License, Version 2.0
"""The base station column defaulted to a staff room

Migration 001 gave users.assigned_base_station a server-side default of
"Staff Room Main". That is a guess about what kind of organization is running
this, and the column is not a cosmetic one: it is the locator's last-resort
answer for where somebody is. A person with no base station recorded came back
as sitting in a staff room that need not exist, on an instance that need not
have staff rooms at all.

The column is optional and always was. The default only ever filled it in for
rows that did not set it, which is every row created by a client that leaves
the field out. Dropping it lets those rows hold NULL, which is what they mean,
and the locator answers "Unassigned" for them instead of naming a room.

Existing values are left where they are. A deployment that has been running has
real base stations in this column, and on some of them "Staff Room Main" is the
right answer that somebody typed. Nothing distinguishes those from the ones the
default wrote, so clearing the column to tidy up the wrong ones would delete an
operator's own data along with them. This migration changes what happens to new
rows and nothing else.

The downgrade puts the default back, and likewise touches no existing row.
"""

import sqlalchemy as sa

from alembic import op

revision = "015"
down_revision = "014"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.alter_column(
        "users",
        "assigned_base_station",
        existing_type=sa.String(100),
        existing_nullable=True,
        server_default=None,
    )


def downgrade() -> None:
    op.alter_column(
        "users",
        "assigned_base_station",
        existing_type=sa.String(100),
        existing_nullable=True,
        server_default="Staff Room Main",
    )
