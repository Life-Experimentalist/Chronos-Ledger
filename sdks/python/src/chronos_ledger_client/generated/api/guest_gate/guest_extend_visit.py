from http import HTTPStatus
from typing import Any
from urllib.parse import quote

import httpx

from ... import errors
from ...client import AuthenticatedClient, Client
from ...models.error_response import ErrorResponse
from ...models.guest_extend_visit_response_200 import GuestExtendVisitResponse200
from ...models.guest_extension_request import GuestExtensionRequest
from ...types import UNSET, Response, Unset


def _get_kwargs(
    entry_id: int,
    *,
    body: GuestExtensionRequest,
    idempotency_key: str | Unset = UNSET,
) -> dict[str, Any]:
    headers: dict[str, Any] = {}
    if not isinstance(idempotency_key, Unset):
        headers["Idempotency-Key"] = idempotency_key

    _kwargs: dict[str, Any] = {
        "method": "patch",
        "url": "/api/v1/guest/{entry_id}/extend".format(
            entry_id=quote(str(entry_id), safe=""),
        ),
    }

    _kwargs["json"] = body.to_dict()

    headers["Content-Type"] = "application/json"

    _kwargs["headers"] = headers
    return _kwargs


def _parse_response(
    *, client: AuthenticatedClient | Client, response: httpx.Response
) -> ErrorResponse | GuestExtendVisitResponse200 | None:
    if response.status_code == 200:
        response_200 = GuestExtendVisitResponse200.from_dict(response.json())

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
) -> Response[ErrorResponse | GuestExtendVisitResponse200]:
    return Response(
        status_code=HTTPStatus(response.status_code),
        content=response.content,
        headers=response.headers,
        parsed=_parse_response(client=client, response=response),
    )


def sync_detailed(
    entry_id: int,
    *,
    client: AuthenticatedClient | Client,
    body: GuestExtensionRequest,
    idempotency_key: str | Unset = UNSET,
) -> Response[ErrorResponse | GuestExtendVisitResponse200]:
    """Give an approved visit longer

     Whoever could have decided the visit can extend it, on the reasoning that a desk which may let
    somebody in may also let them stay. The extension runs from whichever is later, now or the end the
    visit already has, so a visit half an hour over gets the full grant rather than a window that has
    already gone. There is no limit on how many times: this bounds one grant, and the audit record of
    each extension is what an organization gets in place of a ceiling on the whole visit.

    Args:
        entry_id (int):
        idempotency_key (str | Unset):
        body (GuestExtensionRequest):

    Raises:
        errors.UnexpectedStatus: If the server returns an undocumented status code and Client.raise_on_unexpected_status is True.
        httpx.TimeoutException: If the request takes longer than Client.timeout.

    Returns:
        Response[ErrorResponse | GuestExtendVisitResponse200]
    """

    kwargs = _get_kwargs(
        entry_id=entry_id,
        body=body,
        idempotency_key=idempotency_key,
    )

    response = client.get_httpx_client().request(
        **kwargs,
    )

    return _build_response(client=client, response=response)


def sync(
    entry_id: int,
    *,
    client: AuthenticatedClient | Client,
    body: GuestExtensionRequest,
    idempotency_key: str | Unset = UNSET,
) -> ErrorResponse | GuestExtendVisitResponse200 | None:
    """Give an approved visit longer

     Whoever could have decided the visit can extend it, on the reasoning that a desk which may let
    somebody in may also let them stay. The extension runs from whichever is later, now or the end the
    visit already has, so a visit half an hour over gets the full grant rather than a window that has
    already gone. There is no limit on how many times: this bounds one grant, and the audit record of
    each extension is what an organization gets in place of a ceiling on the whole visit.

    Args:
        entry_id (int):
        idempotency_key (str | Unset):
        body (GuestExtensionRequest):

    Raises:
        errors.UnexpectedStatus: If the server returns an undocumented status code and Client.raise_on_unexpected_status is True.
        httpx.TimeoutException: If the request takes longer than Client.timeout.

    Returns:
        ErrorResponse | GuestExtendVisitResponse200
    """

    return sync_detailed(
        entry_id=entry_id,
        client=client,
        body=body,
        idempotency_key=idempotency_key,
    ).parsed


async def asyncio_detailed(
    entry_id: int,
    *,
    client: AuthenticatedClient | Client,
    body: GuestExtensionRequest,
    idempotency_key: str | Unset = UNSET,
) -> Response[ErrorResponse | GuestExtendVisitResponse200]:
    """Give an approved visit longer

     Whoever could have decided the visit can extend it, on the reasoning that a desk which may let
    somebody in may also let them stay. The extension runs from whichever is later, now or the end the
    visit already has, so a visit half an hour over gets the full grant rather than a window that has
    already gone. There is no limit on how many times: this bounds one grant, and the audit record of
    each extension is what an organization gets in place of a ceiling on the whole visit.

    Args:
        entry_id (int):
        idempotency_key (str | Unset):
        body (GuestExtensionRequest):

    Raises:
        errors.UnexpectedStatus: If the server returns an undocumented status code and Client.raise_on_unexpected_status is True.
        httpx.TimeoutException: If the request takes longer than Client.timeout.

    Returns:
        Response[ErrorResponse | GuestExtendVisitResponse200]
    """

    kwargs = _get_kwargs(
        entry_id=entry_id,
        body=body,
        idempotency_key=idempotency_key,
    )

    response = await client.get_async_httpx_client().request(**kwargs)

    return _build_response(client=client, response=response)


async def asyncio(
    entry_id: int,
    *,
    client: AuthenticatedClient | Client,
    body: GuestExtensionRequest,
    idempotency_key: str | Unset = UNSET,
) -> ErrorResponse | GuestExtendVisitResponse200 | None:
    """Give an approved visit longer

     Whoever could have decided the visit can extend it, on the reasoning that a desk which may let
    somebody in may also let them stay. The extension runs from whichever is later, now or the end the
    visit already has, so a visit half an hour over gets the full grant rather than a window that has
    already gone. There is no limit on how many times: this bounds one grant, and the audit record of
    each extension is what an organization gets in place of a ceiling on the whole visit.

    Args:
        entry_id (int):
        idempotency_key (str | Unset):
        body (GuestExtensionRequest):

    Raises:
        errors.UnexpectedStatus: If the server returns an undocumented status code and Client.raise_on_unexpected_status is True.
        httpx.TimeoutException: If the request takes longer than Client.timeout.

    Returns:
        ErrorResponse | GuestExtendVisitResponse200
    """

    return (
        await asyncio_detailed(
            entry_id=entry_id,
            client=client,
            body=body,
            idempotency_key=idempotency_key,
        )
    ).parsed
