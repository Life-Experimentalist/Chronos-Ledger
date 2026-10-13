# Copyright 2026 Chronos Ledger Contributors
# Licensed under the Apache License, Version 2.0
"""The embedded flavour: Chronos as a hidden child process of a host program.

The host (a hospital system, a campus system, a game) starts
`chronos-engine embedded`, reads one ready line from its stdout and talks to
it over loopback. Nobody visits it, nobody signs in to it: the host asserts
who is calling on every request (app.core.host_identity) and Chronos keeps
the schedule.

build_app assembles that application from the same routers (the table in
app.api.v1.router), middleware and lifespan as app.main, minus everything
that only makes sense with Chronos-owned logins. It is a separate FastAPI instance so the ordinary
application, which the published OpenAPI document describes route for route,
is untouched. STRIPPED_OPERATIONS is the list of what is left out, by
operation id, and docs/embedded.md explains each entry. CLOCK_OPERATIONS is
the one thing added: the clock routes (app.api.v1.endpoints.clock), which
only a host program has any business with.
"""

from fastapi import APIRouter, FastAPI
from fastapi.middleware.gzip import GZipMiddleware
from fastapi.routing import APIRoute
from sqlalchemy import text
from sqlalchemy.engine import Engine
from sqlalchemy.exc import TimeoutError as PoolTimeout
from sqlalchemy.orm import Session

import app.main as main
from app.api.v1.endpoints import clock as clock_endpoints
from app.api.v1.router import ROUTERS
from app.core import security
from app.core.audit import AuditMiddleware
from app.core.concurrency import ConcurrencyGate
from app.core.database import POOL_CAPACITY
from app.core.errors import register_error_handlers
from app.core.host_identity import (
    HostSecretMiddleware,
    check_host_secret,
    host_actor,
    seed_system_account,
)
from app.core.schema import ensure_schema

# Routes that exist for Chronos-owned credentials, which the embedded
# flavour has none of. Everything else in app.api.v1.router is mounted as it
# is, under the host's identity. The websocket (/ws) goes too: it
# authenticates with a JWT in its first frame, and there is no JWT.
STRIPPED_OPERATIONS = frozenset(
    {
        # Sessions and passwords.
        "auth.login",
        "auth.federated",
        "auth.refresh",
        "auth.logout",
        "auth.changePassword",
        "auth.getMe",
        # API keys are a second Chronos-owned credential.
        "apiKeys.create",
        "apiKeys.list",
        "apiKeys.revoke",
        # Accounts are made by the host asserting them, with no password.
        "users.create",
        "users.resetPassword",
        # Calendar feed tokens are a credential of their own, and the feed
        # they unlock is for a calendar program reaching the port, which a
        # hidden child process has no reason to allow.
        "sync.getFeedToken",
        "sync.rotateFeedToken",
        "sync.getFeed",
        # Federated sign-in is another way to get a Chronos session.
        "federation.createIssuer",
        "federation.listIssuers",
        "federation.updateIssuer",
        "federation.deleteIssuer",
        "federation.addKey",
        "federation.listKeys",
        "federation.retireKey",
        "federation.deleteKey",
        "federation.addRoleMapEntry",
        "federation.listRoleMap",
        "federation.deleteRoleMapEntry",
        "federation.createLink",
        "federation.listLinks",
        "federation.deleteLink",
        # Live updates ride the websocket, which is not mounted.
        "ws.getStats",
    }
)

# Routes the embedded flavour has and the ordinary application does not: the
# host clock (docs/clock.md), read by any actor and advanced by `system`.
CLOCK_OPERATIONS = frozenset({"clock.read", "clock.advance"})


def build_app(secret: str) -> FastAPI:
    """The embedded application, bound to one host secret."""
    # Starlette builds its middleware on the first request; the secret is
    # checked here so a bad one stops the process before it listens.
    check_host_secret(secret)
    embedded = FastAPI(
        title="Chronos Ledger (embedded)",
        version=main.app.version,
        docs_url=None,
        redoc_url=None,
        openapi_url=None,
        lifespan=main.lifespan,
    )
    # Innermost, so a refused request is still written to the audit log the
    # way a bad token is in the ordinary application.
    embedded.add_middleware(HostSecretMiddleware, secret=secret)
    embedded.add_middleware(GZipMiddleware, minimum_size=1000)
    embedded.add_middleware(AuditMiddleware)
    embedded.add_middleware(ConcurrencyGate, limit=POOL_CAPACITY)
    # No CORS: nothing in a browser talks to this process.

    for router, prefix, tag in ROUTERS:
        kept = APIRouter(
            routes=[
                route
                for route in router.routes
                if isinstance(route, APIRoute) and route.operation_id not in STRIPPED_OPERATIONS
            ]
        )
        embedded.include_router(kept, prefix=f"/api/v1{prefix}", tags=[tag])
    embedded.include_router(clock_endpoints.router, prefix="/api/v1/clock", tags=["Clock"])
    register_error_handlers(embedded)
    embedded.add_exception_handler(PoolTimeout, main.pool_exhausted)
    embedded.add_api_route("/health", main.health_check, operation_id="health.check")
    embedded.add_api_route("/health/ready", main.readiness_check, operation_id="health.ready")

    # The one switch that makes JWT and API-key authentication unreachable:
    # every protected route depends on this, directly or through
    # get_current_user and require_roles.
    embedded.dependency_overrides[security.get_current_user_id] = host_actor
    return embedded


def prepare_database(engine: Engine, schema: str | None) -> str:
    """Build what the host's database lacks, inside the schema when there is one.

    The schema is created first, in its own transaction, because create_all
    cannot put tables in a schema that is not there yet. Then the same step
    every flavour runs (app.core.schema.ensure_schema), then the account the
    host acts as itself.
    """
    if schema is not None:
        with engine.begin() as connection:
            connection.execute(text(f'CREATE SCHEMA IF NOT EXISTS "{schema}"'))
    outcome = ensure_schema(engine)
    with Session(engine) as db:
        seed_system_account(db)
    return outcome
