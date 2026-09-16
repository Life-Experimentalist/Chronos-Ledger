from http import HTTPStatus
from typing import Any

import httpx

from ... import errors
from ...client import AuthenticatedClient, Client
from ...models.error_response import ErrorResponse
from ...models.refresh_request import RefreshRequest
from ...models.token_response import TokenResponse
from ...types import Response


def _get_kwargs(
    *,
    body: RefreshRequest,
) -> dict[str, Any]:
    headers: dict[str, Any] = {}

    _kwargs: dict[str, Any] = {
        "method": "post",
        "url": "/api/v1/auth/refresh",
    }

    _kwargs["json"] = body.to_dict()

    headers["Content-Type"] = "application/json"

    _kwargs["headers"] = headers
    return _kwargs


def _parse_response(
    *, client: AuthenticatedClient | Client, response: httpx.Response
) -> ErrorResponse | TokenResponse | None:
    if response.status_code == 200:
        response_200 = TokenResponse.from_dict(response.json())

        return response_200

    if response.status_code == 401:
        response_401 = ErrorResponse.from_dict(response.json())

        return response_401

    if response.status_code == 422:
        response_422 = ErrorResponse.from_dict(response.json())

        return response_422

    if client.raise_on_unexpected_status:
        raise errors.UnexpectedStatus(response.status_code, response.content)
    else:
        return None


def _build_response(
    *, client: AuthenticatedClient | Client, response: httpx.Response
) -> Response[ErrorResponse | TokenResponse]:
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
) -> Response[ErrorResponse | TokenResponse]:
    """Exchange a refresh token for a new access token

     A refresh token works exactly once. The response carries its replacement, so a client that loses the
    response signs in again. A used token presented again more than ten seconds after its use ends every
    token descended from the same sign-in, on the reading that two parties hold it; inside those ten
    seconds it is refused and nothing else changes.

    Args:
        body (RefreshRequest):

    Raises:
        errors.UnexpectedStatus: If the server returns an undocumented status code and Client.raise_on_unexpected_status is True.
        httpx.TimeoutException: If the request takes longer than Client.timeout.

    Returns:
        Response[ErrorResponse | TokenResponse]
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
) -> ErrorResponse | TokenResponse | None:
    """Exchange a refresh token for a new access token

     A refresh token works exactly once. The response carries its replacement, so a client that loses the
    response signs in again. A used token presented again more than ten seconds after its use ends every
    token descended from the same sign-in, on the reading that two parties hold it; inside those ten
    seconds it is refused and nothing else changes.

    Args:
        body (RefreshRequest):

    Raises:
        errors.UnexpectedStatus: If the server returns an undocumented status code and Client.raise_on_unexpected_status is True.
        httpx.TimeoutException: If the request takes longer than Client.timeout.

    Returns:
        ErrorResponse | TokenResponse
    """

    return sync_detailed(
        client=client,
        body=body,
    ).parsed


async def asyncio_detailed(
    *,
    client: AuthenticatedClient | Client,
    body: RefreshRequest,
) -> Response[ErrorResponse | TokenResponse]:
    """Exchange a refresh token for a new access token

     A refresh token works exactly once. The response carries its replacement, so a client that loses the
    response signs in again. A used token presented again more than ten seconds after its use ends every
    token descended from the same sign-in, on the reading that two parties hold it; inside those ten
    seconds it is refused and nothing else changes.

    Args:
        body (RefreshRequest):

    Raises:
        errors.UnexpectedStatus: If the server returns an undocumented status code and Client.raise_on_unexpected_status is True.
        httpx.TimeoutException: If the request takes longer than Client.timeout.

    Returns:
        Response[ErrorResponse | TokenResponse]
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
) -> ErrorResponse | TokenResponse | None:
    """Exchange a refresh token for a new access token

     A refresh token works exactly once. The response carries its replacement, so a client that loses the
    response signs in again. A used token presented again more than ten seconds after its use ends every
    token descended from the same sign-in, on the reading that two parties hold it; inside those ten
    seconds it is refused and nothing else changes.

    Args:
        body (RefreshRequest):

    Raises:
        errors.UnexpectedStatus: If the server returns an undocumented status code and Client.raise_on_unexpected_status is True.
        httpx.TimeoutException: If the request takes longer than Client.timeout.

    Returns:
        ErrorResponse | TokenResponse
    """

    return (
        await asyncio_detailed(
            client=client,
            body=body,
        )
    ).parsed
