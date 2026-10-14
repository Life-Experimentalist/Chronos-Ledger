# Copyright 2026 Chronos Ledger Contributors
# Licensed under the Apache License, Version 2.0

"""Where the schedule already contradicts itself, over a range of dates.

The write paths refuse a clash as it arrives, but they cannot vouch for what
is already in the table. Rows written before a check existed, a day kept
behind by a closed cycle, a timetable imported into a closed cycle and
edited by hand, and anything written straight into the database all get
past them. This module finds those and reports them. It never refuses and
never changes a row.

Two kinds of clash are looked for.

A resource clash is two things holding one resource at one moment. What
holds a resource is exactly what GET /resources/{id}/availability reports as
busy, by the same rules: a weekly slot whose cycle is open, on the dates
inside that cycle's bounds; a generated day that names the resource and a
window, whatever its cycle now says; and a reservation that is still HELD.
Where a generated day and the slot it came from cover the same date, only
the day counts, because they are one class and not two.

A member clash is one person enrolled in two activities that run at the same
moment. An activity runs when its slots and its generated days say it does,
on any resource or on none, by the same rules as above. Two windows of one
activity are not a member clash: that is one activity, and if the two share a
room the resource side already names them.

Each clash is found by sorting the intervals of one resource, or of one
member, by start and sweeping them once while keeping the intervals still
open at that point. That costs a sort per group plus one step per clash
found, rather than comparing every interval with every other. A pair is
emitted when the later of the two arrives, which is why no pair is ever
named twice.

A weekly clash is reported once per date it happens in the range, the same
way availability lists a weekly slot once per date.

A resource's mode changes what counts, by the rules the booking route
refuses by (app.models.db.ResourceMode). On a shared resource a reservation
clashes with nothing and is left out; the timetable on it still clashes with
itself, as the write paths still refuse that. On a pooled resource the
timetable clashes as everywhere else, against itself and against any
reservation, because a class takes the whole pool, and two reservations do
not clash in pairs at all: what is reported is a resource_overbooked, a
stretch in which the reservations together hold more than the capacity,
naming every one of them that is open in it.

A requirement_unmet is the third kind and a different sort of thing: not two
rows in each other's way but one row that needs something it cannot have. It
is found for a weekly slot or a generated day whose activity or resource has
requirements (app.services.requirements), by the dry run the booking route
shares, and names that one row. The timetable never holds the extra
resources, so this is a report and nothing is refused.
"""

import datetime
from collections import defaultdict
from collections.abc import Iterable, Iterator

from sqlalchemy.orm import Session, joinedload

from app.core import recurrence
from app.core.time import window_span
from app.models.db import (
    Activity,
    ActivityEnrollment,
    DailyLedger,
    PlanningCycle,
    Reservation,
    ReservationStatus,
    Resource,
    ResourceMode,
    StructuralMasterSlot,
    User,
)
from app.services.availability import pool_peak, pool_stretches
from app.services.requirements import owners_with_requirements, unmet_for_window

# A quarter of a year. Smaller than the 366 days availability allows because
# this expands every resource and every member at once rather than one
# resource, and a clash report is read a term at a time.
MAX_CONFLICT_RANGE_DAYS = 92

RESOURCE_OVERLAP = "resource_overlap"
RESOURCE_OVERBOOKED = "resource_overbooked"
MEMBER_OVERLAP = "member_overlap"
REQUIREMENT_UNMET = "requirement_unmet"

SLOT = "slot"
LEDGER_DAY = "ledger_day"
RESERVATION = "reservation"

# (starts, ends, item). The two instants come first so a list of these sorts
# by time; the item is what the response carries.
Entry = tuple[datetime.datetime, datetime.datetime, dict]


def _entry(
    kind: str,
    row_id: int,
    day: datetime.date,
    start: datetime.time,
    end: datetime.time,
    activity_id: int | None,
    resource_id: int | None,
) -> Entry:
    starts, ends = window_span(day, start, end)
    item = {
        "type": kind,
        "id": row_id,
        "date": day,
        "start": start,
        "end_date": ends.date(),
        "end": end,
        "activity_id": activity_id,
        "resource_id": resource_id,
    }
    return starts, ends, item


def _sort_key(entry: Entry) -> tuple:
    starts, ends, item = entry
    return (starts, ends, item["type"], item["id"])


def _sweep(entries: Iterable[Entry]) -> Iterator[tuple[Entry, Entry]]:
    """Every overlapping pair in entries, each once, earlier first.

    Half open, as everywhere else: a window ending at ten and one starting at
    ten do not clash.
    """
    open_now: list[Entry] = []
    for entry in sorted(entries, key=_sort_key):
        open_now = [other for other in open_now if other[1] > entry[0]]
        for other in open_now:
            yield other, entry
        open_now.append(entry)


def _conflict(kind: str, first: Entry, second: Entry, **subject) -> dict:
    starts = max(first[0], second[0])
    ends = min(first[1], second[1])
    return _report(kind, starts, ends, [first[2], second[2]], **subject)


def _report(kind: str, starts, ends, items: list[dict], **subject) -> dict:
    return {
        "kind": kind,
        "resource_id": subject.get("resource_id"),
        "member_id": subject.get("member_id"),
        "date": starts.date(),
        "start": starts.time(),
        "end_date": ends.date(),
        "end": ends.time(),
        "items": items,
        "capacity": subject.get("capacity"),
        "taken": subject.get("taken"),
        "requirement_id": subject.get("requirement_id"),
        "message": subject.get("message"),
        "_starts": starts,
    }


def _overbooked(resource: Resource, held_on: list[Entry], holds: dict) -> Iterator[dict]:
    """Every stretch in which a pool's reservations hold more than it has.

    One report per stretch, not per pair: a pool of twelve with thirteen
    bookings open at once is one overbooking, and the thirteen are its
    items. taken is the most they hold at any moment of the stretch.
    """
    booked = [entry for entry in held_on if entry[2]["type"] == RESERVATION]
    rows = [holds[entry[2]["id"]] for entry in booked]
    for starts, ends in pool_stretches(rows, resource.capacity + 1):
        items = [
            entry[2]
            for entry in sorted(booked, key=_sort_key)
            if entry[0] < ends and starts < entry[1]
        ]
        yield _report(
            RESOURCE_OVERBOOKED,
            starts,
            ends,
            items,
            resource_id=resource.id,
            capacity=resource.capacity,
            taken=pool_peak(rows, (starts, ends)),
        )


def _report_key(conflict: dict) -> tuple:
    resource_id = conflict["resource_id"]
    return (
        conflict["kind"],
        -1 if resource_id is None else resource_id,
        conflict["member_id"] or "",
        conflict["_starts"],
        tuple((item["type"], item["id"], item["date"]) for item in conflict["items"]),
    )


def find_conflicts(db: Session, from_date: datetime.date, to_date: datetime.date) -> list[dict]:
    """Every resource clash and member clash that reaches into the range.

    Both dates are included. An interval counts when the hours it covers
    reach into the range, so a window dated the day before `from_date` that
    runs past midnight is swept too, and its date is the day it opened on.
    """
    reach_from = datetime.datetime.combine(from_date, datetime.time.min)
    reach_to = datetime.datetime.combine(to_date + datetime.timedelta(days=1), datetime.time.min)
    first_date = from_date - datetime.timedelta(days=1)

    slots = (
        db.query(StructuralMasterSlot)
        .join(Activity, StructuralMasterSlot.activity_id == Activity.id)
        .join(PlanningCycle, Activity.cycle_id == PlanningCycle.id)
        .filter(
            PlanningCycle.operational_status,
            StructuralMasterSlot.retired_at.is_(None),
            Activity.retired_at.is_(None),
        )
        .options(joinedload(StructuralMasterSlot.activity).joinedload(Activity.cycle))
        .all()
    )
    days = (
        db.query(DailyLedger)
        .filter(
            DailyLedger.target_date >= first_date,
            DailyLedger.target_date <= to_date,
            DailyLedger.time_window_start.isnot(None),
            DailyLedger.time_window_end.isnot(None),
        )
        .all()
    )
    holds = (
        db.query(Reservation)
        .filter(
            Reservation.status == ReservationStatus.HELD,
            Reservation.reserved_date >= first_date,
            Reservation.reserved_date <= to_date,
        )
        .all()
    )

    entries: list[Entry] = []

    # A day stands in for the slot that produced it on that date, the same
    # rule occupied() keeps for availability.
    settled = {(day.target_date, day.master_slot_id) for day in days if day.master_slot_id}
    runs_on = {
        slot.id: set(recurrence.occurrences(slot.rrule, slot.dtstart, first_date, to_date))
        for slot in slots
    }
    on = first_date
    while on <= to_date:
        for slot in slots:
            if on not in runs_on[slot.id]:
                continue
            cycle = slot.activity.cycle
            if not cycle.date_bounds_start <= on <= cycle.date_bounds_end:
                continue
            if (on, slot.id) in settled:
                continue
            entries.append(
                _entry(
                    SLOT,
                    slot.id,
                    on,
                    slot.time_window_start,
                    slot.time_window_end,
                    slot.activity_id,
                    slot.resource_id,
                )
            )
        on += datetime.timedelta(days=1)

    for day in days:
        entries.append(
            _entry(
                LEDGER_DAY,
                day.id,
                day.target_date,
                day.time_window_start,
                day.time_window_end,
                day.activity_id,
                day.resource_id,
            )
        )
    for held in holds:
        entries.append(
            _entry(
                RESERVATION,
                held.id,
                held.reserved_date,
                held.time_window_start,
                held.time_window_end,
                None,
                held.resource_id,
            )
        )

    entries = [entry for entry in entries if entry[0] < reach_to and reach_from < entry[1]]

    conflicts = []

    by_resource: dict[int, list[Entry]] = defaultdict(list)
    for entry in entries:
        if entry[2]["resource_id"] is not None:
            by_resource[entry[2]["resource_id"]].append(entry)
    resources = {
        resource.id: resource
        for resource in db.query(Resource).filter(Resource.id.in_(list(by_resource)))
    }
    holds_by_id = {held.id: held for held in holds}
    for resource_id, held_on in by_resource.items():
        mode = resources[resource_id].mode
        if mode is ResourceMode.SHARED:
            held_on = [entry for entry in held_on if entry[2]["type"] != RESERVATION]
        for first, second in _sweep(held_on):
            if mode is ResourceMode.POOLED and first[2]["type"] == second[2]["type"] == RESERVATION:
                continue
            conflicts.append(_conflict(RESOURCE_OVERLAP, first, second, resource_id=resource_id))
        if mode is ResourceMode.POOLED:
            conflicts.extend(_overbooked(resources[resource_id], held_on, holds_by_id))

    by_activity: dict[int, list[Entry]] = defaultdict(list)
    for entry in entries:
        if entry[2]["activity_id"] is not None:
            by_activity[entry[2]["activity_id"]].append(entry)
    by_member: dict[str, list[Entry]] = defaultdict(list)
    if by_activity:
        enrollments = (
            db.query(ActivityEnrollment.member_id, ActivityEnrollment.activity_id)
            .join(User, ActivityEnrollment.member_id == User.id)
            .filter(
                ActivityEnrollment.activity_id.in_(list(by_activity)),
                User.deactivated_at.is_(None),
            )
            .all()
        )
        for member_id, activity_id in enrollments:
            by_member[member_id].extend(by_activity[activity_id])
    for member_id, attending in by_member.items():
        for first, second in _sweep(attending):
            if first[2]["activity_id"] == second[2]["activity_id"]:
                continue
            conflicts.append(_conflict(MEMBER_OVERLAP, first, second, member_id=member_id))

    needing = owners_with_requirements(db)
    if needing:
        for starts, ends, item in entries:
            if item["type"] == RESERVATION:
                continue
            activity_id = (
                item["activity_id"] if ("ACTIVITY", item["activity_id"]) in needing else None
            )
            resource_id = (
                item["resource_id"] if ("RESOURCE", item["resource_id"]) in needing else None
            )
            if activity_id is None and resource_id is None:
                continue
            window = (item["date"], item["start"], item["end"])
            for gap in unmet_for_window(db, activity_id, resource_id, window):
                conflicts.append(
                    _report(
                        REQUIREMENT_UNMET,
                        starts,
                        ends,
                        [item],
                        resource_id=item["resource_id"],
                        requirement_id=gap["requirement_id"],
                        message=gap["message"],
                    )
                )

    conflicts.sort(key=_report_key)
    for conflict in conflicts:
        del conflict["_starts"]
    return conflicts
