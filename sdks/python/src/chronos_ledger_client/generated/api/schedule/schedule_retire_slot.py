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
    slot_id: int,
    *,
    idempotency_key: str | Unset = UNSET,
) -> dict[str, Any]:
    headers: dict[str, Any] = {}
    if not isinstance(idempotency_key, Unset):
        headers["Idempotency-Key"] = idempotency_key

    _kwargs: dict[str, Any] = {
        "method": "post",
        "url": "/api/v1/schedule/slots/{slot_id}/retire".format(
            slot_id=quote(str(slot_id), safe=""),
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
    slot_id: int,
    *,
    client: AuthenticatedClient | Client,
    idempotency_key: str | Unset = UNSET,
) -> Response[ErrorResponse | RetireResult]:
    """Retire a master slot

     Admin only, inside the admin's unit. Where DELETE refuses while a day ahead carries attendance or a
    note, this keeps that day and removes the days ahead that are still plans. Days before today are not
    touched. The slot stays, marked retired, so the generator writes no more days for it and its room is
    free again. A retired slot cannot be edited, deleted or retired again (409 `STATE_CONFLICT`), and a
    CSV row naming it is refused.

    Args:
        slot_id (int):
        idempotency_key (str | Unset):

    Raises:
        errors.UnexpectedStatus: If the server returns an undocumented status code and Client.raise_on_unexpected_status is True.
        httpx.TimeoutException: If the request takes longer than Client.timeout.

    Returns:
        Response[ErrorResponse | RetireResult]
    """

    kwargs = _get_kwargs(
        slot_id=slot_id,
        idempotency_key=idempotency_key,
    )

    response = client.get_httpx_client().request(
        **kwargs,
    )

    return _build_response(client=client, response=response)


def sync(
    slot_id: int,
    *,
    client: AuthenticatedClient | Client,
    idempotency_key: str | Unset = UNSET,
) -> ErrorResponse | RetireResult | None:
    """Retire a master slot

     Admin only, inside the admin's unit. Where DELETE refuses while a day ahead carries attendance or a
    note, this keeps that day and removes the days ahead that are still plans. Days before today are not
    touched. The slot stays, marked retired, so the generator writes no more days for it and its room is
    free again. A retired slot cannot be edited, deleted or retired again (409 `STATE_CONFLICT`), and a
    CSV row naming it is refused.

    Args:
        slot_id (int):
        idempotency_key (str | Unset):

    Raises:
        errors.UnexpectedStatus: If the server returns an undocumented status code and Client.raise_on_unexpected_status is True.
        httpx.TimeoutException: If the request takes longer than Client.timeout.

    Returns:
        ErrorResponse | RetireResult
    """

    return sync_detailed(
        slot_id=slot_id,
        client=client,
        idempotency_key=idempotency_key,
    ).parsed


async def asyncio_detailed(
    slot_id: int,
    *,
    client: AuthenticatedClient | Client,
    idempotency_key: str | Unset = UNSET,
) -> Response[ErrorResponse | RetireResult]:
    """Retire a master slot

     Admin only, inside the admin's unit. Where DELETE refuses while a day ahead carries attendance or a
    note, this keeps that day and removes the days ahead that are still plans. Days before today are not
    touched. The slot stays, marked retired, so the generator writes no more days for it and its room is
    free again. A retired slot cannot be edited, deleted or retired again (409 `STATE_CONFLICT`), and a
    CSV row naming it is refused.

    Args:
        slot_id (int):
        idempotency_key (str | Unset):

    Raises:
        errors.UnexpectedStatus: If the server returns an undocumented status code and Client.raise_on_unexpected_status is True.
        httpx.TimeoutException: If the request takes longer than Client.timeout.

    Returns:
        Response[ErrorResponse | RetireResult]
    """

    kwargs = _get_kwargs(
        slot_id=slot_id,
        idempotency_key=idempotency_key,
    )

    response = await client.get_async_httpx_client().request(**kwargs)

    return _build_response(client=client, response=response)


async def asyncio(
    slot_id: int,
    *,
    client: AuthenticatedClient | Client,
    idempotency_key: str | Unset = UNSET,
) -> ErrorResponse | RetireResult | None:
    """Retire a master slot

     Admin only, inside the admin's unit. Where DELETE refuses while a day ahead carries attendance or a
    note, this keeps that day and removes the days ahead that are still plans. Days before today are not
    touched. The slot stays, marked retired, so the generator writes no more days for it and its room is
    free again. A retired slot cannot be edited, deleted or retired again (409 `STATE_CONFLICT`), and a
    CSV row naming it is refused.

    Args:
        slot_id (int):
        idempotency_key (str | Unset):

    Raises:
        errors.UnexpectedStatus: If the server returns an undocumented status code and Client.raise_on_unexpected_status is True.
        httpx.TimeoutException: If the request takes longer than Client.timeout.

    Returns:
        ErrorResponse | RetireResult
    """

    return (
        await asyncio_detailed(
            slot_id=slot_id,
            client=client,
            idempotency_key=idempotency_key,
        )
    ).parsed
