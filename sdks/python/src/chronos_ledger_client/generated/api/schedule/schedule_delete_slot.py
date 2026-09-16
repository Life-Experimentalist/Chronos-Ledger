from http import HTTPStatus
from typing import Any
from urllib.parse import quote

import httpx

from ... import errors
from ...client import AuthenticatedClient, Client
from ...models.error_response import ErrorResponse
from ...models.slot_deletion_result import SlotDeletionResult
from ...types import Response


def _get_kwargs(
    slot_id: int,
) -> dict[str, Any]:

    _kwargs: dict[str, Any] = {
        "method": "delete",
        "url": "/api/v1/schedule/slots/{slot_id}".format(
            slot_id=quote(str(slot_id), safe=""),
        ),
    }

    return _kwargs


def _parse_response(
    *, client: AuthenticatedClient | Client, response: httpx.Response
) -> ErrorResponse | SlotDeletionResult | None:
    if response.status_code == 200:
        response_200 = SlotDeletionResult.from_dict(response.json())

        return response_200

    if response.status_code == 403:
        response_403 = ErrorResponse.from_dict(response.json())

        return response_403

    if response.status_code == 404:
        response_404 = ErrorResponse.from_dict(response.json())

        return response_404

    if response.status_code == 409:
        response_409 = ErrorResponse.from_dict(response.json())

        return response_409

    if client.raise_on_unexpected_status:
        raise errors.UnexpectedStatus(response.status_code, response.content)
    else:
        return None


def _build_response(
    *, client: AuthenticatedClient | Client, response: httpx.Response
) -> Response[ErrorResponse | SlotDeletionResult]:
    return Response(
        status_code=HTTPStatus(response.status_code),
        content=response.content,
        headers=response.headers,
        parsed=_parse_response(client=client, response=response),
    )


def sync_detailed(
    slot_id: int,
    *,
    client: AuthenticatedClient | Client,
) -> Response[ErrorResponse | SlotDeletionResult]:
    """Take a master slot off the timetable

     Admin only. Days from today onward are still plans and are removed; days already past keep their
    attendance and notes and are left with no slot to point at. If any day from today onward has been
    marked, nothing is deleted and the response names those dates.

    A detached day keeps its window. The day was copied off the slot when it was generated, so losing
    the slot does not lose the hour it ran at and it stays a timed event on a calendar feed. Days
    generated before the ledger carried its own window have none to keep and still appear as all-day
    events.

    Args:
        slot_id (int):

    Raises:
        errors.UnexpectedStatus: If the server returns an undocumented status code and Client.raise_on_unexpected_status is True.
        httpx.TimeoutException: If the request takes longer than Client.timeout.

    Returns:
        Response[ErrorResponse | SlotDeletionResult]
    """

    kwargs = _get_kwargs(
        slot_id=slot_id,
    )

    response = client.get_httpx_client().request(
        **kwargs,
    )

    return _build_response(client=client, response=response)


def sync(
    slot_id: int,
    *,
    client: AuthenticatedClient | Client,
) -> ErrorResponse | SlotDeletionResult | None:
    """Take a master slot off the timetable

     Admin only. Days from today onward are still plans and are removed; days already past keep their
    attendance and notes and are left with no slot to point at. If any day from today onward has been
    marked, nothing is deleted and the response names those dates.

    A detached day keeps its window. The day was copied off the slot when it was generated, so losing
    the slot does not lose the hour it ran at and it stays a timed event on a calendar feed. Days
    generated before the ledger carried its own window have none to keep and still appear as all-day
    events.

    Args:
        slot_id (int):

    Raises:
        errors.UnexpectedStatus: If the server returns an undocumented status code and Client.raise_on_unexpected_status is True.
        httpx.TimeoutException: If the request takes longer than Client.timeout.

    Returns:
        ErrorResponse | SlotDeletionResult
    """

    return sync_detailed(
        slot_id=slot_id,
        client=client,
    ).parsed


async def asyncio_detailed(
    slot_id: int,
    *,
    client: AuthenticatedClient | Client,
) -> Response[ErrorResponse | SlotDeletionResult]:
    """Take a master slot off the timetable

     Admin only. Days from today onward are still plans and are removed; days already past keep their
    attendance and notes and are left with no slot to point at. If any day from today onward has been
    marked, nothing is deleted and the response names those dates.

    A detached day keeps its window. The day was copied off the slot when it was generated, so losing
    the slot does not lose the hour it ran at and it stays a timed event on a calendar feed. Days
    generated before the ledger carried its own window have none to keep and still appear as all-day
    events.

    Args:
        slot_id (int):

    Raises:
        errors.UnexpectedStatus: If the server returns an undocumented status code and Client.raise_on_unexpected_status is True.
        httpx.TimeoutException: If the request takes longer than Client.timeout.

    Returns:
        Response[ErrorResponse | SlotDeletionResult]
    """

    kwargs = _get_kwargs(
        slot_id=slot_id,
    )

    response = await client.get_async_httpx_client().request(**kwargs)

    return _build_response(client=client, response=response)


async def asyncio(
    slot_id: int,
    *,
    client: AuthenticatedClient | Client,
) -> ErrorResponse | SlotDeletionResult | None:
    """Take a master slot off the timetable

     Admin only. Days from today onward are still plans and are removed; days already past keep their
    attendance and notes and are left with no slot to point at. If any day from today onward has been
    marked, nothing is deleted and the response names those dates.

    A detached day keeps its window. The day was copied off the slot when it was generated, so losing
    the slot does not lose the hour it ran at and it stays a timed event on a calendar feed. Days
    generated before the ledger carried its own window have none to keep and still appear as all-day
    events.

    Args:
        slot_id (int):

    Raises:
        errors.UnexpectedStatus: If the server returns an undocumented status code and Client.raise_on_unexpected_status is True.
        httpx.TimeoutException: If the request takes longer than Client.timeout.

    Returns:
        ErrorResponse | SlotDeletionResult
    """

    return (
        await asyncio_detailed(
            slot_id=slot_id,
            client=client,
        )
    ).parsed
