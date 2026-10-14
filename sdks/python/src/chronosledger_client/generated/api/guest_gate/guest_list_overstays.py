from http import HTTPStatus
from typing import Any

import httpx

from ... import errors
from ...client import AuthenticatedClient, Client
from ...models.guest_response import GuestResponse
from ...types import Response


def _get_kwargs() -> dict[str, Any]:

    _kwargs: dict[str, Any] = {
        "method": "get",
        "url": "/api/v1/guest/overstays",
    }

    return _kwargs


def _parse_response(
    *, client: AuthenticatedClient | Client, response: httpx.Response
) -> list[GuestResponse] | None:
    if response.status_code == 200:
        response_200 = []
        _response_200 = response.json()
        for response_200_item_data in _response_200:
            response_200_item = GuestResponse.from_dict(response_200_item_data)

            response_200.append(response_200_item)

        return response_200

    if client.raise_on_unexpected_status:
        raise errors.UnexpectedStatus(response.status_code, response.content)
    else:
        return None


def _build_response(
    *, client: AuthenticatedClient | Client, response: httpx.Response
) -> Response[list[GuestResponse]]:
    return Response(
        status_code=HTTPStatus(response.status_code),
        content=response.content,
        headers=response.headers,
        parsed=_parse_response(client=client, response=response),
    )


def sync_detailed(
    *,
    client: AuthenticatedClient | Client,
) -> Response[list[GuestResponse]]:
    """List the approved visits that have run past their end

     Longest over first, which is the desk's other list: who was let in and has not been dealt with
    since. The same reach as the decision, so for an ORG_ADMIN with GUEST_ADMIN_CAN_DECIDE on it is the
    whole organization's. Nothing here has been revoked; each row says the time is up, and a person
    decides whether to extend it or to go and find them. Empty while GUEST_VISIT_LENGTH_MINUTES is 0,
    since then no visit has an end. Unpaginated, as /guest/pending is.

    Raises:
        errors.UnexpectedStatus: If the server returns an undocumented status code and Client.raise_on_unexpected_status is True.
        httpx.TimeoutException: If the request takes longer than Client.timeout.

    Returns:
        Response[list[GuestResponse]]
    """

    kwargs = _get_kwargs()

    response = client.get_httpx_client().request(
        **kwargs,
    )

    return _build_response(client=client, response=response)


def sync(
    *,
    client: AuthenticatedClient | Client,
) -> list[GuestResponse] | None:
    """List the approved visits that have run past their end

     Longest over first, which is the desk's other list: who was let in and has not been dealt with
    since. The same reach as the decision, so for an ORG_ADMIN with GUEST_ADMIN_CAN_DECIDE on it is the
    whole organization's. Nothing here has been revoked; each row says the time is up, and a person
    decides whether to extend it or to go and find them. Empty while GUEST_VISIT_LENGTH_MINUTES is 0,
    since then no visit has an end. Unpaginated, as /guest/pending is.

    Raises:
        errors.UnexpectedStatus: If the server returns an undocumented status code and Client.raise_on_unexpected_status is True.
        httpx.TimeoutException: If the request takes longer than Client.timeout.

    Returns:
        list[GuestResponse]
    """

    return sync_detailed(
        client=client,
    ).parsed


async def asyncio_detailed(
    *,
    client: AuthenticatedClient | Client,
) -> Response[list[GuestResponse]]:
    """List the approved visits that have run past their end

     Longest over first, which is the desk's other list: who was let in and has not been dealt with
    since. The same reach as the decision, so for an ORG_ADMIN with GUEST_ADMIN_CAN_DECIDE on it is the
    whole organization's. Nothing here has been revoked; each row says the time is up, and a person
    decides whether to extend it or to go and find them. Empty while GUEST_VISIT_LENGTH_MINUTES is 0,
    since then no visit has an end. Unpaginated, as /guest/pending is.

    Raises:
        errors.UnexpectedStatus: If the server returns an undocumented status code and Client.raise_on_unexpected_status is True.
        httpx.TimeoutException: If the request takes longer than Client.timeout.

    Returns:
        Response[list[GuestResponse]]
    """

    kwargs = _get_kwargs()

    response = await client.get_async_httpx_client().request(**kwargs)

    return _build_response(client=client, response=response)


async def asyncio(
    *,
    client: AuthenticatedClient | Client,
) -> list[GuestResponse] | None:
    """List the approved visits that have run past their end

     Longest over first, which is the desk's other list: who was let in and has not been dealt with
    since. The same reach as the decision, so for an ORG_ADMIN with GUEST_ADMIN_CAN_DECIDE on it is the
    whole organization's. Nothing here has been revoked; each row says the time is up, and a person
    decides whether to extend it or to go and find them. Empty while GUEST_VISIT_LENGTH_MINUTES is 0,
    since then no visit has an end. Unpaginated, as /guest/pending is.

    Raises:
        errors.UnexpectedStatus: If the server returns an undocumented status code and Client.raise_on_unexpected_status is True.
        httpx.TimeoutException: If the request takes longer than Client.timeout.

    Returns:
        list[GuestResponse]
    """

    return (
        await asyncio_detailed(
            client=client,
        )
    ).parsed
