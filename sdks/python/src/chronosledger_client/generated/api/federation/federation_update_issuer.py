from http import HTTPStatus
from typing import Any
from urllib.parse import quote

import httpx

from ... import errors
from ...client import AuthenticatedClient, Client
from ...models.error_response import ErrorResponse
from ...models.issuer_response import IssuerResponse
from ...models.issuer_update import IssuerUpdate
from ...types import UNSET, Response, Unset


def _get_kwargs(
    issuer_id: int,
    *,
    body: IssuerUpdate,
    idempotency_key: str | Unset = UNSET,
) -> dict[str, Any]:
    headers: dict[str, Any] = {}
    if not isinstance(idempotency_key, Unset):
        headers["Idempotency-Key"] = idempotency_key

    _kwargs: dict[str, Any] = {
        "method": "patch",
        "url": "/api/v1/federation/issuers/{issuer_id}".format(
            issuer_id=quote(str(issuer_id), safe=""),
        ),
    }

    _kwargs["json"] = body.to_dict()

    headers["Content-Type"] = "application/json"

    _kwargs["headers"] = headers
    return _kwargs


def _parse_response(
    *, client: AuthenticatedClient | Client, response: httpx.Response
) -> ErrorResponse | IssuerResponse | None:
    if response.status_code == 200:
        response_200 = IssuerResponse.from_dict(response.json())

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
) -> Response[ErrorResponse | IssuerResponse]:
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
    body: IssuerUpdate,
    idempotency_key: str | Unset = UNSET,
) -> Response[ErrorResponse | IssuerResponse]:
    """Change a registration

     Requires `ORG_ADMIN`. `enabled` false is how an issuer is stopped without losing what it was allowed
    to assert; notes from it are then refused exactly the way an unknown issuer's are.

    Args:
        issuer_id (int):
        idempotency_key (str | Unset):
        body (IssuerUpdate): Every field is optional and one left out is unchanged. `issuer`
            cannot be changed: it is the value notes already in the wild carry, and editing it would
            retarget a registration rather than register another.

    Raises:
        errors.UnexpectedStatus: If the server returns an undocumented status code and Client.raise_on_unexpected_status is True.
        httpx.TimeoutException: If the request takes longer than Client.timeout.

    Returns:
        Response[ErrorResponse | IssuerResponse]
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
    body: IssuerUpdate,
    idempotency_key: str | Unset = UNSET,
) -> ErrorResponse | IssuerResponse | None:
    """Change a registration

     Requires `ORG_ADMIN`. `enabled` false is how an issuer is stopped without losing what it was allowed
    to assert; notes from it are then refused exactly the way an unknown issuer's are.

    Args:
        issuer_id (int):
        idempotency_key (str | Unset):
        body (IssuerUpdate): Every field is optional and one left out is unchanged. `issuer`
            cannot be changed: it is the value notes already in the wild carry, and editing it would
            retarget a registration rather than register another.

    Raises:
        errors.UnexpectedStatus: If the server returns an undocumented status code and Client.raise_on_unexpected_status is True.
        httpx.TimeoutException: If the request takes longer than Client.timeout.

    Returns:
        ErrorResponse | IssuerResponse
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
    body: IssuerUpdate,
    idempotency_key: str | Unset = UNSET,
) -> Response[ErrorResponse | IssuerResponse]:
    """Change a registration

     Requires `ORG_ADMIN`. `enabled` false is how an issuer is stopped without losing what it was allowed
    to assert; notes from it are then refused exactly the way an unknown issuer's are.

    Args:
        issuer_id (int):
        idempotency_key (str | Unset):
        body (IssuerUpdate): Every field is optional and one left out is unchanged. `issuer`
            cannot be changed: it is the value notes already in the wild carry, and editing it would
            retarget a registration rather than register another.

    Raises:
        errors.UnexpectedStatus: If the server returns an undocumented status code and Client.raise_on_unexpected_status is True.
        httpx.TimeoutException: If the request takes longer than Client.timeout.

    Returns:
        Response[ErrorResponse | IssuerResponse]
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
    body: IssuerUpdate,
    idempotency_key: str | Unset = UNSET,
) -> ErrorResponse | IssuerResponse | None:
    """Change a registration

     Requires `ORG_ADMIN`. `enabled` false is how an issuer is stopped without losing what it was allowed
    to assert; notes from it are then refused exactly the way an unknown issuer's are.

    Args:
        issuer_id (int):
        idempotency_key (str | Unset):
        body (IssuerUpdate): Every field is optional and one left out is unchanged. `issuer`
            cannot be changed: it is the value notes already in the wild carry, and editing it would
            retarget a registration rather than register another.

    Raises:
        errors.UnexpectedStatus: If the server returns an undocumented status code and Client.raise_on_unexpected_status is True.
        httpx.TimeoutException: If the request takes longer than Client.timeout.

    Returns:
        ErrorResponse | IssuerResponse
    """

    return (
        await asyncio_detailed(
            issuer_id=issuer_id,
            client=client,
            body=body,
            idempotency_key=idempotency_key,
        )
    ).parsed
