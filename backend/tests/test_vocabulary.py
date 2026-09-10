# Copyright 2026 Chronos Ledger Contributors
# Licensed under the Apache License, Version 2.0
"""What an instance calls the engine's six nouns.

L-04: a profile was the only way to change a label, so a deployment whose words
did not match one of three presets had no way to fix it short of forking. The
presets were never going to match: a domain does not agree with itself.
"""

from app.api.v1.endpoints import org_config
from app.core.config import Settings, label_overrides
from app.core.vocabulary import LABEL_KEYS, labels_for


def test_a_profile_supplies_all_six():
    labels = labels_for("campus")
    assert set(labels) == set(LABEL_KEYS)
    assert labels["member"] == "Student"


def test_an_unknown_profile_falls_back_to_generic():
    assert labels_for("orbital_station") == labels_for("generic")


def test_the_hospital_member_is_a_resident():
    """It said Patient. A patient has no attendance to mark; the person whose
    attendance a rotation records is the one working it."""
    assert labels_for("hospital")["member"] == "Resident"


def test_one_override_leaves_the_other_five_alone():
    labels = labels_for("campus", {"activity": "Module"})
    assert labels["activity"] == "Module"
    assert labels["member"] == "Student"
    assert labels["unit"] == "Department"


def test_an_empty_override_is_not_a_blank_heading():
    """LABEL_UNIT= means "leave it", not "call it nothing". Both compose files
    would pass an empty string for every one of these."""
    assert labels_for("campus", {"unit": ""})["unit"] == "Department"
    assert labels_for("campus", {"unit": "   "})["unit"] == "Department"


def test_a_key_outside_the_six_is_ignored():
    assert set(labels_for("generic", {"room": "Theatre"})) == set(LABEL_KEYS)


def test_every_profile_defines_every_key():
    """A profile missing one would render a KeyError in the interface rather
    than a word."""
    from app.core.vocabulary import VOCABULARY_PROFILES

    for name, labels in VOCABULARY_PROFILES.items():
        assert set(labels) == set(LABEL_KEYS), name


def test_settings_carry_an_override_through():
    settings = Settings(org_profile="hospital", label_staff="Clinician")
    labels = labels_for(settings.org_profile, label_overrides(settings))
    assert labels["staff"] == "Clinician"
    assert labels["lead"] == "Attending"


def test_the_config_endpoint_publishes_an_override(client, monkeypatch):
    """The whole pipe: an environment variable reaching the login page, which
    reads this before anybody has signed in."""
    monkeypatch.setattr(
        org_config,
        "get_settings",
        lambda: Settings(org_profile="campus", label_activity="Module"),
    )

    res = client.get("/api/v1/config")

    assert res.status_code == 200, res.text
    body = res.json()
    assert body["labels"]["activity"] == "Module"
    assert body["labels"]["member"] == "Student"
    assert body["org_profile"] == "campus"
