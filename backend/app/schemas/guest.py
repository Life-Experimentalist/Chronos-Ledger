# Copyright 2026 Chronos Ledger Contributors
# Licensed under the Apache License, Version 2.0

from datetime import datetime

from pydantic import BaseModel, Field

from app.models.db import LogVerificationState


class GuestCheckInRequest(BaseModel):
    # Bounds match the kiosk form's own validation, so a real visitor never
    # meets them, while a scripted caller cannot post a megabyte per field.
    guest_name: str = Field(min_length=2, max_length=100)
    contact_phone: str = Field(min_length=8, max_length=20, pattern=r"^[-0-9+() ]+$")
    originating_body: str = Field(min_length=2, max_length=100)
    target_staff_id: str = Field(min_length=1, max_length=50)
    visitation_intent: str = Field(min_length=10, max_length=500)


class GuestDecisionRequest(BaseModel):
    decision: LogVerificationState


class GuestResponse(BaseModel):
    id: int
    guest_name: str
    contact_phone: str
    originating_body: str
    target_staff_id: str
    visitation_intent: str
    handshake_status: LogVerificationState
    timestamp_marked: datetime

    model_config = {"from_attributes": True}


class StaffAvailabilityResponse(BaseModel):
    staff_id: str
    full_name: str
    unit_code: str | None
    availability_label: str
