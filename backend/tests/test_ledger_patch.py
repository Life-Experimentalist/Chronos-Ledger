# Copyright 2026 Chronos Ledger Contributors
# Licensed under the Apache License, Version 2.0
"""PATCH /schedule/ledger/{id} and the fields it writes.

The route used to write whatever DailyLedgerUpdate carried and looked up
nobody named as a substitute, so an id that did not exist went to the
foreign key: a 500 on Postgres, a dangling id on SQLite.
"""

from tests.conftest import ADMIN_PASSWORD, login
from tests.test_unit_admin_scope import _seed_unit_world


def _patch(client, ledger_id, **fields):
    headers = login(client, "admin@test.internal", ADMIN_PASSWORD)
    return client.patch(f"/api/v1/schedule/ledger/{ledger_id}", headers=headers, json=fields)


def test_the_fields_sent_are_written_and_the_rest_are_kept(client, db, seed_users):
    _, ledgers = _seed_unit_world(db)
    day = ledgers["CSE"]
    r = _patch(
        client,
        day.id,
        substitute_lead_id="FAC001",
        delivery_format="ONLINE_STREAM",
        virtual_connection_string="https://meet.example.com/abc",
    )
    assert r.status_code == 200, r.text
    assert r.json() == {"message": "Updated"}
    db.refresh(day)
    assert day.substitute_lead_id == "FAC001"
    assert day.delivery_format.value == "ONLINE_STREAM"
    assert day.target_room_identifier == "LH-900"

    # A null leaves the field as it was.
    r = _patch(client, day.id, substitute_lead_id=None, precision_radius_meters=30)
    assert r.status_code == 200, r.text
    db.refresh(day)
    assert day.substitute_lead_id == "FAC001"
    assert day.precision_radius_meters == 30


def test_a_substitute_who_does_not_exist_is_a_404(client, db, seed_users):
    _, ledgers = _seed_unit_world(db)
    day = ledgers["CSE"]
    r = _patch(client, day.id, substitute_lead_id="NOBODY", precision_radius_meters=30)
    assert r.status_code == 404, r.text
    assert r.json()["detail"] == "Substitute not found"
    db.refresh(day)
    assert day.substitute_lead_id is None
    assert day.precision_radius_meters != 30
