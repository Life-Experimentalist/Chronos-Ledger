# Copyright 2026 Chronos Ledger Contributors
# Licensed under the Apache License, Version 2.0
"""The real-time channel, and how a socket proves who is on the other end.

The token used to arrive as ?token=<jwt> on the connect URL, which put a bearer
credential into the proxy's access log, the browser's history and any Referer
the page sent. It now arrives in the first frame after the handshake, where
none of those can see it.

A short-lived single-use ticket fetched over HTTP and exchanged here would also
have closed that hole. It wants an endpoint of its own plus a store with expiry
semantics every replica can see, for a credential that grants exactly the
authority of the token it was exchanged for. The frame needs none of that.
"""

import asyncio
import json

from fastapi import APIRouter, Depends, WebSocket, WebSocketDisconnect
from starlette.concurrency import run_in_threadpool

from app.core.database import get_session_opener
from app.core.security import first_login_blocks, require_roles, verify_jwt_token_string
from app.core.websocket_manager import socket_broker

router = APIRouter()

# How long a freshly accepted socket has to name itself. Not a setting: it is
# the shape of the handshake rather than a policy, the same way the rate
# limiter's windows are, and the only reason to raise it would be a client that
# is not sending the frame at all.
AUTH_FRAME_TIMEOUT_SECONDS = 5.0

# Close codes, from the 4000 range applications may use. A browser treats every
# close the same way (wait, reconnect), so these are for whoever reads a log and
# wonders why a client never arrived.
CLOSE_UNAUTHENTICATED = 4003
CLOSE_AUTH_TIMEOUT = 4008


def _token_from_frame(raw: str) -> str | None:
    """The token out of a frame shaped {"event": "AUTH", "payload": {...}}.

    The same envelope the server sends events in, so a client has one frame
    shape to know about rather than two.
    """
    try:
        frame = json.loads(raw)
    except ValueError:
        return None
    if not isinstance(frame, dict) or frame.get("event") != "AUTH":
        return None
    payload = frame.get("payload")
    if not isinstance(payload, dict):
        return None
    token = payload.get("token")
    return token if isinstance(token, str) and token else None


def _identify(open_session, token: str) -> str | None:
    """Whose socket this is, or None if that account may not connect.

    A valid signature used to be the whole check. This applies the three tests
    get_current_user applies as well: the account still exists, it has not
    been deactivated, and an admin who has never chosen a password of its own
    is not let past. Deactivating somebody also closes a socket they already
    have open, through socket_broker.close_session.

    Synchronous, and called through run_in_threadpool, because the ORM here is
    synchronous and the event loop should not wait on a database. The session
    is opened and closed around the lookup rather than taken as a dependency:
    FastAPI tears a yield dependency down when the handler returns, which on a
    socket is when the browser tab closes, so every open connection would hold
    one connection out of the pool for as long as it stayed open.
    """
    identity = verify_jwt_token_string(token)
    if not identity:
        return None
    user_id = identity.get("sub")
    if not user_id:
        return None

    from app.models.db import User

    with open_session() as db:
        user = db.query(User).filter(User.id == user_id).first()
        if not user or user.deactivated_at is not None or first_login_blocks(user):
            return None
        return user.id


@router.websocket("/ws")
async def websocket_endpoint(
    websocket: WebSocket,
    open_session=Depends(get_session_opener),
):
    """Accept, wait for one AUTH frame, and only then join the broker.

    Accepting first is what lets the token travel in a frame at all: a
    handshake refused before the accept has nowhere to carry one. Nothing is
    registered until that frame checks out, so an unauthenticated socket is
    never a possible recipient of anything.
    """
    await websocket.accept()
    try:
        first = await asyncio.wait_for(websocket.receive_text(), AUTH_FRAME_TIMEOUT_SECONDS)
    except TimeoutError:
        await websocket.close(code=CLOSE_AUTH_TIMEOUT)
        return
    except WebSocketDisconnect:
        return

    token = _token_from_frame(first)
    user_id = await run_in_threadpool(_identify, open_session, token) if token else None
    if not user_id:
        await websocket.close(code=CLOSE_UNAUTHENTICATED)
        return

    socket_broker.register_session(user_id, websocket)
    try:
        # A definite "you are in", so a client can tell an authenticated socket
        # from one that is about to be closed under it. Everything after this
        # frame travels server to client.
        await websocket.send_text(json.dumps({"event": "AUTHENTICATED", "payload": {}}))
        while True:
            await websocket.receive_text()
    except WebSocketDisconnect:
        pass
    finally:
        socket_broker.terminate_session(user_id, websocket)


@router.get("/ws/stats")
def ws_stats(_=Depends(require_roles("SUPER_ADMIN"))):
    """How many sockets are open right now.

    Unauthenticated, this told anybody how many people were signed in across
    the organization and let them watch that number over a day. SUPER_ADMIN
    rather than any admin because the count is org-wide, and there is nothing
    in it a unit admin could be shown only their own share of.
    """
    return {"online_connections": socket_broker.online_count()}
