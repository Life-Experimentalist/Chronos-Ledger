# Copyright 2026 Chronos Ledger Contributors
# SPDX-License-Identifier: Apache-2.0
"""Retries: which failures are tried again, how long they wait, and when they stop."""

from __future__ import annotations

import datetime as dt
import email.utils
import json
import time
from collections.abc import Callable

import httpx
import pytest

import chronos_ledger_client as chronos
from chronos_ledger_client._transport import ChronosTransport, RetryPolicy
from chronos_ledger_client.generated.api.resources import resources_list
from chronos_ledger_client.generated.models import ReservationCreate

BODY = ReservationCreate(date=dt.date(2026, 1, 6), start="14:00", end="15:00", purpose="Viva")
HOLD = {"id": 7, "resource_id": 3}


class Harness:
    """A transport over a scripted server, with a clock that only sleeping moves."""

    def __init__(self, handler: Callable[[httpx.Request], httpx.Response], retry: RetryPolicy | None) -> None:
        self.seen: list[httpx.Request] = []
        self.waits: list[float] = []
        self.now = 1000.0
        self._handler = handler
        self.transport = ChronosTransport(
            base_url="https://c.test",
            user_agent="test",
            api_key="k",
            retry=retry,
            inner=httpx.MockTransport(self._handle),
            sleep=self._sleep,
            clock=lambda: self.now,
            rng=lambda: 1.0,  # the longest wait the jitter allows
        )
        self.http = httpx.Client(transport=self.transport, base_url="https://c.test")

    def _handle(self, request: httpx.Request) -> httpx.Response:
        self.seen.append(request)
        return self._handler(request)

    def _sleep(self, seconds: float) -> None:
        self.waits.append(seconds)
        self.now += seconds

    def keys(self) -> list[str | None]:
        return [r.headers.get("Idempotency-Key") for r in self.seen]


def scripted(*answers: httpx.Response | Exception) -> Callable[[httpx.Request], httpx.Response]:
    queue = list(answers)

    def handle(request: httpx.Request) -> httpx.Response:
        answer = queue.pop(0)
        if isinstance(answer, Exception):
            raise answer
        return answer

    return handle


def test_a_dropped_response_is_retried_and_the_create_goes_out_under_one_key():
    dropped = httpx.ReadError("connection reset")
    harness = Harness(scripted(dropped, httpx.Response(201, json=HOLD)), RetryPolicy())
    client = chronos.Client(base_url="https://c.test", httpx_args={"transport": harness.transport})
    hold = chronos.create_reservation(client, 3, BODY)
    assert hold.id == 7
    assert len(harness.seen) == 2
    first, second = harness.keys()
    assert first and first == second


def test_a_write_the_caller_gave_no_key_gets_one_and_keeps_it_across_retries():
    answers = scripted(httpx.Response(503), httpx.Response(503), httpx.Response(200, json={}))
    harness = Harness(answers, RetryPolicy())
    assert harness.http.post("/api/v1/resources/", json={"code": "R1"}).status_code == 200
    first, second, third = harness.keys()
    assert first and len(first) == 36
    assert first == second == third


@pytest.mark.parametrize("method", ["POST", "PATCH", "PUT", "DELETE"])
def test_no_write_is_ever_sent_without_a_key(method):
    harness = Harness(scripted(httpx.Response(200, json={})), RetryPolicy())
    harness.http.request(method, "/api/v1/resources/1")
    assert harness.keys()[0]


def test_a_key_the_caller_chose_is_kept():
    harness = Harness(scripted(httpx.Response(502), httpx.Response(200, json={})), RetryPolicy())
    harness.http.post("/api/v1/resources/", json={}, headers={"Idempotency-Key": "mine-12345"})
    assert harness.keys() == ["mine-12345", "mine-12345"]


def test_a_read_carries_no_key():
    harness = Harness(scripted(httpx.Response(200, json=[])), RetryPolicy())
    harness.http.get("/api/v1/resources/")
    assert harness.keys() == [None]


@pytest.mark.parametrize("status", [400, 401, 403, 404, 409, 422])
def test_other_client_errors_are_never_retried(status):
    harness = Harness(
        lambda r: httpx.Response(status, json={"detail": "no", "code": "SOME_CODE"}), RetryPolicy()
    )
    with pytest.raises(chronos.ChronosError) as caught:
        harness.http.post("/api/v1/resources/", json={})
    assert caught.value.status == status
    assert len(harness.seen) == 1
    assert harness.waits == []


@pytest.mark.parametrize("status", [429, 502, 503, 504])
def test_the_retryable_statuses_are_retried_for_reads_and_writes(status):
    for method in ("GET", "POST"):
        harness = Harness(scripted(httpx.Response(status), httpx.Response(200, json={})), RetryPolicy())
        assert harness.http.request(method, "/api/v1/resources/").status_code == 200
        assert len(harness.seen) == 2


def test_a_409_while_the_first_request_is_running_is_retried_with_the_same_key():
    running = httpx.Response(409, json={"detail": "still running", "code": "IDEMPOTENCY_KEY_IN_PROGRESS"})
    harness = Harness(scripted(running, httpx.Response(201, json=HOLD)), RetryPolicy())
    assert harness.http.post("/api/v1/resources/", json={}).status_code == 201
    first, second = harness.keys()
    assert first == second


def test_a_503_with_retry_after_waits_that_long():
    answers = scripted(httpx.Response(503, headers={"Retry-After": "7"}), httpx.Response(200, json={}))
    harness = Harness(answers, RetryPolicy())
    harness.http.get("/api/v1/resources/")
    assert harness.waits == [7.0]


def test_retry_after_as_an_http_date_is_honoured():
    # retry_after reads the real wall clock, so the wait is a little under 5 s.
    later = email.utils.formatdate(time.time() + 5, usegmt=True)
    answers = scripted(httpx.Response(429, headers={"Retry-After": later}), httpx.Response(200, json={}))
    harness = Harness(answers, RetryPolicy())
    harness.http.get("/api/v1/resources/")
    (wait,) = harness.waits
    assert 3.0 < wait <= 5.0


def test_a_retry_after_past_the_deadline_ends_retrying_with_the_last_error():
    answer = httpx.Response(
        429, json={"detail": "slow", "code": "RATE_LIMITED"}, headers={"Retry-After": "60"}
    )
    harness = Harness(lambda r: answer, RetryPolicy(deadline=30.0))
    with pytest.raises(chronos.ChronosError) as caught:
        harness.http.get("/api/v1/resources/")
    assert (caught.value.status, caught.value.code) == (429, "RATE_LIMITED")
    assert len(harness.seen) == 1
    assert harness.waits == []


def test_backoff_is_full_jitter_over_a_doubling_ceiling_capped_by_max_delay():
    policy = RetryPolicy(max_attempts=6, base_delay=0.25, max_delay=1.0, deadline=1000.0)
    harness = Harness(lambda r: httpx.Response(503), policy)
    with pytest.raises(chronos.ChronosError):
        harness.http.get("/api/v1/resources/")
    # rng() is 1.0, so each wait is its ceiling: 0.25, 0.5, then capped at 1.0.
    assert harness.waits == [0.25, 0.5, 1.0, 1.0, 1.0]
    half = Harness(lambda r: httpx.Response(503), policy)
    half.transport._rng = lambda: 0.5
    with pytest.raises(chronos.ChronosError):
        half.http.get("/api/v1/resources/")
    assert half.waits == [0.125, 0.25, 0.5, 0.5, 0.5]


def test_the_deadline_stops_retrying_before_the_attempts_run_out():
    policy = RetryPolicy(max_attempts=10, base_delay=4.0, max_delay=8.0, deadline=10.0)
    harness = Harness(lambda r: httpx.Response(503, json={"detail": "down"}), policy)
    with pytest.raises(chronos.ChronosError) as caught:
        harness.http.get("/api/v1/resources/")
    assert caught.value.status == 503
    # Waits of 4 s and 8 s: the first fits in 10 s, the second would end at 12 s.
    assert harness.waits == [4.0]
    assert len(harness.seen) == 2


def test_attempts_run_out_and_the_last_error_is_raised():
    harness = Harness(
        lambda r: httpx.Response(502, json={"detail": "bad gateway"}), RetryPolicy(max_attempts=3)
    )
    with pytest.raises(chronos.ChronosError) as caught:
        harness.http.get("/api/v1/resources/")
    assert caught.value.status == 502
    assert caught.value.detail == "bad gateway"
    assert len(harness.seen) == 3


def test_transport_errors_are_raised_as_they_came_when_attempts_run_out():
    def refuse(request: httpx.Request) -> httpx.Response:
        raise httpx.ConnectTimeout("timed out", request=request)

    harness = Harness(refuse, RetryPolicy(max_attempts=2))
    with pytest.raises(httpx.ConnectTimeout):
        harness.http.get("/api/v1/resources/")
    assert len(harness.seen) == 2


def test_none_turns_retries_off_but_a_write_still_carries_a_key():
    harness = Harness(lambda r: httpx.Response(503, json={"detail": "down"}), None)
    with pytest.raises(chronos.ChronosError):
        harness.http.post("/api/v1/resources/", json={})
    assert len(harness.seen) == 1
    assert harness.keys()[0]


def test_connect_passes_the_policy_to_the_transport():
    answers = scripted(httpx.Response(503), httpx.Response(503), httpx.Response(200, json=[]))
    seen: list[httpx.Request] = []

    def handle(request: httpx.Request) -> httpx.Response:
        seen.append(request)
        return answers(request)

    client = chronos.connect(
        "https://c.test",
        api_key="k",
        retry=chronos.RetryPolicy(max_attempts=3, base_delay=0.0),
        transport=httpx.MockTransport(handle),
    )
    assert resources_list.sync(client=client) == []
    assert len(seen) == 3


def test_a_policy_with_no_attempts_is_refused():
    with pytest.raises(ValueError):
        RetryPolicy(max_attempts=0)
    with pytest.raises(ValueError):
        RetryPolicy(base_delay=-1)


def test_the_retried_body_is_the_same_body():
    harness = Harness(scripted(httpx.Response(503), httpx.Response(200, json={})), RetryPolicy())
    harness.http.post("/api/v1/resources/", json={"code": "R1"})
    assert [json.loads(r.content) for r in harness.seen] == [{"code": "R1"}, {"code": "R1"}]
