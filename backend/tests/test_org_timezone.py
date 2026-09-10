# Copyright 2026 Chronos Ledger Contributors
# Licensed under the Apache License, Version 2.0
"""Which day the organization is standing in.

The code used to ask the container, and a container runs UTC unless somebody
tells it otherwise. So "today" meant today in UTC, and the size of the damage
was exactly the UTC offset: at UTC+5:30 anybody opening the app between
midnight and 05:30 was shown yesterday's sessions and could not mark the day
they were actually in.

The two zones used here are 25 or 26 hours apart, so their calendar dates
never agree, at any hour of any day. That is what makes these tests decide
something instead of passing by luck at whatever time they happen to run.
"""

import datetime
from zoneinfo import ZoneInfo

import pytest
from pydantic import ValidationError

from app.core.config import Settings, get_settings
from app.core.time import org_now, org_today, org_tomorrow
from app.cron.ledger_generator import generate_daily_ledger_entries
from app.models.db import Activity, PlanningCycle, StructuralMasterSlot
from app.services.resource import get_or_create_room
from tests.conftest import ADMIN_PASSWORD, login

# UTC+14 and UTC-11. Always a different date from each other.
FURTHEST_AHEAD = "Pacific/Kiritimati"
FURTHEST_BEHIND = "Pacific/Niue"


@pytest.fixture
def org_zone(monkeypatch):
    """Run the app somewhere else for the duration of one test.

    get_settings is lru_cached, which is what makes the setting cheap to read
    from a query filter, so the cache has to be dropped on the way in and on
    the way out. Dropping it afterwards matters more: leaving a test's zone
    cached would move every test that ran after it.
    """

    def set_to(name: str):
        monkeypatch.setenv("ORG_TIMEZONE", name)
        get_settings.cache_clear()

    yield set_to
    get_settings.cache_clear()


def _date_in(name: str) -> datetime.date:
    return datetime.datetime.now(ZoneInfo(name)).date()


def test_today_follows_the_configured_zone_and_not_the_server(org_zone):
    org_zone(FURTHEST_AHEAD)
    assert org_today() == _date_in(FURTHEST_AHEAD)

    org_zone(FURTHEST_BEHIND)
    assert org_today() == _date_in(FURTHEST_BEHIND)


def test_the_two_zones_really_do_disagree(org_zone):
    """The premise every other test here rests on. If this ever fails the
    others have stopped proving anything."""
    org_zone(FURTHEST_AHEAD)
    ahead = org_today()
    org_zone(FURTHEST_BEHIND)
    assert ahead != org_today()


def test_now_is_aware_and_reads_as_the_local_wall_clock(org_zone):
    org_zone(FURTHEST_AHEAD)
    now = org_now()
    assert now.utcoffset() is not None
    assert now.hour == datetime.datetime.now(ZoneInfo(FURTHEST_AHEAD)).hour


def test_tomorrow_steps_the_calendar_by_a_day(org_zone):
    org_zone(FURTHEST_BEHIND)
    assert org_tomorrow() - org_today() == datetime.timedelta(days=1)


def test_a_timezone_that_does_not_exist_is_refused_at_startup(monkeypatch):
    """Loudly, and naming the value. Falling back to UTC would put the whole
    schedule an offset out and say nothing about it."""
    monkeypatch.setenv("ORG_TIMEZONE", "Asia/Kolkatta")
    with pytest.raises(ValidationError) as raised:
        Settings()
    assert "Asia/Kolkatta" in str(raised.value)


def test_an_offset_is_not_a_timezone(monkeypatch):
    """An offset cannot know when daylight saving moves, so a schedule
    running across a spring forward would drift for half the year."""
    monkeypatch.setenv("ORG_TIMEZONE", "+05:30")
    with pytest.raises(ValidationError):
        Settings()


def _class_running_every_day(db) -> None:
    """One slot on every weekday, so a ledger can be generated for any date
    without the test having to care which day of the week it lands on."""
    cycle = PlanningCycle(
        cycle_label="Cycle",
        date_bounds_start=org_today() - datetime.timedelta(days=30),
        date_bounds_end=org_today() + datetime.timedelta(days=300),
        operational_status=True,
    )
    db.add(cycle)
    db.flush()
    activity = Activity(
        activity_code="CS101",
        activity_title="Something",
        unit_code="CSE",
        cycle_id=cycle.id,
    )
    db.add(activity)
    db.flush()
    room = get_or_create_room("LH-201", db)
    for weekday in range(1, 8):
        db.add(
            StructuralMasterSlot(
                day_of_week_index=weekday,
                time_window_start=datetime.time(9, 0),
                time_window_end=datetime.time(10, 0),
                activity_id=activity.id,
                primary_lead_id="FAC001",
                resource_id=room.id,
                target_room_identifier=room.code,
            )
        )
    db.commit()


def test_the_dashboard_shows_the_day_the_organization_is_in(client, db, seed_users, org_zone):
    """The defect end to end. Both dates exist in the ledger, and which one
    comes back is decided by ORG_TIMEZONE and nothing else."""
    _class_running_every_day(db)
    ahead = _date_in(FURTHEST_AHEAD)
    behind = _date_in(FURTHEST_BEHIND)
    assert generate_daily_ledger_entries(ahead, db) == 1
    assert generate_daily_ledger_entries(behind, db) == 1
    headers = login(client, "admin@test.internal", ADMIN_PASSWORD)

    org_zone(FURTHEST_AHEAD)
    r = client.get("/api/v1/schedule/ledger/today", headers=headers)
    assert r.status_code == 200, r.text
    assert [e["target_date"] for e in r.json()] == [str(ahead)]

    org_zone(FURTHEST_BEHIND)
    r = client.get("/api/v1/schedule/ledger/today", headers=headers)
    assert [e["target_date"] for e in r.json()] == [str(behind)]


def test_the_default_is_utc_so_a_bare_checkout_still_runs():
    """Nobody has to set this to get a working system. It is only wrong for
    an organization that is not in UTC, which is why it is a setting and not
    a guess at the server's own zone, which is UTC in a container anyway.

    Read off the field rather than by constructing Settings, because Settings
    reads a .env file if one is sitting there and this is a question about
    the default, not about this machine.
    """
    assert Settings.model_fields["org_timezone"].default == "UTC"
