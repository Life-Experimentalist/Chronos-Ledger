# Architecture

<!-- Copyright 2026 Chronos Ledger Contributors — Apache 2.0 -->

## System Topology

```mermaid
graph TB
    subgraph Clients["Client Layer (PWA — installed or browser)"]
        S[Member Mobile]
        F[Staff Desktop]
        A[Admin Dashboard]
        G[Guest Kiosk<br/>no auth]
    end

    subgraph Edge["Edge — Nginx 1.27"]
        NX[Reverse Proxy<br/>Port 80/443]
        ST[Static Files<br/>Next.js export]
    end

    subgraph App["Application — FastAPI 0.115"]
        API[REST API<br/>/api/v1/…]
        WS[WebSocket<br/>/ws]
        CRON[Ledger Cron<br/>APScheduler]
    end

    subgraph Data["Data Layer"]
        PG[(PostgreSQL 17<br/>Relational store)]
        RD[(Redis 7.4<br/>State cache &amp;<br/>WS session registry)]
    end

    S & F & A & G -->|HTTPS / WSS| NX
    NX -->|static assets| ST
    NX -->|/api/v1 proxy| API
    NX -->|/ws proxy| WS
    API & WS & CRON --> PG
    API & WS --> RD
```

**What each box does**

| Component | Role |
|---|---|
| **Nginx** | TLS termination, gzip, security headers, static file serving, proxy to FastAPI. Serves pre-built Next.js export from the shared `frontend_build` Docker volume. |
| **FastAPI app** | All REST endpoints + WebSocket hub. Single process (uvicorn), stateless beyond DB/Redis. |
| **APScheduler** | Runs `ledger_generator` at midnight UTC to materialise `DailyLedger` rows from `StructuralMasterSlot` for the next day. |
| **PostgreSQL** | Source of truth for all persistent data: users, schedule, attendance, absence logs, guest transactions. |
| **Redis** | Short-lived state: staff status overrides (TTL), in-memory WebSocket connection registry serialised for pub/sub. |

---

## Backend Module Dependency Graph

```mermaid
graph LR
    subgraph API["api/v1/endpoints/"]
        auth
        users
        schedule
        attendance
        guest
        ingestion
        calendar_sync
        websocket
    end

    subgraph Core["core/"]
        config
        database
        security
        redis_client
        websocket_manager
    end

    subgraph Services["services/"]
        geo_fence
        location_resolver
        reverse_rsvp
        ingestion_engine
    end

    subgraph Models["models/"]
        db_models["db.py<br/>(ORM + Enums)"]
    end

    subgraph Schemas["schemas/"]
        sch_auth["auth.py"]
        sch_users["users.py"]
        sch_schedule["schedule.py"]
        sch_attendance["attendance.py"]
        sch_guest["guest.py"]
    end

    auth --> security & database & sch_auth
    users --> security & database & sch_users
    schedule --> security & database & sch_schedule & location_resolver
    attendance --> security & database & sch_attendance & geo_fence & reverse_rsvp & websocket_manager
    guest --> security & database & sch_guest & websocket_manager
    ingestion --> security & database & ingestion_engine
    websocket --> security & redis_client & websocket_manager

    location_resolver --> redis_client & database
    reverse_rsvp --> database & websocket_manager
    ingestion_engine --> database
    security --> config
    database --> config
    redis_client --> config
```

**Why this layout matters:** Each endpoint module imports from `core/` (infra) and `services/` (domain logic) but never imports another endpoint module. Services are pure domain logic with no HTTP concerns. This makes unit-testing services straightforward without mocking HTTP.

---

## 4-Tier Staff Location Resolution

```mermaid
flowchart TD
    Start([Resolve location for staff_id]) --> R1

    R1{Redis override<br/>exists?}
    R1 -->|Yes| RET1[Return override value<br/>e.g. 'In Meeting — Back at 15:00']
    R1 -->|No| R2

    R2{Approved absence<br/>today?}
    R2 -->|Yes| RET2[Return 'ON_LEAVE']
    R2 -->|No| R3

    R3{Active master slot<br/>right now?}
    R3 -->|Yes| RET3[Return room from<br/>DailyLedger entry]
    R3 -->|No| R4

    R4[Return base station<br/>assigned_base_station]
```

**Each tier explained:**

1. **Redis override** — A staff member or admin has pushed a manual status via `PATCH /users/{id}/status`. Stored in Redis with an optional TTL. Cleared automatically when TTL expires or manually via the same endpoint.
2. **Daily exception log** — The `ReverseRsvpLog` table is checked for an approved absence on today's date. If found, the ledger entry for that slot is in `ON_LEAVE`.
3. **Master timetable** — The current wall-clock time is compared against `StructuralMasterSlot` time windows. If the staff is in a scheduled session right now, the room from the `DailyLedger` entry is returned.
4. **Base station fallback** — The `assigned_base_station` field on the `User` record (e.g., "Staff Room Block A") is the last-resort answer.

---

## WebSocket Session Lifecycle

```mermaid
sequenceDiagram
    participant C as Client (browser/PWA)
    participant N as Nginx
    participant WS as FastAPI WebSocket
    participant Reg as OrganizationConnectionManager<br/>(in-memory + Redis)

    C->>N: GET /ws?token=<jwt> (Upgrade)
    N->>WS: Proxy WebSocket handshake
    WS->>WS: Validate JWT → extract user_id + role
    WS->>Reg: register(user_id, socket)
    Note over Reg: Stores {user_id → WebSocket} in<br/>process memory; user_id → pid<br/>key written to Redis for future<br/>multi-instance routing

    loop Event loop
        Note over WS,Reg: Domain events trigger broadcast()
        Reg->>C: JSON frame {event, payload}
    end

    C--xWS: Disconnect (tab closed / network drop)
    WS->>Reg: unregister(user_id)
    Reg-->>Redis: Delete user_id key
```

**Why WebSockets instead of polling:** Absence approvals and guest handshakes need sub-second delivery to the staff dashboard. Polling at any sane interval (≥5s) introduces noticeable lag in the two-party guest interaction flow. The connection registry is kept in process memory (fast path) with Redis as the index; this enables adding multi-process fanout later without changing client code.

---

## Frontend Architecture

```mermaid
graph TD
    subgraph Pages["app/ — Next.js App Router"]
        Login["/  Login"]
        Landing["/landing  Marketing"]
        Admin["/admin/dashboard"]
        Staff["/staff/dashboard"]
        Member["/member/dashboard"]
        Kiosk["/guest/kiosk  (no auth)"]
    end

    subgraph Shared["components/shared/"]
        Sidebar
        NotificationPanel
    end

    subgraph FComp["components/staff/"]
        StatusSwitcher
        AttendanceMatrix
        InteractionDesk
    end

    subgraph SComp["components/member/"]
        LiveTimeline
        ProximityCard
        StaffLocator
    end

    subgraph AComp["components/admin/"]
        CsvImportZone
        ProxyOrchestration
        MasterLedger
    end

    subgraph Hooks["hooks/"]
        useAuth
        useWebSocket
        useGeolocation
        useScheduleNotifications
    end

    subgraph Lib["lib/"]
        api["api.ts — Axios wrappers"]
        auth["auth.ts — localStorage helpers"]
        idb["indexeddb.ts — IDB schema + helpers"]
    end

    subgraph Store["store/"]
        authStore["auth.ts — Zustand"]
        notifStore["notifications.ts — Zustand"]
    end

    subgraph SW["Service Worker (Workbox + sw-custom.js)"]
        BGSync[background-sync<br/>attendance queue]
        PeriodicSync[periodicsync<br/>class reminders]
        Push[push<br/>server notifications]
    end

    Admin & Staff & Member --> Shared
    Staff --> FComp
    Member --> SComp
    Admin --> AComp
    Pages --> Hooks
    Hooks --> Lib & Store
    idb <--> SW
```

**Key design choices:**

- **Static export** (`output: 'export'`): The entire frontend is pre-built into static HTML/JS at Docker image build time. Nginx serves it from a shared volume — no Node.js runtime in production, no cold-start latency.
- **Zustand over Redux**: Minimal boilerplate. Auth state and notification inbox are the only global stores; everything else is local component state or server state via Axios.
- **`useSearchParams` Suspense**: Next.js 14 static export requires any component calling `useSearchParams()` to be wrapped in a `<Suspense>` boundary. All three dashboards use an outer default-export wrapper + inner content component pattern.
- **Offline notifications**: Two-layer design — `setTimeout` timers while the page is open (via `useScheduleNotifications`), and `periodicsync` in the service worker for when the device is locked. Both layers deduplicate via the `notified-classes` IndexedDB store.
