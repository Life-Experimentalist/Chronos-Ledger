# Failure modes

What an integrator sees when something underneath Chronos fails, whether a
retry is safe, and what the operator does about it. Every case names the
test that holds it, so a change that alters the behaviour fails a test
before it changes this page.

Error bodies are `{"detail", "code"}` throughout ([Errors](api.md#errors)).
Branch on `code`, not on `detail`. Retrying means sending the same request
again, with the same `Idempotency-Key` when it is a write
([Idempotency](api.md#idempotency)).

The Python and TypeScript SDKs do the safe retries on their own: a request
that got no response, a `429`, `502`, `503` or `504`, and a `409
IDEMPOTENCY_KEY_IN_PROGRESS` are retried with the same key, honouring
`Retry-After`, until the SDK's deadline ([Python SDK](sdks/python.md)).

Tests are under `backend/tests/`. Files ending in `_pg.py` run against
PostgreSQL 17 in CI and skip without `TEST_DATABASE_URL`.

| Case | Status and code | Retry |
|---|---|---|
| [PostgreSQL down](#1-postgresql-down-or-restarting) | `503 DATABASE_UNAVAILABLE` | Safe, after `Retry-After` |
| [PostgreSQL restarting mid-request](#1-postgresql-down-or-restarting) | `503 DATABASE_UNAVAILABLE` | Safe with the same key |
| [Redis down](#2-redis-down-container-flavour) | Nothing, except federated sign-in: `503 FEDERATION_UNAVAILABLE` | Safe |
| [Embedded process killed](#3-the-embedded-process-killed-or-crashing) | Connection refused or reset | Safe with the same key, after a restart |
| [Clock goes backwards](#4-a-clock-that-goes-backwards) | Host clock: `422 INVALID_VALUE`. System clock: nothing | Not a retry case |
| [Response lost after commit](#5-the-client-timed-out-after-the-server-committed) | The first response, replayed | Safe with the same key |
| [Two first uses of one key](#6-two-requests-with-one-key) | `409 IDEMPOTENCY_KEY_IN_PROGRESS` | Safe, after `Retry-After` |
| [One key, a different body](#6-two-requests-with-one-key) | `422 IDEMPOTENCY_KEY_REUSED` | Never: use a fresh key |
| [Two overlapping bookings at once](#7-two-overlapping-bookings-at-once) | One `201`, one `409 RESOURCE_CONFLICT` | Not the same request; pick another window |
| [Rate limit](#8-rate-limit) | `429 RATE_LIMITED` | After `Retry-After` |

## 1. PostgreSQL down, or restarting

**PostgreSQL unreachable.** A request that needs the database gets:

```http
HTTP/1.1 503 Service Unavailable
Retry-After: 1

{"detail": "Database unavailable, try again shortly.", "code": "DATABASE_UNAVAILABLE"}
```

The driver's own message, which can name the database host, goes to the
server log and not to the caller. A request that never touches the database
(an expired token, a malformed body) is answered as usual.

`GET /health` answers `200` throughout: it touches nothing, so the process is
alive. `GET /health/ready` answers `503` with
`{"status": "not ready", "database": "unavailable", "redis": ...}`. That body
has no `code`; it is the one documented response that is not an error body.

**PostgreSQL restarting, or failing over, mid-request.** The connection under
a request is dropped inside its transaction. The request gets the same `503
DATABASE_UNAVAILABLE`, and nothing it wrote is kept: the claim on its
`Idempotency-Key` is in the same transaction as its changes, so both go.

**Retry.** Safe. The retry with the same key runs as a first use and does the
work once. Without a key a read is safe; a write is safe too, since nothing
was committed, except in the window below.

One narrow window remains. If the connection drops while `COMMIT` itself is
in flight and PostgreSQL did commit, the caller still gets the `503`, and the
server lets go of the key because the response was a 5xx. A retry under the
same key then runs again. For a create with a natural unique field (a
resource `code`, a reservation `external_ref`) the second run is refused as
a duplicate, which tells the caller the first one landed. Otherwise read
the record back before writing again.

**Operator.** Bring PostgreSQL back; nothing in Chronos needs a restart. The
engine checks each pooled connection before use (`pool_pre_ping`), so stale
connections are replaced on the next request. While it is down, a load
balancer reading `/health/ready` takes the instance out of rotation, and an
orchestrator reading `/health` does not restart it for no gain.

A related answer, not an outage: when every pooled connection is in use for
10 seconds, the request gets `503 SERVER_BUSY` with `Retry-After: 1`. That
is load, and the fix is capacity, not PostgreSQL.

On SQLite (standalone and embedded) the same `503 DATABASE_UNAVAILABLE`
answers a database file that cannot be opened, or a write that waited past
the busy timeout for another writer. Nothing was committed, and the retry
is safe.

Tests:
- `test_failure_modes.py::test_a_database_that_cannot_be_reached_is_a_503_with_a_code`
- `test_failure_modes.py::test_a_connection_dropped_mid_transaction_commits_nothing`
- `test_failure_modes_pg.py::test_a_backend_terminated_mid_transaction_is_a_503_and_commits_nothing`
  (PostgreSQL ends the request's backend with `pg_terminate_backend`)
- `test_readiness.py::test_postgres_down_is_not_ready`
- `test_readiness.py::test_liveness_answers_with_postgres_and_redis_down`
- `test_concurrency_gate.py::test_request_past_the_cap_gets_503_and_health_still_answers`

## 2. Redis down (container flavour)

Redis is a cache in Chronos, not a system of record. Standalone and embedded
keep it in the process (`REDIS_URL=memory://`), so this case is the container
flavour's only. Each call to Redis gives up in about two seconds (1 second
timeouts and a short retry), and the caller falls back:

| What uses Redis | With Redis down |
|---|---|
| Rate limits | Stop applying. Requests are let through, not refused. |
| Federated sign-in replay cache | Fails closed: `POST /auth/federated` answers `503 FEDERATION_UNAVAILABLE`, since a copied note cannot be ruled out. Password sign-in is unaffected. |
| Location override cache | Skipped; the other tiers answer. |
| WebSocket relay | Each instance still reaches its own sockets; sockets on other instances miss its events until Redis is back. The online count is this instance's own. |

What keeps working: everything else, including every write and every
`Idempotency-Key` replay. Idempotency records live in the database, not in
Redis, so a lost response is still answered from its key.

`GET /health` is `200`. `GET /health/ready` stays `200` and reports
`"redis": "unavailable"`, on purpose: taking a degraded instance out of
rotation would turn it into a missing one.

**Retry.** Nothing new to retry, except federated sign-in, which is safe to
retry once Redis is back.

**Operator.** Bring Redis back. The relay reconnects on its own. Watch the
`redis` field of `/health/ready`, not its status code.

Tests:
- `test_rate_limit.py::test_redis_being_down_does_not_stop_anyone_signing_in`
- `test_federated_identity.py::test_an_unreachable_replay_cache_gets_a_503_and_not_a_sign_in`
- `test_location_resolver.py::test_the_other_tiers_answer_when_redis_is_down`
- `test_websocket_relay.py::test_a_failed_publish_still_reaches_the_sockets_here`
- `test_websocket_relay.py::test_without_the_relay_the_count_is_this_instances_own`
- `test_websocket_relay.py::test_the_relay_comes_back_when_redis_does`
- `test_readiness.py::test_redis_down_is_reported_and_still_ready`

## 3. The embedded process killed or crashing

The engine stops cleanly when stdin closes, when `--parent-pid` is gone, or
on SIGTERM ([Lifecycle](embedded.md#lifecycle)). This case is the other kind:
the process killed outright, or dying.

**What the host sees.** Requests in flight fail with a connection reset, new
ones with connection refused, and stdout reaches end of file. There is no
HTTP status to read.

**What was committed.** Every transaction that committed before the process
died is kept, on SQLite and on PostgreSQL; one that had not committed is
rolled back. SQLite replays its write-ahead log on the next open, so
nothing needs repairing by hand.

**Restart.** Start a new process the way the first one was started, with a
fresh secret, and wait for its ready line. It gets a new port when started
with `--port 0`. Then retry what was in flight, with the same keys:

- A write that committed and whose response was recorded is replayed.
- A write that never committed runs.
- A write that committed in the instant before the process died, before its
  response was recorded, answers `409 IDEMPOTENCY_KEY_IN_PROGRESS` with
  `Retry-After: 1`, and keeps answering it until the key expires
  (`IDEMPOTENCY_RETENTION_HOURS`, 24 by default). The work was done; read
  the record (for example by `external_ref`) to find it. This errs towards
  no duplicate, and is the gap [Idempotency](api.md#idempotency) describes.
  An SDK retries this `409` until its deadline and then raises it.

On a host clock, pass `--clock-start` again: the engine does not remember
where the clock stood ([embedded.md](embedded.md#the-clock)).

**Operator.** The host is the operator here. It restarts the child; nothing
else is needed.

Tests:
- `test_failure_modes.py::test_an_embedded_process_killed_and_restarted_keeps_what_it_committed`
  (a real child process, killed and started again on the same data directory)
- `test_failure_modes.py::test_a_write_committed_just_before_the_process_died_answers_409`
- `test_embedded.py::test_stdin_closing_stops_the_server`
- `test_embedded.py::test_the_parent_going_away_stops_the_server`

## 4. A clock that goes backwards

See [clock.md](clock.md) for the two clocks.

**Host clock (embedded, `--clock-start`).** It refuses to go backwards.
`POST /api/v1/clock/advance` to an earlier instant answers:

```json
{"detail": "The clock does not go backwards: it reads 2026-09-07T02:30:00+00:00", "code": "INVALID_VALUE"}
```

with status `422`, and the clock is unchanged. Not a retry case: the host
asked for something the clock does not do. To replay a day, start a fresh
process with an earlier `--clock-start`. Nothing stops a restart from using
an earlier start than the last one; the consequences are those of the system
clock below.

**System clock (every other flavour).** Nothing guards it: an NTP step or a
hand-set clock moves Chronos with it, and no request fails. What changes:

- New rows are stamped earlier than rows written before the step, so
  timestamps are out of order for that stretch.
- Every expiry measured from the clock (refresh tokens, API keys, visit
  codes, `Idempotency-Key` retention) is pushed later by the size of the
  step. An `Idempotency-Key` is never forgotten early, so a replay is not
  lost.
- The change feed's cursor is a sequence number, not a time, so a step does
  not hide a change from a reader.
- Access tokens and federated notes are checked against real time
  (`clock.wall_now()`), as they are under a host clock.

**Operator.** Keep the host on NTP with slewing rather than stepping. After a
large step back, expect out-of-order timestamps for that period; there is
nothing to repair.

Tests:
- `test_embedded_clock.py::test_the_clock_does_not_go_backwards`
- `test_clock.py::test_a_host_clock_refuses_to_go_backwards`
- `test_failure_modes.py::test_a_system_clock_set_back_loses_no_replay_and_refuses_nothing`

## 5. The client timed out after the server committed

The request ran and committed, and the response was lost: a client timeout,
a proxy reset, a dropped mobile connection. The client cannot tell whether
it happened.

**Retry.** With the same `Idempotency-Key` and the same request: the first
response comes back, status and body, with `Idempotency-Replayed: true`, and
nothing runs a second time. Without a key a retried create can make a second
record; send a key on every write that matters.

If the retry arrives while the first is still running, it gets case 6's
`409 IDEMPOTENCY_KEY_IN_PROGRESS`; wait `Retry-After` and send it again.

**Operator.** Nothing.

Tests:
- `test_idempotency.py::test_a_retried_post_gets_the_first_response_and_makes_one_room`
- `test_idempotency.py::test_a_server_error_is_not_kept_and_the_retry_runs`

## 6. Two requests with one key

**Two first uses at once.** Two copies of one request, same key, arrive
together. The unique constraint on (caller, key) lets one claim the key. The
other either waits and gets the replay, or gets:

```http
HTTP/1.1 409 Conflict
Retry-After: 1

{"detail": "a request with that Idempotency-Key is still running, retry shortly", "code": "IDEMPOTENCY_KEY_IN_PROGRESS"}
```

The work happens once either way. **Retry:** safe, after `Retry-After`.

**One key, a different request.** A key already used for a different method,
path, query string or body answers `422` with `IDEMPOTENCY_KEY_REUSED`.
Nothing runs and nothing is stored. **Retry:** never with that key; it is a
bug in the client. Use a fresh key per operation.

Before 0.16 every route except reservation create sent `409` here.

**Operator.** Nothing.

Tests:
- `test_idempotency.py::test_two_copies_at_once_make_one_room`
- `test_idempotency.py::test_a_retry_while_the_first_is_still_running_is_409`
- `test_idempotency.py::test_the_same_key_for_a_different_request_is_422`
- `test_reservations.py::test_the_same_key_for_a_different_request_is_refused`

## 7. Two overlapping bookings at once

Two holds on one resource, for windows that overlap, arrive together. One
gets `201`. The other gets `409`:

```json
{
  "detail": {
    "message": "the resource is already taken for part of that window",
    "conflicts": [{"date": "2026-01-06", "start": "14:30:00", "end_date": "2026-01-06", "end": "15:30:00", "activity_id": null, "activity_code": null, "master_slot_id": null, "reservation_id": 28}]
  },
  "code": "RESOURCE_CONFLICT"
}
```

`detail.conflicts` names what won. On PostgreSQL the exclusion constraint
`ex_reservations_no_overlap` decides the race when both requests passed the
application's check; the loser is told what beat it, not a bare database
error. On SQLite the write lock lets one request through at a time, so the
second sees the first in the check itself.

**Retry.** Not the same request: the same request gets the same `409`. Pick
another window or another resource.

**Operator.** Nothing.

Tests:
- `test_reservation_overlap_pg.py::test_the_database_refuses_an_overlap_the_endpoint_did_not_see`
  (the loser of the race on PostgreSQL)
- `test_reservations.py::test_two_holds_on_the_same_hour_is_409`
- `test_reservations.py::test_the_conflict_says_what_it_ran_into`

## 8. Rate limit

Sign-in failures, kiosk check-ins and calendar feed fetches carry a budget
([Rate limits](api.md#rate-limits)). Past it:

```http
HTTP/1.1 429 Too Many Requests
Retry-After: 840

{"detail": "Too many sign-in attempts from this address. Try again in 840 seconds.", "code": "RATE_LIMITED"}
```

A `429` is never stored against an `Idempotency-Key`, so the retry runs.

**Retry.** After `Retry-After` seconds, not before.

**Operator.** The budgets are the `RATE_LIMIT_*` settings. With Redis down
they stop applying (case 2).

Tests:
- `test_rate_limit.py::test_the_attempt_past_the_budget_is_refused`

---

Webhook delivery failures are documented with webhooks, in [webhooks.md](webhooks.md).
