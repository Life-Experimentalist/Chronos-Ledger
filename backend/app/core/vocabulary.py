# Copyright 2026 Chronos Ledger Contributors
# Licensed under the Apache License, Version 2.0

"""Display vocabulary per deployment profile.

The engine's own names are neutral (staff, member, activity, unit); the
org_profile setting only changes what the UI calls them. Three presets,
no per-label overrides.
"""

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
        "member": "Patient",
        "activity": "Rotation",
        "unit": "Department",
        "lead": "Attending",
        "cycle": "Roster Period",
    },
}


def labels_for(profile: str) -> dict[str, str]:
    return VOCABULARY_PROFILES.get(profile, VOCABULARY_PROFILES["generic"])
