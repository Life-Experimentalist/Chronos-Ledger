from http import HTTPStatus
from typing import Any

import httpx

from ... import errors
from ...client import AuthenticatedClient, Client
from ...models.error_response import ErrorResponse
from ...models.resource_create import ResourceCreate
from ...models.resource_response import ResourceResponse
from ...types import Response


def _get_kwargs(
    *,
    body: ResourceCreate,
) -> dict[str, Any]:
    headers: dict[str, Any] = {}

    _kwargs: dict[str, Any] = {
        "method": "post",
        "url": "/api/v1/resources/",
    }

    _kwargs["json"] = body.to_dict()

    headers["Content-Type"] = "application/json"

    _kwargs["headers"] = headers
    return _kwargs


def _parse_response(
    *, client: AuthenticatedClient | Client, response: httpx.Response
) -> ErrorResponse | ResourceResponse | None:
    if response.status_code == 201:
        response_201 = ResourceResponse.from_dict(response.json())

        return response_201

    if response.status_code == 401:
        response_401 = ErrorResponse.from_dict(response.json())

        return response_401

    if response.status_code == 403:
        response_403 = ErrorResponse.from_dict(response.json())

        return response_403

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
) -> Response[ErrorResponse | ResourceResponse]:
    return Response(
        status_code=HTTPStatus(response.status_code),
        content=response.content,
        headers=response.headers,
        parsed=_parse_response(client=client, response=response),
    )


def sync_detailed(
    *,
    client: AuthenticatedClient | Client,
    body: ResourceCreate,
) -> Response[ErrorResponse | ResourceResponse]:
    """Create a room

     Requires `SUPER_ADMIN`. Registers a room before any timetable names it, for a system that manages
    its own rooms. The row is the one an import would have made, so a later CSV naming the room finds it
    rather than creating a second. A retry after a lost response reads the room back with `GET
    /api/v1/resources/?code=`: the code already identifies it, so no Idempotency-Key is taken.

    Args:
        body (ResourceCreate): A room. Every string is trimmed first, code included, the same as
            the importer trims a room name, so this room and the same name in a later CSV are one row.

    Raises:
        errors.UnexpectedStatus: If the server returns an undocumented status code and Client.raise_on_unexpected_status is True.
        httpx.TimeoutException: If the request takes longer than Client.timeout.

    Returns:
        Response[ErrorResponse | ResourceResponse]
    """

    kwargs = _get_kwargs(
        body=body,
    )

    response = client.get_httpx_client().request(
        **kwargs,
    )

    return _build_response(client=client, response=response)


def sync(
    *,
    client: AuthenticatedClient | Client,
    body: ResourceCreate,
) -> ErrorResponse | ResourceResponse | None:
    """Create a room

     Requires `SUPER_ADMIN`. Registers a room before any timetable names it, for a system that manages
    its own rooms. The row is the one an import would have made, so a later CSV naming the room finds it
    rather than creating a second. A retry after a lost response reads the room back with `GET
    /api/v1/resources/?code=`: the code already identifies it, so no Idempotency-Key is taken.

    Args:
        body (ResourceCreate): A room. Every string is trimmed first, code included, the same as
            the importer trims a room name, so this room and the same name in a later CSV are one row.

    Raises:
        errors.UnexpectedStatus: If the server returns an undocumented status code and Client.raise_on_unexpected_status is True.
        httpx.TimeoutException: If the request takes longer than Client.timeout.

    Returns:
        ErrorResponse | ResourceResponse
    """

    return sync_detailed(
        client=client,
        body=body,
    ).parsed


async def asyncio_detailed(
    *,
    client: AuthenticatedClient | Client,
    body: ResourceCreate,
) -> Response[ErrorResponse | ResourceResponse]:
    """Create a room

     Requires `SUPER_ADMIN`. Registers a room before any timetable names it, for a system that manages
    its own rooms. The row is the one an import would have made, so a later CSV naming the room finds it
    rather than creating a second. A retry after a lost response reads the room back with `GET
    /api/v1/resources/?code=`: the code already identifies it, so no Idempotency-Key is taken.

    Args:
        body (ResourceCreate): A room. Every string is trimmed first, code included, the same as
            the importer trims a room name, so this room and the same name in a later CSV are one row.

    Raises:
        errors.UnexpectedStatus: If the server returns an undocumented status code and Client.raise_on_unexpected_status is True.
        httpx.TimeoutException: If the request takes longer than Client.timeout.

    Returns:
        Response[ErrorResponse | ResourceResponse]
    """

    kwargs = _get_kwargs(
        body=body,
    )

    response = await client.get_async_httpx_client().request(**kwargs)

    return _build_response(client=client, response=response)


async def asyncio(
    *,
    client: AuthenticatedClient | Client,
    body: ResourceCreate,
) -> ErrorResponse | ResourceResponse | None:
    """Create a room

     Requires `SUPER_ADMIN`. Registers a room before any timetable names it, for a system that manages
    its own rooms. The row is the one an import would have made, so a later CSV naming the room finds it
    rather than creating a second. A retry after a lost response reads the room back with `GET
    /api/v1/resources/?code=`: the code already identifies it, so no Idempotency-Key is taken.

    Args:
        body (ResourceCreate): A room. Every string is trimmed first, code included, the same as
            the importer trims a room name, so this room and the same name in a later CSV are one row.

    Raises:
        errors.UnexpectedStatus: If the server returns an undocumented status code and Client.raise_on_unexpected_status is True.
        httpx.TimeoutException: If the request takes longer than Client.timeout.

    Returns:
        ErrorResponse | ResourceResponse
    """

    return (
        await asyncio_detailed(
            client=client,
            body=body,
        )
    ).parsed
