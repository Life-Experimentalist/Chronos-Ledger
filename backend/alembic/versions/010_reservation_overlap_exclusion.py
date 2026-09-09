# Copyright 2026 Chronos Ledger Contributors
# Licensed under the Apache License, Version 2.0
"""The database refuses two holds on one resource at one time

Migration 009 left this open and said so. The endpoint checks for a clash and
then inserts, and those are two statements. Two callers that both check before
either inserts both see a free room and both get told they have it, which is
the one answer a booking system must never give. Locking the resource row
narrowed the window on Postgres and closed nothing on a database that does not
take the lock, and neither of those is a rule: they are timing.

An exclusion constraint is the rule. Two rows may not both exist if they name
the same resource and their windows overlap, and the database enforces that
however many callers arrive at once, from however many processes, whatever the
application forgot to check.

The window is built from the columns already there rather than from new
tz-aware ones. Reservations store naive wall clock because slots do, and the
two get compared, so making this one table mean something different by nine
o'clock would break the comparison it exists for. A date plus a time is a
timestamp, and that is what the range is made of.

The bound is half open, '[)', which is the same rule the application uses: a
hold that ends at ten and a hold that starts at ten do not overlap, because
nothing is in two places at the instant one hands over to the other.

Only HELD rows are covered. A cancelled hold stays in the table so an outside
system can be told the room was let go, and a row that is no longer holding
anything must not keep the room.

The upper bound carries a day when the end is not after the start. Nothing can
insert such a row yet: a check constraint refuses it and so does the request
schema. It is written now because relaxing that limit is the next change, a
night shift that runs 22:00 to 06:00 being an ordinary thing to book, and a
range whose lower bound is above its upper one is an error at insert rather
than a row that sorts oddly. Writing it later would mean dropping this
constraint and building its index again on a table with holds in it.

btree_gist is needed for the equality half: GiST knows how to index a range
overlap on its own and does not know how to index an integer for equality
until that extension is present. It is a trusted extension on PostgreSQL 13
and later, so the database owner can create it without being a superuser. On a
managed host that allows neither, a person with rights runs the CREATE
EXTENSION once and this migration finds it already there.

The downgrade leaves the extension alone. Dropping it would fail if anything
else had come to depend on it, and an extension sitting unused costs nothing.

Revision ID: 010
Revises: 009
Create Date: 2026-09-10
"""

from alembic import op

revision = "010"
down_revision = "009"
branch_labels = None
depends_on = None

CONSTRAINT = "ex_reservations_no_overlap"


def upgrade() -> None:
    op.execute("CREATE EXTENSION IF NOT EXISTS btree_gist")
    op.execute(
        f"""
        ALTER TABLE reservations ADD CONSTRAINT {CONSTRAINT}
        EXCLUDE USING gist (
            resource_id WITH =,
            tsrange(
                reserved_date + time_window_start,
                reserved_date + time_window_end + CASE
                    WHEN time_window_end <= time_window_start THEN INTERVAL '1 day'
                    ELSE INTERVAL '0'
                END,
                '[)'
            ) WITH &&
        )
        WHERE (status = 'HELD')
        """
    )


def downgrade() -> None:
    op.execute(f"ALTER TABLE reservations DROP CONSTRAINT IF EXISTS {CONSTRAINT}")
