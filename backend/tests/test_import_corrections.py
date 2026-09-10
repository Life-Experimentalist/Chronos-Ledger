# Copyright 2026 Chronos Ledger Contributors
# Licensed under the Apache License, Version 2.0
"""Re-uploading a corrected CSV, and what that does to days already generated.

The import used to create on a miss and skip on a hit, so a timetable was
write-once: fixing a room or a lead in the source file and uploading it
again changed nothing and reported nothing. These tests pin down what a
correction now reaches, and the two things it deliberately does not touch:
a day somebody has already marked, and any day in the past.
"""

import datetime

from app.core.time import org_today
from app.cron.ledger_generator import generate_daily_ledger_entries
from app.models.db import (
    Activity,
    DailyLedger,
    StructuralMasterSlot,
    User,
    VerificationLedger,
    VerificationMetric,
)
from tests.conftest import ADMIN_PASSWORD, login
from tests.test_ingestion import HEADER, _make_cycle, _upload

TOMORROW = org_today() + datetime.timedelta(days=1)
YESTERDAY = org_today() - datetime.timedelta(days=1)


def _row(
    room="LH-201",
    lead="FAC001",
    end="10:00",
    start="09:00",
    title="Linear Algebra",
    day=None,
    code="MA201",
):
    day = TOMORROW.isoweekday() if day is None else day
    return (
        f"STU900,Ada Newling,ada@test.internal,{code},{title},"
        f"CSE,{day},{start},{end},{lead},{room}\n"
    )


def _csv(*rows):
    return HEADER + "\n" + "".join(rows)


def _slots(db, code="MA201"):
    return (
        db.query(StructuralMasterSlot)
        .join(Activity, StructuralMasterSlot.activity_id == Activity.id)
        .filter(Activity.activity_code == code)
        .order_by(StructuralMasterSlot.time_window_start)
        .all()
    )


def _import_twice(client, db, seed_users, first, second):
    cycle = _make_cycle(db)
    headers = login(client, "admin@test.internal", ADMIN_PASSWORD)
    r1 = _upload(client, headers, cycle.id, first)
    assert r1.status_code == 200, r1.text
    r2 = _upload(client, headers, cycle.id, second)
    assert r2.status_code == 200, r2.text
    db.expire_all()
    return r2.json()


def test_a_corrected_room_reaches_the_master_slot(client, db, seed_users):
    body = _import_twice(
        client,
        db,
        seed_users,
        _csv(_row(room="LH-201")),
        _csv(_row(room="LH-305")),
    )
    slots = _slots(db)
    assert len(slots) == 1
    assert slots[0].target_room_identifier == "LH-305"
    assert body["slots_corrected"] == 1


def test_a_corrected_lead_and_end_time_reach_the_master_slot(client, db, seed_users):
    _import_twice(
        client,
        db,
        seed_users,
        _csv(_row(lead="FAC001", end="10:00")),
        _csv(_row(lead="ADM001", end="11:00")),
    )
    slots = _slots(db)
    assert len(slots) == 1
    assert slots[0].primary_lead_id == "ADM001"
    assert slots[0].time_window_end == datetime.time(11, 0)


def test_a_corrected_activity_title_reaches_the_offering(client, db, seed_users):
    _import_twice(
        client,
        db,
        seed_users,
        _csv(_row(title="Linear Algebra")),
        _csv(_row(title="Linear Algebra II")),
    )
    offering = db.query(Activity).filter(Activity.activity_code == "MA201").one()
    assert offering.activity_title == "Linear Algebra II"


def test_a_changed_start_time_arrives_as_a_second_slot(client, db, seed_users):
    """The identity decision, written down.

    A slot is identified by (activity, day, start time). Move the start
    time and the file no longer describes the same slot, so the import
    adds one and leaves the original standing. Nothing in the CSV can say
    "this is the 09:00 class, moved", so the alternative to keeping both
    is guessing, and a wrong guess deletes a real timetable. Removing the
    stale one is a job for the delete endpoint, not for the importer.
    """
    body = _import_twice(
        client,
        db,
        seed_users,
        _csv(_row(start="09:00", end="10:00")),
        _csv(_row(start="11:00", end="12:00")),
    )
    slots = _slots(db)
    assert [s.time_window_start for s in slots] == [
        datetime.time(9, 0),
        datetime.time(11, 0),
    ]
    assert body["slots_corrected"] == 0


def test_an_identical_reimport_corrects_nothing(client, db, seed_users):
    body = _import_twice(client, db, seed_users, _csv(_row()), _csv(_row()))
    assert len(_slots(db)) == 1
    assert body["slots_corrected"] == 0
    assert body["ledger_rows_updated"] == 0


def test_an_email_already_in_use_is_named_not_crashed(client, db, seed_users):
    cycle = _make_cycle(db)
    headers = login(client, "admin@test.internal", ADMIN_PASSWORD)
    first = _csv(
        _row(),
        "STU901,Grace Hoppen,grace@test.internal,MA201,Linear Algebra,"
        f"CSE,{TOMORROW.isoweekday()},09:00,10:00,FAC001,LH-201\n",
    )
    assert _upload(client, headers, cycle.id, first).status_code == 200

    # Ada's row now carries Grace's address.
    clash = _csv(
        "STU900,Ada Newling,grace@test.internal,MA201,Linear Algebra,"
        f"CSE,{TOMORROW.isoweekday()},09:00,10:00,FAC001,LH-201\n"
    )
    r = _upload(client, headers, cycle.id, clash)
    assert r.status_code == 422
    detail = r.json()["detail"]
    assert "grace@test.internal" in detail
    assert "STU901" in detail

    db.expire_all()
    assert db.query(User).filter(User.id == "STU900").one().email_address == "ada@test.internal"


# ── What a correction does to days already on the board ─────────────────────


def _materialize_tomorrow(client, db, seed_users, csv_text):
    cycle = _make_cycle(db)
    headers = login(client, "admin@test.internal", ADMIN_PASSWORD)
    assert _upload(client, headers, cycle.id, csv_text).status_code == 200
    assert generate_daily_ledger_entries(TOMORROW, db) == 1
    db.expire_all()
    return headers, cycle, db.query(DailyLedger).one()


def test_a_correction_reaches_a_day_that_is_only_a_plan(client, db, seed_users):
    headers, cycle, entry = _materialize_tomorrow(client, db, seed_users, _csv(_row(room="LH-201")))
    # An admin had pinned the geofence to the old room.
    entry.latitude_target = 12.9716
    entry.longitude_target = 77.5946
    db.commit()

    r = _upload(client, headers, cycle.id, _csv(_row(room="LH-305", lead="ADM001")))

    db.expire_all()
    entry = db.query(DailyLedger).one()
    assert entry.target_room_identifier == "LH-305"
    assert entry.active_lead_id == "ADM001"
    # The fence described the room the class has just left. Keeping it would
    # shut members out of the room they were told to go to instead.
    assert entry.latitude_target is None
    assert entry.longitude_target is None
    assert r.json()["ledger_rows_updated"] == 1


def test_a_correction_leaves_a_marked_day_alone(client, db, seed_users):
    headers, cycle, entry = _materialize_tomorrow(client, db, seed_users, _csv(_row(room="LH-201")))
    db.add(
        VerificationLedger(
            ledger_instance_id=entry.id,
            member_id="STU900",
            marking_status=VerificationMetric.PRESENT,
        )
    )
    db.commit()

    body = _upload(client, headers, cycle.id, _csv(_row(room="LH-305"))).json()

    db.expire_all()
    # The slot is corrected for every day it has yet to produce; the day that
    # already carries a record of who turned up keeps what it recorded.
    assert _slots(db)[0].target_room_identifier == "LH-305"
    assert db.query(DailyLedger).one().target_room_identifier == "LH-201"
    assert body["ledger_rows_updated"] == 0
    assert body["ledger_rows_kept"] == 1


def test_a_correction_does_not_rewrite_the_past(client, db, seed_users):
    cycle = _make_cycle(db)
    headers = login(client, "admin@test.internal", ADMIN_PASSWORD)
    csv_text = _csv(_row(room="LH-201", day=YESTERDAY.isoweekday()))
    assert _upload(client, headers, cycle.id, csv_text).status_code == 200
    assert generate_daily_ledger_entries(YESTERDAY, db) == 1

    body = _upload(
        client, headers, cycle.id, _csv(_row(room="LH-305", day=YESTERDAY.isoweekday()))
    ).json()

    db.expire_all()
    assert _slots(db)[0].target_room_identifier == "LH-305"
    assert db.query(DailyLedger).one().target_room_identifier == "LH-201"
    assert body["slots_corrected"] == 1
    assert body["ledger_rows_updated"] == 0
