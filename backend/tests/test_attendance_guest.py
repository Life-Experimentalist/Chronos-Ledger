# Copyright 2026 Chronos Ledger Contributors
# Licensed under the Apache License, Version 2.0
"""Attendance marking, reverse-RSVP absence flow, guest gate, and staff location."""

import datetime
import json

import pytest
import redis
from pydantic import ValidationError

from app.core.config import Settings, get_settings
from app.core.time import org_today
from app.core.websocket_manager import socket_broker
from app.models.db import (
    Activity,
    DailyLedger,
    InstitutionalRole,
    PlanningCycle,
    Resource,
    ResourceType,
    ReverseRsvpLog,
    User,
    VerificationLedger,
)
from tests.conftest import ADMIN_PASSWORD, MEMBER_PASSWORD, STAFF_PASSWORD, login

TODAY = org_today()


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


def _second_ledger(db, first, lead_id="FAC999"):
    """Another session on the same day, run by somebody else."""
    offering = Activity(
        activity_code="CS102",
        activity_title="Data Structures",
        unit_code="CSE",
        cycle_id=first.activity.cycle_id,
    )
    db.add(offering)
    db.flush()
    ledger = DailyLedger(target_date=TODAY, activity_id=offering.id, active_lead_id=lead_id)
    db.add(ledger)
    db.commit()
    return ledger


def _add_member(db, member_id):
    db.add(
        User(
            id=member_id,
            full_name=member_id,
            email_address=f"{member_id.lower()}@test.internal",
            credential_secure_hash="not-a-real-hash",
            role_type=InstitutionalRole.MEMBER,
            unit_code="CSE",
        )
    )
    db.commit()


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


def _mark_at_the_target(client, ledger, **fix):
    headers = login(client, "member@test.internal", MEMBER_PASSWORD)
    return client.post(
        "/api/v1/attendance/mark",
        json={
            "ledger_instance_id": ledger.id,
            "member_id": "STU001",
            "marking_status": "PRESENT",
            "user_lat": 12.9716,
            "user_lon": 77.5946,
            **fix,
        },
        headers=headers,
    )


@pytest.fixture()
def accuracy_factor(monkeypatch):
    def set_factor(value):
        monkeypatch.setenv("GEOFENCE_ACCURACY_FACTOR", value)
        get_settings.cache_clear()

    yield set_factor
    get_settings.cache_clear()


def test_a_fix_too_coarse_for_the_fence_is_refused(client, db, seed_users):
    """A point inside a 15 m fence proves little when it could be 80 m off."""
    ledger = _make_ledger(db, with_geo=True)
    res = _mark_at_the_target(client, ledger, user_accuracy=80.0)
    assert res.status_code == 400
    assert res.json()["detail"] == (
        "Location accuracy of 80 m is too coarse for this session's 15 m fence; the limit is 30 m"
    )
    assert db.query(VerificationLedger).count() == 0


def test_a_fix_within_the_limit_is_marked(client, db, seed_users):
    ledger = _make_ledger(db, with_geo=True)
    assert _mark_at_the_target(client, ledger, user_accuracy=30.0).status_code == 200


def test_a_mark_that_reports_no_accuracy_is_not_refused_for_it(client, db, seed_users):
    ledger = _make_ledger(db, with_geo=True)
    assert _mark_at_the_target(client, ledger).status_code == 200


def test_the_limit_follows_the_factor(client, db, seed_users, accuracy_factor):
    accuracy_factor("1")
    ledger = _make_ledger(db, with_geo=True)
    assert _mark_at_the_target(client, ledger, user_accuracy=20.0).status_code == 400


def test_a_factor_of_zero_turns_the_accuracy_check_off(client, db, seed_users, accuracy_factor):
    accuracy_factor("0")
    ledger = _make_ledger(db, with_geo=True)
    assert _mark_at_the_target(client, ledger, user_accuracy=500.0).status_code == 200


def test_a_negative_factor_is_refused_at_startup():
    with pytest.raises(ValidationError, match="GEOFENCE_ACCURACY_FACTOR"):
        Settings(geofence_accuracy_factor=-1)


@pytest.mark.parametrize("accuracy", [-1, "inf", "nan"])
def test_an_accuracy_that_is_not_a_distance_is_refused(client, db, seed_users, accuracy):
    ledger = _make_ledger(db, with_geo=True)
    assert _mark_at_the_target(client, ledger, user_accuracy=accuracy).status_code == 422


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


def _put_in_room(db, ledger, lat=12.9716, lon=77.5946, alt=920.0):
    """Give the ledger a room that knows where it is."""
    room = Resource(
        code="LH-101",
        label="LH-101",
        resource_type=ResourceType.ROOM,
        latitude=lat,
        longitude=lon,
        altitude_target=alt,
    )
    db.add(room)
    db.flush()
    ledger.resource_id = room.id
    db.commit()
    return room


def test_the_room_fences_the_session_when_the_day_says_nothing(client, db, seed_users):
    """The first way a fence can actually be switched on.

    Nothing has ever written daily_ledger.latitude_target: the only writes in
    the codebase set it to None. So until a room could carry coordinates and
    the check could fall back to them, this branch was unreachable through
    the API and every fenced session was in fact unfenced.
    """
    ledger = _make_ledger(db)
    _put_in_room(db, ledger)
    headers = login(client, "member@test.internal", MEMBER_PASSWORD)
    res = client.post(
        "/api/v1/attendance/mark",
        json={
            "ledger_instance_id": ledger.id,
            "member_id": "STU001",
            "marking_status": "PRESENT",
            "user_lat": 12.9816,  # about 1.1 km north of the room
            "user_lon": 77.5946,
            "user_alt": 920.0,
        },
        headers=headers,
    )
    assert res.status_code == 400
    assert "geofence" in res.json()["detail"].lower()


def test_a_member_in_the_room_is_marked(client, db, seed_users):
    ledger = _make_ledger(db)
    _put_in_room(db, ledger)
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
    assert res.status_code == 200, res.text
    assert db.query(VerificationLedger).filter_by(ledger_instance_id=ledger.id).count() == 1


def test_the_day_overrides_the_room_it_is_normally_in(client, db, seed_users):
    """One day held somewhere else is what the ledger's own copy is for.

    The room here is a kilometre from where the day says it is. A member
    standing at the day's coordinates is present; the room's must not be
    consulted at all, or the override would fence people into both places.
    """
    ledger = _make_ledger(db, with_geo=True)
    _put_in_room(db, ledger, lat=12.9816, lon=77.5946)
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
    assert res.status_code == 200, res.text


def test_a_room_with_no_coordinates_leaves_the_session_unfenced(client, db, seed_users):
    """A room nobody has placed yet must not start refusing marks."""
    ledger = _make_ledger(db)
    _put_in_room(db, ledger, lat=None, lon=None, alt=None)
    headers = login(client, "member@test.internal", MEMBER_PASSWORD)
    res = client.post(
        "/api/v1/attendance/mark",
        json={"ledger_instance_id": ledger.id, "member_id": "STU001", "marking_status": "PRESENT"},
        headers=headers,
    )
    assert res.status_code == 200, res.text


def test_the_room_altitude_is_not_mixed_with_the_day_coordinates(client, db, seed_users):
    """The triple comes from one source or the other, never half of each.

    The day names lat/lon and no altitude. The room, several floors below,
    names one. Reading the room's altitude against the day's position would
    reject a member standing exactly where the day says to stand.
    """
    ledger = _make_ledger(db, with_geo=True, alt_target=None)
    _put_in_room(db, ledger, alt=850.0)
    headers = login(client, "member@test.internal", MEMBER_PASSWORD)
    res = client.post(
        "/api/v1/attendance/mark",
        json={
            "ledger_instance_id": ledger.id,
            "member_id": "STU001",
            "marking_status": "PRESENT",
            "user_lat": 12.9716,
            "user_lon": 77.5946,
            "user_alt": 920.0,
        },
        headers=headers,
    )
    assert res.status_code == 200, res.text


def test_an_admin_can_place_a_room_and_the_fence_starts_working(client, db, seed_users):
    """End to end: the route that switches geofencing on."""
    ledger = _make_ledger(db)
    room = _put_in_room(db, ledger, lat=None, lon=None, alt=None)
    admin = login(client, "admin@test.internal", ADMIN_PASSWORD)
    placed = client.patch(
        f"/api/v1/resources/{room.id}",
        json={"latitude": 12.9716, "longitude": 77.5946, "altitude_target": 920.0},
        headers=admin,
    )
    assert placed.status_code == 200, placed.text

    headers = login(client, "member@test.internal", MEMBER_PASSWORD)
    res = client.post(
        "/api/v1/attendance/mark",
        json={
            "ledger_instance_id": ledger.id,
            "member_id": "STU001",
            "marking_status": "PRESENT",
            "user_lat": 12.9816,
            "user_lon": 77.5946,
            "user_alt": 920.0,
        },
        headers=headers,
    )
    assert res.status_code == 400
    assert "geofence" in res.json()["detail"].lower()


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
    _add_member(db, "STU002")
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
    assert res.json() == {"status": "batch_complete", "count": 2}
    assert db.query(VerificationLedger).filter_by(ledger_instance_id=ledger.id).count() == 2


def test_batch_refuses_a_record_naming_another_ledger(client, db, seed_users):
    """Each record's own ledger id was the one written to, and only the batch's
    was checked, so a lead could mark a session somebody else runs."""
    mine = _make_ledger(db, lead_id="FAC001")
    theirs = _second_ledger(db, mine)
    mine_id, theirs_id = mine.id, theirs.id
    headers = login(client, "staff@test.internal", STAFF_PASSWORD)
    body = {
        "ledger_instance_id": mine_id,
        "records": [
            {"ledger_instance_id": theirs_id, "member_id": "STU001", "marking_status": "ABSENT"}
        ],
    }
    res = client.post("/api/v1/attendance/batch", json=body, headers=headers)
    assert res.status_code == 422
    assert res.json()["detail"] == f"Every record must name ledger {mine_id}, not {theirs_id}"
    assert db.query(VerificationLedger).count() == 0


def test_batch_refuses_a_member_listed_twice(client, db, seed_users):
    """Which of the two lines counted was down to the order they came in."""
    ledger = _make_ledger(db, lead_id="FAC001")
    headers = login(client, "staff@test.internal", STAFF_PASSWORD)
    body = {
        "ledger_instance_id": ledger.id,
        "records": [
            {"ledger_instance_id": ledger.id, "member_id": "STU001", "marking_status": "PRESENT"},
            {"ledger_instance_id": ledger.id, "member_id": "STU001", "marking_status": "ABSENT"},
        ],
    }
    res = client.post("/api/v1/attendance/batch", json=body, headers=headers)
    assert res.status_code == 422
    assert res.json()["detail"] == "Listed more than once: STU001"
    assert db.query(VerificationLedger).count() == 0


def test_batch_with_an_unknown_member_writes_nothing(client, db, seed_users):
    """Each record used to commit on its own, so on PostgreSQL the members
    before an unknown one were marked and the batch then failed with a 500."""
    ledger = _make_ledger(db, lead_id="FAC001")
    headers = login(client, "staff@test.internal", STAFF_PASSWORD)
    body = {
        "ledger_instance_id": ledger.id,
        "records": [
            {"ledger_instance_id": ledger.id, "member_id": "STU001", "marking_status": "PRESENT"},
            {"ledger_instance_id": ledger.id, "member_id": "NOBODY", "marking_status": "ABSENT"},
        ],
    }
    res = client.post("/api/v1/attendance/batch", json=body, headers=headers)
    assert res.status_code == 404
    assert res.json()["detail"] == "Member not found: NOBODY"
    assert db.query(VerificationLedger).count() == 0


def test_mark_refuses_an_unknown_member(client, db, seed_users):
    ledger = _make_ledger(db, lead_id="FAC001")
    headers = login(client, "staff@test.internal", STAFF_PASSWORD)
    res = client.post(
        "/api/v1/attendance/mark",
        json={"ledger_instance_id": ledger.id, "member_id": "NOBODY", "marking_status": "PRESENT"},
        headers=headers,
    )
    assert res.status_code == 404
    assert res.json()["detail"] == "Member not found: NOBODY"


def test_batch_replaces_an_existing_mark_and_adds_the_rest(client, db, seed_users):
    ledger = _make_ledger(db, lead_id="FAC001")
    ledger_id = ledger.id
    _add_member(db, "STU002")
    headers = login(client, "staff@test.internal", STAFF_PASSWORD)
    first = {"ledger_instance_id": ledger_id, "member_id": "STU001", "marking_status": "PRESENT"}
    res = client.post("/api/v1/attendance/mark", json=first, headers=headers)
    assert res.json() == {"status": "marked", "member_id": "STU001", "marking_status": "PRESENT"}

    body = {
        "ledger_instance_id": ledger_id,
        "records": [
            {**first, "marking_status": "ABSENT"},
            {"ledger_instance_id": ledger_id, "member_id": "STU002", "marking_status": "PRESENT"},
        ],
    }
    assert client.post("/api/v1/attendance/batch", json=body, headers=headers).status_code == 200
    db.expire_all()
    rows = db.query(VerificationLedger).filter_by(ledger_instance_id=ledger_id)
    assert {r.member_id: r.marking_status.value for r in rows} == {
        "STU001": "ABSENT",
        "STU002": "PRESENT",
    }


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
    assert res.json() == {"status": "VERIFIED_APPROVED", "guest": "Ravi Verma"}
    assert client.get("/api/v1/guest/pending", headers=fac).json() == []


# -- Notices over the socket ---------------------------------------------------


class _FakeSocket:
    """Stands in for a browser with the app open, and keeps what it is sent."""

    def __init__(self):
        self.frames = []

    async def send_text(self, text):
        self.frames.append(json.loads(text))


@pytest.fixture()
def open_socket():
    opened = {}

    def open_for(user_id):
        opened[user_id] = _FakeSocket()
        socket_broker.register_session(user_id, opened[user_id])
        return opened[user_id]

    yield open_for
    for user_id, sock in opened.items():
        socket_broker.terminate_session(user_id, sock)


def test_absence_notices_reach_the_manager_and_the_submitter(client, db, seed_users, open_socket):
    """The routes are plain functions now, and the notices go out after the response."""
    seed_users["staff"].reporting_line_manager = "ADM001"
    db.commit()
    manager, submitter = open_socket("ADM001"), open_socket("FAC001")

    fac = login(client, "staff@test.internal", STAFF_PASSWORD)
    log_id = client.post(
        "/api/v1/attendance/absence",
        json={"target_absence_date": str(TODAY), "context_justification": "Medical"},
        headers=fac,
    ).json()["id"]
    assert manager.frames == [
        {
            "event": "ABSENCE_APPROVAL_REQUIRED",
            "payload": {"log_id": log_id, "from": "Staff One", "date": str(TODAY)},
        }
    ]

    adm = login(client, "admin@test.internal", ADMIN_PASSWORD)
    res = client.patch(
        f"/api/v1/attendance/absence/{log_id}/decide",
        json={"decision": "VERIFIED_DENIED"},
        headers=adm,
    )
    assert res.json() == {"status": "VERIFIED_DENIED"}
    assert submitter.frames == [
        {"event": "ABSENCE_DECISION", "payload": {"log_id": log_id, "decision": "VERIFIED_DENIED"}}
    ]


def test_guest_checkin_notice_reaches_the_staff_member(client, seed_users, kiosk_key, open_socket):
    staff = open_socket("FAC001")
    res = client.post("/api/v1/guest/register-checkin", json=_GUEST, headers=kiosk_key)
    assert res.json()["registration_state"] == "PENDING_STAFF_AUTH"
    assert staff.frames == [
        {
            "event": "GUEST_HANDSHAKE_REQ",
            "payload": {
                "transaction_reference": res.json()["reference_token"],
                "guest_name": "Ravi Verma",
                "organization": "Acme Corp",
                "intent": "Project discussion",
            },
        }
    ]


# -- Staff location (Redis-backed) -----------------------------------------


class _FakeRedis:
    def __init__(self, value=None):
        self.value = value

    def mget(self, keys):
        return [self.value for _ in keys]


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
    assert res.json()["resolved_location"] == "UNKNOWN"


class _DownRedis:
    def mget(self, keys):
        raise redis.ConnectionError("Connection refused.")


@pytest.mark.parametrize(
    "path", ["/api/v1/schedule/staff/FAC001/location", "/api/v1/schedule/staff/all/locations"]
)
def test_staff_location_answers_with_redis_down(client, seed_users, monkeypatch, path):
    """Both routes read the override first and answered 500 when it failed."""
    monkeypatch.setattr("app.api.v1.endpoints.schedule.get_redis", lambda: _DownRedis())
    headers = login(client, "member@test.internal", MEMBER_PASSWORD)
    res = client.get(path, headers=headers)
    assert res.status_code == 200
    body = res.json()
    assert (body[0] if isinstance(body, list) else body)["status"] == "Available / Unassigned"


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
