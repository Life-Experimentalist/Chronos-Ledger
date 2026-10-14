from http import HTTPStatus
from typing import Any

import httpx

from ... import errors
from ...client import AuthenticatedClient, Client
from ...models.error_response import ErrorResponse
from ...models.link_create import LinkCreate
from ...models.link_response import LinkResponse
from ...types import UNSET, Response, Unset


def _get_kwargs(
    *,
    body: LinkCreate,
    idempotency_key: str | Unset = UNSET,
) -> dict[str, Any]:
    headers: dict[str, Any] = {}
    if not isinstance(idempotency_key, Unset):
        headers["Idempotency-Key"] = idempotency_key

    _kwargs: dict[str, Any] = {
        "method": "post",
        "url": "/api/v1/federation/links",
    }

    _kwargs["json"] = body.to_dict()

    headers["Content-Type"] = "application/json"

    _kwargs["headers"] = headers
    return _kwargs


def _parse_response(
    *, client: AuthenticatedClient | Client, response: httpx.Response
) -> ErrorResponse | LinkResponse | None:
    if response.status_code == 201:
        response_201 = LinkResponse.from_dict(response.json())

        return response_201

    if response.status_code == 401:
        response_401 = ErrorResponse.from_dict(response.json())

        return response_401

    if response.status_code == 403:
        response_403 = ErrorResponse.from_dict(response.json())

        return response_403

    if response.status_code == 404:
        response_404 = ErrorResponse.from_dict(response.json())

        return response_404

    if response.status_code == 409:
        response_409 = ErrorResponse.from_dict(response.json())

        return response_409

    if response.status_code == 422:
        response_422 = ErrorResponse.from_dict(response.json())

        return response_422

    if client.raise_on_unexpected_status:
        raise errors.UnexpectedStatus(response.status_code, response.content)
    else:
        return None


def _build_response(
    *, client: AuthenticatedClient | Client, response: httpx.Response
) -> Response[ErrorResponse | LinkResponse]:
    return Response(
        status_code=HTTPStatus(response.status_code),
        content=response.content,
        headers=response.headers,
        parsed=_parse_response(client=client, response=response),
    )


def sync_detailed(
    *,
    client: AuthenticatedClient | Client,
    body: LinkCreate,
    idempotency_key: str | Unset = UNSET,
) -> Response[ErrorResponse | LinkResponse]:
    """Let an existing account arrive through an issuer

     Requires `ORG_ADMIN`. The link is the identity: a note is the account its `(issuer, subject)` pair
    points at, whatever address the note carries. Without this route the only accounts that can use the
    shortcut are ones federation created itself, so this is how somebody who already has a password here
    starts arriving through their institution instead. One account may hold several links, one per
    issuer.

    Args:
        idempotency_key (str | Unset):
        body (LinkCreate):

    Raises:
        errors.UnexpectedStatus: If the server returns an undocumented status code and Client.raise_on_unexpected_status is True.
        httpx.TimeoutException: If the request takes longer than Client.timeout.

    Returns:
        Response[ErrorResponse | LinkResponse]
    """

    kwargs = _get_kwargs(
        body=body,
        idempotency_key=idempotency_key,
    )

    response = client.get_httpx_client().request(
        **kwargs,
    )

    return _build_response(client=client, response=response)


def sync(
    *,
    client: AuthenticatedClient | Client,
    body: LinkCreate,
    idempotency_key: str | Unset = UNSET,
) -> ErrorResponse | LinkResponse | None:
    """Let an existing account arrive through an issuer

     Requires `ORG_ADMIN`. The link is the identity: a note is the account its `(issuer, subject)` pair
    points at, whatever address the note carries. Without this route the only accounts that can use the
    shortcut are ones federation created itself, so this is how somebody who already has a password here
    starts arriving through their institution instead. One account may hold several links, one per
    issuer.

    Args:
        idempotency_key (str | Unset):
        body (LinkCreate):

    Raises:
        errors.UnexpectedStatus: If the server returns an undocumented status code and Client.raise_on_unexpected_status is True.
        httpx.TimeoutException: If the request takes longer than Client.timeout.

    Returns:
        ErrorResponse | LinkResponse
    """

    return sync_detailed(
        client=client,
        body=body,
        idempotency_key=idempotency_key,
    ).parsed


async def asyncio_detailed(
    *,
    client: AuthenticatedClient | Client,
    body: LinkCreate,
    idempotency_key: str | Unset = UNSET,
) -> Response[ErrorResponse | LinkResponse]:
    """Let an existing account arrive through an issuer

     Requires `ORG_ADMIN`. The link is the identity: a note is the account its `(issuer, subject)` pair
    points at, whatever address the note carries. Without this route the only accounts that can use the
    shortcut are ones federation created itself, so this is how somebody who already has a password here
    starts arriving through their institution instead. One account may hold several links, one per
    issuer.

    Args:
        idempotency_key (str | Unset):
        body (LinkCreate):

    Raises:
        errors.UnexpectedStatus: If the server returns an undocumented status code and Client.raise_on_unexpected_status is True.
        httpx.TimeoutException: If the request takes longer than Client.timeout.

    Returns:
        Response[ErrorResponse | LinkResponse]
    """

    kwargs = _get_kwargs(
        body=body,
        idempotency_key=idempotency_key,
    )

    response = await client.get_async_httpx_client().request(**kwargs)

    return _build_response(client=client, response=response)


async def asyncio(
    *,
    client: AuthenticatedClient | Client,
    body: LinkCreate,
    idempotency_key: str | Unset = UNSET,
) -> ErrorResponse | LinkResponse | None:
    """Let an existing account arrive through an issuer

     Requires `ORG_ADMIN`. The link is the identity: a note is the account its `(issuer, subject)` pair
    points at, whatever address the note carries. Without this route the only accounts that can use the
    shortcut are ones federation created itself, so this is how somebody who already has a password here
    starts arriving through their institution instead. One account may hold several links, one per
    issuer.

    Args:
        idempotency_key (str | Unset):
        body (LinkCreate):

    Raises:
        errors.UnexpectedStatus: If the server returns an undocumented status code and Client.raise_on_unexpected_status is True.
        httpx.TimeoutException: If the request takes longer than Client.timeout.

    Returns:
        ErrorResponse | LinkResponse
    """

    return (
        await asyncio_detailed(
            client=client,
            body=body,
            idempotency_key=idempotency_key,
        )
    ).parsed
