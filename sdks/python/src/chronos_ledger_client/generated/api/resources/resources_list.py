from http import HTTPStatus
from typing import Any

import httpx

from ... import errors
from ...client import AuthenticatedClient, Client
from ...models.error_response import ErrorResponse
from ...models.resource_response import ResourceResponse
from ...models.resources_list_resource_type import ResourcesListResourceType
from ...types import UNSET, Response, Unset


def _get_kwargs(
    *,
    resource_type: ResourcesListResourceType | Unset = UNSET,
    active: bool | Unset = UNSET,
    code: str | Unset = UNSET,
    limit: int | Unset = UNSET,
    offset: int | Unset = 0,
) -> dict[str, Any]:

    params: dict[str, Any] = {}

    json_resource_type: str | Unset = UNSET
    if not isinstance(resource_type, Unset):
        json_resource_type = resource_type.value

    params["resource_type"] = json_resource_type

    params["active"] = active

    params["code"] = code

    params["limit"] = limit

    params["offset"] = offset

    params = {k: v for k, v in params.items() if v is not UNSET and v is not None}

    _kwargs: dict[str, Any] = {
        "method": "get",
        "url": "/api/v1/resources/",
        "params": params,
    }

    return _kwargs


def _parse_response(
    *, client: AuthenticatedClient | Client, response: httpx.Response
) -> ErrorResponse | list[ResourceResponse] | None:
    if response.status_code == 200:
        response_200 = []
        _response_200 = response.json()
        for response_200_item_data in _response_200:
            response_200_item = ResourceResponse.from_dict(response_200_item_data)

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
) -> Response[ErrorResponse | list[ResourceResponse]]:
    return Response(
        status_code=HTTPStatus(response.status_code),
        content=response.content,
        headers=response.headers,
        parsed=_parse_response(client=client, response=response),
    )


def sync_detailed(
    *,
    client: AuthenticatedClient | Client,
    resource_type: ResourcesListResourceType | Unset = UNSET,
    active: bool | Unset = UNSET,
    code: str | Unset = UNSET,
    limit: int | Unset = UNSET,
    offset: int | Unset = 0,
) -> Response[ErrorResponse | list[ResourceResponse]]:
    """List resources

     Every room, person and piece of equipment the schedule can point at. Readable by anyone signed in:
    an external system that has to book a room needs to be able to find it first.

    Args:
        resource_type (ResourcesListResourceType | Unset):
        active (bool | Unset):
        code (str | Unset):
        limit (int | Unset):
        offset (int | Unset):  Default: 0.

    Raises:
        errors.UnexpectedStatus: If the server returns an undocumented status code and Client.raise_on_unexpected_status is True.
        httpx.TimeoutException: If the request takes longer than Client.timeout.

    Returns:
        Response[ErrorResponse | list[ResourceResponse]]
    """

    kwargs = _get_kwargs(
        resource_type=resource_type,
        active=active,
        code=code,
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
    resource_type: ResourcesListResourceType | Unset = UNSET,
    active: bool | Unset = UNSET,
    code: str | Unset = UNSET,
    limit: int | Unset = UNSET,
    offset: int | Unset = 0,
) -> ErrorResponse | list[ResourceResponse] | None:
    """List resources

     Every room, person and piece of equipment the schedule can point at. Readable by anyone signed in:
    an external system that has to book a room needs to be able to find it first.

    Args:
        resource_type (ResourcesListResourceType | Unset):
        active (bool | Unset):
        code (str | Unset):
        limit (int | Unset):
        offset (int | Unset):  Default: 0.

    Raises:
        errors.UnexpectedStatus: If the server returns an undocumented status code and Client.raise_on_unexpected_status is True.
        httpx.TimeoutException: If the request takes longer than Client.timeout.

    Returns:
        ErrorResponse | list[ResourceResponse]
    """

    return sync_detailed(
        client=client,
        resource_type=resource_type,
        active=active,
        code=code,
        limit=limit,
        offset=offset,
    ).parsed


async def asyncio_detailed(
    *,
    client: AuthenticatedClient | Client,
    resource_type: ResourcesListResourceType | Unset = UNSET,
    active: bool | Unset = UNSET,
    code: str | Unset = UNSET,
    limit: int | Unset = UNSET,
    offset: int | Unset = 0,
) -> Response[ErrorResponse | list[ResourceResponse]]:
    """List resources

     Every room, person and piece of equipment the schedule can point at. Readable by anyone signed in:
    an external system that has to book a room needs to be able to find it first.

    Args:
        resource_type (ResourcesListResourceType | Unset):
        active (bool | Unset):
        code (str | Unset):
        limit (int | Unset):
        offset (int | Unset):  Default: 0.

    Raises:
        errors.UnexpectedStatus: If the server returns an undocumented status code and Client.raise_on_unexpected_status is True.
        httpx.TimeoutException: If the request takes longer than Client.timeout.

    Returns:
        Response[ErrorResponse | list[ResourceResponse]]
    """

    kwargs = _get_kwargs(
        resource_type=resource_type,
        active=active,
        code=code,
        limit=limit,
        offset=offset,
    )

    response = await client.get_async_httpx_client().request(**kwargs)

    return _build_response(client=client, response=response)


async def asyncio(
    *,
    client: AuthenticatedClient | Client,
    resource_type: ResourcesListResourceType | Unset = UNSET,
    active: bool | Unset = UNSET,
    code: str | Unset = UNSET,
    limit: int | Unset = UNSET,
    offset: int | Unset = 0,
) -> ErrorResponse | list[ResourceResponse] | None:
    """List resources

     Every room, person and piece of equipment the schedule can point at. Readable by anyone signed in:
    an external system that has to book a room needs to be able to find it first.

    Args:
        resource_type (ResourcesListResourceType | Unset):
        active (bool | Unset):
        code (str | Unset):
        limit (int | Unset):
        offset (int | Unset):  Default: 0.

    Raises:
        errors.UnexpectedStatus: If the server returns an undocumented status code and Client.raise_on_unexpected_status is True.
        httpx.TimeoutException: If the request takes longer than Client.timeout.

    Returns:
        ErrorResponse | list[ResourceResponse]
    """

    return (
        await asyncio_detailed(
            client=client,
            resource_type=resource_type,
            active=active,
            code=code,
            limit=limit,
            offset=offset,
        )
    ).parsed
