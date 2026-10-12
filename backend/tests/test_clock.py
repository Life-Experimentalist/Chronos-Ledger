# Copyright 2026 Chronos Ledger Contributors
# Licensed under the Apache License, Version 2.0
"""The simulation clock, the seeded ids and the job table under a host clock."""

import asyncio
import datetime
import uuid

import pytest

from app.core import clock, ids
from app.core.config import Settings, get_settings
from app.cron import scheduled

UTC = datetime.UTC
START = datetime.datetime(2026, 9, 7, 8, 0, tzinfo=UTC)


@pytest.fixture()
def _clocks_reset():
    yield
    clock.reset()
    ids.reset()
    get_settings.cache_clear()


# -- The clock ----------------------------------------------------------------


def test_the_system_clock_is_the_default(_clocks_reset):
    clock.reset()
    assert isinstance(clock.current(), clock.SystemClock)
    assert not clock.is_host()
    before = datetime.datetime.now(UTC)
    read = clock.now()
    assert before <= read <= datetime.datetime.now(UTC)
    assert read.tzinfo is not None


def test_the_system_clock_cannot_be_advanced():
    with pytest.raises(RuntimeError):
        clock.SystemClock().advance_to(START)


def test_a_host_clock_does_not_move_on_its_own():
    host = clock.HostClock(START)
    assert host.now() == START
    assert host.now() == START
    assert host.now().tzinfo is UTC


def test_a_host_clock_refuses_to_go_backwards():
    host = clock.HostClock(START)
    host.advance_to(START + datetime.timedelta(hours=1))
    with pytest.raises(ValueError):
        host.advance_to(START)
    assert host.now() == START + datetime.timedelta(hours=1)


def test_advancing_to_the_same_instant_is_allowed():
    host = clock.HostClock(START)
    host.advance_to(START)
    assert host.now() == START


def test_a_host_clock_keeps_utc_whatever_offset_it_is_given():
    kolkata = datetime.timezone(datetime.timedelta(hours=5, minutes=30))
    host = clock.HostClock(datetime.datetime(2026, 9, 7, 13, 30, tzinfo=kolkata))
    assert host.now() == START
    host.advance_to(datetime.datetime(2026, 9, 7, 14, 30, tzinfo=kolkata))
    assert host.now() == START + datetime.timedelta(hours=1)


def test_a_naive_instant_is_refused():
    with pytest.raises(ValueError):
        clock.HostClock(datetime.datetime(2026, 9, 7, 8, 0))
    with pytest.raises(ValueError):
        clock.HostClock(START).advance_to(datetime.datetime(2026, 9, 7, 9, 0))


def test_the_installed_clock_is_what_the_module_reads(_clocks_reset):
    clock.install(clock.HostClock(START))
    assert clock.is_host()
    assert clock.now() == START
    clock.advance_to(START + datetime.timedelta(minutes=5))
    assert clock.now() == START + datetime.timedelta(minutes=5)


def test_wall_now_is_real_time_even_under_a_host_clock(_clocks_reset):
    clock.install(clock.HostClock(START))
    assert clock.wall_now() - datetime.datetime.now(UTC) < datetime.timedelta(seconds=5)


def test_org_now_reads_the_installed_clock(_clocks_reset, monkeypatch):
    from app.core.time import org_now, org_today, org_tomorrow

    monkeypatch.setenv("ORG_TIMEZONE", "Asia/Kolkata")
    get_settings.cache_clear()
    clock.install(clock.HostClock(datetime.datetime(2026, 9, 7, 20, 0, tzinfo=UTC)))
    assert org_now().hour == 1
    assert org_today() == datetime.date(2026, 9, 8)
    assert org_tomorrow() == datetime.date(2026, 9, 9)


# -- Settings -----------------------------------------------------------------


def test_the_clock_is_built_from_settings():
    system = Settings(_env_file=None)
    assert isinstance(clock.from_settings(system), clock.SystemClock)
    host = Settings(_env_file=None, clock_mode="host", clock_start="2026-09-07T08:00:00+00:00")
    built = clock.from_settings(host)
    assert isinstance(built, clock.HostClock)
    assert built.now() == START


def test_host_mode_needs_a_start():
    with pytest.raises(ValueError, match="CLOCK_START"):
        Settings(_env_file=None, clock_mode="host")


def test_the_start_must_carry_an_offset():
    with pytest.raises(ValueError, match="offset"):
        Settings(_env_file=None, clock_mode="host", clock_start="2026-09-07T08:00:00")


def test_the_start_must_parse():
    with pytest.raises(ValueError, match="ISO 8601"):
        Settings(_env_file=None, clock_mode="host", clock_start="next tuesday")


def test_an_unknown_mode_is_refused():
    with pytest.raises(ValueError, match="CLOCK_MODE"):
        Settings(_env_file=None, clock_mode="frozen")


def test_a_start_is_harmless_under_the_system_clock():
    settings = Settings(_env_file=None, clock_start="2026-09-07T08:00:00+00:00")
    assert isinstance(clock.from_settings(settings), clock.SystemClock)


# -- Identifiers --------------------------------------------------------------


def test_unseeded_ids_are_random():
    generator = ids.IdGenerator(None)
    assert not generator.seeded
    first, second = generator.uuid(), generator.uuid()
    assert first != second
    assert first.version == 4
    assert generator.hex(8) != generator.hex(8)
    assert len(generator.hex(8)) == 16


def test_seeded_ids_repeat():
    first = ids.IdGenerator(42)
    second = ids.IdGenerator(42)
    assert first.seeded
    drawn = [first.uuid() for _ in range(5)] + [first.hex(8) for _ in range(5)]
    again = [second.uuid() for _ in range(5)] + [second.hex(8) for _ in range(5)]
    assert drawn == again
    assert len(set(drawn)) == 10
    assert all(value.version == 4 for value in drawn[:5])
    assert all(isinstance(value, uuid.UUID) for value in drawn[:5])


def test_a_different_seed_is_a_different_sequence():
    assert ids.IdGenerator(1).uuid() != ids.IdGenerator(2).uuid()


def test_the_installed_generator_is_what_the_module_draws_from(_clocks_reset):
    ids.install(ids.IdGenerator(7))
    expected = ids.IdGenerator(7)
    assert ids.new_uuid() == expected.uuid()
    assert ids.new_hex(4) == expected.hex(4)
    ids.reset()
    assert not ids.current().seeded


def test_the_generator_is_built_from_settings():
    assert not ids.from_settings(Settings(_env_file=None)).seeded
    assert ids.from_settings(Settings(_env_file=None, id_seed=3)).seeded


# -- The job table ------------------------------------------------------------

NIGHTLY = datetime.datetime(2026, 9, 7, 23, 0, tzinfo=UTC)


def _names(due):
    return [(moment, job.name) for moment, job in due]


def test_a_job_exactly_at_current_runs():
    due = _names(scheduled.due_jobs(NIGHTLY - datetime.timedelta(hours=1), NIGHTLY))
    assert (NIGHTLY, "nightly_ledger_gen") in due


def test_a_job_exactly_at_previous_does_not_run():
    due = _names(scheduled.due_jobs(NIGHTLY, NIGHTLY + datetime.timedelta(hours=1)))
    assert "nightly_ledger_gen" not in [name for _, name in due]


def test_nothing_is_due_in_an_empty_window():
    moment = datetime.datetime(2026, 9, 7, 10, 1, tzinfo=UTC)
    assert scheduled.due_jobs(moment, moment + datetime.timedelta(minutes=1)) == []


def test_current_before_previous_is_refused():
    with pytest.raises(ValueError):
        scheduled.due_jobs(NIGHTLY, NIGHTLY - datetime.timedelta(seconds=1))


def test_a_day_runs_every_job_once_in_order():
    due = _names(scheduled.due_jobs(START, START + datetime.timedelta(hours=20)))
    assert due == [
        (NIGHTLY, "nightly_ledger_gen"),
        (datetime.datetime(2026, 9, 8, 3, 0, tzinfo=UTC), "refresh_token_purge"),
        (datetime.datetime(2026, 9, 8, 3, 30, tzinfo=UTC), "guest_retention_purge"),
        (datetime.datetime(2026, 9, 8, 4, 0, tzinfo=UTC), "guest_overstay_notice"),
    ]


def test_the_overstay_notice_runs_once_per_window_at_the_last_mark():
    due = _names(scheduled.due_jobs(START, START + datetime.timedelta(minutes=17)))
    assert due == [(START + datetime.timedelta(minutes=15), "guest_overstay_notice")]


def test_the_daily_jobs_follow_the_organization_zone(monkeypatch):
    monkeypatch.setenv("ORG_TIMEZONE", "Asia/Kolkata")
    get_settings.cache_clear()
    try:
        due = _names(scheduled.due_jobs(START, START + datetime.timedelta(hours=12)))
    finally:
        get_settings.cache_clear()
    # 23:00 in Kolkata is 17:30 UTC.
    assert (datetime.datetime(2026, 9, 7, 17, 30, tzinfo=UTC), "nightly_ledger_gen") in due


def test_ties_keep_the_table_order(monkeypatch):
    at_once = scheduled.daily_at(23, 0)
    fake = tuple(scheduled.Job(job.name, job.run, at_once) for job in reversed(scheduled.JOBS))
    monkeypatch.setattr(scheduled, "JOBS", fake)
    due = _names(scheduled.due_jobs(NIGHTLY - datetime.timedelta(hours=1), NIGHTLY))
    assert [name for _, name in due] == [job.name for job in fake]


def test_run_due_jobs_needs_a_host_clock(_clocks_reset):
    clock.install(clock.SystemClock())
    with pytest.raises(RuntimeError):
        asyncio.run(scheduled.run_due_jobs(START, START + datetime.timedelta(hours=1)))


def test_run_due_jobs_sets_the_clock_to_each_moment(_clocks_reset, monkeypatch):
    seen = []

    def sync_job():
        seen.append(("sync", clock.now()))

    async def async_job():
        seen.append(("async", clock.now()))

    monkeypatch.setattr(
        scheduled,
        "JOBS",
        (
            scheduled.Job("first", sync_job, scheduled.daily_at(23, 0)),
            scheduled.Job("second", async_job, scheduled.daily_at(3, 0)),
        ),
    )
    clock.install(clock.HostClock(START))
    current = START + datetime.timedelta(hours=20)

    ran = scheduled.advance(current)

    assert ran == ["first", "second"]
    assert seen == [
        ("sync", NIGHTLY),
        ("async", datetime.datetime(2026, 9, 8, 3, 0, tzinfo=UTC)),
    ]
    assert clock.now() == current


def test_advance_with_nothing_due_still_moves_the_clock(_clocks_reset):
    clock.install(clock.HostClock(START))
    assert scheduled.advance(START + datetime.timedelta(minutes=1)) == []
    assert clock.now() == START + datetime.timedelta(minutes=1)


def test_advance_backwards_runs_nothing_and_leaves_the_clock(_clocks_reset):
    clock.install(clock.HostClock(START))
    with pytest.raises(ValueError):
        scheduled.advance(START - datetime.timedelta(minutes=1))
    assert clock.now() == START
