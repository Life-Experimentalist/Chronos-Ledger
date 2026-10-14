from http import HTTPStatus
from typing import Any
from urllib.parse import quote

import httpx

from ... import errors
from ...client import AuthenticatedClient, Client
from ...models.activity_response import ActivityResponse
from ...models.activity_update import ActivityUpdate
from ...models.error_response import ErrorResponse
from ...types import UNSET, Response, Unset


def _get_kwargs(
    activity_id: int,
    *,
    body: ActivityUpdate,
    idempotency_key: str | Unset = UNSET,
) -> dict[str, Any]:
    headers: dict[str, Any] = {}
    if not isinstance(idempotency_key, Unset):
        headers["Idempotency-Key"] = idempotency_key

    _kwargs: dict[str, Any] = {
        "method": "patch",
        "url": "/api/v1/schedule/activities/{activity_id}".format(
            activity_id=quote(str(activity_id), safe=""),
        ),
    }

    _kwargs["json"] = body.to_dict()

    headers["Content-Type"] = "application/json"

    _kwargs["headers"] = headers
    return _kwargs


def _parse_response(
    *, client: AuthenticatedClient | Client, response: httpx.Response
) -> ActivityResponse | ErrorResponse | None:
    if response.status_code == 200:
        response_200 = ActivityResponse.from_dict(response.json())

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
) -> Response[ActivityResponse | ErrorResponse]:
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
    body: ActivityUpdate,
    idempotency_key: str | Unset = UNSET,
) -> Response[ActivityResponse | ErrorResponse]:
    """Rename an activity

     Admin only, inside the admin's unit. Only the title can change; see ActivityUpdate for why. Refused
    with 409 `STATE_CONFLICT` once the activity is retired.

    Args:
        activity_id (int):
        idempotency_key (str | Unset):
        body (ActivityUpdate): Only the title can change. The code and the cycle are what identify
            an activity, the same pair a CSV upsert matches on, so changing either is a different
            activity. The unit is what a unit admin's permission is checked against, and moving an
            activity between units is left to an import, which only an org admin can run.

    Raises:
        errors.UnexpectedStatus: If the server returns an undocumented status code and Client.raise_on_unexpected_status is True.
        httpx.TimeoutException: If the request takes longer than Client.timeout.

    Returns:
        Response[ActivityResponse | ErrorResponse]
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
    body: ActivityUpdate,
    idempotency_key: str | Unset = UNSET,
) -> ActivityResponse | ErrorResponse | None:
    """Rename an activity

     Admin only, inside the admin's unit. Only the title can change; see ActivityUpdate for why. Refused
    with 409 `STATE_CONFLICT` once the activity is retired.

    Args:
        activity_id (int):
        idempotency_key (str | Unset):
        body (ActivityUpdate): Only the title can change. The code and the cycle are what identify
            an activity, the same pair a CSV upsert matches on, so changing either is a different
            activity. The unit is what a unit admin's permission is checked against, and moving an
            activity between units is left to an import, which only an org admin can run.

    Raises:
        errors.UnexpectedStatus: If the server returns an undocumented status code and Client.raise_on_unexpected_status is True.
        httpx.TimeoutException: If the request takes longer than Client.timeout.

    Returns:
        ActivityResponse | ErrorResponse
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
    body: ActivityUpdate,
    idempotency_key: str | Unset = UNSET,
) -> Response[ActivityResponse | ErrorResponse]:
    """Rename an activity

     Admin only, inside the admin's unit. Only the title can change; see ActivityUpdate for why. Refused
    with 409 `STATE_CONFLICT` once the activity is retired.

    Args:
        activity_id (int):
        idempotency_key (str | Unset):
        body (ActivityUpdate): Only the title can change. The code and the cycle are what identify
            an activity, the same pair a CSV upsert matches on, so changing either is a different
            activity. The unit is what a unit admin's permission is checked against, and moving an
            activity between units is left to an import, which only an org admin can run.

    Raises:
        errors.UnexpectedStatus: If the server returns an undocumented status code and Client.raise_on_unexpected_status is True.
        httpx.TimeoutException: If the request takes longer than Client.timeout.

    Returns:
        Response[ActivityResponse | ErrorResponse]
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
    body: ActivityUpdate,
    idempotency_key: str | Unset = UNSET,
) -> ActivityResponse | ErrorResponse | None:
    """Rename an activity

     Admin only, inside the admin's unit. Only the title can change; see ActivityUpdate for why. Refused
    with 409 `STATE_CONFLICT` once the activity is retired.

    Args:
        activity_id (int):
        idempotency_key (str | Unset):
        body (ActivityUpdate): Only the title can change. The code and the cycle are what identify
            an activity, the same pair a CSV upsert matches on, so changing either is a different
            activity. The unit is what a unit admin's permission is checked against, and moving an
            activity between units is left to an import, which only an org admin can run.

    Raises:
        errors.UnexpectedStatus: If the server returns an undocumented status code and Client.raise_on_unexpected_status is True.
        httpx.TimeoutException: If the request takes longer than Client.timeout.

    Returns:
        ActivityResponse | ErrorResponse
    """

    return (
        await asyncio_detailed(
            activity_id=activity_id,
            client=client,
            body=body,
            idempotency_key=idempotency_key,
        )
    ).parsed
