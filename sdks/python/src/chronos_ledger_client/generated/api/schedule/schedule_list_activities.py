from http import HTTPStatus
from typing import Any

import httpx

from ... import errors
from ...client import AuthenticatedClient, Client
from ...models.activity_response import ActivityResponse
from ...models.error_response import ErrorResponse
from ...types import UNSET, Response, Unset


def _get_kwargs(
    *,
    cycle_id: int | Unset = UNSET,
    include_retired: bool | Unset = False,
    limit: int | Unset = UNSET,
    offset: int | Unset = 0,
) -> dict[str, Any]:

    params: dict[str, Any] = {}

    params["cycle_id"] = cycle_id

    params["include_retired"] = include_retired

    params["limit"] = limit

    params["offset"] = offset

    params = {k: v for k, v in params.items() if v is not UNSET and v is not None}

    _kwargs: dict[str, Any] = {
        "method": "get",
        "url": "/api/v1/schedule/activities",
        "params": params,
    }

    return _kwargs


def _parse_response(
    *, client: AuthenticatedClient | Client, response: httpx.Response
) -> ErrorResponse | list[ActivityResponse] | None:
    if response.status_code == 200:
        response_200 = []
        _response_200 = response.json()
        for response_200_item_data in _response_200:
            response_200_item = ActivityResponse.from_dict(response_200_item_data)

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
) -> Response[ErrorResponse | list[ActivityResponse]]:
    return Response(
        status_code=HTTPStatus(response.status_code),
        content=response.content,
        headers=response.headers,
        parsed=_parse_response(client=client, response=response),
    )


def sync_detailed(
    *,
    client: AuthenticatedClient | Client,
    cycle_id: int | Unset = UNSET,
    include_retired: bool | Unset = False,
    limit: int | Unset = UNSET,
    offset: int | Unset = 0,
) -> Response[ErrorResponse | list[ActivityResponse]]:
    """List activities

     Any signed-in user. Retired activities are left out unless `include_retired` is set.

    Args:
        cycle_id (int | Unset):
        include_retired (bool | Unset):  Default: False.
        limit (int | Unset):
        offset (int | Unset):  Default: 0.

    Raises:
        errors.UnexpectedStatus: If the server returns an undocumented status code and Client.raise_on_unexpected_status is True.
        httpx.TimeoutException: If the request takes longer than Client.timeout.

    Returns:
        Response[ErrorResponse | list[ActivityResponse]]
    """

    kwargs = _get_kwargs(
        cycle_id=cycle_id,
        include_retired=include_retired,
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
    cycle_id: int | Unset = UNSET,
    include_retired: bool | Unset = False,
    limit: int | Unset = UNSET,
    offset: int | Unset = 0,
) -> ErrorResponse | list[ActivityResponse] | None:
    """List activities

     Any signed-in user. Retired activities are left out unless `include_retired` is set.

    Args:
        cycle_id (int | Unset):
        include_retired (bool | Unset):  Default: False.
        limit (int | Unset):
        offset (int | Unset):  Default: 0.

    Raises:
        errors.UnexpectedStatus: If the server returns an undocumented status code and Client.raise_on_unexpected_status is True.
        httpx.TimeoutException: If the request takes longer than Client.timeout.

    Returns:
        ErrorResponse | list[ActivityResponse]
    """

    return sync_detailed(
        client=client,
        cycle_id=cycle_id,
        include_retired=include_retired,
        limit=limit,
        offset=offset,
    ).parsed


async def asyncio_detailed(
    *,
    client: AuthenticatedClient | Client,
    cycle_id: int | Unset = UNSET,
    include_retired: bool | Unset = False,
    limit: int | Unset = UNSET,
    offset: int | Unset = 0,
) -> Response[ErrorResponse | list[ActivityResponse]]:
    """List activities

     Any signed-in user. Retired activities are left out unless `include_retired` is set.

    Args:
        cycle_id (int | Unset):
        include_retired (bool | Unset):  Default: False.
        limit (int | Unset):
        offset (int | Unset):  Default: 0.

    Raises:
        errors.UnexpectedStatus: If the server returns an undocumented status code and Client.raise_on_unexpected_status is True.
        httpx.TimeoutException: If the request takes longer than Client.timeout.

    Returns:
        Response[ErrorResponse | list[ActivityResponse]]
    """

    kwargs = _get_kwargs(
        cycle_id=cycle_id,
        include_retired=include_retired,
        limit=limit,
        offset=offset,
    )

    response = await client.get_async_httpx_client().request(**kwargs)

    return _build_response(client=client, response=response)


async def asyncio(
    *,
    client: AuthenticatedClient | Client,
    cycle_id: int | Unset = UNSET,
    include_retired: bool | Unset = False,
    limit: int | Unset = UNSET,
    offset: int | Unset = 0,
) -> ErrorResponse | list[ActivityResponse] | None:
    """List activities

     Any signed-in user. Retired activities are left out unless `include_retired` is set.

    Args:
        cycle_id (int | Unset):
        include_retired (bool | Unset):  Default: False.
        limit (int | Unset):
        offset (int | Unset):  Default: 0.

    Raises:
        errors.UnexpectedStatus: If the server returns an undocumented status code and Client.raise_on_unexpected_status is True.
        httpx.TimeoutException: If the request takes longer than Client.timeout.

    Returns:
        ErrorResponse | list[ActivityResponse]
    """

    return (
        await asyncio_detailed(
            client=client,
            cycle_id=cycle_id,
            include_retired=include_retired,
            limit=limit,
            offset=offset,
        )
    ).parsed
