# Python client

<!-- Copyright 2026 Chronos Ledger Contributors (Apache 2.0) -->

Package `chronos-ledger-client`, import name `chronos_ledger_client`, in
[`sdks/python`](../../sdks/python). The calls are generated from
[openapi.yaml](../openapi.yaml) by `openapi-python-client` and live in
`chronos_ledger_client.generated`. Python 3.10 or newer; depends on `httpx`
and `attrs`.

## Install

The package is not on PyPI yet. Install it from a checkout:

```bash
pip install ./sdks/python
```

With uv, `uv add ./sdks/python` from your project does the same.

## Construct a client

```python
import os

import chronos_ledger_client as chronos
from chronos_ledger_client.generated.api.resources import resources_list

client = chronos.connect("https://chronos.example.org", api_key=os.environ["CHRONOS_API_KEY"])
resources = resources_list.sync(client=client)
```

Each operation is a module under `generated.api.<area>`, named after its
`operationId`, with `sync` and `sync_detailed`. Auth, retries and errors
below come from the transport that `connect` installs, which serves the sync
calls.

## Signing in with tokens

```python
client = chronos.connect(
    base_url,
    tokens=chronos.Tokens(access_token, refresh_token),
    on_tokens=save,
)
```

On a `401` the client calls `/api/v1/auth/refresh` once and repeats the
request. A refresh token works only once, so `on_tokens` must store each new
pair. Threads that hit a `401` together share one refresh. Passing both
`api_key` and `tokens` raises `ValueError`.

## Reservations

```python
import datetime as dt

from chronos_ledger_client.generated.models import ReservationCreate

hold = chronos.create_reservation(
    client,
    3,
    ReservationCreate(date=dt.date(2026, 1, 6), start="14:00", end="15:00", purpose="Viva"),
)
```

An `Idempotency-Key` is generated when `idempotency_key` is not given, and the
same key goes out on every retry, so a retry never takes a second hold. Every
other write gets a key too, see [Retries](#retries).

## Retries

A request is tried again when:

- no response arrived: a refused or dropped connection, or a timeout;
- the status is `429`, `502`, `503` or `504`;
- the status is `409` and the body code is `IDEMPOTENCY_KEY_IN_PROGRESS`, which
  means the first request under that key is still running. The same key gets
  the stored answer once it finishes.

No other `4xx` is retried: `400`, `401` (after the one token refresh), `403`,
`404`, `422` and a plain `409` conflict come straight back as `ChronosError`.

Every write (`POST`, `PATCH`, `PUT`, `DELETE`) is sent with an
`Idempotency-Key`: the header you set, or a UUIDv4 the client makes once per
call and sends again on each retry, so a retried write has one effect. A write
is never sent without a key, which is why writes can be retried at all. `GET`,
`HEAD` and `OPTIONS` carry none.

The wait before retry `n` (counting from 0) is a random number between 0 and
`min(max_delay, base_delay * 2**n)`. When the response has a `Retry-After`
header, in seconds or as an HTTP date, the client waits that long instead. A
wait that would run past the deadline is not started: the last response is
raised instead.

Settings go in a `RetryPolicy`:

```python
client = chronos.connect(
    base_url,
    api_key=key,
    retry=chronos.RetryPolicy(max_attempts=6, base_delay=0.5, max_delay=10.0, deadline=60.0),
)
```

| Setting | Default | Meaning |
|---|---|---|
| `max_attempts` | 4 | Tries in all, the first included |
| `base_delay` | 0.25 | Seconds; the first jitter ceiling |
| `max_delay` | 8.0 | Seconds; the highest a jittered wait can reach |
| `deadline` | 30.0 | Seconds from the first send; no wait starts past it |

`retry=None` turns retries off. A write still carries its key. The deadline
does not interrupt a request in flight, so set `timeout` for that.

When the tries or the deadline run out, a response error is raised as
`ChronosError` with the status, `code` and `detail` of the last response, and a
transport error is raised as the `httpx` exception it was.

## Paging

```python
from chronos_ledger_client.generated.api.users import users_list

for user in chronos.paginate(users_list, client=client, page_size=50):
    print(user.id)
```

Extra keyword arguments go to the operation. The walk stops once
`X-Total-Count` rows have been seen or a page is empty.

## Errors

Every status of 400 or above raises `chronos.ChronosError` with `status`,
`detail` (as the server sent it) and `conflicts` (the busy intervals of a
`409`, otherwise empty):

```python
try:
    chronos.create_reservation(client, 3, body)
except chronos.ChronosError as error:
    if error.status == 409:
        print(error.conflicts)
```

## Regenerating

After a change to `docs/openapi.yaml`, from `sdks/python`:

```bash
uvx --from openapi-python-client==0.29.1 openapi-python-client generate --path ../../docs/openapi.yaml --meta none --config openapi-python-client.yaml --output-path src/chronos_ledger_client/generated --overwrite
```

Delete the `.ruff_cache` it leaves inside `generated`, then commit the result
with the spec change. CI runs the same command and fails when the committed
code is out of date.
