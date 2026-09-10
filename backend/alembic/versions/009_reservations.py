# Copyright 2026 Chronos Ledger Contributors
# Licensed under the Apache License, Version 2.0
"""Something outside can hold a room

Chronos could be read from and could not be written to. An outside system
could ask when a room was free and then had nowhere to put the answer, so
the room it had just checked stayed bookable by everyone else.

A reservation is its own table because it is neither of the two things that
already occupy a resource. A structural master slot is a weekly repeat that
belongs to an activity inside a planning cycle, and a daily ledger row is one
generated day that attendance is marked against. A booking belongs to no
timetable and nobody takes attendance at it, so recording one as a slot would
have meant inventing an activity and a cycle for it, and recording one as a
ledger row would have meant every attendance path learning to skip it.

Times are Time, not timestamptz, matching the slot exactly. A lone tz-aware
table here would be the one place in the schema that meant something
different by nine o'clock, and the conversion that makes every table tz-aware
together is its own migration.

idempotency_key is unique across the whole table rather than per resource. A
caller that reuses one key for two different rooms has a bug, and the
constraint says so instead of quietly booking both.

Nothing overlapping is refused by the database yet. The endpoint checks, and
between the check and the insert there is a window a second writer can fit
through. Closing it needs an EXCLUDE USING gist constraint over a range type,
which needs btree_gist, and that is the migration after this one.

Revision ID: 009
Revises: 008
Create Date: 2026-09-09
"""

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

revision = "009"
down_revision = "008"
branch_labels = None
depends_on = None


def upgrade() -> None:
    reservation_status = postgresql.ENUM(
        "HELD", "CANCELLED", name="reservation_status", create_type=False
    )
    reservation_status.create(op.get_bind(), checkfirst=True)

    op.create_table(
        "reservations",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column(
            "resource_id",
            sa.Integer(),
            sa.ForeignKey("resources.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("reserved_date", sa.Date(), nullable=False),
        sa.Column("time_window_start", sa.Time(), nullable=False),
        sa.Column("time_window_end", sa.Time(), nullable=False),
        sa.Column("purpose", sa.String(200), nullable=False),
        # SET NULL, not CASCADE. Deleting the service account an integration
        # booked through must not delete the bookings: the room is still held
        # and the people expecting it still turn up.
        sa.Column(
            "requested_by_id",
            sa.String(50),
            sa.ForeignKey("users.id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column("idempotency_key", sa.String(120), nullable=False),
        sa.Column("request_fingerprint", sa.String(64), nullable=False),
        sa.Column("status", reservation_status, nullable=False, server_default="HELD"),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("CURRENT_TIMESTAMP"),
        ),
        sa.Column("cancelled_at", sa.DateTime(timezone=True), nullable=True),
        sa.CheckConstraint("time_window_end > time_window_start", name="ck_reservations_window"),
    )
    op.create_index(
        "ix_reservations_idempotency_key", "reservations", ["idempotency_key"], unique=True
    )
    # The conflict check reads one resource on one date, and cancelled rows
    # are filtered out of it, so that is the index it gets.
    op.create_index(
        "ix_reservations_resource_date", "reservations", ["resource_id", "reserved_date"]
    )


def downgrade() -> None:
    op.drop_index("ix_reservations_resource_date", table_name="reservations")
    op.drop_index("ix_reservations_idempotency_key", table_name="reservations")
    op.drop_table("reservations")
    # drop_table leaves the enum type behind on Postgres.
    sa.Enum(name="reservation_status").drop(op.get_bind())
