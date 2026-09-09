# Copyright 2026 Chronos Ledger Contributors
# Licensed under the Apache License, Version 2.0

"""When a resource is already spoken for, over a range of dates.

Two things occupy a resource: a weekly slot from the timetable, and a
reservation somebody placed by hand or through the API. Both are gathered
here so that the endpoint that answers "when is this free" and the endpoint
that refuses a clashing booking are looking at the same set. If they were not,
availability could report an hour free that booking then refused, or worse,
booking could accept an hour availability had already given away.

Expansion is kept in one function that touches neither the database nor
FastAPI, because it is the piece that changes next. A weekly repeat is the
only pattern the schema can express today; when a slot learns an RRULE, that
function is what gets replaced and everything around it stays as it is.

Times here are naive wall clock in the organisation's own timezone, which is
what the slot and the reservation both store. They carry no offset and no Z,
and they are not converted, because there is nothing yet that says what
timezone they mean.
"""

import datetime

from sqlalchemy.orm import Session, joinedload

from app.core.time import org_today
from app.models.db import (
    Activity,
    PlanningCycle,
    Reservation,
    ReservationStatus,
    StructuralMasterSlot,
)

# A year and a day, so that "the next twelve months" from any date, leap
# years included, fits in one request and nothing longer does. The cap is
# on the answer, not the question: a ten year range is a mistake being made
# quickly, not a query anybody wants to wait for.
MAX_RANGE_DAYS = 366


def _span(
    day: datetime.date, start: datetime.time, end: datetime.time
) -> tuple[datetime.datetime, datetime.datetime]:
    """The two instants a window opened on this date actually runs between.

    A window whose end is earlier than its start runs past midnight and
    finishes on the following date. 22:00 to 06:00 is eight hours on a night
    shift, not a negative sixteen, and a ward or a factory line that runs one
    is ordinary rather than exotic.

    That encoding is the whole of it: there is no column saying which day the
    end falls on, only the two times and the rule that a backwards pair means
    the next day. Every comparison in this module goes through here so the
    rule is stated once, and migration 010 writes the same rule in SQL for the
    exclusion constraint on reservations.

    Equal times are not a window this can describe and are refused at the
    edge, in the schema validators and in a check constraint, because 09:00 to
    09:00 would be either nothing at all or a full day and there is no way to
    tell which was meant.
    """
    ends_on = day + datetime.timedelta(days=1) if end < start else day
    return datetime.datetime.combine(day, start), datetime.datetime.combine(ends_on, end)


def _bounds(entry: dict) -> tuple[datetime.datetime, datetime.datetime]:
    """The same two instants, for a busy interval that already carries its end date."""
    return (
        datetime.datetime.combine(entry["date"], entry["start"]),
        datetime.datetime.combine(entry["end_date"], entry["end"]),
    )


def _overlaps(
    first: tuple[datetime.datetime, datetime.datetime],
    second: tuple[datetime.datetime, datetime.datetime],
) -> bool:
    """Half open, so a window ending at ten and one starting at ten do not clash.

    Back to back bookings are the normal case, and refusing them would make a
    room unusable in every schedule that runs on the hour.
    """
    return first[0] < second[1] and second[0] < first[1]


def booked_slots(db: Session, resource_id: int) -> list[StructuralMasterSlot]:
    """The weekly slots that count against this resource.

    A slot counts when its cycle is flagged open, and the flag is the whole
    test. generate_daily_ledger_entries books a day whenever the cycle is
    open and never looks at date_bounds_start or date_bounds_end, so neither
    does this. Reading the bounds here would report a room free on a date the
    nightly job is going to fill, and two systems would book it.
    """
    return (
        db.query(StructuralMasterSlot)
        .join(Activity, StructuralMasterSlot.activity_id == Activity.id)
        .join(PlanningCycle, Activity.cycle_id == PlanningCycle.id)
        .filter(
            StructuralMasterSlot.resource_id == resource_id,
            PlanningCycle.operational_status,
        )
        .options(joinedload(StructuralMasterSlot.activity))
        .all()
    )


def held_reservations(
    db: Session, resource_id: int, from_date: datetime.date, to_date: datetime.date
) -> list[Reservation]:
    """The bookings still standing on this resource, in the range.

    A cancelled reservation stays in the table and stops occupying anything.
    The row is kept because a cancellation is an event an outside system has
    to hear about, and a deleted row is not an event.

    The day before the range is fetched too. A booking dated Monday that runs
    from 22:00 to 06:00 occupies Tuesday morning, so a caller asking only
    about Tuesday has to be told about it or the room reads as free at five in
    the morning while somebody is in it. Fetching it is not the same as
    reporting it: occupied() drops whatever turns out not to reach the range.
    """
    return (
        db.query(Reservation)
        .filter(
            Reservation.resource_id == resource_id,
            Reservation.status == ReservationStatus.HELD,
            Reservation.reserved_date >= from_date - datetime.timedelta(days=1),
            Reservation.reserved_date <= to_date,
        )
        .all()
    )


def _held_interval(held: Reservation) -> dict:
    """One booking, in the shape every busy interval takes."""
    _, ends = _span(held.reserved_date, held.time_window_start, held.time_window_end)
    return {
        "date": held.reserved_date,
        "start": held.time_window_start,
        "end_date": ends.date(),
        "end": held.time_window_end,
        "activity_id": None,
        "activity_code": None,
        "master_slot_id": None,
        "reservation_id": held.id,
    }


def held_against_slot(
    db: Session, resource_id: int, weekday: int, start: datetime.time, end: datetime.time
) -> list[dict]:
    """The still standing bookings a weekly slot at this window would sit on.

    This is the same question the other way round. Availability and booking
    ask what occupies a resource over a range of dates; a slot has no range,
    so what it needs to know is which of a resource's holds fall on its
    weekday, and which of those overlap its window.

    The weekday match is done here in Python rather than in SQL. Postgres
    numbers isodow Monday 1 to Sunday 7 and SQLite numbers strftime('%w')
    Sunday 0 to Saturday 6, and the suite runs on SQLite while a deployment
    runs on Postgres, so a comparison written in SQL would be a day out in
    production and correct in every test. day_of_week_index is 1 for Monday,
    which is what isoweekday() returns.

    Only holds from today forward count. A slot produces days from now
    onwards, never backwards, so a hold that has already passed cannot be
    sat on by a class created after it. Counting those would mean a Monday
    class could not be created because the room was held one Monday in March.

    Matching the weekday is not the same as matching the date, once either
    side may run past midnight. A hold dated Tuesday that starts at five in
    the morning is sat on by a Monday slot running 22:00 to 06:00, and a hold
    dated Monday running 22:00 to 06:00 is sat on by a Tuesday slot starting
    at five. So each hold is tried against the three dates a slot on this
    weekday could have and still touch it, its own and the two either side.
    Only one of those three is this weekday, so a hold can be named once at
    most. Nothing further apart can reach it: both windows are under a day.
    """
    clashes = []
    for held in (
        db.query(Reservation)
        .filter(
            Reservation.resource_id == resource_id,
            Reservation.status == ReservationStatus.HELD,
            Reservation.reserved_date >= org_today(),
        )
        .all()
    ):
        for offset in (-1, 0, 1):
            slot_date = held.reserved_date + datetime.timedelta(days=offset)
            if slot_date.isoweekday() != weekday:
                continue
            taken = _span(held.reserved_date, held.time_window_start, held.time_window_end)
            if _overlaps(_span(slot_date, start, end), taken):
                clashes.append(_held_interval(held))
    return clashes


def occupied(
    slots,
    reservations,
    from_date: datetime.date,
    to_date: datetime.date,
) -> list[dict]:
    """Expand weekly slots and dated bookings into the intervals they take.

    Returns the busy intervals rather than the free ones. Free time is the
    complement of this against whatever hours the caller considers open, and
    only the caller knows those: a hospital theatre and a lecture hall
    disagree about what an empty Tuesday night means.

    The caller decides what comes in. Nothing here reads the ledger: the
    ledger only ever holds tomorrow, so a resource would read as free on
    every date past it. That also means a day-level change made through
    PATCH /ledger/{id} is not reflected, since that change lives on the day
    and not on the slot it came from.

    A reservation carries no activity and a slot carries no reservation id,
    so which kind an interval is can be read off the fields that are set.
    What a booking is for is deliberately not here: a room's calendar is
    visible to everyone signed in, and the purpose of a booking need not be.

    An interval is reported when the hours it covers reach into the range,
    not when its date falls inside it. Those were the same test until a
    window could run past midnight, and they are not the same now: a booking
    dated Monday from 22:00 to 06:00 is on the calendar for a caller asking
    about Tuesday, and its date is the Monday it opened on. So an entry's
    date can be one day before the range that returned it.
    """
    range_from = datetime.datetime.combine(from_date, datetime.time.min)
    range_to = datetime.datetime.combine(to_date + datetime.timedelta(days=1), datetime.time.min)
    asked = (range_from, range_to)

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
                    "date": day,
                    "start": slot.time_window_start,
                    "end_date": day,
                    "end": slot.time_window_end,
                    "activity_id": slot.activity_id,
                    "activity_code": activity.activity_code if activity else None,
                    "master_slot_id": slot.id,
                    "reservation_id": None,
                }
            )
        day += datetime.timedelta(days=1)

    for held in reservations:
        entry = _held_interval(held)
        if _overlaps(_bounds(entry), asked):
            busy.append(entry)

    busy.sort(key=lambda entry: (entry["date"], entry["start"], entry["end_date"], entry["end"]))
    return busy


def clashing(
    busy: list[dict], day: datetime.date, start: datetime.time, end: datetime.time
) -> list[dict]:
    """The intervals that overlap a window opened on this date, out of a busy list.

    Takes the date as well as the two times, because the times alone no
    longer say when the window is. 23:00 to 01:00 and 01:00 to 23:00 are the
    same pair of times and are almost disjoint, and which one is meant is
    decided by _span from the order they come in.
    """
    window = _span(day, start, end)
    return [entry for entry in busy if _overlaps(_bounds(entry), window)]
