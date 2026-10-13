# Copyright 2026 Chronos Ledger Contributors
# Licensed under the Apache License, Version 2.0
"""Signed outgoing webhooks, fed from the change feed.

docs/webhooks.md is the design and the receiver's documentation. In short:

- fan_out turns change_markers rows into one webhook_deliveries row per
  marker per subscription that wants it, with the body built there and then,
  and moves the subscription's cursor past them in the same transaction.
- run_pass claims what is due, sends it, and records the attempt. A delivery
  waits while an earlier one for the same row on the same subscription is
  still pending, so a receiver sees each row's changes in order.
- vet decides whether a URL may be called at all, and is asked again on
  every attempt, because what a name resolves to can change between the
  admin typing it and the hundredth retry.

Every timestamp comes from app.core.clock, so under a host clock the whole
thing, retries included, moves only when the host advances the clock.
"""

from __future__ import annotations

import base64
import hashlib
import hmac
import ipaddress
import json
import secrets
import socket
import threading
import time
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from urllib.parse import urlsplit, urlunsplit

import httpx
from sqlalchemy import exists, func
from sqlalchemy.orm import Session, aliased

from app.api.v1.endpoints.changes import current_rows
from app.core import clock, ids
from app.core.config import get_settings
from app.models.db import ChangeMarker, WebhookAttempt, WebhookDelivery, WebhookSubscription
from app.schemas.changes import Change

EVENT_TYPES = (
    "reservation.created",
    "reservation.updated",
    "resource.created",
    "resource.updated",
)

PENDING = "pending"
SUCCEEDED = "succeeded"
FAILED = "failed"

SECRET_PREFIX = "whsec_"
# How long the secret before a rotation keeps signing, unless an admin
# removes it sooner. A day is long enough to roll the new one out to every
# receiver and short enough that a leaked old secret stops working on its own.
PREVIOUS_SECRET_LIFETIME = timedelta(hours=24)

# The longest wait before each retry, after the first attempt fails, after the
# second, and so on. The Standard Webhooks schedule: 5 seconds, 5 minutes, 30
# minutes, 2, 5, 10 and 10 hours, about 27 hours in all. Each wait is drawn
# from zero up to this (full jitter), so many deliveries that failed together
# do not all come back together.
RETRY_DELAYS = (
    timedelta(seconds=5),
    timedelta(minutes=5),
    timedelta(minutes=30),
    timedelta(hours=2),
    timedelta(hours=5),
    timedelta(hours=10),
    timedelta(hours=10),
)
MAX_ATTEMPTS = len(RETRY_DELAYS) + 1

# A subscription is paused when this many deliveries in a row have used up
# every attempt. One success resets the count. Five is more than a day of a
# receiver answering nothing but errors, which is a receiver that is gone
# rather than one having a bad hour.
PAUSE_AFTER_FAILED_DELIVERIES = 5

# httpx applies these to each operation on its own: the connect, and then
# every single read or write. A receiver that drips its answer a byte at a
# time never trips the read timeout, so ATTEMPT_DEADLINE is what bounds an
# attempt as a whole, the name lookup in vet included.
CONNECT_TIMEOUT = 3.0
READ_TIMEOUT = 10.0
ATTEMPT_DEADLINE = 15.0
# How long a claimed delivery is left alone while it is being sent, so a
# second worker does not send it too. A worker that dies mid-send leaves it
# to be retried once this runs out. A pass starts an attempt only while at
# least ATTEMPT_DEADLINE plus LEASE_MARGIN of its lease is left, so every
# request it makes is made inside the lease; the margin covers writing the
# outcome down and clocks on two machines that do not quite agree.
CLAIM_LEASE = timedelta(seconds=60)
LEASE_MARGIN = timedelta(seconds=10)
EXCERPT_CHARS = 200

FAN_OUT_BATCH = 500
SEND_BATCH = 50

# On PostgreSQL a marker's id is handed out at the insert and not at the
# commit, so a transaction that commits late can leave a lower id behind a
# cursor that has already moved past it. Markers younger than this are left
# for the next pass, by which time the transaction that wrote them has
# committed or rolled back. SQLite writes one transaction at a time, so it
# needs no wait. Neither does a host clock: commit latency is real time and
# the wait would be measured in host time, and the host advances the clock
# after its writes have returned, so there is nothing still in flight.
POSTGRES_COMMIT_GRACE = timedelta(seconds=5)

# None is httpx's own transport. Tests put an httpx.MockTransport here.
TRANSPORT: httpx.BaseTransport | None = None


class Refused(Exception):
    """A URL that may not be called, with the reason in words."""


# Secrets and signatures.


def new_secret() -> str:
    return SECRET_PREFIX + base64.b64encode(secrets.token_bytes(32)).decode()


def sign(secret: str, event_id: str, timestamp: int, body: bytes) -> str:
    """One Standard Webhooks signature: v1, then base64 HMAC-SHA256 of id.timestamp.body."""
    key = base64.b64decode(secret.removeprefix(SECRET_PREFIX))
    signed = f"{event_id}.{timestamp}.".encode() + body
    return "v1," + base64.b64encode(hmac.new(key, signed, hashlib.sha256).digest()).decode()


def previous_secret_live(subscription: WebhookSubscription, now: datetime) -> bool:
    if not subscription.previous_secret:
        return False
    expires = subscription.previous_secret_expires_at
    return expires is None or _aware(expires) > now


def signing_secrets(subscription: WebhookSubscription, now: datetime) -> list[str]:
    """The current secret, and the one before it while it is still live."""
    found = [subscription.secret]
    if previous_secret_live(subscription, now):
        found.append(subscription.previous_secret)
    return found


# Which URLs may be called.


@dataclass(frozen=True)
class Target:
    scheme: str
    host: str
    port: int
    address: str
    path: str
    query: str

    @property
    def address_url(self) -> str:
        """The URL with the vetted address in place of the name."""
        literal = f"[{self.address}]" if ":" in self.address else self.address
        return urlunsplit((self.scheme, f"{literal}:{self.port}", self.path, self.query, ""))

    @property
    def host_header(self) -> str:
        name = f"[{self.host}]" if ":" in self.host else self.host
        default = 443 if self.scheme == "https" else 80
        return name if self.port == default else f"{name}:{self.port}"


def resolve(host: str, port: int) -> list[str]:
    """Every address a name resolves to. Tests replace this."""
    found = []
    for info in socket.getaddrinfo(host, port, type=socket.SOCK_STREAM):
        address = str(info[4][0])
        if address not in found:
            found.append(address)
    return found


def vet(url: str) -> Target:
    """The address to connect to for url, or Refused saying why there is none.

    The name is resolved here and the connection goes to the address that
    passed, not to the name, so a resolver that answers differently a moment
    later cannot slip a private address in between the check and the call.
    Any one bad address refuses the whole name: a name with a public and a
    private address is a name somebody can steer.
    """
    settings = get_settings()
    parts = urlsplit(url)
    scheme = parts.scheme.lower()
    host = (parts.hostname or "").lower()
    if scheme not in ("http", "https"):
        raise Refused("only https URLs are accepted")
    if not host:
        raise Refused("the URL has no host")
    if parts.username is not None or parts.password is not None:
        raise Refused("the URL carries a user name or password, which would be stored in clear")
    if scheme == "http" and host not in settings.webhook_allow_http_hosts_set:
        raise Refused(
            f"plain http to {host} is not allowed; "
            "use https or list the host in WEBHOOK_ALLOW_HTTP_HOSTS"
        )
    try:
        port = parts.port or (443 if scheme == "https" else 80)
    except ValueError:
        raise Refused("the port is not a number from 1 to 65535") from None

    try:
        addresses = [str(ipaddress.ip_address(host))]
    except ValueError:
        try:
            addresses = resolve(host, port)
        except OSError:
            raise Refused(f"{host} does not resolve") from None
    if not addresses:
        raise Refused(f"{host} does not resolve")
    for address in addresses:
        _check_address(host, address, settings.webhook_allow_private_targets)
    return Target(scheme, host, port, addresses[0], parts.path or "/", parts.query)


def _check_address(host: str, address: str, allow_private: bool) -> None:
    ip = ipaddress.ip_address(address)
    # ::ffff:127.0.0.1 is 127.0.0.1 to the network stack, whatever the IPv6
    # flags say about it, so it is judged as the IPv4 address it carries.
    if isinstance(ip, ipaddress.IPv6Address) and ip.ipv4_mapped is not None:
        ip = ip.ipv4_mapped
    if ip.is_multicast or ip.is_unspecified or ip.is_reserved:
        raise Refused(f"{host} resolves to {address}, which no receiver can be at")
    if allow_private:
        return
    if ip.is_loopback or ip.is_private or ip.is_link_local or not ip.is_global:
        raise Refused(
            f"{host} resolves to {address}, a loopback, private or link-local address; "
            "WEBHOOK_ALLOW_PRIVATE_TARGETS allows those"
        )


# Fan-out.


def latest_marker_id(db: Session) -> int:
    return db.query(func.max(ChangeMarker.id)).scalar() or 0


def fan_out(db: Session) -> int:
    """Turn the markers each live subscription has not seen into deliveries.

    One transaction: the deliveries and the cursors move together or not at
    all, so a crash halfway through neither loses an event nor sends one
    twice. Returns how many deliveries were made.
    """
    if not get_settings().change_feed_enabled:
        return 0
    wait_for_commits = _is_postgres(db) and not clock.is_host()
    now = clock.now()
    settled = now - POSTGRES_COMMIT_GRACE

    query = (
        db.query(WebhookSubscription)
        .filter(WebhookSubscription.active.is_(True), WebhookSubscription.paused_at.is_(None))
        .order_by(WebhookSubscription.id)
    )
    if _is_postgres(db):
        # Two instances fanning out at once take a subscription each, rather
        # than both reading the same markers for it.
        query = query.with_for_update(skip_locked=True)

    made = 0
    for subscription in query.all():
        markers = []
        for marker in (
            db.query(ChangeMarker)
            .filter(ChangeMarker.id > subscription.cursor)
            .order_by(ChangeMarker.id)
            .limit(FAN_OUT_BATCH)
        ):
            # Stop at the first one too young to trust, rather than skipping
            # it, so the cursor never passes a marker that was left behind.
            if wait_for_commits and _aware(marker.at) > settled:
                break
            markers.append(marker)
        if not markers:
            continue
        wanted = set(subscription.event_types.split(","))
        chosen = [m for m in markers if _event_type(m) in wanted]
        rows = current_rows(db, sorted({(m.entity_kind, m.entity_id) for m in chosen}))
        for marker in chosen:
            db.add(
                WebhookDelivery(
                    subscription_id=subscription.id,
                    marker_id=marker.id,
                    event_id=f"msg_{ids.new_hex(16)}",
                    event_type=_event_type(marker),
                    entity_kind=marker.entity_kind,
                    entity_id=marker.entity_id,
                    payload=build_payload(marker, rows.get((marker.entity_kind, marker.entity_id))),
                    status=PENDING,
                    attempt_count=0,
                    next_attempt_at=now,
                    created_at=now,
                )
            )
        subscription.cursor = markers[-1].id
        made += len(chosen)
    db.commit()
    return made


def build_payload(marker: ChangeMarker, row: object) -> str:
    """The body for one marker: the Standard Webhooks envelope around a Change.

    The row goes through the same Change model the change feed answers with,
    so data holds the room or the booking exactly as the feed would have shown
    it at this moment. Compact JSON, since these are the bytes that are signed.
    """
    at = _aware(marker.at)
    change = Change.model_validate(
        {
            "cursor": marker.id,
            "entity_kind": marker.entity_kind,
            "entity_id": marker.entity_id,
            "change_kind": marker.change_kind,
            "at": at,
            marker.entity_kind: row,
        },
        from_attributes=True,
    ).model_dump(mode="json")
    body = {
        "type": _event_type(marker),
        "timestamp": change["at"],
        "data": {
            "marker_id": marker.id,
            "entity_kind": marker.entity_kind,
            "entity_id": marker.entity_id,
            "change_kind": marker.change_kind,
            "at": change["at"],
            marker.entity_kind: change.get(marker.entity_kind),
        },
    }
    return json.dumps(body, separators=(",", ":"), ensure_ascii=False)


# Sending.


@dataclass(frozen=True)
class Outgoing:
    """What one send needs, read out of the database before the call is made.

    Plain values and not ORM rows, so nothing touches the session while the
    request is in flight: on SQLite a read there would open a transaction and
    hold the write lock for as long as the receiver takes to answer.

    lease is the next_attempt_at the claim wrote. It is how record tells that
    the row is still this pass's to write: once the lease runs out another
    pass can claim the row and write its own lease over it.
    """

    delivery_id: int
    subscription_id: int
    url: str
    event_id: str
    payload: str
    secrets: tuple[str, ...]
    lease: datetime


@dataclass(frozen=True)
class Outcome:
    status_code: int | None
    response_ms: int
    error: str | None
    excerpt: str | None

    @property
    def succeeded(self) -> bool:
        return self.status_code is not None and 200 <= self.status_code < 300


def run_pass(db: Session) -> int:
    """Fan out what is new, then send what is due. Returns how many were sent.

    The lease is measured from just before the claim, on a real-time counter
    rather than the clock, because what can outlast it is a real receiver
    taking real seconds. Once too little of it is left for another attempt,
    the pass stops, and what it claimed and did not send comes due again
    when the lease runs out.
    """
    fan_out(db)
    started = time.perf_counter()
    claimed = claim_due(db)
    last_start = (CLAIM_LEASE - LEASE_MARGIN).total_seconds() - ATTEMPT_DEADLINE
    sent = 0
    for outgoing in claimed:
        if time.perf_counter() - started > last_start:
            break
        record(db, outgoing, send(outgoing))
        sent += 1
    return sent


def claim_due(db: Session) -> list[Outgoing]:
    """The deliveries due now that nothing earlier is holding up, leased to this pass."""
    now = clock.now()
    lease = now + CLAIM_LEASE
    earlier = aliased(WebhookDelivery)
    held_up = exists().where(
        earlier.subscription_id == WebhookDelivery.subscription_id,
        earlier.entity_kind == WebhookDelivery.entity_kind,
        earlier.entity_id == WebhookDelivery.entity_id,
        earlier.marker_id < WebhookDelivery.marker_id,
        earlier.status == PENDING,
    )
    query = (
        db.query(WebhookDelivery, WebhookSubscription)
        .join(WebhookSubscription, WebhookSubscription.id == WebhookDelivery.subscription_id)
        .filter(
            WebhookDelivery.status == PENDING,
            WebhookDelivery.next_attempt_at <= now,
            WebhookSubscription.active.is_(True),
            WebhookSubscription.paused_at.is_(None),
            ~held_up,
        )
        .order_by(WebhookDelivery.next_attempt_at, WebhookDelivery.id)
        .limit(SEND_BATCH)
    )
    if _is_postgres(db):
        # Another instance's pass skips what this one has locked instead of
        # waiting for it, and the lease below keeps it skipped after commit.
        query = query.with_for_update(skip_locked=True, of=WebhookDelivery)

    claimed = []
    for delivery, subscription in query.all():
        claimed.append(
            Outgoing(
                delivery_id=delivery.id,
                subscription_id=subscription.id,
                url=subscription.url,
                event_id=delivery.event_id,
                payload=delivery.payload,
                secrets=tuple(signing_secrets(subscription, now)),
                lease=lease,
            )
        )
        delivery.next_attempt_at = lease
    db.commit()
    return claimed


def send(outgoing: Outgoing) -> Outcome:
    """One attempt, given up on after ATTEMPT_DEADLINE. Never raises.

    httpx has no deadline for a request as a whole, and a name lookup cannot
    be interrupted at all, so the attempt runs on a thread of its own and
    this one stops waiting for it at the deadline. The client is then closed
    under it, which ends the attempt at its next read or write at the latest,
    and an attempt still looking the name up when that happens never sends.
    """
    started = time.perf_counter()
    client = httpx.Client(
        transport=TRANSPORT,
        follow_redirects=False,
        trust_env=False,
        timeout=httpx.Timeout(READ_TIMEOUT, connect=CONNECT_TIMEOUT),
    )
    gave_up = threading.Event()
    result: list[Outcome] = []

    def attempt() -> None:
        try:
            result.append(_attempt(client, outgoing, started, gave_up))
        except Exception as problem:
            # Closing the client under the attempt lands here, after nobody
            # is waiting for the result; anything else is still a failed
            # attempt rather than a pass that stops.
            result.append(
                Outcome(None, _ms_since(started), _short(f"failed: {type(problem).__name__}"), None)
            )

    worker = threading.Thread(target=attempt, name="webhook-attempt", daemon=True)
    worker.start()
    worker.join(ATTEMPT_DEADLINE)
    if worker.is_alive():
        gave_up.set()
        client.close()
        return Outcome(None, _ms_since(started), "timed out", None)
    client.close()
    return result[0]


def _attempt(
    client: httpx.Client, outgoing: Outgoing, started: float, gave_up: threading.Event
) -> Outcome:
    try:
        target = vet(outgoing.url)
    except Refused as refused:
        return Outcome(None, _ms_since(started), _short(f"refused: {refused}"), None)
    if gave_up.is_set():
        return Outcome(None, _ms_since(started), "timed out", None)

    timestamp = int(clock.now().timestamp())
    body = outgoing.payload.encode()
    headers = {
        "Host": target.host_header,
        "Content-Type": "application/json",
        "User-Agent": "Chronos-Ledger-Webhooks",
        "webhook-id": outgoing.event_id,
        "webhook-timestamp": str(timestamp),
        "webhook-signature": " ".join(
            sign(secret, outgoing.event_id, timestamp, body) for secret in outgoing.secrets
        ),
    }
    extensions = {"sni_hostname": target.host} if target.scheme == "https" else {}
    try:
        with client.stream(
            "POST", target.address_url, content=body, headers=headers, extensions=extensions
        ) as response:
            excerpt = _excerpt(response)
            status_code = response.status_code
    except httpx.TimeoutException:
        return Outcome(None, _ms_since(started), "timed out", None)
    except httpx.HTTPError as problem:
        return Outcome(
            None, _ms_since(started), _short(f"connection failed: {type(problem).__name__}"), None
        )

    if 200 <= status_code < 300:
        error = None
    elif 300 <= status_code < 400:
        error = "redirect not followed"
    else:
        error = f"HTTP {status_code}"
    return Outcome(status_code, _ms_since(started), error, excerpt)


def record(db: Session, outgoing: Outgoing, outcome: Outcome) -> bool:
    """Write the attempt down and decide what happens to the delivery next.

    Only while the row still carries this pass's lease. If the lease ran out
    and another pass claimed the row, or an administrator redelivered it, or
    it was deleted, nothing is written and this returns False: the attempt
    belongs to a claim that no longer exists, and charging it would count
    one send twice.
    """
    delivery = db.get(WebhookDelivery, outgoing.delivery_id)
    subscription = db.get(WebhookSubscription, outgoing.subscription_id)
    if delivery is None or subscription is None:
        db.rollback()
        return False
    now = clock.now()
    attempts = delivery.attempt_count + 1
    if outcome.succeeded:
        changes = {"status": SUCCEEDED, "completed_at": now, "next_attempt_at": None}
    elif attempts >= MAX_ATTEMPTS:
        changes = {"status": FAILED, "completed_at": now, "next_attempt_at": None}
    else:
        changes = {"next_attempt_at": now + backoff(delivery.event_id, attempts)}
    changes["attempt_count"] = attempts

    # The lease is checked by the update itself rather than by the read
    # above, so a claim that lands between the two cannot be written over.
    held = (
        db.query(WebhookDelivery)
        .filter(
            WebhookDelivery.id == outgoing.delivery_id,
            WebhookDelivery.status == PENDING,
            WebhookDelivery.next_attempt_at == outgoing.lease,
            WebhookDelivery.attempt_count == delivery.attempt_count,
        )
        .update(changes, synchronize_session=False)
    )
    if not held:
        db.rollback()
        return False

    db.add(
        WebhookAttempt(
            delivery_id=outgoing.delivery_id,
            at=now,
            status_code=outcome.status_code,
            response_ms=outcome.response_ms,
            error=outcome.error,
            response_excerpt=outcome.excerpt,
        )
    )
    if outcome.succeeded:
        subscription.consecutive_failures = 0
    elif attempts >= MAX_ATTEMPTS:
        subscription.consecutive_failures += 1
        if (
            subscription.consecutive_failures >= PAUSE_AFTER_FAILED_DELIVERIES
            and subscription.paused_at is None
        ):
            subscription.paused_at = now
    db.commit()
    return True


def backoff(event_id: str, attempts: int) -> timedelta:
    """The wait after the given number of failed attempts: full jitter under RETRY_DELAYS.

    The fraction comes from a hash of the event id and the attempt number, not
    from a random number generator. Event ids are already random (or seeded,
    under ID_SEED), so deliveries still spread out, and a host replaying the
    same script sees the same retries at the same instants.
    """
    ceiling = RETRY_DELAYS[min(attempts, len(RETRY_DELAYS)) - 1]
    digest = hashlib.sha256(f"{event_id}:{attempts}".encode()).digest()
    fraction = int.from_bytes(digest[:8], "big") / 2**64
    return ceiling * fraction


def redeliver(delivery: WebhookDelivery) -> None:
    """Send a delivery again from the start of the schedule, on the next pass.

    The same event id and the same body, so a receiver that already has it can
    tell. The timestamp and the signature are made at the send, so they are new.
    """
    delivery.status = PENDING
    delivery.attempt_count = 0
    delivery.next_attempt_at = clock.now()
    delivery.completed_at = None


# Small things.


def _event_type(marker: ChangeMarker) -> str:
    return f"{marker.entity_kind}.{marker.change_kind}"


def _excerpt(response: httpx.Response) -> str | None:
    """The start of the body and no more. send's deadline bounds how long it takes."""
    kept = b""
    for chunk in response.iter_bytes():
        kept += chunk
        if len(kept) >= EXCERPT_CHARS * 4:
            break
    text = kept.decode("utf-8", errors="replace")[:EXCERPT_CHARS]
    return text or None


def _ms_since(started: float) -> int:
    return int((time.perf_counter() - started) * 1000)


def _short(text: str) -> str:
    return text[:200]


def _aware(moment: datetime) -> datetime:
    # SQLite hands back a naive datetime for a column that was written in UTC.
    return moment if moment.tzinfo is not None else moment.replace(tzinfo=UTC)


def _is_postgres(db: Session) -> bool:
    return db.get_bind().dialect.name == "postgresql"
