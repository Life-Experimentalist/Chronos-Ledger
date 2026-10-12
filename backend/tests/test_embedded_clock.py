# Copyright 2026 Chronos Ledger Contributors
# Licensed under the Apache License, Version 2.0
"""The host clock in the embedded flavour: the flags, the routes, the replay."""

import os
from contextlib import contextmanager
from datetime import UTC, datetime

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import select

import app.api.v1.endpoints.clock as clock_endpoints
from app import standalone
from app.core import clock, ids
from app.core.config import get_settings
from app.core.database import Base, get_db, get_session_opener
from app.core.host_identity import SYSTEM_ACTOR_ID, seed_system_account
from app.cron import scheduled
from app.embedded import build_app
from tests.conftest import TestingSessionLocal, engine

SECRET = "h" * 40
HOST = {"Authorization": f"Host {SECRET}"}
START = "2026-09-07T08:00:00+05:30"
# 23:00 in Kolkata, the nightly ledger run, and a mark of the five-minute grid.
NIGHT = "2026-09-07T23:00:00+05:30"
NIGHT_UTC = datetime.fromisoformat(NIGHT).astimezone(UTC)
# Columns that are secrets, drawn fresh for every account the host names.
SECRET_COLUMNS = {"users": {"credential_secure_hash", "calendar_feed_token"}}


def actor(actor_id, role="ORG_ADMIN"):
    return {**HOST, "X-Chronos-Actor": actor_id, "X-Chronos-Actor-Role": role}


@pytest.fixture(autouse=True)
def _clock_restored():
    saved = dict(os.environ)
    yield
    os.environ.clear()
    os.environ.update(saved)
    get_settings.cache_clear()
    clock.reset()
    ids.reset()


@pytest.fixture()
def host_clock(monkeypatch):
    monkeypatch.setenv("CLOCK_MODE", "host")
    monkeypatch.setenv("CLOCK_START", START)
    monkeypatch.setenv("ID_SEED", "42")
    monkeypatch.setenv("ORG_TIMEZONE", "Asia/Kolkata")
    get_settings.cache_clear()
    clock.reset()
    ids.reset()


def _client(db, monkeypatch):
    seed_system_account(db)
    application = build_app(SECRET)

    def override_get_db():
        yield db

    @contextmanager
    def override_open_session():
        yield db

    application.dependency_overrides[get_db] = override_get_db
    application.dependency_overrides[get_session_opener] = lambda: override_open_session
    # The jobs open sessions of their own.
    monkeypatch.setattr(scheduled, "SessionLocal", lambda: db)
    return TestClient(application)


@pytest.fixture()
def embedded(host_clock, db, monkeypatch):
    return _client(db, monkeypatch)


# The flags.


def test_clock_start_puts_the_process_in_host_mode():
    standalone.configure_clock(START, 7)
    assert os.environ["CLOCK_MODE"] == "host"
    assert os.environ["CLOCK_START"] == START
    assert os.environ["ID_SEED"] == "7"


def test_without_clock_start_the_system_clock_is_used_whatever_the_environment_says():
    os.environ["CLOCK_MODE"] = "host"
    os.environ.pop("ID_SEED", None)
    standalone.configure_clock(None, None)
    assert os.environ["CLOCK_MODE"] == "system"
    assert "ID_SEED" not in os.environ


@pytest.mark.parametrize("value", ["2026-09-07T08:00:00", "yesterday", "2026-09-07"])
def test_a_clock_start_without_an_offset_is_refused_before_anything_starts(value, capsys):
    with pytest.raises(ValueError, match="--clock-start"):
        standalone.configure_clock(value, None)
    args = ["embedded", "--clock-start", value]
    assert standalone.main(args) == 2
    assert "--clock-start" in capsys.readouterr().err


def test_the_parser_takes_the_clock_flags():
    args = standalone.build_parser().parse_args(
        ["embedded", "--clock-start", START, "--id-seed", "3"]
    )
    assert (args.clock_start, args.id_seed) == (START, 3)
    args = standalone.build_parser().parse_args(["embedded"])
    assert (args.clock_start, args.id_seed) == (None, None)


# The routes.


def test_anyone_may_read_the_clock(embedded):
    res = embedded.get("/api/v1/clock", headers=actor("H-1", "MEMBER"))
    assert res.status_code == 200, res.text
    assert res.json() == {"mode": "host", "now": "2026-09-07T02:30:00Z"}


def test_the_clock_needs_an_actor(embedded):
    assert embedded.get("/api/v1/clock", headers=HOST).status_code == 401
    assert embedded.get("/api/v1/clock").status_code == 401


def test_advancing_past_eleven_runs_the_nightly_ledger(embedded):
    res = embedded.post("/api/v1/clock/advance", json={"to": NIGHT}, headers=actor(SYSTEM_ACTOR_ID))
    assert res.status_code == 200, res.text
    assert res.json() == {
        "now": "2026-09-07T17:30:00Z",
        "ran": ["nightly_ledger_gen", "guest_overstay_notice"],
    }
    assert clock.now() == NIGHT_UTC
    assert (
        embedded.get("/api/v1/clock", headers=actor("H-1")).json()["now"] == "2026-09-07T17:30:00Z"
    )


def test_advancing_to_the_same_instant_runs_nothing(embedded):
    res = embedded.post("/api/v1/clock/advance", json={"to": START}, headers=actor(SYSTEM_ACTOR_ID))
    assert res.status_code == 200, res.text
    assert res.json() == {"now": "2026-09-07T02:30:00Z", "ran": []}


def test_the_clock_does_not_go_backwards(embedded):
    earlier = {"to": "2026-09-07T07:59:59+05:30"}
    res = embedded.post("/api/v1/clock/advance", json=earlier, headers=actor(SYSTEM_ACTOR_ID))
    assert res.status_code == 422, res.text
    assert "backwards" in res.json()["detail"]
    assert clock.now() == datetime.fromisoformat(START).astimezone(UTC)


def test_a_naive_instant_is_refused(embedded):
    naive = {"to": "2026-09-07T23:00:00"}
    res = embedded.post("/api/v1/clock/advance", json=naive, headers=actor(SYSTEM_ACTOR_ID))
    assert res.status_code == 422, res.text


def test_only_the_host_itself_may_advance(embedded):
    # An administrator the host names is still not the host.
    res = embedded.post(
        "/api/v1/clock/advance", json={"to": NIGHT}, headers=actor("H-1", "ORG_ADMIN")
    )
    assert res.status_code == 403, res.text
    assert SYSTEM_ACTOR_ID in res.json()["detail"]
    assert clock.now() == datetime.fromisoformat(START).astimezone(UTC)


def test_a_process_on_the_system_clock_cannot_be_advanced(db, monkeypatch):
    monkeypatch.delenv("CLOCK_MODE", raising=False)
    get_settings.cache_clear()
    clock.reset()
    embedded = _client(db, monkeypatch)

    assert embedded.get("/api/v1/clock", headers=actor("H-1")).json()["mode"] == "system"
    to = {"to": "2999-01-01T00:00:00+00:00"}
    res = embedded.post("/api/v1/clock/advance", json=to, headers=actor(SYSTEM_ACTOR_ID))
    assert res.status_code == 409, res.text
    assert "--clock-start" in res.json()["detail"]


def test_advances_are_serialized(embedded, monkeypatch):
    held = []

    def advance(instant):
        held.append(clock_endpoints._advancing.locked())
        clock.advance_to(instant)
        return []

    monkeypatch.setattr(scheduled, "advance", advance)
    res = embedded.post("/api/v1/clock/advance", json={"to": NIGHT}, headers=actor(SYSTEM_ACTOR_ID))
    assert res.status_code == 200, res.text
    assert held == [True]
    assert not clock_endpoints._advancing.locked()


# The replay.


def _fresh_database():
    Base.metadata.drop_all(bind=engine)
    Base.metadata.create_all(bind=engine)
    return TestingSessionLocal()


def _export(db):
    """Every row of every table, as strings, in primary key order, secrets left out."""
    rows = {}
    for table in Base.metadata.sorted_tables:
        kept = [c for c in table.columns if c.name not in SECRET_COLUMNS.get(table.name, ())]
        statement = select(*kept).order_by(*table.primary_key.columns)
        rows[table.name] = [
            tuple(str(value) for value in row) for row in db.execute(statement).all()
        ]
    return rows


def _run_the_day(monkeypatch):
    clock.reset()
    ids.reset()
    db = _fresh_database()
    client = _client(db, monkeypatch)
    admin = actor("H-1", "ORG_ADMIN")
    try:
        res = client.post("/api/v1/resources/", json={"code": "R-101"}, headers=admin)
        assert res.status_code == 201, res.text
        resource_id = res.json()["id"]

        res = client.post(
            f"/api/v1/resources/{resource_id}/reservations",
            json={"date": "2026-09-08", "start": "10:00", "end": "11:00", "purpose": "Hold"},
            headers={**admin, "Idempotency-Key": "hold-0000-0001"},
        )
        assert res.status_code == 201, res.text
        held = res.json()["id"]

        res = client.post(
            "/api/v1/clock/advance", json={"to": NIGHT}, headers=actor(SYSTEM_ACTOR_ID)
        )
        assert res.status_code == 200, res.text
        assert res.json()["ran"] == ["nightly_ledger_gen", "guest_overstay_notice"]

        res = client.get("/api/v1/clock", headers=actor("H-2", "MEMBER"))
        assert res.status_code == 200, res.text

        res = client.delete(f"/api/v1/resources/{resource_id}/reservations/{held}", headers=admin)
        assert res.status_code == 200, res.text
        return _export(db)
    finally:
        db.close()


def test_the_same_day_twice_writes_the_same_rows(host_clock, monkeypatch):
    first = _run_the_day(monkeypatch)
    second = _run_the_day(monkeypatch)

    assert first == second
    # Three accounts the host named, one of them the host itself, the hold
    # taken and let go, and every write audited (the read of the clock is not).
    assert sorted(row[0] for row in first["users"]) == ["H-1", "H-2", "system"]
    assert len(first["reservations"]) == 1
    assert len(first["audit_records"]) == 4
