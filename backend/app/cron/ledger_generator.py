# Copyright 2026 Chronos Ledger Contributors
# Licensed under the Apache License, Version 2.0

"""Turning the weekly timetable into the dated rows people actually work off.

A slot says a class runs on Mondays at nine. A ledger row says it runs on the
sixteenth of March at nine, in this room, with this lead, and is the row
attendance is marked against. This is the only thing that writes those rows.

A slot produces a day only while its cycle is open and the date falls inside
the cycle's own dates, both ends included. availability.occupied applies the
same two tests, so what the API reports as taken is what this will write. A
retired slot, or a slot of a retired activity, produces nothing.

generate_daily_ledger_entries writes one date. materialize_horizon writes every
missing date from tomorrow to LEDGER_HORIZON_DAYS ahead, which is what the
nightly job and an import call; it follows the same rules and the same
refusals, but reads the window once instead of asking per slot per day.

Two slots can be on one room at one hour despite every check in the API, a
slot written straight into the database being the plainest way, so this has
to survive finding out. Before a day is written it is checked against the days
already on its room, and one that would sit on another is not written. That
check is what holds the line on SQLite, which has no exclusion constraint.
On PostgreSQL daily_ledger also carries one, which catches the race the check
cannot: two writers that both looked before either wrote. Without a savepoint
around each insert that refusal would poison the whole transaction and the
night's other classes would be lost with it, so each row gets its own and a
refused one is skipped.

Skipped is not the same as silent. Nothing else in the system would ever
mention the day that did not get written, so it is logged, with the slot that
lost, the day it lost, the room, and the days that were already there.
"""

import datetime
import logging

from sqlalchemy import func
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.core import recurrence
from app.core.config import get_settings
from app.core.time import org_today, org_tomorrow, window_span
from app.models.db import (
    Activity,
    DailyLedger,
    DynamicState,
    LogVerificationState,
    PlanningCycle,
    Resource,
    ReverseRsvpLog,
    StructuralMasterSlot,
)
from app.services.availability import days_against_window
from app.services.requirements import owners_with_requirements, unmet_for_window

logger = logging.getLogger(__name__)

# Rows written per savepoint. A batch the database accepts costs one round
# trip; one it refuses is retried a row at a time, so the size also bounds
# how much work a single refusal can cost.
LEDGER_BATCH_SIZE = 500


def _day_fields(
    slot: StructuralMasterSlot, target_date: datetime.date, state: DynamicState
) -> dict:
    return {
        "target_date": target_date,
        # Copied, not pointed at. The slot may be edited or deleted after
        # today has been generated, and neither should reach back and
        # change what time a day that has already happened ran at.
        "time_window_start": slot.time_window_start,
        "time_window_end": slot.time_window_end,
        "master_slot_id": slot.id,
        "activity_id": slot.activity_id,
        "active_lead_id": slot.primary_lead_id,
        "resource_id": slot.resource_id,
        "operational_state": state,
        # The slot's, because the nightly job has no caller to take it from.
        "organization_id": slot.organization_id,
    }


def _claims_a_window(fields: dict) -> bool:
    """Whether a day names a room and an hour, the rows the no-overlap rule covers."""
    return (
        fields["resource_id"] is not None
        and fields["time_window_start"] is not None
        and fields["time_window_end"] is not None
    )


def _report_taken(db: Session, fields: dict, taken: list) -> None:
    """Log a day that was not written because its room was taken.

    Nothing else in the system would ever mention it. taken is the days that
    were there first, as (slot, date, start) triples.
    """
    activity = db.get(Activity, fields["activity_id"])
    room = db.get(Resource, fields["resource_id"])
    logger.warning(
        "ledger: no day written for slot %s (%s) on %s in %s, the room is already taken by %s",
        fields["master_slot_id"],
        activity.activity_code if activity else "unknown activity",
        fields["target_date"],
        room.code if room else fields["resource_id"],
        taken or "a row this query could not find",
    )


def _report_unmet(db: Session, written: list[dict]) -> None:
    """Log the requirements the days just written cannot have.

    The timetable holds nothing for a requirement, so the log is where a gap
    shows up on the night it becomes real, next to GET /schedule/conflicts
    which lists the same gaps on demand. A day is never withheld for one.
    """
    needing = owners_with_requirements(db)
    if not needing:
        return
    for fields in written:
        if not _claims_a_window(fields):
            continue
        activity_id = (
            fields["activity_id"] if ("ACTIVITY", fields["activity_id"]) in needing else None
        )
        resource_id = (
            fields["resource_id"] if ("RESOURCE", fields["resource_id"]) in needing else None
        )
        if activity_id is None and resource_id is None:
            continue
        window = (fields["target_date"], fields["time_window_start"], fields["time_window_end"])
        for gap in unmet_for_window(db, activity_id, resource_id, window):
            logger.warning(
                "ledger: slot %s on %s has an unmet requirement: %s",
                fields["master_slot_id"],
                fields["target_date"],
                gap["message"],
            )


def _taken_by(db: Session, fields: dict) -> list:
    """The days already on this day's room that its window would sit on."""
    if not _claims_a_window(fields):
        return []
    found = days_against_window(
        db,
        fields["resource_id"],
        fields["target_date"],
        fields["time_window_start"],
        fields["time_window_end"],
        exclude_slot_id=fields["master_slot_id"],
    )
    return [(day["master_slot_id"], day["date"], str(day["start"])) for day in found]


def _insert_day(db: Session, fields: dict) -> bool:
    """Write one day, or find out why it could not be. True if it was written.

    A day that would sit on another day on its room is not written, on any
    database. Its own slot's other days are left out of that check: the only
    one that could collide is the same date, and the unique key below is
    what answers for that.
    """
    slot_id = fields["master_slot_id"]
    target_date = fields["target_date"]
    taken = _taken_by(db, fields)
    if taken:
        _report_taken(db, fields, taken)
        return False
    entry = DailyLedger(**fields)
    try:
        # The flush is inside the savepoint on purpose: it is the flush
        # that sends the INSERT, so a flush outside would be refused with
        # nothing left to roll back to.
        #
        # This is also what closes the gap between the existence check before
        # this and the insert. Two runs of this job against one database both find no
        # existing row and both insert; the second is refused here, by the
        # one-day-per-slot key uq_daily_ledger_slot_date, instead of quietly
        # doubling every day of the week.
        with db.begin_nested():
            db.add(entry)
            db.flush()
    except IntegrityError:
        # Nothing to expunge: rolling the savepoint back has already taken
        # the pending row out of the session, and asking for it again
        # raises rather than being a harmless no-op.
        #
        # A row for this slot and date now means another run wrote it
        # between the existence check and the insert. The day exists, so there
        # is nothing to report.
        lost_race = (
            db.query(DailyLedger)
            .filter(DailyLedger.master_slot_id == slot_id, DailyLedger.target_date == target_date)
            .first()
        )
        if lost_race:
            return False
        _report_taken(db, fields, _taken_by(db, fields))
        return False
    return True


def generate_daily_ledger_entries(target_date: datetime.date, db: Session) -> int:
    candidates = (
        db.query(StructuralMasterSlot)
        .join(Activity, StructuralMasterSlot.activity_id == Activity.id)
        .join(PlanningCycle, Activity.cycle_id == PlanningCycle.id)
        .filter(
            StructuralMasterSlot.retired_at.is_(None),
            Activity.retired_at.is_(None),
            PlanningCycle.operational_status,
            PlanningCycle.date_bounds_start <= target_date,
            PlanningCycle.date_bounds_end >= target_date,
        )
        # Oldest slot first, so which of two clashing classes keeps the room
        # is decided by which was put on the timetable first and not by the
        # order the database felt like returning them in. Rerunning a night
        # then produces the same answer it did the first time.
        .order_by(StructuralMasterSlot.id)
        .all()
    )
    # Whether the rule lands on the date is asked in Python: an RRULE is not
    # something either database can evaluate.
    slots = [s for s in candidates if recurrence.occurs_on(s.rrule, s.dtstart, target_date)]

    created = 0
    written = []
    for slot in slots:
        # Check for approved leave on this date for this lead
        leave = (
            db.query(ReverseRsvpLog)
            .filter(
                ReverseRsvpLog.submitting_user_id == slot.primary_lead_id,
                ReverseRsvpLog.target_absence_date <= target_date,
                func.coalesce(ReverseRsvpLog.end_date, ReverseRsvpLog.target_absence_date)
                >= target_date,
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

        fields = _day_fields(slot, target_date, initial_state)
        if _insert_day(db, fields):
            created += 1
            written.append(fields)

    db.commit()
    _report_unmet(db, written)
    return created


def horizon_window() -> tuple[datetime.date, datetime.date]:
    """The first and last day the ledger should be written for, both included.

    LEDGER_HORIZON_DAYS days counted from tomorrow, in the organization's
    calendar and off the application clock, so a host that moves the clock
    moves the window with it. Today is left out on purpose: a day that has
    begun is the catch-up's business (missed_ledger_dates), not the horizon's.
    """
    return org_tomorrow(), org_today() + datetime.timedelta(days=get_settings().ledger_horizon_days)


def materialize_horizon(db: Session, cycle_id: int | None = None) -> int:
    """Write every missing day inside the horizon, for every open cycle or for one.

    The nightly job calls it for all cycles. An import calls it for the cycle
    it just changed, so the new timetable is on the calendar at once and not
    at 23:00.

    It never touches a row that exists. A day is written only when no row has
    its slot and date, so a day somebody has marked, annotated or reassigned
    is left as it is, and running this twice in a row writes nothing the
    second time. The same rules as generate_daily_ledger_entries decide
    which days a slot has: the cycle open, the date inside the cycle's own
    dates (so nothing is written past a cycle's end), the slot's rule, and
    neither the slot nor its activity retired.
    A lead on approved leave that day gets the row ON_LEAVE, as there.

    This reads the existing rows, the slots and the leave once for the whole
    window instead of asking per slot per day, then writes in batches of
    LEDGER_BATCH_SIZE, each its own commit. Returns how many days were
    written.
    """
    first, last = horizon_window()
    slot_query = (
        db.query(
            StructuralMasterSlot,
            PlanningCycle.date_bounds_start,
            PlanningCycle.date_bounds_end,
        )
        .join(Activity, StructuralMasterSlot.activity_id == Activity.id)
        .join(PlanningCycle, Activity.cycle_id == PlanningCycle.id)
        .filter(
            StructuralMasterSlot.retired_at.is_(None),
            Activity.retired_at.is_(None),
            PlanningCycle.operational_status,
            PlanningCycle.date_bounds_start <= last,
            PlanningCycle.date_bounds_end >= first,
        )
        .order_by(StructuralMasterSlot.id)
    )
    have_query = db.query(DailyLedger.master_slot_id, DailyLedger.target_date).filter(
        DailyLedger.target_date >= first, DailyLedger.target_date <= last
    )
    if cycle_id is not None:
        slot_query = slot_query.filter(PlanningCycle.id == cycle_id)
        have_query = have_query.join(Activity, DailyLedger.activity_id == Activity.id).filter(
            Activity.cycle_id == cycle_id
        )

    have = {(slot_id, day) for slot_id, day in have_query}

    missing = []
    for slot, cycle_start, cycle_end in slot_query:
        # The rule's dates inside both the window and the cycle.
        for day in recurrence.occurrences(
            slot.rrule, slot.dtstart, max(first, cycle_start), min(last, cycle_end)
        ):
            if (slot.id, day) not in have:
                missing.append((day, slot))
    if not missing:
        return 0

    # Earliest day first and the older slot first within it, the order the
    # one-day job would have written them in, so which of two clashing
    # classes keeps the room does not depend on how the horizon is walked.
    missing.sort(key=lambda item: (item[0], item[1].id))

    leads = {slot.primary_lead_id for _, slot in missing if slot.primary_lead_id}
    leave: dict[str, list[tuple[datetime.date, datetime.date]]] = {}
    if leads:
        for lead_id, starts, ends in db.query(
            ReverseRsvpLog.submitting_user_id,
            ReverseRsvpLog.target_absence_date,
            ReverseRsvpLog.end_date,
        ).filter(
            ReverseRsvpLog.submitting_user_id.in_(leads),
            ReverseRsvpLog.target_absence_date <= last,
            func.coalesce(ReverseRsvpLog.end_date, ReverseRsvpLog.target_absence_date) >= first,
            ReverseRsvpLog.approval_state == LogVerificationState.VERIFIED_APPROVED,
        ):
            leave.setdefault(lead_id, []).append((starts, ends or starts))

    # Plain values, built before the first commit. A commit expires every
    # slot in the session, and reading them again would be a query each.
    rows = []
    for day, slot in missing:
        on_leave = any(a <= day <= b for a, b in leave.get(slot.primary_lead_id, ()))
        state = DynamicState.ON_LEAVE if on_leave else DynamicState.SCHEDULED
        rows.append(_day_fields(slot, day, state))
    rows = _without_overlaps(db, rows, first, last)

    created = 0
    written = []
    for offset in range(0, len(rows), LEDGER_BATCH_SIZE):
        batch = rows[offset : offset + LEDGER_BATCH_SIZE]
        try:
            with db.begin_nested():
                db.add_all(DailyLedger(**fields) for fields in batch)
                db.flush()
            created += len(batch)
            written.extend(batch)
        except IntegrityError:
            # One of them was refused: a room clash on PostgreSQL, or another
            # instance writing the same day first. Go a row at a time so only
            # the refused one is lost.
            kept = [fields for fields in batch if _insert_day(db, fields)]
            created += len(kept)
            written.extend(kept)
        db.commit()
    _report_unmet(db, written)
    return created


def _without_overlaps(db: Session, rows: list[dict], first, last) -> list[dict]:
    """The rows that can be written without one sitting on another on its room.

    A batch goes to the database in one flush, so a check per row against the
    table cannot see two new rows that collide with each other, and SQLite has
    no constraint to refuse them either. So the days already on the rooms
    involved are read once, the rows are walked in the order they will be
    written (earliest day, then the older slot), and a row is kept only if it
    sits on nothing already there or already kept. A dropped row is logged the
    same way _insert_day logs one.

    A day from the day before the window can run into its first morning, and
    one from the day after can start inside its last night, so the read
    reaches one day further at each end.
    """
    rooms = {fields["resource_id"] for fields in rows if _claims_a_window(fields)}
    if not rooms:
        return rows
    one_day = datetime.timedelta(days=1)
    held: dict[int, list[tuple]] = {}
    for day in db.query(DailyLedger).filter(
        DailyLedger.resource_id.in_(rooms),
        DailyLedger.target_date >= first - one_day,
        DailyLedger.target_date <= last + one_day,
        DailyLedger.time_window_start.isnot(None),
        DailyLedger.time_window_end.isnot(None),
    ):
        opens, closes = window_span(day.target_date, day.time_window_start, day.time_window_end)
        held.setdefault(day.resource_id, []).append(
            (opens, closes, day.master_slot_id, day.target_date, str(day.time_window_start))
        )

    kept = []
    for fields in rows:
        if not _claims_a_window(fields):
            kept.append(fields)
            continue
        opens, closes = window_span(
            fields["target_date"], fields["time_window_start"], fields["time_window_end"]
        )
        on_room = held.setdefault(fields["resource_id"], [])
        taken = [
            (slot_id, day, start)
            for other_opens, other_closes, slot_id, day, start in on_room
            if other_opens < closes and opens < other_closes
        ]
        if taken:
            _report_taken(db, fields, taken)
            continue
        on_room.append(
            (
                opens,
                closes,
                fields["master_slot_id"],
                fields["target_date"],
                str(fields["time_window_start"]),
            )
        )
        kept.append(fields)
    return kept


def missed_ledger_dates(now: datetime.datetime, nightly_hour: int) -> list[datetime.date]:
    """The dates a process starting at `now` should make sure exist.

    The nightly job writes tomorrow at nightly_hour, and the scheduler keeps no
    record of runs it missed while the process was down. Today is always
    included, because last night's run may be the one that was missed.
    Tomorrow is included once the nightly hour has come, because tonight's may
    have been missed too. Earlier dates never are: a day that is over is
    history, and a planned row written into it now would read as a class that
    ran with nobody marked present.

    Running a date twice is harmless, since generation skips a slot that
    already has its day.
    """
    today = now.date()
    if now.hour >= nightly_hour:
        return [today, today + datetime.timedelta(days=1)]
    return [today]
