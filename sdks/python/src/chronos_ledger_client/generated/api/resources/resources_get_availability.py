import datetime
from http import HTTPStatus
from typing import Any
from urllib.parse import quote

import httpx

from ... import errors
from ...client import AuthenticatedClient, Client
from ...models.availability_response import AvailabilityResponse
from ...models.error_response import ErrorResponse
from ...types import UNSET, Response


def _get_kwargs(
    resource_id: int,
    *,
    from_: datetime.date,
    to: datetime.date,
) -> dict[str, Any]:

    params: dict[str, Any] = {}

    json_from_ = from_.isoformat()
    params["from"] = json_from_

    json_to = to.isoformat()
    params["to"] = json_to

    params = {k: v for k, v in params.items() if v is not UNSET and v is not None}

    _kwargs: dict[str, Any] = {
        "method": "get",
        "url": "/api/v1/resources/{resource_id}/availability".format(
            resource_id=quote(str(resource_id), safe=""),
        ),
        "params": params,
    }

    return _kwargs


def _parse_response(
    *, client: AuthenticatedClient | Client, response: httpx.Response
) -> AvailabilityResponse | ErrorResponse | None:
    if response.status_code == 200:
        response_200 = AvailabilityResponse.from_dict(response.json())

        return response_200

    if response.status_code == 401:
        response_401 = ErrorResponse.from_dict(response.json())

        return response_401

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
) -> Response[AvailabilityResponse | ErrorResponse]:
    return Response(
        status_code=HTTPStatus(response.status_code),
        content=response.content,
        headers=response.headers,
        parsed=_parse_response(client=client, response=response),
    )


def sync_detailed(
    resource_id: int,
    *,
    client: AuthenticatedClient | Client,
    from_: datetime.date,
    to: datetime.date,
) -> Response[AvailabilityResponse | ErrorResponse]:
    """When a resource is already taken

     Expands the weekly slots pointing at this resource over the range, inclusive of both ends, and
    unions in the reservations and the days the nightly generator has already written. A slot counts
    when its cycle is flagged open and the date is inside the cycle's date bounds, both ends included,
    which are the two tests nightly ledger generation applies; answering otherwise would report a room
    free on a date the generator is going to fill.

    A generated day counts whatever its cycle now says: closing a cycle leaves behind the days already
    past and any ahead that carry attendance or a note, deleting a slot leaves behind the days
    attendance was marked on, and the database refuses a second booking on top of either. Where a day
    and the slot it came from both cover a date you get the day, once, because the day is the row that
    holds the hour and keeps its window when the slot is corrected later. Dates the generator has not
    reached yet come from the slot. An inactive resource still answers: retiring a room does not clear
    its calendar.

    A busy interval's date can be the day before `from`. A booking that runs past midnight is dated the
    day it opened on and occupies the morning after, so a caller asking about Tuesday is told about a
    hold dated Monday that ends at six. Read each interval by its own date and end_date and not by the
    range that returned it: grouping by date alone files that hold under a day nobody asked about, and
    discarding anything outside the range shows a ward as free while it is staffed.

    Args:
        resource_id (int):
        from_ (datetime.date):
        to (datetime.date):

    Raises:
        errors.UnexpectedStatus: If the server returns an undocumented status code and Client.raise_on_unexpected_status is True.
        httpx.TimeoutException: If the request takes longer than Client.timeout.

    Returns:
        Response[AvailabilityResponse | ErrorResponse]
    """

    kwargs = _get_kwargs(
        resource_id=resource_id,
        from_=from_,
        to=to,
    )

    response = client.get_httpx_client().request(
        **kwargs,
    )

    return _build_response(client=client, response=response)


def sync(
    resource_id: int,
    *,
    client: AuthenticatedClient | Client,
    from_: datetime.date,
    to: datetime.date,
) -> AvailabilityResponse | ErrorResponse | None:
    """When a resource is already taken

     Expands the weekly slots pointing at this resource over the range, inclusive of both ends, and
    unions in the reservations and the days the nightly generator has already written. A slot counts
    when its cycle is flagged open and the date is inside the cycle's date bounds, both ends included,
    which are the two tests nightly ledger generation applies; answering otherwise would report a room
    free on a date the generator is going to fill.

    A generated day counts whatever its cycle now says: closing a cycle leaves behind the days already
    past and any ahead that carry attendance or a note, deleting a slot leaves behind the days
    attendance was marked on, and the database refuses a second booking on top of either. Where a day
    and the slot it came from both cover a date you get the day, once, because the day is the row that
    holds the hour and keeps its window when the slot is corrected later. Dates the generator has not
    reached yet come from the slot. An inactive resource still answers: retiring a room does not clear
    its calendar.

    A busy interval's date can be the day before `from`. A booking that runs past midnight is dated the
    day it opened on and occupies the morning after, so a caller asking about Tuesday is told about a
    hold dated Monday that ends at six. Read each interval by its own date and end_date and not by the
    range that returned it: grouping by date alone files that hold under a day nobody asked about, and
    discarding anything outside the range shows a ward as free while it is staffed.

    Args:
        resource_id (int):
        from_ (datetime.date):
        to (datetime.date):

    Raises:
        errors.UnexpectedStatus: If the server returns an undocumented status code and Client.raise_on_unexpected_status is True.
        httpx.TimeoutException: If the request takes longer than Client.timeout.

    Returns:
        AvailabilityResponse | ErrorResponse
    """

    return sync_detailed(
        resource_id=resource_id,
        client=client,
        from_=from_,
        to=to,
    ).parsed


async def asyncio_detailed(
    resource_id: int,
    *,
    client: AuthenticatedClient | Client,
    from_: datetime.date,
    to: datetime.date,
) -> Response[AvailabilityResponse | ErrorResponse]:
    """When a resource is already taken

     Expands the weekly slots pointing at this resource over the range, inclusive of both ends, and
    unions in the reservations and the days the nightly generator has already written. A slot counts
    when its cycle is flagged open and the date is inside the cycle's date bounds, both ends included,
    which are the two tests nightly ledger generation applies; answering otherwise would report a room
    free on a date the generator is going to fill.

    A generated day counts whatever its cycle now says: closing a cycle leaves behind the days already
    past and any ahead that carry attendance or a note, deleting a slot leaves behind the days
    attendance was marked on, and the database refuses a second booking on top of either. Where a day
    and the slot it came from both cover a date you get the day, once, because the day is the row that
    holds the hour and keeps its window when the slot is corrected later. Dates the generator has not
    reached yet come from the slot. An inactive resource still answers: retiring a room does not clear
    its calendar.

    A busy interval's date can be the day before `from`. A booking that runs past midnight is dated the
    day it opened on and occupies the morning after, so a caller asking about Tuesday is told about a
    hold dated Monday that ends at six. Read each interval by its own date and end_date and not by the
    range that returned it: grouping by date alone files that hold under a day nobody asked about, and
    discarding anything outside the range shows a ward as free while it is staffed.

    Args:
        resource_id (int):
        from_ (datetime.date):
        to (datetime.date):

    Raises:
        errors.UnexpectedStatus: If the server returns an undocumented status code and Client.raise_on_unexpected_status is True.
        httpx.TimeoutException: If the request takes longer than Client.timeout.

    Returns:
        Response[AvailabilityResponse | ErrorResponse]
    """

    kwargs = _get_kwargs(
        resource_id=resource_id,
        from_=from_,
        to=to,
    )

    response = await client.get_async_httpx_client().request(**kwargs)

    return _build_response(client=client, response=response)


async def asyncio(
    resource_id: int,
    *,
    client: AuthenticatedClient | Client,
    from_: datetime.date,
    to: datetime.date,
) -> AvailabilityResponse | ErrorResponse | None:
    """When a resource is already taken

     Expands the weekly slots pointing at this resource over the range, inclusive of both ends, and
    unions in the reservations and the days the nightly generator has already written. A slot counts
    when its cycle is flagged open and the date is inside the cycle's date bounds, both ends included,
    which are the two tests nightly ledger generation applies; answering otherwise would report a room
    free on a date the generator is going to fill.

    A generated day counts whatever its cycle now says: closing a cycle leaves behind the days already
    past and any ahead that carry attendance or a note, deleting a slot leaves behind the days
    attendance was marked on, and the database refuses a second booking on top of either. Where a day
    and the slot it came from both cover a date you get the day, once, because the day is the row that
    holds the hour and keeps its window when the slot is corrected later. Dates the generator has not
    reached yet come from the slot. An inactive resource still answers: retiring a room does not clear
    its calendar.

    A busy interval's date can be the day before `from`. A booking that runs past midnight is dated the
    day it opened on and occupies the morning after, so a caller asking about Tuesday is told about a
    hold dated Monday that ends at six. Read each interval by its own date and end_date and not by the
    range that returned it: grouping by date alone files that hold under a day nobody asked about, and
    discarding anything outside the range shows a ward as free while it is staffed.

    Args:
        resource_id (int):
        from_ (datetime.date):
        to (datetime.date):

    Raises:
        errors.UnexpectedStatus: If the server returns an undocumented status code and Client.raise_on_unexpected_status is True.
        httpx.TimeoutException: If the request takes longer than Client.timeout.

    Returns:
        AvailabilityResponse | ErrorResponse
    """

    return (
        await asyncio_detailed(
            resource_id=resource_id,
            client=client,
            from_=from_,
            to=to,
        )
    ).parsed
