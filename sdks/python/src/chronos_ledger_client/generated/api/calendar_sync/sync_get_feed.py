from http import HTTPStatus
from typing import Any
from urllib.parse import quote

import httpx

from ... import errors
from ...client import AuthenticatedClient, Client
from ...models.error_response import ErrorResponse
from ...types import Response


def _get_kwargs(
    feed_token: str,
) -> dict[str, Any]:

    _kwargs: dict[str, Any] = {
        "method": "get",
        "url": "/api/v1/sync/user-feed/{feed_token}.ics".format(
            feed_token=quote(str(feed_token), safe=""),
        ),
    }

    return _kwargs


def _parse_response(
    *, client: AuthenticatedClient | Client, response: httpx.Response
) -> ErrorResponse | str | None:
    if response.status_code == 200:
        response_200 = response.text
        return response_200

    if response.status_code == 404:
        response_404 = ErrorResponse.from_dict(response.json())

        return response_404

    if response.status_code == 429:
        response_429 = ErrorResponse.from_dict(response.json())

        return response_429

    if client.raise_on_unexpected_status:
        raise errors.UnexpectedStatus(response.status_code, response.content)
    else:
        return None


def _build_response(
    *, client: AuthenticatedClient | Client, response: httpx.Response
) -> Response[ErrorResponse | str]:
    return Response(
        status_code=HTTPStatus(response.status_code),
        content=response.content,
        headers=response.headers,
        parsed=_parse_response(client=client, response=response),
    )


def sync_detailed(
    feed_token: str,
    *,
    client: AuthenticatedClient | Client,
) -> Response[ErrorResponse | str]:
    """iCalendar feed for a user (rolling 37-day window)

     Subscribe this URL directly in Google Calendar, Apple Calendar, or Outlook. Returns standard
    iCalendar (text/calendar) content. Staff feed includes all sessions where they are active or
    substitute lead. Member feed includes all registered activities. Timed sessions are written as UTC
    instants (DTSTART and DTEND end in Z), converted from the organization's wall clock through
    ORG_TIMEZONE, so a subscriber reading the feed from anywhere sees the session at the moment it
    happens. An entry with no window of its own is an all-day date and carries no zone, because a date
    reads the same everywhere. That is an ad-hoc day nobody gave a time to, or a day generated before
    the ledger carried its own window.

    Args:
        feed_token (str):

    Raises:
        errors.UnexpectedStatus: If the server returns an undocumented status code and Client.raise_on_unexpected_status is True.
        httpx.TimeoutException: If the request takes longer than Client.timeout.

    Returns:
        Response[ErrorResponse | str]
    """

    kwargs = _get_kwargs(
        feed_token=feed_token,
    )

    response = client.get_httpx_client().request(
        **kwargs,
    )

    return _build_response(client=client, response=response)


def sync(
    feed_token: str,
    *,
    client: AuthenticatedClient | Client,
) -> ErrorResponse | str | None:
    """iCalendar feed for a user (rolling 37-day window)

     Subscribe this URL directly in Google Calendar, Apple Calendar, or Outlook. Returns standard
    iCalendar (text/calendar) content. Staff feed includes all sessions where they are active or
    substitute lead. Member feed includes all registered activities. Timed sessions are written as UTC
    instants (DTSTART and DTEND end in Z), converted from the organization's wall clock through
    ORG_TIMEZONE, so a subscriber reading the feed from anywhere sees the session at the moment it
    happens. An entry with no window of its own is an all-day date and carries no zone, because a date
    reads the same everywhere. That is an ad-hoc day nobody gave a time to, or a day generated before
    the ledger carried its own window.

    Args:
        feed_token (str):

    Raises:
        errors.UnexpectedStatus: If the server returns an undocumented status code and Client.raise_on_unexpected_status is True.
        httpx.TimeoutException: If the request takes longer than Client.timeout.

    Returns:
        ErrorResponse | str
    """

    return sync_detailed(
        feed_token=feed_token,
        client=client,
    ).parsed


async def asyncio_detailed(
    feed_token: str,
    *,
    client: AuthenticatedClient | Client,
) -> Response[ErrorResponse | str]:
    """iCalendar feed for a user (rolling 37-day window)

     Subscribe this URL directly in Google Calendar, Apple Calendar, or Outlook. Returns standard
    iCalendar (text/calendar) content. Staff feed includes all sessions where they are active or
    substitute lead. Member feed includes all registered activities. Timed sessions are written as UTC
    instants (DTSTART and DTEND end in Z), converted from the organization's wall clock through
    ORG_TIMEZONE, so a subscriber reading the feed from anywhere sees the session at the moment it
    happens. An entry with no window of its own is an all-day date and carries no zone, because a date
    reads the same everywhere. That is an ad-hoc day nobody gave a time to, or a day generated before
    the ledger carried its own window.

    Args:
        feed_token (str):

    Raises:
        errors.UnexpectedStatus: If the server returns an undocumented status code and Client.raise_on_unexpected_status is True.
        httpx.TimeoutException: If the request takes longer than Client.timeout.

    Returns:
        Response[ErrorResponse | str]
    """

    kwargs = _get_kwargs(
        feed_token=feed_token,
    )

    response = await client.get_async_httpx_client().request(**kwargs)

    return _build_response(client=client, response=response)


async def asyncio(
    feed_token: str,
    *,
    client: AuthenticatedClient | Client,
) -> ErrorResponse | str | None:
    """iCalendar feed for a user (rolling 37-day window)

     Subscribe this URL directly in Google Calendar, Apple Calendar, or Outlook. Returns standard
    iCalendar (text/calendar) content. Staff feed includes all sessions where they are active or
    substitute lead. Member feed includes all registered activities. Timed sessions are written as UTC
    instants (DTSTART and DTEND end in Z), converted from the organization's wall clock through
    ORG_TIMEZONE, so a subscriber reading the feed from anywhere sees the session at the moment it
    happens. An entry with no window of its own is an all-day date and carries no zone, because a date
    reads the same everywhere. That is an ad-hoc day nobody gave a time to, or a day generated before
    the ledger carried its own window.

    Args:
        feed_token (str):

    Raises:
        errors.UnexpectedStatus: If the server returns an undocumented status code and Client.raise_on_unexpected_status is True.
        httpx.TimeoutException: If the request takes longer than Client.timeout.

    Returns:
        ErrorResponse | str
    """

    return (
        await asyncio_detailed(
            feed_token=feed_token,
            client=client,
        )
    ).parsed
