# Copyright 2026 Chronos Ledger Contributors
# Licensed under the Apache License, Version 2.0
"""A key can be narrowed to what it is for, and can be made to run out.

A key used to be everything its bound user could do, forever. That is a poor
thing to hand an external system, and handing one to an external system is
what keys are for. These tests pin the two limits and, just as much, pin
that a key issued before either existed still works exactly as it did.
"""

import datetime

from app.core.security import key_allows, required_scope
from tests.conftest import ADMIN_PASSWORD, login

FUTURE = datetime.datetime.now(datetime.UTC) + datetime.timedelta(days=30)
PAST = datetime.datetime.now(datetime.UTC) - datetime.timedelta(minutes=1)


def _create(client, headers, **extra):
    payload = {"label": "PulseWard", "user_id": "ADM001", **extra}
    return client.post("/api/v1/api-keys/", json=payload, headers=headers)


def _key(client, headers, **extra):
    res = _create(client, headers, **extra)
    assert res.status_code == 201, res.text
    return {"X-API-Key": res.json()["api_key"]}


def _admin(client):
    return login(client, "admin@test.internal", ADMIN_PASSWORD)


def test_a_key_with_no_scopes_named_is_unrestricted(client, seed_users):
    """What every key issued before this existed is, and stays."""
    headers = _admin(client)
    body = _create(client, headers).json()
    assert body["scopes"] == "*"
    assert body["expires_at"] is None

    key = {"X-API-Key": body["api_key"]}
    assert client.get("/api/v1/auth/me", headers=key).status_code == 200
    assert client.get("/api/v1/schedule/cycles", headers=key).status_code == 200


def test_a_read_scope_does_not_carry_write(client, seed_users):
    headers = _admin(client)
    key = _key(client, headers, scopes=["schedule:read"])

    assert client.get("/api/v1/schedule/cycles", headers=key).status_code == 200

    denied = client.post(
        "/api/v1/schedule/cycles",
        headers=key,
        json={
            "cycle_label": "Autumn",
            "date_bounds_start": "2026-01-01",
            "date_bounds_end": "2026-06-01",
        },
    )
    assert denied.status_code == 403
    assert "schedule:write" in denied.json()["detail"]


def test_a_scope_does_not_carry_to_another_area(client, seed_users):
    headers = _admin(client)
    key = _key(client, headers, scopes=["schedule:read"])

    denied = client.get("/api/v1/users/", headers=key)
    assert denied.status_code == 403
    assert "users:read" in denied.json()["detail"]


def test_scopes_are_stored_sorted_and_deduplicated(client, seed_users):
    headers = _admin(client)
    body = _create(client, headers, scopes=["schedule:read", "users:read", "schedule:read"]).json()
    assert body["scopes"] == "schedule:read,users:read"

    key = {"X-API-Key": body["api_key"]}
    assert client.get("/api/v1/users/", headers=key).status_code == 200
    assert client.get("/api/v1/schedule/cycles", headers=key).status_code == 200


def test_an_expired_key_is_refused(client, db, seed_users):
    from app.models.db import ApiKey

    headers = _admin(client)
    created = _create(client, headers, expires_at=FUTURE.isoformat()).json()
    key = {"X-API-Key": created["api_key"]}
    assert client.get("/api/v1/auth/me", headers=key).status_code == 200

    # Wound forward rather than created expired: the endpoint refuses a key
    # that is dead on arrival, so the only way to reach this state is to live
    # through it.
    db.query(ApiKey).filter(ApiKey.id == created["id"]).one().expires_at = PAST
    db.commit()

    refused = client.get("/api/v1/auth/me", headers=key)
    assert refused.status_code == 401
    assert refused.json()["detail"] == "API key expired"


def test_an_expiry_already_past_is_refused_at_creation(client, seed_users):
    res = _create(client, _admin(client), expires_at=PAST.isoformat())
    assert res.status_code == 422
    assert "dead on arrival" in res.json()["detail"]


def test_a_scope_that_is_not_a_scope_is_refused(client, seed_users):
    headers = _admin(client)
    assert _create(client, headers, scopes=["schedule"]).status_code == 422
    assert _create(client, headers, scopes=["schedule:delete"]).status_code == 422
    assert _create(client, headers, scopes=["Schedule:read"]).status_code == 422
    # An empty list reads as "no access at all", which is not a key anybody
    # wants. Omitting the field is how you ask for an unrestricted one.
    assert _create(client, headers, scopes=[]).status_code == 422


def test_a_kiosk_key_reaches_the_lobby_and_nothing_else(client, seed_users):
    """The case the docs hold up: a device in a public space, narrowed."""
    headers = _admin(client)
    key = _key(client, headers, scopes=["guest:read", "guest:write"])

    assert client.get("/api/v1/guest/directory", headers=key).status_code == 200

    checked_in = client.post(
        "/api/v1/guest/register-checkin",
        headers=key,
        json={
            "guest_name": "A Visitor",
            "contact_phone": "+91 98765 43210",
            "originating_body": "Somewhere",
            "target_staff_id": "FAC001",
            "visitation_intent": "Here to see about the timetable",
        },
    )
    assert checked_in.status_code == 200, checked_in.text

    # Whoever picks the kiosk up off the desk gets no further than the lobby.
    denied = client.get("/api/v1/users/", headers=key)
    assert denied.status_code == 403


def test_the_list_shows_which_keys_are_unrestricted(client, seed_users):
    headers = _admin(client)
    _create(client, headers)
    _create(client, headers, scopes=["schedule:read"], expires_at=FUTURE.isoformat())

    listed = client.get("/api/v1/api-keys/", headers=headers).json()
    assert sorted(row["scopes"] for row in listed) == ["*", "schedule:read"]
    assert [row["expires_at"] is None for row in listed] == [True, False]


def test_the_scope_a_request_needs_is_read_off_the_request():
    """The whole vocabulary, in one place, so nobody has to guess it."""
    assert required_scope("GET", "/api/v1/schedule/slots") == "schedule:read"
    assert required_scope("DELETE", "/api/v1/schedule/slots/12") == "schedule:write"
    assert required_scope("POST", "/api/v1/attendance/mark") == "attendance:write"
    assert required_scope("GET", "/api/v1/sync/user-feed/tok.ics") == "sync:read"
    # Nothing to name means nothing to allow, and the caller refuses.
    assert required_scope("GET", "/health") is None
    assert not key_allows("schedule:read", None)
    # Except for a key that was never narrowed in the first place.
    assert key_allows("*", None)
