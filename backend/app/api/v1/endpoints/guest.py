# Copyright 2026 Chronos Ledger Contributors
# Licensed under the Apache License, Version 2.0


from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from app.core import rate_limit
from app.core.config import get_settings
from app.core.database import get_db
from app.core.security import generate_visit_code, get_current_user, hash_visit_code
from app.core.websocket_manager import socket_broker
from app.models.db import (
    AccessReadiness,
    GuestGateRegistry,
    InstitutionalRole,
    LogVerificationState,
    User,
)
from app.schemas.guest import (
    GuestCheckInRequest,
    GuestDecisionRequest,
    GuestResponse,
    GuestVisitStatus,
    StaffAvailabilityResponse,
)

router = APIRouter()

_AVAILABILITY_LABELS = {
    AccessReadiness.OPEN_AD_HOC: "Available",
    AccessReadiness.VERY_FREE: "Very Available",
    AccessReadiness.BUSY: "Occupied",
    AccessReadiness.CRITICAL_DO_NOT_DISTURB: "Do Not Disturb",
}


@router.post("/register-checkin")
def process_guest_entry(
    payload: GuestCheckInRequest,
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db),
    # The visitor does not sign in; the kiosk device does, with an API key an
    # admin issues it once. It turns anonymous callers away before they reach
    # the visitor log, and it is what the rate limit below counts against.
    caller: User = Depends(get_current_user),
):
    # Keyed on the account the kiosk key belongs to rather than the address it
    # dialled from: a lobby tablet on the guest network changes address, and
    # two kiosks behind one router would otherwise share a budget.
    budget = get_settings().rate_limit_guest_checkin
    window = rate_limit.GUEST_WINDOW_SECONDS
    rate_limit.guard(
        "guest-checkin", caller.id, budget, window, "visitor check-ins from this device"
    )
    rate_limit.spend("guest-checkin", caller.id, budget, window)

    staff = db.query(User).filter(User.id == payload.target_staff_id).first()
    if (
        not staff
        or staff.deactivated_at is not None
        or staff.role_type
        not in (
            InstitutionalRole.STAFF,
            InstitutionalRole.SUPER_ADMIN,
            InstitutionalRole.UNIT_ADMIN,
        )
    ):
        raise HTTPException(status_code=404, detail="Staff member not found")

    visit_code = generate_visit_code()
    entry = GuestGateRegistry(
        guest_name=payload.guest_name,
        contact_phone=payload.contact_phone,
        originating_body=payload.originating_body,
        target_staff_id=payload.target_staff_id,
        visitation_intent=payload.visitation_intent,
        visit_code_hash=hash_visit_code(visit_code),
    )
    db.add(entry)
    db.commit()
    db.refresh(entry)

    # The socket belongs to the event loop, so the notice goes out from there
    # once the response is sent, as with the absence notices.
    background_tasks.add_task(
        socket_broker.forward_direct_message,
        payload.target_staff_id,
        "GUEST_HANDSHAKE_REQ",
        {
            "transaction_reference": entry.id,
            "guest_name": payload.guest_name,
            "organization": payload.originating_body,
            "intent": payload.visitation_intent,
        },
    )
    # The visit code exists here and nowhere else; the row keeps its hash.
    return {
        "registration_state": "PENDING_STAFF_AUTH",
        "reference_token": entry.id,
        "visit_code": visit_code,
    }


@router.patch("/{entry_id}/decide")
def decide_guest_entry(
    entry_id: int,
    payload: GuestDecisionRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    entry = (
        db.query(GuestGateRegistry)
        .filter(
            GuestGateRegistry.id == entry_id,
            GuestGateRegistry.target_staff_id == current_user.id,
        )
        .first()
    )
    if not entry:
        raise HTTPException(status_code=404, detail="Entry not found or not authorized")

    entry.handshake_status = payload.decision
    db.commit()
    return {"status": payload.decision.value, "guest": entry.guest_name}


@router.get("/visit/{code}", response_model=GuestVisitStatus)
def get_visit_status(code: str, db: Session = Depends(get_db)):
    # No credential. The visitor has no account and the phone they follow the
    # check-in from holds no kiosk key, so the code is the credential, and it
    # opens one check-in's status and nothing about who made it or whom they
    # came to see. core/rate_limit.py says why it carries no budget.
    digest = hash_visit_code(code)
    # A None digest must not reach the filter: compared with None the column
    # reads IS NULL, which is every check-in made before there were codes.
    entry = (
        db.query(GuestGateRegistry).filter(GuestGateRegistry.visit_code_hash == digest).first()
        if digest
        else None
    )
    if entry is None:
        raise HTTPException(status_code=404, detail="No visit with that code")
    return entry


@router.get("/pending", response_model=list[GuestResponse])
def get_pending_guests(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    return (
        db.query(GuestGateRegistry)
        .filter(
            GuestGateRegistry.target_staff_id == current_user.id,
            GuestGateRegistry.handshake_status == LogVerificationState.PENDING_VERIFICATION,
        )
        .all()
    )


@router.get("/directory", response_model=list[StaffAvailabilityResponse])
def get_staff_directory(
    name: str | None = Query(default=None, min_length=2, max_length=100),
    db: Session = Depends(get_db),
    # Same kiosk credential. This response is the staff roster plus each
    # person's live presence, so it is not something to hand out anonymously.
    _caller: User = Depends(get_current_user),
):
    q = db.query(User).filter(
        User.role_type == InstitutionalRole.STAFF, User.deactivated_at.is_(None)
    )
    if name:
        q = q.filter(User.full_name.ilike(f"%{name}%"))
    return [
        StaffAvailabilityResponse(
            staff_id=f.id,
            full_name=f.full_name,
            unit_code=f.unit_code,
            availability_label=_AVAILABILITY_LABELS.get(f.current_occupancy_index, "Unknown"),
        )
        for f in q.limit(20).all()
    ]
