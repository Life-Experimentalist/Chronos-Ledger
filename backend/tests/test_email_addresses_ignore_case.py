# Copyright 2026 Chronos Ledger Contributors
# Licensed under the Apache License, Version 2.0
"""An address names one account, whatever case it is written in.

Two things used to be true. Two accounts could exist differing only by case,
and somebody whose stored address carries a capital got a 401 for typing their
own address in lower case, which reads as a wrong password and is not one.
uq_users_email_address_lower closes the first with a unique index on
lower(email_address); these pin down the second and the writers that now agree
on a stored case.

Every address here varies in its local part. The domain half proves nothing:
email-validator lowercases it before a schema is ever handed one.
"""

import pytest
from sqlalchemy import text
from sqlalchemy.exc import IntegrityError

from app.core.security import hash_password
from app.models.db import User
from tests.conftest import ADMIN_PASSWORD, login
from tests.test_ingestion import HEADER, _make_cycle, _upload
from tests.test_users_rbac import NEW_USER

LEGACY_PASSWORD = "LegacyPass123!"
_LEGACY_HASH = hash_password(LEGACY_PASSWORD)
# Written the way somebody typed it the day the account was made, which is
# what a row inserted before 029 still holds.
STORED = "Priya.Sharma@test.internal"


def _plant_a_row_written_before_029(db, address=STORED, user_id="STU900"):
    """A row that keeps its original case, the way 029 finds them.

    Straight SQL because an ORM insert goes through the model's validator and
    comes out folded, which would prove nothing: the point of these tests is
    what happens to a row the validator never saw.
    """
    db.execute(
        text(
            "INSERT INTO users (id, full_name, email_address, credential_secure_hash,"
            " role_type, unit_code, initial_login_state, organization_id)"
            " VALUES (:id, 'Priya Sharma', :email, :hash, 'MEMBER', 'CSE', 0, 'default')"
        ),
        {"id": user_id, "email": address, "hash": _LEGACY_HASH},
    )
    db.commit()


def _csv(email, member_id="STU901"):
    return (
        HEADER + "\n"
        f"{member_id},Grace Hoppen,{email},MA201,Linear Algebra,"
        "CSE,2,09:00,10:00,FAC001,LH-201\n"
    )


def test_a_legacy_address_signs_in_in_whatever_case_the_person_types(client, db, seed_users):
    _plant_a_row_written_before_029(db)

    assert login(client, STORED, LEGACY_PASSWORD)
    assert login(client, STORED.lower(), LEGACY_PASSWORD)
    assert login(client, STORED.upper(), LEGACY_PASSWORD)

    # Nothing rewrote the row on the way past. The validator does not fire on
    # load, so what an admin sees is still the case it was stored with.
    assert db.query(User).filter(User.id == "STU900").one().email_address == STORED


def test_a_wrong_password_is_still_a_401_whatever_the_case(client, db, seed_users):
    _plant_a_row_written_before_029(db)

    res = client.post(
        "/api/v1/auth/login",
        json={"email_address": STORED.lower(), "password": "NotTheirPassword1!"},
    )
    assert res.status_code == 401, res.text


def test_an_address_is_stored_folded_whoever_wrote_it(client, db, seed_users):
    headers = login(client, "admin@test.internal", ADMIN_PASSWORD)
    res = client.post(
        "/api/v1/users/",
        headers=headers,
        json=dict(NEW_USER, email_address="Member.Two@test.internal"),
    )
    assert res.status_code == 201, res.text
    assert res.json()["email_address"] == "member.two@test.internal"

    db.expire_all()
    stored = db.query(User).filter(User.id == NEW_USER["id"]).one()
    assert stored.email_address == "member.two@test.internal"
    assert login(client, "Member.Two@test.internal", NEW_USER["password"])


def test_a_new_account_differing_from_another_only_by_case_is_a_409(client, seed_users):
    headers = login(client, "admin@test.internal", ADMIN_PASSWORD)
    res = client.post(
        "/api/v1/users/",
        headers=headers,
        json=dict(NEW_USER, email_address="Member@test.internal"),
    )
    assert res.status_code == 409, res.text
    assert res.json()["detail"] == "Email already registered"


def test_a_patch_onto_another_account_by_case_alone_is_a_409(client, db, seed_users):
    headers = login(client, "admin@test.internal", ADMIN_PASSWORD)
    res = client.patch(
        "/api/v1/users/STU001", headers=headers, json={"email_address": "Staff@test.internal"}
    )
    assert res.status_code == 409, res.text

    db.expire_all()
    assert db.query(User).filter(User.id == "STU001").one().email_address == "member@test.internal"


def test_a_patch_recasing_your_own_address_is_not_a_conflict_with_yourself(client, db, seed_users):
    headers = login(client, "admin@test.internal", ADMIN_PASSWORD)
    res = client.patch(
        "/api/v1/users/STU001", headers=headers, json={"email_address": "Member@test.internal"}
    )
    assert res.status_code == 200, res.text
    assert res.json()["email_address"] == "member@test.internal"


def test_an_import_does_not_read_a_case_variant_as_an_address_change(client, db, seed_users):
    cycle = _make_cycle(db)
    headers = login(client, "admin@test.internal", ADMIN_PASSWORD)
    assert _upload(client, headers, cycle.id, _csv("grace@test.internal")).status_code == 200
    assert _upload(client, headers, cycle.id, _csv("Grace@Test.internal")).status_code == 200

    db.expire_all()
    assert db.query(User).filter(User.id == "STU901").one().email_address == "grace@test.internal"


def test_an_import_naming_another_members_address_in_another_case_is_named(client, db, seed_users):
    cycle = _make_cycle(db)
    headers = login(client, "admin@test.internal", ADMIN_PASSWORD)
    assert _upload(client, headers, cycle.id, _csv("grace@test.internal")).status_code == 200

    res = _upload(client, headers, cycle.id, _csv("Grace@Test.internal", member_id="STU900"))
    assert res.status_code == 422, res.text
    detail = res.json()["detail"]
    # The cell as the file spells it, because that is the line to go and fix.
    assert "Grace@Test.internal" in detail
    assert "STU901" in detail

    db.expire_all()
    assert db.query(User).filter(User.id == "STU900").first() is None


def test_two_rows_differing_only_by_case_meet_the_index(db):
    """The index holds the line with no application code in the way.

    This is what 029 creates in Postgres, and what a writer nobody has thought
    of yet runs into.
    """
    _plant_a_row_written_before_029(db)
    with pytest.raises(IntegrityError):
        _plant_a_row_written_before_029(db, address=STORED.lower(), user_id="STU901")
    db.rollback()
