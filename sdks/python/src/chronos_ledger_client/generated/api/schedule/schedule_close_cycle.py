from http import HTTPStatus
from typing import Any
from urllib.parse import quote

import httpx

from ... import errors
from ...client import AuthenticatedClient, Client
from ...models.error_response import ErrorResponse
from ...models.schedule_close_cycle_response_200 import ScheduleCloseCycleResponse200
from ...types import Response


def _get_kwargs(
    cycle_id: int,
) -> dict[str, Any]:

    _kwargs: dict[str, Any] = {
        "method": "patch",
        "url": "/api/v1/schedule/cycles/{cycle_id}/close".format(
            cycle_id=quote(str(cycle_id), safe=""),
        ),
    }

    return _kwargs


def _parse_response(
    *, client: AuthenticatedClient | Client, response: httpx.Response
) -> ErrorResponse | ScheduleCloseCycleResponse200 | None:
    if response.status_code == 200:
        response_200 = ScheduleCloseCycleResponse200.from_dict(response.json())

        return response_200

    if response.status_code == 404:
        response_404 = ErrorResponse.from_dict(response.json())

        return response_404

    if client.raise_on_unexpected_status:
        raise errors.UnexpectedStatus(response.status_code, response.content)
    else:
        return None


def _build_response(
    *, client: AuthenticatedClient | Client, response: httpx.Response
) -> Response[ErrorResponse | ScheduleCloseCycleResponse200]:
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
) -> Response[ErrorResponse | ScheduleCloseCycleResponse200]:
    """Take a planning cycle out of service

     Sets `operational_status = false`, so the nightly generator writes no more days for the cycle's
    slots, and removes the days it has already written from today onward, which are still only plans. A
    day that carries attendance or a note is kept rather than refused over. Days before today are not
    touched.

    Closing a cycle that is already closed runs the same sweep. Requires `SUPER_ADMIN`.

    Args:
        cycle_id (int):

    Raises:
        errors.UnexpectedStatus: If the server returns an undocumented status code and Client.raise_on_unexpected_status is True.
        httpx.TimeoutException: If the request takes longer than Client.timeout.

    Returns:
        Response[ErrorResponse | ScheduleCloseCycleResponse200]
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
) -> ErrorResponse | ScheduleCloseCycleResponse200 | None:
    """Take a planning cycle out of service

     Sets `operational_status = false`, so the nightly generator writes no more days for the cycle's
    slots, and removes the days it has already written from today onward, which are still only plans. A
    day that carries attendance or a note is kept rather than refused over. Days before today are not
    touched.

    Closing a cycle that is already closed runs the same sweep. Requires `SUPER_ADMIN`.

    Args:
        cycle_id (int):

    Raises:
        errors.UnexpectedStatus: If the server returns an undocumented status code and Client.raise_on_unexpected_status is True.
        httpx.TimeoutException: If the request takes longer than Client.timeout.

    Returns:
        ErrorResponse | ScheduleCloseCycleResponse200
    """

    return sync_detailed(
        cycle_id=cycle_id,
        client=client,
    ).parsed


async def asyncio_detailed(
    cycle_id: int,
    *,
    client: AuthenticatedClient | Client,
) -> Response[ErrorResponse | ScheduleCloseCycleResponse200]:
    """Take a planning cycle out of service

     Sets `operational_status = false`, so the nightly generator writes no more days for the cycle's
    slots, and removes the days it has already written from today onward, which are still only plans. A
    day that carries attendance or a note is kept rather than refused over. Days before today are not
    touched.

    Closing a cycle that is already closed runs the same sweep. Requires `SUPER_ADMIN`.

    Args:
        cycle_id (int):

    Raises:
        errors.UnexpectedStatus: If the server returns an undocumented status code and Client.raise_on_unexpected_status is True.
        httpx.TimeoutException: If the request takes longer than Client.timeout.

    Returns:
        Response[ErrorResponse | ScheduleCloseCycleResponse200]
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
) -> ErrorResponse | ScheduleCloseCycleResponse200 | None:
    """Take a planning cycle out of service

     Sets `operational_status = false`, so the nightly generator writes no more days for the cycle's
    slots, and removes the days it has already written from today onward, which are still only plans. A
    day that carries attendance or a note is kept rather than refused over. Days before today are not
    touched.

    Closing a cycle that is already closed runs the same sweep. Requires `SUPER_ADMIN`.

    Args:
        cycle_id (int):

    Raises:
        errors.UnexpectedStatus: If the server returns an undocumented status code and Client.raise_on_unexpected_status is True.
        httpx.TimeoutException: If the request takes longer than Client.timeout.

    Returns:
        ErrorResponse | ScheduleCloseCycleResponse200
    """

    return (
        await asyncio_detailed(
            cycle_id=cycle_id,
            client=client,
        )
    ).parsed
