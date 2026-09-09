# Copyright 2026 Chronos Ledger Contributors
# Licensed under the Apache License, Version 2.0


from redis import Redis
from sqlalchemy.orm import Session

from app.core.time import org_now
from app.models.db import Activity, DailyLedger, DynamicState, StructuralMasterSlot, User


def determine_staff_current_state(staff_id: str, db: Session, redis_cache: Redis) -> dict:
    now = org_now()
    date_str = now.date()
    day_index = now.isoweekday()

    # Tier 1: Redis manual status override (TTL-based, e.g. "in meeting", "out for lunch")
    # redis-py returns bytes; decode before use.
    cached_raw = redis_cache.get(f"state_override:{staff_id}")
    if cached_raw:
        cached = cached_raw.decode("utf-8") if isinstance(cached_raw, bytes) else cached_raw
        return {"resolved_location": "ISOLATED_CELL", "status": cached}

    # Tier 2: Daily exception log (leaves, proxies, ad-hoc)
    daily = (
        db.query(DailyLedger, StructuralMasterSlot)
        .join(StructuralMasterSlot, DailyLedger.master_slot_id == StructuralMasterSlot.id)
        .filter(
            DailyLedger.active_lead_id == staff_id,
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
            offering = db.query(Activity).filter(Activity.id == ledger.activity_id).first()
            return {
                "resolved_location": ledger.target_room_identifier,
                "status": f"Teaching {offering.activity_code if offering else 'class'} in Room {ledger.target_room_identifier}",
            }

    # Tier 3: Structural master timetable
    master = (
        db.query(StructuralMasterSlot, Activity)
        .join(Activity, StructuralMasterSlot.activity_id == Activity.id)
        .filter(
            StructuralMasterSlot.primary_lead_id == staff_id,
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
            "status": f"Teaching {offering.activity_code} in Room {slot.target_room_identifier}",
        }

    # Tier 4: Base station fallback
    user = db.query(User).filter(User.id == staff_id).first()
    base = user.assigned_base_station if user else "Staff Room"
    return {"resolved_location": base, "status": "Available / Unassigned"}
