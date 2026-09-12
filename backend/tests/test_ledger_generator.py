# Copyright 2026 Chronos Ledger Contributors
# Licensed under the Apache License, Version 2.0

import datetime

import pytest
from sqlalchemy.exc import IntegrityError

from app import main
from app.cron.ledger_generator import generate_daily_ledger_entries, missed_ledger_dates
from app.models.db import (
    Activity,
    DailyLedger,
    DynamicState,
    LogVerificationState,
    PlanningCycle,
    ReverseRsvpLog,
    StructuralMasterSlot,
)

# 2026-09-07 is a Monday: isoweekday() == 1.
MONDAY = datetime.date(2026, 9, 7)


def _build_slot(db, seed_users, active=True, day_index=1):
    cycle = PlanningCycle(
        cycle_label="Odd 2026",
        date_bounds_start=datetime.date(2026, 8, 1),
        date_bounds_end=datetime.date(2026, 12, 20),
        operational_status=active,
    )
    db.add(cycle)
    db.flush()
    offering = Activity(
        activity_code="CS101",
        activity_title="Intro to Computing",
        unit_code="CSE",
        cycle_id=cycle.id,
    )
    db.add(offering)
    db.flush()
    slot = StructuralMasterSlot(
        day_of_week_index=day_index,
        time_window_start=datetime.time(9, 0),
        time_window_end=datetime.time(10, 0),
        activity_id=offering.id,
        primary_lead_id=seed_users["staff"].id,
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
    assert entry.active_lead_id == "FAC001"
    assert entry.target_room_identifier == "LH-101"
    assert entry.operational_state == DynamicState.SCHEDULED
    # Copied off the slot rather than pointed at. A day is an interval on a
    # date and had no times of its own, so everything that needed to know
    # when it ran read them back through a pointer that can go away.
    assert entry.time_window_start == datetime.time(9, 0)
    assert entry.time_window_end == datetime.time(10, 0)


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
            submitting_user_id=seed_users["staff"].id,
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


# 2026-08-01 is a Saturday and 2026-12-20 a Sunday: the two ends of the cycle
# _build_slot makes.
@pytest.mark.parametrize(
    ("day_index", "edge"),
    [(6, datetime.date(2026, 8, 1)), (7, datetime.date(2026, 12, 20))],
    ids=["first day", "last day"],
)
def test_both_of_the_cycles_own_dates_generate(db, seed_users, day_index, edge):
    _build_slot(db, seed_users, day_index=day_index)
    assert generate_daily_ledger_entries(edge, db) == 1


@pytest.mark.parametrize(
    "outside",
    [datetime.date(2026, 7, 27), datetime.date(2026, 12, 21)],
    ids=["before it starts", "after it ends"],
)
def test_a_monday_outside_the_cycle_generates_nothing(db, seed_users, outside):
    """The cycle is open and the weekday matches. Only its dates say no."""
    _build_slot(db, seed_users)
    assert generate_daily_ledger_entries(outside, db) == 0


def test_one_slot_cannot_have_two_days_on_one_date(db, seed_users):
    """The key the existence check leans on, from migration 017.

    This slot has no room, so the overlap constraint from migration 013 does
    not see it. Without the key, two runs that both got past the check would
    both write the day.
    """
    slot = _build_slot(db, seed_users)
    assert generate_daily_ledger_entries(MONDAY, db) == 1

    db.add(DailyLedger(target_date=MONDAY, master_slot_id=slot.id, activity_id=slot.activity_id))
    with pytest.raises(IntegrityError):
        db.commit()
    db.rollback()


@pytest.mark.parametrize(
    ("hour", "minute", "dates"),
    [
        (0, 30, [MONDAY]),
        (22, 59, [MONDAY]),
        (23, 0, [MONDAY, MONDAY + datetime.timedelta(days=1)]),
    ],
)
def test_a_restart_catches_up_today_and_only_then_tomorrow(hour, minute, dates):
    now = datetime.datetime.combine(MONDAY, datetime.time(hour, minute))
    assert missed_ledger_dates(now, 23) == dates


def test_the_startup_catch_up_writes_what_a_restart_missed(db, seed_users, monkeypatch):
    """Started at 23:30 on a Monday, with nothing written for either night.

    Monday's day was last night's run and Tuesday's is tonight's, and the
    process that should have done both was down for them.
    """
    monday = _build_slot(db, seed_users, day_index=1)
    tuesday = StructuralMasterSlot(
        day_of_week_index=2,
        time_window_start=datetime.time(9, 0),
        time_window_end=datetime.time(10, 0),
        activity_id=monday.activity_id,
        primary_lead_id=seed_users["staff"].id,
        target_room_identifier="LH-101",
    )
    db.add(tuesday)
    db.commit()
    expected = {(monday.id, MONDAY), (tuesday.id, MONDAY + datetime.timedelta(days=1))}
    monkeypatch.setattr(main, "SessionLocal", lambda: db)
    monkeypatch.setattr(
        main, "org_now", lambda: datetime.datetime.combine(MONDAY, datetime.time(23, 30))
    )

    main._catch_up_ledger()

    written = {(day.master_slot_id, day.target_date) for day in db.query(DailyLedger).all()}
    assert written == expected
