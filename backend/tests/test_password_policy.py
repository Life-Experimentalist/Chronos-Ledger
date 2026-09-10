# Copyright 2026 Chronos Ledger Contributors
# Licensed under the Apache License, Version 2.0
"""The first-login gate used to be satisfiable with one character.

The seeded administrator is forced to change the password before doing
anything else, and then was permitted to set it to "a". Every account created
through the admin UI or the CSV importer had the same hole on the other side
of it.

The floor is a setting rather than a constant, because 12 is right for a
school and wrong for somewhere with its own policy, and because a deployment
that cannot raise it will not raise it.
"""

import pytest
from pydantic import ValidationError

from app.core.config import ABSOLUTE_PASSWORD_FLOOR, Settings, get_settings
from app.core.passwords import check_password
from tests.conftest import ADMIN_PASSWORD, MEMBER_PASSWORD, login

CHANGE = "/api/v1/auth/change-password"


@pytest.fixture
def password_floor(monkeypatch):
    """Move PASSWORD_MIN_LENGTH for one test and put it back afterwards.

    Same shape as the org_zone fixture: get_settings is lru_cached, so the
    cache is dropped going in and coming out. Coming out matters more, since
    a floor left cached would follow every test that ran after this one.
    """

    def set_to(length: int):
        monkeypatch.setenv("PASSWORD_MIN_LENGTH", str(length))
        get_settings.cache_clear()

    yield set_to
    get_settings.cache_clear()


def test_a_one_character_password_is_refused(client, seed_users):
    headers = login(client, "member@test.internal", MEMBER_PASSWORD)
    res = client.post(
        CHANGE,
        headers=headers,
        json={"current_password": MEMBER_PASSWORD, "new_password": "a"},
    )
    assert res.status_code == 422
    assert "at least 12 characters" in res.text


def test_the_old_password_still_logs_in_after_a_refused_change(client, seed_users):
    headers = login(client, "member@test.internal", MEMBER_PASSWORD)
    client.post(
        CHANGE,
        headers=headers,
        json={"current_password": MEMBER_PASSWORD, "new_password": "short"},
    )
    again = client.post(
        "/api/v1/auth/login",
        json={"email": "member@test.internal", "password": MEMBER_PASSWORD},
    )
    assert again.status_code == 200


def test_changing_a_password_to_itself_is_refused(client, seed_users):
    headers = login(client, "member@test.internal", MEMBER_PASSWORD)
    res = client.post(
        CHANGE,
        headers=headers,
        json={"current_password": MEMBER_PASSWORD, "new_password": MEMBER_PASSWORD},
    )
    assert res.status_code == 400
    assert "already have" in res.json()["detail"]


def test_a_password_published_in_this_repository_is_refused(client, seed_users):
    headers = login(client, "member@test.internal", MEMBER_PASSWORD)
    res = client.post(
        CHANGE,
        headers=headers,
        json={"current_password": MEMBER_PASSWORD, "new_password": "ChronosAdmin2026!"},
    )
    assert res.status_code == 422
    assert "published in this repository" in res.text


def test_creating_a_user_with_a_short_password_is_refused(client, seed_users):
    headers = login(client, "admin@test.internal", ADMIN_PASSWORD)
    res = client.post(
        "/api/v1/users/",
        headers=headers,
        json={
            "id": "MEM777",
            "full_name": "Short Password",
            "email_address": "short@test.internal",
            "password": "abc",
            "role_type": "MEMBER",
            "unit_code": "CSE",
        },
    )
    assert res.status_code == 422


def test_the_floor_follows_the_setting(password_floor):
    password_floor(20)
    with pytest.raises(ValueError, match="at least 20 characters"):
        check_password("SixteenCharsHere")
    assert check_password("TwentyCharactersLong") == "TwentyCharactersLong"


def test_a_raised_floor_refuses_what_the_default_allowed(client, seed_users, password_floor):
    password_floor(24)
    headers = login(client, "member@test.internal", MEMBER_PASSWORD)
    res = client.post(
        CHANGE,
        headers=headers,
        json={"current_password": MEMBER_PASSWORD, "new_password": "SixteenCharsHere"},
    )
    assert res.status_code == 422


def test_the_floor_cannot_be_lowered_into_uselessness():
    with pytest.raises(ValidationError, match=str(ABSOLUTE_PASSWORD_FLOOR)):
        Settings(password_min_length=1)
    assert Settings(password_min_length=ABSOLUTE_PASSWORD_FLOOR).password_min_length == (
        ABSOLUTE_PASSWORD_FLOOR
    )


def test_login_is_not_length_checked(client, seed_users):
    """A wrong short password is a failed login, not a validation error.

    Putting the policy on LoginRequest would lock out every account that
    predates the policy, and would tell an attacker which guesses were the
    right shape.
    """
    res = client.post(
        "/api/v1/auth/login",
        json={"email": "member@test.internal", "password": "x"},
    )
    assert res.status_code == 401
