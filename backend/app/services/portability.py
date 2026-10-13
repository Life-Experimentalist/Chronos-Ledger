# Copyright 2026 Chronos Ledger Contributors
# Licensed under the Apache License, Version 2.0

"""An organization's data as one archive, and back into an empty database.

The archive is a zip file: manifest.json plus one JSON Lines member per
table, `<table>.jsonl`, one row per line. docs/portability.md is the
format's documentation and says why a zip.

The same archive moves between SQLite and PostgreSQL, and an export, an
import into an empty database and a second export give the same bytes. That
rests on three things, all in this module: rows go out in primary key order
(bytewise for string keys, whatever the database's collation), every value
has exactly one written form (_encode), and the zip carries nothing about
when or where it was made (_member).

Secrets stay out unless asked for. SECRET_COLUMNS lists them; without
include_secrets their keys are left off every row, and an import fills them
with values that open nothing (_redacted_value). EXCLUDED lists the tables
that never travel. tests/test_portability.py fails when a table is in
neither EXPORTED nor EXCLUDED, so a new table forces the decision.

The route (endpoints/admin.py) and the CLI (app/standalone.py) only open the
connection and the file; everything else is here.
"""

import json
import secrets
import zipfile
from collections.abc import Iterator
from datetime import UTC, date, datetime, time
from decimal import Decimal, InvalidOperation
from typing import BinaryIO

from sqlalchemy import (
    BigInteger,
    Boolean,
    Date,
    DateTime,
    Enum,
    Integer,
    Numeric,
    String,
    Table,
    Text,
    Time,
    func,
    inspect,
    select,
    text,
)
from sqlalchemy.engine import Connection, Engine
from sqlalchemy.exc import DBAPIError

import app.models.db  # noqa: F401 (registers every table with the metadata)
from app.core.bootstrap import SEEDED_ADMIN_ID
from app.core.database import Base
from app.core.schema import SCHEMA_LOCK_KEY, SCHEMA_VERSION

FORMAT_NAME = "chronos-ledger-archive"
# Bumped when the archive's layout or the written form of a value changes.
# An import refuses any other number, newer or older: there is one reader.
FORMAT_VERSION = 1
MANIFEST = "manifest.json"

# Tables that never travel, each with the reason. Every table in the metadata
# is either here or exported, and tests/test_portability.py holds that.
EXCLUDED: dict[str, str] = {
    # Hashes of one-use bearer secrets that expire within days. Carrying them
    # would carry live sessions into another deployment; leaving them out
    # means everyone signs in again after an import, which is the point.
    "refresh_tokens": "one-use session tokens that expire within days; "
    "an imported deployment signs everyone in again",
    # Stored responses for Idempotency-Key retries, deleted by the nightly job
    # after IDEMPOTENCY_RETENTION_HOURS. They are a short-lived cache of what a
    # write already returned, not data of their own; a client retrying against
    # the imported deployment gets its write treated as a new request.
    "idempotency_records": "stored responses to retried writes, kept for hours; "
    "a retry after an import is treated as a new request",
}

# Exported tables in foreign key order, which is also the order an import
# inserts them in and the order of the members in the zip.
EXPORTED: tuple[Table, ...] = tuple(
    table for table in Base.metadata.sorted_tables if table.name not in EXCLUDED
)

# Columns that hold a credential or something that opens a door. Left off
# every row unless the export asks for secrets.
SECRET_COLUMNS: dict[str, tuple[str, ...]] = {
    "users": ("calendar_feed_token", "credential_secure_hash"),
    "api_keys": ("key_hash",),
    "guest_gate_registry": ("visit_code_hash",),
}

# Rows per INSERT on import. Enough to keep round trips down, small enough
# that one batch never matters for memory.
BATCH_SIZE = 1000
# Rows fetched per round trip on export.
FETCH_SIZE = 1000

# The zip's own metadata, fixed so that two exports of the same data are the
# same bytes: the earliest date a zip can hold, Unix as the maker (Python
# picks by platform otherwise), and an ordinary readable file's mode.
_ZIP_DATE = (1980, 1, 1, 0, 0, 0)
_ZIP_UNIX = 3
_ZIP_MODE = 0o100644 << 16


class ArchiveError(Exception):
    """An archive this release will not import, or a database it will not import into.

    The message is for a person and says what to do. Nothing has been written
    when one is raised: the import's single transaction has rolled back.
    """


# Writing.


def export_archive(connection: Connection, target: BinaryIO, *, include_secrets: bool = False):
    """Write the whole organization to target as a zip. Returns the manifest.

    target has to be seekable (a real file): zipfile then writes each
    member's sizes into its header instead of a data descriptor after it,
    which keeps the layout the same however the file was written.

    connection must not have run a statement in its current transaction. On
    PostgreSQL the first thing this does is make that transaction a
    repeatable read snapshot, so every table is read as of the same moment
    while the server keeps taking writes. SQLite's own transaction already
    is one.
    """
    postgres = connection.dialect.name == "postgresql"
    if postgres:
        connection.execute(text("SET TRANSACTION ISOLATION LEVEL REPEATABLE READ, READ ONLY"))

    omitted = {} if include_secrets else {k: list(v) for k, v in SECRET_COLUMNS.items()}
    entries = []
    with zipfile.ZipFile(target, "w", compression=zipfile.ZIP_DEFLATED) as archive:
        for table in EXPORTED:
            skip = set(omitted.get(table.name, ()))
            columns = [c for c in table.columns if c.name not in skip]
            order = [_bytewise(c, postgres) for c in table.primary_key.columns]
            query = select(*columns).order_by(*order).execution_options(yield_per=FETCH_SIZE)
            result = connection.execute(query)
            count = 0
            with archive.open(_member(f"{table.name}.jsonl"), "w", force_zip64=True) as out:
                for row in result:
                    record = {c.name: _encode(c, row[i]) for i, c in enumerate(columns)}
                    out.write(_line(record))
                    count += 1
            entries.append({"name": table.name, "file": f"{table.name}.jsonl", "rows": count})

        manifest = {
            "format": FORMAT_NAME,
            "format_version": FORMAT_VERSION,
            "schema_version": SCHEMA_VERSION,
            "secrets_included": include_secrets,
            "omitted_columns": omitted,
            "tables": entries,
        }
        # Last, because the row counts are only known once every table is out.
        body = json.dumps(manifest, sort_keys=True, indent=2, ensure_ascii=False) + "\n"
        with archive.open(_member(MANIFEST), "w", force_zip64=True) as out:
            out.write(body.encode("utf-8"))
    return manifest


def _member(name: str) -> zipfile.ZipInfo:
    info = zipfile.ZipInfo(name, date_time=_ZIP_DATE)
    info.compress_type = zipfile.ZIP_DEFLATED
    info.create_system = _ZIP_UNIX
    info.external_attr = _ZIP_MODE
    return info


def _bytewise(column, postgres: bool):
    # PostgreSQL sorts text by the database's collation, which can put "a"
    # before "B" or the other way round depending on how it was created.
    # "C" is byte order, which is what SQLite's default already is.
    if postgres and isinstance(column.type, String) and not isinstance(column.type, Enum):
        return column.collate("C")
    return column


def _line(record: dict) -> bytes:
    return (
        json.dumps(record, sort_keys=True, separators=(",", ":"), ensure_ascii=False) + "\n"
    ).encode("utf-8")


def _encode(column, value):
    """The one written form of a value, whichever database it came out of."""
    if value is None:
        return None
    kind = column.type
    if isinstance(kind, Enum):
        return value.value if hasattr(value, "value") else str(value)
    if isinstance(kind, DateTime):
        # SQLite hands back the wall time it was given with no zone, and
        # every writer gives it UTC. PostgreSQL hands back the session's zone.
        if value.tzinfo is None:
            value = value.replace(tzinfo=UTC)
        return value.astimezone(UTC).isoformat(timespec="microseconds")
    if isinstance(kind, Time):
        return value.isoformat(timespec="microseconds")
    if isinstance(kind, Date):
        return value.isoformat()
    if isinstance(kind, Numeric):
        # A string, so no float rounding on the way through JSON, at the
        # column's own scale, so SQLite's REAL and PostgreSQL's NUMERIC agree.
        return str(Decimal(str(value)).quantize(Decimal(1).scaleb(-kind.scale)))
    return value


# Reading.


def read_manifest(archive: zipfile.ZipFile) -> dict:
    """The manifest, checked against what this release reads. Touches no database."""
    try:
        manifest = json.loads(archive.read(MANIFEST).decode("utf-8"))
    except KeyError:
        raise ArchiveError(
            f"The archive has no {MANIFEST}, so it is not a Chronos export"
        ) from None
    except (UnicodeDecodeError, json.JSONDecodeError) as problem:
        raise ArchiveError(f"{MANIFEST} is not valid JSON: {problem}") from None
    if not isinstance(manifest, dict) or manifest.get("format") != FORMAT_NAME:
        raise ArchiveError(
            f"{MANIFEST} does not describe a Chronos export (format {FORMAT_NAME!r})"
        )

    version = manifest.get("format_version")
    if isinstance(version, int) and not isinstance(version, bool) and version > FORMAT_VERSION:
        raise ArchiveError(
            f"The archive is format version {version}, newer than this release reads "
            f"(format version {FORMAT_VERSION}). Import it with the release that made it "
            "or a later one."
        )
    if version != FORMAT_VERSION or isinstance(version, bool):
        raise ArchiveError(
            f"The archive is format version {version!r}, which this release does not know. "
            f"It reads format version {FORMAT_VERSION}."
        )

    schema = manifest.get("schema_version")
    if schema != SCHEMA_VERSION:
        raise ArchiveError(
            f"The archive was made at schema version {schema!r} and this release is at "
            f"schema version {SCHEMA_VERSION!r}. There are no migrations yet, so an archive "
            "moves only between releases at the same schema version."
        )

    included = manifest.get("secrets_included")
    if not isinstance(included, bool):
        raise ArchiveError(f"{MANIFEST} has no true or false secrets_included")
    expected_omitted = {} if included else {k: list(v) for k, v in SECRET_COLUMNS.items()}
    if manifest.get("omitted_columns") != expected_omitted:
        raise ArchiveError(
            f"{MANIFEST} lists omitted columns {manifest.get('omitted_columns')!r}; "
            f"format version {FORMAT_VERSION} omits exactly {expected_omitted!r}"
        )

    entries = manifest.get("tables")
    if not isinstance(entries, list) or not all(isinstance(e, dict) for e in entries):
        raise ArchiveError(f"{MANIFEST} has no list of tables")
    listed = [e.get("name") for e in entries]
    wanted = [t.name for t in EXPORTED]
    if sorted(map(str, listed)) != sorted(wanted):
        missing = sorted(set(wanted) - set(listed))
        extra = sorted(set(map(str, listed)) - set(wanted))
        raise ArchiveError(
            f"{MANIFEST} lists the wrong tables for schema version {SCHEMA_VERSION}: "
            f"missing {missing}, unexpected {extra}"
        )
    names = set(archive.namelist())
    for entry in entries:
        if entry.get("file") != f"{entry['name']}.jsonl" or entry["file"] not in names:
            raise ArchiveError(f"The archive has no {entry['name']}.jsonl member")
        rows = entry.get("rows")
        if not isinstance(rows, int) or isinstance(rows, bool) or rows < 0:
            raise ArchiveError(f"{MANIFEST} has no row count for {entry['name']}")
    return manifest


def import_archive(engine: Engine, source, *, admin_password: str | None = None) -> dict:
    """Load an archive into an empty database, in one transaction. Returns the manifest.

    source is a path or a seekable binary file. The archive and its manifest
    are checked before the database is touched. Then the schema is built,
    the database is checked for rows (any row at all refuses the import), and
    the tables go in in foreign key order. Any failure rolls everything back,
    so the database is left as empty as it was found.

    An archive without secrets carries no password hashes. Every account gets
    a hash nobody knows the password for, and admin_password, when given,
    becomes the password of the seeded administrator account. When that
    account is in the archive and no password is given the import refuses,
    because nobody could sign in afterwards.
    """
    try:
        archive = zipfile.ZipFile(source)
    except (zipfile.BadZipFile, OSError) as problem:
        raise ArchiveError(f"Not a readable zip archive: {problem}") from None
    with archive:
        manifest = read_manifest(archive)
        counts = {e["name"]: e["rows"] for e in manifest["tables"]}
        redacted = not manifest["secrets_included"]
        with engine.begin() as connection:
            if connection.dialect.name == "postgresql":
                # The lock ensure_schema takes, so a server starting on this
                # database at the same moment waits for the import to finish.
                connection.execute(
                    text("SELECT pg_advisory_xact_lock(:key)"), {"key": SCHEMA_LOCK_KEY}
                )
            _refuse_rows(connection)
            # Built here rather than by ensure_schema, which would also seed
            # the administrator account and so make the database not empty.
            Base.metadata.create_all(connection)
            for table in EXPORTED:
                _load(connection, archive, table, counts[table.name], redacted)
            if redacted:
                _open_admin(connection, admin_password)
            if connection.dialect.name == "postgresql":
                _advance_sequences(connection)
    return manifest


def _refuse_rows(connection: Connection) -> None:
    inspector = inspect(connection)
    holding = []
    for table in Base.metadata.sorted_tables:
        if not inspector.has_table(table.name):
            continue
        if connection.execute(select(func.count()).select_from(table)).scalar_one():
            holding.append(table.name)
    if holding:
        raise ArchiveError(
            f"The target database is not empty: {', '.join(holding)} already hold rows. "
            "An import goes only into an empty database. A database a server has started "
            "on already holds the seeded administrator account, so import before the "
            "first start."
        )


def _load(connection, archive, table: Table, expected: int, redacted: bool) -> None:
    name = f"{table.name}.jsonl"
    omitted = set(SECRET_COLUMNS.get(table.name, ())) if redacted else set()
    present = {c.name for c in table.columns} - omitted
    # A column naming a row of its own table (users.reporting_line_manager)
    # goes in empty and is filled in on a second pass, because the row it
    # names can come later in primary key order.
    deferred = [fk.parent.name for fk in table.foreign_keys if fk.column.table is table]

    count = 0
    batch = []
    for number, record in _records(archive, name):
        count += 1
        if set(record) != present:
            missing = sorted(present - set(record))
            extra = sorted(set(record) - present)
            raise ArchiveError(f"{name} line {number}: missing {missing}, unexpected {extra}")
        row = {}
        for column in table.columns:
            if column.name in omitted:
                row[column.name] = _redacted_value(table.name, column.name)
            elif column.name in deferred:
                row[column.name] = None
            else:
                try:
                    row[column.name] = _decode(column, record[column.name])
                except (TypeError, ValueError, InvalidOperation) as problem:
                    raise ArchiveError(
                        f"{name} line {number}: {column.name} {record[column.name]!r}: {problem}"
                    ) from None
        batch.append(row)
        if len(batch) >= BATCH_SIZE:
            _insert(connection, table, batch, name, number)
            batch = []
    if batch:
        _insert(connection, table, batch, name, count)
    if count != expected:
        raise ArchiveError(f"{name} has {count} rows and {MANIFEST} says {expected}")

    for column_name in deferred:
        key = table.primary_key.columns.values()[0]
        target = table.c[column_name]
        for number, record in _records(archive, name):
            if record[column_name] is None:
                continue
            try:
                connection.execute(
                    table.update()
                    .where(key == _decode(key, record[key.name]))
                    .values({column_name: _decode(target, record[column_name])})
                )
            except DBAPIError as problem:
                raise ArchiveError(
                    f"{name} line {number}: {column_name} was refused by the database: "
                    f"{problem.orig}"
                ) from None


def _records(archive: zipfile.ZipFile, name: str) -> Iterator[tuple[int, dict]]:
    with archive.open(name) as member:
        for number, raw in enumerate(member, start=1):
            try:
                record = json.loads(raw.decode("utf-8"))
            except (UnicodeDecodeError, json.JSONDecodeError) as problem:
                raise ArchiveError(f"{name} line {number}: not a JSON object: {problem}") from None
            if not isinstance(record, dict):
                raise ArchiveError(f"{name} line {number}: not a JSON object")
            yield number, record


def _insert(connection, table, batch, name, last_line) -> None:
    try:
        connection.execute(table.insert(), batch)
    except DBAPIError as problem:
        raise ArchiveError(
            f"{name}: the rows up to line {last_line} were refused by the database: {problem.orig}"
        ) from None


def _decode(column, value):
    """The archive's written form back to what the column takes. Strict on types."""
    if value is None:
        if not column.nullable:
            raise ValueError("is null and the column is not")
        return None
    kind = column.type
    if isinstance(kind, Enum):
        return kind.enum_class(_expect(value, str))
    if isinstance(kind, Boolean):
        return _expect(value, bool)
    if isinstance(kind, DateTime):
        moment = datetime.fromisoformat(_expect(value, str))
        if moment.tzinfo is None:
            raise ValueError("has no UTC offset")
        return moment.astimezone(UTC)
    if isinstance(kind, Time):
        return time.fromisoformat(_expect(value, str))
    if isinstance(kind, Date):
        return date.fromisoformat(_expect(value, str))
    if isinstance(kind, Numeric):
        return Decimal(_expect(value, str))
    if isinstance(kind, Integer | BigInteger):
        if isinstance(value, bool):
            raise TypeError("is a boolean, not an integer")
        return _expect(value, int)
    if isinstance(kind, String | Text):
        return _expect(value, str)
    raise TypeError(f"has a column type ({kind!r}) this format does not carry")


def _expect(value, kind):
    if not isinstance(value, kind):
        raise TypeError(f"is {type(value).__name__}, expected {kind.__name__}")
    return value


def _redacted_value(table: str, column: str):
    """What a secret the archive left out becomes. Each one opens nothing."""
    from app.core.security import ABSENT_ACCOUNT_HASH

    if (table, column) == ("users", "credential_secure_hash"):
        # A real bcrypt hash of a random string nobody kept, so a sign-in
        # attempt fails the ordinary way. Shared by every account, which is
        # harmless for a hash no password matches.
        return ABSENT_ACCOUNT_HASH
    if (table, column) == ("api_keys", "key_hash"):
        # The column is unique and required. A random value that is the hash
        # of no key keeps the row, its label and its scopes, and lets nothing
        # in. Reissue the key.
        return secrets.token_hex(32)
    # users.calendar_feed_token and guest_gate_registry.visit_code_hash are
    # nullable. A person gets a new feed link from GET /sync/feed-token; a
    # visitor's code was only ever good for that visit.
    return None


def _open_admin(connection: Connection, password: str | None) -> None:
    from app.core.security import hash_password

    users = Base.metadata.tables["users"]
    found = connection.execute(select(users.c.id).where(users.c.id == SEEDED_ADMIN_ID)).first()
    if found is None:
        # The server seeds the account on its first start, and
        # INITIAL_ADMIN_PASSWORD opens it then, as on any new deployment.
        return
    if not password:
        raise ArchiveError(
            f"The archive carries no password hashes and holds the administrator account "
            f"{SEEDED_ADMIN_ID}, so nobody could sign in after the import. Set "
            "INITIAL_ADMIN_PASSWORD for the import and it becomes that account's password."
        )
    connection.execute(
        users.update()
        .where(users.c.id == SEEDED_ADMIN_ID)
        .values(credential_secure_hash=hash_password(password))
    )


def _advance_sequences(connection: Connection) -> None:
    """Move each id sequence past the ids the import wrote.

    The rows went in with their ids, so the sequences behind those columns
    were never asked for one and still stand at 1. The next insert would
    collide without this.
    """
    for table in EXPORTED:
        keys = table.primary_key.columns.values()
        if len(keys) != 1 or not isinstance(keys[0].type, Integer):
            continue
        column = keys[0].name
        connection.execute(
            text(
                f"SELECT setval(pg_get_serial_sequence(:table, :column), "
                f'COALESCE(MAX("{column}"), 1), MAX("{column}") IS NOT NULL) '
                f'FROM "{table.name}"'
            ),
            {"table": table.name, "column": column},
        )
