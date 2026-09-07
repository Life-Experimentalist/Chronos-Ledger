# Copyright 2026 Chronos Ledger Contributors
# Licensed under the Apache License, Version 2.0

import datetime

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import Response
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.security import get_current_user
from app.models.db import (
    CourseOffering,
    CourseRegistration,
    DailyLedger,
    InstitutionalRole,
    StructuralMasterSlot,
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


@router.get("/user-feed/{feed_token}.ics")
def stream_icalendar_feed(feed_token: str, db: Session = Depends(get_db)):
    # The feed stays unauthenticated so calendar apps can subscribe, but the key
    # is an unguessable per-user token, never the user id.
    user = db.query(User).filter(User.calendar_feed_token == feed_token).first()
    if not user:
        raise HTTPException(status_code=404, detail="Feed not found")

    start_range = datetime.date.today() - datetime.timedelta(days=7)
    end_range = datetime.date.today() + datetime.timedelta(days=30)

    is_faculty = user.role_type in (
        InstitutionalRole.FACULTY,
        InstitutionalRole.SUPER_ADMIN,
        InstitutionalRole.DEPT_ADMIN,
    )

    if is_faculty:
        # Faculty feed: ledger entries where they are instructor or substitute
        ledger_entries = (
            db.query(DailyLedger)
            .join(CourseOffering, DailyLedger.course_offering_id == CourseOffering.id)
            .outerjoin(StructuralMasterSlot, DailyLedger.master_slot_id == StructuralMasterSlot.id)
            .filter(
                (DailyLedger.active_instructor_id == user.id)
                | (DailyLedger.substitute_instructor_id == user.id),
                DailyLedger.target_date.between(start_range, end_range),
            )
            .all()
        )
    else:
        # Student feed: ledger entries for their registered courses
        ledger_entries = (
            db.query(DailyLedger)
            .join(CourseOffering, DailyLedger.course_offering_id == CourseOffering.id)
            .join(StructuralMasterSlot, DailyLedger.master_slot_id == StructuralMasterSlot.id)
            .join(CourseRegistration, CourseRegistration.course_offering_id == CourseOffering.id)
            .filter(
                CourseRegistration.student_id == user.id,
                DailyLedger.target_date.between(start_range, end_range),
            )
            .all()
        )

    lines = [
        "BEGIN:VCALENDAR",
        "VERSION:2.0",
        "PRODID:-//ChronosLedger Engine//CampusOS 2026//EN",
        f"X-WR-CALNAME:Chronos Timeline - {user.full_name}",
        "X-WR-TIMEZONE:UTC",
        "CALSCALE:GREGORIAN",
    ]

    for entry in ledger_entries:
        slot = entry.master_slot
        offering = entry.course_offering
        if not offering:
            continue

        if slot:
            dtstart_line = f"DTSTART:{entry.target_date.strftime('%Y%m%d')}T{slot.time_window_start.strftime('%H%M%S')}"
            dtend_line = f"DTEND:{entry.target_date.strftime('%Y%m%d')}T{slot.time_window_end.strftime('%H%M%S')}"
            uid_time = slot.time_window_start.strftime("%H%M%S")
        else:
            # Ad-hoc entry without a master slot: an all-day event. RFC 5545 makes
            # DTSTART default to DATE-TIME, so a date-only value must declare
            # VALUE=DATE, and the all-day DTEND is non-inclusive (the next day).
            next_day = entry.target_date + datetime.timedelta(days=1)
            dtstart_line = f"DTSTART;VALUE=DATE:{entry.target_date.strftime('%Y%m%d')}"
            dtend_line = f"DTEND;VALUE=DATE:{next_day.strftime('%Y%m%d')}"
            uid_time = "000000"

        summary = f"[{offering.course_code}] {offering.course_title}"
        if entry.operational_state.value == "PROXY_SUBSTITUTE":
            summary += " (Proxy Assignment)"
        elif entry.operational_state.value == "ON_LEAVE":
            summary += " [CANCELLED — Faculty Absent]"

        lines.extend(
            [
                "BEGIN:VEVENT",
                f"UID:slot_{entry.target_date.strftime('%Y%m%d')}_{offering.course_code}_{uid_time}@chronos.internal",
                dtstart_line,
                dtend_line,
                f"SUMMARY:{summary}",
                f"LOCATION:Room {entry.target_room_identifier}",
                f"DESCRIPTION:Status: {entry.operational_state.value} | Synchronized via Chronos Ledger.",
                "END:VEVENT",
            ]
        )

    lines.append("END:VCALENDAR")
    return Response(content="\r\n".join(lines), media_type="text/calendar")
