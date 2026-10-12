# Standalone engine

<!-- Copyright 2026 Chronos Ledger Contributors (Apache 2.0) -->

`chronos-engine` runs the Chronos Ledger API as one Python process, with no
Docker and no Redis. It is for running the engine next to another program on
the same machine: a laptop, a developer's workstation, or a small site with no
server room.

PostgreSQL is the database Chronos is built for. Give `chronos-engine` a local
PostgreSQL with `--database-url` for anything that holds real data. Without
one it falls back to a single SQLite file, which needs no setup and is meant
for trying the engine out and for tests. Nothing in Chronos is designed around
SQLite; a behaviour that only works there is a bug.

The HTTP API is the one the container serves, route for route. A program that
integrates against `chronos-engine` can later point at a container deployment
by changing the base URL and nothing else. The SDKs in [sdks.md](sdks.md) work
against either.

## Install

From a checkout, with [uv](https://github.com/astral-sh/uv):

```bash
cd backend
uv sync --extra standalone
uv run chronos-engine serve --data-dir ./chronos-data
```

Or as a tool on the PATH, from a checkout pinned to a release tag:

```bash
uv tool install "./backend[standalone]"
chronos-engine serve --data-dir ~/chronos-data
```

Pin to a tag (`git checkout vX.Y.Z`) rather than `main`. A program that embeds
the engine should move between tagged releases on purpose, because a release
can migrate the data file forward and an older release then refuses to open it.

The `standalone` extra adds one package, `fakeredis`, which keeps the rate
limit counters and the federated replay cache in memory.

## On a local PostgreSQL

Install PostgreSQL natively (the platform's package manager or the
installer from postgresql.org; it runs as a service and is light at idle),
create an empty database and a user that owns it, then:

```bash
chronos-engine serve --data-dir ./chronos-data --database-url postgresql://chronos:PASSWORD@localhost:5432/chronos
```

On an empty database the engine runs every migration, exactly as the
container does, so the schema has the exclusion constraints that make double
booking impossible. `--data-dir` then holds only `signing.key`. Back up with
`pg_dump`; `chronos-engine backup` is for the SQLite file.

## First start

```bash
INITIAL_ADMIN_PASSWORD='a password you choose' chronos-engine serve --data-dir ./chronos-data
```

On the first start the data directory gets:

| File | What it is |
|---|---|
| `chronos.db` | The SQLite database, when there is no `--database-url`. |
| `signing.key` | The key sessions are signed with, made once. Readable by the owner only where the platform supports it. |

The administrator account is `admin@org.internal`. `INITIAL_ADMIN_PASSWORD`
sets its password on that first start, and the first sign-in has to change it
(`POST /api/v1/auth/change-password`) before any other administrative call
answers. Leave the variable out on later starts.

The process listens on `127.0.0.1:8000`. Options:

| Option | Default | Meaning |
|---|---|---|
| `--data-dir` | `chronos-data` | Where `signing.key` lives, and `chronos.db` when there is no `--database-url`. Created if missing. |
| `--database-url` | none | A PostgreSQL URL. Without it the engine uses the SQLite file. |
| `--host` | `127.0.0.1` | Address to listen on. Keep the loopback default unless a proxy sits in front. |
| `--port` | `8000` | Port. |
| `--log-level` | `info` | uvicorn's log level. |
| `--behind-proxy` | off | Trust `X-Forwarded-*` from the proxy in front, for client addresses in the audit log and the rate limiter. |

Every setting in `.env.example` still applies through the environment, with
two exceptions: `DATABASE_URL` and `REDIS_URL` are always set by
`chronos-engine` (from `--database-url` or the data directory), so a value
left over from a container setup cannot send it elsewhere. `JWT_SECRET_SIGNING_KEY`, if set, wins over `signing.key`.

`APP_ENV` defaults to `production`, which turns off `/docs`. Set
`DOCS_ENABLED=true` to see the interactive API reference.

Health checks are the same as the container's: `/health` for liveness,
`/health/ready` for readiness. Readiness reports `"redis": "memory"`.

## Backups

```bash
chronos-engine backup --data-dir ./chronos-data --to ./backups/chronos-2026-10-12.db
```

This takes a consistent copy through SQLite's backup API while the engine is
running. It refuses to overwrite an existing file. A plain copy of
`chronos.db` while the engine runs can miss recent commits, which sit in
`chronos.db-wal` until SQLite folds them in. On a clean stop the engine folds
them in itself, so after a stop `chronos.db` alone is the whole database.

Keep `signing.key` with the backups if restoring should keep people signed in.
Without it, a restored database works and everyone signs in again.

## Do not put the data directory in a synced folder

OneDrive, Dropbox, Google Drive and iCloud rewrite files underneath a program
that has them open. SQLite's locking does not survive that and the usual
outcome is a corrupt database. `chronos-engine` warns when the data directory
path looks like one of these. Keep the data in a local folder and copy backups
into the synced folder instead.

## What this profile gives up for being one process

These are the differences from the container deployment, all of them a
consequence of running as one process. The second applies only to the SQLite
file; on PostgreSQL the engine uses the same row locks and exclusion
constraints as the container.

- **One worker.** There is no option for more. Two processes would each keep
  their own rate limits and their own scheduler, so the nightly ledger run
  would happen twice and every limit would be twice as loose.
- **Writes take turns.** Every transaction starts with `BEGIN IMMEDIATE`, so
  one transaction holds the write lock at a time and the next waits for it, up
  to ten seconds. This is what stands in for PostgreSQL's row locks and
  exclusion constraints, neither of which SQLite has: two requests booking the
  same room cannot both see it free. Reads in WAL mode are cheap, but they go
  through the same lock, so a long import holds up other requests until it
  finishes. Fine for one organization's traffic; the container is the answer
  for more.
- **The replay cache forgets on restart.** A federated sign-in note
  ([federated-identity.md](federated-identity.md)) used just before a restart
  could be used once more after it, until it expires. That window is at most
  `FEDERATED_TOKEN_MAX_LIFETIME_SECONDS`, 120 by default. Lower it if that
  matters.
- **Live updates stay in this process.** The websocket relay between instances
  is off, since there is only one instance.

## Upgrading

Stop the engine, take a backup, move to the new tag, start it again. A new
file is built straight from the models and stamped at the newest migration. An
existing file is brought forward by the migration scripts, which run on SQLite
from migration 030 onwards. The engine refuses to start on a file migrated by
a newer release, and says so, rather than guessing.

A file not made by `chronos-engine` (tables but no migration stamp) is refused
too. Point `--data-dir` at an empty folder.

## For contributors: migrations are written for PostgreSQL

PostgreSQL is the target; schema, queries, locking and time handling are
designed for it, and the tests that prove the no-overlap guarantees run
against a real PostgreSQL in CI. SQLite is a convenience. A new SQLite file is
built from the models, never from the early migrations. Migrations from 030 on
are kept runnable on SQLite as well, so a SQLite file made by one release can
still be upgraded by the next, but that never bends a PostgreSQL design. In
practice:

- Use `op.create_index`, `op.add_column` and friends. `alembic/env.py` turns on
  batch mode on SQLite, which copies the table where SQLite cannot alter it in
  place.
- Anything PostgreSQL-only (exclusion constraints, GiST, partial indexes using
  PostgreSQL operators, `ALTER TYPE`) goes behind
  `if op.get_bind().dialect.name == "postgresql":`, with the model kept in step
  so a file built from the models matches.
- `tests/test_standalone.py::test_an_older_file_is_upgraded_with_the_migrations`
  runs the newest migration against a SQLite file.
