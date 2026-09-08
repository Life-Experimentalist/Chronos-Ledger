# Copyright 2026 Chronos Ledger Contributors
# Licensed under the Apache License, Version 2.0

"""What a leave decision does to the days already on the board.

Approving leave rewrites the materialized ledger rows for that person and
date. A decision is not final, so reversing one has to rewrite them back:
before this, a reversed approval left the day sitting at ON_LEAVE with
nobody scheduled to run it and nothing to show it was wrong.
"""

import datetime

from app.cron.ledger_generator import generate_daily_ledger_entries
from app.models.db import (
    Activity,
    DailyLedger,
    DynamicState,
    LogVerificationState,
    PlanningCycle,
    ReverseRsvpLog,
    StructuralMasterSlot,
)
from app.services.reverse_rsvp import commit_absence_override

# 2026-09-07 is a Monday: isoweekday() == 1.
MONDAY = datetime.date(2026, 9, 7)


def _materialized_day(db, seed_users):
    """One staff member, one Monday class, already on the board."""
    cycle = PlanningCycle(
        cycle_label="Odd 2026",
        date_bounds_start=datetime.date(2026, 8, 1),
        date_bounds_end=datetime.date(2026, 12, 20),
        operational_status=True,
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
    db.add(
        StructuralMasterSlot(
            day_of_week_index=1,
            time_window_start=datetime.time(9, 0),
            time_window_end=datetime.time(10, 0),
            activity_id=offering.id,
            primary_lead_id=seed_users["staff"].id,
            target_room_identifier="LH-101",
        )
    )
    db.commit()

    assert generate_daily_ledger_entries(MONDAY, db) == 1
    return db.query(DailyLedger).one()


def _pending_request(db, seed_users):
    log = ReverseRsvpLog(
        submitting_user_id=seed_users["staff"].id,
        target_absence_date=MONDAY,
        context_justification="Conference",
        approval_state=LogVerificationState.PENDING_VERIFICATION,
        authorized_by_user_id=seed_users["admin"].id,
    )
    db.add(log)
    db.commit()
    return log


def test_approval_marks_the_day_on_leave(db, seed_users):
    entry = _materialized_day(db, seed_users)
    log = _pending_request(db, seed_users)

    commit_absence_override(log.id, seed_users["admin"].id, "VERIFIED_APPROVED", db)

    db.refresh(entry)
    assert entry.operational_state == DynamicState.ON_LEAVE


def test_reversing_an_approval_puts_the_day_back(db, seed_users):
    entry = _materialized_day(db, seed_users)
    log = _pending_request(db, seed_users)

    commit_absence_override(log.id, seed_users["admin"].id, "VERIFIED_APPROVED", db)
    db.refresh(entry)
    assert entry.operational_state == DynamicState.ON_LEAVE

    commit_absence_override(log.id, seed_users["admin"].id, "VERIFIED_DENIED", db)

    db.refresh(entry)
    assert entry.operational_state == DynamicState.SCHEDULED
    assert entry.active_lead_id == seed_users["staff"].id
    db.refresh(log)
    assert log.approval_state == LogVerificationState.VERIFIED_DENIED


def test_reversal_leaves_a_covered_day_alone(db, seed_users):
    """A substitute assigned after the approval keeps the day.

    Reversing the leave must not silently unassign whoever is now
    covering it: only days still parked at ON_LEAVE go back.
    """
    entry = _materialized_day(db, seed_users)
    log = _pending_request(db, seed_users)
    commit_absence_override(log.id, seed_users["admin"].id, "VERIFIED_APPROVED", db)

    db.refresh(entry)
    entry.operational_state = DynamicState.PROXY_SUBSTITUTE
    entry.substitute_lead_id = seed_users["admin"].id
    db.commit()

    commit_absence_override(log.id, seed_users["admin"].id, "VERIFIED_DENIED", db)

    db.refresh(entry)
    assert entry.operational_state == DynamicState.PROXY_SUBSTITUTE
    assert entry.substitute_lead_id == seed_users["admin"].id


def test_denial_does_not_reach_another_day(db, seed_users):
    entry = _materialized_day(db, seed_users)
    entry.operational_state = DynamicState.ON_LEAVE
    db.commit()

    # A request for a different date entirely.
    log = ReverseRsvpLog(
        submitting_user_id=seed_users["staff"].id,
        target_absence_date=MONDAY + datetime.timedelta(days=7),
        context_justification="Conference",
        approval_state=LogVerificationState.PENDING_VERIFICATION,
        authorized_by_user_id=seed_users["admin"].id,
    )
    db.add(log)
    db.commit()

    commit_absence_override(log.id, seed_users["admin"].id, "VERIFIED_DENIED", db)

    db.refresh(entry)
    assert entry.operational_state == DynamicState.ON_LEAVE
