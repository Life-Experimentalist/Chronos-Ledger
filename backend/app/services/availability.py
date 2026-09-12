# Copyright 2026 Chronos Ledger Contributors
# Licensed under the Apache License, Version 2.0

"""When a resource is already spoken for, over a range of dates.

Three things occupy a resource: a weekly slot from the timetable, a
reservation somebody placed by hand or through the API, and a generated day,
which is what a slot turns into once the nightly job has written it and is
the row attendance is marked against. All three are gathered here so that the
endpoint that answers "when is this free" and the endpoint that refuses a
clashing booking are looking at the same set. If they were not, availability
could report an hour free that booking then refused, or worse, booking could
accept an hour availability had already given away.

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


def _within(cycle: PlanningCycle | None, day: datetime.date) -> bool:
    """Whether a date falls inside a cycle's own dates, both ends included.

    No cycle means no bound, for a caller that wants every date counted.
    """
    return cycle is None or cycle.date_bounds_start <= day <= cycle.date_bounds_end


def booked_slots(db: Session, resource_id: int) -> list[StructuralMasterSlot]:
    """The weekly slots that count against this resource.

    A slot counts while its cycle is flagged open, and only on the dates
    inside the cycle's own bounds. Those are the two tests
    generate_daily_ledger_entries applies before it writes a day, so a room
    reported free here is a room the nightly job is not going to fill. The
    flag is tested here. The dates are tested date by date, in occupied() and
    slots_against_slot, which is why the cycle is loaded with the slot.
    """
    return (
        db.query(StructuralMasterSlot)
        .join(Activity, StructuralMasterSlot.activity_id == Activity.id)
        .join(PlanningCycle, Activity.cycle_id == PlanningCycle.id)
        .filter(
            StructuralMasterSlot.resource_id == resource_id,
            PlanningCycle.operational_status,
        )
        .options(joinedload(StructuralMasterSlot.activity).joinedload(Activity.cycle))
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
    db: Session,
    resource_id: int,
    weekday: int,
    start: datetime.time,
    end: datetime.time,
    cycle: PlanningCycle | None = None,
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

    cycle is the new slot's own. The slot only ever produces days inside its
    cycle's dates, so a hold on a date it will never run on is not sat on.
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
            if not _within(cycle, slot_date):
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
    cycle: PlanningCycle | None = None,
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
    is free. Two windows that meet on the probe meet in every week both
    slots run, and each runs only inside its own cycle's dates, so what is
    left to ask is whether there is such a week. cycle is the new slot's
    own. Two open cycles covering different parts of the year can share a
    room at one hour, and when they do overlap the date reported is the
    first week they both run, not the probe.
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
            shift = datetime.timedelta(days=offset)
            day = probe + shift
            if day.isoweekday() != slot.day_of_week_index:
                continue
            if not _overlaps(
                window_span(day, slot.time_window_start, slot.time_window_end), window
            ):
                continue
            # The first date on the new slot's weekday, from the probe on,
            # that is inside its cycle while the other side, a shift away, is
            # inside the other cycle. None of them means the two never meet.
            other = slot.activity.cycle
            first = max(probe, other.date_bounds_start - shift)
            last = other.date_bounds_end - shift
            if cycle is not None:
                first = max(first, cycle.date_bounds_start)
                last = min(last, cycle.date_bounds_end)
            first += datetime.timedelta(days=(weekday - first.isoweekday()) % 7)
            if first > last:
                continue
            day = first + shift
            _, ends = window_span(day, slot.time_window_start, slot.time_window_end)
            clashes.append(
                {
                    "date": day,
                    "start": slot.time_window_start,
                    "end_date": ends.date(),
                    "end": slot.time_window_end,
                    "activity_id": slot.activity_id,
                    "activity_code": slot.activity.activity_code,
                    "master_slot_id": slot.id,
                    "reservation_id": None,
                }
            )
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


def _dated_days(
    db: Session, resource_id: int, since: datetime.date, until: datetime.date | None = None
):
    """Generated days on a resource from a date onwards, windows only.

    A day with no window is an ad-hoc entry that never claimed an hour, and a
    day with no resource is not on this room. Neither occupies anything, and
    both are dropped here rather than in each caller, because the database
    constraint drops exactly the same rows and the two must not disagree.

    until is open by default because the two slot-side callers want every
    future day of the resource: a correction is copied onto every day the
    slot has still to run and the clash can be on any of them. A caller
    asking about a range closes it.

    The activity is loaded with the day. _day_interval reads it for the
    activity code, and this runs on the path GET availability takes, where a
    query per row would be a query per booked hour of the range.
    """
    query = db.query(DailyLedger).filter(
        DailyLedger.resource_id == resource_id,
        DailyLedger.target_date >= since,
        DailyLedger.time_window_start.isnot(None),
        DailyLedger.time_window_end.isnot(None),
    )
    if until is not None:
        query = query.filter(DailyLedger.target_date <= until)
    return (
        query.options(joinedload(DailyLedger.activity))
        .order_by(DailyLedger.target_date, DailyLedger.time_window_start)
        .all()
    )


def booked_days(
    db: Session, resource_id: int, from_date: datetime.date, to_date: datetime.date
) -> list[DailyLedger]:
    """The generated days sitting on this resource, in the range.

    No cycle gate, and that is the point of the function. booked_slots counts
    open cycles only, because closing a cycle stops the generator producing
    any more days and reporting its slots would claim dates nothing is going
    to fill. The days it already produced are still in the table, still name
    a room and an hour, and the database refuses a second row on top of them
    whatever their cycle says. days_against_slot does not gate the days by
    cycle either, for the same reason, and these two must not disagree.

    The day before the range is fetched too, exactly as held_reservations
    fetches it: a day dated Monday running 22:00 to 06:00 occupies Tuesday
    morning. occupied() drops whatever turns out not to reach the range.
    """
    return _dated_days(db, resource_id, from_date - datetime.timedelta(days=1), to_date)


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
    cycle: PlanningCycle | None = None,
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
    on top of them whatever their cycle says. So the days are not gated by
    cycle at all. The new slot is: cycle is its own, and it only ever
    produces days inside that cycle's dates, so a day on a date it will never
    run beside is not a clash.

    Every future day of the resource is scanned rather than one probe date,
    because a correction is copied onto every day this slot has still to run
    and the clash can be on any of them. The three date offsets are the same
    ones held_against_slot uses and for the same reason: sharing a weekday and
    overlapping in time came apart the moment a window could pass midnight.
    Only one of three consecutive dates falls on a given weekday, so a day is
    named at most once.
    """
    clashes = []
    for row in _dated_days(db, resource_id, org_today()):
        if exclude_slot_id is not None and row.master_slot_id == exclude_slot_id:
            continue
        for offset in (-1, 0, 1):
            slot_date = row.target_date + datetime.timedelta(days=offset)
            if slot_date.isoweekday() != weekday:
                continue
            if not _within(cycle, slot_date):
                continue
            entry = _day_interval(row)
            if _overlaps(_bounds(entry), window_span(slot_date, start, end)):
                clashes.append(entry)
    return clashes


def occupied(
    slots,
    reservations,
    days,
    from_date: datetime.date,
    to_date: datetime.date,
) -> list[dict]:
    """Expand weekly slots, generated days and dated bookings into intervals.

    Returns the busy intervals rather than the free ones. Free time is the
    complement of this against whatever hours the caller considers open, and
    only the caller knows those: a hospital theatre and a lecture hall
    disagree about what an empty Tuesday night means.

    The caller decides what comes in. Nothing here touches the database.

    The generated days are unioned in rather than read on their own. The
    ledger reaches a day or two ahead at most, so a calendar built from it
    alone would report a resource free on every date past that; the weekly
    expansion is what answers for the rest of the year. But where a day
    exists it is the row that holds the hour, so where the two disagree the
    day wins and the slot it came from is dropped for that date only. That is
    the timetable being corrected while days already in use keep the window
    they were generated with, and it is a closed cycle's leftovers and a
    deleted slot's days staying booked: those carry no live slot to drop and
    are simply added.

    A slot is expanded only onto the dates inside its cycle's own bounds,
    which are the dates the generator will write it on.

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

    # Both halves of the key, never the slot alone. A slot recurs weekly and
    # the generator has usually reached one of its dates, so suppressing on
    # the slot would hide the fifty-one dates it has not reached yet and the
    # room would read free for the rest of the year.
    settled = {
        (row.target_date, row.master_slot_id) for row in days if row.master_slot_id is not None
    }

    busy = []
    day = from_date - datetime.timedelta(days=1)
    while day <= to_date:
        for slot in by_weekday.get(day.isoweekday(), ()):
            if (day, slot.id) in settled:
                continue
            activity = slot.activity
            if activity is not None and not _within(activity.cycle, day):
                continue
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

    for row in days:
        entry = _day_interval(row)
        if _overlaps(_bounds(entry), asked):
            busy.append(entry)

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
