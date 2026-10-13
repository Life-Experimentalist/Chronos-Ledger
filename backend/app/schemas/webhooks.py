# Copyright 2026 Chronos Ledger Contributors
# Licensed under the Apache License, Version 2.0

import datetime
from typing import Literal

from pydantic import BaseModel, Field, field_validator

EventType = Literal[
    "reservation.created",
    "reservation.updated",
    "resource.created",
    "resource.updated",
]


def _no_repeats(value: list[str] | None) -> list[str] | None:
    if value is None:
        return None
    return sorted(set(value))


class WebhookCreate(BaseModel):
    url: str = Field(min_length=1, max_length=2000)
    event_types: list[EventType] = Field(min_length=1)
    active: bool = True

    @field_validator("event_types")
    @classmethod
    def _sorted(cls, value: list[str] | None) -> list[str] | None:
        return _no_repeats(value)


class WebhookUpdate(BaseModel):
    """Only the fields sent are changed."""

    url: str | None = Field(default=None, min_length=1, max_length=2000)
    event_types: list[EventType] | None = Field(default=None, min_length=1)
    active: bool | None = None

    @field_validator("event_types")
    @classmethod
    def _sorted(cls, value: list[str] | None) -> list[str] | None:
        return _no_repeats(value)


class WebhookResponse(BaseModel):
    """A subscription, without its secrets.

    paused_at is set while it is paused, by repeated failures or by an import,
    and cleared by resume. previous_secret_expires_at is set while the secret
    before the last rotation still signs alongside the current one.
    """

    id: int
    url: str
    event_types: list[str]
    active: bool
    paused_at: datetime.datetime | None
    consecutive_failures: int
    previous_secret_expires_at: datetime.datetime | None
    created_at: datetime.datetime | None
    updated_at: datetime.datetime | None


class WebhookWithSecret(WebhookResponse):
    # The signing secret appears in this response and nowhere else. Keep it:
    # it cannot be read back, only replaced by rotating.
    secret: str


class WebhookAttemptResponse(BaseModel):
    at: datetime.datetime
    status_code: int | None
    response_ms: int
    error: str | None
    response_excerpt: str | None

    model_config = {"from_attributes": True}


class WebhookDeliveryResponse(BaseModel):
    id: int
    subscription_id: int
    event_id: str
    event_type: str
    entity_kind: str
    entity_id: int
    marker_id: int
    status: str
    attempt_count: int
    next_attempt_at: datetime.datetime | None
    created_at: datetime.datetime | None
    completed_at: datetime.datetime | None
    attempts: list[WebhookAttemptResponse]
