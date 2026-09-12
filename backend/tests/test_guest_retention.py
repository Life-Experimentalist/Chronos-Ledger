# Copyright 2026 Chronos Ledger Contributors
# Licensed under the Apache License, Version 2.0
"""A visitor check-in is kept for GUEST_RETENTION_DAYS, then deleted."""

from datetime import UTC, datetime, timedelta

import pytest
from pydantic import ValidationError

from app.core.config import Settings
from app.cron.guest_retention import purge_old_guest_check_ins
from app.models.db import GuestGateRegistry, LogVerificationState


def _check_in(db, days_ago, **fields):
    db.add(
        GuestGateRegistry(
            guest_name=f"Visitor {days_ago}",
            contact_phone="5550100",
            originating_body="Outside",
            target_staff_id="FAC001",
            visitation_intent="A meeting",
            timestamp_marked=datetime.now(UTC) - timedelta(days=days_ago),
            **fields,
        )
    )


def _left(db):
    return sorted(row.guest_name for row in db.query(GuestGateRegistry))


def test_the_purge_takes_check_ins_past_the_window_and_leaves_the_rest(db, seed_users):
    for days_ago in (1, 89, 91):
        _check_in(db, days_ago)
    db.commit()

    assert purge_old_guest_check_ins(db, 90) == 1
    assert _left(db) == ["Visitor 1", "Visitor 89"]


def test_a_decided_check_in_goes_the_same_as_a_pending_one(db, seed_users):
    _check_in(db, 91, handshake_status=LogVerificationState.VERIFIED_APPROVED)
    _check_in(db, 92)
    db.commit()

    assert purge_old_guest_check_ins(db, 90) == 2
    assert _left(db) == []


def test_zero_keeps_every_check_in(db, seed_users):
    _check_in(db, 4000)
    db.commit()

    assert purge_old_guest_check_ins(db, 0) == 0
    assert _left(db) == ["Visitor 4000"]


def test_zero_is_the_default():
    assert Settings().guest_retention_days == 0


def test_a_negative_retention_is_refused_at_startup():
    with pytest.raises(ValidationError, match="GUEST_RETENTION_DAYS"):
        Settings(guest_retention_days=-1)
