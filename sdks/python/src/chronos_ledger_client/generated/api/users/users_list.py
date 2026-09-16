from http import HTTPStatus
from typing import Any

import httpx

from ... import errors
from ...client import AuthenticatedClient, Client
from ...models.error_response import ErrorResponse
from ...models.institutional_role import InstitutionalRole
from ...models.user_response import UserResponse
from ...types import UNSET, Response, Unset


def _get_kwargs(
    *,
    role: InstitutionalRole | Unset = UNSET,
    unit: str | Unset = UNSET,
    include_deactivated: bool | Unset = False,
    limit: int | Unset = UNSET,
    offset: int | Unset = 0,
) -> dict[str, Any]:

    params: dict[str, Any] = {}

    json_role: str | Unset = UNSET
    if not isinstance(role, Unset):
        json_role = role.value

    params["role"] = json_role

    params["unit"] = unit

    params["include_deactivated"] = include_deactivated

    params["limit"] = limit

    params["offset"] = offset

    params = {k: v for k, v in params.items() if v is not UNSET and v is not None}

    _kwargs: dict[str, Any] = {
        "method": "get",
        "url": "/api/v1/users/",
        "params": params,
    }

    return _kwargs


def _parse_response(
    *, client: AuthenticatedClient | Client, response: httpx.Response
) -> ErrorResponse | list[UserResponse] | None:
    if response.status_code == 200:
        response_200 = []
        _response_200 = response.json()
        for response_200_item_data in _response_200:
            response_200_item = UserResponse.from_dict(response_200_item_data)

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
) -> Response[ErrorResponse | list[UserResponse]]:
    return Response(
        status_code=HTTPStatus(response.status_code),
        content=response.content,
        headers=response.headers,
        parsed=_parse_response(client=client, response=response),
    )


def sync_detailed(
    *,
    client: AuthenticatedClient | Client,
    role: InstitutionalRole | Unset = UNSET,
    unit: str | Unset = UNSET,
    include_deactivated: bool | Unset = False,
    limit: int | Unset = UNSET,
    offset: int | Unset = 0,
) -> Response[ErrorResponse | list[UserResponse]]:
    """List all users

     Requires `SUPER_ADMIN` or `UNIT_ADMIN`.

    Args:
        role (InstitutionalRole | Unset): Role assigned to a system user.
        unit (str | Unset):
        include_deactivated (bool | Unset):  Default: False.
        limit (int | Unset):
        offset (int | Unset):  Default: 0.

    Raises:
        errors.UnexpectedStatus: If the server returns an undocumented status code and Client.raise_on_unexpected_status is True.
        httpx.TimeoutException: If the request takes longer than Client.timeout.

    Returns:
        Response[ErrorResponse | list[UserResponse]]
    """

    kwargs = _get_kwargs(
        role=role,
        unit=unit,
        include_deactivated=include_deactivated,
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
    role: InstitutionalRole | Unset = UNSET,
    unit: str | Unset = UNSET,
    include_deactivated: bool | Unset = False,
    limit: int | Unset = UNSET,
    offset: int | Unset = 0,
) -> ErrorResponse | list[UserResponse] | None:
    """List all users

     Requires `SUPER_ADMIN` or `UNIT_ADMIN`.

    Args:
        role (InstitutionalRole | Unset): Role assigned to a system user.
        unit (str | Unset):
        include_deactivated (bool | Unset):  Default: False.
        limit (int | Unset):
        offset (int | Unset):  Default: 0.

    Raises:
        errors.UnexpectedStatus: If the server returns an undocumented status code and Client.raise_on_unexpected_status is True.
        httpx.TimeoutException: If the request takes longer than Client.timeout.

    Returns:
        ErrorResponse | list[UserResponse]
    """

    return sync_detailed(
        client=client,
        role=role,
        unit=unit,
        include_deactivated=include_deactivated,
        limit=limit,
        offset=offset,
    ).parsed


async def asyncio_detailed(
    *,
    client: AuthenticatedClient | Client,
    role: InstitutionalRole | Unset = UNSET,
    unit: str | Unset = UNSET,
    include_deactivated: bool | Unset = False,
    limit: int | Unset = UNSET,
    offset: int | Unset = 0,
) -> Response[ErrorResponse | list[UserResponse]]:
    """List all users

     Requires `SUPER_ADMIN` or `UNIT_ADMIN`.

    Args:
        role (InstitutionalRole | Unset): Role assigned to a system user.
        unit (str | Unset):
        include_deactivated (bool | Unset):  Default: False.
        limit (int | Unset):
        offset (int | Unset):  Default: 0.

    Raises:
        errors.UnexpectedStatus: If the server returns an undocumented status code and Client.raise_on_unexpected_status is True.
        httpx.TimeoutException: If the request takes longer than Client.timeout.

    Returns:
        Response[ErrorResponse | list[UserResponse]]
    """

    kwargs = _get_kwargs(
        role=role,
        unit=unit,
        include_deactivated=include_deactivated,
        limit=limit,
        offset=offset,
    )

    response = await client.get_async_httpx_client().request(**kwargs)

    return _build_response(client=client, response=response)


async def asyncio(
    *,
    client: AuthenticatedClient | Client,
    role: InstitutionalRole | Unset = UNSET,
    unit: str | Unset = UNSET,
    include_deactivated: bool | Unset = False,
    limit: int | Unset = UNSET,
    offset: int | Unset = 0,
) -> ErrorResponse | list[UserResponse] | None:
    """List all users

     Requires `SUPER_ADMIN` or `UNIT_ADMIN`.

    Args:
        role (InstitutionalRole | Unset): Role assigned to a system user.
        unit (str | Unset):
        include_deactivated (bool | Unset):  Default: False.
        limit (int | Unset):
        offset (int | Unset):  Default: 0.

    Raises:
        errors.UnexpectedStatus: If the server returns an undocumented status code and Client.raise_on_unexpected_status is True.
        httpx.TimeoutException: If the request takes longer than Client.timeout.

    Returns:
        ErrorResponse | list[UserResponse]
    """

    return (
        await asyncio_detailed(
            client=client,
            role=role,
            unit=unit,
            include_deactivated=include_deactivated,
            limit=limit,
            offset=offset,
        )
    ).parsed
