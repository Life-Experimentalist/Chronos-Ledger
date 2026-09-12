# Copyright 2026 Chronos Ledger Contributors
# Licensed under the Apache License, Version 2.0
"""Putting a class where a day has already been generated.

The third of the siblings. test_slot_vs_hold checks a new slot against the
bookings and test_slot_vs_slot checks it against the timetable, and between
them they still miss the rows that actually put somebody at a door. A
generated day is neither a slot nor a hold, and there are two ordinary ways
to end up with one that no slot speaks for any more:

Closing a cycle keeps the days ahead that carry attendance or a note, and both
of the checks above skip a closed cycle on purpose. Deleting a slot nulls
master_slot_id on the days it has already run rather than erasing them, so
that attendance marked against those days survives, and those days keep
their room and their hour.

Either way the room reads as free to the availability endpoint and the
database refuses the second row anyway. Being refused with a 409 that names
what is in the way is the point of these tests; migration 013 is what makes
the refusal true rather than merely polite, and test_ledger_overlap_pg
covers that end. Everything here is a query and some Python, so it runs on
SQLite, which is the suite CI actually runs.

A CSV upload is the third way a slot reaches the database, and the one
carrying the mistake in bulk. It is checked here too, and unlike the two
verbs it is checked whatever the cycle says: correcting a slot rewrites
the future days it has already produced, and it does that in a closed
cycle as readily as an open one.

Dates are computed rather than written down, for the reason given in both
siblings: the comparison runs from today forward, so a date typed into this
file would eventually fall into the past and the tests would pass for the
wrong reason.
"""

import datetime

from app.core.time import org_today
from app.models.db import DailyLedger, StructuralMasterSlot
from app.services.availability import days_against_slot
from tests.conftest import ADMIN_PASSWORD, login
from tests.test_import_corrections import TOMORROW, _csv, _row
from tests.test_ingestion import _make_cycle, _upload
from tests.test_slot_vs_hold import DAY_AFTER, _activity, _new_slot, _room
from tests.test_slot_vs_slot import _sibling, _slot_in_db

HAS_A_DAY = "the resource already has a generated day in part of that window"

# Four weeks on is the same weekday as tomorrow, so a slot laid on tomorrow's
# weekday reaches it. Nothing bounds the search at the far end, because a
# correction is copied onto every day the slot has still to run.
FAR_OFF = TOMORROW + datetime.timedelta(days=28)
LAST_WEEK = TOMORROW - datetime.timedelta(days=7)


def _day(db, activity_id, room_id, on, start=9, end=10, slot_id=None):
    """A generated day written straight in, which is how they all arrive.

    The nightly generator is the only thing that writes these, and it is not
    what is under test here: what is under test is a slot meeting one that is
    already there. slot_id defaults to nothing, which is the deleted-class
    case, the commoner of the two ways a day outlives whatever produced it.
    """
    entry = DailyLedger(
        target_date=on,
        time_window_start=None if start is None else datetime.time(start),
        time_window_end=None if end is None else datetime.time(end),
        master_slot_id=slot_id,
        activity_id=activity_id,
        resource_id=room_id,
    )
    db.add(entry)
    db.commit()
    return entry


# ── Creating a slot ──────────────────────────────────────────────────────────


def test_a_class_is_refused_where_a_day_has_already_been_generated(client, db, seed_users):
    headers = login(client, "admin@test.internal", ADMIN_PASSWORD)
    room = _room(db)
    gone = _activity(db)
    _day(db, gone.id, room.id, TOMORROW)
    second = _sibling(db, gone.cycle_id)

    r = _new_slot(client, headers, second.id, start="09:30", end="10:30")
    assert r.status_code == 409, r.text

    body = r.json()["detail"]
    assert body["message"] == HAS_A_DAY
    # The same body the other two refusals send, so an integrator reads a
    # clash the same way whichever of the three rules produced it. A day
    # carries no reservation_id, and its master_slot_id is null here because
    # the class that produced it is no longer on the timetable.
    assert len(body["conflicts"]) == 1
    assert body["conflicts"][0]["master_slot_id"] is None
    assert body["conflicts"][0]["reservation_id"] is None
    assert body["conflicts"][0]["activity_code"] == "CS101"
    assert body["conflicts"][0]["date"] == str(TOMORROW)
    assert body["conflicts"][0]["start"] == "09:00:00"
    assert db.query(StructuralMasterSlot).count() == 0


def test_a_closed_cycles_leftover_day_still_holds_the_room(client, db, seed_users):
    """The other way in, and the reason this check has no cycle gate.

    A slot in a closed cycle occupies nothing: the two checks above skip it
    and the generator lays down no more days for it. The days it already laid
    down are a different matter. They are still in the table, they still name
    a room and an hour, and the database will refuse a second row on top of
    one of them whatever its cycle now says. A check that disagreed with the
    constraint would turn this 409 into a 500.
    """
    headers = login(client, "admin@test.internal", ADMIN_PASSWORD)
    room = _room(db)
    closed = _activity(db, is_open=False)
    leftover = _slot_in_db(
        db, closed.id, room.id, TOMORROW.isoweekday(), datetime.time(9), datetime.time(10)
    )
    _day(db, closed.id, room.id, TOMORROW, slot_id=leftover.id)
    live = _activity(db, code="CS102")

    r = _new_slot(client, headers, live.id)
    assert r.status_code == 409, r.text
    body = r.json()["detail"]
    assert body["message"] == HAS_A_DAY
    assert [c["master_slot_id"] for c in body["conflicts"]] == [leftover.id]


def test_a_class_back_to_back_with_a_generated_day_is_allowed(client, db, seed_users):
    """Half open, the same as everywhere else."""
    headers = login(client, "admin@test.internal", ADMIN_PASSWORD)
    room = _room(db)
    gone = _activity(db)
    _day(db, gone.id, room.id, TOMORROW, start=8, end=9)
    second = _sibling(db, gone.cycle_id)

    r = _new_slot(client, headers, second.id)
    assert r.status_code == 200, r.text


def test_a_day_in_another_room_is_not_in_the_way(client, db, seed_users):
    headers = login(client, "admin@test.internal", ADMIN_PASSWORD)
    _room(db)
    elsewhere = _room(db, "LH-999")
    gone = _activity(db)
    _day(db, gone.id, elsewhere.id, TOMORROW)
    second = _sibling(db, gone.cycle_id)

    r = _new_slot(client, headers, second.id)
    assert r.status_code == 200, r.text


def test_a_day_on_another_weekday_is_not_in_the_way(client, db, seed_users):
    headers = login(client, "admin@test.internal", ADMIN_PASSWORD)
    room = _room(db)
    gone = _activity(db)
    # Two days on, so it is neither the same weekday nor either side of it.
    _day(db, gone.id, room.id, TOMORROW + datetime.timedelta(days=2))
    second = _sibling(db, gone.cycle_id)

    r = _new_slot(client, headers, second.id)
    assert r.status_code == 200, r.text


def test_a_day_with_no_window_is_not_in_the_way(client, db, seed_users):
    """An ad-hoc day never claimed an hour, so it cannot be sat on.

    The database drops the same rows: the exclusion constraint is written
    WHERE both times are present, because a range with null ends is not null
    in Postgres, it overlaps everything, and a single such row would make the
    room unbookable for the rest of time.
    """
    headers = login(client, "admin@test.internal", ADMIN_PASSWORD)
    room = _room(db)
    gone = _activity(db)
    _day(db, gone.id, room.id, TOMORROW, start=None, end=None)
    second = _sibling(db, gone.cycle_id)

    r = _new_slot(client, headers, second.id)
    assert r.status_code == 200, r.text


def test_a_day_that_has_already_run_is_not_in_the_way(client, db, seed_users):
    """Last week's days are history, not a claim on the room.

    The search starts at today for the same reason the hold check does: a
    slot laid down now runs from now on, and refusing it over a day that has
    already happened would make a room unusable by everything that ever used
    it.
    """
    headers = login(client, "admin@test.internal", ADMIN_PASSWORD)
    room = _room(db)
    gone = _activity(db)
    _day(db, gone.id, room.id, LAST_WEEK)
    second = _sibling(db, gone.cycle_id)

    r = _new_slot(client, headers, second.id)
    assert r.status_code == 200, r.text


def test_a_day_four_weeks_out_still_holds_the_room(client, db, seed_users):
    """Every future day is scanned, not one probe date.

    A weekly slot runs every week, and the day it collides with can be on any
    of them. Checking only the next occurrence of the weekday would accept a
    slot that the generator then cannot lay down for a month.
    """
    headers = login(client, "admin@test.internal", ADMIN_PASSWORD)
    room = _room(db)
    gone = _activity(db)
    _day(db, gone.id, room.id, FAR_OFF)
    second = _sibling(db, gone.cycle_id)

    r = _new_slot(client, headers, second.id)
    assert r.status_code == 409, r.text
    assert r.json()["detail"]["conflicts"][0]["date"] == str(FAR_OFF)


def test_a_night_day_blocks_the_next_mornings_class(client, db, seed_users):
    """The reason the weekday either side is checked here too.

    A day running 22:00 to 06:00 occupies the following morning, and a slot
    that would collide with it sits on a different weekday. The three offsets
    are the ones the hold check uses, for the same reason.
    """
    headers = login(client, "admin@test.internal", ADMIN_PASSWORD)
    room = _room(db)
    gone = _activity(db)
    _day(db, gone.id, room.id, TOMORROW, start=22, end=6)
    second = _sibling(db, gone.cycle_id)

    r = _new_slot(
        client, headers, second.id, day=DAY_AFTER.isoweekday(), start="05:00", end="07:00"
    )
    assert r.status_code == 409, r.text
    body = r.json()["detail"]
    # Dated the day it opens on, not the day it runs into.
    assert body["conflicts"][0]["date"] == str(TOMORROW)
    assert body["conflicts"][0]["end_date"] == str(DAY_AFTER)


# ── Changing a slot ──────────────────────────────────────────────────────────


def test_moving_a_class_onto_a_generated_day_is_refused(client, db, seed_users):
    headers = login(client, "admin@test.internal", ADMIN_PASSWORD)
    room = _room(db)
    gone = _activity(db)
    _day(db, gone.id, room.id, TOMORROW)
    second = _sibling(db, gone.cycle_id)
    moving = _slot_in_db(
        db, second.id, room.id, TOMORROW.isoweekday(), datetime.time(14), datetime.time(15)
    )

    r = client.patch(
        f"/api/v1/schedule/slots/{moving.id}",
        headers=headers,
        json={"time_window_start": "09:30", "time_window_end": "10:30"},
    )
    assert r.status_code == 409, r.text
    assert r.json()["detail"]["message"] == HAS_A_DAY
    db.expire_all()
    assert db.get(StructuralMasterSlot, moving.id).time_window_start == datetime.time(14)


def test_a_slot_is_not_refused_by_the_days_it_produced_itself(client, db, seed_users):
    """Without excluding the slot being edited, no class could ever be moved.

    A slot's own days sit on its own window, so every change to its times
    would be refused by the days it laid down last week, which is the sort of
    bug that only shows up once the check exists.
    """
    headers = login(client, "admin@test.internal", ADMIN_PASSWORD)
    room = _room(db)
    activity = _activity(db)
    slot = _slot_in_db(
        db, activity.id, room.id, TOMORROW.isoweekday(), datetime.time(9), datetime.time(10)
    )
    _day(db, activity.id, room.id, TOMORROW, slot_id=slot.id)

    r = client.patch(
        f"/api/v1/schedule/slots/{slot.id}",
        headers=headers,
        json={"time_window_end": "11:00"},
    )
    assert r.status_code == 200, r.text
    db.expire_all()
    assert db.get(StructuralMasterSlot, slot.id).time_window_end == datetime.time(11)


def test_changing_only_the_lead_is_not_checked(client, db, seed_users):
    """The guard that was already there, and this rule must not break it.

    A slot sitting on top of somebody else's day predates this rule or was
    written straight into the database. Refusing to change its lead over that
    would leave no way to fix the lead at all.
    """
    headers = login(client, "admin@test.internal", ADMIN_PASSWORD)
    room = _room(db)
    gone = _activity(db)
    _day(db, gone.id, room.id, TOMORROW)
    second = _sibling(db, gone.cycle_id)
    overlapping = _slot_in_db(
        db, second.id, room.id, TOMORROW.isoweekday(), datetime.time(9), datetime.time(10)
    )

    r = client.patch(
        f"/api/v1/schedule/slots/{overlapping.id}",
        headers=headers,
        json={"primary_lead_id": "ADM001"},
    )
    assert r.status_code == 200, r.text


# ── The query on its own ─────────────────────────────────────────────────────


def test_the_search_names_a_day_once_and_not_three_times(db, seed_users):
    """Three date offsets are tried against every day, and only one can match.

    Only one of three consecutive dates falls on a given weekday, so a day
    reached through the offsets is reached exactly once. If that stopped
    being true the 409 body would list the same day three times over and the
    duplicate would read as three separate classes in the way.
    """
    room = _room(db)
    gone = _activity(db)
    day = _day(db, gone.id, room.id, TOMORROW)

    found = days_against_slot(
        db, room.id, TOMORROW.isoweekday(), datetime.time(9, 30), datetime.time(10, 30)
    )
    assert [c["master_slot_id"] for c in found] == [None]
    assert [c["date"] for c in found] == [day.target_date]


def test_today_is_searched_and_not_only_tomorrow(db, seed_users):
    """The floor is today, inclusive, so a day still to run today counts.

    A slot entered this morning for this weekday collides with this
    afternoon's already generated day, and the generator would be refused by
    the database when it next ran if this let the slot through.
    """
    room = _room(db)
    gone = _activity(db)
    today = org_today()
    _day(db, gone.id, room.id, today, start=15, end=16)

    found = days_against_slot(
        db, room.id, today.isoweekday(), datetime.time(15, 30), datetime.time(16, 30)
    )
    assert [c["date"] for c in found] == [today]


# ── Uploading a timetable ────────────────────────────────────────────────────


def test_an_upload_is_refused_where_a_day_has_already_been_generated(client, db, seed_users):
    """The whole file, not the row, the same as every other bad row in an
    import. A CSV that half applied would leave an admin diffing the file
    against the database to find out what landed."""
    headers = login(client, "admin@test.internal", ADMIN_PASSWORD)
    cycle = _make_cycle(db)
    room = _room(db)
    gone = _activity(db)
    _day(db, gone.id, room.id, TOMORROW)

    r = _upload(client, headers, cycle.id, _csv(_row()))
    assert r.status_code == 422, r.text
    # Which room and which day. An admin fixing a timetable needs to know what
    # it collided with, not that something did.
    assert "LH-201" in r.json()["detail"]
    assert str(TOMORROW) in r.json()["detail"]
    assert db.query(StructuralMasterSlot).count() == 0


def test_a_re_upload_into_a_closed_cycle_is_refused_by_a_day(client, db, seed_users):
    """The one check here that runs whatever the cycle says.

    The hold and timetable checks skip a closed cycle, because a slot in one
    is not going to be generated and so is not competing for the room. A day
    already generated is a different matter, and a re-upload reaches it:
    moving a slot rewrites the future days it has already produced, closed
    cycle or not, and the row that gets rewritten is a row the database is
    holding a room for. Gating this check on the cycle would let the import
    write the clash and then hand back the driver's error as an upload
    failure nobody could read.
    """
    headers = login(client, "admin@test.internal", ADMIN_PASSWORD)
    cycle = _make_cycle(db)
    assert _upload(client, headers, cycle.id, _csv(_row())).status_code == 200
    cycle.operational_status = False
    db.commit()

    theatre = _room(db, code="LH-999")
    gone = _activity(db)
    _day(db, gone.id, theatre.id, TOMORROW)

    r = _upload(client, headers, cycle.id, _csv(_row(room="LH-999")))
    assert r.status_code == 422, r.text
    assert "LH-999" in r.json()["detail"]

    db.expire_all()
    assert db.query(StructuralMasterSlot).one().target_room_identifier == "LH-201"


def test_a_re_upload_is_not_refused_by_its_own_days(client, db, seed_users):
    """A class's own days sit on its own window, so without excluding them no
    timetable could ever be corrected by re-uploading the file."""
    headers = login(client, "admin@test.internal", ADMIN_PASSWORD)
    cycle = _make_cycle(db)
    assert _upload(client, headers, cycle.id, _csv(_row())).status_code == 200

    db.expire_all()
    slot = db.query(StructuralMasterSlot).one()
    _day(db, slot.activity_id, slot.resource_id, TOMORROW, slot_id=slot.id)

    r = _upload(client, headers, cycle.id, _csv(_row(end="10:30")))
    assert r.json()["status"] == "SUCCESS", r.text
    db.expire_all()
    assert db.query(StructuralMasterSlot).one().time_window_end == datetime.time(10, 30)


def test_a_re_upload_that_changes_nothing_is_not_refused_by_a_day(client, db, seed_users):
    """The check runs only when a row would put a class somewhere it is not
    already. A day sitting on a class predates this rule, or was written
    straight into the database, and either way re-uploading the file that
    describes the timetable as it stands must not start failing over it."""
    headers = login(client, "admin@test.internal", ADMIN_PASSWORD)
    cycle = _make_cycle(db)
    assert _upload(client, headers, cycle.id, _csv(_row())).status_code == 200

    db.expire_all()
    room_id = db.query(StructuralMasterSlot).one().resource_id
    gone = _activity(db)
    _day(db, gone.id, room_id, TOMORROW)

    r = _upload(client, headers, cycle.id, _csv(_row()))
    assert r.json()["status"] == "SUCCESS", r.text
