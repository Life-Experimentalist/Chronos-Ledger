# Copyright 2026 Chronos Ledger Contributors
# Licensed under the Apache License, Version 2.0

import re
from contextlib import contextmanager

from sqlalchemy import create_engine, event
from sqlalchemy.engine import Engine
from sqlalchemy.orm import DeclarativeBase, sessionmaker

from app.core.config import get_settings

settings = get_settings()


def is_sqlite(url: str) -> bool:
    return url.startswith("sqlite")


# SQLite takes one writer at a time whatever the pool holds, so a handful of
# connections is all the standalone profile needs. More would only queue on
# the database lock instead of on the gate in app.core.concurrency, where
# waiting is cheaper.
SQLITE_POOL_SIZE = 4
# How long a connection waits for the write lock before giving up. Longer than
# any one transaction should take, short enough that a stuck one surfaces.
SQLITE_BUSY_TIMEOUT_MS = 10_000

if is_sqlite(settings.database_url):
    POOL_SIZE = SQLITE_POOL_SIZE
    MAX_OVERFLOW = 0
else:
    POOL_SIZE = 10
    MAX_OVERFLOW = 20
# The most connections one process can hold, and so the most API requests it
# works on at once (see app.core.concurrency).
POOL_CAPACITY = POOL_SIZE + MAX_OVERFLOW


def sqlite_engine(
    url: str,
    pool_size: int = SQLITE_POOL_SIZE,
    busy_timeout_ms: int = SQLITE_BUSY_TIMEOUT_MS,
) -> Engine:
    """An engine on a SQLite file, set up for the standalone profile.

    Postgres keeps the schedule honest with exclusion constraints, which the
    models declare for that dialect only because SQLite has no equivalent, so
    the OVERLAP_CONSTRAINT branch in the reservations route never fires here. What
    takes their place is that every transaction starts with BEGIN IMMEDIATE:
    it takes the write lock before the first read, so the conflict check and
    the insert that follows it run with nobody else between them, and the
    second of two overlapping bookings sees the first and is told 409.

    The price is that transactions run one at a time, reads included. A
    request's transaction is a few milliseconds, and WAL keeps a backup or an
    outside reader from blocking anyone.
    """
    engine = create_engine(
        url,
        pool_size=pool_size,
        max_overflow=0,
        pool_timeout=10,
        # Requests run in a thread pool, and a pooled connection moves between
        # threads. The pool hands each one to a single thread at a time.
        connect_args={"check_same_thread": False},
    )

    @event.listens_for(engine, "connect")
    def _configure(dbapi_connection, _record):
        # pysqlite opens transactions on its own terms and never with
        # IMMEDIATE. None hands that to the "begin" listener below.
        dbapi_connection.isolation_level = None
        cursor = dbapi_connection.cursor()
        cursor.execute("PRAGMA journal_mode=WAL")
        # In WAL mode NORMAL loses at most the last commits on a power cut,
        # never the file, and saves an fsync per commit.
        cursor.execute("PRAGMA synchronous=NORMAL")
        cursor.execute("PRAGMA foreign_keys=ON")
        cursor.execute(f"PRAGMA busy_timeout={int(busy_timeout_ms)}")
        cursor.close()

    @event.listens_for(engine, "begin")
    def _begin_immediate(connection):
        connection.exec_driver_sql("BEGIN IMMEDIATE")

    return engine


SCHEMA_NAME = re.compile(r"^[A-Za-z_][A-Za-z0-9_]{0,62}$")


def use_schema(engine: Engine, name: str) -> None:
    """Keep every connection of this engine inside one PostgreSQL schema.

    For the embedded flavour (app.embedded), where Chronos lives in a host
    program's database and must not touch the host's tables. Every pooled
    connection gets `search_path` set to that schema alone, so an unqualified
    name resolves there and nowhere else: create_all puts the tables, types
    and constraints in it, has_table looks only in it, and a host table of
    the same name in `public` is neither seen nor touched. The btree_gist
    extension is database-wide; if the host already has it, in whatever
    schema, CREATE EXTENSION IF NOT EXISTS is a no-op and the exclusion
    constraints still find its operator classes, since the default class for
    an index is looked up by type, not by search_path.

    Attach before the first connection is made.
    """
    if not SCHEMA_NAME.match(name):
        raise ValueError(f"{name!r} is not a plain schema name (letters, digits, underscores)")

    @event.listens_for(engine, "connect")
    def _set_search_path(dbapi_connection, _record):
        # Outside a transaction: the pool rolls back whatever is open when a
        # connection comes back, and SET inside that transaction goes with it.
        previous = dbapi_connection.autocommit
        dbapi_connection.autocommit = True
        cursor = dbapi_connection.cursor()
        try:
            cursor.execute(f'SET search_path TO "{name}"')
        finally:
            cursor.close()
        dbapi_connection.autocommit = previous


if is_sqlite(settings.database_url):
    engine = sqlite_engine(settings.database_url)
else:
    engine = create_engine(
        settings.database_url,
        pool_pre_ping=True,
        pool_size=POOL_SIZE,
        max_overflow=MAX_OVERFLOW,
        pool_timeout=10,
    )

SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)


class Base(DeclarativeBase):
    pass


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


@contextmanager
def open_session():
    """A session for code that is not an ordinary request handler.

    get_db is a yield dependency, so FastAPI closes it when the handler
    returns. On a websocket that is when the browser tab closes, which would
    hold one connection out of the pool for every socket anybody has open.
    This opens one, hands it over, and closes it when the block ends.
    """
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def get_session_opener():
    """open_session itself, as a dependency, so a test can substitute its own.

    Handing over the opener rather than a session is what keeps the closing in
    the handler's hands instead of FastAPI's.
    """
    return open_session
