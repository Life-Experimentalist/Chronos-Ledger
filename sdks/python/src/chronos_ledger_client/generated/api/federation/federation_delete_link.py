from http import HTTPStatus
from typing import Any, cast
from urllib.parse import quote

import httpx

from ... import errors
from ...client import AuthenticatedClient, Client
from ...models.error_response import ErrorResponse
from ...types import UNSET, Response, Unset


def _get_kwargs(
    link_id: int,
    *,
    idempotency_key: str | Unset = UNSET,
) -> dict[str, Any]:
    headers: dict[str, Any] = {}
    if not isinstance(idempotency_key, Unset):
        headers["Idempotency-Key"] = idempotency_key

    _kwargs: dict[str, Any] = {
        "method": "delete",
        "url": "/api/v1/federation/links/{link_id}".format(
            link_id=quote(str(link_id), safe=""),
        ),
    }

    _kwargs["headers"] = headers
    return _kwargs


def _parse_response(
    *, client: AuthenticatedClient | Client, response: httpx.Response
) -> Any | ErrorResponse | None:
    if response.status_code == 204:
        response_204 = cast(Any, None)
        return response_204

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
) -> Response[Any | ErrorResponse]:
    return Response(
        status_code=HTTPStatus(response.status_code),
        content=response.content,
        headers=response.headers,
        parsed=_parse_response(client=client, response=response),
    )


def sync_detailed(
    link_id: int,
    *,
    client: AuthenticatedClient | Client,
    idempotency_key: str | Unset = UNSET,
) -> Response[Any | ErrorResponse]:
    """Stop an account arriving through an issuer

     Requires `ORG_ADMIN`. The account stays, with whatever role and unit it holds; what goes is the
    route. A note carrying the unlinked pair is then a stranger, and a stranger whose address is taken
    is refused rather than given a second account.

    Args:
        link_id (int):
        idempotency_key (str | Unset):

    Raises:
        errors.UnexpectedStatus: If the server returns an undocumented status code and Client.raise_on_unexpected_status is True.
        httpx.TimeoutException: If the request takes longer than Client.timeout.

    Returns:
        Response[Any | ErrorResponse]
    """

    kwargs = _get_kwargs(
        link_id=link_id,
        idempotency_key=idempotency_key,
    )

    response = client.get_httpx_client().request(
        **kwargs,
    )

    return _build_response(client=client, response=response)


def sync(
    link_id: int,
    *,
    client: AuthenticatedClient | Client,
    idempotency_key: str | Unset = UNSET,
) -> Any | ErrorResponse | None:
    """Stop an account arriving through an issuer

     Requires `ORG_ADMIN`. The account stays, with whatever role and unit it holds; what goes is the
    route. A note carrying the unlinked pair is then a stranger, and a stranger whose address is taken
    is refused rather than given a second account.

    Args:
        link_id (int):
        idempotency_key (str | Unset):

    Raises:
        errors.UnexpectedStatus: If the server returns an undocumented status code and Client.raise_on_unexpected_status is True.
        httpx.TimeoutException: If the request takes longer than Client.timeout.

    Returns:
        Any | ErrorResponse
    """

    return sync_detailed(
        link_id=link_id,
        client=client,
        idempotency_key=idempotency_key,
    ).parsed


async def asyncio_detailed(
    link_id: int,
    *,
    client: AuthenticatedClient | Client,
    idempotency_key: str | Unset = UNSET,
) -> Response[Any | ErrorResponse]:
    """Stop an account arriving through an issuer

     Requires `ORG_ADMIN`. The account stays, with whatever role and unit it holds; what goes is the
    route. A note carrying the unlinked pair is then a stranger, and a stranger whose address is taken
    is refused rather than given a second account.

    Args:
        link_id (int):
        idempotency_key (str | Unset):

    Raises:
        errors.UnexpectedStatus: If the server returns an undocumented status code and Client.raise_on_unexpected_status is True.
        httpx.TimeoutException: If the request takes longer than Client.timeout.

    Returns:
        Response[Any | ErrorResponse]
    """

    kwargs = _get_kwargs(
        link_id=link_id,
        idempotency_key=idempotency_key,
    )

    response = await client.get_async_httpx_client().request(**kwargs)

    return _build_response(client=client, response=response)


async def asyncio(
    link_id: int,
    *,
    client: AuthenticatedClient | Client,
    idempotency_key: str | Unset = UNSET,
) -> Any | ErrorResponse | None:
    """Stop an account arriving through an issuer

     Requires `ORG_ADMIN`. The account stays, with whatever role and unit it holds; what goes is the
    route. A note carrying the unlinked pair is then a stranger, and a stranger whose address is taken
    is refused rather than given a second account.

    Args:
        link_id (int):
        idempotency_key (str | Unset):

    Raises:
        errors.UnexpectedStatus: If the server returns an undocumented status code and Client.raise_on_unexpected_status is True.
        httpx.TimeoutException: If the request takes longer than Client.timeout.

    Returns:
        Any | ErrorResponse
    """

    return (
        await asyncio_detailed(
            link_id=link_id,
            client=client,
            idempotency_key=idempotency_key,
        )
    ).parsed
