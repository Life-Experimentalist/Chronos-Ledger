# Copyright 2026 Chronos Ledger Contributors
# Licensed under the Apache License, Version 2.0

"""A department admin's reach stops at their own department.

Q12: DEPT_ADMIN could previously list, create, and edit users in any
department, schedule slots and edit ledgers for other departments' courses,
batch-mark their attendance, and upload the institution-wide CSV matrix.
"""

import datetime

from app.core.security import hash_password
from app.models.db import (
    AcademicCycle,
    CourseOffering,
    DailyLedger,
    InstitutionalRole,
    User,
)
from tests.conftest import ADMIN_PASSWORD, login

TODAY = datetime.date.today()
DEPT_ADMIN_PASSWORD = "DeptAdminPass123!"
_DEPT_ADMIN_HASH = hash_password(DEPT_ADMIN_PASSWORD)


def _seed_dept_world(db):
    """A CSE dept admin, an ECE student, and one offering + ledger per department."""
    db.add_all(
        [
            User(
                id="DAD001",
                full_name="CSE Dept Admin",
                email_address="deptadmin@test.internal",
                credential_secure_hash=_DEPT_ADMIN_HASH,
                role_type=InstitutionalRole.DEPT_ADMIN,
                department_code="CSE",
                initial_login_state=False,
            ),
            User(
                id="STU900",
                full_name="ECE Student",
                email_address="ece.student@test.internal",
                credential_secure_hash=_DEPT_ADMIN_HASH,
                role_type=InstitutionalRole.STUDENT,
                department_code="ECE",
            ),
        ]
    )
    cycle = AcademicCycle(
        cycle_label="Scope 2026",
        date_bounds_start=TODAY - datetime.timedelta(days=30),
        date_bounds_end=TODAY + datetime.timedelta(days=90),
        operational_status=True,
    )
    db.add(cycle)
    db.flush()
    offerings = {}
    ledgers = {}
    for dept, code in (("CSE", "CS900"), ("ECE", "EC900")):
        offering = CourseOffering(
            course_code=code,
            course_title=f"{dept} Course",
            department_code=dept,
            cycle_id=cycle.id,
        )
        db.add(offering)
        db.flush()
        ledger = DailyLedger(
            target_date=TODAY,
            course_offering_id=offering.id,
            target_room_identifier="LH-900",
        )
        db.add(ledger)
        db.flush()
        offerings[dept] = offering
        ledgers[dept] = ledger
    db.commit()
    return offerings, ledgers


def _dept_admin(client):
    return login(client, "deptadmin@test.internal", DEPT_ADMIN_PASSWORD)


def test_list_users_is_forced_to_own_department(client, db, seed_users):
    _seed_dept_world(db)
    headers = _dept_admin(client)
    res = client.get("/api/v1/users/", headers=headers)
    assert res.status_code == 200
    depts = {u["department_code"] for u in res.json()}
    assert depts == {"CSE"}
    # Asking for another department explicitly changes nothing.
    res = client.get("/api/v1/users/?department=ECE", headers=headers)
    assert res.status_code == 200
    assert res.json() == []


def test_cannot_create_user_in_another_department(client, db, seed_users):
    _seed_dept_world(db)
    headers = _dept_admin(client)
    payload = {
        "id": "STU901",
        "full_name": "New Student",
        "email_address": "new.student@test.internal",
        "password": "StudentPass901!",
        "role_type": "STUDENT",
        "department_code": "ECE",
    }
    assert client.post("/api/v1/users/", headers=headers, json=payload).status_code == 403
    payload["department_code"] = "CSE"
    assert client.post("/api/v1/users/", headers=headers, json=payload).status_code == 201


def test_cannot_view_or_update_user_in_another_department(client, db, seed_users):
    _seed_dept_world(db)
    headers = _dept_admin(client)
    assert client.get("/api/v1/users/STU900", headers=headers).status_code == 403
    res = client.patch("/api/v1/users/STU900", headers=headers, json={"full_name": "Renamed"})
    assert res.status_code == 403
    # And a user cannot be moved out of the admin's department.
    res = client.patch("/api/v1/users/STU001", headers=headers, json={"department_code": "ECE"})
    assert res.status_code == 403
    res = client.patch("/api/v1/users/STU001", headers=headers, json={"full_name": "Renamed"})
    assert res.status_code == 200


def test_cannot_schedule_slot_for_another_departments_course(client, db, seed_users):
    offerings, _ = _seed_dept_world(db)
    headers = _dept_admin(client)
    slot = {
        "day_of_week_index": 1,
        "time_window_start": "10:00:00",
        "time_window_end": "11:00:00",
        "course_offering_id": offerings["ECE"].id,
        "target_room_identifier": "LH-900",
    }
    assert client.post("/api/v1/schedule/slots", headers=headers, json=slot).status_code == 403
    slot["course_offering_id"] = offerings["CSE"].id
    assert client.post("/api/v1/schedule/slots", headers=headers, json=slot).status_code == 200


def test_cannot_edit_another_departments_ledger(client, db, seed_users):
    _, ledgers = _seed_dept_world(db)
    headers = _dept_admin(client)
    body = {"operational_state": "ON_LEAVE"}
    res = client.patch(f"/api/v1/schedule/ledger/{ledgers['ECE'].id}", headers=headers, json=body)
    assert res.status_code == 403
    res = client.patch(f"/api/v1/schedule/ledger/{ledgers['CSE'].id}", headers=headers, json=body)
    assert res.status_code == 200


def test_cannot_batch_mark_another_departments_attendance(client, db, seed_users):
    _, ledgers = _seed_dept_world(db)
    headers = _dept_admin(client)
    body = {
        "ledger_instance_id": ledgers["ECE"].id,
        "records": [
            {
                "ledger_instance_id": ledgers["ECE"].id,
                "student_id": "STU900",
                "marking_status": "PRESENT",
            }
        ],
    }
    assert client.post("/api/v1/attendance/batch", headers=headers, json=body).status_code == 403
    body["ledger_instance_id"] = ledgers["CSE"].id
    body["records"][0]["ledger_instance_id"] = ledgers["CSE"].id
    body["records"][0]["student_id"] = "STU001"
    assert client.post("/api/v1/attendance/batch", headers=headers, json=body).status_code == 200


def test_csv_upload_is_super_admin_only(client, db, seed_users):
    _seed_dept_world(db)
    headers = _dept_admin(client)
    res = client.post(
        "/api/v1/ingestion/upload-csv?cycle_id=1",
        headers=headers,
        files={"file": ("matrix.csv", b"header", "text/csv")},
    )
    assert res.status_code == 403


def test_super_admin_still_reaches_every_department(client, db, seed_users):
    _seed_dept_world(db)
    headers = login(client, "admin@test.internal", ADMIN_PASSWORD)
    res = client.get("/api/v1/users/", headers=headers)
    assert res.status_code == 200
    assert {"CSE", "ECE"} <= {u["department_code"] for u in res.json()}
    assert client.get("/api/v1/users/STU900", headers=headers).status_code == 200
