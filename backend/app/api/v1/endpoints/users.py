# Copyright 2026 Chronos Ledger Contributors
# Licensed under the Apache License, Version 2.0


from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.security import (
    ensure_unit_scope,
    generate_password,
    get_current_user,
    hash_password,
    require_roles,
)
from app.models.db import InstitutionalRole, RefreshToken, User, generate_feed_token
from app.schemas.users import (
    PasswordResetResponse,
    UserCreate,
    UserResponse,
    UserStatusUpdate,
    UserUpdate,
)

router = APIRouter()


@router.get("/", response_model=list[UserResponse])
def list_users(
    role: str | None = None,
    unit: str | None = None,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_roles("SUPER_ADMIN", "UNIT_ADMIN")),
):
    q = db.query(User)
    if role:
        q = q.filter(User.role_type == role)
    if unit:
        q = q.filter(User.unit_code == unit)
    # A unit admin only ever sees their own unit, whatever they ask for.
    if current_user.role_type == InstitutionalRole.UNIT_ADMIN:
        q = q.filter(User.unit_code == current_user.unit_code)
    return q.all()


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
    db: Session = Depends(get_db),
    _=Depends(get_current_user),
):
    q = db.query(User).filter(User.role_type == InstitutionalRole.STAFF)
    if unit:
        q = q.filter(User.unit_code == unit)
    staff = q.all()
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
