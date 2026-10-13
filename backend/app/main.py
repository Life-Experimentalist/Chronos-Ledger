# Copyright 2026 Chronos Ledger Contributors
# Licensed under the Apache License, Version 2.0

import asyncio
import logging
from contextlib import asynccontextmanager, suppress

import redis
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.middleware.gzip import GZipMiddleware
from fastapi.responses import JSONResponse
from sqlalchemy import text
from sqlalchemy.exc import TimeoutError as PoolTimeout

from app.api.v1.router import api_router
from app.core import clock
from app.core.audit import AuditMiddleware
from app.core.bootstrap import apply_initial_admin_password
from app.core.concurrency import ConcurrencyGate
from app.core.config import docs_are_published, get_settings
from app.core.database import POOL_CAPACITY, SessionLocal, engine, is_sqlite
from app.core.errors import ErrorCode, error_body, register_error_handlers
from app.core.idempotency import REPLAYED_HEADER, IdempotencyMiddleware
from app.core.pagination import TOTAL_COUNT_HEADER
from app.core.redis_client import get_redis, is_memory
from app.core.schema import SCHEMA_VERSION, ensure_schema
from app.core.time import org_timezone
from app.core.websocket_manager import socket_broker
from app.cron.scheduled import (
    NIGHTLY_LEDGER_HOUR,
    OVERSTAY_INTERVAL,
    announce_guest_overstays,
    catch_up_ledger,
    purge_guest_check_ins,
    purge_idempotency_records,
    purge_refresh_tokens,
    run_ledger_generator,
)

settings = get_settings()
# Pinned to the organization's zone, not the container's. Unpinned, "23:00"
# meant 23:00 UTC, which is 04:30 the next morning in Kolkata and lunchtime in
# Los Angeles, so the nightly job ran in the middle of the working day for
# half the world.
#
# A run that comes due while the process is busy still happens if it is under
# half an hour late, instead of being dropped after the one second APScheduler
# allows by default. Not a full hour: the ledger run works out tomorrow when
# it starts, and an hour after 23:00 tomorrow is a different date. The
# catch-up job is due the moment it is added, before the scheduler starts,
# so it leans on this as well.
scheduler = AsyncIOScheduler(timezone=org_timezone(), job_defaults={"misfire_grace_time": 1800})


@asynccontextmanager
async def lifespan(_app: FastAPI):
    # Before the admin account is opened, because on an empty database the
    # schema step is what puts that account there.
    logging.getLogger(__name__).info("Schema %s: %s", SCHEMA_VERSION, ensure_schema(engine))
    _open_the_admin_account()
    if is_memory(settings.redis_url):
        # Now rather than at the first rate-limited request, so a missing
        # standalone extra stops the process with a message instead of
        # failing sign-ins one at a time.
        get_redis()
    if clock.is_host():
        # A host clock moves only when the host says so, and the jobs run
        # from cron/scheduled.py::run_due_jobs as it moves. The catch-up still
        # happens once, so the day the clock starts in has its rows.
        catch_up_ledger()
    else:
        _start_the_scheduler()
    # Socket events and closes for people connected to another instance, and
    # the presence the connection count reads. Harmless with one instance, and
    # skipped where Redis is this process's own memory: there is only one
    # instance and nobody else to hear it.
    relay = None
    if not is_memory(settings.redis_url):
        relay = asyncio.create_task(socket_broker.run_relay(settings.redis_url))
    yield
    if scheduler.running:
        scheduler.shutdown(wait=False)
    if relay is not None:
        relay.cancel()
        with suppress(asyncio.CancelledError):
            await relay
    if is_sqlite(settings.database_url):
        _fold_the_write_ahead_log()


def _start_the_scheduler():
    # Schedule nightly ledger generation at 23:00
    scheduler.add_job(
        run_ledger_generator,
        "cron",
        hour=NIGHTLY_LEDGER_HOUR,
        minute=0,
        id="nightly_ledger_gen",
        replace_existing=True,
    )
    # Once, now: whatever the nightly job missed while this process was down.
    scheduler.add_job(catch_up_ledger, id="ledger_catch_up", replace_existing=True)
    # Daily, away from the ledger run.
    scheduler.add_job(
        purge_refresh_tokens,
        "cron",
        hour=3,
        minute=0,
        id="refresh_token_purge",
        replace_existing=True,
    )
    # Daily, after the token purge. Deletes nothing while GUEST_RETENTION_DAYS is 0.
    scheduler.add_job(
        purge_guest_check_ins,
        "cron",
        hour=3,
        minute=30,
        id="guest_retention_purge",
        replace_existing=True,
    )
    # Daily, after the visitor purge. Keys past IDEMPOTENCY_RETENTION_HOURS
    # are already treated as new; this only takes their rows away.
    scheduler.add_job(
        purge_idempotency_records,
        "cron",
        hour=3,
        minute=45,
        id="idempotency_purge",
        replace_existing=True,
    )
    # Often enough that a desk hears about an overstay while the visitor is
    # still in the building, seldom enough to be nothing on a database: it
    # reads the approved visits that have run over and not been announced,
    # which is a short list or an empty one. Announces nothing while
    # GUEST_VISIT_LENGTH_MINUTES is 0, since then no visit has an end.
    scheduler.add_job(
        announce_guest_overstays,
        "interval",
        seconds=int(OVERSTAY_INTERVAL.total_seconds()),
        id="guest_overstay_notice",
        replace_existing=True,
    )
    scheduler.start()


def _open_the_admin_account():
    """Apply INITIAL_ADMIN_PASSWORD before the first request arrives.

    Here rather than in the schema step because that step knows nothing of the
    application's settings, and it has already run, so the seeded row exists.

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


def _fold_the_write_ahead_log():
    """Leave one file behind on a clean stop, not three.

    In WAL mode recent commits sit in chronos.db-wal until a checkpoint moves
    them into the database. Folding them in on the way out means a copy of
    chronos.db alone is the whole data, which is what somebody copying the
    data directory by hand expects.
    """
    # On the driver's connection, not through SQLAlchemy: every transaction
    # here opens with BEGIN IMMEDIATE, and SQLite will not checkpoint from
    # inside one.
    try:
        connection = engine.raw_connection()
        try:
            connection.driver_connection.execute("PRAGMA wal_checkpoint(TRUNCATE)")
        finally:
            connection.close()
    except Exception:
        logging.getLogger(__name__).exception("Could not checkpoint the SQLite write-ahead log.")


# Off in production unless DOCS_ENABLED says otherwise. All three go
# together: turning off the two viewers while leaving openapi_url up still
# publishes the entire surface as a document, which is the thing worth not
# publishing.
_docs_published = docs_are_published(settings)

app = FastAPI(
    title="Chronos Ledger API",
    description="Organization Schedule & Attendance Management System",
    version="0.15.0",  # x-release-please-version
    docs_url="/docs" if _docs_published else None,
    redoc_url="/redoc" if _docs_published else None,
    openapi_url="/openapi.json" if _docs_published else None,
    lifespan=lifespan,
)

# Innermost, so it records a response before compression and CORS touch it.
app.add_middleware(IdempotencyMiddleware)
app.add_middleware(GZipMiddleware, minimum_size=1000)
app.add_middleware(AuditMiddleware)
# The last middleware added runs first. The gate wraps the audit write, which
# takes a connection of its own, and CORS wraps the gate, so a 503 still
# carries the headers a browser needs to read it.
app.add_middleware(ConcurrencyGate, limit=POOL_CAPACITY)
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins_list,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
    # A browser hides every response header outside a short safe list from
    # a cross-origin page unless it is named here.
    expose_headers=[TOTAL_COUNT_HEADER, REPLAYED_HEADER],
)

app.include_router(api_router, prefix="/api/v1")
register_error_handlers(app)


@app.exception_handler(PoolTimeout)
async def pool_exhausted(_request, _exc):
    return JSONResponse(
        status_code=503,
        headers={"Retry-After": "1"},
        content=error_body(ErrorCode.SERVER_BUSY, "Server busy, try again shortly."),
    )


@app.get("/health", operation_id="health.check")
async def health_check():
    return {
        "status": "healthy",
        "service": "chronos-ledger",
        "version": app.version,
        "schema_version": SCHEMA_VERSION,
    }


@app.get("/health/ready", operation_id="health.ready")
def readiness_check():
    """Whether this instance can serve requests: the database has to answer.

    Redis is pinged and reported, but it being down does not fail readiness.
    Everything that uses it falls back without it, so taking the app out of
    rotation over it would turn a degraded instance into a missing one. Under
    REDIS_URL=memory:// there is nothing to ping and it reports "memory".
    """
    try:
        with engine.connect() as connection:
            connection.execute(text("SELECT 1"))
        database = "ok"
    except Exception:
        logging.getLogger(__name__).exception("Readiness: the database did not answer.")
        database = "unavailable"
    if is_memory(settings.redis_url):
        cache = "memory"
    else:
        try:
            redis.from_url(settings.redis_url, socket_connect_timeout=1, socket_timeout=1).ping()
            cache = "ok"
        except Exception:
            cache = "unavailable"
    ready = database == "ok"
    return JSONResponse(
        status_code=200 if ready else 503,
        content={
            "status": "ready" if ready else "not ready",
            "database": database,
            "redis": cache,
        },
    )
