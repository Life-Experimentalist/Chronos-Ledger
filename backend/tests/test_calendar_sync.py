# Copyright 2026 Chronos Ledger Contributors
# Licensed under the Apache License, Version 2.0
"""iCalendar feed: staff and member views, state annotations, ad-hoc entries.

The feed is deliberately unauthenticated so calendar apps can subscribe to it,
but it is keyed by an unguessable per-user token, never the plain user id.
"""

import datetime

from app.core.time import org_today
from app.models.db import (
    Activity,
    ActivityEnrollment,
    DailyLedger,
    DynamicState,
    PlanningCycle,
    StructuralMasterSlot,
    User,
)
from tests.conftest import STAFF_PASSWORD, login

TODAY = org_today()


def _seed_schedule(db, state=DynamicState.SCHEDULED, with_slot=True, substitute=None):
    cycle = PlanningCycle(
        cycle_label="Cal 2026",
        date_bounds_start=TODAY - datetime.timedelta(days=30),
        date_bounds_end=TODAY + datetime.timedelta(days=90),
        operational_status=True,
    )
    db.add(cycle)
    db.flush()
    offering = Activity(
        activity_code="CS500",
        activity_title="Distributed Systems",
        unit_code="CSE",
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
            activity_id=offering.id,
            primary_lead_id="FAC001",
            target_room_identifier="LH-500",
        )
        db.add(slot)
        db.flush()
        slot_id = slot.id
    ledger = DailyLedger(
        target_date=TODAY,
        master_slot_id=slot_id,
        activity_id=offering.id,
        active_lead_id="FAC001",
        substitute_lead_id=substitute,
        target_room_identifier="LH-500",
        operational_state=state,
    )
    db.add(ledger)
    db.add(ActivityEnrollment(activity_id=offering.id, member_id="STU001"))
    db.commit()
    return offering


def _feed_url(db, user_id):
    token = db.query(User).filter(User.id == user_id).first().calendar_feed_token
    return f"/api/v1/sync/user-feed/{token}.ics"


def test_staff_feed_lists_their_class(client, db, seed_users):
    _seed_schedule(db)
    r = client.get(_feed_url(db, "FAC001"))
    assert r.status_code == 200
    assert r.headers["content-type"].startswith("text/calendar")
    body = r.text
    assert "BEGIN:VCALENDAR" in body and "END:VCALENDAR" in body
    assert "[CS500] Distributed Systems" in body
    assert f"DTSTART:{TODAY.strftime('%Y%m%d')}T100000" in body
    assert "LOCATION:Room LH-500" in body


def test_member_feed_requires_registration(client, db, seed_users):
    _seed_schedule(db)
    registered = client.get(_feed_url(db, "STU001")).text
    assert "[CS500] Distributed Systems" in registered

    # Drop the registration: the same member now sees an empty calendar.
    db.query(ActivityEnrollment).delete()
    db.commit()
    unregistered = client.get(_feed_url(db, "STU001")).text
    assert "BEGIN:VEVENT" not in unregistered


def test_on_leave_class_is_marked_cancelled(client, db, seed_users):
    _seed_schedule(db, state=DynamicState.ON_LEAVE)
    body = client.get(_feed_url(db, "FAC001")).text
    assert "CANCELLED" in body


def test_substitute_sees_proxy_assignment(client, db, seed_users):
    # FAC001 is on leave; the admin user substitutes and gets the entry
    # in their own feed, marked as a proxy assignment.
    _seed_schedule(db, state=DynamicState.PROXY_SUBSTITUTE, substitute="ADM001")
    body = client.get(_feed_url(db, "ADM001")).text
    assert "(Proxy Assignment)" in body


def test_adhoc_entry_without_slot_is_all_day(client, db, seed_users):
    _seed_schedule(db, with_slot=False)
    body = client.get(_feed_url(db, "FAC001")).text
    # No master slot: an RFC 5545 all-day event (VALUE=DATE, non-inclusive DTEND).
    tomorrow = TODAY + datetime.timedelta(days=1)
    assert f"DTSTART;VALUE=DATE:{TODAY.strftime('%Y%m%d')}\r\n" in body
    assert f"DTEND;VALUE=DATE:{tomorrow.strftime('%Y%m%d')}\r\n" in body


def test_unknown_token_is_404(client, db, seed_users):
    r = client.get("/api/v1/sync/user-feed/NOBODY.ics")
    assert r.status_code == 404


def test_plain_user_id_no_longer_serves_a_feed(client, db, seed_users):
    _seed_schedule(db)
    r = client.get("/api/v1/sync/user-feed/FAC001.ics")
    assert r.status_code == 404


def test_rotate_invalidates_the_old_feed_url(client, db, seed_users):
    _seed_schedule(db)
    old_url = _feed_url(db, "FAC001")
    assert client.get(old_url).status_code == 200

    headers = login(client, "staff@test.internal", STAFF_PASSWORD)
    rotated = client.post("/api/v1/sync/feed-token/rotate", headers=headers)
    assert rotated.status_code == 200
    new_path = rotated.json()["feed_path"]

    assert client.get(old_url).status_code == 404
    assert client.get(new_path).status_code == 200


def test_feed_token_endpoint_returns_the_current_url(client, db, seed_users):
    headers = login(client, "staff@test.internal", STAFF_PASSWORD)
    r = client.get("/api/v1/sync/feed-token", headers=headers)
    assert r.status_code == 200
    body = r.json()
    assert body["feed_path"] == f"/api/v1/sync/user-feed/{body['feed_token']}.ics"
