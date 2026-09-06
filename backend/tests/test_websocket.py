# Copyright 2026 Chronos Ledger Contributors
# Licensed under the Apache License, Version 2.0

import asyncio

import pytest
from starlette.websockets import WebSocketDisconnect

from app.core.websocket_manager import CampusConnectionManager, socket_broker
from tests.conftest import STUDENT_PASSWORD


def _token(client):
    res = client.post(
        "/api/v1/auth/login",
        json={"email": "student@test.internal", "password": STUDENT_PASSWORD},
    )
    assert res.status_code == 200
    return res.json()["access_token"]


def test_ws_rejects_invalid_token(client):
    with (
        pytest.raises(WebSocketDisconnect),
        client.websocket_connect("/api/v1/ws?token=not-a-token"),
    ):
        pass


def test_ws_accepts_valid_token(client, seed_users):
    token = _token(client)
    with client.websocket_connect(f"/api/v1/ws?token={token}"):
        assert socket_broker.is_online("STU001")
    assert not socket_broker.is_online("STU001")


def test_stale_close_does_not_evict_reconnected_socket():
    class FakeSocket:
        async def accept(self):
            pass

    async def scenario():
        broker = CampusConnectionManager()
        first, second = FakeSocket(), FakeSocket()
        await broker.establish_session("U1", first)
        # A reconnect replaces the stored socket for the same user.
        await broker.establish_session("U1", second)
        # The stale connection closing must not evict the replacement.
        broker.terminate_session("U1", first)
        assert broker.is_online("U1")
        broker.terminate_session("U1", second)
        assert not broker.is_online("U1")

    asyncio.run(scenario())
