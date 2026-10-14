from http import HTTPStatus
from typing import Any
from urllib.parse import quote

import httpx

from ... import errors
from ...client import AuthenticatedClient, Client
from ...models.capacity_exceeded import CapacityExceeded
from ...models.error_response import ErrorResponse
from ...models.reservation_conflict import ReservationConflict
from ...models.reservation_create import ReservationCreate
from ...models.reservation_ref_taken import ReservationRefTaken
from ...models.reservation_response import ReservationResponse
from ...types import Response


def _get_kwargs(
    resource_id: int,
    *,
    body: ReservationCreate,
    idempotency_key: str,
) -> dict[str, Any]:
    headers: dict[str, Any] = {}
    headers["Idempotency-Key"] = idempotency_key

    _kwargs: dict[str, Any] = {
        "method": "post",
        "url": "/api/v1/resources/{resource_id}/reservations".format(
            resource_id=quote(str(resource_id), safe=""),
        ),
    }

    _kwargs["json"] = body.to_dict()

    headers["Content-Type"] = "application/json"

    _kwargs["headers"] = headers
    return _kwargs


def _parse_response(
    *, client: AuthenticatedClient | Client, response: httpx.Response
) -> (
    CapacityExceeded | ReservationConflict | ReservationRefTaken | ErrorResponse | ReservationResponse | None
):
    if response.status_code == 200:
        response_200 = ReservationResponse.from_dict(response.json())

        return response_200

    if response.status_code == 201:
        response_201 = ReservationResponse.from_dict(response.json())

        return response_201

    if response.status_code == 401:
        response_401 = ErrorResponse.from_dict(response.json())

        return response_401

    if response.status_code == 403:
        response_403 = ErrorResponse.from_dict(response.json())

        return response_403

    if response.status_code == 404:
        response_404 = ErrorResponse.from_dict(response.json())

        return response_404

    if response.status_code == 409:

        def _parse_response_409(data: object) -> CapacityExceeded | ReservationConflict | ReservationRefTaken:
            try:
                if not isinstance(data, dict):
                    raise TypeError()
                response_409_type_0 = ReservationRefTaken.from_dict(data)

                return response_409_type_0
            except (TypeError, ValueError, AttributeError, KeyError):
                pass
            try:
                if not isinstance(data, dict):
                    raise TypeError()
                response_409_type_1 = CapacityExceeded.from_dict(data)

                return response_409_type_1
            except (TypeError, ValueError, AttributeError, KeyError):
                pass
            if not isinstance(data, dict):
                raise TypeError()
            response_409_type_2 = ReservationConflict.from_dict(data)

            return response_409_type_2

        response_409 = _parse_response_409(response.json())

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
) -> Response[
    CapacityExceeded | ReservationConflict | ReservationRefTaken | ErrorResponse | ReservationResponse
]:
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
    body: ReservationCreate,
    idempotency_key: str,
) -> Response[
    CapacityExceeded | ReservationConflict | ReservationRefTaken | ErrorResponse | ReservationResponse
]:
    """Hold a resource for one dated window

     Requires `ORG_ADMIN` or `UNIT_ADMIN`. The route an outside system uses to take a room. What it
    refuses is exactly what GET availability calls busy, through the same queries and the same
    expansion, so a caller cannot read an hour as free and then be refused it.

    The rule runs both ways. A class cannot be put on top of a hold either, so POST /schedule/slots,
    PATCH /schedule/slots/{slot_id} and a CSV upload are each refused where a booking already stands. A
    hold taken here holds against the timetable and not only against other holds.

    Windows are half open, so an interval ending at ten and one starting at ten do not clash. A window
    may end earlier than it starts, and that is how it says it runs past midnight: 22:00 to 06:00 is a
    night shift of eight hours, and date is the day it opens on. Equal times are refused, because 09:00
    to 09:00 is either nothing at all or a full day and there is no way to tell which was meant.

    A weekly slot reads its two times by the same rule, so an overnight booking is checked against night
    shifts on the timetable as well as against day ones.

    An `external_ref` already on one of the caller's reservations, cancelled or not, is a 409 with
    `RESERVATION_EXTERNAL_REF_TAKEN` and the id of that reservation in `detail.reservation_id`. The
    reference is checked after the Idempotency-Key, so a retry under the same key and the same body is
    still a `200` with the original hold, and before the window, so the same booking sent again under a
    new key is told it already exists rather than that the window is taken. Two requests racing for one
    reference get one booking and the same 409 for the loser. A cancelled reservation keeps its
    reference: clear or change it with PATCH before booking under it again.

    The resource's mode decides what is in the way. EXCLUSIVE is all of the above. POOLED refuses a
    window the timetable holds, because a class takes the whole pool, and otherwise takes `quantity`
    units when the bookings already there leave that many free at every moment of the window; otherwise
    409 `RESOURCE_CAPACITY_EXCEEDED`. SHARED refuses nothing. A quantity above 1 on a resource that is
    not POOLED is a 422.

    Args:
        resource_id (int):
        idempotency_key (str):
        body (ReservationCreate):

    Raises:
        errors.UnexpectedStatus: If the server returns an undocumented status code and Client.raise_on_unexpected_status is True.
        httpx.TimeoutException: If the request takes longer than Client.timeout.

    Returns:
        Response[CapacityExceeded | ReservationConflict | ReservationRefTaken | ErrorResponse | ReservationResponse]
    """

    kwargs = _get_kwargs(
        resource_id=resource_id,
        body=body,
        idempotency_key=idempotency_key,
    )

    response = client.get_httpx_client().request(
        **kwargs,
    )

    return _build_response(client=client, response=response)


def sync(
    resource_id: int,
    *,
    client: AuthenticatedClient | Client,
    body: ReservationCreate,
    idempotency_key: str,
) -> (
    CapacityExceeded | ReservationConflict | ReservationRefTaken | ErrorResponse | ReservationResponse | None
):
    """Hold a resource for one dated window

     Requires `ORG_ADMIN` or `UNIT_ADMIN`. The route an outside system uses to take a room. What it
    refuses is exactly what GET availability calls busy, through the same queries and the same
    expansion, so a caller cannot read an hour as free and then be refused it.

    The rule runs both ways. A class cannot be put on top of a hold either, so POST /schedule/slots,
    PATCH /schedule/slots/{slot_id} and a CSV upload are each refused where a booking already stands. A
    hold taken here holds against the timetable and not only against other holds.

    Windows are half open, so an interval ending at ten and one starting at ten do not clash. A window
    may end earlier than it starts, and that is how it says it runs past midnight: 22:00 to 06:00 is a
    night shift of eight hours, and date is the day it opens on. Equal times are refused, because 09:00
    to 09:00 is either nothing at all or a full day and there is no way to tell which was meant.

    A weekly slot reads its two times by the same rule, so an overnight booking is checked against night
    shifts on the timetable as well as against day ones.

    An `external_ref` already on one of the caller's reservations, cancelled or not, is a 409 with
    `RESERVATION_EXTERNAL_REF_TAKEN` and the id of that reservation in `detail.reservation_id`. The
    reference is checked after the Idempotency-Key, so a retry under the same key and the same body is
    still a `200` with the original hold, and before the window, so the same booking sent again under a
    new key is told it already exists rather than that the window is taken. Two requests racing for one
    reference get one booking and the same 409 for the loser. A cancelled reservation keeps its
    reference: clear or change it with PATCH before booking under it again.

    The resource's mode decides what is in the way. EXCLUSIVE is all of the above. POOLED refuses a
    window the timetable holds, because a class takes the whole pool, and otherwise takes `quantity`
    units when the bookings already there leave that many free at every moment of the window; otherwise
    409 `RESOURCE_CAPACITY_EXCEEDED`. SHARED refuses nothing. A quantity above 1 on a resource that is
    not POOLED is a 422.

    Args:
        resource_id (int):
        idempotency_key (str):
        body (ReservationCreate):

    Raises:
        errors.UnexpectedStatus: If the server returns an undocumented status code and Client.raise_on_unexpected_status is True.
        httpx.TimeoutException: If the request takes longer than Client.timeout.

    Returns:
        CapacityExceeded | ReservationConflict | ReservationRefTaken | ErrorResponse | ReservationResponse
    """

    return sync_detailed(
        resource_id=resource_id,
        client=client,
        body=body,
        idempotency_key=idempotency_key,
    ).parsed


async def asyncio_detailed(
    resource_id: int,
    *,
    client: AuthenticatedClient | Client,
    body: ReservationCreate,
    idempotency_key: str,
) -> Response[
    CapacityExceeded | ReservationConflict | ReservationRefTaken | ErrorResponse | ReservationResponse
]:
    """Hold a resource for one dated window

     Requires `ORG_ADMIN` or `UNIT_ADMIN`. The route an outside system uses to take a room. What it
    refuses is exactly what GET availability calls busy, through the same queries and the same
    expansion, so a caller cannot read an hour as free and then be refused it.

    The rule runs both ways. A class cannot be put on top of a hold either, so POST /schedule/slots,
    PATCH /schedule/slots/{slot_id} and a CSV upload are each refused where a booking already stands. A
    hold taken here holds against the timetable and not only against other holds.

    Windows are half open, so an interval ending at ten and one starting at ten do not clash. A window
    may end earlier than it starts, and that is how it says it runs past midnight: 22:00 to 06:00 is a
    night shift of eight hours, and date is the day it opens on. Equal times are refused, because 09:00
    to 09:00 is either nothing at all or a full day and there is no way to tell which was meant.

    A weekly slot reads its two times by the same rule, so an overnight booking is checked against night
    shifts on the timetable as well as against day ones.

    An `external_ref` already on one of the caller's reservations, cancelled or not, is a 409 with
    `RESERVATION_EXTERNAL_REF_TAKEN` and the id of that reservation in `detail.reservation_id`. The
    reference is checked after the Idempotency-Key, so a retry under the same key and the same body is
    still a `200` with the original hold, and before the window, so the same booking sent again under a
    new key is told it already exists rather than that the window is taken. Two requests racing for one
    reference get one booking and the same 409 for the loser. A cancelled reservation keeps its
    reference: clear or change it with PATCH before booking under it again.

    The resource's mode decides what is in the way. EXCLUSIVE is all of the above. POOLED refuses a
    window the timetable holds, because a class takes the whole pool, and otherwise takes `quantity`
    units when the bookings already there leave that many free at every moment of the window; otherwise
    409 `RESOURCE_CAPACITY_EXCEEDED`. SHARED refuses nothing. A quantity above 1 on a resource that is
    not POOLED is a 422.

    Args:
        resource_id (int):
        idempotency_key (str):
        body (ReservationCreate):

    Raises:
        errors.UnexpectedStatus: If the server returns an undocumented status code and Client.raise_on_unexpected_status is True.
        httpx.TimeoutException: If the request takes longer than Client.timeout.

    Returns:
        Response[CapacityExceeded | ReservationConflict | ReservationRefTaken | ErrorResponse | ReservationResponse]
    """

    kwargs = _get_kwargs(
        resource_id=resource_id,
        body=body,
        idempotency_key=idempotency_key,
    )

    response = await client.get_async_httpx_client().request(**kwargs)

    return _build_response(client=client, response=response)


async def asyncio(
    resource_id: int,
    *,
    client: AuthenticatedClient | Client,
    body: ReservationCreate,
    idempotency_key: str,
) -> (
    CapacityExceeded | ReservationConflict | ReservationRefTaken | ErrorResponse | ReservationResponse | None
):
    """Hold a resource for one dated window

     Requires `ORG_ADMIN` or `UNIT_ADMIN`. The route an outside system uses to take a room. What it
    refuses is exactly what GET availability calls busy, through the same queries and the same
    expansion, so a caller cannot read an hour as free and then be refused it.

    The rule runs both ways. A class cannot be put on top of a hold either, so POST /schedule/slots,
    PATCH /schedule/slots/{slot_id} and a CSV upload are each refused where a booking already stands. A
    hold taken here holds against the timetable and not only against other holds.

    Windows are half open, so an interval ending at ten and one starting at ten do not clash. A window
    may end earlier than it starts, and that is how it says it runs past midnight: 22:00 to 06:00 is a
    night shift of eight hours, and date is the day it opens on. Equal times are refused, because 09:00
    to 09:00 is either nothing at all or a full day and there is no way to tell which was meant.

    A weekly slot reads its two times by the same rule, so an overnight booking is checked against night
    shifts on the timetable as well as against day ones.

    An `external_ref` already on one of the caller's reservations, cancelled or not, is a 409 with
    `RESERVATION_EXTERNAL_REF_TAKEN` and the id of that reservation in `detail.reservation_id`. The
    reference is checked after the Idempotency-Key, so a retry under the same key and the same body is
    still a `200` with the original hold, and before the window, so the same booking sent again under a
    new key is told it already exists rather than that the window is taken. Two requests racing for one
    reference get one booking and the same 409 for the loser. A cancelled reservation keeps its
    reference: clear or change it with PATCH before booking under it again.

    The resource's mode decides what is in the way. EXCLUSIVE is all of the above. POOLED refuses a
    window the timetable holds, because a class takes the whole pool, and otherwise takes `quantity`
    units when the bookings already there leave that many free at every moment of the window; otherwise
    409 `RESOURCE_CAPACITY_EXCEEDED`. SHARED refuses nothing. A quantity above 1 on a resource that is
    not POOLED is a 422.

    Args:
        resource_id (int):
        idempotency_key (str):
        body (ReservationCreate):

    Raises:
        errors.UnexpectedStatus: If the server returns an undocumented status code and Client.raise_on_unexpected_status is True.
        httpx.TimeoutException: If the request takes longer than Client.timeout.

    Returns:
        CapacityExceeded | ReservationConflict | ReservationRefTaken | ErrorResponse | ReservationResponse
    """

    return (
        await asyncio_detailed(
            resource_id=resource_id,
            client=client,
            body=body,
            idempotency_key=idempotency_key,
        )
    ).parsed
