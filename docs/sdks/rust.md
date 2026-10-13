# Rust client

<!-- Copyright 2026 Chronos Ledger Contributors (Apache 2.0) -->

Crate `chronos-ledger-client`, in [`sdks/rust`](../../sdks/rust). The calls are
generated from [openapi.yaml](../openapi.yaml) by `progenitor`, pinned to one
version, from `build.rs` on every build. Built on `reqwest` and `tokio`; Rust
1.88 or newer.

## Install

The crate is not on crates.io yet. Use it from a checkout:

```toml
[dependencies]
chronos-ledger-client = { path = "../Chronos-Ledger/sdks/rust" }
```

## Construct a client

```rust
use chronos_ledger_client::{ClientBuilder, Error};

let client = ClientBuilder::new("https://chronos.example.org")
    .api_key(std::env::var("CHRONOS_API_KEY")?)
    .build()?;

let users = client.users_list().send().await.map_err(Error::from)?;
```

Every operation is a method on `Client` named after its `operationId`
(`users.list` becomes `users_list`) that returns a builder; `send` makes the
call. `ClientBuilder::new` takes the server root. A trailing `/api/v1` is
accepted and dropped, because every generated path already carries it. The API
key goes out as `X-API-Key`. The user agent is `chronos-rust/<version>`.

## Signing in with tokens

Use `tokens` instead of `api_key`. On a `401` the client calls
`/api/v1/auth/refresh` once and repeats the request. A refresh token works only
once, so store every new pair:

```rust
let client = ClientBuilder::new(base_url)
    .tokens(Tokens { access_token, refresh_token }, |pair| save(pair))
    .build()?;
```

Calls that hit a `401` at the same moment share one refresh. Setting both an
API key and tokens is an `Error::Config` from `build`.

## Reservations

`resources.createReservation` has the `Idempotency-Key` as a required header
parameter, so the generated builder asks for one. `new_idempotency_key()` makes
a fresh UUID. The same key goes out on every retry, so a retry never takes a
second hold. Keep your own key when a retry can come from outside the process,
for example after a crash.

Every other write gets a generated key unless the request already carries an
`Idempotency-Key` header.

## Retries

A request is sent again when no response arrived, or the status was `429`,
`502`, `503` or `504`, or a `409` whose code is `IDEMPOTENCY_KEY_IN_PROGRESS`.
Any other `4xx` is returned at once. A read is always retried. A write is
retried only because it carries an `Idempotency-Key`, which the client adds. A
request whose body is a stream is sent once.

The wait before each retry is a random time between zero and
`min(max_delay, base_delay * 2^n)` ("full jitter"). A `Retry-After` header, in
seconds or as an HTTP date, replaces it. `RetryPolicy::default()` is 4
attempts, a 0.25 s base, an 8 s cap and a 30 s deadline. The deadline counts
from the first attempt, and a wait that would pass it is skipped, so the last
failure comes back instead.

```rust
let client = ClientBuilder::new(base_url)
    .retry(RetryPolicy {
        max_attempts: 6,
        base_delay: Duration::from_millis(500),
        max_delay: Duration::from_secs(10),
        deadline: Some(Duration::from_secs(60)),
    })
    .build()?;
// or .without_retries() to send everything once
```

`http_client` replaces the `reqwest::Client`. The default has a 30 second
timeout per attempt.

## Paging

```rust
use futures::TryStreamExt;
use chronos_ledger_client::paginate;

let users: Vec<_> = paginate(100, |limit, offset| {
    let client = client.clone();
    async move {
        let page = client.users_list().limit(limit).offset(offset).send().await?;
        Ok(page.into())
    }
})
.try_collect()
.await?;
```

`paginate` returns a `Stream`. The walk stops once `X-Total-Count` rows have
been seen or a page is empty. The page size defaults to 100.

## Errors

A generated call returns `progenitor_client::Error<()>`. Convert it with
`Error::from` and a status of 400 or above becomes `Error::Api(ApiError)`:

```rust
let result = client.users_get().user_id(id).send().await.map_err(Error::from);
if let Err(Error::Api(api)) = result {
    println!("{} {:?} {:?}", api.status, api.code, api.conflicts);
}
```

`code` is a string, so a code added after your copy of the client was built
still arrives. `detail` is a `serde_json::Value` holding exactly what the
server sent: a string, for a `409` an object with `message` and `conflicts`, or
for `VALIDATION_FAILED` a list. A body that is not JSON is kept as text.
`Error::Client` covers a request that never got an answer.

## How the client is generated

progenitor reads OpenAPI 3.0 and refuses a document that says 3.1, and it
allows one error response shape per operation. `build.rs` therefore rewrites the
spec in memory before generating:

- The version becomes 3.0.3. The only 3.1 construct in the spec is a `type`
  that is a list with `null`, which becomes `nullable: true`.
- Error responses are dropped from every operation. The retry layer has
  already read the `{"detail", "code"}` body and attached it to the response,
  so `Error::from` can return it as an `ApiError`. The generated error types
  are therefore not used.
- Operations that take `multipart/form-data` are dropped, because progenitor
  cannot send them. The one that exists, the CSV import, is written by hand as
  `Client::ingestion_upload_csv`. It is sent once and never retried.

`sdks/rust/openapi.yaml` is a byte for byte copy of `docs/openapi.yaml`, which
the crate needs because a published crate cannot reach outside its directory.
CI fails when the two differ.

## Regenerating

There is nothing to run. After a change to `docs/openapi.yaml`, copy it over:

```bash
cp docs/openapi.yaml sdks/rust/openapi.yaml
```

The client is rebuilt from that copy by the next `cargo build`. CI fails when the
copy is stale or when progenitor cannot read the new spec. Nothing here is
published to crates.io.
