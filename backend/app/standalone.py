# Copyright 2026 Chronos Ledger Contributors
# Licensed under the Apache License, Version 2.0
"""chronos-engine: Chronos Ledger as one process on one SQLite file.

No Docker, no PostgreSQL, no Redis. For running the engine beside another
program on the same machine, a laptop, or a small site with no server room.
The HTTP API is the same one the container serves, so an integrator that
starts here can move to the container later without changing a call.

    chronos-engine serve --data-dir ./chronos-data
    chronos-engine backup --data-dir ./chronos-data --to backup.db

docs/standalone.md has what this profile gives up for being one process.
"""

import argparse
import logging
import os
import secrets
import sqlite3
import sys
from pathlib import Path

DATABASE_FILE = "chronos.db"
SIGNING_KEY_FILE = "signing.key"
# Folders a sync client rewrites underneath an open database. SQLite's locks
# do not survive that, and the usual outcome is a corrupt file.
SYNCED_FOLDER_MARKERS = ("onedrive", "dropbox", "google drive", "icloud")

log = logging.getLogger("chronos.standalone")


def database_url(data_dir: Path) -> str:
    return f"sqlite:///{(data_dir / DATABASE_FILE).as_posix()}"


def _signing_key(data_dir: Path) -> str:
    """The key sessions are signed with, made once and kept beside the data.

    Kept rather than made fresh on each start, because a new key signs out
    everyone and invalidates every refresh token on every restart.
    """
    path = data_dir / SIGNING_KEY_FILE
    if path.exists():
        return path.read_text(encoding="utf-8").strip()
    key = secrets.token_hex(32)
    path.write_text(key, encoding="utf-8")
    # Owner only, where the platform has the notion. Windows ignores it and
    # relies on the folder's own permissions.
    path.chmod(0o600)
    return key


def configure_environment(data_dir: Path) -> None:
    """Point the settings at this data directory, before anything reads them.

    get_settings is cached on first use and app.core.database builds its
    engine at import, so this has to run before either is imported.

    DATABASE_URL and REDIS_URL are set outright: this command is the SQLite
    profile, and a DATABASE_URL left over from a container setup must not
    quietly send it somewhere else. Everything else is a default the operator
    can override in the environment.
    """
    os.environ["DATABASE_URL"] = database_url(data_dir)
    os.environ["REDIS_URL"] = "memory://"
    os.environ.setdefault("APP_ENV", "production")
    if "JWT_SECRET_SIGNING_KEY" not in os.environ:
        os.environ["JWT_SECRET_SIGNING_KEY"] = _signing_key(data_dir)


def prepare_database(engine) -> str:
    """Bring the database to the schema this code expects. Returns what it did.

    A new file gets the schema from the models in one transaction, the seeded
    administrator migration 001 would have written, and a stamp at the newest
    migration. The migrations themselves are not replayed on SQLite: the early
    ones are written for PostgreSQL and use what only it has. Migrations from
    030 on run on both, which is how a file made by this release is upgraded
    by the next one.
    """
    from alembic.runtime.migration import MigrationContext
    from sqlalchemy import inspect

    from app.core.migrations import _scripts, database_revision, unknown_revision_message

    message = unknown_revision_message(engine)
    if message:
        raise SystemExit(message)

    scripts = _scripts()
    head = scripts.get_current_head()
    revision = database_revision(engine)
    if revision == head:
        return "current"
    if revision is not None:
        _upgrade(engine)
        return "upgraded"
    if inspect(engine).has_table("users"):
        raise SystemExit(
            "The database has tables but no migration stamp, so it was not made by "
            "chronos-engine. Point --data-dir at an empty folder."
        )

    import app.models.db  # noqa: F401 (registers every table with the metadata)
    from app.core.database import Base

    with engine.begin() as connection:
        Base.metadata.create_all(connection)
        _seed_administrator(connection)
        MigrationContext.configure(connection).stamp(scripts, head)
    return "created"


def _seed_administrator(connection) -> None:
    """The account migration 001 seeds, as migration 004 left it.

    Its password is random and unknown, as there: INITIAL_ADMIN_PASSWORD opens
    it on the first start (app/core/bootstrap.py).
    """
    from sqlalchemy.orm import Session

    from app.core.bootstrap import SEEDED_ADMIN_ID
    from app.core.security import hash_password
    from app.models.db import InstitutionalRole, User

    session = Session(bind=connection)
    session.add(
        User(
            id=SEEDED_ADMIN_ID,
            full_name="Organization Administrator",
            email_address="admin@org.internal",
            credential_secure_hash=hash_password(secrets.token_urlsafe(32)),
            role_type=InstitutionalRole.ORG_ADMIN,
            initial_login_state=True,
        )
    )
    session.flush()


def _upgrade(engine) -> None:
    from alembic.config import Config

    from alembic import command
    from app.core.migrations import script_location

    # No alembic.ini: it carries only logging setup, which would replace the
    # app's, and a PostgreSQL URL that env.py overrides anyway.
    config = Config()
    config.set_main_option("script_location", str(script_location()))
    config.set_main_option("sqlalchemy.url", engine.url.render_as_string(hide_password=False))
    command.upgrade(config, "head")


def _warn_about_synced_folders(data_dir: Path) -> None:
    lowered = str(data_dir).lower()
    if any(marker in lowered for marker in SYNCED_FOLDER_MARKERS):
        log.warning(
            "%s looks like a folder a sync client manages. A sync client "
            "rewriting the database while it is open corrupts it. Use a local "
            "folder and copy backups there instead.",
            data_dir,
        )


def serve(args) -> int:
    data_dir = Path(args.data_dir).resolve()
    data_dir.mkdir(parents=True, exist_ok=True)
    _warn_about_synced_folders(data_dir)
    configure_environment(data_dir)

    import uvicorn

    from app.core.database import engine

    log.info("Database %s: %s", data_dir / DATABASE_FILE, prepare_database(engine))
    # One worker, always. Two processes would each keep their own rate limits
    # and their own scheduler, so the nightly jobs would run twice and the
    # limits would be twice as loose. There is no flag for more on purpose.
    uvicorn.run(
        "app.main:app",
        host=args.host,
        port=args.port,
        workers=1,
        log_level=args.log_level,
        proxy_headers=args.behind_proxy,
    )
    return 0


def backup(args) -> int:
    """Copy the database while it is in use, through SQLite's backup API.

    A plain file copy of a database in WAL mode can miss the commits that are
    still in the -wal file. This takes a consistent copy and never blocks the
    running engine for longer than one page step.
    """
    source_path = Path(args.data_dir).resolve() / DATABASE_FILE
    if not source_path.exists():
        print(f"No database at {source_path}", file=sys.stderr)
        return 1
    target_path = Path(args.to).resolve()
    if target_path.exists():
        print(f"{target_path} already exists; choose a new file", file=sys.stderr)
        return 1
    source = sqlite3.connect(source_path)
    target = sqlite3.connect(target_path)
    try:
        with target:
            source.backup(target)
    finally:
        target.close()
        source.close()
    print(f"Backed up {source_path} to {target_path}")
    return 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="chronos-engine", description=__doc__.splitlines()[0])
    commands = parser.add_subparsers(dest="command", required=True)

    run = commands.add_parser("serve", help="run the API on a SQLite file")
    run.add_argument("--data-dir", default="chronos-data", help="where the database lives")
    run.add_argument("--host", default="127.0.0.1", help="address to listen on")
    run.add_argument("--port", type=int, default=8000)
    run.add_argument("--log-level", default="info")
    run.add_argument(
        "--behind-proxy",
        action="store_true",
        help="trust X-Forwarded-* headers from the proxy in front",
    )
    run.set_defaults(handler=serve)

    copy = commands.add_parser("backup", help="copy the database while it runs")
    copy.add_argument("--data-dir", default="chronos-data")
    copy.add_argument("--to", required=True, help="new file to write the copy to")
    copy.set_defaults(handler=backup)
    return parser


def main(argv: list[str] | None = None) -> int:
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(name)s: %(message)s")
    args = build_parser().parse_args(argv)
    return args.handler(args)


if __name__ == "__main__":
    sys.exit(main())
