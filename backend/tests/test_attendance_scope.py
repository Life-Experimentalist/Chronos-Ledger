# Copyright 2026 Chronos Ledger Contributors
# Licensed under the Apache License, Version 2.0
"""Who may read a session's roster, and who may read or write its notes.

H-03 and H-04: all three of these routes took nothing but a valid token, so
any member could count upwards through the ledger ids and read who attended
every session in the organization, read every note written about one, and
write a note onto any session including one that did not exist.
"""

import datetime

from app.core.security import hash_password
from app.core.time import org_today
from app.models.db import (
    Activity,
    DailyLedger,
    InstitutionalRole,
    PlanningCycle,
    User,
    VerificationLedger,
    VerificationMetric,
)
from tests.conftest import ADMIN_PASSWORD, MEMBER_PASSWORD, STAFF_PASSWORD, login

TODAY = org_today()
OTHER_PASSWORD = "OtherPass123!"
_OTHER_HASH = hash_password(OTHER_PASSWORD)
ABSENT_LEDGER_ID = 999999


def _world(db):
    """A CSE session led by FAC001 with two members marked, and an ECE one.

    Also the two people the scope rules turn on and no fixture has: a unit
    admin, so the branch that compares units is exercised at all, and a staff
    member who leads nothing, so "signed in as staff" is not mistaken for
    "runs this session".
    """
    db.add_all(
        [
            User(
                id="DAD001",
                full_name="CSE Unit Admin",
                email_address="cse.unitadmin@test.internal",
                credential_secure_hash=_OTHER_HASH,
                role_type=InstitutionalRole.UNIT_ADMIN,
                unit_code="CSE",
                initial_login_state=False,
            ),
            User(
                id="FAC900",
                full_name="Bystander Staff",
                email_address="bystander.staff@test.internal",
                credential_secure_hash=_OTHER_HASH,
                role_type=InstitutionalRole.STAFF,
                unit_code="CSE",
                initial_login_state=False,
            ),
            User(
                id="STU900",
                full_name="Second Member",
                email_address="second.member@test.internal",
                credential_secure_hash=_OTHER_HASH,
                role_type=InstitutionalRole.MEMBER,
                unit_code="CSE",
                initial_login_state=False,
            ),
        ]
    )
    cycle = PlanningCycle(
        cycle_label="Scope 2026",
        date_bounds_start=TODAY - datetime.timedelta(days=30),
        date_bounds_end=TODAY + datetime.timedelta(days=90),
        operational_status=True,
    )
    db.add(cycle)
    db.flush()
    ledgers = {}
    for unit, code, lead in (("CSE", "CS800", "FAC001"), ("ECE", "EC800", None)):
        activity = Activity(
            activity_code=code,
            activity_title=f"{unit} Activity",
            unit_code=unit,
            cycle_id=cycle.id,
        )
        db.add(activity)
        db.flush()
        ledger = DailyLedger(
            target_date=TODAY,
            activity_id=activity.id,
            active_lead_id=lead,
            target_room_identifier="LH-800",
        )
        db.add(ledger)
        db.flush()
        ledgers[unit] = ledger
    db.add_all(
        [
            VerificationLedger(
                ledger_instance_id=ledgers["CSE"].id,
                member_id=member,
                marking_status=VerificationMetric.PRESENT,
                authorizing_agent_id="FAC001",
            )
            for member in ("STU001", "STU900")
        ]
    )
    db.commit()
    return ledgers


def _roster(client, headers, ledger_id):
    return client.get(f"/api/v1/attendance/ledger/{ledger_id}", headers=headers)


# -- The roster ---------------------------------------------------------------


def test_a_member_reads_only_their_own_row(client, db, seed_users):
    """The whole roster used to come back, so who attended what was readable
    by anybody with an account."""
    ledgers = _world(db)
    headers = login(client, "member@test.internal", MEMBER_PASSWORD)

    res = _roster(client, headers, ledgers["CSE"].id)
    assert res.status_code == 200, res.text
    assert [row["member_id"] for row in res.json()] == ["STU001"]


def test_a_member_with_no_row_gets_an_empty_roster(client, db, seed_users):
    """Not a refusal: they are entitled to the answer, and the answer is that
    nothing has been recorded for them."""
    ledgers = _world(db)
    headers = login(client, "member@test.internal", MEMBER_PASSWORD)

    res = _roster(client, headers, ledgers["ECE"].id)
    assert res.status_code == 200, res.text
    assert res.json() == []


def test_the_lead_reads_the_whole_roster(client, db, seed_users):
    ledgers = _world(db)
    headers = login(client, "staff@test.internal", STAFF_PASSWORD)

    res = _roster(client, headers, ledgers["CSE"].id)
    assert res.status_code == 200, res.text
    assert {row["member_id"] for row in res.json()} == {"STU001", "STU900"}


def test_an_admin_inside_the_unit_reads_the_whole_roster(client, db, seed_users):
    ledgers = _world(db)
    headers = login(client, "cse.unitadmin@test.internal", OTHER_PASSWORD)

    res = _roster(client, headers, ledgers["CSE"].id)
    assert res.status_code == 200, res.text
    assert len(res.json()) == 2


def test_a_super_admin_reads_the_whole_roster(client, db, seed_users):
    ledgers = _world(db)
    headers = login(client, "admin@test.internal", ADMIN_PASSWORD)

    res = _roster(client, headers, ledgers["CSE"].id)
    assert res.status_code == 200, res.text
    assert len(res.json()) == 2


def test_an_admin_outside_the_unit_is_refused_the_roster(client, db, seed_users):
    ledgers = _world(db)
    headers = login(client, "cse.unitadmin@test.internal", OTHER_PASSWORD)

    assert _roster(client, headers, ledgers["ECE"].id).status_code == 403


def test_staff_who_do_not_run_the_session_are_refused_the_roster(client, db, seed_users):
    """Refused rather than handed an empty list. An empty list here would read
    as "nobody came", which is a worse answer than being told no."""
    ledgers = _world(db)
    headers = login(client, "bystander.staff@test.internal", OTHER_PASSWORD)

    assert _roster(client, headers, ledgers["CSE"].id).status_code == 403


def test_a_roster_for_a_session_that_does_not_exist_is_404(client, db, seed_users):
    _world(db)
    headers = login(client, "admin@test.internal", ADMIN_PASSWORD)

    assert _roster(client, headers, ABSENT_LEDGER_ID).status_code == 404


# -- Annotations --------------------------------------------------------------


def test_the_lead_writes_a_note_and_reads_it_back(client, db, seed_users):
    ledgers = _world(db)
    headers = login(client, "staff@test.internal", STAFF_PASSWORD)
    body = {
        "ledger_instance_id": ledgers["CSE"].id,
        "classification_tag": "LATE_START",
        "annotation_payload": "Started ten minutes late, lab setup.",
    }

    written = client.post("/api/v1/attendance/annotations", json=body, headers=headers)
    assert written.status_code == 200, written.text
    assert written.json()["creator_id"] == "FAC001"

    read = client.get(
        f"/api/v1/attendance/annotations/{ledgers['CSE'].id}",
        headers=headers,
    )
    assert read.status_code == 200, read.text
    assert [n["classification_tag"] for n in read.json()] == ["LATE_START"]


def test_a_member_cannot_read_the_notes(client, db, seed_users):
    """No per-member row to fall back to here: a note is about the session,
    and in a hospital that is a handover."""
    ledgers = _world(db)
    headers = login(client, "member@test.internal", MEMBER_PASSWORD)

    res = client.get(f"/api/v1/attendance/annotations/{ledgers['CSE'].id}", headers=headers)
    assert res.status_code == 403


def test_an_admin_outside_the_unit_cannot_read_the_notes(client, db, seed_users):
    ledgers = _world(db)
    headers = login(client, "cse.unitadmin@test.internal", OTHER_PASSWORD)

    res = client.get(f"/api/v1/attendance/annotations/{ledgers['ECE'].id}", headers=headers)
    assert res.status_code == 403


def test_a_member_cannot_write_a_note(client, db, seed_users):
    ledgers = _world(db)
    headers = login(client, "member@test.internal", MEMBER_PASSWORD)
    body = {
        "ledger_instance_id": ledgers["CSE"].id,
        "classification_tag": "INCIDENT",
        "annotation_payload": "Anyone with an account could write this.",
    }

    res = client.post("/api/v1/attendance/annotations", json=body, headers=headers)
    assert res.status_code == 403


def test_a_note_against_a_session_that_does_not_exist_is_404(client, db, seed_users):
    """It used to be accepted, leaving a row pointing at nothing."""
    _world(db)
    headers = login(client, "admin@test.internal", ADMIN_PASSWORD)
    body = {
        "ledger_instance_id": ABSENT_LEDGER_ID,
        "classification_tag": "INCIDENT",
        "annotation_payload": "Pointing at nothing.",
    }

    res = client.post("/api/v1/attendance/annotations", json=body, headers=headers)
    assert res.status_code == 404


def test_notes_for_a_session_that_does_not_exist_are_404(client, db, seed_users):
    _world(db)
    headers = login(client, "admin@test.internal", ADMIN_PASSWORD)

    res = client.get(f"/api/v1/attendance/annotations/{ABSENT_LEDGER_ID}", headers=headers)
    assert res.status_code == 404


# -- The bounds on a note -----------------------------------------------------


def test_a_tag_longer_than_the_column_is_refused(client, db, seed_users):
    """classification_tag is a String(30). Unbounded it was an error from the
    database on Postgres and a silent truncation on SQLite, which is why this
    is the only thing proving the bound: the suite runs on SQLite."""
    ledgers = _world(db)
    headers = login(client, "staff@test.internal", STAFF_PASSWORD)
    body = {
        "ledger_instance_id": ledgers["CSE"].id,
        "classification_tag": "T" * 31,
        "annotation_payload": "Fits.",
    }

    res = client.post("/api/v1/attendance/annotations", json=body, headers=headers)
    assert res.status_code == 422


def test_a_note_longer_than_the_ceiling_is_refused(client, db, seed_users):
    ledgers = _world(db)
    headers = login(client, "staff@test.internal", STAFF_PASSWORD)
    body = {
        "ledger_instance_id": ledgers["CSE"].id,
        "classification_tag": "INCIDENT",
        "annotation_payload": "x" * 4001,
    }

    res = client.post("/api/v1/attendance/annotations", json=body, headers=headers)
    assert res.status_code == 422


def test_an_empty_note_is_refused(client, db, seed_users):
    ledgers = _world(db)
    headers = login(client, "staff@test.internal", STAFF_PASSWORD)
    body = {
        "ledger_instance_id": ledgers["CSE"].id,
        "classification_tag": "INCIDENT",
        "annotation_payload": "",
    }

    res = client.post("/api/v1/attendance/annotations", json=body, headers=headers)
    assert res.status_code == 422
