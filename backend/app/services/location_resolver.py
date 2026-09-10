# Copyright 2026 Chronos Ledger Contributors
# Licensed under the Apache License, Version 2.0

import datetime

from redis import Redis
from sqlalchemy.orm import Session

from app.core.time import org_now, window_span
from app.models.db import Activity, DailyLedger, DynamicState, StructuralMasterSlot, User


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


def determine_staff_current_state(staff_id: str, db: Session, redis_cache: Redis) -> dict:
    now = org_now()
    # The zone dropped, because a slot stores naive wall clock and carries
    # nothing saying which zone it means. Taking .time() off now used to do
    # exactly this, only the date came away with it and a window that runs
    # past midnight needs the date to say which side of it we are on.
    instant = now.replace(tzinfo=None)
    today = now.date()
    yesterday = today - datetime.timedelta(days=1)

    # Tier 1: Redis manual status override (TTL-based, e.g. "in meeting", "out for lunch")
    # redis-py returns bytes; decode before use.
    cached_raw = redis_cache.get(f"state_override:{staff_id}")
    if cached_raw:
        cached = cached_raw.decode("utf-8") if isinstance(cached_raw, bytes) else cached_raw
        # An override says what somebody is doing, not where. No location was
        # worked out at all on this path, and saying so is better than naming
        # a place the override never claimed.
        return {"resolved_location": "UNKNOWN", "status": cached}

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
    daily = next(
        (
            ledger
            for ledger in db.query(DailyLedger)
            .filter(
                DailyLedger.active_lead_id == staff_id,
                DailyLedger.target_date.in_((yesterday, today)),
                DailyLedger.time_window_start.isnot(None),
                DailyLedger.time_window_end.isnot(None),
            )
            .order_by(DailyLedger.target_date, DailyLedger.time_window_start)
            .all()
            if _covers(
                ledger.target_date,
                ledger.time_window_start,
                ledger.time_window_end,
                instant,
            )
        ),
        None,
    )
    if daily:
        ledger = daily
        if ledger.operational_state == DynamicState.ON_LEAVE:
            return {"resolved_location": "OFF_SITE", "status": "On Approved Leave"}
        if ledger.operational_state == DynamicState.PROXY_SUBSTITUTE:
            return {
                "resolved_location": ledger.target_room_identifier,
                "status": f"Substituting in Room {ledger.target_room_identifier}",
            }
        if ledger.operational_state == DynamicState.SCHEDULED:
            offering = db.query(Activity).filter(Activity.id == ledger.activity_id).first()
            return {
                "resolved_location": ledger.target_room_identifier,
                "status": f"Leading {offering.activity_code if offering else 'a session'} in Room {ledger.target_room_identifier}",
            }

    # Tier 3: Structural master timetable
    days = {yesterday.isoweekday(): yesterday, today.isoweekday(): today}
    candidates = [
        (days[slot.day_of_week_index], slot, offering)
        for slot, offering in db.query(StructuralMasterSlot, Activity)
        .join(Activity, StructuralMasterSlot.activity_id == Activity.id)
        .filter(
            StructuralMasterSlot.primary_lead_id == staff_id,
            StructuralMasterSlot.day_of_week_index.in_(list(days)),
        )
        .all()
    ]
    candidates.sort(key=lambda found: (found[0], found[1].time_window_start))
    master = next(
        (
            (slot, offering)
            for day, slot, offering in candidates
            if _covers(day, slot.time_window_start, slot.time_window_end, instant)
        ),
        None,
    )
    if master:
        slot, offering = master
        return {
            "resolved_location": slot.target_room_identifier,
            "status": f"Leading {offering.activity_code} in Room {slot.target_room_identifier}",
        }

    # Tier 4: Base station fallback
    user = db.query(User).filter(User.id == staff_id).first()
    # No base station is the normal state now that the column has no default,
    # and the field is a plain string to every client, so it is filled in here
    # rather than handed out as null.
    base = (user.assigned_base_station if user else None) or "Unassigned"
    return {"resolved_location": base, "status": "Available / Unassigned"}
