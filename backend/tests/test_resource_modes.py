# Copyright 2026 Chronos Ledger Contributors
# Licensed under the Apache License, Version 2.0
"""Exclusive, pooled and shared resources.

A resource used to be one booking at a time, always. Now it says how it is
consumed: EXCLUSIVE is that old rule and stays the default, POOLED is a
stock of capacity interchangeable units of which a booking takes quantity,
and SHARED records who is there and refuses nobody. These pin the booking
route, the PATCH rules, availability and the conflict report for each.

The PostgreSQL side, where the pool is held by a row lock and the exclusive
rule by the exclusion constraint, is in tests/test_resource_modes_pg.py.
"""

import datetime
import hashlib

from app.api.v1.endpoints.resources import _fingerprint
from app.core.time import org_today
from app.models.db import (
    Activity,
    PlanningCycle,
    Reservation,
    ReservationStatus,
    Resource,
    ResourceMode,
    StructuralMasterSlot,
)
from app.schemas.resources import ReservationCreate
from app.services.availability import held_against_slot
from tests.conftest import ADMIN_PASSWORD, login, weekly

# A week out, so every hold here is one still to come and the PATCH rules,
# which only look forward, see all of them.
DAY = org_today() + datetime.timedelta(days=7)


def _admin(client):
    return login(client, "admin@test.internal", ADMIN_PASSWORD)


def _resource(db, code="VENT", mode=ResourceMode.EXCLUSIVE, capacity=None):
    resource = Resource(code=code, label=code, mode=mode, capacity=capacity)
    db.add(resource)
    db.commit()
    return resource


def _book(client, headers, resource_id, key, start="09:00", end="10:00", on=DAY, **extra):
    return client.post(
        f"/api/v1/resources/{resource_id}/reservations",
        json={"date": str(on), "start": start, "end": end, "purpose": "Ward", **extra},
        # Prefixed because the route wants at least eight characters.
        headers={**headers, "Idempotency-Key": f"booking-{key}"},
    )


def _busy(client, headers, resource_id):
    return client.get(
        f"/api/v1/resources/{resource_id}/availability",
        params={"from": str(DAY), "to": str(DAY)},
        headers=headers,
    ).json()["busy"]


def _slot(db, resource, start, end):
    cycle = PlanningCycle(
        cycle_label="Cycle",
        date_bounds_start=DAY - datetime.timedelta(days=30),
        date_bounds_end=DAY + datetime.timedelta(days=30),
        operational_status=True,
    )
    db.add(cycle)
    db.flush()
    activity = Activity(
        activity_code="CS101", activity_title="CS", unit_code="CSE", cycle_id=cycle.id
    )
    db.add(activity)
    db.flush()
    slot = StructuralMasterSlot(
        **weekly(DAY.isoweekday()),
        time_window_start=datetime.time.fromisoformat(start),
        time_window_end=datetime.time.fromisoformat(end),
        activity_id=activity.id,
        resource_id=resource.id,
        target_room_identifier=resource.code,
    )
    db.add(slot)
    db.commit()
    return slot


def _hold(db, resource, start, end, key, quantity=1):
    """A hold written straight in, as the conflict report has to find them."""
    hold = Reservation(
        resource_id=resource.id,
        reserved_date=DAY,
        time_window_start=datetime.time.fromisoformat(start),
        time_window_end=datetime.time.fromisoformat(end),
        purpose="Written straight in",
        requested_by_id="ADM001",
        idempotency_key=key,
        request_fingerprint="x" * 64,
        quantity=quantity,
        mode=resource.mode,
        status=ReservationStatus.HELD,
    )
    db.add(hold)
    db.commit()
    return hold


# -- Creating and reading a mode ----------------------------------------------


def test_a_resource_is_exclusive_unless_it_says_otherwise(client, db, seed_users):
    headers = _admin(client)
    res = client.post("/api/v1/resources/", json={"code": "LH-1"}, headers=headers)
    assert res.status_code == 201, res.text
    assert res.json()["mode"] == "EXCLUSIVE"
    assert db.query(Resource).one().mode is ResourceMode.EXCLUSIVE


def test_a_pool_is_created_with_its_capacity(client, db, seed_users):
    headers = _admin(client)
    res = client.post(
        "/api/v1/resources/",
        json={"code": "VENT", "mode": "POOLED", "capacity": 12},
        headers=headers,
    )
    assert res.status_code == 201, res.text
    assert (res.json()["mode"], res.json()["capacity"]) == ("POOLED", 12)


def test_a_pool_needs_a_capacity_of_at_least_one(client, db, seed_users):
    headers = _admin(client)
    for body in (
        {"code": "VENT", "mode": "POOLED"},
        {"code": "VENT", "mode": "POOLED", "capacity": 0},
    ):
        res = client.post("/api/v1/resources/", json=body, headers=headers)
        assert res.status_code == 422, res.text
    assert db.query(Resource).count() == 0


# -- Pooled ---------------------------------------------------------------------


def test_thirteen_of_twelve_ventilators_is_refused(client, db, seed_users):
    vents = _resource(db, mode=ResourceMode.POOLED, capacity=12)
    headers = _admin(client)

    res = _book(client, headers, vents.id, "key-thirteen", quantity=13)
    assert res.status_code == 409, res.text
    body = res.json()
    assert body["code"] == "RESOURCE_CAPACITY_EXCEEDED"
    detail = body["detail"]
    assert (detail["capacity"], detail["taken"], detail["requested"]) == (12, 0, 13)
    assert detail["conflicts"] == []
    assert db.query(Reservation).count() == 0


def test_a_pool_fills_and_then_refuses_naming_what_holds_it(client, db, seed_users):
    vents = _resource(db, mode=ResourceMode.POOLED, capacity=12)
    headers = _admin(client)

    first = _book(client, headers, vents.id, "key-ten", quantity=10)
    assert first.status_code == 201, first.text
    assert first.json()["quantity"] == 10
    second = _book(client, headers, vents.id, "key-two", quantity=2)
    assert second.status_code == 201, second.text

    res = _book(client, headers, vents.id, "key-one-more", start="09:30", end="11:00")
    assert res.status_code == 409, res.text
    assert res.json()["code"] == "RESOURCE_CAPACITY_EXCEEDED"
    detail = res.json()["detail"]
    assert (detail["capacity"], detail["taken"], detail["requested"]) == (12, 12, 1)
    assert sorted(c["reservation_id"] for c in detail["conflicts"]) == sorted(
        [first.json()["id"], second.json()["id"]]
    )
    assert detail["message"]

    # Back to back is not overlapping: the pool is empty again at ten.
    after = _book(client, headers, vents.id, "key-at-ten", start="10:00", end="11:00", quantity=12)
    assert after.status_code == 201, after.text


def test_a_pool_counts_the_peak_and_not_the_total(client, db, seed_users):
    """Two sixes that never meet leave room for a third six across both."""
    vents = _resource(db, mode=ResourceMode.POOLED, capacity=12)
    headers = _admin(client)

    assert (
        _book(client, headers, vents.id, "key-a", "09:00", "10:00", quantity=6).status_code == 201
    )
    assert (
        _book(client, headers, vents.id, "key-b", "10:00", "11:00", quantity=6).status_code == 201
    )
    across = _book(client, headers, vents.id, "key-c", "09:30", "10:30", quantity=6)
    assert across.status_code == 201, across.text

    full = _book(client, headers, vents.id, "key-d", "09:45", "10:15")
    assert full.status_code == 409, full.text
    assert full.json()["detail"]["taken"] == 12


def test_a_pool_counts_a_booking_across_midnight(client, db, seed_users):
    vents = _resource(db, mode=ResourceMode.POOLED, capacity=2)
    headers = _admin(client)

    night = _book(client, headers, vents.id, "key-night", "22:00", "06:00", quantity=2)
    assert night.status_code == 201, night.text
    morning = _book(
        client,
        headers,
        vents.id,
        "key-morning",
        "05:00",
        "07:00",
        on=DAY + datetime.timedelta(days=1),
    )
    assert morning.status_code == 409, morning.text
    assert morning.json()["detail"]["taken"] == 2


def test_a_class_takes_the_whole_pool(client, db, seed_users):
    vents = _resource(db, mode=ResourceMode.POOLED, capacity=12)
    _slot(db, vents, "09:00", "10:00")
    headers = _admin(client)

    res = _book(client, headers, vents.id, "key-over-class")
    assert res.status_code == 409, res.text
    assert res.json()["code"] == "RESOURCE_CONFLICT"


def test_a_quantity_needs_a_pool(client, db, seed_users):
    room = _resource(db)
    headers = _admin(client)

    res = _book(client, headers, room.id, "key-two-rooms", quantity=2)
    assert res.status_code == 422, res.text
    assert res.json()["code"] == "INVALID_VALUE"
    assert _book(client, headers, room.id, "key-one-room", quantity=1).status_code == 201


def test_a_retry_with_a_different_quantity_is_a_different_request(client, db, seed_users):
    vents = _resource(db, mode=ResourceMode.POOLED, capacity=12)
    headers = _admin(client)

    assert _book(client, headers, vents.id, "key-retry", quantity=3).status_code == 201
    again = _book(client, headers, vents.id, "key-retry", quantity=3)
    assert again.status_code == 200, again.text
    changed = _book(client, headers, vents.id, "key-retry", quantity=4)
    assert changed.status_code == 422, changed.text
    assert changed.json()["code"] == "IDEMPOTENCY_KEY_REUSED"


def test_a_fingerprint_without_a_quantity_is_what_it_always_was():
    """Rows stored before quantity existed still match a retry that leaves it out."""
    payload = ReservationCreate(
        date=datetime.date(2026, 1, 6),
        start=datetime.time(14),
        end=datetime.time(15),
        purpose="Ward round",
    )
    old = hashlib.sha256(b"7|2026-01-06|14:00:00|15:00:00|Ward round").hexdigest()
    assert _fingerprint(7, payload) == old


# -- Shared ---------------------------------------------------------------------


def test_two_shared_bookings_at_once_both_succeed(client, db, seed_users):
    lounge = _resource(db, code="LOUNGE", mode=ResourceMode.SHARED)
    headers = _admin(client)

    first = _book(client, headers, lounge.id, "key-first")
    second = _book(client, headers, lounge.id, "key-second")
    assert (first.status_code, second.status_code) == (201, 201), second.text
    assert db.query(Reservation).filter(Reservation.mode == ResourceMode.SHARED).count() == 2
    assert _busy(client, headers, lounge.id) == []


def test_a_shared_resource_and_the_timetable_do_not_refuse_each_other(client, db, seed_users):
    lounge = _resource(db, code="LOUNGE", mode=ResourceMode.SHARED)
    _slot(db, lounge, "09:00", "10:00")
    headers = _admin(client)

    assert _book(client, headers, lounge.id, "key-over-class").status_code == 201
    assert (
        held_against_slot(db, lounge.id, DAY.isoweekday(), datetime.time(9), datetime.time(10))
        == []
    )


# -- Exclusive ------------------------------------------------------------------


def test_exclusive_is_what_it_always_was(client, db, seed_users):
    room = _resource(db, code="LH-201")
    headers = _admin(client)

    first = _book(client, headers, room.id, "key-first")
    assert first.status_code == 201, first.text
    assert first.json()["quantity"] == 1
    res = _book(client, headers, room.id, "key-second", "09:30", "10:30")
    assert res.status_code == 409, res.text
    assert res.json()["code"] == "RESOURCE_CONFLICT"
    assert [c["reservation_id"] for c in res.json()["detail"]["conflicts"]] == [first.json()["id"]]
    assert db.query(Reservation).one().mode is ResourceMode.EXCLUSIVE


# -- Changing the mode or the capacity ----------------------------------------


def test_a_change_the_bookings_would_not_fit_is_refused_and_names_them(client, db, seed_users):
    vents = _resource(db, mode=ResourceMode.POOLED, capacity=3)
    headers = _admin(client)
    url = f"/api/v1/resources/{vents.id}"
    first = _book(client, headers, vents.id, "key-first").json()["id"]
    second = _book(client, headers, vents.id, "key-second", "09:30", "10:30").json()["id"]
    apart = _book(client, headers, vents.id, "key-apart", "12:00", "13:00").json()["id"]

    for change in ({"mode": "EXCLUSIVE"}, {"capacity": 1}):
        res = client.patch(url, json=change, headers=headers)
        assert res.status_code == 409, res.text
        assert res.json()["code"] == "RESOURCE_BOOKINGS_WOULD_NOT_FIT"
        named = [held["id"] for held in res.json()["detail"]["reservations"]]
        assert named == [first, second]
        assert apart not in named
    db.expire_all()
    assert (vents.mode, vents.capacity) == (ResourceMode.POOLED, 3)

    assert client.patch(url, json={"capacity": 2}, headers=headers).status_code == 200


def test_a_change_that_fits_is_written_onto_the_bookings(client, db, seed_users):
    vents = _resource(db, mode=ResourceMode.POOLED, capacity=3)
    headers = _admin(client)
    url = f"/api/v1/resources/{vents.id}"
    first = _book(client, headers, vents.id, "key-first").json()["id"]
    _book(client, headers, vents.id, "key-second", "09:30", "10:30")

    res = client.patch(url, json={"mode": "SHARED"}, headers=headers)
    assert res.status_code == 200, res.text
    assert res.json()["mode"] == "SHARED"
    db.expire_all()
    assert {held.mode for held in db.query(Reservation)} == {ResourceMode.SHARED}

    # Two that overlap cannot become exclusive; one of them alone can.
    assert client.patch(url, json={"mode": "EXCLUSIVE"}, headers=headers).status_code == 409
    cancelled = client.delete(f"{url}/reservations/{first}", headers=headers)
    assert cancelled.status_code == 200, cancelled.text
    assert client.patch(url, json={"mode": "EXCLUSIVE"}, headers=headers).status_code == 200
    db.expire_all()
    held = db.query(Reservation).filter(Reservation.status == ReservationStatus.HELD).one()
    assert held.mode is ResourceMode.EXCLUSIVE


def test_leaving_shared_meets_the_timetable(client, db, seed_users):
    lounge = _resource(db, code="LOUNGE", mode=ResourceMode.SHARED)
    _slot(db, lounge, "09:00", "10:00")
    headers = _admin(client)
    held = _book(client, headers, lounge.id, "key-over-class").json()["id"]

    res = client.patch(
        f"/api/v1/resources/{lounge.id}", json={"mode": "POOLED", "capacity": 5}, headers=headers
    )
    assert res.status_code == 409, res.text
    assert [r["id"] for r in res.json()["detail"]["reservations"]] == [held]


def test_a_pool_cannot_be_left_without_a_capacity(client, db, seed_users):
    room = _resource(db)
    vents = _resource(db, code="VENT2", mode=ResourceMode.POOLED, capacity=4)
    headers = _admin(client)

    for resource_id, change in (
        (room.id, {"mode": "POOLED"}),
        (vents.id, {"capacity": None}),
        (vents.id, {"capacity": 0}),
        (vents.id, {"mode": None}),
    ):
        res = client.patch(f"/api/v1/resources/{resource_id}", json=change, headers=headers)
        assert res.status_code == 422, (change, res.text)
    ok = client.patch(
        f"/api/v1/resources/{room.id}", json={"mode": "POOLED", "capacity": 2}, headers=headers
    )
    assert ok.status_code == 200, ok.text


# -- Availability -------------------------------------------------------------


def test_a_pool_is_busy_only_where_it_is_full(client, db, seed_users):
    vents = _resource(db, mode=ResourceMode.POOLED, capacity=2)
    headers = _admin(client)
    _book(client, headers, vents.id, "key-first", "09:00", "11:00")
    assert _busy(client, headers, vents.id) == []
    _book(client, headers, vents.id, "key-second", "10:00", "12:00")

    assert _busy(client, headers, vents.id) == [
        {
            "date": str(DAY),
            "start": "10:00:00",
            "end_date": str(DAY),
            "end": "11:00:00",
            "activity_id": None,
            "activity_code": None,
            "master_slot_id": None,
            "reservation_id": None,
        }
    ]


def test_a_pool_reports_its_timetable_as_busy(client, db, seed_users):
    vents = _resource(db, mode=ResourceMode.POOLED, capacity=2)
    slot = _slot(db, vents, "14:00", "15:00")
    headers = _admin(client)
    assert [entry["master_slot_id"] for entry in _busy(client, headers, vents.id)] == [slot.id]


# -- The conflict report ------------------------------------------------------


def _report(client, headers):
    res = client.get(
        "/api/v1/schedule/conflicts",
        params={"from": str(DAY), "to": str(DAY)},
        headers=headers,
    )
    assert res.status_code == 200, res.text
    return res.json()["conflicts"]


def test_an_overbooked_pool_is_reported_once_with_every_booking_in_it(client, db, seed_users):
    vents = _resource(db, mode=ResourceMode.POOLED, capacity=2)
    holds = [
        _hold(db, vents, "09:00", "11:00", "key-a"),
        _hold(db, vents, "09:30", "10:30", "key-b"),
        _hold(db, vents, "10:00", "12:00", "key-c"),
    ]

    conflicts = _report(client, _admin(client))
    assert len(conflicts) == 1
    overbooked = conflicts[0]
    assert overbooked["kind"] == "resource_overbooked"
    assert overbooked["resource_id"] == vents.id
    assert (overbooked["start"], overbooked["end"]) == ("10:00:00", "10:30:00")
    assert (overbooked["capacity"], overbooked["taken"]) == (2, 3)
    assert sorted(item["id"] for item in overbooked["items"]) == sorted(h.id for h in holds)


def test_a_pool_within_its_capacity_is_not_reported(client, db, seed_users):
    vents = _resource(db, mode=ResourceMode.POOLED, capacity=3)
    _hold(db, vents, "09:00", "11:00", "key-a", quantity=2)
    _hold(db, vents, "10:00", "12:00", "key-b")
    assert _report(client, _admin(client)) == []


def test_a_class_on_a_pool_with_a_booking_is_reported_as_an_overlap(client, db, seed_users):
    vents = _resource(db, mode=ResourceMode.POOLED, capacity=3)
    _slot(db, vents, "09:00", "10:00")
    _hold(db, vents, "09:30", "10:30", "key-a")

    conflicts = _report(client, _admin(client))
    assert [c["kind"] for c in conflicts] == ["resource_overlap"]
    assert conflicts[0]["capacity"] is None


def test_a_shared_resource_is_never_reported(client, db, seed_users):
    lounge = _resource(db, code="LOUNGE", mode=ResourceMode.SHARED)
    _slot(db, lounge, "09:00", "10:00")
    _hold(db, lounge, "09:00", "10:00", "key-a")
    _hold(db, lounge, "09:30", "10:30", "key-b")
    assert _report(client, _admin(client)) == []
