# Data Model

<!-- Copyright 2026 Chronos Ledger Contributors (Apache 2.0) -->

All ten production tables live in the default PostgreSQL `public` schema.
Migrations are managed by Alembic (`backend/alembic/versions/`).

---

## Entity-Relationship Diagram

```mermaid
erDiagram
    User {
        string id PK "e.g. FAC001, STU20210001"
        string full_name
        string email_address UK
        string credential_secure_hash
        string role_type "SUPER_ADMIN | UNIT_ADMIN | STAFF | MEMBER"
        string unit_code
        string assigned_base_station
        string current_occupancy_index "AccessReadiness enum"
        string reporting_line_manager FK "→ User.id (nullable)"
        bool initial_login_state
    }

    PlanningCycle {
        int id PK
        string cycle_label UK "e.g. 2026-Fall-Trimester"
        date date_bounds_start
        date date_bounds_end
        bool operational_status
    }

    Activity {
        int id PK
        string activity_code
        string activity_title
        string unit_code
        int cycle_id FK "→ PlanningCycle.id"
    }

    StructuralMasterSlot {
        int id PK
        int day_of_week_index "1 = Monday … 7 = Sunday"
        time time_window_start
        time time_window_end
        int activity_id FK "→ Activity.id"
        string primary_lead_id FK "→ User.id (nullable)"
        string target_room_identifier
    }

    ActivityEnrollment {
        int id PK
        string member_id FK "→ User.id"
        int activity_id FK "→ Activity.id"
    }

    DailyLedger {
        int id PK
        date target_date
        int activity_id FK "→ Activity.id"
        int master_slot_id FK "→ StructuralMasterSlot.id (nullable)"
        string active_lead_id FK "→ User.id (nullable)"
        string substitute_lead_id FK "→ User.id (nullable)"
        string target_room_identifier
        string delivery_format "PHYSICAL | ONLINE_STREAM"
        string virtual_connection_string "nullable"
        string operational_state "DynamicState enum"
        float latitude_target
        float longitude_target
        float altitude_target
        int precision_radius_meters
    }

    VerificationLedger {
        int id PK
        int ledger_instance_id FK "→ DailyLedger.id"
        string member_id FK "→ User.id"
        string marking_status "PRESENT | ABSENT | LATE"
        string authorizing_agent_id FK "→ User.id (nullable)"
        datetime modification_timestamp
    }

    ReverseRsvpLog {
        int id PK
        string submitting_user_id FK "→ User.id"
        date target_absence_date
        string context_justification
        string approval_state "LogVerificationState enum"
        string authorized_by_user_id FK "→ User.id (nullable)"
    }

    GuestGateRegistry {
        int id PK
        string guest_name
        string contact_phone
        string originating_body
        string target_staff_id FK "→ User.id"
        string visitation_intent
        string handshake_status "LogVerificationState enum"
        datetime timestamp_marked
    }

    LedgerAnnotation {
        int id PK
        int ledger_instance_id FK "→ DailyLedger.id"
        string creator_id FK "→ User.id"
        string classification_tag
        string annotation_payload
        datetime distribution_timestamp
    }

    PlanningCycle ||--o{ Activity : "contains"
    Activity ||--o{ StructuralMasterSlot : "has slots"
    Activity ||--o{ ActivityEnrollment : "enrols members"
    Activity ||--o{ DailyLedger : "materialised as"
    StructuralMasterSlot ||--o{ DailyLedger : "source slot"
    User ||--o{ ActivityEnrollment : "member enrols"
    User ||--o{ DailyLedger : "teaches (active)"
    User ||--o{ DailyLedger : "substitutes"
    DailyLedger ||--o{ VerificationLedger : "records attendance"
    DailyLedger ||--o{ LedgerAnnotation : "annotated by"
    User ||--o{ VerificationLedger : "member marked"
    User ||--o{ ReverseRsvpLog : "submits absence"
    User ||--o{ GuestGateRegistry : "receives guest"
```

---

## Table Notes

### `User`
Central identity record. Role-based access is enforced at the API layer (`core/security.py`), not as a DB constraint. The `reporting_line_manager` self-join is used to route absence requests to the correct supervisor.

### `PlanningCycle`
The scheduling container. Only one cycle should have `operational_status = true` at a time; the admin UI enforces this but there is no DB-level unique constraint (allowing a brief overlap during rollover).

### `Activity`
A activity within a cycle. A single activity can appear in multiple cycles as independent `Activity` rows, enabling year-over-year history without aliasing.

### `StructuralMasterSlot`
The repeating weekly timetable entry. `day_of_week_index` follows Python's `date.isoweekday()` convention (1 = Monday, 7 = Sunday), enforced by a CHECK constraint. These are the *template* rows that `ledger_generator` reads each night.

### `ActivityEnrollment`
Member-to-activity enrolment. Created in bulk by `ingestion_engine` during CSV import. No per-term attendance target is stored here, percentage calculations are done at query time.

### `DailyLedger`
The materialised daily schedule. Generated nightly from `StructuralMasterSlot` by `cron/ledger_generator.py`. Contains mutable state: `operational_state` (can be flipped to `ON_LEAVE` by an approved absence), substitute lead, and geofence coordinates (overridable per-session for ad-hoc room changes).

### `VerificationLedger`
One row per member per ledger entry. `authorizing_agent_id` is `null` for self-marks and set to the staff/admin user_id for batch marks. The same row is overwritten on re-mark (upsert logic in `attendance.py`).

### `ReverseRsvpLog`
The Reverse RSVP state machine. Starts at `PENDING_VERIFICATION`. Transition to `VERIFIED_APPROVED` triggers `services/reverse_rsvp.py` which updates the corresponding `DailyLedger.operational_state` to `ON_LEAVE` and broadcasts a WebSocket event to the staff member.

### `GuestGateRegistry`
Records each organization visitor interaction. `handshake_status` transitions from `PENDING_VERIFICATION` → `VERIFIED_APPROVED | VERIFIED_DENIED` when the target staff member acts via the Interaction Desk. The decision is broadcast back to the kiosk via WebSocket.

### `LedgerAnnotation`
Free-form notes attached to a ledger entry (e.g., "lab equipment failure", "class started late"). Used for post-session audits. No schema constraint on `classification_tag`, it's a freeform string at the application layer.
