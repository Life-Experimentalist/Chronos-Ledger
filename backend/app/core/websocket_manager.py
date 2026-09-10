# Copyright 2026 Chronos Ledger Contributors
# Licensed under the Apache License, Version 2.0

import json

from fastapi import WebSocket


class OrganizationConnectionManager:
    def __init__(self):
        self.active_sockets: dict[str, WebSocket] = {}

    def register_session(self, user_id: str, websocket: WebSocket):
        """Take a socket that is already accepted and already identified.

        The accept used to happen here, which meant a socket was registered
        before anything had established who was on the other end of it. The
        route accepts now, because the token arrives in a frame after the
        handshake, and only calls this once that frame has checked out.
        """
        self.active_sockets[user_id] = websocket

    def terminate_session(self, user_id: str, websocket: WebSocket | None = None):
        # A reconnect replaces the stored socket; when the stale connection
        # then closes, it must not evict the replacement.
        if websocket is not None and self.active_sockets.get(user_id) is not websocket:
            return
        self.active_sockets.pop(user_id, None)

    async def forward_direct_message(self, recipient_id: str, event_type: str, data_payload: dict):
        websocket = self.active_sockets.get(recipient_id)
        if not websocket:
            return
        frame = json.dumps({"event": event_type, "payload": data_payload})
        try:
            await websocket.send_text(frame)
        except Exception:
            self.terminate_session(recipient_id)

    async def broadcast_global_event(self, event_type: str, data_payload: dict):
        frame = json.dumps({"event": event_type, "payload": data_payload})
        for user_id, websocket in list(self.active_sockets.items()):
            try:
                await websocket.send_text(frame)
            except Exception:
                self.terminate_session(user_id)

    def online_count(self) -> int:
        return len(self.active_sockets)

    def is_online(self, user_id: str) -> bool:
        return user_id in self.active_sockets


socket_broker = OrganizationConnectionManager()
