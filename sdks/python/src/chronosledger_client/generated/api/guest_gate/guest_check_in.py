from http import HTTPStatus
from typing import Any

import httpx

from ... import errors
from ...client import AuthenticatedClient, Client
from ...models.error_response import ErrorResponse
from ...models.guest_check_in_request import GuestCheckInRequest
from ...models.guest_check_in_response_200 import GuestCheckInResponse200
from ...types import Response


def _get_kwargs(
    *,
    body: GuestCheckInRequest,
) -> dict[str, Any]:
    headers: dict[str, Any] = {}

    _kwargs: dict[str, Any] = {
        "method": "post",
        "url": "/api/v1/guest/register-checkin",
    }

    _kwargs["json"] = body.to_dict()

    headers["Content-Type"] = "application/json"

    _kwargs["headers"] = headers
    return _kwargs


def _parse_response(
    *, client: AuthenticatedClient | Client, response: httpx.Response
) -> ErrorResponse | GuestCheckInResponse200 | None:
    if response.status_code == 200:
        response_200 = GuestCheckInResponse200.from_dict(response.json())

        return response_200

    if response.status_code == 404:
        response_404 = ErrorResponse.from_dict(response.json())

        return response_404

    if response.status_code == 429:
        response_429 = ErrorResponse.from_dict(response.json())

        return response_429

    if client.raise_on_unexpected_status:
        raise errors.UnexpectedStatus(response.status_code, response.content)
    else:
        return None


def _build_response(
    *, client: AuthenticatedClient | Client, response: httpx.Response
) -> Response[ErrorResponse | GuestCheckInResponse200]:
    return Response(
        status_code=HTTPStatus(response.status_code),
        content=response.content,
        headers=response.headers,
        parsed=_parse_response(client=client, response=response),
    )


def sync_detailed(
    *,
    client: AuthenticatedClient | Client,
    body: GuestCheckInRequest,
) -> Response[ErrorResponse | GuestCheckInResponse200]:
    """Register an organization visitor (kiosk)

     The visitor does not authenticate; the kiosk device does, with an admin-issued API key in `X-API-
    Key`. Sends a `GUEST_HANDSHAKE_REQ` WebSocket frame to the target staff member. The kiosk and the
    visitor learn the decision from `/guest/visit/{code}`, with the code this response carries.

    Args:
        body (GuestCheckInRequest):

    Raises:
        errors.UnexpectedStatus: If the server returns an undocumented status code and Client.raise_on_unexpected_status is True.
        httpx.TimeoutException: If the request takes longer than Client.timeout.

    Returns:
        Response[ErrorResponse | GuestCheckInResponse200]
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
    body: GuestCheckInRequest,
) -> ErrorResponse | GuestCheckInResponse200 | None:
    """Register an organization visitor (kiosk)

     The visitor does not authenticate; the kiosk device does, with an admin-issued API key in `X-API-
    Key`. Sends a `GUEST_HANDSHAKE_REQ` WebSocket frame to the target staff member. The kiosk and the
    visitor learn the decision from `/guest/visit/{code}`, with the code this response carries.

    Args:
        body (GuestCheckInRequest):

    Raises:
        errors.UnexpectedStatus: If the server returns an undocumented status code and Client.raise_on_unexpected_status is True.
        httpx.TimeoutException: If the request takes longer than Client.timeout.

    Returns:
        ErrorResponse | GuestCheckInResponse200
    """

    return sync_detailed(
        client=client,
        body=body,
    ).parsed


async def asyncio_detailed(
    *,
    client: AuthenticatedClient | Client,
    body: GuestCheckInRequest,
) -> Response[ErrorResponse | GuestCheckInResponse200]:
    """Register an organization visitor (kiosk)

     The visitor does not authenticate; the kiosk device does, with an admin-issued API key in `X-API-
    Key`. Sends a `GUEST_HANDSHAKE_REQ` WebSocket frame to the target staff member. The kiosk and the
    visitor learn the decision from `/guest/visit/{code}`, with the code this response carries.

    Args:
        body (GuestCheckInRequest):

    Raises:
        errors.UnexpectedStatus: If the server returns an undocumented status code and Client.raise_on_unexpected_status is True.
        httpx.TimeoutException: If the request takes longer than Client.timeout.

    Returns:
        Response[ErrorResponse | GuestCheckInResponse200]
    """

    kwargs = _get_kwargs(
        body=body,
    )

    response = await client.get_async_httpx_client().request(**kwargs)

    return _build_response(client=client, response=response)


async def asyncio(
    *,
    client: AuthenticatedClient | Client,
    body: GuestCheckInRequest,
) -> ErrorResponse | GuestCheckInResponse200 | None:
    """Register an organization visitor (kiosk)

     The visitor does not authenticate; the kiosk device does, with an admin-issued API key in `X-API-
    Key`. Sends a `GUEST_HANDSHAKE_REQ` WebSocket frame to the target staff member. The kiosk and the
    visitor learn the decision from `/guest/visit/{code}`, with the code this response carries.

    Args:
        body (GuestCheckInRequest):

    Raises:
        errors.UnexpectedStatus: If the server returns an undocumented status code and Client.raise_on_unexpected_status is True.
        httpx.TimeoutException: If the request takes longer than Client.timeout.

    Returns:
        ErrorResponse | GuestCheckInResponse200
    """

    return (
        await asyncio_detailed(
            client=client,
            body=body,
        )
    ).parsed
