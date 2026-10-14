# Copyright 2026 Chronos Ledger Contributors
# Licensed under the Apache License, Version 2.0

import datetime
import hashlib

from fastapi import APIRouter, Depends, Header, Query, Response, status
from fastapi.encoders import jsonable_encoder
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session, joinedload

from app.core import change_feed, clock
from app.core.database import get_db
from app.core.errors import ChronosError, ErrorCode
from app.core.idempotency import KEY_REUSED
from app.core.pagination import Page
from app.core.security import ensure_resource_scope, get_current_user, require_roles
from app.core.time import org_today
from app.models.db import (
    RequirementOwner,
    Reservation,
    ReservationStatus,
    Resource,
    ResourceMode,
)
from app.schemas.resources import (
    POOL_NEEDS_CAPACITY,
    AvailabilityResponse,
    BookingsWouldNotFit,
    CapacityExceeded,
    RequirementCreate,
    RequirementResponse,
    ReservationConflict,
    ReservationCreate,
    ReservationCreated,
    ReservationRefTaken,
    ReservationResponse,
    ReservationUpdate,
    ResourceCreate,
    ResourceResponse,
    ResourceUpdate,
)
from app.services.availability import (
    MAX_RANGE_DAYS,
    booked_days,
    booked_slots,
    clashing,
    full_intervals,
    held_reservations,
    held_span,
    last_date,
    occupied,
    pool_state,
    pool_stretches,
    window_conflicts,
)
from app.services.requirements import (
    add_requirement,
    check_assignments,
    delete_requirement,
    free_for,
    list_requirements,
    resolve,
)
from app.services.resource_classes import require_active_class

router = APIRouter()

RANGE_BACKWARDS = "from must not be after to"
RANGE_TOO_LONG = f"the range must not exceed {MAX_RANGE_DAYS} days"
ALREADY_TAKEN = "the resource is already taken for part of that window"
NOT_YOUR_HOLD = "only the caller that took a hold may cancel it"
NOT_YOUR_HOLD_TO_CHANGE = "only the caller that took a hold may change it"
REF_TAKEN = "a reservation of yours already has that external_ref"
CODE_TAKEN = "a resource with that code already exists"
POOL_FULL = "the resource does not have that many units left for that window"
ONE_OF_IT = "quantity above 1 needs a POOLED resource"
WOULD_NOT_FIT = "bookings still to come would not fit the resource after that change"
# The name of the exclusion constraint on reservations. Postgres puts it in
# the error text, which is how an overlap is told apart from the unique keys
# on the idempotency key and the external_ref: all arrive here as one
# IntegrityError.
OVERLAP_CONSTRAINT = "ex_reservations_no_overlap"


@router.get("/", operation_id="resources.list", response_model=list[ResourceResponse])
def list_resources(
    resource_type: str | None = None,
    active: bool | None = None,
    code: str | None = None,
    page: Page = Depends(),
    db: Session = Depends(get_db),
    _=Depends(get_current_user),
):
    """Every room, person and piece of equipment the schedule can point at.

    Readable by anyone signed in. A resource is a place and a capacity, not
    a secret, and an external system that has to book one needs to be able
    to find it first.

    Rows come back in code order, and the page is optional: with no limit and
    no offset this is every row, as it always was. A building with hundreds of
    rooms is a list a settings screen should be able to ask for a page of.
    """
    query = db.query(Resource)
    if resource_type is not None:
        query = query.filter(Resource.resource_type == resource_type)
    if active is not None:
        query = query.filter(Resource.active == active)
    if code is not None:
        query = query.filter(Resource.code == code.strip())
    return page.rows(query, Resource.code)


# Declared before any route on /{resource_id}, so that a GET added there later
# cannot take this path for a resource id.
@router.get(
    "/reservations",
    operation_id="resources.listReservations",
    response_model=list[ReservationResponse],
)
def list_reservations(
    external_ref: str | None = None,
    page: Page = Depends(),
    db: Session = Depends(get_db),
    current_user=Depends(require_roles("ORG_ADMIN", "UNIT_ADMIN")),
):
    """The caller's own reservations, cancelled ones included, in id order.

    Only the caller's, for every role. A reference is unique per caller and
    means nothing outside the system that chose it, so an integration asking
    for its booking by reference must get its own booking back and never
    another caller's under the same string. An ORG_ADMIN gets its own too:
    this is the list an integration finds its bookings in, not a view of
    everybody's.

    external_ref matches exactly, so it returns one reservation or none.
    """
    query = (
        db.query(Reservation)
        .options(joinedload(Reservation.resource))
        .filter(Reservation.requested_by_id == current_user.id)
    )
    if external_ref is not None:
        query = query.filter(Reservation.external_ref == external_ref)
    return [reservation_view(held, held.resource) for held in page.rows(query, Reservation.id)]


@router.post(
    "/",
    operation_id="resources.create",
    response_model=ResourceResponse,
    status_code=status.HTTP_201_CREATED,
)
def create_resource(
    payload: ResourceCreate,
    db: Session = Depends(get_db),
    _=Depends(require_roles("ORG_ADMIN")),
):
    """Register a room before any timetable names it.

    Otherwise a room comes into being only when an import or a slot first
    names it. That suits a timetable and does not suit a system that manages
    its own rooms and wants to book one before any class is put in it. The
    row is the one the importer would have made, so a later CSV naming the
    room finds it rather than creating a second.

    resource_type is the code of an active class of the organization and
    defaults to ROOM. A class that is unknown, inactive or another
    organization's is 422 UNKNOWN_RESOURCE_CLASS. user_id is not taken: a
    resource tied to a user row is a different thing to create.

    A code already taken is 409. A caller retrying after a lost response
    reads the room back with GET /resources/?code=, or sends an
    Idempotency-Key and gets the first 201 back.
    """
    fields = payload.model_dump()
    if fields["label"] is None:
        fields["label"] = fields["code"]
    require_active_class(db, fields["resource_type"])
    resource = Resource(**fields)
    db.add(resource)
    try:
        # The insert is what hands out the id the marker points at and what
        # the taken code is refused by, so the flush that does both sits
        # inside the same try as the commit.
        db.flush()
        change_feed.record(db, change_feed.RESOURCE, resource.id, change_feed.CREATED)
        db.commit()
    except IntegrityError:
        db.rollback()
        raise ChronosError(
            status_code=status.HTTP_409_CONFLICT, detail=CODE_TAKEN, code=ErrorCode.ALREADY_EXISTS
        ) from None
    db.refresh(resource)
    return resource


def _resource_or_404(db: Session, resource_id: int) -> Resource:
    resource = db.query(Resource).filter(Resource.id == resource_id).first()
    if not resource:
        raise ChronosError(status_code=404, detail="Resource not found", code=ErrorCode.NOT_FOUND)
    return resource


@router.get(
    "/{resource_id}/requirements",
    operation_id="resources.listRequirements",
    response_model=list[RequirementResponse],
)
def list_resource_requirements(
    resource_id: int, db: Session = Depends(get_db), _=Depends(get_current_user)
):
    """What booking this resource also holds, in id order."""
    _resource_or_404(db, resource_id)
    return list_requirements(db, RequirementOwner.RESOURCE, resource_id)


@router.post(
    "/{resource_id}/requirements",
    operation_id="resources.createRequirement",
    response_model=RequirementResponse,
    status_code=status.HTTP_201_CREATED,
)
def create_resource_requirement(
    resource_id: int,
    payload: RequirementCreate,
    db: Session = Depends(get_db),
    _=Depends(require_roles("ORG_ADMIN")),
):
    """Say that booking this resource also needs another, or any of a kind.

    Whoever books the resource then holds the target too, in the same
    transaction, for the same window widened by before_minutes and
    after_minutes. enforcement left out follows the organization's
    default_requirement_enforcement.

    422 for a target that is not a resource of this organization, a quantity
    above 1 on a named target that is not POOLED, and a cycle of named
    resources (a needing b needing a). 409 for a requirement the resource
    already has.
    """
    _resource_or_404(db, resource_id)
    return add_requirement(db, RequirementOwner.RESOURCE, resource_id, payload)


@router.delete(
    "/{resource_id}/requirements/{requirement_id}",
    operation_id="resources.deleteRequirement",
    status_code=status.HTTP_204_NO_CONTENT,
)
def delete_resource_requirement(
    resource_id: int,
    requirement_id: int,
    db: Session = Depends(get_db),
    _=Depends(require_roles("ORG_ADMIN")),
):
    """Drop a requirement. Holds already taken under it stay until cancelled."""
    delete_requirement(db, RequirementOwner.RESOURCE, resource_id, requirement_id)


@router.get(
    "/{resource_id}/availability",
    operation_id="resources.getAvailability",
    response_model=AvailabilityResponse,
)
def resource_availability(
    resource_id: int,
    from_: datetime.date = Query(alias="from"),
    to: datetime.date = Query(),
    with_requirements: bool = False,
    start: datetime.time | None = None,
    end: datetime.time | None = None,
    db: Session = Depends(get_db),
    _=Depends(get_current_user),
):
    """When this resource is already taken, between two dates inclusive.

    The timetable, the bookings and the days already generated, in one
    answer. Anything less would let a caller read a room as free and then be
    refused when it tried to take the hour, or take an hour something had
    already claimed.

    A slot counts when its cycle is open and the date is inside the cycle's
    own dates, both ends included, because those are the two tests the
    nightly ledger generation applies before it books a day. Answering
    anything else here would tell a caller a room was free on a date the
    ledger is going to fill, which is the direction that ends in two bookings.

    A generated day counts whatever its cycle says, because closing a cycle
    keeps the days already past and any ahead that carry attendance or a
    note, and the database refuses a second row on top of them either way. Where a day and the slot
    it came from both cover a date, the day is what is reported: it is the
    row that holds the hour, and it keeps the window it was generated with
    when the slot is later corrected.

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

    The resource's mode decides what a booking counts for, and this answers
    by the same rule the booking route refuses by. On an exclusive resource
    every hold is busy. On a pooled one the timetable is busy, because a
    class takes the whole pool, and the holds are busy only where they add
    up to the capacity: those intervals name no single row and are cut to the
    range. On a shared one no hold is ever busy.

    with_requirements=true also answers whether the resource and everything
    it requires could be held for one window, with nothing held. The window
    is `from` with start and end, which are then required, because a kind
    of resource has no busy intervals to show: whether "any anaesthetist" is
    free is only a question about a window. requirements_met is true when the
    resource itself is free for it and every requirement could be met, and
    unmet lists the requirements that could not, ADVISORY ones included.
    """
    resource = db.query(Resource).filter(Resource.id == resource_id).first()
    if not resource:
        raise ChronosError(status_code=404, detail="Resource not found", code=ErrorCode.NOT_FOUND)
    if with_requirements and (start is None or end is None or from_ != to or start == end):
        raise ChronosError(
            status_code=422,
            detail="with_requirements needs from equal to to, and a start and an end that differ",
            code=ErrorCode.INVALID_VALUE,
        )
    if from_ > to:
        raise ChronosError(status_code=422, detail=RANGE_BACKWARDS, code=ErrorCode.INVALID_VALUE)
    if (to - from_).days + 1 > MAX_RANGE_DAYS:
        raise ChronosError(status_code=422, detail=RANGE_TOO_LONG, code=ErrorCode.INVALID_VALUE)

    holds = held_reservations(db, resource_id, from_, to)
    busy = occupied(
        booked_slots(db, resource_id),
        holds if resource.mode is ResourceMode.EXCLUSIVE else [],
        booked_days(db, resource_id, from_, to),
        from_,
        to,
    )
    if resource.mode is ResourceMode.POOLED:
        busy += full_intervals(holds, resource.capacity, from_, to)
        busy.sort(
            key=lambda entry: (entry["date"], entry["start"], entry["end_date"], entry["end"])
        )
    answer = {
        "resource_id": resource.id,
        "code": resource.code,
        "from": from_,
        "to": to,
        "busy": busy,
    }
    if with_requirements:
        window = (from_, start, end)
        unmet = resolve(db, [(RequirementOwner.RESOURCE, resource.id)], window, {resource.id}).unmet
        answer["requirements_met"] = not unmet and free_for(db, resource, window)
        answer["unmet"] = unmet
    return answer


@router.patch(
    "/{resource_id}",
    operation_id="resources.update",
    response_model=ResourceResponse,
    responses={409: {"model": BookingsWouldNotFit}},
)
def update_resource(
    resource_id: int,
    payload: ResourceUpdate,
    db: Session = Depends(get_db),
    _=Depends(require_roles("ORG_ADMIN")),
):
    """Fill in what a CSV could not know.

    Rooms arrive from an import knowing only their name. Their capacity and
    where they physically are is something a person knows, and until this
    existed there was no way to tell the system: geofencing was a feature
    with no route that could switch it on.

    mode and capacity change what the bookings on the resource are held to,
    so a change that bookings still to come would no longer fit is refused
    with 409 and RESOURCE_BOOKINGS_WOULD_NOT_FIT, naming them. Cancel those
    first. A change that fits is written onto those bookings too, because
    each one carries its resource's mode for the database's sake
    (app.models.db.Reservation).
    """
    # Locked, as the booking route locks it, so no booking can land between
    # the check below and the change.
    resource = db.query(Resource).filter(Resource.id == resource_id).with_for_update().first()
    if not resource:
        raise ChronosError(status_code=404, detail="Resource not found", code=ErrorCode.NOT_FOUND)

    # exclude_unset, not exclude_none: clearing a coordinate is a thing an
    # admin does on purpose, and it has to be distinguishable from not
    # mentioning it.
    fields = payload.model_dump(exclude_unset=True)
    mode = fields.get("mode", resource.mode)
    capacity = fields.get("capacity", resource.capacity)
    if mode is ResourceMode.POOLED and not capacity:
        raise ChronosError(
            status_code=422, detail=POOL_NEEDS_CAPACITY, code=ErrorCode.INVALID_VALUE
        )
    if mode is not resource.mode or (mode is ResourceMode.POOLED and capacity != resource.capacity):
        # From yesterday, so a night that opened yesterday and is still
        # running counts.
        since = org_today() - datetime.timedelta(days=1)
        to_come = (
            db.query(Reservation)
            .filter(
                Reservation.resource_id == resource_id,
                Reservation.status == ReservationStatus.HELD,
                Reservation.reserved_date >= since,
            )
            .order_by(Reservation.id)
            .all()
        )
        misfits = _would_not_fit(db, resource_id, mode, capacity, to_come)
        if misfits:
            raise _bookings_would_not_fit(misfits, resource)
        if mode is not resource.mode:
            for held in to_come:
                held.mode = mode

    for field, value in fields.items():
        setattr(resource, field, value)
    change_feed.record(db, change_feed.RESOURCE, resource.id, change_feed.UPDATED)
    try:
        db.commit()
    except IntegrityError as exc:
        # The check above runs under the row lock, so this is the database
        # disagreeing with it, not a race the lock missed. Answer it the way
        # the check would have rather than as a 500.
        db.rollback()
        if OVERLAP_CONSTRAINT not in str(exc.orig):
            raise
        raise ChronosError(
            status_code=status.HTTP_409_CONFLICT,
            detail={"message": WOULD_NOT_FIT, "reservations": []},
            code=ErrorCode.RESOURCE_BOOKINGS_WOULD_NOT_FIT,
        ) from None
    db.refresh(resource)
    return resource


def _would_not_fit(
    db: Session, resource_id: int, mode: ResourceMode, capacity: int | None, holds: list
) -> list[Reservation]:
    """The holds that would break the rules of the mode they are moving to.

    Shared holds anything. Exclusive holds one booking at a time, of one
    unit. Pooled holds up to capacity units at a time. Leaving shared also
    means meeting the timetable, which a shared hold never had to, so on
    the way to either of the other two a hold sitting on a slot or a
    generated day does not fit either.
    """
    if mode is ResourceMode.SHARED or not holds:
        return []
    spans = {held.id: held_span(held) for held in holds}
    misfits = set()

    first = min(held.reserved_date for held in holds)
    last = max(span[1].date() for span in spans.values())
    timetable = occupied(
        booked_slots(db, resource_id), [], booked_days(db, resource_id, first, last), first, last
    )
    for held in holds:
        if clashing(timetable, held.reserved_date, held.time_window_start, held.time_window_end):
            misfits.add(held.id)

    if mode is ResourceMode.EXCLUSIVE:
        for held in holds:
            if held.quantity > 1:
                misfits.add(held.id)
            for other in holds:
                if other.id != held.id and _meet(spans[held.id], spans[other.id]):
                    misfits.add(held.id)
    else:
        for stretch in pool_stretches(holds, capacity + 1):
            misfits.update(held.id for held in holds if _meet(spans[held.id], stretch))
    return [held for held in holds if held.id in misfits]


def _meet(first: tuple, second: tuple) -> bool:
    """Half open, as everywhere: ten o'clock ends and ten o'clock starts do not meet."""
    return first[0] < second[1] and second[0] < first[1]


def _bookings_would_not_fit(misfits: list[Reservation], resource: Resource) -> ChronosError:
    return ChronosError(
        status_code=status.HTTP_409_CONFLICT,
        detail=jsonable_encoder(
            {
                "message": WOULD_NOT_FIT,
                "reservations": [reservation_view(held, resource) for held in misfits],
            }
        ),
        code=ErrorCode.RESOURCE_BOOKINGS_WOULD_NOT_FIT,
    )


def _fingerprint(resource_id: int, payload: ReservationCreate) -> str:
    """What was asked for, boiled down to a string a replay can be checked against.

    The resource is in it because it is in the path and not in the body: the
    same key sent to two different rooms is two different requests, and
    without this it would look like one.

    external_ref is in it only when it was sent, so every fingerprint stored
    before the field existed still matches a retry of the same request.
    quantity follows the same rule, and is labelled so that a quantity can
    never be read as a reference.
    """
    parts = [
        str(resource_id),
        payload.date.isoformat(),
        payload.start.isoformat(),
        payload.end.isoformat(),
        payload.purpose.strip(),
    ]
    if payload.external_ref is not None:
        parts.append(payload.external_ref)
    if "quantity" in payload.model_fields_set:
        parts.append(f"quantity={payload.quantity}")
    if payload.assignments:
        # In the order sent, because the order is the order they are used in.
        chosen = ";".join(
            f"{kind}:{','.join(map(str, ids))}" for kind, ids in sorted(payload.assignments.items())
        )
        parts.append(f"assignments={chosen}")
    asked = "|".join(parts)
    return hashlib.sha256(asked.encode("utf-8")).hexdigest()


def _conflicts_for(
    db: Session, resource_id: int, payload: ReservationCreate, holds: bool = True
) -> list[dict]:
    """What already holds any part of the asked-for window.

    Exactly the three queries GET availability runs, through the same
    expansion. A booking accepted for an hour availability calls busy is the
    double booking this endpoint exists to prevent, so the two cannot be
    allowed to answer differently.

    Asked twice: once before inserting, and again if the database refuses the
    insert, because by then somebody else's row is in the table and is the
    thing to name.

    A window that runs past midnight is asked about over two days, not one.
    Expanding only the date it opened on would leave out everything sitting
    on the far side of midnight, and a booking from 22:00 to 06:00 would be
    accepted straight through the top of somebody else's morning.

    holds=False asks about the timetable alone, for a pooled resource, where
    the other holds are a sum and are counted by _pool_check instead.
    """
    return window_conflicts(db, resource_id, payload.date, payload.start, payload.end, holds=holds)


def _last_date(payload: ReservationCreate) -> datetime.date:
    return last_date(payload.date, payload.start, payload.end)


def _pool_check(db: Session, resource: Resource, payload: ReservationCreate) -> None:
    """Refuse a pooled booking the pool has not got the units left for.

    The most units already held at any one moment of the window, plus the
    ones asked for, against the capacity. Run under the resource's row lock,
    which on PostgreSQL is what makes the sum true at the moment of the
    insert: a second booking of the same pool waits for this one to commit
    and then counts it. On SQLite BEGIN IMMEDIATE has already made every
    writer wait its turn.
    """
    last = _last_date(payload)
    taken, holds = pool_state(db, resource.id, payload.date, payload.start, payload.end)
    if taken + payload.quantity > resource.capacity:
        raise ChronosError(
            status_code=status.HTTP_409_CONFLICT,
            detail=jsonable_encoder(
                {
                    "message": POOL_FULL,
                    "conflicts": occupied([], holds, [], payload.date, last),
                    "capacity": resource.capacity,
                    "taken": taken,
                    "requested": payload.quantity,
                }
            ),
            code=ErrorCode.RESOURCE_CAPACITY_EXCEEDED,
        )


def _already_taken(conflicts: list[dict]) -> ChronosError:
    # jsonable_encoder because the detail of an HTTPException is serialised
    # straight to JSON, with none of the conversion a response_model would
    # have done for the dates and times in here.
    return ChronosError(
        status_code=status.HTTP_409_CONFLICT,
        detail=jsonable_encoder({"message": ALREADY_TAKEN, "conflicts": conflicts}),
        code=ErrorCode.RESOURCE_CONFLICT,
    )


def _ref_taken(existing: Reservation) -> ChronosError:
    # An object rather than a string so the id is a field a program reads,
    # not a number to be parsed out of a sentence.
    return ChronosError(
        status_code=status.HTTP_409_CONFLICT,
        detail={"message": REF_TAKEN, "reservation_id": existing.id},
        code=ErrorCode.RESERVATION_EXTERNAL_REF_TAKEN,
    )


def reservation_view(reservation: Reservation, resource: Resource) -> dict:
    """The ReservationResponse shape, built once.

    Public because the change feed hands back the same reservation in the same
    shape, and a second copy of this dict is a second place for the two to
    drift apart.
    """
    return {
        "id": reservation.id,
        "resource_id": resource.id,
        "resource_code": resource.code,
        "date": reservation.reserved_date,
        "start": reservation.time_window_start,
        "end": reservation.time_window_end,
        "purpose": reservation.purpose,
        "quantity": reservation.quantity,
        "status": reservation.status,
        "requested_by_id": reservation.requested_by_id,
        "idempotency_key": reservation.idempotency_key,
        "external_ref": reservation.external_ref,
        "created_at": reservation.created_at,
        "cancelled_at": reservation.cancelled_at,
        "parent_reservation_id": reservation.parent_reservation_id,
    }


def created_view(
    db: Session, reservation: Reservation, resource: Resource, children=None, unmet=None
) -> dict:
    """The create response: the booking, what was held alongside it, and the gaps.

    children is read from the table when it is not handed in, which is the
    case for a replay. A gap is not stored, so a replay's unmet is empty.
    """
    if children is None:
        children = (
            db.query(Reservation)
            .options(joinedload(Reservation.resource))
            .filter(Reservation.parent_reservation_id == reservation.id)
            .order_by(Reservation.id)
            .all()
        )
    return {
        **reservation_view(reservation, resource),
        "children": [reservation_view(child, child.resource) for child in children],
        "unmet": unmet or [],
    }


@router.post(
    "/{resource_id}/reservations",
    operation_id="resources.createReservation",
    response_model=ReservationCreated,
    status_code=status.HTTP_201_CREATED,
    # The taken reference first, the same order as docs/openapi.yaml. The
    # generated clients try each shape in turn, and the spec requires nothing
    # in ReservationConflict's detail, so the other way round they would read
    # a taken reference as a window conflict.
    # CapacityExceeded before ReservationConflict for the same reason: its
    # detail is the conflict body with three numbers more.
    responses={409: {"model": ReservationRefTaken | CapacityExceeded | ReservationConflict}},
)
def create_reservation(
    resource_id: int,
    payload: ReservationCreate,
    response: Response,
    idempotency_key: str = Header(
        alias="Idempotency-Key",
        min_length=8,
        max_length=120,
        description="Unique per caller. A UUID is the right shape.",
    ),
    db: Session = Depends(get_db),
    current_user=Depends(require_roles("ORG_ADMIN", "UNIT_ADMIN")),
):
    """Hold a resource for one dated window.

    201 when the hold is taken, 200 when the same request arrives again under
    the same key, 409 when something already has the window. A booking system
    talking over a network retries, and a retry that books a second room is
    worse than one that fails, so the key is required rather than optional.

    What it checks against is exactly what GET availability reports: the same
    three queries, through the same expansion. A booking accepted for an hour
    availability calls busy is the double booking this endpoint exists to
    prevent, so the two cannot be allowed to answer differently.

    The check and the insert are not one atomic step, and two callers can both
    pass the check before either inserts. Hold against hold, that no longer
    decides anything: the table carries an exclusion constraint and the
    database refuses the second row whatever the timing was. The loser
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

    An external_ref already on one of the caller's reservations, cancelled
    or not, is a 409 naming that reservation. It is checked after the key,
    so a retry under the same key is still answered from the row it made,
    and before the window, so a caller that books the same thing again under
    a new key is told it already has it rather than that something is in
    the way.

    The resource's mode decides what is in the way. Exclusive is all of the
    above. Pooled refuses a window the timetable holds, because a class
    takes the whole pool, and otherwise sums: quantity units are taken when
    the bookings already there leave that many free at every moment of the
    window, and refused with 409 RESOURCE_CAPACITY_EXCEEDED when they do
    not. Shared refuses nothing; the hold records who is there. A quantity
    above 1 on a resource that is not pooled is 422.

    A UNIT_ADMIN may hold a resource of its own unit and one with no unit,
    which the whole organization shares. A resource of another unit is 403
    OUTSIDE_UNIT.
    """
    # Still here, and now for one job: holding a booking off against a class,
    # which is in another table and so is out of reach of the constraint.
    # with_for_update compiles to nothing on SQLite, which is what the suite
    # runs on, so this serialises two callers on Postgres and is a no-op in
    # the tests, which is why that overlap is the one the tests cannot prove.
    resource = db.query(Resource).filter(Resource.id == resource_id).with_for_update().first()
    if not resource:
        raise ChronosError(status_code=404, detail="Resource not found", code=ErrorCode.NOT_FOUND)
    # A unit admin holds their own unit's resources and the shared ones.
    ensure_resource_scope(current_user, resource)

    fingerprint = _fingerprint(resource_id, payload)
    seen = _by_key(db, current_user.id, idempotency_key)
    if seen is not None:
        if seen.request_fingerprint != fingerprint:
            raise ChronosError(
                status_code=422, detail=KEY_REUSED, code=ErrorCode.IDEMPOTENCY_KEY_REUSED
            )
        # The same request, again. Hand back what it made the first time,
        # cancelled or not: a retry is asking what happened, not asking for
        # a second room.
        response.status_code = status.HTTP_200_OK
        return created_view(db, seen, resource)

    if payload.external_ref is not None:
        taken = _by_ref(db, current_user.id, payload.external_ref)
        if taken is not None:
            raise _ref_taken(taken)

    mode = resource.mode
    if payload.quantity > 1 and mode is not ResourceMode.POOLED:
        raise ChronosError(status_code=422, detail=ONE_OF_IT, code=ErrorCode.INVALID_VALUE)
    assignments = check_assignments(db, payload.assignments)
    if mode is not ResourceMode.SHARED:
        conflicts = _conflicts_for(db, resource_id, payload, holds=mode is ResourceMode.EXCLUSIVE)
        if conflicts:
            raise _already_taken(conflicts)
    if mode is ResourceMode.POOLED:
        _pool_check(db, resource, payload)

    reservation = Reservation(
        resource_id=resource_id,
        reserved_date=payload.date,
        time_window_start=payload.start,
        time_window_end=payload.end,
        purpose=payload.purpose.strip(),
        requested_by_id=current_user.id,
        idempotency_key=idempotency_key,
        request_fingerprint=fingerprint,
        external_ref=payload.external_ref,
        quantity=payload.quantity,
        mode=mode,
        status=ReservationStatus.HELD,
    )
    db.add(reservation)

    def lost(exc: IntegrityError):
        db.rollback()
        if OVERLAP_CONSTRAINT in str(exc.orig):
            # Somebody else took the window between the check above and this
            # insert, and the constraint caught what the check could not.
            # Asking again names the row that won, so the caller is told what
            # it lost to rather than only that it lost.
            raise _already_taken(_conflicts_for(db, resource_id, payload)) from None
        # Two copies of the same request arrived at once and the loser lands
        # here. The winner's row is the answer to both.
        won = _by_key(db, current_user.id, idempotency_key)
        if won is None and payload.external_ref is not None:
            # Or two different requests under one reference, and the other
            # one committed first. The check above saw neither; the unique
            # constraint saw both, and the row that won is the answer.
            taken = _by_ref(db, current_user.id, payload.external_ref)
            if taken is not None:
                raise _ref_taken(taken) from None
        if won is None or won.request_fingerprint != fingerprint:
            raise ChronosError(
                status_code=422, detail=KEY_REUSED, code=ErrorCode.IDEMPOTENCY_KEY_REUSED
            ) from None
        response.status_code = status.HTTP_200_OK
        return created_view(db, won, resource)

    try:
        # Flushed here rather than at the commit because the marker needs the
        # id. What the constraint refuses it refuses at the flush, and an
        # IntegrityError from a flush is the same one, so the branching above
        # reads exc.orig exactly as it did.
        db.flush()
        change_feed.record(db, change_feed.RESERVATION, reservation.id, change_feed.CREATED)
    except IntegrityError as exc:
        return lost(exc)

    # What the resource requires, held under this booking in this transaction.
    # Any refusal rolls the booking back with it, so nothing is half held.
    try:
        held = resolve(
            db,
            [(RequirementOwner.RESOURCE, resource_id)],
            (payload.date, payload.start, payload.end),
            {resource_id},
            parent=reservation,
            requester_id=current_user.id,
            assignments=assignments,
        )
    except ChronosError:
        db.rollback()
        raise
    except IntegrityError as exc:
        db.rollback()
        if OVERLAP_CONSTRAINT not in str(exc.orig):
            raise
        # The pick or the named resource was free at the check and taken by
        # the time of the insert. No second try: the caller retries.
        raise ChronosError(
            status_code=status.HTTP_409_CONFLICT,
            detail={
                "message": "a required resource was taken while it was being held",
                "conflicts": [],
            },
            code=ErrorCode.REQUIREMENT_UNSATISFIED,
        ) from None

    try:
        db.commit()
    except IntegrityError as exc:
        return lost(exc)

    db.refresh(reservation)
    return created_view(db, reservation, resource, held.children, held.unmet)


def _by_key(db: Session, requester_id: str, idempotency_key: str) -> Reservation | None:
    """The booking this requester already made under this key, if any."""
    return (
        db.query(Reservation)
        .filter(
            Reservation.requested_by_id == requester_id,
            Reservation.idempotency_key == idempotency_key,
        )
        .first()
    )


def _by_ref(db: Session, requester_id: str, external_ref: str) -> Reservation | None:
    """The booking this requester already gave this reference, if any."""
    return (
        db.query(Reservation)
        .filter(
            Reservation.requested_by_id == requester_id,
            Reservation.external_ref == external_ref,
        )
        .first()
    )


def _changeable(
    db: Session, resource_id: int, reservation_id: int, current_user, refusal: str
) -> Reservation:
    """The reservation, if it is on this resource and the caller may change it.

    The rule cancelling has always had: whoever took the hold, or an
    ORG_ADMIN, because a hold taken by an account that no longer exists has
    nobody left to act on it.
    """
    reservation = (
        db.query(Reservation)
        .filter(Reservation.id == reservation_id, Reservation.resource_id == resource_id)
        .first()
    )
    if not reservation:
        raise ChronosError(
            status_code=404, detail="Reservation not found", code=ErrorCode.NOT_FOUND
        )

    if (
        current_user.role_type.value != "ORG_ADMIN"
        and reservation.requested_by_id != current_user.id
    ):
        raise ChronosError(
            status_code=status.HTTP_403_FORBIDDEN, detail=refusal, code=ErrorCode.FORBIDDEN
        )
    return reservation


@router.patch(
    "/{resource_id}/reservations/{reservation_id}",
    operation_id="resources.updateReservation",
    response_model=ReservationResponse,
    responses={409: {"model": ReservationRefTaken}},
)
def update_reservation(
    resource_id: int,
    reservation_id: int,
    payload: ReservationUpdate,
    db: Session = Depends(get_db),
    current_user=Depends(require_roles("ORG_ADMIN", "UNIT_ADMIN")),
):
    """Set, change or clear a reservation's external_ref.

    The same reference on another of the requester's reservations is the
    same 409 create gives. A cancelled reservation keeps its reference, so
    clearing or changing it here is how a caller frees a reference to book
    under again.

    Changing nothing writes nothing: sending the reference the reservation
    already has leaves no change marker, the same as cancelling twice.
    """
    reservation = _changeable(
        db, resource_id, reservation_id, current_user, NOT_YOUR_HOLD_TO_CHANGE
    )

    fields = payload.model_dump(exclude_unset=True)
    if "external_ref" in fields and fields["external_ref"] != reservation.external_ref:
        ref = fields["external_ref"]
        # Unique per requester, and the requester is the row's, not the
        # caller's: an ORG_ADMIN changing another caller's booking is held
        # to that caller's references. A null requester has none to clash.
        requester = reservation.requested_by_id
        if ref is not None and requester is not None:
            taken = _by_ref(db, requester, ref)
            if taken is not None:
                raise _ref_taken(taken)
        reservation.external_ref = ref
        change_feed.record(db, change_feed.RESERVATION, reservation.id, change_feed.UPDATED)
        try:
            db.commit()
        except IntegrityError:
            # Another request gave the same reference to another booking
            # between the check and this commit.
            db.rollback()
            taken = _by_ref(db, requester, ref) if ref is not None and requester else None
            if taken is None:
                raise
            raise _ref_taken(taken) from None
        db.refresh(reservation)
    return reservation_view(reservation, reservation.resource)


@router.delete(
    "/{resource_id}/reservations/{reservation_id}",
    operation_id="resources.cancelReservation",
    response_model=ReservationResponse,
)
def cancel_reservation(
    resource_id: int,
    reservation_id: int,
    db: Session = Depends(get_db),
    current_user=Depends(require_roles("ORG_ADMIN", "UNIT_ADMIN")),
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
    quietly free under something that still believes it has it. An ORG_ADMIN
    is the exception, because a hold taken by an account that no longer
    exists has nobody left to cancel it.
    """
    reservation = _changeable(db, resource_id, reservation_id, current_user, NOT_YOUR_HOLD)

    if reservation.status is not ReservationStatus.CANCELLED:
        reservation.status = ReservationStatus.CANCELLED
        reservation.cancelled_at = clock.now()
        change_feed.record(db, change_feed.RESERVATION, reservation.id, change_feed.UPDATED)
        # What was held for it goes with it, in the same transaction.
        for child in (
            db.query(Reservation)
            .filter(
                Reservation.parent_reservation_id == reservation.id,
                Reservation.status == ReservationStatus.HELD,
            )
            .order_by(Reservation.id)
        ):
            child.status = ReservationStatus.CANCELLED
            child.cancelled_at = reservation.cancelled_at
            change_feed.record(db, change_feed.RESERVATION, child.id, change_feed.UPDATED)
        db.commit()
        db.refresh(reservation)
    return reservation_view(reservation, reservation.resource)
