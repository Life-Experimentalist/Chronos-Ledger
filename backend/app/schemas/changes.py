# Copyright 2026 Chronos Ledger Contributors
# Licensed under the Apache License, Version 2.0

import datetime

from pydantic import BaseModel

from app.schemas.resources import ReservationResponse, ResourceResponse


class Change(BaseModel):
    """One thing that changed, and what it now holds.

    resource and reservation are the row as it stands, one of them filled in
    according to entity_kind, so a consumer applies the entry without a second
    request. Both are null in the full log, which is the markers alone: a row
    renamed twice appears there twice, and the state a reader of the log would
    have to pick out of it is what the collapsed feed hands over already.

    Null in the collapsed feed too if the row has gone. Nothing this feed
    covers is deleted, so in practice it is not null.
    """

    cursor: int
    entity_kind: str
    entity_id: int
    change_kind: str
    at: datetime.datetime
    resource: ResourceResponse | None = None
    reservation: ReservationResponse | None = None


class ChangeFeed(BaseModel):
    """A page of changes and where to carry on from.

    next_cursor is what the next poll sends as since. It is the cursor sent in
    when nothing changed, so a consumer that stores it unconditionally keeps
    its place.
    """

    changes: list[Change]
    next_cursor: int
