# Copyright 2026 Chronos Ledger Contributors
# Licensed under the Apache License, Version 2.0
"""Every error leaves with a code, and every code the server can send is in the spec.

A client branches on `code` rather than on the wording of `detail`, so the
list in docs/openapi.yaml has to be the list the server works from. The
`ErrorCode` enum there is compared with app.core.errors.ErrorCode as a set: a
code added on one side only fails here, before a generated SDK ships without
it. The documented error responses are walked too, so a route cannot document
an error whose body has no code in it.

The rest sends real requests and reads the bodies, for the errors no route
raises itself: a path or method the router does not serve, a malformed body,
and an exception nothing caught.
"""

import ast
from pathlib import Path

import pytest
from fastapi import FastAPI, HTTPException
from fastapi.testclient import TestClient

from app.core.errors import (
    FALLBACK_BY_STATUS,
    INTERNAL_ERROR_DETAIL,
    ChronosError,
    ErrorCode,
    register_error_handlers,
)
from tests.conftest import ADMIN_PASSWORD
from tests.test_openapi_spec_matches_app import COMMITTED, COMMITTED_OPS

APP_DIR = Path(__file__).resolve().parents[1] / "app"
SPEC_CODES = set(COMMITTED["components"]["schemas"]["ErrorCode"]["enum"])
CODE_REF = {"$ref": "#/components/schemas/ErrorCode"}

# Documented failures whose body is not an error. The readiness probe answers
# 503 with the same Readiness body it answers 200 with, so a load balancer
# reads one shape either way.
NOT_AN_ERROR_BODY = {("GET /health/ready", "503")}


def _resolve(ref: str) -> dict:
    node = COMMITTED
    for part in ref.removeprefix("#/").split("/"):
        node = node[part]
    return node


def _documented_errors():
    for name, op in sorted(COMMITTED_OPS.items()):
        for status, response in op.get("responses", {}).items():
            if str(status)[0] in "45" and (name, str(status)) not in NOT_AN_ERROR_BODY:
                yield f"{name} {status}", response


def test_the_spec_lists_exactly_the_codes_the_server_has():
    server = {code.value for code in ErrorCode}
    assert server - SPEC_CODES == set(), "add these to ErrorCode in docs/openapi.yaml"
    assert SPEC_CODES - server == set(), "the spec lists codes the server never sends"


def test_every_fallback_is_a_code():
    assert set(FALLBACK_BY_STATUS.values()) <= set(ErrorCode)


@pytest.mark.parametrize(("where", "response"), list(_documented_errors()))
def test_every_documented_error_carries_a_listed_code(where, response):
    if "$ref" in response:
        response = _resolve(response["$ref"])
    schema = response.get("content", {}).get("application/json", {}).get("schema")
    assert schema, f"{where} documents no JSON body"
    # A route that can refuse in two shapes lists both under oneOf, and
    # whichever one comes back has to carry the code.
    for choice in schema.get("oneOf", [schema]):
        if "$ref" in choice:
            choice = _resolve(choice["$ref"])
        assert choice.get("properties", {}).get("code") == CODE_REF, f"{where} has no code"
        assert "code" in choice.get("required", []), f"{where} does not require code"


def test_no_route_raises_a_bare_http_exception():
    """A bare HTTPException still gets a code by its status, but only the generic one.

    Raising ChronosError makes whoever writes the raise pick the code, which
    is the only way a caller gets one specific enough to branch on.
    """
    bare = []
    for path in APP_DIR.rglob("*.py"):
        if path.name == "errors.py":
            continue
        for node in ast.walk(ast.parse(path.read_text(encoding="utf-8"))):
            if isinstance(node, ast.Call):
                func = node.func
                name = func.id if isinstance(func, ast.Name) else getattr(func, "attr", None)
                if name == "HTTPException":
                    bare.append(f"{path.relative_to(APP_DIR)}:{node.lineno}")
    assert not bare, f"raise ChronosError with a code instead: {bare}"


def _body(res, status: int, code: ErrorCode) -> dict:
    assert res.status_code == status, res.text
    body = res.json()
    assert body["code"] == code.value
    assert body["code"] in SPEC_CODES
    assert set(body) == {"detail", "code"}
    return body


def test_an_unknown_path_is_not_found(client):
    body = _body(client.get("/api/v1/no-such-thing"), 404, ErrorCode.NOT_FOUND)
    assert body["detail"] == "Not Found"


def test_a_method_the_route_does_not_take(client):
    _body(client.delete("/api/v1/auth/login"), 405, ErrorCode.METHOD_NOT_ALLOWED)


def test_no_credentials_at_all(client):
    body = _body(client.get("/api/v1/users/"), 401, ErrorCode.NOT_AUTHENTICATED)
    assert body["detail"] == "Not authenticated"


def test_a_token_that_does_not_verify(client):
    res = client.get("/api/v1/users/", headers={"Authorization": "Bearer not-a-token"})
    _body(res, 401, ErrorCode.TOKEN_INVALID)
    assert res.headers["WWW-Authenticate"] == "Bearer"


def test_a_wrong_password(client, seed_users):
    res = client.post(
        "/api/v1/auth/login",
        json={"email_address": "admin@test.internal", "password": ADMIN_PASSWORD + "x"},
    )
    body = _body(res, 401, ErrorCode.INVALID_CREDENTIALS)
    assert body["detail"] == "Invalid credentials"


def test_a_malformed_body_keeps_fastapis_list_of_field_errors(client):
    body = _body(client.post("/api/v1/auth/login", json={}), 422, ErrorCode.VALIDATION_FAILED)
    assert isinstance(body["detail"], list)
    assert {error["loc"][-1] for error in body["detail"]} == {"email_address", "password"}


def _bare_app() -> TestClient:
    app = FastAPI()
    register_error_handlers(app)

    @app.get("/boom")
    def boom():
        raise RuntimeError("secret internals: password=hunter2")

    @app.get("/bare/{status}")
    def bare(status: int):
        raise HTTPException(status_code=status, detail="plain")

    @app.get("/coded")
    def coded():
        raise ChronosError(409, "taken", code=ErrorCode.EMAIL_TAKEN, headers={"X-Why": "because"})

    return TestClient(app, raise_server_exceptions=False)


def test_an_unhandled_exception_says_nothing_about_itself():
    res = _bare_app().get("/boom")
    body = _body(res, 500, ErrorCode.INTERNAL_ERROR)
    assert body["detail"] == INTERNAL_ERROR_DETAIL
    assert "hunter2" not in res.text
    assert "Traceback" not in res.text


@pytest.mark.parametrize(
    ("status", "code"),
    [(404, ErrorCode.NOT_FOUND), (409, ErrorCode.STATE_CONFLICT), (418, ErrorCode.BAD_REQUEST)],
)
def test_a_bare_http_exception_gets_a_code_by_its_status(status, code):
    body = _body(_bare_app().get(f"/bare/{status}"), status, code)
    assert body["detail"] == "plain"


def test_a_chronos_error_keeps_its_code_and_headers():
    res = _bare_app().get("/coded")
    assert _body(res, 409, ErrorCode.EMAIL_TAKEN)["detail"] == "taken"
    assert res.headers["X-Why"] == "because"


def test_a_chronos_error_is_still_an_http_exception():
    assert isinstance(ChronosError(404, "x", code=ErrorCode.NOT_FOUND), HTTPException)
