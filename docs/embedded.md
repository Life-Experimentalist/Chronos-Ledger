# Embedded engine

<!-- Copyright 2026 Chronos Ledger Contributors (Apache 2.0) -->

`chronos-engine embedded` runs Chronos Ledger as a hidden child process of
another program: a hospital system, a campus system, a game. The host starts
it, reads one line from its stdout to learn the port, talks to it over
loopback, and the process exits when the host does. Nobody visits it and
nobody signs in to it: the host already knows who its user is and says so on
every request.

It is the standalone engine ([standalone.md](standalone.md)) with three
changes: identity comes from the host instead of a login, the routes that only
make sense with Chronos-owned logins are not mounted, and the process ties
its life to the host's. Everything else (one worker, no Redis, the scheduler
jobs, a SQLite file or a local PostgreSQL) is as standalone describes. The
container deployment and `chronos-engine serve` are unchanged.

## Starting it

```bash
CHRONOS_HOST_SECRET=... chronos-engine embedded --data-dir ./chronos-data
```

| Option | Default | Meaning |
|---|---|---|
| `--data-dir PATH` | `chronos-data` | Holds the SQLite file and `signing.key`. |
| `--database-url URL` | none | The host's PostgreSQL. Without it, SQLite at `--data-dir/chronos.db`. |
| `--schema NAME` | `chronos` | The PostgreSQL schema Chronos lives in (below). Not used with SQLite. |
| `--port N` | `0` | TCP port on 127.0.0.1. `0` picks a free one, reported in the ready line. |
| `--socket PATH` | none | Listen on a Unix socket instead of a port. POSIX only. |
| `--secret-from-stdin` | off | Read the host secret from the first line of stdin instead of the environment. |
| `--parent-pid N` | none | Also exit when this process is gone (polled once a second). |
| `--log-level LEVEL` | `info` | Logs go to stderr. |

The process binds 127.0.0.1 only, serves no frontend, no `/docs` and no
OpenAPI document, and sends no CORS headers. There is nothing for a browser
to reach.

### The host secret

The host and Chronos share one secret of at least 32 characters. Chronos
reads it from the `CHRONOS_HOST_SECRET` environment variable, or from the
first line of stdin with `--secret-from-stdin`, and refuses to start without
one. It is never taken from the command line, where every process on the
machine could read it. Generate a fresh one each time the host starts
Chronos; it only has to live as long as the child process.

### The ready line

When the process is listening, with the schema built and the scheduler
running, it prints exactly one line to stdout and nothing else, ever:

```json
{"chronos": "ready", "port": 54321, "schema_version": "1"}
```

With `--socket` the line carries `"socket": "/path"` in place of `"port"`.
`schema_version` is what `/health` reports (`backend/app/core/schema.py::SCHEMA_VERSION`).
Logs go to stderr, so a host can read stdout line by line and treat the first
line as the announcement. Until it arrives, `GET /health` is also answered,
without the secret.

## Every request

Two headers on every request except `/health` and `/health/ready`:

```
Authorization: Host <secret>
X-Chronos-Actor: <the host's stable id for the person>
```

and on every request that needs an account (nearly all of them):

```
X-Chronos-Actor-Role: ORG_ADMIN | UNIT_ADMIN | STAFF | MEMBER
X-Chronos-Actor-Name: <display name>            optional
X-Chronos-Actor-Email: <address>                optional
```

The secret is compared in constant time by
`backend/app/core/host_identity.py::HostSecretMiddleware`. A missing or wrong
one is `401 {"detail": "Not authenticated"}` with `WWW-Authenticate: Host`,
the same shape as a bad token in the ordinary flavour, and the attempt is
written to the audit log. The two routes that need no account in the ordinary
flavour (the labels at `GET /api/v1/config`, a visitor's own status at
`GET /api/v1/guest/visit/{code}`) still need the secret here, since nothing
but the host may reach the process at all. A guest check-in, which a kiosk
makes with an API key in the other flavours, is made here by the host with an
actor, `system` or the desk's own user.

The actor headers are read by `backend/app/core/host_identity.py::host_actor`,
which takes the place of the token check
(`backend/app/core/security.py::get_current_user_id`). Everything built on
that, the current-user lookup, the role and unit checks, the audit record's
`actor_id`, runs unchanged. No JWT or API key is looked at in this flavour:
the code that reads them is not reachable.

What the host asserts is the truth:

- The actor id is the Chronos user id, up to 50 characters. The first time an
  id is seen an account is made for it with the role and name from the
  headers; there is no password to set or remember. After that the role,
  name and email are brought up to date from the headers on every request,
  and a change on the host's side takes effect on the next call.
- `X-Chronos-Actor-Role` is required for every id except `system`, and must
  be an `InstitutionalRole` name; anything else is `400`. Scope rules apply
  as they do everywhere: a `UNIT_ADMIN` sees their unit, a `MEMBER` their own
  rows. A unit is not asserted by header; set `unit_code` with
  `PATCH /api/v1/users/{id}` as an administrator when the host first sees a
  unit administrator.
- `X-Chronos-Actor-Email` is optional. Without it the account gets a
  placeholder address under `host.invalid`, which cannot receive mail. An
  address already on another account is `409`.
- The id `system` is reserved for the host itself: an `ORG_ADMIN` account
  seeded when the database is prepared
  (`backend/app/core/host_identity.py::seed_system_account`), for the host's
  own imports, reports and scheduled work. The role header is ignored for it.
- An account Chronos has deactivated stays out (`401 Account deactivated`)
  whatever the host asserts, so the usual `deactivate` and `reactivate`
  routes still mean something.

Audit records carry the actor id the host sent, exactly as a logged-in user's
id is carried in the other flavours.

## What is not mounted

The API is a subset of the one in [openapi.yaml](openapi.yaml), so the SDKs
work as they are. Decided route by route
(`backend/app/embedded.py::STRIPPED_OPERATIONS`); everything not listed here
is mounted as it is.

| Operation ids | Why |
|---|---|
| `auth.login`, `auth.federated`, `auth.refresh`, `auth.logout`, `auth.changePassword`, `auth.getMe` | Sessions and passwords. There are no Chronos-owned credentials, so there is nothing to log in with, refresh, or change. `auth.getMe` is the current-session lookup; the host already knows who it is. |
| `apiKeys.create`, `apiKeys.list`, `apiKeys.revoke` | API keys are a second Chronos-owned credential. |
| `users.create`, `users.resetPassword` | Accounts are made by the host asserting an id; there is no password to set or reset. The other user routes (list, get, update, status, deactivate, reactivate) stay. |
| `sync.getFeedToken`, `sync.rotateFeedToken`, `sync.getFeed` | Calendar feed tokens are a credential of their own, and the feed they unlock is for a calendar program reaching the port, which a hidden child process has no reason to allow. |
| `federation.*` (issuers, keys, role map, links) | Federated sign-in is another way to obtain a Chronos session. |
| `/ws` (websocket) and `ws.getStats` | The websocket authenticates with a JWT in its first frame, and there is no JWT. Live updates are not available in this flavour; poll `/api/v1/changes`. |

A call to any of these is `404`.

## The database

### A schema of the host's PostgreSQL

With `--database-url`, Chronos lives inside one schema of the host's
database, `chronos` unless `--schema` says otherwise. The schema is created
if missing, and every pooled connection has its `search_path` set to that
schema alone (`backend/app/core/database.py::use_schema`), so every table,
type, index and exclusion constraint Chronos makes lands there, and a host
table that happens to share a name, `public.users` say, is neither seen nor
touched. The database role Chronos connects as needs `CREATE` on the database
the first time (to make the schema and, if the host does not have it yet, the
`btree_gist` extension) and ordinary rights on its own schema after that. If
the host already has `btree_gist`, in whatever schema, it is used as it is.
`tests/test_embedded_pg.py` is the proof, against a real PostgreSQL in CI.

### Or a SQLite file

Without `--database-url` the engine uses `--data-dir/chronos.db`, as
standalone does, with the same locking and the same `chronos-engine backup`.
`--schema` is ignored with a note in the log: a SQLite file has no schemas.

## Lifecycle

The process exits when the host goes away, in whichever of these happens
first:

- **stdin closes.** The default, and the portable one: the pipe the host
  opened for the child's stdin closes when the host exits, cleanly or not, on
  Windows and POSIX alike. Keep that pipe open for as long as Chronos should
  run; closing it is also the polite way to stop the engine. With
  `--secret-from-stdin` the first line is the secret and the pipe is watched
  from there. Anything else written to it is read and ignored. Do not start
  the process with stdin on `/dev/null` or closed; that reads as a host that
  has already gone.
- **`--parent-pid N` is gone.** Polled once a second, for a host that cannot
  keep a pipe open.
- **SIGTERM, SIGINT, or CTRL_BREAK on Windows.** Handled by uvicorn.

Every one of these is a clean stop: the lifespan shutdown runs, the scheduler
stops and, on SQLite, the write-ahead log is folded into the file.

## A host, in outline

```go
// Pseudo-Go. Error handling left out.
secret := randomString(48)
cmd := exec.Command("chronos-engine", "embedded",
    "--data-dir", dataDir,
    "--database-url", hostDatabaseURL, "--schema", "chronos",
    "--secret-from-stdin", "--parent-pid", strconv.Itoa(os.Getpid()))
stdin, _ := cmd.StdinPipe()      // keep this open for the life of the host
stdout, _ := cmd.StdoutPipe()
cmd.Stderr = hostLog
cmd.Start()
fmt.Fprintln(stdin, secret)

var ready struct {
    Port          int    `json:"port"`
    SchemaVersion string `json:"schema_version"`
}
json.NewDecoder(stdout).Decode(&ready)     // blocks until the one line arrives
base := fmt.Sprintf("http://127.0.0.1:%d/api/v1", ready.Port)

// For every call on behalf of a signed-in user of the host:
req, _ := http.NewRequest("GET", base+"/schedule/ledger?...", nil)
req.Header.Set("Authorization", "Host "+secret)
req.Header.Set("X-Chronos-Actor", user.ID)
req.Header.Set("X-Chronos-Actor-Role", "STAFF")
req.Header.Set("X-Chronos-Actor-Name", user.DisplayName)

// On exit: stdin.Close(), then wait for the process. The parent-pid watch is
// the fallback if the host dies without closing anything.
```

Any SDK in [sdks.md](sdks.md) can be pointed at the base URL and given the
headers as defaults; the request and response shapes are the published ones.
