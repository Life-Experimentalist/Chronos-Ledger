# Copyright 2026 Chronos Ledger Contributors
# Licensed under the Apache License, Version 2.0
"""What an import says about the rows the file did not mention.

The import creates and corrects, and it will not remove. A CSV covering half
a timetable is indistinguishable from a timetable that lost half its classes,
and acting on that guess would delete enrollments nobody asked to delete. So
the response names what it did not see and stops there.

These tests pin both halves: the report finds the rows, and the rows are
still in the database after it does.
"""

from app.models.db import ActivityEnrollment, PlanningCycle, StructuralMasterSlot
from tests.conftest import ADMIN_PASSWORD, login
from tests.test_import_corrections import TOMORROW, _csv
from tests.test_ingestion import _make_cycle, _upload

DAY = TOMORROW.isoweekday()


def _line(
    member="STU900",
    name="Ada Newling",
    code="MA201",
    title="Linear Algebra",
    unit="CSE",
    day=None,
    start="09:00",
    end="10:00",
    lead="FAC001",
    room="LH-201",
):
    day = DAY if day is None else day
    return (
        f"{member},{name},{member.lower()}@test.internal,{code},{title},"
        f"{unit},{day},{start},{end},{lead},{room}\n"
    )


def _import(client, db, *rows):
    headers = login(client, "admin@test.internal", ADMIN_PASSWORD)
    cycle = db.query(PlanningCycle).first() or _make_cycle(db)
    r = _upload(client, headers, cycle.id, _csv(*rows))
    assert r.status_code == 200, r.text
    return r.json()


def test_a_first_import_has_nothing_to_report(client, db, seed_users):
    body = _import(client, db, _line())
    assert body["not_in_file"] == {"slots": [], "enrollments": []}


def test_the_same_file_twice_reports_nothing(client, db, seed_users):
    _import(client, db, _line())
    body = _import(client, db, _line())
    assert body["not_in_file"] == {"slots": [], "enrollments": []}


def test_a_class_dropped_from_the_file_is_reported_and_kept(client, db, seed_users):
    _import(
        client,
        db,
        _line(code="MA201"),
        _line(code="PH101", title="Optics", start="11:00", end="12:00"),
    )
    body = _import(client, db, _line(code="MA201"))

    assert [s["activity_code"] for s in body["not_in_file"]["slots"]] == ["PH101"]
    assert [e["activity_code"] for e in body["not_in_file"]["enrollments"]] == ["PH101"]

    db.expire_all()
    # Reported, not removed. This is the whole point.
    assert db.query(StructuralMasterSlot).count() == 2
    assert db.query(ActivityEnrollment).count() == 2


def test_a_member_dropped_from_the_file_keeps_their_enrollment(client, db, seed_users):
    _import(client, db, _line(member="STU900"), _line(member="STU901", name="Bo Ferrers"))
    body = _import(client, db, _line(member="STU900"))

    assert body["not_in_file"]["enrollments"] == [{"member_id": "STU901", "activity_code": "MA201"}]
    # Both members sit on the one slot, which the file still names.
    assert body["not_in_file"]["slots"] == []

    db.expire_all()
    assert db.query(ActivityEnrollment).count() == 2


def test_the_report_names_a_slot_well_enough_to_act_on(client, db, seed_users):
    _import(
        client,
        db,
        _line(code="MA201"),
        _line(code="PH101", title="Optics", start="11:00", end="12:00", room="LH-305"),
    )
    body = _import(client, db, _line(code="MA201"))

    db.expire_all()
    reported = body["not_in_file"]["slots"][0]
    assert reported["activity_code"] == "PH101"
    assert reported["day_of_week_index"] == DAY
    assert reported["time_window_start"] == "11:00:00"
    assert reported["room"] == "LH-305"
    # The id is what a follow-up DELETE /schedule/slots/{id} needs.
    assert (
        db.query(StructuralMasterSlot).filter_by(id=reported["id"]).one().resource.code == "LH-305"
    )


def test_another_unit_is_not_reported_as_missing(client, db, seed_users):
    """Why the report is scoped to the units the file names.

    Uploads are per-unit in practice. Scoping by cycle alone would make a CSE
    file report every ECE class every single time, and a field that is always
    full of rows nobody has to act on is a field nobody reads.
    """
    _import(
        client,
        db,
        _line(code="MA201", unit="CSE"),
        _line(member="STU902", name="Cy Alderton", code="EC201", title="Circuits", unit="ECE"),
    )
    body = _import(client, db, _line(code="MA201", unit="CSE"))

    assert body["not_in_file"] == {"slots": [], "enrollments": []}


def test_a_moved_start_time_leaves_the_old_slot_and_the_report_says_so(client, db, seed_users):
    """The one correction the import cannot make, now visible.

    A slot is matched on activity, weekday and start time, so moving a class
    from 09:00 to 14:00 does not match: it arrives as a second slot and the
    09:00 one stays behind. The import still will not guess which one to
    remove, but it no longer stays quiet about the one left over.
    """
    _import(client, db, _line(start="09:00", end="10:00"))
    body = _import(client, db, _line(start="14:00", end="15:00"))

    assert [s["time_window_start"] for s in body["not_in_file"]["slots"]] == ["09:00:00"]

    db.expire_all()
    assert sorted(str(s.time_window_start) for s in db.query(StructuralMasterSlot).all()) == [
        "09:00:00",
        "14:00:00",
    ]
