# Copyright 2026 Chronos Ledger Contributors
# Licensed under the Apache License, Version 2.0

import enum
import secrets

from sqlalchemy import (
    DDL,
    BigInteger,
    Boolean,
    CheckConstraint,
    Column,
    Date,
    DateTime,
    Enum,
    ForeignKey,
    Index,
    Integer,
    LargeBinary,
    Numeric,
    String,
    Text,
    Time,
    UniqueConstraint,
    event,
    func,
    text,
)
from sqlalchemy.dialects.postgresql import ExcludeConstraint
from sqlalchemy.orm import relationship, validates

from app.core import clock, recurrence
from app.core.database import Base
from app.core.emails import normalize_email
from app.core.organization import OrganizationScoped

# The two exclusion constraints below compare an integer with = inside a gist
# index, which PostgreSQL can only do with btree_gist loaded. Created ahead of
# the tables, and only there: SQLite has no extensions and no exclusion
# constraints, and skips both.
event.listen(
    Base.metadata,
    "before_create",
    DDL("CREATE EXTENSION IF NOT EXISTS btree_gist").execute_if(dialect="postgresql"),
)


def _no_overlap(name: str, date_column: str, where: str) -> ExcludeConstraint:
    """Two rows on one resource may not cover the same moment.

    A window is the date plus its two times, and an end at or before the start
    means the window runs past midnight into the next date; the same rule
    app.core.time.window_span applies in Python. Half open, so a window that
    ends at 10:00 does not collide with one that starts at 10:00.

    PostgreSQL only, by ddl_if: SQLite cannot express it, and the standalone
    profile holds the same line with BEGIN IMMEDIATE instead
    (app.core.database.sqlite_engine).
    """
    return ExcludeConstraint(
        ("resource_id", "="),
        (
            text(
                f"tsrange({date_column} + time_window_start, {date_column} + time_window_end"
                " + CASE WHEN time_window_end <= time_window_start THEN INTERVAL '1 day'"
                " ELSE INTERVAL '0' END, '[)')"
            ),
            "&&",
        ),
        name=name,
        using="gist",
        where=text(where),
    ).ddl_if(dialect="postgresql")


def generate_feed_token() -> str:
    """Unguessable key for a user's public iCalendar feed URL."""
    return secrets.token_urlsafe(32)


class InstitutionalRole(enum.StrEnum):
    ORG_ADMIN = "ORG_ADMIN"
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
    incoherent. Adding a kind later is one ALTER TYPE. How a resource is
    consumed is a separate axis, ResourceMode, so any kind can be any mode.
    """

    ROOM = "ROOM"
    PERSON = "PERSON"


class ResourceMode(enum.StrEnum):
    """How bookings on one resource stand against each other.

    EXCLUSIVE is one booking at a time, which is what every resource was
    before modes existed and what every resource is unless it says
    otherwise. POOLED is a stock of interchangeable units, capacity of them,
    and a booking takes quantity of them: twelve ventilators, any one as
    good as another. SHARED records who is there and never refuses anybody:
    a corridor, a common room.

    The mode governs reservations only. Weekly slots and generated days hold
    a resource exclusively whatever its mode, as they always did, and on a
    pooled resource a slot or a day takes the whole pool for its window. On
    a shared resource a reservation is not refused by them either.
    """

    EXCLUSIVE = "EXCLUSIVE"
    POOLED = "POOLED"
    SHARED = "SHARED"


# One Enum object for both tables, so PostgreSQL makes the type once.
RESOURCE_MODE = Enum(ResourceMode, name="resource_mode")


class ReservationStatus(enum.StrEnum):
    """A hold either stands or it has been let go.

    Cancelling keeps the row rather than deleting it. A cancellation is
    something an outside system has to be told about, and there is nothing
    left to tell it about once the row is gone.
    """

    HELD = "HELD"
    CANCELLED = "CANCELLED"


class Organization(Base):
    """One organization's corner of the deployment. Every scoped row names one.

    The seeded one is DEFAULT_ORGANIZATION_ID (app/core/schema.py); another
    comes from `chronos-engine organization create`. There is no route that
    makes, renames or removes one.
    """

    __tablename__ = "organizations"

    id = Column(String(50), primary_key=True)
    name = Column(String(120), nullable=False)
    created_at = Column(DateTime(timezone=True), nullable=False, default=clock.now)


class PlanningCycle(OrganizationScoped, Base):
    __tablename__ = "planning_cycles"

    id = Column(Integer, primary_key=True)
    cycle_label = Column(String(50), nullable=False)
    date_bounds_start = Column(Date, nullable=False)
    date_bounds_end = Column(Date, nullable=False)
    operational_status = Column(
        Boolean, default=False, server_default=text("false"), nullable=False
    )

    activities = relationship("Activity", back_populates="cycle", cascade="all, delete-orphan")


class User(OrganizationScoped, Base):
    __tablename__ = "users"

    id = Column(String(50), primary_key=True)
    full_name = Column(String(120), nullable=False)
    email_address = Column(String(120), unique=True, nullable=False)
    credential_secure_hash = Column(String(255), nullable=False)
    # Unlike every other __table_args__ in this file this one cannot sit at the
    # top of the class, because the expression needs the Column above it. The
    # column's own `unique=True` stays: it costs nothing.
    __table_args__ = (
        Index("uq_users_email_address_lower", func.lower(email_address), unique=True),
    )
    role_type = Column(Enum(InstitutionalRole, name="institutional_role"), nullable=False)
    unit_code = Column(String(50), nullable=True)
    assigned_base_station = Column(String(100))
    current_occupancy_index = Column(
        Enum(AccessReadiness, name="access_readiness"),
        default=AccessReadiness.OPEN_AD_HOC,
        server_default="OPEN_AD_HOC",
    )
    reporting_line_manager = Column(
        String(50), ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )
    initial_login_state = Column(Boolean, default=True, server_default=text("true"))
    calendar_feed_token = Column(
        String(64), unique=True, index=True, nullable=True, default=generate_feed_token
    )
    # Set by POST /users/{id}/deactivate and cleared by reactivate. Somebody who
    # leaves is deactivated rather than deleted, so the attendance recorded
    # against them stays (verification_ledger.member_id is ON DELETE RESTRICT).
    deactivated_at = Column(DateTime(timezone=True), nullable=True)

    @validates("email_address")
    def _fold_email(self, _key, value):
        # Every writer agrees on the stored case, including the three that
        # never see a Pydantic schema. A None is handed back untouched so a
        # missing address fails at flush against NOT NULL, which says what is
        # wrong, rather than here on `.strip()`.
        return value if value is None else normalize_email(value)

    manager = relationship("User", remote_side="User.id", foreign_keys=[reporting_line_manager])
    activity_enrollments = relationship(
        "ActivityEnrollment", back_populates="member", cascade="all, delete-orphan"
    )


class Activity(OrganizationScoped, Base):
    __tablename__ = "activities"
    __table_args__ = (UniqueConstraint("activity_code", "cycle_id", name="uq_activity_cycle"),)

    id = Column(Integer, primary_key=True)
    activity_code = Column(String(30), nullable=False)
    activity_title = Column(String(150), nullable=False)
    unit_code = Column(String(50), nullable=False)
    cycle_id = Column(Integer, ForeignKey("planning_cycles.id", ondelete="CASCADE"), nullable=False)
    # Set by POST /schedule/activities/{id}/retire, which also retires every
    # slot. A retired activity is kept rather than deleted so the days it ran
    # and the attendance taken on them stay, and it produces no new days.
    retired_at = Column(DateTime(timezone=True), nullable=True)

    cycle = relationship("PlanningCycle", back_populates="activities")
    master_slots = relationship(
        "StructuralMasterSlot", back_populates="activity", cascade="all, delete-orphan"
    )
    registrations = relationship(
        "ActivityEnrollment", back_populates="activity", cascade="all, delete-orphan"
    )


class ActivityEnrollment(OrganizationScoped, Base):
    __tablename__ = "activity_enrollments"
    __table_args__ = (
        UniqueConstraint("activity_id", "member_id", name="unique_member_registration"),
    )

    id = Column(Integer, primary_key=True)
    activity_id = Column(Integer, ForeignKey("activities.id", ondelete="CASCADE"), nullable=False)
    member_id = Column(String(50), ForeignKey("users.id", ondelete="CASCADE"), nullable=False)

    activity = relationship("Activity", back_populates="registrations")
    member = relationship("User", back_populates="activity_enrollments")


class Resource(OrganizationScoped, Base):
    """A thing a reservation consumes: a room today, a person or a machine later.

    Rooms used to be a bare string repeated on every slot and every generated
    day, which meant nothing could hold a room's capacity or its coordinates,
    a rename had to be found and replaced everywhere, and two rows naming the
    same room were the same room only by spelling.

    code is unique within an organization, and one row per distinct string
    is exactly what the backfill produces. Two organizations each have their
    own "101". It is deliberately not scoped by unit: two units both calling
    a room "101" is a real fact about the data that the data cannot resolve,
    so the import treats them as one room rather than inventing a
    distinction it cannot verify.
    """

    __tablename__ = "resources"
    __table_args__ = (
        # A pool with nothing in it, or with no size at all, refuses every
        # booking and says nothing about why. capacity on any other mode is
        # what it always was: seats, for information.
        CheckConstraint(
            "mode <> 'POOLED' OR (capacity IS NOT NULL AND capacity >= 1)",
            name="ck_resources_pool_capacity",
        ),
        UniqueConstraint("organization_id", "code", name="uq_resources_organization_code"),
    )

    id = Column(Integer, primary_key=True)
    code = Column(String(30), nullable=False, index=True)
    label = Column(String(120), nullable=False)
    resource_type = Column(
        Enum(ResourceType, name="resource_type"),
        nullable=False,
        default=ResourceType.ROOM,
        server_default="ROOM",
    )
    unit_code = Column(String(50), nullable=True)
    # Seats, for information, on an exclusive or shared resource. The size of
    # the pool on a pooled one, and then a limit the booking route enforces.
    capacity = Column(Integer, nullable=True)
    mode = Column(
        RESOURCE_MODE,
        nullable=False,
        default=ResourceMode.EXCLUSIVE,
        server_default="EXCLUSIVE",
    )
    # A resource row with user_id set is a person. Without it, staff
    # availability and room availability become two mechanisms that drift.
    user_id = Column(String(50), ForeignKey("users.id", ondelete="CASCADE"), nullable=True)
    latitude = Column(Numeric(10, 8), nullable=True)
    longitude = Column(Numeric(11, 8), nullable=True)
    altitude_target = Column(Numeric(6, 2), nullable=True)
    active = Column(Boolean, default=True, server_default=text("true"), nullable=False)


class StructuralMasterSlot(OrganizationScoped, Base):
    __tablename__ = "structural_master_slots"

    id = Column(Integer, primary_key=True)
    # The value of an RFC 5545 RRULE property, FREQ=WEEKLY;BYDAY=MO and the
    # like, and the date it starts from. Both are calendar terms in
    # ORG_TIMEZONE; the time of day is the two Time columns below.
    # dtstart is always an occurrence of the rule (app/core/recurrence.py).
    rrule = Column(String(255), nullable=False)
    dtstart = Column(Date, nullable=False)
    time_window_start = Column(Time, nullable=False)
    time_window_end = Column(Time, nullable=False)
    activity_id = Column(Integer, ForeignKey("activities.id", ondelete="CASCADE"), nullable=False)
    primary_lead_id = Column(String(50), ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    resource_id = Column(Integer, ForeignKey("resources.id"), nullable=True, index=True)
    # Kept in step with the resource by every write path, and read by the
    # frontend and the calendar feed, until they move to resource_id.
    target_room_identifier = Column(String(30), nullable=True)
    # Set by POST /schedule/slots/{id}/retire or by retiring the activity. A
    # retired slot produces no new days and holds no room.
    retired_at = Column(DateTime(timezone=True), nullable=True)

    activity = relationship("Activity", back_populates="master_slots")
    primary_lead = relationship("User", foreign_keys=[primary_lead_id])
    resource = relationship("Resource", foreign_keys=[resource_id])
    # No delete cascade on purpose. Deleting a slot used to delete every day
    # it had ever produced, attendance and all, so removing a cancelled class
    # from the timetable erased the record that it had ever run. Days that are
    # still only plans are removed by the delete endpoint; days that became
    # records are left behind with master_slot_id nulled.
    daily_ledger_entries = relationship("DailyLedger", back_populates="master_slot")

    @property
    def day_of_week_index(self) -> int | None:
        """The weekday the rule first lands on, 1 for Monday to 7 for Sunday.

        What a slot stored before it had a rule, kept for API clients through
        0.17 and deprecated. For a rule on more than one weekday it is the
        first one only.
        """
        if self.rrule is None or self.dtstart is None:
            return None
        first = recurrence.first_occurrence(self.rrule, self.dtstart)
        return (first or self.dtstart).isoweekday()


class DailyLedger(OrganizationScoped, Base):
    __tablename__ = "daily_ledger"
    # One day per slot per date.
    __table_args__ = (
        UniqueConstraint("target_date", "master_slot_id", name="uq_daily_ledger_slot_date"),
        # The two ways the ledger is read by range: one room across some days
        # (availability, the room calendar) and one person's days (a staff
        # member's schedule, the location resolver).
        Index("ix_daily_ledger_resource_date", "resource_id", "target_date"),
        Index("ix_daily_ledger_lead_date", "active_lead_id", "target_date"),
        # Two generated days may not put one room to two uses at once. Only
        # rows that name a room and a window take part: an ad-hoc day with no
        # window, or a day with no room, has nothing to collide with. The
        # ledger generator matches the name in the IntegrityError it gets.
        _no_overlap(
            "ex_daily_ledger_no_overlap",
            "target_date",
            "resource_id IS NOT NULL AND time_window_start IS NOT NULL"
            " AND time_window_end IS NOT NULL",
        ),
    )

    id = Column(BigInteger().with_variant(Integer, "sqlite"), primary_key=True)
    target_date = Column(Date, nullable=False, index=True)
    # Copied from the slot when the day is generated rather than read back
    # through it. A day is a booking on a date and had no window of its own,
    # so deleting a slot nulled master_slot_id and the days it had already
    # produced forgot what time they happened at: the calendar feed demoted
    # them to all-day events and the API returned null. Editing a slot's
    # times rewrote history the same way, showing every day it had already
    # run at the new time.
    #
    # Nullable, because an ad-hoc day has no window by design and because a
    # day orphaned before this column existed has no slot left to copy from.
    # An end earlier than a start means the day finishes on the following
    # date, the same rule window_span keeps everywhere else.
    time_window_start = Column(Time, nullable=True)
    time_window_end = Column(Time, nullable=True)
    master_slot_id = Column(
        Integer, ForeignKey("structural_master_slots.id", ondelete="SET NULL"), nullable=True
    )
    activity_id = Column(Integer, ForeignKey("activities.id", ondelete="CASCADE"), nullable=False)
    active_lead_id = Column(String(50), ForeignKey("users.id"), nullable=True)
    substitute_lead_id = Column(String(50), ForeignKey("users.id"), nullable=True)
    resource_id = Column(Integer, ForeignKey("resources.id"), nullable=True, index=True)
    target_room_identifier = Column(String(30), nullable=True)
    delivery_format = Column(
        Enum(ExecutionMode, name="execution_mode"),
        default=ExecutionMode.PHYSICAL,
        server_default="PHYSICAL",
    )
    virtual_connection_string = Column(Text, nullable=True)
    latitude_target = Column(Numeric(10, 8), nullable=True)
    longitude_target = Column(Numeric(11, 8), nullable=True)
    altitude_target = Column(Numeric(6, 2), nullable=True)
    precision_radius_meters = Column(Integer, default=15, server_default="15")
    operational_state = Column(
        Enum(DynamicState, name="dynamic_state"),
        default=DynamicState.SCHEDULED,
        server_default="SCHEDULED",
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


class Reservation(OrganizationScoped, Base):
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
    applied. Equal times are refused, by ck_reservations_window, because
    09:00 to 09:00 could mean nothing at all or a full day and the row does
    not say which.

    A weekly slot reads its two times by the same rule, so a night shift can
    be a recurring slot and not only a one off booking, and a booking that
    runs past midnight is compared against the whole timetable.

    Two HELD rows on one exclusive resource may not overlap, and on
    PostgreSQL the database refuses them: ex_reservations_no_overlap below,
    an EXCLUDE USING gist constraint. SQLite has no such thing, so there the
    constraint is skipped and the route's own conflict check, run under BEGIN
    IMMEDIATE, is the whole of the protection. The tests that prove the
    constraint only run against a real PostgreSQL (tests/*_pg.py).

    mode is the resource's mode, copied onto the row, because an exclusion
    constraint can only read the row it is checking and the constraint has
    to know whether this row is one that excludes. The route writes it at
    booking time, and changing a resource's mode rewrites it on the holds
    still to come (app.api.v1.endpoints.resources.update_resource), where on
    PostgreSQL the rewrite is itself checked by the constraint. Pooled and
    shared rows are outside the constraint: a pool is a sum, which no
    exclusion constraint can express, and is checked by the route under the
    resource's row lock.
    """

    __tablename__ = "reservations"
    __table_args__ = (
        CheckConstraint("time_window_end <> time_window_start", name="ck_reservations_window"),
        # The conflict check reads one resource on one date.
        Index("ix_reservations_resource_date", "resource_id", "reserved_date"),
        # A cancelled hold keeps its row and frees its window, so only HELD
        # rows take part, and only on an exclusive resource. The reservations
        # route matches the name in the IntegrityError it gets and answers 409.
        _no_overlap(
            "ex_reservations_no_overlap",
            "reserved_date",
            "status = 'HELD' AND mode = 'EXCLUSIVE'",
        ),
        CheckConstraint("quantity >= 1", name="ck_reservations_quantity"),
        # A key belongs to the person who sent it, so two callers cannot
        # collide on one by chance. SQLite and PostgreSQL both let any number
        # of rows share a key once their requester is deleted (SET NULL).
        UniqueConstraint(
            "requested_by_id", "idempotency_key", name="uq_reservations_requester_key"
        ),
        # The caller's own name for the booking, unique per caller for the
        # same reason the key is. A null is no reference at all, and SQLite
        # and PostgreSQL both treat nulls as distinct here, so any number of
        # rows may leave it unset. A cancelled row keeps its reference.
        UniqueConstraint("requested_by_id", "external_ref", name="uq_reservations_requester_ref"),
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
    # Unique per requester across every resource, not per resource. A caller
    # reusing one key for two different rooms has a bug, and a collision here
    # says so rather than quietly booking both. The same key also has a row in
    # idempotency_records (app/core/idempotency.py); this column stays because
    # the route answers a retry from the reservation itself, as it stands now.
    idempotency_key = Column(String(120), nullable=False, index=True)
    # sha256 of what was asked for, the resource included. The same key with
    # the same request gets the original row back; the same key with a
    # different request is refused, because at that point the caller has lost
    # track of which of the two it meant.
    request_fingerprint = Column(String(64), nullable=False)
    # What the caller calls this booking in its own system, so it can find and
    # change the booking without keeping Chronos's id. Optional, and the same
    # length as the key.
    external_ref = Column(String(120), nullable=True)
    # How many units of a pooled resource this holds. Always 1 on any other
    # mode.
    quantity = Column(Integer, nullable=False, default=1, server_default="1")
    mode = Column(
        RESOURCE_MODE,
        nullable=False,
        default=ResourceMode.EXCLUSIVE,
        server_default="EXCLUSIVE",
    )
    status = Column(
        Enum(ReservationStatus, name="reservation_status"),
        nullable=False,
        default=ReservationStatus.HELD,
        server_default="HELD",
    )
    created_at = Column(
        DateTime(timezone=True),
        nullable=False,
        default=clock.now,
    )
    cancelled_at = Column(DateTime(timezone=True), nullable=True)

    resource = relationship("Resource")


class ReverseRsvpLog(OrganizationScoped, Base):
    __tablename__ = "reverse_rsvp_logs"

    id = Column(Integer, primary_key=True)
    submitting_user_id = Column(
        String(50), ForeignKey("users.id", ondelete="CASCADE"), nullable=False
    )
    target_absence_date = Column(Date, nullable=False)
    # The last day of a longer absence, inclusive. Null means the one day.
    end_date = Column(Date, nullable=True)
    context_justification = Column(Text, nullable=False)
    approval_state = Column(
        Enum(LogVerificationState, name="log_verification_state"),
        default=LogVerificationState.PENDING_VERIFICATION,
        server_default="PENDING_VERIFICATION",
    )
    authorized_by_user_id = Column(
        String(50), ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )

    submitting_user = relationship("User", foreign_keys=[submitting_user_id])
    authorizing_user = relationship("User", foreign_keys=[authorized_by_user_id])


class VerificationLedger(OrganizationScoped, Base):
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
    member_id = Column(String(50), ForeignKey("users.id", ondelete="RESTRICT"), nullable=False)
    marking_status = Column(Enum(VerificationMetric, name="verification_metric"), nullable=False)
    authorizing_agent_id = Column(String(50), ForeignKey("users.id"), nullable=True)
    modification_timestamp = Column(DateTime(timezone=True), default=clock.now)

    ledger_instance = relationship("DailyLedger", back_populates="verification_records")
    member = relationship("User", foreign_keys=[member_id])
    authorizing_agent = relationship("User", foreign_keys=[authorizing_agent_id])


class LedgerAnnotation(OrganizationScoped, Base):
    __tablename__ = "ledger_annotations"

    id = Column(Integer, primary_key=True)
    ledger_instance_id = Column(
        BigInteger, ForeignKey("daily_ledger.id", ondelete="CASCADE"), nullable=False
    )
    creator_id = Column(String(50), ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    classification_tag = Column(String(30), nullable=False)
    annotation_payload = Column(Text, nullable=False)
    distribution_timestamp = Column(DateTime(timezone=True), default=clock.now)

    ledger_instance = relationship("DailyLedger", back_populates="annotations")
    creator = relationship("User", foreign_keys=[creator_id])


class GuestGateRegistry(OrganizationScoped, Base):
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
        server_default="PENDING_VERIFICATION",
    )
    timestamp_marked = Column(DateTime(timezone=True), default=clock.now)
    # What GET /guest/visit/{code} finds the check-in by. The code itself is
    # shown to the visitor once and kept nowhere. Null on the check-ins made
    # before there were codes.
    visit_code_hash = Column(String(64), unique=True, index=True, nullable=True)
    # When the code stops opening the status lookup. Null means it does not,
    # which is every check-in made while GUEST_VISIT_CODE_TTL_MINUTES was 0 and
    # every one made before the column existed.
    visit_code_expires_at = Column(DateTime(timezone=True), nullable=True)
    # Whoever decided it, which with GUEST_ADMIN_CAN_DECIDE on is not
    # necessarily the person the visitor came to see. Written at the decision
    # whoever makes it, so null is a check-in nobody has decided yet, or one
    # decided before this column existed. SET NULL rather than the CASCADE on
    # target_staff_id: deleting the account that decided must not delete the
    # visitor record it decided.
    decided_by_id = Column(String(50), ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    # When an approved visit is over. Written at the decision from
    # GUEST_VISIT_LENGTH_MINUTES, so null is a visit nobody has approved, one
    # approved while that setting was 0, or one approved before this column
    # existed. Nothing enforces it: past this moment the visit reads as
    # overstayed and the desk is told, and a person decides the rest.
    visit_expires_at = Column(DateTime(timezone=True), nullable=True)
    # When the sweep last told somebody this visit had run over, so that it
    # tells them once rather than every five minutes. Cleared by an extension,
    # which is what makes a second overrun announce itself again.
    overstay_notified_at = Column(DateTime(timezone=True), nullable=True)

    target_staff = relationship("User", foreign_keys=[target_staff_id])


class RefreshToken(Base):
    """One row per refresh token issued, until it expires. The raw token never
    touches the database: only its SHA-256 hash is stored.

    A token works once. Using it sets consumed_at and mints its successor in
    the same family_id, and a sign-in starts a new family. The used row is
    kept so that a second presentation of it reads as reuse rather than as a
    typo, and reuse ends the family: see endpoints/auth.py::refresh. Rows go
    at logout (the whole family), at a password change (every family the
    user has), and a day after expiry (cron/refresh_token_cleanup.py)."""

    __tablename__ = "refresh_tokens"

    id = Column(Integer, primary_key=True, autoincrement=True)
    token_hash = Column(String(64), unique=True, index=True, nullable=False)
    user_id = Column(
        String(50), ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True
    )
    family_id = Column(String(36), nullable=False, index=True)
    expires_at = Column(DateTime(timezone=True), nullable=False)
    consumed_at = Column(DateTime(timezone=True), nullable=True)
    created_at = Column(DateTime(timezone=True), default=clock.now)


# A key holding this instead of a scope list may do anything its bound user
# may do. Every key issued before scopes existed is one of these.
WILDCARD_SCOPE = "*"


class ApiKey(OrganizationScoped, Base):
    """A long-lived machine credential for external integrations, bound to a
    normal user row (a service account). Only the SHA-256 hash is stored; the
    raw key is shown once at creation. Every request made with the key acts
    as the bound user, so role checks and unit scoping apply unchanged. The
    first-login gate does not: it concerns the account's password, which a
    key never uses."""

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
    # been. Bound as a string rather than a
    # table because a scope is never queried across keys: it is read once,
    # with the key, on the request the key authenticates. Text rather than a
    # width because a key naming every area twice is already 265 characters,
    # and a width Postgres enforces is a width SQLite would let the tests
    # sail past.
    scopes = Column(Text, nullable=False, default=WILDCARD_SCOPE)
    # Null means the key never expires, which is what every key issued before
    # this column existed was.
    expires_at = Column(DateTime(timezone=True), nullable=True)
    created_at = Column(DateTime(timezone=True), default=clock.now)


class AuditRecord(OrganizationScoped, Base):
    """One write made through the API, or one read of the conflict report: who, with
    which key, what, and how it ended.

    No foreign keys to users or keys on purpose. A record has to outlive the
    account and the key that made it, and a user deleted with ON DELETE
    CASCADE would take their history with them. Bodies are never kept: a
    login carries a password and an upload carries a whole file.

    The organization is the caller's, and empty when there was no caller (a
    failed sign-in). No organization's admin sees an empty one.
    """

    __tablename__ = "audit_records"
    organization_optional = True

    id = Column(BigInteger().with_variant(Integer, "sqlite"), primary_key=True, autoincrement=True)
    at = Column(DateTime(timezone=True), nullable=False, index=True)
    actor_id = Column(String(50), nullable=True, index=True)
    api_key_id = Column(Integer, nullable=True)
    method = Column(String(10), nullable=False)
    path = Column(String(500), nullable=False)
    status_code = Column(Integer, nullable=False)


class IdempotencyRecord(Base):
    """A write sent with an Idempotency-Key, and the response it got.

    app/core/idempotency.py writes and reads these. A row with no
    status_code is a request still running, or one whose process stopped
    after its handler committed and before the response was recorded. The
    nightly job deletes rows older than IDEMPOTENCY_RETENTION_HOURS.

    caller is "key:<api key id>" or "user:<user id>" (security.caller_identity),
    so a key means something only to whoever sent it. No foreign keys, for
    the reason audit_records has none: a row should not take a user or a key
    down with it, and it expires on its own.
    """

    __tablename__ = "idempotency_records"
    __table_args__ = (UniqueConstraint("caller", "key", name="uq_idempotency_caller_key"),)

    id = Column(BigInteger().with_variant(Integer, "sqlite"), primary_key=True, autoincrement=True)
    caller = Column(String(80), nullable=False)
    key = Column(String(255), nullable=False)
    # sha256 of the method, path, query string and body (idempotency.request_hash).
    request_hash = Column(String(64), nullable=False)
    status_code = Column(Integer, nullable=True)
    # The headers worth sending again (Content-Type, Location), as a JSON object.
    response_headers = Column(Text, nullable=True)
    response_body = Column(LargeBinary, nullable=True)
    created_at = Column(DateTime(timezone=True), nullable=False, default=clock.now, index=True)


class ChangeMarker(OrganizationScoped, Base):
    """A note that one row changed, kept so an outside system can find out.

    An integrator holding its own copy of the rooms and the bookings has no
    way to learn that one moved. The websocket cannot tell it: a notice goes
    to a signed-in socket, and a service behind somebody else's firewall has
    none. Polling every room on a timer is the alternative, and it scales
    with the building rather than with what happened.

    Deliberately thin. It says what changed and when, and nothing about what
    the row now holds or who touched it: the feed reads the current row back
    out of its own table, so a marker cannot go stale or disagree with it,
    and audit_records already answers who. A change that arrives twice is
    therefore harmless, which is what lets the marker be written without a
    lock.

    No foreign keys to the row, as with AuditRecord. A marker outlives what it points
    at, and a cascade would quietly take the news of a deletion away with the
    row it was about.
    """

    __tablename__ = "change_markers"

    # The cursor a consumer holds on to. A sequence and not a timestamp:
    # two markers written in the same millisecond are still ordered, and
    # ordering is the whole of what a cursor needs.
    id = Column(BigInteger().with_variant(Integer, "sqlite"), primary_key=True, autoincrement=True)
    # "resource" or "reservation". A string and not an enum so that a router
    # gaining a feed does not need a schema change to say so.
    entity_kind = Column(String(20), nullable=False)
    entity_id = Column(Integer, nullable=False)
    # "created" or "updated". There is no "deleted": nothing the feed carries
    # is deleted, a cancelled booking keeps its row on purpose, and a change
    # nobody can read afterwards is one a consumer could not act on.
    change_kind = Column(String(10), nullable=False)
    # Not indexed. The feed reads by id and never by time, and this is here
    # to be shown to a consumer rather than to be filtered on.
    at = Column(DateTime(timezone=True), nullable=False, default=clock.now)


class FederatedIssuer(OrganizationScoped, Base):
    """An outside identity system this instance will accept a note from.

    A registration and not an environment variable, because rotating a key and
    revoking an issuer are two of the things this feature exists to survive,
    and both would otherwise be a restart. See docs/federated-identity.md.

    `enabled` false is refused the same way an unknown issuer is, so turning
    one off does not have to mean deleting what it was allowed to assert.
    """

    __tablename__ = "federated_issuers"

    id = Column(Integer, primary_key=True, autoincrement=True)
    # The exact `iss` value the note carries. Compared, never parsed: it is an
    # identifier that happens to look like a URL, and nothing here fetches it.
    issuer = Column(String(255), unique=True, index=True, nullable=False)
    display_name = Column(String(100), nullable=False)
    # The `aud` this instance answers to. An issuer serving several relying
    # parties gives each one its own, so a note for one is refused by the rest.
    audience = Column(String(255), nullable=False)
    enabled = Column(Boolean, nullable=False, default=True)
    created_at = Column(DateTime(timezone=True), default=clock.now)

    keys = relationship(
        "FederatedIssuerKey", back_populates="issuer_row", cascade="all, delete-orphan"
    )
    role_map = relationship(
        "FederatedRoleMap", back_populates="issuer_row", cascade="all, delete-orphan"
    )


class FederatedIssuerKey(OrganizationScoped, Base):
    """One Ed25519 public key an issuer signs with, valid for a stated window.

    A set rather than a single key so a rotation has an overlap: the new key is
    added, the old one's not_after passes, and the old one is removed. A note
    names its key by `kid` in the header and is verified against that key only.
    Trying every key in turn would make the overlap a period in which a retired
    key still works, which is the opposite of the point.
    """

    __tablename__ = "federated_issuer_keys"

    id = Column(Integer, primary_key=True, autoincrement=True)
    issuer_id = Column(
        Integer,
        ForeignKey("federated_issuers.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    kid = Column(String(100), nullable=False)
    # PEM. A public key, so there is nothing here a leak would cost anybody,
    # which is why the administration routes may read it back.
    public_key = Column(Text, nullable=False)
    not_before = Column(DateTime(timezone=True), nullable=False)
    # Null is a key with no planned retirement. A rotation sets it on the old
    # key rather than deleting it, so notes already in flight still verify.
    not_after = Column(DateTime(timezone=True), nullable=True)
    created_at = Column(DateTime(timezone=True), default=clock.now)

    issuer_row = relationship("FederatedIssuer", back_populates="keys")

    __table_args__ = (UniqueConstraint("issuer_id", "kid", name="uq_federated_key_kid"),)


class FederatedRoleMap(OrganizationScoped, Base):
    """What a group an issuer asserts means here.

    The map belongs to the operator. A note names a subject and may name
    groups; it never names a role. A group with no entry lands on MEMBER, so
    an issuer that is trusted to say who somebody is has not thereby been
    trusted to say what they may do.

    Neither admin role can appear. That is a check in the database as well as
    a validator on the route, because it is the one rule whose failure would
    hand an outside system this instance.
    """

    __tablename__ = "federated_role_map"

    id = Column(Integer, primary_key=True, autoincrement=True)
    issuer_id = Column(
        Integer,
        ForeignKey("federated_issuers.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    # One value out of the note's `groups` claim, matched exactly.
    group_claim_value = Column(String(200), nullable=False)
    role_type = Column(Enum(InstitutionalRole, name="institutional_role"), nullable=False)
    unit_code = Column(String(50), nullable=True)

    issuer_row = relationship("FederatedIssuer", back_populates="role_map")

    __table_args__ = (
        UniqueConstraint("issuer_id", "group_claim_value", name="uq_federated_role_map_group"),
        CheckConstraint(
            "role_type IN ('STAFF', 'MEMBER')",
            name="ck_federated_role_map_no_admin",
        ),
    )


class FederatedIdentity(OrganizationScoped, Base):
    """The link between a subject at an issuer and an account here.

    This table is the record of federation, and the only thing consulted to
    decide whether a note belongs to an existing account. An email address
    that happens to match is never enough: linking on one would let an issuer
    that never verified an address take over the account holding it.

    user_id cascades. There is a hard-delete path for accounts, and a link
    left pointing at a deleted one would refuse that person forever instead of
    letting them arrive as somebody new.
    """

    __tablename__ = "federated_identities"

    id = Column(Integer, primary_key=True, autoincrement=True)
    issuer_id = Column(
        Integer,
        ForeignKey("federated_issuers.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    # The note's `sub`. Opaque and issuer-scoped: two issuers may use the same
    # string for different people, which is why the pair is what is unique.
    subject = Column(String(255), nullable=False)
    user_id = Column(
        String(50), ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True
    )
    created_at = Column(DateTime(timezone=True), default=clock.now)

    __table_args__ = (UniqueConstraint("issuer_id", "subject", name="uq_federated_identity"),)


class WebhookSubscription(OrganizationScoped, Base):
    """A URL that is told about changes as they happen, instead of polling for them.

    Fed from change_markers and nothing else, so it says what the change feed
    says. cursor is the last marker this subscription has turned into
    deliveries; a new one starts at the newest marker, so it hears about what
    happens from then on and never about history.

    The secrets are kept as they are, not hashed: signing needs the key
    itself. They are in portability's SECRET_COLUMNS for that reason.
    """

    __tablename__ = "webhook_subscriptions"

    id = Column(Integer, primary_key=True, autoincrement=True)
    url = Column(String(2000), nullable=False)
    # The event types it wants, comma separated and sorted, for example
    # "reservation.created,resource.updated".
    event_types = Column(String(200), nullable=False)
    # The admin's switch. Off, nothing is fanned out or sent until it is on.
    active = Column(Boolean, nullable=False, default=True)
    # Set when deliveries kept failing (services/webhooks.py says how many) or
    # when an import gave it a secret nobody holds. Paused, it fans out and
    # sends nothing until an admin resumes it.
    paused_at = Column(DateTime(timezone=True), nullable=True)
    consecutive_failures = Column(Integer, nullable=False, default=0)
    cursor = Column(BigInteger, nullable=False, default=0)
    secret = Column(String(100), nullable=False)
    # The secret before the last rotation, still signed with until it expires
    # or an admin removes it, so a receiver can switch over without a gap.
    previous_secret = Column(String(100), nullable=True)
    previous_secret_expires_at = Column(DateTime(timezone=True), nullable=True)
    created_at = Column(DateTime(timezone=True), default=clock.now)
    updated_at = Column(DateTime(timezone=True), default=clock.now, onupdate=clock.now)


class WebhookDelivery(OrganizationScoped, Base):
    """One event for one subscription, and whether it has arrived.

    payload is the exact body, built when the marker was fanned out, so every
    retry sends the same bytes. event_id is the webhook-id header and the same
    on every retry, which is what a receiver deduplicates on.
    """

    __tablename__ = "webhook_deliveries"

    id = Column(BigInteger().with_variant(Integer, "sqlite"), primary_key=True, autoincrement=True)
    subscription_id = Column(
        Integer,
        ForeignKey("webhook_subscriptions.id", ondelete="CASCADE"),
        nullable=False,
    )
    marker_id = Column(BigInteger, nullable=False)
    event_id = Column(String(40), nullable=False, unique=True)
    event_type = Column(String(40), nullable=False)
    entity_kind = Column(String(20), nullable=False)
    entity_id = Column(Integer, nullable=False)
    payload = Column(Text, nullable=False)
    # "pending" until it arrives ("succeeded") or runs out of attempts ("failed").
    status = Column(String(10), nullable=False, default="pending")
    attempt_count = Column(Integer, nullable=False, default=0)
    next_attempt_at = Column(DateTime(timezone=True), nullable=True)
    created_at = Column(DateTime(timezone=True), default=clock.now)
    completed_at = Column(DateTime(timezone=True), nullable=True)

    __table_args__ = (
        # One delivery per marker per subscription, whatever two dispatchers
        # racing each other try to write.
        UniqueConstraint("subscription_id", "marker_id", name="uq_webhook_delivery_marker"),
        Index("ix_webhook_deliveries_due", "status", "next_attempt_at"),
        Index(
            "ix_webhook_deliveries_entity",
            "subscription_id",
            "entity_kind",
            "entity_id",
            "marker_id",
        ),
    )


class WebhookAttempt(Base):
    """One try at sending a delivery: what came back and how long it took."""

    __tablename__ = "webhook_attempts"

    id = Column(BigInteger().with_variant(Integer, "sqlite"), primary_key=True, autoincrement=True)
    delivery_id = Column(
        BigInteger().with_variant(Integer, "sqlite"),
        ForeignKey("webhook_deliveries.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    at = Column(DateTime(timezone=True), nullable=False, default=clock.now)
    # Null when nothing came back: a timeout, a refused connection, or a
    # target the SSRF check turned down.
    status_code = Column(Integer, nullable=True)
    response_ms = Column(Integer, nullable=False)
    error = Column(String(200), nullable=True)
    # The first couple of hundred characters of the response body, no more.
    response_excerpt = Column(String(300), nullable=True)
