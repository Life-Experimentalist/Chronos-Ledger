# Copyright 2026 Chronos Ledger Contributors
# Licensed under the Apache License, Version 2.0
"""Which dates a slot runs on, from its RFC 5545 rule.

A slot used to store a weekday and nothing else, so "every Monday" was the
only thing the timetable could say. It stores a rule now (the value of an
RRULE property, such as FREQ=WEEKLY;BYDAY=MO) and the date the rule starts
from, and this module is the one place that turns the two into dates.

Everything is expanded as calendar dates in the organization's calendar
(ORG_TIMEZONE), never as instants. The time of day lives in the slot's own
two Time columns and is read off them for each date, so a class at 09:00 is
at 09:00 on both sides of a daylight saving change. Expanding in UTC and
converting back would move it by an hour twice a year, which is the bug this
shape exists to rule out.

dtstart is a date, and it is always an occurrence of its rule: anchor() moves
a requested start forward to the first date the rule produces. RFC 5545 counts
DTSTART as the first instance whether or not it matches the rule, and
dateutil does not, so an unsynchronised pair would mean different things to
different readers. Keeping them synchronised makes the question go away.

A slot can occur at most once a date, so rules that repeat within a day
(FREQ=HOURLY and finer, BYHOUR, BYMINUTE, BYSECOND) are refused, and so is an
UNTIL in UTC: a slot's start is wall clock with no zone, and RFC 5545 asks for
a local UNTIL in that case.
"""

import datetime
from functools import lru_cache

from dateutil.rrule import rrule, rrulestr

MAX_RULE_LENGTH = 255

_DAY_CODES = ("MO", "TU", "WE", "TH", "FR", "SA", "SU")
_FREQUENCIES = {"DAILY", "WEEKLY", "MONTHLY", "YEARLY"}
_WITHIN_A_DAY = {"BYHOUR", "BYMINUTE", "BYSECOND"}


def normalize(value: str) -> str:
    """The rule as it is stored, or ValueError saying what is wrong with it.

    Accepts the RRULE property value, with or without the "RRULE:" name in
    front. Only the rule itself is stored: DTSTART, EXDATE and the rest of an
    iCalendar recurrence set have no place here, and a value with a line
    break or a second property in it is refused rather than half read.
    """
    rule = value.strip().upper()
    if rule.startswith("RRULE:"):
        rule = rule[len("RRULE:") :]
    if not rule:
        raise ValueError("rrule must not be empty")
    if len(rule) > MAX_RULE_LENGTH:
        raise ValueError(f"rrule must not be longer than {MAX_RULE_LENGTH} characters")
    if any(ch in rule for ch in "\r\n:"):
        raise ValueError(
            "rrule is the value of one RRULE property, such as FREQ=WEEKLY;BYDAY=MO; "
            "DTSTART and other properties are not part of it"
        )
    parts = {}
    for part in rule.split(";"):
        name, sep, setting = part.partition("=")
        if not sep or not name or not setting:
            raise ValueError(f"rrule part '{part}' is not NAME=VALUE")
        parts[name] = setting
    if parts.get("FREQ") not in _FREQUENCIES:
        raise ValueError("rrule FREQ must be DAILY, WEEKLY, MONTHLY or YEARLY")
    within = sorted(_WITHIN_A_DAY & parts.keys())
    if within:
        raise ValueError(f"rrule must not repeat within a day ({', '.join(within)})")
    if parts.get("UNTIL", "").endswith("Z"):
        raise ValueError(
            "rrule UNTIL must be a local date or date-time, without Z: "
            "slot times are wall clock in ORG_TIMEZONE"
        )
    try:
        _parsed(rule, datetime.date(2000, 1, 3))
    except (ValueError, TypeError) as exc:
        raise ValueError(f"rrule is not a valid RFC 5545 rule: {exc}") from None
    return rule


@lru_cache(maxsize=4096)
def _parsed(rule: str, dtstart: datetime.date) -> rrule:
    """The rule from this start, built once and kept with its own cache."""
    return rrulestr(rule, dtstart=datetime.datetime.combine(dtstart, datetime.time.min), cache=True)


def occurrences(
    rule: str, dtstart: datetime.date, first: datetime.date, last: datetime.date
) -> list[datetime.date]:
    """The dates the rule produces from first to last, both included."""
    first = max(first, dtstart)
    if first > last:
        return []
    return [
        hit.date()
        for hit in _parsed(rule, dtstart).between(
            datetime.datetime.combine(first, datetime.time.min),
            datetime.datetime.combine(last, datetime.time.min),
            inc=True,
        )
    ]


def occurs_on(rule: str, dtstart: datetime.date, day: datetime.date) -> bool:
    return bool(occurrences(rule, dtstart, day, day))


def first_occurrence(rule: str, on_or_after: datetime.date) -> datetime.date | None:
    """The first date the rule produces when it starts from on_or_after."""
    hit = _parsed(rule, on_or_after).after(
        datetime.datetime.combine(on_or_after, datetime.time.min), inc=True
    )
    return hit.date() if hit else None


def anchor(rule: str, on_or_after: datetime.date) -> datetime.date:
    """The dtstart to store for a rule asked to start on a date.

    The first occurrence on or after it, so the stored pair is synchronised.
    A rule that has nothing left from that date (an UNTIL or COUNT already
    used up) would be a slot that never runs, and is refused.
    """
    found = first_occurrence(rule, on_or_after)
    if found is None:
        raise ValueError(f"rrule produces no date on or after {on_or_after.isoformat()}")
    return found


def weekly_rule(weekday: int) -> str:
    """FREQ=WEEKLY on one weekday, 1 for Monday to 7 for Sunday (isoweekday)."""
    return f"FREQ=WEEKLY;BYDAY={_DAY_CODES[weekday - 1]}"


def weekly(weekday: int, on_or_after: datetime.date) -> dict:
    """rrule and dtstart for a slot given as a weekday, the shape of a CSV row."""
    rule = weekly_rule(weekday)
    return {"rrule": rule, "dtstart": anchor(rule, on_or_after)}
