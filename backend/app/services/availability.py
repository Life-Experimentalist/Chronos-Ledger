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
FastAPI. A slot's dates come from its RFC 5545 rule through
app/core/recurrence.py, the same expansion the nightly generator uses.

Times here are naive wall clock in the organisation's own timezone, which is
what the slot and the reservation both store. They carry no offset and no Z,
and they are not converted, because there is nothing yet that says what
timezone they mean.
"""

import datetime

from sqlalchemy.orm import Session, joinedload

from app.core import recurrence
from app.core.time import org_today, window_span
from app.models.db import (
    Activity,
    DailyLedger,
    PlanningCycle,
    Reservation,
    ReservationStatus,
    ResourceMode,
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

    A slot counts while its cycle is flagged open and neither it nor its
    activity is retired, and only on the dates inside the cycle's own bounds. Those are the two tests
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
            StructuralMasterSlot.retired_at.is_(None),
            Activity.retired_at.is_(None),
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
    rule: str,
    dtstart: datetime.date,
    start: datetime.time,
    end: datetime.time,
    cycle: PlanningCycle | None = None,
) -> list[dict]:
    """The still standing bookings a slot with this rule and window would sit on.

    This is the same question the other way round. Availability and booking
    ask what occupies a resource over a range of dates; a slot has no range,
    so what it needs to know is which of a resource's holds fall on one of
    the dates its rule gives, and which of those overlap its window.

    Whether the rule lands on a date is asked in Python, through
    app/core/recurrence.py. Neither database can evaluate an RRULE, and the
    nightly generator asks the same function, so this refuses exactly the
    dates the generator would write.

    Only holds from today forward count. A slot produces days from now
    onwards, never backwards, so a hold that has already passed cannot be
    sat on by a class created after it. Counting those would mean a Monday
    class could not be created because the room was held one Monday in March.

    Sharing a date is not the same as clashing, once either side may run past
    midnight. A hold dated Tuesday that starts at five in the morning is sat
    on by a Monday slot running 22:00 to 06:00, and a hold dated Monday
    running 22:00 to 06:00 is sat on by a Tuesday slot starting at five. So
    each hold is tried against the three dates a slot could have and still
    touch it, its own and the two either side. Nothing further apart can
    reach it: both windows are under a day. A daily rule can land on all
    three, and the hold is still named once.

    cycle is the new slot's own. The slot only ever produces days inside its
    cycle's dates, so a hold on a date it will never run on is not sat on.

    A hold on a shared resource is never sat on. It records that somebody is
    there and contends with nothing, a class included, the same as a class
    does not refuse it.
    """
    clashes = []
    for held in (
        db.query(Reservation)
        .filter(
            Reservation.resource_id == resource_id,
            Reservation.status == ReservationStatus.HELD,
            Reservation.mode != ResourceMode.SHARED,
            Reservation.reserved_date >= org_today(),
        )
        .all()
    ):
        taken = window_span(held.reserved_date, held.time_window_start, held.time_window_end)
        for offset in (-1, 0, 1):
            slot_date = held.reserved_date + datetime.timedelta(days=offset)
            if not _within(cycle, slot_date):
                continue
            if not recurrence.occurs_on(rule, dtstart, slot_date):
                continue
            if _overlaps(window_span(slot_date, start, end), taken):
                clashes.append(_held_interval(held))
                break
    return clashes


def slots_against_slot(
    db: Session,
    resource_id: int,
    rule: str,
    dtstart: datetime.date,
    start: datetime.time,
    end: datetime.time,
    exclude_slot_id: int | None = None,
    cycle: PlanningCycle | None = None,
) -> list[dict]:
    """The slots a slot with this rule and window on this resource would sit on.

    held_against_slot answers this for bookings. Nothing answered it for the
    timetable itself, so two classes could be put in one room at one time and
    the only sign of it was two rows in the ledger every day from then on.

    Both sides are rules, and two rules can meet on one date in a year and
    on no other: a fortnightly class and a monthly one, or a weekly class and
    a short daily block. Comparing one weekday cannot see that. So both rules
    are expanded into the dates they will actually be written on, the dates
    inside each one's cycle, and compared date by date. Those are the rows
    the ledger will hold, so a clash this misses is a row the ledger refuses
    later, and a clash this reports is one the ledger would have had.

    Tomorrow is the earliest date considered, the same as the generator's
    horizon, and the date reported is the first one where the other slot's
    day is sat on. The other slot is named once however often the two meet.

    The day either side is checked as well, for the same reason
    held_against_slot checks the dates either side: once a window may run
    past midnight, sharing a date and overlapping in time have come apart. A
    Monday 22:00 to 06:00 class occupies Tuesday morning.

    exclude_slot_id keeps a slot being edited from finding itself. Widening
    a window from 09:00 to 10:00 into 09:00 to 11:00 overlaps the window it
    is replacing, and without this the slot would refuse its own change.

    Which slots count is booked_slots' decision, not this function's, so
    this and the availability endpoint cannot disagree about whether a room
    is free. cycle is the new slot's own. With no cycle the new rule is
    expanded over the other slot's cycle only, which is as far as a clash
    with it could reach.
    """
    one_day = datetime.timedelta(days=1)
    tomorrow = org_today() + one_day

    clashes = []
    for slot in booked_slots(db, resource_id):
        if slot.id == exclude_slot_id:
            continue
        other = slot.activity.cycle
        # The new slot's dates that can touch one of the other's: its own
        # cycle, from tomorrow, and no more than a day outside the other's.
        first = max(tomorrow, other.date_bounds_start - one_day)
        last = other.date_bounds_end + one_day
        if cycle is not None:
            first = max(first, cycle.date_bounds_start)
            last = min(last, cycle.date_bounds_end)
        if first > last:
            continue
        theirs = set(
            recurrence.occurrences(
                slot.rrule,
                slot.dtstart,
                max(first - one_day, other.date_bounds_start),
                min(last + one_day, other.date_bounds_end),
            )
        )
        if not theirs:
            continue
        met = _first_meeting(
            recurrence.occurrences(rule, dtstart, first, last),
            start,
            end,
            theirs,
            slot.time_window_start,
            slot.time_window_end,
        )
        if met is None:
            continue
        _, ends = window_span(met, slot.time_window_start, slot.time_window_end)
        clashes.append(
            {
                "date": met,
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


def _first_meeting(
    ours: list[datetime.date],
    start: datetime.time,
    end: datetime.time,
    theirs: set[datetime.date],
    their_start: datetime.time,
    their_end: datetime.time,
) -> datetime.date | None:
    """The first of their dates that one of ours sits on, or None.

    ours is in date order, so the first hit is the earliest clash on our
    side. The date returned is theirs, which is what a conflict entry
    describes: the window that is already there.
    """
    for day in ours:
        window = window_span(day, start, end)
        for offset in (-1, 0, 1):
            their_day = day + datetime.timedelta(days=offset)
            if their_day not in theirs:
                continue
            if _overlaps(window, window_span(their_day, their_start, their_end)):
                return their_day
    return None


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
    to fill. Closing withdraws the days it had planned from today on, but the
    ones already past, and any ahead that carry attendance or a note, are
    still in the table, still name a room and an hour, and the database
    refuses a second row on top of them whatever their cycle says. days_against_slot does not gate the days by
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
    rule: str,
    dtstart: datetime.date,
    start: datetime.time,
    end: datetime.time,
    exclude_slot_id: int | None = None,
    cycle: PlanningCycle | None = None,
) -> list[dict]:
    """The generated days a slot with this rule and window would sit on.

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

    Every future day of the resource is scanned, because a correction is
    copied onto every day this slot has still to run and the clash can be on
    any of them. Each is tried against the three dates around it that the
    rule could land on, for the same reason held_against_slot does, and is
    named once however many of them the rule lands on.
    """
    clashes = []
    for row in _dated_days(db, resource_id, org_today()):
        if exclude_slot_id is not None and row.master_slot_id == exclude_slot_id:
            continue
        entry = _day_interval(row)
        for offset in (-1, 0, 1):
            slot_date = row.target_date + datetime.timedelta(days=offset)
            if not _within(cycle, slot_date):
                continue
            if not recurrence.occurs_on(rule, dtstart, slot_date):
                continue
            if _overlaps(_bounds(entry), window_span(slot_date, start, end)):
                clashes.append(entry)
                break
    return clashes


def occupied(
    slots,
    reservations,
    days,
    from_date: datetime.date,
    to_date: datetime.date,
) -> list[dict]:
    """Expand slots, generated days and dated bookings into intervals.

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

    # Both halves of the key, never the slot alone. A slot recurs weekly and
    # the generator has usually reached one of its dates, so suppressing on
    # the slot would hide the fifty-one dates it has not reached yet and the
    # room would read free for the rest of the year.
    settled = {
        (row.target_date, row.master_slot_id) for row in days if row.master_slot_id is not None
    }

    busy = []
    for slot in slots:
        activity = slot.activity
        for day in recurrence.occurrences(
            slot.rrule, slot.dtstart, from_date - datetime.timedelta(days=1), to_date
        ):
            if (day, slot.id) in settled:
                continue
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


def held_span(held: Reservation) -> tuple[datetime.datetime, datetime.datetime]:
    """The two instants a booking holds, for the pool arithmetic below."""
    return window_span(held.reserved_date, held.time_window_start, held.time_window_end)


def _levels(spans: list[tuple[datetime.datetime, datetime.datetime, int]]) -> list[tuple]:
    """How many units are held from each instant the total changes, in order.

    Half open like everything else: a booking ending at ten and one starting
    at ten are summed at ten as the second alone, because the change at an
    instant is applied whole before the total is read.
    """
    deltas: dict[datetime.datetime, int] = {}
    for starts, ends, units in spans:
        deltas[starts] = deltas.get(starts, 0) + units
        deltas[ends] = deltas.get(ends, 0) - units
    total = 0
    levels = []
    for instant in sorted(deltas):
        total += deltas[instant]
        levels.append((instant, total))
    return levels


def pool_peak(holds, window: tuple[datetime.datetime, datetime.datetime] | None = None) -> int:
    """The most units of a pool the holds take at any one moment.

    Inside window when one is given, so a booking that only touches the
    window for an hour counts for that hour and not for the rest of its own.
    """
    spans = []
    for held in holds:
        starts, ends = held_span(held)
        if window is not None:
            starts, ends = max(starts, window[0]), min(ends, window[1])
        if starts < ends:
            spans.append((starts, ends, held.quantity))
    return max((total for _, total in _levels(spans)), default=0)


def pool_stretches(holds, at_least: int) -> list[tuple[datetime.datetime, datetime.datetime]]:
    """The longest stretches in which the holds take at_least units or more.

    Maximal, so two full hours back to back are one stretch and not two. The
    sum is a sum: it says how much of the pool is taken, never by whom, so a
    stretch is not one booking's window but the part where they add up.
    """
    stretches = []
    opened = None
    for instant, total in _levels([(*held_span(held), held.quantity) for held in holds]):
        if total >= at_least and opened is None:
            opened = instant
        elif total < at_least and opened is not None:
            stretches.append((opened, instant))
            opened = None
    return stretches


def full_intervals(
    holds, capacity: int, from_date: datetime.date, to_date: datetime.date
) -> list[dict]:
    """When a pooled resource has no units left, as busy intervals over a range.

    A pooled resource is busy only when it is full, and full is a property of
    several bookings at once, so these intervals name no single row: the
    activity and reservation fields are all null. Each is cut to the range
    asked about, because the bookings beyond it were not fetched and a
    stretch reaching past it cannot be told where it really ends.
    """
    range_from = datetime.datetime.combine(from_date, datetime.time.min)
    range_to = datetime.datetime.combine(to_date + datetime.timedelta(days=1), datetime.time.min)
    busy = []
    for starts, ends in pool_stretches(holds, capacity):
        starts, ends = max(starts, range_from), min(ends, range_to)
        if starts < ends:
            busy.append(
                {
                    "date": starts.date(),
                    "start": starts.time(),
                    "end_date": ends.date(),
                    "end": ends.time(),
                    "activity_id": None,
                    "activity_code": None,
                    "master_slot_id": None,
                    "reservation_id": None,
                }
            )
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
