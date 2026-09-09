# Copyright 2026 Chronos Ledger Contributors
# Licensed under the Apache License, Version 2.0

from datetime import date, time

from pydantic import BaseModel, Field, model_validator

from app.models.db import DynamicState, ExecutionMode


class PlanningCycleCreate(BaseModel):
    cycle_label: str
    date_bounds_start: date
    date_bounds_end: date
    operational_status: bool = False


class PlanningCycleResponse(BaseModel):
    id: int
    cycle_label: str
    date_bounds_start: date
    date_bounds_end: date
    operational_status: bool

    model_config = {"from_attributes": True}


class MasterSlotCreate(BaseModel):
    day_of_week_index: int = Field(ge=1, le=7)
    time_window_start: time
    time_window_end: time
    activity_id: int
    primary_lead_id: str | None = None
    target_room_identifier: str

    @model_validator(mode="after")
    def _window_runs_forward(self):
        # Windows that cross midnight are not supported yet: the ledger,
        # attendance resolver and calendar feed all assume start < end
        # within one day. Reject at the edge instead of breaking there.
        if self.time_window_end <= self.time_window_start:
            raise ValueError(
                "time_window_end must be after time_window_start "
                "(windows crossing midnight are not supported yet)"
            )
        return self


class MasterSlotUpdate(BaseModel):
    """What an admin may change about a slot that already exists.

    activity_id is deliberately absent. Every day the slot has produced
    carries its own copy of the activity, so moving a slot to a different
    one would leave every past day recording a class that is no longer the
    class it belongs to. Pointing a slot at another activity is deleting
    this slot and creating one there, and it should have to say so.

    The window is validated in the endpoint rather than here: patching only
    the start time can invert a window whose end this payload never names,
    and only the merged values can tell.
    """

    day_of_week_index: int | None = Field(default=None, ge=1, le=7)
    time_window_start: time | None = None
    time_window_end: time | None = None
    primary_lead_id: str | None = None
    target_room_identifier: str | None = None


class DailyLedgerUpdate(BaseModel):
    operational_state: DynamicState | None = None
    substitute_lead_id: str | None = None
    delivery_format: ExecutionMode | None = None
    virtual_connection_string: str | None = None
    latitude_target: float | None = None
    longitude_target: float | None = None
    altitude_target: float | None = None
    precision_radius_meters: int | None = None


class DailyLedgerResponse(BaseModel):
    id: int
    target_date: date
    activity_id: int
    active_lead_id: str | None
    substitute_lead_id: str | None
    resource_id: int | None = None
    target_room_identifier: str | None
    delivery_format: ExecutionMode
    virtual_connection_string: str | None
    operational_state: DynamicState
    activity_code: str | None = None
    activity_title: str | None = None
    time_window_start: time | None = None
    time_window_end: time | None = None

    model_config = {"from_attributes": True}


class StaffLocationResponse(BaseModel):
    resolved_location: str
    status: str
    staff_id: str
    full_name: str
    occupancy_index: str
