# Copyright 2026 Chronos Ledger Contributors
# Licensed under the Apache License, Version 2.0

import datetime
from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import Response
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.models.db import (
    User,
    DailyLedger,
    CourseOffering,
    StructuralMasterSlot,
    CourseRegistration,
    InstitutionalRole,
)

router = APIRouter()


@router.get("/user-feed/{user_token_id}.ics")
def stream_icalendar_feed(user_token_id: str, db: Session = Depends(get_db)):
    user = db.query(User).filter(User.id == user_token_id).first()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")

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
                (DailyLedger.active_instructor_id == user_token_id)
                | (DailyLedger.substitute_instructor_id == user_token_id),
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
                CourseRegistration.student_id == user_token_id,
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
            dtstart = f"{entry.target_date.strftime('%Y%m%d')}T{slot.time_window_start.strftime('%H%M%S')}"
            dtend = (
                f"{entry.target_date.strftime('%Y%m%d')}T{slot.time_window_end.strftime('%H%M%S')}"
            )
            uid_time = slot.time_window_start.strftime("%H%M%S")
        else:
            # Ad-hoc entry without a master slot — use all-day event
            dtstart = entry.target_date.strftime("%Y%m%d")
            dtend = entry.target_date.strftime("%Y%m%d")
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
                f"DTSTART:{dtstart}",
                f"DTEND:{dtend}",
                f"SUMMARY:{summary}",
                f"LOCATION:Room {entry.target_room_identifier}",
                f"DESCRIPTION:Status: {entry.operational_state.value} | Synchronized via Chronos Ledger.",
                "END:VEVENT",
            ]
        )

    lines.append("END:VCALENDAR")
    return Response(content="\r\n".join(lines), media_type="text/calendar")
