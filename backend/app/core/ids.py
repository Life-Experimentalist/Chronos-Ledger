# Copyright 2026 Chronos Ledger Contributors
# Licensed under the Apache License, Version 2.0
"""Identifiers that are random by default and reproducible when seeded.

``ID_SEED`` makes every identifier drawn here follow one fixed sequence,
so a host program replaying the same script gets the same rows. Only
identifiers that are not secrets come from here: a refresh token family
id, a federated account id. Tokens, keys, passwords and codes that a
caller must present to be believed stay on ``secrets`` whatever the seed.
"""

from __future__ import annotations

import random
import secrets
import uuid

from app.core.config import Settings, get_settings


class IdGenerator:
    def __init__(self, seed: int | None) -> None:
        self._rng = random.Random(seed) if seed is not None else None

    @property
    def seeded(self) -> bool:
        return self._rng is not None

    def uuid(self) -> uuid.UUID:
        if self._rng is None:
            return uuid.uuid4()
        return uuid.UUID(bytes=self._rng.randbytes(16), version=4)

    def hex(self, nbytes: int) -> str:
        if self._rng is None:
            return secrets.token_hex(nbytes)
        return self._rng.randbytes(nbytes).hex()


def from_settings(settings: Settings) -> IdGenerator:
    return IdGenerator(settings.id_seed)


_generator: IdGenerator | None = None


def current() -> IdGenerator:
    global _generator
    if _generator is None:
        _generator = from_settings(get_settings())
    return _generator


def install(generator: IdGenerator) -> None:
    global _generator
    _generator = generator


def reset() -> None:
    global _generator
    _generator = None


def new_uuid() -> uuid.UUID:
    return current().uuid()


def new_hex(nbytes: int) -> str:
    return current().hex(nbytes)
