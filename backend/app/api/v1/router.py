# Copyright 2026 Chronos Ledger Contributors
# Licensed under the Apache License, Version 2.0

from fastapi import APIRouter

from app.api.v1.endpoints import (
    attendance,
    auth,
    calendar_sync,
    guest,
    ingestion,
    org_config,
    schedule,
    users,
    websocket,
)

api_router = APIRouter()

api_router.include_router(org_config.router, prefix="/config", tags=["Configuration"])
api_router.include_router(auth.router, prefix="/auth", tags=["Authentication"])
api_router.include_router(users.router, prefix="/users", tags=["Users"])
api_router.include_router(schedule.router, prefix="/schedule", tags=["Schedule"])
api_router.include_router(attendance.router, prefix="/attendance", tags=["Attendance"])
api_router.include_router(guest.router, prefix="/guest", tags=["Guest Gate"])
api_router.include_router(ingestion.router, prefix="/ingestion", tags=["Data Ingestion"])
api_router.include_router(websocket.router, tags=["WebSocket"])
api_router.include_router(calendar_sync.router, prefix="/sync", tags=["Calendar Sync"])
