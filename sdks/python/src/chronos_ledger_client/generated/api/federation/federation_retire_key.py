from http import HTTPStatus
from typing import Any
from urllib.parse import quote

import httpx

from ... import errors
from ...client import AuthenticatedClient, Client
from ...models.error_response import ErrorResponse
from ...models.issuer_key_response import IssuerKeyResponse
from ...models.issuer_key_retire import IssuerKeyRetire
from ...types import Response


def _get_kwargs(
    issuer_id: int,
    key_id: int,
    *,
    body: IssuerKeyRetire,
) -> dict[str, Any]:
    headers: dict[str, Any] = {}

    _kwargs: dict[str, Any] = {
        "method": "patch",
        "url": "/api/v1/federation/issuers/{issuer_id}/keys/{key_id}".format(
            issuer_id=quote(str(issuer_id), safe=""),
            key_id=quote(str(key_id), safe=""),
        ),
    }

    _kwargs["json"] = body.to_dict()

    headers["Content-Type"] = "application/json"

    _kwargs["headers"] = headers
    return _kwargs


def _parse_response(
    *, client: AuthenticatedClient | Client, response: httpx.Response
) -> ErrorResponse | IssuerKeyResponse | None:
    if response.status_code == 200:
        response_200 = IssuerKeyResponse.from_dict(response.json())

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
) -> Response[ErrorResponse | IssuerKeyResponse]:
    return Response(
        status_code=HTTPStatus(response.status_code),
        content=response.content,
        headers=response.headers,
        parsed=_parse_response(client=client, response=response),
    )


def sync_detailed(
    issuer_id: int,
    key_id: int,
    *,
    client: AuthenticatedClient | Client,
    body: IssuerKeyRetire,
) -> Response[ErrorResponse | IssuerKeyResponse]:
    """Give a key an end

     Requires `ORG_ADMIN`. A moment in the past stops the key now: the next note naming it is refused. A
    moment in the future is the overlap a planned rotation wants. The key stays readable either way,
    which is why this is a separate route from deleting it.

    Args:
        issuer_id (int):
        key_id (int):
        body (IssuerKeyRetire):

    Raises:
        errors.UnexpectedStatus: If the server returns an undocumented status code and Client.raise_on_unexpected_status is True.
        httpx.TimeoutException: If the request takes longer than Client.timeout.

    Returns:
        Response[ErrorResponse | IssuerKeyResponse]
    """

    kwargs = _get_kwargs(
        issuer_id=issuer_id,
        key_id=key_id,
        body=body,
    )

    response = client.get_httpx_client().request(
        **kwargs,
    )

    return _build_response(client=client, response=response)


def sync(
    issuer_id: int,
    key_id: int,
    *,
    client: AuthenticatedClient | Client,
    body: IssuerKeyRetire,
) -> ErrorResponse | IssuerKeyResponse | None:
    """Give a key an end

     Requires `ORG_ADMIN`. A moment in the past stops the key now: the next note naming it is refused. A
    moment in the future is the overlap a planned rotation wants. The key stays readable either way,
    which is why this is a separate route from deleting it.

    Args:
        issuer_id (int):
        key_id (int):
        body (IssuerKeyRetire):

    Raises:
        errors.UnexpectedStatus: If the server returns an undocumented status code and Client.raise_on_unexpected_status is True.
        httpx.TimeoutException: If the request takes longer than Client.timeout.

    Returns:
        ErrorResponse | IssuerKeyResponse
    """

    return sync_detailed(
        issuer_id=issuer_id,
        key_id=key_id,
        client=client,
        body=body,
    ).parsed


async def asyncio_detailed(
    issuer_id: int,
    key_id: int,
    *,
    client: AuthenticatedClient | Client,
    body: IssuerKeyRetire,
) -> Response[ErrorResponse | IssuerKeyResponse]:
    """Give a key an end

     Requires `ORG_ADMIN`. A moment in the past stops the key now: the next note naming it is refused. A
    moment in the future is the overlap a planned rotation wants. The key stays readable either way,
    which is why this is a separate route from deleting it.

    Args:
        issuer_id (int):
        key_id (int):
        body (IssuerKeyRetire):

    Raises:
        errors.UnexpectedStatus: If the server returns an undocumented status code and Client.raise_on_unexpected_status is True.
        httpx.TimeoutException: If the request takes longer than Client.timeout.

    Returns:
        Response[ErrorResponse | IssuerKeyResponse]
    """

    kwargs = _get_kwargs(
        issuer_id=issuer_id,
        key_id=key_id,
        body=body,
    )

    response = await client.get_async_httpx_client().request(**kwargs)

    return _build_response(client=client, response=response)


async def asyncio(
    issuer_id: int,
    key_id: int,
    *,
    client: AuthenticatedClient | Client,
    body: IssuerKeyRetire,
) -> ErrorResponse | IssuerKeyResponse | None:
    """Give a key an end

     Requires `ORG_ADMIN`. A moment in the past stops the key now: the next note naming it is refused. A
    moment in the future is the overlap a planned rotation wants. The key stays readable either way,
    which is why this is a separate route from deleting it.

    Args:
        issuer_id (int):
        key_id (int):
        body (IssuerKeyRetire):

    Raises:
        errors.UnexpectedStatus: If the server returns an undocumented status code and Client.raise_on_unexpected_status is True.
        httpx.TimeoutException: If the request takes longer than Client.timeout.

    Returns:
        ErrorResponse | IssuerKeyResponse
    """

    return (
        await asyncio_detailed(
            issuer_id=issuer_id,
            key_id=key_id,
            client=client,
            body=body,
        )
    ).parsed
