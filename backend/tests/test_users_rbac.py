# Copyright 2026 Chronos Ledger Contributors
# Licensed under the Apache License, Version 2.0

from tests.conftest import ADMIN_PASSWORD, FACULTY_PASSWORD, STUDENT_PASSWORD, login

NEW_USER = {
    "id": "STU002",
    "full_name": "Student Two",
    "email_address": "student2@test.internal",
    "password": "StudentPass789!",
    "role_type": "STUDENT",
    "department_code": "ECE",
}


def test_list_users_denied_for_student_and_faculty(client, seed_users):
    for email, password in [
        ("student@test.internal", STUDENT_PASSWORD),
        ("faculty@test.internal", FACULTY_PASSWORD),
    ]:
        headers = login(client, email, password)
        assert client.get("/api/v1/users/", headers=headers).status_code == 403


def test_list_users_allowed_for_admin(client, seed_users):
    headers = login(client, "admin@test.internal", ADMIN_PASSWORD)
    res = client.get("/api/v1/users/", headers=headers)
    assert res.status_code == 200
    assert {u["id"] for u in res.json()} == {"ADM001", "FAC001", "STU001"}


def test_create_user_denied_for_student(client, seed_users):
    headers = login(client, "student@test.internal", STUDENT_PASSWORD)
    assert client.post("/api/v1/users/", headers=headers, json=NEW_USER).status_code == 403


def test_create_user_as_admin_then_login(client, seed_users):
    headers = login(client, "admin@test.internal", ADMIN_PASSWORD)
    res = client.post("/api/v1/users/", headers=headers, json=NEW_USER)
    assert res.status_code == 201
    assert res.json()["id"] == "STU002"

    # The created credential actually works.
    assert login(client, "student2@test.internal", "StudentPass789!")


def test_create_user_conflicts(client, seed_users):
    headers = login(client, "admin@test.internal", ADMIN_PASSWORD)
    dup_id = dict(NEW_USER, id="STU001")
    assert client.post("/api/v1/users/", headers=headers, json=dup_id).status_code == 409
    dup_email = dict(NEW_USER, email_address="student@test.internal")
    assert client.post("/api/v1/users/", headers=headers, json=dup_email).status_code == 409


def test_available_faculty_visible_to_any_authenticated_user(client, seed_users):
    headers = login(client, "student@test.internal", STUDENT_PASSWORD)
    res = client.get("/api/v1/users/faculty/available", headers=headers)
    assert res.status_code == 200
    listed = res.json()
    assert [f["id"] for f in listed] == ["FAC001"]
    assert listed[0]["current_occupancy_index"] == "OPEN_AD_HOC"


def test_dept_admin_cannot_create_admin_accounts(client, seed_users):
    headers = login(client, "admin@test.internal", ADMIN_PASSWORD)
    dept_admin = {
        "id": "DAD001",
        "full_name": "Dept Admin",
        "email_address": "deptadmin@test.internal",
        "password": "DeptAdmin456!",
        "role_type": "DEPT_ADMIN",
        "department_code": "CSE",
    }
    assert client.post("/api/v1/users/", headers=headers, json=dept_admin).status_code == 201

    da_headers = login(client, "deptadmin@test.internal", "DeptAdmin456!")
    # Clear the first-login gate so the dept-admin can reach /users/.
    res = client.post(
        "/api/v1/auth/change-password",
        headers=da_headers,
        json={"current_password": "DeptAdmin456!", "new_password": "DeptAdmin789!"},
    )
    assert res.status_code == 200
    da_headers = login(client, "deptadmin@test.internal", "DeptAdmin789!")

    for role in ("SUPER_ADMIN", "DEPT_ADMIN"):
        payload = dict(
            NEW_USER,
            id=f"ESC_{role}",
            email_address=f"esc.{role.lower()}@test.internal",
            role_type=role,
        )
        res = client.post("/api/v1/users/", headers=da_headers, json=payload)
        assert res.status_code == 403

    # Ordinary members are still theirs to create.
    assert client.post("/api/v1/users/", headers=da_headers, json=NEW_USER).status_code == 201
