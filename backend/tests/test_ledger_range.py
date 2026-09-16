# Copyright 2026 Chronos Ledger Contributors
# Licensed under the Apache License, Version 2.0
"""GET /schedule/ledger: the ledger between two dates, for integrations.

Today's ledger was the only read path, so a system showing a week had to be
told about each day as it came. The range reads any span, in date and start
time order, with the same rows and the same role filter as today's.
"""

import datetime

import pytest

from app.core.time import org_today
from app.models.db import (
    Activity,
    ActivityEnrollment,
    DailyLedger,
    PlanningCycle,
    Resource,
)
from tests.conftest import ADMIN_PASSWORD, MEMBER_PASSWORD, STAFF_PASSWORD, login

PATH = "/api/v1/schedule/ledger"


@pytest.fixture()
def week(db, seed_users):
    """Two activities over three days, inserted out of date order."""
    today = org_today()
    cycle = PlanningCycle(
        cycle_label="Cycle",
        date_bounds_start=today - datetime.timedelta(days=30),
        date_bounds_end=today + datetime.timedelta(days=30),
        operational_status=True,
    )
    db.add(cycle)
    room = Resource(code="R101", label="Room 101")
    db.add(room)
    db.flush()
    enrolled = Activity(
        activity_code="ACT1", activity_title="One", unit_code="CSE", cycle_id=cycle.id
    )
    other = Activity(activity_code="ACT2", activity_title="Two", unit_code="CSE", cycle_id=cycle.id)
    db.add_all([enrolled, other])
    db.flush()
    for offset in (2, 0, 1):
        day = today + datetime.timedelta(days=offset)
        db.add(
            DailyLedger(
                target_date=day,
                activity_id=other.id,
                time_window_start=datetime.time(11),
                time_window_end=datetime.time(12),
                active_lead_id="FAC001",
            )
        )
        db.add(
            DailyLedger(
                target_date=day,
                activity_id=enrolled.id,
                resource_id=room.id,
                time_window_start=datetime.time(9),
                time_window_end=datetime.time(10),
                active_lead_id="ADM001",
            )
        )
    db.add(ActivityEnrollment(activity_id=enrolled.id, member_id="STU001"))
    db.commit()
    return {"today": today, "room": room.id}


def _span(week, first, last):
    today = week["today"]
    return {
        "from": str(today + datetime.timedelta(days=first)),
        "to": str(today + datetime.timedelta(days=last)),
    }


def test_rows_come_in_date_then_start_time_order(client, week):
    headers = login(client, "admin@test.internal", ADMIN_PASSWORD)
    res = client.get(PATH, headers=headers, params=_span(week, 0, 2))
    assert res.status_code == 200
    rows = res.json()
    assert res.headers["X-Total-Count"] == "6"
    order = [(r["target_date"], r["time_window_start"]) for r in rows]
    assert order == sorted(order)


def test_both_ends_are_included_and_nothing_outside(client, week):
    headers = login(client, "admin@test.internal", ADMIN_PASSWORD)
    rows = client.get(PATH, headers=headers, params=_span(week, 1, 1)).json()
    tomorrow = str(week["today"] + datetime.timedelta(days=1))
    assert len(rows) == 2
    assert {r["target_date"] for r in rows} == {tomorrow}


def test_a_row_is_the_same_as_todays_ledger_gives(client, week):
    headers = login(client, "admin@test.internal", ADMIN_PASSWORD)
    today = client.get(f"{PATH}/today", headers=headers).json()
    ranged = client.get(PATH, headers=headers, params=_span(week, 0, 0)).json()
    assert sorted(today, key=lambda r: r["id"]) == sorted(ranged, key=lambda r: r["id"])


def test_resource_id_narrows_to_that_resource(client, week):
    headers = login(client, "admin@test.internal", ADMIN_PASSWORD)
    params = {**_span(week, 0, 2), "resource_id": week["room"]}
    res = client.get(PATH, headers=headers, params=params)
    assert res.headers["X-Total-Count"] == "3"
    assert {r["activity_code"] for r in res.json()} == {"ACT1"}


def test_pages_follow_the_same_order(client, week):
    headers = login(client, "admin@test.internal", ADMIN_PASSWORD)
    span = _span(week, 0, 2)
    whole = [r["id"] for r in client.get(PATH, headers=headers, params=span).json()]
    paged = []
    for offset in range(0, 6, 4):
        res = client.get(PATH, headers=headers, params={**span, "limit": 4, "offset": offset})
        assert res.headers["X-Total-Count"] == "6"
        paged += [r["id"] for r in res.json()]
    assert paged == whole


def test_a_member_sees_only_the_activities_they_are_enrolled_in(client, week):
    headers = login(client, "member@test.internal", MEMBER_PASSWORD)
    res = client.get(PATH, headers=headers, params=_span(week, 0, 2))
    assert res.headers["X-Total-Count"] == "3"
    assert {r["activity_code"] for r in res.json()} == {"ACT1"}


def test_staff_see_only_the_days_they_lead_or_cover(client, week):
    headers = login(client, "staff@test.internal", STAFF_PASSWORD)
    res = client.get(PATH, headers=headers, params=_span(week, 0, 2))
    assert {r["active_lead_id"] for r in res.json()} == {"FAC001"}
    assert res.headers["X-Total-Count"] == "3"


def test_to_before_from_is_refused(client, week):
    headers = login(client, "admin@test.internal", ADMIN_PASSWORD)
    assert client.get(PATH, headers=headers, params=_span(week, 2, 0)).status_code == 422


@pytest.mark.parametrize("missing", ["from", "to"])
def test_both_dates_are_required(client, week, missing):
    headers = login(client, "admin@test.internal", ADMIN_PASSWORD)
    params = _span(week, 0, 2)
    del params[missing]
    assert client.get(PATH, headers=headers, params=params).status_code == 422


def test_it_needs_a_signed_in_caller(client, week):
    assert client.get(PATH, params=_span(week, 0, 2)).status_code == 401
