# Copyright 2026 Chronos Ledger Contributors
# Licensed under the Apache License, Version 2.0
"""Every HTTP route is a plain def.

The database session is synchronous. FastAPI runs a plain def route on a
worker thread, but an async def route runs on the event loop, so every query
in one holds every other request and socket until it returns. A route that
has something to await, a socket notice say, hands it to BackgroundTasks.
"""

import inspect

from fastapi.routing import APIRoute

from app.main import app


def test_no_http_route_runs_on_the_event_loop():
    offenders = [
        f"{','.join(sorted(route.methods))} {route.path}"
        for route in app.routes
        if isinstance(route, APIRoute) and inspect.iscoroutinefunction(route.endpoint)
    ]
    assert offenders == []
