from http import HTTPStatus
from typing import Any

import httpx

from ... import errors
from ...client import AuthenticatedClient, Client
from ...models.error_response import ErrorResponse
from ...models.users_list_available_staff_response_200_item import (
    UsersListAvailableStaffResponse200Item,
)
from ...types import UNSET, Response, Unset


def _get_kwargs(
    *,
    unit: str | Unset = UNSET,
    limit: int | Unset = UNSET,
    offset: int | Unset = 0,
) -> dict[str, Any]:

    params: dict[str, Any] = {}

    params["unit"] = unit

    params["limit"] = limit

    params["offset"] = offset

    params = {k: v for k, v in params.items() if v is not UNSET and v is not None}

    _kwargs: dict[str, Any] = {
        "method": "get",
        "url": "/api/v1/users/staff/available",
        "params": params,
    }

    return _kwargs


def _parse_response(
    *, client: AuthenticatedClient | Client, response: httpx.Response
) -> ErrorResponse | list[UsersListAvailableStaffResponse200Item] | None:
    if response.status_code == 200:
        response_200 = []
        _response_200 = response.json()
        for response_200_item_data in _response_200:
            response_200_item = UsersListAvailableStaffResponse200Item.from_dict(
                response_200_item_data
            )

            response_200.append(response_200_item)

        return response_200

    if response.status_code == 401:
        response_401 = ErrorResponse.from_dict(response.json())

        return response_401

    if client.raise_on_unexpected_status:
        raise errors.UnexpectedStatus(response.status_code, response.content)
    else:
        return None


def _build_response(
    *, client: AuthenticatedClient | Client, response: httpx.Response
) -> Response[ErrorResponse | list[UsersListAvailableStaffResponse200Item]]:
    return Response(
        status_code=HTTPStatus(response.status_code),
        content=response.content,
        headers=response.headers,
        parsed=_parse_response(client=client, response=response),
    )


def sync_detailed(
    *,
    client: AuthenticatedClient | Client,
    unit: str | Unset = UNSET,
    limit: int | Unset = UNSET,
    offset: int | Unset = 0,
) -> Response[ErrorResponse | list[UsersListAvailableStaffResponse200Item]]:
    """List active staff with their current status

     Every staff member who has not been deactivated, whatever their status. The visitor kiosk searches
    by name through `GET /guest/directory` instead. This route **must** appear before `GET
    /users/{user_id}` in the router to prevent "staff" being matched as a user_id path parameter.

    Args:
        unit (str | Unset):
        limit (int | Unset):
        offset (int | Unset):  Default: 0.

    Raises:
        errors.UnexpectedStatus: If the server returns an undocumented status code and Client.raise_on_unexpected_status is True.
        httpx.TimeoutException: If the request takes longer than Client.timeout.

    Returns:
        Response[ErrorResponse | list[UsersListAvailableStaffResponse200Item]]
    """

    kwargs = _get_kwargs(
        unit=unit,
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
    unit: str | Unset = UNSET,
    limit: int | Unset = UNSET,
    offset: int | Unset = 0,
) -> ErrorResponse | list[UsersListAvailableStaffResponse200Item] | None:
    """List active staff with their current status

     Every staff member who has not been deactivated, whatever their status. The visitor kiosk searches
    by name through `GET /guest/directory` instead. This route **must** appear before `GET
    /users/{user_id}` in the router to prevent "staff" being matched as a user_id path parameter.

    Args:
        unit (str | Unset):
        limit (int | Unset):
        offset (int | Unset):  Default: 0.

    Raises:
        errors.UnexpectedStatus: If the server returns an undocumented status code and Client.raise_on_unexpected_status is True.
        httpx.TimeoutException: If the request takes longer than Client.timeout.

    Returns:
        ErrorResponse | list[UsersListAvailableStaffResponse200Item]
    """

    return sync_detailed(
        client=client,
        unit=unit,
        limit=limit,
        offset=offset,
    ).parsed


async def asyncio_detailed(
    *,
    client: AuthenticatedClient | Client,
    unit: str | Unset = UNSET,
    limit: int | Unset = UNSET,
    offset: int | Unset = 0,
) -> Response[ErrorResponse | list[UsersListAvailableStaffResponse200Item]]:
    """List active staff with their current status

     Every staff member who has not been deactivated, whatever their status. The visitor kiosk searches
    by name through `GET /guest/directory` instead. This route **must** appear before `GET
    /users/{user_id}` in the router to prevent "staff" being matched as a user_id path parameter.

    Args:
        unit (str | Unset):
        limit (int | Unset):
        offset (int | Unset):  Default: 0.

    Raises:
        errors.UnexpectedStatus: If the server returns an undocumented status code and Client.raise_on_unexpected_status is True.
        httpx.TimeoutException: If the request takes longer than Client.timeout.

    Returns:
        Response[ErrorResponse | list[UsersListAvailableStaffResponse200Item]]
    """

    kwargs = _get_kwargs(
        unit=unit,
        limit=limit,
        offset=offset,
    )

    response = await client.get_async_httpx_client().request(**kwargs)

    return _build_response(client=client, response=response)


async def asyncio(
    *,
    client: AuthenticatedClient | Client,
    unit: str | Unset = UNSET,
    limit: int | Unset = UNSET,
    offset: int | Unset = 0,
) -> ErrorResponse | list[UsersListAvailableStaffResponse200Item] | None:
    """List active staff with their current status

     Every staff member who has not been deactivated, whatever their status. The visitor kiosk searches
    by name through `GET /guest/directory` instead. This route **must** appear before `GET
    /users/{user_id}` in the router to prevent "staff" being matched as a user_id path parameter.

    Args:
        unit (str | Unset):
        limit (int | Unset):
        offset (int | Unset):  Default: 0.

    Raises:
        errors.UnexpectedStatus: If the server returns an undocumented status code and Client.raise_on_unexpected_status is True.
        httpx.TimeoutException: If the request takes longer than Client.timeout.

    Returns:
        ErrorResponse | list[UsersListAvailableStaffResponse200Item]
    """

    return (
        await asyncio_detailed(
            client=client,
            unit=unit,
            limit=limit,
            offset=offset,
        )
    ).parsed
