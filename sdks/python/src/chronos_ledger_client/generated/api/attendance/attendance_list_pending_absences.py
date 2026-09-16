from http import HTTPStatus
from typing import Any

import httpx

from ... import errors
from ...client import AuthenticatedClient, Client
from ...models.reverse_rsvp_response import ReverseRsvpResponse
from ...types import Response


def _get_kwargs() -> dict[str, Any]:

    _kwargs: dict[str, Any] = {
        "method": "get",
        "url": "/api/v1/attendance/absence/pending",
    }

    return _kwargs


def _parse_response(
    *, client: AuthenticatedClient | Client, response: httpx.Response
) -> list[ReverseRsvpResponse] | None:
    if response.status_code == 200:
        response_200 = []
        _response_200 = response.json()
        for response_200_item_data in _response_200:
            response_200_item = ReverseRsvpResponse.from_dict(response_200_item_data)

            response_200.append(response_200_item)

        return response_200

    if client.raise_on_unexpected_status:
        raise errors.UnexpectedStatus(response.status_code, response.content)
    else:
        return None


def _build_response(
    *, client: AuthenticatedClient | Client, response: httpx.Response
) -> Response[list[ReverseRsvpResponse]]:
    return Response(
        status_code=HTTPStatus(response.status_code),
        content=response.content,
        headers=response.headers,
        parsed=_parse_response(client=client, response=response),
    )


def sync_detailed(
    *,
    client: AuthenticatedClient | Client,
) -> Response[list[ReverseRsvpResponse]]:
    """List absence requests pending the caller's approval

     Any signed-in user. Returns the undecided requests the caller may decide: those routed to them as
    the submitter's line manager and, for an admin, those whose manager has since been deactivated. A
    SUPER_ADMIN gets every one of those, a UNIT_ADMIN those from the non-admin accounts of their own
    unit, and nobody gets their own.

    Raises:
        errors.UnexpectedStatus: If the server returns an undocumented status code and Client.raise_on_unexpected_status is True.
        httpx.TimeoutException: If the request takes longer than Client.timeout.

    Returns:
        Response[list[ReverseRsvpResponse]]
    """

    kwargs = _get_kwargs()

    response = client.get_httpx_client().request(
        **kwargs,
    )

    return _build_response(client=client, response=response)


def sync(
    *,
    client: AuthenticatedClient | Client,
) -> list[ReverseRsvpResponse] | None:
    """List absence requests pending the caller's approval

     Any signed-in user. Returns the undecided requests the caller may decide: those routed to them as
    the submitter's line manager and, for an admin, those whose manager has since been deactivated. A
    SUPER_ADMIN gets every one of those, a UNIT_ADMIN those from the non-admin accounts of their own
    unit, and nobody gets their own.

    Raises:
        errors.UnexpectedStatus: If the server returns an undocumented status code and Client.raise_on_unexpected_status is True.
        httpx.TimeoutException: If the request takes longer than Client.timeout.

    Returns:
        list[ReverseRsvpResponse]
    """

    return sync_detailed(
        client=client,
    ).parsed


async def asyncio_detailed(
    *,
    client: AuthenticatedClient | Client,
) -> Response[list[ReverseRsvpResponse]]:
    """List absence requests pending the caller's approval

     Any signed-in user. Returns the undecided requests the caller may decide: those routed to them as
    the submitter's line manager and, for an admin, those whose manager has since been deactivated. A
    SUPER_ADMIN gets every one of those, a UNIT_ADMIN those from the non-admin accounts of their own
    unit, and nobody gets their own.

    Raises:
        errors.UnexpectedStatus: If the server returns an undocumented status code and Client.raise_on_unexpected_status is True.
        httpx.TimeoutException: If the request takes longer than Client.timeout.

    Returns:
        Response[list[ReverseRsvpResponse]]
    """

    kwargs = _get_kwargs()

    response = await client.get_async_httpx_client().request(**kwargs)

    return _build_response(client=client, response=response)


async def asyncio(
    *,
    client: AuthenticatedClient | Client,
) -> list[ReverseRsvpResponse] | None:
    """List absence requests pending the caller's approval

     Any signed-in user. Returns the undecided requests the caller may decide: those routed to them as
    the submitter's line manager and, for an admin, those whose manager has since been deactivated. A
    SUPER_ADMIN gets every one of those, a UNIT_ADMIN those from the non-admin accounts of their own
    unit, and nobody gets their own.

    Raises:
        errors.UnexpectedStatus: If the server returns an undocumented status code and Client.raise_on_unexpected_status is True.
        httpx.TimeoutException: If the request takes longer than Client.timeout.

    Returns:
        list[ReverseRsvpResponse]
    """

    return (
        await asyncio_detailed(
            client=client,
        )
    ).parsed
