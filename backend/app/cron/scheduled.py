# Copyright 2026 Chronos Ledger Contributors
# Licensed under the Apache License, Version 2.0
"""The scheduled jobs, in one table, and how they run under each clock.

Under the system clock main.py hands these wrappers to APScheduler and the
table is only documentation. Under a host clock (docs/clock.md) the
scheduler never starts, and ``run_due_jobs`` is what moves the clock: it
runs every job whose moment falls in (previous, current], in order, with the
clock set to that moment while the job runs, so a nightly run sees the same
"tomorrow" it would have seen at 23:00.

Order within one instant is the order of JOBS below. The ledger run goes
first because the purges and the overstay notice read what the day holds,
and the day should be laid down before anything reads it.
"""

from __future__ import annotations

import asyncio
import inspect
from collections.abc import Callable, Iterator
from dataclasses import dataclass
from datetime import UTC, datetime, time, timedelta

from app.core import clock
from app.core.config import get_settings
from app.core.database import SessionLocal
from app.core.idempotency import purge_expired
from app.core.time import org_now, org_timezone
from app.cron.guest_overstay import announce_overstayed_visits
from app.cron.guest_retention import purge_old_guest_check_ins
from app.cron.ledger_generator import (
    generate_daily_ledger_entries,
    materialize_horizon,
    missed_ledger_dates,
)
from app.cron.refresh_token_cleanup import purge_expired_refresh_tokens

NIGHTLY_LEDGER_HOUR = 23
OVERSTAY_INTERVAL = timedelta(minutes=5)


def run_ledger_generator():
    """Keep LEDGER_HORIZON_DAYS of days written, counted from tomorrow.

    Only the missing ones are written, so a night that finds the horizon full
    writes the one new day at its far end, and a run after a stretch with no
    jobs (a host that advanced the clock several days, or a process that was
    down) fills the whole gap.
    """
    db = SessionLocal()
    try:
        materialize_horizon(db)
    finally:
        db.close()


def catch_up_ledger():
    """Write the days the nightly job would have written while nothing ran.

    The scheduler forgets a run it missed across a restart, so a deploy over
    23:00 left tomorrow empty until somebody called generate-ledger by hand.
    missed_ledger_dates says which dates, and why never earlier ones.

    Every instance does this when it starts, and two at once is safe: the
    database refuses a second day for one slot and date, and the run that
    loses skips it without a word.
    """
    db = SessionLocal()
    try:
        for day in missed_ledger_dates(org_now(), NIGHTLY_LEDGER_HOUR):
            generate_daily_ledger_entries(day, db)
    finally:
        db.close()


def purge_refresh_tokens():
    db = SessionLocal()
    try:
        purge_expired_refresh_tokens(db)
    finally:
        db.close()


def purge_guest_check_ins():
    db = SessionLocal()
    try:
        purge_old_guest_check_ins(db, get_settings().guest_retention_days)
    finally:
        db.close()


def purge_idempotency_records():
    db = SessionLocal()
    try:
        purge_expired(db)
    finally:
        db.close()


async def announce_guest_overstays():
    # Async, unlike its neighbours: the notice goes out over the socket, which
    # belongs to this loop, and the scheduler runs in the same process.
    db = SessionLocal()
    try:
        await announce_overstayed_visits(db)
    finally:
        db.close()


Moments = Callable[[datetime, datetime], Iterator[datetime]]


def daily_at(hour: int, minute: int) -> Moments:
    """The moments a cron job at hour:minute, organization time, has in (previous, current]."""

    def moments(previous: datetime, current: datetime) -> Iterator[datetime]:
        zone = org_timezone()
        day = previous.astimezone(zone).date()
        last = current.astimezone(zone).date()
        while day <= last:
            moment = datetime.combine(day, time(hour, minute), tzinfo=zone).astimezone(UTC)
            if previous < moment <= current:
                yield moment
            day += timedelta(days=1)

    return moments


def every(interval: timedelta) -> Moments:
    """The last mark of a fixed UTC grid that falls in (previous, current], if any.

    One run rather than one per mark, the way APScheduler coalesces the
    runs it missed while the process was busy. The jobs on an interval are
    idempotent sweeps, so the last mark does the work of all of them.
    """
    step = int(interval.total_seconds())

    def moments(previous: datetime, current: datetime) -> Iterator[datetime]:
        mark = datetime.fromtimestamp(int(current.timestamp()) // step * step, UTC)
        if previous < mark <= current:
            yield mark

    return moments


@dataclass(frozen=True)
class Job:
    name: str
    run: Callable[[], object]
    moments: Moments


# In the order they run when two fall on the same instant. The names are the
# APScheduler job ids main.py registers, so a log reads the same either way.
JOBS: tuple[Job, ...] = (
    Job("nightly_ledger_gen", run_ledger_generator, daily_at(NIGHTLY_LEDGER_HOUR, 0)),
    Job("refresh_token_purge", purge_refresh_tokens, daily_at(3, 0)),
    Job("guest_retention_purge", purge_guest_check_ins, daily_at(3, 30)),
    Job("idempotency_purge", purge_idempotency_records, daily_at(3, 45)),
    Job("guest_overstay_notice", announce_guest_overstays, every(OVERSTAY_INTERVAL)),
)


def due_jobs(previous: datetime, current: datetime) -> list[tuple[datetime, Job]]:
    """Every (moment, job) with previous < moment <= current, in the order they run."""
    if current < previous:
        raise ValueError("current is before previous")
    rank = {job.name: index for index, job in enumerate(JOBS)}
    due = [(moment, job) for job in JOBS for moment in job.moments(previous, current)]
    due.sort(key=lambda pair: (pair[0], rank[pair[1].name]))
    return due


async def run_due_jobs(previous: datetime, current: datetime) -> list[str]:
    """Run the jobs due in (previous, current] and leave the clock at current.

    Host clock only. The clock is moved to each job's moment before the job
    runs, so the job stamps and reasons about the time it would have run at.
    Returns the names of the jobs that ran, in the order they ran.
    """
    if not clock.is_host():
        raise RuntimeError("run_due_jobs needs CLOCK_MODE=host; the scheduler runs the jobs")
    ran = []
    for moment, job in due_jobs(previous, current):
        clock.advance_to(moment)
        outcome = job.run()
        if inspect.isawaitable(outcome):
            await outcome
        ran.append(job.name)
    clock.advance_to(current)
    return ran


def advance(instant: datetime) -> list[str]:
    """Move the host clock to instant, running what came due on the way."""
    return asyncio.run(run_due_jobs(clock.now(), instant))
