# Copyright 2026 Chronos Ledger Contributors
# Licensed under the Apache License, Version 2.0

import datetime

from pydantic import BaseModel, Field, model_validator

from app.models.db import (
    RequirementEnforcement,
    RequirementOwner,
    ReservationStatus,
    ResourceMode,
)
from app.schemas.resource_classes import ClassCode


class ResourceResponse(BaseModel):
    id: int
    code: str
    label: str
    resource_type: str
    unit_code: str | None
    capacity: int | None
    mode: ResourceMode
    user_id: str | None
    latitude: float | None
    longitude: float | None
    altitude_target: float | None
    active: bool

    model_config = {"from_attributes": True}


POOL_NEEDS_CAPACITY = "a POOLED resource needs a capacity of at least 1"


class ResourceCreate(BaseModel):
    """A resource registered before any timetable names it.

    Every string is stripped first, code included, the same as the importer
    strips a room name, so this row and a later CSV mentioning the room are
    one room. label defaults to the code, which is what an imported room
    gets.

    mode defaults to EXCLUSIVE, which is what every resource was before
    modes existed. A POOLED resource needs a capacity of at least one,
    because that is the size of the pool.
    """

    model_config = {"str_strip_whitespace": True}

    code: str = Field(min_length=1, max_length=30)
    label: str | None = Field(default=None, min_length=1, max_length=120)
    # The code of an active class of the organization. ROOM is what a
    # resource was before classes were configured.
    resource_type: ClassCode = "ROOM"
    unit_code: str | None = Field(default=None, max_length=50)
    capacity: int | None = Field(default=None, ge=0)
    mode: ResourceMode = ResourceMode.EXCLUSIVE
    latitude: float | None = Field(default=None, ge=-90, le=90)
    longitude: float | None = Field(default=None, ge=-180, le=180)
    altitude_target: float | None = None

    @model_validator(mode="after")
    def _coordinates_come_together(self):
        # The same rule as on update: half a location fences the room to a
        # point on the equator.
        if (self.latitude is None) != (self.longitude is None):
            raise ValueError("latitude and longitude must be set together")
        if self.mode is ResourceMode.POOLED and not self.capacity:
            raise ValueError(POOL_NEEDS_CAPACITY)
        return self


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

    mode and capacity can change, but not under bookings still to come that
    would no longer fit: the route refuses that with a 409 naming them.
    Whether a pooled resource ends up with a capacity is checked by the
    route too, because it depends on what the row already has.
    """

    label: str | None = Field(default=None, min_length=1, max_length=120)
    capacity: int | None = Field(default=None, ge=0)
    # Leaving it out keeps the mode; null is not a mode.
    mode: ResourceMode | None = None
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
        if "mode" in named and self.mode is None:
            raise ValueError("mode cannot be cleared, only changed")
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

    end_date is always set, and is the same as date for an interval that
    finishes on the day it started. It is spelled out rather than left to be
    inferred because inferring it wrong is silent: a reader that takes date
    with end and ignores end_date computes minus sixteen hours for a night
    shift running 22:00 to 06:00, and gets a plausible answer for every
    interval written before overnight windows existed.
    """

    date: datetime.date
    start: datetime.time
    end_date: datetime.date
    end: datetime.time
    activity_id: int | None
    activity_code: str | None
    master_slot_id: int | None
    reservation_id: int | None


class UnmetRequirement(BaseModel):
    """A requirement that could not be held, and why.

    On a booking it is an ADVISORY gap: the booking went ahead without it.
    On GET availability with with_requirements it is whatever would stop the
    window being held with everything it needs, whatever the enforcement.
    enforcement is the resolved value, the organization's default filled in
    where the requirement did not say.

    quantity is how many units or resources were missing, not how many were
    asked for. conflicts is what stands in the way on a named target; it is
    empty when a kind had no free resource to name.
    """

    requirement_id: int
    owner_kind: RequirementOwner
    owner_id: int
    target_resource_id: int | None
    target_kind: str | None
    quantity: int
    enforcement: RequirementEnforcement
    message: str
    conflicts: list[BusyInterval]


class AvailabilityResponse(BaseModel):
    """The busy intervals of a resource, and with with_requirements, whether it can be held.

    requirements_met and unmet are null and empty unless with_requirements
    was asked for. Nothing is held either way.
    """

    resource_id: int
    code: str
    range_start: datetime.date = Field(alias="from")
    to: datetime.date
    busy: list[BusyInterval]
    requirements_met: bool | None = None
    unmet: list[UnmetRequirement] = []


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
    # How many units of a pooled resource to hold. Anything above 1 is
    # refused on a resource that is not pooled, where there is one of it.
    quantity: int = Field(default=1, ge=1)
    # The caller's own identifier for the booking, kept exactly as sent.
    # Unique per caller, so it finds this booking again through
    # GET /resources/reservations?external_ref=.
    external_ref: str | None = Field(default=None, min_length=1, max_length=120)
    # Which resources to hold for the requirements that name a kind of
    # resource rather than a resource: a class code mapped to the ids to
    # use, in order. Where it says nothing, or runs out, the engine picks the
    # first free resources of the kind by code.
    assignments: dict[str, list[int]] | None = None

    @model_validator(mode="after")
    def _is_a_window_at_all(self):
        # An end earlier than the start means the window runs past midnight
        # and finishes on the next date: 22:00 to 06:00 is a night shift.
        # The date field is the day it opens on.
        #
        # Equal times are refused and always will be. 09:00 to 09:00 is
        # either nothing at all or a full twenty four hours, there is no way
        # to tell which was meant, and both readings are trouble: one books
        # a window that clashes with nothing, the other one that clashes with
        # everything.
        #
        # A weekly slot reads its two times by the same rule, so a booking
        # that runs past midnight is checked against the whole timetable and
        # not only against the part of it that stays inside one day.
        if self.end == self.start:
            raise ValueError("end must not equal start")
        return self


class ReservationResponse(BaseModel):
    id: int
    resource_id: int
    resource_code: str
    date: datetime.date
    start: datetime.time
    end: datetime.time
    purpose: str
    quantity: int
    status: ReservationStatus
    requested_by_id: str | None
    idempotency_key: str
    external_ref: str | None
    created_at: datetime.datetime
    cancelled_at: datetime.datetime | None
    # The booking this hold was taken for, when a requirement made it.
    parent_reservation_id: int | None = None


class ReservationCreated(ReservationResponse):
    """A new booking with what was held alongside it.

    children are the holds its requirements took, at every depth, in the
    order they were taken. unmet are the ADVISORY requirements that could not
    be met; the booking went ahead without them. A REQUIRED one that cannot
    be met refuses the booking instead. A replay of the same request answers
    with the children as they stand and an empty unmet, because a gap is not
    stored.
    """

    children: list[ReservationResponse] = []
    unmet: list[UnmetRequirement] = []


class ReservationUpdate(BaseModel):
    """What the caller may change about a reservation it already holds.

    Only its reference, for now. The window is what the conflict check, the
    exclusion constraint and the idempotency fingerprint are all built on,
    and moving it is a cancel and a new booking. Null clears the reference;
    leaving the field out leaves it alone. Any other field is refused rather
    than ignored, so a caller trying to move a booking is told it did not.
    """

    model_config = {"extra": "forbid"}

    external_ref: str | None = Field(default=None, min_length=1, max_length=120)


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


class CapacityExceededDetail(BaseModel):
    """A pooled resource without enough units left for the window.

    conflicts are the bookings already holding units of the pool somewhere
    in the window. taken is the most of the pool they hold at any one moment
    of it, so capacity minus taken is the most this window could still have.
    """

    message: str
    conflicts: list[BusyInterval]
    capacity: int
    taken: int
    requested: int


class CapacityExceeded(BaseModel):
    """The body of a 409 with RESOURCE_CAPACITY_EXCEEDED."""

    detail: CapacityExceededDetail


class BookingsWouldNotFitDetail(BaseModel):
    """The bookings still to come that a change of mode or capacity would break."""

    message: str
    reservations: list[ReservationResponse]


class BookingsWouldNotFit(BaseModel):
    """The body of a 409 with RESOURCE_BOOKINGS_WOULD_NOT_FIT."""

    detail: BookingsWouldNotFitDetail


class ReservationRefTakenDetail(BaseModel):
    """Which reservation already carries the reference.

    The id is what the caller needs next: the booking it made earlier under
    the same reference, which it can now read, change or cancel.
    """

    message: str
    reservation_id: int


class ReservationRefTaken(BaseModel):
    """The body of a 409 with RESERVATION_EXTERNAL_REF_TAKEN."""

    detail: ReservationRefTakenDetail


class RequirementCreate(BaseModel):
    """One rule: whoever uses the owner also needs the target.

    Exactly one of target_resource_id and target_kind. quantity above 1 on a
    named target needs it to be POOLED (units of the pool); on a kind it is
    that many distinct resources. enforcement left out follows the
    organization's default.
    """

    target_resource_id: int | None = Field(default=None, ge=1)
    target_kind: ClassCode | None = None
    quantity: int = Field(default=1, ge=1, le=1000)
    before_minutes: int = Field(default=0, ge=0, le=1440)
    after_minutes: int = Field(default=0, ge=0, le=1440)
    enforcement: RequirementEnforcement | None = None

    @model_validator(mode="after")
    def _one_target(self):
        if (self.target_resource_id is None) == (self.target_kind is None):
            raise ValueError("set exactly one of target_resource_id and target_kind")
        return self


class RequirementResponse(BaseModel):
    id: int
    owner_kind: RequirementOwner
    owner_id: int
    target_resource_id: int | None
    target_kind: str | None
    quantity: int
    before_minutes: int
    after_minutes: int
    enforcement: RequirementEnforcement | None
    created_at: datetime.datetime

    model_config = {"from_attributes": True}
