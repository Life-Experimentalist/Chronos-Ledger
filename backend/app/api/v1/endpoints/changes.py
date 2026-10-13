# Copyright 2026 Chronos Ledger Contributors
# Licensed under the Apache License, Version 2.0

from fastapi import APIRouter, Depends, Query, status
from sqlalchemy import func
from sqlalchemy.orm import Session, joinedload

from app.api.v1.endpoints.resources import reservation_view
from app.core import change_feed
from app.core.config import get_settings
from app.core.database import get_db
from app.core.errors import ChronosError, ErrorCode
from app.core.security import require_roles
from app.models.db import ChangeMarker, Reservation, Resource
from app.schemas.changes import ChangeFeed

router = APIRouter()

FEED_OFF = "the change feed is off. Set CHANGE_FEED_ENABLED=true to start recording changes."


@router.get("/", operation_id="changes.list", response_model=ChangeFeed)
def list_changes(
    since: int = Query(
        0, ge=0, description="The cursor the last poll returned. 0 is from the beginning."
    ),
    limit: int = Query(200, ge=1, le=1000, description="At most this many entries."),
    full: bool = Query(
        False, description="Every marker rather than one entry per row, and no row state."
    ),
    db: Session = Depends(get_db),
    _=Depends(require_roles("ORG_ADMIN")),
):
    """What has changed about the rooms and the bookings since a cursor.

    For a system that keeps its own copy of them. The websocket cannot tell it
    anything: those notices go to a signed-in socket, and a service behind
    somebody else's firewall has none. Polling every room on a timer is the
    alternative, and its cost grows with the building rather than with what
    happened.

    One entry per row, not one per change. A room renamed to Bedroom and then
    to Living Room is one entry saying Living Room, because a consumer
    catching up wants where things ended, not the walk. The whole walk is
    there for the asking: `full=true` returns every marker, oldest first, and
    no row state, which is the log to read when the question is what happened
    rather than what is.

    Send next_cursor back as since. An entry can arrive twice, after a crash
    between the commit and the poll that read it, or because a row changed
    again while the page was being built; applying one is replacing a row with
    what the row already says, so a consumer needs no bookkeeping to be safe.

    An entry can also be missed, and this is the one thing a consumer has to
    plan around. The cursor is the marker's own id, handed out at the insert
    and not at the commit, so two writes that commit in the other order leave a
    gap: a poll that reads the later id and stores it will not come back for
    the earlier one. So a consumer re-reads the rooms and the bookings in full
    on a slow timer, which it needs anyway, because the feed records only from
    the moment it was switched on and knows nothing of what happened before.

    A page as long as limit means there is probably more: poll again rather
    than waiting for the timer.

    Requires ORG_ADMIN, which is more than reading the rooms takes. A booking
    carries what it is for, and the availability calendar withholds that from
    everyone but the account that made it precisely because anyone signed in
    can read the calendar. This hands the whole booking over, so it is an
    operator's route, like the audit log.

    503 while the feed is off, which it is by default. An instance with no
    integrator has nobody to read this, and it is a table that grows with
    every write.
    """
    if not get_settings().change_feed_enabled:
        raise ChronosError(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=FEED_OFF,
            code=ErrorCode.CHANGE_FEED_DISABLED,
        )

    if full:
        markers = (
            db.query(ChangeMarker)
            .filter(ChangeMarker.id > since)
            .order_by(ChangeMarker.id)
            .limit(limit)
            .all()
        )
        return {
            "changes": [
                {
                    "cursor": m.id,
                    "entity_kind": m.entity_kind,
                    "entity_id": m.entity_id,
                    "change_kind": m.change_kind,
                    "at": m.at,
                }
                for m in markers
            ],
            "next_cursor": markers[-1].id if markers else since,
        }

    # One group per row that changed in the window. Ordered and cut by the
    # newest marker in the group, so a group left out by the limit is left out
    # whole and comes back on the next poll.
    groups = (
        db.query(
            ChangeMarker.entity_kind,
            ChangeMarker.entity_id,
            func.max(ChangeMarker.id).label("newest"),
            func.min(ChangeMarker.id).label("oldest"),
        )
        .filter(ChangeMarker.id > since)
        .group_by(ChangeMarker.entity_kind, ChangeMarker.entity_id)
        .order_by(func.max(ChangeMarker.id))
        .limit(limit)
        .all()
    )
    if not groups:
        return {"changes": [], "next_cursor": since}

    wanted = {g.newest for g in groups} | {g.oldest for g in groups}
    markers = {m.id: m for m in db.query(ChangeMarker).filter(ChangeMarker.id.in_(wanted))}

    resource_ids = [g.entity_id for g in groups if g.entity_kind == change_feed.RESOURCE]
    reservation_ids = [g.entity_id for g in groups if g.entity_kind == change_feed.RESERVATION]
    resources = (
        {r.id: r for r in db.query(Resource).filter(Resource.id.in_(resource_ids))}
        if resource_ids
        else {}
    )
    reservations = (
        {
            r.id: r
            for r in db.query(Reservation)
            .options(joinedload(Reservation.resource))
            .filter(Reservation.id.in_(reservation_ids))
        }
        if reservation_ids
        else {}
    )

    changes = []
    for group in groups:
        entry = {
            "cursor": group.newest,
            "entity_kind": group.entity_kind,
            "entity_id": group.entity_id,
            # The oldest marker in the window, not the newest. A consumer whose
            # cursor predates the row is told the row is new to them, whatever
            # was done to it afterwards; one that already had it is told it
            # changed. The newest would say "updated" about a row created and
            # then edited between two polls, which is a row the consumer has
            # never seen.
            "change_kind": markers[group.oldest].change_kind,
            "at": markers[group.newest].at,
        }
        if group.entity_kind == change_feed.RESOURCE:
            entry["resource"] = resources.get(group.entity_id)
        else:
            held = reservations.get(group.entity_id)
            entry["reservation"] = reservation_view(held, held.resource) if held else None
        changes.append(entry)

    return {"changes": changes, "next_cursor": changes[-1]["cursor"]}
