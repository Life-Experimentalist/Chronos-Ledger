from http import HTTPStatus
from typing import Any
from urllib.parse import quote

import httpx

from ... import errors
from ...client import AuthenticatedClient, Client
from ...models.error_response import ErrorResponse
from ...models.retire_result import RetireResult
from ...types import UNSET, Response, Unset


def _get_kwargs(
    activity_id: int,
    *,
    idempotency_key: str | Unset = UNSET,
) -> dict[str, Any]:
    headers: dict[str, Any] = {}
    if not isinstance(idempotency_key, Unset):
        headers["Idempotency-Key"] = idempotency_key

    _kwargs: dict[str, Any] = {
        "method": "post",
        "url": "/api/v1/schedule/activities/{activity_id}/retire".format(
            activity_id=quote(str(activity_id), safe=""),
        ),
    }

    _kwargs["headers"] = headers
    return _kwargs


def _parse_response(
    *, client: AuthenticatedClient | Client, response: httpx.Response
) -> ErrorResponse | RetireResult | None:
    if response.status_code == 200:
        response_200 = RetireResult.from_dict(response.json())

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

    if client.raise_on_unexpected_status:
        raise errors.UnexpectedStatus(response.status_code, response.content)
    else:
        return None


def _build_response(
    *, client: AuthenticatedClient | Client, response: httpx.Response
) -> Response[ErrorResponse | RetireResult]:
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
    idempotency_key: str | Unset = UNSET,
) -> Response[ErrorResponse | RetireResult]:
    """Retire an activity

     Admin only, inside the admin's unit. Nothing is deleted that has happened. The activity and every
    slot it still has are marked retired, so the generator writes no more days for them and their rooms
    are free again. Days from today onward that nobody has marked or annotated are removed; days that
    carry attendance or a note are kept; days before today are not touched.

    A retired activity stays readable through GET /schedule/activities/{activity_id} and is left out of
    the list unless `include_retired` is set. It cannot be edited, given slots or members, or retired
    again (409 `STATE_CONFLICT`), and a CSV import that names it is refused. Its code stays taken in the
    cycle.

    Args:
        activity_id (int):
        idempotency_key (str | Unset):

    Raises:
        errors.UnexpectedStatus: If the server returns an undocumented status code and Client.raise_on_unexpected_status is True.
        httpx.TimeoutException: If the request takes longer than Client.timeout.

    Returns:
        Response[ErrorResponse | RetireResult]
    """

    kwargs = _get_kwargs(
        activity_id=activity_id,
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
    idempotency_key: str | Unset = UNSET,
) -> ErrorResponse | RetireResult | None:
    """Retire an activity

     Admin only, inside the admin's unit. Nothing is deleted that has happened. The activity and every
    slot it still has are marked retired, so the generator writes no more days for them and their rooms
    are free again. Days from today onward that nobody has marked or annotated are removed; days that
    carry attendance or a note are kept; days before today are not touched.

    A retired activity stays readable through GET /schedule/activities/{activity_id} and is left out of
    the list unless `include_retired` is set. It cannot be edited, given slots or members, or retired
    again (409 `STATE_CONFLICT`), and a CSV import that names it is refused. Its code stays taken in the
    cycle.

    Args:
        activity_id (int):
        idempotency_key (str | Unset):

    Raises:
        errors.UnexpectedStatus: If the server returns an undocumented status code and Client.raise_on_unexpected_status is True.
        httpx.TimeoutException: If the request takes longer than Client.timeout.

    Returns:
        ErrorResponse | RetireResult
    """

    return sync_detailed(
        activity_id=activity_id,
        client=client,
        idempotency_key=idempotency_key,
    ).parsed


async def asyncio_detailed(
    activity_id: int,
    *,
    client: AuthenticatedClient | Client,
    idempotency_key: str | Unset = UNSET,
) -> Response[ErrorResponse | RetireResult]:
    """Retire an activity

     Admin only, inside the admin's unit. Nothing is deleted that has happened. The activity and every
    slot it still has are marked retired, so the generator writes no more days for them and their rooms
    are free again. Days from today onward that nobody has marked or annotated are removed; days that
    carry attendance or a note are kept; days before today are not touched.

    A retired activity stays readable through GET /schedule/activities/{activity_id} and is left out of
    the list unless `include_retired` is set. It cannot be edited, given slots or members, or retired
    again (409 `STATE_CONFLICT`), and a CSV import that names it is refused. Its code stays taken in the
    cycle.

    Args:
        activity_id (int):
        idempotency_key (str | Unset):

    Raises:
        errors.UnexpectedStatus: If the server returns an undocumented status code and Client.raise_on_unexpected_status is True.
        httpx.TimeoutException: If the request takes longer than Client.timeout.

    Returns:
        Response[ErrorResponse | RetireResult]
    """

    kwargs = _get_kwargs(
        activity_id=activity_id,
        idempotency_key=idempotency_key,
    )

    response = await client.get_async_httpx_client().request(**kwargs)

    return _build_response(client=client, response=response)


async def asyncio(
    activity_id: int,
    *,
    client: AuthenticatedClient | Client,
    idempotency_key: str | Unset = UNSET,
) -> ErrorResponse | RetireResult | None:
    """Retire an activity

     Admin only, inside the admin's unit. Nothing is deleted that has happened. The activity and every
    slot it still has are marked retired, so the generator writes no more days for them and their rooms
    are free again. Days from today onward that nobody has marked or annotated are removed; days that
    carry attendance or a note are kept; days before today are not touched.

    A retired activity stays readable through GET /schedule/activities/{activity_id} and is left out of
    the list unless `include_retired` is set. It cannot be edited, given slots or members, or retired
    again (409 `STATE_CONFLICT`), and a CSV import that names it is refused. Its code stays taken in the
    cycle.

    Args:
        activity_id (int):
        idempotency_key (str | Unset):

    Raises:
        errors.UnexpectedStatus: If the server returns an undocumented status code and Client.raise_on_unexpected_status is True.
        httpx.TimeoutException: If the request takes longer than Client.timeout.

    Returns:
        ErrorResponse | RetireResult
    """

    return (
        await asyncio_detailed(
            activity_id=activity_id,
            client=client,
            idempotency_key=idempotency_key,
        )
    ).parsed
