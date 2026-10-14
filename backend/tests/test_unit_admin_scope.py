# Copyright 2026 Chronos Ledger Contributors
# Licensed under the Apache License, Version 2.0

"""A unit admin's reach stops at their own unit.

Q12: UNIT_ADMIN could previously list, create, and edit users in any
unit, schedule slots and edit ledgers for other units' activities,
batch-mark their attendance, and upload the institution-wide CSV matrix.
"""

import datetime

from app.core.recurrence import weekly_rule
from app.core.security import hash_password
from app.core.time import org_today
from app.models.db import (
    Activity,
    DailyLedger,
    InstitutionalRole,
    PlanningCycle,
    Reservation,
    ReservationStatus,
    Resource,
    User,
)
from app.services.resource import get_or_create_room
from tests.conftest import ADMIN_PASSWORD, login

TODAY = org_today()
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
            resource_id=get_or_create_room("LH-900", db).id,
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
        "rrule": weekly_rule(1),
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


def test_csv_upload_is_org_admin_only(client, db, seed_users):
    _seed_unit_world(db)
    headers = _unit_admin(client)
    res = client.post(
        "/api/v1/ingestion/upload-csv?cycle_id=1",
        headers=headers,
        files={"file": ("matrix.csv", b"header", "text/csv")},
    )
    assert res.status_code == 403


def test_org_admin_still_reaches_every_unit(client, db, seed_users):
    _seed_unit_world(db)
    headers = login(client, "admin@test.internal", ADMIN_PASSWORD)
    res = client.get("/api/v1/users/", headers=headers)
    assert res.status_code == 200
    assert {"CSE", "ECE"} <= {u["unit_code"] for u in res.json()}
    assert client.get("/api/v1/users/STU900", headers=headers).status_code == 200


def test_cannot_single_mark_another_units_attendance(client, db, seed_users):
    """The mirror of the batch test above.

    /attendance/batch was scoped when this file was written; /attendance/mark
    was not, so the same unit admin could reach any unit one record at a time.
    """
    _, ledgers = _seed_unit_world(db)
    headers = _unit_admin(client)
    body = {
        "ledger_instance_id": ledgers["ECE"].id,
        "member_id": "STU900",
        "marking_status": "PRESENT",
    }
    assert client.post("/api/v1/attendance/mark", headers=headers, json=body).status_code == 403
    body["ledger_instance_id"] = ledgers["CSE"].id
    body["member_id"] = "STU001"
    assert client.post("/api/v1/attendance/mark", headers=headers, json=body).status_code == 200


# -- Rooms, the ledger and the conflict report --------------------------------

TOMORROW = TODAY + datetime.timedelta(days=1)
LAST = TOMORROW + datetime.timedelta(days=6)


def _room(db, code, unit_code=None):
    room = Resource(code=code, label=code, resource_type="ROOM", unit_code=unit_code)
    db.add(room)
    db.commit()
    return room


def _org_admin(client):
    return login(client, "admin@test.internal", ADMIN_PASSWORD)


def _book(client, headers, resource_id, key="booking-0000-0001"):
    return client.post(
        f"/api/v1/resources/{resource_id}/reservations",
        json={"date": str(TOMORROW), "start": "14:00", "end": "15:00", "purpose": "Ward round"},
        headers={**headers, "Idempotency-Key": key},
    )


def test_cannot_hold_another_units_resource(client, db, seed_users):
    _seed_unit_world(db)
    cse_room = _room(db, "CSE-1", "CSE")
    ece_room = _room(db, "ECE-1", "ECE")
    shared = _room(db, "SHARED-1")
    headers = _unit_admin(client)

    res = _book(client, headers, ece_room.id, key="ece-room-0001")
    assert res.status_code == 403
    assert res.json()["code"] == "OUTSIDE_UNIT"
    assert _book(client, headers, cse_room.id, key="cse-room-0001").status_code == 201
    # A room with no unit is shared by the whole organization.
    assert _book(client, headers, shared.id, key="shared-room-01").status_code == 201

    # An organization admin holds any of them.
    admin = _org_admin(client)
    assert _book(client, admin, ece_room.id, key="ece-room-0002").status_code == 201


def test_cannot_put_a_slot_in_another_units_room(client, db, seed_users):
    offerings, _ = _seed_unit_world(db)
    _room(db, "ECE-2", "ECE")
    _room(db, "CSE-2", "CSE")
    headers = _unit_admin(client)
    slot = {
        "rrule": weekly_rule(1),
        "time_window_start": "10:00:00",
        "time_window_end": "11:00:00",
        "activity_id": offerings["CSE"].id,
        "target_room_identifier": "ECE-2",
    }
    res = client.post("/api/v1/schedule/slots", headers=headers, json=slot)
    assert res.status_code == 403
    assert res.json()["code"] == "OUTSIDE_UNIT"
    slot["target_room_identifier"] = "CSE-2"
    created = client.post("/api/v1/schedule/slots", headers=headers, json=slot)
    assert created.status_code == 200

    # Moving the slot into the other unit's room is refused the same way.
    url = f"/api/v1/schedule/slots/{created.json()['id']}"
    res = client.patch(url, headers=headers, json={"target_room_identifier": "ECE-2"})
    assert res.status_code == 403
    assert res.json()["code"] == "OUTSIDE_UNIT"

    # An organization admin puts a slot in any room.
    slot["target_room_identifier"] = "ECE-2"
    slot["time_window_start"], slot["time_window_end"] = "12:00:00", "13:00:00"
    admin = _org_admin(client)
    assert client.post("/api/v1/schedule/slots", headers=admin, json=slot).status_code == 200


def test_ledger_reads_are_narrowed_to_the_unit(client, db, seed_users):
    _seed_unit_world(db)
    params = {"from": str(TODAY), "to": str(TODAY)}
    headers = _unit_admin(client)
    rows = client.get("/api/v1/schedule/ledger", params=params, headers=headers)
    assert [r["activity_code"] for r in rows.json()] == ["CS900"]
    today = client.get("/api/v1/schedule/ledger/today", headers=headers)
    assert [r["activity_code"] for r in today.json()] == ["CS900"]

    rows = client.get("/api/v1/schedule/ledger", params=params, headers=_org_admin(client))
    assert {r["activity_code"] for r in rows.json()} == {"CS900", "EC900"}


def _clash(db, activity, room):
    db.add(
        DailyLedger(
            target_date=TOMORROW,
            time_window_start=datetime.time(9),
            time_window_end=datetime.time(10),
            activity_id=activity.id,
            resource_id=room.id,
        )
    )
    db.commit()


def _hold(db, room, key):
    db.add(
        Reservation(
            resource_id=room.id,
            reserved_date=TOMORROW,
            time_window_start=datetime.time(14),
            time_window_end=datetime.time(15),
            purpose="Written straight in",
            requested_by_id="ADM001",
            idempotency_key=key,
            request_fingerprint="x" * 64,
            status=ReservationStatus.HELD,
        )
    )
    db.commit()


def _seed_clashes(db):
    """Four clashes: CSE against ECE, ECE alone, two holds of a CSE room, two of a shared room."""
    offerings, _ = _seed_unit_world(db)
    cse, ece = offerings["CSE"], offerings["ECE"]
    both = _room(db, "CLASH-BOTH")
    ece_only = _room(db, "CLASH-ECE")
    cse_room = _room(db, "CLASH-CSE", "CSE")
    shared = _room(db, "CLASH-SHARED")
    _clash(db, cse, both)
    _clash(db, ece, both)
    _clash(db, ece, ece_only)
    _clash(db, ece, ece_only)
    _hold(db, cse_room, "cse-hold-0001")
    _hold(db, cse_room, "cse-hold-0002")
    _hold(db, shared, "shared-hold-01")
    _hold(db, shared, "shared-hold-02")
    return {"both": both.id, "ece_only": ece_only.id, "cse_room": cse_room.id, "shared": shared.id}


def _conflicts(client, headers):
    res = client.get(
        "/api/v1/schedule/conflicts",
        params={"from": str(TOMORROW), "to": str(LAST)},
        headers=headers,
    )
    assert res.status_code == 200
    return res.json()["conflicts"]


def test_conflict_report_keeps_the_clashes_that_touch_the_unit(client, db, seed_users):
    rooms = _seed_clashes(db)
    found = _conflicts(client, _unit_admin(client))
    assert {c["resource_id"] for c in found} == {rooms["both"], rooms["cse_room"]}
    # A clash with another unit comes back whole, with the other unit's day in it.
    cross = next(c for c in found if c["resource_id"] == rooms["both"])
    assert len(cross["items"]) == 2
    assert len({item["activity_id"] for item in cross["items"]}) == 2


def test_conflict_report_is_whole_for_an_org_admin(client, db, seed_users):
    rooms = _seed_clashes(db)
    found = _conflicts(client, _org_admin(client))
    assert {c["resource_id"] for c in found} == set(rooms.values())


def test_unit_admin_without_a_unit_reaches_nothing(client, db, seed_users):
    """The column compared with None reads IS NULL, which is every row with no unit."""
    _seed_clashes(db)
    db.add_all(
        [
            User(
                id="DAD002",
                full_name="Unit Admin Without A Unit",
                email_address="nounit@test.internal",
                credential_secure_hash=_UNIT_ADMIN_HASH,
                role_type=InstitutionalRole.UNIT_ADMIN,
                unit_code=None,
                initial_login_state=False,
            ),
            User(
                id="STU902",
                full_name="Member Without A Unit",
                email_address="nounit.member@test.internal",
                credential_secure_hash=_UNIT_ADMIN_HASH,
                role_type=InstitutionalRole.MEMBER,
            ),
        ]
    )
    db.commit()
    headers = login(client, "nounit@test.internal", UNIT_ADMIN_PASSWORD)

    assert client.get("/api/v1/users/", headers=headers).json() == []
    assert client.get("/api/v1/users/STU902", headers=headers).status_code == 403
    assert _conflicts(client, headers) == []
    params = {"from": str(TODAY), "to": str(TODAY)}
    assert client.get("/api/v1/schedule/ledger", params=params, headers=headers).json() == []
