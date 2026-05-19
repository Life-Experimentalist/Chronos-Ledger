# API Reference

<!-- Copyright 2026 Chronos Ledger Contributors — Apache 2.0 -->

**Machine-readable contract**: [`docs/openapi.yaml`](openapi.yaml) — OpenAPI 3.1.

**Interactive UI** (live server): `http://<server>/docs` (Swagger UI) · `http://<server>/redoc` (ReDoc)

Base URL: `http://<server>/api/v1`

---

## Authentication

All endpoints except `/auth/login`, `/guest/register-checkin`, and `/guest/directory`
require a Bearer token:

```
Authorization: Bearer <access_token>
```

Tokens expire after `JWT_ACCESS_TOKEN_EXPIRE_MINUTES` (default: 480 min / 8 hours).

### Role hierarchy

```mermaid
graph TD
    SA[SUPER_ADMIN] --> DA[DEPT_ADMIN]
    DA --> FAC[FACULTY]
    FAC --> STU[STUDENT]
```

Higher roles inherit the permissions of all roles below them. Role is embedded in the JWT payload and validated server-side on every request.

---

### POST /auth/login

```json
// Request
{ "email": "user@college.internal", "password": "…" }

// Response 200
{
  "access_token": "<jwt>",
  "token_type": "bearer",
  "user_id": "FAC001",
  "role": "FACULTY",
  "full_name": "Dr. Priya Sharma",
  "initial_login_state": false
}
```

`initial_login_state: true` on first login — the client should redirect to the change-password flow.

### POST /auth/change-password

```json
{ "current_password": "…", "new_password": "…" }
```

### GET /auth/me

Returns the current user's `UserResponse` (see Users section).

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
  "email_address": "rajan@college.internal",
  "password": "InitialPass1!",
  "role_type": "FACULTY",
  "department_code": "CSE",
  "assigned_base_station": "Staff Room Block A",
  "reporting_line_manager": "HOD001"
}
```

### GET /users/faculty/available `[public]`

Returns faculty with `OPEN_AD_HOC` or `VERY_FREE` status. Used by the Guest Kiosk.

### GET /users/{user_id}
### PUT /users/{user_id}
### DELETE /users/{user_id} `[SUPER_ADMIN]`
### PATCH /users/{user_id}/status

Update faculty occupancy. Enum values: `OPEN_AD_HOC`, `BUSY`, `CRITICAL_DO_NOT_DISTURB`, `VERY_FREE`.

```json
{ "status": "BUSY" }
```

---

## Schedule

### GET /schedule/ledger/today

Returns today's `DailyLedger` entries scoped to the caller's role:
- **Faculty** → sessions where they are active or substitute instructor
- **Student** → sessions for their registered courses
- **Admin** → all sessions

### GET /schedule/ledger/{ledger_id}
### PATCH /schedule/ledger/{ledger_id} `[FACULTY, ADMIN]`

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

### GET /schedule/faculty/{faculty_id}/location

4-tier location resolver result. See [`docs/flows.md`](flows.md) for resolution order.

```json
{
  "resolved_location": "Room 204 — Active Class",
  "status": "SCHEDULED",
  "faculty_id": "FAC001",
  "full_name": "Dr. Priya Sharma",
  "occupancy_index": "BUSY"
}
```

### GET /schedule/faculty/all/locations

Snapshot of all faculty locations. Polled by the Student Locator panel.

### GET /schedule/cycles
### POST /schedule/cycles `[ADMIN]`
### PATCH /schedule/cycles/{id}/close `[ADMIN]`
### POST /schedule/cycles/{old}/clone-to/{new} `[ADMIN]`

---

## Attendance

### POST /attendance/mark

```json
{
  "ledger_instance_id": 1042,
  "student_id": "STU20210001",
  "marking_status": "PRESENT",
  "user_lat": 12.971598,
  "user_lon": 77.594562,
  "user_alt": 920.5
}
```

Omit `user_lat`/`user_lon`/`user_alt` to skip geofence validation (e.g., GPS unavailable).
Students may only mark themselves; faculty/admins can mark any student.

### POST /attendance/batch `[FACULTY, ADMIN]`

```json
{
  "ledger_instance_id": 1042,
  "records": [
    { "ledger_instance_id": 1042, "student_id": "STU001", "marking_status": "PRESENT" },
    { "ledger_instance_id": 1042, "student_id": "STU002", "marking_status": "LATE" }
  ]
}
```

### GET /attendance/ledger/{ledger_id}

All attendance records for a session.

### POST /attendance/absence `[FACULTY]`

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

### POST /attendance/annotations `[FACULTY, ADMIN]`
### GET /attendance/annotations/{ledger_id}

Attach freeform notes to a session (lab issues, late starts, etc.).

```json
{ "ledger_instance_id": 1042, "classification_tag": "LATE_START", "annotation_payload": "Lab setup delayed." }
```

---

## Guest Gate

### POST /guest/register-checkin `[no auth]`

Public kiosk endpoint. Fires a real-time WebSocket notification to the target faculty.

```json
{
  "guest_name": "John Smith",
  "contact_phone": "+91 98765 43210",
  "originating_body": "TechCorp Ltd",
  "target_faculty_id": "FAC001",
  "visitation_intent": "Research collaboration discussion"
}
```

### GET /guest/directory `[no auth]`

`?name=<string>` — case-insensitive name search. Returns faculty with `OPEN_AD_HOC` or `VERY_FREE` status.

### GET /guest/ `[FACULTY]`

Pending guest requests targeting the authenticated faculty member.

### PATCH /guest/{id}/decide `[FACULTY]`

```json
{ "decision": "VERIFIED_APPROVED" }
```

---

## Ingestion

### POST /ingestion/upload-csv?cycle_id={id} `[ADMIN]`

Upload a `multipart/form-data` CSV file. Required columns:

| Column | Example |
|---|---|
| `student_id` | STU20210001 |
| `student_name` | Alice Kumar |
| `student_email` | alice@college.internal |
| `subject_code` | CS301 |
| `subject_title` | Operating Systems |
| `department` | CSE |
| `day_of_week_index` | 0 (Monday) … 6 (Sunday) |
| `time_window_start` | 09:00 |
| `time_window_end` | 10:00 |
| `teacher_id` | FAC001 |
| `room` | Room 204 |

Import is idempotent — re-uploading the same file is safe.

### POST /ingestion/generate-ledger `[ADMIN]`

```json
{ "target_date": "2026-09-01" }   // optional; defaults to tomorrow
```

---

## Calendar Sync

### GET /sync/user-feed/{user_id}.ics

Live iCalendar feed (rolling 37-day window). Subscribe directly in any calendar app:

```
webcal://<server>/api/v1/sync/user-feed/FAC001.ics
```

Faculty feed includes sessions where they are active or substitute instructor.
Student feed includes all registered courses.

---

## WebSocket

```
ws://<server>/ws?token=<jwt>
```

Persistent receive-only connection. Events delivered as JSON frames:

| Event | Who receives | Payload |
|---|---|---|
| `ABSENCE_APPROVAL_REQUIRED` | Line manager | `{log_id, from, date}` |
| `ABSENCE_DECISION` | Faculty who submitted | `{log_id, decision}` |
| `GUEST_HANDSHAKE_REQ` | Target faculty | `{transaction_id, guest_name, originating_body, intent}` |
| `LEDGER_STATE_CHANGE` | All connected users | `{ledger_id, new_state}` |

The client sends no upstream frames — the connection is subscribe-only.
