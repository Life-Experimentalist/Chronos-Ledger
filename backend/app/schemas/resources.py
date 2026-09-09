# Copyright 2026 Chronos Ledger Contributors
# Licensed under the Apache License, Version 2.0

import datetime

from pydantic import BaseModel, Field, model_validator

from app.models.db import ReservationStatus, ResourceType


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
    """One window in which a resource is taken, by a slot or by a booking.

    A slot interval carries the activity fields and a null reservation_id; a
    booking carries the reverse. Which kind it is can be read off whichever
    set is filled in.

    What a booking is for is not here on purpose. A room's calendar is
    readable by anyone signed in, and "this room is held from two until
    three" is a fact about the room, while what is happening in it need not
    be.
    """

    date: datetime.date
    start: datetime.time
    end: datetime.time
    activity_id: int | None
    activity_code: str | None
    master_slot_id: int | None
    reservation_id: int | None


class AvailabilityResponse(BaseModel):
    resource_id: int
    code: str
    range_start: datetime.date = Field(alias="from")
    to: datetime.date
    busy: list[BusyInterval]


class ReservationCreate(BaseModel):
    """A hold on a resource for one dated window.

    No recurrence and no end date: this books one window on one day. A weekly
    repeat is a structural master slot, which belongs to an activity in a
    planning cycle and is a different thing to ask for.
    """

    date: datetime.date
    start: datetime.time
    end: datetime.time
    purpose: str = Field(min_length=1, max_length=200)

    @model_validator(mode="after")
    def _ends_after_it_starts(self):
        # Equal times would book nothing and clash with nothing, and a window
        # that ends before it starts would clash with everything after it.
        # Crossing midnight is not supported here because it is not supported
        # on a slot either, so a booking that did would be invisible to the
        # timetable it has to be compared against.
        if self.end <= self.start:
            raise ValueError("end must be after start")
        return self


class ReservationResponse(BaseModel):
    id: int
    resource_id: int
    resource_code: str
    date: datetime.date
    start: datetime.time
    end: datetime.time
    purpose: str
    status: ReservationStatus
    requested_by_id: str | None
    idempotency_key: str
    created_at: datetime.datetime
    cancelled_at: datetime.datetime | None


class ReservationConflictDetail(BaseModel):
    """What the booking ran into, not merely that it did.

    A caller told only "no" has to ask availability again and diff the two
    answers to work out which hour to try next. The intervals it collided
    with are already in hand at the point of refusal, so they are returned.
    """

    message: str
    conflicts: list[BusyInterval]


class ReservationConflict(BaseModel):
    """The body of a 409.

    Nested under detail because that is where every other error in this API
    puts its body. An integrator that already reads detail should not need a
    second code path for this one response.
    """

    detail: ReservationConflictDetail
