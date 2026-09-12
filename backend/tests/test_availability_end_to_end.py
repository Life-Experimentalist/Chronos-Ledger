# Copyright 2026 Chronos Ledger Contributors
# Licensed under the Apache License, Version 2.0
"""What GET availability says after a timetable is edited through the API.

The service-level tests next door write ledger rows by hand and ask the
availability functions directly. That proves the functions agree with each
other; it does not prove the endpoints that move a timetable leave the room's
calendar telling the truth afterwards. These drive the real verbs, DELETE and
PATCH on a slot and close and open on a cycle, and then ask the room what it
is busy with.

Every date here is counted from today, because the routes are: deleting a
slot withdraws days from today onward and detaches the ones before it, and a
correction is copied only onto days that have not happened yet. A test on
fixed January dates would exercise the past branch of all three and pass for
the wrong reason.
"""

import datetime

from app.cron.ledger_generator import generate_daily_ledger_entries
from app.models.db import DailyLedger
from tests.test_availability_vs_day import ALREADY_TAKEN, _hold
from tests.test_cycle_activation import _close
from tests.test_import_corrections import TOMORROW
from tests.test_slot_editing import _mark, _timetable

LAST_WEEK = TOMORROW - datetime.timedelta(days=7)
NEXT_WEEK = TOMORROW + datetime.timedelta(days=7)


def _busy(client, headers, resource_id, from_=LAST_WEEK, to=NEXT_WEEK):
    r = client.get(
        f"/api/v1/resources/{resource_id}/availability",
        params={"from": str(from_), "to": str(to)},
        headers=headers,
    )
    assert r.status_code == 200, r.text
    return r.json()["busy"]


def _on(busy, day):
    return [window for window in busy if window["date"] == str(day)]


# -- DELETE /schedule/slots/{id} -----------------------------------------------


def test_a_deleted_slot_stops_occupying_the_dates_it_had_not_reached(client, db, seed_users):
    """The day it already ran keeps the hour; the dates ahead of it let go.

    Both halves matter. A detached day that stopped being reported would let
    a booking land on top of a class somebody was marked present at, and a
    withdrawn date that kept being reported would hold a room against a
    class that no longer exists anywhere.
    """
    headers, slot = _timetable(client, db, seed_users)
    room_id, slot_id = slot.resource_id, slot.id
    assert generate_daily_ledger_entries(LAST_WEEK, db) == 1
    assert generate_daily_ledger_entries(TOMORROW, db) == 1

    r = client.delete(f"/api/v1/schedule/slots/{slot_id}", headers=headers)
    assert r.status_code == 200, r.text
    assert r.json() == {"ledger_rows_removed": 1, "ledger_rows_detached": 1}

    busy = _busy(client, headers, room_id)
    assert [window["date"] for window in busy] == [str(LAST_WEEK)]
    assert busy[0]["start"] == "09:00:00"
    assert busy[0]["end"] == "10:00:00"
    assert busy[0]["master_slot_id"] is None


def test_the_hour_a_deleted_slot_gave_up_can_be_booked(client, db, seed_users):
    """Reading free and being allowed to take it are the same answer here."""
    headers, slot = _timetable(client, db, seed_users)
    room_id, slot_id = slot.resource_id, slot.id
    assert generate_daily_ledger_entries(TOMORROW, db) == 1
    assert client.delete(f"/api/v1/schedule/slots/{slot_id}", headers=headers).status_code == 200

    r = _hold(client, headers, room_id, TOMORROW)
    assert r.status_code == 201, r.text

    busy = _busy(client, headers, room_id, from_=TOMORROW, to=TOMORROW)
    assert len(busy) == 1
    assert busy[0]["master_slot_id"] is None
    assert busy[0]["reservation_id"] is not None


# -- PATCH /schedule/slots/{id} ------------------------------------------------


def test_a_marked_day_keeps_its_hour_while_the_slot_moves_on(client, db, seed_users):
    """The disagreement availability has to resolve, arrived at honestly.

    A day somebody has marked is a record and the correction does not touch
    it, so after moving the class to 10:00 the room genuinely has a day at
    09:00 and a slot at 10:00 covering the same weekday. The date the day
    holds reads 09:00 and reads it once; every later date reads 10:00.
    """
    headers, slot = _timetable(client, db, seed_users)
    room_id, slot_id = slot.resource_id, slot.id
    assert generate_daily_ledger_entries(TOMORROW, db) == 1
    _mark(db, db.query(DailyLedger).one().id)

    r = client.patch(
        f"/api/v1/schedule/slots/{slot_id}",
        headers=headers,
        json={"time_window_start": "10:00:00", "time_window_end": "11:00:00"},
    )
    assert r.status_code == 200, r.text
    assert r.json()["ledger_rows_kept"] == 1

    busy = _busy(client, headers, room_id, from_=TOMORROW)
    tomorrow = _on(busy, TOMORROW)
    assert len(tomorrow) == 1
    assert tomorrow[0]["start"] == "09:00:00"
    assert tomorrow[0]["master_slot_id"] == slot_id

    next_week = _on(busy, NEXT_WEEK)
    assert len(next_week) == 1
    assert next_week[0]["start"] == "10:00:00"


# -- PATCH /schedule/cycles/{id}/close and /open -------------------------------


def test_closing_a_cycle_gives_up_the_days_it_had_planned(client, db, seed_users):
    """Closing only flipped the flag, and the room stayed taken until the dates ran out."""
    headers, slot = _timetable(client, db, seed_users)
    room_id, cycle_id = slot.resource_id, slot.activity.cycle_id
    assert generate_daily_ledger_entries(TOMORROW, db) == 1

    r = client.patch(f"/api/v1/schedule/cycles/{cycle_id}/close", headers=headers)
    assert r.status_code == 200, r.text
    assert r.json() == {
        "message": f"Cycle {cycle_id} closed",
        "ledger_rows_removed": 1,
        "ledger_rows_kept": 0,
    }

    assert _busy(client, headers, room_id, from_=TOMORROW) == []
    held = _hold(client, headers, room_id, TOMORROW)
    assert held.status_code == 201, held.text


def test_closing_a_cycle_leaves_the_days_already_past_alone(client, db, seed_users):
    headers, slot = _timetable(client, db, seed_users)
    room_id, cycle_id = slot.resource_id, slot.activity.cycle_id
    assert generate_daily_ledger_entries(LAST_WEEK, db) == 1

    r = client.patch(f"/api/v1/schedule/cycles/{cycle_id}/close", headers=headers)
    assert r.status_code == 200, r.text
    assert (r.json()["ledger_rows_removed"], r.json()["ledger_rows_kept"]) == (0, 0)

    busy = _busy(client, headers, room_id, to=LAST_WEEK)
    assert [window["date"] for window in busy] == [str(LAST_WEEK)]


def test_closing_again_clears_the_days_an_earlier_close_left(client, db, seed_users):
    """A cycle closed before the route withdrew anything still has its days."""
    headers, slot = _timetable(client, db, seed_users)
    room_id, cycle_id = slot.resource_id, slot.activity.cycle_id
    assert generate_daily_ledger_entries(TOMORROW, db) == 1
    _close(db, cycle_id)

    r = client.patch(f"/api/v1/schedule/cycles/{cycle_id}/close", headers=headers)
    assert r.status_code == 200, r.text
    assert r.json()["ledger_rows_removed"] == 1
    assert _busy(client, headers, room_id, from_=TOMORROW) == []


def test_closing_a_cycle_leaves_a_marked_day_busy(client, db, seed_users):
    """A day somebody was marked on is a record, and closing keeps it."""
    headers, slot = _timetable(client, db, seed_users)
    room_id, cycle_id = slot.resource_id, slot.activity.cycle_id
    assert generate_daily_ledger_entries(TOMORROW, db) == 1
    _mark(db, db.query(DailyLedger).one().id)

    r = client.patch(f"/api/v1/schedule/cycles/{cycle_id}/close", headers=headers)
    assert r.status_code == 200, r.text
    assert (r.json()["ledger_rows_removed"], r.json()["ledger_rows_kept"]) == (0, 1)

    busy = _busy(client, headers, room_id, from_=TOMORROW)
    assert [window["date"] for window in busy] == [str(TOMORROW)]
    assert busy[0]["start"] == "09:00:00"

    held = _hold(client, headers, room_id, TOMORROW, start="09:30", end="10:30")
    assert held.status_code == 409, held.text
    assert held.json()["detail"]["message"] == ALREADY_TAKEN


def test_reopening_a_cycle_is_not_blocked_by_the_day_its_own_slot_produced(client, db, seed_users):
    """Opening checks every slot against the room, and must skip its own days.

    The check is the same one that refuses a slot drafted onto an hour a day
    already holds. Without the exclusion a cycle closed after that day's
    register was taken could never be reopened, because closing keeps a day
    somebody has been marked on.
    """
    headers, slot = _timetable(client, db, seed_users)
    room_id, cycle_id = slot.resource_id, slot.activity.cycle_id
    assert generate_daily_ledger_entries(TOMORROW, db) == 1
    _mark(db, db.query(DailyLedger).one().id)
    closed = client.patch(f"/api/v1/schedule/cycles/{cycle_id}/close", headers=headers)
    assert closed.status_code == 200, closed.text

    r = client.patch(f"/api/v1/schedule/cycles/{cycle_id}/open", headers=headers)
    assert r.status_code == 200, r.text

    busy = _busy(client, headers, room_id, from_=TOMORROW)
    assert [window["date"] for window in busy] == [str(TOMORROW), str(NEXT_WEEK)]
    assert _on(busy, TOMORROW)[0]["master_slot_id"] == slot.id
