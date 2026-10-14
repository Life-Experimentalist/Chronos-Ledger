# Export and import

<!-- Copyright 2026 Chronos Ledger Contributors (Apache 2.0) -->

An organization's data can leave a deployment as one file and go into another,
on the same database engine or the other one. The file is the archive this
page describes. It is for moving a deployment (SQLite to PostgreSQL, one
server to another), for keeping a copy in a form that outlives the database
engine, and for reading the data with ordinary tools.

It is not a backup in the sense of `chronos-engine backup` or `pg_dump`.
Those copy the database whole, secrets and sessions included, and restore it
as it was. The archive leaves secrets out unless asked, never carries
sessions, and goes only into an empty database.

## Making one

From the API, as an `ORG_ADMIN` (an API key needs `admin:read`):

```bash
curl -H "Authorization: Bearer $TOKEN" -o chronos.zip \
  "http://localhost/api/v1/admin/export"
```

The route always leaves out the secrets listed below. It writes the archive
to a temporary file and sends it, so a large organization waits for the whole
export before the download starts. Every export is written to the audit log
with the account, the key and the status, although it is a read.

The route exports the caller's organization only: its row in `organizations`
and the rows of every other table whose `organization_id` is that
organization's. Audit records with no organization (a failed sign-in, which
has no caller) are in no organization's archive. An archive of an
organization other than `default` does not hold the seeded administrator, so
loaded into a new database it gives nobody a password; its own accounts sign
in only if the archive carries their password hashes, which only the command
line can export.

From the command line, against a stopped or running engine, every
organization in the database:

```bash
chronos-engine export --data-dir ./chronos-data --to ./chronos.zip
chronos-engine export --database-url postgresql://chronos:PASSWORD@localhost/chronos --to ./chronos.zip
```

`--include-secrets` adds the secrets. This is the only way to get an archive
with them: the command needs the database itself, so it exposes nothing its
user could not read already, while over HTTP an admin API key or a stolen
admin session would be enough. `--to` must not exist yet. An embedded
deployment keeps its tables in a schema of the host's database, so name it:
`--schema chronos` (see [embedded.md](embedded.md)).

The export is one consistent read. On PostgreSQL it runs as a single
`REPEATABLE READ, READ ONLY` transaction, so writes made while it runs are not
in it and are not held up by it. On SQLite every transaction takes the write
lock (see [standalone.md](standalone.md)), so writes wait until the export
finishes.

## Loading one

```bash
INITIAL_ADMIN_PASSWORD='a password you choose' \
  chronos-engine import --data-dir ./new-data --from ./chronos.zip
chronos-engine import --database-url postgresql://chronos:PASSWORD@localhost/chronos --from ./chronos.zip
```

The target must be empty. A database with no tables is fine, and so is one
whose tables exist with no rows in them. A database a server has already
started on is not empty, because the first start seeds the administrator
account, so run the import before the first `serve`. The tables are built
from the models when they are missing, as the server would.

The whole import is one transaction. If any row is refused, the error names
the file, the line and the column, and the database is left as empty as it
was. Fix the cause and run the import again.

There is no import route on the API. A running server has always seeded its
administrator, so its database is never empty.

## Secrets

These columns are left off every row unless the export was made with
`chronos-engine export --include-secrets`:

| Table | Column | What it is |
|---|---|---|
| `users` | `credential_secure_hash` | The password hash. |
| `users` | `calendar_feed_token` | The secret in the account's calendar feed URL. |
| `api_keys` | `key_hash` | The hash of the key a client sends. |
| `guest_gate_registry` | `visit_code_hash` | The hash of a guest's visit code. |
| `webhook_subscriptions` | `secret` | The key outgoing webhooks are signed with. |
| `webhook_subscriptions` | `previous_secret` | The key before the last rotation, while it still signs. |

The manifest lists them under `omitted_columns`, so a reader can tell a
missing value from a null one.

Two secrets are never in the archive. Refresh tokens are excluded (see
Excluded tables). The signing key (`signing.key`, or `JWT_SECRET_SIGNING_KEY`)
is not data in the database at all. It does not need to move: a new key only
means everyone signs in again, which an import already means.

### After importing an archive without secrets

The import fills each left-out column with a value that opens nothing:

- Every password hash becomes one no password matches, so nobody can sign in
  with a password.
- The seeded administrator, `ADMIN001`, is the exception. The import sets its
  password from `INITIAL_ADMIN_PASSWORD` and refuses to run without it, since
  otherwise nobody could sign in to repair the rest. The account keeps the
  `initial_login_state` it had in the archive.
- Every API key hash becomes the hash of a random value nobody holds, so every
  key stops working. The key rows stay, with their labels, scopes and expiry.
- Calendar feed tokens and visit code hashes become null.
- Every webhook subscription gets a new random signing secret that no
  receiver knows, loses any previous secret, and is paused. A paused
  subscription sends nothing, so nothing goes out signed with a key the
  receiver would refuse. It keeps its place in the change feed.

Then, on the new deployment:

1. Sign in as `ADMIN001` with the password given to the import, and change it
   (`POST /auth/change-password`).
2. Give each person who signs in with a password a new one with
   `POST /users/{user_id}/reset-password`, and pass it on. People who sign in
   through a federated issuer need nothing: their links to the issuer came
   across.
3. Issue a new key (`POST /api-keys/`) for each client that used one, with the
   same scopes, and revoke the old row (`DELETE /api-keys/{key_id}`).
4. Calendar subscriptions stop updating. Each person fetches a new feed URL
   from `GET /sync/feed-token`, which makes a token when there is none, and
   subscribes again.
5. A guest visit that was approved but not yet used has no code anymore. The
   guest registers again.
6. For each webhook subscription, rotate the secret
   (`POST /webhooks/{subscription_id}/rotate-secret`), give the new one to
   the receiver, remove the random one it replaced
   (`DELETE /webhooks/{subscription_id}/previous-secret`), and resume it
   (`POST /webhooks/{subscription_id}/resume`). It then sends what changed
   since its place, oldest first ([webhooks.md](webhooks.md)).

An archive with secrets needs none of this, except that everyone signs in
again. Treat it like a database backup: anyone holding it can try password
hashes offline and holds every calendar feed URL.

## The archive

One zip file. Each table is a member named `<table>.jsonl`, in the order the
import inserts them, and `manifest.json` comes last.

A zip rather than a directory or a tarball because it is one file, every
platform opens it without extra tools, Python's standard library writes it,
a reader can open `manifest.json` without reading past the tables, and each
member is written and read as a stream, so neither side holds a table in
memory. Members are compressed with deflate.

Each `.jsonl` member holds one JSON object per line, one line per row,
ordered by primary key. String keys are ordered by their bytes, whatever the
database's collation. Every object has every column of its table except the
omitted secrets, with keys in sorted order and no spaces. Text is UTF-8 and
not escaped to ASCII.

Values have one written form each:

| Column type | Written as | Example |
|---|---|---|
| Date and time | ISO 8601 in UTC, microseconds, `+00:00` | `"2026-01-06T08:31:02.114000+00:00"` |
| Time of day | `HH:MM:SS.ffffff` | `"09:00:00.000000"` |
| Date | `YYYY-MM-DD` | `"2026-01-06"` |
| Decimal | A string with exactly the column's scale | `"12.97159360"` |
| Enumeration | The value, as the API shows it | `"SCHEDULED"` |
| Integer, boolean, text | JSON's own | `40`, `true`, `"Room 101"` |
| No value | `null` | `null` |

A time of day without a date is the organization's local time, as everywhere
in Chronos. A booking that runs past midnight has an end before its start.

### manifest.json

```json
{
  "format": "chronos-ledger-archive",
  "format_version": 1,
  "omitted_columns": {
    "api_keys": ["key_hash"],
    "guest_gate_registry": ["visit_code_hash"],
    "users": ["calendar_feed_token", "credential_secure_hash"],
    "webhook_subscriptions": ["previous_secret", "secret"]
  },
  "schema_version": "4",
  "secrets_included": false,
  "tables": [
    { "file": "audit_records.jsonl", "name": "audit_records", "rows": 4812 }
  ]
}
```

| Field | Meaning |
|---|---|
| `format` | Always `chronos-ledger-archive`. |
| `format_version` | The version of this layout. See Version rules. |
| `schema_version` | `SCHEMA_VERSION` of the release that wrote it, as `/health` reports it. |
| `secrets_included` | Whether the secret columns are in the rows. |
| `omitted_columns` | Table to the columns left off its rows. Empty when secrets are included. |
| `tables` | Every exported table in insert order: its name, its member, and its row count. |

The import checks each member's row count against `rows`.

### Same bytes every time

An export, an import into an empty database and a second export give the
same bytes, whether the import went into SQLite or PostgreSQL. The zip
carries no times, owners or platform details: every member is dated
1980-01-01 with fixed permissions. Deflate's output depends on the zlib
library, so two machines with different zlib builds can compress the same
rows to different bytes. The unpacked members are equal everywhere.

## Version rules

`format_version` changes when the layout or the written form of any value
changes. A release reads only its own format version. An archive with a
newer one is refused with a message naming both versions; so is one with an
older one or a value that is not a whole number.

`schema_version` must equal the importing release's `SCHEMA_VERSION`, and the
message names both when it does not. There are no migrations yet (see
[standalone.md](standalone.md)), so an archive moves only between releases
with the same schema version. To move data across a schema change, import it
into the release that made it, then follow that release's upgrade notes.

## Tables

The archive holds the tables below, in insert order. A parent comes before
the tables that point at it. `users.reporting_line_manager` points at
`users` itself, so the import leaves it empty on the first pass and fills it
once every user is in.

Units are not a table: a unit is the `unit_code` text on people, rooms and
activities, so it travels with them.

### audit_records

The audit log ([api.md](api.md#audit)): one row per write request, plus one
per read of the conflict report. It points at no other table, so its
`actor_id` and `api_key_id` may name accounts and keys that no longer exist.

### change_markers

The change feed ([api.md](api.md#changes)): one row per change to a room or a
booking, the source of `GET /changes/`.

### federated_issuers

Identity providers this deployment accepts federated sign-in from
([federated-identity.md](federated-identity.md)).

### planning_cycles

Terms or cycles: a label, the first and last date, and whether it is open.

### users

People, including service accounts and the seeded administrator.
`credential_secure_hash` and `calendar_feed_token` are secrets.

### webhook_subscriptions

Outgoing webhooks ([webhooks.md](webhooks.md)): the URL, the event types,
whether each is active or paused, and `cursor`, the last change feed marker
it has turned into deliveries. The markers come across with their ids, so
an imported subscription carries on from the same place. `secret` and
`previous_secret` are secrets. An archive made without them pauses every
subscription on import, active ones included, so a round trip through a
redacted archive leaves them all paused until an administrator resumes
them.

### activities

Courses or other recurring activities, each in a unit and a cycle.

### api_keys

Issued API keys: the key prefix shown in listings, the label, the bound
account, scopes and expiry. `key_hash` is a secret.

### federated_identities

Which issuer subject is which account.

### federated_issuer_keys

The public keys each issuer signs with, and when each is valid.

### federated_role_map

Which group claim from an issuer gives which role, and in which unit.

### guest_gate_registry

Guest visits: who, whom they came to see, the decision and the times.
`visit_code_hash` is a secret.

### resources

Rooms, and people treated as bookable resources, with capacity and location.

### reverse_rsvp_logs

Absence requests and their approval state.

### activity_enrollments

Which member is in which activity.

### reservations

Bookings on resources, held and cancelled ones alike, with the
idempotency key (unique per requester) and request fingerprint that make a
retried booking safe.

### structural_master_slots

The weekly timetable: day of week, start and end, activity, lead and room.

### daily_ledger

The days materialized from the timetable, and one-off entries, each with its
state (scheduled, on leave, substituted and so on).

### ledger_annotations

Notes attached to a ledger day.

### verification_ledger

Attendance marks: one per member per ledger day.

## Excluded tables

| Table | Why it stays behind |
|---|---|
| `refresh_tokens` | Hashes of one-use session tokens that expire within days. Carrying them would carry live sessions into another deployment. After an import everyone signs in again. |
| `idempotency_records` | Stored responses for `Idempotency-Key` retries, deleted after `IDEMPOTENCY_RETENTION_HOURS`. They copy what a write already returned. A client that retries against the imported deployment has its write treated as a new request. |
| `webhook_deliveries` | The outgoing webhook queue and what was sent. An imported subscription carries on from its cursor instead, so nothing that was already sent from the old deployment is sent again from the new one. Anything still pending there when the archive was made is not sent from the new one either. |
| `webhook_attempts` | The record of each send: status code, time taken and the start of the reply. It describes the deployment that made the calls, not the organization's data. |

`backend/tests/test_portability.py` fails when a table is neither exported
nor on this list, so a new table cannot be left out of the archive by
accident. Add it to `EXCLUDED` in `backend/app/services/portability.py` with
its reason, or let it be exported and give it a section here.
