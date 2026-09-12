# Copyright 2026 Chronos Ledger Contributors
# Licensed under the Apache License, Version 2.0
"""A slot runs only on its own cycle's dates, and the checks now know it.

The nightly generator writes a day for a slot only while its cycle is open and
the date is inside the cycle's two dates. The checks that refuse a slot asked
the first question and not the second, so next year's cycle could not be put
into a room this year's timetable used at the same hour, and a cycle whose
dates had run out held every room it named for as long as nobody closed it.

Each of the three things a slot is checked against is pinned here, and each of
the ways a slot gets in: the verb that writes one, the importer, and opening a
drafted cycle. The refusals themselves are pinned in test_slot_vs_hold,
test_slot_vs_slot and test_slot_vs_day, which pass the cycle the same way.

Dates are computed from today, for the reason test_slot_vs_hold gives.
"""

import datetime

import pytest

from app.core.time import org_today
from app.models.db import Activity, PlanningCycle, StructuralMasterSlot
from tests.conftest import ADMIN_PASSWORD, login
from tests.test_cycle_activation import _open
from tests.test_import_corrections import TOMORROW, _csv, _row
from tests.test_ingestion import _make_cycle, _upload
from tests.test_slot_vs_day import HAS_A_DAY, _day
from tests.test_slot_vs_hold import HELD, _activity, _hold, _new_slot, _room
from tests.test_slot_vs_slot import SCHEDULED, _slot_in_db


def _activity_between(db, starts, ends, is_open=True, code="CS301"):
    """An activity in a cycle running from `starts` to `ends` days from today."""
    today = org_today()
    cycle = PlanningCycle(
        cycle_label=f"Days {starts} to {ends}",
        date_bounds_start=today + datetime.timedelta(days=starts),
        date_bounds_end=today + datetime.timedelta(days=ends),
        operational_status=is_open,
    )
    db.add(cycle)
    db.flush()
    activity = Activity(
        activity_code=code,
        activity_title="Something",
        unit_code="CSE",
        cycle_id=cycle.id,
    )
    db.add(activity)
    db.commit()
    return activity


def _nine_tomorrow(db, activity_id, room_id):
    return _slot_in_db(
        db, activity_id, room_id, TOMORROW.isoweekday(), datetime.time(9), datetime.time(10)
    )


# ── Creating a slot ──────────────────────────────────────────────────────────


def test_a_cycle_that_starts_after_another_ends_can_share_its_room(client, db, seed_users):
    headers = login(client, "admin@test.internal", ADMIN_PASSWORD)
    room = _room(db)
    _nine_tomorrow(db, _activity(db).id, room.id)
    next_year = _activity_between(db, 400, 500)

    r = _new_slot(client, headers, next_year.id)
    assert r.status_code == 200, r.text
    assert db.query(StructuralMasterSlot).count() == 2


def test_a_cycle_whose_dates_have_run_out_holds_nothing(client, db, seed_users):
    """Still flagged open, because nobody closed it.

    The generator stopped writing its days the day after it ended, so the
    room is free, whatever the flag says.
    """
    headers = login(client, "admin@test.internal", ADMIN_PASSWORD)
    room = _room(db)
    _nine_tomorrow(db, _activity_between(db, -300, -10).id, room.id)

    r = _new_slot(client, headers, _activity(db).id)
    assert r.status_code == 200, r.text


def test_where_two_cycles_meet_later_the_clash_is_dated_when_they_do(client, db, seed_users):
    headers = login(client, "admin@test.internal", ADMIN_PASSWORD)
    room = _room(db)
    sitting = _nine_tomorrow(db, _activity_between(db, 200, 500).id, room.id)

    r = _new_slot(client, headers, _activity(db).id)
    assert r.status_code == 409, r.text
    body = r.json()["detail"]
    assert body["message"] == SCHEDULED
    # Not tomorrow: the other cycle has no day then. The first date the two
    # both run on is the first of its weeks.
    starts = org_today() + datetime.timedelta(days=200)
    first = starts + datetime.timedelta(days=(TOMORROW.isoweekday() - starts.isoweekday()) % 7)
    assert [(c["master_slot_id"], c["date"]) for c in body["conflicts"]] == [
        (sitting.id, str(first))
    ]


def test_a_hold_before_a_cycle_starts_is_not_in_its_way(client, db, seed_users):
    headers = login(client, "admin@test.internal", ADMIN_PASSWORD)
    room = _room(db)
    _hold(client, headers, room.id, TOMORROW)

    this_year = _new_slot(client, headers, _activity(db).id)
    assert this_year.status_code == 409, this_year.text
    assert this_year.json()["detail"]["message"] == HELD

    r = _new_slot(client, headers, _activity_between(db, 400, 500).id)
    assert r.status_code == 200, r.text


def test_a_generated_day_before_a_cycle_starts_is_not_in_its_way(client, db, seed_users):
    headers = login(client, "admin@test.internal", ADMIN_PASSWORD)
    room = _room(db)
    leftover = _activity(db, is_open=False)
    slot = _nine_tomorrow(db, leftover.id, room.id)
    _day(db, leftover.id, room.id, TOMORROW, slot_id=slot.id)

    this_year = _new_slot(client, headers, _activity(db, code="CS102").id)
    assert this_year.status_code == 409, this_year.text
    assert this_year.json()["detail"]["message"] == HAS_A_DAY

    r = _new_slot(client, headers, _activity_between(db, 400, 500).id)
    assert r.status_code == 200, r.text


# ── Opening a drafted cycle ──────────────────────────────────────────────────


@pytest.mark.parametrize(
    ("starts", "status"),
    [(400, 200), (200, 409)],
    ids=["after the live one ends", "before the live one ends"],
)
def test_a_draft_opens_over_a_room_only_where_the_dates_leave_it_free(
    client, db, seed_users, starts, status
):
    headers = login(client, "admin@test.internal", ADMIN_PASSWORD)
    room = _room(db)
    _nine_tomorrow(db, _activity(db).id, room.id)
    draft = _activity_between(db, starts, 500, is_open=False)
    _nine_tomorrow(db, draft.id, room.id)

    r = _open(client, headers, draft.cycle_id)
    assert r.status_code == status, r.text


# ── Uploading a timetable ────────────────────────────────────────────────────


@pytest.mark.parametrize(
    ("starts", "status"),
    [(200, 200), (60, 422)],
    ids=["after the upload's cycle ends", "before the upload's cycle ends"],
)
def test_an_upload_meets_another_cycle_only_on_their_shared_dates(
    client, db, seed_users, starts, status
):
    headers = login(client, "admin@test.internal", ADMIN_PASSWORD)
    room = _room(db)
    _nine_tomorrow(db, _activity_between(db, starts, 300).id, room.id)
    # From thirty days ago to ninety days on.
    cycle = _make_cycle(db)

    r = _upload(client, headers, cycle.id, _csv(_row()))
    assert r.status_code == status, r.text


# ── Creating a cycle ─────────────────────────────────────────────────────────


def test_a_cycle_that_ends_before_it_starts_is_refused(client, db, seed_users):
    headers = login(client, "admin@test.internal", ADMIN_PASSWORD)
    backwards = {
        "cycle_label": "Backwards",
        "date_bounds_start": "2026-10-10",
        "date_bounds_end": "2026-10-09",
    }

    r = client.post("/api/v1/schedule/cycles", headers=headers, json=backwards)
    assert r.status_code == 422, r.text
    assert db.query(PlanningCycle).count() == 0

    one_day = {**backwards, "cycle_label": "One day", "date_bounds_end": "2026-10-10"}
    r = client.post("/api/v1/schedule/cycles", headers=headers, json=one_day)
    assert r.status_code == 200, r.text
