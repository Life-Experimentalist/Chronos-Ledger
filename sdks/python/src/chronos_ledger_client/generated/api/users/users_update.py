from http import HTTPStatus
from typing import Any
from urllib.parse import quote

import httpx

from ... import errors
from ...client import AuthenticatedClient, Client
from ...models.error_response import ErrorResponse
from ...models.user_response import UserResponse
from ...models.user_update import UserUpdate
from ...types import Response


def _get_kwargs(
    user_id: str,
    *,
    body: UserUpdate,
) -> dict[str, Any]:
    headers: dict[str, Any] = {}

    _kwargs: dict[str, Any] = {
        "method": "patch",
        "url": "/api/v1/users/{user_id}".format(
            user_id=quote(str(user_id), safe=""),
        ),
    }

    _kwargs["json"] = body.to_dict()

    headers["Content-Type"] = "application/json"

    _kwargs["headers"] = headers
    return _kwargs


def _parse_response(
    *, client: AuthenticatedClient | Client, response: httpx.Response
) -> ErrorResponse | UserResponse | None:
    if response.status_code == 200:
        response_200 = UserResponse.from_dict(response.json())

        return response_200

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
    user_id: str,
    *,
    client: AuthenticatedClient | Client,
    body: UserUpdate,
) -> Response[ErrorResponse | UserResponse]:
    """Update a user

     Requires `SUPER_ADMIN` or `UNIT_ADMIN`, and a unit admin only within their own unit. Only a super-
    admin can modify an account that is itself an admin. A user cannot update their own record here.

    Args:
        user_id (str):
        body (UserUpdate): A field left out keeps its value and a null clears it, except full_name
            and email_address, which cannot be null (422).

    Raises:
        errors.UnexpectedStatus: If the server returns an undocumented status code and Client.raise_on_unexpected_status is True.
        httpx.TimeoutException: If the request takes longer than Client.timeout.

    Returns:
        Response[ErrorResponse | UserResponse]
    """

    kwargs = _get_kwargs(
        user_id=user_id,
        body=body,
    )

    response = client.get_httpx_client().request(
        **kwargs,
    )

    return _build_response(client=client, response=response)


def sync(
    user_id: str,
    *,
    client: AuthenticatedClient | Client,
    body: UserUpdate,
) -> ErrorResponse | UserResponse | None:
    """Update a user

     Requires `SUPER_ADMIN` or `UNIT_ADMIN`, and a unit admin only within their own unit. Only a super-
    admin can modify an account that is itself an admin. A user cannot update their own record here.

    Args:
        user_id (str):
        body (UserUpdate): A field left out keeps its value and a null clears it, except full_name
            and email_address, which cannot be null (422).

    Raises:
        errors.UnexpectedStatus: If the server returns an undocumented status code and Client.raise_on_unexpected_status is True.
        httpx.TimeoutException: If the request takes longer than Client.timeout.

    Returns:
        ErrorResponse | UserResponse
    """

    return sync_detailed(
        user_id=user_id,
        client=client,
        body=body,
    ).parsed


async def asyncio_detailed(
    user_id: str,
    *,
    client: AuthenticatedClient | Client,
    body: UserUpdate,
) -> Response[ErrorResponse | UserResponse]:
    """Update a user

     Requires `SUPER_ADMIN` or `UNIT_ADMIN`, and a unit admin only within their own unit. Only a super-
    admin can modify an account that is itself an admin. A user cannot update their own record here.

    Args:
        user_id (str):
        body (UserUpdate): A field left out keeps its value and a null clears it, except full_name
            and email_address, which cannot be null (422).

    Raises:
        errors.UnexpectedStatus: If the server returns an undocumented status code and Client.raise_on_unexpected_status is True.
        httpx.TimeoutException: If the request takes longer than Client.timeout.

    Returns:
        Response[ErrorResponse | UserResponse]
    """

    kwargs = _get_kwargs(
        user_id=user_id,
        body=body,
    )

    response = await client.get_async_httpx_client().request(**kwargs)

    return _build_response(client=client, response=response)


async def asyncio(
    user_id: str,
    *,
    client: AuthenticatedClient | Client,
    body: UserUpdate,
) -> ErrorResponse | UserResponse | None:
    """Update a user

     Requires `SUPER_ADMIN` or `UNIT_ADMIN`, and a unit admin only within their own unit. Only a super-
    admin can modify an account that is itself an admin. A user cannot update their own record here.

    Args:
        user_id (str):
        body (UserUpdate): A field left out keeps its value and a null clears it, except full_name
            and email_address, which cannot be null (422).

    Raises:
        errors.UnexpectedStatus: If the server returns an undocumented status code and Client.raise_on_unexpected_status is True.
        httpx.TimeoutException: If the request takes longer than Client.timeout.

    Returns:
        ErrorResponse | UserResponse
    """

    return (
        await asyncio_detailed(
            user_id=user_id,
            client=client,
            body=body,
        )
    ).parsed
