# Copyright 2026 Chronos Ledger Contributors
# Licensed under the Apache License, Version 2.0

from datetime import UTC, datetime

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.security import get_current_user, in_unit_scope
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


def _fence_target(ledger: DailyLedger) -> tuple[float, float, float | None] | None:
    """Where this session physically is, if anywhere says.

    The day's own coordinates win, since they are the override an admin sets
    when one day of something happens somewhere else. Otherwise the room's,
    which is where a fence normally comes from: nothing writes the day's copy
    on its own, so before rooms could carry coordinates this check had no way
    to engage at all.

    Taken as a whole triple from whichever source supplies the pair, never an
    altitude from the room read against a latitude from the day.
    """
    if ledger.latitude_target is not None and ledger.longitude_target is not None:
        return (
            float(ledger.latitude_target),
            float(ledger.longitude_target),
            float(ledger.altitude_target) if ledger.altitude_target is not None else None,
        )
    room = ledger.resource
    if room is not None and room.latitude is not None and room.longitude is not None:
        return (
            float(room.latitude),
            float(room.longitude),
            float(room.altitude_target) if room.altitude_target is not None else None,
        )
    return None


def _ledger_or_404(db: Session, ledger_id: int) -> DailyLedger:
    ledger = db.query(DailyLedger).filter(DailyLedger.id == ledger_id).first()
    if not ledger:
        raise HTTPException(status_code=404, detail="Ledger instance not found")
    return ledger


def _has_ledger_authority(current_user: User, ledger: DailyLedger) -> bool:
    """Whether this user runs this session, as far as the record is concerned.

    The assigned or substitute lead does. Anyone else has to be an admin, and
    a unit admin only within their own unit. Everything that reads or writes
    somebody else's line on a session asks this: marking it, the roster, and
    the notes against it.
    """
    if current_user.id in (ledger.active_lead_id, ledger.substitute_lead_id):
        return True
    if current_user.role_type.value not in ("SUPER_ADMIN", "UNIT_ADMIN"):
        return False
    return in_unit_scope(current_user, ledger.activity.unit_code)


def _ensure_ledger_authority(current_user: User, ledger: DailyLedger) -> None:
    if not _has_ledger_authority(current_user, ledger):
        raise HTTPException(status_code=403, detail="Not authorized for this ledger")


@router.post("/mark")
async def mark_attendance(
    payload: AttendanceMarkRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    ledger = _ledger_or_404(db, payload.ledger_instance_id)

    # Members can only mark their own attendance; must pass geo validation
    if current_user.role_type.value == "MEMBER":
        if payload.member_id != current_user.id:
            raise HTTPException(status_code=403, detail="Cannot mark attendance for another member")

        # The horizontal target is what makes a session fenced. Altitude is
        # optional on both sides: requiring altitude_target here meant a ledger
        # with only lat/lon was silently not fenced at all.
        target = _fence_target(ledger)
        if target is not None and ledger.delivery_format == ExecutionMode.PHYSICAL:
            if payload.user_lat is None or payload.user_lon is None:
                raise HTTPException(
                    status_code=400,
                    detail="This session is geo-fenced; location coordinates are required",
                )
            target_lat, target_lon, target_alt = target
            valid = validate_3d_presence(
                payload.user_lat,
                payload.user_lon,
                payload.user_alt,
                target_lat,
                target_lon,
                target_alt,
                ledger.precision_radius_meters or 15,
            )
            if not valid:
                raise HTTPException(status_code=400, detail="Location outside geofence boundary")
    else:
        _ensure_ledger_authority(current_user, ledger)

    _upsert_attendance(db, payload, current_user.id)
    return {
        "status": "marked",
        "member_id": payload.member_id,
        "marking_status": payload.marking_status.value,
    }


@router.post("/batch")
def batch_mark_attendance(
    payload: AttendanceBatchRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    ledger = _ledger_or_404(db, payload.ledger_instance_id)
    _ensure_ledger_authority(current_user, ledger)

    for record in payload.records:
        _upsert_attendance(db, record, current_user.id)

    return {"status": "batch_complete", "count": len(payload.records)}


def _upsert_attendance(db: Session, payload: AttendanceMarkRequest, agent_id: str):
    existing = (
        db.query(VerificationLedger)
        .filter(
            VerificationLedger.ledger_instance_id == payload.ledger_instance_id,
            VerificationLedger.member_id == payload.member_id,
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
            member_id=payload.member_id,
            marking_status=payload.marking_status,
            authorizing_agent_id=agent_id,
        )
        db.add(record)
    db.commit()


@router.get("/ledger/{ledger_id}", response_model=list[AttendanceResponse])
def get_attendance_for_ledger(
    ledger_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """The roster for one session, or the caller's own line in it.

    This handed the whole roster to anyone holding a token, so a member could
    count upwards through the ledger ids and read who was present at every
    session in the organization. Whoever runs the session still gets all of
    it, because marking it is their job. A member gets their own row, which
    is what a "was I marked present" screen needs and no more. Anybody else
    is refused rather than handed an empty list, because an empty list reads
    as "nobody came" and is a worse answer than a refusal.

    An API key carries the role of the account it was issued to, so an
    integration that needs whole rosters wants a key on an admin account.
    """
    ledger = _ledger_or_404(db, ledger_id)
    rows = db.query(VerificationLedger).filter(VerificationLedger.ledger_instance_id == ledger_id)
    if _has_ledger_authority(current_user, ledger):
        return rows.all()
    if current_user.role_type.value == "MEMBER":
        return rows.filter(VerificationLedger.member_id == current_user.id).all()
    raise HTTPException(status_code=403, detail="Not authorized for this ledger")


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
    """A note against one session, written by whoever runs it.

    The ledger id was taken on trust and never looked up, so any token could
    write free text onto any session in the organization, and an id matching
    nothing produced a row pointing at nothing.
    """
    ledger = _ledger_or_404(db, payload.ledger_instance_id)
    _ensure_ledger_authority(current_user, ledger)

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
    current_user: User = Depends(get_current_user),
):
    """The notes against one session, for whoever runs it.

    Unlike the roster there is no per-member row to fall back to. A note is
    about the session rather than about a person in it, and in a hospital
    that is a handover, so this is the same gate as writing one.
    """
    ledger = _ledger_or_404(db, ledger_id)
    _ensure_ledger_authority(current_user, ledger)
    return db.query(LedgerAnnotation).filter(LedgerAnnotation.ledger_instance_id == ledger_id).all()
