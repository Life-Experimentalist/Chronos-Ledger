# Copyright 2026 Chronos Ledger Contributors
# Licensed under the Apache License, Version 2.0

from datetime import UTC, datetime

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, status
from sqlalchemy import or_
from sqlalchemy.orm import Session

from app.api.v1.endpoints.websocket import CLOSE_UNAUTHENTICATED
from app.core.database import get_db
from app.core.pagination import Page
from app.core.security import (
    ensure_unit_scope,
    generate_password,
    get_current_user,
    hash_password,
    require_roles,
)
from app.core.time import org_today
from app.core.websocket_manager import socket_broker
from app.models.db import (
    Activity,
    ApiKey,
    DailyLedger,
    InstitutionalRole,
    LogVerificationState,
    PlanningCycle,
    RefreshToken,
    ReverseRsvpLog,
    StructuralMasterSlot,
    User,
    generate_feed_token,
)
from app.schemas.users import (
    DeactivatedUserResponse,
    OpenItems,
    PasswordResetResponse,
    UserCreate,
    UserResponse,
    UserStatusUpdate,
    UserUpdate,
)

router = APIRouter()


def _check_manager(user_id: str, manager_id: str, db: Session) -> None:
    """Refuse a manager who does not exist, is deactivated, or already reports to the user.

    Absence requests go to the manager for approval, so a user set as their
    own manager approves their own, a deactivated one cannot sign in to
    approve anything, and a loop of any length is a reporting line with
    nobody at the top of it.
    """
    if manager_id == user_id:
        raise HTTPException(status_code=422, detail="A user cannot be their own manager")
    row = (
        db.query(User.reporting_line_manager, User.deactivated_at)
        .filter(User.id == manager_id)
        .first()
    )
    if row is None:
        raise HTTPException(status_code=404, detail="Manager not found")
    if row[1] is not None:
        raise HTTPException(status_code=422, detail="Manager is deactivated")
    above, seen = row[0], {manager_id}
    # A loop the user is not in can predate this check; stop rather than spin.
    while above is not None and above not in seen:
        if above == user_id:
            raise HTTPException(
                status_code=422,
                detail=f"{manager_id} already reports to {user_id}, directly or through others",
            )
        seen.add(above)
        above = db.query(User.reporting_line_manager).filter(User.id == above).scalar()


@router.get("/", response_model=list[UserResponse])
def list_users(
    role: str | None = None,
    unit: str | None = None,
    include_deactivated: bool = False,
    page: Page = Depends(),
    db: Session = Depends(get_db),
    current_user: User = Depends(require_roles("SUPER_ADMIN", "UNIT_ADMIN")),
):
    q = db.query(User)
    if not include_deactivated:
        q = q.filter(User.deactivated_at.is_(None))
    if role:
        q = q.filter(User.role_type == role)
    if unit:
        q = q.filter(User.unit_code == unit)
    # A unit admin only ever sees their own unit, whatever they ask for.
    if current_user.role_type == InstitutionalRole.UNIT_ADMIN:
        q = q.filter(User.unit_code == current_user.unit_code)
    return page.rows(q, User.id)


@router.post("/", response_model=UserResponse, status_code=status.HTTP_201_CREATED)
def create_user(
    payload: UserCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_roles("SUPER_ADMIN", "UNIT_ADMIN")),
):
    admin_roles = (InstitutionalRole.SUPER_ADMIN, InstitutionalRole.UNIT_ADMIN)
    if payload.role_type in admin_roles and current_user.role_type != InstitutionalRole.SUPER_ADMIN:
        raise HTTPException(status_code=403, detail="Only a super-admin can create admin accounts")
    ensure_unit_scope(current_user, payload.unit_code)
    if db.query(User).filter(User.id == payload.id).first():
        raise HTTPException(status_code=409, detail="User ID already exists")
    if db.query(User).filter(User.email_address == payload.email_address).first():
        raise HTTPException(status_code=409, detail="Email already registered")
    if payload.reporting_line_manager is not None:
        _check_manager(payload.id, payload.reporting_line_manager, db)

    user = User(
        id=payload.id,
        full_name=payload.full_name,
        email_address=payload.email_address,
        credential_secure_hash=hash_password(payload.password),
        role_type=payload.role_type,
        unit_code=payload.unit_code,
        assigned_base_station=payload.assigned_base_station,
        reporting_line_manager=payload.reporting_line_manager,
    )
    db.add(user)
    db.commit()
    db.refresh(user)
    return user


# NOTE: /staff/available MUST be declared before /{user_id} or FastAPI
# will match the literal string "staff" as a user_id path param.
@router.get("/staff/available")
def list_available_staff(
    unit: str | None = None,
    page: Page = Depends(),
    db: Session = Depends(get_db),
    _=Depends(get_current_user),
):
    q = db.query(User).filter(
        User.role_type == InstitutionalRole.STAFF, User.deactivated_at.is_(None)
    )
    if unit:
        q = q.filter(User.unit_code == unit)
    staff = page.rows(q, User.id)
    return [
        {
            "id": f.id,
            "full_name": f.full_name,
            "unit_code": f.unit_code,
            "current_occupancy_index": f.current_occupancy_index.value,
        }
        for f in staff
    ]


@router.get("/{user_id}", response_model=UserResponse)
def get_user(
    user_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    if current_user.id != user_id and current_user.role_type.value not in (
        "SUPER_ADMIN",
        "UNIT_ADMIN",
    ):
        raise HTTPException(status_code=403, detail="Access denied")
    user = db.query(User).filter(User.id == user_id).first()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    if current_user.id != user_id:
        ensure_unit_scope(current_user, user.unit_code)
    return user


@router.patch("/{user_id}", response_model=UserResponse)
def update_user(
    user_id: str,
    payload: UserUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_roles("SUPER_ADMIN", "UNIT_ADMIN")),
):
    user = db.query(User).filter(User.id == user_id).first()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    admin_roles = (InstitutionalRole.SUPER_ADMIN, InstitutionalRole.UNIT_ADMIN)
    if user.role_type in admin_roles and current_user.role_type != InstitutionalRole.SUPER_ADMIN:
        raise HTTPException(status_code=403, detail="Only a super-admin can modify admin accounts")
    ensure_unit_scope(current_user, user.unit_code)
    if payload.unit_code is not None:
        # A unit admin cannot move a user into or out of another unit.
        ensure_unit_scope(current_user, payload.unit_code)
    if payload.email_address is not None:
        taken = (
            db.query(User)
            .filter(User.email_address == payload.email_address, User.id != user.id)
            .first()
        )
        if taken:
            raise HTTPException(status_code=409, detail="Email already registered")
    if payload.reporting_line_manager is not None:
        _check_manager(user.id, payload.reporting_line_manager, db)
    for field, value in payload.model_dump(exclude_none=True).items():
        setattr(user, field, value)
    db.commit()
    db.refresh(user)
    return user


@router.post("/{user_id}/reset-password", response_model=PasswordResetResponse)
def reset_user_password(
    user_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_roles("SUPER_ADMIN", "UNIT_ADMIN")),
):
    """Issue a new random password for someone who cannot sign in.

    There is no self-service route back into a locked-out account:
    change-password needs the current password, and there is no mail
    sender to put a reset link through. Without this, an account whose
    password is lost is lost with it, and the CSV import creates accounts
    whose password is only ever shown once.

    The new password comes back in this response for the admin to hand
    over. It is never stored and never logged.
    """
    user = db.query(User).filter(User.id == user_id).first()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    admin_roles = (InstitutionalRole.SUPER_ADMIN, InstitutionalRole.UNIT_ADMIN)
    if user.role_type in admin_roles and current_user.role_type != InstitutionalRole.SUPER_ADMIN:
        raise HTTPException(status_code=403, detail="Only a super-admin can modify admin accounts")
    ensure_unit_scope(current_user, user.unit_code)

    raw_password = generate_password()
    user.credential_secure_hash = hash_password(raw_password)
    # The same consequences a self-service change has. A reset is how an
    # admin responds to a compromised account, so whoever is already in it
    # has to lose their sessions and their calendar feed URL with it.
    user.calendar_feed_token = generate_feed_token()
    db.query(RefreshToken).filter(RefreshToken.user_id == user.id).delete()
    # Inert for a member, since the first-login gate only covers admins,
    # but it makes a reset admin choose their own password before going on.
    user.initial_login_state = True
    db.commit()
    return PasswordResetResponse(user_id=user.id, initial_password=raw_password)


def _managed_account(user_id: str, db: Session, current_user: User) -> User:
    """The account an admin is about to change, once they are allowed to change it."""
    user = db.query(User).filter(User.id == user_id).first()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    admin_roles = (InstitutionalRole.SUPER_ADMIN, InstitutionalRole.UNIT_ADMIN)
    if user.role_type in admin_roles and current_user.role_type != InstitutionalRole.SUPER_ADMIN:
        raise HTTPException(status_code=403, detail="Only a super-admin can modify admin accounts")
    ensure_unit_scope(current_user, user.unit_code)
    return user


def _open_items(user_id: str, db: Session) -> OpenItems:
    """What still names an account, counted for whoever is handing it over.

    Deactivating changes none of it. Requests waiting on the account are
    decided by an admin from the pending list; the rest is reassigned
    through the usual routes.
    """
    today = org_today()
    pending = db.query(ReverseRsvpLog).filter(
        ReverseRsvpLog.authorized_by_user_id == user_id,
        ReverseRsvpLog.approval_state == LogVerificationState.PENDING_VERIFICATION,
    )
    reports = db.query(User).filter(
        User.reporting_line_manager == user_id, User.deactivated_at.is_(None)
    )
    # Drafts included: a cycle not yet published runs the slot once it is.
    slots = (
        db.query(StructuralMasterSlot)
        .join(Activity, StructuralMasterSlot.activity_id == Activity.id)
        .join(PlanningCycle, Activity.cycle_id == PlanningCycle.id)
        .filter(
            StructuralMasterSlot.primary_lead_id == user_id,
            PlanningCycle.date_bounds_end >= today,
        )
    )
    rows = db.query(DailyLedger).filter(
        DailyLedger.target_date >= today,
        or_(DailyLedger.active_lead_id == user_id, DailyLedger.substitute_lead_id == user_id),
    )
    return OpenItems(
        pending_absence_requests=pending.count(),
        direct_reports=reports.count(),
        slots_led=slots.count(),
        ledger_rows_ahead=rows.count(),
    )


@router.post("/{user_id}/deactivate", response_model=DeactivatedUserResponse)
def deactivate_user(
    user_id: str,
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_roles("SUPER_ADMIN", "UNIT_ADMIN")),
):
    """Stop an account without deleting it, for somebody who has left.

    Deleting a user took the attendance recorded against them, and the
    database now refuses to. This keeps every record and closes every way
    in: signing in, refreshing, an access token already issued, an API key
    bound to the account, the calendar feed and an open socket. The account
    also drops out of the lists staff are picked from.

    API keys are deleted, not held, and reactivating does not bring them
    back. The email address stays taken, because the account can come back;
    changing it on the deactivated account frees it. Calling it again
    changes nothing.

    Work still assigned to the account never blocks this. Refusing would
    keep the account open for as long as the handover takes, which is what
    deactivating is meant to end. The response counts what is left instead,
    and calling again counts afresh, so it doubles as the check that the
    handover is done.
    """
    user = _managed_account(user_id, db, current_user)
    # Refusing this is also what keeps one super admin standing: whoever
    # deactivates the others is still there.
    if user.id == current_user.id:
        raise HTTPException(status_code=422, detail="You cannot deactivate your own account")
    if user.deactivated_at is None:
        user.deactivated_at = datetime.now(UTC)
        user.calendar_feed_token = generate_feed_token()
        db.query(RefreshToken).filter(RefreshToken.user_id == user.id).delete()
        # Deleted rather than held. A key kept on an account nobody answers
        # for is a working credential nobody is accountable for, and whoever
        # takes the integration over is issued a key of their own.
        db.query(ApiKey).filter(ApiKey.user_id == user.id).delete()
        db.commit()
        db.refresh(user)
        background_tasks.add_task(socket_broker.close_session, user.id, CLOSE_UNAUTHENTICATED)
    return DeactivatedUserResponse(
        **UserResponse.model_validate(user).model_dump(),
        open_items=_open_items(user.id, db),
    )


@router.post("/{user_id}/reactivate", response_model=UserResponse)
def reactivate_user(
    user_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_roles("SUPER_ADMIN", "UNIT_ADMIN")),
):
    """Let a deactivated account back in, with its password as it was.

    Its API keys are not: deactivating deleted them, so an integration that
    signs in as the account is issued a new one. Nor is the calendar feed
    URL, which deactivating rotated, so the person fetches the new one. If
    the old password should not work again, a reset-password after this
    issues a new one. Calling it on an active account changes nothing.
    """
    user = _managed_account(user_id, db, current_user)
    if user.deactivated_at is not None:
        user.deactivated_at = None
        db.commit()
        db.refresh(user)
    return user


@router.put("/{user_id}/status")
def update_user_status(
    user_id: str,
    payload: UserStatusUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    if current_user.id != user_id and current_user.role_type.value not in ("SUPER_ADMIN",):
        raise HTTPException(status_code=403, detail="Can only update own status")
    user = db.query(User).filter(User.id == user_id).first()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    user.current_occupancy_index = payload.status
    db.commit()
    return {"status": payload.status.value}
