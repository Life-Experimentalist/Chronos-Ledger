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

from app.core.time import org_today, window_span
from app.models.db import (
    Activity,
    DailyLedger,
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
    _, ends = window_span(held.reserved_date, held.time_window_start, held.time_window_end)
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
            taken = window_span(held.reserved_date, held.time_window_start, held.time_window_end)
            if _overlaps(window_span(slot_date, start, end), taken):
                clashes.append(_held_interval(held))
    return clashes


def slots_against_slot(
    db: Session,
    resource_id: int,
    weekday: int,
    start: datetime.time,
    end: datetime.time,
    exclude_slot_id: int | None = None,
) -> list[dict]:
    """The weekly slots a slot at this window on this resource would sit on.

    held_against_slot answers this for bookings. Nothing answered it for the
    timetable itself, so two classes could be put in one room at one time and
    the only sign of it was two rows in the ledger every day from then on.

    Both sides are weekly repeats with no date, so the comparison is made on
    a date picked to stand for every week: the next occurrence of the new
    slot's weekday. The clash repeats until one of the two moves, and the
    date returned is the first time it happens rather than a date the caller
    asked about. Tomorrow is the earliest one considered, so an adjacent
    weekday is never reported as yesterday.

    The weekday either side is checked as well, for the same reason
    held_against_slot checks the dates either side: once a window may run
    past midnight, sharing a weekday and overlapping in time have come
    apart. A Monday 22:00 to 06:00 class occupies Tuesday morning. Only one
    of the three candidate dates falls on any given weekday, so a slot can
    be named at most once.

    exclude_slot_id keeps a slot being edited from finding itself. Widening
    a window from 09:00 to 10:00 into 09:00 to 11:00 overlaps the window it
    is replacing, and without this the slot would refuse its own change.

    Which slots count is booked_slots' decision, not this function's, so
    this and the availability endpoint cannot disagree about whether a room
    is free. That means every open cycle counts, including a second one
    covering a different part of the year: the generator lays both onto the
    same date today, so both occupy the room today. Whether two cycles
    should be open at once is a separate question and is not decided here.
    """
    probe = org_today() + datetime.timedelta(days=1)
    while probe.isoweekday() != weekday:
        probe += datetime.timedelta(days=1)
    window = window_span(probe, start, end)

    clashes = []
    for slot in booked_slots(db, resource_id):
        if slot.id == exclude_slot_id:
            continue
        for offset in (-1, 0, 1):
            day = probe + datetime.timedelta(days=offset)
            if day.isoweekday() != slot.day_of_week_index:
                continue
            _, ends = window_span(day, slot.time_window_start, slot.time_window_end)
            entry = {
                "date": day,
                "start": slot.time_window_start,
                "end_date": ends.date(),
                "end": slot.time_window_end,
                "activity_id": slot.activity_id,
                "activity_code": slot.activity.activity_code if slot.activity else None,
                "master_slot_id": slot.id,
                "reservation_id": None,
            }
            if _overlaps(_bounds(entry), window):
                clashes.append(entry)
    return clashes


def _day_interval(day: DailyLedger) -> dict:
    """One generated day, in the shape every busy interval takes.

    The same keys a slot produces, because a generated day is what a slot
    turns into and a caller reading a conflict should not have to learn a
    second shape to find out a room is taken. master_slot_id is the slot it
    came from, or nothing if that slot has since been deleted or the day was
    never produced by one.
    """
    _, ends = window_span(day.target_date, day.time_window_start, day.time_window_end)
    activity = day.activity
    return {
        "date": day.target_date,
        "start": day.time_window_start,
        "end_date": ends.date(),
        "end": day.time_window_end,
        "activity_id": day.activity_id,
        "activity_code": activity.activity_code if activity else None,
        "master_slot_id": day.master_slot_id,
        "reservation_id": None,
    }


def _dated_days(db: Session, resource_id: int, since: datetime.date):
    """Generated days on a resource from a date onwards, windows only.

    A day with no window is an ad-hoc entry that never claimed an hour, and a
    day with no resource is not on this room. Neither occupies anything, and
    both are dropped here rather than in each caller, because the database
    constraint drops exactly the same rows and the two must not disagree.
    """
    return (
        db.query(DailyLedger)
        .filter(
            DailyLedger.resource_id == resource_id,
            DailyLedger.target_date >= since,
            DailyLedger.time_window_start.isnot(None),
            DailyLedger.time_window_end.isnot(None),
        )
        .order_by(DailyLedger.target_date, DailyLedger.time_window_start)
        .all()
    )


def days_against_window(
    db: Session,
    resource_id: int,
    day: datetime.date,
    start: datetime.time,
    end: datetime.time,
    exclude_slot_id: int | None = None,
) -> list[dict]:
    """The generated days a window opened on this date would sit on.

    One date, not a weekday, because the caller is the nightly generator and
    it is writing one dated row. The day either side is fetched as well: a day
    dated yesterday running 22:00 to 06:00 occupies this morning, and a day
    dated tomorrow starting at five is occupied by a window opened tonight.
    """
    window = window_span(day, start, end)
    clashes = []
    for row in _dated_days(db, resource_id, day - datetime.timedelta(days=1)):
        if row.target_date > day + datetime.timedelta(days=1):
            continue
        if exclude_slot_id is not None and row.master_slot_id == exclude_slot_id:
            continue
        entry = _day_interval(row)
        if _overlaps(_bounds(entry), window):
            clashes.append(entry)
    return clashes


def days_against_slot(
    db: Session,
    resource_id: int,
    weekday: int,
    start: datetime.time,
    end: datetime.time,
    exclude_slot_id: int | None = None,
) -> list[dict]:
    """The generated days a weekly slot at this window would sit on.

    slots_against_slot asks this of the timetable and held_against_slot asks
    it of the bookings. Neither sees the rows that actually put somebody at a
    door, and two of them can be on one room at one time without either of
    those checks noticing.

    A slot in a closed cycle occupies nothing as far as those two are
    concerned, and that is deliberate: booked_slots counts open cycles only,
    so a booking may be accepted on top of a closed cycle's slot. The days it
    already produced are a different matter. They are still in the table, they
    still name a room and an hour, and the database will refuse a second row
    on top of them whatever their cycle says. So there is no cycle gate here,
    on either side.

    Every future day of the resource is scanned rather than one probe date,
    because a correction is copied onto every day this slot has still to run
    and the clash can be on any of them. The three date offsets are the same
    ones held_against_slot uses and for the same reason: sharing a weekday and
    overlapping in time came apart the moment a window could pass midnight.
    Only one of three consecutive dates falls on a given weekday, so a day is
    named at most once.

    This is stricter than the availability endpoint, which reads slots and
    bookings and never the ledger. The gap between them is exactly the days no
    slot speaks for any more: a closed cycle's leftovers, and the days of a
    deleted slot that had attendance on them. Those read as free there and are
    refused here, and being refused is the correct half of that.
    """
    clashes = []
    for row in _dated_days(db, resource_id, org_today()):
        if exclude_slot_id is not None and row.master_slot_id == exclude_slot_id:
            continue
        for offset in (-1, 0, 1):
            slot_date = row.target_date + datetime.timedelta(days=offset)
            if slot_date.isoweekday() != weekday:
                continue
            entry = _day_interval(row)
            if _overlaps(_bounds(entry), window_span(slot_date, start, end)):
                clashes.append(entry)
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
    window could run past midnight, and they are not the same now: a slot or
    a booking dated Monday from 22:00 to 06:00 is on the calendar for a
    caller asking about Tuesday, and its date is the Monday it opened on. So
    an entry's date can be one day before the range that returned it, and the
    weekly expansion starts a day early for the same reason the reservation
    query fetches a day early.
    """
    range_from = datetime.datetime.combine(from_date, datetime.time.min)
    range_to = datetime.datetime.combine(to_date + datetime.timedelta(days=1), datetime.time.min)
    asked = (range_from, range_to)

    by_weekday: dict[int, list] = {}
    for slot in slots:
        by_weekday.setdefault(slot.day_of_week_index, []).append(slot)

    busy = []
    day = from_date - datetime.timedelta(days=1)
    while day <= to_date:
        for slot in by_weekday.get(day.isoweekday(), ()):
            activity = slot.activity
            _, ends = window_span(day, slot.time_window_start, slot.time_window_end)
            entry = {
                "date": day,
                "start": slot.time_window_start,
                "end_date": ends.date(),
                "end": slot.time_window_end,
                "activity_id": slot.activity_id,
                "activity_code": activity.activity_code if activity else None,
                "master_slot_id": slot.id,
                "reservation_id": None,
            }
            if _overlaps(_bounds(entry), asked):
                busy.append(entry)
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
    decided by window_span from the order they come in.
    """
    window = window_span(day, start, end)
    return [entry for entry in busy if _overlaps(_bounds(entry), window)]
