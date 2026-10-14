from http import HTTPStatus
from typing import Any

import httpx

from ... import errors
from ...client import AuthenticatedClient, Client
from ...models.error_response import ErrorResponse
from ...models.organization_response import OrganizationResponse
from ...models.organization_update import OrganizationUpdate
from ...types import UNSET, Response, Unset


def _get_kwargs(
    *,
    body: OrganizationUpdate,
    idempotency_key: str | Unset = UNSET,
) -> dict[str, Any]:
    headers: dict[str, Any] = {}
    if not isinstance(idempotency_key, Unset):
        headers["Idempotency-Key"] = idempotency_key

    _kwargs: dict[str, Any] = {
        "method": "patch",
        "url": "/api/v1/admin/organization",
    }

    _kwargs["json"] = body.to_dict()

    headers["Content-Type"] = "application/json"

    _kwargs["headers"] = headers
    return _kwargs


def _parse_response(
    *, client: AuthenticatedClient | Client, response: httpx.Response
) -> ErrorResponse | OrganizationResponse | None:
    if response.status_code == 200:
        response_200 = OrganizationResponse.from_dict(response.json())

        return response_200

    if response.status_code == 401:
        response_401 = ErrorResponse.from_dict(response.json())

        return response_401

    if response.status_code == 403:
        response_403 = ErrorResponse.from_dict(response.json())

        return response_403

    if response.status_code == 422:
        response_422 = ErrorResponse.from_dict(response.json())

        return response_422

    if client.raise_on_unexpected_status:
        raise errors.UnexpectedStatus(response.status_code, response.content)
    else:
        return None


def _build_response(
    *, client: AuthenticatedClient | Client, response: httpx.Response
) -> Response[ErrorResponse | OrganizationResponse]:
    return Response(
        status_code=HTTPStatus(response.status_code),
        content=response.content,
        headers=response.headers,
        parsed=_parse_response(client=client, response=response),
    )


def sync_detailed(
    *,
    client: AuthenticatedClient | Client,
    body: OrganizationUpdate,
    idempotency_key: str | Unset = UNSET,
) -> Response[ErrorResponse | OrganizationResponse]:
    """Change the organization's settings

     Requires `ORG_ADMIN`; an API key needs `admin:write`. Today the one setting is
    `default_requirement_enforcement`, what a requirement with no enforcement of its own does. It
    applies from the next booking.

    Args:
        idempotency_key (str | Unset):
        body (OrganizationUpdate):

    Raises:
        errors.UnexpectedStatus: If the server returns an undocumented status code and Client.raise_on_unexpected_status is True.
        httpx.TimeoutException: If the request takes longer than Client.timeout.

    Returns:
        Response[ErrorResponse | OrganizationResponse]
    """

    kwargs = _get_kwargs(
        body=body,
        idempotency_key=idempotency_key,
    )

    response = client.get_httpx_client().request(
        **kwargs,
    )

    return _build_response(client=client, response=response)


def sync(
    *,
    client: AuthenticatedClient | Client,
    body: OrganizationUpdate,
    idempotency_key: str | Unset = UNSET,
) -> ErrorResponse | OrganizationResponse | None:
    """Change the organization's settings

     Requires `ORG_ADMIN`; an API key needs `admin:write`. Today the one setting is
    `default_requirement_enforcement`, what a requirement with no enforcement of its own does. It
    applies from the next booking.

    Args:
        idempotency_key (str | Unset):
        body (OrganizationUpdate):

    Raises:
        errors.UnexpectedStatus: If the server returns an undocumented status code and Client.raise_on_unexpected_status is True.
        httpx.TimeoutException: If the request takes longer than Client.timeout.

    Returns:
        ErrorResponse | OrganizationResponse
    """

    return sync_detailed(
        client=client,
        body=body,
        idempotency_key=idempotency_key,
    ).parsed


async def asyncio_detailed(
    *,
    client: AuthenticatedClient | Client,
    body: OrganizationUpdate,
    idempotency_key: str | Unset = UNSET,
) -> Response[ErrorResponse | OrganizationResponse]:
    """Change the organization's settings

     Requires `ORG_ADMIN`; an API key needs `admin:write`. Today the one setting is
    `default_requirement_enforcement`, what a requirement with no enforcement of its own does. It
    applies from the next booking.

    Args:
        idempotency_key (str | Unset):
        body (OrganizationUpdate):

    Raises:
        errors.UnexpectedStatus: If the server returns an undocumented status code and Client.raise_on_unexpected_status is True.
        httpx.TimeoutException: If the request takes longer than Client.timeout.

    Returns:
        Response[ErrorResponse | OrganizationResponse]
    """

    kwargs = _get_kwargs(
        body=body,
        idempotency_key=idempotency_key,
    )

    response = await client.get_async_httpx_client().request(**kwargs)

    return _build_response(client=client, response=response)


async def asyncio(
    *,
    client: AuthenticatedClient | Client,
    body: OrganizationUpdate,
    idempotency_key: str | Unset = UNSET,
) -> ErrorResponse | OrganizationResponse | None:
    """Change the organization's settings

     Requires `ORG_ADMIN`; an API key needs `admin:write`. Today the one setting is
    `default_requirement_enforcement`, what a requirement with no enforcement of its own does. It
    applies from the next booking.

    Args:
        idempotency_key (str | Unset):
        body (OrganizationUpdate):

    Raises:
        errors.UnexpectedStatus: If the server returns an undocumented status code and Client.raise_on_unexpected_status is True.
        httpx.TimeoutException: If the request takes longer than Client.timeout.

    Returns:
        ErrorResponse | OrganizationResponse
    """

    return (
        await asyncio_detailed(
            client=client,
            body=body,
            idempotency_key=idempotency_key,
        )
    ).parsed
