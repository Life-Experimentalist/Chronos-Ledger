# Copyright 2026 Chronos Ledger Contributors
# Licensed under the Apache License, Version 2.0

import datetime

from redis import Redis
from sqlalchemy import and_, or_
from sqlalchemy.orm import Session

from app.core.time import org_now, window_span
from app.models.db import (
    Activity,
    DailyLedger,
    DynamicState,
    LogVerificationState,
    PlanningCycle,
    ReverseRsvpLog,
    StructuralMasterSlot,
    User,
)

# The states a named cover is in the room for. A lunch or a meeting with a
# substitute on it is not a class anybody is running.
_COVERABLE = {DynamicState.SCHEDULED, DynamicState.PROXY_SUBSTITUTE, DynamicState.ON_LEAVE}


def _covers(
    day: datetime.date,
    start: datetime.time,
    end: datetime.time,
    instant: datetime.datetime,
) -> bool:
    """Whether a window opened on this date is running at this instant.

    Half open, the start in and the end out, which is what every other
    comparison in the system does. It used to be closed at both ends, so
    wherever two shifts met the person handing over was in two rooms at once
    and which of the two the dashboard showed was decided by whatever order
    the database happened to return them in.

    Deliberately not written with an interval overlap helper. An instant is a
    zero length interval and a half open overlap of one of those is always
    empty, so an overlap test would answer no at every instant, the one the
    shift starts on included.

    Two times rather than the row holding them, because a generated day and a
    weekly slot each have a window now and neither is the other.
    """
    starts, ends = window_span(day, start, end)
    return starts <= instant < ends


def determine_staff_current_states(
    staff: list[User], db: Session, redis_cache: Redis
) -> dict[str, dict]:
    """Where each of these people is right now, keyed by their id.

    Each tier is asked about everybody at once and its rows are handed back
    out by lead. The locator used to ask one person at a time, which was a
    Redis round trip and up to four queries for every member of staff on
    every poll. Looking up one person is this with a list of one, so the
    locator and the single lookup cannot disagree.
    """
    if not staff:
        return {}

    now = org_now()
    # The zone dropped, because a slot stores naive wall clock and carries
    # nothing saying which zone it means. Taking .time() off now used to do
    # exactly this, only the date came away with it and a window that runs
    # past midnight needs the date to say which side of it we are on.
    instant = now.replace(tzinfo=None)
    today = now.date()
    yesterday = today - datetime.timedelta(days=1)
    resolved: dict[str, dict] = {}

    # Tier 1: Redis manual status override (TTL-based, e.g. "in meeting", "out for lunch")
    # redis-py returns bytes; decode before use.
    overrides = redis_cache.mget([f"state_override:{person.id}" for person in staff])
    for person, cached_raw in zip(staff, overrides, strict=True):
        if cached_raw:
            cached = cached_raw.decode("utf-8") if isinstance(cached_raw, bytes) else cached_raw
            # An override says what somebody is doing, not where. No location was
            # worked out at all on this path, and saying so is better than naming
            # a place the override never claimed.
            resolved[person.id] = {"resolved_location": "UNKNOWN", "status": cached}

    # Both tiers below fetch yesterday as well as today and then decide in
    # Python. A shift running 22:00 to 06:00 is dated the day it opened on,
    # so at two in the morning the row that has somebody on shift is
    # yesterday's, and the hours it covers cannot be compared in SQL: the
    # comparison start <= now <= end is false at every instant of a window
    # whose end is the smaller of the two. Fetching a day is not the same as
    # reporting it, and _covers drops whatever is not actually running.
    #
    # Yesterday is tried first where both could answer, so a night shift that
    # is still running outranks one that started this morning.

    # Tier 2: Daily exception log (leaves, proxies, ad-hoc)
    #
    # The day's own window, and no join to the slot that produced it. The join
    # was an inner one, so a day whose slot had since been deleted and an
    # ad-hoc day that never had one were both invisible here. Somebody on
    # approved leave from a class later taken off the timetable was reported
    # as teaching it, because the tier that knew about the leave never saw the
    # row and tier 3 answered instead.
    #
    # A row speaks for two people once somebody covers it. It was only ever
    # looked up by its lead, so the cover was never found here at all, and a
    # PROXY_SUBSTITUTE row reported its original lead as the one substituting.
    # Now the cover is in the room on any row they have taken over, and the
    # lead is answered only by a row that is still theirs to run: ON_LEAVE
    # says where they are not, SCHEDULED with nobody covering says where they
    # are, and anything else says nothing about them.
    #
    # The rows come back in the order they are tried in, so the first one
    # running that answers for somebody is the one that does. A row that says
    # nothing about a person leaves a later one free to.
    unresolved = [person.id for person in staff if person.id not in resolved]
    asked = set(unresolved)
    running = [
        ledger
        for ledger in db.query(DailyLedger)
        .filter(
            or_(
                DailyLedger.active_lead_id.in_(unresolved),
                DailyLedger.substitute_lead_id.in_(unresolved),
            ),
            DailyLedger.target_date.in_((yesterday, today)),
            DailyLedger.time_window_start.isnot(None),
            DailyLedger.time_window_end.isnot(None),
        )
        .order_by(DailyLedger.target_date, DailyLedger.time_window_start)
        .all()
        if _covers(ledger.target_date, ledger.time_window_start, ledger.time_window_end, instant)
    ]
    codes = dict(
        db.query(Activity.id, Activity.activity_code)
        .filter(Activity.id.in_([ledger.activity_id for ledger in running]))
        .all()
    )
    for ledger in running:
        room = ledger.target_room_identifier
        cover, lead = ledger.substitute_lead_id, ledger.active_lead_id
        if cover in asked and cover not in resolved and ledger.operational_state in _COVERABLE:
            resolved[cover] = {"resolved_location": room, "status": f"Substituting in Room {room}"}
        if lead not in asked or lead in resolved:
            continue
        if ledger.operational_state == DynamicState.ON_LEAVE:
            resolved[lead] = {"resolved_location": "OFF_SITE", "status": "On Approved Leave"}
        elif ledger.operational_state == DynamicState.SCHEDULED and cover is None:
            code = codes.get(ledger.activity_id, "a session")
            resolved[lead] = {"resolved_location": room, "status": f"Leading {code} in Room {room}"}

    # Tier 3: Structural master timetable
    #
    # Only what the nightly job would have written, and only where it has not
    # written it yet. The slots used to be read on their own, so a slot in a
    # closed cycle, or on a date outside its cycle, still put its lead in the
    # room. Worse, a day already generated was read twice: whatever tier 2 made
    # of it, a class handed to a substitute or a row marked as a lunch, tier 3
    # then answered off the slot and reported the lead as leading it. The
    # filter is the generator's own, and a slot with a row for the date is
    # left to the row, whether or not tier 2 had anything to say about it.
    days = {yesterday.isoweekday(): yesterday, today.isoweekday(): today}
    unresolved = [lead for lead in unresolved if lead not in resolved]
    candidates = [
        (days[slot.day_of_week_index], slot, offering)
        for slot, offering in db.query(StructuralMasterSlot, Activity)
        .join(Activity, StructuralMasterSlot.activity_id == Activity.id)
        .join(PlanningCycle, Activity.cycle_id == PlanningCycle.id)
        .filter(
            StructuralMasterSlot.primary_lead_id.in_(unresolved),
            PlanningCycle.operational_status,
            or_(
                *(
                    and_(
                        StructuralMasterSlot.day_of_week_index == day.isoweekday(),
                        PlanningCycle.date_bounds_start <= day,
                        PlanningCycle.date_bounds_end >= day,
                    )
                    for day in days.values()
                )
            ),
        )
        .all()
    ]
    generated = {
        (slot_id, day)
        for slot_id, day in db.query(DailyLedger.master_slot_id, DailyLedger.target_date).filter(
            DailyLedger.master_slot_id.in_([slot.id for _, slot, _ in candidates]),
            DailyLedger.target_date.in_((yesterday, today)),
        )
    }
    # Leave used to reach this function only through the rows an approval
    # marks ON_LEAVE, so it answered only while one of them was running.
    # Before and after somebody's classes, or on a day with none, they read
    # as available, and on a date the nightly job had not written yet the
    # timetable put them in the room they had leave from.
    absent = {
        (person, day)
        for person, day in db.query(
            ReverseRsvpLog.submitting_user_id, ReverseRsvpLog.target_absence_date
        ).filter(
            ReverseRsvpLog.submitting_user_id.in_(unresolved),
            ReverseRsvpLog.target_absence_date.in_(list(days.values())),
            ReverseRsvpLog.approval_state == LogVerificationState.VERIFIED_APPROVED,
        )
    }
    candidates.sort(key=lambda found: (found[0], found[1].time_window_start))
    for day, slot, offering in candidates:
        if (slot.id, day) in generated:
            continue
        if slot.primary_lead_id not in resolved and _covers(
            day, slot.time_window_start, slot.time_window_end, instant
        ):
            if (slot.primary_lead_id, day) in absent:
                # What the nightly job writes for this slot on this date.
                resolved[slot.primary_lead_id] = {
                    "resolved_location": "OFF_SITE",
                    "status": "On Approved Leave",
                }
                continue
            resolved[slot.primary_lead_id] = {
                "resolved_location": slot.target_room_identifier,
                "status": f"Leading {offering.activity_code} in Room {slot.target_room_identifier}",
            }

    # The rest of a day of leave. Only today's: yesterday's leave is over,
    # and a night shift from yesterday still running has answered above.
    for lead in unresolved:
        if lead not in resolved and (lead, today) in absent:
            resolved[lead] = {"resolved_location": "OFF_SITE", "status": "On Approved Leave"}

    # Tier 4: Base station fallback
    #
    # No base station is the normal state now that the column has no default,
    # and the field is a plain string to every client, so it is filled in here
    # rather than handed out as null.
    for person in staff:
        if person.id not in resolved:
            resolved[person.id] = {
                "resolved_location": person.assigned_base_station or "Unassigned",
                "status": "Available / Unassigned",
            }
    return resolved
