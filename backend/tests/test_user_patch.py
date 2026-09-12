# Copyright 2026 Chronos Ledger Contributors
# Licensed under the Apache License, Version 2.0
"""PATCH /users/{id} and what a null in it does.

A null used to be dropped along with the fields left out, so once a user
had a manager, a base station or a unit, nothing in the API could take it
away again.
"""

from tests.conftest import ADMIN_PASSWORD, login
from tests.test_unit_admin_scope import _seed_unit_world, _unit_admin


def _patch(client, headers, user_id, **fields):
    return client.patch(f"/api/v1/users/{user_id}", headers=headers, json=fields)


def test_a_null_clears_the_field_and_a_field_left_out_is_kept(client, db, seed_users):
    headers = login(client, "admin@test.internal", ADMIN_PASSWORD)
    r = _patch(
        client, headers, "STU001", reporting_line_manager="FAC001", assigned_base_station="LH-201"
    )
    assert r.status_code == 200, r.text

    r = _patch(
        client,
        headers,
        "STU001",
        reporting_line_manager=None,
        assigned_base_station=None,
        unit_code=None,
    )
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["reporting_line_manager"] is None
    assert body["assigned_base_station"] is None
    assert body["unit_code"] is None
    assert body["full_name"] == "Member One"
    assert body["email_address"] == "member@test.internal"


def test_a_name_or_an_email_cannot_be_cleared(client, db, seed_users):
    headers = login(client, "admin@test.internal", ADMIN_PASSWORD)
    for field in ("full_name", "email_address"):
        r = _patch(client, headers, "STU001", **{field: None, "assigned_base_station": "LH-201"})
        assert r.status_code == 422, r.text
        assert r.json()["detail"][0]["loc"][-1] == field
    body = client.get("/api/v1/users/STU001", headers=headers).json()
    assert body["full_name"] == "Member One"
    assert body["assigned_base_station"] is None


def test_a_unit_admin_cannot_clear_a_unit(client, db, seed_users):
    """A user taken out of every unit is taken out of the admin's as well."""
    _seed_unit_world(db)
    headers = _unit_admin(client)
    r = _patch(client, headers, "STU001", unit_code=None)
    assert r.status_code == 403, r.text

    # What stays inside the unit is still theirs to clear.
    r = _patch(client, headers, "STU001", assigned_base_station=None, reporting_line_manager=None)
    assert r.status_code == 200, r.text
    assert r.json()["unit_code"] == "CSE"
