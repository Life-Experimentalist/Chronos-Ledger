# Copyright 2026 Chronos Ledger Contributors
# Licensed under the Apache License, Version 2.0
"""The one clock the application reads.

Every timestamp the backend stamps, every "is it expired yet" check and
every "what day is it in the organisation's zone" question goes through
``now()`` here. By default that is the system clock and nothing behaves
differently. Under ``CLOCK_MODE=host`` the clock starts at ``CLOCK_START``
and does not move until the host program calls ``advance_to``; a host can
then drive a day of operations in a second and get the same rows every
time (see ``docs/clock.md``).

``wall_now()`` is the single sanctioned read of real time. It exists for
instants that an outside verifier compares against its own clock: the
``exp`` claim of a JWT (PyJWT checks it against real time) and the
not-before window of a federated signing key. Anything else that calls it
is a bug; ``tests/test_clock_guard.py`` lists the callers.
"""

from __future__ import annotations

from datetime import UTC, datetime

from app.core.config import Settings, get_settings


class SystemClock:
    """Real time. The default, and the only clock in production use."""

    def now(self) -> datetime:
        return datetime.now(UTC)

    def advance_to(self, instant: datetime) -> None:
        raise RuntimeError("the system clock cannot be advanced; set CLOCK_MODE=host")


class HostClock:
    """A clock that reads ``start`` until a host moves it forward."""

    def __init__(self, start: datetime) -> None:
        self._now = _as_utc(start, "CLOCK_START")

    def now(self) -> datetime:
        return self._now

    def advance_to(self, instant: datetime) -> None:
        instant = _as_utc(instant, "instant")
        if instant < self._now:
            raise ValueError(
                f"the clock does not go backwards: at {self._now.isoformat()}, "
                f"asked for {instant.isoformat()}"
            )
        self._now = instant


def _as_utc(instant: datetime, label: str) -> datetime:
    if instant.tzinfo is None or instant.utcoffset() is None:
        raise ValueError(f"{label} must be timezone-aware")
    return instant.astimezone(UTC)


def from_settings(settings: Settings) -> SystemClock | HostClock:
    if settings.clock_mode == "host":
        return HostClock(datetime.fromisoformat(settings.clock_start))
    return SystemClock()


_clock: SystemClock | HostClock | None = None


def current() -> SystemClock | HostClock:
    """The installed clock, built from settings on first use."""
    global _clock
    if _clock is None:
        _clock = from_settings(get_settings())
    return _clock


def install(clock: SystemClock | HostClock) -> None:
    global _clock
    _clock = clock


def reset() -> None:
    """Forget the installed clock so the next read rebuilds it from settings."""
    global _clock
    _clock = None


def is_host() -> bool:
    return isinstance(current(), HostClock)


def now() -> datetime:
    """The application's current instant, timezone-aware, in UTC."""
    return current().now()


def advance_to(instant: datetime) -> None:
    """Move the host clock forward to ``instant``. Refuses to go backwards."""
    current().advance_to(instant)


def wall_now() -> datetime:
    """Real time, for instants an outside verifier checks against its own clock."""
    return datetime.now(UTC)
