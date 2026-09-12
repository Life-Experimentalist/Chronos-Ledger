# Key Flows

<!-- Copyright 2026 Chronos Ledger Contributors (Apache 2.0) -->

Sequence diagrams for the four core interaction flows. Each diagram is followed
by a plain-English walk-through of every significant step.

---

## 1. Member Attendance Marking (Geofenced)

```mermaid
sequenceDiagram
    actor Stu as Member (PWA)
    participant SW as Service Worker
    participant IDB as IndexedDB
    participant API as FastAPI /attendance/mark
    participant GF as geo_fence.py
    participant DB as PostgreSQL

    Stu->>Stu: Opens ProximityCard<br/>for today's class

    alt Online
        Stu->>API: POST /attendance/mark<br/>{ledger_id, member_id, lat, lon, alt}
        API->>DB: SELECT DailyLedger WHERE id = ledger_id
        DB-->>API: lat_target, lon_target, alt_target, radius_m
        API->>GF: check_geofence(user_coords, target_coords, radius)
        GF-->>API: inside=true / false
        alt Inside geofence
            API->>DB: UPSERT VerificationLedger (PRESENT)
            API-->>Stu: 201 {marking_status: PRESENT}
        else Outside geofence
            API-->>Stu: 400 {detail: "Geofence violation"}
        end
    else Offline
        Stu->>IDB: enqueueAttendance(record)
        SW->>SW: Register background-sync tag<br/>"sync-attendance"
        Note over SW: Fires when connectivity restored
        SW->>API: POST /attendance/mark (replayed)
        API->>DB: UPSERT VerificationLedger
        API-->>SW: 201
    end
```

**Step-by-step:**

1. The member opens the **ProximityCard** component which starts a GPS watch via `useGeolocation.ts`. The hook calls `navigator.geolocation.watchPosition` (stable `useRef` for the watch ID, fixes a prior bug where a plain object was used).
2. **Online path**: Coordinates + ledger ID are posted to `/attendance/mark`. The backend queries the `DailyLedger` row for the geofence target coordinates and calls `geo_fence.check_geofence()`. The function runs a Haversine 2D distance check then validates `|user_alt - target_alt| < 4m` to prevent members on adjacent floors from registering.
3. If the check passes, a `VerificationLedger` row is upserted (idempotent, re-marking is allowed, last write wins).
4. **Offline path**: The mark is written to the `attendance-queue` IndexedDB store. The service worker's `background-sync` tag `sync-attendance` is registered. On reconnect, the SW replays the queue to `/attendance/mark` and clears the store entry on 2xx response.

---

## 2. Staff Absence Request (Reverse RSVP)

```mermaid
sequenceDiagram
    actor Fac as Staff
    actor Mgr as Line Manager
    participant API as FastAPI
    participant RSVP as reverse_rsvp.py
    participant WS as WebSocket Hub
    participant DB as PostgreSQL

    Fac->>API: POST /attendance/absence<br/>{target_absence_date, context_justification}
    API->>DB: INSERT ReverseRsvpLog<br/>approval_state = PENDING_VERIFICATION
    API->>DB: SELECT User WHERE id = fac.reporting_line_manager
    API->>WS: broadcast(manager_id, ABSENCE_APPROVAL_REQUIRED)
    WS-->>Mgr: {event: ABSENCE_APPROVAL_REQUIRED,<br/>payload: {log_id, from, date}}
    API-->>Fac: 201 ReverseRsvpResponse

    Mgr->>API: PATCH /attendance/absence/{id}/decide<br/>{decision: VERIFIED_APPROVED}
    API->>RSVP: process_decision(log_id, decision)

    alt VERIFIED_APPROVED
        RSVP->>DB: UPDATE ReverseRsvpLog<br/>approval_state = VERIFIED_APPROVED
        RSVP->>DB: UPDATE DailyLedger<br/>operational_state = ON_LEAVE<br/>(for target_absence_date slots)
        RSVP->>WS: broadcast(staff_id, ABSENCE_DECISION)
        WS-->>Fac: {event: ABSENCE_DECISION,<br/>payload: {log_id, decision: VERIFIED_APPROVED}}
    else VERIFIED_DENIED
        RSVP->>DB: UPDATE ReverseRsvpLog<br/>approval_state = VERIFIED_DENIED
        RSVP->>WS: broadcast(staff_id, ABSENCE_DECISION)
        WS-->>Fac: {event: ABSENCE_DECISION,<br/>payload: {log_id, decision: VERIFIED_DENIED}}
    end

    API-->>Mgr: 200 ReverseRsvpResponse
```

**Step-by-step:**

1. Staff submits an absence request via the **Absence Requests** tab. The `ReverseRsvpLog` row is created with `approval_state = PENDING_VERIFICATION`.
2. The API immediately resolves the staff's `reporting_line_manager` user ID and broadcasts a `ABSENCE_APPROVAL_REQUIRED` WebSocket event. If the manager is connected, they see a notification badge in real time.
3. The manager opens **Pending Approvals** and approves or denies.
4. On approval, `services/reverse_rsvp.py` updates every `DailyLedger` entry on the target date where the staff is `active_lead_id` to `operational_state = ON_LEAVE`. This cascades the absence into the live schedule.
5. A `ABSENCE_DECISION` WebSocket event is sent to the staff member so they see the outcome immediately without polling.

---

## 3. Guest Handshake

```mermaid
sequenceDiagram
    actor G as Guest (Kiosk)
    participant KI as /guest/kiosk (PWA)
    participant API as FastAPI /guest/register-checkin
    participant WS as WebSocket Hub
    actor Fac as Staff (dashboard)
    participant DB as PostgreSQL

    G->>KI: Fills check-in form<br/>(name, phone, org, staff, intent)
    KI->>API: POST /guest/register-checkin<br/>(no auth required)
    API->>DB: INSERT GuestGateRegistry<br/>handshake_status = PENDING_VERIFICATION
    API->>DB: SELECT User WHERE id = target_staff_id
    API->>WS: broadcast(staff_id, GUEST_HANDSHAKE_REQ)
    API-->>KI: 201 GuestResponse
    KI-->>G: "Your request has been sent.<br/>Please wait."

    WS-->>Fac: {event: GUEST_HANDSHAKE_REQ,<br/>payload: {transaction_id, guest_name, org, intent}}
    Note over Fac: NotificationPanel shows badge

    Fac->>API: PATCH /guest/{id}/decide<br/>{decision: VERIFIED_APPROVED}
    API->>DB: UPDATE GuestGateRegistry<br/>handshake_status = VERIFIED_APPROVED
    API-->>Fac: 200 GuestResponse

    Note over KI,G: Kiosk polls /guest/{id} or receives<br/>push notification on approval
```

**Step-by-step:**

1. The **Guest Kiosk** (`/guest/kiosk`) is a public, unauthenticated page accessible from any organization terminal. It searches the staff directory (`GET /guest/directory?name=…`) to let the guest pick the right person.
2. The check-in POST requires no bearer token. The server creates a `GuestGateRegistry` row and immediately pushes a `GUEST_HANDSHAKE_REQ` frame to the target staff's WebSocket connection.
3. If the staff is connected, their **NotificationPanel** badge increments and the **Interaction Desk** tab shows the incoming request within milliseconds.
4. Staff approves or declines. The `GuestGateRegistry` row is updated and the decision is broadcast back. The kiosk can display the outcome to the guest.

---

## 4. Nightly Ledger Generation

```mermaid
flowchart TD
    T([APScheduler fires at 23:00 in ORG_TIMEZONE]) --> Q1

    Q1[Query open PlanningCycles<br/>whose dates include tomorrow] --> Q2
    Q2[Query their StructuralMasterSlots<br/>for tomorrows day_of_week_index] --> LOOP

    LOOP{For each slot} --> CHK

    CHK{DailyLedger row<br/>already exists<br/>for date + slot?}
    CHK -->|Yes| SKIP[Skip, idempotent]
    CHK -->|No| INS

    INS[INSERT DailyLedger
    target_date = tomorrow
    operational_state = SCHEDULED
    active_lead_id = slot.primary_lead_id
    delivery_format = PHYSICAL
    lat/lon/alt from slot room registry] --> LOOP

    SKIP --> LOOP
    LOOP -->|done| LOG[Log: N rows generated, M skipped]
```

**Step-by-step:**

1. APScheduler (configured in `backend/app/main.py`) runs `cron/ledger_generator.generate_daily_ledger_entries()` for tomorrow at 23:00 in `ORG_TIMEZONE`. A server that starts also runs it once for today, and for tomorrow too if it starts at or after 23:00, because the scheduler keeps no record of a run it missed while the server was down. The catch-up never writes a date that has already passed.
2. Only cycles that are open and whose `date_bounds_start` to `date_bounds_end` includes tomorrow, both ends included, count. If there are none (e.g., term break), the job is a no-op.
3. For tomorrow's `day_of_week_index`, the `StructuralMasterSlot` rows of those cycles are fetched.
4. For each slot, an existence check is performed, backed by a unique key on `target_date` and `master_slot_id` (migration 017). This makes the job fully **idempotent**, safe to re-run manually via `POST /ingestion/generate-ledger` and safe on several instances at once, without creating duplicates.
5. New rows are inserted with `operational_state = SCHEDULED` and the slot's lead. Admins (a unit admin only within their own unit) can subsequently mutate the row (substitute lead, delivery format, geofence coords) via `PATCH /schedule/ledger/{id}`.
