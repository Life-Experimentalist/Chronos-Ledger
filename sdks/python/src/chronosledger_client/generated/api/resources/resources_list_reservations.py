from http import HTTPStatus
from typing import Any

import httpx

from ... import errors
from ...client import AuthenticatedClient, Client
from ...models.error_response import ErrorResponse
from ...models.reservation_response import ReservationResponse
from ...types import UNSET, Response, Unset


def _get_kwargs(
    *,
    external_ref: str | Unset = UNSET,
    limit: int | Unset = UNSET,
    offset: int | Unset = 0,
) -> dict[str, Any]:

    params: dict[str, Any] = {}

    params["external_ref"] = external_ref

    params["limit"] = limit

    params["offset"] = offset

    params = {k: v for k, v in params.items() if v is not UNSET and v is not None}

    _kwargs: dict[str, Any] = {
        "method": "get",
        "url": "/api/v1/resources/reservations",
        "params": params,
    }

    return _kwargs


def _parse_response(
    *, client: AuthenticatedClient | Client, response: httpx.Response
) -> ErrorResponse | list[ReservationResponse] | None:
    if response.status_code == 200:
        response_200 = []
        _response_200 = response.json()
        for response_200_item_data in _response_200:
            response_200_item = ReservationResponse.from_dict(response_200_item_data)

            response_200.append(response_200_item)

        return response_200

    if response.status_code == 401:
        response_401 = ErrorResponse.from_dict(response.json())

        return response_401

    if response.status_code == 403:
        response_403 = ErrorResponse.from_dict(response.json())

        return response_403

    if client.raise_on_unexpected_status:
        raise errors.UnexpectedStatus(response.status_code, response.content)
    else:
        return None


def _build_response(
    *, client: AuthenticatedClient | Client, response: httpx.Response
) -> Response[ErrorResponse | list[ReservationResponse]]:
    return Response(
        status_code=HTTPStatus(response.status_code),
        content=response.content,
        headers=response.headers,
        parsed=_parse_response(client=client, response=response),
    )


def sync_detailed(
    *,
    client: AuthenticatedClient | Client,
    external_ref: str | Unset = UNSET,
    limit: int | Unset = UNSET,
    offset: int | Unset = 0,
) -> Response[ErrorResponse | list[ReservationResponse]]:
    """List the caller's own reservations

     Requires `ORG_ADMIN` or `UNIT_ADMIN`. The reservations the caller made, cancelled ones included, in
    id order. Only the caller's, for every role, an `ORG_ADMIN` included: a reference means something
    only to the system that chose it, so asking for one must return the caller's own booking and never
    another caller's under the same string. This is where an integration finds its bookings, not a view
    of everybody's.

    `external_ref` matches exactly, case included, so with it the answer is one reservation or none.
    Under `/resources` so that a key scoped `resources:read` reaches it.

    Args:
        external_ref (str | Unset):
        limit (int | Unset):
        offset (int | Unset):  Default: 0.

    Raises:
        errors.UnexpectedStatus: If the server returns an undocumented status code and Client.raise_on_unexpected_status is True.
        httpx.TimeoutException: If the request takes longer than Client.timeout.

    Returns:
        Response[ErrorResponse | list[ReservationResponse]]
    """

    kwargs = _get_kwargs(
        external_ref=external_ref,
        limit=limit,
        offset=offset,
    )

    response = client.get_httpx_client().request(
        **kwargs,
    )

    return _build_response(client=client, response=response)


def sync(
    *,
    client: AuthenticatedClient | Client,
    external_ref: str | Unset = UNSET,
    limit: int | Unset = UNSET,
    offset: int | Unset = 0,
) -> ErrorResponse | list[ReservationResponse] | None:
    """List the caller's own reservations

     Requires `ORG_ADMIN` or `UNIT_ADMIN`. The reservations the caller made, cancelled ones included, in
    id order. Only the caller's, for every role, an `ORG_ADMIN` included: a reference means something
    only to the system that chose it, so asking for one must return the caller's own booking and never
    another caller's under the same string. This is where an integration finds its bookings, not a view
    of everybody's.

    `external_ref` matches exactly, case included, so with it the answer is one reservation or none.
    Under `/resources` so that a key scoped `resources:read` reaches it.

    Args:
        external_ref (str | Unset):
        limit (int | Unset):
        offset (int | Unset):  Default: 0.

    Raises:
        errors.UnexpectedStatus: If the server returns an undocumented status code and Client.raise_on_unexpected_status is True.
        httpx.TimeoutException: If the request takes longer than Client.timeout.

    Returns:
        ErrorResponse | list[ReservationResponse]
    """

    return sync_detailed(
        client=client,
        external_ref=external_ref,
        limit=limit,
        offset=offset,
    ).parsed


async def asyncio_detailed(
    *,
    client: AuthenticatedClient | Client,
    external_ref: str | Unset = UNSET,
    limit: int | Unset = UNSET,
    offset: int | Unset = 0,
) -> Response[ErrorResponse | list[ReservationResponse]]:
    """List the caller's own reservations

     Requires `ORG_ADMIN` or `UNIT_ADMIN`. The reservations the caller made, cancelled ones included, in
    id order. Only the caller's, for every role, an `ORG_ADMIN` included: a reference means something
    only to the system that chose it, so asking for one must return the caller's own booking and never
    another caller's under the same string. This is where an integration finds its bookings, not a view
    of everybody's.

    `external_ref` matches exactly, case included, so with it the answer is one reservation or none.
    Under `/resources` so that a key scoped `resources:read` reaches it.

    Args:
        external_ref (str | Unset):
        limit (int | Unset):
        offset (int | Unset):  Default: 0.

    Raises:
        errors.UnexpectedStatus: If the server returns an undocumented status code and Client.raise_on_unexpected_status is True.
        httpx.TimeoutException: If the request takes longer than Client.timeout.

    Returns:
        Response[ErrorResponse | list[ReservationResponse]]
    """

    kwargs = _get_kwargs(
        external_ref=external_ref,
        limit=limit,
        offset=offset,
    )

    response = await client.get_async_httpx_client().request(**kwargs)

    return _build_response(client=client, response=response)


async def asyncio(
    *,
    client: AuthenticatedClient | Client,
    external_ref: str | Unset = UNSET,
    limit: int | Unset = UNSET,
    offset: int | Unset = 0,
) -> ErrorResponse | list[ReservationResponse] | None:
    """List the caller's own reservations

     Requires `ORG_ADMIN` or `UNIT_ADMIN`. The reservations the caller made, cancelled ones included, in
    id order. Only the caller's, for every role, an `ORG_ADMIN` included: a reference means something
    only to the system that chose it, so asking for one must return the caller's own booking and never
    another caller's under the same string. This is where an integration finds its bookings, not a view
    of everybody's.

    `external_ref` matches exactly, case included, so with it the answer is one reservation or none.
    Under `/resources` so that a key scoped `resources:read` reaches it.

    Args:
        external_ref (str | Unset):
        limit (int | Unset):
        offset (int | Unset):  Default: 0.

    Raises:
        errors.UnexpectedStatus: If the server returns an undocumented status code and Client.raise_on_unexpected_status is True.
        httpx.TimeoutException: If the request takes longer than Client.timeout.

    Returns:
        ErrorResponse | list[ReservationResponse]
    """

    return (
        await asyncio_detailed(
            client=client,
            external_ref=external_ref,
            limit=limit,
            offset=offset,
        )
    ).parsed
