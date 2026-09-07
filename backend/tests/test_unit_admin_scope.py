# Copyright 2026 Chronos Ledger Contributors
# Licensed under the Apache License, Version 2.0

"""A unit admin's reach stops at their own unit.

Q12: UNIT_ADMIN could previously list, create, and edit users in any
unit, schedule slots and edit ledgers for other units' activities,
batch-mark their attendance, and upload the institution-wide CSV matrix.
"""

import datetime

from app.core.security import hash_password
from app.models.db import (
    Activity,
    DailyLedger,
    InstitutionalRole,
    PlanningCycle,
    User,
)
from tests.conftest import ADMIN_PASSWORD, login

TODAY = datetime.date.today()
UNIT_ADMIN_PASSWORD = "UnitAdminPass123!"
_UNIT_ADMIN_HASH = hash_password(UNIT_ADMIN_PASSWORD)


def _seed_unit_world(db):
    """A CSE unit admin, an ECE member, and one offering + ledger per unit."""
    db.add_all(
        [
            User(
                id="DAD001",
                full_name="CSE Unit Admin",
                email_address="unitadmin@test.internal",
                credential_secure_hash=_UNIT_ADMIN_HASH,
                role_type=InstitutionalRole.UNIT_ADMIN,
                unit_code="CSE",
                initial_login_state=False,
            ),
            User(
                id="STU900",
                full_name="ECE Member",
                email_address="ece.member@test.internal",
                credential_secure_hash=_UNIT_ADMIN_HASH,
                role_type=InstitutionalRole.MEMBER,
                unit_code="ECE",
            ),
        ]
    )
    cycle = PlanningCycle(
        cycle_label="Scope 2026",
        date_bounds_start=TODAY - datetime.timedelta(days=30),
        date_bounds_end=TODAY + datetime.timedelta(days=90),
        operational_status=True,
    )
    db.add(cycle)
    db.flush()
    offerings = {}
    ledgers = {}
    for unit, code in (("CSE", "CS900"), ("ECE", "EC900")):
        offering = Activity(
            activity_code=code,
            activity_title=f"{unit} Activity",
            unit_code=unit,
            cycle_id=cycle.id,
        )
        db.add(offering)
        db.flush()
        ledger = DailyLedger(
            target_date=TODAY,
            activity_id=offering.id,
            target_room_identifier="LH-900",
        )
        db.add(ledger)
        db.flush()
        offerings[unit] = offering
        ledgers[unit] = ledger
    db.commit()
    return offerings, ledgers


def _unit_admin(client):
    return login(client, "unitadmin@test.internal", UNIT_ADMIN_PASSWORD)


def test_list_users_is_forced_to_own_unit(client, db, seed_users):
    _seed_unit_world(db)
    headers = _unit_admin(client)
    res = client.get("/api/v1/users/", headers=headers)
    assert res.status_code == 200
    units = {u["unit_code"] for u in res.json()}
    assert units == {"CSE"}
    # Asking for another unit explicitly changes nothing.
    res = client.get("/api/v1/users/?unit=ECE", headers=headers)
    assert res.status_code == 200
    assert res.json() == []


def test_cannot_create_user_in_another_unit(client, db, seed_users):
    _seed_unit_world(db)
    headers = _unit_admin(client)
    payload = {
        "id": "STU901",
        "full_name": "New Member",
        "email_address": "new.member@test.internal",
        "password": "MemberPass901!",
        "role_type": "MEMBER",
        "unit_code": "ECE",
    }
    assert client.post("/api/v1/users/", headers=headers, json=payload).status_code == 403
    payload["unit_code"] = "CSE"
    assert client.post("/api/v1/users/", headers=headers, json=payload).status_code == 201


def test_cannot_view_or_update_user_in_another_unit(client, db, seed_users):
    _seed_unit_world(db)
    headers = _unit_admin(client)
    assert client.get("/api/v1/users/STU900", headers=headers).status_code == 403
    res = client.patch("/api/v1/users/STU900", headers=headers, json={"full_name": "Renamed"})
    assert res.status_code == 403
    # And a user cannot be moved out of the admin's unit.
    res = client.patch("/api/v1/users/STU001", headers=headers, json={"unit_code": "ECE"})
    assert res.status_code == 403
    res = client.patch("/api/v1/users/STU001", headers=headers, json={"full_name": "Renamed"})
    assert res.status_code == 200


def test_cannot_schedule_slot_for_another_units_activity(client, db, seed_users):
    offerings, _ = _seed_unit_world(db)
    headers = _unit_admin(client)
    slot = {
        "day_of_week_index": 1,
        "time_window_start": "10:00:00",
        "time_window_end": "11:00:00",
        "activity_id": offerings["ECE"].id,
        "target_room_identifier": "LH-900",
    }
    assert client.post("/api/v1/schedule/slots", headers=headers, json=slot).status_code == 403
    slot["activity_id"] = offerings["CSE"].id
    assert client.post("/api/v1/schedule/slots", headers=headers, json=slot).status_code == 200


def test_cannot_edit_another_units_ledger(client, db, seed_users):
    _, ledgers = _seed_unit_world(db)
    headers = _unit_admin(client)
    body = {"operational_state": "ON_LEAVE"}
    res = client.patch(f"/api/v1/schedule/ledger/{ledgers['ECE'].id}", headers=headers, json=body)
    assert res.status_code == 403
    res = client.patch(f"/api/v1/schedule/ledger/{ledgers['CSE'].id}", headers=headers, json=body)
    assert res.status_code == 200


def test_cannot_batch_mark_another_units_attendance(client, db, seed_users):
    _, ledgers = _seed_unit_world(db)
    headers = _unit_admin(client)
    body = {
        "ledger_instance_id": ledgers["ECE"].id,
        "records": [
            {
                "ledger_instance_id": ledgers["ECE"].id,
                "member_id": "STU900",
                "marking_status": "PRESENT",
            }
        ],
    }
    assert client.post("/api/v1/attendance/batch", headers=headers, json=body).status_code == 403
    body["ledger_instance_id"] = ledgers["CSE"].id
    body["records"][0]["ledger_instance_id"] = ledgers["CSE"].id
    body["records"][0]["member_id"] = "STU001"
    assert client.post("/api/v1/attendance/batch", headers=headers, json=body).status_code == 200


def test_csv_upload_is_super_admin_only(client, db, seed_users):
    _seed_unit_world(db)
    headers = _unit_admin(client)
    res = client.post(
        "/api/v1/ingestion/upload-csv?cycle_id=1",
        headers=headers,
        files={"file": ("matrix.csv", b"header", "text/csv")},
    )
    assert res.status_code == 403


def test_super_admin_still_reaches_every_unit(client, db, seed_users):
    _seed_unit_world(db)
    headers = login(client, "admin@test.internal", ADMIN_PASSWORD)
    res = client.get("/api/v1/users/", headers=headers)
    assert res.status_code == 200
    assert {"CSE", "ECE"} <= {u["unit_code"] for u in res.json()}
    assert client.get("/api/v1/users/STU900", headers=headers).status_code == 200
