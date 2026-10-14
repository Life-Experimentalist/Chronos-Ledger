# Copyright 2026 Chronos Ledger Contributors
# Licensed under the Apache License, Version 2.0
"""What a resource or an activity needs held alongside it.

One walk does three jobs. A booking runs it for real: each requirement that
can be met becomes a child reservation, in the booking's own transaction.
GET availability with with_requirements and the timetable checks run the
same walk as a dry run, which holds nothing and only reports. Sharing the
walk is what keeps the three answering alike: a window availability says can
be held is a window the booking route will hold.

A requirement names one resource or any resource of a kind.

A named resource is held for the window widened by the requirement's before
and after minutes, by its own mode: EXCLUSIVE must be free, POOLED must have
quantity units left, SHARED is never refused. The same rules the reservations
route applies to a booking on that resource, through the same functions.

A kind is filled from the caller's assignments first, in order, and then by
the first free active resources of that kind by code, so a retry picks the
same ones. A resource named by the caller that is not free is a gap and is
not swapped for another. Anything already held in the same booking is left
out of the pick, which is also what stops a kind from picking the resource
that asked for it.

Requirements chain, to MAX_DEPTH levels. A requirement that would sit deeper
is not resolved and counts as unmet, with the enforcement it would have had,
so a long chain is refused (or reported) and never half held without a word.
A cycle of named resources is refused when the requirement is saved
(would_cycle). A cycle that runs through a kind cannot be seen then, because
which resource the kind picks is only known at booking time; the walk leaves
everything already held out of the pick, so it ends.

REQUIRED unmet refuses the whole booking: the caller rolls the transaction
back, so nothing is held. ADVISORY unmet is listed and the rest is held.
A requirement with no enforcement of its own follows the organization's
default_requirement_enforcement, read when the walk runs.
"""

import datetime
import hashlib
from dataclasses import dataclass, field

from fastapi import status
from fastapi.encoders import jsonable_encoder
from sqlalchemy.orm import Session

from app.core import change_feed, recurrence
from app.core.errors import ChronosError, ErrorCode
from app.core.organization import DEFAULT_ORGANIZATION_ID, current_organization
from app.core.time import org_today, window_span
from app.models.db import (
    Organization,
    RequirementEnforcement,
    RequirementOwner,
    Reservation,
    ReservationStatus,
    Resource,
    ResourceMode,
    ResourceRequirement,
    ResourceType,
)
from app.services.availability import last_date, occupied, pool_state, window_conflicts

MAX_DEPTH = 4

Window = tuple[datetime.date, datetime.time, datetime.time]


def default_enforcement(db: Session) -> RequirementEnforcement:
    organization = db.get(Organization, current_organization(db) or DEFAULT_ORGANIZATION_ID)
    if organization is None:
        return RequirementEnforcement.REQUIRED
    return organization.default_requirement_enforcement


def would_cycle(db: Session, owner_resource_id: int, target_resource_id: int) -> bool:
    """Whether saving owner -> target would close a loop of named resources.

    Follows the requirements that name a resource and ignores those that name
    a kind, for the reason in the module docstring.
    """
    seen = set()
    todo = [target_resource_id]
    while todo:
        here = todo.pop()
        if here == owner_resource_id:
            return True
        if here in seen:
            continue
        seen.add(here)
        todo.extend(
            row.target_resource_id
            for row in db.query(ResourceRequirement).filter(
                ResourceRequirement.owner_kind == RequirementOwner.RESOURCE,
                ResourceRequirement.owner_id == here,
                ResourceRequirement.target_resource_id.is_not(None),
            )
        )
    return False


def _padded(window: Window, before: int, after: int) -> Window | None:
    """The window widened by the padding, or None when it would leave its day.

    A hold is one reservation row on one date, and a padded start before
    midnight of that date, or a padded end after the midnight that closes the
    window's last day, would need a row on another date. A window that itself
    runs past midnight is fine with no padding: the limit is the end of the
    day it finishes on, not the end of the day it opened on.
    """
    if not before and not after:
        return window
    day, start, end = window
    starts, ends = window_span(day, start, end)
    padded_starts = starts - datetime.timedelta(minutes=before)
    padded_ends = ends + datetime.timedelta(minutes=after)
    last_day = (ends - datetime.timedelta(microseconds=1)).date()
    opens = datetime.datetime.combine(day, datetime.time.min)
    closes = datetime.datetime.combine(last_day + datetime.timedelta(days=1), datetime.time.min)
    if padded_starts < opens or padded_ends > closes:
        return None
    if padded_starts.time() == padded_ends.time():
        return None
    return (day, padded_starts.time(), padded_ends.time())


@dataclass
class Resolution:
    children: list[Reservation] = field(default_factory=list)
    unmet: list[dict] = field(default_factory=list)


@dataclass
class _Run:
    db: Session
    default: RequirementEnforcement
    used: set[int]
    # Dry runs hold nothing and never refuse; they list every gap.
    parent: Reservation | None
    requester_id: str | None = None
    assigned: dict[ResourceType, list[int]] = field(default_factory=dict)
    named: set[int] = field(default_factory=set)
    resolution: Resolution = field(default_factory=Resolution)

    @property
    def dry(self) -> bool:
        return self.parent is None


def _problem(
    db: Session, resource: Resource, window: Window, quantity: int
) -> tuple[str, list[dict]] | None:
    """Why a resource cannot be held for a window, by its own mode, or None."""
    day, start, end = window
    if not resource.active:
        return (f"{resource.code} is not active", [])
    if resource.mode is ResourceMode.SHARED:
        return None
    if resource.mode is ResourceMode.EXCLUSIVE:
        clashes = window_conflicts(db, resource.id, day, start, end, holds=True)
        if clashes:
            return (f"{resource.code} is already taken for part of that window", clashes)
        return None
    clashes = window_conflicts(db, resource.id, day, start, end, holds=False)
    if clashes:
        return (f"{resource.code} is taken by the timetable for part of that window", clashes)
    taken, holds = pool_state(db, resource.id, day, start, end)
    if taken + quantity > resource.capacity:
        shown = occupied([], holds, [], day, last_date(day, start, end))
        return (f"{resource.code} does not have {quantity} unit(s) left for that window", shown)
    return None


def _miss(
    run: _Run,
    requirement: ResourceRequirement,
    message: str,
    conflicts: list[dict],
    missing: int = 1,
) -> None:
    enforcement = requirement.enforcement or run.default
    if enforcement is RequirementEnforcement.REQUIRED and not run.dry:
        raise ChronosError(
            status_code=status.HTTP_409_CONFLICT,
            detail=jsonable_encoder(
                {
                    "message": f"requirement {requirement.id} is not met: {message}",
                    "conflicts": conflicts,
                }
            ),
            code=ErrorCode.REQUIREMENT_UNSATISFIED,
        )
    run.resolution.unmet.append(
        {
            "requirement_id": requirement.id,
            "owner_kind": requirement.owner_kind,
            "owner_id": requirement.owner_id,
            "target_resource_id": requirement.target_resource_id,
            "target_kind": requirement.target_kind,
            "quantity": missing,
            "enforcement": enforcement,
            "message": message,
            "conflicts": conflicts,
        }
    )


def _hold(run: _Run, resource: Resource, window: Window, quantity: int) -> Reservation | None:
    """Take the resource for the window under the booking, or only note it on a dry run."""
    run.used.add(resource.id)
    if run.dry:
        return None
    parent = run.parent
    number = len(run.resolution.children) + 1
    # Derived from the parent's key so a retry finds the parent and not a
    # child, and short enough for the column whatever the key's length.
    key = f"child-{hashlib.sha256(parent.idempotency_key.encode()).hexdigest()[:32]}-{number}"
    day, start, end = window
    child = Reservation(
        resource_id=resource.id,
        reserved_date=day,
        time_window_start=start,
        time_window_end=end,
        purpose=parent.purpose,
        requested_by_id=run.requester_id,
        idempotency_key=key,
        request_fingerprint=hashlib.sha256(
            f"{parent.request_fingerprint}|{number}".encode()
        ).hexdigest(),
        quantity=quantity,
        mode=resource.mode,
        status=ReservationStatus.HELD,
        parent_reservation_id=parent.id,
    )
    run.db.add(child)
    # Flushed so the next check in this booking sees it, and so the
    # exclusion constraint speaks now rather than at the commit.
    run.db.flush()
    change_feed.record(run.db, change_feed.RESERVATION, child.id, change_feed.CREATED)
    run.resolution.children.append(child)
    return child


def _locked(db: Session, resource_id: int, lock: bool) -> Resource | None:
    """The resource, under its row lock when the walk is going to hold it."""
    query = db.query(Resource).filter(Resource.id == resource_id)
    return (query.with_for_update() if lock else query).first()


def free_for(db: Session, resource: Resource, window: Window) -> bool:
    """Whether one unit of the resource itself could be held for the window."""
    return _problem(db, resource, window, 1) is None


def _walk(run: _Run, owners: list[tuple[RequirementOwner, int]], window: Window, depth: int):
    for kind, owner_id in owners:
        rows = (
            run.db.query(ResourceRequirement)
            .filter(
                ResourceRequirement.owner_kind == kind, ResourceRequirement.owner_id == owner_id
            )
            .order_by(ResourceRequirement.id)
            .all()
        )
        # Named targets are locked together in id order, so two bookings that
        # need the same pair take them in the same order.
        named = sorted({row.target_resource_id for row in rows if row.target_resource_id})
        targets = {rid: _locked(run.db, rid, not run.dry) for rid in named}
        for row in rows:
            if depth > MAX_DEPTH:
                _miss(run, row, f"the chain of requirements is deeper than {MAX_DEPTH}", [])
                continue
            padded = _padded(window, row.before_minutes, row.after_minutes)
            if padded is None:
                if run.dry:
                    _miss(run, row, "the window with its padding would cross midnight", [])
                    continue
                raise ChronosError(
                    status_code=422,
                    detail=f"requirement {row.id}: the window with its padding would cross midnight",
                    code=ErrorCode.INVALID_VALUE,
                )
            if row.target_resource_id is not None:
                _named(run, row, targets.get(row.target_resource_id), padded, depth)
            else:
                _kind(run, row, padded, depth)


def _named(run, row, resource, window, depth):
    if resource is None:
        _miss(run, row, "the required resource no longer exists", [])
        return
    if resource.id in run.used:
        _miss(run, row, f"{resource.code} is already used by this booking", [])
        return
    quantity = row.quantity if resource.mode is ResourceMode.POOLED else 1
    problem = _problem(run.db, resource, window, quantity)
    if problem:
        _miss(run, row, *problem)
        return
    _hold(run, resource, window, quantity)
    _walk(run, [(RequirementOwner.RESOURCE, resource.id)], window, depth + 1)


def _kind(run, row, window, depth):
    wanted = run.assigned.get(row.target_kind, [])
    got = 0
    seen = []
    # Named by the caller first. One that is not free is a gap, not a reason
    # to hand the caller a resource it did not ask for.
    while got + len(seen) < row.quantity and wanted:
        resource = _locked(run.db, wanted.pop(0), not run.dry)
        if resource.id in run.used:
            problem = (f"{resource.code} is already used by this booking", [])
        else:
            problem = _problem(run.db, resource, window, 1)
        if problem:
            seen.append(problem)
            continue
        _hold(run, resource, window, 1)
        _walk(run, [(RequirementOwner.RESOURCE, resource.id)], window, depth + 1)
        got += 1
    if got + len(seen) < row.quantity:
        candidates = (
            run.db.query(Resource.id)
            .filter(Resource.resource_type == row.target_kind, Resource.active.is_(True))
            .order_by(Resource.code, Resource.id)
            .all()
        )
        for (candidate_id,) in candidates:
            if got + len(seen) >= row.quantity:
                break
            if candidate_id in run.used or candidate_id in run.named:
                continue
            resource = _locked(run.db, candidate_id, not run.dry)
            if _problem(run.db, resource, window, 1):
                continue
            _hold(run, resource, window, 1)
            _walk(run, [(RequirementOwner.RESOURCE, resource.id)], window, depth + 1)
            got += 1
    missing = row.quantity - got
    if missing:
        message, conflicts = seen[0] if seen else (f"no free {row.target_kind.value} resource", [])
        if seen:
            conflicts = [c for _, found in seen for c in found]
        _miss(
            run,
            row,
            f"{message}: {missing} of {row.quantity} {row.target_kind.value} missing",
            conflicts,
            missing,
        )


def resolve(
    db: Session,
    owners: list[tuple[RequirementOwner, int]],
    window: Window,
    used: set[int],
    parent: Reservation | None = None,
    requester_id: str | None = None,
    assignments: dict[ResourceType, list[int]] | None = None,
) -> Resolution:
    """Walk the requirements of the owners over a window.

    With a parent the requirements that can be met are held as its children
    and a REQUIRED one that cannot raises 409 REQUIREMENT_UNSATISFIED; the
    caller rolls the transaction back. Without one nothing is held and every
    gap is listed.
    """
    run = _Run(
        db=db,
        default=default_enforcement(db),
        used=set(used),
        parent=parent,
        requester_id=requester_id,
        assigned={kind: list(ids) for kind, ids in (assignments or {}).items()},
        named={rid for ids in (assignments or {}).values() for rid in ids},
    )
    _walk(run, owners, window, 1)
    left = [rid for ids in run.assigned.values() for rid in ids]
    if left:
        raise ChronosError(
            status_code=422,
            detail=f"assignments name resources no requirement asks for: {sorted(left)}",
            code=ErrorCode.INVALID_VALUE,
        )
    return run.resolution


def check_assignments(
    db: Session, assignments: dict[ResourceType, list[int]] | None
) -> dict[ResourceType, list[int]]:
    """Refuse a resource that is not of the kind it was named under, or not in this organization.

    The query is scoped to the caller's organization, so a resource of another
    one is missing here exactly as it is anywhere else.
    """
    checked = {}
    for kind, ids in (assignments or {}).items():
        for rid in ids:
            resource = db.query(Resource).filter(Resource.id == rid).first()
            if resource is None or resource.resource_type is not kind or not resource.active:
                raise ChronosError(
                    status_code=422,
                    detail=f"resource {rid} is not an active {kind.value} of this organization",
                    code=ErrorCode.INVALID_VALUE,
                )
        checked[kind] = list(ids)
    return checked


def unmet_for_window(
    db: Session, activity_id: int | None, resource_id: int | None, window: Window
) -> list[dict]:
    """The requirements of an activity and of its resource that a window cannot meet.

    A dry run for the timetable, which reports and never refuses. The slot's
    own resource is left out of every pick.
    """
    owners = []
    used = set()
    if activity_id is not None:
        owners.append((RequirementOwner.ACTIVITY, activity_id))
    if resource_id is not None:
        owners.append((RequirementOwner.RESOURCE, resource_id))
        used.add(resource_id)
    if not owners:
        return []
    return resolve(db, owners, window, used).unmet


# How far ahead to look for the date a slot next runs on. A weekly or
# monthly rule has one well inside this; a yearly one may not, and then there
# is nothing to check and nothing is reported.
NEXT_RUN_LOOKAHEAD_DAYS = 366


def unmet_for_slot(db: Session, slot) -> list[dict]:
    """What the slot's next run cannot have, for the responses that report it.

    The next date is the first one on or after today inside the cycle's
    bounds. One entry per unmet requirement: its id, the date checked and the
    message. Empty when neither the activity nor the resource requires
    anything, which is the common case and costs two small queries.
    """
    needing = owners_with_requirements(db)
    if ("ACTIVITY", slot.activity_id) not in needing and (
        "RESOURCE",
        slot.resource_id,
    ) not in needing:
        return []
    cycle = slot.activity.cycle
    first = max(org_today(), cycle.date_bounds_start)
    last = min(cycle.date_bounds_end, first + datetime.timedelta(days=NEXT_RUN_LOOKAHEAD_DAYS))
    dates = recurrence.occurrences(slot.rrule, slot.dtstart, first, last)
    if not dates:
        return []
    window = (dates[0], slot.time_window_start, slot.time_window_end)
    return [
        {"requirement_id": gap["requirement_id"], "date": dates[0], "message": gap["message"]}
        for gap in unmet_for_window(db, slot.activity_id, slot.resource_id, window)
    ]


def owners_with_requirements(db: Session) -> set[tuple[str, int]]:
    """(owner kind name, owner id) for every owner that has a requirement.

    Lets the timetable checks skip the many rows whose activity and resource
    require nothing, without a query for each.
    """
    rows = db.query(ResourceRequirement.owner_kind, ResourceRequirement.owner_id).distinct().all()
    return {(kind.value, owner_id) for kind, owner_id in rows}


def list_requirements(
    db: Session, owner_kind: RequirementOwner, owner_id: int
) -> list[ResourceRequirement]:
    return (
        db.query(ResourceRequirement)
        .filter(
            ResourceRequirement.owner_kind == owner_kind, ResourceRequirement.owner_id == owner_id
        )
        .order_by(ResourceRequirement.id)
        .all()
    )


def _refuse(detail: str, status_code: int = 422, code: ErrorCode = ErrorCode.INVALID_VALUE):
    return ChronosError(status_code=status_code, detail=detail, code=code)


def add_requirement(
    db: Session, owner_kind: RequirementOwner, owner_id: int, payload
) -> ResourceRequirement:
    """Save a requirement, refusing the ones that could never be held.

    Activities are never targets, which the payload cannot express anyway.
    A named target must be a resource of this organization. A quantity above
    1 on a named target is units of a pool, so the target must be POOLED. An
    owner that is a resource may not (through any chain of named resources)
    require itself.
    """
    if payload.target_resource_id is not None:
        target = db.query(Resource).filter(Resource.id == payload.target_resource_id).first()
        if target is None:
            raise _refuse("the target resource does not exist in this organization")
        if payload.quantity > 1 and target.mode is not ResourceMode.POOLED:
            raise _refuse("a quantity above 1 on a named resource needs it to be POOLED")
        if owner_kind is RequirementOwner.RESOURCE and would_cycle(db, owner_id, target.id):
            raise _refuse("that requirement would make a resource need itself, through a cycle")
    same = db.query(ResourceRequirement).filter(
        ResourceRequirement.owner_kind == owner_kind,
        ResourceRequirement.owner_id == owner_id,
        ResourceRequirement.target_resource_id == payload.target_resource_id
        if payload.target_resource_id is not None
        else ResourceRequirement.target_kind == payload.target_kind,
    )
    if same.first() is not None:
        raise _refuse(
            "that owner already requires that target",
            status_code=status.HTTP_409_CONFLICT,
            code=ErrorCode.ALREADY_EXISTS,
        )
    row = ResourceRequirement(owner_kind=owner_kind, owner_id=owner_id, **payload.model_dump())
    db.add(row)
    db.commit()
    db.refresh(row)
    return row


def delete_requirement(
    db: Session, owner_kind: RequirementOwner, owner_id: int, requirement_id: int
) -> None:
    row = (
        db.query(ResourceRequirement)
        .filter(
            ResourceRequirement.id == requirement_id,
            ResourceRequirement.owner_kind == owner_kind,
            ResourceRequirement.owner_id == owner_id,
        )
        .first()
    )
    if row is None:
        raise ChronosError(
            status_code=404, detail="Requirement not found", code=ErrorCode.NOT_FOUND
        )
    db.delete(row)
    db.commit()
