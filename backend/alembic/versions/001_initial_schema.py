# Copyright 2026 Chronos Ledger Contributors
# Licensed under the Apache License, Version 2.0
"""Initial schema with seed super-admin

Revision ID: 001
Revises:
Create Date: 2026-01-01 00:00:00.000000
"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy import text
from sqlalchemy.dialects import postgresql
import bcrypt

revision = "001"
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "academic_cycles",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("cycle_label", sa.String(50), nullable=False),
        sa.Column("date_bounds_start", sa.Date(), nullable=False),
        sa.Column("date_bounds_end", sa.Date(), nullable=False),
        sa.Column("operational_status", sa.Boolean(), server_default="false", nullable=False),
        sa.PrimaryKeyConstraint("id"),
    )

    institutional_role = postgresql.ENUM(
        "SUPER_ADMIN", "DEPT_ADMIN", "FACULTY", "STUDENT", name="institutional_role"
    )
    access_readiness = postgresql.ENUM(
        "OPEN_AD_HOC", "BUSY", "CRITICAL_DO_NOT_DISTURB", "VERY_FREE", name="access_readiness"
    )
    institutional_role.create(op.get_bind())
    access_readiness.create(op.get_bind())

    op.create_table(
        "users",
        sa.Column("id", sa.String(50), nullable=False),
        sa.Column("full_name", sa.String(120), nullable=False),
        sa.Column("email_address", sa.String(120), unique=True, nullable=False),
        sa.Column("credential_secure_hash", sa.String(255), nullable=False),
        sa.Column(
            "role_type",
            sa.Enum("SUPER_ADMIN", "DEPT_ADMIN", "FACULTY", "STUDENT", name="institutional_role"),
            nullable=False,
        ),
        sa.Column("department_code", sa.String(50), nullable=True),
        sa.Column("assigned_base_station", sa.String(100), server_default="Staff Room Main"),
        sa.Column(
            "current_occupancy_index",
            sa.Enum(
                "OPEN_AD_HOC",
                "BUSY",
                "CRITICAL_DO_NOT_DISTURB",
                "VERY_FREE",
                name="access_readiness",
            ),
            server_default="OPEN_AD_HOC",
        ),
        sa.Column(
            "reporting_line_manager",
            sa.String(50),
            sa.ForeignKey("users.id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column("initial_login_state", sa.Boolean(), server_default="true"),
        sa.PrimaryKeyConstraint("id"),
    )

    op.create_table(
        "course_offerings",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("course_code", sa.String(30), nullable=False),
        sa.Column("course_title", sa.String(150), nullable=False),
        sa.Column("department_code", sa.String(50), nullable=False),
        sa.Column(
            "cycle_id",
            sa.Integer(),
            sa.ForeignKey("academic_cycles.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("course_code", "cycle_id", name="uq_course_cycle"),
    )

    op.create_table(
        "course_registrations",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column(
            "course_offering_id",
            sa.Integer(),
            sa.ForeignKey("course_offerings.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "student_id",
            sa.String(50),
            sa.ForeignKey("users.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("course_offering_id", "student_id", name="unique_student_registration"),
    )

    op.create_table(
        "structural_master_slots",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("day_of_week_index", sa.Integer(), nullable=False),
        sa.Column("time_window_start", sa.Time(), nullable=False),
        sa.Column("time_window_end", sa.Time(), nullable=False),
        sa.Column(
            "course_offering_id",
            sa.Integer(),
            sa.ForeignKey("course_offerings.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "primary_instructor_id",
            sa.String(50),
            sa.ForeignKey("users.id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column("target_room_identifier", sa.String(30), nullable=False),
        sa.PrimaryKeyConstraint("id"),
        sa.CheckConstraint("day_of_week_index BETWEEN 1 AND 7"),
    )

    dynamic_state = postgresql.ENUM(
        "SCHEDULED",
        "ON_LEAVE",
        "PROXY_SUBSTITUTE",
        "LUNCH",
        "INTERNAL_MEETING",
        "ADHOC_EVENT",
        name="dynamic_state",
    )
    execution_mode = postgresql.ENUM("PHYSICAL", "ONLINE_STREAM", name="execution_mode")
    dynamic_state.create(op.get_bind())
    execution_mode.create(op.get_bind())

    op.create_table(
        "daily_ledger",
        sa.Column("id", sa.BigInteger(), nullable=False),
        sa.Column("target_date", sa.Date(), nullable=False),
        sa.Column(
            "master_slot_id",
            sa.Integer(),
            sa.ForeignKey("structural_master_slots.id", ondelete="CASCADE"),
            nullable=True,
        ),
        sa.Column(
            "course_offering_id",
            sa.Integer(),
            sa.ForeignKey("course_offerings.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("active_instructor_id", sa.String(50), sa.ForeignKey("users.id"), nullable=True),
        sa.Column(
            "substitute_instructor_id", sa.String(50), sa.ForeignKey("users.id"), nullable=True
        ),
        sa.Column("target_room_identifier", sa.String(30), nullable=False),
        sa.Column(
            "delivery_format",
            sa.Enum("PHYSICAL", "ONLINE_STREAM", name="execution_mode"),
            server_default="PHYSICAL",
        ),
        sa.Column("virtual_connection_string", sa.Text(), nullable=True),
        sa.Column("latitude_target", sa.Numeric(10, 8), nullable=True),
        sa.Column("longitude_target", sa.Numeric(11, 8), nullable=True),
        sa.Column("altitude_target", sa.Numeric(6, 2), nullable=True),
        sa.Column("precision_radius_meters", sa.Integer(), server_default="15"),
        sa.Column(
            "operational_state",
            sa.Enum(
                "SCHEDULED",
                "ON_LEAVE",
                "PROXY_SUBSTITUTE",
                "LUNCH",
                "INTERNAL_MEETING",
                "ADHOC_EVENT",
                name="dynamic_state",
            ),
            server_default="SCHEDULED",
        ),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_daily_ledger_target_date", "daily_ledger", ["target_date"])

    log_verification_state = postgresql.ENUM(
        "PENDING_VERIFICATION",
        "VERIFIED_APPROVED",
        "VERIFIED_DENIED",
        name="log_verification_state",
    )
    log_verification_state.create(op.get_bind())

    op.create_table(
        "reverse_rsvp_logs",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column(
            "submitting_user_id",
            sa.String(50),
            sa.ForeignKey("users.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("target_absence_date", sa.Date(), nullable=False),
        sa.Column("context_justification", sa.Text(), nullable=False),
        sa.Column(
            "approval_state",
            sa.Enum(
                "PENDING_VERIFICATION",
                "VERIFIED_APPROVED",
                "VERIFIED_DENIED",
                name="log_verification_state",
            ),
            server_default="PENDING_VERIFICATION",
        ),
        sa.Column(
            "authorized_by_user_id",
            sa.String(50),
            sa.ForeignKey("users.id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.PrimaryKeyConstraint("id"),
    )

    verification_metric = postgresql.ENUM("PRESENT", "ABSENT", "LATE", name="verification_metric")
    verification_metric.create(op.get_bind())

    op.create_table(
        "verification_ledger",
        sa.Column("id", sa.BigInteger(), nullable=False),
        sa.Column(
            "ledger_instance_id",
            sa.BigInteger(),
            sa.ForeignKey("daily_ledger.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "student_id",
            sa.String(50),
            sa.ForeignKey("users.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "marking_status",
            sa.Enum("PRESENT", "ABSENT", "LATE", name="verification_metric"),
            nullable=False,
        ),
        sa.Column("authorizing_agent_id", sa.String(50), sa.ForeignKey("users.id"), nullable=True),
        sa.Column(
            "modification_timestamp", sa.DateTime(timezone=True), server_default=sa.func.now()
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "ledger_instance_id", "student_id", name="single_student_per_instance_record"
        ),
    )

    op.create_table(
        "ledger_annotations",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column(
            "ledger_instance_id",
            sa.BigInteger(),
            sa.ForeignKey("daily_ledger.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "creator_id",
            sa.String(50),
            sa.ForeignKey("users.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("classification_tag", sa.String(30), nullable=False),
        sa.Column("annotation_payload", sa.Text(), nullable=False),
        sa.Column(
            "distribution_timestamp", sa.DateTime(timezone=True), server_default=sa.func.now()
        ),
        sa.PrimaryKeyConstraint("id"),
    )

    op.create_table(
        "guest_gate_registry",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("guest_name", sa.String(100), nullable=False),
        sa.Column("contact_phone", sa.String(20), nullable=False),
        sa.Column("originating_body", sa.String(150), nullable=False),
        sa.Column(
            "target_faculty_id",
            sa.String(50),
            sa.ForeignKey("users.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("visitation_intent", sa.Text(), nullable=False),
        sa.Column(
            "handshake_status",
            sa.Enum(
                "PENDING_VERIFICATION",
                "VERIFIED_APPROVED",
                "VERIFIED_DENIED",
                name="log_verification_state",
            ),
            server_default="PENDING_VERIFICATION",
        ),
        sa.Column("timestamp_marked", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.PrimaryKeyConstraint("id"),
    )

    # Seed the default super-admin using parameterized query (avoids f-string injection)
    hashed = bcrypt.hashpw(b"ChronosAdmin2026!", bcrypt.gensalt()).decode("utf-8")
    op.execute(
        text(
            "INSERT INTO users (id, full_name, email_address, credential_secure_hash, role_type, initial_login_state) "
            "VALUES (:uid, :name, :email, :hash, 'SUPER_ADMIN', true) "
            "ON CONFLICT DO NOTHING"
        ),
        {
            "uid": "ADMIN001",
            "name": "Campus Administrator",
            "email": "admin@college.internal",
            "hash": hashed,
        },
    )


def downgrade() -> None:
    for table in [
        "guest_gate_registry",
        "ledger_annotations",
        "verification_ledger",
        "reverse_rsvp_logs",
        "daily_ledger",
        "structural_master_slots",
        "course_registrations",
        "course_offerings",
        "users",
        "academic_cycles",
    ]:
        op.drop_table(table)
    for enum_name in [
        "verification_metric",
        "log_verification_state",
        "execution_mode",
        "dynamic_state",
        "access_readiness",
        "institutional_role",
    ]:
        sa.Enum(name=enum_name).drop(op.get_bind())
