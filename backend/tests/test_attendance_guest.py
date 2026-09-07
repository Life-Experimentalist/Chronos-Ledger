# Copyright 2026 Chronos Ledger Contributors
# Licensed under the Apache License, Version 2.0
"""Attendance marking, reverse-RSVP absence flow, guest gate, and staff location."""

import datetime

import pytest

from app.models.db import (
    Activity,
    DailyLedger,
    PlanningCycle,
    ReverseRsvpLog,
    VerificationLedger,
)
from tests.conftest import ADMIN_PASSWORD, MEMBER_PASSWORD, STAFF_PASSWORD, login

TODAY = datetime.date.today()


def _make_ledger(db, lead_id=None, with_geo=False, alt_target=920.0):
    cycle = PlanningCycle(
        cycle_label="Odd 2026",
        date_bounds_start=TODAY - datetime.timedelta(days=30),
        date_bounds_end=TODAY + datetime.timedelta(days=90),
        operational_status=True,
    )
    db.add(cycle)
    db.flush()
    offering = Activity(
        activity_code="CS101",
        activity_title="Intro to Computing",
        unit_code="CSE",
        cycle_id=cycle.id,
    )
    db.add(offering)
    db.flush()
    ledger = DailyLedger(
        target_date=TODAY,
        activity_id=offering.id,
        active_lead_id=lead_id,
        target_room_identifier="LH-101",
    )
    if with_geo:
        ledger.latitude_target = 12.9716
        ledger.longitude_target = 77.5946
        ledger.altitude_target = alt_target
        ledger.precision_radius_meters = 15
    db.add(ledger)
    db.commit()
    return ledger


# -- Attendance marking -------------------------------------------------------


def test_member_marks_own_attendance(client, db, seed_users):
    ledger = _make_ledger(db)
    headers = login(client, "member@test.internal", MEMBER_PASSWORD)
    res = client.post(
        "/api/v1/attendance/mark",
        json={"ledger_instance_id": ledger.id, "member_id": "STU001", "marking_status": "PRESENT"},
        headers=headers,
    )
    assert res.status_code == 200
    row = db.query(VerificationLedger).filter_by(ledger_instance_id=ledger.id).one()
    assert row.member_id == "STU001"
    assert row.marking_status.value == "PRESENT"


def test_member_cannot_mark_for_another(client, db, seed_users):
    ledger = _make_ledger(db)
    headers = login(client, "member@test.internal", MEMBER_PASSWORD)
    res = client.post(
        "/api/v1/attendance/mark",
        json={"ledger_instance_id": ledger.id, "member_id": "STU999", "marking_status": "PRESENT"},
        headers=headers,
    )
    assert res.status_code == 403


def test_mark_unknown_ledger_is_404(client, seed_users):
    headers = login(client, "member@test.internal", MEMBER_PASSWORD)
    res = client.post(
        "/api/v1/attendance/mark",
        json={"ledger_instance_id": 9999, "member_id": "STU001", "marking_status": "PRESENT"},
        headers=headers,
    )
    assert res.status_code == 404


def test_geofence_rejects_far_member(client, db, seed_users):
    ledger = _make_ledger(db, with_geo=True)
    headers = login(client, "member@test.internal", MEMBER_PASSWORD)
    res = client.post(
        "/api/v1/attendance/mark",
        json={
            "ledger_instance_id": ledger.id,
            "member_id": "STU001",
            "marking_status": "PRESENT",
            "user_lat": 12.9816,  # about 1.1 km north of the target
            "user_lon": 77.5946,
            "user_alt": 920.0,
        },
        headers=headers,
    )
    assert res.status_code == 400
    assert "geofence" in res.json()["detail"].lower()


def test_geofence_accepts_member_at_target(client, db, seed_users):
    ledger = _make_ledger(db, with_geo=True)
    headers = login(client, "member@test.internal", MEMBER_PASSWORD)
    res = client.post(
        "/api/v1/attendance/mark",
        json={
            "ledger_instance_id": ledger.id,
            "member_id": "STU001",
            "marking_status": "PRESENT",
            "user_lat": 12.9716,
            "user_lon": 77.5946,
            "user_alt": 921.0,
        },
        headers=headers,
    )
    assert res.status_code == 200


def test_omitting_coordinates_is_rejected_on_geofenced_session(client, db, seed_users):
    ledger = _make_ledger(db, with_geo=True)
    headers = login(client, "member@test.internal", MEMBER_PASSWORD)
    res = client.post(
        "/api/v1/attendance/mark",
        json={"ledger_instance_id": ledger.id, "member_id": "STU001", "marking_status": "PRESENT"},
        headers=headers,
    )
    assert res.status_code == 400
    assert "geo-fenced" in res.json()["detail"]


def test_geofence_accepts_member_without_altitude(client, db, seed_users):
    """A device that reports no altitude must still be able to check in.

    Laptops, and any phone on a network-based fix, return altitude: null. The
    horizontal radius is the real fence; the floor check is a bonus when the
    hardware can supply it, never a precondition for marking attendance.
    """
    ledger = _make_ledger(db, with_geo=True)
    headers = login(client, "member@test.internal", MEMBER_PASSWORD)
    res = client.post(
        "/api/v1/attendance/mark",
        json={
            "ledger_instance_id": ledger.id,
            "member_id": "STU001",
            "marking_status": "PRESENT",
            "user_lat": 12.9716,
            "user_lon": 77.5946,
        },
        headers=headers,
    )
    assert res.status_code == 200, res.text


def test_geofence_still_rejects_far_member_without_altitude(client, db, seed_users):
    ledger = _make_ledger(db, with_geo=True)
    headers = login(client, "member@test.internal", MEMBER_PASSWORD)
    res = client.post(
        "/api/v1/attendance/mark",
        json={
            "ledger_instance_id": ledger.id,
            "member_id": "STU001",
            "marking_status": "PRESENT",
            "user_lat": 12.9816,
            "user_lon": 77.5946,
        },
        headers=headers,
    )
    assert res.status_code == 400
    assert "geofence" in res.json()["detail"].lower()


def test_geofence_rejects_wrong_floor_when_altitude_is_supplied(client, db, seed_users):
    ledger = _make_ledger(db, with_geo=True)
    headers = login(client, "member@test.internal", MEMBER_PASSWORD)
    res = client.post(
        "/api/v1/attendance/mark",
        json={
            "ledger_instance_id": ledger.id,
            "member_id": "STU001",
            "marking_status": "PRESENT",
            "user_lat": 12.9716,
            "user_lon": 77.5946,
            "user_alt": 970.0,  # 50 m above target, several floors up
        },
        headers=headers,
    )
    assert res.status_code == 400
    assert "geofence" in res.json()["detail"].lower()


def test_geofence_engages_when_the_ledger_has_no_altitude_target(client, db, seed_users):
    """lat/lon alone must fence.

    Requiring all three targets meant an admin who left the optional altitude
    blank silently got no fence at all.
    """
    ledger = _make_ledger(db, with_geo=True, alt_target=None)
    headers = login(client, "member@test.internal", MEMBER_PASSWORD)
    res = client.post(
        "/api/v1/attendance/mark",
        json={
            "ledger_instance_id": ledger.id,
            "member_id": "STU001",
            "marking_status": "PRESENT",
            "user_lat": 12.9816,
            "user_lon": 77.5946,
        },
        headers=headers,
    )
    assert res.status_code == 400
    assert "geofence" in res.json()["detail"].lower()


def test_missing_longitude_is_rejected_on_geofenced_session(client, db, seed_users):
    ledger = _make_ledger(db, with_geo=True)
    headers = login(client, "member@test.internal", MEMBER_PASSWORD)
    res = client.post(
        "/api/v1/attendance/mark",
        json={
            "ledger_instance_id": ledger.id,
            "member_id": "STU001",
            "marking_status": "PRESENT",
            "user_lat": 12.9716,
        },
        headers=headers,
    )
    assert res.status_code == 400
    assert "geo-fenced" in res.json()["detail"]


def test_batch_mark_requires_assigned_lead(client, db, seed_users):
    ledger = _make_ledger(db, lead_id="FAC999")
    headers = login(client, "staff@test.internal", STAFF_PASSWORD)
    body = {
        "ledger_instance_id": ledger.id,
        "records": [
            {"ledger_instance_id": ledger.id, "member_id": "STU001", "marking_status": "PRESENT"}
        ],
    }
    res = client.post("/api/v1/attendance/batch", json=body, headers=headers)
    assert res.status_code == 403


def test_batch_mark_by_assigned_lead(client, db, seed_users):
    ledger = _make_ledger(db, lead_id="FAC001")
    headers = login(client, "staff@test.internal", STAFF_PASSWORD)
    body = {
        "ledger_instance_id": ledger.id,
        "records": [
            {"ledger_instance_id": ledger.id, "member_id": "STU001", "marking_status": "PRESENT"},
            {"ledger_instance_id": ledger.id, "member_id": "STU002", "marking_status": "ABSENT"},
        ],
    }
    res = client.post("/api/v1/attendance/batch", json=body, headers=headers)
    assert res.status_code == 200
    assert res.json()["count"] == 2
    assert db.query(VerificationLedger).filter_by(ledger_instance_id=ledger.id).count() == 2


# -- Reverse RSVP (absence) ---------------------------------------------------


def test_absence_without_manager_is_400(client, seed_users):
    headers = login(client, "staff@test.internal", STAFF_PASSWORD)
    res = client.post(
        "/api/v1/attendance/absence",
        json={"target_absence_date": str(TODAY), "context_justification": "Conference"},
        headers=headers,
    )
    assert res.status_code == 400
    assert "hierarchy" in res.json()["detail"].lower()


def test_absence_flow_submit_pending_decide(client, db, seed_users):
    seed_users["staff"].reporting_line_manager = "ADM001"
    db.commit()
    ledger = _make_ledger(db, lead_id="FAC001")

    fac = login(client, "staff@test.internal", STAFF_PASSWORD)
    res = client.post(
        "/api/v1/attendance/absence",
        json={"target_absence_date": str(TODAY), "context_justification": "Medical"},
        headers=fac,
    )
    assert res.status_code == 200
    log_id = res.json()["id"]
    assert res.json()["approval_state"] == "PENDING_VERIFICATION"

    adm = login(client, "admin@test.internal", ADMIN_PASSWORD)
    pending = client.get("/api/v1/attendance/absence/pending", headers=adm)
    assert [p["id"] for p in pending.json()] == [log_id]

    res = client.patch(
        f"/api/v1/attendance/absence/{log_id}/decide",
        json={"decision": "VERIFIED_APPROVED"},
        headers=adm,
    )
    assert res.status_code == 200
    db.expire_all()
    log = db.query(ReverseRsvpLog).filter_by(id=log_id).one()
    assert log.approval_state.value == "VERIFIED_APPROVED"
    # Approval flips the lead's ledger for that date to ON_LEAVE.
    assert db.query(DailyLedger).filter_by(id=ledger.id).one().operational_state.value == "ON_LEAVE"


def test_absence_decide_requires_the_named_approver(client, db, seed_users):
    seed_users["staff"].reporting_line_manager = "ADM001"
    db.commit()
    fac = login(client, "staff@test.internal", STAFF_PASSWORD)
    log_id = client.post(
        "/api/v1/attendance/absence",
        json={"target_absence_date": str(TODAY), "context_justification": "Travel"},
        headers=fac,
    ).json()["id"]
    stu = login(client, "member@test.internal", MEMBER_PASSWORD)
    res = client.patch(
        f"/api/v1/attendance/absence/{log_id}/decide",
        json={"decision": "VERIFIED_APPROVED"},
        headers=stu,
    )
    assert res.status_code == 404


# -- Guest gate ---------------------------------------------------------------

_GUEST = {
    "guest_name": "Ravi Verma",
    "contact_phone": "9000000000",
    "originating_body": "Acme Corp",
    "target_staff_id": "FAC001",
    "visitation_intent": "Project discussion",
}


def test_guest_checkin_works_with_a_kiosk_credential(client, db, seed_users, kiosk_key):
    res = client.post("/api/v1/guest/register-checkin", json=_GUEST, headers=kiosk_key)
    assert res.status_code == 200, res.text
    assert res.json()["registration_state"] == "PENDING_STAFF_AUTH"

    fac = login(client, "staff@test.internal", STAFF_PASSWORD)
    pending = client.get("/api/v1/guest/pending", headers=fac).json()
    assert [p["guest_name"] for p in pending] == ["Ravi Verma"]


def test_guest_checkin_refuses_an_anonymous_caller(client, seed_users):
    """Without this, anyone on the internet can fill the visitor log."""
    res = client.post("/api/v1/guest/register-checkin", json=_GUEST)
    assert res.status_code == 401


def test_guest_directory_refuses_an_anonymous_caller(client, seed_users):
    """The roster and every staff member's live presence used to be public."""
    res = client.get("/api/v1/guest/directory")
    assert res.status_code == 401


def test_guest_directory_works_with_a_kiosk_credential(client, seed_users, kiosk_key):
    res = client.get("/api/v1/guest/directory", headers=kiosk_key)
    assert res.status_code == 200, res.text
    names = [f["full_name"] for f in res.json()]
    assert seed_users["staff"].full_name in names


def test_guest_directory_refuses_a_one_character_search(client, seed_users, kiosk_key):
    """A single letter walks the whole roster alphabetically."""
    res = client.get("/api/v1/guest/directory", params={"name": "a"}, headers=kiosk_key)
    assert res.status_code == 422


@pytest.mark.parametrize(
    "field,value",
    [
        ("guest_name", "R" * 101),
        ("originating_body", "A" * 101),
        ("visitation_intent", "P" * 501),
        ("contact_phone", "9" * 21),
        ("contact_phone", "not-a-phone-number"),
    ],
)
def test_guest_checkin_bounds_every_field(client, seed_users, kiosk_key, field, value):
    res = client.post(
        "/api/v1/guest/register-checkin", json={**_GUEST, field: value}, headers=kiosk_key
    )
    assert res.status_code == 422


def test_guest_checkin_rejects_non_staff_target(client, seed_users, kiosk_key):
    res = client.post(
        "/api/v1/guest/register-checkin",
        json={**_GUEST, "target_staff_id": "STU001"},
        headers=kiosk_key,
    )
    assert res.status_code == 404


def test_guest_decide_only_by_target_staff(client, db, seed_users, kiosk_key):
    entry_id = client.post("/api/v1/guest/register-checkin", json=_GUEST, headers=kiosk_key).json()[
        "reference_token"
    ]

    stu = login(client, "member@test.internal", MEMBER_PASSWORD)
    res = client.patch(
        f"/api/v1/guest/{entry_id}/decide", json={"decision": "VERIFIED_APPROVED"}, headers=stu
    )
    assert res.status_code == 404

    fac = login(client, "staff@test.internal", STAFF_PASSWORD)
    res = client.patch(
        f"/api/v1/guest/{entry_id}/decide", json={"decision": "VERIFIED_APPROVED"}, headers=fac
    )
    assert res.status_code == 200
    assert client.get("/api/v1/guest/pending", headers=fac).json() == []


# -- Staff location (Redis-backed) -----------------------------------------


class _FakeRedis:
    def __init__(self, value=None):
        self.value = value

    def get(self, key):
        return self.value


def test_staff_location_base_fallback(client, seed_users, monkeypatch):
    monkeypatch.setattr("app.api.v1.endpoints.schedule.get_redis", lambda: _FakeRedis())
    headers = login(client, "member@test.internal", MEMBER_PASSWORD)
    res = client.get("/api/v1/schedule/staff/FAC001/location", headers=headers)
    assert res.status_code == 200
    assert res.json()["status"] == "Available / Unassigned"


def test_staff_location_redis_override(client, seed_users, monkeypatch):
    monkeypatch.setattr(
        "app.api.v1.endpoints.schedule.get_redis", lambda: _FakeRedis("In a meeting")
    )
    headers = login(client, "member@test.internal", MEMBER_PASSWORD)
    res = client.get("/api/v1/schedule/staff/FAC001/location", headers=headers)
    assert res.status_code == 200
    assert res.json()["status"] == "In a meeting"
    assert res.json()["resolved_location"] == "ISOLATED_CELL"


def test_all_staff_locations(client, seed_users, monkeypatch):
    monkeypatch.setattr("app.api.v1.endpoints.schedule.get_redis", lambda: _FakeRedis())
    headers = login(client, "admin@test.internal", ADMIN_PASSWORD)
    res = client.get("/api/v1/schedule/staff/all/locations", headers=headers)
    assert res.status_code == 200
    assert [f["staff_id"] for f in res.json()] == ["FAC001"]


def test_staff_cannot_single_mark_a_ledger_they_do_not_lead(client, db, seed_users):
    """Every check on /mark sat inside `if role == MEMBER`.

    The else branch was empty, so any authenticated non-member could mark any
    member on any ledger. /batch has always required lead or in-scope admin.
    """
    ledger = _make_ledger(db, lead_id="FAC999")
    headers = login(client, "staff@test.internal", STAFF_PASSWORD)
    res = client.post(
        "/api/v1/attendance/mark",
        json={"ledger_instance_id": ledger.id, "member_id": "STU001", "marking_status": "PRESENT"},
        headers=headers,
    )
    assert res.status_code == 403
    assert db.query(VerificationLedger).filter_by(ledger_instance_id=ledger.id).count() == 0


def test_staff_lead_can_single_mark_their_own_ledger(client, db, seed_users):
    ledger = _make_ledger(db, lead_id="FAC001")
    headers = login(client, "staff@test.internal", STAFF_PASSWORD)
    res = client.post(
        "/api/v1/attendance/mark",
        json={"ledger_instance_id": ledger.id, "member_id": "STU001", "marking_status": "PRESENT"},
        headers=headers,
    )
    assert res.status_code == 200, res.text


def test_substitute_lead_can_single_mark(client, db, seed_users):
    ledger = _make_ledger(db, lead_id="FAC999")
    ledger.substitute_lead_id = "FAC001"
    db.commit()
    headers = login(client, "staff@test.internal", STAFF_PASSWORD)
    res = client.post(
        "/api/v1/attendance/mark",
        json={"ledger_instance_id": ledger.id, "member_id": "STU001", "marking_status": "PRESENT"},
        headers=headers,
    )
    assert res.status_code == 200, res.text


def test_super_admin_can_single_mark_any_ledger(client, db, seed_users):
    ledger = _make_ledger(db, lead_id="FAC999")
    headers = login(client, "admin@test.internal", ADMIN_PASSWORD)
    res = client.post(
        "/api/v1/attendance/mark",
        json={"ledger_instance_id": ledger.id, "member_id": "STU001", "marking_status": "PRESENT"},
        headers=headers,
    )
    assert res.status_code == 200, res.text
