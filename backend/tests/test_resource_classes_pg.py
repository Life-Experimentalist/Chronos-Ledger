# Copyright 2026 Chronos Ledger Contributors
# Licensed under the Apache License, Version 2.0
"""Resource classes on a real PostgreSQL, where the foreign keys do the holding.

A resource and a requirement name a class by (organization, code). The
application checks that the class is active and the organization's own, but the
rows must hold even when something writes around it: an import, a script, or a
request that raced a delete. SQLite does not enforce foreign keys here, so only
this file can show the database refusing each of those.

Skipped without TEST_DATABASE_URL, the same as the other *_pg.py files.
"""

import os
import uuid

import pytest
from sqlalchemy import create_engine, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.core.organization import DEFAULT_ORGANIZATION_ID
from app.core.schema import ensure_schema
from app.models.db import (
    Organization,
    RequirementOwner,
    Resource,
    ResourceClass,
    ResourceRequirement,
)

DATABASE_URL = os.environ.get("TEST_DATABASE_URL")

pytestmark = pytest.mark.skipif(
    not DATABASE_URL,
    reason="needs a real PostgreSQL: set TEST_DATABASE_URL",
)


@pytest.fixture(scope="module")
def engine():
    built = create_engine(DATABASE_URL)
    ensure_schema(built)
    yield built
    built.dispose()


@pytest.fixture()
def db(engine):
    """A session whose work is thrown away when the test ends."""
    connection = engine.connect()
    transaction = connection.begin()
    session = Session(bind=connection, join_transaction_mode="create_savepoint")
    try:
        yield session
    finally:
        session.close()
        transaction.rollback()
        connection.close()


def _codes(db, organization_id):
    rows = db.execute(
        select(ResourceClass.code)
        .where(ResourceClass.organization_id == organization_id)
        .order_by(ResourceClass.code)
    )
    return list(rows.scalars())


def test_the_default_organization_has_the_built_in_classes(db):
    assert {"PERSON", "ROOM"} <= set(_codes(db, DEFAULT_ORGANIZATION_ID))


def test_a_new_organization_is_seeded_with_room_and_person(db):
    other = f"pg-{uuid.uuid4().hex[:8]}"
    db.add(Organization(id=other, name="Another"))
    db.commit()

    assert _codes(db, other) == ["PERSON", "ROOM"]


def test_a_class_code_is_unique_within_an_organization(db):
    db.add(ResourceClass(organization_id=DEFAULT_ORGANIZATION_ID, code="PG_CART", name="Cart"))
    db.commit()

    db.add(ResourceClass(organization_id=DEFAULT_ORGANIZATION_ID, code="PG_CART", name="Again"))
    with pytest.raises(IntegrityError) as refused:
        db.commit()
    assert "uq_resource_classes_organization_code" in str(refused.value.orig)


def test_a_resource_cannot_name_a_class_the_organization_lacks(db):
    db.add(Resource(code="PG-CLS-1", label="x", resource_type="NO_SUCH_CLASS"))
    with pytest.raises(IntegrityError) as refused:
        db.commit()
    assert "fk_resources_class" in str(refused.value.orig)


def test_a_resource_cannot_name_another_organizations_class(db):
    other = f"pg-{uuid.uuid4().hex[:8]}"
    db.add(Organization(id=other, name="Another"))
    db.commit()
    db.add(ResourceClass(organization_id=other, code="PG_LAB", name="Lab"))
    db.commit()

    db.add(Resource(code="PG-CLS-2", label="x", resource_type="PG_LAB"))
    with pytest.raises(IntegrityError) as refused:
        db.commit()
    assert "fk_resources_class" in str(refused.value.orig)


def test_a_requirement_cannot_ask_for_a_class_the_organization_lacks(db):
    owner = Resource(code="PG-CLS-3", label="x")
    db.add(owner)
    db.commit()

    db.add(
        ResourceRequirement(
            owner_kind=RequirementOwner.RESOURCE, owner_id=owner.id, target_kind="NO_SUCH_CLASS"
        )
    )
    with pytest.raises(IntegrityError) as refused:
        db.commit()
    assert "fk_resource_requirements_class" in str(refused.value.orig)


def test_a_class_in_use_cannot_be_deleted_underneath_its_resources(db):
    cart = ResourceClass(organization_id=DEFAULT_ORGANIZATION_ID, code="PG_CART2", name="Cart")
    db.add(cart)
    db.commit()
    db.add(Resource(code="PG-CLS-4", label="x", resource_type="PG_CART2"))
    db.commit()

    db.delete(cart)
    with pytest.raises(IntegrityError) as refused:
        db.commit()
    assert "fk_resources_class" in str(refused.value.orig)
