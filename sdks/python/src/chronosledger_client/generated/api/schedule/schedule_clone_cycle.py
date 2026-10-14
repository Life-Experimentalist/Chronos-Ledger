from http import HTTPStatus
from typing import Any
from urllib.parse import quote

import httpx

from ... import errors
from ...client import AuthenticatedClient, Client
from ...models.error_response import ErrorResponse
from ...models.schedule_clone_cycle_response_200 import ScheduleCloneCycleResponse200
from ...types import UNSET, Response, Unset


def _get_kwargs(
    old_id: int,
    new_id: int,
    *,
    idempotency_key: str | Unset = UNSET,
) -> dict[str, Any]:
    headers: dict[str, Any] = {}
    if not isinstance(idempotency_key, Unset):
        headers["Idempotency-Key"] = idempotency_key

    _kwargs: dict[str, Any] = {
        "method": "post",
        "url": "/api/v1/schedule/cycles/{old_id}/clone-to/{new_id}".format(
            old_id=quote(str(old_id), safe=""),
            new_id=quote(str(new_id), safe=""),
        ),
    }

    _kwargs["headers"] = headers
    return _kwargs


def _parse_response(
    *, client: AuthenticatedClient | Client, response: httpx.Response
) -> ErrorResponse | ScheduleCloneCycleResponse200 | None:
    if response.status_code == 200:
        response_200 = ScheduleCloneCycleResponse200.from_dict(response.json())

        return response_200

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
) -> Response[ErrorResponse | ScheduleCloneCycleResponse200]:
    return Response(
        status_code=HTTPStatus(response.status_code),
        content=response.content,
        headers=response.headers,
        parsed=_parse_response(client=client, response=response),
    )


def sync_detailed(
    old_id: int,
    new_id: int,
    *,
    client: AuthenticatedClient | Client,
    idempotency_key: str | Unset = UNSET,
) -> Response[ErrorResponse | ScheduleCloneCycleResponse200]:
    """Copy one cycle's activities and weekly slots into another

     Copies every `Activity` in the old cycle and every `StructuralMasterSlot` under them, each slot
    pointed at its activity's copy with the same lead, room and window. Member enrollment and attendance
    records are **not** cloned. Re-import CSV after cloning to update enrollment. Retired activities and
    retired slots are left behind.

    The target must be closed and have no activities. The copied slots are not checked against the rooms
    here; opening the target runs those checks over all of them at once. Requires `ORG_ADMIN`.

    Args:
        old_id (int):
        new_id (int):
        idempotency_key (str | Unset):

    Raises:
        errors.UnexpectedStatus: If the server returns an undocumented status code and Client.raise_on_unexpected_status is True.
        httpx.TimeoutException: If the request takes longer than Client.timeout.

    Returns:
        Response[ErrorResponse | ScheduleCloneCycleResponse200]
    """

    kwargs = _get_kwargs(
        old_id=old_id,
        new_id=new_id,
        idempotency_key=idempotency_key,
    )

    response = client.get_httpx_client().request(
        **kwargs,
    )

    return _build_response(client=client, response=response)


def sync(
    old_id: int,
    new_id: int,
    *,
    client: AuthenticatedClient | Client,
    idempotency_key: str | Unset = UNSET,
) -> ErrorResponse | ScheduleCloneCycleResponse200 | None:
    """Copy one cycle's activities and weekly slots into another

     Copies every `Activity` in the old cycle and every `StructuralMasterSlot` under them, each slot
    pointed at its activity's copy with the same lead, room and window. Member enrollment and attendance
    records are **not** cloned. Re-import CSV after cloning to update enrollment. Retired activities and
    retired slots are left behind.

    The target must be closed and have no activities. The copied slots are not checked against the rooms
    here; opening the target runs those checks over all of them at once. Requires `ORG_ADMIN`.

    Args:
        old_id (int):
        new_id (int):
        idempotency_key (str | Unset):

    Raises:
        errors.UnexpectedStatus: If the server returns an undocumented status code and Client.raise_on_unexpected_status is True.
        httpx.TimeoutException: If the request takes longer than Client.timeout.

    Returns:
        ErrorResponse | ScheduleCloneCycleResponse200
    """

    return sync_detailed(
        old_id=old_id,
        new_id=new_id,
        client=client,
        idempotency_key=idempotency_key,
    ).parsed


async def asyncio_detailed(
    old_id: int,
    new_id: int,
    *,
    client: AuthenticatedClient | Client,
    idempotency_key: str | Unset = UNSET,
) -> Response[ErrorResponse | ScheduleCloneCycleResponse200]:
    """Copy one cycle's activities and weekly slots into another

     Copies every `Activity` in the old cycle and every `StructuralMasterSlot` under them, each slot
    pointed at its activity's copy with the same lead, room and window. Member enrollment and attendance
    records are **not** cloned. Re-import CSV after cloning to update enrollment. Retired activities and
    retired slots are left behind.

    The target must be closed and have no activities. The copied slots are not checked against the rooms
    here; opening the target runs those checks over all of them at once. Requires `ORG_ADMIN`.

    Args:
        old_id (int):
        new_id (int):
        idempotency_key (str | Unset):

    Raises:
        errors.UnexpectedStatus: If the server returns an undocumented status code and Client.raise_on_unexpected_status is True.
        httpx.TimeoutException: If the request takes longer than Client.timeout.

    Returns:
        Response[ErrorResponse | ScheduleCloneCycleResponse200]
    """

    kwargs = _get_kwargs(
        old_id=old_id,
        new_id=new_id,
        idempotency_key=idempotency_key,
    )

    response = await client.get_async_httpx_client().request(**kwargs)

    return _build_response(client=client, response=response)


async def asyncio(
    old_id: int,
    new_id: int,
    *,
    client: AuthenticatedClient | Client,
    idempotency_key: str | Unset = UNSET,
) -> ErrorResponse | ScheduleCloneCycleResponse200 | None:
    """Copy one cycle's activities and weekly slots into another

     Copies every `Activity` in the old cycle and every `StructuralMasterSlot` under them, each slot
    pointed at its activity's copy with the same lead, room and window. Member enrollment and attendance
    records are **not** cloned. Re-import CSV after cloning to update enrollment. Retired activities and
    retired slots are left behind.

    The target must be closed and have no activities. The copied slots are not checked against the rooms
    here; opening the target runs those checks over all of them at once. Requires `ORG_ADMIN`.

    Args:
        old_id (int):
        new_id (int):
        idempotency_key (str | Unset):

    Raises:
        errors.UnexpectedStatus: If the server returns an undocumented status code and Client.raise_on_unexpected_status is True.
        httpx.TimeoutException: If the request takes longer than Client.timeout.

    Returns:
        ErrorResponse | ScheduleCloneCycleResponse200
    """

    return (
        await asyncio_detailed(
            old_id=old_id,
            new_id=new_id,
            client=client,
            idempotency_key=idempotency_key,
        )
    ).parsed
