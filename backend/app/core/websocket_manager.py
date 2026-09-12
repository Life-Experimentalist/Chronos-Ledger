# Copyright 2026 Chronos Ledger Contributors
# Licensed under the Apache License, Version 2.0
"""Who has a socket open, and getting an event to them whichever instance holds it.

Each instance keeps the sockets it accepted in a dict and writes to those
directly. Behind a load balancer the person an event is for may be connected to
a different instance, so every instance also publishes what it delivers on a
Redis channel, and delivers what the others publish to the sockets it holds. A
deactivation's close travels the same way.

Local delivery happens first and does not wait on Redis. With Redis down, or
the relay between reconnects, an instance still reaches its own sockets the way
a single instance always has, and only the other instances' sockets miss out
until it is back. Each message carries the id of the instance that sent it and
an instance skips its own, so a socket here never gets one event twice.

Who is connected is kept the same way: each instance writes the ids it holds to
a set of its own, under a key that expires, and rewrites it every few seconds.
An instance that dies stops rewriting, and its key lapses rather than leaving
its people counted as online.

Redis is inside the trust boundary here, as it already is for the status
overrides: whatever can publish on the channel can send a connected person a
frame or close their socket.
"""

import asyncio
import contextlib
import json
import logging
import uuid

import redis
import redis.asyncio as aioredis
from fastapi import WebSocket

log = logging.getLogger(__name__)

CHANNEL = "ws:events"
PRESENCE_PREFIX = "ws:online:"
# Not settings: they are the shape of the relay rather than a policy, the same
# way the handshake timeout and the rate limiter's windows are. A key survives
# two missed rewrites before it lapses.
PRESENCE_REFRESH_SECONDS = 15
PRESENCE_TTL_SECONDS = 45
RETRY_SECONDS = 5


class OrganizationConnectionManager:
    def __init__(self):
        self.active_sockets: dict[str, WebSocket] = {}
        # Tells this instance's messages apart from everybody else's.
        self.instance_id = uuid.uuid4().hex
        # The relay's Redis client while it is connected, and None otherwise:
        # never started (tests, a script) or Redis unreachable. While it is
        # None nothing is published and the count is this instance's own.
        self._client: aioredis.Redis | None = None

    def register_session(self, user_id: str, websocket: WebSocket):
        """Take a socket that is already accepted and already identified.

        The accept used to happen here, which meant a socket was registered
        before anything had established who was on the other end of it. The
        route accepts now, because the token arrives in a frame after the
        handshake, and only calls this once that frame has checked out.
        """
        self.active_sockets[user_id] = websocket

    def terminate_session(self, user_id: str, websocket: WebSocket | None = None):
        # A reconnect replaces the stored socket; when the stale connection
        # then closes, it must not evict the replacement.
        if websocket is not None and self.active_sockets.get(user_id) is not websocket:
            return
        self.active_sockets.pop(user_id, None)

    async def close_session(self, user_id: str, code: int):
        """Close the socket this user has open, on whichever instance holds it.

        A socket is checked once, when it connects, so revoking the account
        does not reach one already open until this closes it.
        """
        await self._close_here(user_id, code)
        await self._publish({"to": user_id, "close": code})

    async def forward_direct_message(self, recipient_id: str, event_type: str, data_payload: dict):
        await self._deliver_here(recipient_id, event_type, data_payload)
        await self._publish({"to": recipient_id, "event": event_type, "payload": data_payload})

    async def broadcast_global_event(self, event_type: str, data_payload: dict):
        await self._broadcast_here(event_type, data_payload)
        await self._publish({"to": None, "event": event_type, "payload": data_payload})

    async def online_count(self) -> int:
        """How many people have a socket open, on every instance.

        A person connected to two instances is counted once. The other
        instances' figures are as of their last rewrite, so up to
        PRESENCE_REFRESH_SECONDS old; this instance's come from its dict rather
        than its own key, which can be as old. Without the relay, this
        instance counts its own.
        """
        here = set(self.active_sockets)
        client = self._client
        if client is None:
            return len(here)
        own = self._presence_key()
        try:
            keys = [
                key async for key in client.scan_iter(match=f"{PRESENCE_PREFIX}*") if key != own
            ]
            elsewhere = await client.sunion(keys) if keys else set()
        except (redis.RedisError, OSError) as unreachable:
            log.warning("websocket count is this instance's alone: %s", unreachable)
            return len(here)
        return len(here | elsewhere)

    def is_online(self, user_id: str) -> bool:
        """Whether this user has a socket open on this instance.

        Only this one. Nothing in the app asks, and online_count is the figure
        that covers every instance.
        """
        return user_id in self.active_sockets

    async def run_relay(self, redis_url: str):
        """Relay messages between instances and keep this one's presence current.

        Runs for as long as the process does, from the app's lifespan, and
        stops only when cancelled. An unreachable Redis is retried every
        RETRY_SECONDS, with one warning when it goes and one line when it is
        back rather than a line for every attempt.
        """
        loop = asyncio.get_running_loop()
        down = False
        while True:
            # Made here rather than at import: a client's connections belong to
            # the event loop that opened them.
            client = aioredis.from_url(
                redis_url,
                decode_responses=True,
                socket_connect_timeout=RETRY_SECONDS,
                socket_timeout=RETRY_SECONDS,
                health_check_interval=30,
            )
            try:
                async with client.pubsub() as pubsub:
                    await pubsub.subscribe(CHANNEL)
                    self._client = client
                    if down:
                        log.info("websocket relay reconnected to Redis")
                        down = False
                    due = loop.time()
                    while True:
                        if loop.time() >= due:
                            await self._write_presence(client)
                            due = loop.time() + PRESENCE_REFRESH_SECONDS
                        message = await pubsub.get_message(
                            ignore_subscribe_messages=True, timeout=max(0.0, due - loop.time())
                        )
                        if message is not None:
                            await self._relay(message["data"])
            except (redis.RedisError, OSError) as unreachable:
                self._client = None
                if not down:
                    log.warning(
                        "websocket relay cannot reach Redis, so events reach only the "
                        "sockets on this instance until it can: %s",
                        unreachable,
                    )
                    down = True
            finally:
                if self._client is not None:
                    # Stopping on purpose: take this instance's people out of
                    # the count now rather than when the key lapses.
                    self._client = None
                    with contextlib.suppress(Exception):
                        await client.delete(self._presence_key())
                with contextlib.suppress(Exception):
                    await client.aclose()
            await asyncio.sleep(RETRY_SECONDS)

    def _presence_key(self) -> str:
        return f"{PRESENCE_PREFIX}{self.instance_id}"

    async def _write_presence(self, client: aioredis.Redis):
        """Replace this instance's presence set with who it holds now."""
        key = self._presence_key()
        async with client.pipeline(transaction=True) as pipe:
            pipe.delete(key)
            if self.active_sockets:
                pipe.sadd(key, *self.active_sockets)
                pipe.expire(key, PRESENCE_TTL_SECONDS)
            await pipe.execute()

    async def _publish(self, message: dict):
        """Pass a message to the other instances, when the relay is up.

        Never raises. The sockets here have had theirs by the time this runs,
        so a Redis that has gone away costs the other instances' sockets this
        one message and nothing more.
        """
        client = self._client
        if client is None:
            return
        try:
            await client.publish(CHANNEL, json.dumps({"origin": self.instance_id, **message}))
        except (redis.RedisError, OSError) as unreachable:
            log.warning("websocket message not relayed to other instances: %s", unreachable)

    async def _relay(self, raw: str):
        """Hand a message another instance published to the sockets here."""
        try:
            message = json.loads(raw)
            if message["origin"] == self.instance_id:
                return
            recipient = message["to"]
            if "close" in message:
                await self._close_here(recipient, message["close"])
            elif recipient is None:
                await self._broadcast_here(message["event"], message["payload"])
            else:
                await self._deliver_here(recipient, message["event"], message["payload"])
        except (ValueError, TypeError, KeyError):
            # Nothing published here looks like that. Dropping it keeps the
            # relay up for the messages that do.
            log.warning("dropped a malformed message on %s", CHANNEL)

    async def _close_here(self, user_id: str, code: int):
        websocket = self.active_sockets.pop(user_id, None)
        if websocket is None:
            return
        # Already closed from the other end is the outcome being asked for.
        with contextlib.suppress(Exception):
            await websocket.close(code=code)

    async def _deliver_here(self, recipient_id: str, event_type: str, data_payload: dict):
        websocket = self.active_sockets.get(recipient_id)
        if not websocket:
            return
        frame = json.dumps({"event": event_type, "payload": data_payload})
        try:
            await websocket.send_text(frame)
        except Exception:
            self.terminate_session(recipient_id)

    async def _broadcast_here(self, event_type: str, data_payload: dict):
        frame = json.dumps({"event": event_type, "payload": data_payload})
        for user_id, websocket in list(self.active_sockets.items()):
            try:
                await websocket.send_text(frame)
            except Exception:
                self.terminate_session(user_id)


socket_broker = OrganizationConnectionManager()
