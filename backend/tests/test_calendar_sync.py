# Copyright 2026 Chronos Ledger Contributors
# Licensed under the Apache License, Version 2.0
"""iCalendar feed: staff and member views, state annotations, ad-hoc entries.

The feed is deliberately unauthenticated so calendar apps can subscribe to it,
but it is keyed by an unguessable per-user token, never the plain user id.
"""

import datetime

import pytest

from app.api.v1.endpoints.calendar_sync import _utc_stamp
from app.core.config import get_settings
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

# UTC+5:30 all year, so a conversion either happened or it did not.
IST = "Asia/Kolkata"
# UTC-5 in January and UTC-4 in July. The zone that catches a hardcoded offset.
NEW_YORK = "America/New_York"


@pytest.fixture
def org_zone(monkeypatch):
    """Stand the organization somewhere else for the length of one test.

    get_settings is lru_cached, so the cache has to be dropped on the way in,
    and again on the way out or the next test inherits this one's zone.
    """

    def set_to(name: str):
        monkeypatch.setenv("ORG_TIMEZONE", name)
        get_settings.cache_clear()

    yield set_to
    get_settings.cache_clear()


def _seed_schedule(
    db,
    state=DynamicState.SCHEDULED,
    with_slot=True,
    substitute=None,
    start=datetime.time(10, 0),
    end=datetime.time(11, 0),
    title="Distributed Systems",
):
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
        activity_title=title,
        unit_code="CSE",
        cycle_id=cycle.id,
    )
    db.add(offering)
    db.flush()
    slot_id = None
    if with_slot:
        slot = StructuralMasterSlot(
            day_of_week_index=TODAY.isoweekday(),
            time_window_start=start,
            time_window_end=end,
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


def test_staff_feed_lists_their_class(client, db, seed_users, org_zone):
    # Pinned so the stamp below is a fact rather than a reading of whatever
    # zone this machine happens to be configured for.
    org_zone("UTC")
    _seed_schedule(db)
    r = client.get(_feed_url(db, "FAC001"))
    assert r.status_code == 200
    assert r.headers["content-type"].startswith("text/calendar")
    body = r.text
    assert "BEGIN:VCALENDAR" in body and "END:VCALENDAR" in body
    assert "[CS500] Distributed Systems" in body
    assert f"DTSTART:{TODAY.strftime('%Y%m%d')}T100000Z" in body
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


# ── When the event actually happens ──────────────────────────────────────────


def test_a_timed_event_is_an_instant_and_not_a_floating_time(client, db, seed_users, org_zone):
    """The defect. A ten o'clock class went out as the bare digits 100000,
    which RFC 5545 calls a floating time and every client reads in whatever
    zone the person holding the phone is standing in. Half the people
    subscribed to a feed are not in the organization's zone, and for them the
    class moved."""
    org_zone(IST)
    _seed_schedule(db)
    body = client.get(_feed_url(db, "FAC001")).text
    # Ten in the morning in Kolkata is 04:30 UTC, and Z says so out loud.
    assert f"DTSTART:{TODAY.strftime('%Y%m%d')}T043000Z" in body
    assert f"DTEND:{TODAY.strftime('%Y%m%d')}T053000Z" in body


def test_an_early_class_belongs_to_the_previous_date_in_utc(client, db, seed_users, org_zone):
    """The conversion moves the date and not only the clock, which is the part
    an offset pasted onto the end of the time string would get wrong."""
    org_zone(IST)
    _seed_schedule(db, start=datetime.time(3, 0), end=datetime.time(4, 0))
    yesterday = TODAY - datetime.timedelta(days=1)
    body = client.get(_feed_url(db, "FAC001")).text
    assert f"DTSTART:{yesterday.strftime('%Y%m%d')}T213000Z" in body


def test_a_night_shift_ends_on_the_day_after_it_starts(client, db, seed_users, org_zone):
    """The end takes the next date, not the date the entry is filed under.

    A ledger row is dated the day its window opened on, and a window from
    22:00 to 06:00 finishes on the day after that. Handing the row's own date
    to both ends writes an event that stops sixteen hours before it starts,
    which a strict client rejects outright and a lenient one draws backwards.
    """
    org_zone(IST)
    _seed_schedule(db, start=datetime.time(22, 0), end=datetime.time(6, 0))
    tomorrow = TODAY + datetime.timedelta(days=1)
    body = client.get(_feed_url(db, "FAC001")).text
    # Ten at night in Kolkata is 16:30 UTC, and six the next morning is 00:30
    # UTC on the morning after that in local terms, which is the same date in
    # UTC either way. The date on DTEND is the point.
    assert f"DTSTART:{TODAY.strftime('%Y%m%d')}T163000Z" in body
    assert f"DTEND:{tomorrow.strftime('%Y%m%d')}T003000Z" in body


def test_the_same_wall_clock_is_a_different_instant_either_side_of_a_dst_move(org_zone):
    """Why the conversion goes through a real zone instead of adding a fixed
    number of hours. Nine in the morning in New York is 14:00 UTC in January
    and 13:00 UTC in July, so a feed carrying one offset all year would be an
    hour out for half of it.

    Written against fixed dates, because a daylight saving move is a fixed
    point in the calendar and the feed only ever looks a month ahead.
    """
    org_zone(NEW_YORK)
    nine = datetime.time(9, 0)
    assert _utc_stamp(datetime.date(2026, 1, 15), nine) == "20260115T140000Z"
    assert _utc_stamp(datetime.date(2026, 7, 15), nine) == "20260715T130000Z"


def test_an_all_day_entry_carries_no_zone(client, db, seed_users, org_zone):
    """A date is the same date wherever it is read. Converting one would turn
    a day off into two half days."""
    org_zone(IST)
    _seed_schedule(db, with_slot=False)
    body = client.get(_feed_url(db, "FAC001")).text
    assert f"DTSTART;VALUE=DATE:{TODAY.strftime('%Y%m%d')}\r\n" in body
    assert "TZID" not in body


def test_the_calendar_names_the_zone_the_organization_is_in(client, db, seed_users, org_zone):
    """The header said UTC wherever the organization was, and then wrote times
    that were not UTC either."""
    org_zone(IST)
    _seed_schedule(db)
    assert f"X-WR-TIMEZONE:{IST}" in client.get(_feed_url(db, "FAC001")).text


# ── What a title can and cannot do to the file ───────────────────────────────


def _unfold(body: str) -> str:
    """Put the continuation lines back onto the lines they came off, which is
    the first thing a parser does and the last thing it undoes."""
    return body.replace("\r\n ", "")


def test_a_comma_in_a_title_does_not_split_the_summary(client, db, seed_users):
    """A comma separates values in a TEXT property, so a perfectly ordinary
    title arrived at the other end as two of them."""
    _seed_schedule(db, title="Ward round, morning")
    body = client.get(_feed_url(db, "FAC001")).text
    assert "SUMMARY:[CS500] Ward round\\, morning" in body


def test_the_characters_that_mean_something_are_all_escaped(client, db, seed_users):
    """Backslash, semicolon, comma, newline. The backslash has to go first or
    the marks added for the other three get escaped a second time."""
    _seed_schedule(db, title="a;b,c\\d\ne")
    body = client.get(_feed_url(db, "FAC001")).text
    assert "SUMMARY:[CS500] a\\;b\\,c\\\\d\\ne" in body


def test_a_title_cannot_smuggle_a_second_event_into_the_file(client, db, seed_users):
    """A newline ends a property, so a title carrying one could write its own
    event into somebody's calendar. The titles come out of an uploaded CSV,
    which makes this an injection with a calendar as the target."""
    _seed_schedule(db, title="Real\r\nEND:VEVENT\r\nBEGIN:VEVENT\r\nSUMMARY:Fake")
    lines = _unfold(client.get(_feed_url(db, "FAC001")).text).split("\r\n")
    # Counted as lines, because lines are what a parser sees. The words are
    # still in there, sitting inside the summary where they belong.
    assert lines.count("BEGIN:VEVENT") == 1
    assert lines.count("END:VEVENT") == 1
    assert not any(line.startswith("SUMMARY:Fake") for line in lines)


def test_the_calendar_name_is_escaped_as_well(client, db, seed_users):
    """It carries a person's name, and a person's name is typed in by a
    person."""
    db.query(User).filter(User.id == "FAC001").update({"full_name": "Rao, Priya"})
    db.commit()
    _seed_schedule(db)
    body = client.get(_feed_url(db, "FAC001")).text
    assert "X-WR-CALNAME:Chronos Timeline - Rao\\, Priya" in body


def test_every_event_carries_a_dtstamp(client, db, seed_users):
    """RFC 5545 requires one on every VEVENT, and a strict parser drops a
    component that has none."""
    _seed_schedule(db)
    lines = _unfold(client.get(_feed_url(db, "FAC001")).text).split("\r\n")
    stamps = [line for line in lines if line.startswith("DTSTAMP:")]
    assert len(stamps) == 1
    assert stamps[0].endswith("Z")


def test_no_content_line_runs_past_seventy_five_octets(client, db, seed_users):
    """A long title is the normal case, not the odd one: SUMMARY has spent
    sixteen characters on the activity code before the title starts."""
    long_title = " ".join(["Advanced"] * 12) + " Systems"
    _seed_schedule(db, title=long_title)
    body = client.get(_feed_url(db, "FAC001")).text
    for line in body.split("\r\n"):
        assert len(line.encode("utf-8")) <= 75, line
    assert f"SUMMARY:[CS500] {long_title}" in _unfold(body)


def test_folding_never_cuts_a_character_in_half(client, db, seed_users):
    """The limit is 75 octets and not 75 characters. A title in a script that
    spends three bytes a character would have a cut counted in bytes land in
    the middle of one, and the reader gets mojibake."""
    long_title = " ".join(["प्रबंधन"] * 20)
    _seed_schedule(db, title=long_title)
    body = client.get(_feed_url(db, "FAC001")).text
    for line in body.split("\r\n"):
        assert len(line.encode("utf-8")) <= 75, line
    assert f"SUMMARY:[CS500] {long_title}" in _unfold(body)


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
