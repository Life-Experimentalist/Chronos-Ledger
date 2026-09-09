# Copyright 2026 Chronos Ledger Contributors
# Licensed under the Apache License, Version 2.0

"""Where a staff member is right now, when the shift they are on runs past midnight.

This resolver is the one place in the system where getting a window wrong
shows up as a wrong answer rather than a refused request. A booking that is
compared badly gets a 409 somebody can argue with; a night nurse who reads as
"Available / Unassigned" at two in the morning is simply lost, and the
dashboard looks like it is working.

The dates here are fixed rather than relative to today, because a resolver
that reads a weekday cannot be tested by a suite that runs on whichever
weekday it happens to be run.
"""

import datetime

import pytest

from app.core.time import org_timezone
from app.models.db import (
    Activity,
    DailyLedger,
    DynamicState,
    PlanningCycle,
    StructuralMasterSlot,
)
from app.services import location_resolver
from app.services.location_resolver import determine_staff_current_state

MONDAY = datetime.date(2026, 3, 2)
TUESDAY = MONDAY + datetime.timedelta(days=1)

NIGHT = (datetime.time(22, 0), datetime.time(6, 0))
DAY = (datetime.time(9, 0), datetime.time(10, 0))


class NoOverride:
    """A Redis that has never been told anything, so tier 1 always misses."""

    def get(self, key):
        return None


@pytest.fixture()
def at(monkeypatch):
    """Stand the resolver at a named instant.

    Aware, because org_now() is aware and the slot's own times are not. That
    difference is the whole reason this fixture builds a real zoned datetime
    instead of a bare one: comparing an aware now against a naive window
    raises rather than quietly answering, and a test that hands over
    something naive would never find out.
    """

    def stand_at(day: datetime.date, hour: int, minute: int = 0, second: int = 0):
        frozen = datetime.datetime.combine(
            day, datetime.time(hour, minute, second), tzinfo=org_timezone()
        )
        monkeypatch.setattr(location_resolver, "org_now", lambda: frozen)

    return stand_at


def _slot(db, weekday: int, window, room: str = "W-1") -> StructuralMasterSlot:
    cycle = db.query(PlanningCycle).first()
    if cycle is None:
        cycle = PlanningCycle(
            cycle_label="Wards 2026",
            date_bounds_start=MONDAY - datetime.timedelta(days=30),
            date_bounds_end=MONDAY + datetime.timedelta(days=300),
            operational_status=True,
        )
        db.add(cycle)
        db.flush()
    activity = db.query(Activity).first()
    if activity is None:
        activity = Activity(
            activity_code="WARD-A",
            activity_title="Ward A rounds",
            unit_code="CSE",
            cycle_id=cycle.id,
        )
        db.add(activity)
        db.flush()
    start, end = window
    slot = StructuralMasterSlot(
        day_of_week_index=weekday,
        time_window_start=start,
        time_window_end=end,
        activity_id=activity.id,
        primary_lead_id="FAC001",
        target_room_identifier=room,
    )
    db.add(slot)
    db.commit()
    return slot


def _ledger(db, slot: StructuralMasterSlot, day: datetime.date, state: DynamicState, room: str):
    db.add(
        DailyLedger(
            target_date=day,
            master_slot_id=slot.id,
            activity_id=slot.activity_id,
            active_lead_id="FAC001",
            target_room_identifier=room,
            operational_state=state,
        )
    )
    db.commit()


def _state(db):
    return determine_staff_current_state("FAC001", db, NoOverride())


def test_the_dates_here_are_the_weekdays_they_claim():
    """The premise the rest of the file rests on. If this fails the others
    have stopped proving anything about weekdays."""
    assert MONDAY.isoweekday() == 1
    assert TUESDAY.isoweekday() == 2


# -- Within a day, which is what worked before ---------------------------------


def test_a_day_shift_is_found_while_it_runs(db, seed_users, at):
    _slot(db, 1, DAY)
    at(MONDAY, 9, 30)
    assert _state(db)["resolved_location"] == "W-1"


def test_a_shift_is_on_at_the_instant_it_starts(db, seed_users, at):
    """The lower bound is inclusive. Nine o'clock is the first minute of a
    nine o'clock shift, not the last minute before it."""
    _slot(db, 1, DAY)
    at(MONDAY, 9, 0, 0)
    assert _state(db)["resolved_location"] == "W-1"


def test_a_shift_is_over_at_the_instant_it_ends(db, seed_users, at):
    """The upper bound is exclusive, which it was not before this. A closed
    bound puts somebody in two rooms at once wherever two shifts meet, and
    which of the two the dashboard shows is decided by whatever order the
    database happened to return them in.
    """
    _slot(db, 1, DAY)
    at(MONDAY, 10, 0, 0)
    assert _state(db)["status"] == "Available / Unassigned"


def test_nothing_scheduled_reads_as_unassigned(db, seed_users, at):
    at(MONDAY, 9, 30)
    assert _state(db)["status"] == "Available / Unassigned"


# -- Past midnight -------------------------------------------------------------


def test_a_night_shift_is_found_before_midnight(db, seed_users, at):
    _slot(db, 1, NIGHT)
    at(MONDAY, 23, 0)
    assert _state(db)["resolved_location"] == "W-1"


def test_a_night_shift_is_found_after_midnight(db, seed_users, at):
    """The defect this file was written for. A Monday shift running 22:00 to
    06:00 is still on at two on Tuesday morning, and the weekday to look for
    is Monday's, not the one the clock is currently showing."""
    _slot(db, 1, NIGHT)
    at(TUESDAY, 2, 0)
    assert _state(db)["resolved_location"] == "W-1"


def test_a_night_shift_is_over_once_the_morning_arrives(db, seed_users, at):
    _slot(db, 1, NIGHT)
    at(TUESDAY, 6, 0, 0)
    assert _state(db)["status"] == "Available / Unassigned"


def test_yesterdays_day_shift_does_not_leak_into_today(db, seed_users, at):
    """Yesterday's weekday is fetched now, so it has to be filtered by the
    hours it actually covers and not by having been fetched. A Monday shift
    from nine to ten is nothing to do with Tuesday at half past nine."""
    _slot(db, 1, DAY)
    at(TUESDAY, 9, 30)
    assert _state(db)["status"] == "Available / Unassigned"


# -- The daily ledger, which is consulted first --------------------------------


def test_a_night_shift_on_the_ledger_is_found_after_midnight(db, seed_users, at):
    """The ledger row is dated the day the shift opened on, the same as the
    slot's weekday is. Its room is different from the slot's here so that the
    answer says which tier produced it."""
    slot = _slot(db, 1, NIGHT)
    _ledger(db, slot, MONDAY, DynamicState.SCHEDULED, "W-9")
    at(TUESDAY, 2, 0)
    assert _state(db)["resolved_location"] == "W-9"


def test_leave_on_a_night_shift_is_still_leave_after_midnight(db, seed_users, at):
    """Falling through to the timetable here would report somebody on
    approved leave as being at work."""
    slot = _slot(db, 1, NIGHT)
    _ledger(db, slot, MONDAY, DynamicState.ON_LEAVE, "W-9")
    at(TUESDAY, 2, 0)
    assert _state(db)["resolved_location"] == "OFF_CAMPUS"


def test_a_ledger_row_from_a_finished_night_shift_is_not_reported(db, seed_users, at):
    slot = _slot(db, 1, NIGHT)
    _ledger(db, slot, MONDAY, DynamicState.SCHEDULED, "W-9")
    at(TUESDAY, 7, 0)
    assert _state(db)["status"] == "Available / Unassigned"
