# Copyright 2026 Chronos Ledger Contributors
# Licensed under the Apache License, Version 2.0
"""Two organizations on one deployment, each seeing and booking only its own.

On a SQLite file with foreign keys on and a session per request, as a server
runs, rather than the shared in-memory session the rest of the suite uses:
that session would remember rows across callers, and the scoping under test
is per session. tests/test_organizations_pg.py is the same check on
PostgreSQL.
"""

import datetime
import io
import json
import os
import zipfile
from contextlib import contextmanager

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import select
from sqlalchemy.orm import Session, sessionmaker

from app import standalone
from app.core.config import get_settings
from app.core.database import get_db, get_session_opener, sqlite_engine
from app.core.organization import DEFAULT_ORGANIZATION_ID, use_organization
from app.core.schema import ensure_schema
from app.core.security import hash_password
from app.cron.ledger_generator import generate_daily_ledger_entries, materialize_horizon
from app.main import app
from app.models.db import (
    Activity,
    ChangeMarker,
    DailyLedger,
    InstitutionalRole,
    Organization,
    PlanningCycle,
    Resource,
    StructuralMasterSlot,
    User,
    WebhookDelivery,
    WebhookSubscription,
)
from app.services.organizations import create_organization
from app.services.webhooks import fan_out
from tests.conftest import weekly

PASSWORD = "OrgPassword123!"
SECOND = "second"
DAY = "2026-04-07"


@pytest.fixture()
def engine(tmp_path):
    built = sqlite_engine(f"sqlite:///{(tmp_path / 'organizations.db').as_posix()}")
    ensure_schema(built)
    with Session(built) as db:
        db.add(
            User(
                id="ADM-A",
                full_name="Admin A",
                email_address="admin-a@test.internal",
                credential_secure_hash=hash_password(PASSWORD),
                role_type=InstitutionalRole.ORG_ADMIN,
                initial_login_state=False,
            )
        )
        create_organization(db, SECOND, "Second", "ADM-B", "admin-b@test.internal", PASSWORD)
        db.commit()
    yield built
    built.dispose()


@pytest.fixture()
def client(engine):
    opened = sessionmaker(autocommit=False, autoflush=False, bind=engine)

    def own_session():
        with opened() as session:
            yield session

    @contextmanager
    def own_open_session():
        with opened() as session:
            yield session

    app.dependency_overrides[get_db] = own_session
    app.dependency_overrides[get_session_opener] = lambda: own_open_session
    try:
        yield TestClient(app)
    finally:
        app.dependency_overrides.clear()


def _sign_in(client, email: str) -> dict:
    res = client.post("/api/v1/auth/login", json={"email_address": email, "password": PASSWORD})
    assert res.status_code == 200, res.text
    return {"Authorization": f"Bearer {res.json()['access_token']}"}


@pytest.fixture()
def heads(client):
    """A's admin, and B's admin past the first-login password change."""
    b = _sign_in(client, "admin-b@test.internal")
    changed = client.post(
        "/api/v1/auth/change-password",
        json={"current_password": PASSWORD, "new_password": PASSWORD + "x"},
        headers=b,
    )
    assert changed.status_code == 200, changed.text
    res = client.post(
        "/api/v1/auth/login",
        json={"email_address": "admin-b@test.internal", "password": PASSWORD + "x"},
    )
    assert res.status_code == 200, res.text
    b = {"Authorization": f"Bearer {res.json()['access_token']}"}
    return _sign_in(client, "admin-a@test.internal"), b


def _room(client, headers, code="101") -> int:
    res = client.post("/api/v1/resources/", json={"code": code}, headers=headers)
    assert res.status_code == 201, res.text
    return res.json()["id"]


def _book(client, headers, resource_id: int, key: str):
    return client.post(
        f"/api/v1/resources/{resource_id}/reservations",
        json={"date": DAY, "start": "09:00:00", "end": "10:00:00", "purpose": "Review"},
        headers={**headers, "Idempotency-Key": key},
    )


def test_two_organizations_each_have_room_101_and_book_the_same_hour(client, heads):
    a, b = heads
    room_a = _room(client, a)
    room_b = _room(client, b)
    assert room_a != room_b

    first = _book(client, a, room_a, "org-a-booking")
    second = _book(client, b, room_b, "org-b-booking")
    assert first.status_code == 201, first.text
    assert second.status_code == 201, second.text


def test_a_code_is_still_unique_inside_one_organization(client, heads):
    a, _ = heads
    _room(client, a)
    again = client.post("/api/v1/resources/", json={"code": "101"}, headers=a)
    assert again.status_code == 409
    assert again.json()["code"] == "ALREADY_EXISTS"


def test_neither_organization_can_read_or_book_the_others_room(client, heads):
    a, b = heads
    room_a = _room(client, a)
    room_b = _room(client, b)

    listed = client.get("/api/v1/resources/", headers=b).json()
    assert [r["id"] for r in listed] == [room_b]
    by_code = client.get("/api/v1/resources/", params={"code": "101"}, headers=a).json()
    assert [r["id"] for r in by_code] == [room_a]

    seen = client.get(
        f"/api/v1/resources/{room_a}/availability",
        params={"from": DAY, "to": DAY},
        headers=b,
    )
    assert seen.status_code == 404
    assert seen.json()["code"] == "NOT_FOUND"

    booked = _book(client, b, room_a, "org-b-into-a")
    assert booked.status_code == 404
    assert booked.json()["code"] == "NOT_FOUND"

    renamed = client.patch(f"/api/v1/resources/{room_a}", json={"label": "Mine now"}, headers=b)
    assert renamed.status_code == 404

    # A's own booking of its room is untouched by any of that.
    assert _book(client, a, room_a, "org-a-own").status_code == 201


def test_a_booking_in_one_organization_does_not_show_in_the_other(client, heads):
    a, b = heads
    room_a = _room(client, a)
    held = _book(client, a, room_a, "org-a-held")
    assert held.status_code == 201
    reservation_id = held.json()["id"]

    cancelled = client.delete(
        f"/api/v1/resources/{room_a}/reservations/{reservation_id}", headers=b
    )
    assert cancelled.status_code == 404
    assert client.get("/api/v1/resources/reservations", headers=b).json() == []


def test_people_are_scoped_but_ids_and_addresses_stay_unique_everywhere(client, heads):
    a, b = heads
    ids = {u["id"] for u in client.get("/api/v1/users/", headers=b).json()}
    assert ids == {"ADM-B"}
    assert client.get("/api/v1/users/ADM-A", headers=b).status_code == 404

    taken = client.post(
        "/api/v1/users/",
        json={
            "id": "NEW-B",
            "full_name": "Copy",
            "email_address": "admin-a@test.internal",
            "password": PASSWORD,
            "role_type": "MEMBER",
        },
        headers=b,
    )
    assert taken.status_code == 409
    assert taken.json()["code"] == "EMAIL_TAKEN"

    same_id = client.post(
        "/api/v1/users/",
        json={
            "id": "ADM-A",
            "full_name": "Copy",
            "email_address": "copy@test.internal",
            "password": PASSWORD,
            "role_type": "MEMBER",
        },
        headers=b,
    )
    assert same_id.status_code == 409

    me = client.get("/api/v1/auth/me", headers=b).json()
    assert me["organization_id"] == SECOND
    me = client.get("/api/v1/auth/me", headers=a).json()
    assert me["organization_id"] == DEFAULT_ORGANIZATION_ID


def test_the_export_over_http_holds_the_callers_organization_only(client, heads):
    a, b = heads
    _room(client, a, "A-ONLY")
    room_b = _room(client, b, "B-ONLY")

    res = client.get("/api/v1/admin/export", headers=b)
    assert res.status_code == 200
    with zipfile.ZipFile(io.BytesIO(res.content)) as archive:
        organizations = archive.read("organizations.jsonl").decode().splitlines()
        resources = archive.read("resources.jsonl").decode().splitlines()
        users = archive.read("users.jsonl").decode().splitlines()
        audit = [json.loads(line) for line in archive.read("audit_records.jsonl").splitlines()]
    assert len(organizations) == 1 and f'"id":"{SECOND}"' in organizations[0].replace(" ", "")
    assert len(resources) == 1 and f'"id":{room_b}' in resources[0].replace(" ", "")
    assert len(users) == 1 and '"id":"ADM-B"' in users[0].replace(" ", "")
    # B's own requests (its room among them) are there, and nothing of A's.
    assert audit and {row["organization_id"] for row in audit} == {SECOND}


@pytest.fixture()
def change_feed_on(monkeypatch):
    monkeypatch.setenv("CHANGE_FEED_ENABLED", "true")
    get_settings.cache_clear()
    yield
    get_settings.cache_clear()


def test_the_change_feed_and_webhooks_carry_one_organization(client, heads, engine, change_feed_on):
    a, b = heads
    with Session(engine) as db:
        for organization in (DEFAULT_ORGANIZATION_ID, SECOND):
            db.add(
                WebhookSubscription(
                    url=f"https://{organization}.example/hook",
                    event_types="resource.created",
                    secret="s" * 40,
                    organization_id=organization,
                )
            )
        db.commit()
    room_a = _room(client, a)
    room_b = _room(client, b)

    feed = client.get("/api/v1/changes/", headers=b).json()["changes"]
    assert [(c["entity_kind"], c["entity_id"]) for c in feed] == [("resource", room_b)]

    with Session(engine) as db:
        assert fan_out(db) == 2
        db.commit()
        sent = {
            (d.organization_id, d.entity_id)
            for d in db.scalars(select(WebhookDelivery).order_by(WebhookDelivery.id))
        }
    assert sent == {(DEFAULT_ORGANIZATION_ID, room_a), (SECOND, room_b)}


def test_a_session_filters_whatever_it_queries(engine):
    """The listener underneath every route: no organization, no rows of another."""
    with Session(engine) as db:
        db.add(Resource(code="101", label="A", organization_id=DEFAULT_ORGANIZATION_ID))
        db.add(Resource(code="101", label="B", organization_id=SECOND))
        db.commit()
    with Session(engine) as db:
        use_organization(db, SECOND)
        assert [r.label for r in db.scalars(select(Resource))] == ["B"]
        db.add(ChangeMarker(entity_kind="resource", entity_id=1, change_kind="created"))
        db.flush()
        assert db.scalars(select(ChangeMarker.organization_id)).all() == [SECOND]
        everyone = select(Resource).execution_options(all_organizations=True)
        assert len(db.scalars(everyone).all()) == 2


def test_a_rule_based_slot_stamps_its_days_with_its_own_organization(engine):
    """The nightly jobs have no caller, so each day takes its slot's organization."""
    monday = datetime.date(2026, 9, 7)
    with Session(engine) as db:
        for organization in (DEFAULT_ORGANIZATION_ID, SECOND):
            cycle = PlanningCycle(
                cycle_label="Odd 2026",
                date_bounds_start=datetime.date(2026, 8, 1),
                date_bounds_end=datetime.date(2026, 12, 20),
                operational_status=True,
                organization_id=organization,
            )
            db.add(cycle)
            db.flush()
            offering = Activity(
                activity_code="CS101",
                activity_title="Intro",
                unit_code="CSE",
                cycle_id=cycle.id,
                organization_id=organization,
            )
            db.add(offering)
            room = Resource(code="LH-101", label="LH-101", organization_id=organization)
            db.add(room)
            db.flush()
            db.add(
                StructuralMasterSlot(
                    **weekly(1),
                    time_window_start=datetime.time(9, 0),
                    time_window_end=datetime.time(10, 0),
                    activity_id=offering.id,
                    resource_id=room.id,
                    organization_id=organization,
                )
            )
        db.commit()
    with Session(engine) as db:
        assert generate_daily_ledger_entries(monday, db) == 2
        assert materialize_horizon(db) > 0
        db.commit()
    for organization in (DEFAULT_ORGANIZATION_ID, SECOND):
        with Session(engine) as db:
            use_organization(db, organization)
            days = db.scalars(select(DailyLedger)).all()
            assert days
            assert {day.organization_id for day in days} == {organization}
            assert monday in {day.target_date for day in days}


def test_creating_an_organization_refuses_anything_already_taken(engine):
    with Session(engine) as db:
        attempts = [
            (SECOND, "ADM-C", "c@test.internal", "already an organization"),
            ("third", "ADM-A", "c@test.internal", "User ID 'ADM-A'"),
            ("third", "ADM-C", "ADMIN-A@test.internal", "already in use"),
            ("", "ADM-C", "c@test.internal", "1 to 50 characters"),
            ("x" * 51, "ADM-C", "c@test.internal", "1 to 50 characters"),
        ]
        for organization, admin, email, said in attempts:
            with pytest.raises(ValueError, match=said):
                create_organization(db, organization, "Third", admin, email, PASSWORD)
        with pytest.raises(ValueError, match="at least"):
            create_organization(db, "third", "Third", "ADM-C", "c@test.internal", "short")
        assert db.get(Organization, "third") is None


@pytest.fixture()
def environment_restored():
    """The CLI runs configure_environment, which writes os.environ."""
    saved = dict(os.environ)
    yield
    os.environ.clear()
    os.environ.update(saved)
    get_settings.cache_clear()


def test_the_command_line_creates_an_organization(
    tmp_path, monkeypatch, capsys, environment_restored
):
    data_dir = tmp_path / "data"
    monkeypatch.delenv("DATABASE_URL", raising=False)
    monkeypatch.delenv("JWT_SECRET_SIGNING_KEY", raising=False)
    monkeypatch.setattr("sys.stdin", io.StringIO(PASSWORD + "\n"))
    argv = [
        "organization",
        "create",
        "--data-dir",
        str(data_dir),
        "--id",
        "third",
        "--name",
        "Third",
        "--admin-id",
        "ADM-C",
        "--admin-email",
        "admin-c@test.internal",
    ]
    assert standalone.main(argv) == 0
    out = capsys.readouterr().out
    assert "Created organization third" in out
    assert PASSWORD not in out

    monkeypatch.setattr("sys.stdin", io.StringIO(PASSWORD + "\n"))
    assert standalone.main(argv) == 1
    assert "already an organization" in capsys.readouterr().err

    made = sqlite_engine(standalone.database_url(data_dir))
    try:
        with Session(made) as db:
            admin = db.get(User, "ADM-C")
            assert admin.organization_id == "third"
            assert admin.role_type == InstitutionalRole.ORG_ADMIN
            assert admin.initial_login_state is True
            assert db.get(Organization, DEFAULT_ORGANIZATION_ID) is not None
    finally:
        made.dispose()
