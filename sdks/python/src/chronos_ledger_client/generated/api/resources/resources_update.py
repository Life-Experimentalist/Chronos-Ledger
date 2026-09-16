from http import HTTPStatus
from typing import Any
from urllib.parse import quote

import httpx

from ... import errors
from ...client import AuthenticatedClient, Client
from ...models.error_response import ErrorResponse
from ...models.resource_response import ResourceResponse
from ...models.resource_update import ResourceUpdate
from ...types import Response


def _get_kwargs(
    resource_id: int,
    *,
    body: ResourceUpdate,
) -> dict[str, Any]:
    headers: dict[str, Any] = {}

    _kwargs: dict[str, Any] = {
        "method": "patch",
        "url": "/api/v1/resources/{resource_id}".format(
            resource_id=quote(str(resource_id), safe=""),
        ),
    }

    _kwargs["json"] = body.to_dict()

    headers["Content-Type"] = "application/json"

    _kwargs["headers"] = headers
    return _kwargs


def _parse_response(
    *, client: AuthenticatedClient | Client, response: httpx.Response
) -> ErrorResponse | ResourceResponse | None:
    if response.status_code == 200:
        response_200 = ResourceResponse.from_dict(response.json())

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

    if response.status_code == 422:
        response_422 = ErrorResponse.from_dict(response.json())

        return response_422

    if client.raise_on_unexpected_status:
        raise errors.UnexpectedStatus(response.status_code, response.content)
    else:
        return None


def _build_response(
    *, client: AuthenticatedClient | Client, response: httpx.Response
) -> Response[ErrorResponse | ResourceResponse]:
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
    body: ResourceUpdate,
) -> Response[ErrorResponse | ResourceResponse]:
    """Update a resource

     Fill in what a CSV could not know: capacity, and where the room physically is. Setting latitude and
    longitude is what switches geofencing on for every session held there.

    Args:
        resource_id (int):
        body (ResourceUpdate): Every field is optional and a field left out is left alone. code,
            resource_type and user_id are absent on purpose: code is the importer's match key, and a
            room that becomes a person is a different resource, not an edit.

    Raises:
        errors.UnexpectedStatus: If the server returns an undocumented status code and Client.raise_on_unexpected_status is True.
        httpx.TimeoutException: If the request takes longer than Client.timeout.

    Returns:
        Response[ErrorResponse | ResourceResponse]
    """

    kwargs = _get_kwargs(
        resource_id=resource_id,
        body=body,
    )

    response = client.get_httpx_client().request(
        **kwargs,
    )

    return _build_response(client=client, response=response)


def sync(
    resource_id: int,
    *,
    client: AuthenticatedClient | Client,
    body: ResourceUpdate,
) -> ErrorResponse | ResourceResponse | None:
    """Update a resource

     Fill in what a CSV could not know: capacity, and where the room physically is. Setting latitude and
    longitude is what switches geofencing on for every session held there.

    Args:
        resource_id (int):
        body (ResourceUpdate): Every field is optional and a field left out is left alone. code,
            resource_type and user_id are absent on purpose: code is the importer's match key, and a
            room that becomes a person is a different resource, not an edit.

    Raises:
        errors.UnexpectedStatus: If the server returns an undocumented status code and Client.raise_on_unexpected_status is True.
        httpx.TimeoutException: If the request takes longer than Client.timeout.

    Returns:
        ErrorResponse | ResourceResponse
    """

    return sync_detailed(
        resource_id=resource_id,
        client=client,
        body=body,
    ).parsed


async def asyncio_detailed(
    resource_id: int,
    *,
    client: AuthenticatedClient | Client,
    body: ResourceUpdate,
) -> Response[ErrorResponse | ResourceResponse]:
    """Update a resource

     Fill in what a CSV could not know: capacity, and where the room physically is. Setting latitude and
    longitude is what switches geofencing on for every session held there.

    Args:
        resource_id (int):
        body (ResourceUpdate): Every field is optional and a field left out is left alone. code,
            resource_type and user_id are absent on purpose: code is the importer's match key, and a
            room that becomes a person is a different resource, not an edit.

    Raises:
        errors.UnexpectedStatus: If the server returns an undocumented status code and Client.raise_on_unexpected_status is True.
        httpx.TimeoutException: If the request takes longer than Client.timeout.

    Returns:
        Response[ErrorResponse | ResourceResponse]
    """

    kwargs = _get_kwargs(
        resource_id=resource_id,
        body=body,
    )

    response = await client.get_async_httpx_client().request(**kwargs)

    return _build_response(client=client, response=response)


async def asyncio(
    resource_id: int,
    *,
    client: AuthenticatedClient | Client,
    body: ResourceUpdate,
) -> ErrorResponse | ResourceResponse | None:
    """Update a resource

     Fill in what a CSV could not know: capacity, and where the room physically is. Setting latitude and
    longitude is what switches geofencing on for every session held there.

    Args:
        resource_id (int):
        body (ResourceUpdate): Every field is optional and a field left out is left alone. code,
            resource_type and user_id are absent on purpose: code is the importer's match key, and a
            room that becomes a person is a different resource, not an edit.

    Raises:
        errors.UnexpectedStatus: If the server returns an undocumented status code and Client.raise_on_unexpected_status is True.
        httpx.TimeoutException: If the request takes longer than Client.timeout.

    Returns:
        ErrorResponse | ResourceResponse
    """

    return (
        await asyncio_detailed(
            resource_id=resource_id,
            client=client,
            body=body,
        )
    ).parsed
