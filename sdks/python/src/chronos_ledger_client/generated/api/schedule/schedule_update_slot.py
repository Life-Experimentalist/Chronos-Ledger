from http import HTTPStatus
from typing import Any
from urllib.parse import quote

import httpx

from ... import errors
from ...client import AuthenticatedClient, Client
from ...models.error_response import ErrorResponse
from ...models.master_slot_update import MasterSlotUpdate
from ...models.reservation_conflict import ReservationConflict
from ...models.slot_update_result import SlotUpdateResult
from ...types import Response


def _get_kwargs(
    slot_id: int,
    *,
    body: MasterSlotUpdate,
) -> dict[str, Any]:
    headers: dict[str, Any] = {}

    _kwargs: dict[str, Any] = {
        "method": "patch",
        "url": "/api/v1/schedule/slots/{slot_id}".format(
            slot_id=quote(str(slot_id), safe=""),
        ),
    }

    _kwargs["json"] = body.to_dict()

    headers["Content-Type"] = "application/json"

    _kwargs["headers"] = headers
    return _kwargs


def _parse_response(
    *, client: AuthenticatedClient | Client, response: httpx.Response
) -> ErrorResponse | ReservationConflict | SlotUpdateResult | None:
    if response.status_code == 200:
        response_200 = SlotUpdateResult.from_dict(response.json())

        return response_200

    if response.status_code == 403:
        response_403 = ErrorResponse.from_dict(response.json())

        return response_403

    if response.status_code == 404:
        response_404 = ErrorResponse.from_dict(response.json())

        return response_404

    if response.status_code == 409:

        def _parse_response_409(data: object) -> ErrorResponse | ReservationConflict:
            try:
                if not isinstance(data, dict):
                    raise TypeError()
                response_409_type_0 = ErrorResponse.from_dict(data)

                return response_409_type_0
            except (TypeError, ValueError, AttributeError, KeyError):
                pass
            if not isinstance(data, dict):
                raise TypeError()
            response_409_type_1 = ReservationConflict.from_dict(data)

            return response_409_type_1

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
) -> Response[ErrorResponse | ReservationConflict | SlotUpdateResult]:
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
    body: MasterSlotUpdate,
) -> Response[ErrorResponse | ReservationConflict | SlotUpdateResult]:
    """Change a master slot, and the days it has already produced

     Admin only. A new window, lead or room is copied onto the days that are still plans, while days
    carrying attendance or a note are counted and left alone. Only days after today are moved, so a
    class shifted to 10:00 runs at 10:00 from tomorrow and the days it already ran at 09:00 still say
    09:00.

    Moving the slot to another weekday is the one change that cannot be copied across, because the days
    already generated sit on the old weekday. Those are withdrawn for the generator to lay down again,
    and the request is refused with 409 if any of them has been marked.

    Also refused with 409 where the room it would move to is already taken for part of the window it
    would move to, by a booking or by another class. The slot's own window is not counted against it, so
    widening one is not refused by the window it replaces. A refusal changes nothing: the room is
    resolved and the clashes are checked before any day is withdrawn or any field is written.

    A change that leaves the room, weekday and window alone is not checked, so a new lead can be set on
    a slot a hold is already sitting on. Such a hold predates this rule or was written straight into the
    database, and refusing would leave the lead unfixable short of cancelling somebody else's booking.

    A day already generated on that room in part of the window refuses the change as well, with no cycle
    gate on either side, because such a day still puts somebody at a door whatever its cycle now says.
    The check is made before anything is written and again if the database refuses the write anyway: two
    admins moving two classes onto one room at the same moment both pass the first ask, and the loser is
    told what beat it rather than handed a 500.

    Args:
        slot_id (int):
        body (MasterSlotUpdate): Every field is optional and only the fields present are changed.
            Only primary_lead_id may be null, which takes the lead off the slot; a null for any other
            field is a 422. activity_id is absent on purpose: every day the slot has produced carries
            its own copy of the activity, so pointing the slot at another one is a delete and a
            create, not an edit.

    Raises:
        errors.UnexpectedStatus: If the server returns an undocumented status code and Client.raise_on_unexpected_status is True.
        httpx.TimeoutException: If the request takes longer than Client.timeout.

    Returns:
        Response[ErrorResponse | ErrorResponse | ReservationConflict | SlotUpdateResult]
    """

    kwargs = _get_kwargs(
        slot_id=slot_id,
        body=body,
    )

    response = client.get_httpx_client().request(
        **kwargs,
    )

    return _build_response(client=client, response=response)


def sync(
    slot_id: int,
    *,
    client: AuthenticatedClient | Client,
    body: MasterSlotUpdate,
) -> ErrorResponse | ReservationConflict | SlotUpdateResult | None:
    """Change a master slot, and the days it has already produced

     Admin only. A new window, lead or room is copied onto the days that are still plans, while days
    carrying attendance or a note are counted and left alone. Only days after today are moved, so a
    class shifted to 10:00 runs at 10:00 from tomorrow and the days it already ran at 09:00 still say
    09:00.

    Moving the slot to another weekday is the one change that cannot be copied across, because the days
    already generated sit on the old weekday. Those are withdrawn for the generator to lay down again,
    and the request is refused with 409 if any of them has been marked.

    Also refused with 409 where the room it would move to is already taken for part of the window it
    would move to, by a booking or by another class. The slot's own window is not counted against it, so
    widening one is not refused by the window it replaces. A refusal changes nothing: the room is
    resolved and the clashes are checked before any day is withdrawn or any field is written.

    A change that leaves the room, weekday and window alone is not checked, so a new lead can be set on
    a slot a hold is already sitting on. Such a hold predates this rule or was written straight into the
    database, and refusing would leave the lead unfixable short of cancelling somebody else's booking.

    A day already generated on that room in part of the window refuses the change as well, with no cycle
    gate on either side, because such a day still puts somebody at a door whatever its cycle now says.
    The check is made before anything is written and again if the database refuses the write anyway: two
    admins moving two classes onto one room at the same moment both pass the first ask, and the loser is
    told what beat it rather than handed a 500.

    Args:
        slot_id (int):
        body (MasterSlotUpdate): Every field is optional and only the fields present are changed.
            Only primary_lead_id may be null, which takes the lead off the slot; a null for any other
            field is a 422. activity_id is absent on purpose: every day the slot has produced carries
            its own copy of the activity, so pointing the slot at another one is a delete and a
            create, not an edit.

    Raises:
        errors.UnexpectedStatus: If the server returns an undocumented status code and Client.raise_on_unexpected_status is True.
        httpx.TimeoutException: If the request takes longer than Client.timeout.

    Returns:
        ErrorResponse | ErrorResponse | ReservationConflict | SlotUpdateResult
    """

    return sync_detailed(
        slot_id=slot_id,
        client=client,
        body=body,
    ).parsed


async def asyncio_detailed(
    slot_id: int,
    *,
    client: AuthenticatedClient | Client,
    body: MasterSlotUpdate,
) -> Response[ErrorResponse | ReservationConflict | SlotUpdateResult]:
    """Change a master slot, and the days it has already produced

     Admin only. A new window, lead or room is copied onto the days that are still plans, while days
    carrying attendance or a note are counted and left alone. Only days after today are moved, so a
    class shifted to 10:00 runs at 10:00 from tomorrow and the days it already ran at 09:00 still say
    09:00.

    Moving the slot to another weekday is the one change that cannot be copied across, because the days
    already generated sit on the old weekday. Those are withdrawn for the generator to lay down again,
    and the request is refused with 409 if any of them has been marked.

    Also refused with 409 where the room it would move to is already taken for part of the window it
    would move to, by a booking or by another class. The slot's own window is not counted against it, so
    widening one is not refused by the window it replaces. A refusal changes nothing: the room is
    resolved and the clashes are checked before any day is withdrawn or any field is written.

    A change that leaves the room, weekday and window alone is not checked, so a new lead can be set on
    a slot a hold is already sitting on. Such a hold predates this rule or was written straight into the
    database, and refusing would leave the lead unfixable short of cancelling somebody else's booking.

    A day already generated on that room in part of the window refuses the change as well, with no cycle
    gate on either side, because such a day still puts somebody at a door whatever its cycle now says.
    The check is made before anything is written and again if the database refuses the write anyway: two
    admins moving two classes onto one room at the same moment both pass the first ask, and the loser is
    told what beat it rather than handed a 500.

    Args:
        slot_id (int):
        body (MasterSlotUpdate): Every field is optional and only the fields present are changed.
            Only primary_lead_id may be null, which takes the lead off the slot; a null for any other
            field is a 422. activity_id is absent on purpose: every day the slot has produced carries
            its own copy of the activity, so pointing the slot at another one is a delete and a
            create, not an edit.

    Raises:
        errors.UnexpectedStatus: If the server returns an undocumented status code and Client.raise_on_unexpected_status is True.
        httpx.TimeoutException: If the request takes longer than Client.timeout.

    Returns:
        Response[ErrorResponse | ErrorResponse | ReservationConflict | SlotUpdateResult]
    """

    kwargs = _get_kwargs(
        slot_id=slot_id,
        body=body,
    )

    response = await client.get_async_httpx_client().request(**kwargs)

    return _build_response(client=client, response=response)


async def asyncio(
    slot_id: int,
    *,
    client: AuthenticatedClient | Client,
    body: MasterSlotUpdate,
) -> ErrorResponse | ReservationConflict | SlotUpdateResult | None:
    """Change a master slot, and the days it has already produced

     Admin only. A new window, lead or room is copied onto the days that are still plans, while days
    carrying attendance or a note are counted and left alone. Only days after today are moved, so a
    class shifted to 10:00 runs at 10:00 from tomorrow and the days it already ran at 09:00 still say
    09:00.

    Moving the slot to another weekday is the one change that cannot be copied across, because the days
    already generated sit on the old weekday. Those are withdrawn for the generator to lay down again,
    and the request is refused with 409 if any of them has been marked.

    Also refused with 409 where the room it would move to is already taken for part of the window it
    would move to, by a booking or by another class. The slot's own window is not counted against it, so
    widening one is not refused by the window it replaces. A refusal changes nothing: the room is
    resolved and the clashes are checked before any day is withdrawn or any field is written.

    A change that leaves the room, weekday and window alone is not checked, so a new lead can be set on
    a slot a hold is already sitting on. Such a hold predates this rule or was written straight into the
    database, and refusing would leave the lead unfixable short of cancelling somebody else's booking.

    A day already generated on that room in part of the window refuses the change as well, with no cycle
    gate on either side, because such a day still puts somebody at a door whatever its cycle now says.
    The check is made before anything is written and again if the database refuses the write anyway: two
    admins moving two classes onto one room at the same moment both pass the first ask, and the loser is
    told what beat it rather than handed a 500.

    Args:
        slot_id (int):
        body (MasterSlotUpdate): Every field is optional and only the fields present are changed.
            Only primary_lead_id may be null, which takes the lead off the slot; a null for any other
            field is a 422. activity_id is absent on purpose: every day the slot has produced carries
            its own copy of the activity, so pointing the slot at another one is a delete and a
            create, not an edit.

    Raises:
        errors.UnexpectedStatus: If the server returns an undocumented status code and Client.raise_on_unexpected_status is True.
        httpx.TimeoutException: If the request takes longer than Client.timeout.

    Returns:
        ErrorResponse | ErrorResponse | ReservationConflict | SlotUpdateResult
    """

    return (
        await asyncio_detailed(
            slot_id=slot_id,
            client=client,
            body=body,
        )
    ).parsed
