# Copyright 2026 Chronos Ledger Contributors
# Licensed under the Apache License, Version 2.0
"""Putting a cycle into service, and what stops it.

Nothing set operational_status back to true. A cycle could be closed and
never reopened, and a cycle created closed could never be opened at all, so a
schedule had to be right at the moment it was typed in. That suits a term
planned once and run; it does not suit a rota filled in over a fortnight,
which is the case this route exists for.

Drafting closed is also what makes the route more than a flag flip. A slot
entered into a closed cycle is never checked against the bookings or against
the rest of the timetable, because a closed cycle's slots occupy nothing. All
of them start occupying their rooms the instant the flag goes true, so the
checks POST /slots would have run are run here, over every slot at once.

Dates are computed rather than written down, for the reason the sibling files
give: the checks count from today forward, so a date typed into this file
would eventually fall into the past and the tests would pass for the wrong
reason.
"""

import datetime

from app.cron.ledger_generator import generate_daily_ledger_entries
from app.models.db import PlanningCycle
from tests.conftest import ADMIN_PASSWORD, login
from tests.test_import_corrections import TOMORROW
from tests.test_slot_vs_hold import _activity, _hold, _hold_written_straight_in, _room
from tests.test_slot_vs_slot import _sibling, _slot_in_db

BLOCKED = "opening this cycle would put its slots on rooms already taken"


def _open(client, headers, cycle_id):
    return client.patch(f"/api/v1/schedule/cycles/{cycle_id}/open", headers=headers)


def _close(db, cycle_id):
    """Closed by writing the flag, the way SQL or a close from before the
    route withdrew days would, which leaves every day behind."""
    cycle = db.query(PlanningCycle).filter(PlanningCycle.id == cycle_id).first()
    cycle.operational_status = False
    db.commit()


# ── What refuses an open ─────────────────────────────────────────────────────


def test_a_cycle_is_not_opened_over_a_standing_hold(client, db, seed_users):
    """The booking was taken while the cycle was shut, and legitimately.

    A closed cycle's slot occupies nothing, so the booking endpoint had no
    reason to refuse this hold and did not. Opening the cycle is the moment
    the two start competing, and it is the last moment anybody can be told.
    """
    headers = login(client, "admin@test.internal", ADMIN_PASSWORD)
    room = _room(db)
    draft = _activity(db, is_open=False)
    slot = _slot_in_db(
        db, draft.id, room.id, TOMORROW.isoweekday(), datetime.time(9), datetime.time(10)
    )
    held = _hold(client, headers, room.id, TOMORROW)

    r = _open(client, headers, draft.cycle_id)
    assert r.status_code == 409, r.text

    body = r.json()["detail"]
    assert body["message"] == BLOCKED
    # The eight keys a clash carries everywhere else, plus the one this route
    # adds: which of the caller's own slots wanted the room.
    assert [c["reservation_id"] for c in body["conflicts"]] == [held["id"]]
    assert body["conflicts"][0]["master_slot_id"] is None
    assert body["conflicts"][0]["blocked_slot_id"] == slot.id
    assert body["conflicts"][0]["date"] == str(TOMORROW)


def test_two_of_the_cycles_own_slots_in_one_room_refuse_the_open(client, db, seed_users):
    """The mistake a cycle built up over a fortnight is likeliest to hold.

    Neither of these was refused when it was entered, because POST /slots
    skips the timetable check while the cycle is shut. They are checked
    against each other here, and they find each other through booked_slots,
    which is the same query the write path uses.
    """
    headers = login(client, "admin@test.internal", ADMIN_PASSWORD)
    room = _room(db)
    draft = _activity(db, is_open=False)
    first = _slot_in_db(
        db, draft.id, room.id, TOMORROW.isoweekday(), datetime.time(9), datetime.time(11)
    )
    other = _sibling(db, draft.cycle_id)
    second = _slot_in_db(
        db, other.id, room.id, TOMORROW.isoweekday(), datetime.time(10), datetime.time(12)
    )

    r = _open(client, headers, draft.cycle_id)
    assert r.status_code == 409, r.text

    body = r.json()["detail"]
    # Named from both sides. There is no honest way to pick which of the two
    # is the one at fault, and the admin has to move one of them.
    pairs = {(c["blocked_slot_id"], c["master_slot_id"]) for c in body["conflicts"]}
    assert pairs == {(first.id, second.id), (second.id, first.id)}


def test_a_cycle_is_not_opened_over_another_cycles_class(client, db, seed_users):
    headers = login(client, "admin@test.internal", ADMIN_PASSWORD)
    room = _room(db)
    live = _activity(db)
    sitting = _slot_in_db(
        db, live.id, room.id, TOMORROW.isoweekday(), datetime.time(9), datetime.time(11)
    )
    draft = _activity(db, is_open=False, code="CS102")
    mine = _slot_in_db(
        db, draft.id, room.id, TOMORROW.isoweekday(), datetime.time(10), datetime.time(12)
    )

    r = _open(client, headers, draft.cycle_id)
    assert r.status_code == 409, r.text

    body = r.json()["detail"]
    assert [c["master_slot_id"] for c in body["conflicts"]] == [sitting.id]
    assert body["conflicts"][0]["blocked_slot_id"] == mine.id


def test_a_cycle_is_not_opened_over_a_day_already_generated(client, db, seed_users):
    """A closed cycle can still have days ahead of it.

    The route keeps the ones carrying attendance or a note, and a flag
    written by hand keeps them all. Those days are the rows that put somebody at a door, and they are still
    in the table however their cycle is flagged. Migration 013 refuses a
    second row on top of one, so an open that ignored them would turn a
    refusal the admin could act on into a 500 at 23:00.
    """
    headers = login(client, "admin@test.internal", ADMIN_PASSWORD)
    room = _room(db)
    last_term = _activity(db)
    _slot_in_db(
        db, last_term.id, room.id, TOMORROW.isoweekday(), datetime.time(9), datetime.time(11)
    )
    assert generate_daily_ledger_entries(TOMORROW, db) == 1
    _close(db, last_term.cycle_id)

    draft = _activity(db, is_open=False, code="CS102")
    mine = _slot_in_db(
        db, draft.id, room.id, TOMORROW.isoweekday(), datetime.time(10), datetime.time(12)
    )

    r = _open(client, headers, draft.cycle_id)
    assert r.status_code == 409, r.text

    body = r.json()["detail"]
    assert body["message"] == BLOCKED
    assert body["conflicts"][0]["blocked_slot_id"] == mine.id
    assert body["conflicts"][0]["date"] == str(TOMORROW)


def test_a_refused_open_leaves_the_cycle_closed(client, db, seed_users):
    """The flag is written before the checks run, so a refusal has to undo it.

    Every other refusal in this API asks before it writes. This one cannot:
    the cycle's own slots are invisible to booked_slots until the flag is
    flushed, and checking them against each other is half the point of the
    route. The rollback is the correctness of the refusal rather than tidiness
    after it, and without it a refused open leaves the cycle open.
    """
    headers = login(client, "admin@test.internal", ADMIN_PASSWORD)
    room = _room(db)
    draft = _activity(db, is_open=False)
    _slot_in_db(db, draft.id, room.id, TOMORROW.isoweekday(), datetime.time(9), datetime.time(10))
    _hold(client, headers, room.id, TOMORROW)

    assert _open(client, headers, draft.cycle_id).status_code == 409

    cycle = db.query(PlanningCycle).filter(PlanningCycle.id == draft.cycle_id).first()
    assert cycle.operational_status is False
    # And the generator still lays nothing down for it.
    assert generate_daily_ledger_entries(TOMORROW, db) == 0


# ── What does not ────────────────────────────────────────────────────────────


def test_a_clean_cycle_opens_and_its_days_follow(client, db, seed_users):
    headers = login(client, "admin@test.internal", ADMIN_PASSWORD)
    room = _room(db)
    draft = _activity(db, is_open=False)
    _slot_in_db(db, draft.id, room.id, TOMORROW.isoweekday(), datetime.time(9), datetime.time(10))
    # Nothing is generated for a cycle that has not been put into service.
    assert generate_daily_ledger_entries(TOMORROW, db) == 0

    r = _open(client, headers, draft.cycle_id)
    assert r.status_code == 200, r.text
    assert generate_daily_ledger_entries(TOMORROW, db) == 1


def test_a_cycle_with_no_slots_opens(client, db, seed_users):
    """Created open has always been allowed, and this is the same state
    reached the other way round: created closed, opened before anything has
    been put in it."""
    headers = login(client, "admin@test.internal", ADMIN_PASSWORD)
    draft = _activity(db, is_open=False)

    r = _open(client, headers, draft.cycle_id)
    assert r.status_code == 200, r.text


def test_opening_a_cycle_that_is_already_open_says_so(client, db, seed_users):
    """No checks on a cycle that is already in service.

    Its slots were checked as they landed. Running the checks anyway would
    make this route refuse a state the API is already in, and the hold
    written straight in here is exactly the sort of row that predates the
    rules and would do it.
    """
    headers = login(client, "admin@test.internal", ADMIN_PASSWORD)
    room = _room(db)
    live = _activity(db)
    _slot_in_db(db, live.id, room.id, TOMORROW.isoweekday(), datetime.time(9), datetime.time(10))
    _hold_written_straight_in(db, room.id, TOMORROW)

    r = _open(client, headers, live.cycle_id)
    assert r.status_code == 200, r.text
    assert r.json()["message"].endswith("was already open")


def test_opening_a_cycle_that_is_not_there_is_a_404(client, db, seed_users):
    headers = login(client, "admin@test.internal", ADMIN_PASSWORD)
    r = _open(client, headers, 9999)
    assert r.status_code == 404, r.text
