# REST Quickstart

<!-- Copyright 2026 Chronos Ledger Contributors (Apache 2.0) -->

Everything the web app does goes through the same HTTP API, so any language
that can send a request can drive Chronos Ledger. This page gets a script or
another service talking to an instance in about five minutes. The full
reference is [api.md](api.md) and the machine-readable contract is
[openapi.yaml](openapi.yaml).

Examples use `curl` and `jq`. Replace `https://chronos.example.org` with your
instance.

```bash
export CHRONOS=https://chronos.example.org/api/v1
```

## 1. Check the instance is up

```bash
curl -s https://chronos.example.org/health
```

`/health` sits outside `/api/v1` and needs no credentials.

## 2. Pick how you authenticate

| You are | Use | Header |
|---|---|---|
| A person, or a script acting as one for a while | Sign in, get a token | `Authorization: Bearer <access_token>` |
| Another system (an HMS, a campus portal, a cron job) | An API key bound to a service account | `X-API-Key: ck_...` |

Integrations should use an API key. Tokens expire after 15 minutes by default
and need refreshing. A key does not, and it can be narrowed to the parts of
the API the integration calls.

### Token

```bash
TOKEN=$(curl -s -X POST "$CHRONOS/auth/login" \
  -H 'Content-Type: application/json' \
  -d '{"email_address":"you@org.internal","password":"'"$CHRONOS_PASSWORD"'"}' \
  | jq -r .access_token)

curl -s "$CHRONOS/auth/me" -H "Authorization: Bearer $TOKEN"
```

Keep the password in an environment variable, not in the command line or a
file you commit.

### API key

A `SUPER_ADMIN` creates one. Bind it to a service account and scope it to the
areas the integration calls (see [Service accounts](api.md#service-accounts)):

```bash
curl -s -X POST "$CHRONOS/api-keys/" \
  -H "Authorization: Bearer $TOKEN" -H 'Content-Type: application/json' \
  -d '{"label":"room booking","user_id":"SVC001",
       "scopes":["resources:read","resources:write"],
       "expires_at":"2027-01-01T00:00:00Z"}'
```

The response carries `api_key` once. Store it in your secret manager right
away: only its hash is kept, so a lost key is revoked and reissued.

```bash
export CHRONOS_KEY=ck_...   # from your secret manager
curl -s "$CHRONOS/resources/" -H "X-API-Key: $CHRONOS_KEY"
```

## 3. Read something

```bash
# Rooms and people that can be booked
curl -s "$CHRONOS/resources/" -H "X-API-Key: $CHRONOS_KEY" | jq '.[] | {id, code, label}'

# When resource 12 is free over a week
curl -s "$CHRONOS/resources/12/availability?from=2026-01-05&to=2026-01-11" \
  -H "X-API-Key: $CHRONOS_KEY"
```

## 4. Page through a long list

List routes take `limit` and `offset` and always return `X-Total-Count`:

```bash
curl -s -D - "$CHRONOS/users/?limit=50&offset=0" -H "X-API-Key: $CHRONOS_KEY" -o page.json \
  | grep -i x-total-count
```

Keep going while `offset + limit < X-Total-Count`. [Paging](api.md#paging)
lists which routes page.

## 5. Write something safely

A hold on a resource needs an `Idempotency-Key`. Generate one per intended
booking and reuse it on every retry of that booking:

```bash
KEY=$(uuidgen)
curl -s -X POST "$CHRONOS/resources/12/reservations" \
  -H "X-API-Key: $CHRONOS_KEY" -H "Idempotency-Key: $KEY" \
  -H 'Content-Type: application/json' \
  -d '{"date":"2026-01-06","start":"14:00","end":"15:00","purpose":"Ward round"}'
```

| Status | Meaning | What to do |
|---|---|---|
| `201` | Held | Store the returned `id` |
| `200` | Same key, same body: this is the earlier result | Treat as success |
| `409` | Part of the window is taken; `detail.conflicts` says by what | Pick another window or resource |
| `422` | Bad body, or the key was used for a different request | Fix the request; do not retry unchanged |

Release it with `DELETE /resources/12/reservations/{id}`.

## 6. Errors

Errors are JSON with a `detail` field. Usually it is a string. For `422`
validation errors it is FastAPI's list of field problems. For a `409`
conflict it is an object with `message` and `conflicts`.

| Status | Usual cause |
|---|---|
| `401` | Missing, expired or revoked token or key |
| `403` | Authenticated, but the role or the key's scope does not cover this route; `detail` names the scope needed |
| `404` | No such row, or not visible to this caller |
| `409` | Conflicts with existing state |
| `422` | Request failed validation |
| `429` | Rate limited; wait `Retry-After` seconds |

Retry only `429`, `502`, `503` and `504`, with backoff. Retry writes only when
they carry an idempotency key.

## Calling from a browser on another origin

Server-to-server calls need nothing extra. A web page served from a different
origin can only call the API if the instance lists that origin in
`APP_CORS_ORIGINS` (comma separated, exact scheme and host). Do not put an
API key in browser code: anyone who opens the page can read it. A browser app
should sign its user in and use their token.

## Other languages

Any HTTP client works: set the header, send JSON, read `detail` on errors.
Typed client libraries generated from `openapi.yaml` are planned for
TypeScript, Python, Go and Rust; [sdks.md](sdks.md) tracks them. Until they
ship, most generators can build a client from `openapi.yaml` directly.

The live WebSocket at `/api/v1/ws` is not part of the REST contract and
is not covered by the generated clients.
