from http import HTTPStatus
from typing import Any
from urllib.parse import quote

import httpx

from ... import errors
from ...client import AuthenticatedClient, Client
from ...models.error_response import ErrorResponse
from ...models.schedule_delete_enrollment_response_200 import ScheduleDeleteEnrollmentResponse200
from ...types import UNSET, Response, Unset


def _get_kwargs(
    activity_id: int,
    member_id: str,
    *,
    idempotency_key: str | Unset = UNSET,
) -> dict[str, Any]:
    headers: dict[str, Any] = {}
    if not isinstance(idempotency_key, Unset):
        headers["Idempotency-Key"] = idempotency_key

    _kwargs: dict[str, Any] = {
        "method": "delete",
        "url": "/api/v1/schedule/activities/{activity_id}/enrollments/{member_id}".format(
            activity_id=quote(str(activity_id), safe=""),
            member_id=quote(str(member_id), safe=""),
        ),
    }

    _kwargs["headers"] = headers
    return _kwargs


def _parse_response(
    *, client: AuthenticatedClient | Client, response: httpx.Response
) -> ErrorResponse | ScheduleDeleteEnrollmentResponse200 | None:
    if response.status_code == 200:
        response_200 = ScheduleDeleteEnrollmentResponse200.from_dict(response.json())

        return response_200

    if response.status_code == 403:
        response_403 = ErrorResponse.from_dict(response.json())

        return response_403

    if response.status_code == 404:
        response_404 = ErrorResponse.from_dict(response.json())

        return response_404

    if response.status_code == 409:
        response_409 = ErrorResponse.from_dict(response.json())

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
) -> Response[ErrorResponse | ScheduleDeleteEnrollmentResponse200]:
    return Response(
        status_code=HTTPStatus(response.status_code),
        content=response.content,
        headers=response.headers,
        parsed=_parse_response(client=client, response=response),
    )


def sync_detailed(
    activity_id: int,
    member_id: str,
    *,
    client: AuthenticatedClient | Client,
    idempotency_key: str | Unset = UNSET,
) -> Response[ErrorResponse | ScheduleDeleteEnrollmentResponse200]:
    """Remove a member from an activity

     Admin only, inside the admin's unit. Only the enrollment goes. Days belong to slots, so no day is
    removed, and the attendance already recorded for the member stays.

    Args:
        activity_id (int):
        member_id (str):
        idempotency_key (str | Unset):

    Raises:
        errors.UnexpectedStatus: If the server returns an undocumented status code and Client.raise_on_unexpected_status is True.
        httpx.TimeoutException: If the request takes longer than Client.timeout.

    Returns:
        Response[ErrorResponse | ScheduleDeleteEnrollmentResponse200]
    """

    kwargs = _get_kwargs(
        activity_id=activity_id,
        member_id=member_id,
        idempotency_key=idempotency_key,
    )

    response = client.get_httpx_client().request(
        **kwargs,
    )

    return _build_response(client=client, response=response)


def sync(
    activity_id: int,
    member_id: str,
    *,
    client: AuthenticatedClient | Client,
    idempotency_key: str | Unset = UNSET,
) -> ErrorResponse | ScheduleDeleteEnrollmentResponse200 | None:
    """Remove a member from an activity

     Admin only, inside the admin's unit. Only the enrollment goes. Days belong to slots, so no day is
    removed, and the attendance already recorded for the member stays.

    Args:
        activity_id (int):
        member_id (str):
        idempotency_key (str | Unset):

    Raises:
        errors.UnexpectedStatus: If the server returns an undocumented status code and Client.raise_on_unexpected_status is True.
        httpx.TimeoutException: If the request takes longer than Client.timeout.

    Returns:
        ErrorResponse | ScheduleDeleteEnrollmentResponse200
    """

    return sync_detailed(
        activity_id=activity_id,
        member_id=member_id,
        client=client,
        idempotency_key=idempotency_key,
    ).parsed


async def asyncio_detailed(
    activity_id: int,
    member_id: str,
    *,
    client: AuthenticatedClient | Client,
    idempotency_key: str | Unset = UNSET,
) -> Response[ErrorResponse | ScheduleDeleteEnrollmentResponse200]:
    """Remove a member from an activity

     Admin only, inside the admin's unit. Only the enrollment goes. Days belong to slots, so no day is
    removed, and the attendance already recorded for the member stays.

    Args:
        activity_id (int):
        member_id (str):
        idempotency_key (str | Unset):

    Raises:
        errors.UnexpectedStatus: If the server returns an undocumented status code and Client.raise_on_unexpected_status is True.
        httpx.TimeoutException: If the request takes longer than Client.timeout.

    Returns:
        Response[ErrorResponse | ScheduleDeleteEnrollmentResponse200]
    """

    kwargs = _get_kwargs(
        activity_id=activity_id,
        member_id=member_id,
        idempotency_key=idempotency_key,
    )

    response = await client.get_async_httpx_client().request(**kwargs)

    return _build_response(client=client, response=response)


async def asyncio(
    activity_id: int,
    member_id: str,
    *,
    client: AuthenticatedClient | Client,
    idempotency_key: str | Unset = UNSET,
) -> ErrorResponse | ScheduleDeleteEnrollmentResponse200 | None:
    """Remove a member from an activity

     Admin only, inside the admin's unit. Only the enrollment goes. Days belong to slots, so no day is
    removed, and the attendance already recorded for the member stays.

    Args:
        activity_id (int):
        member_id (str):
        idempotency_key (str | Unset):

    Raises:
        errors.UnexpectedStatus: If the server returns an undocumented status code and Client.raise_on_unexpected_status is True.
        httpx.TimeoutException: If the request takes longer than Client.timeout.

    Returns:
        ErrorResponse | ScheduleDeleteEnrollmentResponse200
    """

    return (
        await asyncio_detailed(
            activity_id=activity_id,
            member_id=member_id,
            client=client,
            idempotency_key=idempotency_key,
        )
    ).parsed
