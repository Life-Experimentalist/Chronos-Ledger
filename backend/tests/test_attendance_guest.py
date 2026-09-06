# Copyright 2026 Chronos Ledger Contributors
# Licensed under the Apache License, Version 2.0
"""Attendance marking, reverse-RSVP absence flow, guest gate, and faculty location."""

import datetime

from app.models.db import (
    AcademicCycle,
    CourseOffering,
    DailyLedger,
    ReverseRsvpLog,
    VerificationLedger,
)
from tests.conftest import ADMIN_PASSWORD, FACULTY_PASSWORD, STUDENT_PASSWORD, login

TODAY = datetime.date.today()


def _make_ledger(db, instructor_id=None, with_geo=False):
    cycle = AcademicCycle(
        cycle_label="Odd 2026",
        date_bounds_start=TODAY - datetime.timedelta(days=30),
        date_bounds_end=TODAY + datetime.timedelta(days=90),
        operational_status=True,
    )
    db.add(cycle)
    db.flush()
    offering = CourseOffering(
        course_code="CS101",
        course_title="Intro to Computing",
        department_code="CSE",
        cycle_id=cycle.id,
    )
    db.add(offering)
    db.flush()
    ledger = DailyLedger(
        target_date=TODAY,
        course_offering_id=offering.id,
        active_instructor_id=instructor_id,
        target_room_identifier="LH-101",
    )
    if with_geo:
        ledger.latitude_target = 12.9716
        ledger.longitude_target = 77.5946
        ledger.altitude_target = 920.0
        ledger.precision_radius_meters = 15
    db.add(ledger)
    db.commit()
    return ledger


# -- Attendance marking -------------------------------------------------------


def test_student_marks_own_attendance(client, db, seed_users):
    ledger = _make_ledger(db)
    headers = login(client, "student@test.internal", STUDENT_PASSWORD)
    res = client.post(
        "/api/v1/attendance/mark",
        json={"ledger_instance_id": ledger.id, "student_id": "STU001", "marking_status": "PRESENT"},
        headers=headers,
    )
    assert res.status_code == 200
    row = db.query(VerificationLedger).filter_by(ledger_instance_id=ledger.id).one()
    assert row.student_id == "STU001"
    assert row.marking_status.value == "PRESENT"


def test_student_cannot_mark_for_another(client, db, seed_users):
    ledger = _make_ledger(db)
    headers = login(client, "student@test.internal", STUDENT_PASSWORD)
    res = client.post(
        "/api/v1/attendance/mark",
        json={"ledger_instance_id": ledger.id, "student_id": "STU999", "marking_status": "PRESENT"},
        headers=headers,
    )
    assert res.status_code == 403


def test_mark_unknown_ledger_is_404(client, seed_users):
    headers = login(client, "student@test.internal", STUDENT_PASSWORD)
    res = client.post(
        "/api/v1/attendance/mark",
        json={"ledger_instance_id": 9999, "student_id": "STU001", "marking_status": "PRESENT"},
        headers=headers,
    )
    assert res.status_code == 404


def test_geofence_rejects_far_student(client, db, seed_users):
    ledger = _make_ledger(db, with_geo=True)
    headers = login(client, "student@test.internal", STUDENT_PASSWORD)
    res = client.post(
        "/api/v1/attendance/mark",
        json={
            "ledger_instance_id": ledger.id,
            "student_id": "STU001",
            "marking_status": "PRESENT",
            "user_lat": 12.9816,  # about 1.1 km north of the target
            "user_lon": 77.5946,
            "user_alt": 920.0,
        },
        headers=headers,
    )
    assert res.status_code == 400
    assert "geofence" in res.json()["detail"].lower()


def test_geofence_accepts_student_at_target(client, db, seed_users):
    ledger = _make_ledger(db, with_geo=True)
    headers = login(client, "student@test.internal", STUDENT_PASSWORD)
    res = client.post(
        "/api/v1/attendance/mark",
        json={
            "ledger_instance_id": ledger.id,
            "student_id": "STU001",
            "marking_status": "PRESENT",
            "user_lat": 12.9716,
            "user_lon": 77.5946,
            "user_alt": 921.0,
        },
        headers=headers,
    )
    assert res.status_code == 200


def test_omitting_coordinates_bypasses_geofence(client, db, seed_users):
    # Documents current behavior: a geo-fenced ledger still accepts a mark with
    # no coordinates at all. Whether that should hard-fail is intake question Q9.
    ledger = _make_ledger(db, with_geo=True)
    headers = login(client, "student@test.internal", STUDENT_PASSWORD)
    res = client.post(
        "/api/v1/attendance/mark",
        json={"ledger_instance_id": ledger.id, "student_id": "STU001", "marking_status": "PRESENT"},
        headers=headers,
    )
    assert res.status_code == 200


def test_batch_mark_requires_assigned_instructor(client, db, seed_users):
    ledger = _make_ledger(db, instructor_id="FAC999")
    headers = login(client, "faculty@test.internal", FACULTY_PASSWORD)
    body = {
        "ledger_instance_id": ledger.id,
        "records": [
            {"ledger_instance_id": ledger.id, "student_id": "STU001", "marking_status": "PRESENT"}
        ],
    }
    res = client.post("/api/v1/attendance/batch", json=body, headers=headers)
    assert res.status_code == 403


def test_batch_mark_by_assigned_instructor(client, db, seed_users):
    ledger = _make_ledger(db, instructor_id="FAC001")
    headers = login(client, "faculty@test.internal", FACULTY_PASSWORD)
    body = {
        "ledger_instance_id": ledger.id,
        "records": [
            {"ledger_instance_id": ledger.id, "student_id": "STU001", "marking_status": "PRESENT"},
            {"ledger_instance_id": ledger.id, "student_id": "STU002", "marking_status": "ABSENT"},
        ],
    }
    res = client.post("/api/v1/attendance/batch", json=body, headers=headers)
    assert res.status_code == 200
    assert res.json()["count"] == 2
    assert db.query(VerificationLedger).filter_by(ledger_instance_id=ledger.id).count() == 2


# -- Reverse RSVP (absence) ---------------------------------------------------


def test_absence_without_manager_is_400(client, seed_users):
    headers = login(client, "faculty@test.internal", FACULTY_PASSWORD)
    res = client.post(
        "/api/v1/attendance/absence",
        json={"target_absence_date": str(TODAY), "context_justification": "Conference"},
        headers=headers,
    )
    assert res.status_code == 400
    assert "hierarchy" in res.json()["detail"].lower()


def test_absence_flow_submit_pending_decide(client, db, seed_users):
    seed_users["faculty"].reporting_line_manager = "ADM001"
    db.commit()
    ledger = _make_ledger(db, instructor_id="FAC001")

    fac = login(client, "faculty@test.internal", FACULTY_PASSWORD)
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
    # Approval flips the instructor's ledger for that date to ON_LEAVE.
    assert db.query(DailyLedger).filter_by(id=ledger.id).one().operational_state.value == "ON_LEAVE"


def test_absence_decide_requires_the_named_approver(client, db, seed_users):
    seed_users["faculty"].reporting_line_manager = "ADM001"
    db.commit()
    fac = login(client, "faculty@test.internal", FACULTY_PASSWORD)
    log_id = client.post(
        "/api/v1/attendance/absence",
        json={"target_absence_date": str(TODAY), "context_justification": "Travel"},
        headers=fac,
    ).json()["id"]
    stu = login(client, "student@test.internal", STUDENT_PASSWORD)
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
    "target_faculty_id": "FAC001",
    "visitation_intent": "Project discussion",
}


def test_guest_checkin_needs_no_auth(client, db, seed_users):
    # The kiosk endpoint is deliberately unauthenticated.
    res = client.post("/api/v1/guest/register-checkin", json=_GUEST)
    assert res.status_code == 200
    assert res.json()["registration_state"] == "PENDING_FACULTY_AUTH"

    fac = login(client, "faculty@test.internal", FACULTY_PASSWORD)
    pending = client.get("/api/v1/guest/pending", headers=fac).json()
    assert [p["guest_name"] for p in pending] == ["Ravi Verma"]


def test_guest_checkin_rejects_non_faculty_target(client, seed_users):
    res = client.post(
        "/api/v1/guest/register-checkin", json={**_GUEST, "target_faculty_id": "STU001"}
    )
    assert res.status_code == 404


def test_guest_decide_only_by_target_faculty(client, db, seed_users):
    entry_id = client.post("/api/v1/guest/register-checkin", json=_GUEST).json()["reference_token"]

    stu = login(client, "student@test.internal", STUDENT_PASSWORD)
    res = client.patch(
        f"/api/v1/guest/{entry_id}/decide", json={"decision": "VERIFIED_APPROVED"}, headers=stu
    )
    assert res.status_code == 404

    fac = login(client, "faculty@test.internal", FACULTY_PASSWORD)
    res = client.patch(
        f"/api/v1/guest/{entry_id}/decide", json={"decision": "VERIFIED_APPROVED"}, headers=fac
    )
    assert res.status_code == 200
    assert client.get("/api/v1/guest/pending", headers=fac).json() == []


def test_guest_directory_is_public(client, seed_users):
    res = client.get("/api/v1/guest/directory")
    assert res.status_code == 200
    names = [f["full_name"] for f in res.json()]
    assert seed_users["faculty"].full_name in names


# -- Faculty location (Redis-backed) -----------------------------------------


class _FakeRedis:
    def __init__(self, value=None):
        self.value = value

    def get(self, key):
        return self.value


def test_faculty_location_base_fallback(client, seed_users, monkeypatch):
    monkeypatch.setattr("app.api.v1.endpoints.schedule.get_redis", lambda: _FakeRedis())
    headers = login(client, "student@test.internal", STUDENT_PASSWORD)
    res = client.get("/api/v1/schedule/faculty/FAC001/location", headers=headers)
    assert res.status_code == 200
    assert res.json()["status"] == "Available / Unassigned"


def test_faculty_location_redis_override(client, seed_users, monkeypatch):
    monkeypatch.setattr(
        "app.api.v1.endpoints.schedule.get_redis", lambda: _FakeRedis("In a meeting")
    )
    headers = login(client, "student@test.internal", STUDENT_PASSWORD)
    res = client.get("/api/v1/schedule/faculty/FAC001/location", headers=headers)
    assert res.status_code == 200
    assert res.json()["status"] == "In a meeting"
    assert res.json()["resolved_location"] == "ISOLATED_CELL"


def test_all_faculty_locations(client, seed_users, monkeypatch):
    monkeypatch.setattr("app.api.v1.endpoints.schedule.get_redis", lambda: _FakeRedis())
    headers = login(client, "admin@test.internal", ADMIN_PASSWORD)
    res = client.get("/api/v1/schedule/faculty/all/locations", headers=headers)
    assert res.status_code == 200
    assert [f["faculty_id"] for f in res.json()] == ["FAC001"]
