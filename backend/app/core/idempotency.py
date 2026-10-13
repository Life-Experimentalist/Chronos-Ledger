# Copyright 2026 Chronos Ledger Contributors
# Licensed under the Apache License, Version 2.0
"""Idempotency-Key on every write under /api/v1.

A caller that sends a write and loses the response cannot tell whether it
happened. With an Idempotency-Key it sends the same request again under the
same key and gets the first response back, with Idempotency-Replayed: true,
instead of a second effect. The same key with a different request is
refused with 409 IDEMPOTENCY_KEY_REUSED, and a retry that arrives while the
first is still running gets 409 IDEMPOTENCY_KEY_IN_PROGRESS.

Two pieces, because neither place can do the whole job alone.

IdempotencyMiddleware is a plain ASGI middleware. It reads the body to hash
the request, and it sees every message the application sends, so what it
records is the response that actually went out, byte for byte, whatever the
route returned and whatever an exception handler made of it. A dependency
sees neither the raw body (get_current_user_id is a sync function) nor the
response.

claim() runs inside get_current_user_id, and inside host_actor in the
embedded app, once the caller is known and allowed in. It writes the claim
through the request's own get_db session, so the claim commits in the same
transaction as the handler's effect, and a request that never got past
authentication never claims anything. Middleware alone would have to commit
the claim in a session of its own, ahead of the handler, and could not tell
who the caller was.

What is stored, by the status that went out:
  2xx                 stored and replayed.
  4xx                 stored and replayed: the request ran and was refused,
                      and the same request will be refused the same way.
  401, 403, 429       never stored. They say who may ask, not what happened,
                      and a retry after signing in again or waiting should run.
  5xx, or an          never stored, and the claim is dropped, so a retry runs
  exception           the request again.
Errors this module raises itself (the key is malformed, reused, or in use)
are never stored either: nothing ran.

The window: the handler commits the claim with its effect, and the response
is recorded after it has been sent, in a separate session. A process that
stops between the two leaves a claim with no response, and a retry under
that key gets 409 IDEMPOTENCY_KEY_IN_PROGRESS until the record expires. That
errs towards no duplicate. A handler that commits through some other session
is not atomic with the claim, and a 5xx after a committed effect drops the
claim, so a retry of that one runs again.

Concurrent first uses are settled by the unique constraint on (caller, key).
On PostgreSQL the second insert waits for the first transaction and then
fails, and the loser answers from the row it then finds. On SQLite every
write transaction starts with BEGIN IMMEDIATE, so the second request waits
before it reads anything and finds the first one's claim committed.

The query string is part of the request hash, sorted: generate-ledger and
upload-csv carry what they act on there, and the same key sent with a
different target_date is a different request. A multipart body (the CSV
upload) is not buffered or hashed, and the key is ignored: the upload is
streamed to disk and is already idempotent by its content. A streamed
response is recorded whole, as it is sent.
"""

from __future__ import annotations

import hashlib
import json
import logging
from dataclasses import dataclass
from datetime import UTC, timedelta
from urllib.parse import parse_qsl, urlencode

from fastapi import Request, status
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session
from starlette.concurrency import run_in_threadpool

from app.core import clock
from app.core.audit import AUDITED_PREFIX, READ_METHODS
from app.core.config import get_settings
from app.core.database import get_session_opener
from app.core.errors import ChronosError, ErrorCode

logger = logging.getLogger(__name__)

KEY_HEADER = b"idempotency-key"
REPLAYED_HEADER = "Idempotency-Replayed"
KEY_LIMIT = 255
KEY_REUSED = "that Idempotency-Key was used for a different request"
KEY_IN_PROGRESS = "a request with that Idempotency-Key is still running, retry shortly"
KEY_MALFORMED = f"Idempotency-Key must be 1 to {KEY_LIMIT} printable ASCII characters"

# The response headers a replay sends again. The rest are made fresh.
KEPT_HEADERS = frozenset({b"content-type", b"location"})

# Statuses that say who may ask rather than what happened. Never stored.
UNSTORED_CLIENT_ERRORS = frozenset({401, 403, 429})

# Reservation create had its own key before this module existed, and keeps
# what it answered then: 422 for a reused key, and a retry answered from the
# reservation as it is now (cancelled or not) rather than replayed from here.
# Moving it to 409 is a breaking change for the next minor release.
OWN_REPLAY_OPERATIONS = frozenset({"resources.createReservation"})

# Writes whose response carries a credential that is stored nowhere else, or
# only as a hash: a password, an API key, a feed token, a visit code, a fresh
# pair of tokens. Keeping the response to replay it would keep the secret, so
# these ignore the key and a retry runs again.
SECRET_OPERATIONS = frozenset(
    {
        "auth.changePassword",
        "users.resetPassword",
        "apiKeys.create",
        "sync.rotateFeedToken",
        "guest.checkIn",
    }
)


@dataclass
class Pending:
    """One keyed write, from the middleware to claim() and back."""

    key: str
    request_hash: str
    caller: str | None = None
    owner: bool = False
    own_replay: bool = False


class Replay(Exception):
    """Raised by claim() to stop the request and send the stored response.

    Not an HTTPException, so no exception handler turns it into an error
    response on the way out: it reaches IdempotencyMiddleware as it is.
    """

    def __init__(self, status_code: int, headers: dict[str, str], body: bytes) -> None:
        super().__init__(status_code)
        self.status_code = status_code
        self.headers = headers
        self.body = body


def request_hash(method: str, path: str, query_string: bytes, body: bytes) -> str:
    """sha256 of the method, path, sorted query string and canonical body.

    A JSON body is hashed in a canonical form, so key order and spacing do
    not make a retry look like a different request. Anything else is hashed
    as it came.
    """
    query = urlencode(sorted(parse_qsl(query_string.decode("latin-1"), keep_blank_values=True)))
    try:
        canonical = json.dumps(
            json.loads(body), sort_keys=True, separators=(",", ":"), ensure_ascii=False
        ).encode()
    except ValueError:
        canonical = body
    digest = hashlib.sha256()
    for part in (method.encode(), path.encode(), query.encode(), canonical):
        digest.update(part)
        digest.update(b"\n")
    return digest.hexdigest()


def key_is_valid(key: str) -> bool:
    return 1 <= len(key) <= KEY_LIMIT and all(" " <= char <= "~" for char in key)


def storable(status_code: int) -> bool:
    if 200 <= status_code < 300:
        return True
    return 400 <= status_code < 500 and status_code not in UNSTORED_CLIENT_ERRORS


def retention() -> timedelta:
    return timedelta(hours=get_settings().idempotency_retention_hours)


def claim(request: Request, db: Session, caller: str) -> None:
    """Claim this request's key for the caller, or answer it from an earlier one.

    Called once the caller is authenticated. Does nothing for a request the
    middleware did not mark (no key, a read, a multipart upload). Raises
    Replay when the same request already has a stored response, and
    ChronosError when the key is malformed, reused or still in use.
    """
    from app.models.db import IdempotencyRecord

    pending = getattr(request.state, "idempotency", None)
    if pending is None or pending.caller is not None:
        return
    operation = getattr(request.scope.get("route"), "operation_id", None)
    if operation in SECRET_OPERATIONS:
        return
    if not key_is_valid(pending.key):
        raise ChronosError(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
            detail=KEY_MALFORMED,
            code=ErrorCode.INVALID_VALUE,
        )
    pending.caller = caller
    pending.own_replay = operation in OWN_REPLAY_OPERATIONS

    row = _find(db, caller, pending.key)
    if row is not None and _expired(row):
        # Past the window the key is new again. Deleted and claimed afresh
        # rather than updated, so two retries racing for an expired key are
        # settled by the unique constraint like any other first use.
        db.delete(row)
        db.flush()
        row = None
    if row is not None:
        _answer(row, pending)
        return

    try:
        with db.begin_nested():
            db.add(
                IdempotencyRecord(
                    caller=caller,
                    key=pending.key,
                    request_hash=pending.request_hash,
                    created_at=clock.now(),
                )
            )
    except IntegrityError:
        row = _find(db, caller, pending.key)
        if row is None:
            # The other request let go of the key between its insert and
            # this lookup. Rare, and a retry will find it free.
            raise _in_progress() from None
        _answer(row, pending)
        return
    pending.owner = True


def _find(db: Session, caller: str, key: str):
    from app.models.db import IdempotencyRecord

    return (
        db.query(IdempotencyRecord)
        .filter(IdempotencyRecord.caller == caller, IdempotencyRecord.key == key)
        .first()
    )


def _expired(row) -> bool:
    created_at = row.created_at if row.created_at.tzinfo else row.created_at.replace(tzinfo=UTC)
    return created_at <= clock.now() - retention()


def _in_progress() -> ChronosError:
    return ChronosError(
        status_code=status.HTTP_409_CONFLICT,
        detail=KEY_IN_PROGRESS,
        code=ErrorCode.IDEMPOTENCY_KEY_IN_PROGRESS,
        headers={"Retry-After": "1"},
    )


def _answer(row, pending: Pending) -> None:
    """Answer a request whose key already has a row: refuse it, or replay."""
    if row.request_hash != pending.request_hash:
        raise ChronosError(
            status_code=(
                status.HTTP_422_UNPROCESSABLE_CONTENT
                if pending.own_replay
                else status.HTTP_409_CONFLICT
            ),
            detail=KEY_REUSED,
            code=ErrorCode.IDEMPOTENCY_KEY_REUSED,
        )
    if pending.own_replay:
        # The route answers the retry from its own row.
        return
    if row.status_code is None:
        raise _in_progress()
    raise Replay(
        row.status_code, json.loads(row.response_headers or "{}"), row.response_body or b""
    )


def purge_expired(db: Session) -> int:
    """Delete every record older than the retention window; return the count."""
    from app.models.db import IdempotencyRecord

    purged = (
        db.query(IdempotencyRecord)
        .filter(IdempotencyRecord.created_at < clock.now() - retention())
        .delete(synchronize_session=False)
    )
    db.commit()
    return purged


class IdempotencyMiddleware:
    """Hashes keyed writes, records what they sent, and sends replays.

    Added innermost, so the body it records has not been compressed yet and
    carries no CORS headers, and a replay goes out through the same
    compression, audit and CORS as any other response.
    """

    def __init__(self, app):
        self.app = app

    async def __call__(self, scope, receive, send):
        if (
            scope["type"] != "http"
            or scope["method"] in READ_METHODS
            or not scope["path"].startswith(AUDITED_PREFIX)
        ):
            await self.app(scope, receive, send)
            return
        key = _header(scope, KEY_HEADER)
        if key is None or (_header(scope, b"content-type") or "").startswith("multipart/"):
            await self.app(scope, receive, send)
            return

        body, receive = await _buffered(receive)
        if body is None:
            return
        pending = Pending(
            key, request_hash(scope["method"], scope["path"], scope.get("query_string", b""), body)
        )
        scope.setdefault("state", {})["idempotency"] = pending

        sent = {"status": None, "headers": [], "body": [], "complete": False}

        async def send_and_keep(message):
            if message["type"] == "http.response.start":
                sent["status"] = message["status"]
                sent["headers"] = message.get("headers", [])
            elif message["type"] == "http.response.body":
                sent["body"].append(message.get("body", b""))
                if not message.get("more_body", False):
                    sent["complete"] = True
            await send(message)

        try:
            await self.app(scope, receive, send_and_keep)
        except Replay as replay:
            await _send_replay(send, replay)
            return
        except Exception:
            if pending.owner:
                await run_in_threadpool(_settle, scope, pending, sent)
            raise
        if pending.owner:
            await run_in_threadpool(_settle, scope, pending, sent)


def _header(scope, name: bytes) -> str | None:
    for header, value in scope.get("headers", []):
        if header.lower() == name:
            return value.decode("latin-1")
    return None


async def _buffered(receive):
    """Read the whole body, and a receive that hands it to the app again."""
    chunks = []
    while True:
        message = await receive()
        if message["type"] == "http.disconnect":
            return None, receive
        chunks.append(message.get("body", b""))
        if not message.get("more_body", False):
            break
    body = b"".join(chunks)
    replayed = False

    async def receive_again():
        nonlocal replayed
        if not replayed:
            replayed = True
            return {"type": "http.request", "body": body, "more_body": False}
        return await receive()

    return body, receive_again


async def _send_replay(send, replay: Replay) -> None:
    headers = [
        (name.encode("latin-1"), value.encode("latin-1")) for name, value in replay.headers.items()
    ]
    if replay.status_code not in (204, 304):
        # Starlette sends no Content-Length on these, so neither does a replay.
        headers.append((b"content-length", str(len(replay.body)).encode()))
    headers.append((REPLAYED_HEADER.lower().encode(), b"true"))
    await send({"type": "http.response.start", "status": replay.status_code, "headers": headers})
    await send({"type": "http.response.body", "body": replay.body, "more_body": False})


def _settle(scope, pending: Pending, sent: dict) -> None:
    """Record the response this request sent, or let go of its claim.

    In a session of its own, after the response: the request's session is
    closed by now. A failure is logged and nothing more, as the audit write
    does, since the response has already gone.
    """
    from app.models.db import IdempotencyRecord

    # The opener the tests substitute is the one used here, as in audit.py.
    app = scope.get("app")
    overrides = getattr(app, "dependency_overrides", {}) if app is not None else {}
    opener = overrides.get(get_session_opener, get_session_opener)()
    try:
        with opener() as db:
            row = _find(db, pending.caller, pending.key)
            if row is not None and row.request_hash != pending.request_hash:
                # Somebody else's claim, after ours expired. Leave it.
                return
            if sent["complete"] and storable(sent["status"]):
                if row is None:
                    row = IdempotencyRecord(
                        caller=pending.caller,
                        key=pending.key,
                        request_hash=pending.request_hash,
                        created_at=clock.now(),
                    )
                    db.add(row)
                kept = {
                    name.decode("latin-1"): value.decode("latin-1")
                    for name, value in sent["headers"]
                    if name.lower() in KEPT_HEADERS
                }
                row.status_code = sent["status"]
                row.response_headers = json.dumps(kept, sort_keys=True)
                row.response_body = b"".join(sent["body"])
            elif row is not None and row.status_code is None:
                db.delete(row)
            db.commit()
    except Exception:
        logger.exception(
            "Could not record the response to %s %s for its Idempotency-Key",
            scope["method"],
            scope["path"],
        )
