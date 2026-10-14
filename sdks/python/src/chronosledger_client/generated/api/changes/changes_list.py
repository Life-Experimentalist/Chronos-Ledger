from http import HTTPStatus
from typing import Any

import httpx

from ... import errors
from ...client import AuthenticatedClient, Client
from ...models.change_feed import ChangeFeed
from ...models.error_response import ErrorResponse
from ...types import UNSET, Response, Unset


def _get_kwargs(
    *,
    since: int | Unset = 0,
    limit: int | Unset = 200,
    full: bool | Unset = False,
) -> dict[str, Any]:

    params: dict[str, Any] = {}

    params["since"] = since

    params["limit"] = limit

    params["full"] = full

    params = {k: v for k, v in params.items() if v is not UNSET and v is not None}

    _kwargs: dict[str, Any] = {
        "method": "get",
        "url": "/api/v1/changes/",
        "params": params,
    }

    return _kwargs


def _parse_response(
    *, client: AuthenticatedClient | Client, response: httpx.Response
) -> ChangeFeed | ErrorResponse | None:
    if response.status_code == 200:
        response_200 = ChangeFeed.from_dict(response.json())

        return response_200

    if response.status_code == 401:
        response_401 = ErrorResponse.from_dict(response.json())

        return response_401

    if response.status_code == 403:
        response_403 = ErrorResponse.from_dict(response.json())

        return response_403

    if response.status_code == 422:
        response_422 = ErrorResponse.from_dict(response.json())

        return response_422

    if response.status_code == 503:
        response_503 = ErrorResponse.from_dict(response.json())

        return response_503

    if client.raise_on_unexpected_status:
        raise errors.UnexpectedStatus(response.status_code, response.content)
    else:
        return None


def _build_response(
    *, client: AuthenticatedClient | Client, response: httpx.Response
) -> Response[ChangeFeed | ErrorResponse]:
    return Response(
        status_code=HTTPStatus(response.status_code),
        content=response.content,
        headers=response.headers,
        parsed=_parse_response(client=client, response=response),
    )


def sync_detailed(
    *,
    client: AuthenticatedClient | Client,
    since: int | Unset = 0,
    limit: int | Unset = 200,
    full: bool | Unset = False,
) -> Response[ChangeFeed | ErrorResponse]:
    """What has changed about the rooms and the bookings

     Requires `ORG_ADMIN`; an API key needs `changes:read`. For a system that keeps its own copy of the
    rooms and the bookings: the websocket cannot tell it anything, because those notices go to a signed-
    in socket and a service behind another firewall has none, and re-reading every room on a timer costs
    the building rather than the change.

    One entry per row, not one per change. A room renamed to Bedroom and then to Living Room is one
    entry saying Living Room, because a consumer catching up wants where things ended and not the walk.
    `full=true` returns the walk: every marker, oldest first, with no row state.

    Send `next_cursor` back as `since`. An entry can arrive twice, after a crash between a write and the
    poll that read it, or because a row changed again while the page was being built; applying an entry
    is replacing a row with what the row already says, so no bookkeeping is needed for that.

    An entry can also be missed, which is the one thing to plan around. The cursor is the marker's own
    id, handed out when the row is inserted and not when it commits, so two writes that commit in the
    other order leave a gap: a poll that reads the later id and stores it does not come back for the
    earlier one. So re-read the rooms and the bookings in full on a slow timer. That is needed anyway,
    because the feed records only from the moment it was switched on.

    A page as long as `limit` means there is probably more, so poll again rather than waiting for the
    timer.

    The role is higher than reading the rooms takes because a booking carries what it is for, which the
    availability calendar withholds from everyone but the account that made it. This hands the booking
    over whole, so it sits where the audit log sits.

    Args:
        since (int | Unset):  Default: 0.
        limit (int | Unset):  Default: 200.
        full (bool | Unset):  Default: False.

    Raises:
        errors.UnexpectedStatus: If the server returns an undocumented status code and Client.raise_on_unexpected_status is True.
        httpx.TimeoutException: If the request takes longer than Client.timeout.

    Returns:
        Response[ChangeFeed | ErrorResponse]
    """

    kwargs = _get_kwargs(
        since=since,
        limit=limit,
        full=full,
    )

    response = client.get_httpx_client().request(
        **kwargs,
    )

    return _build_response(client=client, response=response)


def sync(
    *,
    client: AuthenticatedClient | Client,
    since: int | Unset = 0,
    limit: int | Unset = 200,
    full: bool | Unset = False,
) -> ChangeFeed | ErrorResponse | None:
    """What has changed about the rooms and the bookings

     Requires `ORG_ADMIN`; an API key needs `changes:read`. For a system that keeps its own copy of the
    rooms and the bookings: the websocket cannot tell it anything, because those notices go to a signed-
    in socket and a service behind another firewall has none, and re-reading every room on a timer costs
    the building rather than the change.

    One entry per row, not one per change. A room renamed to Bedroom and then to Living Room is one
    entry saying Living Room, because a consumer catching up wants where things ended and not the walk.
    `full=true` returns the walk: every marker, oldest first, with no row state.

    Send `next_cursor` back as `since`. An entry can arrive twice, after a crash between a write and the
    poll that read it, or because a row changed again while the page was being built; applying an entry
    is replacing a row with what the row already says, so no bookkeeping is needed for that.

    An entry can also be missed, which is the one thing to plan around. The cursor is the marker's own
    id, handed out when the row is inserted and not when it commits, so two writes that commit in the
    other order leave a gap: a poll that reads the later id and stores it does not come back for the
    earlier one. So re-read the rooms and the bookings in full on a slow timer. That is needed anyway,
    because the feed records only from the moment it was switched on.

    A page as long as `limit` means there is probably more, so poll again rather than waiting for the
    timer.

    The role is higher than reading the rooms takes because a booking carries what it is for, which the
    availability calendar withholds from everyone but the account that made it. This hands the booking
    over whole, so it sits where the audit log sits.

    Args:
        since (int | Unset):  Default: 0.
        limit (int | Unset):  Default: 200.
        full (bool | Unset):  Default: False.

    Raises:
        errors.UnexpectedStatus: If the server returns an undocumented status code and Client.raise_on_unexpected_status is True.
        httpx.TimeoutException: If the request takes longer than Client.timeout.

    Returns:
        ChangeFeed | ErrorResponse
    """

    return sync_detailed(
        client=client,
        since=since,
        limit=limit,
        full=full,
    ).parsed


async def asyncio_detailed(
    *,
    client: AuthenticatedClient | Client,
    since: int | Unset = 0,
    limit: int | Unset = 200,
    full: bool | Unset = False,
) -> Response[ChangeFeed | ErrorResponse]:
    """What has changed about the rooms and the bookings

     Requires `ORG_ADMIN`; an API key needs `changes:read`. For a system that keeps its own copy of the
    rooms and the bookings: the websocket cannot tell it anything, because those notices go to a signed-
    in socket and a service behind another firewall has none, and re-reading every room on a timer costs
    the building rather than the change.

    One entry per row, not one per change. A room renamed to Bedroom and then to Living Room is one
    entry saying Living Room, because a consumer catching up wants where things ended and not the walk.
    `full=true` returns the walk: every marker, oldest first, with no row state.

    Send `next_cursor` back as `since`. An entry can arrive twice, after a crash between a write and the
    poll that read it, or because a row changed again while the page was being built; applying an entry
    is replacing a row with what the row already says, so no bookkeeping is needed for that.

    An entry can also be missed, which is the one thing to plan around. The cursor is the marker's own
    id, handed out when the row is inserted and not when it commits, so two writes that commit in the
    other order leave a gap: a poll that reads the later id and stores it does not come back for the
    earlier one. So re-read the rooms and the bookings in full on a slow timer. That is needed anyway,
    because the feed records only from the moment it was switched on.

    A page as long as `limit` means there is probably more, so poll again rather than waiting for the
    timer.

    The role is higher than reading the rooms takes because a booking carries what it is for, which the
    availability calendar withholds from everyone but the account that made it. This hands the booking
    over whole, so it sits where the audit log sits.

    Args:
        since (int | Unset):  Default: 0.
        limit (int | Unset):  Default: 200.
        full (bool | Unset):  Default: False.

    Raises:
        errors.UnexpectedStatus: If the server returns an undocumented status code and Client.raise_on_unexpected_status is True.
        httpx.TimeoutException: If the request takes longer than Client.timeout.

    Returns:
        Response[ChangeFeed | ErrorResponse]
    """

    kwargs = _get_kwargs(
        since=since,
        limit=limit,
        full=full,
    )

    response = await client.get_async_httpx_client().request(**kwargs)

    return _build_response(client=client, response=response)


async def asyncio(
    *,
    client: AuthenticatedClient | Client,
    since: int | Unset = 0,
    limit: int | Unset = 200,
    full: bool | Unset = False,
) -> ChangeFeed | ErrorResponse | None:
    """What has changed about the rooms and the bookings

     Requires `ORG_ADMIN`; an API key needs `changes:read`. For a system that keeps its own copy of the
    rooms and the bookings: the websocket cannot tell it anything, because those notices go to a signed-
    in socket and a service behind another firewall has none, and re-reading every room on a timer costs
    the building rather than the change.

    One entry per row, not one per change. A room renamed to Bedroom and then to Living Room is one
    entry saying Living Room, because a consumer catching up wants where things ended and not the walk.
    `full=true` returns the walk: every marker, oldest first, with no row state.

    Send `next_cursor` back as `since`. An entry can arrive twice, after a crash between a write and the
    poll that read it, or because a row changed again while the page was being built; applying an entry
    is replacing a row with what the row already says, so no bookkeeping is needed for that.

    An entry can also be missed, which is the one thing to plan around. The cursor is the marker's own
    id, handed out when the row is inserted and not when it commits, so two writes that commit in the
    other order leave a gap: a poll that reads the later id and stores it does not come back for the
    earlier one. So re-read the rooms and the bookings in full on a slow timer. That is needed anyway,
    because the feed records only from the moment it was switched on.

    A page as long as `limit` means there is probably more, so poll again rather than waiting for the
    timer.

    The role is higher than reading the rooms takes because a booking carries what it is for, which the
    availability calendar withholds from everyone but the account that made it. This hands the booking
    over whole, so it sits where the audit log sits.

    Args:
        since (int | Unset):  Default: 0.
        limit (int | Unset):  Default: 200.
        full (bool | Unset):  Default: False.

    Raises:
        errors.UnexpectedStatus: If the server returns an undocumented status code and Client.raise_on_unexpected_status is True.
        httpx.TimeoutException: If the request takes longer than Client.timeout.

    Returns:
        ChangeFeed | ErrorResponse
    """

    return (
        await asyncio_detailed(
            client=client,
            since=since,
            limit=limit,
            full=full,
        )
    ).parsed
