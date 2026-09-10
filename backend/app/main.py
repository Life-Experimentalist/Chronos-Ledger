# Copyright 2026 Chronos Ledger Contributors
# Licensed under the Apache License, Version 2.0

import logging
from contextlib import asynccontextmanager

from apscheduler.schedulers.asyncio import AsyncIOScheduler
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.middleware.gzip import GZipMiddleware

from app.api.v1.router import api_router
from app.core.bootstrap import apply_initial_admin_password
from app.core.config import docs_are_published, get_settings
from app.core.database import SessionLocal
from app.core.time import org_timezone, org_tomorrow
from app.cron.ledger_generator import generate_daily_ledger_entries

settings = get_settings()
# Pinned to the organization's zone, not the container's. Unpinned, "23:00"
# meant 23:00 UTC, which is 04:30 the next morning in Kolkata and lunchtime in
# Los Angeles, so the nightly job ran in the middle of the working day for
# half the world.
scheduler = AsyncIOScheduler(timezone=org_timezone())


@asynccontextmanager
async def lifespan(_app: FastAPI):
    _open_the_admin_account()
    # Schedule nightly ledger generation at 23:00
    scheduler.add_job(
        _run_ledger_generator,
        "cron",
        hour=23,
        minute=0,
        id="nightly_ledger_gen",
        replace_existing=True,
    )
    scheduler.start()
    yield
    scheduler.shutdown(wait=False)


def _open_the_admin_account():
    """Apply INITIAL_ADMIN_PASSWORD before the first request arrives.

    Here rather than in the migration because a migration cannot read the
    application's settings, and the container runs alembic before uvicorn
    binds, so by the time this runs the seeded row exists.

    Failures are logged and swallowed on purpose. Nothing here is load
    bearing for a running instance: the consequence of skipping it is that
    the administrator account keeps the password nobody knows, which the
    log then says. Refusing to boot instead would take out an app that
    could otherwise serve /health and tell somebody what is wrong.
    """
    db = SessionLocal()
    try:
        apply_initial_admin_password(db, settings.initial_admin_password)
    except Exception:
        logging.getLogger(__name__).exception(
            "Could not apply INITIAL_ADMIN_PASSWORD. The administrator account is unchanged."
        )
    finally:
        db.close()


def _run_ledger_generator():
    tomorrow = org_tomorrow()
    db = SessionLocal()
    try:
        generate_daily_ledger_entries(tomorrow, db)
    finally:
        db.close()


# Off in production unless DOCS_ENABLED says otherwise. All three go
# together: turning off the two viewers while leaving openapi_url up still
# publishes the entire surface as a document, which is the thing worth not
# publishing.
_docs_published = docs_are_published(settings)

app = FastAPI(
    title="Chronos Ledger API",
    description="Organization Schedule & Attendance Management System",
    version="0.10.0",  # x-release-please-version
    docs_url="/docs" if _docs_published else None,
    redoc_url="/redoc" if _docs_published else None,
    openapi_url="/openapi.json" if _docs_published else None,
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins_list,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)
app.add_middleware(GZipMiddleware, minimum_size=1000)

app.include_router(api_router, prefix="/api/v1")


@app.get("/health")
def health_check():
    return {"status": "healthy", "service": "chronos-ledger"}
