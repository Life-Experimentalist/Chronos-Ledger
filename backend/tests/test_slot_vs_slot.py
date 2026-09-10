# Copyright 2026 Chronos Ledger Contributors
# Licensed under the Apache License, Version 2.0
"""Putting a class where another class already sits.

Chronos checked a slot against the bookings and never against the timetable,
so one room could hold two classes at one hour and nothing said so. Both
slots generated a ledger row every week, both rows named the same room, and
the first anybody knew was two groups arriving at one door.

This is the sibling of test_slot_vs_hold, and the same three ways in are
pinned: the two verbs that write a slot, and the CSV upload that writes them
in bulk. The importer is the one most likely to make the mistake, because
two rows naming one room at one hour read as two ordinary rows.

Dates are computed rather than written down, for the reason given there: the
comparison runs from tomorrow forward, so a date typed into this file would
eventually fall into the past and the tests would pass for the wrong reason.
"""

import datetime

from app.models.db import Activity, PlanningCycle, StructuralMasterSlot
from tests.conftest import ADMIN_PASSWORD, login
from tests.test_import_corrections import TOMORROW, _csv, _row
from tests.test_ingestion import _make_cycle, _upload
from tests.test_slot_vs_hold import DAY_AFTER, _activity, _new_slot, _room

SCHEDULED = "the resource is already on the timetable for part of that window"


def _sibling(db, cycle_id, code="CS102"):
    """A second activity inside a cycle that already exists.

    _activity opens a cycle of its own each time it is called, which is the
    two-open-cycles case. This is the ordinary one: two classes in the same
    term, competing for the same room.
    """
    activity = Activity(
        activity_code=code,
        activity_title="Something else",
        unit_code="CSE",
        cycle_id=cycle_id,
    )
    db.add(activity)
    db.commit()
    return activity


def _slot_in_db(db, activity_id, room_id, day, start, end):
    """A slot written straight in, so the test's subject is the second one."""
    slot = StructuralMasterSlot(
        day_of_week_index=day,
        time_window_start=start,
        time_window_end=end,
        activity_id=activity_id,
        primary_lead_id="FAC001",
        resource_id=room_id,
        target_room_identifier="LH-201",
    )
    db.add(slot)
    db.commit()
    return slot


# ── Creating a slot ──────────────────────────────────────────────────────────


def test_a_class_is_refused_where_another_class_already_is(client, db, seed_users):
    headers = login(client, "admin@test.internal", ADMIN_PASSWORD)
    room = _room(db)
    first = _activity(db)
    sitting = _slot_in_db(
        db, first.id, room.id, TOMORROW.isoweekday(), datetime.time(9), datetime.time(11)
    )
    second = _sibling(db, first.cycle_id)

    r = _new_slot(client, headers, second.id, start="10:00", end="12:00")
    assert r.status_code == 409, r.text

    body = r.json()["detail"]
    assert body["message"] == SCHEDULED
    # The same body a hold clash sends, so an integrator reads a refusal the
    # same way whichever of the two rules produced it. A slot conflict names
    # the activity and carries no reservation_id, which is how the two kinds
    # are told apart everywhere else.
    assert [c["master_slot_id"] for c in body["conflicts"]] == [sitting.id]
    assert body["conflicts"][0]["reservation_id"] is None
    assert body["conflicts"][0]["activity_code"] == "CS101"
    assert body["conflicts"][0]["date"] == str(TOMORROW)
    assert db.query(StructuralMasterSlot).count() == 1


def test_two_classes_back_to_back_in_one_room_are_allowed(client, db, seed_users):
    headers = login(client, "admin@test.internal", ADMIN_PASSWORD)
    room = _room(db)
    first = _activity(db)
    _slot_in_db(db, first.id, room.id, TOMORROW.isoweekday(), datetime.time(9), datetime.time(10))
    second = _sibling(db, first.cycle_id)

    r = _new_slot(client, headers, second.id, start="10:00", end="11:00")
    assert r.status_code == 200, r.text
    assert db.query(StructuralMasterSlot).count() == 2


def test_the_same_window_in_another_room_is_allowed(client, db, seed_users):
    headers = login(client, "admin@test.internal", ADMIN_PASSWORD)
    room = _room(db)
    _room(db, "LH-999")
    first = _activity(db)
    _slot_in_db(db, first.id, room.id, TOMORROW.isoweekday(), datetime.time(9), datetime.time(10))
    second = _sibling(db, first.cycle_id)

    r = _new_slot(client, headers, second.id, room="LH-999")
    assert r.status_code == 200, r.text


def test_the_same_window_on_another_weekday_is_allowed(client, db, seed_users):
    headers = login(client, "admin@test.internal", ADMIN_PASSWORD)
    room = _room(db)
    first = _activity(db)
    _slot_in_db(db, first.id, room.id, TOMORROW.isoweekday(), datetime.time(9), datetime.time(10))
    second = _sibling(db, first.cycle_id)

    # Two days on, so it is neither the same weekday nor either side of it.
    other = (TOMORROW + datetime.timedelta(days=2)).isoweekday()
    r = _new_slot(client, headers, second.id, day=other)
    assert r.status_code == 200, r.text


def test_a_night_class_blocks_the_next_mornings_class(client, db, seed_users):
    """The reason the weekday either side is checked.

    A class running 22:00 to 06:00 occupies the following morning, and the
    slot that would collide with it sits on a different weekday. Sharing a
    weekday and overlapping in time stopped being the same question when a
    window learned to run past midnight.
    """
    headers = login(client, "admin@test.internal", ADMIN_PASSWORD)
    room = _room(db)
    first = _activity(db)
    night = _slot_in_db(
        db, first.id, room.id, TOMORROW.isoweekday(), datetime.time(22), datetime.time(6)
    )
    second = _sibling(db, first.cycle_id)

    r = _new_slot(
        client, headers, second.id, day=DAY_AFTER.isoweekday(), start="05:00", end="07:00"
    )
    assert r.status_code == 409, r.text
    body = r.json()["detail"]
    assert [c["master_slot_id"] for c in body["conflicts"]] == [night.id]
    # Dated the day it opens on, not the day it runs into.
    assert body["conflicts"][0]["date"] == str(TOMORROW)


def test_a_class_in_a_closed_cycle_does_not_block(client, db, seed_users):
    """The gate, and it has to be the same gate the hold check uses.

    A closed cycle's slots occupy nothing: booked_slots counts open cycles
    only, and the generator lays down no days for them. Refusing here would
    make next term's timetable unenterable while last term's rows are still
    in the table.
    """
    headers = login(client, "admin@test.internal", ADMIN_PASSWORD)
    room = _room(db)
    closed = _activity(db, is_open=False)
    _slot_in_db(db, closed.id, room.id, TOMORROW.isoweekday(), datetime.time(9), datetime.time(10))
    live = _activity(db, code="CS102")

    r = _new_slot(client, headers, live.id)
    assert r.status_code == 200, r.text


def test_a_class_being_entered_into_a_closed_cycle_is_not_checked(client, db, seed_users):
    """The other half of the gate: the new slot's own cycle."""
    headers = login(client, "admin@test.internal", ADMIN_PASSWORD)
    room = _room(db)
    first = _activity(db)
    _slot_in_db(db, first.id, room.id, TOMORROW.isoweekday(), datetime.time(9), datetime.time(10))
    shut = _activity(db, is_open=False, code="CS102")

    r = _new_slot(client, headers, shut.id)
    assert r.status_code == 200, r.text


# ── Changing a slot ──────────────────────────────────────────────────────────


def test_widening_a_slot_does_not_refuse_itself(client, db, seed_users):
    """A window that grows overlaps the window it replaces.

    Without excluding the slot being edited from what it is checked against,
    every change to a slot's own times would be refused by the slot itself,
    which is the sort of bug that only shows up once the check exists.
    """
    headers = login(client, "admin@test.internal", ADMIN_PASSWORD)
    room = _room(db)
    activity = _activity(db)
    slot = _slot_in_db(
        db, activity.id, room.id, TOMORROW.isoweekday(), datetime.time(9), datetime.time(10)
    )

    r = client.patch(
        f"/api/v1/schedule/slots/{slot.id}",
        headers=headers,
        json={"time_window_end": "11:00"},
    )
    assert r.status_code == 200, r.text
    db.expire_all()
    assert db.get(StructuralMasterSlot, slot.id).time_window_end == datetime.time(11)


def test_moving_a_slot_onto_another_class_is_refused(client, db, seed_users):
    headers = login(client, "admin@test.internal", ADMIN_PASSWORD)
    room = _room(db)
    first = _activity(db)
    sitting = _slot_in_db(
        db, first.id, room.id, TOMORROW.isoweekday(), datetime.time(9), datetime.time(10)
    )
    second = _sibling(db, first.cycle_id)
    moving = _slot_in_db(
        db, second.id, room.id, TOMORROW.isoweekday(), datetime.time(14), datetime.time(15)
    )

    r = client.patch(
        f"/api/v1/schedule/slots/{moving.id}",
        headers=headers,
        json={"time_window_start": "09:30", "time_window_end": "10:30"},
    )
    assert r.status_code == 409, r.text
    assert [c["master_slot_id"] for c in r.json()["detail"]["conflicts"]] == [sitting.id]
    db.expire_all()
    assert db.get(StructuralMasterSlot, moving.id).time_window_start == datetime.time(14)


def test_changing_only_the_lead_is_not_checked(client, db, seed_users):
    """The guard that was already there, and this rule must not break it.

    A slot that sits on top of another one predates this rule or was written
    straight into the database. Refusing to change its lead over that would
    leave no way to fix the lead at all.
    """
    headers = login(client, "admin@test.internal", ADMIN_PASSWORD)
    room = _room(db)
    first = _activity(db)
    _slot_in_db(db, first.id, room.id, TOMORROW.isoweekday(), datetime.time(9), datetime.time(10))
    second = _sibling(db, first.cycle_id)
    overlapping = _slot_in_db(
        db, second.id, room.id, TOMORROW.isoweekday(), datetime.time(9), datetime.time(10)
    )

    r = client.patch(
        f"/api/v1/schedule/slots/{overlapping.id}",
        headers=headers,
        json={"primary_lead_id": "ADM001"},
    )
    assert r.status_code == 200, r.text


# ── Uploading a timetable ────────────────────────────────────────────────────


def test_two_rows_of_one_file_cannot_share_a_room_and_an_hour(client, db, seed_users):
    """The bulk version of the same mistake.

    The second row is checked against the slot the first row has just added,
    which has not been committed yet. The query flushes it first, so it
    counts.
    """
    cycle = _make_cycle(db)
    headers = login(client, "admin@test.internal", ADMIN_PASSWORD)
    r = _upload(
        client,
        headers,
        cycle.id,
        _csv(_row(), _row(code="MA202", title="Topology", start="09:30", end="10:30")),
    )
    assert r.status_code == 422, r.text
    assert "already on the timetable" in r.json()["detail"]
    assert db.query(StructuralMasterSlot).count() == 0


def test_two_rows_of_one_file_may_share_a_room_at_different_hours(client, db, seed_users):
    cycle = _make_cycle(db)
    headers = login(client, "admin@test.internal", ADMIN_PASSWORD)
    r = _upload(
        client,
        headers,
        cycle.id,
        _csv(_row(), _row(code="MA202", title="Topology", start="10:00", end="11:00")),
    )
    assert r.status_code == 200, r.text
    assert db.query(StructuralMasterSlot).count() == 2


def test_re_uploading_an_unchanged_file_is_not_refused(client, db, seed_users):
    """A file that changes nothing must stay importable.

    The slot the second upload matches is the slot it would be checked
    against, so without excluding it a stable file would start failing on
    its second import.
    """
    cycle = _make_cycle(db)
    headers = login(client, "admin@test.internal", ADMIN_PASSWORD)
    assert _upload(client, headers, cycle.id, _csv(_row())).status_code == 200
    r = _upload(client, headers, cycle.id, _csv(_row()))
    assert r.status_code == 200, r.text
    assert db.query(StructuralMasterSlot).count() == 1


def test_a_correction_moving_a_class_onto_another_is_refused(client, db, seed_users):
    cycle = _make_cycle(db)
    headers = login(client, "admin@test.internal", ADMIN_PASSWORD)
    settled = _csv(
        _row(),
        _row(code="MA202", title="Topology", start="11:00", end="12:00"),
    )
    assert _upload(client, headers, cycle.id, settled).status_code == 200

    # MA202 keeps its start time, so it matches the slot already there and
    # arrives as a correction rather than as a second slot. Its new end runs
    # into nothing; its room is what changes.
    clash = _csv(
        _row(room="LH-777"),
        _row(code="MA202", title="Topology", start="11:00", end="12:00", room="LH-777"),
    )
    assert _upload(client, headers, cycle.id, clash).status_code == 200

    # Now move MA202 on top of MA201 in the room they now share.
    moved = _csv(
        _row(room="LH-777"),
        _row(code="MA202", title="Topology", start="11:00", end="12:00", room="LH-777"),
        _row(code="MA203", title="Analysis", start="09:15", end="09:45", room="LH-777"),
    )
    r = _upload(client, headers, cycle.id, moved)
    assert r.status_code == 422, r.text
    assert "already on the timetable" in r.json()["detail"]


def test_an_upload_into_a_closed_cycle_is_not_checked(client, db, seed_users):
    """The importer's gate, matching the one both endpoints use."""
    cycle = _make_cycle(db)
    cycle.operational_status = False
    db.commit()
    headers = login(client, "admin@test.internal", ADMIN_PASSWORD)
    r = _upload(
        client,
        headers,
        cycle.id,
        _csv(_row(), _row(code="MA202", title="Topology", start="09:30", end="10:30")),
    )
    assert r.status_code == 200, r.text


def test_a_slot_in_another_open_cycle_still_blocks(client, db, seed_users):
    """Two open cycles are two timetables competing for one room.

    booked_slots counts every open cycle and the generator lays every open
    cycle onto today, so both occupy the room today whatever the cycles say
    their date bounds are. This check inherits that and does not decide
    whether two cycles should be open at once.
    """
    headers = login(client, "admin@test.internal", ADMIN_PASSWORD)
    room = _room(db)
    spring = _activity(db)
    sitting = _slot_in_db(
        db, spring.id, room.id, TOMORROW.isoweekday(), datetime.time(9), datetime.time(10)
    )
    autumn = _activity(db, code="CS102")
    assert db.query(PlanningCycle).count() == 2

    r = _new_slot(client, headers, autumn.id)
    assert r.status_code == 409, r.text
    assert [c["master_slot_id"] for c in r.json()["detail"]["conflicts"]] == [sitting.id]
