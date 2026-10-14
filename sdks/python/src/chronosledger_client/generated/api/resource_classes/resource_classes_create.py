from http import HTTPStatus
from typing import Any

import httpx

from ... import errors
from ...client import AuthenticatedClient, Client
from ...models.error_response import ErrorResponse
from ...models.resource_class_create import ResourceClassCreate
from ...models.resource_class_response import ResourceClassResponse
from ...types import UNSET, Response, Unset


def _get_kwargs(
    *,
    body: ResourceClassCreate,
    idempotency_key: str | Unset = UNSET,
) -> dict[str, Any]:
    headers: dict[str, Any] = {}
    if not isinstance(idempotency_key, Unset):
        headers["Idempotency-Key"] = idempotency_key

    _kwargs: dict[str, Any] = {
        "method": "post",
        "url": "/api/v1/resource-classes/",
    }

    _kwargs["json"] = body.to_dict()

    headers["Content-Type"] = "application/json"

    _kwargs["headers"] = headers
    return _kwargs


def _parse_response(
    *, client: AuthenticatedClient | Client, response: httpx.Response
) -> ErrorResponse | ResourceClassResponse | None:
    if response.status_code == 201:
        response_201 = ResourceClassResponse.from_dict(response.json())

        return response_201

    if response.status_code == 401:
        response_401 = ErrorResponse.from_dict(response.json())

        return response_401

    if response.status_code == 403:
        response_403 = ErrorResponse.from_dict(response.json())

        return response_403

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
) -> Response[ErrorResponse | ResourceClassResponse]:
    return Response(
        status_code=HTTPStatus(response.status_code),
        content=response.content,
        headers=response.headers,
        parsed=_parse_response(client=client, response=response),
    )


def sync_detailed(
    *,
    client: AuthenticatedClient | Client,
    body: ResourceClassCreate,
    idempotency_key: str | Unset = UNSET,
) -> Response[ErrorResponse | ResourceClassResponse]:
    """Create a resource class

     Requires `ORG_ADMIN`. Adds a kind of resource. The class is a label: resources are filed under it
    and requirements can ask for it, and nothing about how it books differs from any other resource. The
    code is permanent.

    Args:
        idempotency_key (str | Unset):
        body (ResourceClassCreate):

    Raises:
        errors.UnexpectedStatus: If the server returns an undocumented status code and Client.raise_on_unexpected_status is True.
        httpx.TimeoutException: If the request takes longer than Client.timeout.

    Returns:
        Response[ErrorResponse | ResourceClassResponse]
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
    body: ResourceClassCreate,
    idempotency_key: str | Unset = UNSET,
) -> ErrorResponse | ResourceClassResponse | None:
    """Create a resource class

     Requires `ORG_ADMIN`. Adds a kind of resource. The class is a label: resources are filed under it
    and requirements can ask for it, and nothing about how it books differs from any other resource. The
    code is permanent.

    Args:
        idempotency_key (str | Unset):
        body (ResourceClassCreate):

    Raises:
        errors.UnexpectedStatus: If the server returns an undocumented status code and Client.raise_on_unexpected_status is True.
        httpx.TimeoutException: If the request takes longer than Client.timeout.

    Returns:
        ErrorResponse | ResourceClassResponse
    """

    return sync_detailed(
        client=client,
        body=body,
        idempotency_key=idempotency_key,
    ).parsed


async def asyncio_detailed(
    *,
    client: AuthenticatedClient | Client,
    body: ResourceClassCreate,
    idempotency_key: str | Unset = UNSET,
) -> Response[ErrorResponse | ResourceClassResponse]:
    """Create a resource class

     Requires `ORG_ADMIN`. Adds a kind of resource. The class is a label: resources are filed under it
    and requirements can ask for it, and nothing about how it books differs from any other resource. The
    code is permanent.

    Args:
        idempotency_key (str | Unset):
        body (ResourceClassCreate):

    Raises:
        errors.UnexpectedStatus: If the server returns an undocumented status code and Client.raise_on_unexpected_status is True.
        httpx.TimeoutException: If the request takes longer than Client.timeout.

    Returns:
        Response[ErrorResponse | ResourceClassResponse]
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
    body: ResourceClassCreate,
    idempotency_key: str | Unset = UNSET,
) -> ErrorResponse | ResourceClassResponse | None:
    """Create a resource class

     Requires `ORG_ADMIN`. Adds a kind of resource. The class is a label: resources are filed under it
    and requirements can ask for it, and nothing about how it books differs from any other resource. The
    code is permanent.

    Args:
        idempotency_key (str | Unset):
        body (ResourceClassCreate):

    Raises:
        errors.UnexpectedStatus: If the server returns an undocumented status code and Client.raise_on_unexpected_status is True.
        httpx.TimeoutException: If the request takes longer than Client.timeout.

    Returns:
        ErrorResponse | ResourceClassResponse
    """

    return (
        await asyncio_detailed(
            client=client,
            body=body,
            idempotency_key=idempotency_key,
        )
    ).parsed
