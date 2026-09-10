# Copyright 2026 Chronos Ledger Contributors
# Licensed under the Apache License, Version 2.0

"""Display vocabulary: what the interface calls the engine's six nouns.

The engine's own names are neutral, and none of this touches them. Only the
words on a screen change; the API fields, the columns and the CSV headers stay
as they are whatever an instance calls them.

There are no presets, deliberately. A preset is a guess about words, and a
domain does not agree with itself: two universities disagree on Course against
Module, and "Faculty" is the unit at one and the person at another, so one
preset's unit is another's staff. Worse than being wrong, a preset bakes a
domain word into an engine that should carry no opinion about what a Course is.

So the defaults below are the engine's own nouns, and LABEL_STAFF through
LABEL_CYCLE are the only place a real word appears. Integrators bring theirs.

docs/vocabulary.md is the long version, including what labels never change.
"""

from collections.abc import Mapping

# The contract. Six singular nouns, no plurals and no states: an instance that
# wants ON_LEAVE to read differently is asking a question this does not answer.
LABEL_KEYS = ("staff", "member", "activity", "unit", "lead", "cycle")

# What an instance shows before anybody has configured anything. These are the
# engine's own words rather than any domain's, which is the point: an unset
# label reads as neutral rather than as somebody else's guess.
DEFAULT_LABELS: dict[str, str] = {
    "staff": "Staff",
    "member": "Member",
    "activity": "Activity",
    "unit": "Unit",
    "lead": "Lead",
    "cycle": "Cycle",
}


def labels_for(overrides: Mapping[str, str] | None = None) -> dict[str, str]:
    """The six labels this deployment renders.

    An override that is empty or only spaces is ignored rather than applied, so
    an operator who writes LABEL_UNIT= and stops gets the engine's word back
    instead of a blank heading. Keys outside the six are ignored: they are the
    contract, and a typo should not silently add a seventh.
    """
    labels = dict(DEFAULT_LABELS)
    for key in LABEL_KEYS:
        chosen = ((overrides or {}).get(key) or "").strip()
        if chosen:
            labels[key] = chosen
    return labels
