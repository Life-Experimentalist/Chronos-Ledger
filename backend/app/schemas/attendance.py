# Copyright 2026 Chronos Ledger Contributors
# Licensed under the Apache License, Version 2.0

from datetime import date, datetime

from pydantic import BaseModel, Field

from app.models.db import LogVerificationState, VerificationMetric


class AttendanceMarkRequest(BaseModel):
    ledger_instance_id: int
    member_id: str
    marking_status: VerificationMetric
    user_lat: float | None = None
    user_lon: float | None = None
    user_alt: float | None = None
    # The device's own estimate of how far off the fix may be, in meters:
    # coords.accuracy from the browser's Geolocation API.
    user_accuracy: float | None = Field(default=None, ge=0, allow_inf_nan=False)


class AttendanceBatchRequest(BaseModel):
    ledger_instance_id: int
    records: list[AttendanceMarkRequest]


class AttendanceResponse(BaseModel):
    id: int
    ledger_instance_id: int
    member_id: str
    marking_status: VerificationMetric
    authorizing_agent_id: str | None
    modification_timestamp: datetime

    model_config = {"from_attributes": True}


class ReverseRsvpCreate(BaseModel):
    target_absence_date: date
    context_justification: str


class ReverseRsvpResponse(BaseModel):
    id: int
    submitting_user_id: str
    target_absence_date: date
    context_justification: str
    approval_state: LogVerificationState
    authorized_by_user_id: str | None

    model_config = {"from_attributes": True}


class RsvpDecision(BaseModel):
    decision: LogVerificationState


class AnnotationCreate(BaseModel):
    ledger_instance_id: int
    # Both were unbounded. The tag lands in a String(30), so a longer one was
    # an error from the database on Postgres and a silent truncation on
    # SQLite. The 4000 on the body is a policy figure rather than a column
    # limit, since that column is Text; it is there so a note cannot be used
    # to fill the disk.
    #
    # The tag is deliberately not an enumeration. Nothing in this repository
    # defines a vocabulary for it and nothing in the interface writes one, so
    # a guessed set would refuse whatever an operator actually types.
    classification_tag: str = Field(min_length=1, max_length=30)
    annotation_payload: str = Field(min_length=1, max_length=4000)


class AnnotationResponse(BaseModel):
    id: int
    ledger_instance_id: int
    creator_id: str
    classification_tag: str
    annotation_payload: str
    distribution_timestamp: datetime

    model_config = {"from_attributes": True}
