from http import HTTPStatus
from io import BytesIO
from typing import Any

import httpx

from ... import errors
from ...client import AuthenticatedClient, Client
from ...models.error_response import ErrorResponse
from ...types import File, Response


def _get_kwargs() -> dict[str, Any]:

    _kwargs: dict[str, Any] = {
        "method": "get",
        "url": "/api/v1/admin/export",
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
) -> Response[ErrorResponse | File]:
    """The organization's data as one archive

     Requires `ORG_ADMIN`; an API key needs `admin:read`. A zip holding `manifest.json` and one JSON
    Lines file per table, described in docs/portability.md, with the caller's organization's rows only.
    `chronos-engine export` writes every organization. Password hashes, API key hashes, calendar feed
    tokens and visit code hashes are always left out; an archive with them comes only from `chronos-
    engine export --include-secrets`. Refresh tokens and the signing key are never in it. Every export
    is written to the audit log, although it is a read. `chronos-engine import` loads the archive into
    an empty database.

    Raises:
        errors.UnexpectedStatus: If the server returns an undocumented status code and Client.raise_on_unexpected_status is True.
        httpx.TimeoutException: If the request takes longer than Client.timeout.

    Returns:
        Response[ErrorResponse | File]
    """

    kwargs = _get_kwargs()

    response = client.get_httpx_client().request(
        **kwargs,
    )

    return _build_response(client=client, response=response)


def sync(
    *,
    client: AuthenticatedClient | Client,
) -> ErrorResponse | File | None:
    """The organization's data as one archive

     Requires `ORG_ADMIN`; an API key needs `admin:read`. A zip holding `manifest.json` and one JSON
    Lines file per table, described in docs/portability.md, with the caller's organization's rows only.
    `chronos-engine export` writes every organization. Password hashes, API key hashes, calendar feed
    tokens and visit code hashes are always left out; an archive with them comes only from `chronos-
    engine export --include-secrets`. Refresh tokens and the signing key are never in it. Every export
    is written to the audit log, although it is a read. `chronos-engine import` loads the archive into
    an empty database.

    Raises:
        errors.UnexpectedStatus: If the server returns an undocumented status code and Client.raise_on_unexpected_status is True.
        httpx.TimeoutException: If the request takes longer than Client.timeout.

    Returns:
        ErrorResponse | File
    """

    return sync_detailed(
        client=client,
    ).parsed


async def asyncio_detailed(
    *,
    client: AuthenticatedClient | Client,
) -> Response[ErrorResponse | File]:
    """The organization's data as one archive

     Requires `ORG_ADMIN`; an API key needs `admin:read`. A zip holding `manifest.json` and one JSON
    Lines file per table, described in docs/portability.md, with the caller's organization's rows only.
    `chronos-engine export` writes every organization. Password hashes, API key hashes, calendar feed
    tokens and visit code hashes are always left out; an archive with them comes only from `chronos-
    engine export --include-secrets`. Refresh tokens and the signing key are never in it. Every export
    is written to the audit log, although it is a read. `chronos-engine import` loads the archive into
    an empty database.

    Raises:
        errors.UnexpectedStatus: If the server returns an undocumented status code and Client.raise_on_unexpected_status is True.
        httpx.TimeoutException: If the request takes longer than Client.timeout.

    Returns:
        Response[ErrorResponse | File]
    """

    kwargs = _get_kwargs()

    response = await client.get_async_httpx_client().request(**kwargs)

    return _build_response(client=client, response=response)


async def asyncio(
    *,
    client: AuthenticatedClient | Client,
) -> ErrorResponse | File | None:
    """The organization's data as one archive

     Requires `ORG_ADMIN`; an API key needs `admin:read`. A zip holding `manifest.json` and one JSON
    Lines file per table, described in docs/portability.md, with the caller's organization's rows only.
    `chronos-engine export` writes every organization. Password hashes, API key hashes, calendar feed
    tokens and visit code hashes are always left out; an archive with them comes only from `chronos-
    engine export --include-secrets`. Refresh tokens and the signing key are never in it. Every export
    is written to the audit log, although it is a read. `chronos-engine import` loads the archive into
    an empty database.

    Raises:
        errors.UnexpectedStatus: If the server returns an undocumented status code and Client.raise_on_unexpected_status is True.
        httpx.TimeoutException: If the request takes longer than Client.timeout.

    Returns:
        ErrorResponse | File
    """

    return (
        await asyncio_detailed(
            client=client,
        )
    ).parsed
