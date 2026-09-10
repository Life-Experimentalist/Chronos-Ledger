# Copyright 2026 Chronos Ledger Contributors
# Licensed under the Apache License, Version 2.0
"""What an instance calls the engine's six nouns.

L-04: a profile was the only way to change a label, so a deployment whose words
did not match one of three presets had no way to fix it short of forking. The
presets are gone rather than fixed. They were never going to match, and an
engine that ships the word "Course" has taken a position it has no business
taking.
"""

from app.api.v1.endpoints import org_config
from app.core.config import Settings, label_overrides
from app.core.vocabulary import DEFAULT_LABELS, LABEL_KEYS, labels_for


def test_nothing_set_gives_the_engines_own_words():
    assert labels_for() == DEFAULT_LABELS
    assert set(DEFAULT_LABELS) == set(LABEL_KEYS)


def test_the_defaults_carry_no_domain():
    """The failure this replaces: campus put Student and Course in the engine.

    A word here is one an integrator has to work around, so the defaults name
    the engine's own nouns and nobody else's.
    """
    assert set(DEFAULT_LABELS.values()) == {
        "Staff",
        "Member",
        "Activity",
        "Unit",
        "Lead",
        "Cycle",
    }


def test_one_override_leaves_the_other_five_alone():
    labels = labels_for({"activity": "Module"})
    assert labels["activity"] == "Module"
    assert labels["member"] == "Member"
    assert labels["unit"] == "Unit"


def test_all_six_can_be_set():
    words = {
        "staff": "Clinician",
        "member": "Resident",
        "activity": "Rotation",
        "unit": "Service",
        "lead": "Attending",
        "cycle": "Roster Period",
    }
    assert labels_for(words) == words


def test_an_empty_override_is_not_a_blank_heading():
    """LABEL_UNIT= means "leave it", not "call it nothing". Both compose files
    would pass an empty string for every one of these."""
    assert labels_for({"unit": ""})["unit"] == "Unit"
    assert labels_for({"unit": "   "})["unit"] == "Unit"


def test_a_key_outside_the_six_is_ignored():
    assert set(labels_for({"room": "Theatre"})) == set(LABEL_KEYS)


def test_settings_carry_an_override_through():
    settings = Settings(label_staff="Clinician")
    labels = labels_for(label_overrides(settings))
    assert labels["staff"] == "Clinician"
    assert labels["lead"] == "Lead"


def test_the_config_endpoint_publishes_an_override(client, monkeypatch):
    """The whole pipe: an environment variable reaching the login page, which
    reads this before anybody has signed in."""
    monkeypatch.setattr(
        org_config,
        "get_settings",
        lambda: Settings(label_activity="Module", label_member="Student"),
    )

    res = client.get("/api/v1/config")

    assert res.status_code == 200, res.text
    labels = res.json()["labels"]
    assert labels["activity"] == "Module"
    assert labels["member"] == "Student"
    assert labels["cycle"] == "Cycle"
