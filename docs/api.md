# API Reference

<!-- Copyright 2026 Chronos Ledger Contributors (Apache 2.0) -->

**Machine-readable contract**: [`docs/openapi.yaml`](openapi.yaml): OpenAPI 3.1.

**Interactive UI** (live server): `http://<server>/docs` (Swagger UI) · `http://<server>/redoc` (ReDoc)

Both, and `/openapi.json` with them, follow `DOCS_ENABLED`: off under
`APP_ENV=production` unless you set it, on everywhere else. A production
instance that publishes them hands its whole surface to anybody who finds
the host, so the file above is the contract to work from.

Base URL: `http://<server>/api/v1`

---

## Configuration

### GET /config `[public]`

What a client needs before anyone has logged in: which vocabulary to render,
and how short a password this deployment will accept.

```json
{
  "labels": {
    "staff": "Faculty",
    "member": "Student",
    "activity": "Course",
    "unit": "Department",
    "lead": "Instructor",
    "cycle": "Academic Year"
  },
  "password_min_length": 12
}
```

The label keys are always the same six. Each is set on its own with
`LABEL_STAFF`, `LABEL_MEMBER`, `LABEL_ACTIVITY`, `LABEL_UNIT`, `LABEL_LEAD` or
`LABEL_CYCLE`, and anything left blank comes back as the engine's own neutral
word: `Staff`, `Member`, `Activity`, `Unit`, `Lead`, `Cycle`. There is no
domain preset behind them, so the words above are one deployment's choices and
not a mode you can select. Labels are display only: no field name in this
document changes with them.

Labels change nothing else. The field names in this reference, the database
columns and the CSV headers stay as they are whatever the interface calls them,
so an integration reads `member_id` on a campus and `member_id` in a hospital.
[docs/vocabulary.md](vocabulary.md) is the whole subject, including which value
sets are closed and why.

`password_min_length` follows `PASSWORD_MIN_LENGTH`. Nothing here is a secret:
a caller learns the password floor from a single rejected change anyway.

---

## Authentication

All endpoints except `/auth/login`, `/auth/refresh`, `/auth/logout`, the
`/config` document above and the calendar feed require a Bearer token:

```
Authorization: Bearer <access_token>
```

Access tokens expire after `JWT_ACCESS_TOKEN_EXPIRE_MINUTES` (default: 15).
`POST /auth/refresh` exchanges the refresh token returned by `/auth/login` for a
new pair; refresh tokens are single use and last
`JWT_REFRESH_TOKEN_EXPIRE_DAYS` (default: 30). A used refresh token presented
again more than ten seconds after its use is taken to be in two hands: every
token descended from the same sign-in stops working and the client has to sign
in again. Inside those ten seconds the repeat is refused and nothing else
changes, which is what two tabs refreshing together look like.
`POST /auth/logout` ends the sign-in its refresh token belongs to.

An API key in `X-API-Key` is accepted anywhere a Bearer token is. See
[API keys](#api-keys).

### Rate limits

Three routes carry a budget per caller, counted over a fixed window:

| Route                              | Counted per                                  | Default                          |
| ---------------------------------- | -------------------------------------------- | -------------------------------- |
| `POST /auth/login`                 | calling address, and separately the account  | 10 and 5 failures per 15 minutes |
| `POST /guest/register-checkin`     | the account the kiosk's API key belongs to   | 300 per hour                     |
| `GET /sync/user-feed/{token}.ics`  | the feed token                               | 60 per hour                      |

Only failed sign-ins are counted; a correct password costs nothing. Past the
budget the answer is a `429` carrying `Retry-After` in seconds:

```json
{ "detail": "Too many sign-in attempts from this address. Try again in 840 seconds." }
```

Every number is a setting, `RATE_LIMIT_*` in [`.env.example`](../.env.example).
A count of `0` turns that one limiter off and `RATE_LIMIT_ENABLED=false` turns
off all three. The counters live in Redis; an instance that cannot reach Redis
stops applying the limits rather than refusing the requests.

### Role hierarchy

```mermaid
graph TD
    SA[SUPER_ADMIN] --> DA[UNIT_ADMIN]
    DA --> FAC[STAFF]
    FAC --> STU[MEMBER]
```

Higher roles inherit the permissions of all roles below them. Role is embedded in the JWT payload and validated server-side on every request.

---

### POST /auth/login

```json
// Request
{ "email": "user@org.internal", "password": "…" }

// Response 200
{
  "access_token": "<jwt>",
  "token_type": "bearer",
  "user_id": "FAC001",
  "role": "STAFF",
  "full_name": "Dr. Priya Sharma",
  "initial_login_state": false
}
```

`initial_login_state: true` on first login, the client should redirect to the change-password flow.

### POST /auth/change-password

```json
{ "current_password": "…", "new_password": "…" }
```

`new_password` must be at least `PASSWORD_MIN_LENGTH` characters, 12 unless the
deployment has raised it, and must not be one of the placeholder passwords
published in this repository. Either refusal is a `422` naming the rule.
Repeating the current password is a `400`: the first-login gate exists to move
the account off the password it was handed, and setting it back to itself would
satisfy the flag while changing nothing.

A successful change ends every session the account had, rotates its calendar
feed token (any subscribed calendar stops updating and needs the new URL from
`GET /sync/feed-token`), and returns a replacement refresh token for the caller:

```json
{ "message": "Password updated successfully", "refresh_token": "..." }
```

Store it over the one you hold. Skip that and the browser that changed the
password is signed out as soon as its access token expires.

### GET /auth/me

Returns the current user's `UserResponse` (see Users section).

---

## API keys

A key authenticates a machine the way a token authenticates a person. Send it
in `X-API-Key` and it works on every endpoint a token works on. It acts as the
user it is bound to, so bind one to a service account and not to a person: a
key bound to an admin can do everything that admin can.

Unlike a token, a key can be narrowed to part of the API and can be made to
run out.

### Scopes

A scope is `<area>:read` or `<area>:write`. The area is the path segment after
`/api/v1`, and `GET`, `HEAD` and `OPTIONS` are reads while everything else is
a write. The scope a request needs is therefore read off the request, which
means no endpoint has to opt in to being covered and a new endpoint cannot
land open by nobody remembering to annotate it.

| Area | Covers |
|---|---|
| `config` | `/config` |
| `auth` | login, password change, `/auth/me` |
| `api-keys` | issuing, listing and revoking keys |
| `users` | the user directory |
| `resources` | rooms and their availability |
| `schedule` | slots, the daily ledger, cycles, staff locations |
| `attendance` | marking, absence requests, annotations |
| `guest` | the kiosk endpoints |
| `ingestion` | CSV upload and ledger generation |
| `sync` | the calendar feed |

A key holding `schedule:read` passes `GET /schedule/slots` and is refused
`POST /schedule/slots` with `403` and a detail naming `schedule:write`. The
same key is refused `GET /users/` naming `users:read`: holding one area says
nothing about another.

A scope narrows what the bound account may do and never widens it. The role
checks still run as that account, so a key holding `resources:write` that is
bound to a `STAFF` account reads rooms and is refused a hold, which needs
`UNIT_ADMIN`. See [Service accounts](#service-accounts).

The single scope `*` is every area. That is what a key created without naming
any scopes gets, and what every key issued before scopes existed was
backfilled to, so nothing that worked before stopped working. `GET /api-keys/`
shows the scopes of each key, which is how you find the unrestricted ones.

### Expiry

`expires_at` is checked on the request rather than by a sweep, so a key stops
working the moment it runs out, answering `401` with `API key expired`. Omit
the field for a key that never runs out. A time already in the past is refused
at creation: a key that is dead on arrival is a mistake, not a request.

### Service accounts

An admin account signing in with a password is held at the first-login gate
until it changes the password it was handed (see
[POST /auth/change-password](#post-authchange-password)). A request made with a
key is not held there: the gate exists to move a person off that password, and
a key never uses it. Issuing a key already takes a `SUPER_ADMIN` who has cleared
the gate.

So a service account takes two steps, and nobody signs in as it:

1. `POST /users/` at the role the routes it calls require. Creating and editing
   rooms needs `SUPER_ADMIN`; holding and releasing them needs `UNIT_ADMIN` or
   above.
2. `POST /api-keys/` bound to that account, scoped to the areas it calls (for a
   room-booking integration, `resources:read` and `resources:write`), with an
   `expires_at`.

The password set in step 1 is never used. Anyone who signs in with it still
meets the gate.

### POST /api-keys/ `[SUPER_ADMIN]`

```json
{
  "label": "PulseWard HMS",
  "user_id": "SVC001",
  "scopes": ["schedule:read", "resources:read"],
  "expires_at": "2027-01-01T00:00:00Z"
}
```

`scopes` and `expires_at` are both optional. Omitting `scopes` gives `*`; an
empty array is refused, since a key that can reach nothing is not a key
anybody wants.

```json
{
  "id": 3,
  "key_prefix": "ck_8Kd2mQ7x",
  "label": "PulseWard HMS",
  "user_id": "SVC001",
  "scopes": "resources:read,schedule:read",
  "expires_at": "2027-01-01T00:00:00Z",
  "created_at": "2026-09-09T10:14:00Z",
  "api_key": "ck_8Kd2mQ7xR3nL9vB5tY1wZ0aC6eF4gH2jK8mN"
}
```

`api_key` appears here and nowhere else. Only its hash is stored, so a lost
key is revoked and reissued, never recovered. Scopes come back sorted and
deduplicated.

### GET /api-keys/ `[SUPER_ADMIN]`

Every key, without its secret.

### DELETE /api-keys/{key_id} `[SUPER_ADMIN]`

Revokes immediately: the next request using it gets `401`.

---

## Users

### GET /users/ `[ADMIN]`
### POST /users/ `[SUPER_ADMIN]`

Create users individually. For bulk creation, use CSV import (`POST /ingestion/upload-csv`).

```json
// POST body
{
  "id": "FAC042",
  "full_name": "Dr. Rajan Mehta",
  "email_address": "rajan@org.internal",
  "password": "InitialPass1!",
  "role_type": "STAFF",
  "unit_code": "CSE",
  "assigned_base_station": "Front Desk",
  "reporting_line_manager": "HOD001"
}
```

### GET /users/staff/available `[public]`

Returns staff with `OPEN_AD_HOC` or `VERY_FREE` status. Used by the Guest Kiosk.

### GET /users/{user_id}
### PATCH /users/{user_id} `[ADMIN]`

### POST /users/{user_id}/reset-password `[ADMIN]`

Issues a new random password for someone who cannot sign in, and returns it
once:

```json
{ "user_id": "STU042", "initial_password": "kQ7mZ2pV1xNc" }
```

This is the only way back into a locked-out account: `POST
/auth/change-password` needs the password the user has lost, and there is no
mail sender configured to put a reset link through. Copy the value before
closing the response. It is not stored, and calling the endpoint again issues
a different one.

A reset drops every refresh token the user holds and rotates their calendar
feed URL, so it doubles as the response to a compromised account. A
`UNIT_ADMIN` may only reset users inside their own unit, and may not reset an
admin account.

### PUT /users/{user_id}/status

Update staff occupancy. Enum values: `OPEN_AD_HOC`, `BUSY`, `CRITICAL_DO_NOT_DISTURB`, `VERY_FREE`.

```json
{ "status": "BUSY" }
```

---

## Resources

A resource is a thing the schedule can point at: a room, a person, a piece of
equipment. A room comes into being when a CSV import or a slot first names it,
or ahead of that through `POST /resources/`, which is how a system that manages
its own rooms registers one. An imported room knows only its name, so its
capacity and coordinates are filled in with `PATCH`.

### GET /resources/

Optional filters: `resource_type` (`ROOM` or `PERSON`), `active`, `code`.
Readable by anyone signed in.

```json
[
  {
    "id": 12,
    "code": "LH-3",
    "label": "Lecture Hall 3",
    "resource_type": "ROOM",
    "unit_code": null,
    "capacity": 90,
    "user_id": null,
    "latitude": 12.9716,
    "longitude": 77.5946,
    "altitude_target": 920.0,
    "active": true
  }
]
```

### POST /resources/ `[SUPER_ADMIN]`

Register a room before any timetable names it.

```json
{
  "code": "LH-3",
  "label": "Lecture Hall 3",
  "unit_code": "CSE",
  "capacity": 90,
  "latitude": 12.9716,
  "longitude": 77.5946,
  "altitude_target": 920.0
}
```

Only `code` is required. It is trimmed, the same as the importer trims a room
name, so a room created here and the same name in a later CSV are one row and
the import attaches its slots to this one. `label` defaults to the code.
`latitude` and `longitude` come as a pair or not at all, the same rule as on
`PATCH`.

The answer is `201` with the room in the shape `GET /resources/` returns. A code
already taken, whether by a room created here or one an import made, is `409`
(`a resource with that code already exists`). That is also what a retry gets
when its first attempt went through and the response was lost, so a caller that
meets `409` reads the room back with `GET /resources/?code=` and carries on. No
`Idempotency-Key` is taken: the code already is one.

Rooms only. There is no delete either: retiring a room is `PATCH` with
`"active": false`, which keeps its calendar and every slot and day that points
at it.

### GET /resources/{id}/availability?from={date}&to={date}

When the resource is already taken, between two dates inclusive. Both
parameters are required.

```json
{
  "resource_id": 12,
  "code": "LH-3",
  "from": "2026-01-05",
  "to": "2026-01-11",
  "busy": [
    {
      "date": "2026-01-05",
      "start": "09:00:00",
      "end_date": "2026-01-05",
      "end": "10:00:00",
      "activity_id": 4,
      "activity_code": "CS101",
      "master_slot_id": 7,
      "reservation_id": null
    },
    {
      "date": "2026-01-05",
      "start": "22:00:00",
      "end_date": "2026-01-06",
      "end": "06:00:00",
      "activity_id": null,
      "activity_code": null,
      "master_slot_id": null,
      "reservation_id": 31
    }
  ]
}
```

Busy intervals, not free ones. Free time is the complement against whatever
hours the caller considers open, and only the caller knows those.

Times are naive wall clock in the organisation's own timezone, the same as the
slot stores. They carry no offset and no `Z`.

What counts as taken: a weekly slot pointing at this resource whose cycle is
flagged open, on the dates from that cycle's `date_bounds_start` to its
`date_bounds_end`, both included; any reservation on it that has not been
cancelled; and any day the nightly generator has already written for it. The
flag and the dates are the two tests nightly ledger generation applies, so a
date reported free here is not one the generator is going to fill.

A generated day counts whatever its cycle now says. Closing a cycle stops the
generator producing more days but does not withdraw the ones it produced, and
deleting a slot leaves behind the days attendance was marked on. Those rows
still hold a room and an hour, and the database refuses a second booking on
top of them either way, so they are reported here too.

Where a generated day and the slot it came from both cover a date, you get the
day, once. The day is the row that holds the hour. It keeps the window it was
generated with when the slot is corrected later, so a moved class reads at its
old time until the days already in use have run. Dates the generator has not
reached yet still come from the slot, which is what answers for the rest of
the year.

Which kind an interval is can be read off the fields that are filled in. A
slot carries `activity_id`, `activity_code` and `master_slot_id` with a null
`reservation_id`; a reservation carries the reverse. What a booking is for is
deliberately not here: this route is readable by anyone signed in, and the
purpose is returned only to the caller that made the booking.

An interval carries `end_date` as well as `date`, and the two differ when the
window ran past midnight. `date` is the day it opened on, which for an
overnight interval is the day before the one it occupies, so an interval's
`date` can be earlier than `from`: a booking dated Monday from `22:00` to
`06:00` is on Tuesday's calendar and comes back when you ask about Tuesday.
Read each interval by its own `date` and `end_date` and not by the range that
returned it. Grouping by `date` alone files that hold under a day nobody asked
about, and discarding anything outside the range shows a ward as free while it
is staffed.

`PATCH /schedule/ledger/{id}` cannot move a day's date, hour or resource, so
nothing it changes shows up here. An inactive resource still answers:
retiring a room does not clear its calendar.

`from` after `to` is `422` (`from must not be after to`). A range longer than
366 days inclusive is `422` (`the range must not exceed 366 days`), which
leaves room for the next twelve months from any date, leap years included.

### PATCH /resources/{id} `[SUPER_ADMIN]`

```json
{
  "label": "Lecture Hall 3",
  "capacity": 90,
  "latitude": 12.9716,
  "longitude": 77.5946,
  "altitude_target": 920.0,
  "active": true
}
```

Every field is optional, and a field left out is left alone. `latitude` and
`longitude` are set or cleared together: sending one without the other is
`422`, since half a location fences the room to a point on the equator.
Setting them is what switches geofencing on for every session held there, so
until a room is placed, its sessions are not fenced at all.

`code`, `resource_type` and `user_id` cannot be changed here. `code` is the
importer's match key, so renaming it would make the next upload create a
second row rather than find this one; change `label` instead, which is what
gets shown. A room that becomes a person is not an edit, it is a different
resource.

### POST /resources/{id}/reservations `[SUPER_ADMIN, UNIT_ADMIN]`

Hold a resource for one dated window. This is the route an outside system uses
to take a room: a hospital system books a consulting room here the same way an
admin would.

An `Idempotency-Key` header is required, 8 to 120 characters, and a UUID is
the right shape. It is required rather than optional because a booking client
talking over a network retries, and a retry that books a second room is worse
than one that fails outright.

```json
// POST /api/v1/resources/12/reservations
// Idempotency-Key: 6f1c2e40-2c5f-4d0e-9a5b-1c7c0f9c3a11
{
  "date": "2026-01-06",
  "start": "14:00",
  "end": "15:00",
  "purpose": "Ward round"
}
```

`201` with the hold:

```json
{
  "id": 31,
  "resource_id": 12,
  "resource_code": "LH-3",
  "date": "2026-01-06",
  "start": "14:00:00",
  "end": "15:00:00",
  "purpose": "Ward round",
  "status": "HELD",
  "requested_by_id": "ADM001",
  "idempotency_key": "6f1c2e40-2c5f-4d0e-9a5b-1c7c0f9c3a11",
  "created_at": "2026-01-05T09:14:22Z",
  "cancelled_at": null
}
```

The same key sent again with the same body returns `200` and the original row,
cancelled or not: a retry is asking what happened, not asking for a second
room. The same key with a different body is `422` (`that Idempotency-Key was
used for a different request`). The resource is part of what the key is
checked against, so pointing one key at two different rooms is that same
`422` rather than a quiet double booking.

`409` when something already has part of the window, and the body says what it
ran into:

```json
{
  "detail": {
    "message": "the resource is already taken for part of that window",
    "conflicts": [
      {
        "date": "2026-01-06",
        "start": "14:30:00",
        "end_date": "2026-01-06",
        "end": "15:30:00",
        "activity_id": null,
        "activity_code": null,
        "master_slot_id": null,
        "reservation_id": 28
      }
    ]
  }
}
```

Windows are half open, so an interval ending at ten and one starting at ten do
not clash. Back to back bookings are the normal case and refusing them would
make a room unusable in any schedule that runs on the hour.

An `end` earlier than the `start` means the window runs past midnight and
finishes on the day after `date`: `22:00` to `06:00` is a night shift of eight
hours, not a negative sixteen. No field says which day the end falls on, only
that rule. `end` equal to `start` is `422`, because `09:00` to `09:00` is
either nothing at all or a full day and there is no way to tell which was
meant.

A weekly slot reads its two times by the same rule, so a night shift can be a
recurring slot and not only a one off hold, and an overnight booking is
checked against night shifts on the timetable as well as against day ones.

What this refuses is exactly what `GET availability` calls busy: the same
three queries, through the same expansion. The rule runs both ways. A class cannot
be put on top of a hold either, so `POST /schedule/slots`, `PATCH
/schedule/slots/{id}` and a CSV upload are each refused where a booking
already stands. A hold taken here holds against the timetable and not only
against other holds.

Two callers racing for the same window are serialised by a row lock on the
resource, two copies of one request collide on the unique key index, and
underneath both sits an exclusion constraint over the window itself, added
by migration 010. The second row is refused whatever order the two callers
arrive in. When the constraint is what catches it, the window is looked up
again and the `409` names the hold that won rather than only saying this
one lost.

### DELETE /resources/{id}/reservations/{reservation_id} `[SUPER_ADMIN, UNIT_ADMIN]`

Let a hold go. Returns the reservation with `status` set to `CANCELLED` and
`cancelled_at` filled in. The row stays: a deleted row cannot be told to
anybody, and a system that was informed the room was held has to be able to
learn that it no longer is.

The freed window is bookable again immediately and stops appearing in
availability. Cancelling twice is not an error and returns the same timestamp,
because the caller wanted the room free and the room is free. Cancelling
through the wrong resource id is `404`.

A hold is let go by whoever took it. A `UNIT_ADMIN` that did not make a
reservation gets `403` with `"only the caller that took a hold may cancel it"`,
which matters because more than one integration books through this route with
the same role, and one dropping another's hold is how a room goes quietly free
under a system that still believes it has it. A `SUPER_ADMIN` overrides: a hold
taken by an account that has since been deleted has a null `requested_by_id`
and nobody left to cancel it.

---

## Schedule

### GET /schedule/ledger/today

Returns today's `DailyLedger` entries scoped to the caller's role:
- **Staff** → sessions where they are active or substitute lead
- **Member** → sessions for their registered activities
- **Admin** → all sessions

### PATCH /schedule/ledger/{ledger_id} `[STAFF, ADMIN]`

```json
// Patch to switch to online delivery
{
  "delivery_format": "ONLINE_STREAM",
  "virtual_connection_string": "https://meet.google.com/xyz-abc-def"
}
```

```json
// Patch geofence for ad-hoc room change
{
  "latitude_target": 12.971598,
  "longitude_target": 77.594562,
  "altitude_target": 920.5,
  "precision_radius_meters": 15
}
```

### GET /schedule/staff/{staff_id}/location

4-tier location resolver result. See [`docs/flows.md`](flows.md) for resolution order.

```json
{
  "resolved_location": "Room 204: Active Class",
  "status": "SCHEDULED",
  "staff_id": "FAC001",
  "full_name": "Dr. Priya Sharma",
  "occupancy_index": "BUSY"
}
```

### GET /schedule/staff/all/locations

Snapshot of all staff locations. Polled by the Member Locator panel.

### GET /schedule/cycles
### POST /schedule/cycles `[ADMIN]`
### PATCH /schedule/cycles/{id}/close `[ADMIN]`
### PATCH /schedule/cycles/{id}/open `[ADMIN]`
### POST /schedule/cycles/{old}/clone-to/{new} `[ADMIN]`

A cycle can be created closed, filled in over as long as that takes, and put
into service once it is ready, which is what `open` is for. It is the only
thing that sets `operational_status` back to true.

A cycle's two dates are the days its slots run on, both included: the nightly
generator writes no day for a slot outside them. A `date_bounds_end` earlier
than `date_bounds_start` is refused with `422`, and equal dates are a cycle of
one day.

It is not a flag flip. A slot entered into a closed cycle is never checked
against the bookings or against the rest of the timetable, because a closed
cycle's slots occupy nothing, and every one of them starts occupying its room
the moment the flag goes true. So the checks `POST /schedule/slots` would have
run are run here instead, over every slot in the cycle at once, and the whole
open is refused where any of them lands on a room that is taken. The cycle's
own slots count against each other: two of them drafted into one room at one
hour were never refused when they were entered, and this is where they are
caught.

The body is the one a slot clash sends, with one field added:

```json
{
  "detail": {
    "message": "opening this cycle would put its slots on rooms already taken",
    "conflicts": [
      {
        "date": "2026-03-04",
        "start": "09:00:00",
        "end_date": "2026-03-04",
        "end": "10:00:00",
        "activity_id": null,
        "activity_code": null,
        "master_slot_id": null,
        "reservation_id": 41,
        "blocked_slot_id": 88
      }
    ]
  }
}
```

The eight standard keys name what was already there, read exactly as they are
read anywhere else, and `blocked_slot_id` names which of the cycle's own slots
wanted it. Every clash across every slot is listed at once rather than one per
attempt. A pair of the cycle's own slots is listed twice, once from each side,
because neither of the two is the one at fault and one of them has to move.

A refused open writes nothing: the cycle stays closed. Opening a cycle that is
already open changes nothing and returns `200`.

Two cycles may be open at once. Each slot runs only on the dates inside its
own cycle's bounds, so two cycles covering different parts of the year do not
clash, and where they do overlap the date reported is the first one both
slots run on. That is the same thing `GET /resources/{id}/availability`
reports.

### POST /schedule/slots `[ADMIN]`
### PATCH /schedule/slots/{id} `[ADMIN]`

Create a weekly slot, or move an existing one. Both are refused with `409`
where the room is already taken for part of that window, by a booking, by
another class already on the timetable, or by a day already generated onto
that room:

```json
{
  "detail": {
    "message": "the resource is held for part of that window",
    "conflicts": [
      {
        "date": "2026-03-04",
        "start": "09:00:00",
        "end_date": "2026-03-04",
        "end": "10:00:00",
        "activity_id": null,
        "activity_code": null,
        "master_slot_id": null,
        "reservation_id": 41
      }
    ]
  }
}
```

The same body `POST /resources/{id}/reservations` sends when it refuses, so a
clash reads the same way whichever end it came from. Two limits on what
counts: only holds from today forward, because a slot lays down days from now
onwards and never backwards, and nothing at all if the slot belongs to a
closed cycle, because such a slot does not occupy the room and a booking is
already accepted on top of one.

A class already on the timetable is refused the same way, with a different
message and the same shape:

```json
{
  "detail": {
    "message": "the resource is already on the timetable for part of that window",
    "conflicts": [
      {
        "date": "2026-03-04",
        "start": "09:00:00",
        "end_date": "2026-03-04",
        "end": "10:00:00",
        "activity_id": 12,
        "activity_code": "CS101",
        "master_slot_id": 88,
        "reservation_id": null
      }
    ]
  }
}
```

Which kind of thing an entry is can be read off the fields that are set: a
class names the activity and leaves `reservation_id` null, a booking does the
reverse. That is the same convention `GET /resources/{id}/availability` uses.

A day already generated is the third, with the message `the resource already
has a generated day in part of that window`. It reads as a class, because a
class is what it came from, and its `master_slot_id` is null where that slot
has since been deleted. Unlike the other two it counts whatever its cycle now
says: closing a cycle does not withdraw the days it has already produced, and
the database refuses a second row on top of one either way.

A weekly slot has no date of its own, so the one reported is the next time
the clash actually happens. It repeats every week until one of the two moves.

Every open cycle counts, on its own dates only. A slot produces days only from
its cycle's `date_bounds_start` to its `date_bounds_end`, so a class in a cycle
covering the spring does not block one in a cycle covering the autumn, and
where two cycles do overlap the date reported is the first week both classes
run. The new slot's own cycle limits it the same way: a booking or a generated
day on a date that cycle never reaches is not a clash.

A `PATCH` is only checked when it would actually move the class. Changing the
lead on a slot, or anything else that leaves the room, weekday and window
alone, is allowed even where a hold or another class is sitting on that slot
already: such an overlap predates this rule or was written straight into the
database, and refusing would leave the lead unfixable short of cancelling
somebody else's booking. A slot is never counted against itself either, so
widening a window from 09:00 to 11:00 is not refused by the 09:00 to 10:00 it
replaces.

A refused `PATCH` changes nothing. The room is resolved and the clashes are
checked before any day the slot has already produced is withdrawn.

---

## Attendance

### POST /attendance/mark

```json
{
  "ledger_instance_id": 1042,
  "member_id": "STU20210001",
  "marking_status": "PRESENT",
  "user_lat": 12.971598,
  "user_lon": 77.594562,
  "user_alt": 920.5
}
```

Omit `user_lat`/`user_lon`/`user_alt` to skip geofence validation (e.g., GPS unavailable).
Members may only mark themselves; staff/admins can mark any member.

### POST /attendance/batch `[STAFF, ADMIN]`

```json
{
  "ledger_instance_id": 1042,
  "records": [
    { "ledger_instance_id": 1042, "member_id": "STU001", "marking_status": "PRESENT" },
    { "ledger_instance_id": 1042, "member_id": "STU002", "marking_status": "LATE" }
  ]
}
```

### GET /attendance/ledger/{ledger_id}

The roster for one session. Whoever runs it gets every row: the assigned lead,
the substitute, a super admin, or a unit admin inside that unit. A member gets
their own row and nothing else. Anyone else gets `403` rather than an empty
list, because an empty list reads as "nobody came". A session id that matches
nothing gets `404`.

An API key carries the role of the account it was issued to, so an integration
that needs whole rosters wants a key issued on an admin account.

### POST /attendance/absence `[STAFF]`

Submit a Reverse RSVP (absence request):

```json
{ "target_absence_date": "2026-06-15", "context_justification": "National seminar." }
```

Routes to `reporting_line_manager` for approval. On approval, the corresponding `DailyLedger` entry flips to `ON_LEAVE`. See [`docs/flows.md`](flows.md) for the full state machine.

### GET /attendance/absence/pending `[MANAGER, ADMIN]`

Returns absence requests pending your approval.

### PATCH /attendance/absence/{id}/decide `[MANAGER, ADMIN]`

```json
{ "decision": "VERIFIED_APPROVED" }
// or
{ "decision": "VERIFIED_DENIED" }
```

### POST /attendance/annotations `[LEAD, ADMIN]`
### GET /attendance/annotations/{ledger_id} `[LEAD, ADMIN]`

Freeform notes about a session: lab issues, late starts, a handover. Both
directions are restricted to whoever runs the session, on the same rule as the
roster above, and unlike the roster there is no per-member fallback, because a
note is about the session rather than about one person in it. A session id that
matches nothing gets `404`.

`classification_tag` is free text of up to 30 characters. There is no fixed
vocabulary for it, so pick one and use it consistently.
`annotation_payload` is capped at 4000 characters.

```json
{ "ledger_instance_id": 1042, "classification_tag": "LATE_START", "annotation_payload": "Lab setup delayed." }
```

---

## Guest Gate

### POST /guest/register-checkin `[KIOSK KEY]`

The kiosk endpoint. The visitor does not log in; the kiosk device sends an
admin-issued API key in `X-API-Key`. Fires a real-time WebSocket notification
to the target staff. Every field is length-bounded, and `contact_phone` accepts
only digits, spaces and `+ ( ) -`.

A lobby terminal is the clearest case for a narrow key: `["guest:read",
"guest:write"]` lets it check people in and read the directory and nothing
else, which matters for a device sitting in a public space. See
[Scopes](#scopes).

```json
{
  "guest_name": "John Smith",
  "contact_phone": "+91 98765 43210",
  "originating_body": "TechCorp Ltd",
  "target_staff_id": "FAC001",
  "visitation_intent": "Research collaboration discussion"
}
```

### GET /guest/directory `[KIOSK KEY]`

`?name=<string>`, case-insensitive name search, minimum two characters so the
roster cannot be walked one letter at a time. Returns staff with `OPEN_AD_HOC`
or `VERY_FREE` status.

### GET /guest/pending `[STAFF]`

Pending guest requests targeting the authenticated staff member.

### PATCH /guest/{id}/decide `[STAFF]`

```json
{ "decision": "VERIFIED_APPROVED" }
```

---

## Ingestion

### POST /ingestion/upload-csv?cycle_id={id} `[SUPER_ADMIN]`

Upload a `multipart/form-data` CSV file. Required columns:

| Column | Example |
|---|---|
| `member_id` | STU20210001 |
| `member_name` | Alice Kumar |
| `member_email` | alice@org.internal |
| `activity_code` | CS301 |
| `activity_title` | Operating Systems |
| `unit` | CSE |
| `day_of_week_index` | 1 (Monday) … 7 (Sunday) |
| `time_window_start` | 09:00 |
| `time_window_end` | 10:00 |
| `lead_id` | FAC001 |
| `room` | Room 204 |

Import is idempotent, and a re-upload is how a timetable is corrected in
bulk. A slot matching an existing one on activity, weekday and start time
has its end time, lead and room brought into line, and the days already
generated from it follow. The exception is a day somebody has already
marked or annotated: those are counted in `ledger_rows_kept` and left
disagreeing with the timetable on purpose, because they record what
happened rather than what was planned. A member who already exists keeps
their password, and somebody promoted to STAFF since the last import stays
STAFF.

A row that would put a class in a room already taken for that window, by a
booking, by another class, or by a day already generated onto it, is refused
with `422`, and the whole file is rolled back rather than the row skipped,
which is what every other bad row in an import does. The message names the
room and what it ran into. Rows are checked against each other as well, so
one file cannot put two classes in one room at one hour. The check only looks
where a row would actually move a class, so re-uploading a file that
describes the timetable as it already stands is not refused by what is
sitting on it.

A closed cycle changes two of the three. Its slots occupy nothing, so an
upload into one is not checked against the bookings or against the rest of
the timetable, the same way a slot in a closed cycle does not block a
booking. The days already generated are checked either way, because a
correction is copied onto them whatever the cycle says and the database
refuses to move one onto a room something else is holding.

Every member the file creates gets an individual random password, returned
once in the response and never stored:

```json
{
  "status": "SUCCESS",
  "rows_ingested": 412,
  "provisioned_credentials": [
    { "member_id": "STU20210001", "email_address": "alice@org.internal", "initial_password": "kQ7mZ2pV1xNc" }
  ]
}
```

Save that list. The server keeps only the bcrypt hash, so a lost password
has to be reissued one member at a time through
`POST /users/{user_id}/reset-password`.

**An import never removes anything.** A file covering one unit cannot be
told apart from a timetable that lost every other unit, so slots and
enrollments the cycle holds that the file does not mention come back in
`not_in_file` for somebody to decide about:

```json
{
  "status": "SUCCESS",
  "rows_ingested": 412,
  "slots_corrected": 2,
  "ledger_rows_updated": 5,
  "ledger_rows_kept": 1,
  "not_in_file": {
    "slots": [
      { "id": 87, "activity_code": "PH101", "day_of_week_index": 3, "time_window_start": "11:00:00", "room": "LH-305" }
    ],
    "enrollments": [
      { "member_id": "STU20210044", "activity_code": "PH101" }
    ]
  }
}
```

The report is scoped to the units named in the file, so a CSE upload does
not list every ECE class every time. Act on a reported slot with
`DELETE /schedule/slots/{id}`, which keeps the days already past.

A class whose start time moved shows up here too. The slot match is on
activity, weekday and start time, so a class moved from 09:00 to 14:00 does
not match: it arrives as a second slot and the 09:00 one is reported rather
than guessed at. No column in the file can say "this is the 09:00 class,
moved", and guessing wrong would delete somebody's timetable.

**Practical size limit.** Each new member costs one bcrypt hash on the
request thread, roughly half a second, and the work happens before the
response is sent. The browser client waits 60 seconds and nginx
(`proxy_read_timeout` in `nginx/chronos-common.conf`) also waits 60, which
puts the ceiling near 100 *new* members per file. Rows for members who
already exist are cheap and do not count against it. Split a larger roll
into several files.

A timed-out upload is the awkward case: the server finishes and commits
regardless, so the accounts exist but nobody ever saw their passwords.
Reset those members individually, or re-upload after raising both
timeouts.

### POST /ingestion/generate-ledger `[ADMIN]`

```json
{ "target_date": "2026-09-01" }   // optional; defaults to tomorrow
```

The nightly job does this for tomorrow at 23:00 in `ORG_TIMEZONE`. A server
that starts also does it once for today, and for tomorrow as well if it starts
at or after 23:00, because a run missed while the server was down is not
remembered. That catch-up never writes a date that has already passed.

A slot gets a day only while its cycle is open and the date is inside the
cycle's own dates. Running this again for a date is harmless: a slot has at
most one day per date, and the database refuses a second (migration 017).

---

## Calendar Sync

### GET /sync/user-feed/{feed_token}.ics

Live iCalendar feed (rolling 37-day window). Subscribe directly in any calendar app:

```
webcal://<server>/api/v1/sync/user-feed/<feed_token>.ics
```

The feed takes a token, not a user id. `GET /sync/feed-token` returns the
caller's token and the path built from it, and `POST /sync/feed-token/rotate`
replaces it, which stops every calendar subscribed to the old path.

Staff feed includes sessions where they are active or substitute lead.
Member feed includes all registered activities.

---

## WebSocket

```
ws://<server>/ws
```

The server accepts the socket, then waits five seconds for one frame naming
the token:

```json
{ "event": "AUTH", "payload": { "token": "<jwt>" } }
```

It answers `{"event": "AUTHENTICATED", "payload": {}}` and starts routing
events. A token that does not check out, a first frame of any other shape, or
silence past the five seconds closes the socket: `4003` for a refused token,
`4008` for the silence. The token is checked the way an HTTP request's is, so
one belonging to an account that no longer exists, or to an admin who has not
yet chosen a password, is refused here too.

The token is deliberately not a query parameter. A query string lands in the
proxy's access log and the browser's history, and gets sent onward as a
Referer; a frame does none of that.

Events are delivered as JSON frames:

| Event | Who receives | Payload |
|---|---|---|
| `ABSENCE_APPROVAL_REQUIRED` | Line manager | `{log_id, from, date}` |
| `ABSENCE_DECISION` | Staff who submitted | `{log_id, decision}` |
| `GUEST_HANDSHAKE_REQ` | Target staff | `{transaction_id, guest_name, originating_body, intent}` |
| `LEDGER_STATE_CHANGE` | All connected users | `{ledger_id, new_state}` |

The `AUTH` frame is the only thing a client sends. Everything after it
travels server to client.

### GET /ws/stats `[SUPER_ADMIN]`

How many sockets are open right now: `{"online_connections": 4}`. Super admin
only, because it is an organization-wide headcount and there is no unit-sized
share of it to hand a unit admin.
