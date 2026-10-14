# Copyright 2026 Chronos Ledger Contributors
# Licensed under the Apache License, Version 2.0
"""The ledger is kept written LEDGER_HORIZON_DAYS ahead, not one night at a time."""

import datetime
import logging
from decimal import Decimal

import pytest

from app.core import clock
from app.core.config import Settings, get_settings
from app.core.time import org_today
from app.cron import ledger_generator, scheduled
from app.cron.ledger_generator import generate_daily_ledger_entries, materialize_horizon
from app.models.db import (
    Activity,
    DailyLedger,
    DynamicState,
    LogVerificationState,
    PlanningCycle,
    ReverseRsvpLog,
    StructuralMasterSlot,
)
from tests.conftest import ADMIN_PASSWORD, login, weekly
from tests.test_ingestion import HEADER, _upload

# The import fill is switched off for the rest of the suite (see conftest).
FILL_LEDGER_ON_IMPORT = True

DAY = datetime.timedelta(days=1)
UTC = datetime.UTC


def _cycle(db, start, end, open_=True, code="CS101"):
    cycle = PlanningCycle(
        cycle_label=f"Cycle {code}",
        date_bounds_start=start,
        date_bounds_end=end,
        operational_status=open_,
    )
    db.add(cycle)
    db.flush()
    offering = Activity(
        activity_code=code, activity_title="Intro", unit_code="CSE", cycle_id=cycle.id
    )
    db.add(offering)
    db.flush()
    db.commit()
    return cycle, offering


def _week_of_slots(db, offering, lead):
    """One 09:00 slot on every weekday, so any 28 days hold exactly 28 rows."""
    slots = []
    for weekday in range(1, 8):
        slot = StructuralMasterSlot(
            **weekly(weekday),
            time_window_start=datetime.time(9, 0),
            time_window_end=datetime.time(10, 0),
            activity_id=offering.id,
            primary_lead_id=lead,
            target_room_identifier="LH-101",
        )
        db.add(slot)
        slots.append(slot)
    db.commit()
    return slots


def _dates(db):
    return sorted(day.target_date for day in db.query(DailyLedger).all())


def _days(first, last):
    return [first + DAY * n for n in range((last - first).days + 1)]


@pytest.fixture()
def timetable(db, seed_users):
    today = org_today()
    cycle, offering = _cycle(db, today - 30 * DAY, today + 200 * DAY)
    _week_of_slots(db, offering, seed_users["staff"].id)
    return cycle


# -- The window ---------------------------------------------------------------


def test_the_default_is_four_weeks_counted_from_tomorrow(db, timetable):
    today = org_today()
    assert ledger_generator.horizon_window() == (today + DAY, today + 28 * DAY)

    assert materialize_horizon(db) == 28

    assert _dates(db) == _days(today + DAY, today + 28 * DAY)


def test_the_setting_moves_the_far_end(db, timetable, monkeypatch):
    monkeypatch.setattr(
        ledger_generator, "get_settings", lambda: Settings(_env_file=None, ledger_horizon_days=10)
    )

    assert materialize_horizon(db) == 10

    today = org_today()
    assert _dates(db) == _days(today + DAY, today + 10 * DAY)


@pytest.mark.parametrize("days", [0, -1, 367])
def test_a_horizon_outside_one_to_a_year_is_refused(days):
    with pytest.raises(ValueError, match="LEDGER_HORIZON_DAYS"):
        Settings(_env_file=None, ledger_horizon_days=days)


@pytest.mark.parametrize("days", [1, 28, 366])
def test_the_ends_of_the_range_are_allowed(days):
    assert Settings(_env_file=None, ledger_horizon_days=days).ledger_horizon_days == days


# -- The nightly job ----------------------------------------------------------


def test_running_the_job_twice_adds_nothing(db, timetable, monkeypatch):
    monkeypatch.setattr(scheduled, "SessionLocal", lambda: db)

    scheduled.run_ledger_generator()
    first = db.query(DailyLedger).count()
    ids = sorted(day.id for day in db.query(DailyLedger).all())
    scheduled.run_ledger_generator()

    assert first == 28
    assert db.query(DailyLedger).count() == 28
    assert sorted(day.id for day in db.query(DailyLedger).all()) == ids
    assert materialize_horizon(db) == 0


def test_the_job_writes_only_the_days_that_are_missing(db, timetable):
    today = org_today()
    assert materialize_horizon(db) == 28

    # Yesterday's run has aged out one day and the far end is one day short.
    db.query(DailyLedger).filter(DailyLedger.target_date == today + 28 * DAY).delete()
    db.commit()

    assert materialize_horizon(db) == 1
    assert _dates(db) == _days(today + DAY, today + 28 * DAY)


def test_a_day_with_something_recorded_is_left_as_it_is(db, timetable, seed_users):
    assert materialize_horizon(db) == 28
    entry = db.query(DailyLedger).order_by(DailyLedger.target_date).first()
    entry.active_lead_id = seed_users["admin"].id
    entry.operational_state = DynamicState.PROXY_SUBSTITUTE
    entry.latitude_target = Decimal("12.9716")
    db.commit()

    assert materialize_horizon(db) == 0

    db.expire_all()
    kept = db.get(DailyLedger, entry.id)
    assert kept.active_lead_id == seed_users["admin"].id
    assert kept.operational_state == DynamicState.PROXY_SUBSTITUTE
    assert kept.latitude_target == Decimal("12.9716")


def test_today_is_left_to_the_catch_up(db, timetable):
    """Today is the catch-up's, not the horizon's."""
    materialize_horizon(db)
    assert org_today() not in _dates(db)


def test_batches_split_the_work_without_changing_it(db, timetable, monkeypatch):
    monkeypatch.setattr(ledger_generator, "LEDGER_BATCH_SIZE", 5)
    today = org_today()

    assert materialize_horizon(db) == 28

    assert _dates(db) == _days(today + DAY, today + 28 * DAY)


def test_a_refused_row_costs_only_that_row(db, timetable, monkeypatch, caplog):
    """Another instance writes one of the days between the check and the insert."""
    real = ledger_generator._day_fields
    seen = []

    def racing(slot, day, state):
        fields = real(slot, day, state)
        if not seen:
            seen.append(fields)
            db.add(ledger_generator.DailyLedger(**fields))
            db.flush()
        return fields

    monkeypatch.setattr(ledger_generator, "_day_fields", racing)
    with caplog.at_level(logging.WARNING):
        created = materialize_horizon(db)

    assert created == 27
    assert db.query(DailyLedger).count() == 28
    # The day exists, so there is nothing to warn about.
    assert "no day written" not in caplog.text


def test_a_closed_cycle_is_not_written(db, seed_users):
    today = org_today()
    _, offering = _cycle(db, today - 30 * DAY, today + 200 * DAY, open_=False)
    _week_of_slots(db, offering, seed_users["staff"].id)

    assert materialize_horizon(db) == 0


# -- Where a cycle ends -------------------------------------------------------


def test_nothing_is_written_past_the_end_of_a_cycle(db, seed_users):
    today = org_today()
    _, offering = _cycle(db, today - 30 * DAY, today + 10 * DAY)
    _week_of_slots(db, offering, seed_users["staff"].id)

    assert materialize_horizon(db) == 10

    assert _dates(db) == _days(today + DAY, today + 10 * DAY)


def test_nothing_is_written_before_a_cycle_starts(db, seed_users):
    today = org_today()
    _, offering = _cycle(db, today + 20 * DAY, today + 100 * DAY)
    _week_of_slots(db, offering, seed_users["staff"].id)

    assert materialize_horizon(db) == 9

    assert _dates(db) == _days(today + 20 * DAY, today + 28 * DAY)


# -- Leave --------------------------------------------------------------------


def test_days_inside_approved_leave_come_out_on_leave(db, timetable, seed_users):
    today = org_today()
    db.add(
        ReverseRsvpLog(
            submitting_user_id=seed_users["staff"].id,
            target_absence_date=today + 3 * DAY,
            end_date=today + 5 * DAY,
            context_justification="Conference",
            approval_state=LogVerificationState.VERIFIED_APPROVED,
            authorized_by_user_id=seed_users["admin"].id,
        )
    )
    # A single-day request has no end_date, and a pending one is not leave.
    db.add(
        ReverseRsvpLog(
            submitting_user_id=seed_users["staff"].id,
            target_absence_date=today + 9 * DAY,
            context_justification="Dentist",
            approval_state=LogVerificationState.VERIFIED_APPROVED,
            authorized_by_user_id=seed_users["admin"].id,
        )
    )
    db.add(
        ReverseRsvpLog(
            submitting_user_id=seed_users["staff"].id,
            target_absence_date=today + 12 * DAY,
            context_justification="Maybe",
        )
    )
    db.commit()

    materialize_horizon(db)

    on_leave = sorted(
        day.target_date
        for day in db.query(DailyLedger).filter(
            DailyLedger.operational_state == DynamicState.ON_LEAVE
        )
    )
    assert on_leave == [today + 3 * DAY, today + 4 * DAY, today + 5 * DAY, today + 9 * DAY]


def test_leave_comes_out_as_the_one_day_job_makes_it(db, timetable, seed_users):
    today = org_today()
    db.add(
        ReverseRsvpLog(
            submitting_user_id=seed_users["staff"].id,
            target_absence_date=today + 2 * DAY,
            end_date=today + 4 * DAY,
            context_justification="Conference",
            approval_state=LogVerificationState.VERIFIED_APPROVED,
            authorized_by_user_id=seed_users["admin"].id,
        )
    )
    db.commit()

    materialize_horizon(db)

    def written():
        return {
            (row.master_slot_id, row.target_date): (
                row.operational_state,
                row.active_lead_id,
                row.target_room_identifier,
                row.time_window_start,
                row.time_window_end,
            )
            for row in db.query(DailyLedger)
        }

    horizon = written()
    db.query(DailyLedger).delete()
    db.commit()
    for n in range(1, 29):
        generate_daily_ledger_entries(today + n * DAY, db)

    assert len(horizon) == 28
    assert horizon == written()


# -- The host clock -----------------------------------------------------------


@pytest.fixture()
def host_clock(monkeypatch):
    monkeypatch.setenv("ORG_TIMEZONE", "UTC")
    get_settings.cache_clear()
    yield
    clock.reset()
    get_settings.cache_clear()


def test_advancing_the_host_clock_rolls_the_horizon(db, seed_users, host_clock, monkeypatch):
    monkeypatch.setattr(scheduled, "SessionLocal", lambda: db)
    start = datetime.datetime(2026, 9, 7, 8, 0, tzinfo=UTC)
    clock.install(clock.HostClock(start))
    _, offering = _cycle(db, datetime.date(2026, 8, 1), datetime.date(2026, 12, 20))
    _week_of_slots(db, offering, seed_users["staff"].id)

    # Monday evening. The 23:00 run counts from Tuesday the 8th.
    ran = scheduled.advance(datetime.datetime(2026, 9, 7, 23, 30, tzinfo=UTC))
    assert "nightly_ledger_gen" in ran
    assert _dates(db) == _days(datetime.date(2026, 9, 8), datetime.date(2026, 10, 5))

    # Three more nights pass at once. Each runs in turn, with the clock at its
    # own 23:00, so the far end moves three days and nothing is written twice.
    ran = scheduled.advance(datetime.datetime(2026, 9, 10, 23, 30, tzinfo=UTC))
    assert ran.count("nightly_ledger_gen") == 3
    assert _dates(db) == _days(datetime.date(2026, 9, 8), datetime.date(2026, 10, 8))
    assert db.query(DailyLedger).count() == 31


def test_a_jump_of_a_month_fills_the_whole_window(db, seed_users, host_clock, monkeypatch):
    monkeypatch.setattr(scheduled, "SessionLocal", lambda: db)
    clock.install(clock.HostClock(datetime.datetime(2026, 9, 7, 8, 0, tzinfo=UTC)))
    _, offering = _cycle(db, datetime.date(2026, 8, 1), datetime.date(2026, 12, 20))
    _week_of_slots(db, offering, seed_users["staff"].id)

    scheduled.advance(datetime.datetime(2026, 10, 15, 23, 30, tzinfo=UTC))

    last_run = datetime.date(2026, 10, 15)
    assert _dates(db)[0] == datetime.date(2026, 9, 8)
    assert _dates(db)[-1] == last_run + 28 * DAY
    assert db.query(DailyLedger).count() == len(
        _days(datetime.date(2026, 9, 8), last_run + 28 * DAY)
    )


# -- A CSV import -------------------------------------------------------------


def _csv(lead="FAC001", end="10:00"):
    rows = [
        f"STU900,Ada Newling,ada@test.internal,MA201,Linear Algebra,CSE,{day},09:00,{end},"
        f"{lead},LH-201\n"
        for day in range(1, 8)
    ]
    return HEADER + "\n" + "".join(rows)


def _import(client, db, seed_users, csv_text, start_offset=-30, end_offset=200):
    today = org_today()
    cycle = PlanningCycle(
        cycle_label="Import",
        date_bounds_start=today + start_offset * DAY,
        date_bounds_end=today + end_offset * DAY,
        operational_status=True,
    )
    db.add(cycle)
    db.commit()
    headers = login(client, "admin@test.internal", ADMIN_PASSWORD)
    return cycle, _upload(client, headers, cycle.id, csv_text)


def test_an_import_fills_the_next_four_weeks_at_once(client, db, seed_users):
    today = org_today()

    _, res = _import(client, db, seed_users, _csv())

    assert res.status_code == 200, res.text
    assert _dates(db) == _days(today + DAY, today + 28 * DAY)


def test_the_import_reply_is_what_it_was(client, db, seed_users):
    _, res = _import(client, db, seed_users, _csv())

    assert set(res.json()) == {
        "status",
        "rows_ingested",
        "provisioned_credentials",
        "slots_corrected",
        "not_in_file",
        "ledger_rows_updated",
        "ledger_rows_kept",
        "kept_days",
    }


def test_importing_the_same_file_again_adds_no_days(client, db, seed_users):
    cycle, _ = _import(client, db, seed_users, _csv())
    headers = login(client, "admin@test.internal", ADMIN_PASSWORD)

    res = _upload(client, headers, cycle.id, _csv())

    assert res.status_code == 200, res.text
    assert db.query(DailyLedger).count() == 28


def test_an_import_stops_at_the_end_of_its_cycle(client, db, seed_users):
    today = org_today()

    _, res = _import(client, db, seed_users, _csv(), end_offset=10)

    assert res.status_code == 200, res.text
    assert _dates(db) == _days(today + DAY, today + 10 * DAY)


def test_a_refused_import_writes_no_days(client, db, seed_users):
    _, res = _import(client, db, seed_users, _csv(lead="NOBODY"))

    assert res.status_code == 422
    assert db.query(DailyLedger).count() == 0


def test_a_failure_filling_the_days_does_not_fail_the_import(client, db, seed_users, monkeypatch):
    from app.api.v1.endpoints import ingestion

    def broken(db, cycle_id=None):
        raise RuntimeError("the database went away")

    monkeypatch.setattr(ingestion, "materialize_horizon", broken)

    cycle, res = _import(client, db, seed_users, _csv())

    assert res.status_code == 200, res.text
    assert db.query(StructuralMasterSlot).count() == 7
    # The nightly job picks them up.
    assert materialize_horizon(db, cycle.id) == 28


def test_an_import_fills_its_own_cycle_only(client, db, seed_users):
    today = org_today()
    other, offering = _cycle(db, today - 30 * DAY, today + 200 * DAY, code="OTHER")
    _week_of_slots(db, offering, seed_users["staff"].id)

    cycle, res = _import(client, db, seed_users, _csv())

    assert res.status_code == 200, res.text
    rows = db.query(DailyLedger).all()
    assert len(rows) == 28
    assert {db.get(StructuralMasterSlot, row.master_slot_id).activity.cycle_id for row in rows} == {
        cycle.id
    }
    assert other.id != cycle.id
