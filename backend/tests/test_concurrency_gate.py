# Copyright 2026 Chronos Ledger Contributors
# Licensed under the Apache License, Version 2.0
"""Past the cap, API requests get a 503 instead of queueing for a connection."""

import asyncio

import httpx
from fastapi import FastAPI

from app.core.concurrency import ConcurrencyGate


def _app(release: asyncio.Event) -> FastAPI:
    app = FastAPI()

    @app.get("/api/slow")
    async def slow():
        await release.wait()
        return {"ok": True}

    @app.get("/health")
    async def health():
        return {"ok": True}

    app.add_middleware(ConcurrencyGate, limit=1, wait_seconds=0.2)
    return app


def test_request_past_the_cap_gets_503_and_health_still_answers():
    async def scenario():
        release = asyncio.Event()
        transport = httpx.ASGITransport(app=_app(release))
        async with httpx.AsyncClient(transport=transport, base_url="http://t") as client:
            first = asyncio.create_task(client.get("/api/slow"))
            await asyncio.sleep(0.05)
            second = await client.get("/api/slow")
            health = await client.get("/health")
            release.set()
            return (await first), second, health

    first, second, health = asyncio.run(scenario())
    assert second.status_code == 503
    assert second.headers["retry-after"] == "1"
    assert health.status_code == 200
    assert first.status_code == 200


def test_slot_is_released_after_each_request():
    async def scenario():
        release = asyncio.Event()
        release.set()
        transport = httpx.ASGITransport(app=_app(release))
        async with httpx.AsyncClient(transport=transport, base_url="http://t") as client:
            return [(await client.get("/api/slow")).status_code for _ in range(3)]

    assert asyncio.run(scenario()) == [200, 200, 200]
