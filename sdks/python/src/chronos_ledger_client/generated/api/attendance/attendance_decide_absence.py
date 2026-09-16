from http import HTTPStatus
from typing import Any
from urllib.parse import quote

import httpx

from ... import errors
from ...client import AuthenticatedClient, Client
from ...models.attendance_decide_absence_response_200 import (
    AttendanceDecideAbsenceResponse200,
)
from ...models.error_response import ErrorResponse
from ...models.rsvp_decision import RsvpDecision
from ...types import Response


def _get_kwargs(
    log_id: int,
    *,
    body: RsvpDecision,
) -> dict[str, Any]:
    headers: dict[str, Any] = {}

    _kwargs: dict[str, Any] = {
        "method": "patch",
        "url": "/api/v1/attendance/absence/{log_id}/decide".format(
            log_id=quote(str(log_id), safe=""),
        ),
    }

    _kwargs["json"] = body.to_dict()

    headers["Content-Type"] = "application/json"

    _kwargs["headers"] = headers
    return _kwargs


def _parse_response(
    *, client: AuthenticatedClient | Client, response: httpx.Response
) -> AttendanceDecideAbsenceResponse200 | ErrorResponse | None:
    if response.status_code == 200:
        response_200 = AttendanceDecideAbsenceResponse200.from_dict(response.json())

        return response_200

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
) -> Response[AttendanceDecideAbsenceResponse200 | ErrorResponse]:
    return Response(
        status_code=HTTPStatus(response.status_code),
        content=response.content,
        headers=response.headers,
        parsed=_parse_response(client=client, response=response),
    )


def sync_detailed(
    log_id: int,
    *,
    client: AuthenticatedClient | Client,
    body: RsvpDecision,
) -> Response[AttendanceDecideAbsenceResponse200 | ErrorResponse]:
    """Approve or deny an absence request

     The manager the request went to decides it or, once that manager is deactivated, an admin by the
    rules of the pending list. Whoever decides becomes `authorized_by_user_id` and can revisit the
    decision.

    Args:
        log_id (int):
        body (RsvpDecision):

    Raises:
        errors.UnexpectedStatus: If the server returns an undocumented status code and Client.raise_on_unexpected_status is True.
        httpx.TimeoutException: If the request takes longer than Client.timeout.

    Returns:
        Response[AttendanceDecideAbsenceResponse200 | ErrorResponse]
    """

    kwargs = _get_kwargs(
        log_id=log_id,
        body=body,
    )

    response = client.get_httpx_client().request(
        **kwargs,
    )

    return _build_response(client=client, response=response)


def sync(
    log_id: int,
    *,
    client: AuthenticatedClient | Client,
    body: RsvpDecision,
) -> AttendanceDecideAbsenceResponse200 | ErrorResponse | None:
    """Approve or deny an absence request

     The manager the request went to decides it or, once that manager is deactivated, an admin by the
    rules of the pending list. Whoever decides becomes `authorized_by_user_id` and can revisit the
    decision.

    Args:
        log_id (int):
        body (RsvpDecision):

    Raises:
        errors.UnexpectedStatus: If the server returns an undocumented status code and Client.raise_on_unexpected_status is True.
        httpx.TimeoutException: If the request takes longer than Client.timeout.

    Returns:
        AttendanceDecideAbsenceResponse200 | ErrorResponse
    """

    return sync_detailed(
        log_id=log_id,
        client=client,
        body=body,
    ).parsed


async def asyncio_detailed(
    log_id: int,
    *,
    client: AuthenticatedClient | Client,
    body: RsvpDecision,
) -> Response[AttendanceDecideAbsenceResponse200 | ErrorResponse]:
    """Approve or deny an absence request

     The manager the request went to decides it or, once that manager is deactivated, an admin by the
    rules of the pending list. Whoever decides becomes `authorized_by_user_id` and can revisit the
    decision.

    Args:
        log_id (int):
        body (RsvpDecision):

    Raises:
        errors.UnexpectedStatus: If the server returns an undocumented status code and Client.raise_on_unexpected_status is True.
        httpx.TimeoutException: If the request takes longer than Client.timeout.

    Returns:
        Response[AttendanceDecideAbsenceResponse200 | ErrorResponse]
    """

    kwargs = _get_kwargs(
        log_id=log_id,
        body=body,
    )

    response = await client.get_async_httpx_client().request(**kwargs)

    return _build_response(client=client, response=response)


async def asyncio(
    log_id: int,
    *,
    client: AuthenticatedClient | Client,
    body: RsvpDecision,
) -> AttendanceDecideAbsenceResponse200 | ErrorResponse | None:
    """Approve or deny an absence request

     The manager the request went to decides it or, once that manager is deactivated, an admin by the
    rules of the pending list. Whoever decides becomes `authorized_by_user_id` and can revisit the
    decision.

    Args:
        log_id (int):
        body (RsvpDecision):

    Raises:
        errors.UnexpectedStatus: If the server returns an undocumented status code and Client.raise_on_unexpected_status is True.
        httpx.TimeoutException: If the request takes longer than Client.timeout.

    Returns:
        AttendanceDecideAbsenceResponse200 | ErrorResponse
    """

    return (
        await asyncio_detailed(
            log_id=log_id,
            client=client,
            body=body,
        )
    ).parsed
