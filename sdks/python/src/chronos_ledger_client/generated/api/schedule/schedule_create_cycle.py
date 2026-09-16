from http import HTTPStatus
from typing import Any

import httpx

from ... import errors
from ...client import AuthenticatedClient, Client
from ...models.error_response import ErrorResponse
from ...models.planning_cycle_create import PlanningCycleCreate
from ...models.planning_cycle_response import PlanningCycleResponse
from ...types import Response


def _get_kwargs(
    *,
    body: PlanningCycleCreate,
) -> dict[str, Any]:
    headers: dict[str, Any] = {}

    _kwargs: dict[str, Any] = {
        "method": "post",
        "url": "/api/v1/schedule/cycles",
    }

    _kwargs["json"] = body.to_dict()

    headers["Content-Type"] = "application/json"

    _kwargs["headers"] = headers
    return _kwargs


def _parse_response(
    *, client: AuthenticatedClient | Client, response: httpx.Response
) -> ErrorResponse | PlanningCycleResponse | None:
    if response.status_code == 200:
        response_200 = PlanningCycleResponse.from_dict(response.json())

        return response_200

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
) -> Response[ErrorResponse | PlanningCycleResponse]:
    return Response(
        status_code=HTTPStatus(response.status_code),
        content=response.content,
        headers=response.headers,
        parsed=_parse_response(client=client, response=response),
    )


def sync_detailed(
    *,
    client: AuthenticatedClient | Client,
    body: PlanningCycleCreate,
) -> Response[ErrorResponse | PlanningCycleResponse]:
    """Create a new planning cycle

     Requires `SUPER_ADMIN`. The two dates are the days the cycle's slots run on, both included. An end
    earlier than the start is refused with 422; equal dates are a cycle of one day.

    Args:
        body (PlanningCycleCreate):

    Raises:
        errors.UnexpectedStatus: If the server returns an undocumented status code and Client.raise_on_unexpected_status is True.
        httpx.TimeoutException: If the request takes longer than Client.timeout.

    Returns:
        Response[ErrorResponse | PlanningCycleResponse]
    """

    kwargs = _get_kwargs(
        body=body,
    )

    response = client.get_httpx_client().request(
        **kwargs,
    )

    return _build_response(client=client, response=response)


def sync(
    *,
    client: AuthenticatedClient | Client,
    body: PlanningCycleCreate,
) -> ErrorResponse | PlanningCycleResponse | None:
    """Create a new planning cycle

     Requires `SUPER_ADMIN`. The two dates are the days the cycle's slots run on, both included. An end
    earlier than the start is refused with 422; equal dates are a cycle of one day.

    Args:
        body (PlanningCycleCreate):

    Raises:
        errors.UnexpectedStatus: If the server returns an undocumented status code and Client.raise_on_unexpected_status is True.
        httpx.TimeoutException: If the request takes longer than Client.timeout.

    Returns:
        ErrorResponse | PlanningCycleResponse
    """

    return sync_detailed(
        client=client,
        body=body,
    ).parsed


async def asyncio_detailed(
    *,
    client: AuthenticatedClient | Client,
    body: PlanningCycleCreate,
) -> Response[ErrorResponse | PlanningCycleResponse]:
    """Create a new planning cycle

     Requires `SUPER_ADMIN`. The two dates are the days the cycle's slots run on, both included. An end
    earlier than the start is refused with 422; equal dates are a cycle of one day.

    Args:
        body (PlanningCycleCreate):

    Raises:
        errors.UnexpectedStatus: If the server returns an undocumented status code and Client.raise_on_unexpected_status is True.
        httpx.TimeoutException: If the request takes longer than Client.timeout.

    Returns:
        Response[ErrorResponse | PlanningCycleResponse]
    """

    kwargs = _get_kwargs(
        body=body,
    )

    response = await client.get_async_httpx_client().request(**kwargs)

    return _build_response(client=client, response=response)


async def asyncio(
    *,
    client: AuthenticatedClient | Client,
    body: PlanningCycleCreate,
) -> ErrorResponse | PlanningCycleResponse | None:
    """Create a new planning cycle

     Requires `SUPER_ADMIN`. The two dates are the days the cycle's slots run on, both included. An end
    earlier than the start is refused with 422; equal dates are a cycle of one day.

    Args:
        body (PlanningCycleCreate):

    Raises:
        errors.UnexpectedStatus: If the server returns an undocumented status code and Client.raise_on_unexpected_status is True.
        httpx.TimeoutException: If the request takes longer than Client.timeout.

    Returns:
        ErrorResponse | PlanningCycleResponse
    """

    return (
        await asyncio_detailed(
            client=client,
            body=body,
        )
    ).parsed
