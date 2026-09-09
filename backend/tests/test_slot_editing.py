# Copyright 2026 Chronos Ledger Contributors
# Licensed under the Apache License, Version 2.0
"""Editing and removing a slot that has already put days on the board.

A timetable used to be write-once through the API: there was no way to move
a class or take one off, so the only way to correct one was to edit the
database. Adding those two verbs raises one question over and over, which is
what happens to the days the slot has already produced. The answer these
tests pin down: a day nobody has marked is a plan and may be withdrawn or
rewritten, a day somebody has marked is a record and may be neither, and
what has already happened is never rewritten to match what is planned now.
"""

import datetime

from app.cron.ledger_generator import generate_daily_ledger_entries
from app.models.db import (
    DailyLedger,
    LedgerAnnotation,
    Resource,
    StructuralMasterSlot,
    VerificationLedger,
    VerificationMetric,
)
from tests.conftest import ADMIN_PASSWORD, login
from tests.test_import_corrections import TOMORROW, YESTERDAY, _csv, _row, _slots
from tests.test_ingestion import _make_cycle, _upload


def _timetable(client, db, seed_users, day=None, room="LH-201"):
    """One slot, imported the way a real one arrives, with nothing generated."""
    cycle = _make_cycle(db)
    headers = login(client, "admin@test.internal", ADMIN_PASSWORD)
    csv_text = _csv(_row(room=room, day=day))
    assert _upload(client, headers, cycle.id, csv_text).status_code == 200
    db.expire_all()
    return headers, _slots(db)[0]


def _another_weekday():
    """Any weekday the imported slot does not already sit on."""
    return TOMORROW.isoweekday() % 7 + 1


def _mark(db, entry_id):
    db.add(
        VerificationLedger(
            ledger_instance_id=entry_id,
            member_id="STU900",
            marking_status=VerificationMetric.PRESENT,
        )
    )
    db.commit()


# ── PATCH ─────────────────────────────────────────────────────────────────────


def test_a_moved_time_needs_no_propagation(client, db, seed_users):
    headers, slot = _timetable(client, db, seed_users)
    assert generate_daily_ledger_entries(TOMORROW, db) == 1

    r = client.patch(
        f"/api/v1/schedule/slots/{slot.id}",
        headers=headers,
        json={"time_window_start": "10:00:00", "time_window_end": "11:00:00"},
    )
    assert r.status_code == 200, r.text

    db.expire_all()
    # The day reads its window off the slot, so it moved without being touched.
    entry = db.query(DailyLedger).one()
    assert entry.master_slot.time_window_start == datetime.time(10, 0)
    assert r.json()["ledger_rows_removed"] == 0


def test_a_window_cannot_be_collapsed_by_patching_one_end(client, db, seed_users):
    """The check has to see both ends, and only one of them is in the payload.

    The imported slot runs 09:00 to 10:00, so moving the start onto ten
    leaves a pair that says nothing: a window of no length, or of a whole
    day, with nothing in the row to tell them apart. The schema cannot catch
    it because the end it would collide with is not in the payload.
    """
    headers, slot = _timetable(client, db, seed_users)

    r = client.patch(
        f"/api/v1/schedule/slots/{slot.id}",
        headers=headers,
        json={"time_window_start": "10:00:00"},
    )
    assert r.status_code == 422

    db.expire_all()
    assert _slots(db)[0].time_window_start == datetime.time(9, 0)


def test_a_slot_can_be_moved_onto_a_night_shift(client, db, seed_users):
    """The other side of the same merge. 16:00 against the existing end of
    10:00 is a window that runs past midnight, which is a night shift and is
    allowed, so only the pair that reads as nothing is refused."""
    headers, slot = _timetable(client, db, seed_users)

    r = client.patch(
        f"/api/v1/schedule/slots/{slot.id}",
        headers=headers,
        json={"time_window_start": "16:00:00"},
    )
    assert r.status_code == 200, r.text

    db.expire_all()
    moved = _slots(db)[0]
    assert (moved.time_window_start, moved.time_window_end) == (
        datetime.time(16, 0),
        datetime.time(10, 0),
    )


def test_a_new_room_reaches_the_days_that_are_only_plans(client, db, seed_users):
    headers, slot = _timetable(client, db, seed_users, room="LH-201")
    assert generate_daily_ledger_entries(TOMORROW, db) == 1
    entry = db.query(DailyLedger).one()
    entry.latitude_target = 12.9716
    db.commit()

    r = client.patch(
        f"/api/v1/schedule/slots/{slot.id}",
        headers=headers,
        json={"target_room_identifier": " LH-305 "},
    )
    assert r.status_code == 200, r.text
    assert r.json()["ledger_rows_updated"] == 1

    db.expire_all()
    slot = _slots(db)[0]
    # The name was stripped on the way to the resource, so the mirror is too.
    assert slot.target_room_identifier == "LH-305"
    assert slot.resource.code == "LH-305"
    entry = db.query(DailyLedger).one()
    assert entry.resource_id == slot.resource_id
    # The fence described the room the class has just left.
    assert entry.latitude_target is None


def test_a_new_lead_reaches_the_days_that_are_only_plans(client, db, seed_users):
    headers, slot = _timetable(client, db, seed_users)
    assert generate_daily_ledger_entries(TOMORROW, db) == 1

    r = client.patch(
        f"/api/v1/schedule/slots/{slot.id}",
        headers=headers,
        json={"primary_lead_id": "ADM001"},
    )
    assert r.status_code == 200, r.text

    db.expire_all()
    assert _slots(db)[0].primary_lead_id == "ADM001"
    assert db.query(DailyLedger).one().active_lead_id == "ADM001"


def test_a_patch_leaves_a_marked_day_alone(client, db, seed_users):
    headers, slot = _timetable(client, db, seed_users)
    assert generate_daily_ledger_entries(TOMORROW, db) == 1
    _mark(db, db.query(DailyLedger).one().id)

    r = client.patch(
        f"/api/v1/schedule/slots/{slot.id}",
        headers=headers,
        json={"target_room_identifier": "LH-305"},
    )
    assert r.status_code == 200, r.text
    assert r.json() == {
        "ledger_rows_updated": 0,
        "ledger_rows_kept": 1,
        "ledger_rows_removed": 0,
    }

    db.expire_all()
    assert _slots(db)[0].target_room_identifier == "LH-305"
    assert db.query(DailyLedger).one().target_room_identifier == "LH-201"


def test_a_moved_weekday_withdraws_the_days_on_the_old_one(client, db, seed_users):
    """A day cannot be moved, only withdrawn and laid down again.

    A generated day sits on a date, and the date it sits on came from the
    weekday the slot had. Change the weekday and there is no correction to
    make to that row: the class is not happening then at all.
    """
    headers, slot = _timetable(client, db, seed_users)
    assert generate_daily_ledger_entries(TOMORROW, db) == 1
    new_day = (TOMORROW + datetime.timedelta(days=1)).isoweekday()

    r = client.patch(
        f"/api/v1/schedule/slots/{slot.id}",
        headers=headers,
        json={"day_of_week_index": new_day},
    )
    assert r.status_code == 200, r.text
    assert r.json()["ledger_rows_removed"] == 1

    db.expire_all()
    assert db.query(DailyLedger).count() == 0
    # And the generator lays it back down, on the day it now runs.
    assert generate_daily_ledger_entries(TOMORROW + datetime.timedelta(days=1), db) == 1


def test_a_moved_weekday_is_refused_while_a_marked_day_stands(client, db, seed_users):
    headers, slot = _timetable(client, db, seed_users)
    assert generate_daily_ledger_entries(TOMORROW, db) == 1
    _mark(db, db.query(DailyLedger).one().id)

    r = client.patch(
        f"/api/v1/schedule/slots/{slot.id}",
        headers=headers,
        json={"day_of_week_index": _another_weekday()},
    )
    assert r.status_code == 409
    assert str(TOMORROW) in r.json()["detail"]

    db.expire_all()
    # Refused means nothing moved, not the weekday moved and the day survived.
    assert _slots(db)[0].day_of_week_index == TOMORROW.isoweekday()
    assert db.query(DailyLedger).count() == 1


def test_a_note_on_a_future_day_counts_as_much_as_attendance(client, db, seed_users):
    headers, slot = _timetable(client, db, seed_users)
    assert generate_daily_ledger_entries(TOMORROW, db) == 1
    db.add(
        LedgerAnnotation(
            ledger_instance_id=db.query(DailyLedger).one().id,
            creator_id="ADM001",
            classification_tag="NOTE",
            annotation_payload="Guest lecturer, do not move this",
        )
    )
    db.commit()

    r = client.patch(
        f"/api/v1/schedule/slots/{slot.id}",
        headers=headers,
        json={"day_of_week_index": _another_weekday()},
    )
    assert r.status_code == 409


def test_patching_a_slot_that_is_not_there_is_a_404(client, db, seed_users):
    _make_cycle(db)
    headers = login(client, "admin@test.internal", ADMIN_PASSWORD)
    r = client.patch(
        "/api/v1/schedule/slots/9999", headers=headers, json={"primary_lead_id": "ADM001"}
    )
    assert r.status_code == 404


# ── DELETE ────────────────────────────────────────────────────────────────────


def test_deleting_a_slot_removes_the_days_nobody_has_marked(client, db, seed_users):
    headers, slot = _timetable(client, db, seed_users)
    assert generate_daily_ledger_entries(TOMORROW, db) == 1

    r = client.delete(f"/api/v1/schedule/slots/{slot.id}", headers=headers)
    assert r.status_code == 200, r.text
    assert r.json() == {"ledger_rows_removed": 1, "ledger_rows_detached": 0}

    db.expire_all()
    assert db.query(StructuralMasterSlot).count() == 0
    assert db.query(DailyLedger).count() == 0


def test_deleting_a_slot_keeps_the_days_that_already_happened(client, db, seed_users):
    """The whole reason the delete cascade had to go.

    Taking a class that ran for weeks off the timetable is the ordinary
    reason to delete a slot. If the weeks go with it, an admin has to choose
    between a timetable that lies and an attendance record that is missing.
    """
    day = YESTERDAY.isoweekday()
    headers, slot = _timetable(client, db, seed_users, day=day)
    assert generate_daily_ledger_entries(YESTERDAY, db) == 1
    past = db.query(DailyLedger).one()
    _mark(db, past.id)
    past_id = past.id

    r = client.delete(f"/api/v1/schedule/slots/{slot.id}", headers=headers)
    assert r.status_code == 200, r.text
    assert r.json() == {"ledger_rows_removed": 0, "ledger_rows_detached": 1}

    db.expire_all()
    assert db.query(StructuralMasterSlot).count() == 0
    kept = db.query(DailyLedger).one()
    assert kept.id == past_id
    assert kept.master_slot_id is None
    # The room it was held in is on the row itself, so it survives the slot.
    assert kept.resource.code == "LH-201"
    assert db.query(VerificationLedger).count() == 1


def test_deleting_is_refused_while_a_day_from_today_on_is_marked(client, db, seed_users):
    headers, slot = _timetable(client, db, seed_users)
    assert generate_daily_ledger_entries(TOMORROW, db) == 1
    _mark(db, db.query(DailyLedger).one().id)

    r = client.delete(f"/api/v1/schedule/slots/{slot.id}", headers=headers)
    assert r.status_code == 409
    assert str(TOMORROW) in r.json()["detail"]

    db.expire_all()
    assert db.query(StructuralMasterSlot).count() == 1
    assert db.query(DailyLedger).count() == 1


def test_a_deleted_slot_stops_producing_days(client, db, seed_users):
    headers, slot = _timetable(client, db, seed_users)
    assert client.delete(f"/api/v1/schedule/slots/{slot.id}", headers=headers).status_code == 200

    db.expire_all()
    assert generate_daily_ledger_entries(TOMORROW, db) == 0


def test_a_deleted_slot_leaves_the_room_standing(client, db, seed_users):
    """Rooms outlive the timetables that named them.

    A resource is a thing the organization has, not a detail of one class,
    so deleting the last slot in a room must not take the room with it.
    """
    headers, slot = _timetable(client, db, seed_users, room="LH-201")
    assert client.delete(f"/api/v1/schedule/slots/{slot.id}", headers=headers).status_code == 200

    db.expire_all()
    assert [r.code for r in db.query(Resource).all()] == ["LH-201"]


def test_a_detached_day_still_reaches_a_member_calendar(client, db, seed_users):
    """A cancelled class does not erase itself from the calendar it ran on."""
    day = YESTERDAY.isoweekday()
    headers, slot = _timetable(client, db, seed_users, day=day)
    assert generate_daily_ledger_entries(YESTERDAY, db) == 1
    _mark(db, db.query(DailyLedger).one().id)
    assert client.delete(f"/api/v1/schedule/slots/{slot.id}", headers=headers).status_code == 200

    db.expire_all()
    from app.models.db import User

    token = db.query(User).filter(User.id == "STU900").one().calendar_feed_token
    feed = client.get(f"/api/v1/sync/user-feed/{token}.ics")
    assert feed.status_code == 200, feed.text
    # No window to put it in, so it lands as an all-day event rather than
    # disappearing out of the feed the way an inner join used to make it.
    assert f"DTSTART;VALUE=DATE:{YESTERDAY.strftime('%Y%m%d')}" in feed.text


def test_deleting_a_slot_that_is_not_there_is_a_404(client, db, seed_users):
    _make_cycle(db)
    headers = login(client, "admin@test.internal", ADMIN_PASSWORD)
    assert client.delete("/api/v1/schedule/slots/9999", headers=headers).status_code == 404
