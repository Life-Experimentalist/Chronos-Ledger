from http import HTTPStatus
from typing import Any
from urllib.parse import quote

import httpx

from ... import errors
from ...client import AuthenticatedClient, Client
from ...models.error_response import ErrorResponse
from ...models.issuer_key_response import IssuerKeyResponse
from ...types import Response


def _get_kwargs(
    issuer_id: int,
) -> dict[str, Any]:

    _kwargs: dict[str, Any] = {
        "method": "get",
        "url": "/api/v1/federation/issuers/{issuer_id}/keys".format(
            issuer_id=quote(str(issuer_id), safe=""),
        ),
    }

    return _kwargs


def _parse_response(
    *, client: AuthenticatedClient | Client, response: httpx.Response
) -> ErrorResponse | list[IssuerKeyResponse] | None:
    if response.status_code == 200:
        response_200 = []
        _response_200 = response.json()
        for response_200_item_data in _response_200:
            response_200_item = IssuerKeyResponse.from_dict(response_200_item_data)

            response_200.append(response_200_item)

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
) -> Response[ErrorResponse | list[IssuerKeyResponse]]:
    return Response(
        status_code=HTTPStatus(response.status_code),
        content=response.content,
        headers=response.headers,
        parsed=_parse_response(client=client, response=response),
    )


def sync_detailed(
    issuer_id: int,
    *,
    client: AuthenticatedClient | Client,
) -> Response[ErrorResponse | list[IssuerKeyResponse]]:
    """List an issuer's signing keys

     Requires `ORG_ADMIN`; an API key needs `federation:read`. The keys are public and are returned in
    full, which is how an integrator checks that what was registered is what they are signing with.

    Args:
        issuer_id (int):

    Raises:
        errors.UnexpectedStatus: If the server returns an undocumented status code and Client.raise_on_unexpected_status is True.
        httpx.TimeoutException: If the request takes longer than Client.timeout.

    Returns:
        Response[ErrorResponse | list[IssuerKeyResponse]]
    """

    kwargs = _get_kwargs(
        issuer_id=issuer_id,
    )

    response = client.get_httpx_client().request(
        **kwargs,
    )

    return _build_response(client=client, response=response)


def sync(
    issuer_id: int,
    *,
    client: AuthenticatedClient | Client,
) -> ErrorResponse | list[IssuerKeyResponse] | None:
    """List an issuer's signing keys

     Requires `ORG_ADMIN`; an API key needs `federation:read`. The keys are public and are returned in
    full, which is how an integrator checks that what was registered is what they are signing with.

    Args:
        issuer_id (int):

    Raises:
        errors.UnexpectedStatus: If the server returns an undocumented status code and Client.raise_on_unexpected_status is True.
        httpx.TimeoutException: If the request takes longer than Client.timeout.

    Returns:
        ErrorResponse | list[IssuerKeyResponse]
    """

    return sync_detailed(
        issuer_id=issuer_id,
        client=client,
    ).parsed


async def asyncio_detailed(
    issuer_id: int,
    *,
    client: AuthenticatedClient | Client,
) -> Response[ErrorResponse | list[IssuerKeyResponse]]:
    """List an issuer's signing keys

     Requires `ORG_ADMIN`; an API key needs `federation:read`. The keys are public and are returned in
    full, which is how an integrator checks that what was registered is what they are signing with.

    Args:
        issuer_id (int):

    Raises:
        errors.UnexpectedStatus: If the server returns an undocumented status code and Client.raise_on_unexpected_status is True.
        httpx.TimeoutException: If the request takes longer than Client.timeout.

    Returns:
        Response[ErrorResponse | list[IssuerKeyResponse]]
    """

    kwargs = _get_kwargs(
        issuer_id=issuer_id,
    )

    response = await client.get_async_httpx_client().request(**kwargs)

    return _build_response(client=client, response=response)


async def asyncio(
    issuer_id: int,
    *,
    client: AuthenticatedClient | Client,
) -> ErrorResponse | list[IssuerKeyResponse] | None:
    """List an issuer's signing keys

     Requires `ORG_ADMIN`; an API key needs `federation:read`. The keys are public and are returned in
    full, which is how an integrator checks that what was registered is what they are signing with.

    Args:
        issuer_id (int):

    Raises:
        errors.UnexpectedStatus: If the server returns an undocumented status code and Client.raise_on_unexpected_status is True.
        httpx.TimeoutException: If the request takes longer than Client.timeout.

    Returns:
        ErrorResponse | list[IssuerKeyResponse]
    """

    return (
        await asyncio_detailed(
            issuer_id=issuer_id,
            client=client,
        )
    ).parsed
