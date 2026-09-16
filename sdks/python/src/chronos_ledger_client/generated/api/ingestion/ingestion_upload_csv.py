from http import HTTPStatus
from typing import Any

import httpx

from ... import errors
from ...client import AuthenticatedClient, Client
from ...models.csv_import_result import CsvImportResult
from ...models.error_response import ErrorResponse
from ...models.ingestion_upload_csv_body import IngestionUploadCsvBody
from ...types import UNSET, Response


def _get_kwargs(
    *,
    body: IngestionUploadCsvBody,
    cycle_id: int,
) -> dict[str, Any]:
    headers: dict[str, Any] = {}

    params: dict[str, Any] = {}

    params["cycle_id"] = cycle_id

    params = {k: v for k, v in params.items() if v is not UNSET and v is not None}

    _kwargs: dict[str, Any] = {
        "method": "post",
        "url": "/api/v1/ingestion/upload-csv",
        "params": params,
    }

    _kwargs["files"] = body.to_multipart()

    headers["Content-Type"] = "multipart/form-data; boundary=+++"

    _kwargs["headers"] = headers
    return _kwargs


def _parse_response(
    *, client: AuthenticatedClient | Client, response: httpx.Response
) -> CsvImportResult | ErrorResponse | None:
    if response.status_code == 200:
        response_200 = CsvImportResult.from_dict(response.json())

        return response_200

    if response.status_code == 400:
        response_400 = ErrorResponse.from_dict(response.json())

        return response_400

    if response.status_code == 403:
        response_403 = ErrorResponse.from_dict(response.json())

        return response_403

    if response.status_code == 404:
        response_404 = ErrorResponse.from_dict(response.json())

        return response_404

    if response.status_code == 413:
        response_413 = ErrorResponse.from_dict(response.json())

        return response_413

    if response.status_code == 422:
        response_422 = ErrorResponse.from_dict(response.json())

        return response_422

    if client.raise_on_unexpected_status:
        raise errors.UnexpectedStatus(response.status_code, response.content)
    else:
        return None


def _build_response(
    *, client: AuthenticatedClient | Client, response: httpx.Response
) -> Response[CsvImportResult | ErrorResponse]:
    return Response(
        status_code=HTTPStatus(response.status_code),
        content=response.content,
        headers=response.headers,
        parsed=_parse_response(client=client, response=response),
    )


def sync_detailed(
    *,
    client: AuthenticatedClient | Client,
    body: IngestionUploadCsvBody,
    cycle_id: int,
) -> Response[CsvImportResult | ErrorResponse]:
    """Bulk import schedule from CSV

     Requires `SUPER_ADMIN`. The matrix rewrites activities and registrations across every unit, so a
    unit-scoped admin cannot upload it. The CSV must contain these columns (case-sensitive):
    `member_id`, `member_name`, `member_email`, `activity_code`, `activity_title`, `unit`,
    `day_of_week_index` (ISO 8601: 1=Monday .. 7=Sunday), `time_window_start` (HH:MM), `time_window_end`
    (HH:MM), `lead_id`, `room`.
    Creates/updates: Users, ActivityOfferings, StructuralMasterSlots, ActivityRegistrations. Idempotent,
    re-uploading the same CSV is safe: an existing member keeps their password.

    Never removes. Slots and enrollments the cycle holds that the file does not mention come back in
    `not_in_file` for somebody to act on, which is what makes a partial upload safe.

    A row that would put a class in a room already taken for that window, by a booking, by another
    class, or by a day already generated onto it, is refused with 422 and the whole file is rolled back,
    which is what every other bad row in an import does. Rows are checked against each other as well as
    against what is already stored, so one file cannot put two classes in one room at one hour. The
    check only looks where a row would actually move a class, so re-uploading a file that describes the
    timetable as it already stands is not refused by what is sitting on it.

    A closed cycle changes two of those three. Its slots occupy nothing, so an upload into one is not
    checked against the bookings or against the rest of the timetable, the same way a slot in a closed
    cycle does not block a booking. The days already generated are checked either way, because a
    correction is copied onto them whatever the cycle says and the database refuses to move one onto a
    room something else is holding.
    Each new member costs a bcrypt hash on the request thread, about half a second, so a file creating
    more than roughly 100 new members will exceed the 60s client and proxy timeouts. Split it.

    Args:
        cycle_id (int):
        body (IngestionUploadCsvBody):

    Raises:
        errors.UnexpectedStatus: If the server returns an undocumented status code and Client.raise_on_unexpected_status is True.
        httpx.TimeoutException: If the request takes longer than Client.timeout.

    Returns:
        Response[CsvImportResult | ErrorResponse]
    """

    kwargs = _get_kwargs(
        body=body,
        cycle_id=cycle_id,
    )

    response = client.get_httpx_client().request(
        **kwargs,
    )

    return _build_response(client=client, response=response)


def sync(
    *,
    client: AuthenticatedClient | Client,
    body: IngestionUploadCsvBody,
    cycle_id: int,
) -> CsvImportResult | ErrorResponse | None:
    """Bulk import schedule from CSV

     Requires `SUPER_ADMIN`. The matrix rewrites activities and registrations across every unit, so a
    unit-scoped admin cannot upload it. The CSV must contain these columns (case-sensitive):
    `member_id`, `member_name`, `member_email`, `activity_code`, `activity_title`, `unit`,
    `day_of_week_index` (ISO 8601: 1=Monday .. 7=Sunday), `time_window_start` (HH:MM), `time_window_end`
    (HH:MM), `lead_id`, `room`.
    Creates/updates: Users, ActivityOfferings, StructuralMasterSlots, ActivityRegistrations. Idempotent,
    re-uploading the same CSV is safe: an existing member keeps their password.

    Never removes. Slots and enrollments the cycle holds that the file does not mention come back in
    `not_in_file` for somebody to act on, which is what makes a partial upload safe.

    A row that would put a class in a room already taken for that window, by a booking, by another
    class, or by a day already generated onto it, is refused with 422 and the whole file is rolled back,
    which is what every other bad row in an import does. Rows are checked against each other as well as
    against what is already stored, so one file cannot put two classes in one room at one hour. The
    check only looks where a row would actually move a class, so re-uploading a file that describes the
    timetable as it already stands is not refused by what is sitting on it.

    A closed cycle changes two of those three. Its slots occupy nothing, so an upload into one is not
    checked against the bookings or against the rest of the timetable, the same way a slot in a closed
    cycle does not block a booking. The days already generated are checked either way, because a
    correction is copied onto them whatever the cycle says and the database refuses to move one onto a
    room something else is holding.
    Each new member costs a bcrypt hash on the request thread, about half a second, so a file creating
    more than roughly 100 new members will exceed the 60s client and proxy timeouts. Split it.

    Args:
        cycle_id (int):
        body (IngestionUploadCsvBody):

    Raises:
        errors.UnexpectedStatus: If the server returns an undocumented status code and Client.raise_on_unexpected_status is True.
        httpx.TimeoutException: If the request takes longer than Client.timeout.

    Returns:
        CsvImportResult | ErrorResponse
    """

    return sync_detailed(
        client=client,
        body=body,
        cycle_id=cycle_id,
    ).parsed


async def asyncio_detailed(
    *,
    client: AuthenticatedClient | Client,
    body: IngestionUploadCsvBody,
    cycle_id: int,
) -> Response[CsvImportResult | ErrorResponse]:
    """Bulk import schedule from CSV

     Requires `SUPER_ADMIN`. The matrix rewrites activities and registrations across every unit, so a
    unit-scoped admin cannot upload it. The CSV must contain these columns (case-sensitive):
    `member_id`, `member_name`, `member_email`, `activity_code`, `activity_title`, `unit`,
    `day_of_week_index` (ISO 8601: 1=Monday .. 7=Sunday), `time_window_start` (HH:MM), `time_window_end`
    (HH:MM), `lead_id`, `room`.
    Creates/updates: Users, ActivityOfferings, StructuralMasterSlots, ActivityRegistrations. Idempotent,
    re-uploading the same CSV is safe: an existing member keeps their password.

    Never removes. Slots and enrollments the cycle holds that the file does not mention come back in
    `not_in_file` for somebody to act on, which is what makes a partial upload safe.

    A row that would put a class in a room already taken for that window, by a booking, by another
    class, or by a day already generated onto it, is refused with 422 and the whole file is rolled back,
    which is what every other bad row in an import does. Rows are checked against each other as well as
    against what is already stored, so one file cannot put two classes in one room at one hour. The
    check only looks where a row would actually move a class, so re-uploading a file that describes the
    timetable as it already stands is not refused by what is sitting on it.

    A closed cycle changes two of those three. Its slots occupy nothing, so an upload into one is not
    checked against the bookings or against the rest of the timetable, the same way a slot in a closed
    cycle does not block a booking. The days already generated are checked either way, because a
    correction is copied onto them whatever the cycle says and the database refuses to move one onto a
    room something else is holding.
    Each new member costs a bcrypt hash on the request thread, about half a second, so a file creating
    more than roughly 100 new members will exceed the 60s client and proxy timeouts. Split it.

    Args:
        cycle_id (int):
        body (IngestionUploadCsvBody):

    Raises:
        errors.UnexpectedStatus: If the server returns an undocumented status code and Client.raise_on_unexpected_status is True.
        httpx.TimeoutException: If the request takes longer than Client.timeout.

    Returns:
        Response[CsvImportResult | ErrorResponse]
    """

    kwargs = _get_kwargs(
        body=body,
        cycle_id=cycle_id,
    )

    response = await client.get_async_httpx_client().request(**kwargs)

    return _build_response(client=client, response=response)


async def asyncio(
    *,
    client: AuthenticatedClient | Client,
    body: IngestionUploadCsvBody,
    cycle_id: int,
) -> CsvImportResult | ErrorResponse | None:
    """Bulk import schedule from CSV

     Requires `SUPER_ADMIN`. The matrix rewrites activities and registrations across every unit, so a
    unit-scoped admin cannot upload it. The CSV must contain these columns (case-sensitive):
    `member_id`, `member_name`, `member_email`, `activity_code`, `activity_title`, `unit`,
    `day_of_week_index` (ISO 8601: 1=Monday .. 7=Sunday), `time_window_start` (HH:MM), `time_window_end`
    (HH:MM), `lead_id`, `room`.
    Creates/updates: Users, ActivityOfferings, StructuralMasterSlots, ActivityRegistrations. Idempotent,
    re-uploading the same CSV is safe: an existing member keeps their password.

    Never removes. Slots and enrollments the cycle holds that the file does not mention come back in
    `not_in_file` for somebody to act on, which is what makes a partial upload safe.

    A row that would put a class in a room already taken for that window, by a booking, by another
    class, or by a day already generated onto it, is refused with 422 and the whole file is rolled back,
    which is what every other bad row in an import does. Rows are checked against each other as well as
    against what is already stored, so one file cannot put two classes in one room at one hour. The
    check only looks where a row would actually move a class, so re-uploading a file that describes the
    timetable as it already stands is not refused by what is sitting on it.

    A closed cycle changes two of those three. Its slots occupy nothing, so an upload into one is not
    checked against the bookings or against the rest of the timetable, the same way a slot in a closed
    cycle does not block a booking. The days already generated are checked either way, because a
    correction is copied onto them whatever the cycle says and the database refuses to move one onto a
    room something else is holding.
    Each new member costs a bcrypt hash on the request thread, about half a second, so a file creating
    more than roughly 100 new members will exceed the 60s client and proxy timeouts. Split it.

    Args:
        cycle_id (int):
        body (IngestionUploadCsvBody):

    Raises:
        errors.UnexpectedStatus: If the server returns an undocumented status code and Client.raise_on_unexpected_status is True.
        httpx.TimeoutException: If the request takes longer than Client.timeout.

    Returns:
        CsvImportResult | ErrorResponse
    """

    return (
        await asyncio_detailed(
            client=client,
            body=body,
            cycle_id=cycle_id,
        )
    ).parsed
