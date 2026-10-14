from http import HTTPStatus
from typing import Any, cast
from urllib.parse import quote

import httpx

from ... import errors
from ...client import AuthenticatedClient, Client
from ...models.error_response import ErrorResponse
from ...types import UNSET, Response, Unset


def _get_kwargs(
    code: str,
    *,
    idempotency_key: str | Unset = UNSET,
) -> dict[str, Any]:
    headers: dict[str, Any] = {}
    if not isinstance(idempotency_key, Unset):
        headers["Idempotency-Key"] = idempotency_key

    _kwargs: dict[str, Any] = {
        "method": "delete",
        "url": "/api/v1/resource-classes/{code}".format(
            code=quote(str(code), safe=""),
        ),
    }

    _kwargs["headers"] = headers
    return _kwargs


def _parse_response(
    *, client: AuthenticatedClient | Client, response: httpx.Response
) -> Any | ErrorResponse | None:
    if response.status_code == 204:
        response_204 = cast(Any, None)
        return response_204

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

    if client.raise_on_unexpected_status:
        raise errors.UnexpectedStatus(response.status_code, response.content)
    else:
        return None


def _build_response(
    *, client: AuthenticatedClient | Client, response: httpx.Response
) -> Response[Any | ErrorResponse]:
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
    idempotency_key: str | Unset = UNSET,
) -> Response[Any | ErrorResponse]:
    """Delete a class nothing uses

     Requires `ORG_ADMIN`. Refused with 409 `RESOURCE_CLASS_PROTECTED` for `ROOM` and `PERSON`, and with
    409 `RESOURCE_CLASS_IN_USE` while any resource has the class or any requirement asks for it, whether
    the class is active or not. Switch it off instead to stop new uses and keep the old.

    Args:
        code (str):
        idempotency_key (str | Unset):

    Raises:
        errors.UnexpectedStatus: If the server returns an undocumented status code and Client.raise_on_unexpected_status is True.
        httpx.TimeoutException: If the request takes longer than Client.timeout.

    Returns:
        Response[Any | ErrorResponse]
    """

    kwargs = _get_kwargs(
        code=code,
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
    idempotency_key: str | Unset = UNSET,
) -> Any | ErrorResponse | None:
    """Delete a class nothing uses

     Requires `ORG_ADMIN`. Refused with 409 `RESOURCE_CLASS_PROTECTED` for `ROOM` and `PERSON`, and with
    409 `RESOURCE_CLASS_IN_USE` while any resource has the class or any requirement asks for it, whether
    the class is active or not. Switch it off instead to stop new uses and keep the old.

    Args:
        code (str):
        idempotency_key (str | Unset):

    Raises:
        errors.UnexpectedStatus: If the server returns an undocumented status code and Client.raise_on_unexpected_status is True.
        httpx.TimeoutException: If the request takes longer than Client.timeout.

    Returns:
        Any | ErrorResponse
    """

    return sync_detailed(
        code=code,
        client=client,
        idempotency_key=idempotency_key,
    ).parsed


async def asyncio_detailed(
    code: str,
    *,
    client: AuthenticatedClient | Client,
    idempotency_key: str | Unset = UNSET,
) -> Response[Any | ErrorResponse]:
    """Delete a class nothing uses

     Requires `ORG_ADMIN`. Refused with 409 `RESOURCE_CLASS_PROTECTED` for `ROOM` and `PERSON`, and with
    409 `RESOURCE_CLASS_IN_USE` while any resource has the class or any requirement asks for it, whether
    the class is active or not. Switch it off instead to stop new uses and keep the old.

    Args:
        code (str):
        idempotency_key (str | Unset):

    Raises:
        errors.UnexpectedStatus: If the server returns an undocumented status code and Client.raise_on_unexpected_status is True.
        httpx.TimeoutException: If the request takes longer than Client.timeout.

    Returns:
        Response[Any | ErrorResponse]
    """

    kwargs = _get_kwargs(
        code=code,
        idempotency_key=idempotency_key,
    )

    response = await client.get_async_httpx_client().request(**kwargs)

    return _build_response(client=client, response=response)


async def asyncio(
    code: str,
    *,
    client: AuthenticatedClient | Client,
    idempotency_key: str | Unset = UNSET,
) -> Any | ErrorResponse | None:
    """Delete a class nothing uses

     Requires `ORG_ADMIN`. Refused with 409 `RESOURCE_CLASS_PROTECTED` for `ROOM` and `PERSON`, and with
    409 `RESOURCE_CLASS_IN_USE` while any resource has the class or any requirement asks for it, whether
    the class is active or not. Switch it off instead to stop new uses and keep the old.

    Args:
        code (str):
        idempotency_key (str | Unset):

    Raises:
        errors.UnexpectedStatus: If the server returns an undocumented status code and Client.raise_on_unexpected_status is True.
        httpx.TimeoutException: If the request takes longer than Client.timeout.

    Returns:
        Any | ErrorResponse
    """

    return (
        await asyncio_detailed(
            code=code,
            client=client,
            idempotency_key=idempotency_key,
        )
    ).parsed
