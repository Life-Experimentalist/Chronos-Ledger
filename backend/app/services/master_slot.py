# Copyright 2026 Chronos Ledger Contributors
# Licensed under the Apache License, Version 2.0

"""Keeping already-materialized days in step with a corrected master slot."""

from sqlalchemy.orm import Session

from app.core.errors import ChronosError, ErrorCode
from app.core.time import org_today
from app.models.db import (
    DailyLedger,
    LedgerAnnotation,
    StructuralMasterSlot,
    VerificationLedger,
)


def rows_in_use(row_ids: list[int], db: Session) -> set[int]:
    """Which of these ledger rows have stopped being only a plan.

    A row is a plan until somebody marks attendance against it or writes a
    note on it. After that it is a record of a day that happened, and the
    two things that may not touch it are a correction rewriting it and a
    slot delete removing it. Both ask this function so they cannot drift
    apart on what counts.
    """
    if not row_ids:
        return set()
    used = {
        r[0]
        for r in db.query(VerificationLedger.ledger_instance_id)
        .filter(VerificationLedger.ledger_instance_id.in_(row_ids))
        .distinct()
    }
    used.update(
        r[0]
        for r in db.query(LedgerAnnotation.ledger_instance_id)
        .filter(LedgerAnnotation.ledger_instance_id.in_(row_ids))
        .distinct()
    )
    return used


def propagate_slot_corrections(
    slots: list[StructuralMasterSlot], db: Session, kept: list[DailyLedger] | None = None
) -> dict[str, int]:
    """Copy each slot's lead and room onto the days it has already produced.

    A ledger row starts life as a plan and becomes a record the moment
    somebody marks attendance or leaves a note against it. Only rows that
    are still plans get rewritten: future dates, nothing verified, nothing
    annotated. Everything else is counted and handed back, so the caller can
    say what it left alone instead of silently diverging from the timetable.

    Room, lead and window are safe to overwrite here because nothing else
    writes them. DailyLedgerUpdate exposes none of them, so a row that
    disagrees with its slot disagrees only because the slot moved on after
    materialization.

    The window is copied for the same reason as the room, and the date filter
    is what makes it correct: only days that have not happened yet are moved.
    A class rescheduled to 10:00 runs at 10:00 from tomorrow, and the days it
    already ran at 09:00 keep saying 09:00. Before the ledger carried its own
    window there was no way to have both.

    The room comparison is on resource_id, not on the room's name: renaming
    a room is one row in resources and must not read as every day of every
    class having moved.

    kept, when given, gets the rows left alone appended to it, for a caller
    that has to say which days they were and not only how many.
    """
    if not slots:
        return {"ledger_rows_updated": 0, "ledger_rows_kept": 0}

    by_id = {slot.id: slot for slot in slots}
    rows = (
        db.query(DailyLedger)
        .filter(
            DailyLedger.master_slot_id.in_(by_id),
            DailyLedger.target_date > org_today(),
        )
        .all()
    )
    if not rows:
        return {"ledger_rows_updated": 0, "ledger_rows_kept": 0}

    in_use = rows_in_use([row.id for row in rows], db)

    updated = 0
    for row in rows:
        if row.id in in_use:
            if kept is not None:
                kept.append(row)
            continue
        slot = by_id[row.master_slot_id]
        if row.resource_id != slot.resource_id:
            # The geofence was pinned to the old room. Leaving it would fence
            # members out of the room they have just been told to go to, so it
            # is cleared for an admin to set again. A cleared fence shows up in
            # the count returned; a fence around the wrong building would not.
            row.latitude_target = None
            row.longitude_target = None
            row.altitude_target = None
        row.resource_id = slot.resource_id
        row.active_lead_id = slot.primary_lead_id
        row.time_window_start = slot.time_window_start
        row.time_window_end = slot.time_window_end
        updated += 1

    return {"ledger_rows_updated": updated, "ledger_rows_kept": len(rows) - updated}


def withdraw_planned_days(slot: StructuralMasterSlot, db: Session, why: str) -> int:
    """Remove the days this slot has laid down that have not happened yet.

    Today counts as not yet happened. A day nobody has marked is a plan and
    withdrawing it costs nothing; a day somebody has marked is a record, and
    rather than quietly keep it as a class that no longer exists anywhere in
    the timetable, the whole request is refused and the dates are named.

    The refusal comes before anything is deleted, so a caller that catches it
    is left with the session as it found it.
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
        raise ChronosError(
            status_code=409,
            detail=(
                f"This slot cannot be {why} while days it has produced carry "
                f"attendance or notes: {', '.join(dates)}"
            ),
            code=ErrorCode.STATE_CONFLICT,
        )
    for row in planned:
        db.delete(row)
    return len(planned)


def delete_slot(slot: StructuralMasterSlot, db: Session) -> tuple[int, int]:
    """Take a slot off the timetable without taking its history with it.

    Days from today onward are plans and are removed; days already past keep
    everything recorded on them and are left with no slot to point at. Returns
    how many days were removed and how many were left behind, and does not
    commit. Refuses, as withdraw_planned_days does, while a day ahead carries
    attendance or a note.
    """
    detached = (
        db.query(DailyLedger)
        .filter(
            DailyLedger.master_slot_id == slot.id,
            DailyLedger.target_date < org_today(),
        )
        .count()
    )
    removed = withdraw_planned_days(slot, db, "deleted")
    db.delete(slot)
    return removed, detached
