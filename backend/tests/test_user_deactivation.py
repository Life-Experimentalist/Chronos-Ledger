# Copyright 2026 Chronos Ledger Contributors
# Licensed under the Apache License, Version 2.0
"""H-21: somebody who leaves is deactivated, not deleted.

Deleting a user took the attendance recorded against them, and there was no
other way to stop an account. Deactivating keeps every record, closes every
way in, and takes the account out of the lists people are picked from.
"""

import asyncio
from datetime import UTC, datetime

from app.api.v1.endpoints import websocket as ws_module
from app.core.time import org_today
from app.core.websocket_manager import OrganizationConnectionManager, socket_broker
from app.models.db import User
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


def test_a_key_bound_to_the_account_is_held_and_comes_back(client, db, seed_users, kiosk_key):
    admin = _admin(client)
    assert client.get("/api/v1/guest/directory", headers=kiosk_key).status_code == 200

    assert _deactivate(client, admin, "KIOSK01").status_code == 200
    res = client.get("/api/v1/guest/directory", headers=kiosk_key)
    assert res.status_code == 401
    assert res.json()["detail"] == "Account deactivated"

    assert _reactivate(client, admin, "KIOSK01").status_code == 200
    assert client.get("/api/v1/guest/directory", headers=kiosk_key).status_code == 200


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
