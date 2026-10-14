from http import HTTPStatus
from typing import Any
from urllib.parse import quote

import httpx

from ... import errors
from ...client import AuthenticatedClient, Client
from ...models.error_response import ErrorResponse
from ...models.webhook_response import WebhookResponse
from ...models.webhook_update import WebhookUpdate
from ...types import UNSET, Response, Unset


def _get_kwargs(
    subscription_id: int,
    *,
    body: WebhookUpdate,
    idempotency_key: str | Unset = UNSET,
) -> dict[str, Any]:
    headers: dict[str, Any] = {}
    if not isinstance(idempotency_key, Unset):
        headers["Idempotency-Key"] = idempotency_key

    _kwargs: dict[str, Any] = {
        "method": "patch",
        "url": "/api/v1/webhooks/{subscription_id}".format(
            subscription_id=quote(str(subscription_id), safe=""),
        ),
    }

    _kwargs["json"] = body.to_dict()

    headers["Content-Type"] = "application/json"

    _kwargs["headers"] = headers
    return _kwargs


def _parse_response(
    *, client: AuthenticatedClient | Client, response: httpx.Response
) -> ErrorResponse | WebhookResponse | None:
    if response.status_code == 200:
        response_200 = WebhookResponse.from_dict(response.json())

        return response_200

    if response.status_code == 401:
        response_401 = ErrorResponse.from_dict(response.json())

        return response_401

    if response.status_code == 403:
        response_403 = ErrorResponse.from_dict(response.json())

        return response_403

    if response.status_code == 404:
        response_404 = ErrorResponse.from_dict(response.json())

        return response_404

    if response.status_code == 422:
        response_422 = ErrorResponse.from_dict(response.json())

        return response_422

    if client.raise_on_unexpected_status:
        raise errors.UnexpectedStatus(response.status_code, response.content)
    else:
        return None


def _build_response(
    *, client: AuthenticatedClient | Client, response: httpx.Response
) -> Response[ErrorResponse | WebhookResponse]:
    return Response(
        status_code=HTTPStatus(response.status_code),
        content=response.content,
        headers=response.headers,
        parsed=_parse_response(client=client, response=response),
    )


def sync_detailed(
    subscription_id: int,
    *,
    client: AuthenticatedClient | Client,
    body: WebhookUpdate,
    idempotency_key: str | Unset = UNSET,
) -> Response[ErrorResponse | WebhookResponse]:
    """Change a webhook subscription

     Requires `ORG_ADMIN`; an API key needs `webhooks:write`. New event types apply to changes fanned out
    from now on. Switched off, a subscription keeps its place and sends nothing; switched back on, it
    sends what happened in between.

    Args:
        subscription_id (int):
        idempotency_key (str | Unset):
        body (WebhookUpdate): Only the fields sent are changed.

    Raises:
        errors.UnexpectedStatus: If the server returns an undocumented status code and Client.raise_on_unexpected_status is True.
        httpx.TimeoutException: If the request takes longer than Client.timeout.

    Returns:
        Response[ErrorResponse | WebhookResponse]
    """

    kwargs = _get_kwargs(
        subscription_id=subscription_id,
        body=body,
        idempotency_key=idempotency_key,
    )

    response = client.get_httpx_client().request(
        **kwargs,
    )

    return _build_response(client=client, response=response)


def sync(
    subscription_id: int,
    *,
    client: AuthenticatedClient | Client,
    body: WebhookUpdate,
    idempotency_key: str | Unset = UNSET,
) -> ErrorResponse | WebhookResponse | None:
    """Change a webhook subscription

     Requires `ORG_ADMIN`; an API key needs `webhooks:write`. New event types apply to changes fanned out
    from now on. Switched off, a subscription keeps its place and sends nothing; switched back on, it
    sends what happened in between.

    Args:
        subscription_id (int):
        idempotency_key (str | Unset):
        body (WebhookUpdate): Only the fields sent are changed.

    Raises:
        errors.UnexpectedStatus: If the server returns an undocumented status code and Client.raise_on_unexpected_status is True.
        httpx.TimeoutException: If the request takes longer than Client.timeout.

    Returns:
        ErrorResponse | WebhookResponse
    """

    return sync_detailed(
        subscription_id=subscription_id,
        client=client,
        body=body,
        idempotency_key=idempotency_key,
    ).parsed


async def asyncio_detailed(
    subscription_id: int,
    *,
    client: AuthenticatedClient | Client,
    body: WebhookUpdate,
    idempotency_key: str | Unset = UNSET,
) -> Response[ErrorResponse | WebhookResponse]:
    """Change a webhook subscription

     Requires `ORG_ADMIN`; an API key needs `webhooks:write`. New event types apply to changes fanned out
    from now on. Switched off, a subscription keeps its place and sends nothing; switched back on, it
    sends what happened in between.

    Args:
        subscription_id (int):
        idempotency_key (str | Unset):
        body (WebhookUpdate): Only the fields sent are changed.

    Raises:
        errors.UnexpectedStatus: If the server returns an undocumented status code and Client.raise_on_unexpected_status is True.
        httpx.TimeoutException: If the request takes longer than Client.timeout.

    Returns:
        Response[ErrorResponse | WebhookResponse]
    """

    kwargs = _get_kwargs(
        subscription_id=subscription_id,
        body=body,
        idempotency_key=idempotency_key,
    )

    response = await client.get_async_httpx_client().request(**kwargs)

    return _build_response(client=client, response=response)


async def asyncio(
    subscription_id: int,
    *,
    client: AuthenticatedClient | Client,
    body: WebhookUpdate,
    idempotency_key: str | Unset = UNSET,
) -> ErrorResponse | WebhookResponse | None:
    """Change a webhook subscription

     Requires `ORG_ADMIN`; an API key needs `webhooks:write`. New event types apply to changes fanned out
    from now on. Switched off, a subscription keeps its place and sends nothing; switched back on, it
    sends what happened in between.

    Args:
        subscription_id (int):
        idempotency_key (str | Unset):
        body (WebhookUpdate): Only the fields sent are changed.

    Raises:
        errors.UnexpectedStatus: If the server returns an undocumented status code and Client.raise_on_unexpected_status is True.
        httpx.TimeoutException: If the request takes longer than Client.timeout.

    Returns:
        ErrorResponse | WebhookResponse
    """

    return (
        await asyncio_detailed(
            subscription_id=subscription_id,
            client=client,
            body=body,
            idempotency_key=idempotency_key,
        )
    ).parsed
