# Copyright 2026 Chronos Ledger Contributors
# Licensed under the Apache License, Version 2.0

from datetime import date, datetime, time

from pydantic import BaseModel, Field, field_validator, model_validator

from app.models.db import DynamicState, ExecutionMode
from app.schemas.resources import BusyInterval


class PlanningCycleCreate(BaseModel):
    cycle_label: str
    date_bounds_start: date
    date_bounds_end: date
    operational_status: bool = False

    @model_validator(mode="after")
    def _ends_after_it_starts(self):
        # A day is generated only between the two dates, both included, so a
        # cycle that ends before it starts could never produce one. Equal
        # dates are a cycle of a single day.
        if self.date_bounds_end < self.date_bounds_start:
            raise ValueError("date_bounds_end must not be earlier than date_bounds_start")
        return self


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


class ActivityCreate(BaseModel):
    """An activity, the same one a CSV row names by code, title and unit.

    It has no slots and no members yet. Those are added with POST
    /schedule/slots and POST /schedule/activities/{id}/enrollments.
    """

    activity_code: str = Field(min_length=1, max_length=30)
    activity_title: str = Field(min_length=1, max_length=150)
    unit_code: str = Field(min_length=1, max_length=50)
    cycle_id: int


class ActivityUpdate(BaseModel):
    """What may change about an activity that already exists: its title.

    The code and the cycle are what identify it, the same pair a CSV upsert
    matches on, so changing either is a different activity. The unit is left
    out too: it is what a unit admin's permission is checked against, and
    moving an activity out of a unit is a decision for an import, which only
    an org admin can run.
    """

    activity_title: str = Field(min_length=1, max_length=150)


class ActivityResponse(BaseModel):
    id: int
    activity_code: str
    activity_title: str
    unit_code: str
    cycle_id: int
    retired_at: datetime | None = None

    model_config = {"from_attributes": True}


class RetireResult(BaseModel):
    """What retiring an activity or a slot did to the days ahead.

    Days from today onward that nobody has marked or annotated are removed.
    The ones that carry attendance or a note are kept, and counted here.
    Days before today are records and are not touched.
    """

    retired_at: datetime
    slots_retired: int
    ledger_rows_removed: int
    ledger_rows_kept: int


class EnrollmentCreate(BaseModel):
    member_id: str = Field(min_length=1, max_length=50)


class EnrollmentResponse(BaseModel):
    activity_id: int
    member_id: str

    model_config = {"from_attributes": True}


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

    @field_validator(
        "day_of_week_index", "time_window_start", "time_window_end", "target_room_identifier"
    )
    @classmethod
    def _cannot_be_cleared(cls, value):
        # Only the lead may be taken off a slot: it cannot run without a
        # weekday, both times and a room. A default is never validated, so a
        # field left out does not get here, only a null somebody sent.
        if value is None:
            raise ValueError("cannot be null")
        return value


class DailyLedgerUpdate(BaseModel):
    operational_state: DynamicState | None = None
    substitute_lead_id: str | None = None
    delivery_format: ExecutionMode | None = None
    virtual_connection_string: str | None = None
    latitude_target: float | None = None
    longitude_target: float | None = None
    altitude_target: float | None = None
    precision_radius_meters: int | None = None

    @field_validator("operational_state", "delivery_format")
    @classmethod
    def _cannot_be_cleared(cls, value):
        # Every read of a day returns both, so a day without one could not be
        # read back. A default is never validated, so a field left out does
        # not get here, only a null somebody sent.
        if value is None:
            raise ValueError("cannot be null")
        return value


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


class ConflictItem(BaseModel):
    """One of the rows taking part in a clash, with the window it holds.

    type is "slot" (a weekly slot on one date, id is the slot), "ledger_day"
    (a generated day, id is the ledger row) or "reservation" (a held booking,
    id is the reservation). A string rather than an enum so that a new kind
    of row can be added without breaking a client that does not know it.
    """

    type: str
    id: int
    date: date
    start: time
    end_date: date
    end: time
    activity_id: int | None
    resource_id: int | None


class Conflict(BaseModel):
    """Two rows that hold the same resource, or the same member, at once.

    kind is "resource_overlap", with resource_id set, or "member_overlap",
    with member_id set. date, start, end_date and end are the part of the two
    windows they share. items is a list rather than a pair so that a later
    kind can name more than two rows.
    """

    kind: str
    resource_id: int | None
    member_id: str | None
    date: date
    start: time
    end_date: date
    end: time
    items: list[ConflictItem]


class ConflictReport(BaseModel):
    range_start: date = Field(alias="from")
    to: date
    conflicts: list[Conflict]
