import datetime
from http import HTTPStatus
from typing import Any

import httpx

from ... import errors
from ...client import AuthenticatedClient, Client
from ...models.error_response import ErrorResponse
from ...models.ingestion_generate_ledger_response_200 import IngestionGenerateLedgerResponse200
from ...types import UNSET, Response, Unset


def _get_kwargs(
    *,
    target_date: datetime.date | Unset = UNSET,
) -> dict[str, Any]:

    params: dict[str, Any] = {}

    json_target_date: str | Unset = UNSET
    if not isinstance(target_date, Unset):
        json_target_date = target_date.isoformat()
    params["target_date"] = json_target_date

    params = {k: v for k, v in params.items() if v is not UNSET and v is not None}

    _kwargs: dict[str, Any] = {
        "method": "post",
        "url": "/api/v1/ingestion/generate-ledger",
        "params": params,
    }

    return _kwargs


def _parse_response(
    *, client: AuthenticatedClient | Client, response: httpx.Response
) -> ErrorResponse | IngestionGenerateLedgerResponse200 | None:
    if response.status_code == 200:
        response_200 = IngestionGenerateLedgerResponse200.from_dict(response.json())

        return response_200

    if response.status_code == 403:
        response_403 = ErrorResponse.from_dict(response.json())

        return response_403

    if client.raise_on_unexpected_status:
        raise errors.UnexpectedStatus(response.status_code, response.content)
    else:
        return None


def _build_response(
    *, client: AuthenticatedClient | Client, response: httpx.Response
) -> Response[ErrorResponse | IngestionGenerateLedgerResponse200]:
    return Response(
        status_code=HTTPStatus(response.status_code),
        content=response.content,
        headers=response.headers,
        parsed=_parse_response(client=client, response=response),
    )


def sync_detailed(
    *,
    client: AuthenticatedClient | Client,
    target_date: datetime.date | Unset = UNSET,
) -> Response[ErrorResponse | IngestionGenerateLedgerResponse200]:
    """Trigger daily ledger generation

     Requires `SUPER_ADMIN`. Generates `DailyLedger` rows from `StructuralMasterSlot` for a given date,
    tomorrow by default. The same job the nightly cron runs. Safe to re-run: a day already written for a
    slot is skipped.

    A day is skipped as well where the room is already taken for part of that window by another day. Two
    slots on one room at one hour is a state the API refuses to create, and a database holding one
    anyway materializes the slot that was put on the timetable first and drops the other. The dropped
    day is written to the server log naming the slot, the date and the room. It is not in this response.

    Args:
        target_date (datetime.date | Unset):

    Raises:
        errors.UnexpectedStatus: If the server returns an undocumented status code and Client.raise_on_unexpected_status is True.
        httpx.TimeoutException: If the request takes longer than Client.timeout.

    Returns:
        Response[ErrorResponse | IngestionGenerateLedgerResponse200]
    """

    kwargs = _get_kwargs(
        target_date=target_date,
    )

    response = client.get_httpx_client().request(
        **kwargs,
    )

    return _build_response(client=client, response=response)


def sync(
    *,
    client: AuthenticatedClient | Client,
    target_date: datetime.date | Unset = UNSET,
) -> ErrorResponse | IngestionGenerateLedgerResponse200 | None:
    """Trigger daily ledger generation

     Requires `SUPER_ADMIN`. Generates `DailyLedger` rows from `StructuralMasterSlot` for a given date,
    tomorrow by default. The same job the nightly cron runs. Safe to re-run: a day already written for a
    slot is skipped.

    A day is skipped as well where the room is already taken for part of that window by another day. Two
    slots on one room at one hour is a state the API refuses to create, and a database holding one
    anyway materializes the slot that was put on the timetable first and drops the other. The dropped
    day is written to the server log naming the slot, the date and the room. It is not in this response.

    Args:
        target_date (datetime.date | Unset):

    Raises:
        errors.UnexpectedStatus: If the server returns an undocumented status code and Client.raise_on_unexpected_status is True.
        httpx.TimeoutException: If the request takes longer than Client.timeout.

    Returns:
        ErrorResponse | IngestionGenerateLedgerResponse200
    """

    return sync_detailed(
        client=client,
        target_date=target_date,
    ).parsed


async def asyncio_detailed(
    *,
    client: AuthenticatedClient | Client,
    target_date: datetime.date | Unset = UNSET,
) -> Response[ErrorResponse | IngestionGenerateLedgerResponse200]:
    """Trigger daily ledger generation

     Requires `SUPER_ADMIN`. Generates `DailyLedger` rows from `StructuralMasterSlot` for a given date,
    tomorrow by default. The same job the nightly cron runs. Safe to re-run: a day already written for a
    slot is skipped.

    A day is skipped as well where the room is already taken for part of that window by another day. Two
    slots on one room at one hour is a state the API refuses to create, and a database holding one
    anyway materializes the slot that was put on the timetable first and drops the other. The dropped
    day is written to the server log naming the slot, the date and the room. It is not in this response.

    Args:
        target_date (datetime.date | Unset):

    Raises:
        errors.UnexpectedStatus: If the server returns an undocumented status code and Client.raise_on_unexpected_status is True.
        httpx.TimeoutException: If the request takes longer than Client.timeout.

    Returns:
        Response[ErrorResponse | IngestionGenerateLedgerResponse200]
    """

    kwargs = _get_kwargs(
        target_date=target_date,
    )

    response = await client.get_async_httpx_client().request(**kwargs)

    return _build_response(client=client, response=response)


async def asyncio(
    *,
    client: AuthenticatedClient | Client,
    target_date: datetime.date | Unset = UNSET,
) -> ErrorResponse | IngestionGenerateLedgerResponse200 | None:
    """Trigger daily ledger generation

     Requires `SUPER_ADMIN`. Generates `DailyLedger` rows from `StructuralMasterSlot` for a given date,
    tomorrow by default. The same job the nightly cron runs. Safe to re-run: a day already written for a
    slot is skipped.

    A day is skipped as well where the room is already taken for part of that window by another day. Two
    slots on one room at one hour is a state the API refuses to create, and a database holding one
    anyway materializes the slot that was put on the timetable first and drops the other. The dropped
    day is written to the server log naming the slot, the date and the room. It is not in this response.

    Args:
        target_date (datetime.date | Unset):

    Raises:
        errors.UnexpectedStatus: If the server returns an undocumented status code and Client.raise_on_unexpected_status is True.
        httpx.TimeoutException: If the request takes longer than Client.timeout.

    Returns:
        ErrorResponse | IngestionGenerateLedgerResponse200
    """

    return (
        await asyncio_detailed(
            client=client,
            target_date=target_date,
        )
    ).parsed
