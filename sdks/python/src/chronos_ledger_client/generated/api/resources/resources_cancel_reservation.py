from http import HTTPStatus
from typing import Any
from urllib.parse import quote

import httpx

from ... import errors
from ...client import AuthenticatedClient, Client
from ...models.error_response import ErrorResponse
from ...models.reservation_response import ReservationResponse
from ...types import Response


def _get_kwargs(
    resource_id: int,
    reservation_id: int,
) -> dict[str, Any]:

    _kwargs: dict[str, Any] = {
        "method": "delete",
        "url": "/api/v1/resources/{resource_id}/reservations/{reservation_id}".format(
            resource_id=quote(str(resource_id), safe=""),
            reservation_id=quote(str(reservation_id), safe=""),
        ),
    }

    return _kwargs


def _parse_response(
    *, client: AuthenticatedClient | Client, response: httpx.Response
) -> ErrorResponse | ReservationResponse | None:
    if response.status_code == 200:
        response_200 = ReservationResponse.from_dict(response.json())

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

    if client.raise_on_unexpected_status:
        raise errors.UnexpectedStatus(response.status_code, response.content)
    else:
        return None


def _build_response(
    *, client: AuthenticatedClient | Client, response: httpx.Response
) -> Response[ErrorResponse | ReservationResponse]:
    return Response(
        status_code=HTTPStatus(response.status_code),
        content=response.content,
        headers=response.headers,
        parsed=_parse_response(client=client, response=response),
    )


def sync_detailed(
    resource_id: int,
    reservation_id: int,
    *,
    client: AuthenticatedClient | Client,
) -> Response[ErrorResponse | ReservationResponse]:
    """Let a hold go

     Requires `SUPER_ADMIN` or `UNIT_ADMIN`. Marks the reservation cancelled and leaves the row in place.
    A deleted row cannot be told to anybody, and a system that was informed the room was held has to be
    able to learn that it no longer is.

    The freed window is bookable again immediately and stops appearing in availability. Cancelling twice
    is not an error and returns the same timestamp. Cancelling through the wrong resource id is a 404.

    A hold is let go by whoever took it. A `UNIT_ADMIN` that did not make the reservation gets a 403; a
    `SUPER_ADMIN` overrides, because a hold taken by an account that no longer exists has nobody left to
    cancel it.

    Args:
        resource_id (int):
        reservation_id (int):

    Raises:
        errors.UnexpectedStatus: If the server returns an undocumented status code and Client.raise_on_unexpected_status is True.
        httpx.TimeoutException: If the request takes longer than Client.timeout.

    Returns:
        Response[ErrorResponse | ReservationResponse]
    """

    kwargs = _get_kwargs(
        resource_id=resource_id,
        reservation_id=reservation_id,
    )

    response = client.get_httpx_client().request(
        **kwargs,
    )

    return _build_response(client=client, response=response)


def sync(
    resource_id: int,
    reservation_id: int,
    *,
    client: AuthenticatedClient | Client,
) -> ErrorResponse | ReservationResponse | None:
    """Let a hold go

     Requires `SUPER_ADMIN` or `UNIT_ADMIN`. Marks the reservation cancelled and leaves the row in place.
    A deleted row cannot be told to anybody, and a system that was informed the room was held has to be
    able to learn that it no longer is.

    The freed window is bookable again immediately and stops appearing in availability. Cancelling twice
    is not an error and returns the same timestamp. Cancelling through the wrong resource id is a 404.

    A hold is let go by whoever took it. A `UNIT_ADMIN` that did not make the reservation gets a 403; a
    `SUPER_ADMIN` overrides, because a hold taken by an account that no longer exists has nobody left to
    cancel it.

    Args:
        resource_id (int):
        reservation_id (int):

    Raises:
        errors.UnexpectedStatus: If the server returns an undocumented status code and Client.raise_on_unexpected_status is True.
        httpx.TimeoutException: If the request takes longer than Client.timeout.

    Returns:
        ErrorResponse | ReservationResponse
    """

    return sync_detailed(
        resource_id=resource_id,
        reservation_id=reservation_id,
        client=client,
    ).parsed


async def asyncio_detailed(
    resource_id: int,
    reservation_id: int,
    *,
    client: AuthenticatedClient | Client,
) -> Response[ErrorResponse | ReservationResponse]:
    """Let a hold go

     Requires `SUPER_ADMIN` or `UNIT_ADMIN`. Marks the reservation cancelled and leaves the row in place.
    A deleted row cannot be told to anybody, and a system that was informed the room was held has to be
    able to learn that it no longer is.

    The freed window is bookable again immediately and stops appearing in availability. Cancelling twice
    is not an error and returns the same timestamp. Cancelling through the wrong resource id is a 404.

    A hold is let go by whoever took it. A `UNIT_ADMIN` that did not make the reservation gets a 403; a
    `SUPER_ADMIN` overrides, because a hold taken by an account that no longer exists has nobody left to
    cancel it.

    Args:
        resource_id (int):
        reservation_id (int):

    Raises:
        errors.UnexpectedStatus: If the server returns an undocumented status code and Client.raise_on_unexpected_status is True.
        httpx.TimeoutException: If the request takes longer than Client.timeout.

    Returns:
        Response[ErrorResponse | ReservationResponse]
    """

    kwargs = _get_kwargs(
        resource_id=resource_id,
        reservation_id=reservation_id,
    )

    response = await client.get_async_httpx_client().request(**kwargs)

    return _build_response(client=client, response=response)


async def asyncio(
    resource_id: int,
    reservation_id: int,
    *,
    client: AuthenticatedClient | Client,
) -> ErrorResponse | ReservationResponse | None:
    """Let a hold go

     Requires `SUPER_ADMIN` or `UNIT_ADMIN`. Marks the reservation cancelled and leaves the row in place.
    A deleted row cannot be told to anybody, and a system that was informed the room was held has to be
    able to learn that it no longer is.

    The freed window is bookable again immediately and stops appearing in availability. Cancelling twice
    is not an error and returns the same timestamp. Cancelling through the wrong resource id is a 404.

    A hold is let go by whoever took it. A `UNIT_ADMIN` that did not make the reservation gets a 403; a
    `SUPER_ADMIN` overrides, because a hold taken by an account that no longer exists has nobody left to
    cancel it.

    Args:
        resource_id (int):
        reservation_id (int):

    Raises:
        errors.UnexpectedStatus: If the server returns an undocumented status code and Client.raise_on_unexpected_status is True.
        httpx.TimeoutException: If the request takes longer than Client.timeout.

    Returns:
        ErrorResponse | ReservationResponse
    """

    return (
        await asyncio_detailed(
            resource_id=resource_id,
            reservation_id=reservation_id,
            client=client,
        )
    ).parsed
