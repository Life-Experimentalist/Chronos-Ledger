# Copyright 2026 Chronos Ledger Contributors
# Licensed under the Apache License, Version 2.0

"""Slot input validation: inverted or midnight-crossing time windows and
out-of-range weekdays are rejected at the edge with a 422 (API) or a FAILED
result (CSV ingestion), never accepted or surfaced as a 500.

The ledger generator, location resolver and calendar feed all assume
start < end within one day, so an inverted window would produce events a
calendar client rejects and slots nobody is ever "in".
"""

import datetime
import io

from app.models.db import Activity, PlanningCycle, StructuralMasterSlot
from tests.conftest import ADMIN_PASSWORD, login

HEADER = (
    "member_id,member_name,member_email,activity_code,activity_title,"
    "unit,day_of_week_index,time_window_start,time_window_end,lead_id,room"
)


def _seed_offering(db):
    today = datetime.date.today()
    cycle = PlanningCycle(
        cycle_label="Validation 2026",
        date_bounds_start=today - datetime.timedelta(days=30),
        date_bounds_end=today + datetime.timedelta(days=90),
        operational_status=True,
    )
    db.add(cycle)
    db.flush()
    offering = Activity(
        activity_code="VAL101",
        activity_title="Validation Activity",
        unit_code="CSE",
        cycle_id=cycle.id,
    )
    db.add(offering)
    db.commit()
    return cycle, offering


def _slot_payload(offering, **overrides):
    payload = {
        "day_of_week_index": 2,
        "time_window_start": "09:00:00",
        "time_window_end": "10:00:00",
        "activity_id": offering.id,
        "target_room_identifier": "LH-101",
    }
    payload.update(overrides)
    return payload


def test_valid_slot_is_accepted(client, db, seed_users):
    _, offering = _seed_offering(db)
    headers = login(client, "admin@test.internal", ADMIN_PASSWORD)
    r = client.post("/api/v1/schedule/slots", headers=headers, json=_slot_payload(offering))
    assert r.status_code == 200, r.text


def test_inverted_window_is_rejected_with_422(client, db, seed_users):
    _, offering = _seed_offering(db)
    headers = login(client, "admin@test.internal", ADMIN_PASSWORD)
    r = client.post(
        "/api/v1/schedule/slots",
        headers=headers,
        json=_slot_payload(offering, time_window_start="22:00:00", time_window_end="06:00:00"),
    )
    assert r.status_code == 422, r.text
    assert "midnight" in r.text


def test_zero_length_window_is_rejected_with_422(client, db, seed_users):
    _, offering = _seed_offering(db)
    headers = login(client, "admin@test.internal", ADMIN_PASSWORD)
    r = client.post(
        "/api/v1/schedule/slots",
        headers=headers,
        json=_slot_payload(offering, time_window_start="09:00:00", time_window_end="09:00:00"),
    )
    assert r.status_code == 422, r.text


def test_out_of_range_weekday_is_422_not_500(client, db, seed_users):
    _, offering = _seed_offering(db)
    headers = login(client, "admin@test.internal", ADMIN_PASSWORD)
    for bad_day in (0, 8):
        r = client.post(
            "/api/v1/schedule/slots",
            headers=headers,
            json=_slot_payload(offering, day_of_week_index=bad_day),
        )
        assert r.status_code == 422, r.text


def test_csv_with_inverted_window_fails_and_ingests_nothing(client, db, seed_users):
    cycle, _ = _seed_offering(db)
    headers = login(client, "admin@test.internal", ADMIN_PASSWORD)
    csv_text = (
        HEADER + "\n"
        "STU950,Night Shift,night@test.internal,NS101,Night Rounds,CSE,3,22:00,06:00,FAC001,W-1\n"
    )
    r = client.post(
        f"/api/v1/ingestion/upload-csv?cycle_id={cycle.id}",
        headers=headers,
        files={"file": ("matrix.csv", io.BytesIO(csv_text.encode()), "text/csv")},
    )
    assert r.status_code == 422, r.text
    assert "midnight" in r.json()["detail"]
    db.expire_all()
    assert db.query(StructuralMasterSlot).count() == 0
