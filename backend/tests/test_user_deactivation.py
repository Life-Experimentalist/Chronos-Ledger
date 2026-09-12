# Copyright 2026 Chronos Ledger Contributors
# Licensed under the Apache License, Version 2.0
"""H-21: somebody who leaves is deactivated, not deleted.

Deleting a user took the attendance recorded against them, and there was no
other way to stop an account. Deactivating keeps every record, closes every
way in, and takes the account out of the lists people are picked from.
"""

import asyncio
from datetime import UTC, datetime, time, timedelta

from app.api.v1.endpoints import websocket as ws_module
from app.core.time import org_today
from app.core.websocket_manager import OrganizationConnectionManager, socket_broker
from app.models.db import (
    Activity,
    ApiKey,
    DailyLedger,
    LogVerificationState,
    PlanningCycle,
    ReverseRsvpLog,
    StructuralMasterSlot,
    User,
)
from tests.conftest import ADMIN_PASSWORD, MEMBER_PASSWORD, STAFF_PASSWORD, login
from tests.test_attendance_guest import _GUEST, _FakeRedis
from tests.test_ingestion import HEADER, _make_cycle, _upload
from tests.test_ledger_patch import _patch
from tests.test_unit_admin_scope import _seed_unit_world, _unit_admin
from tests.test_websocket import WS_PATH, _access_token, _auth, _refusal_code


def _admin(client):
    return login(client, "admin@test.internal", ADMIN_PASSWORD)


def _deactivate(client, headers, user_id):
    return client.post(f"/api/v1/users/{user_id}/deactivate", headers=headers)


def _reactivate(client, headers, user_id):
    return client.post(f"/api/v1/users/{user_id}/reactivate", headers=headers)


def _mark_deactivated(db, user_id):
    """Straight into the table, for tests about what a deactivated account is refused."""
    db.query(User).filter(User.id == user_id).update({"deactivated_at": datetime.now(UTC)})
    db.commit()


def _member_login(client):
    res = client.post(
        "/api/v1/auth/login", json={"email": "member@test.internal", "password": MEMBER_PASSWORD}
    )
    assert res.status_code == 200, res.text
    return res.json()


def _feed_token(db, user_id):
    db.expire_all()
    return db.query(User).filter(User.id == user_id).one().calendar_feed_token


# -- Every way in closes ------------------------------------------------------


def test_deactivating_ends_signing_in_and_the_tokens_already_issued(client, db, seed_users):
    member = _member_login(client)
    bearer = {"Authorization": f"Bearer {member['access_token']}"}

    r = _deactivate(client, _admin(client), "STU001")
    assert r.status_code == 200, r.text
    assert r.json()["deactivated_at"] is not None

    # Signing in reads the same as a wrong password.
    res = client.post(
        "/api/v1/auth/login", json={"email": "member@test.internal", "password": MEMBER_PASSWORD}
    )
    assert res.status_code == 401
    assert res.json()["detail"] == "Invalid credentials"
    # A token issued before is refused on its next use, not when it runs out.
    res = client.get("/api/v1/auth/me", headers=bearer)
    assert res.status_code == 401
    assert res.json()["detail"] == "Account deactivated"
    res = client.post("/api/v1/auth/refresh", json={"refresh_token": member["refresh_token"]})
    assert res.status_code == 401


def test_a_refresh_looks_at_the_account_as_well_as_the_token(client, db, seed_users):
    """The route drops every refresh token, and the refresh checks regardless."""
    member = _member_login(client)
    _mark_deactivated(db, "STU001")
    res = client.post("/api/v1/auth/refresh", json={"refresh_token": member["refresh_token"]})
    assert res.status_code == 401


def test_a_key_bound_to_the_account_is_deleted_and_stays_gone(client, db, seed_users, kiosk_key):
    """A held key came back with the account, having answered to nobody in between."""
    admin = _admin(client)
    assert client.get("/api/v1/guest/directory", headers=kiosk_key).status_code == 200

    assert _deactivate(client, admin, "KIOSK01").status_code == 200
    res = client.get("/api/v1/guest/directory", headers=kiosk_key)
    assert res.status_code == 401
    assert res.json()["detail"] == "Invalid API key"
    db.expire_all()
    assert db.query(ApiKey).filter(ApiKey.user_id == "KIOSK01").count() == 0

    # Coming back does not bring the key with it. A new one is issued, and works.
    assert _reactivate(client, admin, "KIOSK01").status_code == 200
    assert client.get("/api/v1/guest/directory", headers=kiosk_key).status_code == 401
    issued = client.post(
        "/api/v1/api-keys/", json={"label": "Lobby kiosk", "user_id": "KIOSK01"}, headers=admin
    )
    assert issued.status_code == 201, issued.text
    fresh = {"X-API-Key": issued.json()["api_key"]}
    assert client.get("/api/v1/guest/directory", headers=fresh).status_code == 200


def test_the_calendar_feed_stops_and_comes_back_under_a_new_url(client, db, seed_users):
    admin = _admin(client)
    before = _feed_token(db, "FAC001")
    assert client.get(f"/api/v1/sync/user-feed/{before}.ics").status_code == 200

    first = _deactivate(client, admin, "FAC001")
    assert first.status_code == 200
    rotated = _feed_token(db, "FAC001")
    assert rotated != before
    assert client.get(f"/api/v1/sync/user-feed/{before}.ics").status_code == 404
    assert client.get(f"/api/v1/sync/user-feed/{rotated}.ics").status_code == 404

    # A second call changes nothing, the token included.
    again = _deactivate(client, admin, "FAC001")
    assert again.status_code == 200
    assert again.json()["deactivated_at"] == first.json()["deactivated_at"]
    assert _feed_token(db, "FAC001") == rotated

    assert _reactivate(client, admin, "FAC001").status_code == 200
    assert client.get(f"/api/v1/sync/user-feed/{before}.ics").status_code == 404
    assert client.get(f"/api/v1/sync/user-feed/{rotated}.ics").status_code == 200


def test_reactivating_lets_the_old_password_back_in(client, db, seed_users):
    admin = _admin(client)
    assert _deactivate(client, admin, "STU001").status_code == 200

    r = _reactivate(client, admin, "STU001")
    assert r.status_code == 200
    assert r.json()["deactivated_at"] is None
    login(client, "member@test.internal", MEMBER_PASSWORD)
    # Reactivating an active account changes nothing.
    assert _reactivate(client, admin, "STU001").status_code == 200


def test_the_address_stays_taken_until_it_is_changed_on_the_old_account(client, db, seed_users):
    """Deactivating can be undone, so the account keeps its address until an admin moves it."""
    admin = _admin(client)
    assert _deactivate(client, admin, "STU001").status_code == 200
    newcomer = {
        "id": "STU777",
        "full_name": "New Member",
        "email_address": "member@test.internal",
        "password": MEMBER_PASSWORD,
        "role_type": "MEMBER",
        "unit_code": "CSE",
    }
    taken = client.post("/api/v1/users/", json=newcomer, headers=admin)
    assert taken.status_code == 409
    assert taken.json()["detail"] == "Email already registered"

    moved = client.patch(
        "/api/v1/users/STU001", json={"email_address": "stu001.left@test.internal"}, headers=admin
    )
    assert moved.status_code == 200, moved.text
    assert moved.json()["deactivated_at"] is not None
    assert client.post("/api/v1/users/", json=newcomer, headers=admin).status_code == 201


# -- Who may do it ------------------------------------------------------------


def test_nobody_deactivates_their_own_account(client, seed_users):
    r = _deactivate(client, _admin(client), "ADM001")
    assert r.status_code == 422
    assert r.json()["detail"] == "You cannot deactivate your own account"


def test_a_unit_admin_is_held_to_their_unit_and_to_non_admins(client, db, seed_users):
    _seed_unit_world(db)
    headers = _unit_admin(client)
    assert _deactivate(client, headers, "ADM001").status_code == 403
    assert _deactivate(client, headers, "STU900").status_code == 403
    assert _reactivate(client, headers, "STU900").status_code == 403
    assert _deactivate(client, headers, "STU001").status_code == 200
    assert _reactivate(client, headers, "STU001").status_code == 200


def test_staff_cannot_deactivate_anybody(client, seed_users):
    headers = login(client, "staff@test.internal", STAFF_PASSWORD)
    assert _deactivate(client, headers, "STU001").status_code == 403


def test_an_unknown_account_is_404(client, seed_users):
    assert _deactivate(client, _admin(client), "NOBODY").status_code == 404


# -- The lists people are picked from ------------------------------------------


def test_the_user_list_leaves_them_out_unless_asked(client, db, seed_users):
    admin = _admin(client)
    assert _deactivate(client, admin, "STU001").status_code == 200

    listed = client.get("/api/v1/users/", headers=admin).json()
    assert "STU001" not in [u["id"] for u in listed]
    everyone = client.get("/api/v1/users/", params={"include_deactivated": "true"}, headers=admin)
    assert "STU001" in [u["id"] for u in everyone.json()]
    # History still resolves the account by its id.
    one = client.get("/api/v1/users/STU001", headers=admin)
    assert one.status_code == 200
    assert one.json()["deactivated_at"] is not None


def test_the_staff_lists_leave_them_out(client, db, seed_users, kiosk_key, monkeypatch):
    monkeypatch.setattr("app.api.v1.endpoints.schedule.get_redis", lambda: _FakeRedis())
    admin = _admin(client)
    assert _deactivate(client, admin, "FAC001").status_code == 200

    available = client.get("/api/v1/users/staff/available", headers=admin).json()
    assert "FAC001" not in [s["id"] for s in available]
    directory = client.get("/api/v1/guest/directory", headers=kiosk_key).json()
    assert "FAC001" not in [s["staff_id"] for s in directory]
    assert client.get("/api/v1/schedule/staff/all/locations", headers=admin).json() == []
    res = client.get("/api/v1/schedule/staff/FAC001/location", headers=admin)
    assert res.status_code == 404


def test_a_guest_cannot_be_sent_to_them(client, db, seed_users, kiosk_key):
    _mark_deactivated(db, "FAC001")
    res = client.post("/api/v1/guest/register-checkin", json=_GUEST, headers=kiosk_key)
    assert res.status_code == 404


def test_they_cannot_be_named_as_a_manager(client, db, seed_users):
    _mark_deactivated(db, "FAC001")
    res = client.patch(
        "/api/v1/users/STU001", json={"reporting_line_manager": "FAC001"}, headers=_admin(client)
    )
    assert res.status_code == 422
    assert res.json()["detail"] == "Manager is deactivated"


def test_an_absence_is_not_sent_to_a_manager_who_has_left(client, db, seed_users):
    seed_users["staff"].reporting_line_manager = "ADM001"
    db.commit()
    headers = login(client, "staff@test.internal", STAFF_PASSWORD)
    _mark_deactivated(db, "ADM001")

    res = client.post(
        "/api/v1/attendance/absence",
        json={"target_absence_date": str(org_today()), "context_justification": "Conference"},
        headers=headers,
    )
    assert res.status_code == 400


def test_no_new_key_is_issued_to_them(client, db, seed_users):
    _mark_deactivated(db, "FAC001")
    res = client.post(
        "/api/v1/api-keys/", json={"label": "Left", "user_id": "FAC001"}, headers=_admin(client)
    )
    assert res.status_code == 409


# -- What they leave behind -----------------------------------------------------


def _request(db, submitter, approver="FAC001", state=LogVerificationState.PENDING_VERIFICATION):
    """An absence request already sent, straight into the table."""
    log = ReverseRsvpLog(
        submitting_user_id=submitter,
        target_absence_date=org_today(),
        context_justification="Conference",
        approval_state=state,
        authorized_by_user_id=approver,
    )
    db.add(log)
    db.commit()
    return log.id


def _pending_ids(client, headers):
    res = client.get("/api/v1/attendance/absence/pending", headers=headers)
    assert res.status_code == 200, res.text
    return {row["id"] for row in res.json()}


def _decide(client, headers, log_id, decision="VERIFIED_APPROVED"):
    url = f"/api/v1/attendance/absence/{log_id}/decide"
    return client.patch(url, json={"decision": decision}, headers=headers)


def test_an_admin_decides_a_request_left_with_a_manager_who_has_gone(client, db, seed_users):
    """It waited on somebody who could no longer sign in, and nothing moved it on."""
    log_id = _request(db, "STU001")
    admin = _admin(client)
    # While the manager is there, the request is theirs alone.
    assert log_id not in _pending_ids(client, admin)
    assert _decide(client, admin, log_id).status_code == 404

    r = _deactivate(client, admin, "FAC001")
    assert r.status_code == 200, r.text
    assert r.json()["open_items"]["pending_absence_requests"] == 1
    assert log_id in _pending_ids(client, admin)
    assert _decide(client, admin, log_id).status_code == 200
    db.expire_all()
    log = db.get(ReverseRsvpLog, log_id)
    assert log.approval_state == LogVerificationState.VERIFIED_APPROVED
    assert log.authorized_by_user_id == "ADM001"
    # The decision is the admin's now, and theirs to revisit.
    assert _decide(client, admin, log_id, "VERIFIED_DENIED").status_code == 200
    again = _deactivate(client, admin, "FAC001")
    assert again.json()["open_items"]["pending_absence_requests"] == 0


def test_a_unit_admin_decides_those_from_their_own_unit(client, db, seed_users):
    _seed_unit_world(db)
    own_unit = _request(db, "STU001")
    other_unit = _request(db, "STU900")
    an_admins = _request(db, "DAD001")
    _mark_deactivated(db, "FAC001")

    unit_admin = _unit_admin(client)
    assert _pending_ids(client, unit_admin) == {own_unit}
    assert _decide(client, unit_admin, other_unit).status_code == 404
    assert _decide(client, unit_admin, an_admins).status_code == 404
    assert _decide(client, unit_admin, own_unit).status_code == 200
    # A super admin reaches the rest, the unit admin's own included.
    assert _pending_ids(client, _admin(client)) == {other_unit, an_admins}


def test_nobody_decides_their_own_and_a_member_decides_none(client, db, seed_users):
    their_own = _request(db, "ADM001")
    # The approver column is SET NULL, so a manager removed outright leaves nobody.
    unrouted = _request(db, "STU001", approver=None)
    _mark_deactivated(db, "FAC001")

    admin = _admin(client)
    assert _pending_ids(client, admin) == {unrouted}
    assert _decide(client, admin, their_own).status_code == 404
    member = login(client, "member@test.internal", MEMBER_PASSWORD)
    assert _pending_ids(client, member) == set()
    assert _decide(client, member, unrouted).status_code == 404


def test_the_response_counts_what_is_left_to_hand_over(client, db, seed_users):
    offerings, ledgers = _seed_unit_world(db)
    today = org_today()
    ended = PlanningCycle(
        cycle_label="Ended",
        date_bounds_start=today - timedelta(days=200),
        date_bounds_end=today - timedelta(days=31),
        operational_status=True,
    )
    db.add(ended)
    db.flush()
    old = Activity(
        activity_code="CS100", activity_title="Ended Activity", unit_code="CSE", cycle_id=ended.id
    )
    db.add(old)
    db.flush()
    # A slot in the running cycle counts; one in a cycle that has ended does not.
    for activity_id in (offerings["CSE"].id, old.id):
        db.add(
            StructuralMasterSlot(
                day_of_week_index=3,
                time_window_start=time(14),
                time_window_end=time(15),
                activity_id=activity_id,
                primary_lead_id="FAC001",
            )
        )
    # Today's rows count whether it leads or covers; yesterday's does not.
    ledgers["CSE"].active_lead_id = "FAC001"
    ledgers["ECE"].substitute_lead_id = "FAC001"
    db.add(
        DailyLedger(
            target_date=today - timedelta(days=1),
            activity_id=offerings["CSE"].id,
            active_lead_id="FAC001",
        )
    )
    # A report who has also left is nobody's to reassign.
    seed_users["member"].reporting_line_manager = "FAC001"
    db.query(User).filter(User.id == "STU900").update(
        {"reporting_line_manager": "FAC001", "deactivated_at": datetime.now(UTC)}
    )
    db.commit()
    _request(db, "STU001")
    _request(db, "STU900", state=LogVerificationState.VERIFIED_APPROVED)

    admin = _admin(client)
    first = _deactivate(client, admin, "FAC001")
    assert first.status_code == 200, first.text
    assert first.json()["open_items"] == {
        "pending_absence_requests": 1,
        "direct_reports": 1,
        "slots_led": 1,
        "ledger_rows_ahead": 2,
    }
    # The handover goes through the usual routes, and calling again counts afresh.
    moved = client.patch(
        "/api/v1/users/STU001", json={"reporting_line_manager": "ADM001"}, headers=admin
    )
    assert moved.status_code == 200, moved.text
    again = _deactivate(client, admin, "FAC001")
    assert again.json()["open_items"]["direct_reports"] == 0
    assert again.json()["deactivated_at"] == first.json()["deactivated_at"]


# -- Leads and substitutes ------------------------------------------------------


def _slot_body(activity_id, lead_id):
    return {
        "day_of_week_index": 3,
        "time_window_start": "14:00:00",
        "time_window_end": "15:00:00",
        "activity_id": activity_id,
        "primary_lead_id": lead_id,
        "target_room_identifier": "LAB-4",
    }


def test_a_new_slot_needs_a_lead_who_exists_and_has_not_left(client, db, seed_users):
    """An unknown id used to reach the foreign key: a 500 on PostgreSQL."""
    offerings, _ = _seed_unit_world(db)
    admin = _admin(client)
    body = _slot_body(offerings["CSE"].id, "NOBODY")
    r = client.post("/api/v1/schedule/slots", json=body, headers=admin)
    assert r.status_code == 404
    assert r.json()["detail"] == "Lead not found"

    _mark_deactivated(db, "FAC001")
    body = _slot_body(offerings["CSE"].id, "FAC001")
    r = client.post("/api/v1/schedule/slots", json=body, headers=admin)
    assert r.status_code == 422
    assert r.json()["detail"] == "Lead is deactivated"


def test_a_slot_cannot_be_handed_to_a_lead_who_has_left(client, db, seed_users):
    offerings, _ = _seed_unit_world(db)
    admin = _admin(client)
    body = _slot_body(offerings["CSE"].id, None)
    created = client.post("/api/v1/schedule/slots", json=body, headers=admin)
    assert created.status_code == 200, created.text
    url = f"/api/v1/schedule/slots/{created.json()['id']}"

    _mark_deactivated(db, "FAC001")
    r = client.patch(url, json={"primary_lead_id": "FAC001"}, headers=admin)
    assert r.status_code == 422
    assert r.json()["detail"] == "Lead is deactivated"
    r = client.patch(url, json={"primary_lead_id": "NOBODY"}, headers=admin)
    assert r.status_code == 404
    assert r.json()["detail"] == "Lead not found"


def test_a_day_cannot_be_covered_by_somebody_who_has_left(client, db, seed_users):
    _, ledgers = _seed_unit_world(db)
    _mark_deactivated(db, "FAC001")
    r = _patch(client, ledgers["CSE"].id, substitute_lead_id="FAC001")
    assert r.status_code == 422
    assert r.json()["detail"] == "Substitute is deactivated"


# -- The CSV import -------------------------------------------------------------


def test_an_import_refuses_a_member_who_has_left(client, db, seed_users):
    cycle = _make_cycle(db)
    _mark_deactivated(db, "STU001")
    csv_text = (
        HEADER + "\n"
        "STU001,Member One,member@test.internal,MA201,Linear Algebra,CSE,2,09:00,10:00,FAC001,LH-201\n"
    )
    r = _upload(client, _admin(client), cycle.id, csv_text)
    assert r.status_code == 422
    assert "member 'STU001' is deactivated" in r.json()["detail"]


def test_an_import_refuses_a_lead_who_has_left(client, db, seed_users):
    cycle = _make_cycle(db)
    _mark_deactivated(db, "FAC001")
    csv_text = (
        HEADER + "\n"
        "STU900,Ada Newling,ada@test.internal,MA201,Linear Algebra,CSE,2,09:00,10:00,FAC001,LH-201\n"
    )
    r = _upload(client, _admin(client), cycle.id, csv_text)
    assert r.status_code == 422
    assert "lead 'FAC001' is deactivated" in r.json()["detail"]
    # The whole file is rolled back, so the member it would have created is not.
    db.expire_all()
    assert db.query(User).filter(User.id == "STU900").first() is None


# -- Sockets --------------------------------------------------------------------


def test_a_socket_is_refused_to_a_deactivated_account(client, db, seed_users):
    token = _access_token(client, "member@test.internal", MEMBER_PASSWORD)
    _mark_deactivated(db, "STU001")
    with client.websocket_connect(WS_PATH) as socket:
        _auth(socket, token)
        assert _refusal_code(socket) == ws_module.CLOSE_UNAUTHENTICATED
    assert not socket_broker.is_online("STU001")


def test_deactivating_closes_a_socket_already_open(client, db, seed_users):
    admin = _admin(client)
    token = _access_token(client, "member@test.internal", MEMBER_PASSWORD)
    with client.websocket_connect(WS_PATH) as socket:
        _auth(socket, token)
        assert socket.receive_json() == {"event": "AUTHENTICATED", "payload": {}}
        assert _deactivate(client, admin, "STU001").status_code == 200
        assert _refusal_code(socket) == ws_module.CLOSE_UNAUTHENTICATED
    assert not socket_broker.is_online("STU001")


class _Socket:
    def __init__(self, fails=False):
        self.fails = fails
        self.closed_with = None

    async def close(self, code):
        if self.fails:
            raise RuntimeError("the other end already went")
        self.closed_with = code


def test_close_session_closes_the_socket_and_forgets_it():
    broker = OrganizationConnectionManager()
    socket = _Socket()
    broker.register_session("STU001", socket)
    asyncio.run(broker.close_session("STU001", ws_module.CLOSE_UNAUTHENTICATED))
    assert socket.closed_with == ws_module.CLOSE_UNAUTHENTICATED
    assert not broker.is_online("STU001")


def test_close_session_shrugs_off_a_socket_that_is_already_gone():
    broker = OrganizationConnectionManager()
    broker.register_session("STU001", _Socket(fails=True))
    asyncio.run(broker.close_session("STU001", ws_module.CLOSE_UNAUTHENTICATED))
    assert not broker.is_online("STU001")
    # Nobody connected is nothing to do.
    asyncio.run(broker.close_session("NOBODY", ws_module.CLOSE_UNAUTHENTICATED))
