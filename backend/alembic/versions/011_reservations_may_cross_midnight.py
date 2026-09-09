# Copyright 2026 Chronos Ledger Contributors
# Licensed under the Apache License, Version 2.0
"""A reservation may run past midnight

Migration 009 wrote time_window_end > time_window_start, which says a booking
has to begin and end on the same date. That was true of everything the system
could express at the time and it is not true of the work people do. A ward
covered from 22:00 to 06:00, a cleaning shift after a plant shuts down, a
night radiography rota: all of them are one window and none of them can be
written as one row under that rule.

The rule becomes <>. An end earlier than a start means the window finishes on
the following date, which is the same encoding migration 010 already put in
SQL when it built the range for the exclusion constraint:

    reserved_date + time_window_end + CASE
        WHEN time_window_end <= time_window_start THEN INTERVAL '1 day'

That CASE was written before anything could produce a row needing it, so the
reservation side of overnight support is already in the database and no index
has to be rebuilt here. Its <= is equivalent to < now that equality is refused
by this constraint, and it is left as it is rather than edited to match: they
agree on every row that can exist, and dropping an exclusion constraint to
rewrite a comparison that cannot fire is not worth the GiST rebuild.

Equality stays refused, and this is the reason it has to. 09:00 to 09:00 under
the new rule is either a zero length window or a full twenty four hours, the
bytes are identical either way, and there is no field left to say which was
meant. A zero length booking clashes with nothing and holds nothing; a day
long one clashes with everything. Refusing the pair is the only reading that
does not silently pick one.

Relaxing a CHECK cannot fail on data: every row that satisfied > satisfies <>.
The downgrade can, and says so below.

A weekly slot still may not cross midnight. That limit lives in the schema
validators rather than in a constraint, and moving it is its own change.
"""

from alembic import op

revision = "011"
down_revision = "010"
branch_labels = None
depends_on = None

CONSTRAINT = "ck_reservations_window"


def upgrade() -> None:
    op.execute(f"ALTER TABLE reservations DROP CONSTRAINT IF EXISTS {CONSTRAINT}")
    op.execute(
        f"ALTER TABLE reservations ADD CONSTRAINT {CONSTRAINT}"
        " CHECK (time_window_end <> time_window_start)"
    )


def downgrade() -> None:
    # Tightening, not relaxing: any overnight booking taken while this
    # migration was applied violates the old rule and the ALTER will be
    # refused, naming the constraint. That refusal is the correct outcome.
    # The rows are real bookings somebody is relying on, and silently
    # deleting or truncating them to let a downgrade through would throw away
    # the schedule to preserve the schema.
    op.execute(f"ALTER TABLE reservations DROP CONSTRAINT IF EXISTS {CONSTRAINT}")
    op.execute(
        f"ALTER TABLE reservations ADD CONSTRAINT {CONSTRAINT}"
        " CHECK (time_window_end > time_window_start)"
    )
