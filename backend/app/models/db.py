# Copyright 2026 Chronos Ledger Contributors
# Licensed under the Apache License, Version 2.0

import enum
import secrets
from datetime import UTC, datetime

from sqlalchemy import (
    BigInteger,
    Boolean,
    CheckConstraint,
    Column,
    Date,
    DateTime,
    Enum,
    ForeignKey,
    Integer,
    Numeric,
    String,
    Text,
    Time,
    UniqueConstraint,
)
from sqlalchemy.orm import relationship

from app.core.database import Base


def generate_feed_token() -> str:
    """Unguessable key for a user's public iCalendar feed URL."""
    return secrets.token_urlsafe(32)


class InstitutionalRole(enum.StrEnum):
    SUPER_ADMIN = "SUPER_ADMIN"
    UNIT_ADMIN = "UNIT_ADMIN"
    STAFF = "STAFF"
    MEMBER = "MEMBER"


class DynamicState(enum.StrEnum):
    SCHEDULED = "SCHEDULED"
    ON_LEAVE = "ON_LEAVE"
    PROXY_SUBSTITUTE = "PROXY_SUBSTITUTE"
    LUNCH = "LUNCH"
    INTERNAL_MEETING = "INTERNAL_MEETING"
    ADHOC_EVENT = "ADHOC_EVENT"


class VerificationMetric(enum.StrEnum):
    PRESENT = "PRESENT"
    ABSENT = "ABSENT"
    LATE = "LATE"


class ExecutionMode(enum.StrEnum):
    PHYSICAL = "PHYSICAL"
    ONLINE_STREAM = "ONLINE_STREAM"


class AccessReadiness(enum.StrEnum):
    OPEN_AD_HOC = "OPEN_AD_HOC"
    BUSY = "BUSY"
    CRITICAL_DO_NOT_DISTURB = "CRITICAL_DO_NOT_DISTURB"
    VERY_FREE = "VERY_FREE"


class LogVerificationState(enum.StrEnum):
    PENDING_VERIFICATION = "PENDING_VERIFICATION"
    VERIFIED_APPROVED = "VERIFIED_APPROVED"
    VERIFIED_DENIED = "VERIFIED_DENIED"


class PlanningCycle(Base):
    __tablename__ = "planning_cycles"

    id = Column(Integer, primary_key=True)
    cycle_label = Column(String(50), nullable=False)
    date_bounds_start = Column(Date, nullable=False)
    date_bounds_end = Column(Date, nullable=False)
    operational_status = Column(Boolean, default=False, nullable=False)

    activities = relationship("Activity", back_populates="cycle", cascade="all, delete-orphan")


class User(Base):
    __tablename__ = "users"

    id = Column(String(50), primary_key=True)
    full_name = Column(String(120), nullable=False)
    email_address = Column(String(120), unique=True, nullable=False)
    credential_secure_hash = Column(String(255), nullable=False)
    role_type = Column(Enum(InstitutionalRole, name="institutional_role"), nullable=False)
    unit_code = Column(String(50), nullable=True)
    assigned_base_station = Column(String(100), default="Staff Room Main")
    current_occupancy_index = Column(
        Enum(AccessReadiness, name="access_readiness"), default=AccessReadiness.OPEN_AD_HOC
    )
    reporting_line_manager = Column(
        String(50), ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )
    initial_login_state = Column(Boolean, default=True)
    calendar_feed_token = Column(
        String(64), unique=True, index=True, nullable=True, default=generate_feed_token
    )

    manager = relationship("User", remote_side="User.id", foreign_keys=[reporting_line_manager])
    activity_enrollments = relationship(
        "ActivityEnrollment", back_populates="member", cascade="all, delete-orphan"
    )


class Activity(Base):
    __tablename__ = "activities"
    __table_args__ = (UniqueConstraint("activity_code", "cycle_id", name="uq_activity_cycle"),)

    id = Column(Integer, primary_key=True)
    activity_code = Column(String(30), nullable=False)
    activity_title = Column(String(150), nullable=False)
    unit_code = Column(String(50), nullable=False)
    cycle_id = Column(Integer, ForeignKey("planning_cycles.id", ondelete="CASCADE"), nullable=False)

    cycle = relationship("PlanningCycle", back_populates="activities")
    master_slots = relationship(
        "StructuralMasterSlot", back_populates="activity", cascade="all, delete-orphan"
    )
    registrations = relationship(
        "ActivityEnrollment", back_populates="activity", cascade="all, delete-orphan"
    )


class ActivityEnrollment(Base):
    __tablename__ = "activity_enrollments"
    __table_args__ = (
        UniqueConstraint("activity_id", "member_id", name="unique_member_registration"),
    )

    id = Column(Integer, primary_key=True)
    activity_id = Column(Integer, ForeignKey("activities.id", ondelete="CASCADE"), nullable=False)
    member_id = Column(String(50), ForeignKey("users.id", ondelete="CASCADE"), nullable=False)

    activity = relationship("Activity", back_populates="registrations")
    member = relationship("User", back_populates="activity_enrollments")


class StructuralMasterSlot(Base):
    __tablename__ = "structural_master_slots"
    __table_args__ = (CheckConstraint("day_of_week_index BETWEEN 1 AND 7"),)

    id = Column(Integer, primary_key=True)
    day_of_week_index = Column(Integer, nullable=False)
    time_window_start = Column(Time, nullable=False)
    time_window_end = Column(Time, nullable=False)
    activity_id = Column(Integer, ForeignKey("activities.id", ondelete="CASCADE"), nullable=False)
    primary_lead_id = Column(String(50), ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    target_room_identifier = Column(String(30), nullable=False)

    activity = relationship("Activity", back_populates="master_slots")
    primary_lead = relationship("User", foreign_keys=[primary_lead_id])
    daily_ledger_entries = relationship(
        "DailyLedger", back_populates="master_slot", cascade="all, delete-orphan"
    )


class DailyLedger(Base):
    __tablename__ = "daily_ledger"

    id = Column(BigInteger().with_variant(Integer, "sqlite"), primary_key=True)
    target_date = Column(Date, nullable=False, index=True)
    master_slot_id = Column(
        Integer, ForeignKey("structural_master_slots.id", ondelete="CASCADE"), nullable=True
    )
    activity_id = Column(Integer, ForeignKey("activities.id", ondelete="CASCADE"), nullable=False)
    active_lead_id = Column(String(50), ForeignKey("users.id"), nullable=True)
    substitute_lead_id = Column(String(50), ForeignKey("users.id"), nullable=True)
    target_room_identifier = Column(String(30), nullable=False)
    delivery_format = Column(
        Enum(ExecutionMode, name="execution_mode"), default=ExecutionMode.PHYSICAL
    )
    virtual_connection_string = Column(Text, nullable=True)
    latitude_target = Column(Numeric(10, 8), nullable=True)
    longitude_target = Column(Numeric(11, 8), nullable=True)
    altitude_target = Column(Numeric(6, 2), nullable=True)
    precision_radius_meters = Column(Integer, default=15)
    operational_state = Column(
        Enum(DynamicState, name="dynamic_state"), default=DynamicState.SCHEDULED
    )

    master_slot = relationship("StructuralMasterSlot", back_populates="daily_ledger_entries")
    active_lead = relationship("User", foreign_keys=[active_lead_id])
    substitute_lead = relationship("User", foreign_keys=[substitute_lead_id])
    activity = relationship("Activity")
    verification_records = relationship(
        "VerificationLedger", back_populates="ledger_instance", cascade="all, delete-orphan"
    )
    annotations = relationship(
        "LedgerAnnotation", back_populates="ledger_instance", cascade="all, delete-orphan"
    )


class ReverseRsvpLog(Base):
    __tablename__ = "reverse_rsvp_logs"

    id = Column(Integer, primary_key=True)
    submitting_user_id = Column(
        String(50), ForeignKey("users.id", ondelete="CASCADE"), nullable=False
    )
    target_absence_date = Column(Date, nullable=False)
    context_justification = Column(Text, nullable=False)
    approval_state = Column(
        Enum(LogVerificationState, name="log_verification_state"),
        default=LogVerificationState.PENDING_VERIFICATION,
    )
    authorized_by_user_id = Column(
        String(50), ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )

    submitting_user = relationship("User", foreign_keys=[submitting_user_id])
    authorizing_user = relationship("User", foreign_keys=[authorized_by_user_id])


class VerificationLedger(Base):
    __tablename__ = "verification_ledger"
    __table_args__ = (
        UniqueConstraint(
            "ledger_instance_id", "member_id", name="single_member_per_instance_record"
        ),
    )

    id = Column(BigInteger().with_variant(Integer, "sqlite"), primary_key=True)
    ledger_instance_id = Column(
        BigInteger, ForeignKey("daily_ledger.id", ondelete="CASCADE"), nullable=False
    )
    member_id = Column(String(50), ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    marking_status = Column(Enum(VerificationMetric, name="verification_metric"), nullable=False)
    authorizing_agent_id = Column(String(50), ForeignKey("users.id"), nullable=True)
    modification_timestamp = Column(DateTime(timezone=True), default=lambda: datetime.now(UTC))

    ledger_instance = relationship("DailyLedger", back_populates="verification_records")
    member = relationship("User", foreign_keys=[member_id])
    authorizing_agent = relationship("User", foreign_keys=[authorizing_agent_id])


class LedgerAnnotation(Base):
    __tablename__ = "ledger_annotations"

    id = Column(Integer, primary_key=True)
    ledger_instance_id = Column(
        BigInteger, ForeignKey("daily_ledger.id", ondelete="CASCADE"), nullable=False
    )
    creator_id = Column(String(50), ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    classification_tag = Column(String(30), nullable=False)
    annotation_payload = Column(Text, nullable=False)
    distribution_timestamp = Column(DateTime(timezone=True), default=lambda: datetime.now(UTC))

    ledger_instance = relationship("DailyLedger", back_populates="annotations")
    creator = relationship("User", foreign_keys=[creator_id])


class GuestGateRegistry(Base):
    __tablename__ = "guest_gate_registry"

    id = Column(Integer, primary_key=True)
    guest_name = Column(String(100), nullable=False)
    contact_phone = Column(String(20), nullable=False)
    originating_body = Column(String(150), nullable=False)
    target_staff_id = Column(String(50), ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    visitation_intent = Column(Text, nullable=False)
    handshake_status = Column(
        Enum(LogVerificationState, name="log_verification_state"),
        default=LogVerificationState.PENDING_VERIFICATION,
    )
    timestamp_marked = Column(DateTime(timezone=True), default=lambda: datetime.now(UTC))

    target_staff = relationship("User", foreign_keys=[target_staff_id])


class RefreshToken(Base):
    """One row per live session. The raw token never touches the database:
    only its SHA-256 hash is stored, and a row is deleted the moment it is used."""

    __tablename__ = "refresh_tokens"

    id = Column(Integer, primary_key=True, autoincrement=True)
    token_hash = Column(String(64), unique=True, index=True, nullable=False)
    user_id = Column(
        String(50), ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True
    )
    expires_at = Column(DateTime(timezone=True), nullable=False)
    created_at = Column(DateTime(timezone=True), default=lambda: datetime.now(UTC))


class ApiKey(Base):
    """A long-lived machine credential for external integrations, bound to a
    normal user row (a service account). Only the SHA-256 hash is stored; the
    raw key is shown once at creation. Every request made with the key acts
    as the bound user, so role checks and unit scoping apply unchanged."""

    __tablename__ = "api_keys"

    id = Column(Integer, primary_key=True, autoincrement=True)
    key_hash = Column(String(64), unique=True, index=True, nullable=False)
    key_prefix = Column(String(12), nullable=False)
    label = Column(String(100), nullable=False)
    user_id = Column(
        String(50), ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True
    )
    created_at = Column(DateTime(timezone=True), default=lambda: datetime.now(UTC))
