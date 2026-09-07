# Copyright 2026 Chronos Ledger Contributors
# Licensed under the Apache License, Version 2.0

"""An admin can put a locked-out account back in reach, and no further.

Nothing else in the system can. change-password needs the password the user
has lost, there is no mail sender to send a reset link through, and there is
no endpoint that deletes a user. Before this, an account whose password went
missing stayed missing.
"""

from app.core.security import hash_password, verify_password
from app.models.db import InstitutionalRole, RefreshToken, User
from tests.conftest import ADMIN_PASSWORD, MEMBER_PASSWORD, STAFF_PASSWORD, login

RESET = "/api/v1/users/%s/reset-password"

UNIT_ADMIN_PASSWORD = "UnitAdminPass123!"


def _seed_cse_unit_admin(db):
    """A CSE unit admin, plus an ECE member outside their reach."""
    db.add_all(
        [
            User(
                id="DAD100",
                full_name="CSE Unit Admin",
                email_address="cse.admin@test.internal",
                credential_secure_hash=hash_password(UNIT_ADMIN_PASSWORD),
                role_type=InstitutionalRole.UNIT_ADMIN,
                unit_code="CSE",
                initial_login_state=False,
            ),
            User(
                id="STU900",
                full_name="ECE Member",
                email_address="ece.member@test.internal",
                credential_secure_hash=hash_password(MEMBER_PASSWORD),
                role_type=InstitutionalRole.MEMBER,
                unit_code="ECE",
            ),
        ]
    )
    db.commit()


# -- The reset works ---


def test_the_new_password_logs_the_user_in(client, seed_users):
    headers = login(client, "admin@test.internal", ADMIN_PASSWORD)
    res = client.post(RESET % "STU001", headers=headers)
    assert res.status_code == 200, res.text
    issued = res.json()["initial_password"]

    assert login(client, "member@test.internal", issued)


def test_the_old_password_stops_working(client, seed_users):
    headers = login(client, "admin@test.internal", ADMIN_PASSWORD)
    assert client.post(RESET % "STU001", headers=headers).status_code == 200

    res = client.post(
        "/api/v1/auth/login",
        json={"email": "member@test.internal", "password": MEMBER_PASSWORD},
    )
    assert res.status_code == 401


def test_the_issued_password_is_never_stored(client, seed_users, db):
    """The response is the only place the raw value ever exists."""
    headers = login(client, "admin@test.internal", ADMIN_PASSWORD)
    issued = client.post(RESET % "STU001", headers=headers).json()["initial_password"]

    member = db.query(User).filter(User.id == "STU001").first()
    assert member.credential_secure_hash != issued
    assert verify_password(issued, member.credential_secure_hash)


def test_two_resets_do_not_produce_the_same_password(client, seed_users):
    headers = login(client, "admin@test.internal", ADMIN_PASSWORD)
    first = client.post(RESET % "STU001", headers=headers).json()["initial_password"]
    second = client.post(RESET % "STU001", headers=headers).json()["initial_password"]
    assert first != second


# -- A reset ends the sessions it was called about ---


def test_a_reset_signs_out_every_device(client, seed_users):
    """An admin resetting a compromised account expects the intruder gone."""
    res = client.post(
        "/api/v1/auth/login",
        json={"email": "member@test.internal", "password": MEMBER_PASSWORD},
    )
    stolen_refresh = res.json()["refresh_token"]

    headers = login(client, "admin@test.internal", ADMIN_PASSWORD)
    assert client.post(RESET % "STU001", headers=headers).status_code == 200

    replay = client.post("/api/v1/auth/refresh", json={"refresh_token": stolen_refresh})
    assert replay.status_code == 401


def test_a_reset_rotates_the_calendar_feed_url(client, seed_users, db):
    """The feed token is a bearer URL, so it outlives a password on its own."""
    before = db.query(User).filter(User.id == "STU001").first().calendar_feed_token

    headers = login(client, "admin@test.internal", ADMIN_PASSWORD)
    assert client.post(RESET % "STU001", headers=headers).status_code == 200

    db.expire_all()
    after = db.query(User).filter(User.id == "STU001").first().calendar_feed_token
    assert after != before


def test_a_reset_admin_must_choose_their_own_password(client, seed_users, db):
    """The first-login gate is re-armed, so a handed-over password is temporary."""
    db.add(
        User(
            id="ADM900",
            full_name="Second Admin",
            email_address="admin2@test.internal",
            credential_secure_hash=hash_password(ADMIN_PASSWORD),
            role_type=InstitutionalRole.SUPER_ADMIN,
            initial_login_state=False,
        )
    )
    db.commit()

    headers = login(client, "admin@test.internal", ADMIN_PASSWORD)
    issued = client.post(RESET % "ADM900", headers=headers).json()["initial_password"]

    res = client.post(
        "/api/v1/auth/login",
        json={"email": "admin2@test.internal", "password": issued},
    )
    assert res.json()["initial_login_state"] is True
    reset_headers = {"Authorization": "Bearer " + res.json()["access_token"]}
    assert client.get("/api/v1/users/", headers=reset_headers).status_code == 403


# -- Who may call it ---


def test_a_member_and_a_staff_member_may_not_reset(client, seed_users):
    for email, password in [
        ("member@test.internal", MEMBER_PASSWORD),
        ("staff@test.internal", STAFF_PASSWORD),
    ]:
        headers = login(client, email, password)
        assert client.post(RESET % "STU001", headers=headers).status_code == 403


def test_a_unit_admin_may_not_reset_outside_their_unit(client, seed_users, db):
    _seed_cse_unit_admin(db)
    headers = login(client, "cse.admin@test.internal", UNIT_ADMIN_PASSWORD)
    assert client.post(RESET % "STU900", headers=headers).status_code == 403


def test_a_unit_admin_may_reset_inside_their_unit(client, seed_users, db):
    _seed_cse_unit_admin(db)
    headers = login(client, "cse.admin@test.internal", UNIT_ADMIN_PASSWORD)
    assert client.post(RESET % "STU001", headers=headers).status_code == 200


def test_a_unit_admin_may_not_reset_an_admin(client, seed_users, db):
    """Otherwise a unit admin promotes themselves by taking the super-admin."""
    _seed_cse_unit_admin(db)
    headers = login(client, "cse.admin@test.internal", UNIT_ADMIN_PASSWORD)
    assert client.post(RESET % "ADM001", headers=headers).status_code == 403


def test_resetting_an_unknown_user_is_a_404(client, seed_users):
    headers = login(client, "admin@test.internal", ADMIN_PASSWORD)
    assert client.post(RESET % "NOBODY", headers=headers).status_code == 404


def test_an_anonymous_caller_is_rejected(client, seed_users):
    assert client.post(RESET % "STU001").status_code in (401, 403)


def test_a_failed_reset_leaves_the_sessions_alone(client, seed_users, db):
    """A 403 must not have deleted the target's refresh tokens on the way."""
    client.post(
        "/api/v1/auth/login",
        json={"email": "member@test.internal", "password": MEMBER_PASSWORD},
    )
    before = db.query(RefreshToken).filter(RefreshToken.user_id == "STU001").count()
    assert before > 0

    headers = login(client, "staff@test.internal", STAFF_PASSWORD)
    assert client.post(RESET % "STU001", headers=headers).status_code == 403
    assert db.query(RefreshToken).filter(RefreshToken.user_id == "STU001").count() == before
