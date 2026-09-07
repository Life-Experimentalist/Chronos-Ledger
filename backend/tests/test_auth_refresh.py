# Copyright 2026 Chronos Ledger Contributors
# Licensed under the Apache License, Version 2.0
"""Session lifetime: a stolen access token dies in minutes on its own; the
long-lived credential is the refresh token, which is single-use, revocable
by logout, and dies wholesale on a password change."""

from datetime import UTC, datetime, timedelta

from app.core.security import hash_refresh_token
from app.models.db import RefreshToken
from tests.conftest import STUDENT_PASSWORD


def _login(client, email="student@test.internal", password=STUDENT_PASSWORD):
    res = client.post("/api/v1/auth/login", json={"email": email, "password": password})
    assert res.status_code == 200
    return res.json()


def test_login_returns_refresh_token(client, seed_users):
    data = _login(client)
    assert data["refresh_token"]
    assert data["access_token"]


def test_refresh_token_stored_hashed_not_raw(client, db, seed_users):
    data = _login(client)
    raw = data["refresh_token"]
    rows = db.query(RefreshToken).all()
    assert len(rows) == 1
    assert rows[0].token_hash == hash_refresh_token(raw)
    assert raw not in rows[0].token_hash


def test_refresh_rotates_and_new_access_token_works(client, seed_users):
    data = _login(client)
    res = client.post("/api/v1/auth/refresh", json={"refresh_token": data["refresh_token"]})
    assert res.status_code == 200
    rotated = res.json()
    assert rotated["refresh_token"] != data["refresh_token"]

    me = client.get(
        "/api/v1/auth/me", headers={"Authorization": f"Bearer {rotated['access_token']}"}
    )
    assert me.status_code == 200
    assert me.json()["id"] == "STU001"


def test_used_refresh_token_is_dead(client, seed_users):
    data = _login(client)
    first = client.post("/api/v1/auth/refresh", json={"refresh_token": data["refresh_token"]})
    assert first.status_code == 200
    replay = client.post("/api/v1/auth/refresh", json={"refresh_token": data["refresh_token"]})
    assert replay.status_code == 401


def test_garbage_refresh_token_rejected(client):
    res = client.post("/api/v1/auth/refresh", json={"refresh_token": "not-a-real-token"})
    assert res.status_code == 401


def test_expired_refresh_token_rejected_and_deleted(client, db, seed_users):
    data = _login(client)
    row = db.query(RefreshToken).first()
    row.expires_at = datetime.now(UTC) - timedelta(minutes=1)
    db.commit()

    res = client.post("/api/v1/auth/refresh", json={"refresh_token": data["refresh_token"]})
    assert res.status_code == 401
    assert db.query(RefreshToken).count() == 0


def test_logout_revokes_refresh_token(client, seed_users):
    data = _login(client)
    out = client.post("/api/v1/auth/logout", json={"refresh_token": data["refresh_token"]})
    assert out.status_code == 200
    res = client.post("/api/v1/auth/refresh", json={"refresh_token": data["refresh_token"]})
    assert res.status_code == 401


def test_password_change_revokes_all_sessions(client, db, seed_users):
    phone = _login(client)
    laptop = _login(client)
    assert db.query(RefreshToken).count() == 2

    res = client.post(
        "/api/v1/auth/change-password",
        json={"current_password": STUDENT_PASSWORD, "new_password": "BrandNewPass456!"},
        headers={"Authorization": f"Bearer {laptop['access_token']}"},
    )
    assert res.status_code == 200
    assert db.query(RefreshToken).count() == 0

    for session in (phone, laptop):
        replay = client.post(
            "/api/v1/auth/refresh", json={"refresh_token": session["refresh_token"]}
        )
        assert replay.status_code == 401
