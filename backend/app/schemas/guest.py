# Copyright 2026 Chronos Ledger Contributors
# Licensed under the Apache License, Version 2.0

from pydantic import BaseModel
from typing import Optional
from datetime import datetime
from app.models.db import LogVerificationState


class GuestCheckInRequest(BaseModel):
    guest_name: str
    contact_phone: str
    originating_body: str
    target_faculty_id: str
    visitation_intent: str


class GuestDecisionRequest(BaseModel):
    decision: LogVerificationState


class GuestResponse(BaseModel):
    id: int
    guest_name: str
    contact_phone: str
    originating_body: str
    target_faculty_id: str
    visitation_intent: str
    handshake_status: LogVerificationState
    timestamp_marked: datetime

    model_config = {"from_attributes": True}


class FacultyAvailabilityResponse(BaseModel):
    faculty_id: str
    full_name: str
    department_code: Optional[str]
    availability_label: str
