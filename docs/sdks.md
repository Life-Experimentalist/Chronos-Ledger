# Client Libraries Plan

<!-- Copyright 2026 Chronos Ledger Contributors (Apache 2.0) -->

Status: planned, not built. Until these ship, use the
[REST quickstart](quickstart.md) or point any OpenAPI generator at
[openapi.yaml](openapi.yaml).

## Goal

A typed client in TypeScript/JavaScript, Python, Go and Rust, generated from
one contract, so a new endpoint reaches every language by regenerating rather
than by hand. Each library adds only the few things a generator cannot know:
how to authenticate, how to retry a write safely, and how to page.

## 0. Preconditions

Generated clients are only as right as the spec. Three things have to hold
before the first library is published.

1. **The spec matches the server, enforced in CI.** Done in 0.13:
   `backend/tests/test_openapi_spec_matches_app.py` loads `app.openapi()` and
   fails when a method and path pair, a request body, or a success response
   schema differs from `docs/openapi.yaml`. Descriptions may differ; shapes
   may not.
2. **Every operation has a stable `operationId`.** Done in 0.13: every route
   is named `<area>.<verb>` (for example `resources.createReservation`) in
   both the FastAPI routes and the YAML, and the same test checks they agree.
   Renaming one later is a breaking change for every SDK.
3. **An OpenAPI 3.0 copy for tools that need it.** The spec is 3.1. Some Go
   and Rust generators only read 3.0, so CI also produces a down-converted
   `openapi-3.0.yaml` as a build artifact (not committed). Check each
   generator's current 3.1 support when implementing; drop this step if
   they all read 3.1 by then.

## 1. Libraries

| Language | Package | Generator | Runtime deps | Registry |
|---|---|---|---|---|
| TypeScript / JavaScript | `@life-experimentalist/chronos` | `openapi-typescript` for types, `openapi-fetch` for calls | none beyond `fetch` | npm, trusted publishing |
| Python | `chronos-ledger-client` | `openapi-python-client` | `httpx`, `attrs` | PyPI, trusted publishing |
| Go | `github.com/Life-Experimentalist/chronos-go` | `oapi-codegen` (client + types) | standard library | Go module proxy, via tag |
| Rust | `chronos-ledger-client` | `progenitor` | `reqwest`, `serde` | crates.io |

Names are proposals; confirm availability before the first publish.

TypeScript works in Node 18+, Deno, Bun and browsers. JavaScript users get the
same package with no type checking needed.

Where the code lives: one `sdks/` directory in this repository with a
subdirectory per language, except Go, which needs its own repository (or a
`sdks/go` module path with prefixed tags such as `sdks/go/v0.13.0`). Prefixed
tags in this repo are the simpler choice and avoid a second repository.

## 2. What each library adds by hand

Kept small and identical in behavior across languages:

| Concern | Behavior |
|---|---|
| Auth | Construct with `api_key` (sends `X-API-Key`) or with a token provider. The token provider variant calls `/auth/refresh` on `401` once, then gives up |
| Idempotency | `createReservation` generates an `Idempotency-Key` if the caller did not pass one, and reuses it on its own retries |
| Retries | Only on `429`, `502`, `503`, `504` and connection errors; honors `Retry-After`; writes retried only when idempotent |
| Paging | An iterator over list routes that reads `X-Total-Count` and walks `limit`/`offset` |
| Errors | One error type carrying status, `detail` as returned, and for `409` the parsed `conflicts` list |
| Base URL | Required argument; the library appends `/api/v1` |
| User agent | `chronos-<lang>/<version>` |

Not covered: the WebSocket at `/api/v1/ws`, CSV upload helpers beyond the
generated call, and the calendar feed (it is a URL you give a calendar app).

## 3. Versioning

Library versions match the server release they were generated from:
`chronos-ledger-client 0.13.0` targets server `0.13.x`. A library works
against a newer server in the same minor series. While the server is `0.x`,
a minor bump may break the API, and the libraries break with it.

The release workflow regenerates all four on each `v*` tag, runs their tests,
and publishes. A pull request that changes the spec regenerates them too and
fails if the checked-in generated code is stale.

## 4. Tests

Each library runs the same scenario against a real server started from the
compose file in CI:

1. Create a service account and a scoped API key with a bootstrap token.
2. List resources with the key.
3. Page through users with a page size of 2 and check the count matches `X-Total-Count`.
4. Create a reservation, repeat it with the same key and get the same id.
5. Create an overlapping reservation and get a typed conflict error.
6. Call a route outside the key's scope and get a `403` naming the scope.
7. Delete the reservation.

## 5. Docs

Per language, one page in `docs/sdks/`: install, construct a client, the
seven steps above as a worked example, and a link to the generated reference
(TypeDoc, pdoc, pkg.go.dev, docs.rs). The quickstart gains a tab per language
next to `curl`.

## 6. Order of work

1. CI spec check and `operationId`s (precondition 1 and 2).
2. TypeScript and Python: the two that current integrators (PulseWard is
   JavaScript) will use first.
3. Shared scenario test harness.
4. Go and Rust.
5. Language pages and quickstart tabs.

## Acceptance checks

- Adding a route to the backend without updating `openapi.yaml` fails CI.
- The scenario in section 4 passes in all four languages against the same server build.
- A published library installs and runs the quickstart example with no generated code edited by hand.
