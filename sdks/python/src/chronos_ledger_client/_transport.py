# Copyright 2026 Chronos Ledger Contributors
# SPDX-License-Identifier: Apache-2.0
"""The httpx transport under the generated client: auth, retries and errors."""

from __future__ import annotations

import email.utils
import threading
import time
from collections.abc import Callable
from dataclasses import dataclass
from typing import Any

import httpx

RETRY_STATUSES = frozenset({429, 502, 503, 504})
IDEMPOTENT_METHODS = frozenset({"GET", "HEAD", "PUT", "DELETE", "OPTIONS"})
MAX_DELAY = 30.0


@dataclass(frozen=True)
class Tokens:
    """An access token and the single-use refresh token that came with it."""

    access_token: str
    refresh_token: str


class ChronosError(Exception):
    """Every response with status 400 or above, after retries and a token refresh."""

    def __init__(self, status: int, detail: Any) -> None:
        self.status = status
        #: ``detail`` exactly as the server returned it: a string, or a dict for a 409.
        self.detail = detail
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
        return cls(response.status_code, detail)


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
        max_retries: int = 3,
        inner: httpx.BaseTransport | None = None,
        sleep: Callable[[float], None] = time.sleep,
    ) -> None:
        self._base_url = base_url
        self._user_agent = user_agent
        self._api_key = api_key
        self._tokens = tokens
        self._on_tokens = on_tokens
        self._max_retries = max_retries
        self._inner = inner or httpx.HTTPTransport()
        self._sleep = sleep
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

    def handle_request(self, request: httpx.Request) -> httpx.Response:
        request.read()
        retryable = request.method in IDEMPOTENT_METHODS or "Idempotency-Key" in request.headers
        refreshed = False
        attempt = 0
        while True:
            sent_with = self._tokens
            self._authorize(request)
            try:
                response = self._inner.handle_request(request)
            except httpx.TransportError:
                if not retryable or attempt >= self._max_retries:
                    raise
                self._sleep(_backoff(attempt))
                attempt += 1
                continue

            if response.status_code == 401 and sent_with and not self._api_key and not refreshed:
                refreshed = True
                if self._refresh(sent_with):
                    response.close()
                    continue
            if response.status_code in RETRY_STATUSES and retryable and attempt < self._max_retries:
                wait = retry_after(response)
                wait = _backoff(attempt) if wait is None else wait
                if wait <= MAX_DELAY:
                    response.close()
                    self._sleep(wait)
                    attempt += 1
                    continue
            if response.status_code >= 400:
                try:
                    raise ChronosError.from_response(response)
                finally:
                    response.close()
            return response

    def close(self) -> None:
        self._inner.close()


def _backoff(attempt: int) -> float:
    return min(0.5 * 2**attempt, 8.0)
