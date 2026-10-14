from http import HTTPStatus
from typing import Any
from urllib.parse import quote

import httpx

from ... import errors
from ...client import AuthenticatedClient, Client
from ...models.error_response import ErrorResponse
from ...models.requirement_response import RequirementResponse
from ...types import Response


def _get_kwargs(
    resource_id: int,
) -> dict[str, Any]:

    _kwargs: dict[str, Any] = {
        "method": "get",
        "url": "/api/v1/resources/{resource_id}/requirements".format(
            resource_id=quote(str(resource_id), safe=""),
        ),
    }

    return _kwargs


def _parse_response(
    *, client: AuthenticatedClient | Client, response: httpx.Response
) -> ErrorResponse | list[RequirementResponse] | None:
    if response.status_code == 200:
        response_200 = []
        _response_200 = response.json()
        for response_200_item_data in _response_200:
            response_200_item = RequirementResponse.from_dict(response_200_item_data)

            response_200.append(response_200_item)

        return response_200

    if response.status_code == 401:
        response_401 = ErrorResponse.from_dict(response.json())

        return response_401

    if response.status_code == 404:
        response_404 = ErrorResponse.from_dict(response.json())

        return response_404

    if client.raise_on_unexpected_status:
        raise errors.UnexpectedStatus(response.status_code, response.content)
    else:
        return None


def _build_response(
    *, client: AuthenticatedClient | Client, response: httpx.Response
) -> Response[ErrorResponse | list[RequirementResponse]]:
    return Response(
        status_code=HTTPStatus(response.status_code),
        content=response.content,
        headers=response.headers,
        parsed=_parse_response(client=client, response=response),
    )


def sync_detailed(
    resource_id: int,
    *,
    client: AuthenticatedClient | Client,
) -> Response[ErrorResponse | list[RequirementResponse]]:
    """What a resource requires

     Any signed-in user. The standing rules of the resource: using it also needs these. Booking the
    resource holds them, see `POST /api/v1/resources/{resource_id}/reservations`.

    Args:
        resource_id (int):

    Raises:
        errors.UnexpectedStatus: If the server returns an undocumented status code and Client.raise_on_unexpected_status is True.
        httpx.TimeoutException: If the request takes longer than Client.timeout.

    Returns:
        Response[ErrorResponse | list[RequirementResponse]]
    """

    kwargs = _get_kwargs(
        resource_id=resource_id,
    )

    response = client.get_httpx_client().request(
        **kwargs,
    )

    return _build_response(client=client, response=response)


def sync(
    resource_id: int,
    *,
    client: AuthenticatedClient | Client,
) -> ErrorResponse | list[RequirementResponse] | None:
    """What a resource requires

     Any signed-in user. The standing rules of the resource: using it also needs these. Booking the
    resource holds them, see `POST /api/v1/resources/{resource_id}/reservations`.

    Args:
        resource_id (int):

    Raises:
        errors.UnexpectedStatus: If the server returns an undocumented status code and Client.raise_on_unexpected_status is True.
        httpx.TimeoutException: If the request takes longer than Client.timeout.

    Returns:
        ErrorResponse | list[RequirementResponse]
    """

    return sync_detailed(
        resource_id=resource_id,
        client=client,
    ).parsed


async def asyncio_detailed(
    resource_id: int,
    *,
    client: AuthenticatedClient | Client,
) -> Response[ErrorResponse | list[RequirementResponse]]:
    """What a resource requires

     Any signed-in user. The standing rules of the resource: using it also needs these. Booking the
    resource holds them, see `POST /api/v1/resources/{resource_id}/reservations`.

    Args:
        resource_id (int):

    Raises:
        errors.UnexpectedStatus: If the server returns an undocumented status code and Client.raise_on_unexpected_status is True.
        httpx.TimeoutException: If the request takes longer than Client.timeout.

    Returns:
        Response[ErrorResponse | list[RequirementResponse]]
    """

    kwargs = _get_kwargs(
        resource_id=resource_id,
    )

    response = await client.get_async_httpx_client().request(**kwargs)

    return _build_response(client=client, response=response)


async def asyncio(
    resource_id: int,
    *,
    client: AuthenticatedClient | Client,
) -> ErrorResponse | list[RequirementResponse] | None:
    """What a resource requires

     Any signed-in user. The standing rules of the resource: using it also needs these. Booking the
    resource holds them, see `POST /api/v1/resources/{resource_id}/reservations`.

    Args:
        resource_id (int):

    Raises:
        errors.UnexpectedStatus: If the server returns an undocumented status code and Client.raise_on_unexpected_status is True.
        httpx.TimeoutException: If the request takes longer than Client.timeout.

    Returns:
        ErrorResponse | list[RequirementResponse]
    """

    return (
        await asyncio_detailed(
            resource_id=resource_id,
            client=client,
        )
    ).parsed
