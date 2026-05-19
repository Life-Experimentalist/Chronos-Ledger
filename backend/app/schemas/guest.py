# Copyright 2026 Chronos Ledger Contributors
# Licensed under the Apache License, Version 2.0

from datetime import datetime

from pydantic import BaseModel

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
    department_code: str | None
    availability_label: str
