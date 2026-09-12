# Copyright 2026 Chronos Ledger Contributors
# Licensed under the Apache License, Version 2.0

"""A budget per caller on the few routes where guessing or hammering pays.

Three routes are counted. Sign-in, because a password is the one credential
here that a person chose and therefore the one worth guessing. The visitor
kiosk, because a device sitting in a lobby with an API key in it is the
credential most likely to end up somewhere it should not be. The calendar
feed, because it is unauthenticated by design and does real work per request.

Nothing else is counted. A bearer token, an API key and a feed token are all
256 bits of `secrets`, and guessing one is not a strategy, so a budget there
would only get in the way of the integrations this is meant to have. The feed
budget is a guard against one subscriber polling in a loop, not against
someone enumerating tokens, which is not a thing that can be done. A
visitor's check-in code is shorter, about 79 bits, because a person types it
on a phone. That is still far past guessing, and a right guess would show
only whether one unnamed visit was approved. Looking one up is a single
indexed read, so the kiosk and the visitor polling it do no work worth a
budget either.

Fixed windows, not sliding. The count lives under a single key with a TTL and
the budget refills when that key expires. A sliding window is more accurate
and wants a sorted set per caller, which is a lot of Redis for a difference
nobody sitting at a login form can perceive.

Checking and counting are two steps, so requests that arrive together can all
read the same count and get through before any of them has been counted. That
is the price of not charging a correct password: the alternative counts first
and refunds afterwards, and a refund lost to a crash locks somebody out of
their own account. The overshoot is bounded by how many requests one caller
can have in flight at once, each of which still pays for a bcrypt comparison.

It fails open. Redis is a cache in this system and not a system of record, and
an instance that cannot reach it should keep letting people sign in rather
than lock the organization out until it comes back. That is a real trade:
whoever can take Redis down can also take the limiter off. The alternative
trade is worse.
"""

import hashlib
import logging

import redis
from fastapi import HTTPException, Request, status

from app.core.config import get_settings
from app.core.redis_client import get_redis

log = logging.getLogger(__name__)

# The counts are settings, the windows are not. A count is the number an
# operator has an opinion about; the window is the shape of the limiter, and
# eight environment variables to describe three limits is a worse deal than
# three variables and a documented window.
LOGIN_WINDOW_SECONDS = 15 * 60
GUEST_WINDOW_SECONDS = 60 * 60
FEED_WINDOW_SECONDS = 60 * 60


def caller_address(request: Request) -> str:
    """The client's own address, or empty when there is none worth counting.

    uvicorn rewrites this from X-Forwarded-For when FORWARDED_ALLOW_IPS names
    the proxy in front of it, which both compose files set. Without that every
    browser in the organization arrives as nginx and shares one bucket, so ten
    failed sign-ins by one person would lock out everybody.

    Trusting the header is only safe because nginx overwrites it rather than
    appending to it (nginx/chronos-common.conf), so the proxy is the only
    thing that can write an address into it. Appending would let a caller put
    its own address on the front and mint a bucket per attempt.

    Empty disables the address budget for that request rather than putting
    every anonymous caller in one bucket, which is the same failure again.
    """
    return request.client.host if request.client else ""


def _bucket_key(bucket: str, subject: str) -> str:
    # Hashed because a subject is sometimes a credential (a calendar feed
    # token) and sometimes personal (an email address), and neither belongs in
    # a keyspace an operator reads with KEYS or a line that reaches a log.
    digest = hashlib.sha256(subject.encode("utf-8")).hexdigest()[:32]
    return f"rl:{bucket}:{digest}"


def _counter(limit: int, subject: str) -> redis.Redis | None:
    """The connection to count on, or None when this budget does not apply."""
    if limit <= 0 or not subject:
        return None
    if not get_settings().rate_limit_enabled:
        return None
    return get_redis()


def guard(bucket: str, subject: str, limit: int, window: int, what: str) -> None:
    """Refuse the request if the budget is spent, without spending any of it.

    Separate from `spend` so a sign-in can be turned away before it pays for a
    bcrypt comparison, and so that getting your own password right does not
    cost you a slice of your own budget.
    """
    client = _counter(limit, subject)
    if client is None:
        return
    key = _bucket_key(bucket, subject)
    try:
        pipe = client.pipeline()
        pipe.get(key)
        pipe.ttl(key)
        counted, ttl = pipe.execute()
    except redis.RedisError as unreachable:
        log.warning("rate limit not applied to %s: %s", bucket, unreachable)
        return

    if counted is None or int(counted) < limit:
        return

    # A key with no expiry is a process that died between the two halves of
    # `spend`. Report a whole window rather than implying forever.
    retry_after = ttl if ttl and ttl > 0 else window
    raise HTTPException(
        status_code=status.HTTP_429_TOO_MANY_REQUESTS,
        detail=f"Too many {what}. Try again in {retry_after} seconds.",
        headers={"Retry-After": str(retry_after)},
    )


def spend(bucket: str, subject: str, limit: int, window: int) -> None:
    """Count one request against the budget."""
    client = _counter(limit, subject)
    if client is None:
        return
    key = _bucket_key(bucket, subject)
    try:
        pipe = client.pipeline()
        pipe.incr(key)
        pipe.ttl(key)
        _, ttl = pipe.execute()
        if ttl is None or ttl < 0:
            # Either the first hit of a window, or a key that lost its expiry
            # because a process died here last time. Both want the same thing.
            client.expire(key, window)
    except redis.RedisError as unreachable:
        log.warning("rate limit not counted for %s: %s", bucket, unreachable)
