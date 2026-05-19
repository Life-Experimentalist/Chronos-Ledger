# Copyright 2026 Chronos Ledger Contributors
# Licensed under the Apache License, Version 2.0

from pydantic import BaseModel
from typing import Optional
from datetime import date, time
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
    primary_instructor_id: Optional[str] = None
    target_room_identifier: str


class DailyLedgerUpdate(BaseModel):
    operational_state: Optional[DynamicState] = None
    substitute_instructor_id: Optional[str] = None
    delivery_format: Optional[ExecutionMode] = None
    virtual_connection_string: Optional[str] = None
    latitude_target: Optional[float] = None
    longitude_target: Optional[float] = None
    altitude_target: Optional[float] = None
    precision_radius_meters: Optional[int] = None


class DailyLedgerResponse(BaseModel):
    id: int
    target_date: date
    course_offering_id: int
    active_instructor_id: Optional[str]
    substitute_instructor_id: Optional[str]
    target_room_identifier: str
    delivery_format: ExecutionMode
    virtual_connection_string: Optional[str]
    operational_state: DynamicState
    course_code: Optional[str] = None
    course_title: Optional[str] = None
    time_window_start: Optional[time] = None
    time_window_end: Optional[time] = None

    model_config = {"from_attributes": True}


class FacultyLocationResponse(BaseModel):
    resolved_location: str
    status: str
    faculty_id: str
    full_name: str
    occupancy_index: str
