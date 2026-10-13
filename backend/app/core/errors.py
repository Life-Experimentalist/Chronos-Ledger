# Copyright 2026 Chronos Ledger Contributors
# Licensed under the Apache License, Version 2.0
"""The machine-readable code on every error response, and the handlers that add it.

Every error body is `{"detail": ..., "code": ...}`. `detail` is for a person
and stays exactly as it was before codes existed, because callers already
parse it: a string for most errors, the `{"message", "conflicts"}` object for
a 409 that names what stood in the way, and FastAPI's list of field errors
for a malformed request. `code` is for a program to branch on.

ErrorCode is the single list of codes. docs/openapi.yaml repeats it as the
`ErrorCode` enum, and tests/test_error_codes.py fails when the two differ. A
code is never renamed or reused for a different meaning once it has shipped:
a new kind of failure gets a new code.

A route raises ChronosError with the code that fits. An HTTPException raised
anywhere else, including the 404 and 405 that Starlette's router raises for a
path or method it does not serve, still leaves with a code: the handler picks
one by status from FALLBACK_BY_STATUS.
"""

from enum import StrEnum

from fastapi import FastAPI, HTTPException
from fastapi.encoders import jsonable_encoder
from fastapi.exceptions import RequestValidationError
from fastapi.utils import is_body_allowed_for_status_code
from starlette.exceptions import HTTPException as StarletteHTTPException
from starlette.requests import Request
from starlette.responses import JSONResponse, Response


class ErrorCode(StrEnum):
    # Generic, one per status. What a bare HTTPException is given, and what a
    # route uses when no caller would act differently on a finer code.
    BAD_REQUEST = "BAD_REQUEST"
    NOT_AUTHENTICATED = "NOT_AUTHENTICATED"
    FORBIDDEN = "FORBIDDEN"
    NOT_FOUND = "NOT_FOUND"
    METHOD_NOT_ALLOWED = "METHOD_NOT_ALLOWED"
    STATE_CONFLICT = "STATE_CONFLICT"
    PAYLOAD_TOO_LARGE = "PAYLOAD_TOO_LARGE"
    INVALID_VALUE = "INVALID_VALUE"
    RATE_LIMITED = "RATE_LIMITED"
    INTERNAL_ERROR = "INTERNAL_ERROR"
    SERVICE_UNAVAILABLE = "SERVICE_UNAVAILABLE"

    # The request body, query or headers did not match the declared shape.
    # The only code whose detail is FastAPI's list of field errors.
    VALIDATION_FAILED = "VALIDATION_FAILED"

    # Signing in and proving who is calling.
    INVALID_CREDENTIALS = "INVALID_CREDENTIALS"
    TOKEN_INVALID = "TOKEN_INVALID"
    API_KEY_INVALID = "API_KEY_INVALID"
    API_KEY_EXPIRED = "API_KEY_EXPIRED"
    ACCOUNT_NOT_FOUND = "ACCOUNT_NOT_FOUND"
    ACCOUNT_DEACTIVATED = "ACCOUNT_DEACTIVATED"
    REFRESH_TOKEN_INVALID = "REFRESH_TOKEN_INVALID"
    REFRESH_TOKEN_EXPIRED = "REFRESH_TOKEN_EXPIRED"
    REFRESH_TOKEN_USED = "REFRESH_TOKEN_USED"
    REFRESH_TOKEN_REUSED = "REFRESH_TOKEN_REUSED"
    FEDERATED_TOKEN_INVALID = "FEDERATED_TOKEN_INVALID"
    FEDERATED_EMAIL_MISSING = "FEDERATED_EMAIL_MISSING"
    FEDERATED_ADMIN_REFUSED = "FEDERATED_ADMIN_REFUSED"
    FEDERATION_UNAVAILABLE = "FEDERATION_UNAVAILABLE"
    CURRENT_PASSWORD_INCORRECT = "CURRENT_PASSWORD_INCORRECT"
    PASSWORD_UNCHANGED = "PASSWORD_UNCHANGED"

    # Who may do what.
    PASSWORD_CHANGE_REQUIRED = "PASSWORD_CHANGE_REQUIRED"
    INSUFFICIENT_ROLE = "INSUFFICIENT_ROLE"
    SCOPE_MISSING = "SCOPE_MISSING"
    OUTSIDE_UNIT = "OUTSIDE_UNIT"

    # Records that already exist or stand in the way.
    RESOURCE_CONFLICT = "RESOURCE_CONFLICT"
    ALREADY_EXISTS = "ALREADY_EXISTS"
    EMAIL_TAKEN = "EMAIL_TAKEN"
    USER_DEACTIVATED = "USER_DEACTIVATED"
    IDEMPOTENCY_KEY_REUSED = "IDEMPOTENCY_KEY_REUSED"
    IDEMPOTENCY_KEY_IN_PROGRESS = "IDEMPOTENCY_KEY_IN_PROGRESS"

    # Attendance and absence.
    LOCATION_REQUIRED = "LOCATION_REQUIRED"
    LOCATION_TOO_COARSE = "LOCATION_TOO_COARSE"
    OUTSIDE_GEOFENCE = "OUTSIDE_GEOFENCE"
    MANAGER_NOT_SET = "MANAGER_NOT_SET"

    # Imports, the change feed, and load.
    IMPORT_REJECTED = "IMPORT_REJECTED"
    CHANGE_FEED_DISABLED = "CHANGE_FEED_DISABLED"
    SERVER_BUSY = "SERVER_BUSY"


# For an HTTPException raised without a code. A status missing here falls back
# by its hundred, so the handler never has to answer without one.
FALLBACK_BY_STATUS: dict[int, ErrorCode] = {
    400: ErrorCode.BAD_REQUEST,
    401: ErrorCode.NOT_AUTHENTICATED,
    403: ErrorCode.FORBIDDEN,
    404: ErrorCode.NOT_FOUND,
    405: ErrorCode.METHOD_NOT_ALLOWED,
    409: ErrorCode.STATE_CONFLICT,
    413: ErrorCode.PAYLOAD_TOO_LARGE,
    422: ErrorCode.INVALID_VALUE,
    429: ErrorCode.RATE_LIMITED,
    500: ErrorCode.INTERNAL_ERROR,
    503: ErrorCode.SERVICE_UNAVAILABLE,
}

INTERNAL_ERROR_DETAIL = "Internal server error"


class ChronosError(HTTPException):
    """An HTTPException that names its code.

    A subclass, so code that catches HTTPException, and tests that read
    status_code and detail off one, carry on as before. The code is keyword
    only and has no default: a raise that forgets it fails where it is written
    rather than quietly taking the fallback for its status.
    """

    def __init__(
        self,
        status_code: int,
        detail: object = None,
        *,
        code: ErrorCode,
        headers: dict[str, str] | None = None,
    ) -> None:
        super().__init__(status_code=status_code, detail=detail, headers=headers)
        self.code = code


def code_for_status(status_code: int) -> ErrorCode:
    if status_code in FALLBACK_BY_STATUS:
        return FALLBACK_BY_STATUS[status_code]
    return ErrorCode.INTERNAL_ERROR if status_code >= 500 else ErrorCode.BAD_REQUEST


def error_body(code: ErrorCode, detail: object) -> dict:
    """The body every error goes out with, for the paths that build one by hand."""
    return {"detail": detail, "code": code.value}


async def _http_error(_request: Request, exc: StarletteHTTPException) -> Response:
    # Registered on Starlette's class rather than FastAPI's subclass of it, so
    # the 404 and 405 the router raises for itself come through here too.
    headers = getattr(exc, "headers", None)
    if not is_body_allowed_for_status_code(exc.status_code):
        return Response(status_code=exc.status_code, headers=headers)
    code = getattr(exc, "code", None) or code_for_status(exc.status_code)
    return JSONResponse(error_body(code, exc.detail), status_code=exc.status_code, headers=headers)


async def _validation_error(_request: Request, exc: RequestValidationError) -> JSONResponse:
    # The same detail FastAPI's own handler sends, so a caller reading the
    # list of field errors sees no change.
    return JSONResponse(
        status_code=422,
        content=error_body(ErrorCode.VALIDATION_FAILED, jsonable_encoder(exc.errors())),
    )


async def _unhandled_error(_request: Request, _exc: Exception) -> JSONResponse:
    # Starlette raises the exception again once this response has gone out,
    # so the server still logs the traceback. The caller gets none of it.
    return JSONResponse(
        status_code=500,
        content=error_body(ErrorCode.INTERNAL_ERROR, INTERNAL_ERROR_DETAIL),
    )


def register_error_handlers(app: FastAPI) -> None:
    """Put the code on every error this application sends.

    Called for the ordinary application in app.main and for the embedded one
    in app.embedded, which is a separate FastAPI instance and inherits none of
    the other's handlers.
    """
    app.add_exception_handler(StarletteHTTPException, _http_error)
    app.add_exception_handler(RequestValidationError, _validation_error)
    app.add_exception_handler(Exception, _unhandled_error)
