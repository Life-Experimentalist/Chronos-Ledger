# Copyright 2026 Chronos Ledger Contributors
# Licensed under the Apache License, Version 2.0

from tests.conftest import ADMIN_PASSWORD, FACULTY_PASSWORD, login


def test_login_returns_token_and_profile(client, seed_users):
    res = client.post(
        "/api/v1/auth/login",
        json={"email": "admin@test.internal", "password": ADMIN_PASSWORD},
    )
    assert res.status_code == 200
    body = res.json()
    assert body["access_token"]
    assert body["user_id"] == "ADM001"
    assert body["role"] == "SUPER_ADMIN"
    assert body["initial_login_state"] is True


def test_login_wrong_password_is_401(client, seed_users):
    res = client.post(
        "/api/v1/auth/login",
        json={"email": "admin@test.internal", "password": "not-the-password"},
    )
    assert res.status_code == 401


def test_login_unknown_email_is_401(client, seed_users):
    res = client.post(
        "/api/v1/auth/login",
        json={"email": "nobody@test.internal", "password": "whatever"},
    )
    assert res.status_code == 401


def test_me_requires_a_token(client, seed_users):
    # Both a missing header and a bad token are a 401 on this FastAPI version.
    assert client.get("/api/v1/auth/me").status_code == 401
    res = client.get("/api/v1/auth/me", headers={"Authorization": "Bearer garbage"})
    assert res.status_code == 401


def test_me_returns_current_user(client, seed_users):
    headers = login(client, "faculty@test.internal", FACULTY_PASSWORD)
    res = client.get("/api/v1/auth/me", headers=headers)
    assert res.status_code == 200
    body = res.json()
    assert body["id"] == "FAC001"
    assert body["role_type"] == "FACULTY"
    assert body["department_code"] == "CSE"


def test_change_password_rejects_wrong_current(client, seed_users):
    headers = login(client, "faculty@test.internal", FACULTY_PASSWORD)
    res = client.post(
        "/api/v1/auth/change-password",
        headers=headers,
        json={"current_password": "wrong", "new_password": "NewPass456!"},
    )
    assert res.status_code == 400


def test_change_password_rotates_and_clears_first_login_flag(client, seed_users):
    headers = login(client, "faculty@test.internal", FACULTY_PASSWORD)
    res = client.post(
        "/api/v1/auth/change-password",
        headers=headers,
        json={"current_password": FACULTY_PASSWORD, "new_password": "NewPass456!"},
    )
    assert res.status_code == 200

    # Old password no longer works; new one does, and the flag is cleared.
    old = client.post(
        "/api/v1/auth/login",
        json={"email": "faculty@test.internal", "password": FACULTY_PASSWORD},
    )
    assert old.status_code == 401
    fresh = client.post(
        "/api/v1/auth/login",
        json={"email": "faculty@test.internal", "password": "NewPass456!"},
    )
    assert fresh.status_code == 200
    assert fresh.json()["initial_login_state"] is False
