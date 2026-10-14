# Go client

<!-- Copyright 2026 Chronos Ledger Contributors (Apache 2.0) -->

Module `chronos.vkrishna04.me/sdks/go`, package
`chronos`, in [`sdks/go`](../../sdks/go). The calls are generated from
[openapi.yaml](../openapi.yaml) by `oapi-codegen` and live in the `generated`
package. Go 1.24 or newer to use it (regenerating needs Go 1.25). The only
dependency outside the standard library is `oapi-codegen/runtime`.

## Install

From 0.18.0:

```bash
go get chronos.vkrishna04.me/sdks/go@latest
```

The import path is served by this project's site (`go-import` meta tags at
`https://chronos.vkrishna04.me/sdks/go`) and points at this repository, so
the tags stay `sdks/go/vX.Y.Z`. The existing `sdks/go/v0.17.0` tag still
declares the old GitHub module path and cannot be fetched under the new one.
Until 0.18.0, add the module with a `replace` directive pointing at a checkout:

```bash
go mod edit -require=chronos.vkrishna04.me/sdks/go@v0.0.0
go mod edit -replace=chronos.vkrishna04.me/sdks/go=../Chronos-Ledger/sdks/go
```

Tags are prefixed with the module directory, for example `sdks/go/v0.18.0`.

## Construct a client

```go
import (
	chronos "chronos.vkrishna04.me/sdks/go"
	"chronos.vkrishna04.me/sdks/go/generated"
)

c, err := chronos.New("https://chronos.example.org", chronos.WithAPIKey(os.Getenv("CHRONOS_API_KEY")))
if err != nil {
	return err
}
res, err := c.ResourcesListWithResponse(ctx, &generated.ResourcesListParams{})
```

Every operation is a method on the client, named after its `operationId`
(`resources.list` becomes `ResourcesListWithResponse`). `New` takes the server
root. A trailing `/api/v1` is accepted and dropped, because every generated
path already carries it. The API key goes out as `X-API-Key`. The user agent is
`chronos-go/<version>`.

## Signing in with tokens

Pass `WithTokens` instead of `WithAPIKey`. On a `401` the client calls
`/api/v1/auth/refresh` once and repeats the request. A refresh token works only
once, so store every new pair:

```go
c, err := chronos.New(baseURL, chronos.WithTokens(
	chronos.Tokens{AccessToken: access, RefreshToken: refresh},
	func(t chronos.Tokens) { save(t) },
))
```

Calls that hit a `401` at the same moment share one refresh. Passing both an API
key and tokens is an error from `New`.

## Reservations

```go
hold, err := c.CreateReservation(ctx, 3, generated.ReservationCreate{
	Date:    openapi_types.Date{Time: day},
	Start:   "14:00",
	End:     "15:00",
	Purpose: "Viva",
}, "")
```

The last argument is the `Idempotency-Key`. When it is empty one is made, and
the same key goes out on every retry, so a retry never takes a second hold. Pass
your own key when a retry can come from outside the process, for example after
a crash.

Every other write gets a generated key too, unless the request already has an
`Idempotency-Key` header.

## Retries

A request is sent again when no response arrived, or the status was `429`,
`502`, `503` or `504`, or a `409` whose code is `IDEMPOTENCY_KEY_IN_PROGRESS`.
Any other `4xx` is returned at once. A read is always retried. A write is
retried only because it carries an `Idempotency-Key`, which the client adds.
A request whose body cannot be read again is sent once.

The wait before each retry is a random time between zero and
`min(MaxDelay, BaseDelay * 2^n)` ("full jitter"). A `Retry-After` header, in
seconds or as an HTTP date, replaces it. `DefaultRetryPolicy` is 4 attempts, a
0.25 s base, an 8 s cap and a 30 s deadline. The deadline counts from the first
attempt, and a wait that would pass it is skipped, so the last failure comes
back instead.

```go
chronos.New(baseURL, chronos.WithRetry(chronos.RetryPolicy{
	MaxAttempts: 6,
	BaseDelay:   500 * time.Millisecond,
	MaxDelay:    10 * time.Second,
	Deadline:    time.Minute,
}))
chronos.New(baseURL, chronos.WithoutRetries()) // send everything once
```

`WithHTTPClient` replaces the `http.Client`. The default has a 30 second
timeout per attempt.

## Paging

```go
users := chronos.Paginate(ctx, 100, func(ctx context.Context, limit, offset int) (chronos.Page[generated.UserResponse], error) {
	res, err := c.UsersListWithResponse(ctx, &generated.UsersListParams{Limit: &limit, Offset: &offset})
	if err != nil || res.JSON200 == nil {
		return chronos.Page[generated.UserResponse]{}, err
	}
	return chronos.Page[generated.UserResponse]{Rows: *res.JSON200, Total: res.Headers200.XTotalCount}, nil
})
for user, err := range users {
	if err != nil {
		return err
	}
	fmt.Println(*user.Id)
}
```

`Paginate` returns an `iter.Seq2`. The walk stops once `X-Total-Count` rows have
been seen or a page is empty. The page size defaults to 100.

## Errors

Every status of 400 or above comes back as a `*chronos.Error` in `err`, so the
typed `JSON4xx` fields of a generated response are never filled:

```go
var apiErr *chronos.Error
if errors.As(err, &apiErr) && apiErr.Status == 409 {
	fmt.Println(apiErr.Code, apiErr.Conflicts) // the busy intervals
}
```

`Code` is a plain string, so a code added after your copy of the client was
built still arrives. `Detail` is exactly what the server sent: a string, for a
`409` a map with `message` and `conflicts`, or for `VALIDATION_FAILED` a list. A
body that is not JSON is kept as text.

## Regenerating

After a change to `docs/openapi.yaml`:

```bash
cd sdks/go && go generate ./...
```

The command in `generate.go` pins `oapi-codegen` to one version, and
`oapi-codegen.yaml` holds its settings. Commit `generated/client.gen.go` with
the spec change. CI regenerates it and fails when the committed file is out of
date. The first run downloads the generator and can take several minutes.

Nothing here is published to a registry. The module becomes installable under
`chronos.vkrishna04.me/sdks/go` with the `sdks/go/v0.18.0` tag; `v0.17.0`
resolves only under the old GitHub path.
