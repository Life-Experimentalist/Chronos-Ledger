# Copyright 2026 Chronos Ledger Contributors
# Licensed under the Apache License, Version 2.0
"""iCalendar feed: faculty and student views, state annotations, ad-hoc entries.

The feed is deliberately unauthenticated so calendar apps can subscribe to it,
but it is keyed by the plain user id rather than a secret token. Whether that
should become an unguessable per-user token is an open intake question.
"""

import datetime

from app.models.db import (
    AcademicCycle,
    CourseOffering,
    CourseRegistration,
    DailyLedger,
    DynamicState,
    StructuralMasterSlot,
)

TODAY = datetime.date.today()


def _seed_schedule(db, state=DynamicState.SCHEDULED, with_slot=True, substitute=None):
    cycle = AcademicCycle(
        cycle_label="Cal 2026",
        date_bounds_start=TODAY - datetime.timedelta(days=30),
        date_bounds_end=TODAY + datetime.timedelta(days=90),
        operational_status=True,
    )
    db.add(cycle)
    db.flush()
    offering = CourseOffering(
        course_code="CS500",
        course_title="Distributed Systems",
        department_code="CSE",
        cycle_id=cycle.id,
    )
    db.add(offering)
    db.flush()
    slot_id = None
    if with_slot:
        slot = StructuralMasterSlot(
            day_of_week_index=TODAY.isoweekday(),
            time_window_start=datetime.time(10, 0),
            time_window_end=datetime.time(11, 0),
            course_offering_id=offering.id,
            primary_instructor_id="FAC001",
            target_room_identifier="LH-500",
        )
        db.add(slot)
        db.flush()
        slot_id = slot.id
    ledger = DailyLedger(
        target_date=TODAY,
        master_slot_id=slot_id,
        course_offering_id=offering.id,
        active_instructor_id="FAC001",
        substitute_instructor_id=substitute,
        target_room_identifier="LH-500",
        operational_state=state,
    )
    db.add(ledger)
    db.add(CourseRegistration(course_offering_id=offering.id, student_id="STU001"))
    db.commit()
    return offering


def test_faculty_feed_lists_their_class(client, db, seed_users):
    _seed_schedule(db)
    r = client.get("/api/v1/sync/user-feed/FAC001.ics")
    assert r.status_code == 200
    assert r.headers["content-type"].startswith("text/calendar")
    body = r.text
    assert "BEGIN:VCALENDAR" in body and "END:VCALENDAR" in body
    assert "[CS500] Distributed Systems" in body
    assert f"DTSTART:{TODAY.strftime('%Y%m%d')}T100000" in body
    assert "LOCATION:Room LH-500" in body


def test_student_feed_requires_registration(client, db, seed_users):
    _seed_schedule(db)
    registered = client.get("/api/v1/sync/user-feed/STU001.ics").text
    assert "[CS500] Distributed Systems" in registered

    # Drop the registration: the same student now sees an empty calendar.
    db.query(CourseRegistration).delete()
    db.commit()
    unregistered = client.get("/api/v1/sync/user-feed/STU001.ics").text
    assert "BEGIN:VEVENT" not in unregistered


def test_on_leave_class_is_marked_cancelled(client, db, seed_users):
    _seed_schedule(db, state=DynamicState.ON_LEAVE)
    body = client.get("/api/v1/sync/user-feed/FAC001.ics").text
    assert "CANCELLED" in body


def test_substitute_sees_proxy_assignment(client, db, seed_users):
    # FAC001 is on leave; the admin user substitutes and gets the entry
    # in their own feed, marked as a proxy assignment.
    _seed_schedule(db, state=DynamicState.PROXY_SUBSTITUTE, substitute="ADM001")
    body = client.get("/api/v1/sync/user-feed/ADM001.ics").text
    assert "(Proxy Assignment)" in body


def test_adhoc_entry_without_slot_is_all_day(client, db, seed_users):
    _seed_schedule(db, with_slot=False)
    body = client.get("/api/v1/sync/user-feed/FAC001.ics").text
    # No master slot: an RFC 5545 all-day event (VALUE=DATE, non-inclusive DTEND).
    tomorrow = TODAY + datetime.timedelta(days=1)
    assert f"DTSTART;VALUE=DATE:{TODAY.strftime('%Y%m%d')}\r\n" in body
    assert f"DTEND;VALUE=DATE:{tomorrow.strftime('%Y%m%d')}\r\n" in body


def test_unknown_user_is_404(client, db, seed_users):
    r = client.get("/api/v1/sync/user-feed/NOBODY.ics")
    assert r.status_code == 404
