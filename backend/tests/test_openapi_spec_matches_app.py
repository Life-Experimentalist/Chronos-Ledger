# Copyright 2026 Chronos Ledger Contributors
# Licensed under the Apache License, Version 2.0
"""docs/openapi.yaml describes the operations the app serves, in the same shapes.

Integrators and the generated SDKs build against that file, and it is
hand-written rather than generated because it carries summaries, public-route
markers and 401/403/429 responses that FastAPI's own output does not.
Hand-written means it can fall behind, and it had: it listed ten operations the
app does not serve and missed thirteen it does, including the whole
refresh-token pair.

Paths are compared verbatim, which is why every path in the file carries its
full `/api/v1` prefix and `servers` stops at the origin: with no normalising
step there is no normalising bug, and `/health` really is served at the root
next to `/api/v1/...`. A path parameter's name is part of the path, so this
catches a renamed one too.

Beyond the operation set, each operation is checked for its `operationId`, its
request body and its success responses. A body or response is compared by
shape: the field names it has and, for a request, which of them are required.
Descriptions, examples and field types stay the spec's own business. The spec
may document more than the app declares (a route with no response_model has
no schema to compare, and a replay answering 200 next to a 201 is fine), but
never less, and never something different.
"""

import re
from pathlib import Path

import pytest
import yaml

from app.main import app

METHODS = frozenset({"get", "put", "post", "delete", "patch", "head", "options", "trace"})
OPERATION_ID = re.compile(r"^[a-z][a-zA-Z]*\.[a-z][a-zA-Z]*$")

SPEC = Path(__file__).resolve().parents[2] / "docs" / "openapi.yaml"
COMMITTED = yaml.safe_load(SPEC.read_text(encoding="utf-8"))
SERVED = app.openapi()


def _operations(spec: dict) -> dict[str, dict]:
    return {
        f"{method.upper()} {path}": op
        for path, item in spec["paths"].items()
        for method, op in item.items()
        if method in METHODS
    }


def _shape(spec: dict, schema: dict | None, request: bool) -> tuple | None:
    """The field names of a schema, following $ref, allOf and array items."""
    if not schema:
        return None
    while "$ref" in schema or schema.get("type") == "array":
        if "$ref" in schema:
            schema = spec["components"]["schemas"][schema["$ref"].rsplit("/", 1)[1]]
        else:
            schema = schema.get("items", {})
    fields: set[str] = set()
    required: set[str] = set()
    for part in schema.get("allOf", [schema]):
        while "$ref" in part:
            part = spec["components"]["schemas"][part["$ref"].rsplit("/", 1)[1]]
        fields |= set(part.get("properties", {}))
        required |= set(part.get("required", []))
    if not fields:
        return None
    return (sorted(fields), sorted(required)) if request else (sorted(fields),)


def _body(spec: dict, op: dict) -> dict:
    content = op.get("requestBody", {}).get("content", {})
    return {kind: _shape(spec, media.get("schema"), True) for kind, media in content.items()}


def _successes(spec: dict, op: dict) -> dict:
    return {
        code: {
            kind: _shape(spec, media.get("schema"), False)
            for kind, media in response.get("content", {}).items()
        }
        for code, response in op.get("responses", {}).items()
        if code.startswith("2")
    }


COMMITTED_OPS = _operations(COMMITTED)
SERVED_OPS = _operations(SERVED)
SHARED = sorted(COMMITTED_OPS.keys() & SERVED_OPS.keys())


def test_committed_spec_lists_every_operation_the_app_serves():
    stale = sorted(COMMITTED_OPS.keys() - SERVED_OPS.keys())
    missing = sorted(SERVED_OPS.keys() - COMMITTED_OPS.keys())

    assert not stale and not missing, (
        "docs/openapi.yaml and the app disagree.\n"
        "Documented but not served (remove from the spec, or restore the route):\n"
        + "".join(f"  {op}\n" for op in stale)
        + "Served but not documented (add to the spec):\n"
        + "".join(f"  {op}\n" for op in missing)
    )


def test_every_operation_has_a_unique_area_dot_verb_operation_id():
    ids = [op.get("operationId", "") for op in SERVED_OPS.values()]
    malformed = sorted(i for i in ids if not OPERATION_ID.match(i))
    assert not malformed, f"operation_id must look like area.verb: {malformed}"
    assert len(ids) == len(set(ids)), "two routes share an operation_id"


@pytest.mark.parametrize("operation", SHARED)
def test_spec_and_app_agree_on_operation_id(operation):
    served = SERVED_OPS[operation]["operationId"]
    assert COMMITTED_OPS[operation].get("operationId") == served


@pytest.mark.parametrize("operation", SHARED)
def test_spec_and_app_agree_on_the_request_body(operation):
    assert _body(COMMITTED, COMMITTED_OPS[operation]) == _body(SERVED, SERVED_OPS[operation])


@pytest.mark.parametrize("operation", SHARED)
def test_spec_documents_every_success_response_the_app_declares(operation):
    committed = _successes(COMMITTED, COMMITTED_OPS[operation])
    for code, content in _successes(SERVED, SERVED_OPS[operation]).items():
        assert code in committed, f"{code} is not documented"
        for kind, shape in content.items():
            if shape is not None:
                assert committed[code].get(kind) == shape, f"{code} {kind} differs"
