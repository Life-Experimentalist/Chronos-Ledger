# Copyright 2026 Chronos Ledger Contributors
# Licensed under the Apache License, Version 2.0

import datetime

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.redis_client import get_redis
from app.core.security import ensure_unit_scope, get_current_user, require_roles
from app.models.db import Activity, DailyLedger, PlanningCycle, StructuralMasterSlot, User
from app.schemas.schedule import (
    DailyLedgerUpdate,
    MasterSlotCreate,
    PlanningCycleCreate,
    PlanningCycleResponse,
    StaffLocationResponse,
)
from app.services.location_resolver import determine_staff_current_state

router = APIRouter()


# ── Planning Cycles ──────────────────────────────────────────────────────────


@router.get("/cycles", response_model=list[PlanningCycleResponse])
def list_cycles(db: Session = Depends(get_db), _=Depends(get_current_user)):
    return db.query(PlanningCycle).all()


@router.post("/cycles", response_model=PlanningCycleResponse)
def create_cycle(
    payload: PlanningCycleCreate,
    db: Session = Depends(get_db),
    _=Depends(require_roles("SUPER_ADMIN")),
):
    cycle = PlanningCycle(**payload.model_dump())
    db.add(cycle)
    db.commit()
    db.refresh(cycle)
    return cycle


@router.patch("/cycles/{cycle_id}/close")
def close_cycle(
    cycle_id: int, db: Session = Depends(get_db), _=Depends(require_roles("SUPER_ADMIN"))
):
    cycle = db.query(PlanningCycle).filter(PlanningCycle.id == cycle_id).first()
    if not cycle:
        raise HTTPException(status_code=404, detail="Cycle not found")
    cycle.operational_status = False
    db.commit()
    return {"message": f"Cycle {cycle_id} closed"}


@router.post("/cycles/{old_id}/clone-to/{new_id}")
def clone_cycle_offerings(
    old_id: int,
    new_id: int,
    db: Session = Depends(get_db),
    _=Depends(require_roles("SUPER_ADMIN")),
):
    old_offerings = db.query(Activity).filter(Activity.cycle_id == old_id).all()
    for offering in old_offerings:
        new = Activity(
            activity_code=offering.activity_code,
            activity_title=offering.activity_title,
            unit_code=offering.unit_code,
            cycle_id=new_id,
        )
        db.add(new)
    db.commit()
    return {"cloned": len(old_offerings)}


# ── Master Slots ──────────────────────────────────────────────────────────────


@router.get("/slots", response_model=list[dict])
def list_master_slots(
    cycle_id: int | None = None,
    db: Session = Depends(get_db),
    _=Depends(get_current_user),
):
    q = db.query(StructuralMasterSlot)
    if cycle_id:
        q = q.join(Activity).filter(Activity.cycle_id == cycle_id)
    return [
        {
            "id": s.id,
            "day_of_week_index": s.day_of_week_index,
            "time_window_start": str(s.time_window_start),
            "time_window_end": str(s.time_window_end),
            "activity_id": s.activity_id,
            "primary_lead_id": s.primary_lead_id,
            "target_room_identifier": s.target_room_identifier,
        }
        for s in q.all()
    ]


@router.post("/slots")
def create_master_slot(
    payload: MasterSlotCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_roles("SUPER_ADMIN", "UNIT_ADMIN")),
):
    offering = db.query(Activity).filter(Activity.id == payload.activity_id).first()
    if not offering:
        raise HTTPException(status_code=404, detail="Activity offering not found")
    ensure_unit_scope(current_user, offering.unit_code)
    slot = StructuralMasterSlot(**payload.model_dump())
    db.add(slot)
    db.commit()
    db.refresh(slot)
    return {"id": slot.id}


# ── Daily Ledger ──────────────────────────────────────────────────────────────


@router.get("/ledger/today")
def get_today_ledger(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    today = datetime.date.today()
    q = db.query(DailyLedger).filter(DailyLedger.target_date == today)

    if current_user.role_type.value == "STAFF":
        q = q.filter(
            (DailyLedger.active_lead_id == current_user.id)
            | (DailyLedger.substitute_lead_id == current_user.id)
        )
    elif current_user.role_type.value == "MEMBER":
        from app.models.db import ActivityEnrollment

        registered_ids = [
            r.activity_id
            for r in db.query(ActivityEnrollment)
            .filter(ActivityEnrollment.member_id == current_user.id)
            .all()
        ]
        q = q.filter(DailyLedger.activity_id.in_(registered_ids))

    entries = q.all()
    result = []
    for e in entries:
        slot = e.master_slot
        offering = e.activity
        result.append(
            {
                "id": e.id,
                "target_date": str(e.target_date),
                "activity_code": offering.activity_code if offering else None,
                "activity_title": offering.activity_title if offering else None,
                "target_room_identifier": e.target_room_identifier,
                "time_window_start": str(slot.time_window_start) if slot else None,
                "time_window_end": str(slot.time_window_end) if slot else None,
                "delivery_format": e.delivery_format.value,
                "virtual_connection_string": e.virtual_connection_string,
                "operational_state": e.operational_state.value,
                "active_lead_id": e.active_lead_id,
                "substitute_lead_id": e.substitute_lead_id,
                "latitude_target": float(e.latitude_target) if e.latitude_target else None,
                "longitude_target": float(e.longitude_target) if e.longitude_target else None,
                "altitude_target": float(e.altitude_target) if e.altitude_target else None,
                "precision_radius_meters": e.precision_radius_meters,
            }
        )
    return result


@router.patch("/ledger/{ledger_id}")
def update_ledger_entry(
    ledger_id: int,
    payload: DailyLedgerUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_roles("SUPER_ADMIN", "UNIT_ADMIN")),
):
    entry = db.query(DailyLedger).filter(DailyLedger.id == ledger_id).first()
    if not entry:
        raise HTTPException(status_code=404, detail="Ledger entry not found")
    ensure_unit_scope(current_user, entry.activity.unit_code)
    for field, value in payload.model_dump(exclude_none=True).items():
        setattr(entry, field, value)
    db.commit()
    return {"message": "Updated"}


# ── Staff Location Resolution ───────────────────────────────────────────────


@router.get("/staff/{staff_id}/location", response_model=StaffLocationResponse)
def get_staff_location(
    staff_id: str,
    db: Session = Depends(get_db),
    _=Depends(get_current_user),
):
    staff = db.query(User).filter(User.id == staff_id).first()
    if not staff:
        raise HTTPException(status_code=404, detail="Staff not found")

    redis = get_redis()
    result = determine_staff_current_state(staff_id, db, redis)
    return StaffLocationResponse(
        staff_id=staff_id,
        full_name=staff.full_name,
        occupancy_index=staff.current_occupancy_index.value,
        **result,
    )


@router.get("/staff/all/locations")
def get_all_staff_locations(db: Session = Depends(get_db), _=Depends(get_current_user)):
    from app.models.db import InstitutionalRole

    staff_list = db.query(User).filter(User.role_type == InstitutionalRole.STAFF).all()
    redis = get_redis()
    results = []
    for f in staff_list:
        location = determine_staff_current_state(f.id, db, redis)
        results.append(
            {
                "staff_id": f.id,
                "full_name": f.full_name,
                "unit_code": f.unit_code,
                "occupancy_index": f.current_occupancy_index.value,
                **location,
            }
        )
    return results
