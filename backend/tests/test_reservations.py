# Copyright 2026 Chronos Ledger Contributors
# Licensed under the Apache License, Version 2.0
"""Holding a room from outside, and being refused when it is already taken.

Availability answered the question an integration asks first and there was
nowhere to put the answer, so a room stayed bookable by everyone else the
moment after it had been checked. These pin the hold: what it refuses, what a
retry gets, and the one thing that has to stay true, which is that the set a
booking is checked against is the set availability reports.
"""

import datetime

from app.core.security import hash_password
from app.models.db import (
    Activity,
    InstitutionalRole,
    PlanningCycle,
    Reservation,
    ReservationStatus,
    Resource,
    ResourceType,
    StructuralMasterSlot,
    User,
)
from tests.conftest import ADMIN_PASSWORD, MEMBER_PASSWORD, STAFF_PASSWORD, login

# Explicit dates, never "today plus one": a weekday computed from the day the
# suite happens to run is a test that only tests something two days in seven.
MONDAY = datetime.date(2026, 1, 5)
TUESDAY = datetime.date(2026, 1, 6)
SUNDAY = datetime.date(2026, 1, 11)

UNIT_ADMIN_PASSWORD = "UnitAdminPass123!"


def _room(db, code="LH-201", resource_type=ResourceType.ROOM, **extra):
    room = Resource(code=code, label=code, resource_type=resource_type, **extra)
    db.add(room)
    db.commit()
    return room


def _slot(db, room, code="CS101", day=1, start="09:00", end="10:00"):
    cycle = PlanningCycle(
        cycle_label="Cycle",
        date_bounds_start=datetime.date(2026, 1, 1),
        date_bounds_end=datetime.date(2026, 6, 30),
        operational_status=True,
    )
    db.add(cycle)
    db.flush()
    activity = Activity(
        activity_code=code,
        activity_title="Something",
        unit_code="CSE",
        cycle_id=cycle.id,
    )
    db.add(activity)
    db.flush()
    slot = StructuralMasterSlot(
        day_of_week_index=day,
        time_window_start=datetime.time.fromisoformat(start),
        time_window_end=datetime.time.fromisoformat(end),
        activity_id=activity.id,
        resource_id=room.id,
        target_room_identifier=room.code,
    )
    db.add(slot)
    db.commit()
    return slot


def _book(
    client,
    headers,
    resource_id,
    key="booking-0000-0001",
    on=TUESDAY,
    start="14:00",
    end="15:00",
    purpose="Ward round",
):
    return client.post(
        f"/api/v1/resources/{resource_id}/reservations",
        json={"date": str(on), "start": start, "end": end, "purpose": purpose},
        headers={**headers, "Idempotency-Key": key},
    )


def _busy(client, headers, resource_id, from_=MONDAY, to=SUNDAY):
    return client.get(
        f"/api/v1/resources/{resource_id}/availability",
        params={"from": str(from_), "to": str(to)},
        headers=headers,
    ).json()["busy"]


# -- Taking a hold ------------------------------------------------------------


def test_a_room_can_be_held(client, db, seed_users):
    room = _room(db)
    headers = login(client, "admin@test.internal", ADMIN_PASSWORD)

    res = _book(client, headers, room.id)
    assert res.status_code == 201, res.text
    body = res.json()
    assert body["resource_code"] == "LH-201"
    assert body["date"] == "2026-01-06"
    assert body["start"] == "14:00:00"
    assert body["end"] == "15:00:00"
    assert body["purpose"] == "Ward round"
    assert body["status"] == "HELD"
    assert body["cancelled_at"] is None


def test_the_caller_is_recorded(client, db, seed_users):
    """An API key acts as the user it is bound to, so this is the same field."""
    room = _room(db)
    headers = login(client, "admin@test.internal", ADMIN_PASSWORD)

    _book(client, headers, room.id)
    held = db.query(Reservation).one()
    assert held.requested_by_id == "ADM001"
    assert held.status is ReservationStatus.HELD


def test_a_hold_shows_up_on_the_calendar(client, db, seed_users):
    """Otherwise the next system to ask would book straight over it."""
    room = _room(db)
    headers = login(client, "admin@test.internal", ADMIN_PASSWORD)
    reservation_id = _book(client, headers, room.id).json()["id"]

    busy = _busy(client, headers, room.id)
    assert busy == [
        {
            "date": "2026-01-06",
            "start": "14:00:00",
            "end": "15:00:00",
            "activity_id": None,
            "activity_code": None,
            "master_slot_id": None,
            "reservation_id": reservation_id,
        }
    ]


def test_a_hold_and_a_class_come_back_together_in_time_order(client, db, seed_users):
    room = _room(db)
    _slot(db, room, day=2, start="09:00", end="10:00")
    headers = login(client, "admin@test.internal", ADMIN_PASSWORD)
    _book(client, headers, room.id, on=TUESDAY, start="14:00", end="15:00")

    busy = _busy(client, headers, room.id, from_=TUESDAY, to=TUESDAY)
    assert [(e["start"], e["activity_code"], e["reservation_id"] is None) for e in busy] == [
        ("09:00:00", "CS101", True),
        ("14:00:00", None, False),
    ]


def test_what_a_booking_is_for_is_not_on_the_public_calendar(client, db, seed_users):
    """A room's calendar is readable by everyone signed in; a purpose need not be."""
    room = _room(db)
    admin = login(client, "admin@test.internal", ADMIN_PASSWORD)
    _book(client, admin, room.id, purpose="Oncology consult, Mr Sharma")

    member = login(client, "member@test.internal", MEMBER_PASSWORD)
    busy = _busy(client, member, room.id)
    assert len(busy) == 1
    assert "Sharma" not in str(busy)
    assert "purpose" not in busy[0]


# -- Being refused ------------------------------------------------------------


def test_two_holds_on_the_same_hour_is_409(client, db, seed_users):
    room = _room(db)
    headers = login(client, "admin@test.internal", ADMIN_PASSWORD)
    first = _book(client, headers, room.id, key="booking-first-01").json()

    res = _book(client, headers, room.id, key="booking-second-1")
    assert res.status_code == 409
    detail = res.json()["detail"]
    assert detail["message"] == "the resource is already taken for part of that window"
    assert [c["reservation_id"] for c in detail["conflicts"]] == [first["id"]]


def test_the_conflict_says_what_it_ran_into(client, db, seed_users):
    """Told only "no", a caller has to diff two availability reads to find out why."""
    room = _room(db)
    _slot(db, room, day=2, start="09:00", end="10:00")
    headers = login(client, "admin@test.internal", ADMIN_PASSWORD)

    res = _book(client, headers, room.id, on=TUESDAY, start="09:30", end="10:30")
    assert res.status_code == 409
    conflict = res.json()["detail"]["conflicts"][0]
    assert conflict["activity_code"] == "CS101"
    assert conflict["start"] == "09:00:00"
    assert conflict["reservation_id"] is None


def test_the_timetable_blocks_a_booking(client, db, seed_users):
    """A class already has the room. An outside system may not take it."""
    room = _room(db)
    _slot(db, room, day=1, start="09:00", end="10:00")
    headers = login(client, "admin@test.internal", ADMIN_PASSWORD)

    assert _book(client, headers, room.id, on=MONDAY, start="09:00", end="10:00").status_code == 409


def test_a_closed_cycle_does_not_block_a_booking(client, db, seed_users):
    """The same gate as availability: a closed cycle occupies nothing."""
    room = _room(db)
    slot = _slot(db, room, day=1, start="09:00", end="10:00")
    cycle = db.query(PlanningCycle).one()
    cycle.operational_status = False
    db.commit()
    assert slot.id is not None
    headers = login(client, "admin@test.internal", ADMIN_PASSWORD)

    assert _book(client, headers, room.id, on=MONDAY, start="09:00", end="10:00").status_code == 201


def test_booking_refuses_exactly_what_availability_calls_busy(client, db, seed_users):
    """The two must not be allowed to answer differently.

    An hour availability reports free and booking refuses is an annoyance. An
    hour availability reports free and booking accepts, when something else
    already had it, is the double booking the whole endpoint exists to stop.
    Both directions are checked by walking the day hour by hour and asking
    each question of the same hour.
    """
    room = _room(db)
    _slot(db, room, day=2, start="09:00", end="10:00")
    headers = login(client, "admin@test.internal", ADMIN_PASSWORD)
    _book(client, headers, room.id, key="fixture-hold-01", on=TUESDAY, start="14:00", end="15:00")

    busy = _busy(client, headers, room.id, from_=TUESDAY, to=TUESDAY)
    for hour in range(8, 18):
        start = datetime.time(hour, 0)
        end = datetime.time(hour + 1, 0)
        availability_says_taken = any(
            e["start"] < end.isoformat() and start.isoformat() < e["end"] for e in busy
        )

        res = _book(
            client,
            headers,
            room.id,
            key=f"probe-{hour:02d}-0001",
            on=TUESDAY,
            start=start.isoformat(),
            end=end.isoformat(),
        )
        booking_says_taken = res.status_code == 409
        assert booking_says_taken == availability_says_taken, (
            f"{start} to {end}: availability said "
            f"{'taken' if availability_says_taken else 'free'}, "
            f"booking said {'taken' if booking_says_taken else 'free'}"
        )
        if not booking_says_taken:
            # Let it go again, or every accepted hour would block the next.
            client.delete(
                f"/api/v1/resources/{room.id}/reservations/{res.json()['id']}", headers=headers
            )


def test_back_to_back_holds_are_allowed(client, db, seed_users):
    """Half open. A room free at ten is free at ten."""
    room = _room(db)
    headers = login(client, "admin@test.internal", ADMIN_PASSWORD)
    assert (
        _book(
            client, headers, room.id, key="back-to-back-1", start="09:00", end="10:00"
        ).status_code
        == 201
    )
    assert (
        _book(
            client, headers, room.id, key="back-to-back-2", start="10:00", end="11:00"
        ).status_code
        == 201
    )


def test_another_room_is_not_blocked(client, db, seed_users):
    room = _room(db)
    other = _room(db, code="LH-305")
    headers = login(client, "admin@test.internal", ADMIN_PASSWORD)
    _book(client, headers, room.id, key="one-room-only1")

    assert _book(client, headers, other.id, key="one-room-only2").status_code == 201


def test_another_date_is_not_blocked(client, db, seed_users):
    room = _room(db)
    headers = login(client, "admin@test.internal", ADMIN_PASSWORD)
    _book(client, headers, room.id, key="tuesday-hold-1", on=TUESDAY)

    assert _book(client, headers, room.id, key="monday-hold-01", on=MONDAY).status_code == 201


def test_a_window_that_ends_before_it_starts_is_refused(client, db, seed_users):
    room = _room(db)
    headers = login(client, "admin@test.internal", ADMIN_PASSWORD)

    assert _book(client, headers, room.id, start="15:00", end="14:00").status_code == 422
    assert _book(client, headers, room.id, start="14:00", end="14:00").status_code == 422


def test_booking_a_room_that_is_not_there_is_404(client, db, seed_users):
    headers = login(client, "admin@test.internal", ADMIN_PASSWORD)
    assert _book(client, headers, 9999).status_code == 404


# -- Idempotency --------------------------------------------------------------


def test_the_same_request_twice_holds_the_room_once(client, db, seed_users):
    """A network retry must not book a second room."""
    room = _room(db)
    headers = login(client, "admin@test.internal", ADMIN_PASSWORD)
    first = _book(client, headers, room.id, key="retried-key-001")
    again = _book(client, headers, room.id, key="retried-key-001")

    assert first.status_code == 201
    assert again.status_code == 200
    assert again.json()["id"] == first.json()["id"]
    assert db.query(Reservation).count() == 1


def test_the_same_key_for_a_different_request_is_refused(client, db, seed_users):
    """At that point the caller has lost track of which of the two it meant."""
    room = _room(db)
    headers = login(client, "admin@test.internal", ADMIN_PASSWORD)
    _book(client, headers, room.id, key="confused-key-01", start="14:00", end="15:00")

    res = _book(client, headers, room.id, key="confused-key-01", start="16:00", end="17:00")
    assert res.status_code == 422
    assert res.json()["detail"] == "that Idempotency-Key was used for a different request"


def test_the_same_key_on_a_different_room_is_refused(client, db, seed_users):
    """The resource is in the path, not the body, so it is in the fingerprint."""
    room = _room(db)
    other = _room(db, code="LH-305")
    headers = login(client, "admin@test.internal", ADMIN_PASSWORD)
    _book(client, headers, room.id, key="one-key-two-rm")

    assert _book(client, headers, other.id, key="one-key-two-rm").status_code == 422


def test_a_booking_without_a_key_is_refused(client, db, seed_users):
    room = _room(db)
    headers = login(client, "admin@test.internal", ADMIN_PASSWORD)

    res = client.post(
        f"/api/v1/resources/{room.id}/reservations",
        json={"date": str(TUESDAY), "start": "14:00", "end": "15:00", "purpose": "Ward round"},
        headers=headers,
    )
    assert res.status_code == 422


def test_a_key_too_short_to_be_unique_is_refused(client, db, seed_users):
    """It is unique across every caller, so "1" is somebody else's key."""
    room = _room(db)
    headers = login(client, "admin@test.internal", ADMIN_PASSWORD)

    assert _book(client, headers, room.id, key="1").status_code == 422


# -- Letting it go ------------------------------------------------------------


def test_cancelling_frees_the_room_and_keeps_the_row(client, db, seed_users):
    room = _room(db)
    headers = login(client, "admin@test.internal", ADMIN_PASSWORD)
    held = _book(client, headers, room.id).json()

    res = client.delete(f"/api/v1/resources/{room.id}/reservations/{held['id']}", headers=headers)
    assert res.status_code == 200
    assert res.json()["status"] == "CANCELLED"
    assert res.json()["cancelled_at"] is not None

    assert _busy(client, headers, room.id) == []
    assert db.query(Reservation).count() == 1


def test_a_cancelled_window_can_be_booked_again(client, db, seed_users):
    room = _room(db)
    headers = login(client, "admin@test.internal", ADMIN_PASSWORD)
    held = _book(client, headers, room.id, key="let-it-go-0001").json()
    client.delete(f"/api/v1/resources/{room.id}/reservations/{held['id']}", headers=headers)

    assert _book(client, headers, room.id, key="take-it-again1").status_code == 201


def test_cancelling_twice_is_not_an_error(client, db, seed_users):
    """The caller wanted the room free and the room is free."""
    room = _room(db)
    headers = login(client, "admin@test.internal", ADMIN_PASSWORD)
    held = _book(client, headers, room.id).json()
    url = f"/api/v1/resources/{room.id}/reservations/{held['id']}"

    first = client.delete(url, headers=headers)
    second = client.delete(url, headers=headers)
    assert (first.status_code, second.status_code) == (200, 200)
    assert first.json()["cancelled_at"] == second.json()["cancelled_at"]


def test_cancelling_through_the_wrong_room_is_404(client, db, seed_users):
    room = _room(db)
    other = _room(db, code="LH-305")
    headers = login(client, "admin@test.internal", ADMIN_PASSWORD)
    held = _book(client, headers, room.id).json()

    res = client.delete(f"/api/v1/resources/{other.id}/reservations/{held['id']}", headers=headers)
    assert res.status_code == 404


def test_cancelling_something_that_is_not_there_is_404(client, db, seed_users):
    room = _room(db)
    headers = login(client, "admin@test.internal", ADMIN_PASSWORD)
    assert (
        client.delete(f"/api/v1/resources/{room.id}/reservations/9999", headers=headers).status_code
        == 404
    )


def test_a_retry_after_cancelling_does_not_book_it_again(client, db, seed_users):
    """A retry is asking what happened, not asking for a second room."""
    room = _room(db)
    headers = login(client, "admin@test.internal", ADMIN_PASSWORD)
    held = _book(client, headers, room.id, key="cancel-retry-1").json()
    client.delete(f"/api/v1/resources/{room.id}/reservations/{held['id']}", headers=headers)

    again = _book(client, headers, room.id, key="cancel-retry-1")
    assert again.status_code == 200
    assert again.json()["status"] == "CANCELLED"
    assert db.query(Reservation).count() == 1


# -- Who may book -------------------------------------------------------------


def test_a_member_may_not_book(client, db, seed_users):
    room = _room(db)
    headers = login(client, "member@test.internal", MEMBER_PASSWORD)
    assert _book(client, headers, room.id).status_code == 403


def test_staff_may_not_book(client, db, seed_users):
    """The same roles that may edit a slot, and no more."""
    room = _room(db)
    headers = login(client, "staff@test.internal", STAFF_PASSWORD)
    assert _book(client, headers, room.id).status_code == 403


def test_a_member_may_not_cancel(client, db, seed_users):
    room = _room(db)
    admin = login(client, "admin@test.internal", ADMIN_PASSWORD)
    held = _book(client, admin, room.id).json()

    member = login(client, "member@test.internal", MEMBER_PASSWORD)
    res = client.delete(f"/api/v1/resources/{room.id}/reservations/{held['id']}", headers=member)
    assert res.status_code == 403


# -- Whose hold it is ---------------------------------------------------------


def _unit_admin(db, client, id_="DAD001", email="unitadmin@test.internal"):
    db.add(
        User(
            id=id_,
            full_name="A Unit Admin",
            email_address=email,
            credential_secure_hash=hash_password(UNIT_ADMIN_PASSWORD),
            role_type=InstitutionalRole.UNIT_ADMIN,
            unit_code="CSE",
            initial_login_state=False,
        )
    )
    db.commit()
    return login(client, email, UNIT_ADMIN_PASSWORD)


def test_a_unit_admin_cancels_the_hold_it_took(client, db, seed_users):
    room = _room(db)
    headers = _unit_admin(db, client)

    held = _book(client, headers, room.id).json()
    res = client.delete(f"/api/v1/resources/{room.id}/reservations/{held['id']}", headers=headers)
    assert res.status_code == 200, res.text
    assert res.json()["status"] == "CANCELLED"


def test_a_unit_admin_may_not_cancel_a_hold_it_did_not_take(client, db, seed_users):
    """One integration must not be able to drop another integration's room.

    Both hold rooms through the same route with the same role. Without this
    the loser finds out its room is free when somebody else walks into it.
    """
    room = _room(db)
    admin = login(client, "admin@test.internal", ADMIN_PASSWORD)
    held = _book(client, admin, room.id).json()

    headers = _unit_admin(db, client)
    res = client.delete(f"/api/v1/resources/{room.id}/reservations/{held['id']}", headers=headers)
    assert res.status_code == 403
    assert res.json()["detail"] == "only the caller that took a hold may cancel it"

    # And the room is still held, which is the point of refusing.
    assert len(_busy(client, admin, room.id)) == 1


def test_an_admin_can_cancel_a_hold_it_did_not_take(client, db, seed_users):
    """Somebody has to be able to clear a hold whose owner is gone."""
    room = _room(db)
    theirs = _unit_admin(db, client)
    held = _book(client, theirs, room.id).json()

    admin = login(client, "admin@test.internal", ADMIN_PASSWORD)
    res = client.delete(f"/api/v1/resources/{room.id}/reservations/{held['id']}", headers=admin)
    assert res.status_code == 200
    assert _busy(client, admin, room.id) == []


# -- Through an API key -------------------------------------------------------


def _issue_key(client, headers, **extra):
    """A key bound to the seeded admin, which is how an integration arrives."""
    payload = {"label": "PulseWard", "user_id": "ADM001", **extra}
    res = client.post("/api/v1/api-keys/", json=payload, headers=headers)
    assert res.status_code == 201, res.text
    return {"X-API-Key": res.json()["api_key"]}


def test_an_integration_books_with_a_key_and_no_password(client, db, seed_users):
    """The path PulseWard actually uses, start to finish.

    Every other test here signs in with a password. An integration never
    does: it holds a scoped key, and the scope for this route is derived
    from the method and the path rather than declared on the endpoint, so
    nothing in the booking code says resources:write out loud. This is what
    checks that it composes.
    """
    room = _room(db)
    admin = login(client, "admin@test.internal", ADMIN_PASSWORD)
    key = _issue_key(client, admin, scopes=["resources:read", "resources:write"])

    res = _book(client, key, room.id)
    assert res.status_code == 201, res.text
    # A key acts as the user it is bound to, so the hold is the admin's.
    assert res.json()["requested_by_id"] == "ADM001"

    # And the same key can read the calendar it just filled in.
    assert len(_busy(client, key, room.id)) == 1


def test_a_read_only_key_cannot_book(client, db, seed_users):
    room = _room(db)
    admin = login(client, "admin@test.internal", ADMIN_PASSWORD)
    key = _issue_key(client, admin, scopes=["resources:read"])

    assert _book(client, key, room.id).status_code == 403
    assert _busy(client, admin, room.id) == []


def test_a_key_scoped_to_another_area_cannot_book(client, db, seed_users):
    """schedule:write is not resources:write, however adjacent they sound."""
    room = _room(db)
    admin = login(client, "admin@test.internal", ADMIN_PASSWORD)
    key = _issue_key(client, admin, scopes=["schedule:write"])

    assert _book(client, key, room.id).status_code == 403


def test_an_integration_cancels_its_own_hold_with_its_key(client, db, seed_users):
    room = _room(db)
    admin = login(client, "admin@test.internal", ADMIN_PASSWORD)
    key = _issue_key(client, admin, scopes=["resources:read", "resources:write"])

    held = _book(client, key, room.id).json()
    res = client.delete(f"/api/v1/resources/{room.id}/reservations/{held['id']}", headers=key)
    assert res.status_code == 200, res.text
    assert _busy(client, admin, room.id) == []
