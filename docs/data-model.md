# Data Model

<!-- Copyright 2026 Chronos Ledger Contributors — Apache 2.0 -->

All nine production tables live in the default PostgreSQL `public` schema.
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
        string role_type "SUPER_ADMIN | DEPT_ADMIN | FACULTY | STUDENT"
        string department_code
        string assigned_base_station
        string current_occupancy_index "AccessReadiness enum"
        string reporting_line_manager FK "→ User.id (nullable)"
        bool initial_login_state
    }

    AcademicCycle {
        int id PK
        string cycle_label UK "e.g. 2026-Fall-Trimester"
        date date_bounds_start
        date date_bounds_end
        bool operational_status
    }

    CourseOffering {
        int id PK
        string course_code
        string course_title
        string department_code
        int cycle_id FK "→ AcademicCycle.id"
    }

    StructuralMasterSlot {
        int id PK
        int day_of_week_index "0 = Monday … 6 = Sunday"
        time time_window_start
        time time_window_end
        int course_offering_id FK "→ CourseOffering.id"
        string primary_instructor_id FK "→ User.id (nullable)"
        string target_room_identifier
    }

    CourseRegistration {
        int id PK
        string student_id FK "→ User.id"
        int course_offering_id FK "→ CourseOffering.id"
    }

    DailyLedger {
        int id PK
        date target_date
        int course_offering_id FK "→ CourseOffering.id"
        int master_slot_id FK "→ StructuralMasterSlot.id (nullable)"
        string active_instructor_id FK "→ User.id (nullable)"
        string substitute_instructor_id FK "→ User.id (nullable)"
        string target_room_identifier
        string delivery_format "PHYSICAL | ONLINE_STREAM"
        string virtual_connection_string "nullable"
        string operational_state "DynamicState enum"
        float latitude_target
        float longitude_target
        float altitude_target
        int precision_radius_meters
    }

    AttendanceLog {
        int id PK
        int ledger_instance_id FK "→ DailyLedger.id"
        string student_id FK "→ User.id"
        string marking_status "PRESENT | ABSENT | LATE"
        string authorizing_agent_id FK "→ User.id (nullable)"
        datetime modification_timestamp
    }

    ReverseAbsenceLog {
        int id PK
        string submitting_user_id FK "→ User.id"
        date target_absence_date
        string context_justification
        string approval_state "LogVerificationState enum"
        string authorized_by_user_id FK "→ User.id (nullable)"
    }

    GuestTransactionLog {
        int id PK
        string guest_name
        string contact_phone
        string originating_body
        string target_faculty_id FK "→ User.id"
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

    AcademicCycle ||--o{ CourseOffering : "contains"
    CourseOffering ||--o{ StructuralMasterSlot : "has slots"
    CourseOffering ||--o{ CourseRegistration : "enrols students"
    CourseOffering ||--o{ DailyLedger : "materialised as"
    StructuralMasterSlot ||--o{ DailyLedger : "source slot"
    User ||--o{ CourseRegistration : "student enrols"
    User ||--o{ DailyLedger : "teaches (active)"
    User ||--o{ DailyLedger : "substitutes"
    DailyLedger ||--o{ AttendanceLog : "records attendance"
    DailyLedger ||--o{ LedgerAnnotation : "annotated by"
    User ||--o{ AttendanceLog : "student marked"
    User ||--o{ ReverseAbsenceLog : "submits absence"
    User ||--o{ GuestTransactionLog : "receives guest"
```

---

## Table Notes

### `User`
Central identity record. Role-based access is enforced at the API layer (`core/security.py`), not as a DB constraint. The `reporting_line_manager` self-join is used to route absence requests to the correct supervisor.

### `AcademicCycle`
The scheduling container. Only one cycle should have `operational_status = true` at a time; the admin UI enforces this but there is no DB-level unique constraint (allowing a brief overlap during rollover).

### `CourseOffering`
A course within a cycle. A single course can appear in multiple cycles as independent `CourseOffering` rows — enabling year-over-year history without aliasing.

### `StructuralMasterSlot`
The repeating weekly timetable entry. `day_of_week_index` follows Python's `date.weekday()` convention (0 = Monday). These are the *template* rows that `ledger_generator` reads each night.

### `CourseRegistration`
Student-to-course enrolment. Created in bulk by `ingestion_engine` during CSV import. No per-semester attendance target is stored here — percentage calculations are done at query time.

### `DailyLedger`
The materialised daily schedule. Generated nightly from `StructuralMasterSlot` by `cron/ledger_generator.py`. Contains mutable state: `operational_state` (can be flipped to `ON_LEAVE` by an approved absence), substitute instructor, and geofence coordinates (overridable per-session for ad-hoc room changes).

### `AttendanceLog`
One row per student per ledger entry. `authorizing_agent_id` is `null` for self-marks and set to the faculty/admin user_id for batch marks. The same row is overwritten on re-mark (upsert logic in `attendance.py`).

### `ReverseAbsenceLog`
The Reverse RSVP state machine. Starts at `PENDING_VERIFICATION`. Transition to `VERIFIED_APPROVED` triggers `services/reverse_rsvp.py` which updates the corresponding `DailyLedger.operational_state` to `ON_LEAVE` and broadcasts a WebSocket event to the faculty member.

### `GuestTransactionLog`
Records each campus visitor interaction. `handshake_status` transitions from `PENDING_VERIFICATION` → `VERIFIED_APPROVED | VERIFIED_DENIED` when the target faculty member acts via the Interaction Desk. The decision is broadcast back to the kiosk via WebSocket.

### `LedgerAnnotation`
Free-form notes attached to a ledger entry (e.g., "lab equipment failure", "class started late"). Used for post-session audits. No schema constraint on `classification_tag` — it's a freeform string at the application layer.
