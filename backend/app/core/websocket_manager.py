# Copyright 2026 Chronos Ledger Contributors
# Licensed under the Apache License, Version 2.0

import json

from fastapi import WebSocket


class CampusConnectionManager:
    def __init__(self):
        self.active_sockets: dict[str, WebSocket] = {}

    async def establish_session(self, user_id: str, websocket: WebSocket):
        await websocket.accept()
        self.active_sockets[user_id] = websocket

    def terminate_session(self, user_id: str):
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


socket_broker = CampusConnectionManager()
