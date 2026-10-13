from http import HTTPStatus
from typing import Any
from urllib.parse import quote

import httpx

from ... import errors
from ...client import AuthenticatedClient, Client
from ...models.error_response import ErrorResponse
from ...models.issuer_key_create import IssuerKeyCreate
from ...models.issuer_key_response import IssuerKeyResponse
from ...types import UNSET, Response, Unset


def _get_kwargs(
    issuer_id: int,
    *,
    body: IssuerKeyCreate,
    idempotency_key: str | Unset = UNSET,
) -> dict[str, Any]:
    headers: dict[str, Any] = {}
    if not isinstance(idempotency_key, Unset):
        headers["Idempotency-Key"] = idempotency_key

    _kwargs: dict[str, Any] = {
        "method": "post",
        "url": "/api/v1/federation/issuers/{issuer_id}/keys".format(
            issuer_id=quote(str(issuer_id), safe=""),
        ),
    }

    _kwargs["json"] = body.to_dict()

    headers["Content-Type"] = "application/json"

    _kwargs["headers"] = headers
    return _kwargs


def _parse_response(
    *, client: AuthenticatedClient | Client, response: httpx.Response
) -> ErrorResponse | IssuerKeyResponse | None:
    if response.status_code == 201:
        response_201 = IssuerKeyResponse.from_dict(response.json())

        return response_201

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
    *,
    client: AuthenticatedClient | Client,
    body: IssuerKeyCreate,
    idempotency_key: str | Unset = UNSET,
) -> Response[ErrorResponse | IssuerKeyResponse]:
    """Add a signing key

     Requires `ORG_ADMIN`. A rotation is this route and then `federation.retireKey` on the old key: add
    the new one, give the old one an end far enough ahead that notes already in flight still verify, and
    delete it afterwards. Adding a key does not retire anything.

    Args:
        issuer_id (int):
        idempotency_key (str | Unset):
        body (IssuerKeyCreate):

    Raises:
        errors.UnexpectedStatus: If the server returns an undocumented status code and Client.raise_on_unexpected_status is True.
        httpx.TimeoutException: If the request takes longer than Client.timeout.

    Returns:
        Response[ErrorResponse | IssuerKeyResponse]
    """

    kwargs = _get_kwargs(
        issuer_id=issuer_id,
        body=body,
        idempotency_key=idempotency_key,
    )

    response = client.get_httpx_client().request(
        **kwargs,
    )

    return _build_response(client=client, response=response)


def sync(
    issuer_id: int,
    *,
    client: AuthenticatedClient | Client,
    body: IssuerKeyCreate,
    idempotency_key: str | Unset = UNSET,
) -> ErrorResponse | IssuerKeyResponse | None:
    """Add a signing key

     Requires `ORG_ADMIN`. A rotation is this route and then `federation.retireKey` on the old key: add
    the new one, give the old one an end far enough ahead that notes already in flight still verify, and
    delete it afterwards. Adding a key does not retire anything.

    Args:
        issuer_id (int):
        idempotency_key (str | Unset):
        body (IssuerKeyCreate):

    Raises:
        errors.UnexpectedStatus: If the server returns an undocumented status code and Client.raise_on_unexpected_status is True.
        httpx.TimeoutException: If the request takes longer than Client.timeout.

    Returns:
        ErrorResponse | IssuerKeyResponse
    """

    return sync_detailed(
        issuer_id=issuer_id,
        client=client,
        body=body,
        idempotency_key=idempotency_key,
    ).parsed


async def asyncio_detailed(
    issuer_id: int,
    *,
    client: AuthenticatedClient | Client,
    body: IssuerKeyCreate,
    idempotency_key: str | Unset = UNSET,
) -> Response[ErrorResponse | IssuerKeyResponse]:
    """Add a signing key

     Requires `ORG_ADMIN`. A rotation is this route and then `federation.retireKey` on the old key: add
    the new one, give the old one an end far enough ahead that notes already in flight still verify, and
    delete it afterwards. Adding a key does not retire anything.

    Args:
        issuer_id (int):
        idempotency_key (str | Unset):
        body (IssuerKeyCreate):

    Raises:
        errors.UnexpectedStatus: If the server returns an undocumented status code and Client.raise_on_unexpected_status is True.
        httpx.TimeoutException: If the request takes longer than Client.timeout.

    Returns:
        Response[ErrorResponse | IssuerKeyResponse]
    """

    kwargs = _get_kwargs(
        issuer_id=issuer_id,
        body=body,
        idempotency_key=idempotency_key,
    )

    response = await client.get_async_httpx_client().request(**kwargs)

    return _build_response(client=client, response=response)


async def asyncio(
    issuer_id: int,
    *,
    client: AuthenticatedClient | Client,
    body: IssuerKeyCreate,
    idempotency_key: str | Unset = UNSET,
) -> ErrorResponse | IssuerKeyResponse | None:
    """Add a signing key

     Requires `ORG_ADMIN`. A rotation is this route and then `federation.retireKey` on the old key: add
    the new one, give the old one an end far enough ahead that notes already in flight still verify, and
    delete it afterwards. Adding a key does not retire anything.

    Args:
        issuer_id (int):
        idempotency_key (str | Unset):
        body (IssuerKeyCreate):

    Raises:
        errors.UnexpectedStatus: If the server returns an undocumented status code and Client.raise_on_unexpected_status is True.
        httpx.TimeoutException: If the request takes longer than Client.timeout.

    Returns:
        ErrorResponse | IssuerKeyResponse
    """

    return (
        await asyncio_detailed(
            issuer_id=issuer_id,
            client=client,
            body=body,
            idempotency_key=idempotency_key,
        )
    ).parsed
