# Copyright 2026 Chronos Ledger Contributors
# Licensed under the Apache License, Version 2.0
"""Rooms become rows

A room was a bare string repeated on every slot and every day generated from
it. Nothing could hold a room's capacity or its coordinates, renaming one
meant finding and replacing it everywhere, and two rows naming the same room
were the same room only by spelling. This is the table that fixes that, and
the thing every later booking feature hangs off: an availability query, a
double-booking constraint and a reservation all need something to point at.

The backfill makes one resource per distinct room string and is deliberately
not scoped by unit. Two units both calling a room "101" is a fact about the
data that the data cannot resolve, so they become one room rather than a
distinction the migration invented.

target_room_identifier stays and stays populated, only becoming nullable, so
the frontend, the calendar feed and every read path keep working while the
foreign key catches up. It is dropped in a later migration, not this one.

resources.latitude, longitude and altitude_target are written by nobody yet:
there is no coordinate column in the CSV and no PATCH /resources. They are
here because the column set belongs to one migration, and they are read when
the resources API lands and attendance can fall back to a room's own
coordinates instead of only the per-day override on the ledger row.

Revision ID: 006
Revises: 005
Create Date: 2026-09-09 00:00:00.000000
"""

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

revision = "006"
down_revision = "005"
branch_labels = None
depends_on = None


def upgrade() -> None:
    resource_type = postgresql.ENUM("ROOM", "PERSON", name="resource_type", create_type=False)
    resource_type.create(op.get_bind(), checkfirst=True)

    op.create_table(
        "resources",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("code", sa.String(30), nullable=False),
        sa.Column("label", sa.String(120), nullable=False),
        sa.Column(
            "resource_type",
            resource_type,
            nullable=False,
            server_default="ROOM",
        ),
        sa.Column("unit_code", sa.String(50), nullable=True),
        sa.Column("capacity", sa.Integer(), nullable=True),
        sa.Column(
            "user_id",
            sa.String(50),
            sa.ForeignKey("users.id", ondelete="CASCADE"),
            nullable=True,
        ),
        sa.Column("latitude", sa.Numeric(10, 8), nullable=True),
        sa.Column("longitude", sa.Numeric(11, 8), nullable=True),
        sa.Column("altitude_target", sa.Numeric(6, 2), nullable=True),
        sa.Column("active", sa.Boolean(), nullable=False, server_default="true"),
    )
    op.create_index("ix_resources_code", "resources", ["code"], unique=True)

    for table in ("structural_master_slots", "daily_ledger"):
        op.add_column(table, sa.Column("resource_id", sa.Integer(), nullable=True))
        op.create_foreign_key(
            f"fk_{table}_resource_id", table, "resources", ["resource_id"], ["id"]
        )
        op.create_index(f"ix_{table}_resource_id", table, ["resource_id"])

    # A ledger row can name a room no surviving slot names: master_slot_id is
    # nullable, so deleting a slot leaves its generated days behind. Both
    # tables are read, or those rooms would have no row to point at.
    op.execute(
        """
        INSERT INTO resources (code, label, resource_type, active)
        SELECT code, code, 'ROOM', true FROM (
            SELECT DISTINCT target_room_identifier AS code
            FROM structural_master_slots
            WHERE target_room_identifier IS NOT NULL
            UNION
            SELECT DISTINCT target_room_identifier AS code
            FROM daily_ledger
            WHERE target_room_identifier IS NOT NULL
        ) AS rooms
        """
    )
    for table in ("structural_master_slots", "daily_ledger"):
        op.execute(
            f"""
            UPDATE {table}
            SET resource_id = (
                SELECT id FROM resources WHERE resources.code = {table}.target_room_identifier
            )
            WHERE target_room_identifier IS NOT NULL
            """
        )

    op.alter_column(
        "structural_master_slots",
        "target_room_identifier",
        existing_type=sa.String(30),
        nullable=True,
    )
    op.alter_column(
        "daily_ledger", "target_room_identifier", existing_type=sa.String(30), nullable=True
    )


def downgrade() -> None:
    # Safe because the upgrade never cleared target_room_identifier: every row
    # that had a room still has it spelled out.
    op.alter_column(
        "daily_ledger", "target_room_identifier", existing_type=sa.String(30), nullable=False
    )
    op.alter_column(
        "structural_master_slots",
        "target_room_identifier",
        existing_type=sa.String(30),
        nullable=False,
    )
    for table in ("daily_ledger", "structural_master_slots"):
        op.drop_index(f"ix_{table}_resource_id", table_name=table)
        op.drop_constraint(f"fk_{table}_resource_id", table, type_="foreignkey")
        op.drop_column(table, "resource_id")
    op.drop_index("ix_resources_code", table_name="resources")
    op.drop_table("resources")
    # drop_table leaves the enum type behind on Postgres.
    sa.Enum(name="resource_type").drop(op.get_bind())
