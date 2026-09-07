# Copyright 2026 Chronos Ledger Contributors
# Licensed under the Apache License, Version 2.0

import datetime

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.redis_client import get_redis
from app.core.security import ensure_department_scope, get_current_user, require_roles
from app.models.db import AcademicCycle, CourseOffering, DailyLedger, StructuralMasterSlot, User
from app.schemas.schedule import (
    AcademicCycleCreate,
    AcademicCycleResponse,
    DailyLedgerUpdate,
    FacultyLocationResponse,
    MasterSlotCreate,
)
from app.services.location_resolver import determine_faculty_current_state

router = APIRouter()


# ── Academic Cycles ──────────────────────────────────────────────────────────


@router.get("/cycles", response_model=list[AcademicCycleResponse])
def list_cycles(db: Session = Depends(get_db), _=Depends(get_current_user)):
    return db.query(AcademicCycle).all()


@router.post("/cycles", response_model=AcademicCycleResponse)
def create_cycle(
    payload: AcademicCycleCreate,
    db: Session = Depends(get_db),
    _=Depends(require_roles("SUPER_ADMIN")),
):
    cycle = AcademicCycle(**payload.model_dump())
    db.add(cycle)
    db.commit()
    db.refresh(cycle)
    return cycle


@router.patch("/cycles/{cycle_id}/close")
def close_cycle(
    cycle_id: int, db: Session = Depends(get_db), _=Depends(require_roles("SUPER_ADMIN"))
):
    cycle = db.query(AcademicCycle).filter(AcademicCycle.id == cycle_id).first()
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
    old_offerings = db.query(CourseOffering).filter(CourseOffering.cycle_id == old_id).all()
    for offering in old_offerings:
        new = CourseOffering(
            course_code=offering.course_code,
            course_title=offering.course_title,
            department_code=offering.department_code,
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
        q = q.join(CourseOffering).filter(CourseOffering.cycle_id == cycle_id)
    return [
        {
            "id": s.id,
            "day_of_week_index": s.day_of_week_index,
            "time_window_start": str(s.time_window_start),
            "time_window_end": str(s.time_window_end),
            "course_offering_id": s.course_offering_id,
            "primary_instructor_id": s.primary_instructor_id,
            "target_room_identifier": s.target_room_identifier,
        }
        for s in q.all()
    ]


@router.post("/slots")
def create_master_slot(
    payload: MasterSlotCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_roles("SUPER_ADMIN", "DEPT_ADMIN")),
):
    offering = (
        db.query(CourseOffering).filter(CourseOffering.id == payload.course_offering_id).first()
    )
    if not offering:
        raise HTTPException(status_code=404, detail="Course offering not found")
    ensure_department_scope(current_user, offering.department_code)
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

    if current_user.role_type.value == "FACULTY":
        q = q.filter(
            (DailyLedger.active_instructor_id == current_user.id)
            | (DailyLedger.substitute_instructor_id == current_user.id)
        )
    elif current_user.role_type.value == "STUDENT":
        from app.models.db import CourseRegistration

        registered_ids = [
            r.course_offering_id
            for r in db.query(CourseRegistration)
            .filter(CourseRegistration.student_id == current_user.id)
            .all()
        ]
        q = q.filter(DailyLedger.course_offering_id.in_(registered_ids))

    entries = q.all()
    result = []
    for e in entries:
        slot = e.master_slot
        offering = e.course_offering
        result.append(
            {
                "id": e.id,
                "target_date": str(e.target_date),
                "course_code": offering.course_code if offering else None,
                "course_title": offering.course_title if offering else None,
                "target_room_identifier": e.target_room_identifier,
                "time_window_start": str(slot.time_window_start) if slot else None,
                "time_window_end": str(slot.time_window_end) if slot else None,
                "delivery_format": e.delivery_format.value,
                "virtual_connection_string": e.virtual_connection_string,
                "operational_state": e.operational_state.value,
                "active_instructor_id": e.active_instructor_id,
                "substitute_instructor_id": e.substitute_instructor_id,
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
    current_user: User = Depends(require_roles("SUPER_ADMIN", "DEPT_ADMIN")),
):
    entry = db.query(DailyLedger).filter(DailyLedger.id == ledger_id).first()
    if not entry:
        raise HTTPException(status_code=404, detail="Ledger entry not found")
    ensure_department_scope(current_user, entry.course_offering.department_code)
    for field, value in payload.model_dump(exclude_none=True).items():
        setattr(entry, field, value)
    db.commit()
    return {"message": "Updated"}


# ── Faculty Location Resolution ───────────────────────────────────────────────


@router.get("/faculty/{faculty_id}/location", response_model=FacultyLocationResponse)
def get_faculty_location(
    faculty_id: str,
    db: Session = Depends(get_db),
    _=Depends(get_current_user),
):
    faculty = db.query(User).filter(User.id == faculty_id).first()
    if not faculty:
        raise HTTPException(status_code=404, detail="Faculty not found")

    redis = get_redis()
    result = determine_faculty_current_state(faculty_id, db, redis)
    return FacultyLocationResponse(
        faculty_id=faculty_id,
        full_name=faculty.full_name,
        occupancy_index=faculty.current_occupancy_index.value,
        **result,
    )


@router.get("/faculty/all/locations")
def get_all_faculty_locations(db: Session = Depends(get_db), _=Depends(get_current_user)):
    from app.models.db import InstitutionalRole

    faculty_list = db.query(User).filter(User.role_type == InstitutionalRole.FACULTY).all()
    redis = get_redis()
    results = []
    for f in faculty_list:
        location = determine_faculty_current_state(f.id, db, redis)
        results.append(
            {
                "faculty_id": f.id,
                "full_name": f.full_name,
                "department_code": f.department_code,
                "occupancy_index": f.current_occupancy_index.value,
                **location,
            }
        )
    return results
