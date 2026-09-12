# Copyright 2026 Chronos Ledger Contributors
# Licensed under the Apache License, Version 2.0
"""The six list routes page on request and always say how many rows matched.

Paging is opt-in: with no limit and no offset a route returns every row, as it
always has, so clients written before it keep working. Pages are checked
against the same route's unpaged answer rather than a fixed list of ids, so
the assertions hold whatever order a database would pick if left to itself.
"""

import datetime

import pytest

from app.core.security import hash_password
from app.core.time import org_today
from app.main import settings
from app.models.db import (
    Activity,
    ActivityEnrollment,
    DailyLedger,
    InstitutionalRole,
    PlanningCycle,
    StructuralMasterSlot,
    User,
)
from tests.conftest import ADMIN_PASSWORD, MEMBER_PASSWORD, login

UNIT_ADMIN_PASSWORD = "UnitAdminPass123!"
_UNIT_ADMIN_HASH = hash_password(UNIT_ADMIN_PASSWORD)

# Each list route, and the field that identifies one of its rows.
LISTS = [
    ("/api/v1/users/", "id"),
    ("/api/v1/users/staff/available", "id"),
    ("/api/v1/schedule/cycles", "id"),
    ("/api/v1/schedule/slots", "id"),
    ("/api/v1/schedule/ledger/today", "id"),
    ("/api/v1/schedule/staff/all/locations", "staff_id"),
]


class _FakeRedis:
    """Nobody has set a status override."""

    def mget(self, keys):
        return [None for _ in keys]


@pytest.fixture()
def lists(db, seed_users, monkeypatch):
    """Enough of everything that each list runs to several pages."""
    monkeypatch.setattr("app.api.v1.endpoints.schedule.get_redis", _FakeRedis)
    today = org_today()
    db.add_all(
        [
            User(
                id=f"FAC{n:03}",
                full_name=f"Staff {n}",
                email_address=f"staff{n}@test.internal",
                credential_secure_hash="never-signs-in",
                role_type=InstitutionalRole.STAFF,
                unit_code="CSE" if n % 2 else "ECE",
            )
            for n in range(2, 7)
        ]
    )
    db.add(
        User(
            id="UAD001",
            full_name="CSE Unit Admin",
            email_address="cse.admin@test.internal",
            credential_secure_hash=_UNIT_ADMIN_HASH,
            role_type=InstitutionalRole.UNIT_ADMIN,
            unit_code="CSE",
            initial_login_state=False,
        )
    )
    cycles = [
        PlanningCycle(
            cycle_label=f"Cycle {n}",
            date_bounds_start=today - datetime.timedelta(days=30),
            date_bounds_end=today + datetime.timedelta(days=90),
            operational_status=n == 0,
        )
        for n in range(5)
    ]
    db.add_all(cycles)
    db.flush()
    activities = [
        Activity(
            activity_code=f"ACT{n}",
            activity_title=f"Activity {n}",
            unit_code="CSE",
            cycle_id=cycles[0].id,
        )
        for n in range(5)
    ]
    db.add_all(activities)
    db.flush()
    for n, activity in enumerate(activities):
        db.add(
            StructuralMasterSlot(
                day_of_week_index=n + 1,
                time_window_start=datetime.time(9),
                time_window_end=datetime.time(10),
                activity_id=activity.id,
                primary_lead_id="FAC001",
            )
        )
        db.add(DailyLedger(target_date=today, activity_id=activity.id, active_lead_id="FAC001"))
    # The member is on two of the five, so sees two of today's five days.
    db.add(ActivityEnrollment(activity_id=activities[0].id, member_id="STU001"))
    db.add(ActivityEnrollment(activity_id=activities[1].id, member_id="STU001"))
    db.commit()


def _ids(res, key):
    return [row[key] for row in res.json()]


@pytest.mark.parametrize(("path", "key"), LISTS)
def test_an_unpaged_list_is_every_row_with_the_count(client, lists, path, key):
    headers = login(client, "admin@test.internal", ADMIN_PASSWORD)
    res = client.get(path, headers=headers)
    assert res.status_code == 200
    assert len(res.json()) >= 5
    assert res.headers["X-Total-Count"] == str(len(res.json()))


@pytest.mark.parametrize(("path", "key"), LISTS)
def test_the_pages_put_together_are_the_whole_list(client, lists, path, key):
    headers = login(client, "admin@test.internal", ADMIN_PASSWORD)
    whole = _ids(client.get(path, headers=headers), key)
    paged = []
    for offset in range(0, len(whole), 2):
        res = client.get(path, headers=headers, params={"limit": 2, "offset": offset})
        assert res.status_code == 200
        assert res.headers["X-Total-Count"] == str(len(whole))
        paged += _ids(res, key)
    assert paged == whole


def test_an_offset_on_its_own_skips_that_many_rows(client, lists):
    headers = login(client, "admin@test.internal", ADMIN_PASSWORD)
    whole = _ids(client.get("/api/v1/users/", headers=headers), "id")
    res = client.get("/api/v1/users/", headers=headers, params={"offset": 3})
    assert _ids(res, "id") == whole[3:]
    assert res.headers["X-Total-Count"] == str(len(whole))


def test_an_offset_past_the_end_is_an_empty_page_that_keeps_the_count(client, lists):
    headers = login(client, "admin@test.internal", ADMIN_PASSWORD)
    whole = client.get("/api/v1/users/", headers=headers).json()
    res = client.get("/api/v1/users/", headers=headers, params={"offset": len(whole) + 10})
    assert res.status_code == 200
    assert res.json() == []
    assert res.headers["X-Total-Count"] == str(len(whole))


@pytest.mark.parametrize("params", [{"limit": 0}, {"limit": -1}, {"offset": -1}])
def test_a_limit_below_one_or_a_negative_offset_is_refused(client, lists, params):
    headers = login(client, "admin@test.internal", ADMIN_PASSWORD)
    for path, _ in LISTS:
        assert client.get(path, headers=headers, params=params).status_code == 422, path


def test_a_unit_admins_count_is_their_own_units(client, lists):
    headers = login(client, "cse.admin@test.internal", UNIT_ADMIN_PASSWORD)
    whole = client.get("/api/v1/users/", headers=headers).json()
    assert {user["unit_code"] for user in whole} == {"CSE"}
    res = client.get("/api/v1/users/", headers=headers, params={"limit": 1})
    assert len(res.json()) == 1
    assert res.headers["X-Total-Count"] == str(len(whole))


def test_a_members_count_is_their_own_days(client, lists):
    headers = login(client, "member@test.internal", MEMBER_PASSWORD)
    res = client.get("/api/v1/schedule/ledger/today", headers=headers, params={"limit": 1})
    assert len(res.json()) == 1
    assert res.headers["X-Total-Count"] == "2"


def test_a_page_on_another_allowed_origin_can_read_the_count(client, lists):
    headers = login(client, "admin@test.internal", ADMIN_PASSWORD)
    origin = settings.cors_origins_list[0]
    res = client.get("/api/v1/schedule/cycles", headers={**headers, "Origin": origin})
    assert res.headers["X-Total-Count"] == "5"
    assert "x-total-count" in res.headers["access-control-expose-headers"].lower()
