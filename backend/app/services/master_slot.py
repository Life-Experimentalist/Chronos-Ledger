# Copyright 2026 Chronos Ledger Contributors
# Licensed under the Apache License, Version 2.0

"""Keeping already-materialized days in step with a corrected master slot."""

import datetime

from sqlalchemy.orm import Session

from app.models.db import (
    DailyLedger,
    LedgerAnnotation,
    StructuralMasterSlot,
    VerificationLedger,
)


def propagate_slot_corrections(slots: list[StructuralMasterSlot], db: Session) -> dict[str, int]:
    """Copy each slot's lead and room onto the days it has already produced.

    A ledger row starts life as a plan and becomes a record the moment
    somebody marks attendance or leaves a note against it. Only rows that
    are still plans get rewritten: future dates, nothing verified, nothing
    annotated. Everything else is counted and handed back, so the caller can
    say what it left alone instead of silently diverging from the timetable.

    Room and lead are safe to overwrite here because nothing else writes
    them. DailyLedgerUpdate exposes neither, so a row that disagrees with
    its slot disagrees only because the slot moved on after materialization.
    """
    if not slots:
        return {"ledger_rows_updated": 0, "ledger_rows_kept": 0}

    by_id = {slot.id: slot for slot in slots}
    rows = (
        db.query(DailyLedger)
        .filter(
            DailyLedger.master_slot_id.in_(by_id),
            DailyLedger.target_date > datetime.date.today(),
        )
        .all()
    )
    if not rows:
        return {"ledger_rows_updated": 0, "ledger_rows_kept": 0}

    row_ids = [row.id for row in rows]
    in_use = {
        r[0]
        for r in db.query(VerificationLedger.ledger_instance_id)
        .filter(VerificationLedger.ledger_instance_id.in_(row_ids))
        .distinct()
    }
    in_use.update(
        r[0]
        for r in db.query(LedgerAnnotation.ledger_instance_id)
        .filter(LedgerAnnotation.ledger_instance_id.in_(row_ids))
        .distinct()
    )

    updated = 0
    for row in rows:
        if row.id in in_use:
            continue
        slot = by_id[row.master_slot_id]
        if row.target_room_identifier != slot.target_room_identifier:
            # The geofence was pinned to the old room. Leaving it would fence
            # members out of the room they have just been told to go to, so it
            # is cleared for an admin to set again. A cleared fence shows up in
            # the count returned; a fence around the wrong building would not.
            row.latitude_target = None
            row.longitude_target = None
            row.altitude_target = None
        row.target_room_identifier = slot.target_room_identifier
        row.active_lead_id = slot.primary_lead_id
        updated += 1

    return {"ledger_rows_updated": updated, "ledger_rows_kept": len(rows) - updated}
