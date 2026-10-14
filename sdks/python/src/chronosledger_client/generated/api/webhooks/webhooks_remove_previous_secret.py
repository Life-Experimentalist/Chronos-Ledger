from http import HTTPStatus
from typing import Any, cast
from urllib.parse import quote

import httpx

from ... import errors
from ...client import AuthenticatedClient, Client
from ...models.error_response import ErrorResponse
from ...types import UNSET, Response, Unset


def _get_kwargs(
    subscription_id: int,
    *,
    idempotency_key: str | Unset = UNSET,
) -> dict[str, Any]:
    headers: dict[str, Any] = {}
    if not isinstance(idempotency_key, Unset):
        headers["Idempotency-Key"] = idempotency_key

    _kwargs: dict[str, Any] = {
        "method": "delete",
        "url": "/api/v1/webhooks/{subscription_id}/previous-secret".format(
            subscription_id=quote(str(subscription_id), safe=""),
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
    subscription_id: int,
    *,
    client: AuthenticatedClient | Client,
    idempotency_key: str | Unset = UNSET,
) -> Response[Any | ErrorResponse]:
    """Stop signing with the previous secret

     Requires `ORG_ADMIN`; an API key needs `webhooks:write`. For when every receiver has moved to the
    new secret before the 24 hours are up. Nothing to remove is not an error.

    Args:
        subscription_id (int):
        idempotency_key (str | Unset):

    Raises:
        errors.UnexpectedStatus: If the server returns an undocumented status code and Client.raise_on_unexpected_status is True.
        httpx.TimeoutException: If the request takes longer than Client.timeout.

    Returns:
        Response[Any | ErrorResponse]
    """

    kwargs = _get_kwargs(
        subscription_id=subscription_id,
        idempotency_key=idempotency_key,
    )

    response = client.get_httpx_client().request(
        **kwargs,
    )

    return _build_response(client=client, response=response)


def sync(
    subscription_id: int,
    *,
    client: AuthenticatedClient | Client,
    idempotency_key: str | Unset = UNSET,
) -> Any | ErrorResponse | None:
    """Stop signing with the previous secret

     Requires `ORG_ADMIN`; an API key needs `webhooks:write`. For when every receiver has moved to the
    new secret before the 24 hours are up. Nothing to remove is not an error.

    Args:
        subscription_id (int):
        idempotency_key (str | Unset):

    Raises:
        errors.UnexpectedStatus: If the server returns an undocumented status code and Client.raise_on_unexpected_status is True.
        httpx.TimeoutException: If the request takes longer than Client.timeout.

    Returns:
        Any | ErrorResponse
    """

    return sync_detailed(
        subscription_id=subscription_id,
        client=client,
        idempotency_key=idempotency_key,
    ).parsed


async def asyncio_detailed(
    subscription_id: int,
    *,
    client: AuthenticatedClient | Client,
    idempotency_key: str | Unset = UNSET,
) -> Response[Any | ErrorResponse]:
    """Stop signing with the previous secret

     Requires `ORG_ADMIN`; an API key needs `webhooks:write`. For when every receiver has moved to the
    new secret before the 24 hours are up. Nothing to remove is not an error.

    Args:
        subscription_id (int):
        idempotency_key (str | Unset):

    Raises:
        errors.UnexpectedStatus: If the server returns an undocumented status code and Client.raise_on_unexpected_status is True.
        httpx.TimeoutException: If the request takes longer than Client.timeout.

    Returns:
        Response[Any | ErrorResponse]
    """

    kwargs = _get_kwargs(
        subscription_id=subscription_id,
        idempotency_key=idempotency_key,
    )

    response = await client.get_async_httpx_client().request(**kwargs)

    return _build_response(client=client, response=response)


async def asyncio(
    subscription_id: int,
    *,
    client: AuthenticatedClient | Client,
    idempotency_key: str | Unset = UNSET,
) -> Any | ErrorResponse | None:
    """Stop signing with the previous secret

     Requires `ORG_ADMIN`; an API key needs `webhooks:write`. For when every receiver has moved to the
    new secret before the 24 hours are up. Nothing to remove is not an error.

    Args:
        subscription_id (int):
        idempotency_key (str | Unset):

    Raises:
        errors.UnexpectedStatus: If the server returns an undocumented status code and Client.raise_on_unexpected_status is True.
        httpx.TimeoutException: If the request takes longer than Client.timeout.

    Returns:
        Any | ErrorResponse
    """

    return (
        await asyncio_detailed(
            subscription_id=subscription_id,
            client=client,
            idempotency_key=idempotency_key,
        )
    ).parsed
