# Architecture

<!-- Copyright 2026 Chronos Ledger Contributors (Apache 2.0) -->

## System Topology

```mermaid
graph TB
    subgraph Clients["Client Layer (PWA, installed or browser)"]
        S[Member Mobile]
        F[Staff Desktop]
        A[Admin Dashboard]
        G[Guest Kiosk<br/>device key]
    end

    subgraph Edge["Edge: Nginx 1.27"]
        NX[Reverse Proxy<br/>Port 80/443]
        ST[Static Files<br/>Next.js export]
    end

    subgraph App["Application: FastAPI"]
        API[REST API<br/>/api/v1/…]
        WS[WebSocket<br/>/ws]
        CRON[Ledger Cron<br/>APScheduler]
    end

    subgraph Data["Data Layer"]
        PG[(PostgreSQL 17<br/>Relational store)]
        RD[(Redis 7.4<br/>State cache &amp;<br/>WS event relay)]
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
| **FastAPI app** | All REST endpoints + WebSocket hub. One uvicorn process per container with no state of its own beyond PostgreSQL and Redis, so several can run behind a load balancer; see [Scaling](deployment.md#scaling). |
| **APScheduler** | Runs `ledger_generator` at 23:00 in `ORG_TIMEZONE` to materialize `DailyLedger` rows from `StructuralMasterSlot` for the next day, and once at startup for any day a stopped process missed. Also deletes expired refresh tokens at 03:00 and, when `GUEST_RETENTION_DAYS` is set, old visitor check-ins at 03:30. |
| **PostgreSQL** | Source of truth for all persistent data: users, schedule, attendance, absence logs, guest transactions. |
| **Redis** | Short-lived state: the rate-limit counters, the per-person status override the location resolver checks first, the channel instances relay WebSocket events and closes over, and each instance's set of connected users (TTL) for the connection count. |

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

    R1{Redis override<br/>state_override:id?}
    R1 -->|Yes| RET1[Return the override as status<br/>location UNKNOWN]
    R1 -->|No| R2

    R2{A generated day they lead<br/>running right now?}
    R2 -->|ON_LEAVE| RET2[Return OFF_SITE<br/>On Approved Leave]
    R2 -->|SCHEDULED or substitute| RET2B[Return the day's room]
    R2 -->|No, or another state| R3

    R3{A weekly slot they lead<br/>running right now?}
    R3 -->|Yes| RET3[Return the slot's room]
    R3 -->|No| R4

    R4[Return base station<br/>assigned_base_station, or Unassigned]
```

**Each tier explained:**

1. **Redis override**: If Redis holds `state_override:<staff_id>`, its value is returned as the status and the location as `UNKNOWN`, since an override says what somebody is doing rather than where. No route in Chronos writes this key. `PUT /users/{user_id}/status` sets the account's `current_occupancy_index` instead, which the location routes report as `occupancy_index` next to whatever the tiers resolve.
2. **Generated day**: The `DailyLedger` rows the person leads today, and yesterday's for a shift that runs past midnight, each compared on its own window. A row running now answers: `ON_LEAVE`, which is what an approved absence sets, gives `OFF_SITE`, and `SCHEDULED` or `PROXY_SUBSTITUTE` gives the row's room. A row in any other state, a lunch or a meeting, falls through to the timetable.
3. **Master timetable**: The weekly `StructuralMasterSlot` rows the person leads. A slot running now gives its room. This is what answers on a day the nightly job has not written yet.
4. **Base station fallback**: The `assigned_base_station` field on the `User` record (e.g., "Front Desk") is the last-resort answer. The column has no default, so a user with none recorded resolves to `Unassigned` rather than to a named place.

---

## WebSocket Session Lifecycle

```mermaid
sequenceDiagram
    participant C as Client (browser/PWA)
    participant N as Nginx
    participant WS as FastAPI WebSocket
    participant Reg as OrganizationConnectionManager<br/>(this instance's sockets)
    participant RD as Redis
    participant O as Other instances

    C->>N: GET /ws (Upgrade)
    N->>WS: Proxy WebSocket handshake
    C->>WS: AUTH frame carrying the JWT
    WS->>WS: Validate JWT and the account → user_id
    WS->>Reg: register_session(user_id, socket)
    WS->>C: AUTHENTICATED frame
    Note over Reg,RD: Stores {user_id → WebSocket} in<br/>process memory, and rewrites this<br/>instance's set of user ids in Redis<br/>every 15s for the connection count

    loop Event loop
        Note over WS,Reg: A domain event calls forward_direct_message()
        Reg->>C: JSON frame {event, payload}, if the socket is here
        Reg->>RD: PUBLISH ws:events
        RD->>O: Each delivers it if it holds the socket
    end

    C--xWS: Disconnect (tab closed / network drop)
    WS->>Reg: terminate_session(user_id)
```

**Why WebSockets instead of polling:** Absence approvals and guest handshakes need sub-second delivery to the staff dashboard. Polling at any sane interval (≥5s) introduces noticeable lag in the two-party guest interaction flow. Each instance keeps the sockets it holds in process memory and relays events to the other instances through Redis, so a client connects to whichever instance the load balancer picks and needs no code of its own for it.

---

## Frontend Architecture

```mermaid
graph TD
    subgraph Pages["app/: Next.js App Router"]
        Login["/  Login"]
        Landing["/landing  Marketing"]
        Admin["/admin/dashboard"]
        Staff["/staff/dashboard"]
        Member["/member/dashboard"]
        Kiosk["/guest/kiosk  (device key)"]
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
        api["api.ts: Axios wrappers"]
        auth["auth.ts, localStorage helpers"]
        idb["indexeddb.ts: IDB schema + helpers"]
    end

    subgraph Store["store/"]
        authStore["auth.ts: Zustand"]
        notifStore["notifications.ts: Zustand"]
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

- **Static export** (`output: 'export'`): The entire frontend is pre-built into static HTML/JS at Docker image build time. Nginx serves it from a shared volume, no Node.js runtime in production, no cold-start latency.
- **Zustand over Redux**: Minimal boilerplate. Auth state and notification inbox are the only global stores; everything else is local component state or server state via Axios.
- **`useSearchParams` Suspense**: Next.js 14 static export requires any component calling `useSearchParams()` to be wrapped in a `<Suspense>` boundary. All three dashboards use an outer default-export wrapper + inner content component pattern.
- **Offline notifications**: Two-layer design: `setTimeout` timers while the page is open (via `useScheduleNotifications`), and `periodicsync` in the service worker for when the device is locked. Both layers deduplicate via the `notified-classes` IndexedDB store.
