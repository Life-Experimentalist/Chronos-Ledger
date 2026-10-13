# Copyright 2026 Chronos Ledger Contributors
# Licensed under the Apache License, Version 2.0
"""A booking an integration can find again by its own name for it.

Without a reference an integration has to keep Chronos's id for every booking
it makes, and a booking whose id it lost is one it can no longer find, change
or let go. These pin external_ref: unique per caller, refused with the id of
the booking that already has it, found through the list by the caller and
nobody else, and settable afterwards under the same rule.
"""

import pytest

from app.api.v1.endpoints import resources
from app.core.config import get_settings
from app.core.errors import ErrorCode
from app.models.db import ChangeMarker, Reservation, ReservationStatus
from tests.conftest import ADMIN_PASSWORD, STAFF_PASSWORD, login
from tests.test_reservations import TUESDAY, WEDNESDAY, _room, _unit_admin

LIST = "/api/v1/resources/reservations"


@pytest.fixture()
def change_feed_on(monkeypatch):
    monkeypatch.setenv("CHANGE_FEED_ENABLED", "true")
    get_settings.cache_clear()
    yield
    get_settings.cache_clear()


def _admin(client):
    return login(client, "admin@test.internal", ADMIN_PASSWORD)


def _book(client, headers, resource_id, key, ref=None, on=TUESDAY, start="14:00", end="15:00"):
    body = {"date": str(on), "start": start, "end": end, "purpose": "Ward round"}
    if ref is not None:
        body["external_ref"] = ref
    return client.post(
        f"/api/v1/resources/{resource_id}/reservations",
        json=body,
        headers={**headers, "Idempotency-Key": key},
    )


def _update(client, headers, resource_id, reservation_id, body):
    return client.patch(
        f"/api/v1/resources/{resource_id}/reservations/{reservation_id}",
        json=body,
        headers=headers,
    )


def _find(client, headers, ref):
    res = client.get(LIST, params={"external_ref": ref}, headers=headers)
    assert res.status_code == 200, res.text
    return res.json()


def _issue_key(client, headers):
    res = client.post(
        "/api/v1/api-keys/",
        json={
            "label": "Booking integration",
            "user_id": "ADM001",
            "scopes": ["resources:read", "resources:write"],
        },
        headers=headers,
    )
    assert res.status_code == 201, res.text
    return {"X-API-Key": res.json()["api_key"]}


# -- Taking a reference -------------------------------------------------------


def test_a_booking_carries_the_reference_it_was_made_with(client, db, seed_users):
    room = _room(db)
    res = _book(client, _admin(client), room.id, "ref-key-0001", ref="ext-001")
    assert res.status_code == 201, res.text
    assert res.json()["external_ref"] == "ext-001"
    assert db.get(Reservation, res.json()["id"]).external_ref == "ext-001"


def test_a_booking_without_a_reference_has_none(client, db, seed_users):
    room = _room(db)
    res = _book(client, _admin(client), room.id, "ref-key-0001")
    assert res.status_code == 201, res.text
    assert res.json()["external_ref"] is None


def test_any_number_of_bookings_may_leave_the_reference_unset(client, db, seed_users):
    """A null is no reference, so it cannot clash with another null."""
    room = _room(db)
    headers = _admin(client)
    first = _book(client, headers, room.id, "ref-key-0001", start="09:00", end="10:00")
    second = _book(client, headers, room.id, "ref-key-0002", start="10:00", end="11:00")
    third = _book(client, headers, room.id, "ref-key-0003", start="11:00", end="12:00")
    assert [r.status_code for r in (first, second, third)] == [201, 201, 201]


def test_an_empty_reference_is_refused(client, db, seed_users):
    room = _room(db)
    res = _book(client, _admin(client), room.id, "ref-key-0001", ref="")
    assert res.status_code == 422


def test_a_reference_longer_than_the_column_is_refused(client, db, seed_users):
    room = _room(db)
    res = _book(client, _admin(client), room.id, "ref-key-0001", ref="x" * 121)
    assert res.status_code == 422


# -- The same reference twice -------------------------------------------------


def test_a_second_booking_under_the_same_reference_is_409_naming_the_first(client, db, seed_users):
    room = _room(db)
    headers = _admin(client)
    first = _book(client, headers, room.id, "ref-key-0001", ref="ext-001").json()

    # Another day, so the window is free and only the reference is in the way.
    again = _book(client, headers, room.id, "ref-key-0002", ref="ext-001", on=WEDNESDAY)
    assert again.status_code == 409, again.text
    body = again.json()
    assert body["code"] == ErrorCode.RESERVATION_EXTERNAL_REF_TAKEN
    assert body["detail"] == {"message": resources.REF_TAKEN, "reservation_id": first["id"]}
    assert db.query(Reservation).count() == 1


def test_the_reference_is_checked_before_the_window(client, db, seed_users):
    """Booking the same thing again under a new key is told it already has it,
    not that something stands in the window, though both are true."""
    room = _room(db)
    headers = _admin(client)
    first = _book(client, headers, room.id, "ref-key-0001", ref="ext-001").json()

    again = _book(client, headers, room.id, "ref-key-0002", ref="ext-001")
    assert again.status_code == 409
    assert again.json()["code"] == ErrorCode.RESERVATION_EXTERNAL_REF_TAKEN
    assert again.json()["detail"]["reservation_id"] == first["id"]


def test_the_same_key_again_is_a_replay_and_not_a_409(client, db, seed_users):
    room = _room(db)
    headers = _admin(client)
    first = _book(client, headers, room.id, "ref-key-0001", ref="ext-001")
    again = _book(client, headers, room.id, "ref-key-0001", ref="ext-001")

    assert first.status_code == 201
    assert again.status_code == 200, again.text
    assert again.json()["id"] == first.json()["id"]
    assert db.query(Reservation).count() == 1


def test_the_same_key_with_a_different_reference_is_still_a_reused_key(client, db, seed_users):
    """The reference is part of the request, so changing it under one key is a
    different request under that key: the 422 that rule has always given."""
    room = _room(db)
    headers = _admin(client)
    assert _book(client, headers, room.id, "ref-key-0001", ref="ext-001").status_code == 201

    res = _book(client, headers, room.id, "ref-key-0001", ref="ext-002")
    assert res.status_code == 422
    assert res.json()["code"] == ErrorCode.IDEMPOTENCY_KEY_REUSED


def test_a_key_used_before_references_existed_still_replays(client, db, seed_users):
    """A booking made without a reference fingerprints as it always did, so a
    retry of it is still recognised as the same request."""
    room = _room(db)
    headers = _admin(client)
    first = _book(client, headers, room.id, "ref-key-0001")
    again = _book(client, headers, room.id, "ref-key-0001")
    assert (first.status_code, again.status_code) == (201, 200)


def test_two_callers_may_use_the_same_reference(client, db, seed_users):
    """A reference means something only to the system that chose it."""
    room = _room(db)
    mine = _book(client, _admin(client), room.id, "ref-key-0001", ref="ext-001")
    theirs = _book(
        client, _unit_admin(db, client), room.id, "ref-key-0002", ref="ext-001", on=WEDNESDAY
    )
    assert (mine.status_code, theirs.status_code) == (201, 201)


def test_a_cancelled_booking_keeps_its_reference(client, db, seed_users):
    """Cancelling is not forgetting. The reference still finds the booking, and
    booking under it again needs the reference cleared or changed first."""
    room = _room(db)
    headers = _admin(client)
    held = _book(client, headers, room.id, "ref-key-0001", ref="ext-001").json()
    client.delete(f"/api/v1/resources/{room.id}/reservations/{held['id']}", headers=headers)

    found = _find(client, headers, "ext-001")
    assert [(r["id"], r["status"]) for r in found] == [(held["id"], "CANCELLED")]

    again = _book(client, headers, room.id, "ref-key-0002", ref="ext-001")
    assert again.status_code == 409
    assert again.json()["detail"]["reservation_id"] == held["id"]

    assert _update(client, headers, room.id, held["id"], {"external_ref": None}).status_code == 200
    assert _book(client, headers, room.id, "ref-key-0003", ref="ext-001").status_code == 201


def test_two_requests_racing_for_one_reference_give_one_booking(
    client, db, seed_users, monkeypatch
):
    """The branch for the race, reached without running one.

    Blinding the check once puts the endpoint where the loser of a race is:
    it believes the reference is free, inserts, and the unique constraint
    refuses it. The answer has to be the same 409 the check gives, naming the
    booking that won, and not the 422 for a reused key it never reused.
    """
    room = _room(db)
    headers = _admin(client)
    winner = _book(client, headers, room.id, "ref-key-0001", ref="ext-001").json()

    honest = resources._by_ref
    seen = []

    def blind_once(*args, **kwargs):
        seen.append(1)
        return None if len(seen) == 1 else honest(*args, **kwargs)

    monkeypatch.setattr(resources, "_by_ref", blind_once)
    loser = _book(client, headers, room.id, "ref-key-0002", ref="ext-001", on=WEDNESDAY)

    assert loser.status_code == 409, loser.text
    assert loser.json()["code"] == ErrorCode.RESERVATION_EXTERNAL_REF_TAKEN
    assert loser.json()["detail"]["reservation_id"] == winner["id"]
    assert len(seen) == 2, "the endpoint never asked again after the database refused it"
    assert db.query(Reservation).count() == 1


# -- Finding by reference -----------------------------------------------------


def test_the_list_finds_a_booking_by_its_reference(client, db, seed_users):
    room = _room(db)
    headers = _admin(client)
    held = _book(client, headers, room.id, "ref-key-0001", ref="ext-001").json()
    _book(client, headers, room.id, "ref-key-0002", ref="ext-002", on=WEDNESDAY)

    assert [r["id"] for r in _find(client, headers, "ext-001")] == [held["id"]]
    assert _find(client, headers, "ext-404") == []


def test_the_list_matches_a_reference_exactly(client, db, seed_users):
    room = _room(db)
    headers = _admin(client)
    _book(client, headers, room.id, "ref-key-0001", ref="Ext-001")

    assert _find(client, headers, "ext-001") == []
    assert _find(client, headers, "Ext-0") == []


def test_the_list_returns_only_the_callers_bookings(client, db, seed_users):
    """Even for an ORG_ADMIN. Two callers using one string each get their own."""
    room = _room(db)
    admin = _admin(client)
    unit = _unit_admin(db, client)
    mine = _book(client, admin, room.id, "ref-key-0001", ref="ext-001").json()
    theirs = _book(client, unit, room.id, "ref-key-0002", ref="ext-001", on=WEDNESDAY).json()

    assert [r["id"] for r in _find(client, admin, "ext-001")] == [mine["id"]]
    assert [r["id"] for r in _find(client, unit, "ext-001")] == [theirs["id"]]

    everything = client.get(LIST, headers=admin)
    assert [r["id"] for r in everything.json()] == [mine["id"]]
    assert everything.headers["X-Total-Count"] == "1"


def test_the_list_without_a_filter_pages_in_id_order(client, db, seed_users):
    room = _room(db)
    headers = _admin(client)
    ids = [
        _book(
            client, headers, room.id, f"ref-key-000{n}", start=f"0{n}:00", end=f"0{n + 1}:00"
        ).json()["id"]
        for n in range(1, 4)
    ]

    page = client.get(LIST, params={"limit": 2, "offset": 1}, headers=headers)
    assert page.status_code == 200, page.text
    assert [r["id"] for r in page.json()] == ids[1:]
    assert page.headers["X-Total-Count"] == "3"


def test_staff_may_not_list_bookings(client, db, seed_users):
    staff = login(client, "staff@test.internal", STAFF_PASSWORD)
    assert client.get(LIST, headers=staff).status_code == 403


# -- Changing the reference ---------------------------------------------------


def test_a_reference_can_be_set_changed_and_cleared(client, db, seed_users):
    room = _room(db)
    headers = _admin(client)
    held = _book(client, headers, room.id, "ref-key-0001").json()

    set_ = _update(client, headers, room.id, held["id"], {"external_ref": "ext-001"})
    assert set_.status_code == 200, set_.text
    assert set_.json()["external_ref"] == "ext-001"

    changed = _update(client, headers, room.id, held["id"], {"external_ref": "ext-002"})
    assert changed.json()["external_ref"] == "ext-002"
    assert _find(client, headers, "ext-001") == []

    cleared = _update(client, headers, room.id, held["id"], {"external_ref": None})
    assert cleared.json()["external_ref"] is None
    assert db.get(Reservation, held["id"]).external_ref is None


def test_leaving_the_reference_out_leaves_it_alone(client, db, seed_users):
    room = _room(db)
    headers = _admin(client)
    held = _book(client, headers, room.id, "ref-key-0001", ref="ext-001").json()

    res = _update(client, headers, room.id, held["id"], {})
    assert res.status_code == 200, res.text
    assert res.json()["external_ref"] == "ext-001"


def test_changing_to_a_reference_already_taken_is_the_same_409(client, db, seed_users):
    room = _room(db)
    headers = _admin(client)
    first = _book(client, headers, room.id, "ref-key-0001", ref="ext-001").json()
    second = _book(client, headers, room.id, "ref-key-0002", on=WEDNESDAY).json()

    res = _update(client, headers, room.id, second["id"], {"external_ref": "ext-001"})
    assert res.status_code == 409, res.text
    assert res.json()["code"] == ErrorCode.RESERVATION_EXTERNAL_REF_TAKEN
    assert res.json()["detail"] == {"message": resources.REF_TAKEN, "reservation_id": first["id"]}
    assert db.get(Reservation, second["id"]).external_ref is None


def test_the_window_cannot_be_moved_through_an_update(client, db, seed_users):
    """Refused rather than ignored, so a caller trying it is told it did not."""
    room = _room(db)
    headers = _admin(client)
    held = _book(client, headers, room.id, "ref-key-0001").json()

    res = _update(client, headers, room.id, held["id"], {"start": "16:00"})
    assert res.status_code == 422
    assert db.get(Reservation, held["id"]).time_window_start.hour == 14


def test_a_unit_admin_may_not_change_a_booking_it_did_not_take(client, db, seed_users):
    room = _room(db)
    held = _book(client, _admin(client), room.id, "ref-key-0001").json()
    unit = _unit_admin(db, client)

    res = _update(client, unit, room.id, held["id"], {"external_ref": "mine-now"})
    assert res.status_code == 403
    assert res.json()["detail"] == resources.NOT_YOUR_HOLD_TO_CHANGE
    assert db.get(Reservation, held["id"]).external_ref is None


def test_an_update_through_the_wrong_room_is_404(client, db, seed_users):
    room = _room(db)
    other = _room(db, code="LH-202")
    headers = _admin(client)
    held = _book(client, headers, room.id, "ref-key-0001").json()

    res = _update(client, headers, other.id, held["id"], {"external_ref": "ext-001"})
    assert res.status_code == 404


def test_an_admin_changing_anothers_booking_is_held_to_their_references(client, db, seed_users):
    """Unique per requester, and the requester is the booking's."""
    room = _room(db)
    unit = _unit_admin(db, client)
    first = _book(client, unit, room.id, "ref-key-0001", ref="ext-001").json()
    second = _book(client, unit, room.id, "ref-key-0002", on=WEDNESDAY).json()
    admin = _admin(client)

    res = _update(client, admin, room.id, second["id"], {"external_ref": "ext-001"})
    assert res.status_code == 409
    assert res.json()["detail"]["reservation_id"] == first["id"]


# -- The change feed ----------------------------------------------------------


def test_changing_the_reference_leaves_one_marker(client, db, seed_users, change_feed_on):
    room = _room(db)
    headers = _admin(client)
    held = _book(client, headers, room.id, "ref-key-0001").json()
    _update(client, headers, room.id, held["id"], {"external_ref": "ext-001"})

    markers = db.query(ChangeMarker).order_by(ChangeMarker.id).all()
    assert [(m.entity_kind, m.entity_id, m.change_kind) for m in markers] == [
        ("reservation", held["id"], "created"),
        ("reservation", held["id"], "updated"),
    ]

    feed = client.get("/api/v1/changes/", params={"since": markers[0].id}, headers=headers)
    assert feed.status_code == 200, feed.text
    assert feed.json()["changes"][0]["reservation"]["external_ref"] == "ext-001"


def test_an_update_that_changes_nothing_leaves_no_marker(client, db, seed_users, change_feed_on):
    room = _room(db)
    headers = _admin(client)
    held = _book(client, headers, room.id, "ref-key-0001", ref="ext-001").json()

    assert (
        _update(client, headers, room.id, held["id"], {"external_ref": "ext-001"}).status_code
        == 200
    )
    assert _update(client, headers, room.id, held["id"], {}).status_code == 200
    assert db.query(ChangeMarker).count() == 1


def test_a_refused_reference_leaves_no_marker(client, db, seed_users, change_feed_on):
    room = _room(db)
    headers = _admin(client)
    _book(client, headers, room.id, "ref-key-0001", ref="ext-001")
    second = _book(client, headers, room.id, "ref-key-0002", on=WEDNESDAY).json()

    assert _book(client, headers, room.id, "ref-key-0003", ref="ext-001").status_code == 409
    assert (
        _update(client, headers, room.id, second["id"], {"external_ref": "ext-001"}).status_code
        == 409
    )
    assert db.query(ChangeMarker).count() == 2


# -- The whole round trip -----------------------------------------------------


def test_an_integration_works_a_booking_by_its_own_reference_alone(client, db, seed_users):
    """What the reference is for, end to end, through a key.

    The integration keeps nothing of Chronos's but the room it books: every
    later step starts from the reference, finds the booking by it, and acts on
    what the find returned.
    """
    room = _room(db)
    key = _issue_key(client, _admin(client))

    made = _book(client, key, room.id, "integration-0001", ref="visit-42")
    assert made.status_code == 201, made.text

    (found,) = _find(client, key, "visit-42")
    assert found["status"] == "HELD"
    assert found["resource_id"] == room.id

    moved = _update(client, key, found["resource_id"], found["id"], {"external_ref": "visit-43"})
    assert moved.status_code == 200, moved.text
    assert _find(client, key, "visit-42") == []

    (found,) = _find(client, key, "visit-43")
    cancelled = client.delete(
        f"/api/v1/resources/{found['resource_id']}/reservations/{found['id']}", headers=key
    )
    assert cancelled.status_code == 200, cancelled.text

    (found,) = _find(client, key, "visit-43")
    assert found["status"] == "CANCELLED"
    assert db.get(Reservation, found["id"]).status is ReservationStatus.CANCELLED
