from http import HTTPStatus
from typing import Any

import httpx

from ... import errors
from ...client import AuthenticatedClient, Client
from ...models.activity_create import ActivityCreate
from ...models.activity_response import ActivityResponse
from ...models.error_response import ErrorResponse
from ...types import UNSET, Response, Unset


def _get_kwargs(
    *,
    body: ActivityCreate,
    idempotency_key: str | Unset = UNSET,
) -> dict[str, Any]:
    headers: dict[str, Any] = {}
    if not isinstance(idempotency_key, Unset):
        headers["Idempotency-Key"] = idempotency_key

    _kwargs: dict[str, Any] = {
        "method": "post",
        "url": "/api/v1/schedule/activities",
    }

    _kwargs["json"] = body.to_dict()

    headers["Content-Type"] = "application/json"

    _kwargs["headers"] = headers
    return _kwargs


def _parse_response(
    *, client: AuthenticatedClient | Client, response: httpx.Response
) -> ActivityResponse | ErrorResponse | None:
    if response.status_code == 201:
        response_201 = ActivityResponse.from_dict(response.json())

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
) -> Response[ActivityResponse | ErrorResponse]:
    return Response(
        status_code=HTTPStatus(response.status_code),
        content=response.content,
        headers=response.headers,
        parsed=_parse_response(client=client, response=response),
    )


def sync_detailed(
    *,
    client: AuthenticatedClient | Client,
    body: ActivityCreate,
    idempotency_key: str | Unset = UNSET,
) -> Response[ActivityResponse | ErrorResponse]:
    """Add an activity

     Admin only. A UNIT_ADMIN may only add activities to their own unit (403 `OUTSIDE_UNIT`). The
    activity starts with no slots and no members. Each slot added to it with POST /schedule/slots fills
    the days ahead at once, through the same generator a CSV import and the nightly job use, so an
    activity built here gets exactly the days the same activity imported from a CSV would.

    Args:
        idempotency_key (str | Unset):
        body (ActivityCreate): An activity, the same one a CSV row names by code, title and unit.
            It starts with no slots and no members; those are added with POST /schedule/slots and POST
            /schedule/activities/{activity_id}/enrollments.

    Raises:
        errors.UnexpectedStatus: If the server returns an undocumented status code and Client.raise_on_unexpected_status is True.
        httpx.TimeoutException: If the request takes longer than Client.timeout.

    Returns:
        Response[ActivityResponse | ErrorResponse]
    """

    kwargs = _get_kwargs(
        body=body,
        idempotency_key=idempotency_key,
    )

    response = client.get_httpx_client().request(
        **kwargs,
    )

    return _build_response(client=client, response=response)


def sync(
    *,
    client: AuthenticatedClient | Client,
    body: ActivityCreate,
    idempotency_key: str | Unset = UNSET,
) -> ActivityResponse | ErrorResponse | None:
    """Add an activity

     Admin only. A UNIT_ADMIN may only add activities to their own unit (403 `OUTSIDE_UNIT`). The
    activity starts with no slots and no members. Each slot added to it with POST /schedule/slots fills
    the days ahead at once, through the same generator a CSV import and the nightly job use, so an
    activity built here gets exactly the days the same activity imported from a CSV would.

    Args:
        idempotency_key (str | Unset):
        body (ActivityCreate): An activity, the same one a CSV row names by code, title and unit.
            It starts with no slots and no members; those are added with POST /schedule/slots and POST
            /schedule/activities/{activity_id}/enrollments.

    Raises:
        errors.UnexpectedStatus: If the server returns an undocumented status code and Client.raise_on_unexpected_status is True.
        httpx.TimeoutException: If the request takes longer than Client.timeout.

    Returns:
        ActivityResponse | ErrorResponse
    """

    return sync_detailed(
        client=client,
        body=body,
        idempotency_key=idempotency_key,
    ).parsed


async def asyncio_detailed(
    *,
    client: AuthenticatedClient | Client,
    body: ActivityCreate,
    idempotency_key: str | Unset = UNSET,
) -> Response[ActivityResponse | ErrorResponse]:
    """Add an activity

     Admin only. A UNIT_ADMIN may only add activities to their own unit (403 `OUTSIDE_UNIT`). The
    activity starts with no slots and no members. Each slot added to it with POST /schedule/slots fills
    the days ahead at once, through the same generator a CSV import and the nightly job use, so an
    activity built here gets exactly the days the same activity imported from a CSV would.

    Args:
        idempotency_key (str | Unset):
        body (ActivityCreate): An activity, the same one a CSV row names by code, title and unit.
            It starts with no slots and no members; those are added with POST /schedule/slots and POST
            /schedule/activities/{activity_id}/enrollments.

    Raises:
        errors.UnexpectedStatus: If the server returns an undocumented status code and Client.raise_on_unexpected_status is True.
        httpx.TimeoutException: If the request takes longer than Client.timeout.

    Returns:
        Response[ActivityResponse | ErrorResponse]
    """

    kwargs = _get_kwargs(
        body=body,
        idempotency_key=idempotency_key,
    )

    response = await client.get_async_httpx_client().request(**kwargs)

    return _build_response(client=client, response=response)


async def asyncio(
    *,
    client: AuthenticatedClient | Client,
    body: ActivityCreate,
    idempotency_key: str | Unset = UNSET,
) -> ActivityResponse | ErrorResponse | None:
    """Add an activity

     Admin only. A UNIT_ADMIN may only add activities to their own unit (403 `OUTSIDE_UNIT`). The
    activity starts with no slots and no members. Each slot added to it with POST /schedule/slots fills
    the days ahead at once, through the same generator a CSV import and the nightly job use, so an
    activity built here gets exactly the days the same activity imported from a CSV would.

    Args:
        idempotency_key (str | Unset):
        body (ActivityCreate): An activity, the same one a CSV row names by code, title and unit.
            It starts with no slots and no members; those are added with POST /schedule/slots and POST
            /schedule/activities/{activity_id}/enrollments.

    Raises:
        errors.UnexpectedStatus: If the server returns an undocumented status code and Client.raise_on_unexpected_status is True.
        httpx.TimeoutException: If the request takes longer than Client.timeout.

    Returns:
        ActivityResponse | ErrorResponse
    """

    return (
        await asyncio_detailed(
            client=client,
            body=body,
            idempotency_key=idempotency_key,
        )
    ).parsed
