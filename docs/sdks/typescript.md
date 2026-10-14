# TypeScript and JavaScript client

<!-- Copyright 2026 Chronos Ledger Contributors (Apache 2.0) -->

Package `chronosledger-client`, in [`sdks/typescript`](../../sdks/typescript).
Types come from [openapi.yaml](../openapi.yaml) through `openapi-typescript`,
and calls go through `openapi-fetch`, the only runtime dependency. Works on
Node 20 or newer, Deno, Bun and browsers.

## Install

From 0.18.0 the package is on npm:

```bash
npm install chronosledger-client
```

Until then, build it from a checkout:

```bash
cd sdks/typescript && npm ci && npm run build && npm pack
```

Then install the `.tgz` that `npm pack` wrote, with
`npm install ./chronosledger-client-<version>.tgz` from your project.

## Construct a client

```ts
import { createChronosClient } from "chronosledger-client";

const chronos = createChronosClient({
  baseUrl: "https://chronos.example.org",
  apiKey: process.env.CHRONOS_API_KEY,
});

const { data: resources } = await chronos.GET("/api/v1/resources/");
```

`baseUrl` is the server root. A trailing `/api/v1` is accepted and dropped,
because every path already carries it. Paths, query parameters, bodies and
responses are typed from the spec.

## Signing in with tokens

Pass `tokens` instead of `apiKey`. On a `401` the client calls
`/api/v1/auth/refresh` once and repeats the request. A refresh token works only
once, so store every new pair:

```ts
const chronos = createChronosClient({
  baseUrl,
  tokens: { accessToken, refreshToken },
  onTokens: (tokens) => save(tokens),
});
```

Requests that hit a `401` at the same moment share one refresh. If the refresh
itself fails (the server refuses it, the connection drops or the answer is not a
token pair), the original `401` is thrown as `ChronosError`. Passing both
`apiKey` and `tokens` throws.

## Reservations

```ts
const hold = await chronos.createReservation(3, {
  date: "2026-01-06",
  start: "14:00",
  end: "15:00",
  purpose: "Viva",
});
```

An `Idempotency-Key` is generated when you do not pass one as the third
argument, and the same key goes out on every retry, so a retry never takes a
second hold. Pass your own key when a retry can come from outside the process,
for example after a crash. Every other write gets a key too, see
[Retries](#retries).

## Retries

A request is tried again when:

- no response arrived: `fetch` threw, for example on a refused or dropped
  connection;
- the status is `429`, `502`, `503` or `504`;
- the status is `409` and the body code is `IDEMPOTENCY_KEY_IN_PROGRESS`, which
  means the first request under that key is still running. The same key gets
  the stored answer once it finishes.

No other `4xx` is retried: `400`, `401` (after the one token refresh), `403`,
`404`, `422` and a plain `409` conflict throw `ChronosError` at once. An abort
from the caller's own `AbortSignal` is not retried either.

Every write (`POST`, `PATCH`, `PUT`, `DELETE`) is sent with an
`Idempotency-Key`: the header you set, or a UUIDv4 the client makes once per
call and sends again on each retry, so a retried write has one effect. A write
is never sent without a key, which is why writes can be retried at all. `GET`,
`HEAD` and `OPTIONS` carry none.

The one `multipart/form-data` request, the CSV import, is sent once and never
retried, and it is not sent again after a token refresh. A failure comes back as
it is.

The wait before retry `n` (counting from 0) is a random number between 0 and
`min(maxDelayMs, baseDelayMs * 2 ** n)`. When the response has a `Retry-After`
header, in seconds or as an HTTP date, the client waits that long instead; a
negative or unreadable value is ignored. A wait that would run past the
deadline is not started: the last response is thrown
instead.

```ts
const chronos = createChronosClient({
  baseUrl,
  apiKey,
  retry: { maxAttempts: 6, baseDelayMs: 500, maxDelayMs: 10_000, deadlineMs: 60_000 },
});
```

| Setting | Default | Meaning |
|---|---|---|
| `maxAttempts` | 4 | Tries in all, the first included |
| `baseDelayMs` | 250 | The first jitter ceiling |
| `maxDelayMs` | 8000 | The highest a jittered wait can reach |
| `deadlineMs` | 30000 | From the first send; no wait starts past it |

`retry: false` turns retries off. A write still carries its key. The deadline
does not interrupt a request in flight; pass a `signal` to the call for that.

When the tries or the deadline run out, a response error is thrown as
`ChronosError` with the status, `code` and `detail` of the last response, and a
network error is thrown as it came from `fetch`.

## Paging

```ts
import { paginate } from "chronosledger-client";

for await (const user of paginate((limit, offset) =>
  chronos.GET("/api/v1/users/", { params: { query: { limit, offset } } }),
)) {
  console.log(user.id);
}
```

The walk stops once `X-Total-Count` rows have been seen or a page is empty.
The page size defaults to 100 and is the second argument.

## Errors

Every status of 400 or above throws `ChronosError`:

```ts
import { ChronosError } from "chronosledger-client";

try {
  await chronos.createReservation(3, body);
} catch (error) {
  if (error instanceof ChronosError && error.status === 409) {
    console.log(error.conflicts); // the busy intervals
  }
}
```

`detail` is exactly what the server sent: a string, or for a `409` an object
with `message` and `conflicts`. A body that is not JSON is kept as text.

## Regenerating

After a change to `docs/openapi.yaml`:

```bash
cd sdks/typescript && npm run generate
```

Commit `src/generated/schema.ts` with the spec change. CI regenerates it and
fails when the committed file is out of date.
