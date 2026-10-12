# Copyright 2026 Chronos Ledger Contributors
# Licensed under the Apache License, Version 2.0

from fastapi import APIRouter

from app.api.v1.endpoints import (
    api_keys,
    attendance,
    audit,
    auth,
    calendar_sync,
    changes,
    federation,
    guest,
    ingestion,
    org_config,
    resources,
    schedule,
    users,
    websocket,
)

# Every router under /api/v1, with its prefix and tag. One table rather than
# a list of include_router calls so another assembly of the same routes
# (app.embedded, which leaves some out) cannot drift from this one.
ROUTERS = (
    (org_config.router, "/config", "Configuration"),
    (auth.router, "/auth", "Authentication"),
    (api_keys.router, "/api-keys", "API Keys"),
    (users.router, "/users", "Users"),
    (resources.router, "/resources", "Resources"),
    (schedule.router, "/schedule", "Schedule"),
    (attendance.router, "/attendance", "Attendance"),
    (guest.router, "/guest", "Guest Gate"),
    (ingestion.router, "/ingestion", "Data Ingestion"),
    (websocket.router, "", "WebSocket"),
    (calendar_sync.router, "/sync", "Calendar Sync"),
    (audit.router, "/audit", "Audit"),
    (changes.router, "/changes", "Changes"),
    (federation.router, "/federation", "Federation"),
)

api_router = APIRouter()
for router, prefix, tag in ROUTERS:
    api_router.include_router(router, prefix=prefix, tags=[tag])
