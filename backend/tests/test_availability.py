# Copyright 2026 Chronos Ledger Contributors
# Licensed under the Apache License, Version 2.0
"""Reading a resource's calendar, and filling in what a CSV never knew.

Availability is the question an outside system asks first: is this room free
on the eleventh. Answering it from the daily ledger would have answered "yes"
for every date past tomorrow, because tomorrow is as far as the ledger is
ever generated. So it is answered by expanding the weekly slots instead, and
these tests pin the expansion, the range limits, and the one thing the
expansion has to agree with: which cycles count.
"""

import datetime

from app.models.db import Activity, PlanningCycle, Resource, ResourceType, StructuralMasterSlot
from tests.conftest import ADMIN_PASSWORD, MEMBER_PASSWORD, login

# Explicit dates, never "today plus one": a weekday computed from the day the
# suite happens to run is a test that only tests something two days in seven.
MONDAY = datetime.date(2026, 1, 5)
TUESDAY = datetime.date(2026, 1, 6)
WEDNESDAY = datetime.date(2026, 1, 7)
SUNDAY = datetime.date(2026, 1, 11)


def _room(db, code="LH-201", resource_type=ResourceType.ROOM, **extra):
    room = Resource(code=code, label=code, resource_type=resource_type, **extra)
    db.add(room)
    db.flush()
    return room


def _cycle(db, open_=True, start=datetime.date(2026, 1, 1), end=datetime.date(2026, 6, 30)):
    cycle = PlanningCycle(
        cycle_label="Cycle",
        date_bounds_start=start,
        date_bounds_end=end,
        operational_status=open_,
    )
    db.add(cycle)
    db.flush()
    return cycle


def _slot(db, room, cycle, code="CS101", day=1, start="09:00", end="10:00"):
    activity = Activity(
        activity_code=code,
        activity_title="Something",
        unit_code="CSE",
        cycle_id=cycle.id,
    )
    db.add(activity)
    db.flush()
    slot = StructuralMasterSlot(
        day_of_week_index=day,
        time_window_start=datetime.time.fromisoformat(start),
        time_window_end=datetime.time.fromisoformat(end),
        activity_id=activity.id,
        resource_id=room.id,
        target_room_identifier=room.code,
    )
    db.add(slot)
    db.commit()
    return slot


def _availability(client, headers, resource_id, from_=MONDAY, to=SUNDAY):
    return client.get(
        f"/api/v1/resources/{resource_id}/availability",
        params={"from": str(from_), "to": str(to)},
        headers=headers,
    )


# -- Expansion ----------------------------------------------------------------


def test_a_weekly_slot_lands_on_the_one_matching_day(client, db, seed_users):
    room = _room(db)
    slot = _slot(db, room, _cycle(db))
    headers = login(client, "admin@test.internal", ADMIN_PASSWORD)

    body = _availability(client, headers, room.id).json()
    assert body["from"] == "2026-01-05"
    assert body["to"] == "2026-01-11"
    assert body["busy"] == [
        {
            "date": "2026-01-05",
            "start": "09:00:00",
            "end_date": "2026-01-05",
            "end": "10:00:00",
            "activity_id": slot.activity_id,
            "activity_code": "CS101",
            "master_slot_id": slot.id,
            # A slot carries no reservation, and a reservation carries no
            # activity. Which kind an interval is can be read off the fields
            # that are filled in.
            "reservation_id": None,
        }
    ]


def test_a_slot_the_day_before_the_range_is_not_reported(client, db, seed_users):
    """The expansion starts a day early and then has to throw that day away.

    Monday is walked so that a Monday night shift can be found, and a Monday
    nine to ten has to be dropped again on the way out. Without the drop a
    caller asking about Tuesday alone is told the room is busy on Monday, and
    every range in the system reads one day wider than it was asked for.
    """
    room = _room(db)
    _slot(db, room, _cycle(db), day=1, start="09:00", end="10:00")
    headers = login(client, "admin@test.internal", ADMIN_PASSWORD)

    body = _availability(client, headers, room.id, from_=TUESDAY, to=TUESDAY).json()
    assert body["busy"] == []


def test_a_night_slot_is_reported_on_the_morning_it_runs_into(client, db, seed_users):
    """The reason the expansion starts a day early at all.

    A Monday shift from 22:00 to 06:00 is on Tuesday's calendar, and its date
    is the Monday it opened on. A caller asking about Tuesday alone gets an
    interval dated the day before, which is why the response documents both
    dates: filing this under date and ignoring end_date puts a night shift on
    a day nobody asked about, and dropping it as out of range shows a staffed
    ward as free until six.
    """
    room = _room(db)
    slot = _slot(db, room, _cycle(db), day=1, start="22:00", end="06:00")
    headers = login(client, "admin@test.internal", ADMIN_PASSWORD)

    body = _availability(client, headers, room.id, from_=TUESDAY, to=TUESDAY).json()
    assert body["busy"] == [
        {
            "date": "2026-01-05",
            "start": "22:00:00",
            "end_date": "2026-01-06",
            "end": "06:00:00",
            "activity_id": slot.activity_id,
            "activity_code": "CS101",
            "master_slot_id": slot.id,
            "reservation_id": None,
        }
    ]


def test_a_night_slot_is_not_reported_two_days_on(client, db, seed_users):
    """It reaches into Tuesday morning and stops there. A caller asking about
    Wednesday hears nothing, which a range widened by a whole day rather than
    by the hours the window covers would get wrong."""
    room = _room(db)
    _slot(db, room, _cycle(db), day=1, start="22:00", end="06:00")
    headers = login(client, "admin@test.internal", ADMIN_PASSWORD)

    body = _availability(client, headers, room.id, from_=WEDNESDAY, to=WEDNESDAY).json()
    assert body["busy"] == []


def test_a_longer_range_repeats_the_slot_every_week(client, db, seed_users):
    room = _room(db)
    _slot(db, room, _cycle(db))
    headers = login(client, "admin@test.internal", ADMIN_PASSWORD)

    body = _availability(client, headers, room.id, to=datetime.date(2026, 1, 25)).json()
    assert [e["date"] for e in body["busy"]] == [
        "2026-01-05",
        "2026-01-12",
        "2026-01-19",
    ]


def test_two_slots_on_one_day_come_back_in_time_order(client, db, seed_users):
    room = _room(db)
    cycle = _cycle(db)
    _slot(db, room, cycle, code="PM", start="14:00", end="15:00")
    _slot(db, room, cycle, code="AM", start="09:00", end="10:00")
    headers = login(client, "admin@test.internal", ADMIN_PASSWORD)

    busy = _availability(client, headers, room.id).json()["busy"]
    assert [e["activity_code"] for e in busy] == ["AM", "PM"]


def test_another_room_slot_does_not_show_on_this_room(client, db, seed_users):
    room = _room(db)
    other = _room(db, code="LH-305")
    cycle = _cycle(db)
    _slot(db, other, cycle)
    headers = login(client, "admin@test.internal", ADMIN_PASSWORD)

    assert _availability(client, headers, room.id).json()["busy"] == []


def test_a_closed_cycle_does_not_occupy_the_room(client, db, seed_users):
    room = _room(db)
    _slot(db, room, _cycle(db, open_=False))
    headers = login(client, "admin@test.internal", ADMIN_PASSWORD)

    assert _availability(client, headers, room.id).json()["busy"] == []


def test_availability_counts_cycles_the_way_generation_does(client, db, seed_users):
    """The gate is the open flag, and only the open flag.

    generate_daily_ledger_entries books a day whenever the cycle is flagged
    open; it never looks at date_bounds_start or date_bounds_end. So neither
    does this. Reading the bounds here would report a room free on a date the
    nightly job is going to fill, and two systems would book it.

    If the generator ever starts honouring bounds, the second half of this
    fails on purpose, so availability moves with it rather than drifting.
    """
    room = _room(db)
    open_cycle = _cycle(db, start=datetime.date(2026, 1, 1), end=datetime.date(2026, 6, 30))
    _slot(db, room, open_cycle, code="OPEN")
    _slot(db, room, _cycle(db, open_=False), code="CLOSED")
    headers = login(client, "admin@test.internal", ADMIN_PASSWORD)

    inside = _availability(client, headers, room.id).json()["busy"]
    assert [e["activity_code"] for e in inside] == ["OPEN"]

    # December is six months past this cycle's declared end date.
    past_the_end = _availability(
        client,
        headers,
        room.id,
        from_=datetime.date(2026, 12, 7),
        to=datetime.date(2026, 12, 13),
    ).json()["busy"]
    assert [e["activity_code"] for e in past_the_end] == ["OPEN"]


def test_a_retired_room_still_answers(client, db, seed_users):
    """Retiring a room does not clear its calendar, and should not look like it."""
    room = _room(db, active=False)
    _slot(db, room, _cycle(db))
    headers = login(client, "admin@test.internal", ADMIN_PASSWORD)

    res = _availability(client, headers, room.id)
    assert res.status_code == 200
    assert len(res.json()["busy"]) == 1


def test_a_member_can_read_availability(client, db, seed_users):
    room = _room(db)
    _slot(db, room, _cycle(db))
    headers = login(client, "member@test.internal", MEMBER_PASSWORD)

    assert _availability(client, headers, room.id).status_code == 200


# -- Range limits -------------------------------------------------------------


def test_a_backwards_range_is_refused(client, db, seed_users):
    room = _room(db)
    headers = login(client, "admin@test.internal", ADMIN_PASSWORD)

    res = _availability(client, headers, room.id, from_=SUNDAY, to=MONDAY)
    assert res.status_code == 422
    assert res.json()["detail"] == "from must not be after to"


def test_a_range_longer_than_a_year_and_a_day_is_refused(client, db, seed_users):
    room = _room(db)
    headers = login(client, "admin@test.internal", ADMIN_PASSWORD)

    # 366 days inclusive is the last accepted range; 367 is the first refused.
    ok = _availability(client, headers, room.id, to=MONDAY + datetime.timedelta(days=365))
    assert ok.status_code == 200

    res = _availability(client, headers, room.id, to=MONDAY + datetime.timedelta(days=366))
    assert res.status_code == 422
    assert res.json()["detail"] == "the range must not exceed 366 days"


def test_availability_of_a_room_that_is_not_there_is_404(client, db, seed_users):
    headers = login(client, "admin@test.internal", ADMIN_PASSWORD)
    assert _availability(client, headers, 9999).status_code == 404


# -- Listing ------------------------------------------------------------------


def test_the_list_can_be_narrowed(client, db, seed_users):
    _room(db, code="LH-201")
    _room(db, code="LH-305", active=False)
    _room(db, code="FAC001-PERSON", resource_type=ResourceType.PERSON, user_id="FAC001")
    db.commit()
    headers = login(client, "admin@test.internal", ADMIN_PASSWORD)

    def codes(**params):
        return [
            r["code"]
            for r in client.get("/api/v1/resources/", params=params, headers=headers).json()
        ]

    assert codes() == ["FAC001-PERSON", "LH-201", "LH-305"]
    assert codes(resource_type="ROOM") == ["LH-201", "LH-305"]
    assert codes(active=True) == ["FAC001-PERSON", "LH-201"]
    assert codes(code="LH-305") == ["LH-305"]


# -- Filling one in -----------------------------------------------------------


def test_an_admin_can_give_a_room_a_capacity_and_a_place(client, db, seed_users):
    room = _room(db)
    db.commit()
    headers = login(client, "admin@test.internal", ADMIN_PASSWORD)

    res = client.patch(
        f"/api/v1/resources/{room.id}",
        json={
            "label": "Lecture Hall 201",
            "capacity": 90,
            "latitude": 12.9716,
            "longitude": 77.5946,
            "altitude_target": 920.0,
        },
        headers=headers,
    )
    assert res.status_code == 200, res.text
    body = res.json()
    assert body["label"] == "Lecture Hall 201"
    assert body["capacity"] == 90
    assert body["latitude"] == 12.9716
    # The code is the importer's match key, so it is not something this can
    # change: renaming it here would make the next upload create a second row.
    assert body["code"] == "LH-201"


def test_a_field_left_out_is_left_alone(client, db, seed_users):
    room = _room(db, capacity=90)
    db.commit()
    headers = login(client, "admin@test.internal", ADMIN_PASSWORD)

    client.patch(f"/api/v1/resources/{room.id}", json={"label": "Renamed"}, headers=headers)
    db.expire_all()
    assert db.query(Resource).one().capacity == 90


def test_coordinates_can_be_cleared_but_only_together(client, db, seed_users):
    room = _room(db, latitude=12.9716, longitude=77.5946)
    db.commit()
    headers = login(client, "admin@test.internal", ADMIN_PASSWORD)

    half = client.patch(f"/api/v1/resources/{room.id}", json={"latitude": None}, headers=headers)
    assert half.status_code == 422

    both = client.patch(
        f"/api/v1/resources/{room.id}",
        json={"latitude": None, "longitude": None},
        headers=headers,
    )
    assert both.status_code == 200
    assert both.json()["latitude"] is None


def test_a_latitude_off_the_planet_is_refused(client, db, seed_users):
    room = _room(db)
    db.commit()
    headers = login(client, "admin@test.internal", ADMIN_PASSWORD)

    res = client.patch(
        f"/api/v1/resources/{room.id}",
        json={"latitude": 91.0, "longitude": 77.5946},
        headers=headers,
    )
    assert res.status_code == 422


def test_only_an_admin_may_edit_a_resource(client, db, seed_users):
    room = _room(db)
    db.commit()
    headers = login(client, "member@test.internal", MEMBER_PASSWORD)

    res = client.patch(f"/api/v1/resources/{room.id}", json={"capacity": 1}, headers=headers)
    assert res.status_code == 403


def test_editing_a_room_that_is_not_there_is_404(client, db, seed_users):
    headers = login(client, "admin@test.internal", ADMIN_PASSWORD)
    res = client.patch("/api/v1/resources/9999", json={"capacity": 1}, headers=headers)
    assert res.status_code == 404
