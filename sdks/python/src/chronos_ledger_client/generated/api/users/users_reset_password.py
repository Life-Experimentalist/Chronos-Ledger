from http import HTTPStatus
from typing import Any
from urllib.parse import quote

import httpx

from ... import errors
from ...client import AuthenticatedClient, Client
from ...models.error_response import ErrorResponse
from ...models.password_reset_response import PasswordResetResponse
from ...types import Response


def _get_kwargs(
    user_id: str,
) -> dict[str, Any]:

    _kwargs: dict[str, Any] = {
        "method": "post",
        "url": "/api/v1/users/{user_id}/reset-password".format(
            user_id=quote(str(user_id), safe=""),
        ),
    }

    return _kwargs


def _parse_response(
    *, client: AuthenticatedClient | Client, response: httpx.Response
) -> ErrorResponse | PasswordResetResponse | None:
    if response.status_code == 200:
        response_200 = PasswordResetResponse.from_dict(response.json())

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
) -> Response[ErrorResponse | PasswordResetResponse]:
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
) -> Response[ErrorResponse | PasswordResetResponse]:
    """Issue a new password for a user who cannot sign in

     The only route back into a locked-out account: change-password needs the password the user has lost,
    and no mail sender is configured. The new password is returned once and is never stored. The reset
    also drops every refresh token the user holds and rotates their calendar feed URL. A UNIT_ADMIN is
    limited to their own unit and may not reset an admin account.

    Args:
        user_id (str):

    Raises:
        errors.UnexpectedStatus: If the server returns an undocumented status code and Client.raise_on_unexpected_status is True.
        httpx.TimeoutException: If the request takes longer than Client.timeout.

    Returns:
        Response[ErrorResponse | PasswordResetResponse]
    """

    kwargs = _get_kwargs(
        user_id=user_id,
    )

    response = client.get_httpx_client().request(
        **kwargs,
    )

    return _build_response(client=client, response=response)


def sync(
    user_id: str,
    *,
    client: AuthenticatedClient | Client,
) -> ErrorResponse | PasswordResetResponse | None:
    """Issue a new password for a user who cannot sign in

     The only route back into a locked-out account: change-password needs the password the user has lost,
    and no mail sender is configured. The new password is returned once and is never stored. The reset
    also drops every refresh token the user holds and rotates their calendar feed URL. A UNIT_ADMIN is
    limited to their own unit and may not reset an admin account.

    Args:
        user_id (str):

    Raises:
        errors.UnexpectedStatus: If the server returns an undocumented status code and Client.raise_on_unexpected_status is True.
        httpx.TimeoutException: If the request takes longer than Client.timeout.

    Returns:
        ErrorResponse | PasswordResetResponse
    """

    return sync_detailed(
        user_id=user_id,
        client=client,
    ).parsed


async def asyncio_detailed(
    user_id: str,
    *,
    client: AuthenticatedClient | Client,
) -> Response[ErrorResponse | PasswordResetResponse]:
    """Issue a new password for a user who cannot sign in

     The only route back into a locked-out account: change-password needs the password the user has lost,
    and no mail sender is configured. The new password is returned once and is never stored. The reset
    also drops every refresh token the user holds and rotates their calendar feed URL. A UNIT_ADMIN is
    limited to their own unit and may not reset an admin account.

    Args:
        user_id (str):

    Raises:
        errors.UnexpectedStatus: If the server returns an undocumented status code and Client.raise_on_unexpected_status is True.
        httpx.TimeoutException: If the request takes longer than Client.timeout.

    Returns:
        Response[ErrorResponse | PasswordResetResponse]
    """

    kwargs = _get_kwargs(
        user_id=user_id,
    )

    response = await client.get_async_httpx_client().request(**kwargs)

    return _build_response(client=client, response=response)


async def asyncio(
    user_id: str,
    *,
    client: AuthenticatedClient | Client,
) -> ErrorResponse | PasswordResetResponse | None:
    """Issue a new password for a user who cannot sign in

     The only route back into a locked-out account: change-password needs the password the user has lost,
    and no mail sender is configured. The new password is returned once and is never stored. The reset
    also drops every refresh token the user holds and rotates their calendar feed URL. A UNIT_ADMIN is
    limited to their own unit and may not reset an admin account.

    Args:
        user_id (str):

    Raises:
        errors.UnexpectedStatus: If the server returns an undocumented status code and Client.raise_on_unexpected_status is True.
        httpx.TimeoutException: If the request takes longer than Client.timeout.

    Returns:
        ErrorResponse | PasswordResetResponse
    """

    return (
        await asyncio_detailed(
            user_id=user_id,
            client=client,
        )
    ).parsed
