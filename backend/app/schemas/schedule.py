# Copyright 2026 Chronos Ledger Contributors
# Licensed under the Apache License, Version 2.0

from datetime import date, time

from pydantic import BaseModel

from app.models.db import DynamicState, ExecutionMode


class AcademicCycleCreate(BaseModel):
    cycle_label: str
    date_bounds_start: date
    date_bounds_end: date
    operational_status: bool = False


class AcademicCycleResponse(BaseModel):
    id: int
    cycle_label: str
    date_bounds_start: date
    date_bounds_end: date
    operational_status: bool

    model_config = {"from_attributes": True}


class MasterSlotCreate(BaseModel):
    day_of_week_index: int
    time_window_start: time
    time_window_end: time
    course_offering_id: int
    primary_instructor_id: str | None = None
    target_room_identifier: str


class DailyLedgerUpdate(BaseModel):
    operational_state: DynamicState | None = None
    substitute_instructor_id: str | None = None
    delivery_format: ExecutionMode | None = None
    virtual_connection_string: str | None = None
    latitude_target: float | None = None
    longitude_target: float | None = None
    altitude_target: float | None = None
    precision_radius_meters: int | None = None


class DailyLedgerResponse(BaseModel):
    id: int
    target_date: date
    course_offering_id: int
    active_instructor_id: str | None
    substitute_instructor_id: str | None
    target_room_identifier: str
    delivery_format: ExecutionMode
    virtual_connection_string: str | None
    operational_state: DynamicState
    course_code: str | None = None
    course_title: str | None = None
    time_window_start: time | None = None
    time_window_end: time | None = None

    model_config = {"from_attributes": True}


class FacultyLocationResponse(BaseModel):
    resolved_location: str
    status: str
    faculty_id: str
    full_name: str
    occupancy_index: str
