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


class GuestExtensionRequest(BaseModel):
    """How much longer a visit gets.

    The upper bound is GUEST_VISIT_EXTENSION_MAX_MINUTES and is checked in the
    route rather than here, because a schema is fixed at import and the setting
    is an operator's to change.
    """

    minutes: int = Field(ge=1)


class GuestResponse(BaseModel):
    id: int
    guest_name: str
    contact_phone: str
    originating_body: str
    target_staff_id: str
    visitation_intent: str
    handshake_status: LogVerificationState
    timestamp_marked: datetime
    # When an approved visit is over. Null is one nobody has approved, one
    # approved while GUEST_VISIT_LENGTH_MINUTES was 0, and every visit approved
    # before the column existed.
    visit_expires_at: datetime | None = None

    model_config = {"from_attributes": True}


class GuestVisitStatus(BaseModel):
    """Everything a visit code answers with.

    Whoever holds the code sees this, and a code on a kiosk screen can be
    read over a shoulder, so the visitor's name, their phone number and whom
    they came to see stay out of it.
    """

    handshake_status: LogVerificationState
    timestamp_marked: datetime
    # When to leave, which is the one thing the visitor most needs from this
    # and gives away nothing about them: whoever reads the code over a shoulder
    # learns a time, not a name. Null is an open-ended visit.
    visit_expires_at: datetime | None = None

    model_config = {"from_attributes": True}


class StaffAvailabilityResponse(BaseModel):
    staff_id: str
    full_name: str
    unit_code: str | None
    availability_label: str
