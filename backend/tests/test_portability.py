# Copyright 2026 Chronos Ledger Contributors
# Licensed under the Apache License, Version 2.0
"""The archive export and import (app/services/portability.py, docs/portability.md)."""

import io
import json
import os
import zipfile
from datetime import UTC, date, datetime, time, timedelta, timezone
from decimal import Decimal

import pytest
from sqlalchemy import func, inspect, select
from sqlalchemy.orm import Session

from app import standalone
from app.api.v1.endpoints import admin
from app.core.bootstrap import SEEDED_ADMIN_ID
from app.core.database import Base, sqlite_engine
from app.core.schema import SCHEMA_VERSION, ensure_schema
from app.core.security import ABSENT_ACCOUNT_HASH, hash_api_key, verify_password
from app.models.db import (
    AccessReadiness,
    Activity,
    ActivityEnrollment,
    ApiKey,
    AuditRecord,
    ChangeMarker,
    DailyLedger,
    DynamicState,
    ExecutionMode,
    FederatedIdentity,
    FederatedIssuer,
    FederatedIssuerKey,
    FederatedRoleMap,
    GuestGateRegistry,
    IdempotencyRecord,
    InstitutionalRole,
    LedgerAnnotation,
    LogVerificationState,
    PlanningCycle,
    RefreshToken,
    Reservation,
    ReservationStatus,
    Resource,
    ResourceType,
    ReverseRsvpLog,
    StructuralMasterSlot,
    User,
    VerificationLedger,
    VerificationMetric,
    WebhookSubscription,
)
from app.services import portability
from app.services.portability import (
    EXCLUDED,
    EXPORTED,
    FORMAT_VERSION,
    SECRET_COLUMNS,
    ArchiveError,
    export_archive,
    import_archive,
)
from tests.conftest import ADMIN_PASSWORD, STAFF_PASSWORD, login

# Only ever handed to the import in these tests. Not a password for anything.
IMPORT_PASSWORD = "import-test-password-not-real"
# Values the secret columns hold in the seed, so a test can look for them in
# the archive's bytes.
FEED_TOKEN = "feed-token-for-tests-only"
SEEDED_KEY = "ck_portability_test_key_for_the_seed"
VISIT_CODE_HASH = "a" * 64
# Shaped like a webhook secret and signing nothing anywhere.
WEBHOOK_SECRET = "whsec_" + "dGVzdHMtb25seS13ZWJob29rLXNlY3JldC0zMmJ5dGU="


@pytest.fixture(autouse=True)
def _environment_restored():
    """The CLI tests run configure_environment, which writes os.environ."""
    saved = dict(os.environ)
    yield
    os.environ.clear()
    os.environ.update(saved)


@pytest.fixture()
def engines(tmp_path):
    """sqlite_engine on a new file per name, so foreign keys are enforced."""
    made = []

    def make(name):
        engine = sqlite_engine(f"sqlite:///{(tmp_path / f'{name}.db').as_posix()}")
        made.append(engine)
        return engine

    yield make
    for engine in made:
        engine.dispose()


@pytest.fixture()
def source(engines):
    engine = engines("source")
    seed(engine)
    return engine


def seed(engine):
    """A row in every table, with the values most likely to come back different.

    A manager whose id sorts after the person reporting to them, times with
    microseconds, numbers at their column's scale,
    a booking that runs past midnight, nulls, text that is not ASCII, and
    every member of every enum.
    """
    ensure_schema(engine)
    with Session(engine) as db:
        admin = db.get(User, SEEDED_ADMIN_ID)
        admin.initial_login_state = False
        db.add_all(
            [
                PlanningCycle(
                    id=1,
                    cycle_label="Spring",
                    date_bounds_start=date(2026, 1, 5),
                    date_bounds_end=date(2026, 5, 29),
                    operational_status=True,
                ),
                PlanningCycle(
                    id=2,
                    cycle_label="Autumn",
                    date_bounds_start=date(2026, 8, 3),
                    date_bounds_end=date(2026, 12, 18),
                ),
            ]
        )
        db.flush()
        db.add_all(
            [
                User(
                    id="ZM900",
                    full_name="Zoë Ångström",
                    email_address="zoe@test.internal",
                    credential_secure_hash=ABSENT_ACCOUNT_HASH,
                    role_type=InstitutionalRole.UNIT_ADMIN,
                    unit_code="CSE",
                    current_occupancy_index=AccessReadiness.CRITICAL_DO_NOT_DISTURB,
                    initial_login_state=False,
                    calendar_feed_token=FEED_TOKEN,
                ),
                User(
                    id="AS100",
                    full_name="Staff Reporting Up",
                    email_address="staff@test.internal",
                    credential_secure_hash=ABSENT_ACCOUNT_HASH,
                    role_type=InstitutionalRole.STAFF,
                    unit_code="CSE",
                    assigned_base_station="Block A",
                    current_occupancy_index=AccessReadiness.BUSY,
                    reporting_line_manager="ZM900",
                ),
                User(
                    id="BM200",
                    full_name="Member 名前",
                    email_address="member@test.internal",
                    credential_secure_hash=ABSENT_ACCOUNT_HASH,
                    role_type=InstitutionalRole.MEMBER,
                    unit_code="CSE",
                    current_occupancy_index=AccessReadiness.VERY_FREE,
                    calendar_feed_token=None,
                    deactivated_at=datetime(2026, 3, 1, 3, 45, 30, 123456, tzinfo=UTC),
                ),
                User(
                    id="SVC001",
                    full_name="Service Account",
                    email_address="svc@test.internal",
                    credential_secure_hash=ABSENT_ACCOUNT_HASH,
                    role_type=InstitutionalRole.MEMBER,
                ),
            ]
        )
        db.flush()
        db.add_all(
            [
                Activity(
                    id=1,
                    activity_code="CS101",
                    activity_title="Introduction, with a comma",
                    unit_code="CSE",
                    cycle_id=1,
                ),
                Activity(
                    id=2,
                    activity_code="CS102",
                    activity_title="Night lab",
                    unit_code="CSE",
                    cycle_id=2,
                ),
            ]
        )
        db.add_all(
            [
                Resource(
                    id=1,
                    code="R101",
                    label="Room 101",
                    unit_code="CSE",
                    capacity=40,
                    latitude=Decimal("12.97159360"),
                    longitude=Decimal("-77.59456270"),
                    altitude_target=Decimal("920.50"),
                ),
                Resource(
                    id=2,
                    code="P-AS100",
                    label="Staff Reporting Up",
                    resource_type=ResourceType.PERSON,
                    user_id="AS100",
                    active=False,
                ),
            ]
        )
        db.flush()
        db.add(ActivityEnrollment(id=1, activity_id=1, member_id="BM200"))
        db.add_all(
            [
                StructuralMasterSlot(
                    id=1,
                    day_of_week_index=1,
                    time_window_start=time(9, 0),
                    time_window_end=time(10, 30),
                    activity_id=1,
                    primary_lead_id="AS100",
                    resource_id=1,
                    target_room_identifier="R101",
                ),
                StructuralMasterSlot(
                    id=2,
                    day_of_week_index=7,
                    time_window_start=time(22, 0),
                    time_window_end=time(6, 0),
                    activity_id=2,
                ),
            ]
        )
        db.flush()
        db.add_all(
            [
                DailyLedger(
                    id=1,
                    target_date=date(2026, 1, 5),
                    time_window_start=time(9, 0),
                    time_window_end=time(10, 30),
                    master_slot_id=1,
                    activity_id=1,
                    active_lead_id="AS100",
                    substitute_lead_id="ZM900",
                    resource_id=1,
                    target_room_identifier="R101",
                    delivery_format=ExecutionMode.PHYSICAL,
                    latitude_target=Decimal("12.97159360"),
                    longitude_target=Decimal("77.59456270"),
                    altitude_target=Decimal("0.05"),
                    precision_radius_meters=25,
                    operational_state=DynamicState.PROXY_SUBSTITUTE,
                ),
                DailyLedger(
                    id=2,
                    target_date=date(2026, 1, 6),
                    activity_id=2,
                    delivery_format=ExecutionMode.ONLINE_STREAM,
                    virtual_connection_string="https://meet.test.internal/x",
                    operational_state=DynamicState.SCHEDULED,
                ),
            ]
            + [
                DailyLedger(
                    id=10 + i, target_date=date(2026, 2, 1), activity_id=1, operational_state=s
                )
                for i, s in enumerate(
                    [
                        DynamicState.ON_LEAVE,
                        DynamicState.LUNCH,
                        DynamicState.INTERNAL_MEETING,
                        DynamicState.ADHOC_EVENT,
                    ]
                )
            ]
        )
        db.flush()
        db.add_all(
            [
                Reservation(
                    id=1,
                    resource_id=1,
                    reserved_date=date(2026, 1, 9),
                    time_window_start=time(22, 0),
                    time_window_end=time(6, 0),
                    purpose="Night shift",
                    requested_by_id="SVC001",
                    idempotency_key="key-1",
                    request_fingerprint="f" * 64,
                    created_at=datetime(2026, 1, 2, 3, 4, 5, 678901, tzinfo=UTC),
                ),
                Reservation(
                    id=2,
                    resource_id=1,
                    reserved_date=date(2026, 1, 10),
                    time_window_start=time(8, 0),
                    time_window_end=time(9, 0),
                    purpose="Cancelled meeting",
                    requested_by_id=None,
                    idempotency_key="key-2",
                    request_fingerprint="e" * 64,
                    status=ReservationStatus.CANCELLED,
                    created_at=datetime(2026, 1, 2, 3, 4, 5, tzinfo=UTC),
                    cancelled_at=datetime(2026, 1, 3, 0, 0, 0, 1, tzinfo=UTC),
                ),
            ]
        )
        db.add_all(
            [
                ReverseRsvpLog(
                    id=i + 1,
                    submitting_user_id="BM200",
                    target_absence_date=date(2026, 1, 12),
                    end_date=date(2026, 1, 14) if i == 0 else None,
                    context_justification="Unwell\nback on Thursday",
                    approval_state=state,
                    authorized_by_user_id="AS100" if i else None,
                )
                for i, state in enumerate(LogVerificationState)
            ]
        )
        db.add_all(
            [
                VerificationLedger(
                    id=i + 1,
                    ledger_instance_id=1 if i == 0 else 10 + i,
                    member_id="BM200",
                    marking_status=metric,
                    authorizing_agent_id="AS100" if i else None,
                    modification_timestamp=datetime(2026, 1, 5, 9, 5, i, 500, tzinfo=UTC),
                )
                for i, metric in enumerate(VerificationMetric)
            ]
        )
        db.add(
            LedgerAnnotation(
                id=1,
                ledger_instance_id=1,
                creator_id="AS100",
                classification_tag="NOTE",
                annotation_payload='Quotes " and backslash \\ and emoji 📅',
                distribution_timestamp=datetime(2026, 1, 5, 9, 0, tzinfo=UTC),
            )
        )
        db.add(
            GuestGateRegistry(
                id=1,
                guest_name="Visitor",
                contact_phone="+10000000000",
                originating_body="Elsewhere",
                target_staff_id="AS100",
                visitation_intent="Meeting",
                handshake_status=LogVerificationState.VERIFIED_APPROVED,
                timestamp_marked=datetime(2026, 1, 5, 8, 0, tzinfo=UTC),
                visit_code_hash=VISIT_CODE_HASH,
                visit_code_expires_at=datetime(2026, 1, 5, 9, 0, tzinfo=UTC),
                decided_by_id="ZM900",
                visit_expires_at=datetime(2026, 1, 5, 10, 0, tzinfo=UTC),
            )
        )
        db.add(
            RefreshToken(
                id=1,
                token_hash="b" * 64,
                user_id=SEEDED_ADMIN_ID,
                family_id="family",
                expires_at=datetime(2026, 1, 10, tzinfo=UTC),
            )
        )
        db.add(
            IdempotencyRecord(
                id=1,
                caller="user:BM200",
                key="retry-1",
                request_hash="c" * 64,
                status_code=201,
                response_headers='{"content-type": "application/json"}',
                response_body=b"{}",
                created_at=datetime(2026, 1, 5, 9, 0, tzinfo=UTC),
            )
        )
        db.add(
            ApiKey(
                id=1,
                key_hash=hash_api_key(SEEDED_KEY),
                key_prefix=SEEDED_KEY[:12],
                label="Scheduler",
                user_id="SVC001",
                scopes="schedule:read,resources:write",
                expires_at=datetime(2027, 1, 1, tzinfo=UTC),
                created_at=datetime(2026, 1, 1, tzinfo=UTC),
            )
        )
        db.add(
            AuditRecord(
                id=1,
                at=datetime(2026, 1, 5, 8, 31, 2, 114000, tzinfo=UTC),
                actor_id="SVC001",
                api_key_id=1,
                method="POST",
                path="/api/v1/resources/1/reservations",
                status_code=201,
            )
        )
        db.add(
            ChangeMarker(
                id=1,
                entity_kind="reservation",
                entity_id=1,
                change_kind="created",
                at=datetime(2026, 1, 5, 8, 31, 2, tzinfo=UTC),
            )
        )
        issuer = FederatedIssuer(
            id=1,
            issuer="https://idp.test.internal",
            display_name="Test IdP",
            audience="chronos",
            enabled=True,
            created_at=datetime(2026, 1, 1, tzinfo=UTC),
        )
        db.add(issuer)
        db.flush()
        db.add(
            FederatedIssuerKey(
                id=1,
                issuer_id=1,
                kid="k1",
                public_key="-----BEGIN PUBLIC KEY-----\nnot a real key\n-----END PUBLIC KEY-----\n",
                not_before=datetime(2026, 1, 1, tzinfo=UTC),
                created_at=datetime(2026, 1, 1, tzinfo=UTC),
            )
        )
        db.add(
            FederatedRoleMap(
                id=1, issuer_id=1, group_claim_value="staff", role_type=InstitutionalRole.STAFF
            )
        )
        db.add(
            FederatedIdentity(
                id=1,
                issuer_id=1,
                subject="sub-1",
                user_id="BM200",
                created_at=datetime(2026, 1, 1, tzinfo=UTC),
            )
        )
        # Paused already, because an import without secrets pauses every
        # subscription, and the round trip without secrets must still give
        # the same bytes.
        db.add(
            WebhookSubscription(
                id=1,
                url="https://receiver.test/hooks",
                event_types="reservation.created,reservation.updated",
                active=True,
                paused_at=datetime(2026, 1, 6, 9, 0, tzinfo=UTC),
                consecutive_failures=5,
                cursor=1,
                secret=WEBHOOK_SECRET,
                previous_secret=None,
                previous_secret_expires_at=None,
                created_at=datetime(2026, 1, 1, tzinfo=UTC),
                updated_at=datetime(2026, 1, 6, 9, 0, tzinfo=UTC),
            )
        )
        db.commit()


def export_bytes(engine, include_secrets=False) -> bytes:
    buffer = io.BytesIO()
    with engine.connect() as connection:
        export_archive(connection, buffer, include_secrets=include_secrets)
    return buffer.getvalue()


def members(archive: bytes) -> dict[str, bytes]:
    with zipfile.ZipFile(io.BytesIO(archive)) as opened:
        return {name: opened.read(name) for name in opened.namelist()}


def rewrite(archive: bytes, **manifest_changes) -> bytes:
    """The same archive with some manifest fields replaced."""
    contents = members(archive)
    manifest = json.loads(contents["manifest.json"])
    manifest.update(manifest_changes)
    contents["manifest.json"] = json.dumps(manifest).encode()
    return build(contents)


def build(contents: dict[str, bytes]) -> bytes:
    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, "w") as out:
        for name, body in contents.items():
            out.writestr(name, body)
    return buffer.getvalue()


def row_count(engine, table: str) -> int:
    if not inspect(engine).has_table(table):
        return 0
    with engine.connect() as connection:
        return connection.execute(
            select(func.count()).select_from(Base.metadata.tables[table])
        ).scalar_one()


# Coverage.


def test_every_table_is_exported_or_excluded_on_purpose():
    """A new table fails this until somebody decides whether it travels.

    Exported means it goes in the archive. Excluded means it is in
    portability.EXCLUDED with the reason it stays behind.
    """
    every = {table.name for table in Base.metadata.sorted_tables}
    exported = {table.name for table in EXPORTED}
    assert exported | set(EXCLUDED) == every
    assert not exported & set(EXCLUDED)
    for table, columns in SECRET_COLUMNS.items():
        assert table in exported
        assert set(columns) <= set(Base.metadata.tables[table].columns.keys())


def test_the_seed_puts_a_row_in_every_exported_table(source):
    manifest = json.loads(members(export_bytes(source))["manifest.json"])
    empty = [entry["name"] for entry in manifest["tables"] if entry["rows"] == 0]
    assert empty == []


# Round trips.


@pytest.mark.parametrize("include_secrets", [False, True])
def test_export_import_export_gives_the_same_bytes(source, engines, include_secrets):
    first = export_bytes(source, include_secrets)
    target = engines("target")
    import_archive(target, io.BytesIO(first), admin_password=IMPORT_PASSWORD)
    second = export_bytes(target, include_secrets)
    assert second == first


def test_the_archive_layout(source):
    archive = export_bytes(source)
    with zipfile.ZipFile(io.BytesIO(archive)) as opened:
        names = opened.namelist()
        infos = opened.infolist()
    assert names == [f"{t.name}.jsonl" for t in EXPORTED] + ["manifest.json"]
    assert {info.date_time for info in infos} == {(1980, 1, 1, 0, 0, 0)}
    manifest = json.loads(members(archive)["manifest.json"])
    assert manifest["format"] == "chronos-ledger-archive"
    assert manifest["format_version"] == FORMAT_VERSION
    assert manifest["schema_version"] == SCHEMA_VERSION
    # The seed has a row in each excluded table, and none of them is here.
    assert "refresh_tokens.jsonl" not in names
    assert "idempotency_records.jsonl" not in names
    assert {entry["name"] for entry in manifest["tables"]}.isdisjoint(EXCLUDED)


def test_values_are_written_in_one_form(source):
    contents = members(export_bytes(source))
    users = [json.loads(line) for line in contents["users.jsonl"].splitlines()]
    # Primary key order, bytewise.
    assert [u["id"] for u in users] == sorted(u["id"] for u in users)
    member = next(u for u in users if u["id"] == "BM200")
    assert member["deactivated_at"] == "2026-03-01T03:45:30.123456+00:00"
    assert member["full_name"] == "Member 名前"
    assert "名前".encode() in contents["users.jsonl"]
    resource = json.loads(contents["resources.jsonl"].splitlines()[0])
    assert resource["latitude"] == "12.97159360"
    assert resource["altitude_target"] == "920.50"
    slot = json.loads(contents["structural_master_slots.jsonl"].splitlines()[1])
    assert (slot["time_window_start"], slot["time_window_end"]) == (
        "22:00:00.000000",
        "06:00:00.000000",
    )


def test_every_time_is_written_in_utc():
    """SQLite hands back naive values and PostgreSQL aware ones in its session zone."""
    column = User.__table__.c.deactivated_at
    ist = timezone(timedelta(hours=5, minutes=30))
    expected = "2026-03-01T03:45:30.000000+00:00"
    assert portability._encode(column, datetime(2026, 3, 1, 9, 15, 30, tzinfo=ist)) == expected
    assert portability._encode(column, datetime(2026, 3, 1, 3, 45, 30)) == expected
    decoded = portability._decode(column, "2026-03-01T09:15:30.000000+05:30")
    assert decoded == datetime(2026, 3, 1, 3, 45, 30, tzinfo=UTC)
    assert decoded.utcoffset() == timedelta(0)


def test_a_manager_later_in_key_order_survives_the_import(source, engines):
    target = engines("target")
    import_archive(target, io.BytesIO(export_bytes(source)), admin_password=IMPORT_PASSWORD)
    with Session(target) as db:
        assert db.get(User, "AS100").reporting_line_manager == "ZM900"


# Secrets.


def test_secrets_are_left_out_by_default(source):
    contents = members(export_bytes(source))
    manifest = json.loads(contents["manifest.json"])
    assert manifest["secrets_included"] is False
    assert manifest["omitted_columns"] == {k: list(v) for k, v in SECRET_COLUMNS.items()}
    everything = b"".join(contents.values())
    assert FEED_TOKEN.encode() not in everything
    assert hash_api_key(SEEDED_KEY).encode() not in everything
    assert VISIT_CODE_HASH.encode() not in everything
    assert WEBHOOK_SECRET.encode() not in everything
    assert b"$2b$" not in everything
    for table, columns in SECRET_COLUMNS.items():
        for line in contents[f"{table}.jsonl"].splitlines():
            assert not set(columns) & set(json.loads(line))


def test_secrets_are_written_with_the_flag(source):
    contents = members(export_bytes(source, include_secrets=True))
    manifest = json.loads(contents["manifest.json"])
    assert manifest["secrets_included"] is True
    assert manifest["omitted_columns"] == {}
    everything = b"".join(contents.values())
    assert FEED_TOKEN.encode() in everything
    assert hash_api_key(SEEDED_KEY).encode() in everything
    assert VISIT_CODE_HASH.encode() in everything
    assert WEBHOOK_SECRET.encode() in everything
    assert b"$2b$" in everything


def test_an_import_without_secrets_opens_nothing_but_the_administrator(source, engines):
    target = engines("target")
    import_archive(target, io.BytesIO(export_bytes(source)), admin_password=IMPORT_PASSWORD)
    with Session(target) as db:
        admin = db.get(User, SEEDED_ADMIN_ID)
        assert verify_password(IMPORT_PASSWORD, admin.credential_secure_hash)
        staff = db.get(User, "ZM900")
        assert staff.credential_secure_hash == ABSENT_ACCOUNT_HASH
        assert staff.calendar_feed_token is None
        key = db.get(ApiKey, 1)
        assert key.key_hash != hash_api_key(SEEDED_KEY)
        assert key.scopes == "schedule:read,resources:write"
        assert db.get(GuestGateRegistry, 1).visit_code_hash is None


def test_an_import_without_secrets_needs_the_administrator_password(source, engines):
    target = engines("target")
    with pytest.raises(ArchiveError, match="INITIAL_ADMIN_PASSWORD"):
        import_archive(target, io.BytesIO(export_bytes(source)))
    assert row_count(target, "users") == 0


def test_an_import_with_secrets_keeps_every_password(source, engines):
    target = engines("target")
    import_archive(target, io.BytesIO(export_bytes(source, include_secrets=True)))
    with Session(target) as db, Session(source) as original:
        assert (
            db.get(User, SEEDED_ADMIN_ID).credential_secure_hash
            == original.get(User, SEEDED_ADMIN_ID).credential_secure_hash
        )
        assert db.get(ApiKey, 1).key_hash == hash_api_key(SEEDED_KEY)
        assert db.get(WebhookSubscription, 1).secret == WEBHOOK_SECRET


def test_an_import_without_secrets_pauses_webhooks_with_a_new_secret(source, engines):
    with Session(source) as db:
        subscription = db.get(WebhookSubscription, 1)
        subscription.paused_at = None
        subscription.previous_secret = WEBHOOK_SECRET.replace("dGVz", "b2xk")
        subscription.previous_secret_expires_at = datetime(2026, 1, 7, tzinfo=UTC)
        db.commit()
    target = engines("target")
    import_archive(target, io.BytesIO(export_bytes(source)), admin_password=IMPORT_PASSWORD)
    with Session(target) as db:
        imported = db.get(WebhookSubscription, 1)
        assert imported.paused_at is not None
        assert imported.secret.startswith("whsec_")
        assert imported.secret != WEBHOOK_SECRET
        assert imported.previous_secret is None
        assert imported.previous_secret_expires_at is None
        assert imported.cursor == 1
        assert imported.url == "https://receiver.test/hooks"


# Refusals.


def test_a_database_with_rows_is_refused(source, engines):
    target = engines("target")
    ensure_schema(target)  # a first start leaves the default organization and its administrator
    with pytest.raises(ArchiveError, match="not empty: organizations, users"):
        import_archive(target, io.BytesIO(export_bytes(source)), admin_password=IMPORT_PASSWORD)
    assert row_count(target, "users") == 1


def test_an_empty_database_with_tables_is_accepted(source, engines):
    target = engines("target")
    Base.metadata.create_all(target)
    import_archive(target, io.BytesIO(export_bytes(source)), admin_password=IMPORT_PASSWORD)
    assert row_count(target, "users") == row_count(source, "users")


@pytest.mark.parametrize("version", [0, 2, 99])
def test_another_format_version_is_refused_naming_both(source, engines, version):
    archive = rewrite(export_bytes(source), format_version=version)
    target = engines("target")
    with pytest.raises(ArchiveError) as refused:
        import_archive(target, io.BytesIO(archive), admin_password=IMPORT_PASSWORD)
    message = str(refused.value)
    assert f"format version {version}" in message
    assert f"format version {FORMAT_VERSION}" in message
    if version > FORMAT_VERSION:
        assert "newer than this release reads" in message
    assert row_count(target, "users") == 0


@pytest.mark.parametrize("version", ["1", True, None])
def test_a_format_version_that_is_not_a_number_is_refused(source, engines, version):
    archive = rewrite(export_bytes(source), format_version=version)
    with pytest.raises(ArchiveError, match="does not know"):
        import_archive(engines("target"), io.BytesIO(archive))


def test_another_schema_version_is_refused_naming_both(source, engines):
    archive = rewrite(export_bytes(source), schema_version="0")
    with pytest.raises(ArchiveError) as refused:
        import_archive(engines("target"), io.BytesIO(archive))
    assert "schema version '0'" in str(refused.value)
    assert f"schema version {SCHEMA_VERSION!r}" in str(refused.value)


def test_a_file_that_is_not_an_archive_is_refused(engines):
    with pytest.raises(ArchiveError, match="zip"):
        import_archive(engines("target"), io.BytesIO(b"not a zip"))
    with pytest.raises(ArchiveError, match="manifest.json"):
        import_archive(engines("target"), io.BytesIO(build({"users.jsonl": b""})))


def test_a_bad_row_rolls_the_whole_import_back(source, engines):
    """The last table to go in is broken, so everything before it has to vanish."""
    contents = members(export_bytes(source, include_secrets=True))
    last = f"{EXPORTED[-1].name}.jsonl"
    contents[last] = contents[last] + b'{"id": "not a number"}\n'
    target = engines("target")
    with pytest.raises(ArchiveError, match=last):
        import_archive(target, io.BytesIO(build(contents)))
    for table in EXPORTED:
        assert row_count(target, table.name) == 0
    # And the database is still one an import will go into.
    import_archive(target, io.BytesIO(export_bytes(source, include_secrets=True)))


def test_a_row_count_that_disagrees_with_the_manifest_is_refused(source, engines):
    contents = members(export_bytes(source, include_secrets=True))
    first = contents["planning_cycles.jsonl"].splitlines(keepends=True)
    contents["planning_cycles.jsonl"] = first[0]
    with pytest.raises(ArchiveError, match="planning_cycles.jsonl has 1 rows"):
        import_archive(engines("target"), io.BytesIO(build(contents)))


def test_an_unknown_column_is_refused(source, engines):
    contents = members(export_bytes(source, include_secrets=True))
    row = json.loads(contents["planning_cycles.jsonl"].splitlines()[0])
    row["colour"] = "red"
    rest = contents["planning_cycles.jsonl"].splitlines(keepends=True)[1:]
    contents["planning_cycles.jsonl"] = json.dumps(row).encode() + b"\n" + b"".join(rest)
    with pytest.raises(ArchiveError, match="unexpected \\['colour'\\]"):
        import_archive(engines("target"), io.BytesIO(build(contents)))


# The route.

EXPORT = "/api/v1/admin/export"


def test_the_export_route_needs_a_signed_in_caller(client, seed_users):
    assert client.get(EXPORT).status_code == 401


def test_the_export_route_is_for_org_admins_only(client, seed_users):
    headers = login(client, "staff@test.internal", STAFF_PASSWORD)
    assert client.get(EXPORT, headers=headers).status_code == 403


def _export_records(db):
    db.expire_all()
    return db.query(AuditRecord).filter(AuditRecord.path == EXPORT).all()


def test_the_export_route_returns_the_archive(client, seed_users):
    headers = login(client, "admin@test.internal", ADMIN_PASSWORD)
    response = client.get(EXPORT, headers=headers)
    assert response.status_code == 200, response.text
    assert response.headers["content-type"] == "application/zip"
    assert "chronos-ledger-export.zip" in response.headers["content-disposition"]
    contents = members(response.content)
    manifest = json.loads(contents["manifest.json"])
    users = {e["name"]: e["rows"] for e in manifest["tables"]}["users"]
    assert users == 3


def test_the_export_route_never_includes_secrets(client, seed_users):
    """Secrets come only from the CLI; the old query parameter does nothing."""
    headers = login(client, "admin@test.internal", ADMIN_PASSWORD)
    response = client.get(EXPORT, params={"include_secrets": "true"}, headers=headers)
    assert response.status_code == 200, response.text
    contents = members(response.content)
    assert json.loads(contents["manifest.json"])["secrets_included"] is False
    assert b"$2b$" not in contents["users.jsonl"]


def test_an_export_is_audited_with_the_signed_in_caller(client, db, seed_users):
    headers = login(client, "admin@test.internal", ADMIN_PASSWORD)
    assert client.get(EXPORT, headers=headers).status_code == 200
    [record] = _export_records(db)
    assert (record.actor_id, record.api_key_id) == ("ADM001", None)
    assert (record.method, record.status_code) == ("GET", 200)


def test_an_export_is_audited_with_the_key_that_asked(client, db, seed_users):
    key = ApiKey(
        key_hash=hash_api_key(SEEDED_KEY),
        key_prefix=SEEDED_KEY[:12],
        label="exporter",
        user_id="ADM001",
        scopes="admin:read",
    )
    db.add(key)
    db.commit()
    assert client.get(EXPORT, headers={"X-API-Key": SEEDED_KEY}).status_code == 200
    [record] = _export_records(db)
    assert (record.actor_id, record.api_key_id) == ("ADM001", key.id)
    assert (record.method, record.status_code) == ("GET", 200)


def test_a_failed_export_is_audited_and_leaves_no_file(client, db, seed_users, monkeypatch):
    made = []
    mkstemp = admin.tempfile.mkstemp

    def noting_mkstemp(**kwargs):
        handle, path = mkstemp(**kwargs)
        made.append(path)
        return handle, path

    def fail(connection, target, include_secrets, organization_id):
        raise RuntimeError("export failed")

    monkeypatch.setattr(admin.tempfile, "mkstemp", noting_mkstemp)
    monkeypatch.setattr(admin, "export_archive", fail)
    headers = login(client, "admin@test.internal", ADMIN_PASSWORD)
    with pytest.raises(RuntimeError, match="export failed"):
        client.get(EXPORT, headers=headers)
    [record] = _export_records(db)
    assert (record.actor_id, record.status_code) == ("ADM001", 500)
    assert not os.path.exists(made[0])


# The CLI.


def test_the_cli_exports_and_imports(source, tmp_path, capsys, monkeypatch):
    archive = tmp_path / "out.zip"
    source_dir = tmp_path / "source-dir"
    source_dir.mkdir()
    source.dispose()
    (tmp_path / "source.db").replace(source_dir / standalone.DATABASE_FILE)

    assert standalone.main(["export", "--data-dir", str(source_dir), "--to", str(archive)]) == 0
    assert not (source_dir / standalone.SIGNING_KEY_FILE).exists()
    # Never over an existing file.
    assert standalone.main(["export", "--data-dir", str(source_dir), "--to", str(archive)]) == 1

    target_dir = tmp_path / "target-dir"
    monkeypatch.setenv("INITIAL_ADMIN_PASSWORD", IMPORT_PASSWORD)
    assert standalone.main(["import", "--data-dir", str(target_dir), "--from", str(archive)]) == 0
    # A second import finds the rows the first one wrote.
    assert standalone.main(["import", "--data-dir", str(target_dir), "--from", str(archive)]) == 1
    assert "not empty" in capsys.readouterr().err

    again = tmp_path / "again.zip"
    assert standalone.main(["export", "--data-dir", str(target_dir), "--to", str(again)]) == 0
    assert again.read_bytes() == archive.read_bytes()


def test_the_cli_says_when_there_is_no_database(tmp_path, capsys):
    target = tmp_path / "out.zip"
    assert standalone.main(["export", "--data-dir", str(tmp_path), "--to", str(target)]) == 1
    assert "No database" in capsys.readouterr().err
    assert not target.exists()


def test_the_cli_import_refuses_a_missing_archive(tmp_path, capsys):
    missing = tmp_path / "missing.zip"
    assert standalone.main(["import", "--data-dir", str(tmp_path), "--from", str(missing)]) == 1
    assert "No archive" in capsys.readouterr().err


def test_portability_names_no_table_twice():
    assert len({t.name for t in portability.EXPORTED}) == len(portability.EXPORTED)
