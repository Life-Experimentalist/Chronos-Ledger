# Copyright 2026 Chronos Ledger Contributors
# Licensed under the Apache License, Version 2.0

import enum
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


class InstitutionalRole(enum.StrEnum):
    SUPER_ADMIN = "SUPER_ADMIN"
    DEPT_ADMIN = "DEPT_ADMIN"
    FACULTY = "FACULTY"
    STUDENT = "STUDENT"


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


class AcademicCycle(Base):
    __tablename__ = "academic_cycles"

    id = Column(Integer, primary_key=True, index=True)
    cycle_label = Column(String(50), nullable=False)
    date_bounds_start = Column(Date, nullable=False)
    date_bounds_end = Column(Date, nullable=False)
    operational_status = Column(Boolean, default=False, nullable=False)

    course_offerings = relationship(
        "CourseOffering", back_populates="cycle", cascade="all, delete-orphan"
    )


class User(Base):
    __tablename__ = "users"

    id = Column(String(50), primary_key=True)
    full_name = Column(String(120), nullable=False)
    email_address = Column(String(120), unique=True, nullable=False)
    credential_secure_hash = Column(String(255), nullable=False)
    role_type = Column(Enum(InstitutionalRole), nullable=False)
    department_code = Column(String(50), nullable=True)
    assigned_base_station = Column(String(100), default="Staff Room Main")
    current_occupancy_index = Column(Enum(AccessReadiness), default=AccessReadiness.OPEN_AD_HOC)
    reporting_line_manager = Column(
        String(50), ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )
    initial_login_state = Column(Boolean, default=True)

    manager = relationship("User", remote_side="User.id", foreign_keys=[reporting_line_manager])
    course_registrations = relationship(
        "CourseRegistration", back_populates="student", cascade="all, delete-orphan"
    )


class CourseOffering(Base):
    __tablename__ = "course_offerings"
    __table_args__ = (UniqueConstraint("course_code", "cycle_id", name="uq_course_cycle"),)

    id = Column(Integer, primary_key=True, index=True)
    course_code = Column(String(30), nullable=False)
    course_title = Column(String(150), nullable=False)
    department_code = Column(String(50), nullable=False)
    cycle_id = Column(Integer, ForeignKey("academic_cycles.id", ondelete="CASCADE"), nullable=False)

    cycle = relationship("AcademicCycle", back_populates="course_offerings")
    master_slots = relationship(
        "StructuralMasterSlot", back_populates="course_offering", cascade="all, delete-orphan"
    )
    registrations = relationship(
        "CourseRegistration", back_populates="course_offering", cascade="all, delete-orphan"
    )


class CourseRegistration(Base):
    __tablename__ = "course_registrations"
    __table_args__ = (
        UniqueConstraint("course_offering_id", "student_id", name="unique_student_registration"),
    )

    id = Column(Integer, primary_key=True, index=True)
    course_offering_id = Column(
        Integer, ForeignKey("course_offerings.id", ondelete="CASCADE"), nullable=False
    )
    student_id = Column(String(50), ForeignKey("users.id", ondelete="CASCADE"), nullable=False)

    course_offering = relationship("CourseOffering", back_populates="registrations")
    student = relationship("User", back_populates="course_registrations")


class StructuralMasterSlot(Base):
    __tablename__ = "structural_master_slots"
    __table_args__ = (CheckConstraint("day_of_week_index BETWEEN 1 AND 7"),)

    id = Column(Integer, primary_key=True, index=True)
    day_of_week_index = Column(Integer, nullable=False)
    time_window_start = Column(Time, nullable=False)
    time_window_end = Column(Time, nullable=False)
    course_offering_id = Column(
        Integer, ForeignKey("course_offerings.id", ondelete="CASCADE"), nullable=False
    )
    primary_instructor_id = Column(
        String(50), ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )
    target_room_identifier = Column(String(30), nullable=False)

    course_offering = relationship("CourseOffering", back_populates="master_slots")
    primary_instructor = relationship("User", foreign_keys=[primary_instructor_id])
    daily_ledger_entries = relationship(
        "DailyLedger", back_populates="master_slot", cascade="all, delete-orphan"
    )


class DailyLedger(Base):
    __tablename__ = "daily_ledger"

    id = Column(BigInteger().with_variant(Integer, "sqlite"), primary_key=True, index=True)
    target_date = Column(Date, nullable=False, index=True)
    master_slot_id = Column(
        Integer, ForeignKey("structural_master_slots.id", ondelete="CASCADE"), nullable=True
    )
    course_offering_id = Column(
        Integer, ForeignKey("course_offerings.id", ondelete="CASCADE"), nullable=False
    )
    active_instructor_id = Column(String(50), ForeignKey("users.id"), nullable=True)
    substitute_instructor_id = Column(String(50), ForeignKey("users.id"), nullable=True)
    target_room_identifier = Column(String(30), nullable=False)
    delivery_format = Column(Enum(ExecutionMode), default=ExecutionMode.PHYSICAL)
    virtual_connection_string = Column(Text, nullable=True)
    latitude_target = Column(Numeric(10, 8), nullable=True)
    longitude_target = Column(Numeric(11, 8), nullable=True)
    altitude_target = Column(Numeric(6, 2), nullable=True)
    precision_radius_meters = Column(Integer, default=15)
    operational_state = Column(Enum(DynamicState), default=DynamicState.SCHEDULED)

    master_slot = relationship("StructuralMasterSlot", back_populates="daily_ledger_entries")
    active_instructor = relationship("User", foreign_keys=[active_instructor_id])
    substitute_instructor = relationship("User", foreign_keys=[substitute_instructor_id])
    course_offering = relationship("CourseOffering")
    verification_records = relationship(
        "VerificationLedger", back_populates="ledger_instance", cascade="all, delete-orphan"
    )
    annotations = relationship(
        "LedgerAnnotation", back_populates="ledger_instance", cascade="all, delete-orphan"
    )


class ReverseRsvpLog(Base):
    __tablename__ = "reverse_rsvp_logs"

    id = Column(Integer, primary_key=True, index=True)
    submitting_user_id = Column(
        String(50), ForeignKey("users.id", ondelete="CASCADE"), nullable=False
    )
    target_absence_date = Column(Date, nullable=False)
    context_justification = Column(Text, nullable=False)
    approval_state = Column(
        Enum(LogVerificationState), default=LogVerificationState.PENDING_VERIFICATION
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
            "ledger_instance_id", "student_id", name="single_student_per_instance_record"
        ),
    )

    id = Column(BigInteger().with_variant(Integer, "sqlite"), primary_key=True, index=True)
    ledger_instance_id = Column(
        BigInteger, ForeignKey("daily_ledger.id", ondelete="CASCADE"), nullable=False
    )
    student_id = Column(String(50), ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    marking_status = Column(Enum(VerificationMetric), nullable=False)
    authorizing_agent_id = Column(String(50), ForeignKey("users.id"), nullable=True)
    modification_timestamp = Column(DateTime(timezone=True), default=lambda: datetime.now(UTC))

    ledger_instance = relationship("DailyLedger", back_populates="verification_records")
    student = relationship("User", foreign_keys=[student_id])
    authorizing_agent = relationship("User", foreign_keys=[authorizing_agent_id])


class LedgerAnnotation(Base):
    __tablename__ = "ledger_annotations"

    id = Column(Integer, primary_key=True, index=True)
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

    id = Column(Integer, primary_key=True, index=True)
    guest_name = Column(String(100), nullable=False)
    contact_phone = Column(String(20), nullable=False)
    originating_body = Column(String(150), nullable=False)
    target_faculty_id = Column(
        String(50), ForeignKey("users.id", ondelete="CASCADE"), nullable=False
    )
    visitation_intent = Column(Text, nullable=False)
    handshake_status = Column(
        Enum(LogVerificationState), default=LogVerificationState.PENDING_VERIFICATION
    )
    timestamp_marked = Column(DateTime(timezone=True), default=lambda: datetime.now(UTC))

    target_faculty = relationship("User", foreign_keys=[target_faculty_id])
