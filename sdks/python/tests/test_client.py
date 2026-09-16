# Copyright 2026 Chronos Ledger Contributors
# SPDX-License-Identifier: Apache-2.0

from __future__ import annotations

import datetime as dt
import email.utils
import json
import threading
import time
from collections.abc import Callable

import httpx
import pytest

import chronos_ledger_client as chronos
from chronos_ledger_client._transport import ChronosTransport, retry_after
from chronos_ledger_client.generated.api.resources import resources_list
from chronos_ledger_client.generated.api.users import users_list
from chronos_ledger_client.generated.models import ReservationCreate

BODY = ReservationCreate(date=dt.date(2026, 1, 6), start="14:00", end="15:00", purpose="Viva")


class Server:
    """A MockTransport that records every request."""

    def __init__(self, handler: Callable[[httpx.Request], httpx.Response]) -> None:
        self.seen: list[httpx.Request] = []
        self._handler = handler
        self._lock = threading.Lock()
        self.transport = httpx.MockTransport(self._handle)

    def _handle(self, request: httpx.Request) -> httpx.Response:
        with self._lock:
            self.seen.append(request)
        return self._handler(request)


def client(server: Server, **kwargs) -> chronos.Client:
    c = chronos.connect("https://c.test/api/v1/", transport=server.transport, **kwargs)
    # Swap the real sleep for a recorder so retries run instantly.
    transport = c.get_httpx_client()._transport
    assert isinstance(transport, ChronosTransport)
    transport.waits = []
    transport._sleep = transport.waits.append
    return c


def test_api_key_goes_out_as_x_api_key_with_the_user_agent():
    server = Server(lambda r: httpx.Response(200, json=[]))
    assert resources_list.sync(client=client(server, api_key="k1")) == []
    (request,) = server.seen
    assert str(request.url) == "https://c.test/api/v1/resources/"
    assert request.headers["X-API-Key"] == "k1"
    assert request.headers["User-Agent"] == f"chronos-python/{chronos.__version__}"
    assert "Authorization" not in request.headers


def test_a_401_refreshes_once_stores_the_pair_and_repeats_the_call():
    def handle(request: httpx.Request) -> httpx.Response:
        if request.url.path.endswith("/auth/refresh"):
            assert json.loads(request.content) == {"refresh_token": "r1"}
            return httpx.Response(200, json={"access_token": "a2", "refresh_token": "r2"})
        if request.headers.get("Authorization") == "Bearer a2":
            return httpx.Response(200, json=[])
        return httpx.Response(401, json={"detail": "expired"})

    server = Server(handle)
    stored: list[chronos.Tokens] = []
    c = client(server, tokens=chronos.Tokens("a1", "r1"), on_tokens=stored.append)
    assert resources_list.sync(client=c) == []
    assert stored == [chronos.Tokens("a2", "r2")]
    assert len(server.seen) == 3


def test_a_refused_refresh_ends_in_the_original_401():
    server = Server(lambda r: httpx.Response(401, json={"detail": "Not authorized."}))
    with pytest.raises(chronos.ChronosError) as caught:
        resources_list.sync(client=client(server, tokens=chronos.Tokens("a", "r")))
    assert caught.value.status == 401
    assert caught.value.detail == "Not authorized."
    assert len(server.seen) == 2


def test_threads_that_see_a_401_together_spend_the_refresh_token_once():
    refreshes = []

    def handle(request: httpx.Request) -> httpx.Response:
        if request.url.path.endswith("/auth/refresh"):
            refreshes.append(1)
            time.sleep(0.05)
            return httpx.Response(200, json={"access_token": "a2", "refresh_token": "r2"})
        if request.headers.get("Authorization") == "Bearer a2":
            return httpx.Response(200, json=[])
        time.sleep(0.02)
        return httpx.Response(401, json={"detail": "expired"})

    c = client(Server(handle), tokens=chronos.Tokens("a1", "r1"))
    results = []
    threads = [
        threading.Thread(target=lambda: results.append(resources_list.sync(client=c))) for _ in range(4)
    ]
    for t in threads:
        t.start()
    for t in threads:
        t.join()
    assert results == [[], [], [], []]
    assert len(refreshes) == 1


def test_a_429_waits_for_retry_after_then_succeeds():
    answers = iter([httpx.Response(429, headers={"Retry-After": "2"}), httpx.Response(200, json=[])])
    c = client(Server(lambda r: next(answers)), api_key="k")
    assert resources_list.sync(client=c) == []
    assert c.get_httpx_client()._transport.waits == [2.0]


def test_retries_stop_after_max_retries_and_raise_the_last_error():
    server = Server(lambda r: httpx.Response(503, json={"detail": "down"}))
    with pytest.raises(chronos.ChronosError) as caught:
        resources_list.sync(client=client(server, api_key="k", max_retries=2))
    assert caught.value.status == 503
    assert len(server.seen) == 3


def test_connection_errors_are_retried_for_reads():
    calls = []

    def handle(request: httpx.Request) -> httpx.Response:
        calls.append(1)
        if len(calls) == 1:
            raise httpx.ConnectError("refused", request=request)
        return httpx.Response(200, json=[])

    assert resources_list.sync(client=client(Server(handle), api_key="k")) == []
    assert len(calls) == 2


def test_a_post_without_an_idempotency_key_is_never_retried():
    server = Server(lambda r: httpx.Response(503, json={"detail": "down"}))
    c = client(server, api_key="k")
    with pytest.raises(chronos.ChronosError):
        c.get_httpx_client().post("/api/v1/resources/", json={})
    assert len(server.seen) == 1


def test_create_reservation_makes_one_key_and_sends_it_again_on_a_retry():
    answers = iter([httpx.Response(502), httpx.Response(201, json={"id": 7, "resource_id": 3})])
    server = Server(lambda r: next(answers))
    hold = chronos.create_reservation(client(server, api_key="k"), 3, BODY)
    assert hold.id == 7
    first, second = (r.headers["Idempotency-Key"] for r in server.seen)
    assert len(first) == 36
    assert first == second
    assert json.loads(server.seen[1].content) == {
        "date": "2026-01-06",
        "start": "14:00",
        "end": "15:00",
        "purpose": "Viva",
    }


def test_a_409_carries_the_conflicts_it_names():
    busy = [{"date": "2026-01-06", "start": "14:00", "end": "15:00", "reservation_id": 4}]
    detail = {"message": "the resource is already taken", "conflicts": busy}
    server = Server(lambda r: httpx.Response(409, json={"detail": detail}))
    with pytest.raises(chronos.ChronosError) as caught:
        chronos.create_reservation(client(server, api_key="k"), 3, BODY, idempotency_key="key-12345")
    assert caught.value.status == 409
    assert str(caught.value) == "409: the resource is already taken"
    assert caught.value.conflicts == busy
    assert server.seen[0].headers["Idempotency-Key"] == "key-12345"


def test_paginate_walks_limit_and_offset_until_x_total_count():
    rows = [{"id": str(i)} for i in range(5)]

    def handle(request: httpx.Request) -> httpx.Response:
        limit = int(request.url.params["limit"])
        offset = int(request.url.params["offset"])
        return httpx.Response(200, json=rows[offset : offset + limit], headers={"X-Total-Count": "5"})

    server = Server(handle)
    ids = [u.id for u in chronos.paginate(users_list, client=client(server, api_key="k"), page_size=2)]
    assert ids == ["0", "1", "2", "3", "4"]
    assert len(server.seen) == 3


def test_retry_after_reads_seconds_and_http_dates():
    assert retry_after(httpx.Response(429, headers={"Retry-After": "3"})) == 3.0
    later = email.utils.formatdate(time.time() + 5, usegmt=True)
    assert 3.0 < retry_after(httpx.Response(429, headers={"Retry-After": later})) <= 5.0
    assert retry_after(httpx.Response(429)) is None


def test_a_non_json_error_body_is_kept_as_text():
    server = Server(lambda r: httpx.Response(400, text="<html>bad gateway</html>"))
    with pytest.raises(chronos.ChronosError) as caught:
        resources_list.sync(client=client(server, api_key="k"))
    assert caught.value.detail == "<html>bad gateway</html>"


def test_api_key_and_tokens_together_are_refused():
    with pytest.raises(ValueError):
        chronos.connect("https://c.test", api_key="k", tokens=chronos.Tokens("a", "r"))
