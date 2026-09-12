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
    InstitutionalRole,
    PlanningCycle,
    StructuralMasterSlot,
    User,
)
from app.services import location_resolver
from app.services.location_resolver import determine_staff_current_states

MONDAY = datetime.date(2026, 3, 2)
TUESDAY = MONDAY + datetime.timedelta(days=1)

NIGHT = (datetime.time(22, 0), datetime.time(6, 0))
DAY = (datetime.time(9, 0), datetime.time(10, 0))


class NoOverride:
    """A Redis that has never been told anything, so tier 1 always misses."""

    def mget(self, keys):
        return [None] * len(keys)


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


def _slot(
    db, weekday: int, window, room: str = "W-1", lead: str = "FAC001"
) -> StructuralMasterSlot:
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
        primary_lead_id=lead,
        target_room_identifier=room,
    )
    db.add(slot)
    db.commit()
    return slot


def _ledger(db, slot: StructuralMasterSlot, day: datetime.date, state: DynamicState, room: str):
    db.add(
        DailyLedger(
            target_date=day,
            # Copied off the slot, the way the generator copies it.
            time_window_start=slot.time_window_start,
            time_window_end=slot.time_window_end,
            master_slot_id=slot.id,
            activity_id=slot.activity_id,
            active_lead_id=slot.primary_lead_id,
            target_room_identifier=room,
            operational_state=state,
        )
    )
    db.commit()


def _state(db):
    staff = db.query(User).filter(User.id == "FAC001").one()
    return determine_staff_current_states([staff], db, NoOverride())["FAC001"]


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
    assert _state(db)["resolved_location"] == "OFF_SITE"


def test_a_ledger_row_from_a_finished_night_shift_is_not_reported(db, seed_users, at):
    slot = _slot(db, 1, NIGHT)
    _ledger(db, slot, MONDAY, DynamicState.SCHEDULED, "W-9")
    at(TUESDAY, 7, 0)
    assert _state(db)["status"] == "Available / Unassigned"


def test_leave_on_a_class_taken_off_the_timetable_is_still_leave(db, seed_users, at):
    """The tier 2 join used to be an inner one.

    A slot deleted after the day was generated nulls the day's
    master_slot_id, on purpose, so that the attendance marked against it
    survives. The join then dropped the row, tier 2 saw nothing, and somebody
    on approved leave was reported as teaching a class that is no longer on
    the timetable at all. The row's own window is what tier 2 reads now, so
    the deletion changes nothing it needs.
    """
    slot = _slot(db, 1, DAY)
    _ledger(db, slot, MONDAY, DynamicState.ON_LEAVE, "W-9")
    db.query(DailyLedger).update({DailyLedger.master_slot_id: None})
    db.query(StructuralMasterSlot).filter(StructuralMasterSlot.id == slot.id).delete()
    db.commit()

    at(MONDAY, 9, 30)
    assert _state(db)["resolved_location"] == "OFF_SITE"


def test_an_adhoc_day_with_no_window_is_not_reported(db, seed_users, at):
    """A day nobody gave a time to is not a day somebody is on shift for.

    It has to be skipped rather than crash: window_span has two times to work
    with or it has nothing, and a row with none is exactly what an ad-hoc
    entry is before anyone fills the times in.
    """
    slot = _slot(db, 1, DAY)
    _ledger(db, slot, MONDAY, DynamicState.SCHEDULED, "W-9")
    db.query(DailyLedger).update(
        {DailyLedger.time_window_start: None, DailyLedger.time_window_end: None}
    )
    db.commit()

    at(MONDAY, 9, 30)
    # Tier 2 skips it and tier 3 answers off the slot, which still has a window.
    assert _state(db)["resolved_location"] == "W-1"


# -- Several people at once ----------------------------------------------------


class Overrides:
    """A Redis holding a status override for some people and not others."""

    def __init__(self, by_id: dict[str, str]):
        self.by_id = by_id

    def mget(self, keys):
        return [self.by_id.get(key.removeprefix("state_override:")) for key in keys]


def test_everybody_asked_about_at_once_gets_their_own_answer(db, seed_users, at):
    """The locator asks about all staff in one call, and each tier fetches its
    rows for the whole list and hands them back out by lead. Every test above
    has one person in it, so a row handed to the wrong person would pass all
    of them. Here each of five people is answered by a different tier.
    """
    for n, base in ((2, None), (3, None), (4, None), (5, "Desk 5")):
        db.add(
            User(
                id=f"FAC00{n}",
                full_name=f"Staff {n}",
                email_address=f"staff{n}@test.internal",
                credential_secure_hash="never-logs-in",
                role_type=InstitutionalRole.STAFF,
                unit_code="CSE",
                assigned_base_station=base,
            )
        )
    db.commit()

    _ledger(db, _slot(db, 1, DAY), MONDAY, DynamicState.ON_LEAVE, "W-9")
    _ledger(db, _slot(db, 1, DAY, "W-2", "FAC002"), MONDAY, DynamicState.SCHEDULED, "W-8")
    _slot(db, 1, DAY, "W-3", "FAC003")
    _slot(db, 1, DAY, "W-4", "FAC004")
    at(MONDAY, 9, 30)

    staff = db.query(User).filter(User.role_type == InstitutionalRole.STAFF).all()
    states = determine_staff_current_states(staff, db, Overrides({"FAC004": "In a meeting"}))
    assert states == {
        "FAC001": {"resolved_location": "OFF_SITE", "status": "On Approved Leave"},
        "FAC002": {"resolved_location": "W-8", "status": "Leading WARD-A in Room W-8"},
        "FAC003": {"resolved_location": "W-3", "status": "Leading WARD-A in Room W-3"},
        "FAC004": {"resolved_location": "UNKNOWN", "status": "In a meeting"},
        "FAC005": {"resolved_location": "Desk 5", "status": "Available / Unassigned"},
    }
