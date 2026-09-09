# Copyright 2026 Chronos Ledger Contributors
# Licensed under the Apache License, Version 2.0

"""When a resource is already spoken for, over a range of dates.

Expansion is kept in one function, away from the database and away from
FastAPI, because it is the piece that changes next. A weekly repeat is the
only pattern the schema can express today; when a slot learns an RRULE, this
function is what gets replaced, and everything around it stays as it is.

Times here are naive wall clock in the organisation's own timezone, which is
what the slot stores. They carry no offset and no Z, and they are not
converted, because there is nothing yet that says what timezone the slot
means.
"""

import datetime

# A year and a day, so that "the next twelve months" from any date, leap
# years included, fits in one request and nothing longer does. The cap is
# on the answer, not the question: a ten year range is a mistake being made
# quickly, not a query anybody wants to wait for.
MAX_RANGE_DAYS = 366


def occupied(slots, from_date: datetime.date, to_date: datetime.date) -> list[dict]:
    """Expand weekly slots into the dated intervals they occupy.

    Returns the busy intervals rather than the free ones. Free time is the
    complement of this against whatever hours the caller considers open, and
    only the caller knows those: a hospital theatre and a lecture hall
    disagree about what an empty Tuesday night means.

    The caller decides which slots come in. Nothing here reads the ledger:
    the ledger only ever holds tomorrow, so a resource would read as free on
    every date past it. That also means a day-level change made through
    PATCH /ledger/{id} is not reflected, since that change lives on the day
    and not on the slot it came from.
    """
    by_weekday: dict[int, list] = {}
    for slot in slots:
        by_weekday.setdefault(slot.day_of_week_index, []).append(slot)

    busy = []
    day = from_date
    while day <= to_date:
        for slot in by_weekday.get(day.isoweekday(), ()):
            activity = slot.activity
            busy.append(
                {
                    "date": day.isoformat(),
                    "start": str(slot.time_window_start),
                    "end": str(slot.time_window_end),
                    "activity_id": slot.activity_id,
                    "activity_code": activity.activity_code if activity else None,
                    "master_slot_id": slot.id,
                }
            )
        day += datetime.timedelta(days=1)

    busy.sort(key=lambda entry: (entry["date"], entry["start"]))
    return busy
