# Copyright 2026 Chronos Ledger Contributors
# Licensed under the Apache License, Version 2.0


from pydantic import BaseModel, EmailStr

from app.core.passwords import AcceptablePassword
from app.models.db import AccessReadiness, InstitutionalRole


class UserCreate(BaseModel):
    id: str
    full_name: str
    email_address: EmailStr
    password: AcceptablePassword
    role_type: InstitutionalRole
    unit_code: str | None = None
    assigned_base_station: str | None = None
    reporting_line_manager: str | None = None


class PasswordResetResponse(BaseModel):
    """Returned once, at reset. The raw password is never stored anywhere."""

    user_id: str
    initial_password: str


class UserUpdate(BaseModel):
    full_name: str | None = None
    email_address: EmailStr | None = None
    unit_code: str | None = None
    assigned_base_station: str | None = None
    reporting_line_manager: str | None = None


class UserStatusUpdate(BaseModel):
    status: AccessReadiness


class UserResponse(BaseModel):
    id: str
    full_name: str
    email_address: str
    role_type: InstitutionalRole
    unit_code: str | None
    assigned_base_station: str | None
    current_occupancy_index: AccessReadiness
    reporting_line_manager: str | None

    model_config = {"from_attributes": True}
