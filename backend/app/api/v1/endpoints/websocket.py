# Copyright 2026 Chronos Ledger Contributors
# Licensed under the Apache License, Version 2.0

from fastapi import APIRouter, WebSocket, WebSocketDisconnect, Query
from app.core.websocket_manager import socket_broker
from app.core.security import verify_jwt_token_string

router = APIRouter()


@router.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket, token: str = Query(...)):
    identity = verify_jwt_token_string(token)
    if not identity:
        await websocket.close(code=4003)
        return

    user_id = identity["sub"]
    await socket_broker.establish_session(user_id, websocket)

    try:
        while True:
            await websocket.receive_text()
    except WebSocketDisconnect:
        socket_broker.terminate_session(user_id)


@router.get("/ws/stats")
def ws_stats():
    return {"online_connections": socket_broker.online_count()}
