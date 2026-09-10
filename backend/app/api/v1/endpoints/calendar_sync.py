# Copyright 2026 Chronos Ledger Contributors
# Licensed under the Apache License, Version 2.0

import datetime

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import Response
from sqlalchemy.orm import Session

from app.core import rate_limit
from app.core.config import get_settings
from app.core.database import get_db
from app.core.security import get_current_user
from app.core.time import org_timezone, org_today, window_span
from app.models.db import (
    Activity,
    ActivityEnrollment,
    DailyLedger,
    InstitutionalRole,
    User,
    generate_feed_token,
)

router = APIRouter()


def _feed_payload(user: User) -> dict:
    return {
        "feed_token": user.calendar_feed_token,
        "feed_path": f"/api/v1/sync/user-feed/{user.calendar_feed_token}.ics",
    }


@router.get("/feed-token")
def get_feed_token(db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    if not current_user.calendar_feed_token:
        current_user.calendar_feed_token = generate_feed_token()
        db.commit()
    return _feed_payload(current_user)


@router.post("/feed-token/rotate")
def rotate_feed_token(
    db: Session = Depends(get_db), current_user: User = Depends(get_current_user)
):
    current_user.calendar_feed_token = generate_feed_token()
    db.commit()
    return _feed_payload(current_user)


def _escape(text: str) -> str:
    """A value written so a calendar parser reads it as one piece of text.

    RFC 5545 gives four characters a meaning inside a TEXT value, and a
    timetable is full of all of them because the titles come out of a CSV that
    somebody typed. A comma separates values, so "Ward round, morning" arrived
    as two. A semicolon starts a parameter. A newline ends the property, and a
    title carrying one could open a property, or a whole second event, that
    nobody put in the timetable: the same shape as an injection anywhere else,
    with a calendar as the target.

    The backslash goes first, or the backslashes added by the three
    replacements after it would be escaped a second time and the value would
    come out the other end with the marks still in it.
    """
    return (
        text.replace("\\", "\\\\")
        .replace(";", "\\;")
        .replace(",", "\\,")
        .replace("\r\n", "\\n")
        .replace("\r", "\\n")
        .replace("\n", "\\n")
    )


def _fold(line: str) -> str:
    """A content line broken to the 75 octets RFC 5545 asks of one.

    Octets and not characters. A name in Devanagari or a title with an accent
    in it weighs more than one byte per character, and a parser counting bytes
    would take the knife to a character halfway through and hand back
    mojibake. So this walks characters and counts what each one weighs, and
    the cut never lands inside one.

    A continuation line opens with a single space that the parser throws away
    again, and that space is itself part of the 75, so a continuation has 74
    to spend. Splitting an escape sequence across a fold is safe: unfolding
    runs before the value is read, so the two halves are back together by the
    time anything looks at them.
    """
    if len(line.encode("utf-8")) <= 75:
        return line

    parts: list[str] = []
    chunk: list[str] = []
    used = 0
    budget = 75
    for character in line:
        weight = len(character.encode("utf-8"))
        if used + weight > budget:
            parts.append("".join(chunk))
            chunk = []
            used = 0
            budget = 74
        chunk.append(character)
        used += weight
    parts.append("".join(chunk))
    return "\r\n ".join(parts)


def _utc_stamp(day: datetime.date, wall: datetime.time) -> str:
    """A wall clock reading on a date, written as the instant it actually is.

    A slot stores 09:00 with no zone attached, because 09:00 is what the
    timetable says. A calendar client needs an instant, and this feed used to
    hand it the bare digits, which RFC 5545 calls a floating time: every
    client reads it in whatever zone the person holding the phone is sitting
    in. For an organization at UTC+5:30 that put a nine o'clock class at half
    past two in the afternoon, and the calendar header said UTC while the
    values were not UTC either.

    Written as a UTC instant rather than with a TZID, because these are dated
    occurrences that have already been worked out, not recurrence rules. An
    instant is unambiguous, every client renders it in the reader's own zone,
    and there is no hand-written VTIMEZONE to get wrong. That trade turns
    around if master slots ever emit RRULEs: a repeating 09:00 has to keep
    saying 09:00 across a daylight saving move, and only a TZID can say that.

    Daylight saving is handled by the conversion, which is the whole reason
    for going through a real zone rather than adding a fixed offset. combine
    leaves fold at 0, so a wall time inside a repeated hour takes the first of
    the two and a wall time inside a skipped hour takes the offset from before
    the jump. Scheduling a class at 02:30 on the morning a zone springs
    forward is a mistake in the timetable, not something a calendar feed can
    resolve.

    A window that runs past midnight ends on the following date, and the
    caller passes that date rather than the slot's.
    """
    local = datetime.datetime.combine(day, wall, tzinfo=org_timezone())
    return local.astimezone(datetime.UTC).strftime("%Y%m%dT%H%M%SZ")


@router.get("/user-feed/{feed_token}.ics")
def stream_icalendar_feed(feed_token: str, db: Session = Depends(get_db)):
    # The feed stays unauthenticated so calendar apps can subscribe, but the key
    # is an unguessable per-user token, never the user id.
    #
    # Counted per token, and counted before the token is resolved: this is a
    # budget against one subscriber polling in a loop, and a 404 costs a query
    # like any other request. Guessing a token is not the threat here, since it
    # is 256 bits out of `secrets`.
    budget = get_settings().rate_limit_calendar_feed
    window = rate_limit.FEED_WINDOW_SECONDS
    rate_limit.guard("calendar-feed", feed_token, budget, window, "calendar feed requests")
    rate_limit.spend("calendar-feed", feed_token, budget, window)

    user = db.query(User).filter(User.calendar_feed_token == feed_token).first()
    if not user:
        raise HTTPException(status_code=404, detail="Feed not found")

    start_range = org_today() - datetime.timedelta(days=7)
    end_range = org_today() + datetime.timedelta(days=30)

    is_staff = user.role_type in (
        InstitutionalRole.STAFF,
        InstitutionalRole.SUPER_ADMIN,
        InstitutionalRole.UNIT_ADMIN,
    )

    if is_staff:
        # Staff feed: ledger entries where they are lead or substitute
        ledger_entries = (
            db.query(DailyLedger)
            .join(Activity, DailyLedger.activity_id == Activity.id)
            .filter(
                (DailyLedger.active_lead_id == user.id)
                | (DailyLedger.substitute_lead_id == user.id),
                DailyLedger.target_date.between(start_range, end_range),
            )
            .all()
        )
    else:
        # Member feed: ledger entries for their registered activities
        ledger_entries = (
            db.query(DailyLedger)
            .join(Activity, DailyLedger.activity_id == Activity.id)
            .join(ActivityEnrollment, ActivityEnrollment.activity_id == Activity.id)
            .filter(
                ActivityEnrollment.member_id == user.id,
                DailyLedger.target_date.between(start_range, end_range),
            )
            .all()
        )

    lines = [
        "BEGIN:VCALENDAR",
        "VERSION:2.0",
        "PRODID:-//ChronosLedger Engine//Chronos 2026//EN",
        f"X-WR-CALNAME:{_escape(f'Chronos Timeline - {user.full_name}')}",
        # A display hint some clients read when they show a calendar's own
        # zone. The timed values below are UTC instants and carry their zone
        # with them, so nothing depends on this being right, but naming a
        # zone the organization is not in would be a lie on the face of it.
        f"X-WR-TIMEZONE:{org_timezone().key}",
        "CALSCALE:GREGORIAN",
    ]

    # RFC 5545 requires DTSTAMP on every VEVENT, and strict parsers reject a
    # component without one. It is when this copy of the event was written,
    # not when the session runs, so one reading serves the whole response.
    written_at = datetime.datetime.now(datetime.UTC).strftime("%Y%m%dT%H%M%SZ")

    for entry in ledger_entries:
        offering = entry.activity
        if not offering:
            continue

        # The day's own window, not the slot's. Reading it back through the
        # slot meant a class removed from the timetable turned every day it
        # had already run into an all-day event, and moving a class to another
        # hour moved the days it had already run with it.
        starts_at = entry.time_window_start
        ends_at = entry.time_window_end
        if starts_at and ends_at:
            # target_date is the day the window opens on, so a night shift ends
            # on the day after it. Handing the same date to both would write an
            # event that finishes sixteen hours before it starts, which a strict
            # calendar client rejects and a lenient one draws backwards.
            _, ends = window_span(entry.target_date, starts_at, ends_at)
            dtstart_line = f"DTSTART:{_utc_stamp(entry.target_date, starts_at)}"
            dtend_line = f"DTEND:{_utc_stamp(ends.date(), ends_at)}"
            # The wall clock reading, not the UTC one. A UID has to name the
            # same event for the life of the event, and a UTC time would move
            # under it the first time the zone changed offset.
            uid_time = starts_at.strftime("%H%M%S")
        else:
            # Ad-hoc entry with no window: an all-day event. RFC 5545 makes
            # DTSTART default to DATE-TIME, so a date-only value must declare
            # VALUE=DATE, and the all-day DTEND is non-inclusive (the next day).
            # No zone on either: a date is a date wherever it is read.
            next_day = entry.target_date + datetime.timedelta(days=1)
            dtstart_line = f"DTSTART;VALUE=DATE:{entry.target_date.strftime('%Y%m%d')}"
            dtend_line = f"DTEND;VALUE=DATE:{next_day.strftime('%Y%m%d')}"
            uid_time = "000000"

        summary = f"[{offering.activity_code}] {offering.activity_title}"
        if entry.operational_state.value == "PROXY_SUBSTITUTE":
            summary += " (Proxy Assignment)"
        elif entry.operational_state.value == "ON_LEAVE":
            summary += " [CANCELLED: Staff Absent]"

        # A UID is a TEXT value like any other, and the activity code sitting
        # in the middle of this one came off a spreadsheet.
        uid = f"slot_{entry.target_date.strftime('%Y%m%d')}_{offering.activity_code}_{uid_time}@chronos.internal"
        location = f"Room {entry.target_room_identifier}"
        description = f"Status: {entry.operational_state.value} | Synchronized via Chronos Ledger."

        lines.extend(
            [
                "BEGIN:VEVENT",
                f"UID:{_escape(uid)}",
                f"DTSTAMP:{written_at}",
                dtstart_line,
                dtend_line,
                f"SUMMARY:{_escape(summary)}",
                f"LOCATION:{_escape(location)}",
                f"DESCRIPTION:{_escape(description)}",
                "END:VEVENT",
            ]
        )

    lines.append("END:VCALENDAR")
    return Response(content="\r\n".join(_fold(line) for line in lines), media_type="text/calendar")
