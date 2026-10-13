# The clock

<!-- Copyright 2026 Chronos Ledger Contributors (Apache 2.0) -->

Every time the backend reads, it reads from one place:
`backend/app/core/clock.py::now`. By default that is the system clock and
nothing about the application is different from before the clock existed.
A host program that embeds the engine can instead hand it a clock that
stands still until told to move, and then drive a day of operations in a
second, as many times as it likes, and get the same database each time.

## System clock

`CLOCK_MODE=system`, the default. `clock.now()` is the current UTC instant,
APScheduler runs the nightly jobs, and `CLOCK_START` and `ID_SEED` are
ignored if set.

## Host clock

`CLOCK_MODE=host` with `CLOCK_START` set to an ISO 8601 instant carrying an
offset, such as `2026-09-07T08:00:00+00:00`. A start without an offset is
refused at startup, as is host mode without a start.

The clock reads `CLOCK_START` until the host calls
`backend/app/cron/scheduled.py::advance` with a later instant. It never
moves on its own: a request that arrives an hour of real time later is
stamped with the same instant as the one before it. `advance` refuses to go
backwards and raises instead; advancing to the instant the clock already
reads is allowed and does nothing.

Two things change under a host clock:

- APScheduler does not start. The jobs it would have run are run by
  `advance` instead, as described below. The ledger catch-up that normally
  runs once at startup still runs once at startup, reading the host clock,
  so the day the clock starts in has its rows.
- `backend/app/core/time.py::org_now`, `org_today` and `org_tomorrow` read
  the host clock, so "today" in the organization's zone is the day the
  host says it is.

A host that runs the engine in its own process calls `advance` directly. A
host that runs it as a separate process uses the embedded flavour
([embedded.md](embedded.md)): `chronos-engine embedded --clock-start
<instant>` puts the process in host mode, `--id-seed` seeds the ids, and
`POST /api/v1/clock/advance` calls `advance` on the host's behalf. Only the
host itself, the reserved actor `system`, may call it; anyone the host names
may read the clock at `GET /api/v1/clock`. The other flavours (`serve`, the
container) have no such route: nothing a deployment serves can move its
clock. The engine keeps no record of where the clock stood, so a host that
restores a save starts the process again with the saved instant as
`--clock-start`.

## What is stamped from the clock

Every timestamp the application writes: `created_at` and `cancelled_at` on
a reservation, `timestamp_marked` on a visitor check-in, `at` on an audit
record, `deactivated_at` on a user, and the rest. The database never stamps
its own time: the models carry Python-side defaults that call the clock and
no `server_default`, so a row inserted under a host clock reads the host's
instant on every database.

Every "is it time yet" question the application asks: a visit code's
expiry, a visit's end, a refresh token's expiry and the grace in which a
reused one is forgiven, an API key's expiry, the retention cutoff for old
check-ins. Under a frozen clock none of these happen until the host moves
the clock past them, which is the point.

## What stays on real time

Three reads use `clock.wall_now()`, which is real time whatever the mode.
`backend/tests/test_clock_guard.py` holds the list and fails if a fourth
appears without being added there.

| Where | Why |
|---|---|
| `backend/app/core/security.py::create_access_token` | The `exp` claim of the access token. PyJWT checks it against the system clock when the token comes back and takes no other clock, so a token stamped from a host clock set in the past would be refused the moment it was issued. |
| `backend/app/services/federated_identity.py::verify_note` | The instant an outside issuer's note is checked against. The issuer stamped `exp`, `nbf` and `iat` from its own clock, and PyJWT checks them against this process's. |
| `backend/app/api/v1/endpoints/federation.py::add_key` | The default `not_before` of a registered signing key, which the verification above reads, so the two agree. |

So an access token lives its fifteen real minutes however the host clock
moves, and a federated sign-in works under a host clock only while the
issuer's clock and the real clock agree, which is what it needs anyway.

## Identifiers

`backend/app/core/ids.py` draws the identifiers that are not secrets:
the family id a sign-in's refresh tokens share, and the account id a
federated sign-in is given. Unseeded, it is `uuid4` and `secrets`; with
`ID_SEED` set to an integer it is one fixed sequence, so the same script
produces the same ids. Primary keys are integers the database hands out in
insertion order and are already the same from one run to the next.

Anything a caller presents to be believed stays on `secrets` whatever the
seed: passwords, refresh tokens, API keys, visit codes, calendar feed
tokens, the standalone signing key, and the hash the seeded administrator
account is created with. A seeded secret is a guessable secret.

## Jobs under a host clock

`backend/app/cron/scheduled.py::JOBS` is the table of what the scheduler
would run. `run_due_jobs(previous, current)` runs every job whose moment
falls in the half-open window `(previous, current]`: a job due exactly at
`current` runs, one due exactly at `previous` ran last time. Moments are
sorted, and jobs that fall on one instant run in table order:

| Order | Job | When, in `ORG_TIMEZONE` | Does |
|---|---|---|---|
| 1 | `nightly_ledger_gen` | 23:00 daily | Writes the `daily_ledger` rows still missing from tomorrow through `LEDGER_HORIZON_DAYS` ahead |
| 2 | `refresh_token_purge` | 03:00 daily | Deletes refresh tokens a day past expiry |
| 3 | `guest_retention_purge` | 03:30 daily | Deletes visitor check-ins older than `GUEST_RETENTION_DAYS`, when set |
| 4 | `idempotency_purge` | 03:45 daily | Deletes `Idempotency-Key` records older than `IDEMPOTENCY_RETENTION_HOURS` |
| 5 | `guest_overstay_notice` | every 5 minutes | Announces approved visits that have run past their end |

Before each job runs the clock is set to that job's moment, so the nightly
run at 23:00 sees the same "tomorrow" it would have seen at 23:00, and the
rows it writes are stamped with 23:00. After the last job the clock is set
to `current`. `advance(instant)` is `run_due_jobs(clock.now(), instant)` and
returns the names of the jobs that ran, in order.

The overstay notice runs once per window, at the last five-minute mark
inside it, rather than once per mark. That is how APScheduler treats runs
it missed while the process was busy, and the job is a sweep that announces
whatever is overdue, so the last run does the work of all of them. An
advance that crosses a whole day therefore runs five jobs, not three
hundred.

## The determinism guarantee

With `CLOCK_MODE=host`, a fixed `CLOCK_START`, a fixed `ID_SEED` and the
same `ORG_TIMEZONE`, the same sequence of requests and advances against a
freshly created database produces the same rows, byte for byte, in every
table. `backend/tests/test_determinism.py` holds the engine to it: it
drives a day through the API twice, holds a room, advances across midnight
so the nightly run lays down a day, books, cancels, and compares the full
export of both databases.

Its limits:

- Secrets differ between runs by design. The seeded administrator's
  password hash, any refresh token, API key or visit code minted during the
  run, and any calendar feed token left to its default are random each
  time. The test authenticates with an API key it seeds itself for that
  reason, and a host that wants two runs to match should do the same, or
  compare with those columns set aside.
- The hash of a password is salted, so two runs that set the same password
  store different hashes.
- Access tokens carry real-time expiry, so the tokens themselves differ.
  Nothing stores them.
- Rows the database orders by its own choice, with no `ORDER BY`, can come
  back in a different order on a different engine; the guarantee is about
  what the rows hold.
- The clock is process-wide. Two hosts in one process share it.
- The relay between instances and the rate limiter read Redis, which keeps
  its own time; the standalone engine's in-memory Redis is in the same
  process and does not.
