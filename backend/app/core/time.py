# Copyright 2026 Chronos Ledger Contributors
# Licensed under the Apache License, Version 2.0
"""What day and time it is where the organization is.

Not where the server is. A container runs UTC unless somebody tells it
otherwise, and the code used to ask the container: date.today() and
datetime.now() with no zone read the process clock, so "today" meant today in
UTC no matter where the people using the system were standing.

The size of the damage is exactly the UTC offset, in whichever direction the
offset runs. At UTC+5:30 the server still calls it yesterday from midnight
until 05:30 local, so anyone opening the app in that window is shown
yesterday's sessions and cannot mark the day they are actually in. West of
UTC it is the mirror image: at UTC-5 the server has rolled into tomorrow from
19:00 local, so evening sessions vanish from the dashboard while they are
still running.

Timestamps are a different question and are not touched here. created_at and
the rest are datetime.now(UTC) throughout the models, which is right: an
instant is an instant. What needed a zone is the calendar, because a calendar
day is a local idea and the schedule is made of calendar days.

The other thing here is window_span, which is about the calendar rather than
the clock. It turns a date and a pair of wall clock readings into the two
instants the window runs between, and it is the one place that says an end
earlier than a start means the window finishes on the next date. Availability,
the location resolver and the calendar feed all need that rule, so it is
stated here once instead of three times slightly differently.
"""

import datetime
from zoneinfo import ZoneInfo

from app.core.config import get_settings


def org_timezone() -> ZoneInfo:
    """The organization's zone, from ORG_TIMEZONE.

    Not cached here. ZoneInfo keeps its own cache of loaded zones, so this is
    a dictionary lookup after the first call, and leaving it uncached means a
    test that changes the setting sees the change.
    """
    return ZoneInfo(get_settings().org_timezone)


def org_now() -> datetime.datetime:
    """Now, as the organization's wall clock reads it.

    Aware, so arithmetic against other aware datetimes works. Take .time()
    off it to compare against a Time column, which stores a wall clock
    reading with no zone of its own.
    """
    return datetime.datetime.now(org_timezone())


def org_today() -> datetime.date:
    """The date the organization is currently living in."""
    return org_now().date()


def org_tomorrow() -> datetime.date:
    """The next date the organization will live in.

    A day, not 24 hours. Adding one to a date steps the calendar, which is
    what the nightly generator wants: it is laying down the next day's rows,
    and on a day that has 23 or 25 hours in it the answer is still the next
    date.
    """
    return org_today() + datetime.timedelta(days=1)


def window_span(
    day: datetime.date, start: datetime.time, end: datetime.time
) -> tuple[datetime.datetime, datetime.datetime]:
    """The two instants a window opened on this date actually runs between.

    A window whose end is earlier than its start runs past midnight and
    finishes on the following date. 22:00 to 06:00 is eight hours on a night
    shift, not a negative sixteen, and a ward or a factory line that runs one
    is ordinary rather than exotic.

    That encoding is the whole of it: there is no column saying which day the
    end falls on, only the two times and the rule that a backwards pair means
    the next day. Reservations and weekly slots read the same way, and
    migration 010 writes the same rule in SQL for the exclusion constraint on
    reservations.

    Naive, because a slot and a reservation both store naive wall clock in the
    organisation's own zone and carry nothing that says which zone. Comparing
    one of these against org_now() means dropping the zone off now first,
    which is what taking .time() off it used to do implicitly.

    Equal times are not a window this can describe and are refused at the
    edge, in the schema validators and in a check constraint, because 09:00 to
    09:00 would be either nothing at all or a full day and there is no way to
    tell which was meant.
    """
    ends_on = day + datetime.timedelta(days=1) if end < start else day
    return datetime.datetime.combine(day, start), datetime.datetime.combine(ends_on, end)
