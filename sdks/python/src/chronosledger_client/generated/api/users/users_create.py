from http import HTTPStatus
from typing import Any

import httpx

from ... import errors
from ...client import AuthenticatedClient, Client
from ...models.error_response import ErrorResponse
from ...models.user_create import UserCreate
from ...models.user_response import UserResponse
from ...types import UNSET, Response, Unset


def _get_kwargs(
    *,
    body: UserCreate,
    idempotency_key: str | Unset = UNSET,
) -> dict[str, Any]:
    headers: dict[str, Any] = {}
    if not isinstance(idempotency_key, Unset):
        headers["Idempotency-Key"] = idempotency_key

    _kwargs: dict[str, Any] = {
        "method": "post",
        "url": "/api/v1/users/",
    }

    _kwargs["json"] = body.to_dict()

    headers["Content-Type"] = "application/json"

    _kwargs["headers"] = headers
    return _kwargs


def _parse_response(
    *, client: AuthenticatedClient | Client, response: httpx.Response
) -> ErrorResponse | UserResponse | None:
    if response.status_code == 201:
        response_201 = UserResponse.from_dict(response.json())

        return response_201

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
) -> Response[ErrorResponse | UserResponse]:
    return Response(
        status_code=HTTPStatus(response.status_code),
        content=response.content,
        headers=response.headers,
        parsed=_parse_response(client=client, response=response),
    )


def sync_detailed(
    *,
    client: AuthenticatedClient | Client,
    body: UserCreate,
    idempotency_key: str | Unset = UNSET,
) -> Response[ErrorResponse | UserResponse]:
    """Create a new user

     Requires `ORG_ADMIN` or `UNIT_ADMIN`. A unit admin can create users only in their own unit, and only
    an organization admin can create an admin account; either is refused with `403`.

    Args:
        idempotency_key (str | Unset):
        body (UserCreate):

    Raises:
        errors.UnexpectedStatus: If the server returns an undocumented status code and Client.raise_on_unexpected_status is True.
        httpx.TimeoutException: If the request takes longer than Client.timeout.

    Returns:
        Response[ErrorResponse | UserResponse]
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
    body: UserCreate,
    idempotency_key: str | Unset = UNSET,
) -> ErrorResponse | UserResponse | None:
    """Create a new user

     Requires `ORG_ADMIN` or `UNIT_ADMIN`. A unit admin can create users only in their own unit, and only
    an organization admin can create an admin account; either is refused with `403`.

    Args:
        idempotency_key (str | Unset):
        body (UserCreate):

    Raises:
        errors.UnexpectedStatus: If the server returns an undocumented status code and Client.raise_on_unexpected_status is True.
        httpx.TimeoutException: If the request takes longer than Client.timeout.

    Returns:
        ErrorResponse | UserResponse
    """

    return sync_detailed(
        client=client,
        body=body,
        idempotency_key=idempotency_key,
    ).parsed


async def asyncio_detailed(
    *,
    client: AuthenticatedClient | Client,
    body: UserCreate,
    idempotency_key: str | Unset = UNSET,
) -> Response[ErrorResponse | UserResponse]:
    """Create a new user

     Requires `ORG_ADMIN` or `UNIT_ADMIN`. A unit admin can create users only in their own unit, and only
    an organization admin can create an admin account; either is refused with `403`.

    Args:
        idempotency_key (str | Unset):
        body (UserCreate):

    Raises:
        errors.UnexpectedStatus: If the server returns an undocumented status code and Client.raise_on_unexpected_status is True.
        httpx.TimeoutException: If the request takes longer than Client.timeout.

    Returns:
        Response[ErrorResponse | UserResponse]
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
    body: UserCreate,
    idempotency_key: str | Unset = UNSET,
) -> ErrorResponse | UserResponse | None:
    """Create a new user

     Requires `ORG_ADMIN` or `UNIT_ADMIN`. A unit admin can create users only in their own unit, and only
    an organization admin can create an admin account; either is refused with `403`.

    Args:
        idempotency_key (str | Unset):
        body (UserCreate):

    Raises:
        errors.UnexpectedStatus: If the server returns an undocumented status code and Client.raise_on_unexpected_status is True.
        httpx.TimeoutException: If the request takes longer than Client.timeout.

    Returns:
        ErrorResponse | UserResponse
    """

    return (
        await asyncio_detailed(
            client=client,
            body=body,
            idempotency_key=idempotency_key,
        )
    ).parsed
