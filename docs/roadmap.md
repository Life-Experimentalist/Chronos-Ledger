# Roadmap

<!-- Copyright 2026 Chronos Ledger Contributors (Apache 2.0) -->

Current release: 0.15.0, with 0.16 next. This page plans the releases after
it. The plan is detailed on purpose: each item has a scope, the files it touches and
a check that says when it is done, so it can be picked up without
re-deciding anything.

Chronos Ledger stays on `0.x` until the scheduling API has stopped changing.
Several items below change the API (recurrence rules, the resource
requirement model, the login field), and those are the reason `1.0` waits.

## What the engine is for

The target is everything a scheduling engine has to do for a hospital
management system, done completely and without surprises: rooms, theatres,
staff and equipment as resources; shifts, rotations and leave; bookings that
can never double-book; and a ledger of what actually happened. Hospital work
is the hardest case in scope, so meeting it covers the simpler ones
(colleges, offices, clinics). An integrator embeds the engine behind its own
product and talks to it only through the HTTP API and the SDKs.

Integrators pin to tagged releases, never to `main`. There are no migrations
before the first real deployment, so a schema change means recreating the
database, and the changelog for each tag is the contract they upgrade against.

## At a glance

| Release | Theme | Breaking |
|---|---|---|
| 0.13 | Platform: contract check, hardening, `chronos` CLI and channels, first SDKs, ledger range queries, audit log | No |
| 0.14 | Roles renamed, guest desk (visit expiry, configurable approver, change feed), federated identity | Yes |
| 0.15 | Standalone engine (`chronos-engine`, no Docker or Redis, on PostgreSQL or a SQLite file), embedded flavour with the host clock, Alembic removed (the models own the schema, `SCHEMA_VERSION`), PostgreSQL-first `--database-url`, optional Cloudflare tunnel compose profile, psycopg 3 and SQLAlchemy 2.1 | Yes |
| 0.16 | Integration contract (error codes, idempotency on every write, export and import, SDK retries, failure modes written down), webhooks, activities CRUD, reservation external reference; engine part 1: resource modes, conflict report, rolling horizon; Go and Rust SDKs, Helm | Additive |
| 0.17 | Engine, part 2: recurrence rules, editable timetable, exclusion on instances; per-organization uniqueness | Yes |

PostgreSQL is the database Chronos is designed for. SQLite exists so the
engine can be tried and tested with no setup; a behaviour that works only on
SQLite is a bug, and no PostgreSQL design is bent to suit it.

Detailed designs: [distribution.md](distribution.md) for installers, channels,
drift and signing; [sdks.md](sdks.md) for client libraries;
[quickstart.md](quickstart.md) is the REST guide that exists today.

---

## 0.13: Platform

### P-1. The spec is checked against the server

- **Scope:** CI job comparing `app.openapi()` with `docs/openapi.yaml` on
  methods, paths, request bodies and response schemas. Add an `operationId` to
  every route in both.
- **Touches:** `.github/workflows/ci.yml`, a script under `backend/scripts/`,
  every router in `backend/app/api/v1/endpoints/`, `docs/openapi.yaml`.
- **Done when:** removing a route from the YAML fails CI, and every operation
  has an `operationId` of the form `<area>.<verb>`.

### P-2. Health reports version and schema version

- **Scope:** `/health` returns `version` and `schema_version`, a constant in
  `backend/app/core/schema.py` the maintainers bump when the models change.
- **Touches:** `backend/app/main.py`, `backend/app/core/schema.py`.
- **Done when:** `/health` carries both and a test checks it.
- **Status:** shipped. It first reported the migration revision, and refused
  to start on a database migrated by a newer release; both went with the
  migrations. There are none before the first real deployment, and a release
  does not upgrade the database the one before it made.

### P-3. Readiness depends only on what must be up

- **Scope:** `/health` stays a liveness check and answers without touching
  anything. A new `/health/ready` runs `SELECT 1` against PostgreSQL and fails
  when that fails. It pings Redis too and reports the result, but Redis being
  down does not fail readiness, since the app keeps working without it.
  Container healthchecks move to `/health/ready`.
- **Touches:** `backend/app/main.py`, `nginx/chronos-common.conf`, compose
  healthchecks, `docs/deployment.md`.
- **Done when:** stopping Redis leaves the stack healthy; stopping PostgreSQL
  does not.

### P-4. Build and supply chain hygiene

- **Scope:**
  - Pin third-party GitHub Actions to commit SHAs, with Dependabot keeping them current.
  - Remove `--legacy-peer-deps` from the frontend install by fixing the peer ranges it hides.
  - Serve icon and font assets from the app itself instead of third-party CDNs.
  - Add a backend coverage floor at the current level, and CodeQL for Python and TypeScript.
  - CI runs the backend tests on the Python version the image uses (3.14) as well as the minimum declared in `pyproject.toml`.
- **Done when:** each is merged and CI is green; the frontend loads with no requests to outside origins.

### P-5. Login field name

- **Scope:** `POST /auth/login` takes `email_address`, the name every other
  schema uses, and keeps accepting `email` as a deprecated alias through 0.15.
  `email` is removed in 0.16.
- **Touches:** `backend/app/schemas/auth.py`, `frontend` login call,
  `docs/api.md`, `docs/quickstart.md`, `docs/openapi.yaml`.
- **Done when:** both forms sign in; the docs show `email_address`.

### P-6. `chronos` CLI and channels

See [distribution.md](distribution.md) and [cli.md](cli.md). In 0.13: the CLI
(`cli/`), drift handling, GitHub Releases, install scripts, the Homebrew tap
and the Scoop bucket. npm, PyPI, crates.io and WinGet moved out of 0.13 and
are added on request, one at a time. Windows signing lands when the
certificate is issued and does not block the release.

### P-7. TypeScript and Python SDKs

See [sdks.md](sdks.md). Depends on P-1. In 0.13: both libraries in `sdks/`,
with token refresh, safe retries, paging and typed errors, checked in CI
against the spec. Publishing to npm and PyPI is added on request.

### P-8. Ledger range queries

- **Scope:** `GET /schedule/ledger?from=&to=` returns ledger rows between two
  dates inclusive, with an optional `resource_id`, paged like the other list
  routes and ordered by date, then start time. Rows have the same shape as
  `/schedule/ledger/today`, and the same role filter applies: staff see the
  rows they lead or cover, members the activities they are enrolled in.
  `to` before `from` is a `422`.
- **Touches:** `backend/app/api/v1/endpoints/schedule.py`, `docs/api.md`,
  `docs/openapi.yaml`.
- **Done when:** a week of rows comes back in date order with `X-Total-Count`;
  `/ledger/today` returns exactly what it did before.

### P-9. Audit log

- **Scope:** every write under `/api/v1` (any method other than GET, HEAD and
  OPTIONS) is recorded after it completes: time, the user, the API key if one
  was used, method, path and status code. Request and response bodies are never
  stored, since they carry passwords and uploaded files. A failed audit write
  is logged and never fails the request. `GET /audit?from=&to=&actor_id=` pages
  through the records, newest first, `ORG_ADMIN` only; API keys need
  `audit:read`.
- **Not in scope:** before and after snapshots of the changed rows. The path
  and status say what was done; the rows say what it is now.
- **Touches:** a new model, `backend/app/main.py` middleware,
  `backend/app/core/security.py`, a new `audit` router, `docs/api.md`,
  `docs/openapi.yaml`.
- **Done when:** a login, a reservation and a refused write each leave one
  record; a GET leaves none; a member gets `403` on `/audit`.

---

## 0.15: Standalone engine

### S-1. `chronos-engine`: one process, no Docker, no Redis

- **Scope:** run the same HTTP API as the container with no Docker and no
  Redis, for a program that embeds Chronos on the same machine.
  `chronos-engine serve --database-url` points it at a local PostgreSQL, whose
  schema is built from the models, exclusion constraints included. Without a
  URL it uses a SQLite file for trials and tests: WAL mode with every
  transaction opened by `BEGIN IMMEDIATE` (standing in for row locks and the
  exclusion constraint), the WAL folded into the file on a clean stop, and
  `chronos-engine backup`. Rate limits and the replay cache live in memory.
- **Touches:** `backend/app/standalone.py`, `backend/app/core/database.py`,
  `backend/app/core/redis_client.py`, `backend/app/core/schema.py`,
  `backend/app/main.py`, `backend/pyproject.toml`, `docs/standalone.md`.
- **Done when:** 40 concurrent overlapping bookings give one `201` and 39
  `409`; an installed wheel starts on a fresh folder. Shipped in 0.15.0.

### S-2. CI upgrades a SQLite file (dropped)

- **Scope:** a CI job builds a standalone file with the previous tag's wheel,
  then starts the current code on it, so a migration that only works on
  PostgreSQL fails the build instead of a user's upgrade.
- **Status:** dropped. There are no migrations before the first real
  deployment: the models are the schema, and a release does not upgrade the
  database the one before it made, so there is no upgrade to test. Comes
  back with the migrations.

### S-3. The PostgreSQL tests run in CI

- **Scope:** the main suite runs on in-memory SQLite, so the tests that prove
  the no-overlap guarantees (the `*_pg.py` files: exclusion constraints, one
  ledger day per slot, booking races) skipped in CI.
  A job now starts PostgreSQL 17, the version the compose files run, and runs
  each of those files against an empty database of its own.
- **Touches:** `.github/workflows/ci.yml`.
- **Done when:** the job is green and none of those tests skip.
- **Status:** shipped in 0.15.0.

### S-4. The integrated flavour: `chronos-engine embedded`

- **Scope:** Chronos as a hidden child process of a host program, which
  starts it, reads one ready line from stdout for the port, and talks to it
  over loopback with a shared secret and the caller's identity in headers
  (`Authorization: Host`, `X-Chronos-Actor`, `X-Chronos-Actor-Role`). No
  Chronos logins: the routes for sessions, passwords, API keys, feed tokens
  and federation are not mounted, and accounts are made as the host asserts
  them. On the host's PostgreSQL, Chronos keeps to one schema of its own
  (`--schema`), so the host's tables are never touched. The process exits
  when the host does (stdin EOF, or `--parent-pid`). `serve` and the
  container are unchanged.
- **Touches:** `backend/app/embedded.py`, `backend/app/core/host_identity.py`,
  `backend/app/core/database.py`, `backend/app/standalone.py`,
  `docs/embedded.md`.
- **Done when:** the SQLite tests cover the secret, the actor mapping and
  the stripped routes; `tests/test_embedded_pg.py` proves that every table
  and constraint lands in the named schema next to a host table of the same
  name. Shipped in 0.15.0.

---

## 0.16: Engine, part 1

0.16 also carries the integration contract (C-1, C-2, C-3, C-5, C-6) and the
integration features (W-1 to W-3), described further down. The order of work
is C-1 first, then C-2, C-3, E-2 and E-3, then the W items, then E-1, and the
Go and Rust SDKs once the spec has settled.

Background: a schedule in Chronos is a set of intervals on resources. Today a
resource is a room or a person and every booking takes the whole resource.
This release lets a resource be consumed in three ways.

### E-1. Resource modes and requirements

- **Scope:** `resource.mode` is one of:
  - `EXCLUSIVE`: one holder at a time (a room, a surgeon).
  - `POOLED`: capacity N, a booking takes k (40 seats, 12 ventilators).
  - `SHARED`: presence is recorded but never contended (a ward during rounds).

  A new `resource_requirement` table says what an activity or reservation
  needs: resource or resource type, quantity, mode. Existing rooms migrate to
  `EXCLUSIVE`, and `target_room_identifier` becomes a foreign key to `resource`.
- **API:** `POST/PATCH /resources` accept `mode` and `capacity`; reservations
  accept `quantity` for pooled resources. Additive: omitted means today's
  behavior.
- **Enforcement:** the database constraint keeps covering exclusive against
  exclusive. Pooled capacity is checked in the transaction under a row lock on
  the resource. Shared is never refused.
- **Done when:** booking 13 of 12 ventilators is refused with a conflict body;
  two shared bookings at once both succeed; every existing test passes unchanged.

### E-2. Conflict report

- **Scope:** `GET /schedule/conflicts?from=&to=` sweeps intervals per resource
  and returns overlaps for every mode, plus members enrolled in two activities
  at the same time. It reports and never refuses.
- **Done when:** a seeded clash of each kind appears exactly once in the report.

### E-3. Rolling materialization horizon

- **Scope:** the nightly job keeps `LEDGER_HORIZON_DAYS` (default 28) of future
  days materialized instead of only tomorrow. A newly imported cycle is filled
  immediately rather than at 23:00.
- **Done when:** after import, the calendar feed shows the next four weeks; running the job twice creates no duplicates.

### E-8. Leave ranges (shipped in 0.14)

- **Scope:** an absence request takes an optional `end_date` beside
  `target_absence_date`. Approving it marks the requester's ledger rows
  `ON_LEAVE` on every day in the range, and reversing it restores them. A
  request without `end_date` behaves as today.
- **Touches:** `ReverseRsvpLog` model, the absence schema,
  `backend/app/services/reverse_rsvp.py`, `docs/api.md`, `docs/openapi.yaml`.
- **Done when:** approving a three-day request marks three days of rows and
  reversing it restores them; single-day requests pass their existing tests.
- **Status:** shipped ahead of plan.

### E-4. Go and Rust SDKs, Helm chart, deb/rpm

See [sdks.md](sdks.md) and [distribution.md](distribution.md). The Go and Rust
SDKs move up in priority: an integrator's planned rewrite is in Go or Rust, and
these SDKs are how it will call Chronos.
They follow the same rules as the other two: generated from the spec, checked
in CI against it, versioned with the server's tags.

---

## 0.17: Engine, part 2 (breaking)

C-4, uniqueness scoped to an organization, is breaking too and ships in this
release; it is described with the integration contract below.

### E-5. Recurrence rules

- **Scope:** a slot carries an RFC 5545 `rrule` and a `dtstart` in the
  organization's timezone, replacing `day_of_week_index`. Existing slots
  migrate to `FREQ=WEEKLY;BYDAY=..`. Expansion uses `dateutil.rrule` and is
  DST-correct: a weekly 09:00 stays 09:00 local time all year.
- **API:** slots return `rrule` and `dtstart`. `day_of_week_index` is still
  returned, derived, through 0.17, and removed after.
- **Done when:** a weekly slot across a DST change materializes at the same
  local time on both sides; migrated slots materialize the same days as before.

### E-6. Editable timetable

- **Scope:** CSV re-import updates matching slots in place instead of skipping
  them, removes slots that are gone, and drops enrollments that are gone.
  Regeneration touches only future ledger rows with no attendance, substitution
  or verification data, and reports the rows it left alone.
- **Done when:** changing a room in the CSV and re-importing changes the room
  on future days; a day with recorded attendance is left as it was and listed
  in the import report.

### E-7. Exclusion on materialized instances

- **Scope:** once rules can collide on dates a weekly key cannot see, the
  no-overlap guarantee moves entirely to materialized instances, and
  template-level checks expand rules in the application before saving.
- **Done when:** two rules that only collide on one date in the horizon are refused at save time and cannot be forced in through the ledger.

---

## Integration contract (approved)

The HTTP contract is what integrators build against, from any language, so
it has to be predictable enough to code against without reading Chronos
source, and it has to behave well when a network, a database or the caller
fails halfway. Approved on 2026-10-13. C-1, C-2, C-3, C-5 and C-6 ship in
0.16, with C-1 first because the others report their failures through its
codes. C-4 is breaking and ships with 0.17.

### C-1. A stable error code on every error

- **Scope:** every error body gains a machine `code` (`RESOURCE_CONFLICT`,
  `IDEMPOTENCY_KEY_REUSED`, `SCOPE_MISSING`, `NOT_FOUND`, ...) beside the
  human `detail`, which stays. Codes are listed in `docs/openapi.yaml` as an
  enum and never renamed; a new failure gets a new code. The 409 conflict body
  keeps its `conflicts` list.
- **Touches:** a small error type and handler in `backend/app/main.py`, the
  `HTTPException` raises in `backend/app/api/v1/endpoints/`, `docs/api.md`,
  `docs/openapi.yaml`, the SDKs' error types.
- **Done when:** a test walks every route's documented errors and finds a
  listed code on each; the contract check fails on an unlisted code.
- **Breaking:** no; `detail` is unchanged.

### C-2. Idempotency-Key on every write

- **Scope:** today only reservation create takes `Idempotency-Key`. Every
  `POST`, `PATCH` and `DELETE` accepts it. A new table keeps, per API key or
  user, the key, a hash of the request, the status and the stored response,
  for a retention window (24 hours by default). A repeat with the same body
  returns the stored response; the same key with a different body is a 422
  with `IDEMPOTENCY_KEY_REUSED`. Two concurrent first uses are settled by the
  table's unique constraint. Reservation create keeps its current behaviour
  and moves onto the shared mechanism; its key, globally unique today,
  becomes unique per caller.
- **Touches:** a model, a new
  `backend/app/core/idempotency.py` dependency applied to write routes,
  `backend/app/api/v1/endpoints/resources.py`, a cleanup in the nightly job.
- **Done when:** retrying any write after a dropped response neither
  duplicates nor fails; a concurrent double submit gives one effect.

### C-3. Export and import

- **Scope:** a versioned, documented archive of an organization's data
  (units, people, resources, cycles, slots, enrollments, ledger, reservations,
  holds, absences, audit) as JSON Lines with a manifest carrying the format
  version and the schema version. `GET /api/v1/admin/export` and
  `chronos-engine export`; `chronos-engine import` into an empty database.
  Secrets (password hashes, API key hashes, the signing key) are left out
  unless asked for. The same archive moves data between SQLite and
  PostgreSQL.
- **Touches:** a new `backend/app/services/portability.py`, an admin route,
  `backend/app/standalone.py`, a doc page for the format.
- **Done when:** export, import into an empty PostgreSQL, export again gives
  the same archive; an archive from an older format version imports or is
  refused with a clear message.

### C-4. Uniqueness scoped to an organization

- **Scope:** today one deployment serves one hospital: there is no
  organization record, and some keys are unique across the whole database
  (`Resource.code` is the main one). Before 1.0, an organization table is
  added, existing data migrates into one default organization, every such key
  becomes unique per organization, and every query is filtered by the
  caller's organization, so several hospitals can share one deployment
  without colliding.
- **Touches:** a new model, an `organization_id` on the
  scoped tables and in each affected constraint (the exclusion constraints
  included), `backend/app/core/security.py` to carry the caller's
  organization, the query helpers that load by code.
- **Done when:** two organizations can each create room `101` and book it at
  the same time; neither can read or book the other's.
- **Breaking:** for anyone relying on a code being unique across
  organizations.

### C-5. Retries in the SDKs

- **Scope:** every SDK retries a request that failed before a response
  arrived, or got a 429, 502, 503 or 504, with exponential backoff and full
  jitter, honouring `Retry-After`. Reads retry freely. A write retries only
  when it carries an `Idempotency-Key` (C-2), and the SDK generates one for
  every write unless the caller passes their own. Attempts, the base delay and
  the overall deadline are settings with safe defaults.
- **Done when:** a test server that drops the first response and answers the
  second sees one effect for a create through each SDK; a 400 is never
  retried.
- **Status:** shipped in 0.16.

### C-6. Failure modes written down

- **Scope:** a page that says what an integrator sees when each part fails:
  PostgreSQL down or restarting, Redis down, the embedded child process
  killed, a host clock that goes backwards, a request that times out after the
  commit. Each case names the status, the error code (C-1) and whether a retry
  is safe. Anything found that behaves worse than the page says is fixed in
  the same release.
- **Done when:** each case on the page has a test or a CI job that produces
  it.

---

## Host clock

A simulation host that embeds the engine can run it on a clock of its own.
`CLOCK_MODE=host` freezes the application's time at `CLOCK_START`, the
nightly jobs run as the host advances the clock rather than on a schedule,
and `ID_SEED` makes the non-secret identifiers repeat, so the same script
writes the same rows twice. Nothing changes for a deployment on the default
system clock. The design, the real-time exceptions and the limits of the
guarantee are in [clock.md](clock.md). A host program in a separate process
drives it through the embedded flavour (S-4): `chronos-engine embedded
--clock-start` starts the process on a host clock, `--id-seed` seeds the
ids, and `POST /api/v1/clock/advance`, open to the host's own actor
`system` alone, moves it. The host owns time across restarts by passing the
saved instant back as `--clock-start`. Neither route exists in `serve` or the
container ([embedded.md](embedded.md)).

## Integration features (approved, 0.16)

Requested for integrations and approved on 2026-10-13. They build on C-1 and
C-2, so they start once those are in.

### W-1. Webhooks

- **Scope:** an admin subscribes a URL to event types
  (`reservation.created`, `reservation.updated`, `resource.updated`,
  `ledger.updated`, ...). Events come from the change feed markers, which are
  written in the same transaction as the change, so a rolled-back change never
  sends an event and a committed one is never lost if the process dies before
  delivery. A delivery worker posts each event with:
  - a signature over the event id, the timestamp and the body (HMAC-SHA256,
    in the shape of the Standard Webhooks headers), so the receiver can check
    it came from Chronos and reject a replay older than five minutes;
  - up to two active secrets per subscription, so a secret can be rotated
    without dropping deliveries;
  - a short timeout, no redirects followed, and retries with exponential
    backoff and jitter for about a day, after which the delivery is marked
    failed and a subscription that keeps failing is paused;
  - a delivery log (attempts, status, response time) and a redeliver call.
- **Security:** targets must be HTTPS unless an admin allows plain HTTP for
  named hosts. Loopback, private and link-local addresses are refused unless
  allowed by a setting, which a sibling container on a private network needs.
  The address is checked after DNS resolution, so a name cannot point a
  delivery at an internal service. Payloads carry ids and the changed fields,
  never secrets.
- **Done when:** a receiver that is down for an hour gets every event once it
  is back, in order per entity, each with a valid signature; a subscription to
  a loopback URL is refused without the setting.

### W-2. Activities CRUD

- **Scope:** create, edit and retire activities, their slots and their
  enrollments through the API instead of only through CSV import. Retiring
  keeps history: past ledger rows stay, future rows without attendance are
  removed. Each write takes an `Idempotency-Key` and reports failures with
  C-1 codes.
- **Done when:** an activity created through the API materializes the same
  ledger rows as the same activity imported from CSV.

### W-3. Reservation external reference

- **Scope:** an optional `external_ref` on a reservation, unique per caller,
  so an integrator can find and update a booking by its own identifier.
  `GET /reservations?external_ref=` finds it; creating a second reservation
  with the same reference is a 409 with its own code and the existing id.
- **Done when:** an integrator can create, find, update and cancel a booking
  using only its own reference.

## Later

A constraint solver as an optional extra (`chronos-ledger[solver]`, CP-SAT)
that proposes timetables rather than only checking them; repair of an existing
timetable after a change; precedence and changeover time for ordered lists
such as operating theatres.
