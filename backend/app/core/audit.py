# Copyright 2026 Chronos Ledger Contributors
# Licensed under the Apache License, Version 2.0
"""Recording every write made through the API.

A plain ASGI middleware rather than a dependency, so a route cannot be added
without being covered, and a request refused before any route runs (a bad
token, a key outside its scope) is still recorded. The caller is whatever the
security dependencies found: they put the account and the key on the
request's state, which this reads once the response has gone out.

The record is written after the response, in its own session, and a failure
to write it is logged and nothing more. An audit table that is down should
not take every write in the application down with it.
"""

import logging
from datetime import UTC, datetime

from starlette.concurrency import run_in_threadpool

from app.core.database import get_session_opener

logger = logging.getLogger(__name__)

READ_METHODS = frozenset({"GET", "HEAD", "OPTIONS"})
AUDITED_PREFIX = "/api/v1/"


class AuditMiddleware:
    def __init__(self, app):
        self.app = app

    async def __call__(self, scope, receive, send):
        if (
            scope["type"] != "http"
            or scope["method"] in READ_METHODS
            or not scope["path"].startswith(AUDITED_PREFIX)
        ):
            await self.app(scope, receive, send)
            return

        status = {}

        async def send_and_note_status(message):
            if message["type"] == "http.response.start":
                status["code"] = message["status"]
            await send(message)

        try:
            await self.app(scope, receive, send_and_note_status)
        finally:
            state = scope.get("state") or {}
            await run_in_threadpool(
                _write,
                scope,
                state.get("actor_id"),
                state.get("api_key_id"),
                status.get("code", 500),
            )


def _write(scope, actor_id, api_key_id, status_code):
    from app.models.db import AuditRecord

    # The opener the tests substitute for the websocket is the one used here,
    # so a test run writes to the test database and not the configured one.
    app = scope.get("app")
    overrides = getattr(app, "dependency_overrides", {}) if app is not None else {}
    opener = overrides.get(get_session_opener, get_session_opener)()
    try:
        with opener() as db:
            db.add(
                AuditRecord(
                    at=datetime.now(UTC),
                    actor_id=actor_id,
                    api_key_id=api_key_id,
                    method=scope["method"],
                    path=scope["path"][:500],
                    status_code=status_code,
                )
            )
            db.commit()
    except Exception:
        logger.exception("Could not record %s %s in the audit log", scope["method"], scope["path"])
