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


class ResourceType(enum.StrEnum):
    """What a bookable thing is.

    Only these two exist because only these two are created. ROOM is what
    the import and the backfill produce. PERSON exists because
    Resource.user_id ships alongside it: a resource row carrying a user is a
    person, and a column that says so with no value to say it with would be
    incoherent. Adding a kind later is one ALTER TYPE, and the modes a kind
    can be consumed in (exclusive, pooled, shared) are a separate axis that
    is not stored yet.
    """

    ROOM = "ROOM"
    PERSON = "PERSON"


class ReservationStatus(enum.StrEnum):
    """A hold either stands or it has been let go.

    Cancelling keeps the row rather than deleting it. A cancellation is
    something an outside system has to be told about, and there is nothing
    left to tell it about once the row is gone.
    """

    HELD = "HELD"
    CANCELLED = "CANCELLED"


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


class Resource(Base):
    """A thing a reservation consumes: a room today, a person or a machine later.

    Rooms used to be a bare string repeated on every slot and every generated
    day, which meant nothing could hold a room's capacity or its coordinates,
    a rename had to be found and replaced everywhere, and two rows naming the
    same room were the same room only by spelling.

    code is unique, and one row per distinct string is exactly what the
    backfill produces. It is deliberately not scoped by unit: two units both
    calling a room "101" is a real fact about the data that the data cannot
    resolve, so the import treats them as one room rather than inventing a
    distinction it cannot verify.
    """

    __tablename__ = "resources"

    id = Column(Integer, primary_key=True)
    code = Column(String(30), nullable=False, unique=True, index=True)
    label = Column(String(120), nullable=False)
    resource_type = Column(
        Enum(ResourceType, name="resource_type"), nullable=False, default=ResourceType.ROOM
    )
    unit_code = Column(String(50), nullable=True)
    capacity = Column(Integer, nullable=True)
    # A resource row with user_id set is a person. Without it, staff
    # availability and room availability become two mechanisms that drift.
    user_id = Column(String(50), ForeignKey("users.id", ondelete="CASCADE"), nullable=True)
    latitude = Column(Numeric(10, 8), nullable=True)
    longitude = Column(Numeric(11, 8), nullable=True)
    altitude_target = Column(Numeric(6, 2), nullable=True)
    active = Column(Boolean, default=True, nullable=False)


class StructuralMasterSlot(Base):
    __tablename__ = "structural_master_slots"
    __table_args__ = (CheckConstraint("day_of_week_index BETWEEN 1 AND 7"),)

    id = Column(Integer, primary_key=True)
    day_of_week_index = Column(Integer, nullable=False)
    time_window_start = Column(Time, nullable=False)
    time_window_end = Column(Time, nullable=False)
    activity_id = Column(Integer, ForeignKey("activities.id", ondelete="CASCADE"), nullable=False)
    primary_lead_id = Column(String(50), ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    resource_id = Column(Integer, ForeignKey("resources.id"), nullable=True, index=True)
    # Kept in step with the resource by every write path, and read by the
    # frontend and the calendar feed, until they move to resource_id.
    target_room_identifier = Column(String(30), nullable=True)

    activity = relationship("Activity", back_populates="master_slots")
    primary_lead = relationship("User", foreign_keys=[primary_lead_id])
    resource = relationship("Resource", foreign_keys=[resource_id])
    # No delete cascade on purpose. Deleting a slot used to delete every day
    # it had ever produced, attendance and all, so removing a cancelled class
    # from the timetable erased the record that it had ever run. Days that are
    # still only plans are removed by the delete endpoint; days that became
    # records are left behind with master_slot_id nulled.
    daily_ledger_entries = relationship("DailyLedger", back_populates="master_slot")


class DailyLedger(Base):
    __tablename__ = "daily_ledger"

    id = Column(BigInteger().with_variant(Integer, "sqlite"), primary_key=True)
    target_date = Column(Date, nullable=False, index=True)
    master_slot_id = Column(
        Integer, ForeignKey("structural_master_slots.id", ondelete="SET NULL"), nullable=True
    )
    activity_id = Column(Integer, ForeignKey("activities.id", ondelete="CASCADE"), nullable=False)
    active_lead_id = Column(String(50), ForeignKey("users.id"), nullable=True)
    substitute_lead_id = Column(String(50), ForeignKey("users.id"), nullable=True)
    resource_id = Column(Integer, ForeignKey("resources.id"), nullable=True, index=True)
    target_room_identifier = Column(String(30), nullable=True)
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
    resource = relationship("Resource", foreign_keys=[resource_id])
    active_lead = relationship("User", foreign_keys=[active_lead_id])
    substitute_lead = relationship("User", foreign_keys=[substitute_lead_id])
    activity = relationship("Activity")
    verification_records = relationship(
        "VerificationLedger", back_populates="ledger_instance", cascade="all, delete-orphan"
    )
    annotations = relationship(
        "LedgerAnnotation", back_populates="ledger_instance", cascade="all, delete-orphan"
    )


class Reservation(Base):
    """A hold an outside system places on a resource, for one dated window.

    Its own table rather than a slot or a ledger row, because it is neither.
    A slot is a weekly repeat belonging to an activity inside a planning
    cycle; a ledger row is one generated day that attendance gets marked
    against. A reservation belongs to nobody's timetable and nobody takes
    attendance at it. Expressing one as a slot would have meant inventing an
    activity and a cycle for every booking, and expressing one as a ledger
    row would have meant every attendance path learning to skip it.

    Times are naive wall clock, the same as the slot stores, so a booking and
    a timetable can be compared without a conversion that neither of them
    carries the information to make.

    A window may run past midnight, and an end earlier than a start is how it
    says so: 22:00 to 06:00 is a night shift of eight hours, and reserved_date
    is the day it opens on. There is no column holding the date it ends on,
    only that rule, and app.core.time.window_span is where the rule is
    applied. Equal times are refused, by ck_reservations_window since
    migration 011, because 09:00 to 09:00 could mean nothing at all or a full
    day and the row does not say which.

    A weekly slot reads its two times by the same rule, so a night shift can
    be a recurring slot and not only a one off booking, and a booking that
    runs past midnight is compared against the whole timetable.

    Two HELD rows on one resource may not overlap, and the database refuses
    them: an EXCLUDE USING gist constraint named ex_reservations_no_overlap,
    added by migration 010. It is not in __table_args__ and cannot be. An
    exclusion constraint is a Postgres construct, the test suite builds its
    schema with create_all on SQLite, and SQLite has no compiler for one, so
    putting it here would stop the suite from starting. The cost of that is
    real and worth naming: this class no longer describes the whole table, and
    a reader who trusts it will not know the rule is there. Read migration 010
    for the expression, and note that the tests which prove it only run
    against a real PostgreSQL.
    """

    __tablename__ = "reservations"
    __table_args__ = (
        CheckConstraint("time_window_end <> time_window_start", name="ck_reservations_window"),
    )

    id = Column(Integer, primary_key=True)
    resource_id = Column(
        Integer, ForeignKey("resources.id", ondelete="CASCADE"), nullable=False, index=True
    )
    reserved_date = Column(Date, nullable=False, index=True)
    time_window_start = Column(Time, nullable=False)
    time_window_end = Column(Time, nullable=False)
    purpose = Column(String(200), nullable=False)
    # The caller, resolved the way every other endpoint resolves one. An API
    # key acts as the user it is bound to, so a machine booking a room is
    # recorded as that service account and needs no identity of its own.
    requested_by_id = Column(String(50), ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    # Unique across every resource, not per resource. A caller reusing one
    # key for two different rooms has a bug, and a collision here says so
    # rather than quietly booking both.
    idempotency_key = Column(String(120), nullable=False, unique=True, index=True)
    # sha256 of what was asked for, the resource included. The same key with
    # the same request gets the original row back; the same key with a
    # different request is refused, because at that point the caller has lost
    # track of which of the two it meant.
    request_fingerprint = Column(String(64), nullable=False)
    status = Column(
        Enum(ReservationStatus, name="reservation_status"),
        nullable=False,
        default=ReservationStatus.HELD,
    )
    created_at = Column(DateTime(timezone=True), nullable=False, default=lambda: datetime.now(UTC))
    cancelled_at = Column(DateTime(timezone=True), nullable=True)

    resource = relationship("Resource")


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


# A key holding this instead of a scope list may do anything its bound user
# may do. Every key issued before scopes existed is one of these.
WILDCARD_SCOPE = "*"


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
    # Comma separated, one entry per allowed "<area>:<read|write>". The single
    # entry "*" is every area, which is what a key without scopes has always
    # been and what the migration backfills. Bound as a string rather than a
    # table because a scope is never queried across keys: it is read once,
    # with the key, on the request the key authenticates. Text rather than a
    # width because a key naming every area twice is already 265 characters,
    # and a width Postgres enforces is a width SQLite would let the tests
    # sail past.
    scopes = Column(Text, nullable=False, default=WILDCARD_SCOPE)
    # Null means the key never expires, which is what every key issued before
    # this column existed was.
    expires_at = Column(DateTime(timezone=True), nullable=True)
    created_at = Column(DateTime(timezone=True), default=lambda: datetime.now(UTC))
