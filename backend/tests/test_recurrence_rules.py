# Copyright 2026 Chronos Ledger Contributors
# Licensed under the Apache License, Version 2.0
"""A slot runs on the dates its RFC 5545 rule gives, at its own wall clock time.

The two things this release has to keep: a weekly class stays at 09:00 on
both sides of a daylight saving change, and a slot made the old way (one
weekday) runs on exactly the days it ran on before.
"""

import datetime

import pytest

from app.api.v1.endpoints.calendar_sync import _utc_stamp
from app.core import recurrence
from app.core.config import get_settings
from app.core.time import org_today
from app.cron.ledger_generator import generate_daily_ledger_entries
from app.models.db import Activity, DailyLedger, PlanningCycle, StructuralMasterSlot
from app.services.resource import get_or_create_room
from tests.conftest import ADMIN_PASSWORD, login
from tests.test_ingestion import HEADER, _make_cycle, _upload

DAY = datetime.timedelta(days=1)
LONDON = "Europe/London"
# British Summer Time starts at 01:00 UTC on this Sunday.
CLOCKS_GO_FORWARD = datetime.date(2026, 3, 29)


@pytest.fixture
def org_zone(monkeypatch):
    def set_to(name: str):
        monkeypatch.setenv("ORG_TIMEZONE", name)
        get_settings.cache_clear()

    yield set_to
    get_settings.cache_clear()


def _offering(db, start, end):
    cycle = PlanningCycle(
        cycle_label="Rules",
        date_bounds_start=start,
        date_bounds_end=end,
        operational_status=True,
    )
    db.add(cycle)
    db.flush()
    offering = Activity(
        activity_code="RR101", activity_title="Rules", unit_code="CSE", cycle_id=cycle.id
    )
    db.add(offering)
    db.commit()
    return cycle, offering


def _slot(db, offering, rule, dtstart, start=datetime.time(9, 0), end=datetime.time(10, 0)):
    slot = StructuralMasterSlot(
        rrule=rule,
        dtstart=dtstart,
        time_window_start=start,
        time_window_end=end,
        activity_id=offering.id,
        resource_id=get_or_create_room("LH-101", db).id,
    )
    db.add(slot)
    db.commit()
    return slot


def _generate(db, first, last):
    day = first
    while day <= last:
        generate_daily_ledger_entries(day, db)
        day += DAY


def _rows(db):
    return sorted(
        (row.target_date, row.time_window_start, row.time_window_end)
        for row in db.query(DailyLedger).all()
    )


# -- Daylight saving ----------------------------------------------------------


def test_a_weekly_slot_keeps_its_local_time_across_a_dst_change(db, seed_users, org_zone):
    org_zone(LONDON)
    _, offering = _offering(db, datetime.date(2026, 3, 1), datetime.date(2026, 4, 30))
    _slot(db, offering, "FREQ=WEEKLY;BYDAY=MO", datetime.date(2026, 3, 2))

    _generate(db, datetime.date(2026, 3, 16), datetime.date(2026, 4, 12))

    nine, ten = datetime.time(9, 0), datetime.time(10, 0)
    assert _rows(db) == [
        (datetime.date(2026, 3, 16), nine, ten),
        (datetime.date(2026, 3, 23), nine, ten),
        (datetime.date(2026, 3, 30), nine, ten),
        (datetime.date(2026, 4, 6), nine, ten),
    ]
    # And 09:00 in London is a different instant either side of the change,
    # which is what a calendar client is handed.
    assert _utc_stamp(datetime.date(2026, 3, 23), nine) == "20260323T090000Z"
    assert _utc_stamp(datetime.date(2026, 3, 30), nine) == "20260330T080000Z"


def test_a_daily_slot_runs_on_the_day_the_clocks_change_too(db, seed_users, org_zone):
    org_zone(LONDON)
    _, offering = _offering(db, datetime.date(2026, 3, 1), datetime.date(2026, 4, 30))
    _slot(db, offering, "FREQ=DAILY", datetime.date(2026, 3, 1))

    _generate(db, CLOCKS_GO_FORWARD - DAY, CLOCKS_GO_FORWARD + DAY)

    assert [row[:2] for row in _rows(db)] == [
        (CLOCKS_GO_FORWARD - DAY, datetime.time(9, 0)),
        (CLOCKS_GO_FORWARD, datetime.time(9, 0)),
        (CLOCKS_GO_FORWARD + DAY, datetime.time(9, 0)),
    ]


# -- The old way --------------------------------------------------------------


def _old_walk(weekday, first, last):
    """What the generator did before rules: every date on that weekday."""
    return [
        first + DAY * n
        for n in range((last - first).days + 1)
        if (first + DAY * n).isoweekday() == weekday
    ]


@pytest.mark.parametrize("weekday", range(1, 8))
def test_a_weekday_rule_gives_the_dates_the_weekday_gave(weekday):
    first, last = datetime.date(2026, 1, 1), datetime.date(2026, 12, 31)
    made = recurrence.weekly(weekday, first)
    assert recurrence.occurrences(made["rrule"], made["dtstart"], first, last) == _old_walk(
        weekday, first, last
    )


def test_an_old_way_slot_is_generated_on_the_same_days(db, seed_users):
    first, last = datetime.date(2026, 2, 3), datetime.date(2026, 4, 14)
    _, offering = _offering(db, first, last)
    for weekday in (1, 3, 7):
        made = recurrence.weekly(weekday, first)
        _slot(db, offering, made["rrule"], made["dtstart"])

    _generate(db, first - 7 * DAY, last + 7 * DAY)

    expected = sorted(day for weekday in (1, 3, 7) for day in _old_walk(weekday, first, last))
    assert [row[0] for row in _rows(db)] == expected


def test_a_csv_weekday_is_stored_as_a_weekly_rule(client, db, seed_users):
    cycle = _make_cycle(db)
    headers = login(client, "admin@test.internal", ADMIN_PASSWORD)
    csv_text = (
        HEADER + "\nSTU951,Ada Rule,ada.rule@test.internal,RR201,Rules,CSE,3,"
        "09:00,10:00,FAC001,LH-201\n"
    )

    r = _upload(client, headers, cycle.id, csv_text)
    assert r.status_code == 200, r.text

    slot = db.query(StructuralMasterSlot).one()
    assert slot.rrule == "FREQ=WEEKLY;BYDAY=WE"
    assert slot.dtstart.isoweekday() == 3
    assert cycle.date_bounds_start <= slot.dtstart < cycle.date_bounds_start + 7 * DAY


# -- Rules a weekday could not say --------------------------------------------


def test_every_other_week_skips_the_weeks_between(db, seed_users):
    _, offering = _offering(db, datetime.date(2026, 1, 1), datetime.date(2026, 3, 31))
    _slot(db, offering, "FREQ=WEEKLY;INTERVAL=2;BYDAY=TU", datetime.date(2026, 1, 6))

    _generate(db, datetime.date(2026, 1, 1), datetime.date(2026, 2, 10))

    assert [row[0] for row in _rows(db)] == [
        datetime.date(2026, 1, 6),
        datetime.date(2026, 1, 20),
        datetime.date(2026, 2, 3),
    ]


def test_nothing_is_generated_before_dtstart_or_after_until(db, seed_users):
    _, offering = _offering(db, datetime.date(2026, 1, 1), datetime.date(2026, 3, 31))
    _slot(
        db,
        offering,
        "FREQ=WEEKLY;BYDAY=FR;UNTIL=20260130",
        datetime.date(2026, 1, 16),
    )

    _generate(db, datetime.date(2026, 1, 1), datetime.date(2026, 2, 28))

    assert [row[0] for row in _rows(db)] == [
        datetime.date(2026, 1, 16),
        datetime.date(2026, 1, 23),
        datetime.date(2026, 1, 30),
    ]


# -- The API ------------------------------------------------------------------


def _api_world(client, db):
    today = org_today()
    cycle, offering = _offering(db, today - 10 * DAY, today + 90 * DAY)
    return cycle, offering, login(client, "admin@test.internal", ADMIN_PASSWORD)


def _post(client, headers, offering, **fields):
    body = {
        "time_window_start": "09:00:00",
        "time_window_end": "10:00:00",
        "activity_id": offering.id,
        "target_room_identifier": "LH-301",
        **fields,
    }
    return client.post("/api/v1/schedule/slots", headers=headers, json=body)


def _listed(client, headers, cycle):
    r = client.get(f"/api/v1/schedule/slots?cycle_id={cycle.id}", headers=headers)
    assert r.status_code == 200, r.text
    return r.json()


def test_a_rule_without_dtstart_starts_on_its_first_date_in_the_cycle(client, db, seed_users):
    cycle, offering, headers = _api_world(client, db)

    r = _post(client, headers, offering, rrule="rrule:freq=weekly;byday=mo")
    assert r.status_code == 200, r.text

    (slot,) = _listed(client, headers, cycle)
    first_monday = recurrence.first_occurrence("FREQ=WEEKLY;BYDAY=MO", cycle.date_bounds_start)
    assert slot["rrule"] == "FREQ=WEEKLY;BYDAY=MO"
    assert slot["dtstart"] == first_monday.isoformat()
    # The deprecated weekday field is gone; rrule and dtstart carry it.
    assert "day_of_week_index" not in slot


def test_a_dtstart_off_the_rule_moves_forward_to_the_rule(client, db, seed_users):
    cycle, offering, headers = _api_world(client, db)
    asked = cycle.date_bounds_start + 20 * DAY
    while asked.isoweekday() != 4:
        asked += DAY

    r = _post(client, headers, offering, rrule="FREQ=WEEKLY;BYDAY=MO", dtstart=str(asked))
    assert r.status_code == 200, r.text

    (slot,) = _listed(client, headers, cycle)
    assert slot["dtstart"] == (asked + 4 * DAY).isoformat()


def test_a_rule_with_no_date_left_is_refused(client, db, seed_users):
    _, offering, headers = _api_world(client, db)

    r = _post(client, headers, offering, rrule="FREQ=WEEKLY;BYDAY=MO;UNTIL=20000101")

    assert r.status_code == 422, r.text
    assert r.json()["code"] == "INVALID_VALUE"
    assert db.query(StructuralMasterSlot).count() == 0


def test_a_new_rule_without_dtstart_restarts_from_the_cycle_start(client, db, seed_users):
    cycle, offering, headers = _api_world(client, db)
    r = _post(
        client,
        headers,
        offering,
        rrule="FREQ=WEEKLY;BYDAY=MO",
        dtstart=str(cycle.date_bounds_start + 30 * DAY),
    )
    assert r.status_code == 200, r.text
    slot_id = r.json()["id"]

    r = client.patch(
        f"/api/v1/schedule/slots/{slot_id}", headers=headers, json={"rrule": "FREQ=DAILY"}
    )
    assert r.status_code == 200, r.text

    (slot,) = _listed(client, headers, cycle)
    assert slot["rrule"] == "FREQ=DAILY"
    assert slot["dtstart"] == cycle.date_bounds_start.isoformat()


# -- The rule itself ----------------------------------------------------------


@pytest.mark.parametrize(
    ("given", "stored"),
    [
        ("FREQ=WEEKLY;BYDAY=MO", "FREQ=WEEKLY;BYDAY=MO"),
        (" rrule:freq=weekly;byday=mo,we ", "FREQ=WEEKLY;BYDAY=MO,WE"),
        ("FREQ=MONTHLY;BYDAY=1MO", "FREQ=MONTHLY;BYDAY=1MO"),
        ("FREQ=WEEKLY;BYDAY=TH;UNTIL=20261218", "FREQ=WEEKLY;BYDAY=TH;UNTIL=20261218"),
    ],
)
def test_a_rule_is_stored_in_one_spelling(given, stored):
    assert recurrence.normalize(given) == stored


@pytest.mark.parametrize(
    "bad",
    [
        "",
        "   ",
        "FREQ=WEEKLY;BYDAY",
        "FREQ=SECONDLY",
        "FREQ=WEEKLY;BYMINUTE=30",
        "FREQ=WEEKLY;UNTIL=20261218T000000Z",
        "FREQ=WEEKLY;BYDAY=MO\nEXDATE:20260105",
        "FREQ=WEEKLY;" + "BYDAY=MO;" * 40,
        "FREQ=WEEKLY;BYDAY=QQ",
    ],
)
def test_a_rule_a_slot_cannot_have_is_refused(bad):
    with pytest.raises(ValueError):
        recurrence.normalize(bad)
