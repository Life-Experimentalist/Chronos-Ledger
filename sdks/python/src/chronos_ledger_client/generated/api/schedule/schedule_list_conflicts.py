import datetime
from http import HTTPStatus
from typing import Any

import httpx

from ... import errors
from ...client import AuthenticatedClient, Client
from ...models.conflict_report import ConflictReport
from ...models.error_response import ErrorResponse
from ...types import UNSET, Response


def _get_kwargs(
    *,
    from_: datetime.date,
    to: datetime.date,
) -> dict[str, Any]:

    params: dict[str, Any] = {}

    json_from_ = from_.isoformat()
    params["from"] = json_from_

    json_to = to.isoformat()
    params["to"] = json_to

    params = {k: v for k, v in params.items() if v is not UNSET and v is not None}

    _kwargs: dict[str, Any] = {
        "method": "get",
        "url": "/api/v1/schedule/conflicts",
        "params": params,
    }

    return _kwargs


def _parse_response(
    *, client: AuthenticatedClient | Client, response: httpx.Response
) -> ConflictReport | ErrorResponse | None:
    if response.status_code == 200:
        response_200 = ConflictReport.from_dict(response.json())

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

    if client.raise_on_unexpected_status:
        raise errors.UnexpectedStatus(response.status_code, response.content)
    else:
        return None


def _build_response(
    *, client: AuthenticatedClient | Client, response: httpx.Response
) -> Response[ConflictReport | ErrorResponse]:
    return Response(
        status_code=HTTPStatus(response.status_code),
        content=response.content,
        headers=response.headers,
        parsed=_parse_response(client=client, response=response),
    )


def sync_detailed(
    *,
    client: AuthenticatedClient | Client,
    from_: datetime.date,
    to: datetime.date,
) -> Response[ConflictReport | ErrorResponse]:
    """Clashes already in the schedule between two dates

     Reports two rows holding one resource at once, and one member enrolled in two activities that run at
    once. It reads and reports; nothing is refused or changed. Both dates are included. `to` before
    `from`, or a range longer than 92 days, is refused with 422 and code INVALID_VALUE. ORG_ADMIN and
    UNIT_ADMIN only.

    Args:
        from_ (datetime.date):
        to (datetime.date):

    Raises:
        errors.UnexpectedStatus: If the server returns an undocumented status code and Client.raise_on_unexpected_status is True.
        httpx.TimeoutException: If the request takes longer than Client.timeout.

    Returns:
        Response[ConflictReport | ErrorResponse]
    """

    kwargs = _get_kwargs(
        from_=from_,
        to=to,
    )

    response = client.get_httpx_client().request(
        **kwargs,
    )

    return _build_response(client=client, response=response)


def sync(
    *,
    client: AuthenticatedClient | Client,
    from_: datetime.date,
    to: datetime.date,
) -> ConflictReport | ErrorResponse | None:
    """Clashes already in the schedule between two dates

     Reports two rows holding one resource at once, and one member enrolled in two activities that run at
    once. It reads and reports; nothing is refused or changed. Both dates are included. `to` before
    `from`, or a range longer than 92 days, is refused with 422 and code INVALID_VALUE. ORG_ADMIN and
    UNIT_ADMIN only.

    Args:
        from_ (datetime.date):
        to (datetime.date):

    Raises:
        errors.UnexpectedStatus: If the server returns an undocumented status code and Client.raise_on_unexpected_status is True.
        httpx.TimeoutException: If the request takes longer than Client.timeout.

    Returns:
        ConflictReport | ErrorResponse
    """

    return sync_detailed(
        client=client,
        from_=from_,
        to=to,
    ).parsed


async def asyncio_detailed(
    *,
    client: AuthenticatedClient | Client,
    from_: datetime.date,
    to: datetime.date,
) -> Response[ConflictReport | ErrorResponse]:
    """Clashes already in the schedule between two dates

     Reports two rows holding one resource at once, and one member enrolled in two activities that run at
    once. It reads and reports; nothing is refused or changed. Both dates are included. `to` before
    `from`, or a range longer than 92 days, is refused with 422 and code INVALID_VALUE. ORG_ADMIN and
    UNIT_ADMIN only.

    Args:
        from_ (datetime.date):
        to (datetime.date):

    Raises:
        errors.UnexpectedStatus: If the server returns an undocumented status code and Client.raise_on_unexpected_status is True.
        httpx.TimeoutException: If the request takes longer than Client.timeout.

    Returns:
        Response[ConflictReport | ErrorResponse]
    """

    kwargs = _get_kwargs(
        from_=from_,
        to=to,
    )

    response = await client.get_async_httpx_client().request(**kwargs)

    return _build_response(client=client, response=response)


async def asyncio(
    *,
    client: AuthenticatedClient | Client,
    from_: datetime.date,
    to: datetime.date,
) -> ConflictReport | ErrorResponse | None:
    """Clashes already in the schedule between two dates

     Reports two rows holding one resource at once, and one member enrolled in two activities that run at
    once. It reads and reports; nothing is refused or changed. Both dates are included. `to` before
    `from`, or a range longer than 92 days, is refused with 422 and code INVALID_VALUE. ORG_ADMIN and
    UNIT_ADMIN only.

    Args:
        from_ (datetime.date):
        to (datetime.date):

    Raises:
        errors.UnexpectedStatus: If the server returns an undocumented status code and Client.raise_on_unexpected_status is True.
        httpx.TimeoutException: If the request takes longer than Client.timeout.

    Returns:
        ConflictReport | ErrorResponse
    """

    return (
        await asyncio_detailed(
            client=client,
            from_=from_,
            to=to,
        )
    ).parsed
