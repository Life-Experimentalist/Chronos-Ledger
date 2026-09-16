from http import HTTPStatus
from typing import Any
from urllib.parse import quote

import httpx

from ... import errors
from ...client import AuthenticatedClient, Client
from ...models.deactivated_user_response import DeactivatedUserResponse
from ...models.error_response import ErrorResponse
from ...types import Response


def _get_kwargs(
    user_id: str,
) -> dict[str, Any]:

    _kwargs: dict[str, Any] = {
        "method": "post",
        "url": "/api/v1/users/{user_id}/deactivate".format(
            user_id=quote(str(user_id), safe=""),
        ),
    }

    return _kwargs


def _parse_response(
    *, client: AuthenticatedClient | Client, response: httpx.Response
) -> DeactivatedUserResponse | ErrorResponse | None:
    if response.status_code == 200:
        response_200 = DeactivatedUserResponse.from_dict(response.json())

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
) -> Response[DeactivatedUserResponse | ErrorResponse]:
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
) -> Response[DeactivatedUserResponse | ErrorResponse]:
    """Stop an account without deleting it

     For somebody who has left. Every record against the account stays, and every way in closes: signing
    in, refreshing, an access token already issued, an API key bound to the account, the calendar feed
    and an open WebSocket. The account drops out of `GET /users/` unless `include_deactivated=true`, out
    of the staff directory and staff locations, and cannot be named as a manager, lead or substitute,
    sent a guest, issued a new API key or enrolled by a CSV import. Its refresh tokens are dropped, its
    calendar feed URL is rotated and its API keys are deleted; reactivating does not bring the keys
    back. The email address stays taken, since the account can come back: to reuse it, change it on the
    deactivated account with `PATCH /users/{user_id}` first.

    What already names the account is left alone, and none of it stops the account being deactivated.
    The response counts it under `open_items`, and calling again counts afresh. An absence request sent
    to the account is decided by an admin instead; see `GET /attendance/absence/pending`.

    Calling it on an account that is already deactivated changes nothing. A UNIT_ADMIN is limited to
    their own unit and may not deactivate an admin account, and nobody may deactivate their own.

    Args:
        user_id (str):

    Raises:
        errors.UnexpectedStatus: If the server returns an undocumented status code and Client.raise_on_unexpected_status is True.
        httpx.TimeoutException: If the request takes longer than Client.timeout.

    Returns:
        Response[DeactivatedUserResponse | ErrorResponse]
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
) -> DeactivatedUserResponse | ErrorResponse | None:
    """Stop an account without deleting it

     For somebody who has left. Every record against the account stays, and every way in closes: signing
    in, refreshing, an access token already issued, an API key bound to the account, the calendar feed
    and an open WebSocket. The account drops out of `GET /users/` unless `include_deactivated=true`, out
    of the staff directory and staff locations, and cannot be named as a manager, lead or substitute,
    sent a guest, issued a new API key or enrolled by a CSV import. Its refresh tokens are dropped, its
    calendar feed URL is rotated and its API keys are deleted; reactivating does not bring the keys
    back. The email address stays taken, since the account can come back: to reuse it, change it on the
    deactivated account with `PATCH /users/{user_id}` first.

    What already names the account is left alone, and none of it stops the account being deactivated.
    The response counts it under `open_items`, and calling again counts afresh. An absence request sent
    to the account is decided by an admin instead; see `GET /attendance/absence/pending`.

    Calling it on an account that is already deactivated changes nothing. A UNIT_ADMIN is limited to
    their own unit and may not deactivate an admin account, and nobody may deactivate their own.

    Args:
        user_id (str):

    Raises:
        errors.UnexpectedStatus: If the server returns an undocumented status code and Client.raise_on_unexpected_status is True.
        httpx.TimeoutException: If the request takes longer than Client.timeout.

    Returns:
        DeactivatedUserResponse | ErrorResponse
    """

    return sync_detailed(
        user_id=user_id,
        client=client,
    ).parsed


async def asyncio_detailed(
    user_id: str,
    *,
    client: AuthenticatedClient | Client,
) -> Response[DeactivatedUserResponse | ErrorResponse]:
    """Stop an account without deleting it

     For somebody who has left. Every record against the account stays, and every way in closes: signing
    in, refreshing, an access token already issued, an API key bound to the account, the calendar feed
    and an open WebSocket. The account drops out of `GET /users/` unless `include_deactivated=true`, out
    of the staff directory and staff locations, and cannot be named as a manager, lead or substitute,
    sent a guest, issued a new API key or enrolled by a CSV import. Its refresh tokens are dropped, its
    calendar feed URL is rotated and its API keys are deleted; reactivating does not bring the keys
    back. The email address stays taken, since the account can come back: to reuse it, change it on the
    deactivated account with `PATCH /users/{user_id}` first.

    What already names the account is left alone, and none of it stops the account being deactivated.
    The response counts it under `open_items`, and calling again counts afresh. An absence request sent
    to the account is decided by an admin instead; see `GET /attendance/absence/pending`.

    Calling it on an account that is already deactivated changes nothing. A UNIT_ADMIN is limited to
    their own unit and may not deactivate an admin account, and nobody may deactivate their own.

    Args:
        user_id (str):

    Raises:
        errors.UnexpectedStatus: If the server returns an undocumented status code and Client.raise_on_unexpected_status is True.
        httpx.TimeoutException: If the request takes longer than Client.timeout.

    Returns:
        Response[DeactivatedUserResponse | ErrorResponse]
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
) -> DeactivatedUserResponse | ErrorResponse | None:
    """Stop an account without deleting it

     For somebody who has left. Every record against the account stays, and every way in closes: signing
    in, refreshing, an access token already issued, an API key bound to the account, the calendar feed
    and an open WebSocket. The account drops out of `GET /users/` unless `include_deactivated=true`, out
    of the staff directory and staff locations, and cannot be named as a manager, lead or substitute,
    sent a guest, issued a new API key or enrolled by a CSV import. Its refresh tokens are dropped, its
    calendar feed URL is rotated and its API keys are deleted; reactivating does not bring the keys
    back. The email address stays taken, since the account can come back: to reuse it, change it on the
    deactivated account with `PATCH /users/{user_id}` first.

    What already names the account is left alone, and none of it stops the account being deactivated.
    The response counts it under `open_items`, and calling again counts afresh. An absence request sent
    to the account is decided by an admin instead; see `GET /attendance/absence/pending`.

    Calling it on an account that is already deactivated changes nothing. A UNIT_ADMIN is limited to
    their own unit and may not deactivate an admin account, and nobody may deactivate their own.

    Args:
        user_id (str):

    Raises:
        errors.UnexpectedStatus: If the server returns an undocumented status code and Client.raise_on_unexpected_status is True.
        httpx.TimeoutException: If the request takes longer than Client.timeout.

    Returns:
        DeactivatedUserResponse | ErrorResponse
    """

    return (
        await asyncio_detailed(
            user_id=user_id,
            client=client,
        )
    ).parsed
