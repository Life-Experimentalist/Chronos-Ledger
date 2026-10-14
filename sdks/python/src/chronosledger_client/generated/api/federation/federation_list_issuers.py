from http import HTTPStatus
from typing import Any

import httpx

from ... import errors
from ...client import AuthenticatedClient, Client
from ...models.error_response import ErrorResponse
from ...models.issuer_response import IssuerResponse
from ...types import Response


def _get_kwargs() -> dict[str, Any]:

    _kwargs: dict[str, Any] = {
        "method": "get",
        "url": "/api/v1/federation/issuers",
    }

    return _kwargs


def _parse_response(
    *, client: AuthenticatedClient | Client, response: httpx.Response
) -> ErrorResponse | list[IssuerResponse] | None:
    if response.status_code == 200:
        response_200 = []
        _response_200 = response.json()
        for response_200_item_data in _response_200:
            response_200_item = IssuerResponse.from_dict(response_200_item_data)

            response_200.append(response_200_item)

        return response_200

    if response.status_code == 401:
        response_401 = ErrorResponse.from_dict(response.json())

        return response_401

    if response.status_code == 403:
        response_403 = ErrorResponse.from_dict(response.json())

        return response_403

    if client.raise_on_unexpected_status:
        raise errors.UnexpectedStatus(response.status_code, response.content)
    else:
        return None


def _build_response(
    *, client: AuthenticatedClient | Client, response: httpx.Response
) -> Response[ErrorResponse | list[IssuerResponse]]:
    return Response(
        status_code=HTTPStatus(response.status_code),
        content=response.content,
        headers=response.headers,
        parsed=_parse_response(client=client, response=response),
    )


def sync_detailed(
    *,
    client: AuthenticatedClient | Client,
) -> Response[ErrorResponse | list[IssuerResponse]]:
    """List registered issuers

     Requires `ORG_ADMIN`; an API key needs `federation:read`. Every route under `/federation` works
    whether or not federated sign-in is switched on, because an issuer and a key have to be registered
    before switching it on is worth doing. It is the exchange route that answers 404 while the feature
    is off.

    Raises:
        errors.UnexpectedStatus: If the server returns an undocumented status code and Client.raise_on_unexpected_status is True.
        httpx.TimeoutException: If the request takes longer than Client.timeout.

    Returns:
        Response[ErrorResponse | list[IssuerResponse]]
    """

    kwargs = _get_kwargs()

    response = client.get_httpx_client().request(
        **kwargs,
    )

    return _build_response(client=client, response=response)


def sync(
    *,
    client: AuthenticatedClient | Client,
) -> ErrorResponse | list[IssuerResponse] | None:
    """List registered issuers

     Requires `ORG_ADMIN`; an API key needs `federation:read`. Every route under `/federation` works
    whether or not federated sign-in is switched on, because an issuer and a key have to be registered
    before switching it on is worth doing. It is the exchange route that answers 404 while the feature
    is off.

    Raises:
        errors.UnexpectedStatus: If the server returns an undocumented status code and Client.raise_on_unexpected_status is True.
        httpx.TimeoutException: If the request takes longer than Client.timeout.

    Returns:
        ErrorResponse | list[IssuerResponse]
    """

    return sync_detailed(
        client=client,
    ).parsed


async def asyncio_detailed(
    *,
    client: AuthenticatedClient | Client,
) -> Response[ErrorResponse | list[IssuerResponse]]:
    """List registered issuers

     Requires `ORG_ADMIN`; an API key needs `federation:read`. Every route under `/federation` works
    whether or not federated sign-in is switched on, because an issuer and a key have to be registered
    before switching it on is worth doing. It is the exchange route that answers 404 while the feature
    is off.

    Raises:
        errors.UnexpectedStatus: If the server returns an undocumented status code and Client.raise_on_unexpected_status is True.
        httpx.TimeoutException: If the request takes longer than Client.timeout.

    Returns:
        Response[ErrorResponse | list[IssuerResponse]]
    """

    kwargs = _get_kwargs()

    response = await client.get_async_httpx_client().request(**kwargs)

    return _build_response(client=client, response=response)


async def asyncio(
    *,
    client: AuthenticatedClient | Client,
) -> ErrorResponse | list[IssuerResponse] | None:
    """List registered issuers

     Requires `ORG_ADMIN`; an API key needs `federation:read`. Every route under `/federation` works
    whether or not federated sign-in is switched on, because an issuer and a key have to be registered
    before switching it on is worth doing. It is the exchange route that answers 404 while the feature
    is off.

    Raises:
        errors.UnexpectedStatus: If the server returns an undocumented status code and Client.raise_on_unexpected_status is True.
        httpx.TimeoutException: If the request takes longer than Client.timeout.

    Returns:
        ErrorResponse | list[IssuerResponse]
    """

    return (
        await asyncio_detailed(
            client=client,
        )
    ).parsed
