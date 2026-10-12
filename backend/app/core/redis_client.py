# Copyright 2026 Chronos Ledger Contributors
# Licensed under the Apache License, Version 2.0

from functools import lru_cache

import redis
from redis.backoff import ExponentialBackoff
from redis.retry import Retry

from app.core.config import get_settings

# REDIS_URL=memory:// keeps everything Redis would hold inside this process,
# for the standalone profile, which runs as one process with no server beside
# it. app/standalone.py sets it.
MEMORY_URL_SCHEME = "memory://"


def is_memory(url: str) -> bool:
    return url.startswith(MEMORY_URL_SCHEME)


@lru_cache
def get_redis() -> redis.Redis:
    settings = get_settings()
    if is_memory(settings.redis_url):
        return _memory_redis()
    # Callers fall back when Redis is down, so fail in about two seconds rather
    # than sitting through redis-py 8's defaults (5 s timeouts, 10 retries).
    return redis.from_url(
        settings.redis_url,
        decode_responses=True,
        socket_connect_timeout=1,
        socket_timeout=1,
        retry=Retry(ExponentialBackoff(), 2),
    )


def _memory_redis() -> redis.Redis:
    """A Redis that lives in this process and ends with it.

    Rate limit counters and the cached location overrides lose nothing that
    matters across a restart. Spent federated note ids do: a note used just
    before a restart could be used once more until it expires, which is at most
    FEDERATED_TOKEN_MAX_LIFETIME_SECONDS. docs/standalone.md says so.
    """
    try:
        import fakeredis
    except ImportError as missing:
        raise RuntimeError(
            "REDIS_URL=memory:// needs the standalone extra: "
            "pip install 'chronos-ledger-backend[standalone]'"
        ) from missing
    return fakeredis.FakeRedis(decode_responses=True)
