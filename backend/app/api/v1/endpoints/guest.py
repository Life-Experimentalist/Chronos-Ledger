# Copyright 2026 Chronos Ledger Contributors
# Licensed under the Apache License, Version 2.0


from datetime import UTC, datetime, timedelta

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, Query, Response
from sqlalchemy import or_, select, true
from sqlalchemy.orm import Session

from app.core import clock, rate_limit
from app.core.config import get_settings
from app.core.database import get_db
from app.core.pagination import TOTAL_COUNT_HEADER
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
    GuestExtensionRequest,
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


def _as_utc(moment: datetime) -> datetime:
    """A stored moment as UTC: naive on SQLite and already aware on Postgres.

    The same two lines as auth.py::_as_utc, which they have no shared home for.
    """
    return moment if moment.tzinfo else moment.replace(tzinfo=UTC)


@router.post("/register-checkin", operation_id="guest.checkIn")
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
            InstitutionalRole.ORG_ADMIN,
            InstitutionalRole.UNIT_ADMIN,
        )
    ):
        raise HTTPException(status_code=404, detail="Staff member not found")

    visit_code = generate_visit_code()
    ttl_minutes = get_settings().guest_visit_code_ttl_minutes
    entry = GuestGateRegistry(
        guest_name=payload.guest_name,
        contact_phone=payload.contact_phone,
        originating_body=payload.originating_body,
        target_staff_id=payload.target_staff_id,
        visitation_intent=payload.visitation_intent,
        visit_code_hash=hash_visit_code(visit_code),
        visit_code_expires_at=(
            clock.now() + timedelta(minutes=ttl_minutes) if ttl_minutes > 0 else None
        ),
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


def _decidable_by(current_user: User):
    """The check-ins this user may decide, as a filter.

    The person the visitor came to see decides, and for a long time that was
    the only way, which stalls at the door: the visitor is standing in the
    lobby and the person they came for is in theatre or has gone home. With
    GUEST_ADMIN_CAN_DECIDE on, an admin decides those as well, an organization
    admin any of them and a unit admin those meant for their own unit.

    Unlike the absence requests this mirrors, a unit admin is not held off the
    admin accounts of their unit. An approved absence is something the person
    gets; an approved visit is somebody let in at a door, and whose door it is
    does not change the front desk's job.
    """
    mine = GuestGateRegistry.target_staff_id == current_user.id
    role = current_user.role_type.value
    if not get_settings().guest_admin_can_decide or role not in ("ORG_ADMIN", "UNIT_ADMIN"):
        return mine
    if role == "ORG_ADMIN":
        return true()
    # An admin account with no unit of its own reaches nothing this way.
    # Compared with None the column reads IS NULL, which would be every
    # account that has no unit rather than none of them.
    if current_user.unit_code is None:
        return mine
    return or_(
        mine,
        GuestGateRegistry.target_staff_id.in_(
            select(User.id).where(User.unit_code == current_user.unit_code)
        ),
    )


@router.patch("/{entry_id}/decide", operation_id="guest.decide")
def decide_guest_entry(
    entry_id: int,
    payload: GuestDecisionRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    entry = (
        db.query(GuestGateRegistry)
        .filter(GuestGateRegistry.id == entry_id, _decidable_by(current_user))
        .first()
    )
    if not entry:
        raise HTTPException(status_code=404, detail="Entry not found or not authorized")

    entry.handshake_status = payload.decision
    # Whoever it was, including the person the visitor came to see, so that the
    # row answers who let this visitor in rather than who could have.
    entry.decided_by_id = current_user.id
    # Written on every decision and not only on an approval, so a visit
    # re-decided to denied keeps no expiry from the approval it had, and a
    # re-approval starts the clock again rather than carrying an old end.
    length = get_settings().guest_visit_length_minutes
    approved = payload.decision == LogVerificationState.VERIFIED_APPROVED
    entry.visit_expires_at = (
        clock.now() + timedelta(minutes=length) if approved and length > 0 else None
    )
    entry.overstay_notified_at = None
    db.commit()
    return {"status": payload.decision.value, "guest": entry.guest_name}


@router.patch("/{entry_id}/extend", operation_id="guest.extendVisit")
def extend_guest_visit(
    entry_id: int,
    payload: GuestExtensionRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Give an approved visit longer.

    Whoever could have decided the visit can extend it, on the reasoning that a
    desk which may let somebody in may also let them stay. There is no limit on
    how many times: this bounds one grant, so an organization that wants a hard
    ceiling on a whole visit does not have one here, and the audit record of
    each extension is what it gets instead.
    """
    maximum = get_settings().guest_visit_extension_max_minutes
    if maximum == 0:
        raise HTTPException(
            status_code=422,
            detail=(
                "This organization does not extend visits. The visitor checks in again "
                "instead, or GUEST_VISIT_EXTENSION_MAX_MINUTES is raised above 0."
            ),
        )
    # Refused rather than quietly trimmed, so a desk that meant 30 and typed
    # 300 hears about it instead of wondering later why the visit ended early.
    if payload.minutes > maximum:
        raise HTTPException(
            status_code=422,
            detail=(
                f"{payload.minutes} minutes is longer than a single extension may be "
                f"here, which is {maximum}."
            ),
        )

    entry = (
        db.query(GuestGateRegistry)
        .filter(GuestGateRegistry.id == entry_id, _decidable_by(current_user))
        .first()
    )
    if not entry:
        raise HTTPException(status_code=404, detail="Entry not found or not authorized")
    if (
        entry.handshake_status != LogVerificationState.VERIFIED_APPROVED
        or entry.visit_expires_at is None
    ):
        raise HTTPException(
            status_code=409,
            detail="Only an approved visit that has an end can be extended.",
        )

    # From the later of now and the end it already has, so a visit half an hour
    # over gets the whole grant rather than a window that has already gone.
    start = max(_as_utc(entry.visit_expires_at), clock.now())
    entry.visit_expires_at = start + timedelta(minutes=payload.minutes)
    # So that running over a second time announces itself as the first did.
    entry.overstay_notified_at = None
    db.commit()
    return {
        "status": "VISIT_EXTENDED",
        "guest": entry.guest_name,
        "visit_expires_at": entry.visit_expires_at.isoformat(),
    }


@router.get("/visit/{code}", operation_id="guest.getVisit", response_model=GuestVisitStatus)
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
    # An expired code reads as one that was never issued. Saying "expired"
    # instead would confirm to whoever is trying codes that this one was real.
    if (
        entry.visit_code_expires_at is not None
        and _as_utc(entry.visit_code_expires_at) <= clock.now()
    ):
        raise HTTPException(status_code=404, detail="No visit with that code")
    return entry


@router.get("/pending", operation_id="guest.listPending", response_model=list[GuestResponse])
def get_pending_guests(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """The visitors waiting on this user, which is what the desk lists.

    The same reach as the decision itself, so an admin who may decide a visit
    can see it waiting. With GUEST_ADMIN_CAN_DECIDE on that makes this the
    whole organization's queue for an organization admin, which is the point of
    a front desk and worth knowing before switching it on.
    """
    return (
        db.query(GuestGateRegistry)
        .filter(
            _decidable_by(current_user),
            GuestGateRegistry.handshake_status == LogVerificationState.PENDING_VERIFICATION,
        )
        .all()
    )


@router.get("/overstays", operation_id="guest.listOverstays", response_model=list[GuestResponse])
def get_overstayed_visits(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Approved visits whose time has passed, longest over first.

    Which is the desk's other list: who was let in and has not been dealt with
    since. Nothing here has been revoked; the row says the time is up and a
    person decides whether to extend it or to go and find them.

    Unpaginated, as /pending is. An organization that leaves every visit
    undecided at the end of the day will find this list as long as its day was.
    """
    return (
        db.query(GuestGateRegistry)
        .filter(
            _decidable_by(current_user),
            GuestGateRegistry.handshake_status == LogVerificationState.VERIFIED_APPROVED,
            GuestGateRegistry.visit_expires_at.isnot(None),
            GuestGateRegistry.visit_expires_at <= clock.now(),
        )
        .order_by(GuestGateRegistry.visit_expires_at)
        .all()
    )


@router.get(
    "/directory", operation_id="guest.getDirectory", response_model=list[StaffAvailabilityResponse]
)
def get_staff_directory(
    response: Response,
    name: str | None = Query(default=None, min_length=2, max_length=100),
    # A kiosk shows one screen of names, so a page stays short by default. The
    # total goes back in X-Total-Count, so a search that matched more than one
    # screen says so instead of quietly stopping at the first 20.
    limit: int = Query(default=20, ge=1, le=100),
    offset: int = Query(default=0, ge=0),
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
    response.headers[TOTAL_COUNT_HEADER] = str(q.count())
    return [
        StaffAvailabilityResponse(
            staff_id=f.id,
            full_name=f.full_name,
            unit_code=f.unit_code,
            availability_label=_AVAILABILITY_LABELS.get(f.current_occupancy_index, "Unknown"),
        )
        for f in q.order_by(User.full_name, User.id).offset(offset).limit(limit).all()
    ]
