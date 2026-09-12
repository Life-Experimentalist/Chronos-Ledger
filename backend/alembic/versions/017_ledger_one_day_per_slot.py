# Copyright 2026 Chronos Ledger Contributors
# Licensed under the Apache License, Version 2.0
"""One generated day per slot per date

Nothing said a slot could produce only one row for a date. Migration 013
refuses a second row for a slot that has a room and a window, but only as a
side effect: the second row overlaps the first in the same room. A slot with
no room was never covered, because a NULL resource_id drops the row out of
that constraint. And the nightly job looks for an existing row and inserts
when it finds none, so two runs at once, from two app instances or from a
restart catching up while the scheduled run is going, can both find none.

(target_date, master_slot_id) is now unique. Rows with no master slot, ad-hoc
days and days whose slot has since been deleted, are untouched: NULLs never
compare equal, so any number of them can share a date.

If the upgrade fails, the duplicates are already there. Nothing here picks
which one to keep, because attendance may have been marked against either.
This lists them:

    SELECT target_date, master_slot_id, array_agg(id)
    FROM daily_ledger
    WHERE master_slot_id IS NOT NULL
    GROUP BY 1, 2
    HAVING count(*) > 1;

Decide which row of each group stays, move anything recorded against the
others onto it, delete the others, and run the upgrade again.
"""

from alembic import op

revision = "017"
down_revision = "016"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_unique_constraint(
        "uq_daily_ledger_slot_date", "daily_ledger", ["target_date", "master_slot_id"]
    )


def downgrade() -> None:
    op.drop_constraint("uq_daily_ledger_slot_date", "daily_ledger", type_="unique")
