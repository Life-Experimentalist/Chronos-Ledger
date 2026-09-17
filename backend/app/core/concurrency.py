# Copyright 2026 Chronos Ledger Contributors
# Licensed under the Apache License, Version 2.0
"""Caps how many API requests one process works on at a time.

Handlers run in a thread pool and each one holds a database connection from
the pool. When more requests arrive than the pool has connections, threads
sit in pool checkout while holding threadpool slots that other requests need
to give their connections back, and the process can stop answering for many
minutes. Past the cap, requests wait here on the event loop, where waiting
costs nothing, and get a 503 if no slot frees up in time.
"""

import asyncio
import json


class ConcurrencyGate:
    def __init__(self, app, limit: int, wait_seconds: float = 10.0, prefix: str = "/api/"):
        self.app = app
        self.limit = limit
        self.wait_seconds = wait_seconds
        self.prefix = prefix
        self._slots = asyncio.Semaphore(limit)

    async def __call__(self, scope, receive, send):
        if scope["type"] != "http" or not scope["path"].startswith(self.prefix):
            await self.app(scope, receive, send)
            return
        try:
            await asyncio.wait_for(self._slots.acquire(), self.wait_seconds)
        except TimeoutError:
            await _busy(send)
            return
        try:
            await self.app(scope, receive, send)
        finally:
            self._slots.release()


async def _busy(send):
    body = json.dumps({"detail": "Server busy, try again shortly."}).encode()
    await send(
        {
            "type": "http.response.start",
            "status": 503,
            "headers": [
                (b"content-type", b"application/json"),
                (b"content-length", str(len(body)).encode()),
                (b"retry-after", b"1"),
            ],
        }
    )
    await send({"type": "http.response.body", "body": body})
