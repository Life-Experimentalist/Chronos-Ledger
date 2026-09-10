# Copyright 2026 Chronos Ledger Contributors
# Licensed under the Apache License, Version 2.0

from app.api.v1.endpoints import org_config
from app.core.config import Settings
from app.core.vocabulary import VOCABULARY_PROFILES


def test_config_is_public_and_returns_generic_labels(client):
    res = client.get("/api/v1/config")
    assert res.status_code == 200
    body = res.json()
    assert body["org_profile"] == "generic"
    assert body["labels"] == VOCABULARY_PROFILES["generic"]


def test_each_profile_returns_its_own_labels(client, monkeypatch):
    for profile in ("generic", "campus", "hospital"):
        monkeypatch.setattr(org_config, "get_settings", lambda p=profile: Settings(org_profile=p))
        res = client.get("/api/v1/config")
        assert res.status_code == 200
        body = res.json()
        assert body["org_profile"] == profile
        assert body["labels"] == VOCABULARY_PROFILES[profile]


def test_the_password_floor_is_published(client):
    """The wizard refuses a short password in the browser, so it needs the number."""
    res = client.get("/api/v1/config")
    assert res.status_code == 200
    assert res.json()["password_min_length"] == Settings().password_min_length


def test_the_published_floor_follows_the_setting(client, monkeypatch):
    monkeypatch.setattr(org_config, "get_settings", lambda: Settings(password_min_length=20))
    res = client.get("/api/v1/config")
    assert res.json()["password_min_length"] == 20


def test_profiles_share_the_same_label_keys():
    keys = set(VOCABULARY_PROFILES["generic"])
    for labels in VOCABULARY_PROFILES.values():
        assert set(labels) == keys
