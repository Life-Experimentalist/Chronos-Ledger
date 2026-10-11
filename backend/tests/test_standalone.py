# Copyright 2026 Chronos Ledger Contributors
# Licensed under the Apache License, Version 2.0
"""chronos-engine: one SQLite file, no Redis, no container."""

import logging
import os
import sqlite3
from types import SimpleNamespace

import pytest
from alembic.runtime.migration import MigrationContext
from sqlalchemy import inspect, text
from sqlalchemy.exc import OperationalError

import app.main as main
from app import standalone
from app.core import redis_client
from app.core.bootstrap import SEEDED_ADMIN_ID
from app.core.config import get_settings
from app.core.database import sqlite_engine
from app.core.migrations import _scripts


@pytest.fixture(autouse=True)
def _environment_restored():
    """configure_environment writes os.environ directly, as it must for the
    process it starts. Put back whatever a test changed, set or unset."""
    saved = dict(os.environ)
    yield
    os.environ.clear()
    os.environ.update(saved)


@pytest.fixture()
def data_dir(tmp_path):
    return tmp_path / "data"


@pytest.fixture()
def file_engine(tmp_path):
    engine = sqlite_engine(f"sqlite:///{(tmp_path / 'chronos.db').as_posix()}")
    yield engine
    engine.dispose()


def test_connections_get_the_pragmas(file_engine):
    with file_engine.connect() as connection:
        pragma = lambda name: connection.exec_driver_sql(f"PRAGMA {name}").scalar()  # noqa: E731
        assert pragma("journal_mode") == "wal"
        assert pragma("foreign_keys") == 1
        assert pragma("busy_timeout") == 10_000
        # NORMAL is 1.
        assert pragma("synchronous") == 1


def test_a_transaction_takes_the_write_lock_when_it_begins(tmp_path):
    """BEGIN IMMEDIATE: the second transaction waits, even to read.

    This is what stands in for SELECT ... FOR UPDATE and the exclusion
    constraints, neither of which SQLite has: two requests checking for a
    clash cannot both see "free" and both write.
    """
    engine = sqlite_engine(f"sqlite:///{(tmp_path / 'lock.db').as_posix()}", busy_timeout_ms=100)
    try:
        with engine.connect() as first, engine.connect() as second:
            first.execute(text("SELECT 1"))
            with pytest.raises(OperationalError, match="locked"):
                second.execute(text("SELECT 1"))
            first.rollback()
            assert second.execute(text("SELECT 1")).scalar() == 1
    finally:
        engine.dispose()


def test_a_new_file_is_built_seeded_and_stamped(file_engine):
    assert standalone.prepare_database(file_engine) == "created"

    with file_engine.connect() as connection:
        revision = MigrationContext.configure(connection).get_current_revision()
        admin = connection.execute(
            text("SELECT role_type, initial_login_state FROM users WHERE id = :id"),
            {"id": SEEDED_ADMIN_ID},
        ).one()
    assert revision == _scripts().get_current_head()
    assert admin.role_type == "ORG_ADMIN"
    assert admin.initial_login_state

    assert standalone.prepare_database(file_engine) == "current"


def test_an_older_file_is_upgraded_with_the_migrations(file_engine, monkeypatch):
    """A file stamped at 029 gets 030 from its script, not from the models."""
    standalone.prepare_database(file_engine)
    with file_engine.begin() as connection:
        connection.exec_driver_sql("DROP INDEX ix_daily_ledger_resource_date")
        connection.exec_driver_sql("DROP INDEX ix_daily_ledger_lead_date")
        MigrationContext.configure(connection).stamp(_scripts(), "029")
    # env.py prefers DATABASE_URL to the URL it is handed.
    monkeypatch.setenv("DATABASE_URL", file_engine.url.render_as_string(hide_password=False))

    assert standalone.prepare_database(file_engine) == "upgraded"

    indexes = {index["name"] for index in inspect(file_engine).get_indexes("daily_ledger")}
    assert {"ix_daily_ledger_resource_date", "ix_daily_ledger_lead_date"} <= indexes
    assert standalone.prepare_database(file_engine) == "current"


def test_tables_without_a_stamp_are_refused(file_engine):
    with file_engine.begin() as connection:
        connection.exec_driver_sql("CREATE TABLE users (id TEXT PRIMARY KEY)")
    with pytest.raises(SystemExit, match="no migration stamp"):
        standalone.prepare_database(file_engine)


def test_a_newer_file_is_refused(file_engine):
    with file_engine.begin() as connection:
        connection.exec_driver_sql("CREATE TABLE alembic_version (version_num VARCHAR(32))")
        connection.exec_driver_sql("INSERT INTO alembic_version VALUES ('999')")
    with pytest.raises(SystemExit, match="newer"):
        standalone.prepare_database(file_engine)


def test_the_environment_points_at_the_data_directory(data_dir, monkeypatch):
    for name in ("DATABASE_URL", "REDIS_URL", "APP_ENV", "JWT_SECRET_SIGNING_KEY"):
        monkeypatch.delenv(name, raising=False)
    data_dir.mkdir()

    standalone.configure_environment(data_dir)

    assert os.environ["DATABASE_URL"] == standalone.database_url(data_dir)
    assert os.environ["REDIS_URL"] == "memory://"
    assert os.environ["APP_ENV"] == "production"
    key = os.environ["JWT_SECRET_SIGNING_KEY"]
    assert len(key) == 64
    assert (data_dir / standalone.SIGNING_KEY_FILE).read_text(encoding="utf-8") == key

    # The next start signs with the same key, so nobody is signed out by it.
    monkeypatch.delenv("JWT_SECRET_SIGNING_KEY")
    standalone.configure_environment(data_dir)
    assert os.environ["JWT_SECRET_SIGNING_KEY"] == key


def test_a_key_in_the_environment_wins(data_dir, monkeypatch):
    monkeypatch.setenv("JWT_SECRET_SIGNING_KEY", "x" * 64)
    monkeypatch.setenv("DATABASE_URL", "postgresql://elsewhere/db")
    monkeypatch.setenv("REDIS_URL", "redis://elsewhere")
    data_dir.mkdir()

    standalone.configure_environment(data_dir)

    assert os.environ["JWT_SECRET_SIGNING_KEY"] == "x" * 64
    assert not (data_dir / standalone.SIGNING_KEY_FILE).exists()
    # A container's URLs left in the shell do not send this profile there.
    assert os.environ["DATABASE_URL"].startswith("sqlite:///")
    assert os.environ["REDIS_URL"] == "memory://"


def _backup_args(data_dir, target):
    return SimpleNamespace(data_dir=str(data_dir), to=str(target))


def test_backup_copies_a_database_in_use(data_dir, tmp_path):
    data_dir.mkdir()
    engine = sqlite_engine(standalone.database_url(data_dir))
    try:
        with engine.begin() as connection:
            connection.exec_driver_sql("CREATE TABLE t (n INTEGER)")
            connection.exec_driver_sql("INSERT INTO t VALUES (42)")
        target = tmp_path / "copy.db"
        # The engine still holds its connection, and the commit may still be
        # in the -wal file.
        assert standalone.backup(_backup_args(data_dir, target)) == 0
    finally:
        engine.dispose()

    copy = sqlite3.connect(target)
    try:
        assert copy.execute("SELECT n FROM t").fetchone() == (42,)
    finally:
        copy.close()


def test_backup_never_overwrites(data_dir, tmp_path, capsys):
    data_dir.mkdir()
    sqlite3.connect(data_dir / standalone.DATABASE_FILE).close()
    target = tmp_path / "copy.db"
    target.write_bytes(b"keep me")

    assert standalone.backup(_backup_args(data_dir, target)) == 1
    assert target.read_bytes() == b"keep me"
    assert "already exists" in capsys.readouterr().err


def test_backup_without_a_database(data_dir, tmp_path, capsys):
    assert standalone.backup(_backup_args(data_dir, tmp_path / "copy.db")) == 1
    assert "No database" in capsys.readouterr().err


@pytest.fixture()
def memory_redis(monkeypatch):
    monkeypatch.setenv("REDIS_URL", "memory://")
    get_settings.cache_clear()
    redis_client.get_redis.cache_clear()
    yield
    get_settings.cache_clear()
    redis_client.get_redis.cache_clear()


def test_memory_redis_holds_what_the_rate_limiter_keeps(memory_redis):
    cache = redis_client.get_redis()
    pipe = cache.pipeline()
    pipe.incr("hits")
    pipe.expire("hits", 60)
    pipe.execute()
    assert cache.get("hits") == "1"
    assert cache.set("jti", "1", nx=True, ex=60)
    assert not cache.set("jti", "1", nx=True, ex=60)
    # One per process, so every caller sees the same counters.
    assert redis_client.get_redis() is cache


def test_memory_redis_without_the_extra_says_what_to_install(memory_redis, monkeypatch):
    import builtins

    real_import = builtins.__import__

    def no_fakeredis(name, *args, **kwargs):
        if name == "fakeredis":
            raise ImportError(name)
        return real_import(name, *args, **kwargs)

    monkeypatch.setattr(builtins, "__import__", no_fakeredis)
    with pytest.raises(RuntimeError, match="standalone"):
        redis_client.get_redis()


def test_readiness_under_memory_redis_pings_nothing(client, monkeypatch, file_engine):
    monkeypatch.setattr(main, "engine", file_engine)
    monkeypatch.setattr(main.settings, "redis_url", "memory://")

    def no_redis(*_args, **_kwargs):
        raise AssertionError("readiness pinged a Redis that is not there")

    monkeypatch.setattr(main.redis, "from_url", no_redis)
    res = client.get("/health/ready")
    assert res.status_code == 200
    assert res.json() == {"status": "ready", "database": "ok", "redis": "memory"}


def test_the_write_ahead_log_is_folded_in_on_the_way_out(monkeypatch, file_engine):
    standalone.prepare_database(file_engine)
    wal = file_engine.url.database + "-wal"
    assert os.path.getsize(wal) > 0
    monkeypatch.setattr(main, "engine", file_engine)
    main._fold_the_write_ahead_log()
    assert not os.path.exists(wal) or os.path.getsize(wal) == 0


def test_a_failed_checkpoint_is_logged_not_raised(monkeypatch, caplog):
    class _Down:
        def raw_connection(self):
            raise ConnectionError("down")

    monkeypatch.setattr(main, "engine", _Down())
    with caplog.at_level(logging.ERROR):
        main._fold_the_write_ahead_log()
    assert "write-ahead log" in caplog.text


def test_serve_prepares_the_file_then_runs_one_worker(tmp_path, monkeypatch):
    for name in ("DATABASE_URL", "REDIS_URL", "APP_ENV", "JWT_SECRET_SIGNING_KEY"):
        monkeypatch.delenv(name, raising=False)
    prepared = []
    monkeypatch.setattr(standalone, "prepare_database", lambda engine: prepared.append(engine))
    runs = []
    import uvicorn

    monkeypatch.setattr(uvicorn, "run", lambda app, **options: runs.append((app, options)))

    assert standalone.main(["serve", "--data-dir", str(tmp_path / "d"), "--port", "9123"]) == 0

    assert len(prepared) == 1
    app_path, options = runs[0]
    assert app_path == "app.main:app"
    assert options["workers"] == 1
    assert options["port"] == 9123
    assert options["host"] == "127.0.0.1"
    assert options["proxy_headers"] is False
    assert (tmp_path / "d" / standalone.SIGNING_KEY_FILE).exists()


def test_a_synced_folder_is_warned_about(tmp_path, caplog):
    with caplog.at_level(logging.WARNING, logger="chronos.standalone"):
        standalone._warn_about_synced_folders(tmp_path / "OneDrive" / "chronos")
    assert "sync client" in caplog.text

    caplog.clear()
    with caplog.at_level(logging.WARNING, logger="chronos.standalone"):
        standalone._warn_about_synced_folders(tmp_path / "chronos")
    assert caplog.text == ""


def test_backup_is_reachable_from_the_command_line(data_dir, tmp_path):
    data_dir.mkdir()
    sqlite3.connect(data_dir / standalone.DATABASE_FILE).close()
    target = tmp_path / "copy.db"
    argv = ["backup", "--data-dir", str(data_dir), "--to", str(target)]
    assert standalone.main(argv) == 0
    assert target.exists()
