# Copyright 2026 Chronos Ledger Contributors
# Licensed under the Apache License, Version 2.0

import datetime

from app.cron.ledger_generator import generate_daily_ledger_entries
from app.models.db import (
    AcademicCycle,
    CourseOffering,
    DailyLedger,
    DynamicState,
    LogVerificationState,
    ReverseRsvpLog,
    StructuralMasterSlot,
)

# 2026-09-07 is a Monday: isoweekday() == 1.
MONDAY = datetime.date(2026, 9, 7)


def _build_slot(db, seed_users, active=True, day_index=1):
    cycle = AcademicCycle(
        cycle_label="Odd 2026",
        date_bounds_start=datetime.date(2026, 8, 1),
        date_bounds_end=datetime.date(2026, 12, 20),
        operational_status=active,
    )
    db.add(cycle)
    db.flush()
    offering = CourseOffering(
        course_code="CS101",
        course_title="Intro to Computing",
        department_code="CSE",
        cycle_id=cycle.id,
    )
    db.add(offering)
    db.flush()
    slot = StructuralMasterSlot(
        day_of_week_index=day_index,
        time_window_start=datetime.time(9, 0),
        time_window_end=datetime.time(10, 0),
        course_offering_id=offering.id,
        primary_instructor_id=seed_users["faculty"].id,
        target_room_identifier="LH-101",
    )
    db.add(slot)
    db.commit()
    return slot


def test_materializes_matching_slot(db, seed_users):
    slot = _build_slot(db, seed_users)
    created = generate_daily_ledger_entries(MONDAY, db)
    assert created == 1

    entry = db.query(DailyLedger).one()
    assert entry.target_date == MONDAY
    assert entry.master_slot_id == slot.id
    assert entry.active_instructor_id == "FAC001"
    assert entry.target_room_identifier == "LH-101"
    assert entry.operational_state == DynamicState.SCHEDULED


def test_rerun_is_idempotent(db, seed_users):
    _build_slot(db, seed_users)
    assert generate_daily_ledger_entries(MONDAY, db) == 1
    assert generate_daily_ledger_entries(MONDAY, db) == 0
    assert db.query(DailyLedger).count() == 1


def test_inactive_cycle_generates_nothing(db, seed_users):
    _build_slot(db, seed_users, active=False)
    assert generate_daily_ledger_entries(MONDAY, db) == 0


def test_other_weekday_generates_nothing(db, seed_users):
    _build_slot(db, seed_users, day_index=3)
    assert generate_daily_ledger_entries(MONDAY, db) == 0


def test_approved_leave_marks_entry_on_leave(db, seed_users):
    _build_slot(db, seed_users)
    db.add(
        ReverseRsvpLog(
            submitting_user_id=seed_users["faculty"].id,
            target_absence_date=MONDAY,
            context_justification="Conference",
            approval_state=LogVerificationState.VERIFIED_APPROVED,
            authorized_by_user_id=seed_users["admin"].id,
        )
    )
    db.commit()

    assert generate_daily_ledger_entries(MONDAY, db) == 1
    entry = db.query(DailyLedger).one()
    assert entry.operational_state == DynamicState.ON_LEAVE
