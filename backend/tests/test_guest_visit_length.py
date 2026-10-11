# Copyright 2026 Chronos Ledger Contributors
# Licensed under the Apache License, Version 2.0
"""An approved visit can run out of time, and somebody is told when it does.

Nothing is revoked at the end of a visit: Chronos does not hold the door. The
row says the time is up, the desk hears about it once, and a person decides
whether to extend it or to go and find them.
"""

import asyncio
import json
from datetime import UTC, datetime, timedelta

import pytest
from pydantic import ValidationError

from app.core.config import Settings, get_settings
from app.core.websocket_manager import socket_broker
from app.cron.guest_overstay import announce_overstayed_visits
from app.models.db import GuestGateRegistry, LogVerificationState
from tests.conftest import ADMIN_PASSWORD, STAFF_PASSWORD, login
from tests.test_attendance_guest import _GUEST, _check_in_for, _decide, _staff_in


@pytest.fixture()
def visit_length(monkeypatch):
    """Set the visit settings, as an operator would, and undo it after."""

    def set_them(minutes, extension_max=None):
        monkeypatch.setenv("GUEST_VISIT_LENGTH_MINUTES", str(minutes))
        if extension_max is not None:
            monkeypatch.setenv("GUEST_VISIT_EXTENSION_MAX_MINUTES", str(extension_max))
        get_settings.cache_clear()

    yield set_them
    get_settings.cache_clear()


@pytest.fixture()
def admin_can_decide(monkeypatch):
    monkeypatch.setenv("GUEST_ADMIN_CAN_DECIDE", "true")
    get_settings.cache_clear()
    yield
    get_settings.cache_clear()


class _FakeSocket:
    """Stands in for a browser with the app open, and keeps what it is sent."""

    def __init__(self):
        self.frames = []

    async def send_text(self, text):
        self.frames.append(json.loads(text))


@pytest.fixture()
def open_socket():
    opened = {}

    def open_for(user_id):
        opened[user_id] = _FakeSocket()
        socket_broker.register_session(user_id, opened[user_id])
        return opened[user_id]

    yield open_for
    for user_id, sock in opened.items():
        socket_broker.terminate_session(user_id, sock)


def _approve_in_the_row(db, entry_id, minutes_ago=None):
    """Approve a visit in the row, and optionally put its end in the past.

    Rather than holding a test open for the length of a visit. Used where the
    decision itself is not what is under test.
    """
    entry = db.get(GuestGateRegistry, entry_id)
    entry.handshake_status = LogVerificationState.VERIFIED_APPROVED
    entry.decided_by_id = entry.target_staff_id
    entry.visit_expires_at = datetime.now(UTC) + timedelta(minutes=60)
    if minutes_ago is not None:
        entry.visit_expires_at = datetime.now(UTC) - timedelta(minutes=minutes_ago)
    entry.overstay_notified_at = None
    db.commit()
    return entry_id


def _expires_at(db, entry_id):
    db.expire_all()
    moment = db.get(GuestGateRegistry, entry_id).visit_expires_at
    return moment if moment is None or moment.tzinfo else moment.replace(tzinfo=UTC)


def _extend(client, headers, entry_id, minutes):
    return client.patch(
        f"/api/v1/guest/{entry_id}/extend", json={"minutes": minutes}, headers=headers
    )


# -- The settings --------------------------------------------------------------


def test_a_visit_is_open_ended_by_default():
    """Upgrading gives no existing instance a rule it did not ask for."""
    assert Settings().guest_visit_length_minutes == 0


def test_four_hours_is_the_default_ceiling_on_one_extension():
    assert Settings().guest_visit_extension_max_minutes == 240


def test_a_negative_visit_length_is_refused_at_startup():
    with pytest.raises(ValidationError, match="GUEST_VISIT_LENGTH_MINUTES"):
        Settings(guest_visit_length_minutes=-1)


def test_a_negative_extension_ceiling_is_refused_at_startup():
    with pytest.raises(ValidationError, match="GUEST_VISIT_EXTENSION_MAX_MINUTES"):
        Settings(guest_visit_extension_max_minutes=-1)


# -- The decision writes the end ----------------------------------------------


def test_approving_a_visit_gives_it_an_end(client, db, seed_users, kiosk_key, visit_length):
    visit_length(120)
    entry_id = _check_in_for(client, kiosk_key, "FAC001")
    fac = login(client, "staff@test.internal", STAFF_PASSWORD)
    assert _decide(client, fac, entry_id).status_code == 200

    # From the decision and not from the check-in: the clock starts when
    # somebody was let in at the door, not when they arrived at it.
    expected = datetime.now(UTC) + timedelta(minutes=120)
    assert abs((_expires_at(db, entry_id) - expected).total_seconds()) < 60


def test_a_visit_stays_open_ended_while_the_setting_is_zero(client, db, seed_users, kiosk_key):
    entry_id = _check_in_for(client, kiosk_key, "FAC001")
    fac = login(client, "staff@test.internal", STAFF_PASSWORD)
    assert _decide(client, fac, entry_id).status_code == 200
    assert _expires_at(db, entry_id) is None


def test_denying_a_visit_gives_it_no_end(client, db, seed_users, kiosk_key, visit_length):
    visit_length(120)
    entry_id = _check_in_for(client, kiosk_key, "FAC001")
    fac = login(client, "staff@test.internal", STAFF_PASSWORD)
    assert _decide(client, fac, entry_id, "VERIFIED_DENIED").status_code == 200
    assert _expires_at(db, entry_id) is None


def test_deciding_again_the_other_way_takes_the_end_away(
    client, db, seed_users, kiosk_key, visit_length
):
    """Or a visit approved and then refused would keep the clock the approval gave it."""
    visit_length(120)
    entry_id = _check_in_for(client, kiosk_key, "FAC001")
    fac = login(client, "staff@test.internal", STAFF_PASSWORD)
    _decide(client, fac, entry_id)
    assert _expires_at(db, entry_id) is not None

    assert _decide(client, fac, entry_id, "VERIFIED_DENIED").status_code == 200
    assert _expires_at(db, entry_id) is None


def test_the_visitor_is_told_when_to_leave_and_nothing_else(
    client, db, seed_users, kiosk_key, visit_length
):
    """The code is read over shoulders, so a time is all it may give away."""
    visit_length(120)
    body = client.post("/api/v1/guest/register-checkin", json=_GUEST, headers=kiosk_key).json()
    fac = login(client, "staff@test.internal", STAFF_PASSWORD)
    _decide(client, fac, body["reference_token"])

    code = body["visit_code"]
    status = client.get(f"/api/v1/guest/visit/{code}").json()
    assert status["visit_expires_at"] is not None
    assert set(status) == {"handshake_status", "timestamp_marked", "visit_expires_at"}


# -- Extending a visit ---------------------------------------------------------


def test_the_person_visited_extends_the_visit(client, db, seed_users, kiosk_key, visit_length):
    visit_length(60)
    entry_id = _check_in_for(client, kiosk_key, "FAC001")
    fac = login(client, "staff@test.internal", STAFF_PASSWORD)
    _decide(client, fac, entry_id)
    before = _expires_at(db, entry_id)

    res = _extend(client, fac, entry_id, 30)
    assert res.status_code == 200, res.text
    assert res.json()["status"] == "VISIT_EXTENDED"
    moved = _expires_at(db, entry_id) - (before + timedelta(minutes=30))
    assert abs(moved.total_seconds()) < 2


def test_an_extension_longer_than_the_ceiling_is_refused(
    client, db, seed_users, kiosk_key, visit_length
):
    """Refused rather than trimmed, so a desk that typed 300 for 30 hears about it."""
    visit_length(60, extension_max=60)
    entry_id = _check_in_for(client, kiosk_key, "FAC001")
    fac = login(client, "staff@test.internal", STAFF_PASSWORD)
    _decide(client, fac, entry_id)
    before = _expires_at(db, entry_id)

    assert _extend(client, fac, entry_id, 61).status_code == 422
    assert _expires_at(db, entry_id) == before


def test_an_organization_can_refuse_every_extension(
    client, db, seed_users, kiosk_key, visit_length
):
    """For one that would rather the visitor checked in again."""
    visit_length(60, extension_max=0)
    entry_id = _check_in_for(client, kiosk_key, "FAC001")
    fac = login(client, "staff@test.internal", STAFF_PASSWORD)
    _decide(client, fac, entry_id)

    res = _extend(client, fac, entry_id, 1)
    assert res.status_code == 422
    assert "does not extend visits" in res.json()["detail"]


def test_extending_a_visit_already_over_starts_from_now(
    client, db, seed_users, kiosk_key, visit_length
):
    """Or a visit an hour over would be granted a window that had already gone."""
    visit_length(60)
    entry_id = _approve_in_the_row(db, _check_in_for(client, kiosk_key, "FAC001"), minutes_ago=60)

    fac = login(client, "staff@test.internal", STAFF_PASSWORD)
    assert _extend(client, fac, entry_id, 30).status_code == 200
    expected = datetime.now(UTC) + timedelta(minutes=30)
    assert abs((_expires_at(db, entry_id) - expected).total_seconds()) < 60


def test_a_visit_nobody_has_approved_cannot_be_extended(
    client, db, seed_users, kiosk_key, visit_length
):
    visit_length(60)
    entry_id = _check_in_for(client, kiosk_key, "FAC001")
    fac = login(client, "staff@test.internal", STAFF_PASSWORD)
    assert _extend(client, fac, entry_id, 30).status_code == 409


def test_an_open_ended_visit_cannot_be_extended(client, db, seed_users, kiosk_key):
    """There is nothing to extend: it has no end to move."""
    entry_id = _check_in_for(client, kiosk_key, "FAC001")
    fac = login(client, "staff@test.internal", STAFF_PASSWORD)
    _decide(client, fac, entry_id)
    assert _extend(client, fac, entry_id, 30).status_code == 409


def test_somebody_who_could_not_decide_the_visit_cannot_extend_it(
    client, db, seed_users, kiosk_key, visit_length
):
    visit_length(60)
    entry_id = _check_in_for(client, kiosk_key, "FAC001")
    fac = login(client, "staff@test.internal", STAFF_PASSWORD)
    _decide(client, fac, entry_id)

    adm = login(client, "admin@test.internal", ADMIN_PASSWORD)
    assert _extend(client, adm, entry_id, 30).status_code == 404


def test_an_admin_who_could_decide_the_visit_extends_it(
    client, db, seed_users, kiosk_key, visit_length, admin_can_decide
):
    """A desk that may let somebody in may also let them stay."""
    visit_length(60)
    entry_id = _check_in_for(client, kiosk_key, "FAC001")
    adm = login(client, "admin@test.internal", ADMIN_PASSWORD)
    assert _decide(client, adm, entry_id).status_code == 200
    assert _extend(client, adm, entry_id, 30).status_code == 200


# -- The overstay list ---------------------------------------------------------


def test_the_overstay_list_holds_the_visits_that_have_run_over(
    client, db, seed_users, kiosk_key, visit_length
):
    visit_length(60)
    over = _approve_in_the_row(db, _check_in_for(client, kiosk_key, "FAC001"), minutes_ago=10)
    still_running = _check_in_for(client, kiosk_key, "FAC001")
    fac = login(client, "staff@test.internal", STAFF_PASSWORD)
    _decide(client, fac, still_running)
    _check_in_for(client, kiosk_key, "FAC001")  # and one nobody has decided

    listed = client.get("/api/v1/guest/overstays", headers=fac).json()
    assert [row["id"] for row in listed] == [over]


def test_the_overstay_list_puts_the_longest_over_first(
    client, db, seed_users, kiosk_key, visit_length
):
    visit_length(60)
    recent = _approve_in_the_row(db, _check_in_for(client, kiosk_key, "FAC001"), minutes_ago=5)
    older = _approve_in_the_row(db, _check_in_for(client, kiosk_key, "FAC001"), minutes_ago=90)

    fac = login(client, "staff@test.internal", STAFF_PASSWORD)
    listed = client.get("/api/v1/guest/overstays", headers=fac).json()
    assert [row["id"] for row in listed] == [older, recent]


def test_extending_a_visit_takes_it_off_the_overstay_list(
    client, db, seed_users, kiosk_key, visit_length
):
    visit_length(60)
    entry_id = _approve_in_the_row(db, _check_in_for(client, kiosk_key, "FAC001"), minutes_ago=10)
    fac = login(client, "staff@test.internal", STAFF_PASSWORD)
    listed = client.get("/api/v1/guest/overstays", headers=fac).json()
    assert [row["id"] for row in listed] == [entry_id]

    assert _extend(client, fac, entry_id, 30).status_code == 200
    assert client.get("/api/v1/guest/overstays", headers=fac).json() == []


def test_the_overstay_list_reaches_no_further_than_the_decision_does(
    client, db, seed_users, kiosk_key, visit_length
):
    visit_length(60)
    elsewhere = _staff_in(db, "ECE", id_="FAC-ECE")
    _approve_in_the_row(db, _check_in_for(client, kiosk_key, elsewhere), minutes_ago=10)

    fac = login(client, "staff@test.internal", STAFF_PASSWORD)
    assert client.get("/api/v1/guest/overstays", headers=fac).json() == []


# -- The sweep that says so ----------------------------------------------------


def test_the_sweep_tells_the_person_the_visitor_came_to_see(
    client, db, seed_users, kiosk_key, visit_length, open_socket
):
    visit_length(60)
    entry_id = _approve_in_the_row(db, _check_in_for(client, kiosk_key, "FAC001"), minutes_ago=10)
    expires_at = db.get(GuestGateRegistry, entry_id).visit_expires_at
    staff = open_socket("FAC001")

    assert asyncio.run(announce_overstayed_visits(db)) == 1
    assert staff.frames == [
        {
            "event": "GUEST_VISIT_EXPIRED",
            "payload": {
                "transaction_reference": entry_id,
                "guest_name": "Ravi Verma",
                "visit_expires_at": expires_at.isoformat(),
            },
        }
    ]


def test_the_sweep_tells_whoever_let_the_visitor_in_as_well(
    client, db, seed_users, kiosk_key, visit_length, admin_can_decide, open_socket
):
    """An admin who approved a visit at the desk is where the visitor walks back past."""
    visit_length(60)
    entry_id = _check_in_for(client, kiosk_key, "FAC001")
    adm = login(client, "admin@test.internal", ADMIN_PASSWORD)
    assert _decide(client, adm, entry_id).status_code == 200
    db.expire_all()
    db.get(GuestGateRegistry, entry_id).visit_expires_at = datetime.now(UTC) - timedelta(minutes=10)
    db.commit()

    staff, desk = open_socket("FAC001"), open_socket("ADM001")
    assert asyncio.run(announce_overstayed_visits(db)) == 1
    assert len(staff.frames) == 1
    assert desk.frames == staff.frames


def test_the_sweep_says_it_once(client, db, seed_users, kiosk_key, visit_length, open_socket):
    """Or a desk would hear about the same visitor every five minutes until closing."""
    visit_length(60)
    _approve_in_the_row(db, _check_in_for(client, kiosk_key, "FAC001"), minutes_ago=10)
    staff = open_socket("FAC001")

    assert asyncio.run(announce_overstayed_visits(db)) == 1
    assert asyncio.run(announce_overstayed_visits(db)) == 0
    assert len(staff.frames) == 1


def test_a_second_overrun_announces_itself_as_the_first_did(
    client, db, seed_users, kiosk_key, visit_length, open_socket
):
    """Which is what clearing the stamp on an extension is for."""
    visit_length(60)
    entry_id = _approve_in_the_row(db, _check_in_for(client, kiosk_key, "FAC001"), minutes_ago=10)
    staff = open_socket("FAC001")
    asyncio.run(announce_overstayed_visits(db))

    fac = login(client, "staff@test.internal", STAFF_PASSWORD)
    assert _extend(client, fac, entry_id, 30).status_code == 200
    db.expire_all()
    db.get(GuestGateRegistry, entry_id).visit_expires_at = datetime.now(UTC) - timedelta(minutes=1)
    db.commit()

    assert asyncio.run(announce_overstayed_visits(db)) == 1
    assert len(staff.frames) == 2


def test_the_sweep_leaves_a_visit_that_is_still_running_alone(
    client, db, seed_users, kiosk_key, visit_length, open_socket
):
    visit_length(60)
    entry_id = _check_in_for(client, kiosk_key, "FAC001")
    fac = login(client, "staff@test.internal", STAFF_PASSWORD)
    _decide(client, fac, entry_id)
    staff = open_socket("FAC001")

    assert asyncio.run(announce_overstayed_visits(db)) == 0
    assert staff.frames == []


def test_the_sweep_leaves_alone_a_visit_nobody_approved(
    client, db, seed_users, kiosk_key, visit_length, open_socket
):
    """A denied visitor was never let in, so there is nothing to have run over."""
    visit_length(60)
    entry_id = _check_in_for(client, kiosk_key, "FAC001")
    fac = login(client, "staff@test.internal", STAFF_PASSWORD)
    _decide(client, fac, entry_id, "VERIFIED_DENIED")
    db.expire_all()
    db.get(GuestGateRegistry, entry_id).visit_expires_at = datetime.now(UTC) - timedelta(minutes=10)
    db.commit()
    staff = open_socket("FAC001")

    assert asyncio.run(announce_overstayed_visits(db)) == 0
    assert staff.frames == []


def test_the_sweep_announces_nothing_while_visits_are_open_ended(
    client, db, seed_users, kiosk_key, open_socket
):
    """With no length set no visit has an end, so the job is a read and nothing else."""
    entry_id = _check_in_for(client, kiosk_key, "FAC001")
    fac = login(client, "staff@test.internal", STAFF_PASSWORD)
    _decide(client, fac, entry_id)
    staff = open_socket("FAC001")

    assert asyncio.run(announce_overstayed_visits(db)) == 0
    assert staff.frames == []
