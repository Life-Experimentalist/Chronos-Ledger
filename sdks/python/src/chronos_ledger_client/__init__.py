# Copyright 2026 Chronos Ledger Contributors
# SPDX-License-Identifier: Apache-2.0
"""Typed client for the Chronos Ledger REST API.

The calls themselves are generated from docs/openapi.yaml and live in
``chronos_ledger_client.generated.api``. This module adds what a generator
cannot know: how to authenticate, when a retry is safe, and how to page.
"""

from __future__ import annotations

import uuid
from collections.abc import Callable, Iterator
from typing import Any

import httpx

from ._transport import ChronosError, ChronosTransport, Tokens
from .generated import Client
from .generated.api.resources import resources_create_reservation
from .generated.models import ReservationCreate, ReservationResponse

__version__ = "0.12.0"  # x-release-please-version

__all__ = [
    "ChronosError",
    "Client",
    "Tokens",
    "__version__",
    "connect",
    "create_reservation",
    "paginate",
]


def connect(
    base_url: str,
    *,
    api_key: str | None = None,
    tokens: Tokens | None = None,
    on_tokens: Callable[[Tokens], None] | None = None,
    max_retries: int = 3,
    timeout: float = 30.0,
    transport: httpx.BaseTransport | None = None,
) -> Client:
    """A client for the server at ``base_url``, for example ``https://chronos.example.org``.

    Pass ``api_key`` for a scoped API key, or ``tokens`` from ``POST /api/v1/auth/login``.
    Tokens are refreshed once on a 401 and each new pair goes to ``on_tokens``,
    because a refresh token works only once. ``transport`` replaces the network,
    which is how the tests run.
    """
    if api_key and tokens:
        raise ValueError("pass api_key or tokens, not both")
    base_url = base_url.rstrip("/").removesuffix("/api/v1")
    return Client(
        base_url=base_url,
        timeout=httpx.Timeout(timeout),
        raise_on_unexpected_status=True,
        httpx_args={
            "transport": ChronosTransport(
                base_url=base_url,
                user_agent=f"chronos-python/{__version__}",
                api_key=api_key,
                tokens=tokens,
                on_tokens=on_tokens,
                max_retries=max_retries,
                inner=transport,
            )
        },
    )


def create_reservation(
    client: Client,
    resource_id: int,
    body: ReservationCreate,
    idempotency_key: str | None = None,
) -> ReservationResponse:
    """Hold a resource.

    An Idempotency-Key is made when none is given, and the same key goes out on
    every retry, so a retry never takes a second hold.
    """
    result = resources_create_reservation.sync(
        resource_id,
        client=client,
        body=body,
        idempotency_key=idempotency_key or str(uuid.uuid4()),
    )
    assert isinstance(result, ReservationResponse)
    return result


def paginate(operation: Any, *, client: Client, page_size: int = 100, **kwargs: Any) -> Iterator[Any]:
    """Every row of a list route, fetched ``page_size`` at a time.

    ``operation`` is a generated module, for example
    ``paginate(users_list, client=client, role=InstitutionalRole.STAFF)``.
    The walk ends once ``X-Total-Count`` rows have been seen, or when a page
    comes back empty.
    """
    offset = 0
    while True:
        response = operation.sync_detailed(client=client, limit=page_size, offset=offset, **kwargs)
        rows = response.parsed or []
        yield from rows
        offset += len(rows)
        total = response.headers.get("X-Total-Count")
        if not rows or total is None or offset >= int(total):
            return
