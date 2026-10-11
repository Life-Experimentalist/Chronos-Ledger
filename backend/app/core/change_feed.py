# Copyright 2026 Chronos Ledger Contributors
# Licensed under the Apache License, Version 2.0
"""Writing down that something changed, for an outside system to poll for.

One function, called by the routes that change a resource or a reservation.
The marker goes into the caller's own session and is committed by the caller's
own commit, so a change that rolls back takes its marker with it and a marker
is never news of something that did not happen.

Off by default. With CHANGE_FEED_ENABLED unset this adds nothing to any
transaction, which is why the call sites do not each have to ask first.

What reads the markers is app/api/v1/endpoints/changes.py.
"""

from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.models.db import ChangeMarker

RESOURCE = "resource"
RESERVATION = "reservation"

CREATED = "created"
UPDATED = "updated"


def record(db: Session, entity_kind: str, entity_id: int, change_kind: str) -> None:
    """Note that one row changed. Committed by whoever is holding the session.

    Called after the row has an id and before the commit that saves it, so
    that the marker and the change are one transaction. Called with a flush in
    between where the id comes from the insert.
    """
    if not get_settings().change_feed_enabled:
        return
    db.add(ChangeMarker(entity_kind=entity_kind, entity_id=entity_id, change_kind=change_kind))
