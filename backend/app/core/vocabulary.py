# Copyright 2026 Chronos Ledger Contributors
# Licensed under the Apache License, Version 2.0

"""Display vocabulary: what the interface calls the engine's six nouns.

The engine's own names are neutral, and none of this touches them. Only the
words on a screen change; the API fields, the columns and the CSV headers stay
as they are whatever an instance calls them.

A profile is a starting value rather than the truth. Domains do not agree with
themselves: two universities disagree on Course against Module, and "Faculty"
is the unit at one and the person at another, so one profile's unit is
another's staff. The hospital set below carries the same problem inside a
single row, calling staff Doctor and member Resident when a resident is a
doctor. None of that is fixable by choosing better words.

So LABEL_STAFF through LABEL_CYCLE are where the truth lives, and the profiles
stay only because a fresh instance needs labels on its first screen, before
anybody has configured anything. generic is itself one of them.

docs/vocabulary.md is the long version, including what labels never change.
"""

from collections.abc import Mapping

# The contract. Six singular nouns, no plurals and no states: an instance that
# wants ON_LEAVE to read differently is asking a question this does not answer.
LABEL_KEYS = ("staff", "member", "activity", "unit", "lead", "cycle")

VOCABULARY_PROFILES: dict[str, dict[str, str]] = {
    "generic": {
        "staff": "Staff",
        "member": "Member",
        "activity": "Activity",
        "unit": "Unit",
        "lead": "Lead",
        "cycle": "Cycle",
    },
    "campus": {
        "staff": "Faculty",
        "member": "Student",
        "activity": "Course",
        "unit": "Department",
        "lead": "Instructor",
        "cycle": "Academic Year",
    },
    "hospital": {
        "staff": "Doctor",
        "member": "Resident",
        "activity": "Rotation",
        "unit": "Department",
        "lead": "Attending",
        "cycle": "Roster Period",
    },
}


def labels_for(profile: str, overrides: Mapping[str, str] | None = None) -> dict[str, str]:
    """The six labels this deployment renders.

    An override that is empty or only spaces is ignored rather than applied, so
    an operator who writes LABEL_UNIT= and stops gets the profile's word back
    instead of a blank heading. Keys outside the six are ignored: they are the
    contract, and a typo should not silently add a seventh.
    """
    labels = dict(VOCABULARY_PROFILES.get(profile, VOCABULARY_PROFILES["generic"]))
    for key in LABEL_KEYS:
        chosen = ((overrides or {}).get(key) or "").strip()
        if chosen:
            labels[key] = chosen
    return labels
