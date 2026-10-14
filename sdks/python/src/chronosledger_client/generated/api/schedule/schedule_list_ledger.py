import datetime
from http import HTTPStatus
from typing import Any

import httpx

from ... import errors
from ...client import AuthenticatedClient, Client
from ...models.daily_ledger_response import DailyLedgerResponse
from ...models.error_response import ErrorResponse
from ...types import UNSET, Response, Unset


def _get_kwargs(
    *,
    from_: datetime.date,
    to: datetime.date,
    resource_id: int | Unset = UNSET,
    limit: int | Unset = UNSET,
    offset: int | Unset = 0,
) -> dict[str, Any]:

    params: dict[str, Any] = {}

    json_from_ = from_.isoformat()
    params["from"] = json_from_

    json_to = to.isoformat()
    params["to"] = json_to

    params["resource_id"] = resource_id

    params["limit"] = limit

    params["offset"] = offset

    params = {k: v for k, v in params.items() if v is not UNSET and v is not None}

    _kwargs: dict[str, Any] = {
        "method": "get",
        "url": "/api/v1/schedule/ledger",
        "params": params,
    }

    return _kwargs


def _parse_response(
    *, client: AuthenticatedClient | Client, response: httpx.Response
) -> ErrorResponse | list[DailyLedgerResponse] | None:
    if response.status_code == 200:
        response_200 = []
        _response_200 = response.json()
        for response_200_item_data in _response_200:
            response_200_item = DailyLedgerResponse.from_dict(response_200_item_data)

            response_200.append(response_200_item)

        return response_200

    if response.status_code == 401:
        response_401 = ErrorResponse.from_dict(response.json())

        return response_401

    if response.status_code == 422:
        response_422 = ErrorResponse.from_dict(response.json())

        return response_422

    if client.raise_on_unexpected_status:
        raise errors.UnexpectedStatus(response.status_code, response.content)
    else:
        return None


def _build_response(
    *, client: AuthenticatedClient | Client, response: httpx.Response
) -> Response[ErrorResponse | list[DailyLedgerResponse]]:
    return Response(
        status_code=HTTPStatus(response.status_code),
        content=response.content,
        headers=response.headers,
        parsed=_parse_response(client=client, response=response),
    )


def sync_detailed(
    *,
    client: AuthenticatedClient | Client,
    from_: datetime.date,
    to: datetime.date,
    resource_id: int | Unset = UNSET,
    limit: int | Unset = UNSET,
    offset: int | Unset = 0,
) -> Response[ErrorResponse | list[DailyLedgerResponse]]:
    """Ledger entries between two dates

     Both dates included, ordered by date, then start time. Rows and the role filter are the same as
    `/schedule/ledger/today`. `to` before `from` is refused with 422.

    Args:
        from_ (datetime.date):
        to (datetime.date):
        resource_id (int | Unset):
        limit (int | Unset):
        offset (int | Unset):  Default: 0.

    Raises:
        errors.UnexpectedStatus: If the server returns an undocumented status code and Client.raise_on_unexpected_status is True.
        httpx.TimeoutException: If the request takes longer than Client.timeout.

    Returns:
        Response[ErrorResponse | list[DailyLedgerResponse]]
    """

    kwargs = _get_kwargs(
        from_=from_,
        to=to,
        resource_id=resource_id,
        limit=limit,
        offset=offset,
    )

    response = client.get_httpx_client().request(
        **kwargs,
    )

    return _build_response(client=client, response=response)


def sync(
    *,
    client: AuthenticatedClient | Client,
    from_: datetime.date,
    to: datetime.date,
    resource_id: int | Unset = UNSET,
    limit: int | Unset = UNSET,
    offset: int | Unset = 0,
) -> ErrorResponse | list[DailyLedgerResponse] | None:
    """Ledger entries between two dates

     Both dates included, ordered by date, then start time. Rows and the role filter are the same as
    `/schedule/ledger/today`. `to` before `from` is refused with 422.

    Args:
        from_ (datetime.date):
        to (datetime.date):
        resource_id (int | Unset):
        limit (int | Unset):
        offset (int | Unset):  Default: 0.

    Raises:
        errors.UnexpectedStatus: If the server returns an undocumented status code and Client.raise_on_unexpected_status is True.
        httpx.TimeoutException: If the request takes longer than Client.timeout.

    Returns:
        ErrorResponse | list[DailyLedgerResponse]
    """

    return sync_detailed(
        client=client,
        from_=from_,
        to=to,
        resource_id=resource_id,
        limit=limit,
        offset=offset,
    ).parsed


async def asyncio_detailed(
    *,
    client: AuthenticatedClient | Client,
    from_: datetime.date,
    to: datetime.date,
    resource_id: int | Unset = UNSET,
    limit: int | Unset = UNSET,
    offset: int | Unset = 0,
) -> Response[ErrorResponse | list[DailyLedgerResponse]]:
    """Ledger entries between two dates

     Both dates included, ordered by date, then start time. Rows and the role filter are the same as
    `/schedule/ledger/today`. `to` before `from` is refused with 422.

    Args:
        from_ (datetime.date):
        to (datetime.date):
        resource_id (int | Unset):
        limit (int | Unset):
        offset (int | Unset):  Default: 0.

    Raises:
        errors.UnexpectedStatus: If the server returns an undocumented status code and Client.raise_on_unexpected_status is True.
        httpx.TimeoutException: If the request takes longer than Client.timeout.

    Returns:
        Response[ErrorResponse | list[DailyLedgerResponse]]
    """

    kwargs = _get_kwargs(
        from_=from_,
        to=to,
        resource_id=resource_id,
        limit=limit,
        offset=offset,
    )

    response = await client.get_async_httpx_client().request(**kwargs)

    return _build_response(client=client, response=response)


async def asyncio(
    *,
    client: AuthenticatedClient | Client,
    from_: datetime.date,
    to: datetime.date,
    resource_id: int | Unset = UNSET,
    limit: int | Unset = UNSET,
    offset: int | Unset = 0,
) -> ErrorResponse | list[DailyLedgerResponse] | None:
    """Ledger entries between two dates

     Both dates included, ordered by date, then start time. Rows and the role filter are the same as
    `/schedule/ledger/today`. `to` before `from` is refused with 422.

    Args:
        from_ (datetime.date):
        to (datetime.date):
        resource_id (int | Unset):
        limit (int | Unset):
        offset (int | Unset):  Default: 0.

    Raises:
        errors.UnexpectedStatus: If the server returns an undocumented status code and Client.raise_on_unexpected_status is True.
        httpx.TimeoutException: If the request takes longer than Client.timeout.

    Returns:
        ErrorResponse | list[DailyLedgerResponse]
    """

    return (
        await asyncio_detailed(
            client=client,
            from_=from_,
            to=to,
            resource_id=resource_id,
            limit=limit,
            offset=offset,
        )
    ).parsed
