# Copyright 2026 Chronos Ledger Contributors
# Licensed under the Apache License, Version 2.0
"""Copying a cycle's timetable into the next one.

The clone route copied the activities and nothing else, so the rollover the
deployment guide describes left the new cycle with no slots. It copies the
slots now, into a cycle that has to be closed and empty, and leaves checking
them against the rooms to the open that follows.

Dates are computed from today, for the reason test_cycle_activation gives.
"""

import datetime

from app.core.time import org_today
from app.cron.ledger_generator import generate_daily_ledger_entries
from app.models.db import Activity, ActivityEnrollment, DailyLedger, StructuralMasterSlot
from tests.test_cycle_activation import BLOCKED, _open
from tests.test_slot_editing import _timetable


def _new_cycle(client, headers, starts, ends):
    """A cycle created through the route, which creates it closed."""
    today = org_today()
    r = client.post(
        "/api/v1/schedule/cycles",
        headers=headers,
        json={
            "cycle_label": f"Days {starts} to {ends}",
            "date_bounds_start": str(today + datetime.timedelta(days=starts)),
            "date_bounds_end": str(today + datetime.timedelta(days=ends)),
        },
    )
    assert r.status_code == 200, r.text
    return r.json()["id"]


def _clone(client, headers, old_id, new_id):
    return client.post(f"/api/v1/schedule/cycles/{old_id}/clone-to/{new_id}", headers=headers)


def test_the_slots_come_across_pointed_at_the_copied_activities(client, db, seed_users):
    headers, slot = _timetable(client, db, seed_users)
    new_id = _new_cycle(client, headers, 200, 300)

    r = _clone(client, headers, slot.activity.cycle_id, new_id)
    assert r.status_code == 200, r.text
    assert r.json() == {"cloned": 1, "cloned_slots": 1}

    db.expire_all()
    copy = db.query(Activity).filter(Activity.cycle_id == new_id).one()
    assert (copy.activity_code, copy.activity_title, copy.unit_code) == (
        "MA201",
        "Linear Algebra",
        "CSE",
    )
    copied = (
        db.query(StructuralMasterSlot).filter(StructuralMasterSlot.activity_id == copy.id).one()
    )
    assert copied.id != slot.id
    assert (
        copied.day_of_week_index,
        copied.time_window_start,
        copied.time_window_end,
        copied.primary_lead_id,
        copied.resource_id,
        copied.target_room_identifier,
    ) == (
        slot.day_of_week_index,
        slot.time_window_start,
        slot.time_window_end,
        slot.primary_lead_id,
        slot.resource_id,
        slot.target_room_identifier,
    )
    # The next cycle's groups come from the next import.
    assert (
        db.query(ActivityEnrollment).filter(ActivityEnrollment.activity_id == copy.id).count() == 0
    )


def test_a_clone_into_later_dates_opens_and_runs(client, db, seed_users):
    """The same room at the same hour, in a cycle that starts after this one ends."""
    headers, slot = _timetable(client, db, seed_users)
    new_id = _new_cycle(client, headers, 200, 300)
    assert _clone(client, headers, slot.activity.cycle_id, new_id).status_code == 200

    r = _open(client, headers, new_id)
    assert r.status_code == 200, r.text

    starts = org_today() + datetime.timedelta(days=200)
    first = starts + datetime.timedelta(days=(slot.day_of_week_index - starts.isoweekday()) % 7)
    assert generate_daily_ledger_entries(first, db) == 1
    day = db.query(DailyLedger).filter(DailyLedger.target_date == first).one()
    assert day.activity.cycle_id == new_id


def test_a_clone_over_the_same_dates_is_stopped_at_the_open(client, db, seed_users):
    """The clone does not check the rooms. Opening does, and finds the original."""
    headers, slot = _timetable(client, db, seed_users)
    new_id = _new_cycle(client, headers, 10, 60)
    assert _clone(client, headers, slot.activity.cycle_id, new_id).status_code == 200

    r = _open(client, headers, new_id)
    assert r.status_code == 409, r.text
    body = r.json()["detail"]
    assert body["message"] == BLOCKED
    assert {c["master_slot_id"] for c in body["conflicts"]} == {slot.id}


def test_an_open_cycle_is_not_cloned_into(client, db, seed_users):
    headers, slot = _timetable(client, db, seed_users)
    new_id = _new_cycle(client, headers, 200, 300)
    assert _open(client, headers, new_id).status_code == 200

    r = _clone(client, headers, slot.activity.cycle_id, new_id)
    assert r.status_code == 409, r.text
    assert db.query(Activity).filter(Activity.cycle_id == new_id).count() == 0


def test_a_cycle_that_already_has_activities_is_not_cloned_into(client, db, seed_users):
    headers, slot = _timetable(client, db, seed_users)
    old_id = slot.activity.cycle_id
    new_id = _new_cycle(client, headers, 200, 300)
    assert _clone(client, headers, old_id, new_id).status_code == 200

    r = _clone(client, headers, old_id, new_id)
    assert r.status_code == 409, r.text
    assert db.query(Activity).filter(Activity.cycle_id == new_id).count() == 1
    assert db.query(StructuralMasterSlot).count() == 2


def test_a_cycle_that_does_not_exist_is_a_404(client, db, seed_users):
    headers, slot = _timetable(client, db, seed_users)
    old_id = slot.activity.cycle_id

    assert _clone(client, headers, old_id, 9999).status_code == 404
    assert _clone(client, headers, 9999, old_id).status_code == 404
