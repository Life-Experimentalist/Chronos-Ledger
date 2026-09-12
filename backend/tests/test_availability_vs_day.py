# Copyright 2026 Chronos Ledger Contributors
# Licensed under the Apache License, Version 2.0
"""Reading a resource's calendar when a day has already been generated.

test_availability pins the expansion of the weekly timetable and the
reservations. Neither of those is the row that actually puts somebody at a
door: the nightly generator writes a dated row per slot per date, and that
row is what attendance is marked against and what the database refuses a
second booking on top of.

Three ordinary things leave a generated day that the timetable no longer
speaks for, or speaks for wrongly. Closing a cycle keeps the days already past
and any ahead that carry attendance or a note, and booked_slots counts open
cycles only. Deleting a
slot nulls master_slot_id on its days rather than erasing them, so attendance
survives. And moving a slot's hours leaves the days already in use holding
their old window. In all three the room read as free here and was refused by
the database, which is the shape of bug an integrator hits once and never
trusts the endpoint again.

test_slot_vs_day is the same question from the other end: a new slot meeting
a day that already exists. This file is availability and booking meeting one.

Dates are fixed rather than computed from today, the way test_availability
does it: a weekday derived from the day the suite happens to run is a test
that only tests something two days in seven.
"""

import datetime

from app.models.db import DailyLedger
from tests.conftest import ADMIN_PASSWORD, login
from tests.test_availability import (
    MONDAY,
    SUNDAY,
    TUESDAY,
    _availability,
    _cycle,
    _room,
    _slot,
)

ALREADY_TAKEN = "the resource is already taken for part of that window"


def _day(db, activity_id, room_id, on, start="09:00", end="10:00", slot_id=None):
    """A generated day written straight in, which is how they all arrive.

    The nightly generator is the only thing that writes these and it is not
    what is under test. slot_id defaults to nothing, the deleted-slot case.
    """
    entry = DailyLedger(
        target_date=on,
        time_window_start=None if start is None else datetime.time.fromisoformat(start),
        time_window_end=None if end is None else datetime.time.fromisoformat(end),
        master_slot_id=slot_id,
        activity_id=activity_id,
        resource_id=room_id,
    )
    db.add(entry)
    db.commit()
    return entry


def _hold(client, headers, resource_id, on, start="09:00", end="10:00", key="hold-0000-0001"):
    return client.post(
        f"/api/v1/resources/{resource_id}/reservations",
        json={"date": str(on), "start": start, "end": end, "purpose": "Ward round"},
        headers={**headers, "Idempotency-Key": key},
    )


# -- Days no slot speaks for any more -----------------------------------------


def test_a_closed_cycles_generated_day_is_still_busy(client, db, seed_users):
    """The gap that let a booking land on top of a running class.

    booked_slots counts open cycles only, on purpose: a closed cycle produces
    no more days, so reporting its slots would claim dates the generator is
    never going to fill. The days it already produced are a different matter.
    """
    room = _room(db)
    slot = _slot(db, room, _cycle(db, open_=False))
    _day(db, slot.activity_id, room.id, MONDAY, slot_id=slot.id)
    headers = login(client, "admin@test.internal", ADMIN_PASSWORD)

    busy = _availability(client, headers, room.id).json()["busy"]
    assert len(busy) == 1
    assert busy[0]["date"] == "2026-01-05"
    assert busy[0]["start"] == "09:00:00"
    assert busy[0]["master_slot_id"] == slot.id
    assert busy[0]["reservation_id"] is None


def test_a_booking_is_refused_on_a_closed_cycles_generated_day(client, db, seed_users):
    """The half of the same bug that wrote a row rather than only reading one."""
    room = _room(db)
    slot = _slot(db, room, _cycle(db, open_=False))
    _day(db, slot.activity_id, room.id, MONDAY, slot_id=slot.id)
    headers = login(client, "admin@test.internal", ADMIN_PASSWORD)

    r = _hold(client, headers, room.id, MONDAY, start="09:30", end="10:30")
    assert r.status_code == 409, r.text

    body = r.json()["detail"]
    assert body["message"] == ALREADY_TAKEN
    assert len(body["conflicts"]) == 1
    assert body["conflicts"][0]["master_slot_id"] == slot.id


def test_a_day_whose_slot_was_deleted_is_still_busy(client, db, seed_users):
    """Deleting a class nulls the link and keeps the day, so attendance survives.

    Nothing in the timetable names this hour any more. The room is booked all
    the same, and it carries no master_slot_id to say where it came from.
    """
    room = _room(db)
    slot = _slot(db, room, _cycle(db))
    _day(db, slot.activity_id, room.id, TUESDAY, start="14:00", end="15:00")
    headers = login(client, "admin@test.internal", ADMIN_PASSWORD)

    busy = _availability(client, headers, room.id, from_=TUESDAY, to=TUESDAY).json()["busy"]
    assert len(busy) == 1
    assert busy[0]["start"] == "14:00:00"
    assert busy[0]["master_slot_id"] is None


def test_a_day_with_no_window_occupies_nothing(client, db, seed_users):
    """An ad-hoc entry that never claimed an hour claims none here either.

    The same rows the database constraint skips, skipped the same way, because
    the two disagreeing is how an endpoint starts refusing what the table
    would have accepted.
    """
    room = _room(db)
    slot = _slot(db, room, _cycle(db))
    _day(db, slot.activity_id, room.id, TUESDAY, start=None, end=None)
    headers = login(client, "admin@test.internal", ADMIN_PASSWORD)

    busy = _availability(client, headers, room.id, from_=TUESDAY, to=TUESDAY).json()["busy"]
    assert busy == []


# -- A day and the slot it came from ------------------------------------------


def test_a_generated_day_replaces_the_slot_it_came_from(client, db, seed_users):
    """One entry, not two, and the day's hour rather than the slot's.

    A day is what a slot turns into. Reporting both would show a room booked
    twice for one class. Which one wins is not arbitrary: the day is the row
    that holds the hour, and where the two disagree the day is what is
    actually booked. Moving a slot leaves its days already in use on their old
    window, so this is how a corrected timetable reads until those days run.
    """
    room = _room(db)
    slot = _slot(db, room, _cycle(db))
    _day(db, slot.activity_id, room.id, MONDAY, start="11:00", end="12:00", slot_id=slot.id)
    headers = login(client, "admin@test.internal", ADMIN_PASSWORD)

    busy = _availability(client, headers, room.id).json()["busy"]
    assert len(busy) == 1
    assert busy[0]["start"] == "11:00:00"
    assert busy[0]["master_slot_id"] == slot.id


def test_the_hour_a_day_moved_off_reads_free(client, db, seed_users):
    """The other half: the slot's original hour is no longer taken."""
    room = _room(db)
    slot = _slot(db, room, _cycle(db))
    _day(db, slot.activity_id, room.id, MONDAY, start="11:00", end="12:00", slot_id=slot.id)
    headers = login(client, "admin@test.internal", ADMIN_PASSWORD)

    r = _hold(client, headers, room.id, MONDAY, start="09:00", end="10:00")
    assert r.status_code == 201, r.text


def test_a_date_with_no_generated_day_still_shows_the_slot(client, db, seed_users):
    """A slot recurs weekly and only some of its dates have been generated.

    Suppressing on the slot alone would hide the fifty-one Mondays the
    generator has not reached yet, which is the whole reason availability
    expands the timetable in the first place.
    """
    room = _room(db)
    slot = _slot(db, room, _cycle(db))
    _day(db, slot.activity_id, room.id, MONDAY, start="11:00", end="12:00", slot_id=slot.id)
    headers = login(client, "admin@test.internal", ADMIN_PASSWORD)

    next_monday = MONDAY + datetime.timedelta(days=7)
    busy = _availability(client, headers, room.id, from_=MONDAY, to=next_monday).json()["busy"]
    assert [(entry["date"], entry["start"]) for entry in busy] == [
        ("2026-01-05", "11:00:00"),
        ("2026-01-12", "09:00:00"),
    ]


# -- Past midnight ------------------------------------------------------------


def test_a_night_day_dated_before_the_range_reaches_into_it(client, db, seed_users):
    """The reason the days are fetched a day early, same as the reservations.

    A day dated Monday running 22:00 to 06:00 is on the calendar for a caller
    asking about Tuesday, and its date is the Monday it opened on.
    """
    room = _room(db)
    slot = _slot(db, room, _cycle(db))
    _day(db, slot.activity_id, room.id, MONDAY, start="22:00", end="06:00")
    headers = login(client, "admin@test.internal", ADMIN_PASSWORD)

    busy = _availability(client, headers, room.id, from_=TUESDAY, to=TUESDAY).json()["busy"]
    assert len(busy) == 1
    assert busy[0]["date"] == "2026-01-05"
    assert busy[0]["end_date"] == "2026-01-06"
    assert busy[0]["end"] == "06:00:00"


def test_a_day_the_range_does_not_reach_is_not_reported(client, db, seed_users):
    """Fetching a day early is not the same as reporting it."""
    room = _room(db)
    slot = _slot(db, room, _cycle(db))
    _day(db, slot.activity_id, room.id, MONDAY, start="09:00", end="10:00")
    headers = login(client, "admin@test.internal", ADMIN_PASSWORD)

    busy = _availability(client, headers, room.id, from_=TUESDAY, to=SUNDAY).json()["busy"]
    assert busy == []
