# Copyright 2026 Chronos Ledger Contributors
# Licensed under the Apache License, Version 2.0

import datetime
import hashlib

from fastapi import APIRouter, Depends, Header, HTTPException, Query, Response, status
from fastapi.encoders import jsonable_encoder
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.security import get_current_user, require_roles
from app.models.db import Reservation, ReservationStatus, Resource, ResourceType
from app.schemas.resources import (
    AvailabilityResponse,
    ReservationConflict,
    ReservationCreate,
    ReservationResponse,
    ResourceResponse,
    ResourceUpdate,
)
from app.services.availability import (
    MAX_RANGE_DAYS,
    booked_slots,
    clashing,
    held_reservations,
    occupied,
)

router = APIRouter()

RANGE_BACKWARDS = "from must not be after to"
RANGE_TOO_LONG = f"the range must not exceed {MAX_RANGE_DAYS} days"
ALREADY_TAKEN = "the resource is already taken for part of that window"
KEY_REUSED = "that Idempotency-Key was used for a different request"
NOT_YOUR_HOLD = "only the caller that took a hold may cancel it"
# The name migration 010 gave the exclusion constraint. Postgres puts it in
# the error text, which is how an overlap is told apart from the unique key
# on the idempotency key: both arrive here as one IntegrityError.
OVERLAP_CONSTRAINT = "ex_reservations_no_overlap"


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

    Both the timetable and the bookings, in one answer. Anything less would
    let a caller read a room as free and then be refused when it tried to
    take the hour, or take an hour the timetable had already claimed.

    A slot counts when its cycle is open. Cycle date bounds are not
    consulted, because the nightly ledger generation does not consult them
    either: it books a day whenever the cycle flag is on. Answering anything
    else here would tell a caller a room was free on a date the ledger is
    going to fill, which is the direction that ends in two bookings.

    An inactive resource still answers. What is on its calendar is a fact
    about the past and about slots nobody has moved yet, and hiding it would
    make retiring a room look like clearing it.

    A busy interval's date can be the day before `from`. A booking that runs
    past midnight is dated the day it opened on and occupies the morning
    after, so a caller asking about Tuesday is told about a hold dated Monday
    that ends at six. Read each interval by its own date and end_date and not
    by the range that returned it; a client that groups by date alone will
    file that hold under a day it did not ask about, and one that discards
    anything outside the range will show a ward as free while it is staffed.
    """
    resource = db.query(Resource).filter(Resource.id == resource_id).first()
    if not resource:
        raise HTTPException(status_code=404, detail="Resource not found")
    if from_ > to:
        raise HTTPException(status_code=422, detail=RANGE_BACKWARDS)
    if (to - from_).days + 1 > MAX_RANGE_DAYS:
        raise HTTPException(status_code=422, detail=RANGE_TOO_LONG)

    return {
        "resource_id": resource.id,
        "code": resource.code,
        "from": from_,
        "to": to,
        "busy": occupied(
            booked_slots(db, resource_id),
            held_reservations(db, resource_id, from_, to),
            from_,
            to,
        ),
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


def _fingerprint(resource_id: int, payload: ReservationCreate) -> str:
    """What was asked for, boiled down to a string a replay can be checked against.

    The resource is in it because it is in the path and not in the body: the
    same key sent to two different rooms is two different requests, and
    without this it would look like one.
    """
    asked = "|".join(
        (
            str(resource_id),
            payload.date.isoformat(),
            payload.start.isoformat(),
            payload.end.isoformat(),
            payload.purpose.strip(),
        )
    )
    return hashlib.sha256(asked.encode("utf-8")).hexdigest()


def _conflicts_for(db: Session, resource_id: int, payload: ReservationCreate) -> list[dict]:
    """What already holds any part of the asked-for window.

    Exactly the two queries GET availability runs, through the same expansion.
    A booking accepted for an hour availability calls busy is the double
    booking this endpoint exists to prevent, so the two cannot be allowed to
    answer differently.

    Asked twice: once before inserting, and again if the database refuses the
    insert, because by then somebody else's row is in the table and is the
    thing to name.

    A window that runs past midnight is asked about over two days, not one.
    Expanding only the date it opened on would leave out everything sitting
    on the far side of midnight, and a booking from 22:00 to 06:00 would be
    accepted straight through the top of somebody else's morning.
    """
    last = payload.date
    if payload.end < payload.start:
        last += datetime.timedelta(days=1)
    return clashing(
        occupied(
            booked_slots(db, resource_id),
            held_reservations(db, resource_id, payload.date, last),
            payload.date,
            last,
        ),
        payload.date,
        payload.start,
        payload.end,
    )


def _already_taken(conflicts: list[dict]) -> HTTPException:
    # jsonable_encoder because the detail of an HTTPException is serialised
    # straight to JSON, with none of the conversion a response_model would
    # have done for the dates and times in here.
    return HTTPException(
        status_code=status.HTTP_409_CONFLICT,
        detail=jsonable_encoder({"message": ALREADY_TAKEN, "conflicts": conflicts}),
    )


def _view(reservation: Reservation, resource: Resource) -> dict:
    return {
        "id": reservation.id,
        "resource_id": resource.id,
        "resource_code": resource.code,
        "date": reservation.reserved_date,
        "start": reservation.time_window_start,
        "end": reservation.time_window_end,
        "purpose": reservation.purpose,
        "status": reservation.status,
        "requested_by_id": reservation.requested_by_id,
        "idempotency_key": reservation.idempotency_key,
        "created_at": reservation.created_at,
        "cancelled_at": reservation.cancelled_at,
    }


@router.post(
    "/{resource_id}/reservations",
    response_model=ReservationResponse,
    status_code=status.HTTP_201_CREATED,
    responses={409: {"model": ReservationConflict}},
)
def create_reservation(
    resource_id: int,
    payload: ReservationCreate,
    response: Response,
    idempotency_key: str = Header(
        alias="Idempotency-Key",
        min_length=8,
        max_length=120,
        description="Unique across every caller. A UUID is the right shape.",
    ),
    db: Session = Depends(get_db),
    current_user=Depends(require_roles("SUPER_ADMIN", "UNIT_ADMIN")),
):
    """Hold a resource for one dated window.

    201 when the hold is taken, 200 when the same request arrives again under
    the same key, 409 when something already has the window. A booking system
    talking over a network retries, and a retry that books a second room is
    worse than one that fails, so the key is required rather than optional.

    What it checks against is exactly what GET availability reports: the same
    two queries, through the same expansion. A booking accepted for an hour
    availability calls busy is the double booking this endpoint exists to
    prevent, so the two cannot be allowed to answer differently.

    The check and the insert are not one atomic step, and two callers can both
    pass the check before either inserts. Hold against hold, that no longer
    decides anything: migration 010 put an exclusion constraint on the table
    and the database refuses the second row whatever the timing was. The loser
    is told 409, the same as if the check had caught it.

    Hold against timetable is still the check plus the row lock. A slot lives
    in another table and no constraint spans the two, so a booking and a class
    landing on the same room at the same instant is held off by locking the
    resource row, which is a lock and not a rule: it works where the database
    takes it and does nothing where it does not.

    The rule runs both ways. A class cannot be put on top of a hold either:
    creating a slot, moving one, and uploading a timetable are all refused
    where a booking already stands, so a hold taken here holds against the
    timetable and not only against other holds.
    """
    # Still here, and now for one job: holding a booking off against a class,
    # which is in another table and so is out of reach of the constraint.
    # with_for_update compiles to nothing on SQLite, which is what the suite
    # runs on, so this serialises two callers on Postgres and is a no-op in
    # the tests, which is why that overlap is the one the tests cannot prove.
    resource = db.query(Resource).filter(Resource.id == resource_id).with_for_update().first()
    if not resource:
        raise HTTPException(status_code=404, detail="Resource not found")

    fingerprint = _fingerprint(resource_id, payload)
    seen = db.query(Reservation).filter(Reservation.idempotency_key == idempotency_key).first()
    if seen is not None:
        if seen.request_fingerprint != fingerprint:
            raise HTTPException(status_code=422, detail=KEY_REUSED)
        # The same request, again. Hand back what it made the first time,
        # cancelled or not: a retry is asking what happened, not asking for
        # a second room.
        response.status_code = status.HTTP_200_OK
        return _view(seen, resource)

    conflicts = _conflicts_for(db, resource_id, payload)
    if conflicts:
        raise _already_taken(conflicts)

    reservation = Reservation(
        resource_id=resource_id,
        reserved_date=payload.date,
        time_window_start=payload.start,
        time_window_end=payload.end,
        purpose=payload.purpose.strip(),
        requested_by_id=current_user.id,
        idempotency_key=idempotency_key,
        request_fingerprint=fingerprint,
        status=ReservationStatus.HELD,
    )
    db.add(reservation)
    try:
        db.commit()
    except IntegrityError as exc:
        db.rollback()
        if OVERLAP_CONSTRAINT in str(exc.orig):
            # Somebody else took the window between the check above and this
            # insert, and the constraint caught what the check could not.
            # Asking again names the row that won, so the caller is told what
            # it lost to rather than only that it lost.
            raise _already_taken(_conflicts_for(db, resource_id, payload)) from None
        # Two copies of the same request arrived at once and the loser lands
        # here. The winner's row is the answer to both.
        won = db.query(Reservation).filter(Reservation.idempotency_key == idempotency_key).first()
        if won is None or won.request_fingerprint != fingerprint:
            raise HTTPException(status_code=422, detail=KEY_REUSED) from None
        response.status_code = status.HTTP_200_OK
        return _view(won, resource)

    db.refresh(reservation)
    return _view(reservation, resource)


@router.delete("/{resource_id}/reservations/{reservation_id}", response_model=ReservationResponse)
def cancel_reservation(
    resource_id: int,
    reservation_id: int,
    db: Session = Depends(get_db),
    current_user=Depends(require_roles("SUPER_ADMIN", "UNIT_ADMIN")),
):
    """Let a hold go. The row stays.

    Cancelling marks the reservation and leaves it in the table. A deleted
    row cannot be told to anybody, and an outside system that was informed
    the room was held has to be able to learn that it no longer is. A
    cancelled hold stops occupying the window immediately.

    Cancelling twice is not an error. The caller wanted the room free and the
    room is free.

    A hold is let go by whoever took it. More than one system books through
    here, and one integration dropping another's hold is how a room goes
    quietly free under something that still believes it has it. A SUPER_ADMIN
    is the exception, because a hold taken by an account that no longer
    exists has nobody left to cancel it.
    """
    reservation = (
        db.query(Reservation)
        .filter(Reservation.id == reservation_id, Reservation.resource_id == resource_id)
        .first()
    )
    if not reservation:
        raise HTTPException(status_code=404, detail="Reservation not found")

    if (
        current_user.role_type.value != "SUPER_ADMIN"
        and reservation.requested_by_id != current_user.id
    ):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=NOT_YOUR_HOLD)

    if reservation.status is not ReservationStatus.CANCELLED:
        reservation.status = ReservationStatus.CANCELLED
        reservation.cancelled_at = datetime.datetime.now(datetime.UTC)
        db.commit()
        db.refresh(reservation)
    return _view(reservation, reservation.resource)
