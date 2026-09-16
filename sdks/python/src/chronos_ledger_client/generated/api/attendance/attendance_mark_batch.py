from http import HTTPStatus
from typing import Any

import httpx

from ... import errors
from ...client import AuthenticatedClient, Client
from ...models.attendance_batch_request import AttendanceBatchRequest
from ...models.attendance_mark_batch_response_200 import AttendanceMarkBatchResponse200
from ...models.error_response import ErrorResponse
from ...types import Response


def _get_kwargs(
    *,
    body: AttendanceBatchRequest,
) -> dict[str, Any]:
    headers: dict[str, Any] = {}

    _kwargs: dict[str, Any] = {
        "method": "post",
        "url": "/api/v1/attendance/batch",
    }

    _kwargs["json"] = body.to_dict()

    headers["Content-Type"] = "application/json"

    _kwargs["headers"] = headers
    return _kwargs


def _parse_response(
    *, client: AuthenticatedClient | Client, response: httpx.Response
) -> AttendanceMarkBatchResponse200 | ErrorResponse | None:
    if response.status_code == 200:
        response_200 = AttendanceMarkBatchResponse200.from_dict(response.json())

        return response_200

    if response.status_code == 403:
        response_403 = ErrorResponse.from_dict(response.json())

        return response_403

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
) -> Response[AttendanceMarkBatchResponse200 | ErrorResponse]:
    return Response(
        status_code=HTTPStatus(response.status_code),
        content=response.content,
        headers=response.headers,
        parsed=_parse_response(client=client, response=response),
    )


def sync_detailed(
    *,
    client: AuthenticatedClient | Client,
    body: AttendanceBatchRequest,
) -> Response[AttendanceMarkBatchResponse200 | ErrorResponse]:
    """Batch mark attendance for multiple members

     For whoever runs the session, on the same rule as `/attendance/mark`: the ledger's assigned or
    substitute lead, or an admin, and a UNIT_ADMIN only within their own unit. Every record must repeat
    the batch's `ledger_instance_id` and no member may appear twice, or the batch is refused with 422. A
    member id matching nobody is refused with 404. A refused batch writes nothing; an accepted one is
    written in one transaction.

    Args:
        body (AttendanceBatchRequest):

    Raises:
        errors.UnexpectedStatus: If the server returns an undocumented status code and Client.raise_on_unexpected_status is True.
        httpx.TimeoutException: If the request takes longer than Client.timeout.

    Returns:
        Response[AttendanceMarkBatchResponse200 | ErrorResponse]
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
    body: AttendanceBatchRequest,
) -> AttendanceMarkBatchResponse200 | ErrorResponse | None:
    """Batch mark attendance for multiple members

     For whoever runs the session, on the same rule as `/attendance/mark`: the ledger's assigned or
    substitute lead, or an admin, and a UNIT_ADMIN only within their own unit. Every record must repeat
    the batch's `ledger_instance_id` and no member may appear twice, or the batch is refused with 422. A
    member id matching nobody is refused with 404. A refused batch writes nothing; an accepted one is
    written in one transaction.

    Args:
        body (AttendanceBatchRequest):

    Raises:
        errors.UnexpectedStatus: If the server returns an undocumented status code and Client.raise_on_unexpected_status is True.
        httpx.TimeoutException: If the request takes longer than Client.timeout.

    Returns:
        AttendanceMarkBatchResponse200 | ErrorResponse
    """

    return sync_detailed(
        client=client,
        body=body,
    ).parsed


async def asyncio_detailed(
    *,
    client: AuthenticatedClient | Client,
    body: AttendanceBatchRequest,
) -> Response[AttendanceMarkBatchResponse200 | ErrorResponse]:
    """Batch mark attendance for multiple members

     For whoever runs the session, on the same rule as `/attendance/mark`: the ledger's assigned or
    substitute lead, or an admin, and a UNIT_ADMIN only within their own unit. Every record must repeat
    the batch's `ledger_instance_id` and no member may appear twice, or the batch is refused with 422. A
    member id matching nobody is refused with 404. A refused batch writes nothing; an accepted one is
    written in one transaction.

    Args:
        body (AttendanceBatchRequest):

    Raises:
        errors.UnexpectedStatus: If the server returns an undocumented status code and Client.raise_on_unexpected_status is True.
        httpx.TimeoutException: If the request takes longer than Client.timeout.

    Returns:
        Response[AttendanceMarkBatchResponse200 | ErrorResponse]
    """

    kwargs = _get_kwargs(
        body=body,
    )

    response = await client.get_async_httpx_client().request(**kwargs)

    return _build_response(client=client, response=response)


async def asyncio(
    *,
    client: AuthenticatedClient | Client,
    body: AttendanceBatchRequest,
) -> AttendanceMarkBatchResponse200 | ErrorResponse | None:
    """Batch mark attendance for multiple members

     For whoever runs the session, on the same rule as `/attendance/mark`: the ledger's assigned or
    substitute lead, or an admin, and a UNIT_ADMIN only within their own unit. Every record must repeat
    the batch's `ledger_instance_id` and no member may appear twice, or the batch is refused with 422. A
    member id matching nobody is refused with 404. A refused batch writes nothing; an accepted one is
    written in one transaction.

    Args:
        body (AttendanceBatchRequest):

    Raises:
        errors.UnexpectedStatus: If the server returns an undocumented status code and Client.raise_on_unexpected_status is True.
        httpx.TimeoutException: If the request takes longer than Client.timeout.

    Returns:
        AttendanceMarkBatchResponse200 | ErrorResponse
    """

    return (
        await asyncio_detailed(
            client=client,
            body=body,
        )
    ).parsed
