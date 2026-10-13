from http import HTTPStatus
from typing import Any

import httpx

from ... import errors
from ...client import AuthenticatedClient, Client
from ...models.annotation_create import AnnotationCreate
from ...models.annotation_response import AnnotationResponse
from ...models.error_response import ErrorResponse
from ...types import UNSET, Response, Unset


def _get_kwargs(
    *,
    body: AnnotationCreate,
    idempotency_key: str | Unset = UNSET,
) -> dict[str, Any]:
    headers: dict[str, Any] = {}
    if not isinstance(idempotency_key, Unset):
        headers["Idempotency-Key"] = idempotency_key

    _kwargs: dict[str, Any] = {
        "method": "post",
        "url": "/api/v1/attendance/annotations",
    }

    _kwargs["json"] = body.to_dict()

    headers["Content-Type"] = "application/json"

    _kwargs["headers"] = headers
    return _kwargs


def _parse_response(
    *, client: AuthenticatedClient | Client, response: httpx.Response
) -> AnnotationResponse | ErrorResponse | None:
    if response.status_code == 200:
        response_200 = AnnotationResponse.from_dict(response.json())

        return response_200

    if response.status_code == 403:
        response_403 = ErrorResponse.from_dict(response.json())

        return response_403

    if response.status_code == 404:
        response_404 = ErrorResponse.from_dict(response.json())

        return response_404

    if client.raise_on_unexpected_status:
        raise errors.UnexpectedStatus(response.status_code, response.content)
    else:
        return None


def _build_response(
    *, client: AuthenticatedClient | Client, response: httpx.Response
) -> Response[AnnotationResponse | ErrorResponse]:
    return Response(
        status_code=HTTPStatus(response.status_code),
        content=response.content,
        headers=response.headers,
        parsed=_parse_response(client=client, response=response),
    )


def sync_detailed(
    *,
    client: AuthenticatedClient | Client,
    body: AnnotationCreate,
    idempotency_key: str | Unset = UNSET,
) -> Response[AnnotationResponse | ErrorResponse]:
    """Create a ledger annotation

     Freeform notes about a session: lab issues, late starts, a handover. Restricted to whoever runs it,
    meaning the assigned lead, the substitute, an organization admin, or a unit admin inside that unit.

    Args:
        idempotency_key (str | Unset):
        body (AnnotationCreate):

    Raises:
        errors.UnexpectedStatus: If the server returns an undocumented status code and Client.raise_on_unexpected_status is True.
        httpx.TimeoutException: If the request takes longer than Client.timeout.

    Returns:
        Response[AnnotationResponse | ErrorResponse]
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
    body: AnnotationCreate,
    idempotency_key: str | Unset = UNSET,
) -> AnnotationResponse | ErrorResponse | None:
    """Create a ledger annotation

     Freeform notes about a session: lab issues, late starts, a handover. Restricted to whoever runs it,
    meaning the assigned lead, the substitute, an organization admin, or a unit admin inside that unit.

    Args:
        idempotency_key (str | Unset):
        body (AnnotationCreate):

    Raises:
        errors.UnexpectedStatus: If the server returns an undocumented status code and Client.raise_on_unexpected_status is True.
        httpx.TimeoutException: If the request takes longer than Client.timeout.

    Returns:
        AnnotationResponse | ErrorResponse
    """

    return sync_detailed(
        client=client,
        body=body,
        idempotency_key=idempotency_key,
    ).parsed


async def asyncio_detailed(
    *,
    client: AuthenticatedClient | Client,
    body: AnnotationCreate,
    idempotency_key: str | Unset = UNSET,
) -> Response[AnnotationResponse | ErrorResponse]:
    """Create a ledger annotation

     Freeform notes about a session: lab issues, late starts, a handover. Restricted to whoever runs it,
    meaning the assigned lead, the substitute, an organization admin, or a unit admin inside that unit.

    Args:
        idempotency_key (str | Unset):
        body (AnnotationCreate):

    Raises:
        errors.UnexpectedStatus: If the server returns an undocumented status code and Client.raise_on_unexpected_status is True.
        httpx.TimeoutException: If the request takes longer than Client.timeout.

    Returns:
        Response[AnnotationResponse | ErrorResponse]
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
    body: AnnotationCreate,
    idempotency_key: str | Unset = UNSET,
) -> AnnotationResponse | ErrorResponse | None:
    """Create a ledger annotation

     Freeform notes about a session: lab issues, late starts, a handover. Restricted to whoever runs it,
    meaning the assigned lead, the substitute, an organization admin, or a unit admin inside that unit.

    Args:
        idempotency_key (str | Unset):
        body (AnnotationCreate):

    Raises:
        errors.UnexpectedStatus: If the server returns an undocumented status code and Client.raise_on_unexpected_status is True.
        httpx.TimeoutException: If the request takes longer than Client.timeout.

    Returns:
        AnnotationResponse | ErrorResponse
    """

    return (
        await asyncio_detailed(
            client=client,
            body=body,
            idempotency_key=idempotency_key,
        )
    ).parsed
