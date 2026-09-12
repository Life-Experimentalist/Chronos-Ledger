# Copyright 2026 Chronos Ledger Contributors
# Licensed under the Apache License, Version 2.0
"""CSV ingestion round-trip: upload, upsert, all-or-nothing rollback, RBAC."""

import datetime
import io

import pytest

from app.core.config import get_settings
from app.core.time import org_today
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
    today = org_today()
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


@pytest.fixture
def upload_limit_of_1_mb(monkeypatch):
    """CSV_UPLOAD_MAX_MB at 1 for one test, dropped from the cache both ways."""
    monkeypatch.setenv("CSV_UPLOAD_MAX_MB", "1")
    get_settings.cache_clear()
    yield
    get_settings.cache_clear()


def test_upload_over_the_size_limit_is_refused_and_imports_nothing(
    client, db, seed_users, upload_limit_of_1_mb
):
    cycle = _make_cycle(db)
    headers = login(client, "admin@test.internal", ADMIN_PASSWORD)
    row = "STU900,Ada Newling,ada@test.internal,MA201,Linear Algebra,CSE,2,09:00,10:00,FAC001,LH-201\n"
    csv_text = HEADER + "\n" + row * (1024 * 1024 // len(row) + 1)
    r = _upload(client, headers, cycle.id, csv_text)
    assert r.status_code == 413, r.text
    assert r.json()["detail"] == "File is larger than the 1 MB upload limit"

    db.expire_all()
    assert db.query(User).filter(User.id == "STU900").first() is None


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
    body = r.json()
    assert body["status"] == "SUCCESS"
    assert body["rows_ingested"] == 2

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


# -- Provisioned credentials --------------------------------------------------


def _two_member_csv():
    return (
        HEADER + "\n"
        "STU900,Ada Newling,ada@test.internal,MA201,Linear Algebra,CSE,2,09:00,10:00,FAC001,LH-201\n"
        "STU901,Grace Hoppen,grace@test.internal,MA201,Linear Algebra,CSE,2,09:00,10:00,FAC001,LH-201\n"
    )


def test_each_imported_member_gets_a_distinct_password(client, db, seed_users):
    """A shared constant meant one leaked credential opened every account."""
    cycle = _make_cycle(db)
    headers = login(client, "admin@test.internal", ADMIN_PASSWORD)

    creds = _upload(client, headers, cycle.id, _two_member_csv()).json()["provisioned_credentials"]
    assert {c["member_id"] for c in creds} == {"STU900", "STU901"}
    assert len({c["initial_password"] for c in creds}) == 2


def test_a_provisioned_password_actually_logs_the_member_in(client, db, seed_users):
    cycle = _make_cycle(db)
    headers = login(client, "admin@test.internal", ADMIN_PASSWORD)

    creds = _upload(client, headers, cycle.id, _two_member_csv()).json()["provisioned_credentials"]
    for cred in creds:
        res = client.post(
            "/api/v1/auth/login",
            json={"email": cred["email_address"], "password": cred["initial_password"]},
        )
        assert res.status_code == 200, res.text


def test_the_plaintext_password_is_never_stored(client, db, seed_users):
    cycle = _make_cycle(db)
    headers = login(client, "admin@test.internal", ADMIN_PASSWORD)

    creds = _upload(client, headers, cycle.id, _two_member_csv()).json()["provisioned_credentials"]
    db.expire_all()
    for cred in creds:
        member = db.query(User).filter(User.id == cred["member_id"]).first()
        assert cred["initial_password"] not in member.credential_secure_hash


def test_a_reimport_does_not_reset_an_existing_password(client, db, seed_users):
    """Rotating every member's password on every re-upload would be worse."""
    cycle = _make_cycle(db)
    headers = login(client, "admin@test.internal", ADMIN_PASSWORD)

    first = _upload(client, headers, cycle.id, _two_member_csv()).json()
    db.expire_all()
    hash_before = db.query(User).filter(User.id == "STU900").first().credential_secure_hash

    second = _upload(client, headers, cycle.id, _two_member_csv()).json()
    assert second["provisioned_credentials"] == []

    db.expire_all()
    assert db.query(User).filter(User.id == "STU900").first().credential_secure_hash == hash_before
    # The password handed out by the first import still works.
    original = first["provisioned_credentials"][0]
    res = client.post(
        "/api/v1/auth/login",
        json={"email": original["email_address"], "password": original["initial_password"]},
    )
    assert res.status_code == 200, res.text


def test_an_unknown_cycle_is_404_not_a_driver_error(client, db, seed_users):
    """A mistyped cycle id used to reach the foreign key and come back as SQL."""
    headers = login(client, "admin@test.internal", ADMIN_PASSWORD)
    csv_text = (
        HEADER + "\n"
        "STU906,Nowhere Near,nowhere@test.internal,PH101,Physics,CSE,3,09:00,10:00,FAC001,LH-401\n"
    )
    r = _upload(client, headers, 4242, csv_text)
    assert r.status_code == 404, r.text
    assert r.json()["detail"] == "Cycle not found"


def test_a_bad_target_date_is_422_not_500(client, db, seed_users):
    """The date was parsed inside the handler, so a typo raised out of it."""
    headers = login(client, "admin@test.internal", ADMIN_PASSWORD)
    r = client.post("/api/v1/ingestion/generate-ledger?target_date=nine-am", headers=headers)
    assert r.status_code == 422, r.text

    ok = client.post("/api/v1/ingestion/generate-ledger?target_date=2026-03-04", headers=headers)
    assert ok.status_code == 200, ok.text
    assert ok.json()["date"] == "2026-03-04"


def test_an_internal_failure_does_not_hand_back_the_sql(client, db, seed_users, monkeypatch):
    """The catch-all returned str(e), which on a database error is the statement.

    Whoever uploaded the spreadsheet is told the import failed and which line
    it stopped on. The rest goes to the log.
    """
    cycle = _make_cycle(db)
    headers = login(client, "admin@test.internal", ADMIN_PASSWORD)

    leak = "INSERT INTO users (credential_secure_hash) VALUES ($2b$12$donotshowthis)"

    def _boom(_password):
        raise RuntimeError(leak)

    monkeypatch.setattr("app.services.ingestion_engine.hash_password", _boom)

    csv_text = (
        HEADER + "\n"
        "STU907,Leaky Row,leaky@test.internal,PH102,Optics,CSE,3,09:00,10:00,FAC001,LH-402\n"
    )
    r = _upload(client, headers, cycle.id, csv_text)
    assert r.status_code == 422
    detail = r.json()["detail"]
    assert leak not in detail
    assert "INSERT INTO" not in detail
    assert "server log" in detail
    # The row it stopped on is still named, because that much is the uploader's.
    assert detail.startswith("line 2: ")

    db.expire_all()
    assert db.query(User).filter(User.id == "STU907").first() is None
