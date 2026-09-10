# Copyright 2026 Chronos Ledger Contributors
# Licensed under the Apache License, Version 2.0
"""A budget per caller on sign-in, the visitor kiosk and the calendar feed.

The rest of the suite runs with the limiter off (see the session fixture in
conftest), so everything here switches it back on for one test at a time and
points it at a Redis that lives in a dictionary.
"""

import pytest
import redis

from app.core.config import get_settings
from app.models.db import User
from tests.conftest import MEMBER_PASSWORD

# ── The fake ───────────────────────────────────────────────────────────────


class _FakePipeline:
    """redis-py queues commands and returns their results from execute() in
    order, which is the only part of a pipeline the limiter depends on."""

    def __init__(self, client):
        self.client = client
        self.queued = []

    def get(self, key):
        self.queued.append(("get", key))
        return self

    def incr(self, key):
        self.queued.append(("incr", key))
        return self

    def ttl(self, key):
        self.queued.append(("ttl", key))
        return self

    def execute(self):
        queued, self.queued = self.queued, []
        return [getattr(self.client, name)(key) for name, key in queued]


class _FakeRedis:
    def __init__(self, fails_with=None):
        self.counts = {}
        self.expiries = {}
        self.fails_with = fails_with

    def _maybe_fail(self):
        if self.fails_with is not None:
            raise self.fails_with

    def get(self, key):
        self._maybe_fail()
        value = self.counts.get(key)
        # The real client with decode_responses=True hands back a string.
        return None if value is None else str(value)

    def incr(self, key):
        self._maybe_fail()
        self.counts[key] = self.counts.get(key, 0) + 1
        return self.counts[key]

    def ttl(self, key):
        self._maybe_fail()
        if key not in self.counts:
            return -2  # no such key
        return self.expiries.get(key, -1)  # -1 is "exists, never expires"

    def expire(self, key, seconds):
        self._maybe_fail()
        self.expiries[key] = seconds
        return True

    def pipeline(self):
        return _FakePipeline(self)


@pytest.fixture
def limiter(monkeypatch):
    """Turn the limiter on for one test, sized by the caller.

    Same shape as the password_floor fixture: get_settings is lru_cached, so
    the cache is dropped going in and coming out. Coming out matters more, or
    a limit left cached would follow every test that ran after this one.
    """

    def enable(fails_with=None, **counts):
        monkeypatch.setenv("RATE_LIMIT_ENABLED", "true")
        for name, value in counts.items():
            monkeypatch.setenv(name.upper(), str(value))
        get_settings.cache_clear()
        fake = _FakeRedis(fails_with=fails_with)
        monkeypatch.setattr("app.core.rate_limit.get_redis", lambda: fake)
        return fake

    yield enable
    get_settings.cache_clear()


def _sign_in(client, email="member@test.internal", password=MEMBER_PASSWORD):
    return client.post("/api/v1/auth/login", json={"email": email, "password": password})


# ── Sign-in ────────────────────────────────────────────────────────────────


def test_the_attempt_past_the_budget_is_refused(client, seed_users, limiter):
    limiter(rate_limit_login_per_ip=3, rate_limit_login_per_email=0)

    for _ in range(3):
        assert _sign_in(client, password="wrong").status_code == 401

    refused = _sign_in(client, password="wrong")
    assert refused.status_code == 429
    # Without this a client has no way to know when to come back, and the
    # answer is guessed as "immediately" by everything that retries.
    assert int(refused.headers["Retry-After"]) > 0


def test_a_correct_password_never_costs_the_budget(client, seed_users, limiter):
    """Otherwise a shared address locks out the people using it correctly."""
    limiter(rate_limit_login_per_ip=2, rate_limit_login_per_email=0)

    for _ in range(5):
        assert _sign_in(client).status_code == 200


def test_the_two_budgets_are_counted_separately(client, seed_users, limiter):
    """The address budget alone lets a botnet through; the account budget
    alone lets one machine work through a list of accounts."""
    limiter(rate_limit_login_per_ip=0, rate_limit_login_per_email=2)

    for _ in range(2):
        assert _sign_in(client, password="wrong").status_code == 401
    assert _sign_in(client, password="wrong").status_code == 429

    # A different account, same address, and the address budget is off: the
    # account budget is genuinely per account.
    assert _sign_in(client, email="staff@test.internal", password="wrong").status_code == 401


def test_the_budget_is_not_an_account_existence_oracle(client, seed_users, limiter):
    """An address nobody holds has to run out at the same attempt a real one
    does, or the 429 answers the question the 401 was careful not to."""
    limiter(rate_limit_login_per_ip=0, rate_limit_login_per_email=2)

    for _ in range(2):
        assert _sign_in(client, email="nobody@test.internal", password="wrong").status_code == 401
    assert _sign_in(client, email="nobody@test.internal", password="wrong").status_code == 429


def test_redis_being_down_does_not_stop_anyone_signing_in(client, seed_users, limiter):
    """Redis is a cache here, not a system of record. An instance that cannot
    reach it should keep letting people in rather than lock the organization
    out until it comes back."""
    limiter(fails_with=redis.ConnectionError("no route to host"), rate_limit_login_per_ip=1)

    for _ in range(3):
        assert _sign_in(client, password="wrong").status_code == 401
    assert _sign_in(client).status_code == 200


def test_a_count_of_zero_turns_that_limiter_off(client, seed_users, limiter):
    limiter(rate_limit_login_per_ip=0, rate_limit_login_per_email=0)

    for _ in range(12):
        assert _sign_in(client, password="wrong").status_code == 401


def test_the_limiter_is_off_when_the_setting_says_so(client, seed_users, limiter, monkeypatch):
    limiter(rate_limit_login_per_ip=1)
    monkeypatch.setenv("RATE_LIMIT_ENABLED", "false")
    get_settings.cache_clear()

    for _ in range(4):
        assert _sign_in(client, password="wrong").status_code == 401


# ── The kiosk and the feed ─────────────────────────────────────────────────

_GUEST = {
    "guest_name": "Ravi Verma",
    "contact_phone": "9000000000",
    "originating_body": "Acme Corp",
    "target_staff_id": "FAC001",
    "visitation_intent": "Project discussion",
}


def test_a_kiosk_runs_out_of_check_ins(client, seed_users, kiosk_key, limiter):
    limiter(rate_limit_guest_checkin=2)

    for _ in range(2):
        res = client.post("/api/v1/guest/register-checkin", json=_GUEST, headers=kiosk_key)
        assert res.status_code == 200, res.text

    refused = client.post("/api/v1/guest/register-checkin", json=_GUEST, headers=kiosk_key)
    assert refused.status_code == 429
    assert int(refused.headers["Retry-After"]) > 0


def test_a_calendar_feed_runs_out_of_fetches(client, db, seed_users, limiter):
    limiter(rate_limit_calendar_feed=2)
    token = db.query(User).filter(User.id == "STU001").first().calendar_feed_token

    for _ in range(2):
        assert client.get(f"/api/v1/sync/user-feed/{token}.ics").status_code == 200

    refused = client.get(f"/api/v1/sync/user-feed/{token}.ics")
    assert refused.status_code == 429


def test_a_feed_token_that_matches_nobody_still_counts(client, seed_users, limiter):
    """The 404 costs a query like any other request, and a budget that only
    applies to tokens that resolve is a free way to find out which do."""
    limiter(rate_limit_calendar_feed=2)

    for _ in range(2):
        assert client.get("/api/v1/sync/user-feed/NOBODY.ics").status_code == 404
    assert client.get("/api/v1/sync/user-feed/NOBODY.ics").status_code == 429


# ── The timing leak ────────────────────────────────────────────────────────


def test_a_missing_account_is_still_compared_against_a_hash(client, seed_users, monkeypatch):
    """A sign-in for an account that does not exist has to do the same work as
    one for an account with the wrong password. Skipping the comparison sorts
    real addresses from invented ones by response time alone, which is a thing
    that can be measured over a network."""
    compared = []
    import app.api.v1.endpoints.auth as auth_module

    real = auth_module.verify_password
    monkeypatch.setattr(
        auth_module,
        "verify_password",
        lambda plain, stored: compared.append(stored) or real(plain, stored),
    )

    assert _sign_in(client, email="nobody@test.internal", password="wrong").status_code == 401
    assert compared == [auth_module.ABSENT_ACCOUNT_HASH]
