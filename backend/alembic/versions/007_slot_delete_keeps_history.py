# Copyright 2026 Chronos Ledger Contributors
# Licensed under the Apache License, Version 2.0

"""Deleting a slot stops deleting the days it produced

Revision ID: 007
Revises: 006
Create Date: 2026-09-09

A ledger row was tied to its slot with ON DELETE CASCADE, so removing a class
from the timetable removed every day that class had ever run, along with the
attendance marked on those days. The common case is a class that ran for six
weeks and then stopped: an admin who takes it off the board should not lose
six weeks of records to do it.

SET NULL instead. The delete endpoint removes the days that are still only
plans and refuses if any of them has become a record; the days that already
happened stay, with no slot to point at. Every reader that joins the slot
already copes with a missing one, because master_slot_id has always been
nullable and ad-hoc entries have always been allowed.

What a detached row loses is its time window, which lives on the slot and
nowhere else. Until the ledger carries its own start and end, a detached day
shows on a calendar feed as an all-day event. That is the same gap ad-hoc
entries have had since the first migration, not a new one.
"""

from alembic import op

revision = "007"
down_revision = "006"
branch_labels = None
depends_on = None

# The original constraint was declared inline in create_table, so Postgres
# named it. The replacement is named explicitly, and the downgrade puts the
# generated name back, so a round trip lands on the schema it started with.
GENERATED = "daily_ledger_master_slot_id_fkey"
EXPLICIT = "fk_daily_ledger_master_slot_id"


def upgrade():
    op.drop_constraint(GENERATED, "daily_ledger", type_="foreignkey")
    op.create_foreign_key(
        EXPLICIT,
        "daily_ledger",
        "structural_master_slots",
        ["master_slot_id"],
        ["id"],
        ondelete="SET NULL",
    )


def downgrade():
    # Rows detached while the constraint was SET NULL keep their null slot.
    # There is nothing to restore them to: the slot they named is gone.
    op.drop_constraint(EXPLICIT, "daily_ledger", type_="foreignkey")
    op.create_foreign_key(
        GENERATED,
        "daily_ledger",
        "structural_master_slots",
        ["master_slot_id"],
        ["id"],
        ondelete="CASCADE",
    )
