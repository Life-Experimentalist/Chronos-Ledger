# Copyright 2026 Chronos Ledger Contributors
# Licensed under the Apache License, Version 2.0
"""docs/openapi.yaml lists exactly the operations the app serves.

Two integrators build against that file, and it is hand-written rather than
generated because it carries summaries, public-route markers and 401/403/429
responses that FastAPI's own output does not. Hand-written means it can fall
behind, and it had: it listed ten operations the app does not serve and missed
thirteen it does, including the whole refresh-token pair.

Only the operation set is compared, method plus path. Summaries, schemas and
examples stay the spec's own business. Paths are compared verbatim, which is
why every path in the file carries its full `/api/v1` prefix and `servers`
stops at the origin: with no normalising step there is no normalising bug, and
`/health` really is served at the root next to `/api/v1/...`. A path
parameter's name is part of the path, so this catches a renamed one too.
"""

from pathlib import Path

import yaml

from app.main import app

METHODS = frozenset({"get", "put", "post", "delete", "patch", "head", "options", "trace"})

SPEC = Path(__file__).resolve().parents[2] / "docs" / "openapi.yaml"


def _operations(spec: dict) -> set[str]:
    return {
        f"{method.upper()} {path}"
        for path, item in spec["paths"].items()
        for method in item
        if method in METHODS
    }


def test_committed_spec_lists_every_operation_the_app_serves():
    committed = _operations(yaml.safe_load(SPEC.read_text(encoding="utf-8")))
    served = _operations(app.openapi())

    stale = sorted(committed - served)
    missing = sorted(served - committed)

    assert not stale and not missing, (
        "docs/openapi.yaml and the app disagree.\n"
        "Documented but not served (remove from the spec, or restore the route):\n"
        + "".join(f"  {op}\n" for op in stale)
        + "Served but not documented (add to the spec):\n"
        + "".join(f"  {op}\n" for op in missing)
    )
