# Copyright 2026 Chronos Ledger Contributors
# Licensed under the Apache License, Version 2.0
"""No two days on one room at one hour, compared on the dates the rules give.

Before rules, a slot was one weekday, and comparing two slots meant comparing
two weekdays. A rule can meet another on one date and on no other: a short
daily block and a weekly class, a fortnightly class and a monthly one. The
room checks now expand both rules into the dates they will be written on and
compare those, and the ledger refuses a day that would sit on another on any
database, not only where an exclusion constraint exists.

Dates are computed from today, for the reason test_slot_vs_hold gives.
"""

import datetime

from app.cron.ledger_generator import generate_daily_ledger_entries, materialize_horizon
from app.models.db import DailyLedger, StructuralMasterSlot
from tests.conftest import ADMIN_PASSWORD, login
from tests.test_slot_vs_hold import DAY_AFTER, TOMORROW, _activity, _room
from tests.test_slot_vs_slot import SCHEDULED, _sibling

NINE = datetime.time(9)
TEN = datetime.time(10)
DAYS = ("MO", "TU", "WE", "TH", "FR", "SA", "SU")


def _byday(day: datetime.date) -> str:
    return DAYS[day.weekday()]


def _slot_in_db(db, activity_id, room_id, rule, dtstart):
    slot = StructuralMasterSlot(
        rrule=rule,
        dtstart=dtstart,
        time_window_start=NINE,
        time_window_end=TEN,
        activity_id=activity_id,
        primary_lead_id="FAC001",
        resource_id=room_id,
        target_room_identifier="LH-201",
    )
    db.add(slot)
    db.commit()
    return slot


def _post(client, headers, activity_id, rule, dtstart):
    return client.post(
        "/api/v1/schedule/slots",
        headers=headers,
        json={
            "rrule": rule,
            "dtstart": str(dtstart),
            "time_window_start": "09:00",
            "time_window_end": "10:00",
            "activity_id": activity_id,
            "primary_lead_id": "FAC001",
            "target_room_identifier": "LH-201",
        },
    )


# -- Saving a slot ------------------------------------------------------------


def test_two_rules_that_meet_on_one_date_are_refused(client, db, seed_users):
    # A two day block from tomorrow, and a weekly class that starts on the
    # second of those days. They share one date in the whole cycle. Compared
    # weekday against weekday (the block starts on tomorrow's weekday, the
    # class on the day after's) the two looked apart.
    headers = login(client, "admin@test.internal", ADMIN_PASSWORD)
    room = _room(db)
    first = _activity(db)
    block = _slot_in_db(db, first.id, room.id, "FREQ=DAILY;COUNT=2", TOMORROW)
    second = _sibling(db, first.cycle_id)

    r = _post(client, headers, second.id, f"FREQ=WEEKLY;BYDAY={_byday(DAY_AFTER)}", DAY_AFTER)
    assert r.status_code == 409, r.text
    body = r.json()
    assert body["code"] == "RESOURCE_CONFLICT"
    assert body["detail"]["message"] == SCHEDULED
    [conflict] = body["detail"]["conflicts"]
    assert conflict["master_slot_id"] == block.id
    # The date reported is the one where the two actually meet.
    assert conflict["date"] == str(DAY_AFTER)
    assert db.query(StructuralMasterSlot).count() == 1


def test_two_rules_on_one_weekday_that_never_meet_are_allowed(client, db, seed_users):
    # Fortnightly on the same weekday, a week apart: every date of one falls
    # between two dates of the other. One weekday each, so the old check
    # refused this.
    headers = login(client, "admin@test.internal", ADMIN_PASSWORD)
    room = _room(db)
    first = _activity(db)
    rule = f"FREQ=WEEKLY;INTERVAL=2;BYDAY={_byday(TOMORROW)}"
    _slot_in_db(db, first.id, room.id, rule, TOMORROW)
    second = _sibling(db, first.cycle_id)

    r = _post(client, headers, second.id, rule, TOMORROW + datetime.timedelta(days=7))
    assert r.status_code == 200, r.text
    assert db.query(StructuralMasterSlot).count() == 2


def test_an_edit_that_makes_two_rules_meet_is_refused(client, db, seed_users):
    headers = login(client, "admin@test.internal", ADMIN_PASSWORD)
    room = _room(db)
    first = _activity(db)
    block = _slot_in_db(db, first.id, room.id, "FREQ=DAILY;COUNT=2", TOMORROW)
    second = _sibling(db, first.cycle_id)
    # Starts the week after the block, so it is clear of it.
    later = DAY_AFTER + datetime.timedelta(days=7)
    r = _post(client, headers, second.id, f"FREQ=WEEKLY;BYDAY={_byday(later)}", later)
    assert r.status_code == 200, r.text

    r = client.patch(
        f"/api/v1/schedule/slots/{r.json()['id']}",
        headers=headers,
        json={"dtstart": str(DAY_AFTER)},
    )
    assert r.status_code == 409, r.text
    [conflict] = r.json()["detail"]["conflicts"]
    assert conflict["master_slot_id"] == block.id
    assert conflict["date"] == str(DAY_AFTER)


# -- The ledger ---------------------------------------------------------------


def _days_on(db, room_id, day):
    return [
        row.master_slot_id
        for row in db.query(DailyLedger).filter(
            DailyLedger.resource_id == room_id, DailyLedger.target_date == day
        )
    ]


def _colliding_pair(db):
    """Two slots written straight in, past every API check, meeting on DAY_AFTER."""
    room = _room(db)
    first = _activity(db)
    block = _slot_in_db(db, first.id, room.id, "FREQ=DAILY;COUNT=2", TOMORROW)
    second = _sibling(db, first.cycle_id)
    weekly = _slot_in_db(
        db, second.id, room.id, f"FREQ=WEEKLY;BYDAY={_byday(DAY_AFTER)}", DAY_AFTER
    )
    return room, block, weekly


def test_the_horizon_writes_one_day_where_two_rules_meet(db, seed_users):
    room, block, weekly = _colliding_pair(db)

    materialize_horizon(db)

    # The older slot keeps the room on the shared date, on SQLite as well as
    # PostgreSQL, and the newer one keeps every other date it has.
    assert _days_on(db, room.id, DAY_AFTER) == [block.id]
    assert _days_on(db, room.id, TOMORROW) == [block.id]
    a_week_on = DAY_AFTER + datetime.timedelta(days=7)
    assert _days_on(db, room.id, a_week_on) == [weekly.id]


def test_the_nightly_job_cannot_force_a_second_day_in(db, seed_users):
    room, block, _ = _colliding_pair(db)

    assert generate_daily_ledger_entries(DAY_AFTER, db) == 1
    assert _days_on(db, room.id, DAY_AFTER) == [block.id]

    # Run again, the refused day is still refused and nothing else changes.
    assert generate_daily_ledger_entries(DAY_AFTER, db) == 0
    assert _days_on(db, room.id, DAY_AFTER) == [block.id]
