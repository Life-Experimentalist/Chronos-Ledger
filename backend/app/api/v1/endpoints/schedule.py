# Copyright 2026 Chronos Ledger Contributors
# Licensed under the Apache License, Version 2.0

import datetime

from fastapi import APIRouter, Depends, HTTPException
from fastapi.encoders import jsonable_encoder
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.redis_client import get_redis
from app.core.security import ensure_unit_scope, get_current_user, require_roles
from app.models.db import Activity, DailyLedger, PlanningCycle, StructuralMasterSlot, User
from app.schemas.resources import ReservationConflict
from app.schemas.schedule import (
    DailyLedgerUpdate,
    MasterSlotCreate,
    MasterSlotUpdate,
    PlanningCycleCreate,
    PlanningCycleResponse,
    StaffLocationResponse,
)
from app.services.availability import held_against_slot
from app.services.location_resolver import determine_staff_current_state
from app.services.master_slot import propagate_slot_corrections, rows_in_use
from app.services.resource import get_or_create_room

router = APIRouter()

ROOM_IS_HELD = "the resource is held for part of that window"


def _refuse_if_held(db, cycle, resource_id, weekday, start, end) -> None:
    """Refuse a slot that would be laid on top of a booking.

    Chronos refused an external booking that clashed with a class and did
    not refuse a class that clashed with an external booking, so a timetable
    edit could take a room out from under the system holding it, silently.
    Both directions are the same rule now.

    A slot in a closed cycle is not checked, because it does not occupy the
    room: booked_slots counts open cycles only, and a booking is already
    accepted on top of a closed cycle's slot. Checking here would make the
    two directions disagree the other way round.

    The body is the one POST /resources/{id}/reservations sends when it
    refuses, so an integrator reads a clash the same way whichever end it
    came from.
    """
    if cycle is None or not cycle.operational_status:
        return
    conflicts = held_against_slot(db, resource_id, weekday, start, end)
    if conflicts:
        raise HTTPException(
            status_code=409,
            detail=jsonable_encoder({"message": ROOM_IS_HELD, "conflicts": conflicts}),
        )


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
            "resource_id": s.resource_id,
            "target_room_identifier": s.target_room_identifier,
        }
        for s in q.all()
    ]


@router.post("/slots", responses={409: {"model": ReservationConflict}})
def create_master_slot(
    payload: MasterSlotCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_roles("SUPER_ADMIN", "UNIT_ADMIN")),
):
    offering = db.query(Activity).filter(Activity.id == payload.activity_id).first()
    if not offering:
        raise HTTPException(status_code=404, detail="Activity offering not found")
    ensure_unit_scope(current_user, offering.unit_code)
    room = get_or_create_room(payload.target_room_identifier, db)
    _refuse_if_held(
        db,
        offering.cycle,
        room.id,
        payload.day_of_week_index,
        payload.time_window_start,
        payload.time_window_end,
    )
    # room.code, not the payload: get_or_create_room strips the name, and a
    # slot whose mirror is spelled differently from its resource is exactly
    # the drift the resource table exists to end.
    slot = StructuralMasterSlot(
        **payload.model_dump(exclude={"target_room_identifier"}),
        resource_id=room.id,
        target_room_identifier=room.code,
    )
    db.add(slot)
    db.commit()
    db.refresh(slot)
    return {"id": slot.id}


@router.patch("/slots/{slot_id}", responses={409: {"model": ReservationConflict}})
def update_master_slot(
    slot_id: int,
    payload: MasterSlotUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_roles("SUPER_ADMIN", "UNIT_ADMIN")),
):
    """Change a slot, and take the days it has already produced with it.

    Times need no propagation: a ledger row has no times of its own and
    reads them off the slot. That also means moving a class to 10:00 shows
    every day it has already run at 10:00, which is wrong for the days that
    ran at 09:00 and stays wrong until the ledger carries its own window.

    Lead and room are copied onto the days that are still plans, by the same
    function the importer uses, so a correction typed into the API and a
    correction uploaded as a CSV reach the same rows and skip the same ones.

    Moving the slot to another weekday is the one change that cannot be
    copied across: the days already generated sit on the old weekday and
    there is no version of them on the new one. Those are withdrawn so the
    generator can lay them down again, and the request is refused outright
    if any of them has already been marked.
    """
    slot = db.query(StructuralMasterSlot).filter(StructuralMasterSlot.id == slot_id).first()
    if not slot:
        raise HTTPException(status_code=404, detail="Master slot not found")
    ensure_unit_scope(current_user, slot.activity.unit_code)

    fields = payload.model_dump(exclude_unset=True)
    start = fields.get("time_window_start", slot.time_window_start)
    end = fields.get("time_window_end", slot.time_window_end)
    if end <= start:
        raise HTTPException(
            status_code=422,
            detail="time_window_end must be after time_window_start",
        )

    weekday = fields.get("day_of_week_index", slot.day_of_week_index)

    # The room is resolved and the holds are checked before anything is
    # withdrawn or written, so a refusal leaves the slot and the days it has
    # already produced exactly as they were. Nothing is committed on this
    # path, so a room created on the way to a refusal never lands.
    moving_to = None
    if "target_room_identifier" in fields:
        moving_to = get_or_create_room(fields.pop("target_room_identifier"), db)
    resource_id = moving_to.id if moving_to else slot.resource_id
    if (resource_id, weekday, start, end) != (
        slot.resource_id,
        slot.day_of_week_index,
        slot.time_window_start,
        slot.time_window_end,
    ):
        # Only when the change would actually move the class. A hold sitting
        # on a slot's own window predates this rule or was written straight
        # into the database, and either way changing that slot's lead must
        # not be refused over it: there would be no way to fix the lead
        # short of cancelling somebody else's booking. The same guard the
        # CSV importer uses, for the same reason.
        _refuse_if_held(db, slot.activity.cycle, resource_id, weekday, start, end)

    removed = 0
    if weekday != slot.day_of_week_index:
        removed = _withdraw_planned_days(slot, db, "moved to another weekday")

    if moving_to is not None:
        slot.resource_id = moving_to.id
        slot.target_room_identifier = moving_to.code
    for field, value in fields.items():
        setattr(slot, field, value)

    result = propagate_slot_corrections([slot], db)
    db.commit()
    return {**result, "ledger_rows_removed": removed}


@router.delete("/slots/{slot_id}")
def delete_master_slot(
    slot_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_roles("SUPER_ADMIN", "UNIT_ADMIN")),
):
    """Take a slot off the timetable without taking its history with it.

    A class that ran for six weeks and then stopped is the ordinary reason
    to call this, so the six weeks have to survive it. Days from today
    onward are still only plans and are removed; days already past keep
    everything recorded on them and are left with no slot to point at.
    """
    slot = db.query(StructuralMasterSlot).filter(StructuralMasterSlot.id == slot_id).first()
    if not slot:
        raise HTTPException(status_code=404, detail="Master slot not found")
    ensure_unit_scope(current_user, slot.activity.unit_code)

    detached = (
        db.query(DailyLedger)
        .filter(
            DailyLedger.master_slot_id == slot.id,
            DailyLedger.target_date < datetime.date.today(),
        )
        .count()
    )
    removed = _withdraw_planned_days(slot, db, "deleted")
    db.delete(slot)
    db.commit()
    return {"ledger_rows_removed": removed, "ledger_rows_detached": detached}


def _withdraw_planned_days(slot: StructuralMasterSlot, db: Session, why: str) -> int:
    """Remove the days this slot has laid down that have not happened yet.

    Today counts as not yet happened. A day nobody has marked is a plan and
    withdrawing it costs nothing; a day somebody has marked is a record, and
    rather than quietly keep it as a class that no longer exists anywhere in
    the timetable, the whole request is refused and the dates are named.
    """
    planned = (
        db.query(DailyLedger)
        .filter(
            DailyLedger.master_slot_id == slot.id,
            DailyLedger.target_date >= datetime.date.today(),
        )
        .all()
    )
    blocked = rows_in_use([row.id for row in planned], db)
    if blocked:
        dates = sorted(str(row.target_date) for row in planned if row.id in blocked)
        raise HTTPException(
            status_code=409,
            detail=(
                f"This slot cannot be {why} while days it has produced carry "
                f"attendance or notes: {', '.join(dates)}"
            ),
        )
    for row in planned:
        db.delete(row)
    return len(planned)


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
                "resource_id": e.resource_id,
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
