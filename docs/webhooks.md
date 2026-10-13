# Webhooks

<!-- Copyright 2026 Chronos Ledger Contributors (Apache 2.0) -->

A webhook subscription tells another system about changes to the rooms and
the bookings as they happen, instead of that system polling the change feed
([api.md](api.md#changes)). Chronos Ledger POSTs a signed JSON body to the
subscription's URL for each change, retries when the receiver is down, and
keeps a record of every attempt.

Webhooks are made from the change feed and from nothing else, so they need
`CHANGE_FEED_ENABLED=true`. While the feed is off, creating a subscription
answers `503` with `CHANGE_FEED_DISABLED`, nothing is fanned out, and the
worker does not run, so deliveries already queued wait until the feed is on
again.

The routes are under `/api/v1/webhooks` and need `ORG_ADMIN`, for the reason
the change feed does: a booking carries what it is for, and a webhook hands
it to somewhere outside. An API key needs `webhooks:read` or
`webhooks:write`. The operations are in [openapi.yaml](openapi.yaml) under
the Webhooks tag.

## Events

| Type | Sent when |
|---|---|
| `resource.created` | A room, or a person bookable as a resource, is created. |
| `resource.updated` | One is edited or deactivated. |
| `reservation.created` | A booking is held. |
| `reservation.updated` | A booking changes, including when it is cancelled. |

Each change feed marker is one event. A row edited three times is three
events, unlike a feed poll, which collapses them into one entry. There is no
`deleted`, because nothing the feed carries is deleted.

A subscription names the types it wants. It starts at the newest marker when
it is created, so it hears about what happens from then on and never about
history: read the rooms and the bookings in full once, then let the webhooks
keep the copy current.

Changes to the daily ledger are not sent. The ledger has no change markers
yet, and adding them is a separate piece of work on the roadmap. Until then
a consumer that needs the ledger reads it.

## The body

The Standard Webhooks envelope:

```json
{
  "type": "resource.updated",
  "timestamp": "2026-01-06T08:31:02.114000Z",
  "data": {
    "marker_id": 4193,
    "entity_kind": "resource",
    "entity_id": 12,
    "change_kind": "updated",
    "at": "2026-01-06T08:31:02.114000Z",
    "resource": {
      "id": 12,
      "code": "LH-3",
      "label": "Living Room",
      "resource_type": "ROOM",
      "unit_code": null,
      "capacity": 90,
      "user_id": null,
      "latitude": 12.9716,
      "longitude": 77.5946,
      "altitude_target": 920.0,
      "active": true
    }
  }
}
```

`timestamp` and `data.at` are when the change was made. `data.marker_id` is
the change feed cursor of that change. `data.resource` or
`data.reservation`, whichever `entity_kind` names, is the row in the same
shape `GET /changes/` gives it.

The body is built when the change is fanned out, which is within a few
seconds of the change, and stored. Every retry sends the same bytes. So
`data` is the row as it stood at fan-out, which can already be newer than
the change that produced the event, and a delivery retried for a day still
carries the row as it was a day ago. The change feed is the source of
truth: a receiver that needs to be sure of a row's current state reads it,
or polls the feed from `marker_id`.

No secret is ever in the body. It holds what the change feed holds, and the
change feed holds no secrets.

## Signing

Every request carries three headers, as Standard Webhooks defines them:

| Header | Value |
|---|---|
| `webhook-id` | The event's id, such as `msg_6f1c...`. The same on every retry and on a redelivery, so it is what a receiver deduplicates on. |
| `webhook-timestamp` | When this attempt was sent, in whole seconds since 1970 UTC. New on every attempt. |
| `webhook-signature` | `v1,` and the base64 of the HMAC-SHA256 of `{webhook-id}.{webhook-timestamp}.{body}`, keyed with the secret. Two of them, separated by a space, while a rotation is under way. |

The secret is `whsec_` and the base64 of 32 random bytes. The key is those
32 bytes, not the text. It is shown once, in the answer to create or to
rotate, and cannot be read back.

A receiver checks a request like this. It recomputes the signature from the
raw body, before parsing it, with every secret it currently holds, accepts
the request if any signature in the header matches any of them, and refuses
a timestamp more than five minutes from its own clock, so that a captured
request cannot be replayed later.

```python
import base64
import hashlib
import hmac
import time

TOLERANCE_SECONDS = 5 * 60


def verify(secrets: list[str], headers: dict[str, str], body: bytes) -> bool:
    """True if the request was signed by one of the secrets, recently."""
    event_id = headers["webhook-id"]
    timestamp = headers["webhook-timestamp"]
    if abs(time.time() - int(timestamp)) > TOLERANCE_SECONDS:
        return False
    signed = f"{event_id}.{timestamp}.".encode() + body
    expected = []
    for secret in secrets:
        key = base64.b64decode(secret.removeprefix("whsec_"))
        digest = hmac.new(key, signed, hashlib.sha256).digest()
        expected.append(base64.b64encode(digest).decode())
    for candidate in headers["webhook-signature"].split(" "):
        version, _, signature = candidate.partition(",")
        if version != "v1":
            continue
        if any(hmac.compare_digest(signature, e) for e in expected):
            return True
    return False
```

The Standard Webhooks libraries for other languages verify the same
signature.

### Rotating the secret

`POST /webhooks/{subscription_id}/rotate-secret` returns a new secret. The
old one keeps signing alongside it for 24 hours, so each request in that
time carries two signatures and a receiver that holds either secret accepts
it. Give the receiver the new secret, and once it is using it, remove the
old one with `DELETE /webhooks/{subscription_id}/previous-secret` rather than
waiting out the day.

A subscription holds at most two live secrets. Rotating again while the old
one is still live answers `409` with `WEBHOOK_SECRET_LIMIT`; remove the old
one first. A secret that leaked is handled the same way: rotate, then remove
the previous one at once.

## Retries

A `2xx` answer is a success. Anything else is a failed attempt: another
status, a timeout, a connection that failed, and a redirect, which is never
followed. An attempt times out when connecting takes more than 3 seconds,
when the receiver goes 10 seconds without sending anything, or when the
whole attempt, from looking the name up to the last byte of the answer
that is kept, takes more than 15 seconds, however steadily the answer
trickles in.

After a failed attempt the delivery waits and tries again. The waits follow
the Standard Webhooks schedule: up to 5 seconds, 5 minutes, 30 minutes, 2
hours, 5 hours, 10 hours and 10 hours, about 27 hours in all across eight
attempts. Each wait is drawn from zero up to that ceiling (full jitter), so
deliveries that failed together do not all come back together. The draw
comes from a hash of the event id and the attempt number rather than a
random number generator, so a host replaying the same script under a host
clock sees the same retries at the same instants.

After the eighth failed attempt the delivery is `failed` and is not tried
again unless an administrator redelivers it
(`POST /webhooks/{subscription_id}/deliveries/{delivery_id}/redeliver`).
A redelivery sends the same `webhook-id` and the same body, with a new
timestamp and signature, on the worker's next pass, and starts the schedule
over.

Each attempt is recorded with the status code (none if no answer came), how
long it took in milliseconds, a short reason when it failed, and the first
200 characters of the answer. `GET /webhooks/{subscription_id}/deliveries`
lists deliveries newest first, each with its attempts, and pages like the
other lists ([api.md](api.md#paging)).

A receiver should answer quickly and do its work afterwards. A receiver
that keeps the request waiting more than 15 seconds has timed out, and the
delivery is sent again.

An attempt is counted once, by the worker that made it. Each pass leases
what it claims for 60 seconds and starts an attempt only while at least 25
of them are left, so with a slow receiver a pass sends a few deliveries and
leaves the rest for a later pass. If an answer is written down after its
lease ran out and another pass has claimed the delivery since, it is
dropped rather than written over the newer claim, so the receiver may get
that delivery twice (deduplicate on `webhook-id`), but no attempt is
counted twice.

## Ordering

For one subscription, the events about one row are sent in the order the
changes were made. A delivery waits while an earlier delivery for the same
row is still pending, retries included, so a receiver never sees a booking's
cancellation before the booking.

A delivery that has failed for good stops holding the later ones back. They
are sent, and the failed one is not, so the receiver can end up a change
short. It still ends up with the row's latest state, since each body carries
the whole row, unless the failed delivery was the last change to that row.
After a failure, read the row, or redeliver.

Events about different rows are not ordered against each other. A receiver
that is slow for one row does not hold up the others.

The same event can arrive twice, when the receiver handled it but the answer
was lost on the way back. Deduplicate on `webhook-id`.

## Pausing

A subscription is paused when five deliveries in a row have failed for good.
That is more than a day of a receiver answering nothing but errors, which is
a receiver that is gone rather than one having a bad hour. One success
anywhere in between resets the count.

A paused subscription fans out nothing and sends nothing. It keeps its
place in the change feed, and its pending deliveries stay where they are.
`POST /webhooks/{subscription_id}/resume` clears the pause and the count,
and the worker then sends the pending deliveries and fans out every change
made while it was paused, oldest first. Nothing is skipped.

`active: false` on `PATCH /webhooks/{subscription_id}` is the
administrator's own switch and behaves the same way: nothing is fanned out
or sent until it is switched back on, and then what happened in between is
sent.

An import from an archive made without secrets also pauses every
subscription, because each one is given a new secret that no receiver
knows ([portability.md](portability.md)).

## Which URLs are allowed

A webhook URL is an address this server will call, chosen by whoever holds an
administrator account or key. Without limits that is a way to make the
server call into its own network: the metadata service of a cloud host, a
database's HTTP port, an internal admin page. So:

- The URL must be `https`. Plain `http` is refused unless the host is listed
  in `WEBHOOK_ALLOW_HTTP_HOSTS`.
- A URL with a user name or password in it is refused, since it would be
  stored in clear.
- The host name is resolved by Chronos Ledger, and every address it resolves
  to is checked. Loopback, private, link-local, multicast, reserved and
  unspecified addresses are refused, including the IPv4 forms of those
  written as IPv6 (`::ffff:127.0.0.1`). One bad address refuses the whole
  name, because a name with a public and a private address is a name
  somebody can steer.
- The connection goes to the address that passed the check, with the host
  name sent as `Host` and as the TLS server name, so a resolver that answers
  differently a moment later cannot slip another address in.
- Redirects are not followed. A `3xx` answer is a failed attempt.
- Proxy settings in the environment are ignored.

The check runs when a subscription is created, when its URL is changed, and
again before every attempt, because what a name resolves to can change
between the administrator typing it and the hundredth retry. A URL refused
at create or update answers `422` with `WEBHOOK_URL_REFUSED` and a detail
saying why. One refused at send time is a failed attempt, with the reason
recorded.

`WEBHOOK_ALLOW_PRIVATE_TARGETS=true` allows loopback, private and link-local
addresses, for a receiver that really is on the private network. Multicast,
reserved and unspecified addresses stay refused, since no receiver can be at
one.

## Settings

| Setting | Default | Meaning |
|---|---|---|
| `CHANGE_FEED_ENABLED` | `false` | Webhooks need it on. |
| `WEBHOOK_DELIVERY_INTERVAL_SECONDS` | `5` | How often the worker fans out new changes and sends what is due, from 1 to 3600. |
| `WEBHOOK_ALLOW_HTTP_HOSTS` | empty | Host names that may be sent plain `http`, comma separated, matched exactly and without the port. |
| `WEBHOOK_ALLOW_PRIVATE_TARGETS` | `false` | Whether loopback, private and link-local addresses may receive webhooks. |

## How it works

`backend/app/services/webhooks.py` does the work, in passes run by
`backend/app/cron/scheduled.py::deliver_webhooks` every
`WEBHOOK_DELIVERY_INTERVAL_SECONDS`. A pass is `run_pass`:

1. `fan_out` reads, for each active subscription that is not paused, the
   change markers past its `cursor`, makes one delivery for each marker of a
   type it wants, with the body built then, and moves the cursor past them.
   The deliveries and the cursor are written in one transaction, so a crash
   halfway neither loses an event nor makes one twice, and a unique
   constraint on the subscription and the marker holds even if two instances
   race. A change that was rolled back left no marker, so it is never sent.
2. `claim_due` picks the pending deliveries whose time has come and that no
   earlier delivery for the same row is holding up, and leases them for 60
   seconds so another instance leaves them alone. The lease is the
   `next_attempt_at` the claim writes.
3. `send` makes each attempt and `record` writes it down and decides what
   happens next: done, retried later, or failed. Nothing reads the database
   while a request is in flight. `send` runs the attempt on a thread of its
   own and stops waiting for it after `ATTEMPT_DEADLINE`, since httpx times
   each read on its own and a name lookup cannot be cut short. `record`
   writes only if the row still carries the lease this pass wrote, in the
   same update that writes the outcome, so it never overwrites another
   pass's claim.

`run_pass` measures its lease on a real-time counter from just before the
claim and starts an attempt only while `ATTEMPT_DEADLINE` plus
`LEASE_MARGIN` of it is left, which keeps every request inside the lease.
The margin covers writing the outcome and two machines whose clocks differ
by a few seconds. What it claimed and did not get to stays leased and comes
due again when the lease runs out.

On PostgreSQL, fan-out and claiming lock with `FOR UPDATE SKIP LOCKED`, so
several instances share the work instead of queuing behind each other. A
marker's id there is handed out at insert and not at commit, so a
transaction that commits late could leave a lower id behind a cursor that
has already moved past it. Fan-out on the system clock therefore leaves
markers younger than 5 seconds for the next pass. A transaction that holds a marker uncommitted
for longer than that can still be passed over, and its change is then not
sent; the full re-read that change feed consumers already do on a slow timer
covers that case as well. SQLite writes one transaction at a time and has
no such gap.

### Under a host clock

With `CLOCK_MODE=host` APScheduler does not run, and the worker is a job in
`backend/app/cron/scheduled.py::JOBS` that the host's advances run
([clock.md](clock.md#jobs-under-a-host-clock)). It runs last at each
instant and once per advance. Every time it reads, from the retry schedule
to the 24 hours an old secret lives, is host time, so a replay sends the
same deliveries at the same instants. The two exceptions are the attempt
deadline and the pass's lease budget, which guard against a receiver that
is slow in real seconds and so are measured in real seconds. A receiver
that answers promptly never reaches either.

Fan-out does not wait the 5 seconds for late commits under a host clock,
on PostgreSQL either. The wait would be measured in host time, which says
nothing about how long a commit takes: a host stepping a few seconds at a
time would see each change held back for a step or two, and a write still
in flight across a longer step would not be covered anyway. What makes it
safe is the host's side of the
contract: it advances the clock after its own writes have returned. A
host that sends requests concurrently and advances before they return can
leave a change behind the cursor on PostgreSQL, and that change is then
not sent.

`webhook-timestamp` is host time too. A receiver that applies the five
minute rule refuses deliveries from a host clock that is far from real time,
which is correct for a real receiver. A simulation's receiver runs on the
host's clock or skips that check.
