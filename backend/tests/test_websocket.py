# Copyright 2026 Chronos Ledger Contributors
# Licensed under the Apache License, Version 2.0
"""Who gets a socket, and what it takes to get one.

M-13, M-14 and M-15: the token arrived in the connect URL, a valid signature
was the only thing checked about it, and the connected-user count was public.
"""

import asyncio

import pytest
from starlette.websockets import WebSocketDisconnect

from app.api.v1.endpoints import websocket as ws_module
from app.core.security import hash_password
from app.core.websocket_manager import OrganizationConnectionManager, socket_broker
from app.models.db import InstitutionalRole, User
from tests.conftest import ADMIN_PASSWORD, MEMBER_PASSWORD, login

WS_PATH = "/api/v1/ws"
STATS_PATH = "/api/v1/ws/stats"
FRESH_ADMIN_PASSWORD = "FreshAdmin123!"
_FRESH_ADMIN_HASH = hash_password(FRESH_ADMIN_PASSWORD)


def _access_token(client, email, password):
    res = client.post("/api/v1/auth/login", json={"email": email, "password": password})
    assert res.status_code == 200, res.text
    return res.json()["access_token"]


def _auth(socket, token):
    socket.send_json({"event": "AUTH", "payload": {"token": token}})


def _refusal_code(socket):
    """The code the server closed with, once it had read the first frame.

    A refusal is no longer a failed handshake. The socket is accepted so the
    token has somewhere to travel, so the close surfaces on the next read
    rather than out of websocket_connect itself.
    """
    with pytest.raises(WebSocketDisconnect) as disconnected:
        socket.receive_text()
    return disconnected.value.code


# -- Getting in ---------------------------------------------------------------


def test_a_valid_token_is_acknowledged_and_registered(client, seed_users):
    token = _access_token(client, "member@test.internal", MEMBER_PASSWORD)
    with client.websocket_connect(WS_PATH) as socket:
        _auth(socket, token)
        assert socket.receive_json() == {"event": "AUTHENTICATED", "payload": {}}
        assert socket_broker.is_online("STU001")
    assert not socket_broker.is_online("STU001")


def test_an_accepted_socket_is_nobody_until_it_says_so(client, seed_users):
    """The accept happens before the token arrives now, so this is the thing
    worth proving: being accepted is not being connected."""
    with client.websocket_connect(WS_PATH):
        assert asyncio.run(socket_broker.online_count()) == 0


def test_a_bad_token_is_refused(client, seed_users):
    with client.websocket_connect(WS_PATH) as socket:
        _auth(socket, "not-a-token")
        assert _refusal_code(socket) == ws_module.CLOSE_UNAUTHENTICATED


def test_a_first_frame_that_is_not_an_auth_frame_is_refused(client, seed_users):
    token = _access_token(client, "member@test.internal", MEMBER_PASSWORD)
    with client.websocket_connect(WS_PATH) as socket:
        socket.send_json({"event": "HELLO", "payload": {"token": token}})
        assert _refusal_code(socket) == ws_module.CLOSE_UNAUTHENTICATED


def test_a_first_frame_that_is_not_json_is_refused(client, seed_users):
    with client.websocket_connect(WS_PATH) as socket:
        socket.send_text("hello")
        assert _refusal_code(socket) == ws_module.CLOSE_UNAUTHENTICATED


def test_a_socket_that_never_says_anything_is_closed(client, seed_users, monkeypatch):
    """Without this an unauthenticated socket could sit there indefinitely,
    which is a cheaper thing to open than it is to hold."""
    monkeypatch.setattr(ws_module, "AUTH_FRAME_TIMEOUT_SECONDS", 0.05)
    with client.websocket_connect(WS_PATH) as socket:
        assert _refusal_code(socket) == ws_module.CLOSE_AUTH_TIMEOUT


# -- The account behind the token ---------------------------------------------


def test_a_token_for_a_user_who_is_gone_is_refused(client, db, seed_users):
    """The signature was the whole check, so a token outliving its account
    still opened a channel and kept receiving events."""
    token = _access_token(client, "member@test.internal", MEMBER_PASSWORD)
    db.query(User).filter(User.id == "STU001").delete()
    db.commit()

    with client.websocket_connect(WS_PATH) as socket:
        _auth(socket, token)
        assert _refusal_code(socket) == ws_module.CLOSE_UNAUTHENTICATED


def test_an_admin_still_on_the_seeded_password_is_refused(client, db, seed_users):
    """The HTTP side has refused this account everything but reading itself and
    changing its password since it was seeded. The socket handed it a live
    channel anyway."""
    db.add(
        User(
            id="ADM900",
            full_name="Fresh Admin",
            email_address="fresh.admin@test.internal",
            credential_secure_hash=_FRESH_ADMIN_HASH,
            role_type=InstitutionalRole.SUPER_ADMIN,
            initial_login_state=True,
        )
    )
    db.commit()
    token = _access_token(client, "fresh.admin@test.internal", FRESH_ADMIN_PASSWORD)

    with client.websocket_connect(WS_PATH) as socket:
        _auth(socket, token)
        assert _refusal_code(socket) == ws_module.CLOSE_UNAUTHENTICATED


# -- The connection count -----------------------------------------------------


def test_the_connection_count_is_not_public(client, seed_users):
    assert client.get(STATS_PATH).status_code == 401


def test_the_connection_count_is_refused_to_a_member(client, seed_users):
    headers = login(client, "member@test.internal", MEMBER_PASSWORD)
    assert client.get(STATS_PATH, headers=headers).status_code == 403


def test_the_connection_count_is_readable_by_a_super_admin(client, seed_users):
    headers = login(client, "admin@test.internal", ADMIN_PASSWORD)

    res = client.get(STATS_PATH, headers=headers)
    assert res.status_code == 200, res.text
    assert res.json() == {"online_connections": 0}


# -- The broker ---------------------------------------------------------------


def test_a_stale_close_does_not_evict_a_reconnected_socket():
    """register_session no longer accepts anything, so this needs nothing that
    behaves like a socket: the broker only ever compares identity."""
    broker = OrganizationConnectionManager()
    first, second = object(), object()
    broker.register_session("U1", first)
    broker.register_session("U1", second)

    broker.terminate_session("U1", first)
    assert broker.is_online("U1")
    broker.terminate_session("U1", second)
    assert not broker.is_online("U1")
