# Copyright 2026 Chronos Ledger Contributors
# Licensed under the Apache License, Version 2.0

import datetime

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
            master_slot_id=slot.id,
            activity_id=slot.activity_id,
            active_lead_id=slot.primary_lead_id,
            target_room_identifier=slot.target_room_identifier,
            operational_state=initial_state,
        )
        db.add(entry)
        created += 1

    db.commit()
    return created
