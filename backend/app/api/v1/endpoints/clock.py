# Copyright 2026 Chronos Ledger Contributors
# Licensed under the Apache License, Version 2.0
"""The clock, read by anyone and moved by the host. Embedded flavour only.

Mounted by app.embedded.build_app and nowhere else: the ordinary application
runs on the system clock and has no route that could move it, and the
published OpenAPI document describes that application route for route.

GET  /api/v1/clock          what the clock reads, and whether a host owns it
POST /api/v1/clock/advance  move a host clock forward, running what came due

Only the host itself, the reserved actor `system`, may advance. The move goes
through app.cron.scheduled.advance, the same call a host in the same process
makes, so what runs on the way is the same too. One advance at a time: the
lock holds the "not before now" check and the move together, so two
concurrent calls cannot interleave their job runs.
"""

import threading

from fastapi import APIRouter, Depends, status
from pydantic import AwareDatetime, BaseModel

from app.core import clock
from app.core.errors import ChronosError, ErrorCode
from app.core.host_identity import SYSTEM_ACTOR_ID
from app.core.security import get_current_user
from app.cron import scheduled
from app.models.db import User

router = APIRouter()
_advancing = threading.Lock()


class ClockReading(BaseModel):
    mode: str
    now: AwareDatetime


class AdvanceRequest(BaseModel):
    to: AwareDatetime


class Advanced(BaseModel):
    now: AwareDatetime
    ran: list[str]


def the_host_itself(user: User = Depends(get_current_user)) -> User:
    if user.id != SYSTEM_ACTOR_ID:
        raise ChronosError(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=f"Only the actor {SYSTEM_ACTOR_ID!r} may advance the clock",
            code=ErrorCode.FORBIDDEN,
        )
    return user


@router.get("", operation_id="clock.read", response_model=ClockReading)
def read_clock(user: User = Depends(get_current_user)):
    return ClockReading(mode="host" if clock.is_host() else "system", now=clock.now())


@router.post("/advance", operation_id="clock.advance", response_model=Advanced)
def advance_clock(body: AdvanceRequest, user: User = Depends(the_host_itself)):
    # A plain def: Starlette runs it in a worker thread, where
    # scheduled.advance can own an event loop of its own for the jobs, and
    # the nightly run stays off the loop that serves requests.
    if not clock.is_host():
        raise ChronosError(
            status_code=status.HTTP_409_CONFLICT,
            detail="This process is on the system clock; start it with --clock-start",
            code=ErrorCode.STATE_CONFLICT,
        )
    with _advancing:
        if body.to < clock.now():
            raise ChronosError(
                status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
                detail=f"The clock does not go backwards: it reads {clock.now().isoformat()}",
                code=ErrorCode.INVALID_VALUE,
            )
        ran = scheduled.advance(body.to)
    return Advanced(now=clock.now(), ran=ran)
