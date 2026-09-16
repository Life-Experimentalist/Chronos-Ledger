# Copyright 2026 Chronos Ledger Contributors
# Licensed under the Apache License, Version 2.0
"""/health/ready fails only when PostgreSQL does; /health touches nothing."""

import pytest
from sqlalchemy import create_engine
from sqlalchemy.pool import StaticPool

import app.main as main


class _Down:
    def connect(self):
        raise ConnectionError("down")

    def ping(self):
        raise ConnectionError("down")


class _Up:
    def ping(self):
        return True


@pytest.fixture()
def working_database(monkeypatch):
    engine = create_engine("sqlite://", poolclass=StaticPool)
    monkeypatch.setattr(main, "engine", engine)


def _redis(monkeypatch, client):
    monkeypatch.setattr(main.redis, "from_url", lambda *_a, **_k: client)


def test_ready_when_both_answer(client, monkeypatch, working_database):
    _redis(monkeypatch, _Up())
    res = client.get("/health/ready")
    assert res.status_code == 200
    assert res.json() == {"status": "ready", "database": "ok", "redis": "ok"}


def test_redis_down_is_reported_and_still_ready(client, monkeypatch, working_database):
    _redis(monkeypatch, _Down())
    res = client.get("/health/ready")
    assert res.status_code == 200
    assert res.json()["redis"] == "unavailable"


def test_postgres_down_is_not_ready(client, monkeypatch):
    monkeypatch.setattr(main, "engine", _Down())
    _redis(monkeypatch, _Up())
    res = client.get("/health/ready")
    assert res.status_code == 503
    assert res.json()["database"] == "unavailable"


def test_liveness_answers_with_postgres_and_redis_down(client, monkeypatch):
    monkeypatch.setattr(main, "engine", _Down())
    _redis(monkeypatch, _Down())
    assert client.get("/health").status_code == 200
