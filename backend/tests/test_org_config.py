# Copyright 2026 Chronos Ledger Contributors
# Licensed under the Apache License, Version 2.0

from app.api.v1.endpoints import org_config
from app.core.config import Settings
from app.core.vocabulary import DEFAULT_LABELS


def test_config_is_public_and_returns_the_engines_own_words(client):
    res = client.get("/api/v1/config")
    assert res.status_code == 200
    assert res.json()["labels"] == DEFAULT_LABELS


def test_the_response_names_no_domain(client):
    """A client reading this before anybody has signed in should not be handed
    somebody else's guess about what the deployment is."""
    res = client.get("/api/v1/config")
    assert "org_profile" not in res.json()


def test_overrides_reach_the_response(client, monkeypatch):
    monkeypatch.setattr(
        org_config,
        "get_settings",
        lambda: Settings(label_staff="Faculty", label_member="Student"),
    )
    labels = client.get("/api/v1/config").json()["labels"]
    assert labels["staff"] == "Faculty"
    assert labels["member"] == "Student"
    assert labels["activity"] == "Activity"


def test_the_password_floor_is_published(client):
    """The wizard refuses a short password in the browser, so it needs the number."""
    res = client.get("/api/v1/config")
    assert res.status_code == 200
    assert res.json()["password_min_length"] == Settings().password_min_length


def test_the_published_floor_follows_the_setting(client, monkeypatch):
    monkeypatch.setattr(org_config, "get_settings", lambda: Settings(password_min_length=20))
    res = client.get("/api/v1/config")
    assert res.json()["password_min_length"] == 20
