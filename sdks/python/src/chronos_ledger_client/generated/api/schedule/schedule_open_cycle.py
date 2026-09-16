from http import HTTPStatus
from typing import Any
from urllib.parse import quote

import httpx

from ... import errors
from ...client import AuthenticatedClient, Client
from ...models.cycle_activation_conflict import CycleActivationConflict
from ...models.error_response import ErrorResponse
from ...models.schedule_open_cycle_response_200 import ScheduleOpenCycleResponse200
from ...types import Response


def _get_kwargs(
    cycle_id: int,
) -> dict[str, Any]:

    _kwargs: dict[str, Any] = {
        "method": "patch",
        "url": "/api/v1/schedule/cycles/{cycle_id}/open".format(
            cycle_id=quote(str(cycle_id), safe=""),
        ),
    }

    return _kwargs


def _parse_response(
    *, client: AuthenticatedClient | Client, response: httpx.Response
) -> CycleActivationConflict | ErrorResponse | ScheduleOpenCycleResponse200 | None:
    if response.status_code == 200:
        response_200 = ScheduleOpenCycleResponse200.from_dict(response.json())

        return response_200

    if response.status_code == 404:
        response_404 = ErrorResponse.from_dict(response.json())

        return response_404

    if response.status_code == 409:
        response_409 = CycleActivationConflict.from_dict(response.json())

        return response_409

    if client.raise_on_unexpected_status:
        raise errors.UnexpectedStatus(response.status_code, response.content)
    else:
        return None


def _build_response(
    *, client: AuthenticatedClient | Client, response: httpx.Response
) -> Response[CycleActivationConflict | ErrorResponse | ScheduleOpenCycleResponse200]:
    return Response(
        status_code=HTTPStatus(response.status_code),
        content=response.content,
        headers=response.headers,
        parsed=_parse_response(client=client, response=response),
    )


def sync_detailed(
    cycle_id: int,
    *,
    client: AuthenticatedClient | Client,
) -> Response[CycleActivationConflict | ErrorResponse | ScheduleOpenCycleResponse200]:
    """Put a drafted planning cycle into service

     Sets `operational_status = true`, and it is the only thing that does. A cycle can be created closed,
    filled in over as long as that takes, and opened once it is ready.

    Not a flag flip. A slot entered into a closed cycle is never checked against the bookings or against
    the rest of the timetable, because a closed cycle's slots occupy nothing, and every one of them
    starts occupying its room the moment the flag goes true. The checks `POST /schedule/slots` would
    have run are run here over every slot in the cycle at once, the cycle's own slots counting against
    each other, and the whole open is refused where any of them lands on a room that is taken. A refused
    open writes nothing.

    Opening a cycle that is already open changes nothing. Requires `SUPER_ADMIN`.

    Args:
        cycle_id (int):

    Raises:
        errors.UnexpectedStatus: If the server returns an undocumented status code and Client.raise_on_unexpected_status is True.
        httpx.TimeoutException: If the request takes longer than Client.timeout.

    Returns:
        Response[CycleActivationConflict | ErrorResponse | ScheduleOpenCycleResponse200]
    """

    kwargs = _get_kwargs(
        cycle_id=cycle_id,
    )

    response = client.get_httpx_client().request(
        **kwargs,
    )

    return _build_response(client=client, response=response)


def sync(
    cycle_id: int,
    *,
    client: AuthenticatedClient | Client,
) -> CycleActivationConflict | ErrorResponse | ScheduleOpenCycleResponse200 | None:
    """Put a drafted planning cycle into service

     Sets `operational_status = true`, and it is the only thing that does. A cycle can be created closed,
    filled in over as long as that takes, and opened once it is ready.

    Not a flag flip. A slot entered into a closed cycle is never checked against the bookings or against
    the rest of the timetable, because a closed cycle's slots occupy nothing, and every one of them
    starts occupying its room the moment the flag goes true. The checks `POST /schedule/slots` would
    have run are run here over every slot in the cycle at once, the cycle's own slots counting against
    each other, and the whole open is refused where any of them lands on a room that is taken. A refused
    open writes nothing.

    Opening a cycle that is already open changes nothing. Requires `SUPER_ADMIN`.

    Args:
        cycle_id (int):

    Raises:
        errors.UnexpectedStatus: If the server returns an undocumented status code and Client.raise_on_unexpected_status is True.
        httpx.TimeoutException: If the request takes longer than Client.timeout.

    Returns:
        CycleActivationConflict | ErrorResponse | ScheduleOpenCycleResponse200
    """

    return sync_detailed(
        cycle_id=cycle_id,
        client=client,
    ).parsed


async def asyncio_detailed(
    cycle_id: int,
    *,
    client: AuthenticatedClient | Client,
) -> Response[CycleActivationConflict | ErrorResponse | ScheduleOpenCycleResponse200]:
    """Put a drafted planning cycle into service

     Sets `operational_status = true`, and it is the only thing that does. A cycle can be created closed,
    filled in over as long as that takes, and opened once it is ready.

    Not a flag flip. A slot entered into a closed cycle is never checked against the bookings or against
    the rest of the timetable, because a closed cycle's slots occupy nothing, and every one of them
    starts occupying its room the moment the flag goes true. The checks `POST /schedule/slots` would
    have run are run here over every slot in the cycle at once, the cycle's own slots counting against
    each other, and the whole open is refused where any of them lands on a room that is taken. A refused
    open writes nothing.

    Opening a cycle that is already open changes nothing. Requires `SUPER_ADMIN`.

    Args:
        cycle_id (int):

    Raises:
        errors.UnexpectedStatus: If the server returns an undocumented status code and Client.raise_on_unexpected_status is True.
        httpx.TimeoutException: If the request takes longer than Client.timeout.

    Returns:
        Response[CycleActivationConflict | ErrorResponse | ScheduleOpenCycleResponse200]
    """

    kwargs = _get_kwargs(
        cycle_id=cycle_id,
    )

    response = await client.get_async_httpx_client().request(**kwargs)

    return _build_response(client=client, response=response)


async def asyncio(
    cycle_id: int,
    *,
    client: AuthenticatedClient | Client,
) -> CycleActivationConflict | ErrorResponse | ScheduleOpenCycleResponse200 | None:
    """Put a drafted planning cycle into service

     Sets `operational_status = true`, and it is the only thing that does. A cycle can be created closed,
    filled in over as long as that takes, and opened once it is ready.

    Not a flag flip. A slot entered into a closed cycle is never checked against the bookings or against
    the rest of the timetable, because a closed cycle's slots occupy nothing, and every one of them
    starts occupying its room the moment the flag goes true. The checks `POST /schedule/slots` would
    have run are run here over every slot in the cycle at once, the cycle's own slots counting against
    each other, and the whole open is refused where any of them lands on a room that is taken. A refused
    open writes nothing.

    Opening a cycle that is already open changes nothing. Requires `SUPER_ADMIN`.

    Args:
        cycle_id (int):

    Raises:
        errors.UnexpectedStatus: If the server returns an undocumented status code and Client.raise_on_unexpected_status is True.
        httpx.TimeoutException: If the request takes longer than Client.timeout.

    Returns:
        CycleActivationConflict | ErrorResponse | ScheduleOpenCycleResponse200
    """

    return (
        await asyncio_detailed(
            cycle_id=cycle_id,
            client=client,
        )
    ).parsed
