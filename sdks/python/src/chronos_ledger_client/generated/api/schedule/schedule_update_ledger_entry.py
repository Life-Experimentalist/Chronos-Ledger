from http import HTTPStatus
from typing import Any
from urllib.parse import quote

import httpx

from ... import errors
from ...client import AuthenticatedClient, Client
from ...models.daily_ledger_update import DailyLedgerUpdate
from ...models.error_response import ErrorResponse
from ...models.schedule_update_ledger_entry_response_200 import ScheduleUpdateLedgerEntryResponse200
from ...types import Response


def _get_kwargs(
    ledger_id: int,
    *,
    body: DailyLedgerUpdate,
) -> dict[str, Any]:
    headers: dict[str, Any] = {}

    _kwargs: dict[str, Any] = {
        "method": "patch",
        "url": "/api/v1/schedule/ledger/{ledger_id}".format(
            ledger_id=quote(str(ledger_id), safe=""),
        ),
    }

    _kwargs["json"] = body.to_dict()

    headers["Content-Type"] = "application/json"

    _kwargs["headers"] = headers
    return _kwargs


def _parse_response(
    *, client: AuthenticatedClient | Client, response: httpx.Response
) -> ErrorResponse | ScheduleUpdateLedgerEntryResponse200 | None:
    if response.status_code == 200:
        response_200 = ScheduleUpdateLedgerEntryResponse200.from_dict(response.json())

        return response_200

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
) -> Response[ErrorResponse | ScheduleUpdateLedgerEntryResponse200]:
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
    body: DailyLedgerUpdate,
) -> Response[ErrorResponse | ScheduleUpdateLedgerEntryResponse200]:
    """Update a ledger entry

     Requires `SUPER_ADMIN` or `UNIT_ADMIN`, and a unit admin only within their own unit. Sets the
    substitute, the delivery format, or the day's own geofence. A field left out, or sent as null, keeps
    its current value.

    Args:
        ledger_id (int):
        body (DailyLedgerUpdate): A field left out keeps its value and a null clears it, except
            operational_state and delivery_format, which cannot be null (422).

    Raises:
        errors.UnexpectedStatus: If the server returns an undocumented status code and Client.raise_on_unexpected_status is True.
        httpx.TimeoutException: If the request takes longer than Client.timeout.

    Returns:
        Response[ErrorResponse | ScheduleUpdateLedgerEntryResponse200]
    """

    kwargs = _get_kwargs(
        ledger_id=ledger_id,
        body=body,
    )

    response = client.get_httpx_client().request(
        **kwargs,
    )

    return _build_response(client=client, response=response)


def sync(
    ledger_id: int,
    *,
    client: AuthenticatedClient | Client,
    body: DailyLedgerUpdate,
) -> ErrorResponse | ScheduleUpdateLedgerEntryResponse200 | None:
    """Update a ledger entry

     Requires `SUPER_ADMIN` or `UNIT_ADMIN`, and a unit admin only within their own unit. Sets the
    substitute, the delivery format, or the day's own geofence. A field left out, or sent as null, keeps
    its current value.

    Args:
        ledger_id (int):
        body (DailyLedgerUpdate): A field left out keeps its value and a null clears it, except
            operational_state and delivery_format, which cannot be null (422).

    Raises:
        errors.UnexpectedStatus: If the server returns an undocumented status code and Client.raise_on_unexpected_status is True.
        httpx.TimeoutException: If the request takes longer than Client.timeout.

    Returns:
        ErrorResponse | ScheduleUpdateLedgerEntryResponse200
    """

    return sync_detailed(
        ledger_id=ledger_id,
        client=client,
        body=body,
    ).parsed


async def asyncio_detailed(
    ledger_id: int,
    *,
    client: AuthenticatedClient | Client,
    body: DailyLedgerUpdate,
) -> Response[ErrorResponse | ScheduleUpdateLedgerEntryResponse200]:
    """Update a ledger entry

     Requires `SUPER_ADMIN` or `UNIT_ADMIN`, and a unit admin only within their own unit. Sets the
    substitute, the delivery format, or the day's own geofence. A field left out, or sent as null, keeps
    its current value.

    Args:
        ledger_id (int):
        body (DailyLedgerUpdate): A field left out keeps its value and a null clears it, except
            operational_state and delivery_format, which cannot be null (422).

    Raises:
        errors.UnexpectedStatus: If the server returns an undocumented status code and Client.raise_on_unexpected_status is True.
        httpx.TimeoutException: If the request takes longer than Client.timeout.

    Returns:
        Response[ErrorResponse | ScheduleUpdateLedgerEntryResponse200]
    """

    kwargs = _get_kwargs(
        ledger_id=ledger_id,
        body=body,
    )

    response = await client.get_async_httpx_client().request(**kwargs)

    return _build_response(client=client, response=response)


async def asyncio(
    ledger_id: int,
    *,
    client: AuthenticatedClient | Client,
    body: DailyLedgerUpdate,
) -> ErrorResponse | ScheduleUpdateLedgerEntryResponse200 | None:
    """Update a ledger entry

     Requires `SUPER_ADMIN` or `UNIT_ADMIN`, and a unit admin only within their own unit. Sets the
    substitute, the delivery format, or the day's own geofence. A field left out, or sent as null, keeps
    its current value.

    Args:
        ledger_id (int):
        body (DailyLedgerUpdate): A field left out keeps its value and a null clears it, except
            operational_state and delivery_format, which cannot be null (422).

    Raises:
        errors.UnexpectedStatus: If the server returns an undocumented status code and Client.raise_on_unexpected_status is True.
        httpx.TimeoutException: If the request takes longer than Client.timeout.

    Returns:
        ErrorResponse | ScheduleUpdateLedgerEntryResponse200
    """

    return (
        await asyncio_detailed(
            ledger_id=ledger_id,
            client=client,
            body=body,
        )
    ).parsed
