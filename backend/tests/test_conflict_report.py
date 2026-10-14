# Copyright 2026 Chronos Ledger Contributors
# Licensed under the Apache License, Version 2.0
"""The conflict report: clashes already in the schedule, read and not refused.

Every row is written straight into the database, because the write paths
would refuse most of these clashes and the report exists for the ones that
got in anyway. Each test seeds one kind of clash on rooms of its own, so a
clash of one kind cannot be mistaken for another.

The window is the seven days from tomorrow, so every weekday appears in it
exactly once and a weekly slot clashes on exactly one date.
"""

import datetime

from app.core.time import org_today
from app.models.db import (
    Activity,
    ActivityEnrollment,
    DailyLedger,
    PlanningCycle,
    Reservation,
    ReservationStatus,
    Resource,
    ResourceType,
    StructuralMasterSlot,
)
from tests.conftest import ADMIN_PASSWORD, MEMBER_PASSWORD, STAFF_PASSWORD, login, weekly

TOMORROW = org_today() + datetime.timedelta(days=1)
LAST = TOMORROW + datetime.timedelta(days=6)

URL = "/api/v1/schedule/conflicts"


def _room(db, code):
    room = Resource(code=code, label=code, resource_type=ResourceType.ROOM)
    db.add(room)
    db.commit()
    return room


def _activity(db, code):
    cycle = PlanningCycle(
        cycle_label=f"Cycle {code}",
        date_bounds_start=org_today() - datetime.timedelta(days=30),
        date_bounds_end=org_today() + datetime.timedelta(days=300),
        operational_status=True,
    )
    db.add(cycle)
    db.flush()
    activity = Activity(activity_code=code, activity_title=code, unit_code="CSE", cycle_id=cycle.id)
    db.add(activity)
    db.commit()
    return activity


def _slot(db, activity, room, start, end):
    slot = StructuralMasterSlot(
        **weekly(TOMORROW.isoweekday()),
        time_window_start=start,
        time_window_end=end,
        activity_id=activity.id,
        resource_id=room.id,
    )
    db.add(slot)
    db.commit()
    return slot


def _day(db, activity, room, start, end, slot=None):
    day = DailyLedger(
        target_date=TOMORROW,
        time_window_start=start,
        time_window_end=end,
        master_slot_id=slot.id if slot else None,
        activity_id=activity.id,
        resource_id=room.id,
    )
    db.add(day)
    db.commit()
    return day


def _hold(db, room, start, end, key, status=ReservationStatus.HELD):
    hold = Reservation(
        resource_id=room.id,
        reserved_date=TOMORROW,
        time_window_start=start,
        time_window_end=end,
        purpose="Written straight in",
        requested_by_id="ADM001",
        idempotency_key=key,
        request_fingerprint="x" * 64,
        status=status,
    )
    db.add(hold)
    db.commit()
    return hold


def _t(hour, minute=0):
    return datetime.time(hour, minute)


def _admin(client):
    return login(client, "admin@test.internal", ADMIN_PASSWORD)


def _report(client, headers, start=TOMORROW, end=LAST):
    r = client.get(URL, params={"from": str(start), "to": str(end)}, headers=headers)
    assert r.status_code == 200, r.text
    return r.json()["conflicts"]


def _pairs(conflicts, kind):
    return [
        {(item["type"], item["id"]) for item in conflict["items"]}
        for conflict in conflicts
        if conflict["kind"] == kind
    ]


# ── One of each kind, once ───────────────────────────────────────────────────


def test_two_slots_on_one_room_clash_once(client, db, seed_users):
    room = _room(db, "LH-101")
    first = _slot(db, _activity(db, "CS101"), room, _t(9), _t(10))
    second = _slot(db, _activity(db, "CS102"), room, _t(9, 30), _t(10, 30))

    conflicts = _report(client, _admin(client))

    assert _pairs(conflicts, "resource_overlap") == [{("slot", first.id), ("slot", second.id)}]
    assert _pairs(conflicts, "member_overlap") == []
    (clash,) = conflicts
    assert clash["resource_id"] == room.id
    assert clash["member_id"] is None
    assert clash["date"] == str(TOMORROW)
    # The part the two windows share.
    assert (clash["start"], clash["end"]) == ("09:30:00", "10:00:00")
    assert [item["type"] for item in clash["items"]] == ["slot", "slot"]


def test_a_slot_and_a_held_booking_clash_once(client, db, seed_users):
    room = _room(db, "LH-102")
    slot = _slot(db, _activity(db, "CS103"), room, _t(9), _t(10))
    hold = _hold(db, room, _t(9, 30), _t(11), "conflict-hold-0001")
    # A cancelled booking holds nothing.
    _hold(db, room, _t(9), _t(10), "conflict-hold-0002", status=ReservationStatus.CANCELLED)

    conflicts = _report(client, _admin(client))

    assert _pairs(conflicts, "resource_overlap") == [{("slot", slot.id), ("reservation", hold.id)}]
    assert len(conflicts) == 1


def test_two_generated_days_on_one_room_clash_once(client, db, seed_users):
    room = _room(db, "LH-103")
    first = _day(db, _activity(db, "CS104"), room, _t(14), _t(16))
    second = _day(db, _activity(db, "CS105"), room, _t(15), _t(17))

    conflicts = _report(client, _admin(client))

    assert _pairs(conflicts, "resource_overlap") == [
        {("ledger_day", first.id), ("ledger_day", second.id)}
    ]
    assert len(conflicts) == 1


def test_a_member_in_two_activities_at_once_clashes_once(client, db, seed_users):
    maths = _activity(db, "MA101")
    physics = _activity(db, "PH101")
    first = _slot(db, maths, _room(db, "LH-104"), _t(9), _t(10))
    second = _slot(db, physics, _room(db, "LH-105"), _t(9, 30), _t(10, 30))
    db.add_all(
        [
            ActivityEnrollment(activity_id=maths.id, member_id="STU001"),
            ActivityEnrollment(activity_id=physics.id, member_id="STU001"),
        ]
    )
    db.commit()

    conflicts = _report(client, _admin(client))

    assert _pairs(conflicts, "member_overlap") == [{("slot", first.id), ("slot", second.id)}]
    assert _pairs(conflicts, "resource_overlap") == []
    (clash,) = conflicts
    assert clash["member_id"] == "STU001"
    assert clash["resource_id"] is None


# ── What is not a clash ──────────────────────────────────────────────────────


def test_back_to_back_windows_do_not_clash(client, db, seed_users):
    room = _room(db, "LH-106")
    maths = _activity(db, "MA102")
    physics = _activity(db, "PH102")
    _slot(db, maths, room, _t(9), _t(10))
    _slot(db, physics, room, _t(10), _t(11))
    _hold(db, room, _t(11), _t(12), "conflict-hold-0003")
    db.add_all(
        [
            ActivityEnrollment(activity_id=maths.id, member_id="STU001"),
            ActivityEnrollment(activity_id=physics.id, member_id="STU001"),
        ]
    )
    db.commit()

    assert _report(client, _admin(client)) == []


def test_a_slot_and_its_own_generated_day_are_one_class(client, db, seed_users):
    room = _room(db, "LH-107")
    activity = _activity(db, "CS106")
    slot = _slot(db, activity, room, _t(9), _t(10))
    _day(db, activity, room, _t(9), _t(10), slot=slot)

    assert _report(client, _admin(client)) == []


# ── The window ───────────────────────────────────────────────────────────────


def test_a_backwards_window_is_refused(client, seed_users):
    r = client.get(URL, params={"from": str(LAST), "to": str(TOMORROW)}, headers=_admin(client))
    assert r.status_code == 422
    assert r.json()["code"] == "INVALID_VALUE"


def test_one_day_is_a_window(client, seed_users):
    assert _report(client, _admin(client), TOMORROW, TOMORROW) == []


def test_the_window_is_capped_at_92_days(client, seed_users):
    headers = _admin(client)
    assert _report(client, headers, TOMORROW, TOMORROW + datetime.timedelta(days=91)) == []

    r = client.get(
        URL,
        params={"from": str(TOMORROW), "to": str(TOMORROW + datetime.timedelta(days=92))},
        headers=headers,
    )
    assert r.status_code == 422
    assert r.json()["code"] == "INVALID_VALUE"


# ── Who may read it ──────────────────────────────────────────────────────────


def test_needs_a_login(client, seed_users):
    r = client.get(URL, params={"from": str(TOMORROW), "to": str(LAST)})
    assert r.status_code == 401


def test_staff_and_members_may_not_read_it(client, seed_users):
    for email, password in (
        ("staff@test.internal", STAFF_PASSWORD),
        ("member@test.internal", MEMBER_PASSWORD),
    ):
        r = client.get(
            URL,
            params={"from": str(TOMORROW), "to": str(LAST)},
            headers=login(client, email, password),
        )
        assert r.status_code == 403, email
