# Copyright 2026 Chronos Ledger Contributors
# Licensed under the Apache License, Version 2.0
"""Paging for the routes that hand back a whole table.

The user list, the staff directory, the cycle list, the slot list, today's
ledger and the staff locator each return every row they match. That is fine
for one department and heavy for an institution with thousands of members, so
each takes an optional limit and offset. Leaving both off returns every row,
as these routes always have, so a client written against them keeps working.

Paged or not, the response says in X-Total-Count how many rows matched, which
is how a client knows how many pages there are without asking for all of them.
Rows come back in id order. Without an order the database may return rows in
whatever order it likes, and the same offset could land somewhere different
from one request to the next.
"""

from fastapi import Query, Response
from sqlalchemy.orm import Query as OrmQuery

TOTAL_COUNT_HEADER = "X-Total-Count"


class Page:
    """A list route's limit and offset, and the response its total goes on."""

    def __init__(
        self,
        response: Response,
        limit: int | None = Query(
            None, ge=1, description="At most this many rows; all if omitted."
        ),
        offset: int = Query(0, ge=0, description="Skip this many rows first."),
    ):
        self.response = response
        self.limit = limit
        self.offset = offset

    def rows(self, q: OrmQuery, key) -> list:
        """This page of q's rows in key order, with the number q matched set on the response.

        q has to carry every filter already, since the count is taken from it
        as it stands, before the order and the slice go on.
        """
        if self.limit is None and self.offset == 0:
            rows = q.order_by(key).all()
            total = len(rows)
        else:
            total = q.count()
            rows = q.order_by(key).offset(self.offset).limit(self.limit).all()
        self.response.headers[TOTAL_COUNT_HEADER] = str(total)
        return rows
