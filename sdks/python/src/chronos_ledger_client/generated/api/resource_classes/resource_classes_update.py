from http import HTTPStatus
from typing import Any
from urllib.parse import quote

import httpx

from ... import errors
from ...client import AuthenticatedClient, Client
from ...models.error_response import ErrorResponse
from ...models.resource_class_response import ResourceClassResponse
from ...models.resource_class_update import ResourceClassUpdate
from ...types import UNSET, Response, Unset


def _get_kwargs(
    code: str,
    *,
    body: ResourceClassUpdate,
    idempotency_key: str | Unset = UNSET,
) -> dict[str, Any]:
    headers: dict[str, Any] = {}
    if not isinstance(idempotency_key, Unset):
        headers["Idempotency-Key"] = idempotency_key

    _kwargs: dict[str, Any] = {
        "method": "patch",
        "url": "/api/v1/resource-classes/{code}".format(
            code=quote(str(code), safe=""),
        ),
    }

    _kwargs["json"] = body.to_dict()

    headers["Content-Type"] = "application/json"

    _kwargs["headers"] = headers
    return _kwargs


def _parse_response(
    *, client: AuthenticatedClient | Client, response: httpx.Response
) -> ErrorResponse | ResourceClassResponse | None:
    if response.status_code == 200:
        response_200 = ResourceClassResponse.from_dict(response.json())

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
    code: str,
    *,
    client: AuthenticatedClient | Client,
    body: ResourceClassUpdate,
    idempotency_key: str | Unset = UNSET,
) -> Response[ErrorResponse | ResourceClassResponse]:
    """Rename or switch a class off

     Requires `ORG_ADMIN`. Renaming is allowed for every class. Deactivating stops new resources and new
    requirements naming the class and leaves the ones that already do as they are; deactivating `ROOM`
    or `PERSON` is a 409 with `RESOURCE_CLASS_PROTECTED`.

    Args:
        code (str):
        idempotency_key (str | Unset):
        body (ResourceClassUpdate): Every field is optional and one left out is left alone.
            Neither can be null. code is absent on purpose: it never changes.

    Raises:
        errors.UnexpectedStatus: If the server returns an undocumented status code and Client.raise_on_unexpected_status is True.
        httpx.TimeoutException: If the request takes longer than Client.timeout.

    Returns:
        Response[ErrorResponse | ResourceClassResponse]
    """

    kwargs = _get_kwargs(
        code=code,
        body=body,
        idempotency_key=idempotency_key,
    )

    response = client.get_httpx_client().request(
        **kwargs,
    )

    return _build_response(client=client, response=response)


def sync(
    code: str,
    *,
    client: AuthenticatedClient | Client,
    body: ResourceClassUpdate,
    idempotency_key: str | Unset = UNSET,
) -> ErrorResponse | ResourceClassResponse | None:
    """Rename or switch a class off

     Requires `ORG_ADMIN`. Renaming is allowed for every class. Deactivating stops new resources and new
    requirements naming the class and leaves the ones that already do as they are; deactivating `ROOM`
    or `PERSON` is a 409 with `RESOURCE_CLASS_PROTECTED`.

    Args:
        code (str):
        idempotency_key (str | Unset):
        body (ResourceClassUpdate): Every field is optional and one left out is left alone.
            Neither can be null. code is absent on purpose: it never changes.

    Raises:
        errors.UnexpectedStatus: If the server returns an undocumented status code and Client.raise_on_unexpected_status is True.
        httpx.TimeoutException: If the request takes longer than Client.timeout.

    Returns:
        ErrorResponse | ResourceClassResponse
    """

    return sync_detailed(
        code=code,
        client=client,
        body=body,
        idempotency_key=idempotency_key,
    ).parsed


async def asyncio_detailed(
    code: str,
    *,
    client: AuthenticatedClient | Client,
    body: ResourceClassUpdate,
    idempotency_key: str | Unset = UNSET,
) -> Response[ErrorResponse | ResourceClassResponse]:
    """Rename or switch a class off

     Requires `ORG_ADMIN`. Renaming is allowed for every class. Deactivating stops new resources and new
    requirements naming the class and leaves the ones that already do as they are; deactivating `ROOM`
    or `PERSON` is a 409 with `RESOURCE_CLASS_PROTECTED`.

    Args:
        code (str):
        idempotency_key (str | Unset):
        body (ResourceClassUpdate): Every field is optional and one left out is left alone.
            Neither can be null. code is absent on purpose: it never changes.

    Raises:
        errors.UnexpectedStatus: If the server returns an undocumented status code and Client.raise_on_unexpected_status is True.
        httpx.TimeoutException: If the request takes longer than Client.timeout.

    Returns:
        Response[ErrorResponse | ResourceClassResponse]
    """

    kwargs = _get_kwargs(
        code=code,
        body=body,
        idempotency_key=idempotency_key,
    )

    response = await client.get_async_httpx_client().request(**kwargs)

    return _build_response(client=client, response=response)


async def asyncio(
    code: str,
    *,
    client: AuthenticatedClient | Client,
    body: ResourceClassUpdate,
    idempotency_key: str | Unset = UNSET,
) -> ErrorResponse | ResourceClassResponse | None:
    """Rename or switch a class off

     Requires `ORG_ADMIN`. Renaming is allowed for every class. Deactivating stops new resources and new
    requirements naming the class and leaves the ones that already do as they are; deactivating `ROOM`
    or `PERSON` is a 409 with `RESOURCE_CLASS_PROTECTED`.

    Args:
        code (str):
        idempotency_key (str | Unset):
        body (ResourceClassUpdate): Every field is optional and one left out is left alone.
            Neither can be null. code is absent on purpose: it never changes.

    Raises:
        errors.UnexpectedStatus: If the server returns an undocumented status code and Client.raise_on_unexpected_status is True.
        httpx.TimeoutException: If the request takes longer than Client.timeout.

    Returns:
        ErrorResponse | ResourceClassResponse
    """

    return (
        await asyncio_detailed(
            code=code,
            client=client,
            body=body,
            idempotency_key=idempotency_key,
        )
    ).parsed
