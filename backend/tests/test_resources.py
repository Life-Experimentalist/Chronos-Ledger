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
from tests.conftest import ADMIN_PASSWORD, login
from tests.test_import_corrections import TOMORROW, _csv, _row, _slots
from tests.test_ingestion import _make_cycle, _upload


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
