from http import HTTPStatus
from typing import Any
from urllib.parse import quote

import httpx

from ... import errors
from ...client import AuthenticatedClient, Client
from ...models.error_response import ErrorResponse
from ...models.role_map_entry_create import RoleMapEntryCreate
from ...models.role_map_entry_response import RoleMapEntryResponse
from ...types import Response


def _get_kwargs(
    issuer_id: int,
    *,
    body: RoleMapEntryCreate,
) -> dict[str, Any]:
    headers: dict[str, Any] = {}

    _kwargs: dict[str, Any] = {
        "method": "post",
        "url": "/api/v1/federation/issuers/{issuer_id}/role-map".format(
            issuer_id=quote(str(issuer_id), safe=""),
        ),
    }

    _kwargs["json"] = body.to_dict()

    headers["Content-Type"] = "application/json"

    _kwargs["headers"] = headers
    return _kwargs


def _parse_response(
    *, client: AuthenticatedClient | Client, response: httpx.Response
) -> ErrorResponse | RoleMapEntryResponse | None:
    if response.status_code == 201:
        response_201 = RoleMapEntryResponse.from_dict(response.json())

        return response_201

    if response.status_code == 401:
        response_401 = ErrorResponse.from_dict(response.json())

        return response_401

    if response.status_code == 403:
        response_403 = ErrorResponse.from_dict(response.json())

        return response_403

    if response.status_code == 404:
        response_404 = ErrorResponse.from_dict(response.json())

        return response_404

    if response.status_code == 409:
        response_409 = ErrorResponse.from_dict(response.json())

        return response_409

    if response.status_code == 422:
        response_422 = ErrorResponse.from_dict(response.json())

        return response_422

    if client.raise_on_unexpected_status:
        raise errors.UnexpectedStatus(response.status_code, response.content)
    else:
        return None


def _build_response(
    *, client: AuthenticatedClient | Client, response: httpx.Response
) -> Response[ErrorResponse | RoleMapEntryResponse]:
    return Response(
        status_code=HTTPStatus(response.status_code),
        content=response.content,
        headers=response.headers,
        parsed=_parse_response(client=client, response=response),
    )


def sync_detailed(
    issuer_id: int,
    *,
    client: AuthenticatedClient | Client,
    body: RoleMapEntryCreate,
) -> Response[ErrorResponse | RoleMapEntryResponse]:
    """Map a group to a role

     Requires `ORG_ADMIN`. The map belongs to the operator: a note names a subject and may name groups,
    and never a role. Two groups may map to different units, which is the ordinary case for a library
    and a lab.

    Args:
        issuer_id (int):
        body (RoleMapEntryCreate):

    Raises:
        errors.UnexpectedStatus: If the server returns an undocumented status code and Client.raise_on_unexpected_status is True.
        httpx.TimeoutException: If the request takes longer than Client.timeout.

    Returns:
        Response[ErrorResponse | RoleMapEntryResponse]
    """

    kwargs = _get_kwargs(
        issuer_id=issuer_id,
        body=body,
    )

    response = client.get_httpx_client().request(
        **kwargs,
    )

    return _build_response(client=client, response=response)


def sync(
    issuer_id: int,
    *,
    client: AuthenticatedClient | Client,
    body: RoleMapEntryCreate,
) -> ErrorResponse | RoleMapEntryResponse | None:
    """Map a group to a role

     Requires `ORG_ADMIN`. The map belongs to the operator: a note names a subject and may name groups,
    and never a role. Two groups may map to different units, which is the ordinary case for a library
    and a lab.

    Args:
        issuer_id (int):
        body (RoleMapEntryCreate):

    Raises:
        errors.UnexpectedStatus: If the server returns an undocumented status code and Client.raise_on_unexpected_status is True.
        httpx.TimeoutException: If the request takes longer than Client.timeout.

    Returns:
        ErrorResponse | RoleMapEntryResponse
    """

    return sync_detailed(
        issuer_id=issuer_id,
        client=client,
        body=body,
    ).parsed


async def asyncio_detailed(
    issuer_id: int,
    *,
    client: AuthenticatedClient | Client,
    body: RoleMapEntryCreate,
) -> Response[ErrorResponse | RoleMapEntryResponse]:
    """Map a group to a role

     Requires `ORG_ADMIN`. The map belongs to the operator: a note names a subject and may name groups,
    and never a role. Two groups may map to different units, which is the ordinary case for a library
    and a lab.

    Args:
        issuer_id (int):
        body (RoleMapEntryCreate):

    Raises:
        errors.UnexpectedStatus: If the server returns an undocumented status code and Client.raise_on_unexpected_status is True.
        httpx.TimeoutException: If the request takes longer than Client.timeout.

    Returns:
        Response[ErrorResponse | RoleMapEntryResponse]
    """

    kwargs = _get_kwargs(
        issuer_id=issuer_id,
        body=body,
    )

    response = await client.get_async_httpx_client().request(**kwargs)

    return _build_response(client=client, response=response)


async def asyncio(
    issuer_id: int,
    *,
    client: AuthenticatedClient | Client,
    body: RoleMapEntryCreate,
) -> ErrorResponse | RoleMapEntryResponse | None:
    """Map a group to a role

     Requires `ORG_ADMIN`. The map belongs to the operator: a note names a subject and may name groups,
    and never a role. Two groups may map to different units, which is the ordinary case for a library
    and a lab.

    Args:
        issuer_id (int):
        body (RoleMapEntryCreate):

    Raises:
        errors.UnexpectedStatus: If the server returns an undocumented status code and Client.raise_on_unexpected_status is True.
        httpx.TimeoutException: If the request takes longer than Client.timeout.

    Returns:
        ErrorResponse | RoleMapEntryResponse
    """

    return (
        await asyncio_detailed(
            issuer_id=issuer_id,
            client=client,
            body=body,
        )
    ).parsed
