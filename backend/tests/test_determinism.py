# Copyright 2026 Chronos Ledger Contributors
# Licensed under the Apache License, Version 2.0
"""The same script under the same host clock and seed writes the same rows.

docs/clock.md promises a host that it can replay a day and get the same
database, byte for byte, ids and timestamps included. This drives one
scripted day through the API twice, each time into a freshly built
database, and compares every table.
"""

import datetime
from contextlib import contextmanager

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import select

from app.core import clock, ids
from app.core.config import get_settings
from app.core.database import Base, get_db, get_session_opener
from app.core.security import hash_api_key
from app.cron import scheduled
from app.main import app
from app.models.db import (
    Activity,
    ApiKey,
    AuditRecord,
    InstitutionalRole,
    PlanningCycle,
    Reservation,
    StructuralMasterSlot,
    User,
)
from tests.conftest import _HASHES, TestingSessionLocal, engine

START = "2026-09-07T08:00:00+05:30"
# Past 23:00 and midnight in Kolkata, and past the two 03:xx purges.
NEXT_MORNING = datetime.datetime(2026, 9, 8, 4, 0, tzinfo=datetime.UTC) - datetime.timedelta(
    hours=5, minutes=30
)
ADMIN_KEY = "ck_test_host_admin_credential_not_a_real_secret"


@pytest.fixture()
def host_clock(monkeypatch):
    monkeypatch.setenv("CLOCK_MODE", "host")
    monkeypatch.setenv("CLOCK_START", START)
    monkeypatch.setenv("ID_SEED", "42")
    monkeypatch.setenv("ORG_TIMEZONE", "Asia/Kolkata")
    get_settings.cache_clear()
    yield
    app.dependency_overrides.clear()
    get_settings.cache_clear()
    clock.reset()
    ids.reset()


def _fresh_database():
    Base.metadata.drop_all(bind=engine)
    Base.metadata.create_all(bind=engine)
    db = TestingSessionLocal()
    db.add(
        User(
            id="ADM001",
            full_name="Admin One",
            email_address="admin@test.internal",
            credential_secure_hash=_HASHES["admin"],
            role_type=InstitutionalRole.ORG_ADMIN,
            initial_login_state=False,
            # The default draws a fresh secret, which is right in production
            # and would make the users table differ between runs here.
            calendar_feed_token="fixed-feed-token-for-the-determinism-test",
        )
    )
    db.add(
        ApiKey(
            key_hash=hash_api_key(ADMIN_KEY),
            key_prefix=ADMIN_KEY[:12],
            label="Host program",
            user_id="ADM001",
        )
    )
    # A Tuesday class, so the nightly run at 23:00 on Monday has a row to write.
    cycle = PlanningCycle(
        cycle_label="Odd 2026",
        date_bounds_start=datetime.date(2026, 8, 1),
        date_bounds_end=datetime.date(2026, 12, 20),
        operational_status=True,
    )
    db.add(cycle)
    db.flush()
    offering = Activity(
        activity_code="CS101",
        activity_title="Intro to Computing",
        unit_code="CSE",
        cycle_id=cycle.id,
    )
    db.add(offering)
    db.flush()
    db.add(
        StructuralMasterSlot(
            day_of_week_index=2,
            time_window_start=datetime.time(9, 0),
            time_window_end=datetime.time(10, 0),
            activity_id=offering.id,
            primary_lead_id="ADM001",
            target_room_identifier="LH-101",
        )
    )
    db.commit()
    return db


def _export(db):
    """Every row of every table, as strings, in primary key order."""
    rows = {}
    for table in Base.metadata.sorted_tables:
        statement = select(table).order_by(*table.primary_key.columns)
        rows[table.name] = [
            tuple(str(value) for value in row) for row in db.execute(statement).all()
        ]
    return rows


def _run_the_day(monkeypatch):
    clock.reset()
    ids.reset()
    db = _fresh_database()

    def override_get_db():
        yield db

    @contextmanager
    def override_open_session():
        yield db

    app.dependency_overrides[get_db] = override_get_db
    app.dependency_overrides[get_session_opener] = lambda: override_open_session
    monkeypatch.setattr(scheduled, "SessionLocal", lambda: db)
    headers = {"X-API-Key": ADMIN_KEY}
    client = TestClient(app)
    try:
        res = client.post("/api/v1/resources/", json={"code": "R-101"}, headers=headers)
        assert res.status_code == 201, res.text
        resource_id = res.json()["id"]

        res = client.post(
            f"/api/v1/resources/{resource_id}/reservations",
            json={"date": "2026-09-08", "start": "10:00", "end": "11:00", "purpose": "Hold"},
            headers={**headers, "Idempotency-Key": "hold-0000-0001"},
        )
        assert res.status_code == 201, res.text
        held = res.json()["id"]

        ran = scheduled.advance(NEXT_MORNING)
        assert ran == [
            "nightly_ledger_gen",
            "refresh_token_purge",
            "guest_retention_purge",
            "guest_overstay_notice",
        ]

        res = client.post(
            f"/api/v1/resources/{resource_id}/reservations",
            json={"date": "2026-09-09", "start": "14:00", "end": "15:00", "purpose": "Book"},
            headers={**headers, "Idempotency-Key": "book-0000-0001"},
        )
        assert res.status_code == 201, res.text

        res = client.delete(f"/api/v1/resources/{resource_id}/reservations/{held}", headers=headers)
        assert res.status_code == 200, res.text

        return _export(db)
    finally:
        app.dependency_overrides.clear()
        db.close()


def test_the_same_day_twice_writes_the_same_rows(host_clock, monkeypatch):
    first = _run_the_day(monkeypatch)
    second = _run_the_day(monkeypatch)

    assert first == second
    # The script did what it says: a day was laid down by the nightly run,
    # two holds were taken and one let go, and every request was audited.
    assert len(first["daily_ledger"]) == 1
    assert len(first["reservations"]) == 2
    assert len(first["audit_records"]) == 4


def test_rows_are_stamped_from_the_host_clock(host_clock, monkeypatch):
    _run_the_day(monkeypatch)
    start = datetime.datetime.fromisoformat(START).astimezone(datetime.UTC)

    def utc(value):
        # SQLite hands back what was stored with no zone on it; it was UTC.
        return value.replace(tzinfo=datetime.UTC)

    db = TestingSessionLocal()
    try:
        held, booked = db.query(Reservation).order_by(Reservation.id).all()
        assert utc(held.created_at) == start
        assert utc(held.cancelled_at) == NEXT_MORNING
        assert utc(booked.created_at) == NEXT_MORNING
        # The nightly run stamped nothing of its own, but the audit trail did:
        # two requests before the clock moved, two after.
        stamps = [utc(row.at) for row in db.query(AuditRecord).order_by(AuditRecord.id)]
        assert stamps == [start, start, NEXT_MORNING, NEXT_MORNING]
    finally:
        db.close()
