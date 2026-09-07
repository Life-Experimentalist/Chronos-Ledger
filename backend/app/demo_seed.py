# Copyright 2026 Chronos Ledger Contributors
# Licensed under the Apache License, Version 2.0
"""Seed a small, self-contained demo data set.

Run inside the app container after the stack is up:

    docker compose run --rm chronos-app uv run --no-sync python -m app.demo_seed

Creates two staff, one member, one active planning cycle, three activities
with slots on every day of the week, and today's ledger rows, so every
portal has something to show on a fresh install. Idempotent: a second run
is a no-op. The seeded admin account and its first-login password gate are
left untouched. Ledger rows carry no geo targets, so a member can mark
attendance from any machine during a demo.
"""

import datetime

from app.core.database import SessionLocal
from app.core.security import hash_password
from app.cron.ledger_generator import generate_daily_ledger_entries
from app.models.db import (
    Activity,
    ActivityEnrollment,
    InstitutionalRole,
    PlanningCycle,
    StructuralMasterSlot,
    User,
)

DEMO_UNIT = "CORE"

DEMO_USERS = [
    ("DEMO-STF01", "Alex Rivera", "staff@demo.internal", "StaffDemo2026!", InstitutionalRole.STAFF),
    ("DEMO-STF02", "Sam Okafor", "staff2@demo.internal", "StaffDemo2026!", InstitutionalRole.STAFF),
    (
        "DEMO-MEM01",
        "Jordan Lee",
        "member@demo.internal",
        "MemberDemo2026!",
        InstitutionalRole.MEMBER,
    ),
]

# (code, title, lead_id, [(start, end), ...]) - slots repeat every day of the
# week so the demo has ledger rows no matter which day it is run on.
DEMO_ACTIVITIES = [
    ("DEMO-101", "Morning Briefing", "DEMO-STF01", [("09:00", "09:45")]),
    ("DEMO-202", "Operations Review", "DEMO-STF02", [("11:00", "12:00")]),
    ("DEMO-303", "Training Session", "DEMO-STF01", [("15:00", "16:30")]),
]


def seed() -> None:
    db = SessionLocal()
    try:
        today = datetime.date.today()
        if db.query(User).filter(User.id == "DEMO-STF01").first():
            created = generate_daily_ledger_entries(today, db)
            print(f"Demo data already present; topped up {created} ledger rows for {today}.")
            return

        for uid, name, email, password, role in DEMO_USERS:
            db.add(
                User(
                    id=uid,
                    full_name=name,
                    email_address=email,
                    credential_secure_hash=hash_password(password),
                    role_type=role,
                    unit_code=DEMO_UNIT,
                    initial_login_state=False,
                )
            )

        cycle = PlanningCycle(
            cycle_label="Demo Cycle",
            date_bounds_start=today - datetime.timedelta(days=30),
            date_bounds_end=today + datetime.timedelta(days=60),
            operational_status=True,
        )
        db.add(cycle)
        db.flush()

        for code, title, lead_id, windows in DEMO_ACTIVITIES:
            activity = Activity(
                activity_code=code,
                activity_title=title,
                unit_code=DEMO_UNIT,
                cycle_id=cycle.id,
            )
            db.add(activity)
            db.flush()
            db.add(ActivityEnrollment(activity_id=activity.id, member_id="DEMO-MEM01"))
            for start, end in windows:
                for day_index in range(1, 8):
                    db.add(
                        StructuralMasterSlot(
                            day_of_week_index=day_index,
                            time_window_start=datetime.time.fromisoformat(start),
                            time_window_end=datetime.time.fromisoformat(end),
                            activity_id=activity.id,
                            primary_lead_id=lead_id,
                            target_room_identifier="ROOM-1",
                        )
                    )

        db.commit()
        created = generate_daily_ledger_entries(today, db)
        print(f"Seeded {len(DEMO_USERS)} demo users, {len(DEMO_ACTIVITIES)} activities,")
        print(f"and {created} ledger rows for {today}.")
    finally:
        db.close()


if __name__ == "__main__":
    seed()
