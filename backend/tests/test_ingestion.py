# Copyright 2026 Chronos Ledger Contributors
# Licensed under the Apache License, Version 2.0
"""CSV ingestion round-trip: upload, upsert, all-or-nothing rollback, RBAC."""

import datetime
import io

from app.models.db import (
    Activity,
    ActivityEnrollment,
    PlanningCycle,
    StructuralMasterSlot,
    User,
)
from tests.conftest import ADMIN_PASSWORD, MEMBER_PASSWORD, login

HEADER = (
    "member_id,member_name,member_email,activity_code,activity_title,"
    "unit,day_of_week_index,time_window_start,time_window_end,lead_id,room"
)


def _make_cycle(db):
    today = datetime.date.today()
    cycle = PlanningCycle(
        cycle_label="Ingest 2026",
        date_bounds_start=today - datetime.timedelta(days=30),
        date_bounds_end=today + datetime.timedelta(days=90),
        operational_status=True,
    )
    db.add(cycle)
    db.commit()
    return cycle


def _upload(client, headers, cycle_id, csv_text, filename="matrix.csv"):
    return client.post(
        f"/api/v1/ingestion/upload-csv?cycle_id={cycle_id}",
        headers=headers,
        files={"file": (filename, io.BytesIO(csv_text.encode()), "text/csv")},
    )


def test_upload_happy_path_creates_everything(client, db, seed_users):
    cycle = _make_cycle(db)
    headers = login(client, "admin@test.internal", ADMIN_PASSWORD)
    csv_text = (
        HEADER + "\n"
        "STU900,Ada Newling,ada@test.internal,MA201,Linear Algebra,CSE,2,09:00,10:00,FAC001,LH-201\n"
        "STU901,Grace Hoppen,grace@test.internal,MA201,Linear Algebra,CSE,2,09:00,10:00,FAC001,LH-201\n"
    )
    r = _upload(client, headers, cycle.id, csv_text)
    assert r.status_code == 200, r.text
    assert r.json() == {"status": "SUCCESS", "rows_ingested": 2}

    db.expire_all()
    ada = db.query(User).filter(User.id == "STU900").first()
    assert ada is not None
    assert ada.role_type.value == "MEMBER"
    assert ada.unit_code == "CSE"

    offerings = db.query(Activity).filter(Activity.activity_code == "MA201").all()
    assert len(offerings) == 1  # both rows share one offering
    regs = (
        db.query(ActivityEnrollment).filter(ActivityEnrollment.activity_id == offerings[0].id).all()
    )
    assert {reg.member_id for reg in regs} == {"STU900", "STU901"}

    slots = (
        db.query(StructuralMasterSlot)
        .filter(StructuralMasterSlot.activity_id == offerings[0].id)
        .all()
    )
    assert len(slots) == 1  # deduplicated by activity + day + start time
    assert slots[0].primary_lead_id == "FAC001"
    assert slots[0].target_room_identifier == "LH-201"


def test_upload_is_idempotent(client, db, seed_users):
    cycle = _make_cycle(db)
    headers = login(client, "admin@test.internal", ADMIN_PASSWORD)
    csv_text = (
        HEADER + "\n"
        "STU902,Alan Turington,alan@test.internal,PH101,Mechanics,CSE,3,11:00,12:00,FAC001,LH-105\n"
    )
    assert _upload(client, headers, cycle.id, csv_text).status_code == 200
    assert _upload(client, headers, cycle.id, csv_text).status_code == 200

    db.expire_all()
    assert db.query(User).filter(User.id == "STU902").count() == 1
    assert db.query(Activity).filter(Activity.activity_code == "PH101").count() == 1


def test_missing_column_is_422(client, db, seed_users):
    cycle = _make_cycle(db)
    headers = login(client, "admin@test.internal", ADMIN_PASSWORD)
    # Drop the room column entirely.
    csv_text = (
        HEADER.replace(",room", "") + "\n"
        "STU903,No Room,noroom@test.internal,CH101,Chemistry,CSE,4,14:00,15:00,FAC001\n"
    )
    r = _upload(client, headers, cycle.id, csv_text)
    assert r.status_code == 422
    assert "Missing columns" in r.json()["detail"]
    assert "room" in r.json()["detail"]


def test_bad_time_rolls_back_the_whole_file(client, db, seed_users):
    cycle = _make_cycle(db)
    headers = login(client, "admin@test.internal", ADMIN_PASSWORD)
    # Row one is valid, row two has an unparseable time: nothing may land.
    csv_text = (
        HEADER + "\n"
        "STU904,First Fine,fine@test.internal,BI101,Biology,CSE,5,09:00,10:00,FAC001,LH-301\n"
        "STU905,Then Broken,broken@test.internal,BI101,Biology,CSE,5,nine am,10:00,FAC001,LH-301\n"
    )
    r = _upload(client, headers, cycle.id, csv_text)
    assert r.status_code == 422
    assert "Cannot parse time value" in r.json()["detail"]

    db.expire_all()
    assert db.query(User).filter(User.id == "STU904").first() is None
    assert db.query(Activity).filter(Activity.activity_code == "BI101").first() is None


def test_non_csv_filename_is_400(client, db, seed_users):
    cycle = _make_cycle(db)
    headers = login(client, "admin@test.internal", ADMIN_PASSWORD)
    r = _upload(client, headers, cycle.id, HEADER + "\n", filename="matrix.xlsx")
    assert r.status_code == 400


def test_member_cannot_upload(client, db, seed_users):
    cycle = _make_cycle(db)
    headers = login(client, "member@test.internal", MEMBER_PASSWORD)
    r = _upload(client, headers, cycle.id, HEADER + "\n")
    assert r.status_code == 403
