# Copyright 2026 Chronos Ledger Contributors
# Licensed under the Apache License, Version 2.0

"""Slot input validation: a zero length window or an out of range weekday is
refused at the edge with a 422, whether it arrives through the API or through
an imported matrix, and never surfaces as a 500.

An end earlier than a start is not one of those. It means the window runs past
midnight and finishes on the day after the one it opened on, which is what a
night shift is, and window_span expands it that way everywhere it is read. It
is accepted here on purpose, and these tests hold it accepted.

Equal times are the one pair that cannot be read at all. 09:00 to 09:00 is
either nothing or a whole day and the row does not say which, so it is refused
in the schema, in the endpoint that patches a slot, and in the importer.
"""

import datetime
import io

from app.core.time import org_today
from app.models.db import Activity, PlanningCycle, StructuralMasterSlot
from tests.conftest import ADMIN_PASSWORD, login

HEADER = (
    "member_id,member_name,member_email,activity_code,activity_title,"
    "unit,day_of_week_index,time_window_start,time_window_end,lead_id,room"
)


def _seed_offering(db):
    today = org_today()
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


def _csv(day: int, start: str, end: str) -> str:
    return (
        HEADER + "\n"
        f"STU950,Night Shift,night@test.internal,NS101,Night Rounds,CSE,{day},"
        f"{start},{end},FAC001,W-1\n"
    )


def _upload(client, headers, cycle, csv_text: str):
    return client.post(
        f"/api/v1/ingestion/upload-csv?cycle_id={cycle.id}",
        headers=headers,
        files={"file": ("matrix.csv", io.BytesIO(csv_text.encode()), "text/csv")},
    )


def test_valid_slot_is_accepted(client, db, seed_users):
    _, offering = _seed_offering(db)
    headers = login(client, "admin@test.internal", ADMIN_PASSWORD)
    r = client.post("/api/v1/schedule/slots", headers=headers, json=_slot_payload(offering))
    assert r.status_code == 200, r.text


def test_a_window_that_runs_past_midnight_is_accepted(client, db, seed_users):
    """A night shift is a window, not a typo.

    The stored row is read back rather than trusting the 200. A validator that
    quietly swapped the two times would answer exactly the same way and mean
    the opposite: a sixteen hour day shift instead of an eight hour night.
    """
    _, offering = _seed_offering(db)
    headers = login(client, "admin@test.internal", ADMIN_PASSWORD)
    r = client.post(
        "/api/v1/schedule/slots",
        headers=headers,
        json=_slot_payload(offering, time_window_start="22:00:00", time_window_end="06:00:00"),
    )
    assert r.status_code == 200, r.text

    db.expire_all()
    slot = db.query(StructuralMasterSlot).one()
    assert (slot.time_window_start, slot.time_window_end) == (
        datetime.time(22, 0),
        datetime.time(6, 0),
    )


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


def test_csv_with_a_night_shift_ingests_it(client, db, seed_users):
    """The importer reads the same rule as the API.

    A matrix is where most night shifts actually arrive, so refusing them
    here would leave a ward's only route in by hand written POSTs.
    """
    cycle, _ = _seed_offering(db)
    headers = login(client, "admin@test.internal", ADMIN_PASSWORD)

    r = _upload(client, headers, cycle, _csv(3, "22:00", "06:00"))
    assert r.status_code == 200, r.text
    assert r.json()["status"] == "SUCCESS"

    db.expire_all()
    slot = db.query(StructuralMasterSlot).one()
    assert (slot.time_window_start, slot.time_window_end) == (
        datetime.time(22, 0),
        datetime.time(6, 0),
    )


def test_csv_with_a_zero_length_window_fails_and_ingests_nothing(client, db, seed_users):
    """The whole upload fails, not the row.

    A matrix that is wrong in one place is usually wrong in others, and half
    a timetable in the database is harder to recover from than none of it.
    """
    cycle, _ = _seed_offering(db)
    headers = login(client, "admin@test.internal", ADMIN_PASSWORD)

    r = _upload(client, headers, cycle, _csv(3, "09:00", "09:00"))
    assert r.status_code == 422, r.text
    assert "same as time_window_start" in r.json()["detail"]

    db.expire_all()
    assert db.query(StructuralMasterSlot).count() == 0
