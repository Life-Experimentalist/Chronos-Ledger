# Copyright 2026 Chronos Ledger Contributors
# Licensed under the Apache License, Version 2.0
"""What changed about the rooms and the bookings, for a system that keeps a copy.

An integrator holding its own rooms had no way to learn that one moved: the
websocket reaches a signed-in socket and not a service behind another firewall,
and re-reading every room on a timer costs the building rather than the change.
These pin the two properties that make the feed usable: an entry carries the
row as it now stands, so applying one twice is applying it once, and a row that
changed three times is one entry and not three.
"""

import pytest

from app.core.config import get_settings
from app.models.db import ChangeMarker
from tests.conftest import ADMIN_PASSWORD, MEMBER_PASSWORD, STAFF_PASSWORD, login
from tests.test_reservations import TUESDAY, _issue_key, _room, _unit_admin


@pytest.fixture()
def change_feed_on(monkeypatch):
    monkeypatch.setenv("CHANGE_FEED_ENABLED", "true")
    get_settings.cache_clear()
    yield
    get_settings.cache_clear()


def _admin(client):
    return login(client, "admin@test.internal", ADMIN_PASSWORD)


def _make_room(client, headers, code="LH-201", **extra):
    res = client.post("/api/v1/resources/", json={"code": code, **extra}, headers=headers)
    assert res.status_code == 201, res.text
    return res.json()


def _rename(client, headers, resource_id, label):
    res = client.patch(f"/api/v1/resources/{resource_id}", json={"label": label}, headers=headers)
    assert res.status_code == 200, res.text
    return res.json()


def _feed(client, headers, **params):
    res = client.get("/api/v1/changes/", params=params, headers=headers)
    assert res.status_code == 200, res.text
    return res.json()


def _book(client, headers, resource_id, key="feed-0000-0001"):
    return client.post(
        f"/api/v1/resources/{resource_id}/reservations",
        json={"date": str(TUESDAY), "start": "14:00", "end": "15:00", "purpose": "Ward round"},
        headers={**headers, "Idempotency-Key": key},
    )


# -- Off unless an operator asks for it ----------------------------------------


def test_the_feed_is_off_and_records_nothing_by_default(client, db, seed_users):
    headers = _admin(client)
    room = _make_room(client, headers)
    _rename(client, headers, room["id"], "Living Room")

    assert db.query(ChangeMarker).count() == 0
    res = client.get("/api/v1/changes/", headers=headers)
    assert res.status_code == 503
    # Named, because "unavailable" on a route that exists is otherwise
    # indistinguishable from an instance that is unwell.
    assert "CHANGE_FEED_ENABLED" in res.json()["detail"]


def test_the_feed_needs_a_credential(client, db, seed_users, change_feed_on):
    assert client.get("/api/v1/changes/").status_code == 401


def test_only_an_org_admin_reads_the_feed(client, db, seed_users, change_feed_on):
    """Higher than reading the rooms takes, because a booking's purpose is here.

    The availability calendar leaves out what a booking is for, on the grounds
    that anyone signed in can read the calendar. This hands over the booking
    whole, so it sits where the audit log sits.
    """
    for headers in (
        login(client, "staff@test.internal", STAFF_PASSWORD),
        login(client, "member@test.internal", MEMBER_PASSWORD),
        _unit_admin(db, client),
    ):
        assert client.get("/api/v1/changes/", headers=headers).status_code == 403


def test_a_key_reaches_the_feed_with_changes_read_and_not_with_resources_read(
    client, db, seed_users, change_feed_on
):
    """The scope is derived from the path, so the feed has its own.

    A key issued before this route existed names the areas it was given and
    does not name this one. That is the point: a key that may read the rooms is
    not thereby a key that may be told about every change to them.
    """
    admin = _admin(client)
    reader = _issue_key(client, admin, scopes=["changes:read"])
    rooms_only = _issue_key(client, admin, scopes=["resources:read"])

    assert client.get("/api/v1/changes/", headers=reader).status_code == 200
    assert client.get("/api/v1/changes/", headers=rooms_only).status_code == 403


# -- One entry per row, carrying the row ---------------------------------------


def test_a_new_room_arrives_as_one_entry_carrying_the_room(client, db, seed_users, change_feed_on):
    headers = _admin(client)
    room = _make_room(client, headers, capacity=40)

    body = _feed(client, headers)
    assert len(body["changes"]) == 1
    entry = body["changes"][0]
    assert entry["entity_kind"] == "resource"
    assert entry["entity_id"] == room["id"]
    assert entry["change_kind"] == "created"
    # The row itself, so a consumer applies the entry without a second request.
    assert entry["resource"]["code"] == "LH-201"
    assert entry["resource"]["capacity"] == 40
    assert entry["reservation"] is None
    assert body["next_cursor"] == entry["cursor"]


def test_two_renames_collapse_to_the_name_it_ended_on(client, db, seed_users, change_feed_on):
    """Renamed to Bedroom, then to Living Room.

    A consumer catching up wants where the room ended, not the walk it took.
    """
    headers = _admin(client)
    room = _make_room(client, headers)
    after_create = _feed(client, headers)["next_cursor"]

    _rename(client, headers, room["id"], "Bedroom")
    _rename(client, headers, room["id"], "Living Room")

    body = _feed(client, headers, since=after_create)
    assert len(body["changes"]) == 1
    assert body["changes"][0]["change_kind"] == "updated"
    assert body["changes"][0]["resource"]["label"] == "Living Room"
    # Three markers exist; the collapsed feed showed one of them.
    assert db.query(ChangeMarker).count() == 3


def test_the_full_log_keeps_every_step_and_no_state(client, db, seed_users, change_feed_on):
    headers = _admin(client)
    room = _make_room(client, headers)
    _rename(client, headers, room["id"], "Bedroom")
    _rename(client, headers, room["id"], "Living Room")

    body = _feed(client, headers, full=True)
    assert [c["change_kind"] for c in body["changes"]] == ["created", "updated", "updated"]
    # Oldest first: the log is read forwards, and a cursor only moves that way.
    cursors = [c["cursor"] for c in body["changes"]]
    assert cursors == sorted(cursors)
    # No row state. Which name it carried at each step is not recorded, and
    # inventing the current one three times over would suggest it was.
    assert all(c["resource"] is None for c in body["changes"])


def test_a_room_created_and_then_changed_between_polls_reads_as_created(
    client, db, seed_users, change_feed_on
):
    """The consumer has never seen this row, so it is not an update to them.

    Reporting the newest marker would say "updated" about a row they have no
    copy of, which is the one answer they cannot act on.
    """
    headers = _admin(client)
    room = _make_room(client, headers)
    _rename(client, headers, room["id"], "Living Room")

    entry = _feed(client, headers)["changes"][0]
    assert entry["change_kind"] == "created"
    assert entry["resource"]["label"] == "Living Room"


# -- The cursor ----------------------------------------------------------------


def test_a_poll_that_finds_nothing_keeps_the_cursor_it_was_given(
    client, db, seed_users, change_feed_on
):
    headers = _admin(client)
    _make_room(client, headers)
    cursor = _feed(client, headers)["next_cursor"]

    again = _feed(client, headers, since=cursor)
    assert again["changes"] == []
    # Handed back unchanged, so a consumer that stores it every time keeps its
    # place instead of walking back to the beginning.
    assert again["next_cursor"] == cursor


def test_a_limit_cuts_the_page_and_the_rest_comes_back_next_poll(
    client, db, seed_users, change_feed_on
):
    headers = _admin(client)
    first = _make_room(client, headers, code="LH-201")
    second = _make_room(client, headers, code="LH-202")

    page = _feed(client, headers, limit=1)
    assert [c["entity_id"] for c in page["changes"]] == [first["id"]]

    rest = _feed(client, headers, since=page["next_cursor"], limit=1)
    assert [c["entity_id"] for c in rest["changes"]] == [second["id"]]


# -- Bookings ------------------------------------------------------------------


def test_a_booking_and_its_cancellation_are_one_entry_reading_cancelled(
    client, db, seed_users, change_feed_on
):
    headers = _unit_admin(db, client)
    room = _room(db)
    held = _book(client, headers, room.id).json()
    res = client.delete(f"/api/v1/resources/{room.id}/reservations/{held['id']}", headers=headers)
    assert res.status_code == 200, res.text

    admin = _admin(client)
    body = _feed(client, admin)
    assert len(body["changes"]) == 1
    entry = body["changes"][0]
    assert entry["entity_kind"] == "reservation"
    assert entry["entity_id"] == held["id"]
    assert entry["change_kind"] == "created"
    # The same shape the booking routes return, built by the same function.
    assert entry["reservation"]["status"] == "CANCELLED"
    assert entry["reservation"]["resource_code"] == room.code
    assert entry["resource"] is None


def test_a_replayed_booking_records_nothing_the_second_time(client, db, seed_users, change_feed_on):
    """A retry under the same key made no change, so there is nothing to tell."""
    headers = _unit_admin(db, client)
    room = _room(db)
    assert _book(client, headers, room.id).status_code == 201
    assert _book(client, headers, room.id).status_code == 200

    assert db.query(ChangeMarker).count() == 1


# -- A marker is part of the change it describes -------------------------------


def test_a_refused_write_leaves_no_marker_behind(client, db, seed_users, change_feed_on):
    """The marker goes in the caller's transaction, so a rollback takes it too.

    A marker for a room that was never created would send a consumer to read a
    row that is not there, and it would stay in the log saying so.
    """
    headers = _admin(client)
    _make_room(client, headers, code="LH-201")
    clash = client.post("/api/v1/resources/", json={"code": "LH-201"}, headers=headers)
    assert clash.status_code == 409

    assert db.query(ChangeMarker).count() == 1
    assert len(_feed(client, headers)["changes"]) == 1
