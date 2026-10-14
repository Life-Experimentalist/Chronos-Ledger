# Copyright 2026 Chronos Ledger Contributors
# Licensed under the Apache License, Version 2.0
"""A resource can require other resources, and an activity can too.

Booking a resource holds what it requires in the same transaction, as child
reservations. The timetable never holds anything for a requirement: it only
reports the ones a slot cannot have. These pin both halves, the saving rules
for a requirement, the organization default, and the padding rules.

The PostgreSQL side, where the exclusion constraint settles a race for a
child, is in tests/test_resource_requirements_pg.py.
"""

import datetime
import logging

from app.core.recurrence import weekly_rule
from app.core.time import org_today
from app.cron.ledger_generator import generate_daily_ledger_entries
from app.models.db import (
    Activity,
    Organization,
    PlanningCycle,
    Reservation,
    ReservationStatus,
    Resource,
    ResourceMode,
    ResourceRequirement,
    ResourceType,
    StructuralMasterSlot,
)
from tests.conftest import ADMIN_PASSWORD, STAFF_PASSWORD, login, weekly
from tests.test_import_corrections import _csv, _row
from tests.test_ingestion import _make_cycle, _upload

DAY = org_today() + datetime.timedelta(days=7)
TOMORROW = org_today() + datetime.timedelta(days=1)

ROOMS = "/api/v1/resources"


def _admin(client):
    return login(client, "admin@test.internal", ADMIN_PASSWORD)


def _resource(
    db,
    code,
    kind=ResourceType.ROOM,
    mode=ResourceMode.EXCLUSIVE,
    capacity=None,
):
    resource = Resource(code=code, label=code, resource_type=kind, mode=mode, capacity=capacity)
    db.add(resource)
    db.commit()
    return resource


def _person(db, code):
    return _resource(db, code, kind=ResourceType.PERSON)


def _require(client, headers, owner_id, **body):
    return client.post(f"{ROOMS}/{owner_id}/requirements", json=body, headers=headers)


def _needs(client, headers, owner_id, target_id, **extra):
    res = _require(client, headers, owner_id, target_resource_id=target_id, **extra)
    assert res.status_code == 201, res.text
    return res.json()


def _needs_kind(client, headers, owner_id, kind, **extra):
    res = _require(client, headers, owner_id, target_kind=kind, **extra)
    assert res.status_code == 201, res.text
    return res.json()


def _book(client, headers, resource_id, key, start="09:00", end="10:00", on=DAY, **extra):
    return client.post(
        f"{ROOMS}/{resource_id}/reservations",
        json={"date": str(on), "start": start, "end": end, "purpose": "Surgery", **extra},
        headers={**headers, "Idempotency-Key": f"booking-{key}"},
    )


def _held_ids(res):
    return [child["resource_id"] for child in res.json()["children"]]


def _count(db):
    return db.query(Reservation).count()


def _hold(db, resource, start, end, key, on=DAY):
    hold = Reservation(
        resource_id=resource.id,
        reserved_date=on,
        time_window_start=datetime.time.fromisoformat(start),
        time_window_end=datetime.time.fromisoformat(end),
        purpose="Written straight in",
        requested_by_id="ADM001",
        idempotency_key=key,
        request_fingerprint="x" * 64,
        quantity=1,
        mode=resource.mode,
        status=ReservationStatus.HELD,
    )
    db.add(hold)
    db.commit()
    return hold


def _set_default(client, headers, value):
    res = client.patch(
        "/api/v1/admin/organization",
        json={"default_requirement_enforcement": value},
        headers=headers,
    )
    assert res.status_code == 200, res.text


# -- Nothing required: nothing changes ----------------------------------------


def test_a_booking_with_no_requirements_is_as_it_was(client, db, seed_users):
    headers = _admin(client)
    room = _resource(db, "OR-1")

    res = _book(client, headers, room.id, "plain")

    assert res.status_code == 201, res.text
    body = res.json()
    assert body["children"] == []
    assert body["unmet"] == []
    assert body["parent_reservation_id"] is None
    assert _count(db) == 1


# -- Saving a requirement -------------------------------------------------------


def test_a_requirement_names_one_target_and_is_read_back(client, db, seed_users):
    headers = _admin(client)
    room = _resource(db, "OR-1")
    crew = _resource(db, "CREW")

    saved = _needs(client, headers, room.id, crew.id, before_minutes=15, after_minutes=30)

    assert saved["owner_kind"] == "RESOURCE"
    assert saved["owner_id"] == room.id
    assert saved["target_resource_id"] == crew.id
    assert saved["target_kind"] is None
    assert (saved["quantity"], saved["before_minutes"], saved["after_minutes"]) == (1, 15, 30)
    assert saved["enforcement"] is None
    listed = client.get(f"{ROOMS}/{room.id}/requirements", headers=headers)
    assert [row["id"] for row in listed.json()] == [saved["id"]]


def test_exactly_one_target_is_needed(client, db, seed_users):
    headers = _admin(client)
    room = _resource(db, "OR-1")
    crew = _resource(db, "CREW")

    both = _require(client, headers, room.id, target_resource_id=crew.id, target_kind="PERSON")
    neither = _require(client, headers, room.id)

    assert both.status_code == 422
    assert neither.status_code == 422
    assert db.query(ResourceRequirement).count() == 0


def test_a_target_has_to_be_a_resource_of_this_organization(client, db, seed_users):
    headers = _admin(client)
    room = _resource(db, "OR-1")

    res = _require(client, headers, room.id, target_resource_id=9999)

    assert res.status_code == 422
    assert res.json()["code"] == "INVALID_VALUE"


def test_more_than_one_of_a_named_resource_needs_it_to_be_a_pool(client, db, seed_users):
    headers = _admin(client)
    room = _resource(db, "OR-1")
    crew = _resource(db, "CREW")
    carts = _resource(db, "CARTS", mode=ResourceMode.POOLED, capacity=5)

    refused = _require(client, headers, room.id, target_resource_id=crew.id, quantity=2)
    accepted = _require(client, headers, room.id, target_resource_id=carts.id, quantity=2)

    assert refused.status_code == 422
    assert accepted.status_code == 201, accepted.text


def test_the_same_target_twice_is_a_conflict(client, db, seed_users):
    headers = _admin(client)
    room = _resource(db, "OR-1")
    crew = _resource(db, "CREW")
    _needs(client, headers, room.id, crew.id)

    again = _require(client, headers, room.id, target_resource_id=crew.id)

    assert again.status_code == 409
    assert again.json()["code"] == "ALREADY_EXISTS"


def test_a_requirement_can_be_removed_once(client, db, seed_users):
    headers = _admin(client)
    room = _resource(db, "OR-1")
    crew = _resource(db, "CREW")
    saved = _needs(client, headers, room.id, crew.id)
    url = f"{ROOMS}/{room.id}/requirements/{saved['id']}"

    assert client.delete(url, headers=headers).status_code == 204
    assert client.delete(url, headers=headers).status_code == 404
    assert client.get(f"{ROOMS}/{room.id}/requirements", headers=headers).json() == []


def test_only_an_org_admin_changes_requirements_and_any_user_reads_them(client, db, seed_users):
    admin = _admin(client)
    room = _resource(db, "OR-1")
    crew = _resource(db, "CREW")
    saved = _needs(client, admin, room.id, crew.id)
    staff = login(client, "staff@test.internal", STAFF_PASSWORD)

    assert _require(client, staff, room.id, target_resource_id=crew.id).status_code == 403
    url = f"{ROOMS}/{room.id}/requirements/{saved['id']}"
    assert client.delete(url, headers=staff).status_code == 403
    assert client.get(f"{ROOMS}/{room.id}/requirements", headers=staff).status_code == 200


def test_a_requirement_that_closes_a_loop_is_refused(client, db, seed_users):
    headers = _admin(client)
    a = _resource(db, "A")
    b = _resource(db, "B")
    c = _resource(db, "C")
    _needs(client, headers, a.id, b.id)
    _needs(client, headers, b.id, c.id)

    loop = _require(client, headers, c.id, target_resource_id=a.id)
    itself = _require(client, headers, a.id, target_resource_id=a.id)

    assert loop.status_code == 422
    assert itself.status_code == 422
    assert db.query(ResourceRequirement).count() == 2


# -- A specific target ------------------------------------------------------------


def test_a_named_target_is_held_with_its_padding(client, db, seed_users):
    headers = _admin(client)
    room = _resource(db, "OR-1")
    crew = _resource(db, "CREW")
    _needs(client, headers, room.id, crew.id, before_minutes=15, after_minutes=30)

    res = _book(client, headers, room.id, "padded")

    assert res.status_code == 201, res.text
    body = res.json()
    (child,) = body["children"]
    assert child["resource_id"] == crew.id
    assert (child["start"], child["end"]) == ("08:45:00", "10:30:00")
    assert child["date"] == str(DAY)
    assert child["parent_reservation_id"] == body["id"]
    assert child["status"] == "HELD"
    assert (body["start"], body["end"]) == ("09:00:00", "10:00:00")
    busy = client.get(
        f"{ROOMS}/{crew.id}/availability",
        params={"from": str(DAY), "to": str(DAY)},
        headers=headers,
    ).json()["busy"]
    assert [(b["start"], b["end"]) for b in busy] == [("08:45:00", "10:30:00")]


def test_a_named_target_that_is_busy_refuses_a_required_booking(client, db, seed_users):
    headers = _admin(client)
    room = _resource(db, "OR-1")
    crew = _resource(db, "CREW")
    _needs(client, headers, room.id, crew.id, after_minutes=30, enforcement="REQUIRED")
    _hold(db, crew, "10:00", "10:30", "crew-busy")

    res = _book(client, headers, room.id, "blocked")

    # The padding is what reaches the crew's hold: 09:00 to 10:00 alone would not.
    assert res.status_code == 409
    assert res.json()["code"] == "REQUIREMENT_UNSATISFIED"
    assert len(res.json()["detail"]["conflicts"]) == 1
    assert _count(db) == 1


def test_a_pooled_target_is_held_by_units(client, db, seed_users):
    headers = _admin(client)
    room = _resource(db, "OR-1")
    carts = _resource(db, "CARTS", mode=ResourceMode.POOLED, capacity=3)
    _needs(client, headers, room.id, carts.id, quantity=2, enforcement="REQUIRED")

    first = _book(client, headers, room.id, "carts-1")
    other = _resource(db, "OR-2")
    _needs(client, headers, other.id, carts.id, quantity=2, enforcement="REQUIRED")
    second = _book(client, headers, other.id, "carts-2")

    assert first.status_code == 201, first.text
    assert first.json()["children"][0]["quantity"] == 2
    assert second.status_code == 409
    assert second.json()["code"] == "REQUIREMENT_UNSATISFIED"


def test_a_shared_target_is_never_refused(client, db, seed_users):
    headers = _admin(client)
    room = _resource(db, "OR-1")
    lounge = _resource(db, "LOUNGE", mode=ResourceMode.SHARED)
    _needs(client, headers, room.id, lounge.id, enforcement="REQUIRED")
    _hold(db, lounge, "09:00", "10:00", "lounge-1")

    res = _book(client, headers, room.id, "shared")

    assert res.status_code == 201, res.text
    assert _held_ids(res) == [lounge.id]


def test_the_same_resource_required_twice_is_held_twice(client, db, seed_users):
    headers = _admin(client)
    room = _resource(db, "OR-1")
    scrub = _resource(db, "SCRUB")
    prep = _resource(db, "PREP")
    _needs(client, headers, room.id, scrub.id, enforcement="REQUIRED")
    _needs(client, headers, room.id, prep.id, enforcement="REQUIRED")
    _needs(client, headers, prep.id, scrub.id, enforcement="REQUIRED")

    res = _book(client, headers, room.id, "twice")

    # SCRUB is held for the room, and PREP then asks for it again. An
    # exclusive resource cannot be held twice for one window.
    assert res.status_code == 409
    assert res.json()["code"] == "REQUIREMENT_UNSATISFIED"
    assert _count(db) == 0


# -- A kind of resource -----------------------------------------------------------


def test_a_kind_is_filled_with_the_first_free_resources_by_code(client, db, seed_users):
    headers = _admin(client)
    room = _resource(db, "OR-1")
    pc = _person(db, "P-C")
    pa = _person(db, "P-A")
    pb = _person(db, "P-B")
    _needs_kind(client, headers, room.id, "PERSON", quantity=2, enforcement="REQUIRED")
    _hold(db, pa, "09:00", "10:00", "pa-busy")

    res = _book(client, headers, room.id, "kind")

    assert res.status_code == 201, res.text
    assert _held_ids(res) == [pb.id, pc.id]
    assert res.json()["unmet"] == []


def test_assignments_choose_the_resources_for_a_kind(client, db, seed_users):
    headers = _admin(client)
    room = _resource(db, "OR-1")
    _person(db, "P-A")
    _person(db, "P-B")
    pc = _person(db, "P-C")
    _needs_kind(client, headers, room.id, "PERSON", enforcement="REQUIRED")

    res = _book(client, headers, room.id, "assigned", assignments={"PERSON": [pc.id]})

    assert res.status_code == 201, res.text
    assert _held_ids(res) == [pc.id]


def test_an_assigned_resource_that_is_busy_is_a_gap_and_is_not_swapped(client, db, seed_users):
    headers = _admin(client)
    room = _resource(db, "OR-1")
    pa = _person(db, "P-A")
    _person(db, "P-B")
    _needs_kind(client, headers, room.id, "PERSON", enforcement="ADVISORY")
    _hold(db, pa, "09:00", "10:00", "pa-busy")

    res = _book(client, headers, room.id, "no-swap", assignments={"PERSON": [pa.id]})

    assert res.status_code == 201, res.text
    assert res.json()["children"] == []
    (gap,) = res.json()["unmet"]
    assert gap["target_kind"] == "PERSON"
    assert gap["quantity"] == 1
    assert len(gap["conflicts"]) == 1


def test_an_assignment_of_the_wrong_kind_is_refused(client, db, seed_users):
    headers = _admin(client)
    room = _resource(db, "OR-1")
    other_room = _resource(db, "OR-2")
    _person(db, "P-A")
    _needs_kind(client, headers, room.id, "PERSON")

    res = _book(client, headers, room.id, "wrong-kind", assignments={"PERSON": [other_room.id]})

    assert res.status_code == 422
    assert res.json()["code"] == "INVALID_VALUE"
    assert _count(db) == 0


def test_an_assignment_from_another_organization_is_refused(client, db, seed_users):
    headers = _admin(client)
    room = _resource(db, "OR-1")
    _needs_kind(client, headers, room.id, "PERSON")
    db.add(Organization(id="other", name="Other"))
    db.commit()
    stranger = Resource(
        code="P-X", label="P-X", resource_type=ResourceType.PERSON, organization_id="other"
    )
    db.add(stranger)
    db.commit()

    res = _book(client, headers, room.id, "stranger", assignments={"PERSON": [stranger.id]})

    assert res.status_code == 422
    assert _count(db) == 0


def test_an_assignment_no_requirement_asks_for_is_refused(client, db, seed_users):
    headers = _admin(client)
    room = _resource(db, "OR-1")
    pa = _person(db, "P-A")

    res = _book(client, headers, room.id, "unused", assignments={"PERSON": [pa.id]})

    assert res.status_code == 422
    assert _count(db) == 0


def test_a_kind_never_picks_the_resource_that_asked(client, db, seed_users):
    headers = _admin(client)
    room = _resource(db, "AAA-1")
    spare = _resource(db, "ZZZ-9")
    _needs_kind(client, headers, room.id, "ROOM", enforcement="REQUIRED")

    res = _book(client, headers, room.id, "not-itself")

    assert res.status_code == 201, res.text
    assert _held_ids(res) == [spare.id]


# -- Enforcement ----------------------------------------------------------------------


def test_a_required_requirement_that_cannot_be_met_holds_nothing(client, db, seed_users):
    headers = _admin(client)
    room = _resource(db, "OR-1")
    crew = _resource(db, "CREW")
    nurse = _resource(db, "NURSE")
    _needs(client, headers, room.id, crew.id, enforcement="REQUIRED")
    _needs(client, headers, room.id, nurse.id, enforcement="REQUIRED")
    _hold(db, nurse, "09:30", "10:30", "nurse-busy")

    res = _book(client, headers, room.id, "refused")

    assert res.status_code == 409
    body = res.json()
    assert body["code"] == "REQUIREMENT_UNSATISFIED"
    assert "NURSE" in body["detail"]["message"]
    assert len(body["detail"]["conflicts"]) == 1
    # The crew was free and was held first; the refusal rolls it back with the
    # booking, so only the nurse's own hold written above is left.
    assert _count(db) == 1
    assert db.query(Reservation).filter(Reservation.resource_id == room.id).count() == 0
    assert db.query(Reservation).filter(Reservation.resource_id == crew.id).count() == 0


def test_an_advisory_requirement_that_cannot_be_met_is_reported(client, db, seed_users):
    headers = _admin(client)
    room = _resource(db, "OR-1")
    crew = _resource(db, "CREW")
    nurse = _resource(db, "NURSE")
    saved = _needs(client, headers, room.id, nurse.id, enforcement="ADVISORY")
    _needs(client, headers, room.id, crew.id, enforcement="ADVISORY")
    _hold(db, nurse, "09:00", "10:00", "nurse-busy")

    res = _book(client, headers, room.id, "advisory")

    assert res.status_code == 201, res.text
    body = res.json()
    assert _held_ids(res) == [crew.id]
    (gap,) = body["unmet"]
    assert gap["requirement_id"] == saved["id"]
    assert gap["enforcement"] == "ADVISORY"
    assert gap["owner_kind"] == "RESOURCE"
    assert gap["target_resource_id"] == nurse.id
    assert "NURSE" in gap["message"]
    assert _count(db) == 3


def test_a_requirement_with_no_enforcement_follows_the_organization(client, db, seed_users):
    headers = _admin(client)
    room = _resource(db, "OR-1")
    nurse = _resource(db, "NURSE")
    _needs(client, headers, room.id, nurse.id)
    _hold(db, nurse, "09:00", "10:00", "nurse-busy")

    refused = _book(client, headers, room.id, "default-required")
    _set_default(client, headers, "ADVISORY")
    booked = _book(client, headers, room.id, "default-advisory")
    _set_default(client, headers, "REQUIRED")
    refused_again = _book(client, headers, room.id, "default-required-again", start="09:30")

    assert refused.status_code == 409
    assert booked.status_code == 201, booked.text
    assert booked.json()["unmet"][0]["enforcement"] == "ADVISORY"
    assert refused_again.status_code == 409


def test_the_organization_setting_is_read_and_changed_by_an_org_admin_only(client, db, seed_users):
    headers = _admin(client)
    staff = login(client, "staff@test.internal", STAFF_PASSWORD)

    first = client.get("/api/v1/admin/organization", headers=headers)
    changed = client.patch(
        "/api/v1/admin/organization",
        json={"default_requirement_enforcement": "ADVISORY"},
        headers=headers,
    )

    assert first.status_code == 200
    assert first.json()["default_requirement_enforcement"] == "REQUIRED"
    assert changed.status_code == 200
    assert changed.json()["default_requirement_enforcement"] == "ADVISORY"
    assert (
        client.get("/api/v1/admin/organization", headers=headers).json()[
            "default_requirement_enforcement"
        ]
        == "ADVISORY"
    )
    assert client.get("/api/v1/admin/organization", headers=staff).status_code == 403
    assert (
        client.patch(
            "/api/v1/admin/organization",
            json={"default_requirement_enforcement": "REQUIRED"},
            headers=staff,
        ).status_code
        == 403
    )


def test_the_organization_setting_refuses_what_it_does_not_know(client, db, seed_users):
    headers = _admin(client)
    url = "/api/v1/admin/organization"

    assert (
        client.patch(
            url, json={"default_requirement_enforcement": "LOUD"}, headers=headers
        ).status_code
        == 422
    )
    assert client.patch(url, json={}, headers=headers).status_code == 422
    assert client.patch(url, json={"name": "Renamed"}, headers=headers).status_code == 422


# -- Chains ---------------------------------------------------------------------------


def _chain(client, db, headers, length):
    """R0 requires R1 requires ... R<length>, every link REQUIRED."""
    rooms = [_resource(db, f"R{i}") for i in range(length + 1)]
    for here, there in zip(rooms, rooms[1:], strict=False):
        _needs(client, headers, here.id, there.id, enforcement="REQUIRED")
    return rooms


def test_a_chain_is_held_to_depth_four(client, db, seed_users):
    headers = _admin(client)
    rooms = _chain(client, db, headers, 4)

    res = _book(client, headers, rooms[0].id, "chain")

    assert res.status_code == 201, res.text
    assert _held_ids(res) == [room.id for room in rooms[1:]]
    # Each child names the booking that started it, not the child before it.
    assert {child["parent_reservation_id"] for child in res.json()["children"]} == {
        res.json()["id"]
    }


def test_a_chain_deeper_than_four_is_refused_when_required(client, db, seed_users):
    headers = _admin(client)
    rooms = _chain(client, db, headers, 5)

    res = _book(client, headers, rooms[0].id, "too-deep")

    assert res.status_code == 409
    assert res.json()["code"] == "REQUIREMENT_UNSATISFIED"
    assert "deeper than 4" in res.json()["detail"]["message"]
    assert _count(db) == 0


def test_a_chain_deeper_than_four_is_reported_when_advisory(client, db, seed_users):
    headers = _admin(client)
    rooms = _chain(client, db, headers, 4)
    last = _resource(db, "R5")
    _needs(client, headers, rooms[4].id, last.id, enforcement="ADVISORY")

    res = _book(client, headers, rooms[0].id, "deep-advisory")

    assert res.status_code == 201, res.text
    assert len(res.json()["children"]) == 4
    (gap,) = res.json()["unmet"]
    assert "deeper than 4" in gap["message"]


# -- Midnight ------------------------------------------------------------------------


def test_padding_that_crosses_midnight_is_a_422_and_holds_nothing(client, db, seed_users):
    headers = _admin(client)
    room = _resource(db, "OR-1")
    crew = _resource(db, "CREW")
    _needs(client, headers, room.id, crew.id, after_minutes=60, enforcement="ADVISORY")

    late = _book(client, headers, room.id, "late", start="22:30", end="23:30")
    early_requirement = _resource(db, "OR-2")
    _needs(client, headers, early_requirement.id, crew.id, before_minutes=30)
    early = _book(client, headers, early_requirement.id, "early", start="00:10", end="01:00")

    assert late.status_code == 422
    assert late.json()["code"] == "INVALID_VALUE"
    assert early.status_code == 422
    assert _count(db) == 0


def test_a_parent_that_crosses_midnight_books_when_nothing_is_padded(client, db, seed_users):
    headers = _admin(client)
    room = _resource(db, "OR-1")
    crew = _resource(db, "CREW")
    _needs(client, headers, room.id, crew.id, enforcement="REQUIRED")

    res = _book(client, headers, room.id, "night", start="22:00", end="06:00")

    assert res.status_code == 201, res.text
    (child,) = res.json()["children"]
    assert (child["start"], child["end"]) == ("22:00:00", "06:00:00")


def test_padding_inside_the_last_day_of_a_night_window_is_fine(client, db, seed_users):
    headers = _admin(client)
    room = _resource(db, "OR-1")
    crew = _resource(db, "CREW")
    _needs(client, headers, room.id, crew.id, after_minutes=30, enforcement="REQUIRED")

    res = _book(client, headers, room.id, "night-pad", start="22:00", end="06:00")

    assert res.status_code == 201, res.text
    (child,) = res.json()["children"]
    assert (child["start"], child["end"]) == ("22:00:00", "06:30:00")


# -- Cancelling ---------------------------------------------------------------------


def test_cancelling_the_parent_cancels_its_held_children(client, db, seed_users):
    headers = _admin(client)
    room = _resource(db, "OR-1")
    crew = _resource(db, "CREW")
    nurse = _resource(db, "NURSE")
    _needs(client, headers, room.id, crew.id, enforcement="REQUIRED")
    _needs(client, headers, room.id, nurse.id, enforcement="REQUIRED")
    res = _book(client, headers, room.id, "cascade")
    parent_id = res.json()["id"]
    first, second = (child["id"] for child in res.json()["children"])
    # One child was already cancelled by hand.
    cancelled = client.delete(f"{ROOMS}/{crew.id}/reservations/{first}", headers=headers)
    assert cancelled.status_code in (200, 204), cancelled.text
    assert db.get(Reservation, parent_id).status is ReservationStatus.HELD

    gone = client.delete(f"{ROOMS}/{room.id}/reservations/{parent_id}", headers=headers)

    assert gone.status_code in (200, 204), gone.text
    db.expire_all()
    statuses = {
        row.id: row.status
        for row in db.query(Reservation).filter(Reservation.id.in_([parent_id, first, second]))
    }
    assert set(statuses.values()) == {ReservationStatus.CANCELLED}
    # The window is free again for the same booking.
    again = _book(client, headers, room.id, "cascade-again")
    assert again.status_code == 201, again.text


def test_a_replay_answers_with_the_children_it_took(client, db, seed_users):
    headers = _admin(client)
    room = _resource(db, "OR-1")
    crew = _resource(db, "CREW")
    _needs(client, headers, room.id, crew.id, enforcement="REQUIRED")
    first = _book(client, headers, room.id, "replay")

    again = _book(client, headers, room.id, "replay")

    assert again.status_code == 200, again.text
    assert again.json()["id"] == first.json()["id"]
    assert _held_ids(again) == [crew.id]
    assert again.json()["unmet"] == []
    assert _count(db) == 2


# -- Availability ---------------------------------------------------------------------


def _can_hold(client, headers, resource_id, **params):
    return client.get(
        f"{ROOMS}/{resource_id}/availability",
        params={
            "from": str(DAY),
            "to": str(DAY),
            "with_requirements": "true",
            "start": "09:00",
            "end": "10:00",
            **params,
        },
        headers=headers,
    )


def test_availability_without_the_flag_says_nothing_about_requirements(client, db, seed_users):
    headers = _admin(client)
    room = _resource(db, "OR-1")
    crew = _resource(db, "CREW")
    _needs(client, headers, room.id, crew.id)

    body = client.get(
        f"{ROOMS}/{room.id}/availability",
        params={"from": str(DAY), "to": str(DAY)},
        headers=headers,
    ).json()

    assert body["requirements_met"] is None
    assert body["unmet"] == []


def test_availability_with_requirements_holds_nothing(client, db, seed_users):
    headers = _admin(client)
    room = _resource(db, "OR-1")
    crew = _resource(db, "CREW")
    _needs(client, headers, room.id, crew.id, enforcement="REQUIRED")

    free = _can_hold(client, headers, room.id)
    assert free.status_code == 200, free.text
    assert free.json()["requirements_met"] is True
    assert free.json()["unmet"] == []
    assert _count(db) == 0

    _hold(db, crew, "09:30", "10:30", "crew-busy")
    blocked = _can_hold(client, headers, room.id).json()
    assert blocked["requirements_met"] is False
    (gap,) = blocked["unmet"]
    assert gap["target_resource_id"] == crew.id
    assert _count(db) == 1

    # The booking route agrees with what availability said.
    assert _book(client, headers, room.id, "agree").status_code == 409


def test_availability_reports_an_advisory_gap_too(client, db, seed_users):
    headers = _admin(client)
    room = _resource(db, "OR-1")
    crew = _resource(db, "CREW")
    _needs(client, headers, room.id, crew.id, enforcement="ADVISORY")
    _hold(db, crew, "09:00", "10:00", "crew-busy")

    body = _can_hold(client, headers, room.id).json()

    assert body["requirements_met"] is False
    assert body["unmet"][0]["enforcement"] == "ADVISORY"


def test_availability_is_not_met_when_the_resource_itself_is_taken(client, db, seed_users):
    headers = _admin(client)
    room = _resource(db, "OR-1")
    _hold(db, room, "09:00", "10:00", "room-busy")

    body = _can_hold(client, headers, room.id).json()

    assert body["requirements_met"] is False


def test_availability_with_requirements_needs_one_date_and_a_window(client, db, seed_users):
    headers = _admin(client)
    room = _resource(db, "OR-1")
    base = {"from": str(DAY), "to": str(DAY), "with_requirements": "true"}
    url = f"{ROOMS}/{room.id}/availability"

    no_window = client.get(url, params=base, headers=headers)
    two_days = _can_hold(client, headers, room.id, to=str(DAY + datetime.timedelta(days=1)))
    no_length = _can_hold(client, headers, room.id, end="09:00")

    assert no_window.status_code == 422
    assert two_days.status_code == 422
    assert no_length.status_code == 422


# -- The timetable: reported, never refused ------------------------------------------


def _timetable_slot(db, room, activity=None, start=datetime.time(9), end=datetime.time(10)):
    if activity is None:
        cycle = PlanningCycle(
            cycle_label="Cycle",
            date_bounds_start=org_today() - datetime.timedelta(days=30),
            date_bounds_end=org_today() + datetime.timedelta(days=300),
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
        **weekly(TOMORROW.isoweekday()),
        time_window_start=start,
        time_window_end=end,
        activity_id=activity.id,
        resource_id=room.id,
    )
    db.add(slot)
    db.commit()
    return slot


def _conflicts(client, headers):
    res = client.get(
        "/api/v1/schedule/conflicts",
        params={"from": str(TOMORROW), "to": str(TOMORROW + datetime.timedelta(days=6))},
        headers=headers,
    )
    assert res.status_code == 200, res.text
    return res.json()["conflicts"]


def test_a_slot_whose_room_requirement_is_unmet_is_reported(client, db, seed_users):
    headers = _admin(client)
    room = _resource(db, "LH-1")
    _needs_kind(client, headers, room.id, "PERSON", enforcement="REQUIRED")
    slot = _timetable_slot(db, room)

    found = [c for c in _conflicts(client, headers) if c["kind"] == "requirement_unmet"]

    (gap,) = found
    assert gap["items"][0]["id"] == slot.id
    assert gap["resource_id"] == room.id
    assert gap["requirement_id"] is not None
    assert "PERSON" in gap["message"]
    assert gap["date"] == str(TOMORROW)


def test_a_slot_whose_activity_requirement_is_unmet_is_reported(client, db, seed_users):
    headers = _admin(client)
    room = _resource(db, "LH-1")
    nurse = _person(db, "P-A")
    slot = _timetable_slot(db, room)
    saved = client.post(
        f"/api/v1/schedule/activities/{slot.activity_id}/requirements",
        json={"target_resource_id": nurse.id},
        headers=headers,
    )
    assert saved.status_code == 201, saved.text
    _hold(db, nurse, "09:00", "10:00", "nurse-busy", on=TOMORROW)

    found = [c for c in _conflicts(client, headers) if c["kind"] == "requirement_unmet"]

    (gap,) = found
    assert gap["requirement_id"] == saved.json()["id"]


def test_a_requirement_the_timetable_can_have_is_not_reported(client, db, seed_users):
    headers = _admin(client)
    room = _resource(db, "LH-1")
    _person(db, "P-A")
    _needs_kind(client, headers, room.id, "PERSON", enforcement="REQUIRED")
    _timetable_slot(db, room)

    kinds = {c["kind"] for c in _conflicts(client, headers)}

    assert "requirement_unmet" not in kinds


def test_saving_a_slot_reports_what_it_cannot_have_and_still_saves(client, db, seed_users):
    headers = _admin(client)
    room = _resource(db, "LH-1")
    _needs_kind(client, headers, room.id, "PERSON", enforcement="REQUIRED")
    cycle = PlanningCycle(
        cycle_label="Cycle",
        date_bounds_start=org_today() - datetime.timedelta(days=30),
        date_bounds_end=org_today() + datetime.timedelta(days=300),
        operational_status=True,
    )
    db.add(cycle)
    db.flush()
    activity = Activity(
        activity_code="CS101", activity_title="CS", unit_code="CSE", cycle_id=cycle.id
    )
    db.add(activity)
    db.commit()

    created = client.post(
        "/api/v1/schedule/slots",
        json={
            "rrule": weekly_rule(TOMORROW.isoweekday()),
            "time_window_start": "09:00:00",
            "time_window_end": "10:00:00",
            "activity_id": activity.id,
            "target_room_identifier": "LH-1",
        },
        headers=headers,
    )

    assert created.status_code == 200, created.text
    (gap,) = created.json()["requirements_unmet"]
    assert gap["date"] == str(TOMORROW)
    assert db.query(StructuralMasterSlot).count() == 1

    moved = client.patch(
        f"/api/v1/schedule/slots/{created.json()['id']}",
        json={"time_window_start": "11:00:00", "time_window_end": "12:00:00"},
        headers=headers,
    )
    assert moved.status_code == 200, moved.text
    assert len(moved.json()["requirements_unmet"]) == 1


def test_a_slot_with_nothing_required_reports_nothing(client, db, seed_users):
    headers = _admin(client)
    room = _resource(db, "LH-1")
    slot = _timetable_slot(db, room)

    moved = client.patch(
        f"/api/v1/schedule/slots/{slot.id}",
        json={"time_window_start": "11:00:00", "time_window_end": "12:00:00"},
        headers=headers,
    )

    assert moved.status_code == 200, moved.text
    assert moved.json()["requirements_unmet"] == []


def test_the_import_reports_an_unmet_requirement_and_still_imports(client, db, seed_users):
    headers = _admin(client)
    room = _resource(db, "LH-201")
    saved = _needs_kind(client, headers, room.id, "PERSON", enforcement="REQUIRED")
    cycle = _make_cycle(db)

    res = _upload(client, headers, cycle.id, _csv(_row(room="LH-201")))

    assert res.status_code == 200, res.text
    body = res.json()
    (gap,) = body["requirements_unmet"]
    assert gap["requirement_id"] == saved["id"]
    assert gap["slot_id"] == db.query(StructuralMasterSlot).one().id
    assert gap["date"] == str(TOMORROW)


def test_the_import_reports_nothing_when_nothing_is_required(client, db, seed_users):
    headers = _admin(client)
    cycle = _make_cycle(db)

    res = _upload(client, headers, cycle.id, _csv(_row(room="LH-201")))

    assert res.status_code == 200, res.text
    assert res.json()["requirements_unmet"] == []


def test_generating_a_day_logs_an_unmet_requirement_and_still_writes_it(
    client, db, seed_users, caplog
):
    headers = _admin(client)
    room = _resource(db, "LH-1")
    _needs_kind(client, headers, room.id, "PERSON", enforcement="REQUIRED")
    _timetable_slot(db, room)

    with caplog.at_level(logging.WARNING):
        written = generate_daily_ledger_entries(TOMORROW, db)

    assert written == 1
    assert any("unmet requirement" in record.getMessage() for record in caplog.records)


def test_the_activity_requirement_routes(client, db, seed_users):
    headers = _admin(client)
    staff = login(client, "staff@test.internal", STAFF_PASSWORD)
    room = _resource(db, "LH-1")
    nurse = _person(db, "P-A")
    slot = _timetable_slot(db, room)
    base = f"/api/v1/schedule/activities/{slot.activity_id}/requirements"

    saved = client.post(base, json={"target_kind": "PERSON", "quantity": 2}, headers=headers)
    assert saved.status_code == 201, saved.text
    assert saved.json()["owner_kind"] == "ACTIVITY"
    assert saved.json()["owner_id"] == slot.activity_id
    assert client.post(base, json={"target_kind": "PERSON"}, headers=headers).status_code == 409
    assert client.post(base, json={}, headers=headers).status_code == 422
    assert (
        client.post(base, json={"target_resource_id": nurse.id}, headers=staff).status_code == 403
    )
    assert [row["id"] for row in client.get(base, headers=headers).json()] == [saved.json()["id"]]
    assert (
        client.get("/api/v1/schedule/activities/9999/requirements", headers=headers).status_code
        == 404
    )

    gone = client.delete(f"{base}/{saved.json()['id']}", headers=headers)
    assert gone.status_code == 204
    assert client.delete(f"{base}/{saved.json()['id']}", headers=headers).status_code == 404
    assert client.get(base, headers=headers).json() == []
