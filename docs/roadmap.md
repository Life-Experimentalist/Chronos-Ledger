# Roadmap

<!-- Copyright 2026 Chronos Ledger Contributors (Apache 2.0) -->

Current release: 0.12. This page plans the next three minor releases. The
plan is detailed on purpose: each item has a scope, the files it touches and
a check that says when it is done, so it can be picked up without
re-deciding anything.

Chronos Ledger stays on `0.x` until the scheduling API has stopped changing.
Several items below change the API (recurrence rules, the resource
requirement model, the login field), and those are the reason `1.0` waits.

## At a glance

| Release | Theme | Breaking |
|---|---|---|
| 0.13 | Platform: contract check, hardening, `chronos` CLI and channels, first SDKs, ledger range queries, audit log | No |
| 0.14 | Engine, part 1: resource modes, conflict report, rolling horizon, leave ranges, Go and Rust SDKs, Helm | Additive |
| 0.15 | Engine, part 2: recurrence rules, editable timetable, exclusion on instances | Yes |
| Waiting on a decision | Webhooks, activities CRUD | n/a |

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

### P-2. Health reports version and migration revision

- **Scope:** `/health` returns `version` and `migration_revision`. The backend
  refuses to start, with one clear message, when the database revision is
  newer than the code knows.
- **Touches:** `backend/app/main.py`, `backend/Dockerfile` start command.
- **Done when:** a test starting against a database stamped with an unknown
  revision exits non-zero with that message instead of retrying.

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
  schema uses, and keeps accepting `email` as a deprecated alias through 0.14.
  `email` is removed in 0.15.
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

See [sdks.md](sdks.md). Depends on P-1.

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
  through the records, newest first, `SUPER_ADMIN` only; API keys need
  `audit:read`.
- **Not in scope:** before and after snapshots of the changed rows. The path
  and status say what was done; the rows say what it is now.
- **Touches:** a new model and migration, `backend/app/main.py` middleware,
  `backend/app/core/security.py`, a new `audit` router, `docs/api.md`,
  `docs/openapi.yaml`.
- **Done when:** a login, a reservation and a refused write each leave one
  record; a GET leaves none; a member gets `403` on `/audit`.

---

## 0.14: Engine, part 1

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

### E-8. Leave ranges

- **Scope:** an absence request takes an optional `end_date` beside
  `target_absence_date`. Approving it marks the requester's ledger rows
  `ON_LEAVE` on every day in the range, and reversing it restores them. A
  request without `end_date` behaves as today.
- **Touches:** `ReverseRsvpLog` model and a migration, the absence schema,
  `backend/app/services/reverse_rsvp.py`, `docs/api.md`, `docs/openapi.yaml`.
- **Done when:** approving a three-day request marks three days of rows and
  reversing it restores them; single-day requests pass their existing tests.

### E-4. Go and Rust SDKs, Helm chart, deb/rpm

See [sdks.md](sdks.md) and [distribution.md](distribution.md).

---

## 0.15: Engine, part 2 (breaking)

### E-5. Recurrence rules

- **Scope:** a slot carries an RFC 5545 `rrule` and a `dtstart` in the
  organization's timezone, replacing `day_of_week_index`. Existing slots
  migrate to `FREQ=WEEKLY;BYDAY=..`. Expansion uses `dateutil.rrule` and is
  DST-correct: a weekly 09:00 stays 09:00 local time all year.
- **API:** slots return `rrule` and `dtstart`. `day_of_week_index` is still
  returned, derived, through 0.15, and removed after.
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

## Waiting on a decision

These were requested for integrations. They are designed enough to estimate
but are not scheduled until the maintainer decides on them; an integrator that
needs one should say so.

| Item | Sketch |
|---|---|
| Webhooks | Subscriptions per event type (`reservation.created`, `ledger.updated`, ...), HMAC-signed bodies, retries with backoff, delivery log |
| Activities CRUD | Create, edit and retire activities through the API instead of only through CSV import |

## Later

A constraint solver as an optional extra (`chronos-ledger[solver]`, CP-SAT)
that proposes timetables rather than only checking them; repair of an existing
timetable after a change; precedence and changeover time for ordered lists
such as operating theatres.
