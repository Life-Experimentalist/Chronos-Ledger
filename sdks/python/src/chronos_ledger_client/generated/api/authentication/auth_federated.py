from http import HTTPStatus
from typing import Any

import httpx

from ... import errors
from ...client import AuthenticatedClient, Client
from ...models.error_response import ErrorResponse
from ...models.federated_token_request import FederatedTokenRequest
from ...models.token_response import TokenResponse
from ...types import Response


def _get_kwargs(
    *,
    body: FederatedTokenRequest,
) -> dict[str, Any]:
    headers: dict[str, Any] = {}

    _kwargs: dict[str, Any] = {
        "method": "post",
        "url": "/api/v1/auth/federated",
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

    if response.status_code == 503:
        response_503 = ErrorResponse.from_dict(response.json())

        return response_503

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
    body: FederatedTokenRequest,
) -> Response[ErrorResponse | TokenResponse]:
    """Exchange a note from a registered outside issuer for a session

     Off unless FEDERATED_IDENTITY_ENABLED is true, and a 404 while it is off. The note is a short-lived
    JWT signed with Ed25519 by a key an operator registered for that issuer; the reply is the same pair
    POST /auth/login returns, so a client handles the session the same way afterwards. A note works
    exactly once. The account is found by the (issuer, subject) pair and not by the address in the note,
    so an issuer cannot name an existing account and be handed it; the first note for a subject creates
    an account, and its role comes from the operator's own map of group claims, never from the note
    alone. Every verification failure is the same 401 with the same message, on purpose: the reason is
    in the server log, where an integrator can be shown it and a forger cannot read it.

    Args:
        body (FederatedTokenRequest):

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
    body: FederatedTokenRequest,
) -> ErrorResponse | TokenResponse | None:
    """Exchange a note from a registered outside issuer for a session

     Off unless FEDERATED_IDENTITY_ENABLED is true, and a 404 while it is off. The note is a short-lived
    JWT signed with Ed25519 by a key an operator registered for that issuer; the reply is the same pair
    POST /auth/login returns, so a client handles the session the same way afterwards. A note works
    exactly once. The account is found by the (issuer, subject) pair and not by the address in the note,
    so an issuer cannot name an existing account and be handed it; the first note for a subject creates
    an account, and its role comes from the operator's own map of group claims, never from the note
    alone. Every verification failure is the same 401 with the same message, on purpose: the reason is
    in the server log, where an integrator can be shown it and a forger cannot read it.

    Args:
        body (FederatedTokenRequest):

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
    body: FederatedTokenRequest,
) -> Response[ErrorResponse | TokenResponse]:
    """Exchange a note from a registered outside issuer for a session

     Off unless FEDERATED_IDENTITY_ENABLED is true, and a 404 while it is off. The note is a short-lived
    JWT signed with Ed25519 by a key an operator registered for that issuer; the reply is the same pair
    POST /auth/login returns, so a client handles the session the same way afterwards. A note works
    exactly once. The account is found by the (issuer, subject) pair and not by the address in the note,
    so an issuer cannot name an existing account and be handed it; the first note for a subject creates
    an account, and its role comes from the operator's own map of group claims, never from the note
    alone. Every verification failure is the same 401 with the same message, on purpose: the reason is
    in the server log, where an integrator can be shown it and a forger cannot read it.

    Args:
        body (FederatedTokenRequest):

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
    body: FederatedTokenRequest,
) -> ErrorResponse | TokenResponse | None:
    """Exchange a note from a registered outside issuer for a session

     Off unless FEDERATED_IDENTITY_ENABLED is true, and a 404 while it is off. The note is a short-lived
    JWT signed with Ed25519 by a key an operator registered for that issuer; the reply is the same pair
    POST /auth/login returns, so a client handles the session the same way afterwards. A note works
    exactly once. The account is found by the (issuer, subject) pair and not by the address in the note,
    so an issuer cannot name an existing account and be handed it; the first note for a subject creates
    an account, and its role comes from the operator's own map of group claims, never from the note
    alone. Every verification failure is the same 401 with the same message, on purpose: the reason is
    in the server log, where an integrator can be shown it and a forger cannot read it.

    Args:
        body (FederatedTokenRequest):

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
