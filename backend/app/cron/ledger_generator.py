# Copyright 2026 Chronos Ledger Contributors
# Licensed under the Apache License, Version 2.0

"""Turning the weekly timetable into the dated rows people actually work off.

A slot says a class runs on Mondays at nine. A ledger row says it runs on the
sixteenth of March at nine, in this room, with this lead, and is the row
attendance is marked against. This is the only thing that writes those rows.

Two slots can be on one room at one hour despite every check in the API, so
this has to survive finding out. Migration 013 puts an exclusion constraint on
daily_ledger, which means the second insert on a taken window is refused by
the database rather than accepted. Without a savepoint around each insert the
refusal would poison the whole transaction and the night's other classes would
be lost with it, so each row gets its own and a refused one is skipped.

Skipped is not the same as silent. Nothing else in the system would ever
mention the day that did not get written, so it is logged, with the slot that
lost, the day it lost, the room, and the days that were already there.
"""

import datetime
import logging

from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.models.db import (
    Activity,
    DailyLedger,
    DynamicState,
    LogVerificationState,
    PlanningCycle,
    ReverseRsvpLog,
    StructuralMasterSlot,
)
from app.services.availability import days_against_window

logger = logging.getLogger(__name__)


def generate_daily_ledger_entries(target_date: datetime.date, db: Session) -> int:
    day_index = target_date.isoweekday()

    slots = (
        db.query(StructuralMasterSlot)
        .join(Activity, StructuralMasterSlot.activity_id == Activity.id)
        .join(PlanningCycle, Activity.cycle_id == PlanningCycle.id)
        .filter(
            StructuralMasterSlot.day_of_week_index == day_index,
            PlanningCycle.operational_status,
        )
        # Oldest slot first, so which of two clashing classes keeps the room
        # is decided by which was put on the timetable first and not by the
        # order the database felt like returning them in. Rerunning a night
        # then produces the same answer it did the first time.
        .order_by(StructuralMasterSlot.id)
        .all()
    )

    created = 0
    for slot in slots:
        # Check for approved leave on this date for this lead
        leave = (
            db.query(ReverseRsvpLog)
            .filter(
                ReverseRsvpLog.submitting_user_id == slot.primary_lead_id,
                ReverseRsvpLog.target_absence_date == target_date,
                ReverseRsvpLog.approval_state == LogVerificationState.VERIFIED_APPROVED,
            )
            .first()
        )
        initial_state = DynamicState.ON_LEAVE if leave else DynamicState.SCHEDULED

        # Skip if already exists for this slot + date
        existing = (
            db.query(DailyLedger)
            .filter(DailyLedger.master_slot_id == slot.id, DailyLedger.target_date == target_date)
            .first()
        )
        if existing:
            continue

        entry = DailyLedger(
            target_date=target_date,
            # Copied, not pointed at. The slot may be edited or deleted after
            # today has been generated, and neither should reach back and
            # change what time a day that has already happened ran at.
            time_window_start=slot.time_window_start,
            time_window_end=slot.time_window_end,
            master_slot_id=slot.id,
            activity_id=slot.activity_id,
            active_lead_id=slot.primary_lead_id,
            resource_id=slot.resource_id,
            target_room_identifier=slot.target_room_identifier,
            operational_state=initial_state,
        )
        try:
            # The flush is inside the savepoint on purpose: it is the flush
            # that sends the INSERT, so a flush outside would be refused with
            # nothing left to roll back to.
            #
            # This is also what closes the gap between the query above and the
            # insert. Two runs of this job against one database both find no
            # existing row and both insert; the second is now refused here
            # instead of quietly doubling every day of the week.
            with db.begin_nested():
                db.add(entry)
                db.flush()
        except IntegrityError:
            # Nothing to expunge: rolling the savepoint back has already taken
            # the pending row out of the session, and asking for it again
            # raises rather than being a harmless no-op.
            taken = days_against_window(
                db,
                slot.resource_id,
                target_date,
                slot.time_window_start,
                slot.time_window_end,
                exclude_slot_id=slot.id,
            )
            logger.warning(
                "ledger: no day written for slot %s (%s) on %s in %s, the room is already "
                "taken by %s",
                slot.id,
                slot.activity.activity_code if slot.activity else "unknown activity",
                target_date,
                slot.target_room_identifier or slot.resource_id,
                [(day["master_slot_id"], day["date"], str(day["start"])) for day in taken]
                or "a row this query could not find",
            )
            continue
        created += 1

    db.commit()
    return created
