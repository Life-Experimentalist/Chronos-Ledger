# Copyright 2026 Chronos Ledger Contributors
# Licensed under the Apache License, Version 2.0

from tests.conftest import ADMIN_PASSWORD, MEMBER_PASSWORD, STAFF_PASSWORD, login

NEW_USER = {
    "id": "STU002",
    "full_name": "Member Two",
    "email_address": "member2@test.internal",
    "password": "MemberPass789!",
    "role_type": "MEMBER",
    "unit_code": "ECE",
}


def test_list_users_denied_for_member_and_staff(client, seed_users):
    for email, password in [
        ("member@test.internal", MEMBER_PASSWORD),
        ("staff@test.internal", STAFF_PASSWORD),
    ]:
        headers = login(client, email, password)
        assert client.get("/api/v1/users/", headers=headers).status_code == 403


def test_list_users_allowed_for_admin(client, seed_users):
    headers = login(client, "admin@test.internal", ADMIN_PASSWORD)
    res = client.get("/api/v1/users/", headers=headers)
    assert res.status_code == 200
    assert {u["id"] for u in res.json()} == {"ADM001", "FAC001", "STU001"}


def test_create_user_denied_for_member(client, seed_users):
    headers = login(client, "member@test.internal", MEMBER_PASSWORD)
    assert client.post("/api/v1/users/", headers=headers, json=NEW_USER).status_code == 403


def test_create_user_as_admin_then_login(client, seed_users):
    headers = login(client, "admin@test.internal", ADMIN_PASSWORD)
    res = client.post("/api/v1/users/", headers=headers, json=NEW_USER)
    assert res.status_code == 201
    assert res.json()["id"] == "STU002"

    # The created credential actually works.
    assert login(client, "member2@test.internal", "MemberPass789!")


def test_create_user_conflicts(client, seed_users):
    headers = login(client, "admin@test.internal", ADMIN_PASSWORD)
    dup_id = dict(NEW_USER, id="STU001")
    assert client.post("/api/v1/users/", headers=headers, json=dup_id).status_code == 409
    dup_email = dict(NEW_USER, email_address="member@test.internal")
    assert client.post("/api/v1/users/", headers=headers, json=dup_email).status_code == 409


def test_available_staff_visible_to_any_authenticated_user(client, seed_users):
    headers = login(client, "member@test.internal", MEMBER_PASSWORD)
    res = client.get("/api/v1/users/staff/available", headers=headers)
    assert res.status_code == 200
    listed = res.json()
    assert [f["id"] for f in listed] == ["FAC001"]
    assert listed[0]["current_occupancy_index"] == "OPEN_AD_HOC"


def test_unit_admin_cannot_create_admin_accounts(client, seed_users):
    headers = login(client, "admin@test.internal", ADMIN_PASSWORD)
    unit_admin = {
        "id": "DAD001",
        "full_name": "Unit Admin",
        "email_address": "unitadmin@test.internal",
        "password": "UnitAdmin456!",
        "role_type": "UNIT_ADMIN",
        "unit_code": "CSE",
    }
    assert client.post("/api/v1/users/", headers=headers, json=unit_admin).status_code == 201

    da_headers = login(client, "unitadmin@test.internal", "UnitAdmin456!")
    # Clear the first-login gate so the unit-admin can reach /users/.
    res = client.post(
        "/api/v1/auth/change-password",
        headers=da_headers,
        json={"current_password": "UnitAdmin456!", "new_password": "UnitAdmin789!"},
    )
    assert res.status_code == 200
    da_headers = login(client, "unitadmin@test.internal", "UnitAdmin789!")

    for role in ("SUPER_ADMIN", "UNIT_ADMIN"):
        payload = dict(
            NEW_USER,
            id=f"ESC_{role}",
            email_address=f"esc.{role.lower()}@test.internal",
            role_type=role,
        )
        res = client.post("/api/v1/users/", headers=da_headers, json=payload)
        assert res.status_code == 403

    # Ordinary members of their own unit are still theirs to create;
    # NEW_USER belongs to ECE, outside this CSE admin"s reach.
    assert client.post("/api/v1/users/", headers=da_headers, json=NEW_USER).status_code == 403
    own_unit = dict(NEW_USER, unit_code="CSE")
    assert client.post("/api/v1/users/", headers=da_headers, json=own_unit).status_code == 201


def test_unit_admin_cannot_modify_admin_accounts(client, seed_users):
    headers = login(client, "admin@test.internal", ADMIN_PASSWORD)
    unit_admin = {
        "id": "DAD002",
        "full_name": "Unit Admin Two",
        "email_address": "unitadmin2@test.internal",
        "password": "UnitAdmin456!",
        "role_type": "UNIT_ADMIN",
        "unit_code": "CSE",
    }
    assert client.post("/api/v1/users/", headers=headers, json=unit_admin).status_code == 201

    da_headers = login(client, "unitadmin2@test.internal", "UnitAdmin456!")
    res = client.post(
        "/api/v1/auth/change-password",
        headers=da_headers,
        json={"current_password": "UnitAdmin456!", "new_password": "UnitAdmin789!"},
    )
    assert res.status_code == 200
    da_headers = login(client, "unitadmin2@test.internal", "UnitAdmin789!")

    # Login is by email, so patching the super-admin's email would lock
    # them out. Any admin account is off-limits to a unit-admin.
    res = client.patch(
        "/api/v1/users/ADM001",
        headers=da_headers,
        json={"email_address": "stolen@test.internal"},
    )
    assert res.status_code == 403

    res = client.patch(
        "/api/v1/users/DAD002",
        headers=da_headers,
        json={"full_name": "Renamed Self"},
    )
    assert res.status_code == 403

    # Ordinary members are still theirs to manage.
    res = client.patch(
        "/api/v1/users/STU001",
        headers=da_headers,
        json={"full_name": "Renamed Member"},
    )
    assert res.status_code == 200

    # The super-admin can still rename a unit-admin.
    res = client.patch(
        "/api/v1/users/DAD002",
        headers=headers,
        json={"full_name": "Renamed By Super"},
    )
    assert res.status_code == 200
