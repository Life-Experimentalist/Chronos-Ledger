# Copyright 2026 Chronos Ledger Contributors
# Licensed under the Apache License, Version 2.0
"""Signed outgoing webhooks (app/services/webhooks.py, docs/webhooks.md).

Nothing here touches the network. The receiver is an httpx.MockTransport put
in webhooks.TRANSPORT, and names resolve through a stand-in for
webhooks.resolve. Time moves only when a test advances the host clock, and
each advance runs one delivery pass through the same job table a host uses.
"""

import base64
import datetime
import hashlib
import hmac
import json
import threading
from datetime import UTC

import httpx
import pytest
from sqlalchemy import update

from app.core import change_feed, clock
from app.core.config import get_settings
from app.cron import scheduled
from app.models.db import ChangeMarker, WebhookAttempt, WebhookDelivery, WebhookSubscription
from app.services import webhooks
from tests.conftest import ADMIN_PASSWORD, STAFF_PASSWORD, login

START = datetime.datetime(2026, 1, 5, 9, 0, tzinfo=UTC)
URL = "https://receiver.test/hooks"
# A public address that nothing in these tests ever connects to: the
# transport is a MockTransport.
PUBLIC_ADDRESS = "93.184.216.34"
EVERYTHING = ["reservation.created", "reservation.updated", "resource.created", "resource.updated"]


class Receiver:
    """Stands in for the far end, and keeps everything it was sent."""

    def __init__(self):
        self.answer = 200
        self.headers = {}
        self.seen = []

    def __call__(self, request: httpx.Request) -> httpx.Response:
        self.seen.append(
            {
                "at": clock.now(),
                "url": str(request.url),
                "host": request.headers.get("host"),
                "sni": request.extensions.get("sni_hostname"),
                "id": request.headers["webhook-id"],
                "timestamp": request.headers["webhook-timestamp"],
                "signature": request.headers["webhook-signature"],
                "body": request.content,
                "status": self.answer,
            }
        )
        return httpx.Response(self.answer, headers=self.headers, text="noted")

    def delivered(self):
        return [hit for hit in self.seen if 200 <= hit["status"] < 300]


def verify(secret: str, hit: dict, now: datetime.datetime) -> bool:
    """A receiver's check, written from the Standard Webhooks text and not from our code."""
    key = base64.b64decode(secret.split("_", 1)[1])
    timestamp = int(hit["timestamp"])
    if abs(now.timestamp() - timestamp) > 5 * 60:
        return False
    content = hit["id"].encode() + b"." + hit["timestamp"].encode() + b"." + hit["body"]
    expected = base64.b64encode(hmac.new(key, content, hashlib.sha256).digest())
    for candidate in hit["signature"].split(" "):
        version, _, value = candidate.partition(",")
        if version == "v1" and hmac.compare_digest(value.encode(), expected):
            return True
    return False


@pytest.fixture()
def feed_on(monkeypatch):
    monkeypatch.setenv("CHANGE_FEED_ENABLED", "true")
    monkeypatch.setenv("ORG_TIMEZONE", "UTC")
    get_settings.cache_clear()
    yield
    get_settings.cache_clear()


@pytest.fixture()
def host_clock(db, monkeypatch):
    monkeypatch.setattr(scheduled, "SessionLocal", lambda: db)
    clock.install(clock.HostClock(START))
    yield
    clock.reset()


@pytest.fixture()
def receiver(monkeypatch):
    found = Receiver()
    monkeypatch.setattr(webhooks, "TRANSPORT", httpx.MockTransport(found))
    monkeypatch.setattr(webhooks, "resolve", lambda host, port: [PUBLIC_ADDRESS])
    return found


def _admin(client):
    return login(client, "admin@test.internal", ADMIN_PASSWORD)


def _subscribe(client, headers, url=URL, event_types=EVERYTHING):
    res = client.post(
        "/api/v1/webhooks/", json={"url": url, "event_types": event_types}, headers=headers
    )
    assert res.status_code == 201, res.text
    return res.json()


def _room(client, headers, code):
    res = client.post("/api/v1/resources/", json={"code": code}, headers=headers)
    assert res.status_code == 201, res.text
    return res.json()["id"]


def _rename(client, headers, room_id, label):
    res = client.patch(f"/api/v1/resources/{room_id}", json={"label": label}, headers=headers)
    assert res.status_code == 200, res.text


def _book(client, headers, room_id, key):
    res = client.post(
        f"/api/v1/resources/{room_id}/reservations",
        json={"date": "2026-01-06", "start": "14:00", "end": "15:00", "purpose": "Ward round"},
        headers={**headers, "Idempotency-Key": key},
    )
    assert res.status_code == 201, res.text
    return res.json()["id"]


def _step(minutes=1):
    return scheduled.advance(clock.now() + datetime.timedelta(minutes=minutes))


def _deliveries(db):
    db.expire_all()
    return db.query(WebhookDelivery).order_by(WebhookDelivery.id).all()


# -- Delivery, order and signatures -------------------------------------------


def test_a_receiver_down_for_an_hour_gets_everything_after_in_order(
    client, db, seed_users, feed_on, host_clock, receiver
):
    headers = _admin(client)
    secret = _subscribe(client, headers)["secret"]
    first = _room(client, headers, "LH-201")
    _rename(client, headers, first, "Seminar Room")
    second = _room(client, headers, "LH-202")
    _rename(client, headers, first, "Seminar Room A")
    booking = _book(client, headers, second, "hook-0000-0001")
    _rename(client, headers, second, "Lecture Hall")
    markers = [m.id for m in db.query(ChangeMarker).order_by(ChangeMarker.id)]
    assert len(markers) == 6

    receiver.answer = 503
    for _ in range(60):
        _step()
    assert receiver.seen, "the worker kept trying while the receiver was down"
    assert not receiver.delivered()

    receiver.answer = 204
    # Long enough for the longest wait the schedule can hand out. A delivery
    # whose jittered waits ran short can fail six times inside the hour, and
    # its next wait is then anything up to ten hours.
    longest_wait = int(max(webhooks.RETRY_DELAYS).total_seconds()) // 60
    for _ in range(longest_wait + 60):
        if all(d.status == webhooks.SUCCEEDED for d in _deliveries(db)):
            break
        _step()
    deliveries = _deliveries(db)
    assert [d.marker_id for d in deliveries] == markers
    assert all(d.status == webhooks.SUCCEEDED for d in deliveries)

    # Every send, failed or not, carries a signature a receiver accepts at
    # the moment it arrives, and every retry keeps the delivery's id.
    ids_by_marker = {d.marker_id: d.event_id for d in deliveries}
    for hit in receiver.seen:
        assert verify(secret, hit, hit["at"])
        assert hit["host"] == "receiver.test"
        assert hit["sni"] == "receiver.test"
        assert hit["url"].startswith(f"https://{PUBLIC_ADDRESS}")
        body = json.loads(hit["body"])
        assert ids_by_marker[body["data"]["marker_id"]] == hit["id"]

    # Each row's changes reach the receiver in the order they happened, the
    # failed sends included: nothing about a row overtakes an earlier change
    # to the same row.
    by_entity = {}
    for hit in receiver.seen:
        data = json.loads(hit["body"])["data"]
        by_entity.setdefault((data["entity_kind"], data["entity_id"]), []).append(data["marker_id"])
    assert set(by_entity) == {("resource", first), ("resource", second), ("reservation", booking)}
    for sent in by_entity.values():
        assert sent == sorted(sent)
    delivered = [json.loads(hit["body"])["data"]["marker_id"] for hit in receiver.delivered()]
    assert sorted(delivered) == markers


def test_the_body_is_the_change_feed_entry_in_an_envelope(
    client, db, seed_users, feed_on, host_clock, receiver
):
    headers = _admin(client)
    _subscribe(client, headers)
    room = _room(client, headers, "LH-201")
    _step()

    (hit,) = receiver.delivered()
    body = json.loads(hit["body"])
    assert body["type"] == "resource.created"
    assert set(body) == {"type", "timestamp", "data"}
    feed = client.get("/api/v1/changes/", headers=headers).json()
    (entry,) = [e for e in feed["changes"] if e["entity_id"] == room]
    # The same instant. The envelope always says it is UTC; the feed on
    # SQLite writes the same time without the offset.
    assert body["timestamp"] == START.isoformat().replace("+00:00", "Z")
    assert entry["at"].removesuffix("Z") == body["timestamp"].removesuffix("Z")
    assert body["data"]["marker_id"] == entry["cursor"]
    assert body["data"]["change_kind"] == "created"
    assert body["data"]["resource"] == entry["resource"]
    assert b"whsec_" not in hit["body"]


def test_only_the_chosen_event_types_are_sent(
    client, db, seed_users, feed_on, host_clock, receiver
):
    headers = _admin(client)
    _subscribe(client, headers, event_types=["resource.updated"])
    room = _room(client, headers, "LH-201")
    _rename(client, headers, room, "Renamed")
    _step()

    assert [json.loads(h["body"])["type"] for h in receiver.seen] == ["resource.updated"]


def test_a_new_subscription_hears_nothing_from_before_it(
    client, db, seed_users, feed_on, host_clock, receiver
):
    headers = _admin(client)
    _room(client, headers, "LH-201")
    _subscribe(client, headers)
    _step()
    assert receiver.seen == []
    assert _deliveries(db) == []


def test_a_rolled_back_change_sends_nothing(client, db, seed_users, feed_on, host_clock, receiver):
    headers = _admin(client)
    _subscribe(client, headers)
    change_feed.record(db, change_feed.RESOURCE, 999, change_feed.CREATED)
    db.flush()
    db.rollback()
    _step()
    assert _deliveries(db) == []
    assert receiver.seen == []

    # And the cursor did not move past anything a later change needs.
    room = _room(client, headers, "LH-201")
    _step()
    (hit,) = receiver.seen
    assert json.loads(hit["body"])["data"]["entity_id"] == room


def test_redeliver_sends_the_same_message_with_a_fresh_signature(
    client, db, seed_users, feed_on, host_clock, receiver
):
    headers = _admin(client)
    created = _subscribe(client, headers)
    _room(client, headers, "LH-201")
    _step()
    (delivery,) = _deliveries(db)
    assert delivery.status == webhooks.SUCCEEDED
    delivery_id = delivery.id

    _step(minutes=30)
    res = client.post(
        f"/api/v1/webhooks/{created['id']}/deliveries/{delivery_id}/redeliver", headers=headers
    )
    assert res.status_code == 202, res.text
    assert res.json()["status"] == "pending"
    _step()

    original, again = receiver.seen
    assert again["id"] == original["id"]
    assert again["body"] == original["body"]
    assert again["timestamp"] != original["timestamp"]
    assert again["signature"] != original["signature"]
    assert verify(created["secret"], again, again["at"])
    # The original would now be refused as too old, which is why a
    # redelivery is signed again rather than replayed.
    assert not verify(created["secret"], original, again["at"])


def test_a_paused_subscription_fans_out_nothing_until_resumed(
    client, db, seed_users, feed_on, host_clock, receiver
):
    headers = _admin(client)
    created = _subscribe(client, headers)
    subscription = db.get(WebhookSubscription, created["id"])
    subscription.paused_at = clock.now()
    db.commit()

    room = _room(client, headers, "LH-201")
    _rename(client, headers, room, "Renamed")
    for _ in range(5):
        _step()
    assert _deliveries(db) == []
    assert receiver.seen == []

    res = client.post(f"/api/v1/webhooks/{created['id']}/resume", headers=headers)
    assert res.status_code == 200, res.text
    assert res.json()["paused_at"] is None
    _step()
    _step()
    assert [json.loads(h["body"])["type"] for h in receiver.seen] == [
        "resource.created",
        "resource.updated",
    ]


def test_an_inactive_subscription_sends_nothing_and_catches_up_when_active(
    client, db, seed_users, feed_on, host_clock, receiver
):
    headers = _admin(client)
    created = _subscribe(client, headers)
    res = client.patch(f"/api/v1/webhooks/{created['id']}", json={"active": False}, headers=headers)
    assert res.status_code == 200, res.text
    _room(client, headers, "LH-201")
    _step()
    assert receiver.seen == []

    client.patch(f"/api/v1/webhooks/{created['id']}", json={"active": True}, headers=headers)
    _step()
    assert len(receiver.seen) == 1


def test_five_deliveries_failing_in_a_row_pause_the_subscription(
    client, db, seed_users, feed_on, host_clock, receiver
):
    headers = _admin(client)
    created = _subscribe(client, headers)
    for number in range(webhooks.PAUSE_AFTER_FAILED_DELIVERIES):
        _room(client, headers, f"LH-{number}")
    receiver.answer = 500

    # Longer than the longest retry wait, so every delivery is tried once per
    # step, and every one of them uses up its attempts on the same step.
    for _ in range(webhooks.MAX_ATTEMPTS):
        _step(minutes=11 * 60)

    deliveries = _deliveries(db)
    assert all(d.status == webhooks.FAILED for d in deliveries)
    assert all(d.attempt_count == webhooks.MAX_ATTEMPTS for d in deliveries)
    view = client.get(f"/api/v1/webhooks/{created['id']}", headers=headers).json()
    assert view["paused_at"] is not None
    assert view["consecutive_failures"] == webhooks.PAUSE_AFTER_FAILED_DELIVERIES

    sent = len(receiver.seen)
    _room(client, headers, "LH-LATER")
    _step()
    assert len(receiver.seen) == sent
    assert len(_deliveries(db)) == len(deliveries)


def test_one_success_resets_the_failure_count(db, seed_users, feed_on, host_clock):
    subscription = WebhookSubscription(
        url=URL, event_types="resource.created", cursor=0, secret=webhooks.new_secret()
    )
    db.add(subscription)
    db.commit()
    for entity in (1, 2):
        change_feed.record(db, change_feed.RESOURCE, entity, change_feed.CREATED)
    db.commit()
    webhooks.fan_out(db)
    first, second = (delivery.id for delivery in _deliveries(db))

    def claim(delivery_id):
        # Past the longest retry wait and the lease, so both are due again.
        clock.advance_to(clock.now() + datetime.timedelta(hours=11))
        return {o.delivery_id: o for o in webhooks.claim_due(db)}[delivery_id]

    for _ in range(webhooks.MAX_ATTEMPTS):
        assert webhooks.record(db, claim(first), webhooks.Outcome(500, 3, "HTTP 500", None))
    assert db.get(WebhookSubscription, subscription.id).consecutive_failures == 1
    assert webhooks.record(db, claim(second), webhooks.Outcome(200, 3, None, None))
    assert db.get(WebhookSubscription, subscription.id).consecutive_failures == 0


def test_a_failure_counted_by_another_replica_is_not_lost(db, seed_users, feed_on, host_clock):
    _one_change(db)
    webhooks.fan_out(db)

    def claim():
        clock.advance_to(clock.now() + datetime.timedelta(hours=11))
        (outgoing,) = webhooks.claim_due(db)
        return outgoing

    for _ in range(webhooks.MAX_ATTEMPTS - 1):
        assert webhooks.record(db, claim(), webhooks.Outcome(500, 3, "HTTP 500", None))
    outgoing = claim()

    # This replica has the subscription loaded with nothing counted, while
    # other replicas count their own failed deliveries in the database.
    subscription = db.get(WebhookSubscription, outgoing.subscription_id)
    assert subscription.consecutive_failures == 0
    db.execute(
        update(WebhookSubscription.__table__).values(
            consecutive_failures=webhooks.PAUSE_AFTER_FAILED_DELIVERIES - 1
        )
    )

    assert webhooks.record(db, outgoing, webhooks.Outcome(500, 3, "HTTP 500", None))
    db.expire_all()
    subscription = db.get(WebhookSubscription, outgoing.subscription_id)
    assert subscription.consecutive_failures == webhooks.PAUSE_AFTER_FAILED_DELIVERIES
    assert subscription.paused_at is not None


def _one_change(db):
    """A subscription to new rooms, and one new room it has not been told about."""
    db.add(
        WebhookSubscription(
            url=URL, event_types="resource.created", cursor=0, secret=webhooks.new_secret()
        )
    )
    db.commit()
    change_feed.record(db, change_feed.RESOURCE, 1, change_feed.CREATED)
    db.commit()


def test_a_claim_whose_lease_ran_out_writes_nothing_over_the_next_claim(
    db, seed_users, feed_on, host_clock
):
    _one_change(db)
    assert webhooks.fan_out(db) == 1
    (late,) = webhooks.claim_due(db)
    clock.advance_to(clock.now() + webhooks.CLAIM_LEASE + datetime.timedelta(seconds=1))
    (current,) = webhooks.claim_due(db)
    assert current.delivery_id == late.delivery_id
    assert current.lease > late.lease

    # The first pass's answer comes back after its lease ran out. It is
    # dropped: the row is the second pass's now, and no attempt is charged.
    assert not webhooks.record(db, late, webhooks.Outcome(200, 3, None, None))
    (delivery,) = _deliveries(db)
    assert delivery.status == webhooks.PENDING
    assert delivery.attempt_count == 0
    assert webhooks._aware(delivery.next_attempt_at) == current.lease
    assert db.query(WebhookAttempt).count() == 0

    assert webhooks.record(db, current, webhooks.Outcome(200, 3, None, None))
    (delivery,) = _deliveries(db)
    assert delivery.status == webhooks.SUCCEEDED
    assert delivery.attempt_count == 1
    assert db.query(WebhookAttempt).count() == 1


class _Stopwatch:
    """Stands in for the time module in webhooks, so a pass's lease runs out on cue."""

    def __init__(self):
        self.seconds = 0.0

    def perf_counter(self):
        return self.seconds


def test_a_pass_stops_sending_before_its_lease_runs_out(
    client, db, seed_users, feed_on, host_clock, receiver, monkeypatch
):
    headers = _admin(client)
    _subscribe(client, headers)
    for number in range(3):
        _room(client, headers, f"LH-{number}")

    # Each send takes 20 seconds of the lease. A pass starts a send only
    # while ATTEMPT_DEADLINE plus LEASE_MARGIN of its 60 seconds is left, so
    # it sends two and leaves the third alone.
    stopwatch = _Stopwatch()
    monkeypatch.setattr(webhooks, "time", stopwatch)
    answer = webhooks.TRANSPORT.handler

    def slow(request):
        stopwatch.seconds += 20
        return answer(request)

    monkeypatch.setattr(webhooks, "TRANSPORT", httpx.MockTransport(slow))
    webhooks.fan_out(db)
    assert webhooks.run_pass(db) == 2
    assert len(receiver.seen) == 2

    pending = [d for d in _deliveries(db) if d.status == webhooks.PENDING]
    assert len(pending) == 1
    assert pending[0].attempt_count == 0
    # Still leased, so no other pass sends it before this lease runs out.
    assert webhooks.claim_due(db) == []


def test_an_attempt_is_given_up_on_at_the_deadline(
    client, db, seed_users, feed_on, host_clock, receiver, monkeypatch
):
    headers = _admin(client)
    _subscribe(client, headers)
    _room(client, headers, "LH-201")

    # A receiver that has not finished answering when the deadline comes. A
    # per-read timeout would never fire on one that drips its headers; the
    # deadline covers the attempt as a whole.
    released = threading.Event()

    def stalled(request):
        released.wait(30)
        return httpx.Response(200)

    monkeypatch.setattr(webhooks, "ATTEMPT_DEADLINE", 0.2)
    monkeypatch.setattr(webhooks, "TRANSPORT", httpx.MockTransport(stalled))
    try:
        webhooks.fan_out(db)
        assert webhooks.run_pass(db) == 1
    finally:
        released.set()
    (delivery,) = _deliveries(db)
    assert delivery.status == webhooks.PENDING
    assert delivery.attempt_count == 1
    (attempt,) = db.query(WebhookAttempt).all()
    assert attempt.error == "timed out"
    assert attempt.status_code is None


def test_fan_out_on_postgres_waits_for_commits_on_the_system_clock_only(
    db, seed_users, feed_on, monkeypatch
):
    # SQLite has no FOR UPDATE and writes one transaction at a time, so
    # standing in for PostgreSQL here only switches the commit grace on.
    monkeypatch.setattr(webhooks, "_is_postgres", lambda db: True)
    try:
        clock.install(clock.SystemClock())
        _one_change(db)
        assert webhooks.fan_out(db) == 0

        # The same change a moment old, under a host clock: the host advances
        # only after its writes return, so there is nothing in flight to wait
        # for.
        clock.install(clock.HostClock(clock.now()))
        assert webhooks.fan_out(db) == 1
    finally:
        clock.reset()


def test_retries_wait_with_full_jitter_under_the_schedule():
    for attempts, ceiling in enumerate(webhooks.RETRY_DELAYS, start=1):
        waits = {webhooks.backoff(f"msg_{n}", attempts) for n in range(50)}
        assert all(datetime.timedelta(0) <= wait <= ceiling for wait in waits)
        assert len(waits) > 40
    assert webhooks.backoff("msg_x", 3) == webhooks.backoff("msg_x", 3)
    total = sum(webhooks.RETRY_DELAYS, datetime.timedelta())
    assert datetime.timedelta(hours=20) < total < datetime.timedelta(hours=30)


def test_each_attempt_records_what_came_back(client, db, seed_users, feed_on, host_clock, receiver):
    headers = _admin(client)
    created = _subscribe(client, headers)
    _room(client, headers, "LH-201")
    receiver.answer = 500
    _step()

    res = client.get(f"/api/v1/webhooks/{created['id']}/deliveries", headers=headers)
    assert res.status_code == 200, res.text
    assert res.headers["X-Total-Count"] == "1"
    (delivery,) = res.json()
    assert delivery["status"] == "pending"
    assert delivery["attempt_count"] == 1
    (attempt,) = delivery["attempts"]
    assert attempt["status_code"] == 500
    assert attempt["error"] == "HTTP 500"
    assert attempt["response_excerpt"] == "noted"
    assert attempt["response_ms"] >= 0


# -- Which URLs may be called --------------------------------------------------


@pytest.mark.parametrize(
    "url",
    [
        "https://127.0.0.1/hooks",
        "https://10.0.0.5/hooks",
        "https://169.254.169.254/latest/meta-data",
        "https://[::1]/hooks",
        "https://[::ffff:127.0.0.1]/hooks",
        "https://[fe80::1]/hooks",
        "https://192.168.1.10/hooks",
        "https://0.0.0.0/hooks",
        "https://224.0.0.1/hooks",
    ],
)
def test_addresses_outside_the_public_internet_are_refused(feed_on, url):
    with pytest.raises(webhooks.Refused):
        webhooks.vet(url)


def test_a_name_that_resolves_to_a_private_address_is_refused(feed_on, monkeypatch):
    monkeypatch.setattr(webhooks, "resolve", lambda host, port: ["10.1.2.3"])
    with pytest.raises(webhooks.Refused, match="10.1.2.3"):
        webhooks.vet(URL)


def test_one_private_address_among_public_ones_refuses_the_name(feed_on, monkeypatch):
    monkeypatch.setattr(webhooks, "resolve", lambda host, port: [PUBLIC_ADDRESS, "127.0.0.1"])
    with pytest.raises(webhooks.Refused):
        webhooks.vet(URL)


def test_a_name_that_does_not_resolve_is_refused(feed_on, monkeypatch):
    def nothing(host, port):
        raise OSError("no such name")

    monkeypatch.setattr(webhooks, "resolve", nothing)
    with pytest.raises(webhooks.Refused, match="does not resolve"):
        webhooks.vet(URL)


@pytest.mark.parametrize(
    "url",
    ["ftp://receiver.test/hooks", "https://user:pass@receiver.test/hooks", "https:///hooks"],
)
def test_other_schemes_credentials_and_missing_hosts_are_refused(feed_on, receiver, url):
    with pytest.raises(webhooks.Refused):
        webhooks.vet(url)


def test_plain_http_is_refused_unless_the_host_is_listed(feed_on, receiver, monkeypatch):
    with pytest.raises(webhooks.Refused, match="WEBHOOK_ALLOW_HTTP_HOSTS"):
        webhooks.vet("http://receiver.test/hooks")
    monkeypatch.setenv("WEBHOOK_ALLOW_HTTP_HOSTS", "Receiver.test, other.test")
    get_settings.cache_clear()
    target = webhooks.vet("http://receiver.test/hooks")
    assert target.address == PUBLIC_ADDRESS
    assert target.port == 80


def test_the_private_setting_allows_loopback(feed_on, monkeypatch):
    with pytest.raises(webhooks.Refused):
        webhooks.vet("http://127.0.0.1:8080/hooks")
    monkeypatch.setenv("WEBHOOK_ALLOW_HTTP_HOSTS", "127.0.0.1")
    monkeypatch.setenv("WEBHOOK_ALLOW_PRIVATE_TARGETS", "true")
    get_settings.cache_clear()
    target = webhooks.vet("http://127.0.0.1:8080/hooks")
    assert target.address_url == "http://127.0.0.1:8080/hooks"
    # Never an address no receiver can be at, whatever the setting.
    with pytest.raises(webhooks.Refused):
        webhooks.vet("https://0.0.0.0/hooks")


def test_a_loopback_subscription_is_refused_by_the_api(client, db, seed_users, feed_on):
    headers = _admin(client)
    res = client.post(
        "/api/v1/webhooks/",
        json={"url": "https://127.0.0.1/hooks", "event_types": EVERYTHING},
        headers=headers,
    )
    assert res.status_code == 422
    assert res.json()["code"] == "WEBHOOK_URL_REFUSED"
    assert db.query(WebhookSubscription).count() == 0


def test_an_update_to_a_refused_url_changes_nothing(client, db, seed_users, feed_on, receiver):
    headers = _admin(client)
    created = _subscribe(client, headers)
    res = client.patch(
        f"/api/v1/webhooks/{created['id']}",
        json={"url": "https://10.0.0.1/hooks"},
        headers=headers,
    )
    assert res.status_code == 422
    assert res.json()["code"] == "WEBHOOK_URL_REFUSED"
    assert client.get(f"/api/v1/webhooks/{created['id']}", headers=headers).json()["url"] == URL


def test_a_redirect_is_not_followed_and_counts_as_a_failure(
    client, db, seed_users, feed_on, host_clock, receiver
):
    headers = _admin(client)
    _subscribe(client, headers)
    _room(client, headers, "LH-201")
    receiver.answer = 302
    receiver.headers = {"Location": "http://127.0.0.1/steal"}
    _step()

    assert len(receiver.seen) == 1
    (delivery,) = _deliveries(db)
    assert delivery.status == webhooks.PENDING
    (attempt,) = client.get(
        f"/api/v1/webhooks/{delivery.subscription_id}/deliveries", headers=headers
    ).json()[0]["attempts"]
    assert attempt["status_code"] == 302
    assert attempt["error"] == "redirect not followed"


def test_every_attempt_checks_the_address_again(
    client, db, seed_users, feed_on, host_clock, receiver, monkeypatch
):
    headers = _admin(client)
    _subscribe(client, headers)
    _room(client, headers, "LH-201")
    monkeypatch.setattr(webhooks, "resolve", lambda host, port: ["10.9.8.7"])
    _step()

    assert receiver.seen == []
    (delivery,) = _deliveries(db)
    (attempt,) = client.get(
        f"/api/v1/webhooks/{delivery.subscription_id}/deliveries", headers=headers
    ).json()[0]["attempts"]
    assert attempt["status_code"] is None
    assert attempt["error"].startswith("refused: ")


# -- Secrets -------------------------------------------------------------------


def test_the_secret_is_shown_by_create_and_rotate_only(client, db, seed_users, feed_on, receiver):
    headers = _admin(client)
    created = _subscribe(client, headers)
    assert created["secret"].startswith("whsec_")
    assert len(base64.b64decode(created["secret"].removeprefix("whsec_"))) == 32
    base = f"/api/v1/webhooks/{created['id']}"

    for res in (
        client.get("/api/v1/webhooks/", headers=headers),
        client.get(base, headers=headers),
        client.patch(base, json={"event_types": ["resource.created"]}, headers=headers),
        client.post(f"{base}/resume", headers=headers),
    ):
        assert res.status_code == 200, res.text
        assert created["secret"] not in res.text
        assert 'secret"' not in res.text.replace("previous_secret_expires_at", "")

    rotated = client.post(f"{base}/rotate-secret", headers=headers)
    assert rotated.status_code == 200, rotated.text
    assert rotated.json()["secret"].startswith("whsec_")
    assert rotated.json()["secret"] != created["secret"]


def test_rotation_signs_with_both_secrets_for_a_day(
    client, db, seed_users, feed_on, host_clock, receiver
):
    headers = _admin(client)
    created = _subscribe(client, headers)
    base = f"/api/v1/webhooks/{created['id']}"
    rotated = client.post(f"{base}/rotate-secret", headers=headers).json()
    assert rotated["previous_secret_expires_at"] is not None

    again = client.post(f"{base}/rotate-secret", headers=headers)
    assert again.status_code == 409
    assert again.json()["code"] == "WEBHOOK_SECRET_LIMIT"

    _room(client, headers, "LH-201")
    _step()
    hit = receiver.seen[-1]
    assert len(hit["signature"].split(" ")) == 2
    assert verify(created["secret"], hit, hit["at"])
    assert verify(rotated["secret"], hit, hit["at"])

    # A day later the old one has stopped signing on its own.
    _step(minutes=24 * 60)
    _room(client, headers, "LH-202")
    _step()
    hit = receiver.seen[-1]
    assert len(hit["signature"].split(" ")) == 1
    assert verify(rotated["secret"], hit, hit["at"])
    assert not verify(created["secret"], hit, hit["at"])
    assert client.get(base, headers=headers).json()["previous_secret_expires_at"] is None


def test_removing_the_previous_secret_stops_it_signing(
    client, db, seed_users, feed_on, host_clock, receiver
):
    headers = _admin(client)
    created = _subscribe(client, headers)
    base = f"/api/v1/webhooks/{created['id']}"
    rotated = client.post(f"{base}/rotate-secret", headers=headers).json()
    assert client.delete(f"{base}/previous-secret", headers=headers).status_code == 204
    assert client.delete(f"{base}/previous-secret", headers=headers).status_code == 204

    _room(client, headers, "LH-201")
    _step()
    hit = receiver.seen[-1]
    assert verify(rotated["secret"], hit, hit["at"])
    assert not verify(created["secret"], hit, hit["at"])
    # And a rotation is allowed again.
    assert client.post(f"{base}/rotate-secret", headers=headers).status_code == 200


def test_the_signature_matches_the_standard_webhooks_example():
    # The worked example from the Standard Webhooks specification's
    # reference libraries, so our signer and the test's verifier are checked
    # against a third party and not only against each other.
    secret = "whsec_MfKQ9r8GKYqrTwjUPD8ILPZIo2LaLaSw"
    body = b'{"test": 2432232314}'
    signature = webhooks.sign(secret, "msg_p5jXN8AQM9LWM0D4loKWxJek", 1614265330, body)
    assert signature == "v1,g0hM9SsE+OTPJTGt/tmIKtSyZlE3uFJELVlNIOLJ1OE="


# -- Who may, and when ---------------------------------------------------------


def test_webhooks_are_for_org_admins(client, db, seed_users, feed_on):
    assert client.get("/api/v1/webhooks/").status_code == 401
    staff = login(client, "staff@test.internal", STAFF_PASSWORD)
    res = client.get("/api/v1/webhooks/", headers=staff)
    assert res.status_code == 403
    res = client.post(
        "/api/v1/webhooks/", json={"url": URL, "event_types": EVERYTHING}, headers=staff
    )
    assert res.status_code == 403


def test_a_subscription_needs_the_change_feed(client, db, seed_users, receiver):
    res = client.post(
        "/api/v1/webhooks/", json={"url": URL, "event_types": EVERYTHING}, headers=_admin(client)
    )
    assert res.status_code == 503
    assert res.json()["code"] == "CHANGE_FEED_DISABLED"


def test_unknown_event_types_are_refused(client, db, seed_users, feed_on, receiver):
    res = client.post(
        "/api/v1/webhooks/",
        json={"url": URL, "event_types": ["ledger.updated"]},
        headers=_admin(client),
    )
    assert res.status_code == 422
    assert res.json()["code"] == "VALIDATION_FAILED"


def test_deleting_a_subscription_takes_its_deliveries(
    client, db, seed_users, feed_on, host_clock, receiver
):
    headers = _admin(client)
    created = _subscribe(client, headers)
    _room(client, headers, "LH-201")
    _step()
    assert len(_deliveries(db)) == 1
    res = client.delete(f"/api/v1/webhooks/{created['id']}", headers=headers)
    assert res.status_code == 204
    assert _deliveries(db) == []
    assert client.get(f"/api/v1/webhooks/{created['id']}", headers=headers).status_code == 404


def test_the_worker_is_not_scheduled_while_the_feed_is_off(host_clock):
    ran = _step()
    assert "webhook_delivery" not in ran


def test_the_worker_runs_on_every_advance_with_the_feed_on(feed_on, host_clock):
    assert _step() == ["webhook_delivery"]
