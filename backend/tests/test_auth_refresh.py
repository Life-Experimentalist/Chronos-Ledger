# Copyright 2026 Chronos Ledger Contributors
# Licensed under the Apache License, Version 2.0
"""Session lifetime: a stolen access token dies in minutes on its own; the
long-lived credential is the refresh token, which is single-use, revocable
by logout, dies wholesale on a password change, and takes its whole sign-in
down with it when it is presented a second time."""

import logging
from datetime import UTC, datetime, timedelta

from app.api.v1.endpoints.auth import REUSE_GRACE
from app.core.security import hash_refresh_token
from app.cron.refresh_token_cleanup import purge_expired_refresh_tokens
from app.models.db import RefreshToken
from tests.conftest import MEMBER_PASSWORD


def _login(client, email="member@test.internal", password=MEMBER_PASSWORD):
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


def test_password_change_revokes_every_session_including_its_own(client, db, seed_users):
    phone = _login(client)
    laptop = _login(client)
    assert db.query(RefreshToken).count() == 2

    res = client.post(
        "/api/v1/auth/change-password",
        json={"current_password": MEMBER_PASSWORD, "new_password": "BrandNewPass456!"},
        headers={"Authorization": f"Bearer {laptop['access_token']}"},
    )
    assert res.status_code == 200
    # Two died, one was issued: the replacement for the caller.
    assert db.query(RefreshToken).count() == 1

    for session in (phone, laptop):
        replay = client.post(
            "/api/v1/auth/refresh", json={"refresh_token": session["refresh_token"]}
        )
        assert replay.status_code == 401


def test_password_change_hands_the_caller_a_working_refresh_token(client, seed_users):
    laptop = _login(client)
    res = client.post(
        "/api/v1/auth/change-password",
        json={"current_password": MEMBER_PASSWORD, "new_password": "BrandNewPass456!"},
        headers={"Authorization": f"Bearer {laptop['access_token']}"},
    )
    assert res.status_code == 200
    issued = res.json()["refresh_token"]
    assert issued != laptop["refresh_token"]

    # Without this the browser that changed the password is signed out as soon
    # as its access token expires, which is the whole point of the fix.
    rotated = client.post("/api/v1/auth/refresh", json={"refresh_token": issued})
    assert rotated.status_code == 200
    me = client.get(
        "/api/v1/auth/me",
        headers={"Authorization": f"Bearer {rotated.json()['access_token']}"},
    )
    assert me.status_code == 200
    assert me.json()["id"] == "STU001"


def _refresh(client, token):
    return client.post("/api/v1/auth/refresh", json={"refresh_token": token})


def test_refresh_keeps_the_used_row_in_the_same_family(client, db, seed_users):
    data = _login(client)
    assert _refresh(client, data["refresh_token"]).status_code == 200

    used, current = db.query(RefreshToken).order_by(RefreshToken.id).all()
    assert used.token_hash == hash_refresh_token(data["refresh_token"])
    assert used.consumed_at is not None
    assert current.consumed_at is None
    assert used.family_id == current.family_id


def test_each_sign_in_is_a_family_of_its_own(client, db, seed_users):
    _login(client)
    _login(client)
    assert len({row.family_id for row in db.query(RefreshToken).all()}) == 2


def test_a_replay_inside_the_grace_window_ends_nothing(client, seed_users):
    # Two tabs sharing one stored token: the slower one presents the token the
    # faster one has just spent. It is refused, and the faster one carries on.
    data = _login(client)
    rotated = _refresh(client, data["refresh_token"]).json()
    assert _refresh(client, data["refresh_token"]).status_code == 401
    assert _refresh(client, rotated["refresh_token"]).status_code == 200


def test_a_replay_after_the_grace_window_ends_the_whole_sign_in(client, db, seed_users, caplog):
    stolen = _login(client)
    elsewhere = _login(client)
    rotated = _refresh(client, stolen["refresh_token"]).json()
    used = (
        db.query(RefreshToken)
        .filter(RefreshToken.token_hash == hash_refresh_token(stolen["refresh_token"]))
        .one()
    )
    used.consumed_at = datetime.now(UTC) - REUSE_GRACE - timedelta(seconds=1)
    db.commit()

    with caplog.at_level(logging.WARNING, logger="app.api.v1.endpoints.auth"):
        assert _refresh(client, stolen["refresh_token"]).status_code == 401
    # Whoever holds the rotated token is out as well: from here there is no
    # telling which of the two holders was the thief.
    assert _refresh(client, rotated["refresh_token"]).status_code == 401
    # Another sign-in on the same account is another family, and lives.
    assert _refresh(client, elsewhere["refresh_token"]).status_code == 200

    assert "STU001" in caplog.text
    assert stolen["refresh_token"] not in caplog.text
    assert rotated["refresh_token"] not in caplog.text


def test_logout_ends_its_family_and_no_other(client, db, seed_users):
    phone = _login(client)
    laptop = _login(client)
    rotated = _refresh(client, laptop["refresh_token"]).json()

    out = client.post("/api/v1/auth/logout", json={"refresh_token": rotated["refresh_token"]})
    assert out.status_code == 200
    remaining = [row.token_hash for row in db.query(RefreshToken).all()]
    assert remaining == [hash_refresh_token(phone["refresh_token"])]


def test_the_purge_takes_rows_a_day_past_expiry_and_leaves_the_rest(db, seed_users):
    now = datetime.now(UTC)
    for name, expires_at in (
        ("live", now + timedelta(days=1)),
        ("just_lapsed", now - timedelta(hours=1)),
        ("long_gone", now - timedelta(days=2)),
    ):
        db.add(
            RefreshToken(
                token_hash=hash_refresh_token(name),
                user_id="STU001",
                family_id=name,
                expires_at=expires_at,
            )
        )
    db.commit()

    assert purge_expired_refresh_tokens(db) == 1
    assert {row.family_id for row in db.query(RefreshToken).all()} == {"live", "just_lapsed"}
