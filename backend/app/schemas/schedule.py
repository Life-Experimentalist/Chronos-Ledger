# Copyright 2026 Chronos Ledger Contributors
# Licensed under the Apache License, Version 2.0

from datetime import date, time

from pydantic import BaseModel, Field, model_validator

from app.models.db import DynamicState, ExecutionMode
from app.schemas.resources import BusyInterval


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


class ActivationConflict(BusyInterval):
    """A busy interval, and which of the opening cycle's slots stands under it.

    The eight fields a conflict carries everywhere else name the other side
    of the clash: the booking, the slot or the generated day that was there
    first. On a single write that is enough, because the caller knows what
    it just tried to put down. Opening a cycle puts every slot in it down at
    once, so without this an admin is told a room is taken and not which of
    their slots wanted it.

    A subclass rather than a ninth field on BusyInterval, which is what the
    availability endpoint returns and what an integrator already reads. The
    eight are unchanged here, so a reader that parses those keeps working
    and can ignore this one.
    """

    blocked_slot_id: int


class CycleActivationConflictDetail(BaseModel):
    message: str
    conflicts: list[ActivationConflict]


class CycleActivationConflict(BaseModel):
    """The body of the 409 that refuses to open a cycle.

    Nested under detail for the reason ReservationConflict gives: that is
    where every other error in this API puts its body.
    """

    detail: CycleActivationConflictDetail


class MasterSlotCreate(BaseModel):
    day_of_week_index: int = Field(ge=1, le=7)
    time_window_start: time
    time_window_end: time
    activity_id: int
    primary_lead_id: str | None = None
    target_room_identifier: str

    @model_validator(mode="after")
    def _is_a_window_at_all(self):
        # An end earlier than the start means the window runs past midnight
        # and finishes on the day after the one it opened on, which is what a
        # night shift is. Equal times are refused: 09:00 to 09:00 is either
        # nothing at all or a whole day and the row does not say which.
        if self.time_window_end == self.time_window_start:
            raise ValueError(
                "time_window_end must not equal time_window_start "
                "(an end earlier than the start means the window crosses midnight)"
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
    the start time can land it on an end this payload never names, and only
    the merged values can tell.
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
