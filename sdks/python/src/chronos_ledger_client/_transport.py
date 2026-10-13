# Copyright 2026 Chronos Ledger Contributors
# SPDX-License-Identifier: Apache-2.0
"""The httpx transport under the generated client: auth, retries and errors."""

from __future__ import annotations

import email.utils
import random
import threading
import time
import uuid
from collections.abc import Callable
from dataclasses import dataclass
from typing import Any

import httpx

RETRY_STATUSES = frozenset({429, 502, 503, 504})
#: The code of a 409 that says the first request under this key is still running.
IN_PROGRESS_CODE = "IDEMPOTENCY_KEY_IN_PROGRESS"
#: Methods that change nothing. Every other method is a write and goes out with an Idempotency-Key.
READ_METHODS = frozenset({"GET", "HEAD", "OPTIONS"})
#: Failures where no response arrived: a refused or dropped connection, a timeout.
NO_RESPONSE_ERRORS = (httpx.TimeoutException, httpx.NetworkError, httpx.RemoteProtocolError)


@dataclass(frozen=True)
class RetryPolicy:
    """How a failed request is tried again. Pass ``retry=None`` to ``connect`` for no retries."""

    #: Tries in all, the first one included.
    max_attempts: int = 4
    #: Seconds. The wait before retry ``n`` is random between 0 and ``base_delay * 2**n``.
    base_delay: float = 0.25
    #: Seconds. The most any one jittered wait can reach.
    max_delay: float = 8.0
    #: Seconds from the first send. No retry starts a wait that would run past it.
    deadline: float = 30.0

    def __post_init__(self) -> None:
        if self.max_attempts < 1:
            raise ValueError("max_attempts must be at least 1")
        if min(self.base_delay, self.max_delay, self.deadline) < 0:
            raise ValueError("delays and the deadline cannot be negative")

    def jitter(self, attempt: int, rng: Callable[[], float]) -> float:
        """Full jitter: a random wait between 0 and the capped exponential step."""
        return rng() * min(self.max_delay, self.base_delay * 2**attempt)


@dataclass(frozen=True)
class Tokens:
    """An access token and the single-use refresh token that came with it."""

    access_token: str
    refresh_token: str


#: What ``connect`` uses when no policy is given.
DEFAULT_RETRY = RetryPolicy()


class ChronosError(Exception):
    """Every response with status 400 or above, after retries and a token refresh."""

    def __init__(self, status: int, detail: Any, code: str | None = None) -> None:
        self.status = status
        #: ``detail`` exactly as the server returned it: a string, or a dict for a 409.
        self.detail = detail
        #: The server's code for what went wrong, such as ``"EMAIL_TAKEN"``, for
        #: a program to branch on. A plain string rather than the generated
        #: ErrorCode, so a code added after this client was built still arrives.
        #: None when the body had no code, for example a proxy's error page.
        self.code = code
        found = detail.get("conflicts") if isinstance(detail, dict) else None
        #: The clashing intervals of a 409, or an empty list.
        self.conflicts: list[dict[str, Any]] = found if isinstance(found, list) else []
        if isinstance(detail, str):
            message = f"{status}: {detail}"
        elif isinstance(detail, dict) and isinstance(detail.get("message"), str):
            message = f"{status}: {detail['message']}"
        else:
            message = f"HTTP {status}"
        super().__init__(message)

    @classmethod
    def from_response(cls, response: httpx.Response) -> ChronosError:
        text = response.read().decode("utf-8", "replace")
        try:
            body = response.json()
        except ValueError:
            return cls(response.status_code, text or None)
        detail = body["detail"] if isinstance(body, dict) and "detail" in body else body
        code = body.get("code") if isinstance(body, dict) else None
        return cls(response.status_code, detail, code if isinstance(code, str) else None)


def retry_after(response: httpx.Response) -> float | None:
    """Seconds from a Retry-After header, given in seconds or as an HTTP date."""
    value = response.headers.get("Retry-After")
    if not value:
        return None
    try:
        return max(0.0, float(value))
    except ValueError:
        pass
    try:
        when = email.utils.parsedate_to_datetime(value)
    except (TypeError, ValueError):
        return None
    return max(0.0, when.timestamp() - time.time())


class ChronosTransport(httpx.BaseTransport):
    def __init__(
        self,
        *,
        base_url: str,
        user_agent: str,
        api_key: str | None = None,
        tokens: Tokens | None = None,
        on_tokens: Callable[[Tokens], None] | None = None,
        retry: RetryPolicy | None = None,
        inner: httpx.BaseTransport | None = None,
        sleep: Callable[[float], None] = time.sleep,
        clock: Callable[[], float] = time.monotonic,
        rng: Callable[[], float] = random.random,
    ) -> None:
        self._base_url = base_url
        self._user_agent = user_agent
        self._api_key = api_key
        self._tokens = tokens
        self._on_tokens = on_tokens
        self._retry = retry
        self._inner = inner or httpx.HTTPTransport()
        self._sleep = sleep
        self._clock = clock
        self._rng = rng
        # A refresh token is spent on first use, so threads that see a 401
        # together must not each refresh.
        self._lock = threading.Lock()

    def _authorize(self, request: httpx.Request) -> None:
        request.headers["User-Agent"] = self._user_agent
        if self._api_key:
            request.headers["X-API-Key"] = self._api_key
        elif self._tokens:
            request.headers["Authorization"] = f"Bearer {self._tokens.access_token}"

    def _refresh(self, sent_with: Tokens) -> bool:
        with self._lock:
            if self._tokens is not sent_with:
                return True  # another thread already refreshed
            request = httpx.Request(
                "POST",
                f"{self._base_url}/api/v1/auth/refresh",
                headers={"User-Agent": self._user_agent},
                json={"refresh_token": sent_with.refresh_token},
            )
            response = self._inner.handle_request(request)
            response.read()
            if response.status_code != 200:
                return False
            body = response.json()
            self._tokens = Tokens(body["access_token"], body["refresh_token"])
            if self._on_tokens:
                self._on_tokens(self._tokens)
            return True

    def _wait_for(self, attempt: int, response: httpx.Response | None, started: float) -> float | None:
        """Seconds to sleep before the next try, or None when this failure is final."""
        policy = self._retry
        if policy is None or attempt + 1 >= policy.max_attempts:
            return None
        wait = retry_after(response) if response is not None else None
        if wait is None:
            wait = policy.jitter(attempt, self._rng)
        if self._clock() + wait - started > policy.deadline:
            return None
        return wait

    def handle_request(self, request: httpx.Request) -> httpx.Response:
        request.read()
        # One key for the whole call, so every try of a write is the same write.
        if request.method not in READ_METHODS and "Idempotency-Key" not in request.headers:
            request.headers["Idempotency-Key"] = str(uuid.uuid4())
        started = self._clock()
        refreshed = False
        attempt = 0
        while True:
            sent_with = self._tokens
            self._authorize(request)
            try:
                response = self._inner.handle_request(request)
            except NO_RESPONSE_ERRORS:
                wait = self._wait_for(attempt, None, started)
                if wait is None:
                    raise
                self._sleep(wait)
                attempt += 1
                continue

            if response.status_code == 401 and sent_with and not self._api_key and not refreshed:
                refreshed = True
                if self._refresh(sent_with):
                    response.close()
                    continue
            if response.status_code < 400:
                return response
            error = ChronosError.from_response(response)
            response.close()
            if response.status_code in RETRY_STATUSES or error.code == IN_PROGRESS_CODE:
                wait = self._wait_for(attempt, response, started)
                if wait is not None:
                    self._sleep(wait)
                    attempt += 1
                    continue
            raise error

    def close(self) -> None:
        self._inner.close()
