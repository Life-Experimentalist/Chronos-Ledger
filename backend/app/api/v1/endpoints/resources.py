# Copyright 2026 Chronos Ledger Contributors
# Licensed under the Apache License, Version 2.0

import datetime

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session, joinedload

from app.core.database import get_db
from app.core.security import get_current_user, require_roles
from app.models.db import (
    Activity,
    PlanningCycle,
    Resource,
    ResourceType,
    StructuralMasterSlot,
)
from app.schemas.resources import AvailabilityResponse, ResourceResponse, ResourceUpdate
from app.services.availability import MAX_RANGE_DAYS, occupied

router = APIRouter()

RANGE_BACKWARDS = "from must not be after to"
RANGE_TOO_LONG = f"the range must not exceed {MAX_RANGE_DAYS} days"


@router.get("/", response_model=list[ResourceResponse])
def list_resources(
    resource_type: ResourceType | None = None,
    active: bool | None = None,
    code: str | None = None,
    db: Session = Depends(get_db),
    _=Depends(get_current_user),
):
    """Every room, person and piece of equipment the schedule can point at.

    Readable by anyone signed in. A resource is a place and a capacity, not
    a secret, and an external system that has to book one needs to be able
    to find it first.
    """
    query = db.query(Resource)
    if resource_type is not None:
        query = query.filter(Resource.resource_type == resource_type)
    if active is not None:
        query = query.filter(Resource.active == active)
    if code is not None:
        query = query.filter(Resource.code == code.strip())
    return query.order_by(Resource.code).all()


@router.get("/{resource_id}/availability", response_model=AvailabilityResponse)
def resource_availability(
    resource_id: int,
    from_: datetime.date = Query(alias="from"),
    to: datetime.date = Query(),
    db: Session = Depends(get_db),
    _=Depends(get_current_user),
):
    """When this resource is already taken, between two dates inclusive.

    A slot counts when its cycle is open. Cycle date bounds are not
    consulted, because the nightly ledger generation does not consult them
    either: it books a day whenever the cycle flag is on. Answering anything
    else here would tell a caller a room was free on a date the ledger is
    going to fill, which is the direction that ends in two bookings.

    An inactive resource still answers. What is on its calendar is a fact
    about the past and about slots nobody has moved yet, and hiding it would
    make retiring a room look like clearing it.
    """
    resource = db.query(Resource).filter(Resource.id == resource_id).first()
    if not resource:
        raise HTTPException(status_code=404, detail="Resource not found")
    if from_ > to:
        raise HTTPException(status_code=422, detail=RANGE_BACKWARDS)
    if (to - from_).days + 1 > MAX_RANGE_DAYS:
        raise HTTPException(status_code=422, detail=RANGE_TOO_LONG)

    slots = (
        db.query(StructuralMasterSlot)
        .join(Activity, StructuralMasterSlot.activity_id == Activity.id)
        .join(PlanningCycle, Activity.cycle_id == PlanningCycle.id)
        .filter(
            StructuralMasterSlot.resource_id == resource_id,
            PlanningCycle.operational_status,
        )
        .options(joinedload(StructuralMasterSlot.activity))
        .all()
    )
    return {
        "resource_id": resource.id,
        "code": resource.code,
        "from": from_,
        "to": to,
        "busy": occupied(slots, from_, to),
    }


@router.patch("/{resource_id}", response_model=ResourceResponse)
def update_resource(
    resource_id: int,
    payload: ResourceUpdate,
    db: Session = Depends(get_db),
    _=Depends(require_roles("SUPER_ADMIN")),
):
    """Fill in what a CSV could not know.

    Rooms arrive from an import knowing only their name. Their capacity and
    where they physically are is something a person knows, and until this
    existed there was no way to tell the system: geofencing was a feature
    with no route that could switch it on.
    """
    resource = db.query(Resource).filter(Resource.id == resource_id).first()
    if not resource:
        raise HTTPException(status_code=404, detail="Resource not found")

    # exclude_unset, not exclude_none: clearing a coordinate is a thing an
    # admin does on purpose, and it has to be distinguishable from not
    # mentioning it.
    for field, value in payload.model_dump(exclude_unset=True).items():
        setattr(resource, field, value)
    db.commit()
    db.refresh(resource)
    return resource
