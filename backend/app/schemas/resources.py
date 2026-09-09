# Copyright 2026 Chronos Ledger Contributors
# Licensed under the Apache License, Version 2.0

from datetime import date

from pydantic import BaseModel, Field, model_validator

from app.models.db import ResourceType


class ResourceResponse(BaseModel):
    id: int
    code: str
    label: str
    resource_type: ResourceType
    unit_code: str | None
    capacity: int | None
    user_id: str | None
    latitude: float | None
    longitude: float | None
    altitude_target: float | None
    active: bool

    model_config = {"from_attributes": True}


class ResourceUpdate(BaseModel):
    """What an admin may change about a resource that already exists.

    code is absent because it is a match key: the importer finds a room by
    its code, so renaming one through here would make the next upload create
    a second row rather than find this one. Rename the label instead, which
    is what gets shown.

    resource_type and user_id are absent for the same kind of reason. A room
    that becomes a person, or a person that becomes a room, is not an edit;
    it is a different resource, and the slots pointing at this one would
    follow it there.
    """

    label: str | None = Field(default=None, min_length=1, max_length=120)
    capacity: int | None = Field(default=None, ge=0)
    latitude: float | None = Field(default=None, ge=-90, le=90)
    longitude: float | None = Field(default=None, ge=-180, le=180)
    altitude_target: float | None = None
    active: bool | None = None

    @model_validator(mode="after")
    def _coordinates_move_together(self):
        # A latitude without a longitude is not half a location, it is no
        # location: the fence reads the pair or it does not engage at all.
        # Setting one and leaving the other behind is how a room ends up
        # fenced to a point on the equator.
        named = self.model_fields_set
        if ("latitude" in named) != ("longitude" in named):
            raise ValueError("latitude and longitude must be set or cleared together")
        if "latitude" in named and (self.latitude is None) != (self.longitude is None):
            raise ValueError("latitude and longitude must be set or cleared together")
        return self


class BusyInterval(BaseModel):
    date: str
    start: str
    end: str
    activity_id: int
    activity_code: str | None
    master_slot_id: int


class AvailabilityResponse(BaseModel):
    resource_id: int
    code: str
    range_start: date = Field(alias="from")
    to: date
    busy: list[BusyInterval]
