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
same key goes out on every retry, so a retry never takes a second hold.

## Retries

`429`, `502`, `503`, `504` and connection errors are retried up to
`max_retries` times (default 3). `Retry-After` is honoured up to 30 seconds;
without it the wait doubles from 0.5 s to at most 8 s. Only `GET`, `HEAD`,
`PUT`, `DELETE`, `OPTIONS` and requests that carry an `Idempotency-Key` are
retried.

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
