# Copyright 2026 Chronos Ledger Contributors
# Licensed under the Apache License, Version 2.0
"""An upload that removes what the file no longer lists, when asked to.

`remove_missing` is off unless sent. On, it acts on the rows the same upload
reports in `not_in_file` and on nothing else: a slot goes the way
DELETE /schedule/slots/{id} takes it, an enrollment the way
DELETE /schedule/activities/{id}/enrollments/{member_id} takes it, and a slot
that delete would refuse is left and listed rather than failing the import.
"""

import datetime
import io

from app.core.time import org_today
from app.cron.ledger_generator import generate_daily_ledger_entries
from app.models.db import (
    ActivityEnrollment,
    DailyLedger,
    PlanningCycle,
    StructuralMasterSlot,
    VerificationLedger,
    VerificationMetric,
)
from tests.conftest import ADMIN_PASSWORD, login
from tests.test_import_corrections import TOMORROW, _csv
from tests.test_import_orphans import DAY, _line
from tests.test_ingestion import _make_cycle

EMPTY = {"slots": [], "enrollments": []}

# The class kept in the file, and the one that is dropped from it.
KEPT = {"code": "MA201"}
DROPPED = {"code": "PH101", "title": "Optics", "start": "11:00", "end": "12:00", "room": "LH-305"}


def _post(client, headers, cycle_id, csv_text, remove_missing=None):
    params = {"cycle_id": cycle_id}
    if remove_missing is not None:
        params["remove_missing"] = remove_missing
    return client.post(
        "/api/v1/ingestion/upload-csv",
        params=params,
        headers=headers,
        files={"file": ("matrix.csv", io.BytesIO(csv_text.encode()), "text/csv")},
    )


def _setup(client, db, *rows):
    headers = login(client, "admin@test.internal", ADMIN_PASSWORD)
    cycle = db.query(PlanningCycle).first() or _make_cycle(db)
    assert _post(client, headers, cycle.id, _csv(*rows)).status_code == 200
    return headers, cycle


def _slot(db, code):
    return next(s for s in db.query(StructuralMasterSlot) if s.activity.activity_code == code)


def _mark(db, code, date, member="STU900"):
    entry = (
        db.query(DailyLedger)
        .filter(DailyLedger.target_date == date, DailyLedger.master_slot_id == _slot(db, code).id)
        .one()
    )
    db.add(
        VerificationLedger(
            ledger_instance_id=entry.id,
            member_id=member,
            marking_status=VerificationMetric.PRESENT,
        )
    )
    db.commit()


def test_off_by_default_nothing_is_removed(client, db, seed_users):
    headers, cycle = _setup(client, db, _line(**KEPT), _line(**DROPPED))

    for flag in (None, False):
        body = _post(client, headers, cycle.id, _csv(_line(**KEPT)), flag).json()
        assert [s["activity_code"] for s in body["not_in_file"]["slots"]] == ["PH101"]
        assert body["removed"] == EMPTY
        assert body["not_removed"] == {"slots": []}

    db.expire_all()
    assert db.query(StructuralMasterSlot).count() == 2
    assert db.query(ActivityEnrollment).count() == 2


def test_a_missing_slot_with_only_planned_days_is_removed_and_its_days_withdrawn(
    client, db, seed_users
):
    headers, cycle = _setup(client, db, _line(**KEPT), _line(**DROPPED))
    assert generate_daily_ledger_entries(TOMORROW, db) == 2
    last_week = TOMORROW - datetime.timedelta(days=7)
    assert generate_daily_ledger_entries(last_week, db) == 2
    dropped_id = _slot(db, "PH101").id

    r = _post(client, headers, cycle.id, _csv(_line(**KEPT)), True)
    assert r.status_code == 200, r.text
    body = r.json()

    assert [s["id"] for s in body["removed"]["slots"]] == [dropped_id]
    assert body["removed"]["slots"][0]["activity_code"] == "PH101"
    assert body["removed"]["slots"][0]["ledger_rows_removed"] == 1
    assert body["removed"]["slots"][0]["ledger_rows_detached"] == 1
    assert body["not_removed"] == {"slots": []}
    # The report of what the file did not list is the same as without the flag.
    assert [s["id"] for s in body["not_in_file"]["slots"]] == [dropped_id]

    db.expire_all()
    assert [s.activity.activity_code for s in db.query(StructuralMasterSlot)] == ["MA201"]
    # The planned day is gone. The day that already happened stays, with no
    # slot left to point at, as after DELETE /schedule/slots/{id}.
    days = {(d.target_date, d.activity.activity_code): d for d in db.query(DailyLedger)}
    assert set(days) == {
        (TOMORROW, "MA201"),
        (last_week, "MA201"),
        (last_week, "PH101"),
    }
    assert days[(last_week, "PH101")].master_slot_id is None


def test_a_missing_slot_with_a_marked_day_ahead_is_left_and_listed(client, db, seed_users):
    headers, cycle = _setup(client, db, _line(**KEPT), _line(**DROPPED))
    assert generate_daily_ledger_entries(TOMORROW, db) == 2
    _mark(db, "PH101", TOMORROW)
    dropped_id = _slot(db, "PH101").id

    r = _post(client, headers, cycle.id, _csv(_line(**KEPT)), True)
    # The rest of the import is not failed by the one slot it could not remove.
    assert r.status_code == 200, r.text
    body = r.json()

    assert body["removed"]["slots"] == []
    [left] = body["not_removed"]["slots"]
    assert left["id"] == dropped_id
    assert left["activity_code"] == "PH101"
    assert TOMORROW.isoformat() in left["reason"]

    db.expire_all()
    assert db.query(StructuralMasterSlot).count() == 2
    assert db.query(DailyLedger).count() == 2
    assert db.query(VerificationLedger).count() == 1


def test_a_refused_slot_does_not_stop_another_from_going(client, db, seed_users):
    gone = {
        "code": "CH101",
        "title": "Chemistry",
        "start": "13:00",
        "end": "14:00",
        "room": "LH-401",
    }
    headers, cycle = _setup(client, db, _line(**KEPT), _line(**DROPPED), _line(**gone))
    assert generate_daily_ledger_entries(TOMORROW, db) == 3
    _mark(db, "PH101", TOMORROW)

    body = _post(client, headers, cycle.id, _csv(_line(**KEPT)), True).json()

    assert [s["activity_code"] for s in body["removed"]["slots"]] == ["CH101"]
    assert [s["activity_code"] for s in body["not_removed"]["slots"]] == ["PH101"]
    db.expire_all()
    assert sorted(s.activity.activity_code for s in db.query(StructuralMasterSlot)) == [
        "MA201",
        "PH101",
    ]


def test_a_missing_enrollment_is_dropped_and_its_attendance_stays(client, db, seed_users):
    second = {"member": "STU901", "name": "Bo Ferrers"}
    headers, cycle = _setup(client, db, _line(**KEPT), _line(**KEPT, **second))
    assert generate_daily_ledger_entries(TOMORROW, db) == 1
    _mark(db, "MA201", TOMORROW, member="STU901")

    body = _post(client, headers, cycle.id, _csv(_line(**KEPT)), True).json()

    assert body["removed"]["enrollments"] == [{"member_id": "STU901", "activity_code": "MA201"}]
    # The slot is still named by the file, so it is not a candidate.
    assert body["removed"]["slots"] == []
    assert body["not_removed"] == {"slots": []}

    db.expire_all()
    assert [e.member_id for e in db.query(ActivityEnrollment)] == ["STU900"]
    record = db.query(VerificationLedger).one()
    assert record.member_id == "STU901"
    assert db.query(DailyLedger).count() == 1


def test_nothing_outside_the_files_units_is_removed(client, db, seed_users):
    other_unit = {
        "member": "STU902",
        "name": "Cy Alderton",
        "code": "EC201",
        "title": "Circuits",
        "unit": "ECE",
        "room": "LH-301",
    }
    headers, cycle = _setup(client, db, _line(**KEPT), _line(**other_unit))

    body = _post(client, headers, cycle.id, _csv(_line(**KEPT)), True).json()

    assert body["not_in_file"] == EMPTY
    assert body["removed"] == EMPTY
    db.expire_all()
    assert db.query(StructuralMasterSlot).count() == 2
    assert db.query(ActivityEnrollment).count() == 2


def test_nothing_in_another_cycle_is_removed(client, db, seed_users):
    headers, cycle = _setup(client, db, _line(**KEPT))
    later = PlanningCycle(
        cycle_label="Later",
        date_bounds_start=org_today(),
        date_bounds_end=org_today() + datetime.timedelta(days=60),
        operational_status=True,
    )
    db.add(later)
    db.commit()
    elsewhere = _line(code="PH101", title="Optics", room="LH-305", day=(DAY % 7) + 1)
    assert _post(client, headers, later.id, _csv(elsewhere)).status_code == 200

    # The first cycle's file lists neither of the later cycle's rows.
    body = _post(client, headers, cycle.id, _csv(_line(**KEPT)), True).json()

    assert body["removed"] == EMPTY
    db.expire_all()
    assert sorted(s.activity.activity_code for s in db.query(StructuralMasterSlot)) == [
        "MA201",
        "PH101",
    ]


def test_a_refused_file_removes_nothing(client, db, seed_users):
    headers, cycle = _setup(client, db, _line(**KEPT), _line(**DROPPED))
    # Row two names a lead who does not exist, so the file is refused whole.
    bad = _line(code="MA201", member="STU903", name="Di Marsh", lead="NOBODY")

    r = _post(client, headers, cycle.id, _csv(_line(**KEPT), bad), True)

    assert r.status_code == 422
    db.expire_all()
    assert db.query(StructuralMasterSlot).count() == 2
    assert db.query(ActivityEnrollment).count() == 2
