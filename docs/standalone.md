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

A program that wants to run Chronos as its own hidden child process, with no
Chronos logins and the identity of each caller asserted by the program, uses
`chronos-engine embedded` instead: see [embedded.md](embedded.md). Everything
on this page about the database, backups and upgrading applies to it too.

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
the engine should move between tagged releases on purpose. There are no
migrations before the first real deployment, so a release does not bring an
older data file forward when the schema has changed (see Upgrading), and a
database Chronos 0.14 or earlier made is refused at start.

The `standalone` extra adds one package, `fakeredis`, which keeps the rate
limit counters and the federated replay cache in memory.

## On a local PostgreSQL

Install PostgreSQL natively (the platform's package manager or the
installer from postgresql.org; it runs as a service and is light at idle),
create an empty database and a user that owns it, then:

```bash
chronos-engine serve --data-dir ./chronos-data --database-url postgresql://chronos:PASSWORD@localhost:5432/chronos
```

On an empty database the engine builds the schema from the models, exactly as
the container does, so the schema has the exclusion constraints that make
double booking impossible. `--data-dir` then holds only `signing.key`. Back up
with `pg_dump`; `chronos-engine backup` is for the SQLite file.

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

## Export and import

To move a deployment, between SQLite and PostgreSQL or to another machine,
use an archive rather than a backup:

```bash
chronos-engine export --data-dir ./chronos-data --to ./chronos.zip
INITIAL_ADMIN_PASSWORD='a password you choose' \
  chronos-engine import --database-url postgresql://chronos:PASSWORD@localhost:5432/chronos --from ./chronos.zip
```

Both take `--data-dir` and `--database-url` as `serve` does, plus `--schema`
for an embedded deployment's schema. The import needs an empty database, so
run it before the first `serve` on the new one. Secrets are left out unless
the export is given `--include-secrets`, and importing an archive without
them needs `INITIAL_ADMIN_PASSWORD`. [portability.md](portability.md) describes the
archive and what to do after an import without secrets.

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

There are no migrations before the first real deployment. The engine builds
whatever tables a database lacks when it starts
(`backend/app/core/schema.py::ensure_schema`) and changes nothing that is
already there, so a file made by one release is not brought forward by the
next when the schema has changed: 0.15 does not upgrade a 0.14 file. A schema
change means recreating the database. `/health` reports `schema_version`,
which the maintainers bump when the models change; when the new release's
number differs from the one your file was made with, stop the engine, move
the old file aside (or recreate the PostgreSQL database), and start again on
an empty one. Migrations come back as a fresh baseline when there is a
deployment worth upgrading.

## For contributors: the models are the schema

PostgreSQL is the target; schema, queries, locking and time handling are
designed for it, and the tests that prove the no-overlap guarantees run
against a real PostgreSQL in CI. SQLite is a convenience. Both are built from
the same models by `create_all`, and that never bends a PostgreSQL design. In
practice:

- Anything PostgreSQL-only (exclusion constraints, `btree_gist`, partial
  indexes using PostgreSQL operators) is declared on the model behind a
  dialect guard, `ddl_if(dialect="postgresql")` on the constraint or
  `DDL(...).execute_if(dialect="postgresql")` on a metadata event, so SQLite
  builds the same models without it. `backend/app/models/db.py::_no_overlap`
  is the pattern.
- Bump `backend/app/core/schema.py::SCHEMA_VERSION` when the models change.
- `tests/test_schema_pg.py` checks what `create_all` leaves on an empty
  PostgreSQL, and `tests/test_schema.py` the step itself on SQLite.
