from http import HTTPStatus
from typing import Any
from urllib.parse import quote

import httpx

from ... import errors
from ...client import AuthenticatedClient, Client
from ...models.error_response import ErrorResponse
from ...models.user_status_update import UserStatusUpdate
from ...models.users_update_status_response_200 import UsersUpdateStatusResponse200
from ...types import Response


def _get_kwargs(
    user_id: str,
    *,
    body: UserStatusUpdate,
) -> dict[str, Any]:
    headers: dict[str, Any] = {}

    _kwargs: dict[str, Any] = {
        "method": "put",
        "url": "/api/v1/users/{user_id}/status".format(
            user_id=quote(str(user_id), safe=""),
        ),
    }

    _kwargs["json"] = body.to_dict()

    headers["Content-Type"] = "application/json"

    _kwargs["headers"] = headers
    return _kwargs


def _parse_response(
    *, client: AuthenticatedClient | Client, response: httpx.Response
) -> ErrorResponse | UsersUpdateStatusResponse200 | None:
    if response.status_code == 200:
        response_200 = UsersUpdateStatusResponse200.from_dict(response.json())

        return response_200

    if response.status_code == 403:
        response_403 = ErrorResponse.from_dict(response.json())

        return response_403

    if response.status_code == 404:
        response_404 = ErrorResponse.from_dict(response.json())

        return response_404

    if client.raise_on_unexpected_status:
        raise errors.UnexpectedStatus(response.status_code, response.content)
    else:
        return None


def _build_response(
    *, client: AuthenticatedClient | Client, response: httpx.Response
) -> Response[ErrorResponse | UsersUpdateStatusResponse200]:
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
    body: UserStatusUpdate,
) -> Response[ErrorResponse | UsersUpdateStatusResponse200]:
    """Update staff availability status

     Anyone signed in can update their own. A super-admin can update anyone's. This is the occupancy
    index, and it does not change the location the location routes resolve.

    Args:
        user_id (str):
        body (UserStatusUpdate):

    Raises:
        errors.UnexpectedStatus: If the server returns an undocumented status code and Client.raise_on_unexpected_status is True.
        httpx.TimeoutException: If the request takes longer than Client.timeout.

    Returns:
        Response[ErrorResponse | UsersUpdateStatusResponse200]
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
    body: UserStatusUpdate,
) -> ErrorResponse | UsersUpdateStatusResponse200 | None:
    """Update staff availability status

     Anyone signed in can update their own. A super-admin can update anyone's. This is the occupancy
    index, and it does not change the location the location routes resolve.

    Args:
        user_id (str):
        body (UserStatusUpdate):

    Raises:
        errors.UnexpectedStatus: If the server returns an undocumented status code and Client.raise_on_unexpected_status is True.
        httpx.TimeoutException: If the request takes longer than Client.timeout.

    Returns:
        ErrorResponse | UsersUpdateStatusResponse200
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
    body: UserStatusUpdate,
) -> Response[ErrorResponse | UsersUpdateStatusResponse200]:
    """Update staff availability status

     Anyone signed in can update their own. A super-admin can update anyone's. This is the occupancy
    index, and it does not change the location the location routes resolve.

    Args:
        user_id (str):
        body (UserStatusUpdate):

    Raises:
        errors.UnexpectedStatus: If the server returns an undocumented status code and Client.raise_on_unexpected_status is True.
        httpx.TimeoutException: If the request takes longer than Client.timeout.

    Returns:
        Response[ErrorResponse | UsersUpdateStatusResponse200]
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
    body: UserStatusUpdate,
) -> ErrorResponse | UsersUpdateStatusResponse200 | None:
    """Update staff availability status

     Anyone signed in can update their own. A super-admin can update anyone's. This is the occupancy
    index, and it does not change the location the location routes resolve.

    Args:
        user_id (str):
        body (UserStatusUpdate):

    Raises:
        errors.UnexpectedStatus: If the server returns an undocumented status code and Client.raise_on_unexpected_status is True.
        httpx.TimeoutException: If the request takes longer than Client.timeout.

    Returns:
        ErrorResponse | UsersUpdateStatusResponse200
    """

    return (
        await asyncio_detailed(
            user_id=user_id,
            client=client,
            body=body,
        )
    ).parsed
