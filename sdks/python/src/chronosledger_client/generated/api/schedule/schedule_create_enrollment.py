from http import HTTPStatus
from typing import Any
from urllib.parse import quote

import httpx

from ... import errors
from ...client import AuthenticatedClient, Client
from ...models.enrollment_create import EnrollmentCreate
from ...models.enrollment_response import EnrollmentResponse
from ...models.error_response import ErrorResponse
from ...types import UNSET, Response, Unset


def _get_kwargs(
    activity_id: int,
    *,
    body: EnrollmentCreate,
    idempotency_key: str | Unset = UNSET,
) -> dict[str, Any]:
    headers: dict[str, Any] = {}
    if not isinstance(idempotency_key, Unset):
        headers["Idempotency-Key"] = idempotency_key

    _kwargs: dict[str, Any] = {
        "method": "post",
        "url": "/api/v1/schedule/activities/{activity_id}/enrollments".format(
            activity_id=quote(str(activity_id), safe=""),
        ),
    }

    _kwargs["json"] = body.to_dict()

    headers["Content-Type"] = "application/json"

    _kwargs["headers"] = headers
    return _kwargs


def _parse_response(
    *, client: AuthenticatedClient | Client, response: httpx.Response
) -> EnrollmentResponse | ErrorResponse | None:
    if response.status_code == 201:
        response_201 = EnrollmentResponse.from_dict(response.json())

        return response_201

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
) -> Response[EnrollmentResponse | ErrorResponse]:
    return Response(
        status_code=HTTPStatus(response.status_code),
        content=response.content,
        headers=response.headers,
        parsed=_parse_response(client=client, response=response),
    )


def sync_detailed(
    activity_id: int,
    *,
    client: AuthenticatedClient | Client,
    body: EnrollmentCreate,
    idempotency_key: str | Unset = UNSET,
) -> Response[EnrollmentResponse | ErrorResponse]:
    """Enroll a member

     Admin only, inside the admin's unit. The member has to exist and be active, as in a CSV import. Days
    belong to slots rather than members, so no day is written: the member sees the activity's days from
    now on.

    Args:
        activity_id (int):
        idempotency_key (str | Unset):
        body (EnrollmentCreate):

    Raises:
        errors.UnexpectedStatus: If the server returns an undocumented status code and Client.raise_on_unexpected_status is True.
        httpx.TimeoutException: If the request takes longer than Client.timeout.

    Returns:
        Response[EnrollmentResponse | ErrorResponse]
    """

    kwargs = _get_kwargs(
        activity_id=activity_id,
        body=body,
        idempotency_key=idempotency_key,
    )

    response = client.get_httpx_client().request(
        **kwargs,
    )

    return _build_response(client=client, response=response)


def sync(
    activity_id: int,
    *,
    client: AuthenticatedClient | Client,
    body: EnrollmentCreate,
    idempotency_key: str | Unset = UNSET,
) -> EnrollmentResponse | ErrorResponse | None:
    """Enroll a member

     Admin only, inside the admin's unit. The member has to exist and be active, as in a CSV import. Days
    belong to slots rather than members, so no day is written: the member sees the activity's days from
    now on.

    Args:
        activity_id (int):
        idempotency_key (str | Unset):
        body (EnrollmentCreate):

    Raises:
        errors.UnexpectedStatus: If the server returns an undocumented status code and Client.raise_on_unexpected_status is True.
        httpx.TimeoutException: If the request takes longer than Client.timeout.

    Returns:
        EnrollmentResponse | ErrorResponse
    """

    return sync_detailed(
        activity_id=activity_id,
        client=client,
        body=body,
        idempotency_key=idempotency_key,
    ).parsed


async def asyncio_detailed(
    activity_id: int,
    *,
    client: AuthenticatedClient | Client,
    body: EnrollmentCreate,
    idempotency_key: str | Unset = UNSET,
) -> Response[EnrollmentResponse | ErrorResponse]:
    """Enroll a member

     Admin only, inside the admin's unit. The member has to exist and be active, as in a CSV import. Days
    belong to slots rather than members, so no day is written: the member sees the activity's days from
    now on.

    Args:
        activity_id (int):
        idempotency_key (str | Unset):
        body (EnrollmentCreate):

    Raises:
        errors.UnexpectedStatus: If the server returns an undocumented status code and Client.raise_on_unexpected_status is True.
        httpx.TimeoutException: If the request takes longer than Client.timeout.

    Returns:
        Response[EnrollmentResponse | ErrorResponse]
    """

    kwargs = _get_kwargs(
        activity_id=activity_id,
        body=body,
        idempotency_key=idempotency_key,
    )

    response = await client.get_async_httpx_client().request(**kwargs)

    return _build_response(client=client, response=response)


async def asyncio(
    activity_id: int,
    *,
    client: AuthenticatedClient | Client,
    body: EnrollmentCreate,
    idempotency_key: str | Unset = UNSET,
) -> EnrollmentResponse | ErrorResponse | None:
    """Enroll a member

     Admin only, inside the admin's unit. The member has to exist and be active, as in a CSV import. Days
    belong to slots rather than members, so no day is written: the member sees the activity's days from
    now on.

    Args:
        activity_id (int):
        idempotency_key (str | Unset):
        body (EnrollmentCreate):

    Raises:
        errors.UnexpectedStatus: If the server returns an undocumented status code and Client.raise_on_unexpected_status is True.
        httpx.TimeoutException: If the request takes longer than Client.timeout.

    Returns:
        EnrollmentResponse | ErrorResponse
    """

    return (
        await asyncio_detailed(
            activity_id=activity_id,
            client=client,
            body=body,
            idempotency_key=idempotency_key,
        )
    ).parsed
