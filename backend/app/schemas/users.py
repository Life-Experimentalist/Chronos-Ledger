# Copyright 2026 Chronos Ledger Contributors
# Licensed under the Apache License, Version 2.0

from pydantic import BaseModel, EmailStr
from typing import Optional
from app.models.db import InstitutionalRole, AccessReadiness


class UserCreate(BaseModel):
    id: str
    full_name: str
    email_address: EmailStr
    password: str
    role_type: InstitutionalRole
    department_code: Optional[str] = None
    assigned_base_station: Optional[str] = "Staff Room Main"
    reporting_line_manager: Optional[str] = None


class UserUpdate(BaseModel):
    full_name: Optional[str] = None
    email_address: Optional[EmailStr] = None
    department_code: Optional[str] = None
    assigned_base_station: Optional[str] = None
    reporting_line_manager: Optional[str] = None


class UserStatusUpdate(BaseModel):
    status: AccessReadiness


class UserResponse(BaseModel):
    id: str
    full_name: str
    email_address: str
    role_type: InstitutionalRole
    department_code: Optional[str]
    assigned_base_station: Optional[str]
    current_occupancy_index: AccessReadiness
    reporting_line_manager: Optional[str]

    model_config = {"from_attributes": True}
