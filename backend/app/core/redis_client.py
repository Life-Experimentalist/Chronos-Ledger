# Copyright 2026 Chronos Ledger Contributors
# Licensed under the Apache License, Version 2.0

import redis
from functools import lru_cache
from app.core.config import get_settings


@lru_cache
def get_redis() -> redis.Redis:
    settings = get_settings()
    return redis.from_url(settings.redis_url, decode_responses=True)
