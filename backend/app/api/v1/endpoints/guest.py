# Copyright 2026 Chronos Ledger Contributors
# Licensed under the Apache License, Version 2.0

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from typing import List

from app.core.database import get_db
from app.core.security import get_current_user
from app.models.db import (
    GuestGateRegistry,
    User,
    LogVerificationState,
    InstitutionalRole,
    AccessReadiness,
)
from app.schemas.guest import (
    GuestCheckInRequest,
    GuestDecisionRequest,
    GuestResponse,
    FacultyAvailabilityResponse,
)
from app.core.websocket_manager import socket_broker

router = APIRouter()

_AVAILABILITY_LABELS = {
    AccessReadiness.OPEN_AD_HOC: "Available",
    AccessReadiness.VERY_FREE: "Very Available",
    AccessReadiness.BUSY: "Occupied",
    AccessReadiness.CRITICAL_DO_NOT_DISTURB: "Do Not Disturb",
}


@router.post("/register-checkin")
async def process_guest_entry(payload: GuestCheckInRequest, db: Session = Depends(get_db)):
    faculty = db.query(User).filter(User.id == payload.target_faculty_id).first()
    if not faculty or faculty.role_type not in (
        InstitutionalRole.FACULTY,
        InstitutionalRole.SUPER_ADMIN,
        InstitutionalRole.DEPT_ADMIN,
    ):
        raise HTTPException(status_code=404, detail="Faculty member not found")

    entry = GuestGateRegistry(
        guest_name=payload.guest_name,
        contact_phone=payload.contact_phone,
        originating_body=payload.originating_body,
        target_faculty_id=payload.target_faculty_id,
        visitation_intent=payload.visitation_intent,
    )
    db.add(entry)
    db.commit()
    db.refresh(entry)

    await socket_broker.forward_direct_message(
        payload.target_faculty_id,
        "GUEST_HANDSHAKE_REQ",
        {
            "transaction_reference": entry.id,
            "guest_name": payload.guest_name,
            "organization": payload.originating_body,
            "intent": payload.visitation_intent,
        },
    )
    return {"registration_state": "PENDING_FACULTY_AUTH", "reference_token": entry.id}


@router.patch("/{entry_id}/decide")
async def decide_guest_entry(
    entry_id: int,
    payload: GuestDecisionRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    entry = (
        db.query(GuestGateRegistry)
        .filter(
            GuestGateRegistry.id == entry_id,
            GuestGateRegistry.target_faculty_id == current_user.id,
        )
        .first()
    )
    if not entry:
        raise HTTPException(status_code=404, detail="Entry not found or not authorized")

    entry.handshake_status = payload.decision
    db.commit()
    return {"status": payload.decision.value, "guest": entry.guest_name}


@router.get("/pending", response_model=List[GuestResponse])
def get_pending_guests(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    return (
        db.query(GuestGateRegistry)
        .filter(
            GuestGateRegistry.target_faculty_id == current_user.id,
            GuestGateRegistry.handshake_status == LogVerificationState.PENDING_VERIFICATION,
        )
        .all()
    )


@router.get("/directory", response_model=List[FacultyAvailabilityResponse])
def get_faculty_directory(name: str | None = None, db: Session = Depends(get_db)):
    q = db.query(User).filter(User.role_type == InstitutionalRole.FACULTY)
    if name:
        q = q.filter(User.full_name.ilike(f"%{name}%"))
    return [
        FacultyAvailabilityResponse(
            faculty_id=f.id,
            full_name=f.full_name,
            department_code=f.department_code,
            availability_label=_AVAILABILITY_LABELS.get(f.current_occupancy_index, "Unknown"),
        )
        for f in q.limit(20).all()
    ]
