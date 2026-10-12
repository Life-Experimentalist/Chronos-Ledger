# Copyright 2026 Chronos Ledger Contributors
# Licensed under the Apache License, Version 2.0
"""The embedded flavour: a host program's secret and its users, by header."""

import asyncio
import io
import json
import os
import sqlite3
import sys
import threading
import time
from contextlib import contextmanager
from datetime import UTC, datetime
from types import SimpleNamespace

import httpx
import pytest
import uvicorn
from fastapi.testclient import TestClient
from sqlalchemy import insert
from starlette.websockets import WebSocketDisconnect

import app.embedded as embedded_module
from app import standalone
from app.core import clock, database, host_identity
from app.core.database import get_db, get_session_opener, sqlite_engine
from app.core.host_identity import SYSTEM_ACTOR_ID, seed_system_account
from app.embedded import CLOCK_OPERATIONS, STRIPPED_OPERATIONS, build_app
from app.main import app as ordinary_app
from app.models.db import AuditRecord, InstitutionalRole, User
from tests.conftest import ADMIN_PASSWORD, login

SECRET = "h" * 40
HOST = {"Authorization": f"Host {SECRET}"}
AUDIT = "/api/v1/audit/"


def actor(actor_id, role="ORG_ADMIN", **extra):
    headers = {**HOST, "X-Chronos-Actor": actor_id, "X-Chronos-Actor-Role": role}
    for key, value in extra.items():
        headers[f"X-Chronos-Actor-{key.title()}"] = value
    return headers


@pytest.fixture()
def embedded(db):
    application = build_app(SECRET)

    def override_get_db():
        yield db

    @contextmanager
    def override_open_session():
        yield db

    application.dependency_overrides[get_db] = override_get_db
    application.dependency_overrides[get_session_opener] = lambda: override_open_session
    # No context manager: entering it runs the lifespan and the scheduler.
    return TestClient(application)


def test_a_short_secret_is_refused_before_anything_starts():
    with pytest.raises(ValueError, match="32 characters"):
        build_app("short")


def test_health_needs_no_secret(embedded):
    assert embedded.get("/health").status_code == 200


def test_everything_else_needs_the_secret(embedded):
    for res in (embedded.get("/api/v1/config"), embedded.get("/api/v1/users/")):
        assert res.status_code == 401
        assert res.json() == {"detail": "Not authenticated"}
        assert res.headers["WWW-Authenticate"] == "Host"


def test_a_wrong_secret_is_refused(embedded):
    wrong = {"Authorization": f"Host {'x' * 40}"}
    assert embedded.get("/api/v1/config", headers=wrong).status_code == 401
    bearer = {"Authorization": f"Bearer {SECRET}"}
    assert embedded.get("/api/v1/config", headers=bearer).status_code == 401


def test_a_public_route_needs_only_the_secret(embedded):
    assert embedded.get("/api/v1/config", headers=HOST).status_code == 200


def test_a_protected_route_needs_the_actor(embedded):
    res = embedded.get("/api/v1/users/", headers=HOST)
    assert res.status_code == 401
    assert "X-Chronos-Actor" in res.json()["detail"]


def test_an_unknown_role_is_refused(embedded):
    res = embedded.get(AUDIT, headers=actor("H-1", role="OWNER"))
    assert res.status_code == 400
    assert "ORG_ADMIN" in res.json()["detail"]


def test_an_actor_is_provisioned_on_first_sight(embedded, db):
    res = embedded.get(AUDIT, headers=actor("H-1", role="ORG_ADMIN", name="Pat Host"))
    assert res.status_code == 200, res.text

    user = db.get(User, "H-1")
    assert user.full_name == "Pat Host"
    assert user.role_type == InstitutionalRole.ORG_ADMIN
    assert user.email_address == "h-1@host.invalid"
    # The first-login gate is for Chronos-issued passwords; this account
    # has none, and the request above would have been refused by it.
    assert user.initial_login_state is False


def test_the_role_and_name_follow_the_host(embedded, db):
    assert embedded.get(AUDIT, headers=actor("H-2", role="MEMBER")).status_code == 403
    db.expire_all()
    assert db.get(User, "H-2").full_name == "H-2"

    res = embedded.get(
        AUDIT, headers=actor("H-2", role="ORG_ADMIN", name="Sam", email="Sam@Host.example")
    )
    assert res.status_code == 200
    db.expire_all()
    user = db.get(User, "H-2")
    assert user.role_type == InstitutionalRole.ORG_ADMIN
    assert user.full_name == "Sam"
    assert user.email_address == "sam@host.example"


def _unit_of(db, actor_id):
    db.expire_all()
    return db.get(User, actor_id).unit_code


def test_the_unit_is_set_on_first_sight(embedded, db):
    assert embedded.get(AUDIT, headers=actor("U-1", role="STAFF", unit=" CSE ")).status_code == 403
    assert _unit_of(db, "U-1") == "CSE"


def test_the_unit_follows_the_host(embedded, db):
    embedded.get(AUDIT, headers=actor("U-2", role="STAFF", unit="CSE"))
    embedded.get(AUDIT, headers=actor("U-2", role="STAFF", unit="ECE"))
    assert _unit_of(db, "U-2") == "ECE"


def test_an_empty_unit_header_clears_the_unit(embedded, db):
    embedded.get(AUDIT, headers=actor("U-3", role="STAFF", unit="CSE"))
    embedded.get(AUDIT, headers=actor("U-3", role="STAFF", unit=""))
    assert _unit_of(db, "U-3") is None


def test_no_unit_header_leaves_the_unit_alone(embedded, db):
    """A host that sets the unit through the users API keeps working."""
    embedded.get(AUDIT, headers=actor("U-4", role="STAFF"))
    db.get(User, "U-4").unit_code = "CSE"
    db.commit()
    embedded.get(AUDIT, headers=actor("U-4", role="STAFF"))
    assert _unit_of(db, "U-4") == "CSE"


def test_a_unit_code_past_the_column_is_refused(embedded, db):
    res = embedded.get(AUDIT, headers=actor("U-5", role="STAFF", unit="c" * 51))
    assert res.status_code == 400
    assert "X-Chronos-Actor-Unit" in res.json()["detail"]
    assert db.get(User, "U-5") is None


def test_the_system_actor_ignores_the_unit_header(embedded, db):
    seed_system_account(db)
    res = embedded.get(AUDIT, headers=actor(SYSTEM_ACTOR_ID, unit="CSE"))
    assert res.status_code == 200
    assert _unit_of(db, SYSTEM_ACTOR_ID) is None


def test_a_unit_administrator_given_a_unit_sees_only_that_unit(embedded):
    """The header lands in User.unit_code, which the unit scope checks read."""
    embedded.get(AUDIT, headers=actor("U-6", role="STAFF", unit="CSE"))
    embedded.get(AUDIT, headers=actor("U-7", role="STAFF", unit="ECE"))
    res = embedded.get("/api/v1/users/", headers=actor("U-8", role="UNIT_ADMIN", unit="CSE"))
    assert res.status_code == 200, res.text
    assert {row["id"] for row in res.json()} == {"U-6", "U-8"}


def test_a_seeded_account_the_host_asserts_is_let_in(embedded, db, seed_users):
    seed_users["staff"].initial_login_state = True
    db.commit()
    res = embedded.get(AUDIT, headers=actor("FAC001", role="ORG_ADMIN"))
    assert res.status_code == 200
    db.expire_all()
    assert db.get(User, "FAC001").initial_login_state is False


def test_an_email_another_account_has_is_refused(embedded, db, seed_users):
    res = embedded.get(AUDIT, headers=actor("H-3", email="admin@test.internal"))
    assert res.status_code == 409
    db.rollback()
    assert db.get(User, "H-3") is None


def _already_made(db, actor_id, role=InstitutionalRole.MEMBER):
    """The other request's row, committed through its own session.

    A Core insert, so the row is not in this session's identity map and the
    request below really does try to insert a second one.
    """
    db.execute(
        insert(User).values(
            id=actor_id,
            full_name=actor_id,
            email_address=f"{actor_id.lower()}@host.invalid",
            credential_secure_hash="not a hash",
            role_type=role,
            initial_login_state=False,
        )
    )
    db.commit()


def _stale_once(db, monkeypatch, actor_id):
    """This request's look at the account came back empty a moment too early."""
    real_get = db.get
    seen = []

    def stale_get(entity, ident, *args, **kwargs):
        if entity is User and ident == actor_id and not seen:
            seen.append(ident)
            return None
        return real_get(entity, ident, *args, **kwargs)

    monkeypatch.setattr(db, "get", stale_get)
    return real_get


def test_the_loser_of_a_first_sight_race_carries_on(embedded, db, monkeypatch):
    """Two first requests for one id both insert; the later one is refused on
    the primary key, which is not an email clash and must not fail the request."""
    _already_made(db, "H-7")
    real_get = _stale_once(db, monkeypatch, "H-7")

    res = embedded.get(AUDIT, headers=actor("H-7", role="ORG_ADMIN", name="Pat Host"))
    assert res.status_code == 200, res.text
    user = real_get(User, "H-7")
    assert user.role_type == InstitutionalRole.ORG_ADMIN
    assert user.full_name == "Pat Host"


def test_a_lost_race_still_refuses_a_taken_email(embedded, db, seed_users, monkeypatch):
    _already_made(db, "H-8")
    real_get = _stale_once(db, monkeypatch, "H-8")

    res = embedded.get(AUDIT, headers=actor("H-8", email="admin@test.internal"))
    assert res.status_code == 409
    db.rollback()
    assert real_get(User, "H-8").email_address == "h-8@host.invalid"


def test_an_unusable_email_is_refused(embedded):
    res = embedded.get(AUDIT, headers=actor("H-4", email=" "))
    assert res.status_code == 400


def test_the_system_actor_is_the_seeded_administrator(embedded, db):
    seed_system_account(db)
    seed_system_account(db)
    res = embedded.get(AUDIT, headers=actor(SYSTEM_ACTOR_ID, role="MEMBER"))
    assert res.status_code == 200
    db.expire_all()
    user = db.get(User, SYSTEM_ACTOR_ID)
    assert user.role_type == InstitutionalRole.ORG_ADMIN
    assert db.query(User).filter(User.id == SYSTEM_ACTOR_ID).count() == 1


def test_a_deactivated_account_stays_out(embedded, db, seed_users):
    seed_users["staff"].deactivated_at = datetime.now(UTC)
    db.commit()
    res = embedded.get(AUDIT, headers=actor("FAC001", role="ORG_ADMIN"))
    assert res.status_code == 401
    assert res.json()["detail"] == "Account deactivated"


def test_a_write_is_audited_under_the_hosts_id(embedded, db):
    res = embedded.put(
        "/api/v1/users/H-5/status",
        headers=actor("H-5", role="STAFF"),
        json={"status": "BUSY"},
    )
    assert res.status_code == 200, res.text
    db.expire_all()
    [record] = db.query(AuditRecord).filter(AuditRecord.path == "/api/v1/users/H-5/status").all()
    assert record.actor_id == "H-5"
    assert record.api_key_id is None


def test_a_chronos_session_or_key_opens_nothing(embedded, client, db, seed_users, kiosk_key):
    bearer = login(client, "admin@test.internal", ADMIN_PASSWORD)
    assert embedded.get(AUDIT, headers=bearer).status_code == 401
    # The secret gets the request in; the key is not looked at.
    res = embedded.get("/api/v1/guest/pending", headers={**HOST, **kiosk_key})
    assert res.status_code == 401
    assert "X-Chronos-Actor" in res.json()["detail"]


def _operation_ids(application):
    """From the OpenAPI document, which is the public account of what is mounted."""
    return {
        operation["operationId"]
        for methods in application.openapi()["paths"].values()
        for operation in methods.values()
    }


def test_the_stripped_routes_exist_only_in_the_ordinary_app(embedded):
    ordinary = _operation_ids(ordinary_app)
    assert ordinary >= STRIPPED_OPERATIONS
    assert not STRIPPED_OPERATIONS & _operation_ids(embedded.app)
    # Everything else is mounted as it is, plus the clock, which is only here.
    assert not CLOCK_OPERATIONS & ordinary
    assert _operation_ids(embedded.app) == (ordinary - STRIPPED_OPERATIONS) | CLOCK_OPERATIONS


def test_the_websocket_is_not_mounted(embedded, client):
    with client.websocket_connect("/api/v1/ws"):
        pass
    with pytest.raises(WebSocketDisconnect), embedded.websocket_connect("/api/v1/ws"):
        pass


def test_a_stripped_route_is_404_in_embedded_mode(embedded, client):
    payload = {"email_address": "admin@test.internal", "password": ADMIN_PASSWORD}
    assert embedded.post("/api/v1/auth/login", headers=HOST, json=payload).status_code == 404
    assert client.post("/api/v1/auth/login", json=payload).status_code != 404


def test_the_ordinary_app_keeps_its_own_authentication(client, seed_users):
    assert client.get(AUDIT, headers=actor("H-9")).status_code == 401
    assert login(client, "admin@test.internal", ADMIN_PASSWORD)


# The process: secret, ready line, and leaving when the host does.


@pytest.fixture(autouse=True)
def _environment_restored():
    saved = dict(os.environ)
    yield
    os.environ.clear()
    os.environ.update(saved)


def test_the_secret_comes_from_the_environment_or_stdin(monkeypatch):
    monkeypatch.setenv(host_identity.HOST_SECRET_ENV, "from-env")
    assert (
        standalone.read_host_secret(SimpleNamespace(secret_from_stdin=False), io.StringIO())
        == "from-env"
    )
    stdin = io.StringIO("from-stdin\r\nnext line\n")
    assert (
        standalone.read_host_secret(SimpleNamespace(secret_from_stdin=True), stdin) == "from-stdin"
    )
    assert stdin.readline() == "next line\n"


def test_embedded_refuses_to_start_without_a_secret(tmp_path, monkeypatch, capsys):
    # The data directory is made before the secret is looked at, so a
    # refusal still needs one that is not the working directory.
    argv = ["embedded", "--data-dir", str(tmp_path)]
    monkeypatch.delenv(host_identity.HOST_SECRET_ENV, raising=False)
    assert standalone.main(argv) == 2
    assert host_identity.HOST_SECRET_ENV in capsys.readouterr().err

    monkeypatch.setenv(host_identity.HOST_SECRET_ENV, "short")
    assert standalone.main(argv) == 2
    assert "32 characters" in capsys.readouterr().err


def test_a_unix_socket_is_refused_on_windows(monkeypatch, capsys):
    monkeypatch.setenv(host_identity.HOST_SECRET_ENV, SECRET)
    monkeypatch.setattr("sys.platform", "win32")
    assert standalone.main(["embedded", "--socket", "/tmp/chronos.sock"]) == 2
    assert "POSIX" in capsys.readouterr().err


def test_embedded_prepares_the_file_then_serves(tmp_path, monkeypatch):
    for name in ("DATABASE_URL", "REDIS_URL", "APP_ENV", "JWT_SECRET_SIGNING_KEY"):
        monkeypatch.delenv(name, raising=False)
    monkeypatch.setattr("sys.stdin", io.StringIO(f"{SECRET}\n"))
    file_engine = sqlite_engine(f"sqlite:///{(tmp_path / 'chronos.db').as_posix()}")
    monkeypatch.setattr(database, "engine", file_engine)
    served = []
    monkeypatch.setattr(
        standalone,
        "run_embedded",
        lambda application, args: served.append((application, args)) or 0,
    )

    argv = [
        "embedded",
        "--data-dir",
        str(tmp_path / "d"),
        "--secret-from-stdin",
        "--parent-pid",
        "4242",
    ]
    try:
        assert standalone.main(argv) == 0
    finally:
        file_engine.dispose()

    [(application, args)] = served
    assert args.parent_pid == 4242
    assert args.port == 0
    assert (
        _operation_ids(application)
        == (_operation_ids(ordinary_app) - STRIPPED_OPERATIONS) | CLOCK_OPERATIONS
    )
    with file_engine.connect() as connection:
        from sqlalchemy import text

        roles = connection.execute(text("SELECT id, role_type FROM users ORDER BY id")).all()
    assert ("system", "ORG_ADMIN") in roles


def test_embedded_puts_a_postgres_database_in_the_schema(tmp_path, monkeypatch):
    from sqlalchemy.engine import make_url

    monkeypatch.setenv(host_identity.HOST_SECRET_ENV, SECRET)
    monkeypatch.setattr(database, "engine", SimpleNamespace(url=make_url("postgresql://h/db")))
    schemas = []
    monkeypatch.setattr(database, "use_schema", lambda engine, name: schemas.append(name))
    prepared = []
    monkeypatch.setattr(
        embedded_module,
        "prepare_database",
        lambda engine, schema: prepared.append(schema) or "created",
    )
    monkeypatch.setattr(standalone, "run_embedded", lambda application, args: 0)

    argv = [
        "embedded",
        "--data-dir",
        str(tmp_path),
        "--database-url",
        "postgresql://h/db",
        "--schema",
        "ward_7",
    ]
    assert standalone.main(argv) == 0

    assert schemas == ["ward_7"]
    assert prepared == ["ward_7"]
    assert os.environ["DATABASE_URL"] == "postgresql://h/db"


def test_a_schema_name_is_a_plain_identifier():
    with pytest.raises(ValueError, match="schema name"):
        database.use_schema(None, 'chronos"; DROP SCHEMA public')


def _listening(port=54321, uds=None):
    socket = SimpleNamespace(getsockname=lambda: ("127.0.0.1", port))
    return SimpleNamespace(
        config=SimpleNamespace(uds=uds), servers=[SimpleNamespace(sockets=[socket])]
    )


def test_the_ready_line_is_one_json_object():
    assert json.loads(standalone.ready_line(_listening())) == {
        "chronos": "ready",
        "port": 54321,
        "schema_version": "1",
        "clock": "system",
    }
    assert json.loads(standalone.ready_line(_listening(uds="/run/chronos.sock"))) == {
        "chronos": "ready",
        "socket": "/run/chronos.sock",
        "schema_version": "1",
        "clock": "system",
    }


def test_the_ready_line_says_when_a_host_owns_the_clock():
    clock.install(clock.HostClock(datetime(2026, 9, 7, 8, tzinfo=UTC)))
    try:
        assert json.loads(standalone.ready_line(_listening()))["clock"] == "host"
    finally:
        clock.reset()


def test_the_ready_line_is_printed_once_the_server_listens(monkeypatch, capsys):
    outcomes = iter([False, True])

    async def startup(self, sockets=None):
        self.started = next(outcomes)

    monkeypatch.setattr(uvicorn.Server, "startup", startup)
    monkeypatch.setattr(standalone, "ready_line", lambda server: '{"chronos": "ready"}')
    server = standalone.AnnouncingServer(uvicorn.Config("app.main:app"))

    asyncio.run(server.startup())
    assert capsys.readouterr().out == ""
    asyncio.run(server.startup())
    assert capsys.readouterr().out == '{"chronos": "ready"}\n'


def test_run_embedded_binds_loopback_and_keeps_stdout_clean(monkeypatch):
    runs = []
    monkeypatch.setattr(standalone.AnnouncingServer, "run", lambda self: runs.append(self))
    monkeypatch.setattr("sys.stdin", io.StringIO(""))
    args = SimpleNamespace(port=0, socket=None, log_level="warning", parent_pid=None)

    assert standalone.run_embedded(build_app(SECRET), args) == 0

    [server] = runs
    assert server.config.host == "127.0.0.1"
    assert server.config.port == 0
    assert server.config.log_config is None
    assert server.config.workers == 1
    # An empty stdin is a host that has already gone.
    for _ in range(50):
        if server.should_exit:
            break
        time.sleep(0.02)
    assert server.should_exit


def test_stdin_closing_stops_the_server():
    stopped = []
    standalone.watch_stdin(
        io.StringIO("a line the host wrote\nanother\n"), lambda: stopped.append(True)
    )
    assert stopped == [True]


def test_the_parent_going_away_stops_the_server():
    answers = iter([True, True, False])
    stopped = []
    standalone.watch_parent(
        4242, lambda: stopped.append(True), alive=lambda pid: next(answers), interval=0
    )
    assert stopped == [True]


def test_parent_alive_tells_a_live_process_from_a_gone_one():
    assert standalone.parent_alive(os.getpid())
    assert not standalone.parent_alive(2**31 - 1)


@pytest.mark.skipif(sys.platform != "win32", reason="the pipe poller is the Windows watcher")
def test_the_pipe_poller_drains_what_the_host_writes_and_notices_it_leaving():
    reading, writing = os.pipe()
    stopped = []
    os.write(writing, b"a line the host wrote\n")
    watcher = threading.Thread(
        target=standalone.watch_stdin_pipe, args=(reading, lambda: stopped.append(True), 0.01)
    )
    watcher.start()
    time.sleep(0.1)
    assert not stopped
    os.write(writing, b"another\n")
    os.close(writing)
    watcher.join(timeout=5)
    os.close(reading)
    assert stopped == [True]


def test_the_watcher_blocks_in_a_read_except_on_a_windows_pipe():
    assert standalone.stdin_watcher(io.StringIO(""))[0] is standalone.watch_stdin
    reading, writing = os.pipe()
    try:
        with os.fdopen(reading, closefd=False) as stream:
            target, source = standalone.stdin_watcher(stream)
    finally:
        os.close(writing)
        os.close(reading)
    if sys.platform == "win32":
        assert (target, source) == (standalone.watch_stdin_pipe, reading)
    else:
        assert target is standalone.watch_stdin


def test_the_entry_point_builds_the_file_the_flag_names(tmp_path, embedded_process):
    """The real entry point in a fresh interpreter, where nothing is cached yet.

    Importing anything under `app.` before configure_environment runs would
    build the engine from whatever DATABASE_URL the host's environment
    carries, and the in-process tests cannot see that: their settings were
    cached long before. So a decoy URL goes in the environment, and the file
    has to appear under --data-dir and nowhere else.
    """
    data_dir = tmp_path / "d"
    decoy = tmp_path / "elsewhere.db"
    child = embedded_process(
        "--data-dir",
        str(data_dir),
        "--port",
        "0",
        env={"DATABASE_URL": f"sqlite:///{decoy.as_posix()}"},
    )

    ready = child.ready()
    assert ready["chronos"] == "ready"
    assert ready["port"] > 0
    assert ready["clock"] == "system"

    connection = sqlite3.connect(data_dir / standalone.DATABASE_FILE)
    try:
        tables = {name for (name,) in connection.execute("SELECT name FROM sqlite_master")}
        users = {user_id for (user_id,) in connection.execute("SELECT id FROM users")}
    finally:
        connection.close()
    assert "users" in tables
    assert SYSTEM_ACTOR_ID in users
    assert not decoy.exists()

    # The host going away: stdin closes, the process leaves on its own.
    assert child.leave() == 0


def test_an_ingestion_request_is_answered_while_the_host_holds_stdin(tmp_path, embedded_process):
    """pandas is imported on the first ingestion request, long after startup.

    On Windows that import hung for as long as the stdin watcher sat in a
    read on the host's pipe, so the request never got an answer. The
    answer here is a refusal, since the file has none of the columns, but
    a refusal from pandas is one that has been through the import.
    """
    child = embedded_process("--data-dir", str(tmp_path), "--port", "0")
    base = f"http://127.0.0.1:{child.ready()['port']}/api/v1"
    headers = actor("H-1", role="ORG_ADMIN")

    with httpx.Client(base_url=base, headers=headers, timeout=60) as api:
        cycle = api.post(
            "/schedule/cycles",
            json={
                "cycle_label": "Ingest",
                "date_bounds_start": "2031-01-06",
                "date_bounds_end": "2031-04-24",
            },
        )
        assert cycle.status_code == 200, cycle.text
        res = api.post(
            "/ingestion/upload-csv",
            params={"cycle_id": cycle.json()["id"]},
            files={"file": ("matrix.csv", b"a,b\n", "text/csv")},
        )
    assert res.status_code == 422, res.text
    assert "Missing columns" in res.json()["detail"]
    assert child.leave() == 0
