from http import HTTPStatus
from typing import Any
from urllib.parse import quote

import httpx

from ... import errors
from ...client import AuthenticatedClient, Client
from ...models.error_response import ErrorResponse
from ...models.guest_decide_response_200 import GuestDecideResponse200
from ...models.guest_decision_request import GuestDecisionRequest
from ...types import Response


def _get_kwargs(
    entry_id: int,
    *,
    body: GuestDecisionRequest,
) -> dict[str, Any]:
    headers: dict[str, Any] = {}

    _kwargs: dict[str, Any] = {
        "method": "patch",
        "url": "/api/v1/guest/{entry_id}/decide".format(
            entry_id=quote(str(entry_id), safe=""),
        ),
    }

    _kwargs["json"] = body.to_dict()

    headers["Content-Type"] = "application/json"

    _kwargs["headers"] = headers
    return _kwargs


def _parse_response(
    *, client: AuthenticatedClient | Client, response: httpx.Response
) -> ErrorResponse | GuestDecideResponse200 | None:
    if response.status_code == 200:
        response_200 = GuestDecideResponse200.from_dict(response.json())

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
) -> Response[ErrorResponse | GuestDecideResponse200]:
    return Response(
        status_code=HTTPStatus(response.status_code),
        content=response.content,
        headers=response.headers,
        parsed=_parse_response(client=client, response=response),
    )


def sync_detailed(
    entry_id: int,
    *,
    client: AuthenticatedClient | Client,
    body: GuestDecisionRequest,
) -> Response[ErrorResponse | GuestDecideResponse200]:
    """Accept or decline a guest visit

    Args:
        entry_id (int):
        body (GuestDecisionRequest):

    Raises:
        errors.UnexpectedStatus: If the server returns an undocumented status code and Client.raise_on_unexpected_status is True.
        httpx.TimeoutException: If the request takes longer than Client.timeout.

    Returns:
        Response[ErrorResponse | GuestDecideResponse200]
    """

    kwargs = _get_kwargs(
        entry_id=entry_id,
        body=body,
    )

    response = client.get_httpx_client().request(
        **kwargs,
    )

    return _build_response(client=client, response=response)


def sync(
    entry_id: int,
    *,
    client: AuthenticatedClient | Client,
    body: GuestDecisionRequest,
) -> ErrorResponse | GuestDecideResponse200 | None:
    """Accept or decline a guest visit

    Args:
        entry_id (int):
        body (GuestDecisionRequest):

    Raises:
        errors.UnexpectedStatus: If the server returns an undocumented status code and Client.raise_on_unexpected_status is True.
        httpx.TimeoutException: If the request takes longer than Client.timeout.

    Returns:
        ErrorResponse | GuestDecideResponse200
    """

    return sync_detailed(
        entry_id=entry_id,
        client=client,
        body=body,
    ).parsed


async def asyncio_detailed(
    entry_id: int,
    *,
    client: AuthenticatedClient | Client,
    body: GuestDecisionRequest,
) -> Response[ErrorResponse | GuestDecideResponse200]:
    """Accept or decline a guest visit

    Args:
        entry_id (int):
        body (GuestDecisionRequest):

    Raises:
        errors.UnexpectedStatus: If the server returns an undocumented status code and Client.raise_on_unexpected_status is True.
        httpx.TimeoutException: If the request takes longer than Client.timeout.

    Returns:
        Response[ErrorResponse | GuestDecideResponse200]
    """

    kwargs = _get_kwargs(
        entry_id=entry_id,
        body=body,
    )

    response = await client.get_async_httpx_client().request(**kwargs)

    return _build_response(client=client, response=response)


async def asyncio(
    entry_id: int,
    *,
    client: AuthenticatedClient | Client,
    body: GuestDecisionRequest,
) -> ErrorResponse | GuestDecideResponse200 | None:
    """Accept or decline a guest visit

    Args:
        entry_id (int):
        body (GuestDecisionRequest):

    Raises:
        errors.UnexpectedStatus: If the server returns an undocumented status code and Client.raise_on_unexpected_status is True.
        httpx.TimeoutException: If the request takes longer than Client.timeout.

    Returns:
        ErrorResponse | GuestDecideResponse200
    """

    return (
        await asyncio_detailed(
            entry_id=entry_id,
            client=client,
            body=body,
        )
    ).parsed
