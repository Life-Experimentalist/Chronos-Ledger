from http import HTTPStatus
from typing import Any
from urllib.parse import quote

import httpx

from ... import errors
from ...client import AuthenticatedClient, Client
from ...models.error_response import ErrorResponse
from ...models.reservation_ref_taken import ReservationRefTaken
from ...models.reservation_response import ReservationResponse
from ...models.reservation_update import ReservationUpdate
from ...types import UNSET, Response, Unset


def _get_kwargs(
    resource_id: int,
    reservation_id: int,
    *,
    body: ReservationUpdate,
    idempotency_key: str | Unset = UNSET,
) -> dict[str, Any]:
    headers: dict[str, Any] = {}
    if not isinstance(idempotency_key, Unset):
        headers["Idempotency-Key"] = idempotency_key

    _kwargs: dict[str, Any] = {
        "method": "patch",
        "url": "/api/v1/resources/{resource_id}/reservations/{reservation_id}".format(
            resource_id=quote(str(resource_id), safe=""),
            reservation_id=quote(str(reservation_id), safe=""),
        ),
    }

    _kwargs["json"] = body.to_dict()

    headers["Content-Type"] = "application/json"

    _kwargs["headers"] = headers
    return _kwargs


def _parse_response(
    *, client: AuthenticatedClient | Client, response: httpx.Response
) -> ErrorResponse | ReservationRefTaken | ReservationResponse | None:
    if response.status_code == 200:
        response_200 = ReservationResponse.from_dict(response.json())

        return response_200

    if response.status_code == 401:
        response_401 = ErrorResponse.from_dict(response.json())

        return response_401

    if response.status_code == 403:
        response_403 = ErrorResponse.from_dict(response.json())

        return response_403

    if response.status_code == 404:
        response_404 = ErrorResponse.from_dict(response.json())

        return response_404

    if response.status_code == 409:
        response_409 = ReservationRefTaken.from_dict(response.json())

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
) -> Response[ErrorResponse | ReservationRefTaken | ReservationResponse]:
    return Response(
        status_code=HTTPStatus(response.status_code),
        content=response.content,
        headers=response.headers,
        parsed=_parse_response(client=client, response=response),
    )


def sync_detailed(
    resource_id: int,
    reservation_id: int,
    *,
    client: AuthenticatedClient | Client,
    body: ReservationUpdate,
    idempotency_key: str | Unset = UNSET,
) -> Response[ErrorResponse | ReservationRefTaken | ReservationResponse]:
    """Change a reservation's external_ref

     Requires `ORG_ADMIN` or `UNIT_ADMIN`. Sets, changes or clears the caller's reference for a
    reservation. Only the reference can change: moving the window is a cancel and a new booking.

    The reference is unique per requester, the same rule as on create, and taking one already on another
    of the requester's reservations is the same 409. When an `ORG_ADMIN` changes a reservation somebody
    else made, the reference is checked against that requester's, not the admin's. A cancelled
    reservation keeps its reference, so this is how a caller frees one to book under again.

    Who may change a reservation is who may cancel it: whoever took it, or an `ORG_ADMIN`. A
    `UNIT_ADMIN` that did not make it gets a 403. Sending the reference the reservation already has
    changes nothing and leaves no entry on the change feed; a real change leaves one.

    Args:
        resource_id (int):
        reservation_id (int):
        idempotency_key (str | Unset):
        body (ReservationUpdate): What the caller may change about a reservation it already holds:
            its reference, for now. The window is what the conflict check and the idempotency
            fingerprint are built on, so moving it is a cancel and a new booking. Any other field is
            refused with a 422 rather than ignored.

    Raises:
        errors.UnexpectedStatus: If the server returns an undocumented status code and Client.raise_on_unexpected_status is True.
        httpx.TimeoutException: If the request takes longer than Client.timeout.

    Returns:
        Response[ErrorResponse | ReservationRefTaken | ReservationResponse]
    """

    kwargs = _get_kwargs(
        resource_id=resource_id,
        reservation_id=reservation_id,
        body=body,
        idempotency_key=idempotency_key,
    )

    response = client.get_httpx_client().request(
        **kwargs,
    )

    return _build_response(client=client, response=response)


def sync(
    resource_id: int,
    reservation_id: int,
    *,
    client: AuthenticatedClient | Client,
    body: ReservationUpdate,
    idempotency_key: str | Unset = UNSET,
) -> ErrorResponse | ReservationRefTaken | ReservationResponse | None:
    """Change a reservation's external_ref

     Requires `ORG_ADMIN` or `UNIT_ADMIN`. Sets, changes or clears the caller's reference for a
    reservation. Only the reference can change: moving the window is a cancel and a new booking.

    The reference is unique per requester, the same rule as on create, and taking one already on another
    of the requester's reservations is the same 409. When an `ORG_ADMIN` changes a reservation somebody
    else made, the reference is checked against that requester's, not the admin's. A cancelled
    reservation keeps its reference, so this is how a caller frees one to book under again.

    Who may change a reservation is who may cancel it: whoever took it, or an `ORG_ADMIN`. A
    `UNIT_ADMIN` that did not make it gets a 403. Sending the reference the reservation already has
    changes nothing and leaves no entry on the change feed; a real change leaves one.

    Args:
        resource_id (int):
        reservation_id (int):
        idempotency_key (str | Unset):
        body (ReservationUpdate): What the caller may change about a reservation it already holds:
            its reference, for now. The window is what the conflict check and the idempotency
            fingerprint are built on, so moving it is a cancel and a new booking. Any other field is
            refused with a 422 rather than ignored.

    Raises:
        errors.UnexpectedStatus: If the server returns an undocumented status code and Client.raise_on_unexpected_status is True.
        httpx.TimeoutException: If the request takes longer than Client.timeout.

    Returns:
        ErrorResponse | ReservationRefTaken | ReservationResponse
    """

    return sync_detailed(
        resource_id=resource_id,
        reservation_id=reservation_id,
        client=client,
        body=body,
        idempotency_key=idempotency_key,
    ).parsed


async def asyncio_detailed(
    resource_id: int,
    reservation_id: int,
    *,
    client: AuthenticatedClient | Client,
    body: ReservationUpdate,
    idempotency_key: str | Unset = UNSET,
) -> Response[ErrorResponse | ReservationRefTaken | ReservationResponse]:
    """Change a reservation's external_ref

     Requires `ORG_ADMIN` or `UNIT_ADMIN`. Sets, changes or clears the caller's reference for a
    reservation. Only the reference can change: moving the window is a cancel and a new booking.

    The reference is unique per requester, the same rule as on create, and taking one already on another
    of the requester's reservations is the same 409. When an `ORG_ADMIN` changes a reservation somebody
    else made, the reference is checked against that requester's, not the admin's. A cancelled
    reservation keeps its reference, so this is how a caller frees one to book under again.

    Who may change a reservation is who may cancel it: whoever took it, or an `ORG_ADMIN`. A
    `UNIT_ADMIN` that did not make it gets a 403. Sending the reference the reservation already has
    changes nothing and leaves no entry on the change feed; a real change leaves one.

    Args:
        resource_id (int):
        reservation_id (int):
        idempotency_key (str | Unset):
        body (ReservationUpdate): What the caller may change about a reservation it already holds:
            its reference, for now. The window is what the conflict check and the idempotency
            fingerprint are built on, so moving it is a cancel and a new booking. Any other field is
            refused with a 422 rather than ignored.

    Raises:
        errors.UnexpectedStatus: If the server returns an undocumented status code and Client.raise_on_unexpected_status is True.
        httpx.TimeoutException: If the request takes longer than Client.timeout.

    Returns:
        Response[ErrorResponse | ReservationRefTaken | ReservationResponse]
    """

    kwargs = _get_kwargs(
        resource_id=resource_id,
        reservation_id=reservation_id,
        body=body,
        idempotency_key=idempotency_key,
    )

    response = await client.get_async_httpx_client().request(**kwargs)

    return _build_response(client=client, response=response)


async def asyncio(
    resource_id: int,
    reservation_id: int,
    *,
    client: AuthenticatedClient | Client,
    body: ReservationUpdate,
    idempotency_key: str | Unset = UNSET,
) -> ErrorResponse | ReservationRefTaken | ReservationResponse | None:
    """Change a reservation's external_ref

     Requires `ORG_ADMIN` or `UNIT_ADMIN`. Sets, changes or clears the caller's reference for a
    reservation. Only the reference can change: moving the window is a cancel and a new booking.

    The reference is unique per requester, the same rule as on create, and taking one already on another
    of the requester's reservations is the same 409. When an `ORG_ADMIN` changes a reservation somebody
    else made, the reference is checked against that requester's, not the admin's. A cancelled
    reservation keeps its reference, so this is how a caller frees one to book under again.

    Who may change a reservation is who may cancel it: whoever took it, or an `ORG_ADMIN`. A
    `UNIT_ADMIN` that did not make it gets a 403. Sending the reference the reservation already has
    changes nothing and leaves no entry on the change feed; a real change leaves one.

    Args:
        resource_id (int):
        reservation_id (int):
        idempotency_key (str | Unset):
        body (ReservationUpdate): What the caller may change about a reservation it already holds:
            its reference, for now. The window is what the conflict check and the idempotency
            fingerprint are built on, so moving it is a cancel and a new booking. Any other field is
            refused with a 422 rather than ignored.

    Raises:
        errors.UnexpectedStatus: If the server returns an undocumented status code and Client.raise_on_unexpected_status is True.
        httpx.TimeoutException: If the request takes longer than Client.timeout.

    Returns:
        ErrorResponse | ReservationRefTaken | ReservationResponse
    """

    return (
        await asyncio_detailed(
            resource_id=resource_id,
            reservation_id=reservation_id,
            client=client,
            body=body,
            idempotency_key=idempotency_key,
        )
    ).parsed
