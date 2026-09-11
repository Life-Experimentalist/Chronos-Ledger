# Copyright 2026 Chronos Ledger Contributors
# Licensed under the Apache License, Version 2.0
"""A room is a row now, and every path that writes one points at the same row.

Before this, a room was a bare string copied onto every slot and every day
generated from it. These tests pin down the two properties that make the
foreign key worth having: one row per room no matter how many slots name it,
and every write path resolving through it rather than inventing a spelling.
"""

import datetime

from app.core.time import org_today
from app.cron.ledger_generator import generate_daily_ledger_entries
from app.models.db import (
    Activity,
    DailyLedger,
    Resource,
    ResourceType,
    StructuralMasterSlot,
)
from app.services.master_slot import propagate_slot_corrections
from tests.conftest import ADMIN_PASSWORD, MEMBER_PASSWORD, STAFF_PASSWORD, login
from tests.test_import_corrections import TOMORROW, _csv, _row, _slots
from tests.test_ingestion import _make_cycle, _upload
from tests.test_reservations import _issue_key, _unit_admin


def _rooms(db):
    return db.query(Resource).order_by(Resource.code).all()


def test_an_imported_room_becomes_a_resource(client, db, seed_users):
    cycle = _make_cycle(db)
    headers = login(client, "admin@test.internal", ADMIN_PASSWORD)
    assert _upload(client, headers, cycle.id, _csv(_row(room="LH-201"))).status_code == 200

    db.expire_all()
    rooms = _rooms(db)
    assert [r.code for r in rooms] == ["LH-201"]
    assert rooms[0].resource_type == ResourceType.ROOM
    assert rooms[0].label == "LH-201"
    # Nothing in a CSV knows a room's capacity or where it is.
    assert rooms[0].capacity is None
    assert rooms[0].latitude is None
    assert rooms[0].active is True

    slot = _slots(db)[0]
    assert slot.resource_id == rooms[0].id
    # The name is kept in step until every reader has moved to the key.
    assert slot.target_room_identifier == "LH-201"


def test_two_classes_in_one_room_share_one_resource(client, db, seed_users):
    cycle = _make_cycle(db)
    headers = login(client, "admin@test.internal", ADMIN_PASSWORD)
    csv_text = _csv(
        _row(code="MA201", room="LH-201"),
        _row(code="PH101", title="Optics", room="LH-201", start="11:00", end="12:00"),
    )
    assert _upload(client, headers, cycle.id, csv_text).status_code == 200

    db.expire_all()
    assert len(_rooms(db)) == 1
    assert _slots(db, "MA201")[0].resource_id == _slots(db, "PH101")[0].resource_id


def test_a_second_import_reuses_the_room_it_already_made(client, db, seed_users):
    cycle = _make_cycle(db)
    headers = login(client, "admin@test.internal", ADMIN_PASSWORD)
    assert _upload(client, headers, cycle.id, _csv(_row(room="LH-201"))).status_code == 200
    assert _upload(client, headers, cycle.id, _csv(_row(room="LH-201"))).status_code == 200

    db.expire_all()
    assert [r.code for r in _rooms(db)] == ["LH-201"]


def test_a_corrected_room_moves_the_slot_to_another_resource(client, db, seed_users):
    cycle = _make_cycle(db)
    headers = login(client, "admin@test.internal", ADMIN_PASSWORD)
    assert _upload(client, headers, cycle.id, _csv(_row(room="LH-201"))).status_code == 200
    body = _upload(client, headers, cycle.id, _csv(_row(room="LH-305"))).json()

    db.expire_all()
    rooms = {r.code: r.id for r in _rooms(db)}
    # The room it left is not deleted: other cycles and past days still name it.
    assert sorted(rooms) == ["LH-201", "LH-305"]
    assert _slots(db)[0].resource_id == rooms["LH-305"]
    assert body["slots_corrected"] == 1


def test_a_generated_day_carries_the_slot_resource(client, db, seed_users):
    cycle = _make_cycle(db)
    headers = login(client, "admin@test.internal", ADMIN_PASSWORD)
    assert _upload(client, headers, cycle.id, _csv(_row(room="LH-201"))).status_code == 200
    assert generate_daily_ledger_entries(TOMORROW, db) == 1

    db.expire_all()
    entry = db.query(DailyLedger).one()
    assert entry.resource_id == _slots(db)[0].resource_id
    assert entry.resource.code == "LH-201"


def test_a_correction_moves_a_planned_day_to_the_new_resource(client, db, seed_users):
    cycle = _make_cycle(db)
    headers = login(client, "admin@test.internal", ADMIN_PASSWORD)
    assert _upload(client, headers, cycle.id, _csv(_row(room="LH-201"))).status_code == 200
    assert generate_daily_ledger_entries(TOMORROW, db) == 1
    body = _upload(client, headers, cycle.id, _csv(_row(room="LH-305"))).json()

    db.expire_all()
    entry = db.query(DailyLedger).one()
    assert entry.resource.code == "LH-305"
    assert entry.resource_id == _slots(db)[0].resource_id
    assert body["ledger_rows_updated"] == 1


def test_a_renamed_room_is_not_read_as_every_class_having_moved(client, db, seed_users):
    """The reason propagation compares keys and not names.

    Renaming a room is one row in resources. If the comparison were on the
    name, that single edit would look like every day of every class in that
    room had been moved somewhere else, and each one would lose its geofence
    for a change that did not move anybody.
    """
    cycle = _make_cycle(db)
    headers = login(client, "admin@test.internal", ADMIN_PASSWORD)
    assert _upload(client, headers, cycle.id, _csv(_row(room="LH-201"))).status_code == 200
    assert generate_daily_ledger_entries(TOMORROW, db) == 1

    entry = db.query(DailyLedger).one()
    entry.latitude_target = 12.9716
    entry.longitude_target = 77.5946
    room = _rooms(db)[0]
    room.code = "Lecture Hall 201"
    room.label = "Lecture Hall 201"
    # The string on the slot mirrors the code, so a rename moves it too. The
    # day still carries the old spelling, which is exactly the state a name
    # comparison would misread as a move.
    _slots(db)[0].target_room_identifier = room.code
    db.commit()

    result = propagate_slot_corrections(_slots(db), db)
    db.commit()

    db.expire_all()
    entry = db.query(DailyLedger).one()
    assert result["ledger_rows_updated"] == 1
    assert entry.latitude_target is not None


def test_a_slot_created_through_the_api_gets_a_resource(client, db, seed_users):
    cycle = _make_cycle(db)
    headers = login(client, "admin@test.internal", ADMIN_PASSWORD)
    activity = Activity(
        activity_code="CH101",
        activity_title="Thermodynamics",
        unit_code="CSE",
        cycle_id=cycle.id,
    )
    db.add(activity)
    db.commit()

    r = client.post(
        "/api/v1/schedule/slots",
        headers=headers,
        json={
            "day_of_week_index": 3,
            "time_window_start": "14:00:00",
            "time_window_end": "15:00:00",
            "activity_id": activity.id,
            "primary_lead_id": "FAC001",
            "target_room_identifier": "LAB-4",
        },
    )
    assert r.status_code == 200, r.text

    db.expire_all()
    slot = db.query(StructuralMasterSlot).filter(StructuralMasterSlot.id == r.json()["id"]).one()
    assert slot.resource.code == "LAB-4"

    listed = client.get("/api/v1/schedule/slots", headers=headers).json()
    assert [s["resource_id"] for s in listed if s["id"] == slot.id] == [slot.resource_id]


def test_a_room_named_with_stray_spaces_is_the_same_room(client, db, seed_users):
    cycle = _make_cycle(db)
    headers = login(client, "admin@test.internal", ADMIN_PASSWORD)
    csv_text = _csv(
        _row(code="MA201", room="LH-201"),
        _row(code="PH101", title="Optics", room=" LH-201 ", start="11:00", end="12:00"),
    )
    assert _upload(client, headers, cycle.id, csv_text).status_code == 200

    db.expire_all()
    assert [r.code for r in _rooms(db)] == ["LH-201"]


def test_a_past_day_can_name_a_room_no_slot_names(client, db, seed_users):
    """Why the backfill reads the ledger and not only the master slots.

    A day that has already happened keeps the room it was held in, and
    correcting the slot does not rewrite it. So the moment a class changes
    room, the old room survives only on past days: reading slots alone would
    leave those days with no resource to point at.
    """
    cycle = _make_cycle(db)
    headers = login(client, "admin@test.internal", ADMIN_PASSWORD)
    yesterday = org_today() - datetime.timedelta(days=1)
    day = yesterday.isoweekday()
    assert _upload(client, headers, cycle.id, _csv(_row(room="LH-201", day=day))).status_code == 200
    assert generate_daily_ledger_entries(yesterday, db) == 1
    assert _upload(client, headers, cycle.id, _csv(_row(room="LH-305", day=day))).status_code == 200

    db.expire_all()
    entry = db.query(DailyLedger).one()
    assert entry.resource.code == "LH-201"
    assert _slots(db)[0].resource.code == "LH-305"
    assert entry.resource_id != _slots(db)[0].resource_id


# -- Created through the API ----------------------------------------------------


def _create(client, headers, **body):
    return client.post("/api/v1/resources/", json={"code": "LH-9", **body}, headers=headers)


def test_a_room_can_be_created_before_any_timetable_names_it(client, db, seed_users):
    headers = login(client, "admin@test.internal", ADMIN_PASSWORD)
    res = _create(
        client,
        headers,
        code="  LH-9 ",
        label="Lecture Hall 9",
        unit_code="CSE",
        capacity=60,
        latitude=12.9716,
        longitude=77.5946,
    )
    assert res.status_code == 201, res.text
    body = res.json()
    # Trimmed the way the importer trims a room name.
    assert body["code"] == "LH-9"
    assert body["label"] == "Lecture Hall 9"
    assert body["resource_type"] == "ROOM"
    assert body["unit_code"] == "CSE"
    assert body["capacity"] == 60
    assert body["latitude"] == 12.9716
    assert body["user_id"] is None
    assert body["active"] is True


def test_a_later_import_finds_the_room_created_here(client, db, seed_users):
    """The row is the one the importer would have made, so there is one room."""
    headers = login(client, "admin@test.internal", ADMIN_PASSWORD)
    created = _create(client, headers, code="LH-201").json()
    assert created["label"] == "LH-201"

    cycle = _make_cycle(db)
    assert _upload(client, headers, cycle.id, _csv(_row(room="LH-201"))).status_code == 200

    db.expire_all()
    assert [r.id for r in _rooms(db)] == [created["id"]]
    assert _slots(db)[0].resource_id == created["id"]


def test_a_code_already_taken_is_409(client, db, seed_users):
    headers = login(client, "admin@test.internal", ADMIN_PASSWORD)
    assert _create(client, headers).status_code == 201

    again = _create(client, headers, code=" LH-9", label="Somewhere else")
    assert again.status_code == 409
    assert again.json()["detail"] == "a resource with that code already exists"
    # A retry that meets it reads the room back by code and carries on.
    found = client.get("/api/v1/resources/", params={"code": "LH-9"}, headers=headers)
    assert [r["label"] for r in found.json()] == ["LH-9"]


def test_only_a_super_admin_creates_rooms(client, db, seed_users):
    for headers in (
        login(client, "staff@test.internal", STAFF_PASSWORD),
        login(client, "member@test.internal", MEMBER_PASSWORD),
        _unit_admin(db, client),
    ):
        assert _create(client, headers).status_code == 403
    assert _rooms(db) == []


def test_a_blank_code_or_half_a_location_is_refused(client, db, seed_users):
    headers = login(client, "admin@test.internal", ADMIN_PASSWORD)
    assert _create(client, headers, code="   ").status_code == 422
    assert _create(client, headers, latitude=12.9716).status_code == 422
    assert _rooms(db) == []


def test_a_key_needs_resources_write_to_create_a_room(client, db, seed_users):
    admin = login(client, "admin@test.internal", ADMIN_PASSWORD)

    refused = _create(client, _issue_key(client, admin, scopes=["resources:read"]))
    assert refused.status_code == 403
    assert "resources:write" in refused.json()["detail"]

    key = _issue_key(client, admin, scopes=["resources:read", "resources:write"])
    assert _create(client, key).status_code == 201
