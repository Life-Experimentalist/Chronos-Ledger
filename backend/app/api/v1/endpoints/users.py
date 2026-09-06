# Copyright 2026 Chronos Ledger Contributors
# Licensed under the Apache License, Version 2.0


from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.security import get_current_user, hash_password, require_roles
from app.models.db import InstitutionalRole, User
from app.schemas.users import UserCreate, UserResponse, UserStatusUpdate, UserUpdate

router = APIRouter()


@router.get("/", response_model=list[UserResponse])
def list_users(
    role: str | None = None,
    department: str | None = None,
    db: Session = Depends(get_db),
    _=Depends(require_roles("SUPER_ADMIN", "DEPT_ADMIN")),
):
    q = db.query(User)
    if role:
        q = q.filter(User.role_type == role)
    if department:
        q = q.filter(User.department_code == department)
    return q.all()


@router.post("/", response_model=UserResponse, status_code=status.HTTP_201_CREATED)
def create_user(
    payload: UserCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_roles("SUPER_ADMIN", "DEPT_ADMIN")),
):
    admin_roles = (InstitutionalRole.SUPER_ADMIN, InstitutionalRole.DEPT_ADMIN)
    if payload.role_type in admin_roles and current_user.role_type != InstitutionalRole.SUPER_ADMIN:
        raise HTTPException(status_code=403, detail="Only a super-admin can create admin accounts")
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
        department_code=payload.department_code,
        assigned_base_station=payload.assigned_base_station,
        reporting_line_manager=payload.reporting_line_manager,
    )
    db.add(user)
    db.commit()
    db.refresh(user)
    return user


# NOTE: /faculty/available MUST be declared before /{user_id} or FastAPI
# will match the literal string "faculty" as a user_id path param.
@router.get("/faculty/available")
def list_available_faculty(
    department: str | None = None,
    db: Session = Depends(get_db),
    _=Depends(get_current_user),
):
    q = db.query(User).filter(User.role_type == InstitutionalRole.FACULTY)
    if department:
        q = q.filter(User.department_code == department)
    faculty = q.all()
    return [
        {
            "id": f.id,
            "full_name": f.full_name,
            "department_code": f.department_code,
            "current_occupancy_index": f.current_occupancy_index.value,
        }
        for f in faculty
    ]


@router.get("/{user_id}", response_model=UserResponse)
def get_user(
    user_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    if current_user.id != user_id and current_user.role_type.value not in (
        "SUPER_ADMIN",
        "DEPT_ADMIN",
    ):
        raise HTTPException(status_code=403, detail="Access denied")
    user = db.query(User).filter(User.id == user_id).first()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    return user


@router.patch("/{user_id}", response_model=UserResponse)
def update_user(
    user_id: str,
    payload: UserUpdate,
    db: Session = Depends(get_db),
    _=Depends(require_roles("SUPER_ADMIN", "DEPT_ADMIN")),
):
    user = db.query(User).filter(User.id == user_id).first()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    for field, value in payload.model_dump(exclude_none=True).items():
        setattr(user, field, value)
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
