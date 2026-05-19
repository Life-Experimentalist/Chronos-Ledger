# Copyright 2026 Chronos Ledger Contributors
# Licensed under the Apache License, Version 2.0

import datetime

from redis import Redis
from sqlalchemy.orm import Session

from app.models.db import CourseOffering, DailyLedger, DynamicState, StructuralMasterSlot, User


def determine_faculty_current_state(faculty_id: str, db: Session, redis_cache: Redis) -> dict:
    now = datetime.datetime.now()
    date_str = now.date()
    day_index = now.isoweekday()

    # Tier 1 — Redis manual status override (TTL-based, e.g. "in meeting", "out for lunch")
    # redis-py returns bytes; decode before use.
    cached_raw = redis_cache.get(f"state_override:{faculty_id}")
    if cached_raw:
        cached = cached_raw.decode("utf-8") if isinstance(cached_raw, bytes) else cached_raw
        return {"resolved_location": "ISOLATED_CELL", "status": cached}

    # Tier 2 — Daily exception log (leaves, proxies, ad-hoc)
    daily = (
        db.query(DailyLedger, StructuralMasterSlot)
        .join(StructuralMasterSlot, DailyLedger.master_slot_id == StructuralMasterSlot.id)
        .filter(
            DailyLedger.active_instructor_id == faculty_id,
            DailyLedger.target_date == date_str,
            StructuralMasterSlot.time_window_start <= now.time(),
            StructuralMasterSlot.time_window_end >= now.time(),
        )
        .first()
    )
    if daily:
        ledger, slot = daily
        if ledger.operational_state == DynamicState.ON_LEAVE:
            return {"resolved_location": "OFF_CAMPUS", "status": "On Approved Leave"}
        if ledger.operational_state == DynamicState.PROXY_SUBSTITUTE:
            return {
                "resolved_location": ledger.target_room_identifier,
                "status": f"Substituting in Room {ledger.target_room_identifier}",
            }
        if ledger.operational_state == DynamicState.SCHEDULED:
            offering = (
                db.query(CourseOffering)
                .filter(CourseOffering.id == ledger.course_offering_id)
                .first()
            )
            return {
                "resolved_location": ledger.target_room_identifier,
                "status": f"Teaching {offering.course_code if offering else 'class'} in Room {ledger.target_room_identifier}",
            }

    # Tier 3 — Structural master timetable
    master = (
        db.query(StructuralMasterSlot, CourseOffering)
        .join(CourseOffering, StructuralMasterSlot.course_offering_id == CourseOffering.id)
        .filter(
            StructuralMasterSlot.primary_instructor_id == faculty_id,
            StructuralMasterSlot.day_of_week_index == day_index,
            StructuralMasterSlot.time_window_start <= now.time(),
            StructuralMasterSlot.time_window_end >= now.time(),
        )
        .first()
    )
    if master:
        slot, offering = master
        return {
            "resolved_location": slot.target_room_identifier,
            "status": f"Teaching {offering.course_code} in Room {slot.target_room_identifier}",
        }

    # Tier 4 — Base station fallback
    user = db.query(User).filter(User.id == faculty_id).first()
    base = user.assigned_base_station if user else "Staff Room"
    return {"resolved_location": base, "status": "Available / Unassigned"}
