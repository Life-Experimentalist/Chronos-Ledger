# Copyright 2026 Chronos Ledger Contributors
# Licensed under the Apache License, Version 2.0
"""One room, one generated day, one window

Migration 010 stopped two reservations sharing a room and an hour. Nothing
stopped two generated days doing it. The application refuses a slot laid on
top of another slot and a booking laid on top of a slot, but every one of
those checks reads slots, and what actually puts somebody at a door is the
day the nightly job writes from the slot.

Two ways past the checks were already known. Two admins editing at once both
pass the slot check before either writes, because nothing between the check
and the insert holds the room. And a cycle that is closed does not occupy
anything as far as the checks are concerned, while the future days it has
already produced sit in the table holding rooms nobody can see them holding.

So the room is held here, on the rows that are the booking, rather than only
on the rows that describe the intention. A check in the application can be
outrun; this cannot.

The predicate names all three columns for a reason. resource_id excludes
itself, because a NULL compared with = gives NULL and the row drops out of
the constraint on its own. The two times do not: tsrange(NULL, NULL, '[)')
is not NULL, it is the range with no bound on either side, and it overlaps
every other range on the same resource. Without both IS NOT NULL clauses a
single ad-hoc day with no window would make its room unbookable for the rest
of time. Postgres 17 agrees:

    SELECT tsrange(NULL,NULL,'[)') && tsrange('2026-01-01','2026-01-02','[)');
     ?column?
    ----------
     t

An end earlier than a start means the day finishes on the following date.
That is the rule window_span keeps in Python and the rule migration 010 put
into the reservations constraint, and the CASE below is the same rule a third
time. The three have to agree: a window the application accepts and the
database refuses is a 500, and a window the database accepts and the
application refuses is a room quietly double booked.

A day on leave still holds its room. booked_slots does not read state either,
and the alternative is worse: freeing the room the moment a lead goes on
leave lets a booking land on a class that then gets un-cancelled.

If this migration fails on the way up, it is not the migration that is
wrong. ADD CONSTRAINT ... EXCLUDE has no NOT VALID, so it checks the rows
already in the table, and a failure means the double booking is already
there. This lists the pairs:

    SELECT a.id AS kept, b.id AS clashes_with, a.resource_id, a.target_date
    FROM daily_ledger a
    JOIN daily_ledger b
      ON b.resource_id = a.resource_id
     AND b.id > a.id
    WHERE a.resource_id IS NOT NULL
      AND a.time_window_start IS NOT NULL AND a.time_window_end IS NOT NULL
      AND b.time_window_start IS NOT NULL AND b.time_window_end IS NOT NULL
      AND tsrange(
            a.target_date + a.time_window_start,
            a.target_date + a.time_window_end + CASE
              WHEN a.time_window_end <= a.time_window_start THEN INTERVAL '1 day'
              ELSE INTERVAL '0' END,
            '[)')
       && tsrange(
            b.target_date + b.time_window_start,
            b.target_date + b.time_window_end + CASE
              WHEN b.time_window_end <= b.time_window_start THEN INTERVAL '1 day'
              ELSE INTERVAL '0' END,
            '[)')
    ORDER BY a.resource_id, a.target_date;

Decide which of each pair is the real one and move or delete the other, then
run this again. Nothing here guesses, because a day may already have
attendance marked against it and picking a loser would erase somebody's
record of being present.
"""

from alembic import op

revision = "013"
down_revision = "012"
branch_labels = None
depends_on = None

CONSTRAINT = "ex_daily_ledger_no_overlap"


def upgrade() -> None:
    op.execute("CREATE EXTENSION IF NOT EXISTS btree_gist")
    op.execute(
        f"""
        ALTER TABLE daily_ledger ADD CONSTRAINT {CONSTRAINT}
        EXCLUDE USING gist (
            resource_id WITH =,
            tsrange(
                target_date + time_window_start,
                target_date + time_window_end + CASE
                    WHEN time_window_end <= time_window_start THEN INTERVAL '1 day'
                    ELSE INTERVAL '0'
                END,
                '[)'
            ) WITH &&
        )
        WHERE (
            resource_id IS NOT NULL
            AND time_window_start IS NOT NULL
            AND time_window_end IS NOT NULL
        )
        """
    )


def downgrade() -> None:
    op.execute(f"ALTER TABLE daily_ledger DROP CONSTRAINT IF EXISTS {CONSTRAINT}")
