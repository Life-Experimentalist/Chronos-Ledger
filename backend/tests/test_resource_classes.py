# Copyright 2026 Chronos Ledger Contributors
# Licensed under the Apache License, Version 2.0
"""Resource classes are configured per organization, not fixed in the code.

ROOM and PERSON exist for every organization and anchor the behaviour that
predates classes. Anything an administrator adds is a label: resources are
filed under it and requirements can ask for it, and nothing else changes.

The PostgreSQL side is in tests/test_resource_classes_pg.py.
"""

from app.core.organization import DEFAULT_ORGANIZATION_ID, use_organization
from app.models.db import Organization, Resource, ResourceClass
from tests.conftest import STAFF_PASSWORD, login
from tests.test_resource_requirements import (
    _admin,
    _book,
    _needs_kind,
    _person,
    _require,
    _resource,
)

CLASSES = "/api/v1/resource-classes"
RESOURCES = "/api/v1/resources"


def _staff(client):
    return login(client, "staff@test.internal", STAFF_PASSWORD)


def _make(client, headers, code="CART", name="Cart"):
    return client.post(CLASSES, json={"code": code, "name": name}, headers=headers)


def _codes(client, headers, **params):
    res = client.get(CLASSES, params=params, headers=headers)
    assert res.status_code == 200, res.text
    return [row["code"] for row in res.json()]


def _new_resource(client, headers, code, kind):
    return client.post(RESOURCES, json={"code": code, "resource_type": kind}, headers=headers)


# -- Seeding ---------------------------------------------------------------------


def test_every_organization_starts_with_room_and_person(client, db, seed_users):
    db.add(Organization(id="other", name="Other"))
    db.commit()

    rows = db.query(ResourceClass).order_by(ResourceClass.organization_id, ResourceClass.code).all()
    seen = [(row.organization_id, row.code) for row in rows]

    assert seen == [
        (DEFAULT_ORGANIZATION_ID, "PERSON"),
        (DEFAULT_ORGANIZATION_ID, "ROOM"),
        ("other", "PERSON"),
        ("other", "ROOM"),
    ]
    assert all(row.active for row in rows)


def test_the_list_marks_the_built_in_classes(client, db, seed_users):
    res = client.get(CLASSES, headers=_staff(client))

    assert res.status_code == 200, res.text
    assert [(row["code"], row["name"], row["seeded"]) for row in res.json()] == [
        ("PERSON", "Person", True),
        ("ROOM", "Room", True),
    ]


def test_anyone_signed_in_can_list_but_only_an_administrator_changes(client, db, seed_users):
    staff = _staff(client)

    assert client.get(CLASSES).status_code == 401
    assert _make(client, staff).status_code == 403
    assert client.patch(f"{CLASSES}/ROOM", json={"name": "Space"}, headers=staff).status_code == 403
    assert client.delete(f"{CLASSES}/ROOM", headers=staff).status_code == 403


# -- A custom class --------------------------------------------------------------


def test_an_administrator_adds_a_class_and_files_a_resource_under_it(client, db, seed_users):
    headers = _admin(client)

    made = _make(client, headers, "CART", "Equipment cart")
    assert made.status_code == 201, made.text
    assert made.json()["code"] == "CART"
    assert made.json()["seeded"] is False
    assert made.json()["active"] is True

    res = _new_resource(client, headers, "CART-1", "CART")
    assert res.status_code == 201, res.text
    assert res.json()["resource_type"] == "CART"

    listed = client.get(RESOURCES, params={"resource_type": "CART"}, headers=headers)
    assert [row["code"] for row in listed.json()] == ["CART-1"]
    assert _codes(client, headers) == ["CART", "PERSON", "ROOM"]


def test_a_code_taken_is_a_conflict_and_a_bad_code_is_invalid(client, db, seed_users):
    headers = _admin(client)
    assert _make(client, headers).status_code == 201

    again = _make(client, headers)
    assert again.status_code == 409
    assert again.json()["code"] == "ALREADY_EXISTS"
    assert _make(client, headers, "ROOM", "Space").status_code == 409

    for bad in ("cart", "1CART", "CART 2", "CART-2", ""):
        assert _make(client, headers, bad).status_code == 422, bad


def test_a_custom_class_changes_nothing_about_how_a_resource_books(client, db, seed_users):
    headers = _admin(client)
    _make(client, headers)
    cart = _resource(db, "CART-1", kind="CART")

    first = _book(client, headers, cart.id, "one")
    clash = _book(client, headers, cart.id, "two")

    assert first.status_code == 201, first.text
    assert clash.status_code == 409


def test_a_requirement_can_ask_for_a_custom_class(client, db, seed_users):
    headers = _admin(client)
    _make(client, headers)
    cart = _resource(db, "CART-1", kind="CART")
    room = _resource(db, "OR-1")
    _needs_kind(client, headers, room.id, "CART", enforcement="REQUIRED")

    res = _book(client, headers, room.id, "with-cart")

    assert res.status_code == 201, res.text
    assert [child["resource_id"] for child in res.json()["children"]] == [cart.id]


def test_a_required_custom_class_with_no_resource_blocks_the_booking(client, db, seed_users):
    headers = _admin(client)
    _make(client, headers)
    room = _resource(db, "OR-1")
    _needs_kind(client, headers, room.id, "CART", enforcement="REQUIRED")

    res = _book(client, headers, room.id, "no-cart")

    assert res.status_code == 409
    assert res.json()["code"] == "REQUIREMENT_UNSATISFIED"


def test_assignments_are_keyed_by_a_custom_class(client, db, seed_users):
    headers = _admin(client)
    _make(client, headers)
    cart = _resource(db, "CART-1", kind="CART")
    _resource(db, "CART-2", kind="CART")
    room = _resource(db, "OR-1")
    _needs_kind(client, headers, room.id, "CART", enforcement="REQUIRED")

    res = _book(client, headers, room.id, "named", assignments={"CART": [cart.id]})

    assert res.status_code == 201, res.text
    assert [child["resource_id"] for child in res.json()["children"]] == [cart.id]


# -- Unknown, inactive and another organization's class ---------------------------


def test_an_unknown_class_is_refused_everywhere(client, db, seed_users):
    headers = _admin(client)
    room = _resource(db, "OR-1")

    made = _new_resource(client, headers, "X-1", "WIDGET")
    required = _require(client, headers, room.id, target_kind="WIDGET")

    for res in (made, required):
        assert res.status_code == 422, res.text
        assert res.json()["code"] == "UNKNOWN_RESOURCE_CLASS"
    assert db.query(Resource).filter_by(code="X-1").first() is None


def test_an_inactive_class_takes_no_new_uses_and_keeps_the_old(client, db, seed_users):
    headers = _admin(client)
    _make(client, headers)
    kept = _resource(db, "CART-1", kind="CART")
    room = _resource(db, "OR-1")
    _needs_kind(client, headers, room.id, "CART")

    off = client.patch(f"{CLASSES}/CART", json={"active": False}, headers=headers)
    assert off.status_code == 200, off.text
    assert off.json()["active"] is False

    refused = _new_resource(client, headers, "CART-2", "CART")
    assert refused.status_code == 422
    assert refused.json()["code"] == "UNKNOWN_RESOURCE_CLASS"
    res = _require(client, headers, room.id, target_kind="CART", quantity=2)
    assert res.status_code == 422
    assert res.json()["code"] == "UNKNOWN_RESOURCE_CLASS"
    db.expire_all()
    assert db.query(Resource).filter_by(id=kept.id).one().resource_type == "CART"
    assert _codes(client, headers, active="true") == ["PERSON", "ROOM"]
    assert _codes(client, headers, active="false") == ["CART"]

    on = client.patch(f"{CLASSES}/CART", json={"active": True}, headers=headers)
    assert on.status_code == 200
    assert _new_resource(client, headers, "CART-2", "CART").status_code == 201


def test_another_organizations_class_is_not_ours_to_use(client, db, seed_users):
    headers = _admin(client)
    db.add(Organization(id="other", name="Other"))
    db.commit()
    db.add(ResourceClass(organization_id="other", code="LAB", name="Lab bench"))
    db.commit()
    room = _resource(db, "OR-1")

    assert _codes(client, headers) == ["PERSON", "ROOM"]
    made = _new_resource(client, headers, "B-1", "LAB")
    required = _require(client, headers, room.id, target_kind="LAB")
    assert made.status_code == 422
    assert made.json()["code"] == "UNKNOWN_RESOURCE_CLASS"
    assert required.status_code == 422
    assert required.json()["code"] == "UNKNOWN_RESOURCE_CLASS"
    assert client.patch(f"{CLASSES}/LAB", json={"name": "x"}, headers=headers).status_code == 404
    assert client.delete(f"{CLASSES}/LAB", headers=headers).status_code == 404

    # The same code is free in this organization, and the other one is untouched.
    assert _make(client, headers, "LAB", "Our lab").status_code == 201
    use_organization(db, "other")
    try:
        assert db.query(ResourceClass).filter_by(code="LAB").one().name == "Lab bench"
    finally:
        use_organization(db, DEFAULT_ORGANIZATION_ID)


# -- ROOM and PERSON stay ---------------------------------------------------------


def test_the_built_in_classes_can_be_renamed_but_not_removed_or_switched_off(
    client, db, seed_users
):
    headers = _admin(client)

    renamed = client.patch(f"{CLASSES}/ROOM", json={"name": "Space"}, headers=headers)
    assert renamed.status_code == 200, renamed.text
    assert renamed.json()["name"] == "Space"
    assert renamed.json()["code"] == "ROOM"

    for code in ("ROOM", "PERSON"):
        off = client.patch(f"{CLASSES}/{code}", json={"active": False}, headers=headers)
        assert off.status_code == 409
        assert off.json()["code"] == "RESOURCE_CLASS_PROTECTED"
        gone = client.delete(f"{CLASSES}/{code}", headers=headers)
        assert gone.status_code == 409
        assert gone.json()["code"] == "RESOURCE_CLASS_PROTECTED"
    assert _codes(client, headers) == ["PERSON", "ROOM"]


def test_a_code_cannot_be_changed(client, db, seed_users):
    headers = _admin(client)
    _make(client, headers)

    res = client.patch(f"{CLASSES}/CART", json={"code": "TROLLEY"}, headers=headers)

    assert res.status_code == 200
    assert res.json()["code"] == "CART"
    assert _codes(client, headers) == ["CART", "PERSON", "ROOM"]


def test_an_update_with_an_explicit_null_is_refused(client, db, seed_users):
    headers = _admin(client)
    _make(client, headers)

    for body in ({"name": None}, {"active": None}):
        assert client.patch(f"{CLASSES}/CART", json=body, headers=headers).status_code == 422


def test_behaviour_that_predates_classes_still_follows_the_seeded_ones(client, db, seed_users):
    # A resource is still a ROOM by default, and a requirement for PERSON still
    # picks people rather than rooms.
    headers = _admin(client)
    made = client.post(RESOURCES, json={"code": "R-1"}, headers=headers)
    assert made.status_code == 201, made.text
    assert made.json()["resource_type"] == "ROOM"

    room = _resource(db, "OR-2")
    person = _person(db, "P-A")
    _resource(db, "R-9")
    _needs_kind(client, headers, room.id, "PERSON", enforcement="REQUIRED")

    res = _book(client, headers, room.id, "crew")

    assert res.status_code == 201, res.text
    assert [child["resource_id"] for child in res.json()["children"]] == [person.id]


# -- Delete is refused while a class is in use -------------------------------------


def test_a_class_nothing_uses_can_be_deleted(client, db, seed_users):
    headers = _admin(client)
    _make(client, headers)

    res = client.delete(f"{CLASSES}/CART", headers=headers)

    assert res.status_code == 204
    assert _codes(client, headers) == ["PERSON", "ROOM"]
    assert client.delete(f"{CLASSES}/CART", headers=headers).status_code == 404


def test_a_class_a_resource_has_cannot_be_deleted_even_when_inactive(client, db, seed_users):
    headers = _admin(client)
    _make(client, headers)
    _resource(db, "CART-1", kind="CART")

    res = client.delete(f"{CLASSES}/CART", headers=headers)
    assert res.status_code == 409
    assert res.json()["code"] == "RESOURCE_CLASS_IN_USE"

    client.patch(f"{CLASSES}/CART", json={"active": False}, headers=headers)
    again = client.delete(f"{CLASSES}/CART", headers=headers)
    assert again.status_code == 409
    assert again.json()["code"] == "RESOURCE_CLASS_IN_USE"


def test_a_class_a_requirement_asks_for_cannot_be_deleted(client, db, seed_users):
    headers = _admin(client)
    _make(client, headers)
    room = _resource(db, "OR-1")
    _needs_kind(client, headers, room.id, "CART")

    res = client.delete(f"{CLASSES}/CART", headers=headers)

    assert res.status_code == 409
    assert res.json()["code"] == "RESOURCE_CLASS_IN_USE"
