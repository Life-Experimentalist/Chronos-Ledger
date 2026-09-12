# Copyright 2026 Chronos Ledger Contributors
# Licensed under the Apache License, Version 2.0
"""An event or a close reaches a socket on another instance, through Redis.

Two brokers stand in for two instances, each running its relay against one fake
Redis they share. As far as the relay is concerned Redis is a channel and a few
sets, and CI has no real one to point at.
"""

import asyncio
import contextlib
import json
import logging

import pytest
import redis

from app.core import websocket_manager
from app.core.websocket_manager import CHANNEL, OrganizationConnectionManager

EVENT = {"event": "ABSENCE_DECISION", "payload": {"log_id": 1, "decision": "APPROVED"}}


class _Hub:
    """The one Redis every instance talks to."""

    def __init__(self):
        self.subscribers: list[asyncio.Queue] = []
        self.sets: dict[str, set] = {}
        self.fails_with: Exception | None = None
        self.refusals = 0


class _FakeRedis:
    def __init__(self, hub):
        self.hub = hub

    async def publish(self, channel, data):
        if self.hub.fails_with:
            raise self.hub.fails_with
        for queue in self.hub.subscribers:
            queue.put_nowait({"type": "message", "channel": channel, "data": data})

    def pubsub(self):
        return _FakePubSub(self.hub)

    def pipeline(self, transaction=True):
        return _FakePipeline(self.hub)

    async def scan_iter(self, match):
        for key in list(self.hub.sets):
            if key.startswith(match.rstrip("*")):
                yield key

    async def sunion(self, keys):
        return set().union(*(self.hub.sets.get(key, set()) for key in keys))

    async def delete(self, key):
        self.hub.sets.pop(key, None)

    async def aclose(self):
        pass


class _FakePubSub:
    def __init__(self, hub):
        self.hub = hub
        self.queue = None

    async def __aenter__(self):
        return self

    async def __aexit__(self, *exc):
        if self.queue in self.hub.subscribers:
            self.hub.subscribers.remove(self.queue)

    async def subscribe(self, channel):
        if self.hub.refusals:
            self.hub.refusals -= 1
            raise redis.ConnectionError("Connection refused")
        self.queue = asyncio.Queue()
        self.hub.subscribers.append(self.queue)

    async def get_message(self, ignore_subscribe_messages, timeout):
        try:
            return await asyncio.wait_for(self.queue.get(), timeout)
        except TimeoutError:
            return None


class _FakePipeline:
    def __init__(self, hub):
        self.hub = hub
        self.writes = []

    async def __aenter__(self):
        return self

    async def __aexit__(self, *exc):
        pass

    def delete(self, key):
        self.writes.append(lambda: self.hub.sets.pop(key, None))

    def sadd(self, key, *members):
        self.writes.append(lambda: self.hub.sets.setdefault(key, set()).update(members))

    def expire(self, key, seconds):
        pass

    async def execute(self):
        for write in self.writes:
            write()


class _Socket:
    def __init__(self):
        self.sent = []
        self.closed_with = None

    async def send_text(self, frame):
        self.sent.append(json.loads(frame))

    async def close(self, code):
        self.closed_with = code


@pytest.fixture()
def hub(monkeypatch):
    shared = _Hub()
    monkeypatch.setattr(websocket_manager.aioredis, "from_url", lambda url, **_: _FakeRedis(shared))
    monkeypatch.setattr(websocket_manager, "RETRY_SECONDS", 0.01)
    return shared


async def _until(condition):
    """Give the relays a moment, and fail if the condition never comes true."""
    for _ in range(200):
        if condition():
            return
        await asyncio.sleep(0.005)
    raise AssertionError("the relay never got there")


@contextlib.asynccontextmanager
async def _running(*brokers):
    tasks = [asyncio.create_task(broker.run_relay("redis://hub")) for broker in brokers]
    try:
        await _until(lambda: all(broker._client is not None for broker in brokers))
        yield
    finally:
        for task in tasks:
            task.cancel()
        await asyncio.gather(*tasks, return_exceptions=True)


def _published_by_another_instance(hub, message):
    return _FakeRedis(hub).publish(CHANNEL, json.dumps({"origin": "elsewhere", **message}))


def _events(socket):
    return [frame["event"] for frame in socket.sent]


def test_an_event_reaches_a_socket_on_the_other_instance(hub):
    async def scenario():
        a, b = OrganizationConnectionManager(), OrganizationConnectionManager()
        socket = _Socket()
        b.register_session("STU001", socket)
        async with _running(a, b):
            await a.forward_direct_message("STU001", EVENT["event"], EVENT["payload"])
            await _until(lambda: socket.sent)
        assert socket.sent == [EVENT]

    asyncio.run(scenario())


def test_a_socket_on_the_sending_instance_gets_the_event_once(hub):
    """The instance that sent it hears its own message back, and skips it.

    B's event is published after A's, so by the time it has arrived A's echo
    has been through the relay: had it been delivered it would sit between them.
    """

    async def scenario():
        a, b = OrganizationConnectionManager(), OrganizationConnectionManager()
        socket = _Socket()
        a.register_session("STU001", socket)
        async with _running(a, b):
            await a.forward_direct_message("STU001", "FIRST", {})
            await b.forward_direct_message("STU001", "SECOND", {})
            await _until(lambda: len(socket.sent) >= 2)
        assert [frame["event"] for frame in socket.sent] == ["FIRST", "SECOND"]

    asyncio.run(scenario())


def test_a_close_reaches_a_socket_on_the_other_instance(hub):
    async def scenario():
        a, b = OrganizationConnectionManager(), OrganizationConnectionManager()
        socket = _Socket()
        b.register_session("STU001", socket)
        async with _running(a, b):
            await a.close_session("STU001", 4003)
            await _until(lambda: socket.closed_with is not None)
        assert socket.closed_with == 4003
        assert not b.is_online("STU001")

    asyncio.run(scenario())


def test_a_broadcast_reaches_every_instance_once(hub):
    """Each instance hears its own broadcast back and skips it.

    The closing marker is published after both broadcasts, so once it has
    reached both sockets every echo ahead of it has been through both relays.
    An instance's own broadcast lands before the other's, so order is not
    what is checked.
    """

    async def scenario():
        a, b = OrganizationConnectionManager(), OrganizationConnectionManager()
        here, there = _Socket(), _Socket()
        a.register_session("STU001", here)
        b.register_session("FAC001", there)
        async with _running(a, b):
            await a.broadcast_global_event("FROM_A", {})
            await b.broadcast_global_event("FROM_B", {})
            await _published_by_another_instance(hub, {"to": None, "event": "DONE", "payload": {}})
            await _until(lambda: "DONE" in _events(here) and "DONE" in _events(there))
        assert sorted(_events(here)) == ["DONE", "FROM_A", "FROM_B"]
        assert sorted(_events(there)) == ["DONE", "FROM_A", "FROM_B"]

    asyncio.run(scenario())


def test_a_failed_publish_still_reaches_the_sockets_here(hub):
    async def scenario():
        a = OrganizationConnectionManager()
        socket = _Socket()
        a.register_session("STU001", socket)
        async with _running(a):
            hub.fails_with = redis.ConnectionError("Connection reset by peer")
            await a.forward_direct_message("STU001", EVENT["event"], EVENT["payload"])
            await a.close_session("STU001", 4003)
        assert socket.sent == [EVENT]
        assert socket.closed_with == 4003

    asyncio.run(scenario())


def test_the_count_is_distinct_people_on_every_instance(hub):
    async def scenario():
        a, b = OrganizationConnectionManager(), OrganizationConnectionManager()
        a.register_session("STU001", _Socket())
        b.register_session("STU001", _Socket())
        b.register_session("FAC001", _Socket())
        async with _running(a, b):
            assert await a.online_count() == 2
            assert await b.online_count() == 2

    asyncio.run(scenario())


def test_the_count_reads_this_instances_own_people_from_its_dict(hub):
    """Its own key can be a refresh old, and would still count a socket that
    closed a moment ago."""

    async def scenario():
        a = OrganizationConnectionManager()
        a.register_session("STU001", _Socket())
        async with _running(a):
            a.terminate_session("STU001")
            assert await a.online_count() == 0

    asyncio.run(scenario())


def test_an_instance_that_stops_takes_its_people_out_of_the_count(hub):
    async def scenario():
        a, b = OrganizationConnectionManager(), OrganizationConnectionManager()
        a.register_session("STU001", _Socket())
        async with _running(b):
            async with _running(a):
                assert await b.online_count() == 1
            assert await b.online_count() == 0

    asyncio.run(scenario())


def test_without_the_relay_the_count_is_this_instances_own(hub):
    broker = OrganizationConnectionManager()
    broker.register_session("STU001", _Socket())
    broker.register_session("FAC001", _Socket())
    assert asyncio.run(broker.online_count()) == 2


def test_the_relay_comes_back_when_redis_does(hub, caplog):
    caplog.set_level(logging.INFO, logger=websocket_manager.__name__)
    hub.refusals = 3

    async def scenario():
        a = OrganizationConnectionManager()
        socket = _Socket()
        a.register_session("STU001", socket)
        async with _running(a):
            await _published_by_another_instance(hub, {"to": "STU001", **EVENT})
            await _until(lambda: socket.sent)
        assert socket.sent == [EVENT]

    asyncio.run(scenario())
    lost = [r for r in caplog.records if "cannot reach Redis" in r.getMessage()]
    back = [r for r in caplog.records if "reconnected" in r.getMessage()]
    assert len(lost) == 1
    assert len(back) == 1


def test_a_malformed_message_is_dropped_and_the_relay_carries_on(hub):
    async def scenario():
        a = OrganizationConnectionManager()
        socket = _Socket()
        a.register_session("STU001", socket)
        async with _running(a):
            publisher = _FakeRedis(hub)
            await publisher.publish(CHANNEL, "not json")
            await publisher.publish(CHANNEL, json.dumps(["a", "list"]))
            await publisher.publish(CHANNEL, json.dumps({"origin": "elsewhere"}))
            await _published_by_another_instance(hub, {"to": "STU001", **EVENT})
            await _until(lambda: socket.sent)
        assert socket.sent == [EVENT]

    asyncio.run(scenario())
