from http import HTTPStatus
from typing import Any

import httpx

from ... import errors
from ...client import AuthenticatedClient, Client
from ...models.error_response import ErrorResponse
from ...models.master_slot_create import MasterSlotCreate
from ...models.reservation_conflict import ReservationConflict
from ...models.schedule_create_slot_response_200 import ScheduleCreateSlotResponse200
from ...types import Response


def _get_kwargs(
    *,
    body: MasterSlotCreate,
) -> dict[str, Any]:
    headers: dict[str, Any] = {}

    _kwargs: dict[str, Any] = {
        "method": "post",
        "url": "/api/v1/schedule/slots",
    }

    _kwargs["json"] = body.to_dict()

    headers["Content-Type"] = "application/json"

    _kwargs["headers"] = headers
    return _kwargs


def _parse_response(
    *, client: AuthenticatedClient | Client, response: httpx.Response
) -> ErrorResponse | ReservationConflict | ScheduleCreateSlotResponse200 | None:
    if response.status_code == 200:
        response_200 = ScheduleCreateSlotResponse200.from_dict(response.json())

        return response_200

    if response.status_code == 403:
        response_403 = ErrorResponse.from_dict(response.json())

        return response_403

    if response.status_code == 404:
        response_404 = ErrorResponse.from_dict(response.json())

        return response_404

    if response.status_code == 409:
        response_409 = ReservationConflict.from_dict(response.json())

        return response_409

    if response.status_code == 422:
        response_422 = ErrorResponse.from_dict(response.json())

        return response_422

    if client.raise_on_unexpected_status:
        raise errors.UnexpectedStatus(response.status_code, response.content)
    else:
        return None


def _build_response(
    *, client: AuthenticatedClient | Client, response: httpx.Response
) -> Response[ErrorResponse | ReservationConflict | ScheduleCreateSlotResponse200]:
    return Response(
        status_code=HTTPStatus(response.status_code),
        content=response.content,
        headers=response.headers,
        parsed=_parse_response(client=client, response=response),
    )


def sync_detailed(
    *,
    client: AuthenticatedClient | Client,
    body: MasterSlotCreate,
) -> Response[ErrorResponse | ReservationConflict | ScheduleCreateSlotResponse200]:
    """Add a master slot

     Admin only. A UNIT_ADMIN may only add slots inside their own unit.

    Refused with 409 where the room is already taken for part of that window, whether by a booking or by
    another class. Only holds from today forward count, because a slot lays down days from now onwards
    and never backwards, and a slot in a closed cycle is neither checked nor counted against, because
    such a slot does not occupy the room and a booking is already accepted on top of one. Every open
    cycle counts, including a second one covering a different part of the year: the nightly generator
    lays every open cycle onto today, so all of them hold the room today.

    Refused with 409 as well where a day has already been generated on that room in part of that window.
    Such a day may have no slot speaking for it any more: closing a cycle leaves behind the days ahead
    that carry attendance or a note, and deleting a slot leaves behind the days that carry attendance.
    Both of those read as free to the two checks above while somebody is still due at the door, so this
    one has no cycle gate on either side.

    Args:
        body (MasterSlotCreate):

    Raises:
        errors.UnexpectedStatus: If the server returns an undocumented status code and Client.raise_on_unexpected_status is True.
        httpx.TimeoutException: If the request takes longer than Client.timeout.

    Returns:
        Response[ErrorResponse | ReservationConflict | ScheduleCreateSlotResponse200]
    """

    kwargs = _get_kwargs(
        body=body,
    )

    response = client.get_httpx_client().request(
        **kwargs,
    )

    return _build_response(client=client, response=response)


def sync(
    *,
    client: AuthenticatedClient | Client,
    body: MasterSlotCreate,
) -> ErrorResponse | ReservationConflict | ScheduleCreateSlotResponse200 | None:
    """Add a master slot

     Admin only. A UNIT_ADMIN may only add slots inside their own unit.

    Refused with 409 where the room is already taken for part of that window, whether by a booking or by
    another class. Only holds from today forward count, because a slot lays down days from now onwards
    and never backwards, and a slot in a closed cycle is neither checked nor counted against, because
    such a slot does not occupy the room and a booking is already accepted on top of one. Every open
    cycle counts, including a second one covering a different part of the year: the nightly generator
    lays every open cycle onto today, so all of them hold the room today.

    Refused with 409 as well where a day has already been generated on that room in part of that window.
    Such a day may have no slot speaking for it any more: closing a cycle leaves behind the days ahead
    that carry attendance or a note, and deleting a slot leaves behind the days that carry attendance.
    Both of those read as free to the two checks above while somebody is still due at the door, so this
    one has no cycle gate on either side.

    Args:
        body (MasterSlotCreate):

    Raises:
        errors.UnexpectedStatus: If the server returns an undocumented status code and Client.raise_on_unexpected_status is True.
        httpx.TimeoutException: If the request takes longer than Client.timeout.

    Returns:
        ErrorResponse | ReservationConflict | ScheduleCreateSlotResponse200
    """

    return sync_detailed(
        client=client,
        body=body,
    ).parsed


async def asyncio_detailed(
    *,
    client: AuthenticatedClient | Client,
    body: MasterSlotCreate,
) -> Response[ErrorResponse | ReservationConflict | ScheduleCreateSlotResponse200]:
    """Add a master slot

     Admin only. A UNIT_ADMIN may only add slots inside their own unit.

    Refused with 409 where the room is already taken for part of that window, whether by a booking or by
    another class. Only holds from today forward count, because a slot lays down days from now onwards
    and never backwards, and a slot in a closed cycle is neither checked nor counted against, because
    such a slot does not occupy the room and a booking is already accepted on top of one. Every open
    cycle counts, including a second one covering a different part of the year: the nightly generator
    lays every open cycle onto today, so all of them hold the room today.

    Refused with 409 as well where a day has already been generated on that room in part of that window.
    Such a day may have no slot speaking for it any more: closing a cycle leaves behind the days ahead
    that carry attendance or a note, and deleting a slot leaves behind the days that carry attendance.
    Both of those read as free to the two checks above while somebody is still due at the door, so this
    one has no cycle gate on either side.

    Args:
        body (MasterSlotCreate):

    Raises:
        errors.UnexpectedStatus: If the server returns an undocumented status code and Client.raise_on_unexpected_status is True.
        httpx.TimeoutException: If the request takes longer than Client.timeout.

    Returns:
        Response[ErrorResponse | ReservationConflict | ScheduleCreateSlotResponse200]
    """

    kwargs = _get_kwargs(
        body=body,
    )

    response = await client.get_async_httpx_client().request(**kwargs)

    return _build_response(client=client, response=response)


async def asyncio(
    *,
    client: AuthenticatedClient | Client,
    body: MasterSlotCreate,
) -> ErrorResponse | ReservationConflict | ScheduleCreateSlotResponse200 | None:
    """Add a master slot

     Admin only. A UNIT_ADMIN may only add slots inside their own unit.

    Refused with 409 where the room is already taken for part of that window, whether by a booking or by
    another class. Only holds from today forward count, because a slot lays down days from now onwards
    and never backwards, and a slot in a closed cycle is neither checked nor counted against, because
    such a slot does not occupy the room and a booking is already accepted on top of one. Every open
    cycle counts, including a second one covering a different part of the year: the nightly generator
    lays every open cycle onto today, so all of them hold the room today.

    Refused with 409 as well where a day has already been generated on that room in part of that window.
    Such a day may have no slot speaking for it any more: closing a cycle leaves behind the days ahead
    that carry attendance or a note, and deleting a slot leaves behind the days that carry attendance.
    Both of those read as free to the two checks above while somebody is still due at the door, so this
    one has no cycle gate on either side.

    Args:
        body (MasterSlotCreate):

    Raises:
        errors.UnexpectedStatus: If the server returns an undocumented status code and Client.raise_on_unexpected_status is True.
        httpx.TimeoutException: If the request takes longer than Client.timeout.

    Returns:
        ErrorResponse | ReservationConflict | ScheduleCreateSlotResponse200
    """

    return (
        await asyncio_detailed(
            client=client,
            body=body,
        )
    ).parsed
