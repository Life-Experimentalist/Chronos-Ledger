from http import HTTPStatus
from typing import Any

import httpx

from ... import errors
from ...client import AuthenticatedClient, Client
from ...models.auth_logout_response_200 import AuthLogoutResponse200
from ...models.error_response import ErrorResponse
from ...models.refresh_request import RefreshRequest
from ...types import Response


def _get_kwargs(
    *,
    body: RefreshRequest,
) -> dict[str, Any]:
    headers: dict[str, Any] = {}

    _kwargs: dict[str, Any] = {
        "method": "post",
        "url": "/api/v1/auth/logout",
    }

    _kwargs["json"] = body.to_dict()

    headers["Content-Type"] = "application/json"

    _kwargs["headers"] = headers
    return _kwargs


def _parse_response(
    *, client: AuthenticatedClient | Client, response: httpx.Response
) -> AuthLogoutResponse200 | ErrorResponse | None:
    if response.status_code == 200:
        response_200 = AuthLogoutResponse200.from_dict(response.json())

        return response_200

    if response.status_code == 422:
        response_422 = ErrorResponse.from_dict(response.json())

        return response_422

    if client.raise_on_unexpected_status:
        raise errors.UnexpectedStatus(response.status_code, response.content)
    else:
        return None


def _build_response(
    *, client: AuthenticatedClient | Client, response: httpx.Response
) -> Response[AuthLogoutResponse200 | ErrorResponse]:
    return Response(
        status_code=HTTPStatus(response.status_code),
        content=response.content,
        headers=response.headers,
        parsed=_parse_response(client=client, response=response),
    )


def sync_detailed(
    *,
    client: AuthenticatedClient | Client,
    body: RefreshRequest,
) -> Response[AuthLogoutResponse200 | ErrorResponse]:
    """Revoke a refresh token

     Deletes the refresh token named in the body along with the used tokens it replaced, which ends that
    sign-in. An unknown token is not an error, so a client that has already lost its token can call this
    without handling a failure. The access token keeps working until it expires: there is no server-side
    revocation of access tokens.

    Args:
        body (RefreshRequest):

    Raises:
        errors.UnexpectedStatus: If the server returns an undocumented status code and Client.raise_on_unexpected_status is True.
        httpx.TimeoutException: If the request takes longer than Client.timeout.

    Returns:
        Response[AuthLogoutResponse200 | ErrorResponse]
    """

    kwargs = _get_kwargs(
        body=body,
    )

    response = client.get_httpx_client().request(
        **kwargs,
    )

    return _build_response(client=client, response=response)


def sync(
    *,
    client: AuthenticatedClient | Client,
    body: RefreshRequest,
) -> AuthLogoutResponse200 | ErrorResponse | None:
    """Revoke a refresh token

     Deletes the refresh token named in the body along with the used tokens it replaced, which ends that
    sign-in. An unknown token is not an error, so a client that has already lost its token can call this
    without handling a failure. The access token keeps working until it expires: there is no server-side
    revocation of access tokens.

    Args:
        body (RefreshRequest):

    Raises:
        errors.UnexpectedStatus: If the server returns an undocumented status code and Client.raise_on_unexpected_status is True.
        httpx.TimeoutException: If the request takes longer than Client.timeout.

    Returns:
        AuthLogoutResponse200 | ErrorResponse
    """

    return sync_detailed(
        client=client,
        body=body,
    ).parsed


async def asyncio_detailed(
    *,
    client: AuthenticatedClient | Client,
    body: RefreshRequest,
) -> Response[AuthLogoutResponse200 | ErrorResponse]:
    """Revoke a refresh token

     Deletes the refresh token named in the body along with the used tokens it replaced, which ends that
    sign-in. An unknown token is not an error, so a client that has already lost its token can call this
    without handling a failure. The access token keeps working until it expires: there is no server-side
    revocation of access tokens.

    Args:
        body (RefreshRequest):

    Raises:
        errors.UnexpectedStatus: If the server returns an undocumented status code and Client.raise_on_unexpected_status is True.
        httpx.TimeoutException: If the request takes longer than Client.timeout.

    Returns:
        Response[AuthLogoutResponse200 | ErrorResponse]
    """

    kwargs = _get_kwargs(
        body=body,
    )

    response = await client.get_async_httpx_client().request(**kwargs)

    return _build_response(client=client, response=response)


async def asyncio(
    *,
    client: AuthenticatedClient | Client,
    body: RefreshRequest,
) -> AuthLogoutResponse200 | ErrorResponse | None:
    """Revoke a refresh token

     Deletes the refresh token named in the body along with the used tokens it replaced, which ends that
    sign-in. An unknown token is not an error, so a client that has already lost its token can call this
    without handling a failure. The access token keeps working until it expires: there is no server-side
    revocation of access tokens.

    Args:
        body (RefreshRequest):

    Raises:
        errors.UnexpectedStatus: If the server returns an undocumented status code and Client.raise_on_unexpected_status is True.
        httpx.TimeoutException: If the request takes longer than Client.timeout.

    Returns:
        AuthLogoutResponse200 | ErrorResponse
    """

    return (
        await asyncio_detailed(
            client=client,
            body=body,
        )
    ).parsed
