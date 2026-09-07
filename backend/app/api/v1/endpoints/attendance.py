# Copyright 2026 Chronos Ledger Contributors
# Licensed under the Apache License, Version 2.0

from datetime import UTC, datetime

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.security import get_current_user
from app.core.websocket_manager import socket_broker
from app.models.db import (
    DailyLedger,
    ExecutionMode,
    LedgerAnnotation,
    LogVerificationState,
    ReverseRsvpLog,
    User,
    VerificationLedger,
)
from app.schemas.attendance import (
    AnnotationCreate,
    AnnotationResponse,
    AttendanceBatchRequest,
    AttendanceMarkRequest,
    AttendanceResponse,
    ReverseRsvpCreate,
    ReverseRsvpResponse,
    RsvpDecision,
)
from app.services.geo_fence import validate_3d_presence
from app.services.reverse_rsvp import commit_absence_override, route_absence_declaration

router = APIRouter()


# ── Attendance Marking ────────────────────────────────────────────────────────


@router.post("/mark")
async def mark_attendance(
    payload: AttendanceMarkRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    ledger = db.query(DailyLedger).filter(DailyLedger.id == payload.ledger_instance_id).first()
    if not ledger:
        raise HTTPException(status_code=404, detail="Ledger instance not found")

    # Students can only mark their own attendance; must pass geo validation
    if current_user.role_type.value == "STUDENT":
        if payload.student_id != current_user.id:
            raise HTTPException(
                status_code=403, detail="Cannot mark attendance for another student"
            )

        geo_targets = [ledger.latitude_target, ledger.longitude_target, ledger.altitude_target]
        if (
            all(v is not None for v in geo_targets)
            and ledger.delivery_format == ExecutionMode.PHYSICAL
        ):
            coords = [payload.user_lat, payload.user_lon, payload.user_alt]
            if any(v is None for v in coords):
                raise HTTPException(
                    status_code=400,
                    detail="This session is geo-fenced; location coordinates are required",
                )
            valid = validate_3d_presence(
                payload.user_lat,
                payload.user_lon,
                payload.user_alt,
                float(ledger.latitude_target),
                float(ledger.longitude_target),
                float(ledger.altitude_target),
                ledger.precision_radius_meters or 15,
            )
            if not valid:
                raise HTTPException(status_code=400, detail="Location outside geofence boundary")

    _upsert_attendance(db, payload, current_user.id)
    return {
        "status": "marked",
        "student_id": payload.student_id,
        "marking_status": payload.marking_status.value,
    }


@router.post("/batch")
def batch_mark_attendance(
    payload: AttendanceBatchRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    ledger = db.query(DailyLedger).filter(DailyLedger.id == payload.ledger_instance_id).first()
    if not ledger:
        raise HTTPException(status_code=404, detail="Ledger instance not found")

    # Only assigned/substitute instructor can batch mark
    if current_user.id not in (
        ledger.active_instructor_id,
        ledger.substitute_instructor_id,
    ) and current_user.role_type.value not in ("SUPER_ADMIN", "DEPT_ADMIN"):
        raise HTTPException(status_code=403, detail="Not authorized to mark this ledger")

    for record in payload.records:
        _upsert_attendance(db, record, current_user.id)

    return {"status": "batch_complete", "count": len(payload.records)}


def _upsert_attendance(db: Session, payload: AttendanceMarkRequest, agent_id: str):
    existing = (
        db.query(VerificationLedger)
        .filter(
            VerificationLedger.ledger_instance_id == payload.ledger_instance_id,
            VerificationLedger.student_id == payload.student_id,
        )
        .first()
    )

    if existing:
        if existing.marking_status != payload.marking_status:
            existing.marking_status = payload.marking_status
            existing.authorizing_agent_id = agent_id
            existing.modification_timestamp = datetime.now(UTC)
    else:
        record = VerificationLedger(
            ledger_instance_id=payload.ledger_instance_id,
            student_id=payload.student_id,
            marking_status=payload.marking_status,
            authorizing_agent_id=agent_id,
        )
        db.add(record)
    db.commit()


@router.get("/ledger/{ledger_id}", response_model=list[AttendanceResponse])
def get_attendance_for_ledger(
    ledger_id: int,
    db: Session = Depends(get_db),
    _=Depends(get_current_user),
):
    return (
        db.query(VerificationLedger)
        .filter(VerificationLedger.ledger_instance_id == ledger_id)
        .all()
    )


# ── Reverse RSVP (Absence System) ────────────────────────────────────────────


@router.post("/absence", response_model=ReverseRsvpResponse)
async def submit_absence(
    payload: ReverseRsvpCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    result = route_absence_declaration(
        submitting_user=current_user.id,
        absence_date=str(payload.target_absence_date),
        reasoning=payload.context_justification,
        db=db,
    )
    log = db.query(ReverseRsvpLog).filter(ReverseRsvpLog.id == result["tracking_reference"]).first()
    await socket_broker.forward_direct_message(
        log.authorized_by_user_id,
        "ABSENCE_APPROVAL_REQUIRED",
        {
            "log_id": log.id,
            "from": current_user.full_name,
            "date": str(payload.target_absence_date),
        },
    )
    return log


@router.get("/absence/pending", response_model=list[ReverseRsvpResponse])
def get_pending_absences(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    return (
        db.query(ReverseRsvpLog)
        .filter(
            ReverseRsvpLog.authorized_by_user_id == current_user.id,
            ReverseRsvpLog.approval_state == LogVerificationState.PENDING_VERIFICATION,
        )
        .all()
    )


@router.patch("/absence/{log_id}/decide")
async def decide_absence(
    log_id: int,
    payload: RsvpDecision,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    log = (
        db.query(ReverseRsvpLog)
        .filter(
            ReverseRsvpLog.id == log_id,
            ReverseRsvpLog.authorized_by_user_id == current_user.id,
        )
        .first()
    )
    if not log:
        raise HTTPException(status_code=404, detail="Absence request not found or not authorized")

    commit_absence_override(log_id, current_user.id, payload.decision.value, db)
    await socket_broker.forward_direct_message(
        log.submitting_user_id,
        "ABSENCE_DECISION",
        {"log_id": log_id, "decision": payload.decision.value},
    )
    return {"status": payload.decision.value}


# ── Annotations ───────────────────────────────────────────────────────────────


@router.post("/annotations", response_model=AnnotationResponse)
def create_annotation(
    payload: AnnotationCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    annotation = LedgerAnnotation(
        ledger_instance_id=payload.ledger_instance_id,
        creator_id=current_user.id,
        classification_tag=payload.classification_tag,
        annotation_payload=payload.annotation_payload,
    )
    db.add(annotation)
    db.commit()
    db.refresh(annotation)
    return annotation


@router.get("/annotations/{ledger_id}", response_model=list[AnnotationResponse])
def get_annotations(
    ledger_id: int,
    db: Session = Depends(get_db),
    _=Depends(get_current_user),
):
    return db.query(LedgerAnnotation).filter(LedgerAnnotation.ledger_instance_id == ledger_id).all()
