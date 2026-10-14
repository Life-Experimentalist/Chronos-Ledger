# Copyright 2026 Chronos Ledger Contributors
# Licensed under the Apache License, Version 2.0


import datetime
import logging

from fastapi import APIRouter, Depends, Query
from fastapi.encoders import jsonable_encoder
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.core import clock, recurrence
from app.core.database import get_db
from app.core.errors import ChronosError, ErrorCode
from app.core.pagination import Page
from app.core.redis_client import get_redis
from app.core.security import ensure_unit_scope, get_current_user, require_roles
from app.core.time import org_today
from app.cron.ledger_generator import materialize_horizon
from app.models.db import (
    Activity,
    ActivityEnrollment,
    DailyLedger,
    PlanningCycle,
    StructuralMasterSlot,
    User,
)
from app.schemas.resources import ReservationConflict
from app.schemas.schedule import (
    ActivityCreate,
    ActivityResponse,
    ActivityUpdate,
    ConflictReport,
    CycleActivationConflict,
    DailyLedgerUpdate,
    EnrollmentCreate,
    EnrollmentResponse,
    MasterSlotCreate,
    MasterSlotUpdate,
    PlanningCycleCreate,
    PlanningCycleResponse,
    RetireResult,
    StaffLocationResponse,
)
from app.services.availability import (
    days_against_slot,
    held_against_slot,
    slots_against_slot,
)
from app.services.conflicts import MAX_CONFLICT_RANGE_DAYS, find_conflicts
from app.services.location_resolver import determine_staff_current_states
from app.services.master_slot import (
    delete_slot,
    propagate_slot_corrections,
    rows_in_use,
    withdraw_planned_days,
)
from app.services.resource import get_or_create_room

logger = logging.getLogger(__name__)

router = APIRouter()

ROOM_IS_HELD = "the resource is held for part of that window"
ROOM_IS_SCHEDULED = "the resource is already on the timetable for part of that window"
ROOM_HAS_A_DAY = "the resource already has a generated day in part of that window"
CYCLE_IS_BLOCKED = "opening this cycle would put its slots on rooms already taken"
CONFLICT_RANGE_BACKWARDS = "from must not be after to"
CONFLICT_RANGE_TOO_LONG = f"the range must not exceed {MAX_CONFLICT_RANGE_DAYS} days"


def _anchor(rule: str, on_or_after: datetime.date) -> datetime.date:
    """The dtstart to store, or a 422 for a rule with no date left from there."""
    try:
        return recurrence.anchor(rule, on_or_after)
    except ValueError as exc:
        raise ChronosError(status_code=422, detail=str(exc), code=ErrorCode.INVALID_VALUE) from None


def _refuse_if_held(db, cycle, resource_id, rule, dtstart, start, end) -> None:
    """Refuse a slot that would be laid on top of a booking.

    Chronos refused an external booking that clashed with a class and did
    not refuse a class that clashed with an external booking, so a timetable
    edit could take a room out from under the system holding it, silently.
    Both directions are the same rule now.

    A slot in a closed cycle is not checked, because it does not occupy the
    room: booked_slots counts open cycles only, and a booking is already
    accepted on top of a closed cycle's slot. Checking here would make the
    two directions disagree the other way round.

    The body is the one POST /resources/{id}/reservations sends when it
    refuses, so an integrator reads a clash the same way whichever end it
    came from.
    """
    if cycle is None or not cycle.operational_status:
        return
    conflicts = held_against_slot(db, resource_id, rule, dtstart, start, end, cycle=cycle)
    if conflicts:
        raise ChronosError(
            status_code=409,
            detail=jsonable_encoder({"message": ROOM_IS_HELD, "conflicts": conflicts}),
            code=ErrorCode.RESOURCE_CONFLICT,
        )


def _refuse_if_scheduled(
    db, cycle, resource_id, rule, dtstart, start, end, exclude_slot_id=None
) -> None:
    """Refuse a slot that would be laid on top of another slot.

    Chronos refused a booking that clashed with a class and a class that
    clashed with a booking, and let one class be put straight on top of
    another. A room could hold two timetables at once and nothing said so:
    both slots generated a ledger row every week, both rows named the same
    room, and the first anyone knew was two groups at one door.

    Gated exactly as the hold check is, on the slot's own cycle being open,
    so the two checks agree on which slots occupy a room. A slot in a closed
    cycle does not occupy anything: booked_slots counts open cycles only.

    Raised separately from the hold check rather than merged with it, so the
    message and the contract of each stay what they were. A window that
    clashes with both a booking and a class is refused twice, once for each,
    which is the rarer case and costs a second attempt.
    """
    if cycle is None or not cycle.operational_status:
        return
    conflicts = slots_against_slot(
        db, resource_id, rule, dtstart, start, end, exclude_slot_id, cycle=cycle
    )
    if conflicts:
        raise ChronosError(
            status_code=409,
            detail=jsonable_encoder({"message": ROOM_IS_SCHEDULED, "conflicts": conflicts}),
            code=ErrorCode.RESOURCE_CONFLICT,
        )


def _refuse_if_a_day_is_there(
    db, cycle, resource_id, rule, dtstart, start, end, exclude_slot_id=None
) -> None:
    """Refuse a slot that would be laid on top of a day already generated.

    The two checks above read the timetable and the bookings. A generated day
    is neither, and it is the row that puts somebody at a door, so a day left
    behind by a slot nobody can see any more holds a room that both of those
    checks report as free.

    There are two ways to get one. Closing a cycle keeps the days ahead that
    carry attendance or a note, and the checks above skip a closed cycle on
    purpose. Deleting a slot withdraws its future days unless attendance has
    been marked on them, and a day that has been marked stays.

    The days are not gated by cycle, for the same reason: a day is in the
    table whatever its cycle now says, and ex_daily_ledger_no_overlap will
    refuse a second row on top of it whatever anybody thinks about the cycle.
    A check that disagreed with the constraint would turn a refusal into a
    500. cycle is
    the new slot's own, and only limits the dates it will run on; whether it
    is open does not matter here.

    Asked twice on the edit path, once before writing and once if the database
    refuses the write anyway. Two admins moving two classes onto one room at
    the same moment both pass the first ask, and the loser has to be told what
    beat it rather than handed a stack trace.
    """
    conflicts = days_against_slot(
        db, resource_id, rule, dtstart, start, end, exclude_slot_id, cycle=cycle
    )
    if conflicts:
        raise ChronosError(
            status_code=409,
            detail=jsonable_encoder({"message": ROOM_HAS_A_DAY, "conflicts": conflicts}),
            code=ErrorCode.RESOURCE_CONFLICT,
        )


# ── Planning Cycles ──────────────────────────────────────────────────────────


@router.get(
    "/cycles", operation_id="schedule.listCycles", response_model=list[PlanningCycleResponse]
)
def list_cycles(
    page: Page = Depends(),
    db: Session = Depends(get_db),
    _=Depends(get_current_user),
):
    return page.rows(db.query(PlanningCycle), PlanningCycle.id)


@router.post("/cycles", operation_id="schedule.createCycle", response_model=PlanningCycleResponse)
def create_cycle(
    payload: PlanningCycleCreate,
    db: Session = Depends(get_db),
    _=Depends(require_roles("ORG_ADMIN")),
):
    cycle = PlanningCycle(**payload.model_dump())
    db.add(cycle)
    db.commit()
    db.refresh(cycle)
    return cycle


@router.patch("/cycles/{cycle_id}/close", operation_id="schedule.closeCycle")
def close_cycle(
    cycle_id: int, db: Session = Depends(get_db), _=Depends(require_roles("ORG_ADMIN"))
):
    """Take a cycle out of service, and the days it had planned ahead with it.

    Closing only flipped the flag. The generator stopped writing new days,
    but every day it had already written from today onward stayed in the
    table naming a room and an hour, so a room a finished term had given up
    read as taken to every check and every booking until those dates passed.

    The days from today onward that are still only plans are removed, the
    same days a slot delete removes. What differs is a day somebody has
    already marked or written a note on. A slot delete refuses over one,
    because it would leave a class the timetable no longer has. Closing keeps
    it and says how many it kept: a cycle is closed at the end of a term,
    and refusing over the register taken on its last morning would leave the
    admin nothing to do but wait for tomorrow.

    Days before today are records and are neither touched nor counted.
    Closing a cycle that is already closed runs the same sweep, which is how
    the days left behind by a close from before this change are cleared.
    """
    cycle = db.query(PlanningCycle).filter(PlanningCycle.id == cycle_id).first()
    if not cycle:
        raise ChronosError(status_code=404, detail="Cycle not found", code=ErrorCode.NOT_FOUND)
    cycle.operational_status = False

    ahead = (
        db.query(DailyLedger)
        .join(Activity, DailyLedger.activity_id == Activity.id)
        .filter(Activity.cycle_id == cycle_id, DailyLedger.target_date >= org_today())
        .all()
    )
    kept = rows_in_use([row.id for row in ahead], db)
    for row in ahead:
        if row.id not in kept:
            db.delete(row)
    db.commit()
    return {
        "message": f"Cycle {cycle_id} closed",
        "ledger_rows_removed": len(ahead) - len(kept),
        "ledger_rows_kept": len(kept),
    }


@router.patch(
    "/cycles/{cycle_id}/open",
    operation_id="schedule.openCycle",
    responses={409: {"model": CycleActivationConflict}},
)
def open_cycle(cycle_id: int, db: Session = Depends(get_db), _=Depends(require_roles("ORG_ADMIN"))):
    """Put a drafted cycle into service, with its slots checked first.

    Nothing set this flag back to true. A cycle could be closed and never
    reopened, and a cycle created closed could never be opened at all, so a
    schedule had to be right at the moment it was typed in. That is fine for
    a term that is planned once and runs, and wrong for a ward that fills up
    a rota over a fortnight: draft it closed, correct it as often as you
    like, commit it when it is ready.

    Drafting closed is exactly why this cannot be a flag flip. A slot
    entered into a closed cycle is not checked against the bookings or
    against the rest of the timetable, because a closed cycle's slots
    occupy nothing: booked_slots counts open cycles only. Every one of those
    unchecked slots starts occupying its room the moment this flag goes
    true, and from that night the generator lays days for all of them. So
    the checks POST /slots would have run, had the cycle been open, run here
    instead, over every slot at once.

    The flag is written and flushed before the checks rather than after,
    which is what lets the cycle's own slots be checked against each other.
    Two slots drafted into one room at one hour are the likeliest mistake in
    a cycle built up over a fortnight, and neither was ever refused. With
    the flag flushed, booked_slots sees them, so they find each other
    through the same query the write path uses and the two cannot disagree.
    A clashing pair is named twice, once from each side, because there is no
    honest way to pick which of the two is the one at fault.

    Writing before checking means the refusal has to roll back, and it is
    the only refusal in this file that does. Everything else asks before it
    writes.

    Every conflict across every slot is collected and raised once. The
    per-slot refusals raise on the first thing they find, which costs a
    second attempt in the rare case something clashes with two rules at
    once; an admin opening a hundred slots should not have to make a hundred
    attempts to see a list they could have been handed.
    """
    cycle = db.query(PlanningCycle).filter(PlanningCycle.id == cycle_id).first()
    if not cycle:
        raise ChronosError(status_code=404, detail="Cycle not found", code=ErrorCode.NOT_FOUND)
    if cycle.operational_status:
        # Its slots were checked as they landed, so there is nothing to ask.
        return {"message": f"Cycle {cycle_id} was already open"}

    slots = (
        db.query(StructuralMasterSlot)
        .join(Activity, StructuralMasterSlot.activity_id == Activity.id)
        .filter(
            Activity.cycle_id == cycle_id,
            StructuralMasterSlot.retired_at.is_(None),
            Activity.retired_at.is_(None),
        )
        .order_by(StructuralMasterSlot.id)
        .all()
    )
    cycle.operational_status = True
    db.flush()

    conflicts: list[dict] = []
    for slot in slots:
        # A slot with no resource takes nothing from anybody. The importer
        # can leave one that way when a room name does not resolve.
        if slot.resource_id is None:
            continue
        window = (slot.rrule, slot.dtstart, slot.time_window_start, slot.time_window_end)
        found = (
            held_against_slot(db, slot.resource_id, *window, cycle=cycle)
            + slots_against_slot(
                db, slot.resource_id, *window, exclude_slot_id=slot.id, cycle=cycle
            )
            + days_against_slot(db, slot.resource_id, *window, exclude_slot_id=slot.id, cycle=cycle)
        )
        conflicts.extend({**clash, "blocked_slot_id": slot.id} for clash in found)

    if conflicts:
        db.rollback()
        raise ChronosError(
            status_code=409,
            detail=jsonable_encoder({"message": CYCLE_IS_BLOCKED, "conflicts": conflicts}),
            code=ErrorCode.RESOURCE_CONFLICT,
        )

    db.commit()
    return {"message": f"Cycle {cycle_id} opened"}


@router.post("/cycles/{old_id}/clone-to/{new_id}", operation_id="schedule.cloneCycle")
def clone_cycle_offerings(
    old_id: int,
    new_id: int,
    db: Session = Depends(get_db),
    _=Depends(require_roles("ORG_ADMIN")),
):
    """Copy one cycle's activities and weekly slots into another.

    It copied the activities and nothing else, so a cloned cycle had no
    timetable and the documented rollover left an admin an empty week to type
    in again. The slots come across now, each pointed at its activity's copy
    with the same lead, room and window. Enrollments do not: the next cycle's
    groups come from the next import. Retired activities and retired slots are
    left behind.

    The target has to be closed and empty. Closed, because the copied slots
    are not checked against the rooms here. Opening a cycle runs every check
    a slot is put through, over all of its slots at once, so a clone into a
    closed cycle followed by an open is the same two steps as drafting one by
    hand, and the checks are not written twice. Empty, because copying into
    a cycle that already has activities would stop halfway on the unique key
    on activity code and cycle, or double a timetable somebody had started.
    """
    found = db.query(PlanningCycle).filter(PlanningCycle.id.in_([old_id, new_id])).all()
    cycles = {cycle.id: cycle for cycle in found}
    if old_id not in cycles or new_id not in cycles:
        raise ChronosError(status_code=404, detail="Cycle not found", code=ErrorCode.NOT_FOUND)
    if cycles[new_id].operational_status:
        raise ChronosError(
            status_code=409,
            detail=(
                f"Cycle {new_id} is open. Clone into a closed cycle and open it "
                "afterwards: opening is what checks the copied slots against the rooms"
            ),
            code=ErrorCode.STATE_CONFLICT,
        )
    if db.query(Activity).filter(Activity.cycle_id == new_id).first():
        raise ChronosError(
            status_code=409,
            detail=f"Cycle {new_id} already has activities. Clone into an empty cycle",
            code=ErrorCode.STATE_CONFLICT,
        )

    old_offerings = (
        db.query(Activity)
        .filter(Activity.cycle_id == old_id, Activity.retired_at.is_(None))
        .order_by(Activity.id)
        .all()
    )
    cloned_slots = 0
    for offering in old_offerings:
        new = Activity(
            activity_code=offering.activity_code,
            activity_title=offering.activity_title,
            unit_code=offering.unit_code,
            cycle_id=new_id,
        )
        db.add(new)
        db.flush()
        for slot in offering.master_slots:
            if slot.retired_at is not None:
                continue
            # The rule comes across as it is and starts again from the new
            # cycle's first date, so a weekly class runs from the first week of
            # the new cycle and not from the date it began in the old one.
            db.add(
                StructuralMasterSlot(
                    rrule=slot.rrule,
                    dtstart=recurrence.first_occurrence(
                        slot.rrule, cycles[new_id].date_bounds_start
                    )
                    or slot.dtstart,
                    time_window_start=slot.time_window_start,
                    time_window_end=slot.time_window_end,
                    activity_id=new.id,
                    primary_lead_id=slot.primary_lead_id,
                    resource_id=slot.resource_id,
                    target_room_identifier=slot.target_room_identifier,
                )
            )
            cloned_slots += 1
    db.commit()
    return {"cloned": len(old_offerings), "cloned_slots": cloned_slots}


# ── Activities ───────────────────────────────────────────────────────────────


def _refuse_if_retired(thing, what: str) -> None:
    """Refuse a write to an activity or a slot that has been retired.

    Retiring is what keeps a finished class's history, so a retired one is
    read but not changed. A slot or an enrollment added to it would produce
    nothing, and a title changed after the fact would rewrite what the days
    it ran were called.
    """
    if thing.retired_at is not None:
        raise ChronosError(
            status_code=409, detail=f"{what} is retired", code=ErrorCode.STATE_CONFLICT
        )


def _fill_horizon(db: Session, cycle_id: int) -> None:
    """Write the days ahead for a cycle, the same way an import does.

    The same function the CSV upload and the nightly job call, so a class
    created here is on the calendar at once and gets exactly the days an
    imported one would. The write before this is committed already, so a
    failure here is logged rather than reported: the nightly job writes the
    same days if this does not.
    """
    try:
        materialize_horizon(db, cycle_id)
    except Exception:
        db.rollback()
        logger.exception("ledger: filling the horizon for cycle %s failed", cycle_id)


def _get_activity(db: Session, activity_id: int) -> Activity:
    activity = db.query(Activity).filter(Activity.id == activity_id).first()
    if not activity:
        raise ChronosError(status_code=404, detail="Activity not found", code=ErrorCode.NOT_FOUND)
    return activity


def _retire_days_ahead(db: Session, rows: list[DailyLedger]) -> tuple[int, int]:
    """Remove the days ahead that are still plans and keep the ones in use.

    The same rule closing a cycle applies: a day from today onward that
    nobody has marked or annotated is removed, and one that has been is kept
    as the record it already is. Returns how many were removed and kept.
    """
    kept = rows_in_use([row.id for row in rows], db)
    for row in rows:
        if row.id not in kept:
            db.delete(row)
    return len(rows) - len(kept), len(kept)


@router.get(
    "/activities", operation_id="schedule.listActivities", response_model=list[ActivityResponse]
)
def list_activities(
    cycle_id: int | None = None,
    include_retired: bool = False,
    page: Page = Depends(),
    db: Session = Depends(get_db),
    _=Depends(get_current_user),
):
    """The activities, without the retired ones unless include_retired is set."""
    q = db.query(Activity)
    if cycle_id:
        q = q.filter(Activity.cycle_id == cycle_id)
    if not include_retired:
        q = q.filter(Activity.retired_at.is_(None))
    return page.rows(q, Activity.id)


@router.get(
    "/activities/{activity_id}",
    operation_id="schedule.getActivity",
    response_model=ActivityResponse,
)
def get_activity(
    activity_id: int,
    db: Session = Depends(get_db),
    _=Depends(get_current_user),
):
    return _get_activity(db, activity_id)


@router.post(
    "/activities",
    operation_id="schedule.createActivity",
    response_model=ActivityResponse,
    status_code=201,
)
def create_activity(
    payload: ActivityCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_roles("ORG_ADMIN", "UNIT_ADMIN")),
):
    """Add an activity to a cycle, the way a CSV row does, without its slots.

    The code is unique within the cycle, retired activities included: a
    retired activity keeps its code, so its history is never confused with a
    new class that happens to reuse it.
    """
    ensure_unit_scope(current_user, payload.unit_code)
    if not db.query(PlanningCycle.id).filter(PlanningCycle.id == payload.cycle_id).first():
        raise ChronosError(status_code=404, detail="Cycle not found", code=ErrorCode.NOT_FOUND)
    taken = (
        db.query(Activity)
        .filter(
            Activity.cycle_id == payload.cycle_id,
            Activity.activity_code == payload.activity_code,
        )
        .first()
    )
    if taken:
        raise ChronosError(
            status_code=409,
            detail=(
                f"Activity '{payload.activity_code}' already exists in cycle "
                f"{payload.cycle_id} as activity {taken.id}"
                + (", retired" if taken.retired_at is not None else "")
            ),
            code=ErrorCode.ALREADY_EXISTS,
        )
    activity = Activity(**payload.model_dump())
    db.add(activity)
    try:
        db.commit()
    except IntegrityError:
        # Another request created the same code between the check and here.
        db.rollback()
        raise ChronosError(
            status_code=409,
            detail=f"Activity '{payload.activity_code}' already exists in cycle {payload.cycle_id}",
            code=ErrorCode.ALREADY_EXISTS,
        ) from None
    db.refresh(activity)
    return activity


@router.patch(
    "/activities/{activity_id}",
    operation_id="schedule.updateActivity",
    response_model=ActivityResponse,
)
def update_activity(
    activity_id: int,
    payload: ActivityUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_roles("ORG_ADMIN", "UNIT_ADMIN")),
):
    activity = _get_activity(db, activity_id)
    ensure_unit_scope(current_user, activity.unit_code)
    _refuse_if_retired(activity, "Activity")
    activity.activity_title = payload.activity_title
    db.commit()
    db.refresh(activity)
    return activity


@router.post(
    "/activities/{activity_id}/retire",
    operation_id="schedule.retireActivity",
    response_model=RetireResult,
)
def retire_activity(
    activity_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_roles("ORG_ADMIN", "UNIT_ADMIN")),
):
    """Take an activity off the timetable and keep everything it has recorded.

    The activity and every slot it still has are marked retired, so the
    generator writes no more days for them and they hold no room. Days from
    today onward that are still plans are removed; days somebody has marked
    or annotated are kept, and days before today are not touched. The
    activity stays readable, and is left out of GET /schedule/activities
    unless include_retired is set.
    """
    activity = _get_activity(db, activity_id)
    ensure_unit_scope(current_user, activity.unit_code)
    _refuse_if_retired(activity, "Activity")
    now = clock.now()
    activity.retired_at = now
    slots_retired = 0
    for slot in activity.master_slots:
        if slot.retired_at is None:
            slot.retired_at = now
            slots_retired += 1
    ahead = (
        db.query(DailyLedger)
        .filter(DailyLedger.activity_id == activity.id, DailyLedger.target_date >= org_today())
        .all()
    )
    removed, kept = _retire_days_ahead(db, ahead)
    db.commit()
    return {
        "retired_at": now,
        "slots_retired": slots_retired,
        "ledger_rows_removed": removed,
        "ledger_rows_kept": kept,
    }


@router.get(
    "/activities/{activity_id}/enrollments",
    operation_id="schedule.listEnrollments",
    response_model=list[EnrollmentResponse],
)
def list_enrollments(
    activity_id: int,
    page: Page = Depends(),
    db: Session = Depends(get_db),
    current_user: User = Depends(require_roles("ORG_ADMIN", "UNIT_ADMIN")),
):
    activity = _get_activity(db, activity_id)
    ensure_unit_scope(current_user, activity.unit_code)
    q = db.query(ActivityEnrollment).filter(ActivityEnrollment.activity_id == activity.id)
    return page.rows(q, ActivityEnrollment.id)


@router.post(
    "/activities/{activity_id}/enrollments",
    operation_id="schedule.createEnrollment",
    response_model=EnrollmentResponse,
    status_code=201,
)
def create_enrollment(
    activity_id: int,
    payload: EnrollmentCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_roles("ORG_ADMIN", "UNIT_ADMIN")),
):
    """Put a member on an activity's roster, as a CSV row does.

    The member has to exist and be active: an import refuses a deactivated
    member for the same reason. Days are per slot, not per member, so this
    writes no days; the member sees the activity's days from now on.
    """
    activity = _get_activity(db, activity_id)
    ensure_unit_scope(current_user, activity.unit_code)
    _refuse_if_retired(activity, "Activity")
    _refuse_unless_active(db, payload.member_id, "Member")
    taken = (
        db.query(ActivityEnrollment.id)
        .filter(
            ActivityEnrollment.activity_id == activity.id,
            ActivityEnrollment.member_id == payload.member_id,
        )
        .first()
    )
    if taken:
        raise ChronosError(
            status_code=409,
            detail=f"Member '{payload.member_id}' is already enrolled",
            code=ErrorCode.ALREADY_EXISTS,
        )
    enrollment = ActivityEnrollment(activity_id=activity.id, member_id=payload.member_id)
    db.add(enrollment)
    try:
        db.commit()
    except IntegrityError:
        db.rollback()
        raise ChronosError(
            status_code=409,
            detail=f"Member '{payload.member_id}' is already enrolled",
            code=ErrorCode.ALREADY_EXISTS,
        ) from None
    db.refresh(enrollment)
    return enrollment


@router.delete(
    "/activities/{activity_id}/enrollments/{member_id}",
    operation_id="schedule.deleteEnrollment",
)
def delete_enrollment(
    activity_id: int,
    member_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_roles("ORG_ADMIN", "UNIT_ADMIN")),
):
    """Take a member off an activity's roster.

    Only the enrollment goes. Days belong to slots, not to members, so no day
    is removed, and the attendance already recorded for the member stays.
    """
    activity = _get_activity(db, activity_id)
    ensure_unit_scope(current_user, activity.unit_code)
    _refuse_if_retired(activity, "Activity")
    enrollment = (
        db.query(ActivityEnrollment)
        .filter(
            ActivityEnrollment.activity_id == activity.id,
            ActivityEnrollment.member_id == member_id,
        )
        .first()
    )
    if not enrollment:
        raise ChronosError(status_code=404, detail="Enrollment not found", code=ErrorCode.NOT_FOUND)
    db.delete(enrollment)
    db.commit()
    return {"activity_id": activity.id, "member_id": member_id, "removed": True}


# ── Master Slots ──────────────────────────────────────────────────────────────


@router.get("/slots", operation_id="schedule.listSlots", response_model=list[dict])
def list_master_slots(
    cycle_id: int | None = None,
    include_retired: bool = False,
    page: Page = Depends(),
    db: Session = Depends(get_db),
    _=Depends(get_current_user),
):
    q = db.query(StructuralMasterSlot)
    if cycle_id:
        q = q.join(Activity).filter(Activity.cycle_id == cycle_id)
    if not include_retired:
        q = q.filter(StructuralMasterSlot.retired_at.is_(None))
    return [
        {
            "id": s.id,
            "rrule": s.rrule,
            "dtstart": s.dtstart.isoformat(),
            # Deprecated: derived from the rule, returned through 0.17.
            "day_of_week_index": s.day_of_week_index,
            "time_window_start": str(s.time_window_start),
            "time_window_end": str(s.time_window_end),
            "activity_id": s.activity_id,
            "primary_lead_id": s.primary_lead_id,
            "resource_id": s.resource_id,
            "target_room_identifier": s.target_room_identifier,
            "retired_at": s.retired_at,
        }
        for s in page.rows(q, StructuralMasterSlot.id)
    ]


def _refuse_unless_active(db: Session, user_id: str, role: str) -> None:
    """Refuse somebody who does not exist or has been deactivated.

    For a person being put in charge of a slot or a day. Left to the foreign
    key, an unknown id is a 500 on PostgreSQL, and a deactivated one would be
    scheduled to run a class they can no longer sign in to.
    """
    found = db.query(User.deactivated_at).filter(User.id == user_id).first()
    if found is None:
        raise ChronosError(status_code=404, detail=f"{role} not found", code=ErrorCode.NOT_FOUND)
    if found[0] is not None:
        raise ChronosError(
            status_code=422, detail=f"{role} is deactivated", code=ErrorCode.USER_DEACTIVATED
        )


@router.post(
    "/slots", operation_id="schedule.createSlot", responses={409: {"model": ReservationConflict}}
)
def create_master_slot(
    payload: MasterSlotCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_roles("ORG_ADMIN", "UNIT_ADMIN")),
):
    offering = db.query(Activity).filter(Activity.id == payload.activity_id).first()
    if not offering:
        raise ChronosError(
            status_code=404, detail="Activity offering not found", code=ErrorCode.NOT_FOUND
        )
    ensure_unit_scope(current_user, offering.unit_code)
    _refuse_if_retired(offering, "Activity")
    if payload.primary_lead_id is not None:
        _refuse_unless_active(db, payload.primary_lead_id, "Lead")
    dtstart = _anchor(payload.rrule, payload.dtstart or offering.cycle.date_bounds_start)
    room = get_or_create_room(payload.target_room_identifier, db)
    _refuse_if_held(
        db,
        offering.cycle,
        room.id,
        payload.rrule,
        dtstart,
        payload.time_window_start,
        payload.time_window_end,
    )
    _refuse_if_scheduled(
        db,
        offering.cycle,
        room.id,
        payload.rrule,
        dtstart,
        payload.time_window_start,
        payload.time_window_end,
    )
    _refuse_if_a_day_is_there(
        db,
        offering.cycle,
        room.id,
        payload.rrule,
        dtstart,
        payload.time_window_start,
        payload.time_window_end,
    )
    # room.code, not the payload: get_or_create_room strips the name, and a
    # slot whose mirror is spelled differently from its resource is exactly
    # the drift the resource table exists to end.
    slot = StructuralMasterSlot(
        **payload.model_dump(exclude={"target_room_identifier", "dtstart"}),
        dtstart=dtstart,
        resource_id=room.id,
        target_room_identifier=room.code,
    )
    db.add(slot)
    db.commit()
    slot_id = slot.id
    _fill_horizon(db, offering.cycle_id)
    return {"id": slot_id}


@router.patch(
    "/slots/{slot_id}",
    operation_id="schedule.updateSlot",
    responses={409: {"model": ReservationConflict}},
)
def update_master_slot(
    slot_id: int,
    payload: MasterSlotUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_roles("ORG_ADMIN", "UNIT_ADMIN")),
):
    """Change a slot, and take the days it has already produced with it.

    Times, lead and room are copied onto the days that are still plans, by
    the same function the importer uses, so a correction typed into the API
    and a correction uploaded as a CSV reach the same rows and skip the same
    ones.

    The times are copied rather than read back through the slot, and the
    filter on future dates is what makes that correct: a class moved to 10:00
    runs at 10:00 from tomorrow, and the days it already ran at 09:00 still
    say 09:00. Reading them off the slot rewrote history instead.

    Changing the rule or its start is the one change that cannot be copied
    across: the days already generated sit on the old dates and there is no
    version of them on the new ones. Those are withdrawn so the generator can
    lay them down again, and the request is refused outright if any of them
    has already been marked.

    A new rule without a dtstart starts again from the cycle's first date,
    as a new slot does. A dtstart is moved forward to the rule's first
    occurrence on or after it.
    """
    slot = db.query(StructuralMasterSlot).filter(StructuralMasterSlot.id == slot_id).first()
    if not slot:
        raise ChronosError(
            status_code=404, detail="Master slot not found", code=ErrorCode.NOT_FOUND
        )
    ensure_unit_scope(current_user, slot.activity.unit_code)
    _refuse_if_retired(slot, "Slot")

    fields = payload.model_dump(exclude_unset=True)
    if fields.get("primary_lead_id") is not None:
        _refuse_unless_active(db, fields["primary_lead_id"], "Lead")
    start = fields.get("time_window_start", slot.time_window_start)
    end = fields.get("time_window_end", slot.time_window_end)
    if end == start:
        raise ChronosError(
            status_code=422,
            detail="time_window_end must not equal time_window_start",
            code=ErrorCode.INVALID_VALUE,
        )

    rule = fields.get("rrule", slot.rrule)
    dtstart = slot.dtstart
    # The same rule sent back without a dtstart is not a new rule, and keeps
    # the start it has.
    if rule != slot.rrule or "dtstart" in fields:
        dtstart = _anchor(rule, fields.get("dtstart") or slot.activity.cycle.date_bounds_start)
        fields["rrule"], fields["dtstart"] = rule, dtstart

    # The room is resolved and the holds are checked before anything is
    # withdrawn or written, so a refusal leaves the slot and the days it has
    # already produced exactly as they were. Nothing is committed on this
    # path, so a room created on the way to a refusal never lands.
    moving_to = None
    if "target_room_identifier" in fields:
        moving_to = get_or_create_room(fields.pop("target_room_identifier"), db)
    resource_id = moving_to.id if moving_to else slot.resource_id
    if (resource_id, rule, dtstart, start, end) != (
        slot.resource_id,
        slot.rrule,
        slot.dtstart,
        slot.time_window_start,
        slot.time_window_end,
    ):
        # Only when the change would actually move the class. A hold sitting
        # on a slot's own window predates this rule or was written straight
        # into the database, and either way changing that slot's lead must
        # not be refused over it: there would be no way to fix the lead
        # short of cancelling somebody else's booking. The same guard the
        # CSV importer uses, for the same reason.
        cycle = slot.activity.cycle
        _refuse_if_held(db, cycle, resource_id, rule, dtstart, start, end)
        _refuse_if_scheduled(db, cycle, resource_id, rule, dtstart, start, end, slot.id)
        _refuse_if_a_day_is_there(db, cycle, resource_id, rule, dtstart, start, end, slot.id)

    removed = 0
    if (rule, dtstart) != (slot.rrule, slot.dtstart):
        removed = withdraw_planned_days(slot, db, "given another rule or start")

    if moving_to is not None:
        slot.resource_id = moving_to.id
        slot.target_room_identifier = moving_to.code
    for field, value in fields.items():
        setattr(slot, field, value)

    result = propagate_slot_corrections([slot], db)
    try:
        db.commit()
    except IntegrityError:
        # The correction is copied onto every day this slot has still to run,
        # and the database holds one room to one window per day. Somebody
        # else's edit landing between the check above and this commit is how
        # that gets refused here, and the rollback is what makes the second
        # ask possible: the session is unusable until it happens.
        #
        # No cycle this time. A day generated before the cycle's dates were
        # honored can sit outside them and still be moved, and a refusal
        # over it has to come back as a 409 and not a 500.
        db.rollback()
        _refuse_if_a_day_is_there(db, None, resource_id, rule, dtstart, start, end, slot_id)
        raise
    return {**result, "ledger_rows_removed": removed}


@router.delete("/slots/{slot_id}", operation_id="schedule.deleteSlot")
def delete_master_slot(
    slot_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_roles("ORG_ADMIN", "UNIT_ADMIN")),
):
    """Take a slot off the timetable without taking its history with it.

    A class that ran for six weeks and then stopped is the ordinary reason
    to call this, so the six weeks have to survive it. Days from today
    onward are still only plans and are removed; days already past keep
    everything recorded on them and are left with no slot to point at.

    Everything includes the hour they ran at, now that a day carries its own
    window. Before that the window lived only on the slot, so deleting one
    turned every day it had already produced into a day nobody could say the
    time of, on a calendar feed and in the API alike.
    """
    slot = db.query(StructuralMasterSlot).filter(StructuralMasterSlot.id == slot_id).first()
    if not slot:
        raise ChronosError(
            status_code=404, detail="Master slot not found", code=ErrorCode.NOT_FOUND
        )
    ensure_unit_scope(current_user, slot.activity.unit_code)
    _refuse_if_retired(slot, "Slot")

    removed, detached = delete_slot(slot, db)
    db.commit()
    return {"ledger_rows_removed": removed, "ledger_rows_detached": detached}


@router.post(
    "/slots/{slot_id}/retire",
    operation_id="schedule.retireSlot",
    response_model=RetireResult,
)
def retire_master_slot(
    slot_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_roles("ORG_ADMIN", "UNIT_ADMIN")),
):
    """Take a slot off the timetable and keep everything it has recorded.

    Where DELETE refuses while a day ahead carries attendance or a note,
    this keeps that day and removes the rest. The slot stays, marked retired,
    so the generator writes no more days for it and it holds no room.
    """
    slot = db.query(StructuralMasterSlot).filter(StructuralMasterSlot.id == slot_id).first()
    if not slot:
        raise ChronosError(
            status_code=404, detail="Master slot not found", code=ErrorCode.NOT_FOUND
        )
    ensure_unit_scope(current_user, slot.activity.unit_code)
    _refuse_if_retired(slot, "Slot")
    now = clock.now()
    slot.retired_at = now
    ahead = (
        db.query(DailyLedger)
        .filter(DailyLedger.master_slot_id == slot.id, DailyLedger.target_date >= org_today())
        .all()
    )
    removed, kept = _retire_days_ahead(db, ahead)
    db.commit()
    return {
        "retired_at": now,
        "slots_retired": 1,
        "ledger_rows_removed": removed,
        "ledger_rows_kept": kept,
    }


# ── Daily Ledger ──────────────────────────────────────────────────────────────


def _visible_ledger(db: Session, current_user: User, q):
    """q narrowed to the rows this user may see.

    Staff see the days they lead or cover, members the activities they are
    enrolled in, and everyone else every row. Shared by today's ledger and the
    range, so the two can never disagree about who sees what.
    """
    if current_user.role_type.value == "STAFF":
        q = q.filter(
            (DailyLedger.active_lead_id == current_user.id)
            | (DailyLedger.substitute_lead_id == current_user.id)
        )
    elif current_user.role_type.value == "MEMBER":
        from app.models.db import ActivityEnrollment

        registered_ids = [
            r.activity_id
            for r in db.query(ActivityEnrollment)
            .filter(ActivityEnrollment.member_id == current_user.id)
            .all()
        ]
        q = q.filter(DailyLedger.activity_id.in_(registered_ids))
    return q


def _ledger_row(e: DailyLedger) -> dict:
    offering = e.activity
    return {
        "id": e.id,
        "target_date": str(e.target_date),
        "activity_code": offering.activity_code if offering else None,
        "activity_title": offering.activity_title if offering else None,
        "resource_id": e.resource_id,
        "target_room_identifier": e.target_room_identifier,
        # The day's own window. It used to be read back off the slot,
        # so a class taken off the timetable made every day it had
        # already run report no time at all, and moving a class to a
        # different hour moved the days it had already run with it.
        "time_window_start": str(e.time_window_start) if e.time_window_start else None,
        "time_window_end": str(e.time_window_end) if e.time_window_end else None,
        "delivery_format": e.delivery_format.value,
        "virtual_connection_string": e.virtual_connection_string,
        "operational_state": e.operational_state.value,
        "active_lead_id": e.active_lead_id,
        "substitute_lead_id": e.substitute_lead_id,
        "latitude_target": float(e.latitude_target) if e.latitude_target else None,
        "longitude_target": float(e.longitude_target) if e.longitude_target else None,
        "altitude_target": float(e.altitude_target) if e.altitude_target else None,
        "precision_radius_meters": e.precision_radius_meters,
    }


@router.get("/ledger/today", operation_id="schedule.getTodayLedger")
def get_today_ledger(
    page: Page = Depends(),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    today = org_today()
    q = db.query(DailyLedger).filter(DailyLedger.target_date == today)
    q = _visible_ledger(db, current_user, q)
    return [_ledger_row(e) for e in page.rows(q, DailyLedger.id)]


@router.get("/ledger", operation_id="schedule.listLedger")
def get_ledger_range(
    from_: datetime.date = Query(alias="from"),
    to: datetime.date = Query(),
    resource_id: int | None = None,
    page: Page = Depends(),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """The ledger between two dates inclusive, in date and start time order.

    Rows have the shape /ledger/today returns and are filtered by role the
    same way, so a client reading one day and a client reading a month parse
    the same thing.
    """
    if to < from_:
        raise ChronosError(
            status_code=422, detail="to is before from", code=ErrorCode.INVALID_VALUE
        )
    q = db.query(DailyLedger).filter(
        DailyLedger.target_date >= from_, DailyLedger.target_date <= to
    )
    if resource_id is not None:
        q = q.filter(DailyLedger.resource_id == resource_id)
    q = _visible_ledger(db, current_user, q)
    keys = (DailyLedger.target_date, DailyLedger.time_window_start, DailyLedger.id)
    return [_ledger_row(e) for e in page.rows(q, *keys)]


@router.get("/conflicts", operation_id="schedule.listConflicts", response_model=ConflictReport)
def get_conflict_report(
    from_: datetime.date = Query(alias="from"),
    to: datetime.date = Query(),
    db: Session = Depends(get_db),
    _=Depends(require_roles("ORG_ADMIN", "UNIT_ADMIN")),
):
    """Every clash already in the schedule between two dates inclusive.

    Two rows holding one resource at once, and one member enrolled in two
    activities that run at once. It reads and reports; nothing is refused
    and nothing is changed. app.services.conflicts says what counts.

    Admins only, because these are the callers _visible_ledger shows every
    row to. The report is only true when it is read over the whole schedule,
    and the member side names who is enrolled where, which a member or a
    member of staff is not shown for anybody but themselves.
    """
    if from_ > to:
        raise ChronosError(
            status_code=422, detail=CONFLICT_RANGE_BACKWARDS, code=ErrorCode.INVALID_VALUE
        )
    if (to - from_).days + 1 > MAX_CONFLICT_RANGE_DAYS:
        raise ChronosError(
            status_code=422, detail=CONFLICT_RANGE_TOO_LONG, code=ErrorCode.INVALID_VALUE
        )
    return {"from": from_, "to": to, "conflicts": find_conflicts(db, from_, to)}


@router.patch("/ledger/{ledger_id}", operation_id="schedule.updateLedgerEntry")
def update_ledger_entry(
    ledger_id: int,
    payload: DailyLedgerUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_roles("ORG_ADMIN", "UNIT_ADMIN")),
):
    entry = db.query(DailyLedger).filter(DailyLedger.id == ledger_id).first()
    if not entry:
        raise ChronosError(
            status_code=404, detail="Ledger entry not found", code=ErrorCode.NOT_FOUND
        )
    ensure_unit_scope(current_user, entry.activity.unit_code)
    if payload.substitute_lead_id is not None:
        _refuse_unless_active(db, payload.substitute_lead_id, "Substitute")
    # Named rather than taken from model_dump: the unit check above holds only
    # while the day stays on its activity, so a field added to DailyLedgerUpdate
    # later has to be listed here before it is written.
    for field in (
        "operational_state",
        "substitute_lead_id",
        "delivery_format",
        "virtual_connection_string",
        "latitude_target",
        "longitude_target",
        "altitude_target",
        "precision_radius_meters",
    ):
        # Left out keeps the value, a null clears it.
        if field in payload.model_fields_set:
            setattr(entry, field, getattr(payload, field))
    db.commit()
    return {"message": "Updated"}


# ── Staff Location Resolution ───────────────────────────────────────────────


@router.get(
    "/staff/{staff_id}/location",
    operation_id="schedule.getStaffLocation",
    response_model=StaffLocationResponse,
)
def get_staff_location(
    staff_id: str,
    db: Session = Depends(get_db),
    _=Depends(get_current_user),
):
    staff = db.query(User).filter(User.id == staff_id).first()
    if not staff or staff.deactivated_at is not None:
        raise ChronosError(status_code=404, detail="Staff not found", code=ErrorCode.NOT_FOUND)

    redis = get_redis()
    result = determine_staff_current_states([staff], db, redis)[staff.id]
    return StaffLocationResponse(
        staff_id=staff_id,
        full_name=staff.full_name,
        occupancy_index=staff.current_occupancy_index.value,
        **result,
    )


@router.get("/staff/all/locations", operation_id="schedule.listStaffLocations")
def get_all_staff_locations(
    page: Page = Depends(),
    db: Session = Depends(get_db),
    _=Depends(get_current_user),
):
    from app.models.db import InstitutionalRole

    q = db.query(User).filter(
        User.role_type == InstitutionalRole.STAFF, User.deactivated_at.is_(None)
    )
    # Paged before resolving, so only the people on this page are looked up.
    staff_list = page.rows(q, User.id)
    redis = get_redis()
    locations = determine_staff_current_states(staff_list, db, redis)
    results = []
    for f in staff_list:
        location = locations[f.id]
        results.append(
            {
                "staff_id": f.id,
                "full_name": f.full_name,
                "unit_code": f.unit_code,
                "occupancy_index": f.current_occupancy_index.value,
                **location,
            }
        )
    return results
