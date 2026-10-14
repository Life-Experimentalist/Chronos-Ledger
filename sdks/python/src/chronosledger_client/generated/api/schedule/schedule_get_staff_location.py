from http import HTTPStatus
from typing import Any
from urllib.parse import quote

import httpx

from ... import errors
from ...client import AuthenticatedClient, Client
from ...models.error_response import ErrorResponse
from ...models.staff_location_response import StaffLocationResponse
from ...types import Response


def _get_kwargs(
    staff_id: str,
) -> dict[str, Any]:

    _kwargs: dict[str, Any] = {
        "method": "get",
        "url": "/api/v1/schedule/staff/{staff_id}/location".format(
            staff_id=quote(str(staff_id), safe=""),
        ),
    }

    return _kwargs


def _parse_response(
    *, client: AuthenticatedClient | Client, response: httpx.Response
) -> ErrorResponse | StaffLocationResponse | None:
    if response.status_code == 200:
        response_200 = StaffLocationResponse.from_dict(response.json())

        return response_200

    if response.status_code == 404:
        response_404 = ErrorResponse.from_dict(response.json())

        return response_404

    if client.raise_on_unexpected_status:
        raise errors.UnexpectedStatus(response.status_code, response.content)
    else:
        return None


def _build_response(
    *, client: AuthenticatedClient | Client, response: httpx.Response
) -> Response[ErrorResponse | StaffLocationResponse]:
    return Response(
        status_code=HTTPStatus(response.status_code),
        content=response.content,
        headers=response.headers,
        parsed=_parse_response(client=client, response=response),
    )


def sync_detailed(
    staff_id: str,
    *,
    client: AuthenticatedClient | Client,
) -> Response[ErrorResponse | StaffLocationResponse]:
    """Resolve a staff member's current location via 4-tier resolver

    Args:
        staff_id (str):

    Raises:
        errors.UnexpectedStatus: If the server returns an undocumented status code and Client.raise_on_unexpected_status is True.
        httpx.TimeoutException: If the request takes longer than Client.timeout.

    Returns:
        Response[ErrorResponse | StaffLocationResponse]
    """

    kwargs = _get_kwargs(
        staff_id=staff_id,
    )

    response = client.get_httpx_client().request(
        **kwargs,
    )

    return _build_response(client=client, response=response)


def sync(
    staff_id: str,
    *,
    client: AuthenticatedClient | Client,
) -> ErrorResponse | StaffLocationResponse | None:
    """Resolve a staff member's current location via 4-tier resolver

    Args:
        staff_id (str):

    Raises:
        errors.UnexpectedStatus: If the server returns an undocumented status code and Client.raise_on_unexpected_status is True.
        httpx.TimeoutException: If the request takes longer than Client.timeout.

    Returns:
        ErrorResponse | StaffLocationResponse
    """

    return sync_detailed(
        staff_id=staff_id,
        client=client,
    ).parsed


async def asyncio_detailed(
    staff_id: str,
    *,
    client: AuthenticatedClient | Client,
) -> Response[ErrorResponse | StaffLocationResponse]:
    """Resolve a staff member's current location via 4-tier resolver

    Args:
        staff_id (str):

    Raises:
        errors.UnexpectedStatus: If the server returns an undocumented status code and Client.raise_on_unexpected_status is True.
        httpx.TimeoutException: If the request takes longer than Client.timeout.

    Returns:
        Response[ErrorResponse | StaffLocationResponse]
    """

    kwargs = _get_kwargs(
        staff_id=staff_id,
    )

    response = await client.get_async_httpx_client().request(**kwargs)

    return _build_response(client=client, response=response)


async def asyncio(
    staff_id: str,
    *,
    client: AuthenticatedClient | Client,
) -> ErrorResponse | StaffLocationResponse | None:
    """Resolve a staff member's current location via 4-tier resolver

    Args:
        staff_id (str):

    Raises:
        errors.UnexpectedStatus: If the server returns an undocumented status code and Client.raise_on_unexpected_status is True.
        httpx.TimeoutException: If the request takes longer than Client.timeout.

    Returns:
        ErrorResponse | StaffLocationResponse
    """

    return (
        await asyncio_detailed(
            staff_id=staff_id,
            client=client,
        )
    ).parsed
