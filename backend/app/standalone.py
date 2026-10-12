# Copyright 2026 Chronos Ledger Contributors
# Licensed under the Apache License, Version 2.0
"""chronos-engine: Chronos Ledger as one process on one SQLite file.

No Docker and no Redis. For running the engine beside another program on the
same machine, a laptop, or a small site with no server room. PostgreSQL is
the database to use for anything real (--database-url, pointing at a local
install); with no URL it falls back to a SQLite file, which is for trying the
engine out and for tests.
The HTTP API is the same one the container serves, so an integrator that
starts here can move to the container later without changing a call.

    chronos-engine serve --data-dir ./chronos-data
    chronos-engine serve --database-url postgresql://user:pass@localhost/chronos
    chronos-engine backup --data-dir ./chronos-data --to backup.db

docs/standalone.md has what this profile gives up for being one process.

`chronos-engine embedded` is the same process started by another program as
a hidden child: loopback only, the host's secret on every request, the
host's users asserted by header, and an exit when the host goes away.
docs/embedded.md has the contract.

    CHRONOS_HOST_SECRET=... chronos-engine embedded --data-dir ./chronos-data --parent-pid 1234
    chronos-engine embedded --database-url postgresql://... --schema chronos --secret-from-stdin
"""

import argparse
import json
import logging
import os
import secrets
import sqlite3
import stat
import sys
import threading
import time
from datetime import datetime
from pathlib import Path

import uvicorn

DATABASE_FILE = "chronos.db"
DEFAULT_SCHEMA = "chronos"
# GetExitCodeProcess answers this for a process that is still running.
STILL_ACTIVE = 259
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


def configure_environment(data_dir: Path, url: str | None = None) -> None:
    """Point the settings at this data directory, before anything reads them.

    get_settings is cached on first use and app.core.database builds its
    engine at import, so this has to run before either is imported.

    DATABASE_URL and REDIS_URL are set outright, from --database-url or the
    data directory: a DATABASE_URL left over from a container setup must not
    quietly send this process somewhere else. Everything else is a default
    the operator can override in the environment.
    """
    os.environ["DATABASE_URL"] = url or database_url(data_dir)
    os.environ["REDIS_URL"] = "memory://"
    os.environ.setdefault("APP_ENV", "production")
    if "JWT_SECRET_SIGNING_KEY" not in os.environ:
        os.environ["JWT_SECRET_SIGNING_KEY"] = _signing_key(data_dir)


def prepare_database(engine) -> str:
    """Build the schema from the models, on either dialect. Returns what it did.

    The same step the server runs on start (app.core.schema.ensure_schema),
    done here first so a database that cannot be built stops the process with
    the error before uvicorn binds a port. A new SQLite file gets every table
    and the seeded administrator; an existing one is left as it is. There are
    no migrations: a file made by an older release is not upgraded.
    """
    from app.core.schema import ensure_schema

    return ensure_schema(engine)


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
    configure_environment(data_dir, args.database_url)

    from app.core.database import engine

    log.info(
        "Database %s: %s",
        engine.url.render_as_string(hide_password=True),
        prepare_database(engine),
    )
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


def read_host_secret(args, stdin) -> str | None:
    """From the environment, or the first line of stdin. Never from argv."""
    from app.core.host_identity import HOST_SECRET_ENV

    if args.secret_from_stdin:
        return stdin.readline().rstrip("\r\n")
    return os.environ.get(HOST_SECRET_ENV)


def configure_clock(clock_start: str | None, id_seed: int | None) -> None:
    """Put the clock settings in the environment, before anything reads them.

    --clock-start is the one switch into host mode: CLOCK_MODE is set
    outright either way, so a CLOCK_MODE left in the environment cannot put
    the process on a clock the host did not ask for. A start without an
    offset is a ValueError here rather than a settings error later, so the
    message names the flag.
    """
    if clock_start is None:
        os.environ["CLOCK_MODE"] = "system"
    else:
        try:
            start = datetime.fromisoformat(clock_start)
        except ValueError:
            start = None
        if start is None or start.tzinfo is None or start.utcoffset() is None:
            raise ValueError(
                f"--clock-start {clock_start!r} is not an ISO 8601 instant with an offset, "
                "such as 2026-09-07T08:00:00+00:00"
            )
        os.environ["CLOCK_MODE"] = "host"
        os.environ["CLOCK_START"] = clock_start
    if id_seed is not None:
        os.environ["ID_SEED"] = str(id_seed)


def embedded(args) -> int:
    # Before the first `app.` import: app.core.config caches its settings on
    # first use, the clock is built from them, and app.core.database builds
    # its engine from them at import. Nothing under `app.` is imported until
    # configure_environment has run, host_identity included: it imports the
    # database module.
    try:
        configure_clock(args.clock_start, args.id_seed)
    except ValueError as problem:
        print(f"chronos-engine embedded: {problem}", file=sys.stderr)
        return 2
    if args.socket and sys.platform == "win32":
        print("chronos-engine embedded: --socket needs a POSIX platform", file=sys.stderr)
        return 2

    data_dir = Path(args.data_dir).resolve()
    data_dir.mkdir(parents=True, exist_ok=True)
    _warn_about_synced_folders(data_dir)
    configure_environment(data_dir, args.database_url)

    from app.core.host_identity import check_host_secret

    try:
        secret = check_host_secret(read_host_secret(args, sys.stdin))
    except ValueError as problem:
        print(f"chronos-engine embedded: {problem}", file=sys.stderr)
        return 2

    from app.core.database import engine, is_sqlite, use_schema

    schema = None
    if is_sqlite(str(engine.url)):
        log.info("A SQLite file has no schemas; --schema is not used")
    else:
        schema = args.schema
        use_schema(engine, schema)

    from app.embedded import build_app, prepare_database

    log.info(
        "Database %s, schema %s: %s",
        engine.url.render_as_string(hide_password=True),
        schema or "(none)",
        prepare_database(engine, schema),
    )
    return run_embedded(build_app(secret), args)


def ready_line(server: uvicorn.Server) -> str:
    """The one line the host reads from stdout. Nothing else is written there."""
    from app.core import clock
    from app.core.schema import SCHEMA_VERSION

    if server.config.uds:
        where = {"socket": server.config.uds}
    else:
        where = {"port": server.servers[0].sockets[0].getsockname()[1]}
    mode = "host" if clock.is_host() else "system"
    return json.dumps(
        {"chronos": "ready", **where, "schema_version": SCHEMA_VERSION, "clock": mode}
    )


class AnnouncingServer(uvicorn.Server):
    """uvicorn's server, which tells the host when it listens.

    After startup, not before: by then the lifespan has run, so the schema is
    built and the scheduler is up, and with --port 0 the port is known.
    """

    async def startup(self, sockets=None) -> None:
        await super().startup(sockets)
        if self.started:
            print(ready_line(self), flush=True)


def watch_stdin(stream, stop) -> None:
    """Block until the host closes our stdin, then ask the server to stop.

    The portable way to notice a parent going away: a pipe closes when the
    process holding the other end exits, on every platform, whether it exited
    cleanly or not. Lines the host writes are read and ignored.
    """
    while stream.readline():
        pass
    stop()


def watch_stdin_pipe(fd: int, stop, interval: float = 0.5) -> None:
    """Windows: poll the stdin pipe instead of leaving a read pending on it.

    A read left pending on the pipe blocks other calls on that handle from
    any thread, and loading numpy's bundled OpenBLAS makes one of those
    calls, so with a reader thread blocked here an import of numpy or pandas
    on another thread never returned. PeekNamedPipe does not pend: it says
    how many bytes are waiting, or fails once the host's end is closed. The
    bytes it reports are read and dropped so the pipe never fills.
    """
    import ctypes
    import msvcrt
    from ctypes import wintypes

    peek = ctypes.windll.kernel32.PeekNamedPipe
    peek.argtypes = [wintypes.HANDLE, wintypes.LPVOID, wintypes.DWORD] + [wintypes.LPDWORD] * 3
    handle = msvcrt.get_osfhandle(fd)
    available = wintypes.DWORD()
    while peek(handle, None, 0, None, ctypes.byref(available), None):
        if available.value:
            os.read(fd, available.value)
        time.sleep(interval)
    stop()


def stdin_watcher(stream):
    """The thread target and its argument for noticing this stdin closing.

    The poller is for a pipe on Windows. A console, NUL, a file, or a stream
    with no descriptor at all keeps the blocking read, where end of file
    means what it always did.
    """
    if sys.platform == "win32":
        try:
            fd = stream.fileno()
            if stat.S_ISFIFO(os.fstat(fd).st_mode):
                return watch_stdin_pipe, fd
        except OSError:
            pass
    return watch_stdin, stream


def parent_alive(pid: int) -> bool:
    if sys.platform == "win32":
        import ctypes

        kernel32 = ctypes.windll.kernel32
        process_query_limited_information = 0x1000
        handle = kernel32.OpenProcess(process_query_limited_information, False, pid)
        if not handle:
            return False
        try:
            code = ctypes.c_ulong()
            if not kernel32.GetExitCodeProcess(handle, ctypes.byref(code)):
                return False
            return code.value == STILL_ACTIVE
        finally:
            kernel32.CloseHandle(handle)
    try:
        os.kill(pid, 0)
    except ProcessLookupError:
        return False
    except PermissionError:
        return True
    return True


def watch_parent(pid: int, stop, alive=parent_alive, interval: float = 1.0) -> None:
    """Poll for the host once a second and ask the server to stop when it is gone."""
    while alive(pid):
        time.sleep(interval)
    stop()


def run_embedded(application, args) -> int:
    # log_config=None: uvicorn's own configuration writes access lines to
    # stdout, which belongs to the ready line. Without it every logger
    # propagates to the root handler main() set up, on stderr.
    config = uvicorn.Config(
        application,
        host="127.0.0.1",
        port=args.port,
        uds=args.socket,
        workers=1,
        log_level=args.log_level,
        log_config=None,
    )
    server = AnnouncingServer(config)

    def stop() -> None:
        log.info("The host went away; stopping")
        # Read by uvicorn's main loop, which then runs the lifespan shutdown.
        server.should_exit = True

    if sys.stdin is not None:
        target, source = stdin_watcher(sys.stdin)
        threading.Thread(target=target, args=(source, stop), daemon=True).start()
    if args.parent_pid is not None:
        threading.Thread(target=watch_parent, args=(args.parent_pid, stop), daemon=True).start()
    # SIGINT, SIGTERM and, on Windows, CTRL_BREAK are uvicorn's to handle.
    server.run()
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
    run.add_argument(
        "--data-dir",
        default="chronos-data",
        help="where the signing key lives, and the SQLite file when there is no --database-url",
    )
    run.add_argument(
        "--database-url",
        help="a PostgreSQL URL; without one the engine uses a SQLite file in --data-dir",
    )
    run.add_argument("--host", default="127.0.0.1", help="address to listen on")
    run.add_argument("--port", type=int, default=8000)
    run.add_argument("--log-level", default="info")
    run.add_argument(
        "--behind-proxy",
        action="store_true",
        help="trust X-Forwarded-* headers from the proxy in front",
    )
    run.set_defaults(handler=serve)

    child = commands.add_parser(
        "embedded", help="run as a hidden child of a host program (docs/embedded.md)"
    )
    child.add_argument(
        "--data-dir",
        default="chronos-data",
        help="where the signing key lives, and the SQLite file when there is no --database-url",
    )
    child.add_argument(
        "--database-url",
        help="the host's PostgreSQL; without one the engine uses a SQLite file in --data-dir",
    )
    child.add_argument(
        "--schema",
        default=DEFAULT_SCHEMA,
        help="the PostgreSQL schema every Chronos table lives in, made if missing",
    )
    child.add_argument("--port", type=int, default=0, help="port on 127.0.0.1; 0 picks a free one")
    child.add_argument("--socket", help="listen on this Unix socket instead of a port (POSIX only)")
    child.add_argument(
        "--secret-from-stdin",
        action="store_true",
        help="read the host secret from the first line of stdin instead of CHRONOS_HOST_SECRET",
    )
    child.add_argument(
        "--parent-pid", type=int, help="also stop when this process is gone (checked every second)"
    )
    child.add_argument("--log-level", default="info")
    child.add_argument(
        "--clock-start",
        metavar="INSTANT",
        help="run on a host clock that starts at this ISO 8601 instant with an offset, "
        "moved by POST /api/v1/clock/advance (docs/clock.md); without it, the system clock",
    )
    child.add_argument(
        "--id-seed", type=int, metavar="N", help="seed the non-secret identifiers (ID_SEED)"
    )
    child.set_defaults(handler=embedded)

    copy = commands.add_parser(
        "backup", help="copy the SQLite file while it runs (on PostgreSQL, use pg_dump)"
    )
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
