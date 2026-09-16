# TypeScript and JavaScript client

<!-- Copyright 2026 Chronos Ledger Contributors (Apache 2.0) -->

Package `@life-experimentalist/chronos`, in [`sdks/typescript`](../../sdks/typescript).
Types come from [openapi.yaml](../openapi.yaml) through `openapi-typescript`,
and calls go through `openapi-fetch`, the only runtime dependency. Works on
Node 20 or newer, Deno, Bun and browsers.

## Install

The package is not on npm yet. Build it from a checkout:

```bash
cd sdks/typescript && npm ci && npm run build && npm pack
```

Then install the `.tgz` that `npm pack` wrote, with
`npm install ./life-experimentalist-chronos-<version>.tgz` from your project.

## Construct a client

```ts
import { createChronosClient } from "@life-experimentalist/chronos";

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

Requests that hit a `401` at the same moment share one refresh. Passing both
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
for example after a crash.

## Retries

`429`, `502`, `503`, `504` and network errors are retried up to `maxRetries`
times (default 3). `Retry-After` is honoured up to 30 seconds; without it the
wait doubles from 500 ms to at most 8 s. Only `GET`, `HEAD`, `PUT`, `DELETE`,
`OPTIONS` and requests that carry an `Idempotency-Key` are retried. Other
writes are sent once.

## Paging

```ts
import { paginate } from "@life-experimentalist/chronos";

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
import { ChronosError } from "@life-experimentalist/chronos";

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
