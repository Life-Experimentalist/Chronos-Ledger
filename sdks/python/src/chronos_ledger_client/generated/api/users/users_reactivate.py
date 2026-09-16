from http import HTTPStatus
from typing import Any
from urllib.parse import quote

import httpx

from ... import errors
from ...client import AuthenticatedClient, Client
from ...models.error_response import ErrorResponse
from ...models.user_response import UserResponse
from ...types import Response


def _get_kwargs(
    user_id: str,
) -> dict[str, Any]:

    _kwargs: dict[str, Any] = {
        "method": "post",
        "url": "/api/v1/users/{user_id}/reactivate".format(
            user_id=quote(str(user_id), safe=""),
        ),
    }

    return _kwargs


def _parse_response(
    *, client: AuthenticatedClient | Client, response: httpx.Response
) -> ErrorResponse | UserResponse | None:
    if response.status_code == 200:
        response_200 = UserResponse.from_dict(response.json())

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
) -> Response[ErrorResponse | UserResponse]:
    """Let a deactivated account back in

     The password works again as it was. The API keys do not come back, since deactivating deleted them,
    and neither does the calendar feed URL: deactivating rotated it, so the person fetches the new one.
    If the old password should not work again, a reset-password afterwards issues a new one. Calling it
    on an active account changes nothing. A UNIT_ADMIN has the same limits as for deactivating.

    Args:
        user_id (str):

    Raises:
        errors.UnexpectedStatus: If the server returns an undocumented status code and Client.raise_on_unexpected_status is True.
        httpx.TimeoutException: If the request takes longer than Client.timeout.

    Returns:
        Response[ErrorResponse | UserResponse]
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
) -> ErrorResponse | UserResponse | None:
    """Let a deactivated account back in

     The password works again as it was. The API keys do not come back, since deactivating deleted them,
    and neither does the calendar feed URL: deactivating rotated it, so the person fetches the new one.
    If the old password should not work again, a reset-password afterwards issues a new one. Calling it
    on an active account changes nothing. A UNIT_ADMIN has the same limits as for deactivating.

    Args:
        user_id (str):

    Raises:
        errors.UnexpectedStatus: If the server returns an undocumented status code and Client.raise_on_unexpected_status is True.
        httpx.TimeoutException: If the request takes longer than Client.timeout.

    Returns:
        ErrorResponse | UserResponse
    """

    return sync_detailed(
        user_id=user_id,
        client=client,
    ).parsed


async def asyncio_detailed(
    user_id: str,
    *,
    client: AuthenticatedClient | Client,
) -> Response[ErrorResponse | UserResponse]:
    """Let a deactivated account back in

     The password works again as it was. The API keys do not come back, since deactivating deleted them,
    and neither does the calendar feed URL: deactivating rotated it, so the person fetches the new one.
    If the old password should not work again, a reset-password afterwards issues a new one. Calling it
    on an active account changes nothing. A UNIT_ADMIN has the same limits as for deactivating.

    Args:
        user_id (str):

    Raises:
        errors.UnexpectedStatus: If the server returns an undocumented status code and Client.raise_on_unexpected_status is True.
        httpx.TimeoutException: If the request takes longer than Client.timeout.

    Returns:
        Response[ErrorResponse | UserResponse]
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
) -> ErrorResponse | UserResponse | None:
    """Let a deactivated account back in

     The password works again as it was. The API keys do not come back, since deactivating deleted them,
    and neither does the calendar feed URL: deactivating rotated it, so the person fetches the new one.
    If the old password should not work again, a reset-password afterwards issues a new one. Calling it
    on an active account changes nothing. A UNIT_ADMIN has the same limits as for deactivating.

    Args:
        user_id (str):

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
        )
    ).parsed
