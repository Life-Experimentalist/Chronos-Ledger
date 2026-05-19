# Copyright 2026 Chronos Ledger Contributors
# Licensed under the Apache License, Version 2.0

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.security import verify_password, create_access_token, hash_password, get_current_user
from app.models.db import User
from app.schemas.auth import LoginRequest, TokenResponse, ChangePasswordRequest

router = APIRouter()


@router.post("/login", response_model=TokenResponse)
def login(payload: LoginRequest, db: Session = Depends(get_db)):
    user = db.query(User).filter(User.email_address == payload.email).first()
    if not user or not verify_password(payload.password, user.credential_secure_hash):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid credentials")

    token = create_access_token(subject=user.id, extra={"role": user.role_type.value})
    return TokenResponse(
        access_token=token,
        user_id=user.id,
        role=user.role_type.value,
        full_name=user.full_name,
        initial_login_state=user.initial_login_state,
    )


@router.post("/change-password")
def change_password(
    payload: ChangePasswordRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    if not verify_password(payload.current_password, current_user.credential_secure_hash):
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Current password is incorrect")

    current_user.credential_secure_hash = hash_password(payload.new_password)
    current_user.initial_login_state = False
    db.commit()
    return {"message": "Password updated successfully"}


@router.get("/me")
def get_me(current_user: User = Depends(get_current_user)):
    return {
        "id": current_user.id,
        "full_name": current_user.full_name,
        "email_address": current_user.email_address,
        "role_type": current_user.role_type.value,
        "department_code": current_user.department_code,
        "current_occupancy_index": current_user.current_occupancy_index.value,
        "initial_login_state": current_user.initial_login_state,
    }
