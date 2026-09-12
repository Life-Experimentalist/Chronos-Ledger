# Copyright 2026 Chronos Ledger Contributors
# Licensed under the Apache License, Version 2.0
"""The fields POST and PATCH /users/ used to write straight through.

A manager who did not exist reached the foreign key, a user could be made
their own manager and approve their own absences, and PATCH sent an email
address already on another account to the unique index, which came back as
a 500.
"""

from app.models.db import User
from tests.conftest import ADMIN_PASSWORD, login
from tests.test_users_rbac import NEW_USER


def _admin(client):
    return login(client, "admin@test.internal", ADMIN_PASSWORD)


def _patch(client, headers, user_id, **fields):
    return client.patch(f"/api/v1/users/{user_id}", headers=headers, json=fields)


def _create(client, headers, **fields):
    return client.post("/api/v1/users/", headers=headers, json=dict(NEW_USER, **fields))


def test_a_manager_is_set_on_create_and_on_patch(client, seed_users):
    headers = _admin(client)
    r = _create(client, headers, reporting_line_manager="FAC001")
    assert r.status_code == 201, r.text
    assert r.json()["reporting_line_manager"] == "FAC001"

    r = _patch(client, headers, NEW_USER["id"], reporting_line_manager="ADM001")
    assert r.status_code == 200, r.text
    assert r.json()["reporting_line_manager"] == "ADM001"


def test_a_manager_that_does_not_exist_is_a_404(client, seed_users):
    headers = _admin(client)
    r = _patch(client, headers, "STU001", reporting_line_manager="NOBODY")
    assert r.status_code == 404, r.text
    r = _create(client, headers, reporting_line_manager="NOBODY")
    assert r.status_code == 404, r.text


def test_a_user_is_not_their_own_manager(client, seed_users):
    headers = _admin(client)
    r = _patch(client, headers, "STU001", reporting_line_manager="STU001")
    assert r.status_code == 422, r.text
    r = _create(client, headers, reporting_line_manager=NEW_USER["id"])
    assert r.status_code == 422, r.text


def test_a_manager_who_already_reports_to_the_user_is_refused(client, seed_users):
    headers = _admin(client)
    assert _patch(client, headers, "STU001", reporting_line_manager="FAC001").status_code == 200
    assert _patch(client, headers, "FAC001", reporting_line_manager="ADM001").status_code == 200

    r = _patch(client, headers, "ADM001", reporting_line_manager="STU001")
    assert r.status_code == 422, r.text
    assert r.json()["detail"] == "STU001 already reports to ADM001, directly or through others"
    kept = client.get("/api/v1/users/ADM001", headers=headers).json()
    assert kept["reporting_line_manager"] is None


def test_a_loop_from_before_the_check_does_not_hang_it(client, db, seed_users):
    """A loop the user is not part of is walked once and let be."""
    headers = _admin(client)
    staff = db.query(User).filter(User.id == "FAC001").one()
    admin = db.query(User).filter(User.id == "ADM001").one()
    staff.reporting_line_manager, admin.reporting_line_manager = "ADM001", "FAC001"
    db.commit()

    r = _patch(client, headers, "STU001", reporting_line_manager="FAC001")
    assert r.status_code == 200, r.text


def test_an_email_already_on_another_account_is_a_409(client, seed_users):
    headers = _admin(client)
    r = _patch(client, headers, "STU001", email_address="staff@test.internal")
    assert r.status_code == 409, r.text
    assert r.json()["detail"] == "Email already registered"
    kept = client.get("/api/v1/users/STU001", headers=headers).json()
    assert kept["email_address"] == "member@test.internal"


def test_a_user_can_be_saved_with_the_email_they_already_have(client, seed_users):
    headers = _admin(client)
    r = _patch(client, headers, "STU001", email_address="member@test.internal", full_name="Renamed")
    assert r.status_code == 200, r.text
    assert r.json()["full_name"] == "Renamed"
