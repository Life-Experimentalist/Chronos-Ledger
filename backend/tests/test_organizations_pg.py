# Copyright 2026 Chronos Ledger Contributors
# Licensed under the Apache License, Version 2.0
"""Two organizations on a real PostgreSQL, each with its own room 101.

The SQLite file in tests/test_organizations.py shows the same thing; this is
where it has to hold, with uq_resources_organization_code and the exclusion
constraint on the reservations as PostgreSQL builds them, and both bookings
sent at the same moment on connections of their own.

Skipped without TEST_DATABASE_URL, the same as the other *_pg.py files.
"""

import asyncio
import datetime
import os
import uuid
from contextlib import contextmanager

import httpx
import pytest
from sqlalchemy import create_engine, delete, text, update
from sqlalchemy.orm import Session

from app.core.database import Base, get_db, get_session_opener
from app.core.schema import ensure_schema
from app.main import app
from app.models.db import User
from app.services.organizations import create_organization

DATABASE_URL = os.environ.get("TEST_DATABASE_URL")

pytestmark = pytest.mark.skipif(
    not DATABASE_URL,
    reason="needs a real PostgreSQL: set TEST_DATABASE_URL",
)

PASSWORD = "OrgPassword123!"
DAY = datetime.date(2026, 4, 7)


@pytest.fixture(scope="module")
def engine():
    built = create_engine(DATABASE_URL, pool_size=10, max_overflow=5)
    ensure_schema(built)
    yield built
    built.dispose()


def test_the_room_code_is_unique_per_organization_in_the_database(engine):
    with engine.connect() as connection:
        columns = connection.execute(
            text(
                "SELECT a.attname FROM pg_constraint c"
                " JOIN pg_attribute a ON a.attrelid = c.conrelid AND a.attnum = ANY (c.conkey)"
                " WHERE c.conname = 'uq_resources_organization_code'"
                " AND c.conrelid = 'resources'::regclass"
            )
        ).scalars()
        assert set(columns) == {"organization_id", "code"}


@pytest.fixture()
def organizations(engine):
    """Two new organizations, each with an admin past the first-login change.

    Committed, because every request below has a session of its own, and
    removed afterwards, table by table, so the shared database is left as it
    was found.
    """
    run = uuid.uuid4().hex[:8]
    made = [(f"pg-org-a-{run}", f"PGA{run}"), (f"pg-org-b-{run}", f"PGB{run}")]
    with Session(engine) as db:
        for organization, admin in made:
            create_organization(
                db, organization, organization, admin, f"{admin.lower()}@test.internal", PASSWORD
            )
        db.flush()
        db.execute(
            update(User)
            .where(User.id.in_([admin for _, admin in made]))
            .values(initial_login_state=False)
        )
        db.commit()
    try:
        yield [(organization, f"{admin.lower()}@test.internal") for organization, admin in made]
    finally:
        names = [organization for organization, _ in made]
        admins = [admin for _, admin in made]
        with Session(engine) as db:
            for table in reversed(Base.metadata.sorted_tables):
                if table.name == "organizations":
                    db.execute(delete(table).where(table.c.id.in_(names)))
                elif "organization_id" in table.c:
                    db.execute(delete(table).where(table.c.organization_id.in_(names)))
                elif table.name == "idempotency_records":
                    callers = [f"user:{admin}" for admin in admins]
                    db.execute(delete(table).where(table.c.caller.in_(callers)))
                else:
                    for key in table.foreign_keys:
                        if key.column.table.name == "users":
                            db.execute(delete(table).where(key.parent.in_(admins)))
            db.commit()


async def _two_organizations(emails: list[str]) -> dict:
    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://testserver") as client:
        heads = []
        for email in emails:
            token = await client.post(
                "/api/v1/auth/login", json={"email_address": email, "password": PASSWORD}
            )
            assert token.status_code == 200, token.text
            heads.append({"Authorization": f"Bearer {token.json()['access_token']}"})

        rooms = await asyncio.gather(
            *(client.post("/api/v1/resources/", json={"code": "101"}, headers=h) for h in heads)
        )
        assert [r.status_code for r in rooms] == [201, 201], [r.text for r in rooms]
        ids = [r.json()["id"] for r in rooms]

        def book(headers, resource_id, key):
            return client.post(
                f"/api/v1/resources/{resource_id}/reservations",
                headers={**headers, "Idempotency-Key": key},
                json={
                    "date": DAY.isoformat(),
                    "start": "09:00:00",
                    "end": "10:00:00",
                    "purpose": "Review",
                },
            )

        booked = await asyncio.gather(
            book(heads[0], ids[0], "pg-org-own-a"), book(heads[1], ids[1], "pg-org-own-b")
        )
        across = await asyncio.gather(
            client.get(
                f"/api/v1/resources/{ids[0]}/availability",
                params={"from": DAY.isoformat(), "to": DAY.isoformat()},
                headers=heads[1],
            ),
            book(heads[1], ids[0], "pg-org-into-a"),
            client.get("/api/v1/resources/", params={"code": "101"}, headers=heads[1]),
        )
        return {"ids": ids, "booked": booked, "across": across}


def test_two_organizations_book_their_own_room_101_and_cannot_reach_the_other(
    engine, organizations
):
    def own_session():
        session = Session(engine)
        try:
            yield session
        finally:
            session.close()

    @contextmanager
    def own_open_session():
        # AuditMiddleware writes in a session of its own; left alone it opens
        # one on the configured database_url, not this one.
        with Session(engine) as session:
            yield session

    app.dependency_overrides[get_db] = own_session
    app.dependency_overrides[get_session_opener] = lambda: own_open_session
    try:
        found = asyncio.run(_two_organizations([email for _, email in organizations]))
    finally:
        app.dependency_overrides.clear()

    room_a, room_b = found["ids"]
    assert room_a != room_b
    assert [r.status_code for r in found["booked"]] == [201, 201], [r.text for r in found["booked"]]

    seen, booked, listed = found["across"]
    assert (seen.status_code, seen.json()["code"]) == (404, "NOT_FOUND")
    assert (booked.status_code, booked.json()["code"]) == (404, "NOT_FOUND")
    assert [r["id"] for r in listed.json()] == [room_b]
