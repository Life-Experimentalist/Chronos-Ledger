# Copyright 2026 Chronos Ledger Contributors
# Licensed under the Apache License, Version 2.0
"""A generated day carries its own window

daily_ledger held a date, a room and a nullable pointer at the weekly slot
that produced it, and no times at all. Everything that needed to know when a
day ran read the times back through that pointer, which made a day the only
thing in the schema that is an interval on a date without saying so.

Three things were wrong with that, and none of them needed a double booking
to show up:

Deleting a slot nulls master_slot_id, on purpose, so that removing a class
from the timetable does not erase the days it already ran and the attendance
marked against them. Those days then had no window. The calendar feed demoted
them to all-day events and GET /schedule/ledger/today returned null for both
times. A day that somebody was marked present at forgot what time it happened.

Editing a slot's times rewrote history. A class moved to 10:00 showed every
day it had already run at 10:00, including the ones that ran at 09:00. The
comment on update_master_slot said so and said it would stay wrong until the
ledger carried its own window.

The staff location resolver reached the slot through an inner join, so a day
with no slot was invisible to it entirely.

The columns are nullable and stay nullable. An ad-hoc day has no window by
design, and a day orphaned before this migration has no slot left to copy
from: the backfill reaches every day that still points at a slot and leaves
the rest alone. Those rows are exactly the ones that were already reporting
no time, so nothing that worked stops working.

An end earlier than a start means the day finishes on the following date,
which is the rule window_span keeps in Python and the rule migration 010 put
in SQL. Nothing here needs to encode it; migration 013 does.

The backfill is one UPDATE over rows that already exist and touches no index.
The downgrade drops the columns, which loses the window of every orphaned and
ad-hoc day, because there is nowhere else those were ever written. Days that
still have a slot lose nothing, since the slot still holds the same times.
"""

import sqlalchemy as sa
from alembic import op

revision = "012"
down_revision = "011"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("daily_ledger", sa.Column("time_window_start", sa.Time(), nullable=True))
    op.add_column("daily_ledger", sa.Column("time_window_end", sa.Time(), nullable=True))
    op.execute(
        """
        UPDATE daily_ledger AS d
        SET time_window_start = s.time_window_start,
            time_window_end = s.time_window_end
        FROM structural_master_slots AS s
        WHERE d.master_slot_id = s.id
        """
    )


def downgrade() -> None:
    op.drop_column("daily_ledger", "time_window_end")
    op.drop_column("daily_ledger", "time_window_start")
