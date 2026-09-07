# Copyright 2026 Chronos Ledger Contributors
# Licensed under the Apache License, Version 2.0

"""Rename campus-specific schema names to the neutral vocabulary.

Stored data is untouched: tables, columns, constraint names and the
institutional_role enum values are renamed in place, and the seeded
admin account is moved to the neutral default address only where the
deployment never changed it.

Revision ID: 004
Revises: 003
"""

import sqlalchemy as sa  # noqa: F401  (kept for parity with sibling revisions)

from alembic import op

revision = "004"
down_revision = "003"
branch_labels = None
depends_on = None

_ROLE_VALUE_RENAMES = [
    ("DEPT_ADMIN", "UNIT_ADMIN"),
    ("FACULTY", "STAFF"),
    ("STUDENT", "MEMBER"),
]

_TABLE_RENAMES = [
    ("academic_cycles", "planning_cycles"),
    ("course_offerings", "activities"),
    ("course_registrations", "activity_enrollments"),
]

_COLUMN_RENAMES = [
    ("users", "department_code", "unit_code"),
    ("activities", "course_code", "activity_code"),
    ("activities", "course_title", "activity_title"),
    ("activities", "department_code", "unit_code"),
    ("activity_enrollments", "course_offering_id", "activity_id"),
    ("activity_enrollments", "student_id", "member_id"),
    ("structural_master_slots", "course_offering_id", "activity_id"),
    ("structural_master_slots", "primary_instructor_id", "primary_lead_id"),
    ("daily_ledger", "course_offering_id", "activity_id"),
    ("daily_ledger", "active_instructor_id", "active_lead_id"),
    ("daily_ledger", "substitute_instructor_id", "substitute_lead_id"),
    ("verification_ledger", "student_id", "member_id"),
    ("guest_gate_registry", "target_faculty_id", "target_staff_id"),
]

_CONSTRAINT_RENAMES = [
    ("activities", "uq_course_cycle", "uq_activity_cycle"),
    ("activity_enrollments", "unique_student_registration", "unique_member_registration"),
    (
        "verification_ledger",
        "single_student_per_instance_record",
        "single_member_per_instance_record",
    ),
]


def upgrade() -> None:
    is_postgres = op.get_bind().dialect.name == "postgresql"

    if is_postgres:
        for old, new in _ROLE_VALUE_RENAMES:
            op.execute(f"ALTER TYPE institutional_role RENAME VALUE '{old}' TO '{new}'")

    for old, new in _TABLE_RENAMES:
        op.rename_table(old, new)

    for table, old, new in _COLUMN_RENAMES:
        op.alter_column(table, old, new_column_name=new)

    if is_postgres:
        for table, old, new in _CONSTRAINT_RENAMES:
            op.execute(f"ALTER TABLE {table} RENAME CONSTRAINT {old} TO {new}")

    # Move the seeded admin to the neutral address, but only where the
    # deployment still runs on the 001 default.
    op.execute(
        "UPDATE users SET email_address = 'admin@org.internal', "
        "full_name = 'Organization Administrator' "
        "WHERE id = 'ADMIN001' AND email_address = 'admin@college.internal'"
    )


def downgrade() -> None:
    is_postgres = op.get_bind().dialect.name == "postgresql"

    op.execute(
        "UPDATE users SET email_address = 'admin@college.internal', "
        "full_name = 'Campus Administrator' "
        "WHERE id = 'ADMIN001' AND email_address = 'admin@org.internal'"
    )

    if is_postgres:
        for table, old, new in _CONSTRAINT_RENAMES:
            op.execute(f"ALTER TABLE {table} RENAME CONSTRAINT {new} TO {old}")

    for table, old, new in _COLUMN_RENAMES:
        op.alter_column(table, new, new_column_name=old)

    for old, new in _TABLE_RENAMES:
        op.rename_table(new, old)

    if is_postgres:
        for old, new in _ROLE_VALUE_RENAMES:
            op.execute(f"ALTER TYPE institutional_role RENAME VALUE '{new}' TO '{old}'")
