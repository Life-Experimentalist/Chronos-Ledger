from http import HTTPStatus
from typing import Any
from urllib.parse import quote

import httpx

from ... import errors
from ...client import AuthenticatedClient, Client
from ...models.error_response import ErrorResponse
from ...models.guest_visit_status import GuestVisitStatus
from ...types import Response


def _get_kwargs(
    code: str,
) -> dict[str, Any]:

    _kwargs: dict[str, Any] = {
        "method": "get",
        "url": "/api/v1/guest/visit/{code}".format(
            code=quote(str(code), safe=""),
        ),
    }

    return _kwargs


def _parse_response(
    *, client: AuthenticatedClient | Client, response: httpx.Response
) -> ErrorResponse | GuestVisitStatus | None:
    if response.status_code == 200:
        response_200 = GuestVisitStatus.from_dict(response.json())

        return response_200

    if response.status_code == 404:
        response_404 = ErrorResponse.from_dict(response.json())

        return response_404

    if client.raise_on_unexpected_status:
        raise errors.UnexpectedStatus(response.status_code, response.content)
    else:
        return None


def _build_response(
    *, client: AuthenticatedClient | Client, response: httpx.Response
) -> Response[ErrorResponse | GuestVisitStatus]:
    return Response(
        status_code=HTTPStatus(response.status_code),
        content=response.content,
        headers=response.headers,
        parsed=_parse_response(client=client, response=response),
    )


def sync_detailed(
    code: str,
    *,
    client: AuthenticatedClient | Client,
) -> Response[ErrorResponse | GuestVisitStatus]:
    """Follow a visit by its code (visitor)

     No credential: the code the check-in returned is the credential. Case, spaces and dashes are
    ignored. The answer is the visit's status and nothing about who came or whom they came to see. Not
    rate limited: a code is about 79 bits, and a right guess shows only whether one unnamed visit was
    approved.

    Args:
        code (str):

    Raises:
        errors.UnexpectedStatus: If the server returns an undocumented status code and Client.raise_on_unexpected_status is True.
        httpx.TimeoutException: If the request takes longer than Client.timeout.

    Returns:
        Response[ErrorResponse | GuestVisitStatus]
    """

    kwargs = _get_kwargs(
        code=code,
    )

    response = client.get_httpx_client().request(
        **kwargs,
    )

    return _build_response(client=client, response=response)


def sync(
    code: str,
    *,
    client: AuthenticatedClient | Client,
) -> ErrorResponse | GuestVisitStatus | None:
    """Follow a visit by its code (visitor)

     No credential: the code the check-in returned is the credential. Case, spaces and dashes are
    ignored. The answer is the visit's status and nothing about who came or whom they came to see. Not
    rate limited: a code is about 79 bits, and a right guess shows only whether one unnamed visit was
    approved.

    Args:
        code (str):

    Raises:
        errors.UnexpectedStatus: If the server returns an undocumented status code and Client.raise_on_unexpected_status is True.
        httpx.TimeoutException: If the request takes longer than Client.timeout.

    Returns:
        ErrorResponse | GuestVisitStatus
    """

    return sync_detailed(
        code=code,
        client=client,
    ).parsed


async def asyncio_detailed(
    code: str,
    *,
    client: AuthenticatedClient | Client,
) -> Response[ErrorResponse | GuestVisitStatus]:
    """Follow a visit by its code (visitor)

     No credential: the code the check-in returned is the credential. Case, spaces and dashes are
    ignored. The answer is the visit's status and nothing about who came or whom they came to see. Not
    rate limited: a code is about 79 bits, and a right guess shows only whether one unnamed visit was
    approved.

    Args:
        code (str):

    Raises:
        errors.UnexpectedStatus: If the server returns an undocumented status code and Client.raise_on_unexpected_status is True.
        httpx.TimeoutException: If the request takes longer than Client.timeout.

    Returns:
        Response[ErrorResponse | GuestVisitStatus]
    """

    kwargs = _get_kwargs(
        code=code,
    )

    response = await client.get_async_httpx_client().request(**kwargs)

    return _build_response(client=client, response=response)


async def asyncio(
    code: str,
    *,
    client: AuthenticatedClient | Client,
) -> ErrorResponse | GuestVisitStatus | None:
    """Follow a visit by its code (visitor)

     No credential: the code the check-in returned is the credential. Case, spaces and dashes are
    ignored. The answer is the visit's status and nothing about who came or whom they came to see. Not
    rate limited: a code is about 79 bits, and a right guess shows only whether one unnamed visit was
    approved.

    Args:
        code (str):

    Raises:
        errors.UnexpectedStatus: If the server returns an undocumented status code and Client.raise_on_unexpected_status is True.
        httpx.TimeoutException: If the request takes longer than Client.timeout.

    Returns:
        ErrorResponse | GuestVisitStatus
    """

    return (
        await asyncio_detailed(
            code=code,
            client=client,
        )
    ).parsed
