from http import HTTPStatus
from typing import Any
from urllib.parse import quote

import httpx

from ... import errors
from ...client import AuthenticatedClient, Client
from ...models.annotation_response import AnnotationResponse
from ...models.error_response import ErrorResponse
from ...types import Response


def _get_kwargs(
    ledger_id: int,
) -> dict[str, Any]:

    _kwargs: dict[str, Any] = {
        "method": "get",
        "url": "/api/v1/attendance/annotations/{ledger_id}".format(
            ledger_id=quote(str(ledger_id), safe=""),
        ),
    }

    return _kwargs


def _parse_response(
    *, client: AuthenticatedClient | Client, response: httpx.Response
) -> ErrorResponse | list[AnnotationResponse] | None:
    if response.status_code == 200:
        response_200 = []
        _response_200 = response.json()
        for response_200_item_data in _response_200:
            response_200_item = AnnotationResponse.from_dict(response_200_item_data)

            response_200.append(response_200_item)

        return response_200

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
) -> Response[ErrorResponse | list[AnnotationResponse]]:
    return Response(
        status_code=HTTPStatus(response.status_code),
        content=response.content,
        headers=response.headers,
        parsed=_parse_response(client=client, response=response),
    )


def sync_detailed(
    ledger_id: int,
    *,
    client: AuthenticatedClient | Client,
) -> Response[ErrorResponse | list[AnnotationResponse]]:
    """Get all annotations for a ledger entry

     The same gate as writing one. Unlike the roster there is no per-member fallback, because a note is
    about the session rather than about one person in it.

    Args:
        ledger_id (int):

    Raises:
        errors.UnexpectedStatus: If the server returns an undocumented status code and Client.raise_on_unexpected_status is True.
        httpx.TimeoutException: If the request takes longer than Client.timeout.

    Returns:
        Response[ErrorResponse | list[AnnotationResponse]]
    """

    kwargs = _get_kwargs(
        ledger_id=ledger_id,
    )

    response = client.get_httpx_client().request(
        **kwargs,
    )

    return _build_response(client=client, response=response)


def sync(
    ledger_id: int,
    *,
    client: AuthenticatedClient | Client,
) -> ErrorResponse | list[AnnotationResponse] | None:
    """Get all annotations for a ledger entry

     The same gate as writing one. Unlike the roster there is no per-member fallback, because a note is
    about the session rather than about one person in it.

    Args:
        ledger_id (int):

    Raises:
        errors.UnexpectedStatus: If the server returns an undocumented status code and Client.raise_on_unexpected_status is True.
        httpx.TimeoutException: If the request takes longer than Client.timeout.

    Returns:
        ErrorResponse | list[AnnotationResponse]
    """

    return sync_detailed(
        ledger_id=ledger_id,
        client=client,
    ).parsed


async def asyncio_detailed(
    ledger_id: int,
    *,
    client: AuthenticatedClient | Client,
) -> Response[ErrorResponse | list[AnnotationResponse]]:
    """Get all annotations for a ledger entry

     The same gate as writing one. Unlike the roster there is no per-member fallback, because a note is
    about the session rather than about one person in it.

    Args:
        ledger_id (int):

    Raises:
        errors.UnexpectedStatus: If the server returns an undocumented status code and Client.raise_on_unexpected_status is True.
        httpx.TimeoutException: If the request takes longer than Client.timeout.

    Returns:
        Response[ErrorResponse | list[AnnotationResponse]]
    """

    kwargs = _get_kwargs(
        ledger_id=ledger_id,
    )

    response = await client.get_async_httpx_client().request(**kwargs)

    return _build_response(client=client, response=response)


async def asyncio(
    ledger_id: int,
    *,
    client: AuthenticatedClient | Client,
) -> ErrorResponse | list[AnnotationResponse] | None:
    """Get all annotations for a ledger entry

     The same gate as writing one. Unlike the roster there is no per-member fallback, because a note is
    about the session rather than about one person in it.

    Args:
        ledger_id (int):

    Raises:
        errors.UnexpectedStatus: If the server returns an undocumented status code and Client.raise_on_unexpected_status is True.
        httpx.TimeoutException: If the request takes longer than Client.timeout.

    Returns:
        ErrorResponse | list[AnnotationResponse]
    """

    return (
        await asyncio_detailed(
            ledger_id=ledger_id,
            client=client,
        )
    ).parsed
