# Copyright 2026 Chronos Ledger Contributors
# Licensed under the Apache License, Version 2.0


from fastapi import APIRouter, Depends, HTTPException
from fastapi.encoders import jsonable_encoder
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.redis_client import get_redis
from app.core.security import ensure_unit_scope, get_current_user, require_roles
from app.core.time import org_today
from app.models.db import Activity, DailyLedger, PlanningCycle, StructuralMasterSlot, User
from app.schemas.resources import ReservationConflict
from app.schemas.schedule import (
    CycleActivationConflict,
    DailyLedgerUpdate,
    MasterSlotCreate,
    MasterSlotUpdate,
    PlanningCycleCreate,
    PlanningCycleResponse,
    StaffLocationResponse,
)
from app.services.availability import (
    days_against_slot,
    held_against_slot,
    slots_against_slot,
)
from app.services.location_resolver import determine_staff_current_state
from app.services.master_slot import propagate_slot_corrections, rows_in_use
from app.services.resource import get_or_create_room

router = APIRouter()

ROOM_IS_HELD = "the resource is held for part of that window"
ROOM_IS_SCHEDULED = "the resource is already on the timetable for part of that window"
ROOM_HAS_A_DAY = "the resource already has a generated day in part of that window"
CYCLE_IS_BLOCKED = "opening this cycle would put its slots on rooms already taken"


def _refuse_if_held(db, cycle, resource_id, weekday, start, end) -> None:
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
    conflicts = held_against_slot(db, resource_id, weekday, start, end, cycle=cycle)
    if conflicts:
        raise HTTPException(
            status_code=409,
            detail=jsonable_encoder({"message": ROOM_IS_HELD, "conflicts": conflicts}),
        )


def _refuse_if_scheduled(db, cycle, resource_id, weekday, start, end, exclude_slot_id=None) -> None:
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
        db, resource_id, weekday, start, end, exclude_slot_id, cycle=cycle
    )
    if conflicts:
        raise HTTPException(
            status_code=409,
            detail=jsonable_encoder({"message": ROOM_IS_SCHEDULED, "conflicts": conflicts}),
        )


def _refuse_if_a_day_is_there(
    db, cycle, resource_id, weekday, start, end, exclude_slot_id=None
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
    table whatever its cycle now says, and migration 013 will refuse a second
    row on top of it whatever anybody thinks about the cycle. A check that
    disagreed with the constraint would turn a refusal into a 500. cycle is
    the new slot's own, and only limits the dates it will run on; whether it
    is open does not matter here.

    Asked twice on the edit path, once before writing and once if the database
    refuses the write anyway. Two admins moving two classes onto one room at
    the same moment both pass the first ask, and the loser has to be told what
    beat it rather than handed a stack trace.
    """
    conflicts = days_against_slot(
        db, resource_id, weekday, start, end, exclude_slot_id, cycle=cycle
    )
    if conflicts:
        raise HTTPException(
            status_code=409,
            detail=jsonable_encoder({"message": ROOM_HAS_A_DAY, "conflicts": conflicts}),
        )


# ── Planning Cycles ──────────────────────────────────────────────────────────


@router.get("/cycles", response_model=list[PlanningCycleResponse])
def list_cycles(db: Session = Depends(get_db), _=Depends(get_current_user)):
    return db.query(PlanningCycle).all()


@router.post("/cycles", response_model=PlanningCycleResponse)
def create_cycle(
    payload: PlanningCycleCreate,
    db: Session = Depends(get_db),
    _=Depends(require_roles("SUPER_ADMIN")),
):
    cycle = PlanningCycle(**payload.model_dump())
    db.add(cycle)
    db.commit()
    db.refresh(cycle)
    return cycle


@router.patch("/cycles/{cycle_id}/close")
def close_cycle(
    cycle_id: int, db: Session = Depends(get_db), _=Depends(require_roles("SUPER_ADMIN"))
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
        raise HTTPException(status_code=404, detail="Cycle not found")
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


@router.patch("/cycles/{cycle_id}/open", responses={409: {"model": CycleActivationConflict}})
def open_cycle(
    cycle_id: int, db: Session = Depends(get_db), _=Depends(require_roles("SUPER_ADMIN"))
):
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
        raise HTTPException(status_code=404, detail="Cycle not found")
    if cycle.operational_status:
        # Its slots were checked as they landed, so there is nothing to ask.
        return {"message": f"Cycle {cycle_id} was already open"}

    slots = (
        db.query(StructuralMasterSlot)
        .join(Activity, StructuralMasterSlot.activity_id == Activity.id)
        .filter(Activity.cycle_id == cycle_id)
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
        window = (slot.day_of_week_index, slot.time_window_start, slot.time_window_end)
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
        raise HTTPException(
            status_code=409,
            detail=jsonable_encoder({"message": CYCLE_IS_BLOCKED, "conflicts": conflicts}),
        )

    db.commit()
    return {"message": f"Cycle {cycle_id} opened"}


@router.post("/cycles/{old_id}/clone-to/{new_id}")
def clone_cycle_offerings(
    old_id: int,
    new_id: int,
    db: Session = Depends(get_db),
    _=Depends(require_roles("SUPER_ADMIN")),
):
    """Copy one cycle's activities and weekly slots into another.

    It copied the activities and nothing else, so a cloned cycle had no
    timetable and the documented rollover left an admin an empty week to type
    in again. The slots come across now, each pointed at its activity's copy
    with the same lead, room and window. Enrollments do not: the next cycle's
    groups come from the next import.

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
        raise HTTPException(status_code=404, detail="Cycle not found")
    if cycles[new_id].operational_status:
        raise HTTPException(
            status_code=409,
            detail=(
                f"Cycle {new_id} is open. Clone into a closed cycle and open it "
                "afterwards: opening is what checks the copied slots against the rooms"
            ),
        )
    if db.query(Activity).filter(Activity.cycle_id == new_id).first():
        raise HTTPException(
            status_code=409,
            detail=f"Cycle {new_id} already has activities. Clone into an empty cycle",
        )

    old_offerings = (
        db.query(Activity).filter(Activity.cycle_id == old_id).order_by(Activity.id).all()
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
            db.add(
                StructuralMasterSlot(
                    day_of_week_index=slot.day_of_week_index,
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


# ── Master Slots ──────────────────────────────────────────────────────────────


@router.get("/slots", response_model=list[dict])
def list_master_slots(
    cycle_id: int | None = None,
    db: Session = Depends(get_db),
    _=Depends(get_current_user),
):
    q = db.query(StructuralMasterSlot)
    if cycle_id:
        q = q.join(Activity).filter(Activity.cycle_id == cycle_id)
    return [
        {
            "id": s.id,
            "day_of_week_index": s.day_of_week_index,
            "time_window_start": str(s.time_window_start),
            "time_window_end": str(s.time_window_end),
            "activity_id": s.activity_id,
            "primary_lead_id": s.primary_lead_id,
            "resource_id": s.resource_id,
            "target_room_identifier": s.target_room_identifier,
        }
        for s in q.all()
    ]


@router.post("/slots", responses={409: {"model": ReservationConflict}})
def create_master_slot(
    payload: MasterSlotCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_roles("SUPER_ADMIN", "UNIT_ADMIN")),
):
    offering = db.query(Activity).filter(Activity.id == payload.activity_id).first()
    if not offering:
        raise HTTPException(status_code=404, detail="Activity offering not found")
    ensure_unit_scope(current_user, offering.unit_code)
    room = get_or_create_room(payload.target_room_identifier, db)
    _refuse_if_held(
        db,
        offering.cycle,
        room.id,
        payload.day_of_week_index,
        payload.time_window_start,
        payload.time_window_end,
    )
    _refuse_if_scheduled(
        db,
        offering.cycle,
        room.id,
        payload.day_of_week_index,
        payload.time_window_start,
        payload.time_window_end,
    )
    _refuse_if_a_day_is_there(
        db,
        offering.cycle,
        room.id,
        payload.day_of_week_index,
        payload.time_window_start,
        payload.time_window_end,
    )
    # room.code, not the payload: get_or_create_room strips the name, and a
    # slot whose mirror is spelled differently from its resource is exactly
    # the drift the resource table exists to end.
    slot = StructuralMasterSlot(
        **payload.model_dump(exclude={"target_room_identifier"}),
        resource_id=room.id,
        target_room_identifier=room.code,
    )
    db.add(slot)
    db.commit()
    db.refresh(slot)
    return {"id": slot.id}


@router.patch("/slots/{slot_id}", responses={409: {"model": ReservationConflict}})
def update_master_slot(
    slot_id: int,
    payload: MasterSlotUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_roles("SUPER_ADMIN", "UNIT_ADMIN")),
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

    Moving the slot to another weekday is the one change that cannot be
    copied across: the days already generated sit on the old weekday and
    there is no version of them on the new one. Those are withdrawn so the
    generator can lay them down again, and the request is refused outright
    if any of them has already been marked.
    """
    slot = db.query(StructuralMasterSlot).filter(StructuralMasterSlot.id == slot_id).first()
    if not slot:
        raise HTTPException(status_code=404, detail="Master slot not found")
    ensure_unit_scope(current_user, slot.activity.unit_code)

    fields = payload.model_dump(exclude_unset=True)
    start = fields.get("time_window_start", slot.time_window_start)
    end = fields.get("time_window_end", slot.time_window_end)
    if end == start:
        raise HTTPException(
            status_code=422,
            detail="time_window_end must not equal time_window_start",
        )

    weekday = fields.get("day_of_week_index", slot.day_of_week_index)

    # The room is resolved and the holds are checked before anything is
    # withdrawn or written, so a refusal leaves the slot and the days it has
    # already produced exactly as they were. Nothing is committed on this
    # path, so a room created on the way to a refusal never lands.
    moving_to = None
    if "target_room_identifier" in fields:
        moving_to = get_or_create_room(fields.pop("target_room_identifier"), db)
    resource_id = moving_to.id if moving_to else slot.resource_id
    if (resource_id, weekday, start, end) != (
        slot.resource_id,
        slot.day_of_week_index,
        slot.time_window_start,
        slot.time_window_end,
    ):
        # Only when the change would actually move the class. A hold sitting
        # on a slot's own window predates this rule or was written straight
        # into the database, and either way changing that slot's lead must
        # not be refused over it: there would be no way to fix the lead
        # short of cancelling somebody else's booking. The same guard the
        # CSV importer uses, for the same reason.
        _refuse_if_held(db, slot.activity.cycle, resource_id, weekday, start, end)
        _refuse_if_scheduled(db, slot.activity.cycle, resource_id, weekday, start, end, slot.id)
        _refuse_if_a_day_is_there(
            db, slot.activity.cycle, resource_id, weekday, start, end, slot.id
        )

    removed = 0
    if weekday != slot.day_of_week_index:
        removed = _withdraw_planned_days(slot, db, "moved to another weekday")

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
        _refuse_if_a_day_is_there(db, None, resource_id, weekday, start, end, slot_id)
        raise
    return {**result, "ledger_rows_removed": removed}


@router.delete("/slots/{slot_id}")
def delete_master_slot(
    slot_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_roles("SUPER_ADMIN", "UNIT_ADMIN")),
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
        raise HTTPException(status_code=404, detail="Master slot not found")
    ensure_unit_scope(current_user, slot.activity.unit_code)

    detached = (
        db.query(DailyLedger)
        .filter(
            DailyLedger.master_slot_id == slot.id,
            DailyLedger.target_date < org_today(),
        )
        .count()
    )
    removed = _withdraw_planned_days(slot, db, "deleted")
    db.delete(slot)
    db.commit()
    return {"ledger_rows_removed": removed, "ledger_rows_detached": detached}


def _withdraw_planned_days(slot: StructuralMasterSlot, db: Session, why: str) -> int:
    """Remove the days this slot has laid down that have not happened yet.

    Today counts as not yet happened. A day nobody has marked is a plan and
    withdrawing it costs nothing; a day somebody has marked is a record, and
    rather than quietly keep it as a class that no longer exists anywhere in
    the timetable, the whole request is refused and the dates are named.
    """
    planned = (
        db.query(DailyLedger)
        .filter(
            DailyLedger.master_slot_id == slot.id,
            DailyLedger.target_date >= org_today(),
        )
        .all()
    )
    blocked = rows_in_use([row.id for row in planned], db)
    if blocked:
        dates = sorted(str(row.target_date) for row in planned if row.id in blocked)
        raise HTTPException(
            status_code=409,
            detail=(
                f"This slot cannot be {why} while days it has produced carry "
                f"attendance or notes: {', '.join(dates)}"
            ),
        )
    for row in planned:
        db.delete(row)
    return len(planned)


# ── Daily Ledger ──────────────────────────────────────────────────────────────


@router.get("/ledger/today")
def get_today_ledger(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    today = org_today()
    q = db.query(DailyLedger).filter(DailyLedger.target_date == today)

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

    entries = q.all()
    result = []
    for e in entries:
        offering = e.activity
        result.append(
            {
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
        )
    return result


@router.patch("/ledger/{ledger_id}")
def update_ledger_entry(
    ledger_id: int,
    payload: DailyLedgerUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_roles("SUPER_ADMIN", "UNIT_ADMIN")),
):
    entry = db.query(DailyLedger).filter(DailyLedger.id == ledger_id).first()
    if not entry:
        raise HTTPException(status_code=404, detail="Ledger entry not found")
    ensure_unit_scope(current_user, entry.activity.unit_code)
    substitute = payload.substitute_lead_id
    if substitute is not None and not db.query(User.id).filter(User.id == substitute).first():
        raise HTTPException(status_code=404, detail="Substitute not found")
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
        value = getattr(payload, field)
        if value is not None:
            setattr(entry, field, value)
    db.commit()
    return {"message": "Updated"}


# ── Staff Location Resolution ───────────────────────────────────────────────


@router.get("/staff/{staff_id}/location", response_model=StaffLocationResponse)
def get_staff_location(
    staff_id: str,
    db: Session = Depends(get_db),
    _=Depends(get_current_user),
):
    staff = db.query(User).filter(User.id == staff_id).first()
    if not staff:
        raise HTTPException(status_code=404, detail="Staff not found")

    redis = get_redis()
    result = determine_staff_current_state(staff_id, db, redis)
    return StaffLocationResponse(
        staff_id=staff_id,
        full_name=staff.full_name,
        occupancy_index=staff.current_occupancy_index.value,
        **result,
    )


@router.get("/staff/all/locations")
def get_all_staff_locations(db: Session = Depends(get_db), _=Depends(get_current_user)):
    from app.models.db import InstitutionalRole

    staff_list = db.query(User).filter(User.role_type == InstitutionalRole.STAFF).all()
    redis = get_redis()
    results = []
    for f in staff_list:
        location = determine_staff_current_state(f.id, db, redis)
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
