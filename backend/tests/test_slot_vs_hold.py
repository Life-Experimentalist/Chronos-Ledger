# Copyright 2026 Chronos Ledger Contributors
# Licensed under the Apache License, Version 2.0
"""Putting a class where something has already booked the room.

Chronos refused a booking that clashed with a class and accepted a class
that clashed with a booking, so the rule only ran one way and the timetable
was the way around it. An outside system holding a room could have it taken
back without being told, which is the one thing a booking authority cannot
do. Every way a slot reaches the database is pinned here: the two verbs that
write one, and the CSV upload that writes them in bulk.

Dates are computed rather than written down. The check counts holds from
today forward only, so a date typed into this file would eventually fall
into the past and every test here would start passing for the wrong reason.
"""

import datetime

from app.cron.ledger_generator import generate_daily_ledger_entries
from app.models.db import (
    Activity,
    DailyLedger,
    PlanningCycle,
    Reservation,
    ReservationStatus,
    Resource,
    ResourceType,
    StructuralMasterSlot,
)
from tests.conftest import ADMIN_PASSWORD, login
from tests.test_import_corrections import TOMORROW, _csv, _row
from tests.test_ingestion import _make_cycle, _upload

# The class sits on tomorrow's weekday, which is what _row imports onto too.
NEXT_WEEK = datetime.date.today() + datetime.timedelta(days=7)
A_WEEK_AGO = TOMORROW - datetime.timedelta(days=7)

HELD = "the resource is held for part of that window"


def _room(db, code="LH-201"):
    room = Resource(code=code, label=code, resource_type=ResourceType.ROOM)
    db.add(room)
    db.commit()
    return room


def _activity(db, is_open=True, code="CS101"):
    cycle = PlanningCycle(
        cycle_label="Cycle",
        date_bounds_start=datetime.date.today() - datetime.timedelta(days=30),
        date_bounds_end=datetime.date.today() + datetime.timedelta(days=300),
        operational_status=is_open,
    )
    db.add(cycle)
    db.flush()
    activity = Activity(
        activity_code=code,
        activity_title="Something",
        unit_code="CSE",
        cycle_id=cycle.id,
    )
    db.add(activity)
    db.commit()
    return activity


def _hold(client, headers, resource_id, on, start="09:00", end="10:00", key="hold-0000-0001"):
    r = client.post(
        f"/api/v1/resources/{resource_id}/reservations",
        json={"date": str(on), "start": start, "end": end, "purpose": "Ward round"},
        headers={**headers, "Idempotency-Key": key},
    )
    assert r.status_code == 201, r.text
    return r.json()


def _new_slot(client, headers, activity_id, room="LH-201", day=None, start="09:00", end="10:00"):
    return client.post(
        "/api/v1/schedule/slots",
        headers=headers,
        json={
            "day_of_week_index": TOMORROW.isoweekday() if day is None else day,
            "time_window_start": start,
            "time_window_end": end,
            "activity_id": activity_id,
            "primary_lead_id": "FAC001",
            "target_room_identifier": room,
        },
    )


# ── Creating a slot ──────────────────────────────────────────────────────────


def test_a_class_is_refused_where_the_room_is_already_held(client, db, seed_users):
    headers = login(client, "admin@test.internal", ADMIN_PASSWORD)
    room = _room(db)
    activity = _activity(db)
    booking = _hold(client, headers, room.id, TOMORROW)

    r = _new_slot(client, headers, activity.id)
    assert r.status_code == 409, r.text

    body = r.json()["detail"]
    assert body["message"] == HELD
    # The same shape a refused booking sends back, so an integrator reads a
    # clash the same way whichever end it came from.
    assert [c["reservation_id"] for c in body["conflicts"]] == [booking["id"]]
    assert body["conflicts"][0]["date"] == str(TOMORROW)
    assert body["conflicts"][0]["start"] == "09:00:00"
    assert db.query(StructuralMasterSlot).count() == 0


def test_a_class_back_to_back_with_a_hold_is_allowed(client, db, seed_users):
    """Half open, the same as everywhere else. A room that cannot be used at
    ten because something ended at ten is a room nobody can schedule."""
    headers = login(client, "admin@test.internal", ADMIN_PASSWORD)
    room = _room(db)
    activity = _activity(db)
    _hold(client, headers, room.id, TOMORROW, start="08:00", end="09:00")

    r = _new_slot(client, headers, activity.id)
    assert r.status_code == 200, r.text


def test_a_hold_on_another_weekday_is_not_in_the_way(client, db, seed_users):
    headers = login(client, "admin@test.internal", ADMIN_PASSWORD)
    room = _room(db)
    activity = _activity(db)
    _hold(client, headers, room.id, NEXT_WEEK)

    r = _new_slot(client, headers, activity.id)
    assert r.status_code == 200, r.text


def test_a_cancelled_hold_is_not_in_the_way(client, db, seed_users):
    headers = login(client, "admin@test.internal", ADMIN_PASSWORD)
    room = _room(db)
    activity = _activity(db)
    booking = _hold(client, headers, room.id, TOMORROW)

    gone = client.delete(
        f"/api/v1/resources/{room.id}/reservations/{booking['id']}", headers=headers
    )
    assert gone.status_code == 200, gone.text

    r = _new_slot(client, headers, activity.id)
    assert r.status_code == 200, r.text


def test_a_hold_that_has_already_passed_is_not_in_the_way(client, db, seed_users):
    """A slot lays down days from now onwards and never backwards, so a room
    held one Tuesday that has been and gone cannot be sat on by a class
    created today. Counting those would make a weekday unusable for good."""
    headers = login(client, "admin@test.internal", ADMIN_PASSWORD)
    room = _room(db)
    activity = _activity(db)
    _hold(client, headers, room.id, A_WEEK_AGO)

    r = _new_slot(client, headers, activity.id)
    assert r.status_code == 200, r.text


def test_a_closed_cycle_is_not_checked(client, db, seed_users):
    """A slot in a closed cycle does not occupy the room: availability counts
    open cycles only, and a booking is already accepted on top of one.
    Refusing here would make the two directions disagree the other way."""
    headers = login(client, "admin@test.internal", ADMIN_PASSWORD)
    room = _room(db)
    activity = _activity(db, is_open=False)
    _hold(client, headers, room.id, TOMORROW)

    r = _new_slot(client, headers, activity.id)
    assert r.status_code == 200, r.text


# ── Moving a slot ────────────────────────────────────────────────────────────


def test_a_class_cannot_be_moved_into_a_held_room(client, db, seed_users):
    headers = login(client, "admin@test.internal", ADMIN_PASSWORD)
    _room(db)
    theatre = _room(db, code="LH-999")
    activity = _activity(db)
    slot_id = _new_slot(client, headers, activity.id).json()["id"]
    _hold(client, headers, theatre.id, TOMORROW)

    r = client.patch(
        f"/api/v1/schedule/slots/{slot_id}",
        headers=headers,
        json={"target_room_identifier": "LH-999"},
    )
    assert r.status_code == 409, r.text
    assert r.json()["detail"]["message"] == HELD

    db.expire_all()
    slot = db.query(StructuralMasterSlot).one()
    assert slot.target_room_identifier == "LH-201"


def test_a_refused_move_leaves_the_slot_and_the_days_it_made_alone(client, db, seed_users):
    """Moving a weekday withdraws the days already generated, and that runs
    after the check rather than before it, so a refusal costs the timetable
    nothing."""
    headers = login(client, "admin@test.internal", ADMIN_PASSWORD)
    room = _room(db)
    activity = _activity(db)
    slot_id = _new_slot(client, headers, activity.id).json()["id"]
    assert generate_daily_ledger_entries(TOMORROW, db) == 1
    _hold(client, headers, room.id, NEXT_WEEK)

    r = client.patch(
        f"/api/v1/schedule/slots/{slot_id}",
        headers=headers,
        json={"day_of_week_index": NEXT_WEEK.isoweekday()},
    )
    assert r.status_code == 409, r.text

    db.expire_all()
    slot = db.query(StructuralMasterSlot).one()
    assert slot.day_of_week_index == TOMORROW.isoweekday()
    assert db.query(DailyLedger).count() == 1


# ── Uploading a timetable ────────────────────────────────────────────────────


def test_an_upload_is_refused_when_the_room_it_names_is_held(client, db, seed_users):
    """The whole file, not the row. Every other bad row in an import aborts
    the upload, and a CSV that half applied would leave an admin diffing the
    file against the database to find out what landed."""
    headers = login(client, "admin@test.internal", ADMIN_PASSWORD)
    cycle = _make_cycle(db)
    room = _room(db)
    _hold(client, headers, room.id, TOMORROW)

    r = _upload(client, headers, cycle.id, _csv(_row()))
    assert r.status_code == 422, r.text
    # Which room, and which hold. An admin fixing a timetable needs to know
    # what it collided with, not that something did.
    assert "LH-201" in r.json()["detail"]
    assert str(TOMORROW) in r.json()["detail"]
    assert db.query(StructuralMasterSlot).count() == 0


def test_moving_a_class_by_re_upload_is_refused_the_same_way(client, db, seed_users):
    headers = login(client, "admin@test.internal", ADMIN_PASSWORD)
    cycle = _make_cycle(db)
    assert _upload(client, headers, cycle.id, _csv(_row())).status_code == 200
    theatre = _room(db, code="LH-999")
    _hold(client, headers, theatre.id, TOMORROW)

    r = _upload(client, headers, cycle.id, _csv(_row(room="LH-999")))
    assert r.status_code == 422, r.text
    assert "LH-999" in r.json()["detail"]

    db.expire_all()
    assert db.query(StructuralMasterSlot).one().target_room_identifier == "LH-201"


def test_a_re_upload_that_changes_nothing_is_not_refused_by_a_hold(client, db, seed_users):
    """The check runs only when a row would put a class somewhere it is not
    already. A hold sitting on a class predates this rule, or was written
    straight into the database, and either way re-uploading the file that
    describes the timetable as it stands must not start failing over it."""
    headers = login(client, "admin@test.internal", ADMIN_PASSWORD)
    cycle = _make_cycle(db)
    assert _upload(client, headers, cycle.id, _csv(_row())).status_code == 200

    room = db.query(Resource).filter(Resource.code == "LH-201").one()
    db.add(
        Reservation(
            resource_id=room.id,
            reserved_date=TOMORROW,
            time_window_start=datetime.time(9, 0),
            time_window_end=datetime.time(10, 0),
            purpose="Placed before the rule existed",
            requested_by_id="ADM001",
            idempotency_key="legacy-0000-0001",
            request_fingerprint="x" * 64,
            status=ReservationStatus.HELD,
        )
    )
    db.commit()

    r = _upload(client, headers, cycle.id, _csv(_row()))
    assert r.json()["status"] == "SUCCESS", r.text
