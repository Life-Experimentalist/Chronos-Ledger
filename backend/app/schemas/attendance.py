# Copyright 2026 Chronos Ledger Contributors
# Licensed under the Apache License, Version 2.0

from datetime import date, datetime

from pydantic import BaseModel

from app.models.db import LogVerificationState, VerificationMetric


class AttendanceMarkRequest(BaseModel):
    ledger_instance_id: int
    student_id: str
    marking_status: VerificationMetric
    user_lat: float | None = None
    user_lon: float | None = None
    user_alt: float | None = None


class AttendanceBatchRequest(BaseModel):
    ledger_instance_id: int
    records: list[AttendanceMarkRequest]


class AttendanceResponse(BaseModel):
    id: int
    ledger_instance_id: int
    student_id: str
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
    classification_tag: str
    annotation_payload: str


class AnnotationResponse(BaseModel):
    id: int
    ledger_instance_id: int
    creator_id: str
    classification_tag: str
    annotation_payload: str
    distribution_timestamp: datetime

    model_config = {"from_attributes": True}
