# Copyright 2026 Chronos Ledger Contributors
# Licensed under the Apache License, Version 2.0
"""Activities, their slots and their enrollments, written through the API.

The CSV import was the only way to put an activity on the timetable. These
endpoints are a second way in, and the test that matters most here is that
the second way produces the same days as the first.
"""

import datetime

from app.core import clock
from app.core.recurrence import weekly_rule
from app.core.security import hash_password
from app.core.time import org_today
from app.cron.ledger_generator import materialize_horizon
from app.models.db import (
    Activity,
    ActivityEnrollment,
    DailyLedger,
    InstitutionalRole,
    PlanningCycle,
    Resource,
    StructuralMasterSlot,
    User,
    VerificationLedger,
    VerificationMetric,
)
from app.services.resource import get_or_create_room
from tests.conftest import ADMIN_PASSWORD, STAFF_PASSWORD, login, weekly
from tests.test_ingestion import HEADER, _upload

# These tests are about the days a create writes (see conftest).
FILL_LEDGER_ON_IMPORT = True

TODAY = org_today()
DAY = datetime.timedelta(days=1)
UNIT_ADMIN_PASSWORD = "UnitAdminPass123!"
REPLAYED = "Idempotency-Replayed"


def _cycle(db):
    cycle = PlanningCycle(
        cycle_label="Activities 2026",
        date_bounds_start=TODAY - 30 * DAY,
        date_bounds_end=TODAY + 90 * DAY,
        operational_status=True,
    )
    db.add(cycle)
    db.commit()
    return cycle


def _admin(client):
    return login(client, "admin@test.internal", ADMIN_PASSWORD)


def _unit_admin(client, db):
    db.add(
        User(
            id="DAD001",
            full_name="CSE Unit Admin",
            email_address="unitadmin@test.internal",
            credential_secure_hash=hash_password(UNIT_ADMIN_PASSWORD),
            role_type=InstitutionalRole.UNIT_ADMIN,
            unit_code="CSE",
            initial_login_state=False,
        )
    )
    db.commit()
    return login(client, "unitadmin@test.internal", UNIT_ADMIN_PASSWORD)


def _create_activity(client, headers, cycle_id, code="CS201", unit="CSE", title="Data Structures"):
    return client.post(
        "/api/v1/schedule/activities",
        json={
            "activity_code": code,
            "activity_title": title,
            "unit_code": unit,
            "cycle_id": cycle_id,
        },
        headers=headers,
    )


def _create_slot(client, headers, activity_id, weekday, start, end, room, lead="FAC001"):
    return client.post(
        "/api/v1/schedule/slots",
        json={
            "rrule": weekly_rule(weekday),
            "time_window_start": start,
            "time_window_end": end,
            "activity_id": activity_id,
            "primary_lead_id": lead,
            "target_room_identifier": room,
        },
        headers=headers,
    )


def _ledger_snapshot(db):
    """Every daily_ledger row, with generated ids swapped for what they name.

    id is dropped. activity_id becomes the activity code, master_slot_id the
    slot's weekday and start, and resource_id the room code, so two states
    built separately compare equal when they describe the same days. Every
    other column is compared as it is.
    """
    db.expire_all()
    columns = [c.name for c in DailyLedger.__table__.columns if c.name != "id"]
    rows = []
    for row in db.query(DailyLedger).all():
        record = {name: getattr(row, name) for name in columns}
        record["activity_id"] = db.get(Activity, row.activity_id).activity_code
        slot = db.get(StructuralMasterSlot, row.master_slot_id)
        record["master_slot_id"] = (slot.dtstart.isoweekday(), slot.time_window_start)
        record["resource_id"] = db.get(Resource, row.resource_id).code
        rows.append(record)
    return sorted(rows, key=lambda r: (r["target_date"], r["time_window_start"]))


def test_an_activity_created_through_the_api_gets_the_days_a_csv_import_gives_it(
    client, db, seed_users
):
    headers = _admin(client)
    cycle = _cycle(db)

    csv_text = "\n".join(
        [
            HEADER,
            "STU001,Member One,member@test.internal,CS201,Data Structures,CSE,"
            "1,09:00,10:00,FAC001,LH-101",
            "STU001,Member One,member@test.internal,CS201,Data Structures,CSE,"
            "3,14:00,15:30,FAC001,LH-102",
        ]
    )
    r = _upload(client, headers, cycle.id, csv_text)
    assert r.status_code == 200, r.text
    from_csv = _ledger_snapshot(db)

    # Back to an empty timetable, keeping the users, the cycle and the rooms.
    db.query(DailyLedger).delete()
    db.query(ActivityEnrollment).delete()
    db.query(StructuralMasterSlot).delete()
    db.query(Activity).delete()
    db.commit()
    assert _ledger_snapshot(db) == []

    r = _create_activity(client, headers, cycle.id)
    assert r.status_code == 201, r.text
    activity_id = r.json()["id"]
    r = _create_slot(client, headers, activity_id, 1, "09:00:00", "10:00:00", "LH-101")
    assert r.status_code == 200, r.text
    r = _create_slot(client, headers, activity_id, 3, "14:00:00", "15:30:00", "LH-102")
    assert r.status_code == 200, r.text
    r = client.post(
        f"/api/v1/schedule/activities/{activity_id}/enrollments",
        json={"member_id": "STU001"},
        headers=headers,
    )
    assert r.status_code == 201, r.text
    from_api = _ledger_snapshot(db)

    # Two weekly slots over a 28 day horizon.
    assert len(from_csv) == 8
    assert from_api == from_csv


def test_create_read_and_rename_an_activity(client, db, seed_users):
    headers = _admin(client)
    cycle = _cycle(db)

    r = _create_activity(client, headers, cycle.id)
    assert r.status_code == 201, r.text
    body = r.json()
    assert body["activity_code"] == "CS201"
    assert body["unit_code"] == "CSE"
    assert body["retired_at"] is None

    r = client.get(f"/api/v1/schedule/activities/{body['id']}", headers=headers)
    assert r.status_code == 200
    assert r.json()["activity_title"] == "Data Structures"

    r = client.patch(
        f"/api/v1/schedule/activities/{body['id']}",
        json={"activity_title": "Algorithms"},
        headers=headers,
    )
    assert r.status_code == 200, r.text
    assert r.json()["activity_title"] == "Algorithms"

    r = client.get(f"/api/v1/schedule/activities?cycle_id={cycle.id}", headers=headers)
    assert [a["id"] for a in r.json()] == [body["id"]]


def test_a_second_activity_with_the_same_code_in_the_cycle_is_refused(client, db, seed_users):
    headers = _admin(client)
    cycle = _cycle(db)
    assert _create_activity(client, headers, cycle.id).status_code == 201

    r = _create_activity(client, headers, cycle.id, title="Again")
    assert r.status_code == 409
    assert r.json()["code"] == "ALREADY_EXISTS"


def test_an_activity_in_a_cycle_that_does_not_exist_is_refused(client, db, seed_users):
    r = _create_activity(client, _admin(client), 9999)
    assert r.status_code == 404
    assert r.json()["code"] == "NOT_FOUND"


def test_a_unit_admin_writes_only_inside_their_unit(client, db, seed_users):
    cycle = _cycle(db)
    other = Activity(
        activity_code="EC201", activity_title="Signals", unit_code="ECE", cycle_id=cycle.id
    )
    db.add(other)
    db.flush()
    other_slot = StructuralMasterSlot(
        **weekly(2),
        time_window_start=datetime.time(9, 0),
        time_window_end=datetime.time(10, 0),
        activity_id=other.id,
        resource_id=get_or_create_room("EC-1", db).id,
    )
    db.add(other_slot)
    db.commit()
    headers = _unit_admin(client, db)

    r = _create_activity(client, headers, cycle.id, code="EC202", unit="ECE")
    assert r.status_code == 403
    assert r.json()["code"] == "OUTSIDE_UNIT"

    for method, url, body in (
        ("patch", f"/api/v1/schedule/activities/{other.id}", {"activity_title": "X"}),
        ("post", f"/api/v1/schedule/activities/{other.id}/retire", None),
        ("post", f"/api/v1/schedule/activities/{other.id}/enrollments", {"member_id": "STU001"}),
        ("delete", f"/api/v1/schedule/activities/{other.id}/enrollments/STU001", None),
        ("get", f"/api/v1/schedule/activities/{other.id}/enrollments", None),
        ("post", f"/api/v1/schedule/slots/{other_slot.id}/retire", None),
    ):
        kwargs = {"headers": headers}
        if body is not None:
            kwargs["json"] = body
        r = getattr(client, method)(url, **kwargs)
        assert r.status_code == 403, (method, url, r.text)
        assert r.json()["code"] == "OUTSIDE_UNIT"

    # Inside their own unit they create, enroll and retire.
    r = _create_activity(client, headers, cycle.id, code="CS301", unit="CSE")
    assert r.status_code == 201, r.text
    own = r.json()["id"]
    r = client.post(
        f"/api/v1/schedule/activities/{own}/enrollments",
        json={"member_id": "STU001"},
        headers=headers,
    )
    assert r.status_code == 201, r.text
    r = client.post(f"/api/v1/schedule/activities/{own}/retire", headers=headers)
    assert r.status_code == 200, r.text


def test_staff_cannot_write_activities(client, db, seed_users):
    cycle = _cycle(db)
    headers = login(client, "staff@test.internal", STAFF_PASSWORD)
    r = _create_activity(client, headers, cycle.id)
    assert r.status_code == 403


def _activity_with_days(client, db, headers):
    """An activity with one slot on tomorrow's weekday, its days written, and one past day."""
    cycle = _cycle(db)
    activity_id = _create_activity(client, headers, cycle.id).json()["id"]
    tomorrow = TODAY + DAY
    r = _create_slot(client, headers, activity_id, tomorrow.isoweekday(), "09:00", "10:00", "LH-1")
    assert r.status_code == 200, r.text
    slot_id = r.json()["id"]
    past = DailyLedger(
        target_date=tomorrow - 7 * DAY,
        time_window_start=datetime.time(9, 0),
        time_window_end=datetime.time(10, 0),
        master_slot_id=slot_id,
        activity_id=activity_id,
        active_lead_id="FAC001",
        resource_id=get_or_create_room("LH-1", db).id,
    )
    db.add(past)
    db.commit()
    ahead = (
        db.query(DailyLedger)
        .filter(DailyLedger.master_slot_id == slot_id, DailyLedger.target_date >= TODAY)
        .order_by(DailyLedger.target_date)
        .all()
    )
    assert ahead and ahead[0].target_date == tomorrow
    return cycle, activity_id, slot_id, past.id, [row.id for row in ahead]


def _mark(db, row_id):
    db.add(
        VerificationLedger(
            ledger_instance_id=row_id, member_id="STU001", marking_status=VerificationMetric.PRESENT
        )
    )
    db.commit()


def test_retiring_an_activity_keeps_its_history_and_stops_new_days(client, db, seed_users):
    headers = _admin(client)
    cycle, activity_id, slot_id, past_id, ahead = _activity_with_days(client, db, headers)
    _mark(db, ahead[0])

    r = client.post(f"/api/v1/schedule/activities/{activity_id}/retire", headers=headers)
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["slots_retired"] == 1
    assert body["ledger_rows_removed"] == len(ahead) - 1
    assert body["ledger_rows_kept"] == 1

    db.expire_all()
    # The past day and the marked day ahead stay; the unmarked days ahead go.
    assert {row.id for row in db.query(DailyLedger).all()} == {past_id, ahead[0]}
    assert db.get(Activity, activity_id).retired_at is not None
    assert db.get(StructuralMasterSlot, slot_id).retired_at is not None

    # Nothing is written for it again.
    assert materialize_horizon(db, cycle.id) == 0

    listed = client.get(f"/api/v1/schedule/activities?cycle_id={cycle.id}", headers=headers)
    assert listed.json() == []
    listed = client.get(
        f"/api/v1/schedule/activities?cycle_id={cycle.id}&include_retired=true", headers=headers
    )
    assert [a["id"] for a in listed.json()] == [activity_id]
    assert client.get(f"/api/v1/schedule/activities/{activity_id}", headers=headers).json()[
        "retired_at"
    ]

    # A retired activity is read, not written.
    for method, url, json in (
        ("patch", f"/api/v1/schedule/activities/{activity_id}", {"activity_title": "X"}),
        ("post", f"/api/v1/schedule/activities/{activity_id}/retire", None),
        ("post", f"/api/v1/schedule/activities/{activity_id}/enrollments", {"member_id": "STU001"}),
    ):
        kwargs = {"headers": headers}
        if json is not None:
            kwargs["json"] = json
        r = getattr(client, method)(url, **kwargs)
        assert r.status_code == 409, (method, url, r.text)
        assert r.json()["code"] == "STATE_CONFLICT"
    r = _create_slot(client, headers, activity_id, 2, "11:00", "12:00", "LH-2")
    assert r.status_code == 409
    assert r.json()["code"] == "STATE_CONFLICT"


def test_retiring_a_slot_keeps_a_marked_day_where_delete_refuses(client, db, seed_users):
    headers = _admin(client)
    cycle, activity_id, slot_id, past_id, ahead = _activity_with_days(client, db, headers)
    _mark(db, ahead[0])

    r = client.delete(f"/api/v1/schedule/slots/{slot_id}", headers=headers)
    assert r.status_code == 409

    r = client.post(f"/api/v1/schedule/slots/{slot_id}/retire", headers=headers)
    assert r.status_code == 200, r.text
    assert r.json()["ledger_rows_removed"] == len(ahead) - 1
    assert r.json()["ledger_rows_kept"] == 1

    db.expire_all()
    assert {row.id for row in db.query(DailyLedger).all()} == {past_id, ahead[0]}
    assert db.get(Activity, activity_id).retired_at is None
    assert materialize_horizon(db, cycle.id) == 0

    slots = client.get(f"/api/v1/schedule/slots?cycle_id={cycle.id}", headers=headers).json()
    assert slots == []
    slots = client.get(
        f"/api/v1/schedule/slots?cycle_id={cycle.id}&include_retired=true", headers=headers
    ).json()
    assert [s["id"] for s in slots] == [slot_id]

    for method, url, json in (
        ("patch", f"/api/v1/schedule/slots/{slot_id}", {"time_window_start": "08:00"}),
        ("delete", f"/api/v1/schedule/slots/{slot_id}", None),
        ("post", f"/api/v1/schedule/slots/{slot_id}/retire", None),
    ):
        kwargs = {"headers": headers}
        if json is not None:
            kwargs["json"] = json
        r = getattr(client, method)(url, **kwargs)
        assert r.status_code == 409, (method, url, r.text)
        assert r.json()["code"] == "STATE_CONFLICT"


def test_a_retired_slot_no_longer_holds_its_room(client, db, seed_users):
    headers = _admin(client)
    cycle, activity_id, slot_id, _, _ = _activity_with_days(client, db, headers)
    weekday = (TODAY + DAY).isoweekday()
    other = _create_activity(client, headers, cycle.id, code="CS202").json()["id"]

    r = _create_slot(client, headers, other, weekday, "09:00", "10:00", "LH-1")
    assert r.status_code == 409
    assert r.json()["code"] == "RESOURCE_CONFLICT"

    assert (
        client.post(f"/api/v1/schedule/slots/{slot_id}/retire", headers=headers).status_code == 200
    )
    r = _create_slot(client, headers, other, weekday, "09:00", "10:00", "LH-1")
    assert r.status_code == 200, r.text


def test_enrollments_are_added_listed_and_removed(client, db, seed_users):
    headers = _admin(client)
    cycle, activity_id, _, past_id, ahead = _activity_with_days(client, db, headers)
    url = f"/api/v1/schedule/activities/{activity_id}/enrollments"

    r = client.post(url, json={"member_id": "STU001"}, headers=headers)
    assert r.status_code == 201, r.text
    assert r.json() == {"activity_id": activity_id, "member_id": "STU001"}
    r = client.post(url, json={"member_id": "STU001"}, headers=headers)
    assert r.status_code == 409
    assert r.json()["code"] == "ALREADY_EXISTS"
    r = client.post(url, json={"member_id": "NOBODY"}, headers=headers)
    assert r.status_code == 404
    assert r.json()["code"] == "NOT_FOUND"

    assert [e["member_id"] for e in client.get(url, headers=headers).json()] == ["STU001"]

    _mark(db, past_id)
    rows_before = db.query(DailyLedger).count()
    r = client.delete(f"{url}/STU001", headers=headers)
    assert r.status_code == 200, r.text
    db.expire_all()
    assert client.get(url, headers=headers).json() == []
    # Days belong to the slot, and the attendance already taken stays.
    assert db.query(DailyLedger).count() == rows_before
    assert db.query(VerificationLedger).filter_by(member_id="STU001").count() == 1

    r = client.delete(f"{url}/STU001", headers=headers)
    assert r.status_code == 404


def test_a_deactivated_member_is_not_enrolled(client, db, seed_users):
    headers = _admin(client)
    cycle = _cycle(db)
    activity_id = _create_activity(client, headers, cycle.id).json()["id"]
    seed_users["member"].deactivated_at = clock.now()
    db.commit()

    r = client.post(
        f"/api/v1/schedule/activities/{activity_id}/enrollments",
        json={"member_id": "STU001"},
        headers=headers,
    )
    assert r.status_code == 422
    assert r.json()["code"] == "USER_DEACTIVATED"


def test_an_import_naming_a_retired_activity_is_refused(client, db, seed_users):
    headers = _admin(client)
    cycle = _cycle(db)
    activity_id = _create_activity(client, headers, cycle.id).json()["id"]
    assert (
        client.post(
            f"/api/v1/schedule/activities/{activity_id}/retire", headers=headers
        ).status_code
        == 200
    )

    csv_text = "\n".join(
        [
            HEADER,
            "STU001,Member One,member@test.internal,CS201,Data Structures,CSE,"
            "1,09:00,10:00,FAC001,LH-101",
        ]
    )
    r = _upload(client, headers, cycle.id, csv_text)
    assert r.status_code == 422
    assert "retired" in r.text
    assert db.query(StructuralMasterSlot).count() == 0


def test_a_retried_create_returns_the_same_activity_and_makes_one(client, db, seed_users):
    headers = {**_admin(client), "Idempotency-Key": "activity-1"}
    cycle = _cycle(db)

    first = _create_activity(client, headers, cycle.id)
    assert first.status_code == 201, first.text
    assert REPLAYED not in first.headers
    again = _create_activity(client, headers, cycle.id)
    assert again.status_code == 201
    assert again.headers[REPLAYED] == "true"
    assert again.json() == first.json()
    assert db.query(Activity).count() == 1
