from http import HTTPStatus
from typing import Any

import httpx

from ... import errors
from ...client import AuthenticatedClient, Client
from ...models.attendance_mark_request import AttendanceMarkRequest
from ...models.attendance_mark_response_200 import AttendanceMarkResponse200
from ...models.error_response import ErrorResponse
from ...types import Response


def _get_kwargs(
    *,
    body: AttendanceMarkRequest,
) -> dict[str, Any]:
    headers: dict[str, Any] = {}

    _kwargs: dict[str, Any] = {
        "method": "post",
        "url": "/api/v1/attendance/mark",
    }

    _kwargs["json"] = body.to_dict()

    headers["Content-Type"] = "application/json"

    _kwargs["headers"] = headers
    return _kwargs


def _parse_response(
    *, client: AuthenticatedClient | Client, response: httpx.Response
) -> AttendanceMarkResponse200 | ErrorResponse | None:
    if response.status_code == 200:
        response_200 = AttendanceMarkResponse200.from_dict(response.json())

        return response_200

    if response.status_code == 400:
        response_400 = ErrorResponse.from_dict(response.json())

        return response_400

    if response.status_code == 403:
        response_403 = ErrorResponse.from_dict(response.json())

        return response_403

    if response.status_code == 404:
        response_404 = ErrorResponse.from_dict(response.json())

        return response_404

    if client.raise_on_unexpected_status:
        raise errors.UnexpectedStatus(response.status_code, response.content)
    else:
        return None


def _build_response(
    *, client: AuthenticatedClient | Client, response: httpx.Response
) -> Response[AttendanceMarkResponse200 | ErrorResponse]:
    return Response(
        status_code=HTTPStatus(response.status_code),
        content=response.content,
        headers=response.headers,
        parsed=_parse_response(client=client, response=response),
    )


def sync_detailed(
    *,
    client: AuthenticatedClient | Client,
    body: AttendanceMarkRequest,
) -> Response[AttendanceMarkResponse200 | ErrorResponse]:
    """Mark single member attendance

     Members may only mark themselves. Anyone else must be the ledger's assigned or substitute lead, or
    an admin, and a UNIT_ADMIN only within their own unit. Same rule as `/attendance/batch`. A ledger
    that carries `latitude_target` and `longitude_target` is geo-fenced: a member must send `user_lat`
    and `user_lon`, and the backend checks Haversine surface distance against `precision_radius_meters`.
    `user_alt` is optional and only adds a floor check when the ledger also carries an
    `altitude_target`. Omitting the coordinates on a fenced session returns 400; there is no client-side
    way to skip the fence. When the member sends `user_accuracy`, a fix coarser than
    `GEOFENCE_ACCURACY_FACTOR` times the radius also returns 400. Marking a member again replaces their
    status rather than adding a second row.

    Args:
        body (AttendanceMarkRequest):

    Raises:
        errors.UnexpectedStatus: If the server returns an undocumented status code and Client.raise_on_unexpected_status is True.
        httpx.TimeoutException: If the request takes longer than Client.timeout.

    Returns:
        Response[AttendanceMarkResponse200 | ErrorResponse]
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
    body: AttendanceMarkRequest,
) -> AttendanceMarkResponse200 | ErrorResponse | None:
    """Mark single member attendance

     Members may only mark themselves. Anyone else must be the ledger's assigned or substitute lead, or
    an admin, and a UNIT_ADMIN only within their own unit. Same rule as `/attendance/batch`. A ledger
    that carries `latitude_target` and `longitude_target` is geo-fenced: a member must send `user_lat`
    and `user_lon`, and the backend checks Haversine surface distance against `precision_radius_meters`.
    `user_alt` is optional and only adds a floor check when the ledger also carries an
    `altitude_target`. Omitting the coordinates on a fenced session returns 400; there is no client-side
    way to skip the fence. When the member sends `user_accuracy`, a fix coarser than
    `GEOFENCE_ACCURACY_FACTOR` times the radius also returns 400. Marking a member again replaces their
    status rather than adding a second row.

    Args:
        body (AttendanceMarkRequest):

    Raises:
        errors.UnexpectedStatus: If the server returns an undocumented status code and Client.raise_on_unexpected_status is True.
        httpx.TimeoutException: If the request takes longer than Client.timeout.

    Returns:
        AttendanceMarkResponse200 | ErrorResponse
    """

    return sync_detailed(
        client=client,
        body=body,
    ).parsed


async def asyncio_detailed(
    *,
    client: AuthenticatedClient | Client,
    body: AttendanceMarkRequest,
) -> Response[AttendanceMarkResponse200 | ErrorResponse]:
    """Mark single member attendance

     Members may only mark themselves. Anyone else must be the ledger's assigned or substitute lead, or
    an admin, and a UNIT_ADMIN only within their own unit. Same rule as `/attendance/batch`. A ledger
    that carries `latitude_target` and `longitude_target` is geo-fenced: a member must send `user_lat`
    and `user_lon`, and the backend checks Haversine surface distance against `precision_radius_meters`.
    `user_alt` is optional and only adds a floor check when the ledger also carries an
    `altitude_target`. Omitting the coordinates on a fenced session returns 400; there is no client-side
    way to skip the fence. When the member sends `user_accuracy`, a fix coarser than
    `GEOFENCE_ACCURACY_FACTOR` times the radius also returns 400. Marking a member again replaces their
    status rather than adding a second row.

    Args:
        body (AttendanceMarkRequest):

    Raises:
        errors.UnexpectedStatus: If the server returns an undocumented status code and Client.raise_on_unexpected_status is True.
        httpx.TimeoutException: If the request takes longer than Client.timeout.

    Returns:
        Response[AttendanceMarkResponse200 | ErrorResponse]
    """

    kwargs = _get_kwargs(
        body=body,
    )

    response = await client.get_async_httpx_client().request(**kwargs)

    return _build_response(client=client, response=response)


async def asyncio(
    *,
    client: AuthenticatedClient | Client,
    body: AttendanceMarkRequest,
) -> AttendanceMarkResponse200 | ErrorResponse | None:
    """Mark single member attendance

     Members may only mark themselves. Anyone else must be the ledger's assigned or substitute lead, or
    an admin, and a UNIT_ADMIN only within their own unit. Same rule as `/attendance/batch`. A ledger
    that carries `latitude_target` and `longitude_target` is geo-fenced: a member must send `user_lat`
    and `user_lon`, and the backend checks Haversine surface distance against `precision_radius_meters`.
    `user_alt` is optional and only adds a floor check when the ledger also carries an
    `altitude_target`. Omitting the coordinates on a fenced session returns 400; there is no client-side
    way to skip the fence. When the member sends `user_accuracy`, a fix coarser than
    `GEOFENCE_ACCURACY_FACTOR` times the radius also returns 400. Marking a member again replaces their
    status rather than adding a second row.

    Args:
        body (AttendanceMarkRequest):

    Raises:
        errors.UnexpectedStatus: If the server returns an undocumented status code and Client.raise_on_unexpected_status is True.
        httpx.TimeoutException: If the request takes longer than Client.timeout.

    Returns:
        AttendanceMarkResponse200 | ErrorResponse
    """

    return (
        await asyncio_detailed(
            client=client,
            body=body,
        )
    ).parsed
