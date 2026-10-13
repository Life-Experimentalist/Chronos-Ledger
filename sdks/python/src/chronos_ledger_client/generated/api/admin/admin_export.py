from http import HTTPStatus
from io import BytesIO
from typing import Any

import httpx

from ... import errors
from ...client import AuthenticatedClient, Client
from ...models.error_response import ErrorResponse
from ...types import UNSET, File, Response, Unset


def _get_kwargs(
    *,
    include_secrets: bool | Unset = False,
) -> dict[str, Any]:

    params: dict[str, Any] = {}

    params["include_secrets"] = include_secrets

    params = {k: v for k, v in params.items() if v is not UNSET and v is not None}

    _kwargs: dict[str, Any] = {
        "method": "get",
        "url": "/api/v1/admin/export",
        "params": params,
    }

    return _kwargs


def _parse_response(
    *, client: AuthenticatedClient | Client, response: httpx.Response
) -> ErrorResponse | File | None:
    if response.status_code == 200:
        response_200 = File(payload=BytesIO(response.content))

        return response_200

    if response.status_code == 401:
        response_401 = ErrorResponse.from_dict(response.json())

        return response_401

    if response.status_code == 403:
        response_403 = ErrorResponse.from_dict(response.json())

        return response_403

    if response.status_code == 422:
        response_422 = ErrorResponse.from_dict(response.json())

        return response_422

    if client.raise_on_unexpected_status:
        raise errors.UnexpectedStatus(response.status_code, response.content)
    else:
        return None


def _build_response(
    *, client: AuthenticatedClient | Client, response: httpx.Response
) -> Response[ErrorResponse | File]:
    return Response(
        status_code=HTTPStatus(response.status_code),
        content=response.content,
        headers=response.headers,
        parsed=_parse_response(client=client, response=response),
    )


def sync_detailed(
    *,
    client: AuthenticatedClient | Client,
    include_secrets: bool | Unset = False,
) -> Response[ErrorResponse | File]:
    """The organization's data as one archive

     Requires `ORG_ADMIN`; an API key needs `admin:read`. A zip holding `manifest.json` and one JSON
    Lines file per table, described in docs/portability.md. Password hashes, API key hashes, calendar
    feed tokens and visit code hashes are left out unless `include_secrets` is true. Refresh tokens and
    the signing key are never in it. `chronos-engine import` loads it into an empty database.

    Args:
        include_secrets (bool | Unset):  Default: False.

    Raises:
        errors.UnexpectedStatus: If the server returns an undocumented status code and Client.raise_on_unexpected_status is True.
        httpx.TimeoutException: If the request takes longer than Client.timeout.

    Returns:
        Response[ErrorResponse | File]
    """

    kwargs = _get_kwargs(
        include_secrets=include_secrets,
    )

    response = client.get_httpx_client().request(
        **kwargs,
    )

    return _build_response(client=client, response=response)


def sync(
    *,
    client: AuthenticatedClient | Client,
    include_secrets: bool | Unset = False,
) -> ErrorResponse | File | None:
    """The organization's data as one archive

     Requires `ORG_ADMIN`; an API key needs `admin:read`. A zip holding `manifest.json` and one JSON
    Lines file per table, described in docs/portability.md. Password hashes, API key hashes, calendar
    feed tokens and visit code hashes are left out unless `include_secrets` is true. Refresh tokens and
    the signing key are never in it. `chronos-engine import` loads it into an empty database.

    Args:
        include_secrets (bool | Unset):  Default: False.

    Raises:
        errors.UnexpectedStatus: If the server returns an undocumented status code and Client.raise_on_unexpected_status is True.
        httpx.TimeoutException: If the request takes longer than Client.timeout.

    Returns:
        ErrorResponse | File
    """

    return sync_detailed(
        client=client,
        include_secrets=include_secrets,
    ).parsed


async def asyncio_detailed(
    *,
    client: AuthenticatedClient | Client,
    include_secrets: bool | Unset = False,
) -> Response[ErrorResponse | File]:
    """The organization's data as one archive

     Requires `ORG_ADMIN`; an API key needs `admin:read`. A zip holding `manifest.json` and one JSON
    Lines file per table, described in docs/portability.md. Password hashes, API key hashes, calendar
    feed tokens and visit code hashes are left out unless `include_secrets` is true. Refresh tokens and
    the signing key are never in it. `chronos-engine import` loads it into an empty database.

    Args:
        include_secrets (bool | Unset):  Default: False.

    Raises:
        errors.UnexpectedStatus: If the server returns an undocumented status code and Client.raise_on_unexpected_status is True.
        httpx.TimeoutException: If the request takes longer than Client.timeout.

    Returns:
        Response[ErrorResponse | File]
    """

    kwargs = _get_kwargs(
        include_secrets=include_secrets,
    )

    response = await client.get_async_httpx_client().request(**kwargs)

    return _build_response(client=client, response=response)


async def asyncio(
    *,
    client: AuthenticatedClient | Client,
    include_secrets: bool | Unset = False,
) -> ErrorResponse | File | None:
    """The organization's data as one archive

     Requires `ORG_ADMIN`; an API key needs `admin:read`. A zip holding `manifest.json` and one JSON
    Lines file per table, described in docs/portability.md. Password hashes, API key hashes, calendar
    feed tokens and visit code hashes are left out unless `include_secrets` is true. Refresh tokens and
    the signing key are never in it. `chronos-engine import` loads it into an empty database.

    Args:
        include_secrets (bool | Unset):  Default: False.

    Raises:
        errors.UnexpectedStatus: If the server returns an undocumented status code and Client.raise_on_unexpected_status is True.
        httpx.TimeoutException: If the request takes longer than Client.timeout.

    Returns:
        ErrorResponse | File
    """

    return (
        await asyncio_detailed(
            client=client,
            include_secrets=include_secrets,
        )
    ).parsed
