# Copyright 2026 Chronos Ledger Contributors
# Licensed under the Apache License, Version 2.0
"""API keys: created by an admin, bound to a user, honoured on X-API-Key."""

from tests.conftest import ADMIN_PASSWORD, STAFF_PASSWORD, login


def _create_key(client, headers, user_id="FAC001", label="HR export"):
    res = client.post(
        "/api/v1/api-keys/",
        json={"label": label, "user_id": user_id},
        headers=headers,
    )
    return res


def test_create_returns_raw_key_exactly_once(client, seed_users):
    headers = login(client, "admin@test.internal", ADMIN_PASSWORD)
    res = _create_key(client, headers)
    assert res.status_code == 201, res.text
    body = res.json()
    assert body["api_key"].startswith("ck_")
    assert body["key_prefix"] == body["api_key"][:12]
    assert body["user_id"] == "FAC001"

    listed = client.get("/api/v1/api-keys/", headers=headers)
    assert listed.status_code == 200
    assert len(listed.json()) == 1
    # The raw key never appears again: not in the list response.
    assert "api_key" not in listed.json()[0]


def test_api_key_authenticates_as_bound_user(client, seed_users):
    headers = login(client, "admin@test.internal", ADMIN_PASSWORD)
    raw = _create_key(client, headers).json()["api_key"]

    res = client.get("/api/v1/auth/me", headers={"X-API-Key": raw})
    assert res.status_code == 200, res.text
    assert res.json()["id"] == "FAC001"


def test_bearer_wins_when_both_credentials_sent(client, seed_users):
    admin_headers = login(client, "admin@test.internal", ADMIN_PASSWORD)
    raw = _create_key(client, admin_headers).json()["api_key"]

    res = client.get("/api/v1/auth/me", headers={**admin_headers, "X-API-Key": raw})
    assert res.status_code == 200
    assert res.json()["id"] == "ADM001"


def test_invalid_api_key_is_401(client, seed_users):
    res = client.get("/api/v1/auth/me", headers={"X-API-Key": "ck_not-a-real-key"})
    assert res.status_code == 401


def test_no_credentials_is_401(client, seed_users):
    res = client.get("/api/v1/auth/me")
    assert res.status_code == 401


def test_key_inherits_bound_user_role(client, seed_users):
    # FAC001 is STAFF: its key must not open an admin-only endpoint.
    headers = login(client, "admin@test.internal", ADMIN_PASSWORD)
    raw = _create_key(client, headers).json()["api_key"]

    res = client.get("/api/v1/api-keys/", headers={"X-API-Key": raw})
    assert res.status_code == 403


def test_non_admin_cannot_manage_keys(client, seed_users):
    staff_headers = login(client, "staff@test.internal", STAFF_PASSWORD)
    assert _create_key(client, staff_headers).status_code == 403
    assert client.get("/api/v1/api-keys/", headers=staff_headers).status_code == 403


def test_create_for_unknown_user_is_404(client, seed_users):
    headers = login(client, "admin@test.internal", ADMIN_PASSWORD)
    res = _create_key(client, headers, user_id="NOBODY")
    assert res.status_code == 404


def test_revoked_key_stops_working(client, seed_users):
    headers = login(client, "admin@test.internal", ADMIN_PASSWORD)
    created = _create_key(client, headers).json()

    assert (
        client.get("/api/v1/auth/me", headers={"X-API-Key": created["api_key"]}).status_code == 200
    )
    res = client.delete(f"/api/v1/api-keys/{created['id']}", headers=headers)
    assert res.status_code == 204
    assert (
        client.get("/api/v1/auth/me", headers={"X-API-Key": created["api_key"]}).status_code == 401
    )
