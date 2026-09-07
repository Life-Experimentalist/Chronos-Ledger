// Copyright 2026 Chronos Ledger Contributors
// Licensed under the Apache License, Version 2.0

export type InstitutionalRole = 'SUPER_ADMIN' | 'DEPT_ADMIN' | 'FACULTY' | 'STUDENT'
export type DynamicState = 'SCHEDULED' | 'ON_LEAVE' | 'PROXY_SUBSTITUTE' | 'LUNCH' | 'INTERNAL_MEETING' | 'ADHOC_EVENT'
export type VerificationMetric = 'PRESENT' | 'ABSENT' | 'LATE'
export type ExecutionMode = 'PHYSICAL' | 'ONLINE_STREAM'
export type AccessReadiness = 'OPEN_AD_HOC' | 'BUSY' | 'CRITICAL_DO_NOT_DISTURB' | 'VERY_FREE'
export type LogVerificationState = 'PENDING_VERIFICATION' | 'VERIFIED_APPROVED' | 'VERIFIED_DENIED'

export interface AuthUser {
  user_id: string
  full_name: string
  role: InstitutionalRole
  initial_login_state: boolean
}

export interface TokenResponse {
  access_token: string
  refresh_token: string
  token_type: string
  user_id: string
  role: InstitutionalRole
  full_name: string
  initial_login_state: boolean
}

export interface UserProfile {
  id: string
  full_name: string
  email_address: string
  role_type: InstitutionalRole
  department_code: string | null
  assigned_base_station: string | null
  current_occupancy_index: AccessReadiness
  reporting_line_manager: string | null
}

export interface LedgerEntry {
  id: number
  target_date: string
  course_code: string | null
  course_title: string | null
  target_room_identifier: string
  time_window_start: string | null
  time_window_end: string | null
  delivery_format: ExecutionMode
  virtual_connection_string: string | null
  operational_state: DynamicState
  active_instructor_id: string | null
  substitute_instructor_id: string | null
  latitude_target: number | null
  longitude_target: number | null
  altitude_target: number | null
  precision_radius_meters: number | null
}

export interface AttendanceRecord {
  id: number
  ledger_instance_id: number
  student_id: string
  marking_status: VerificationMetric
  authorizing_agent_id: string | null
  modification_timestamp: string
}

export interface AbsenceRequest {
  id: number
  submitting_user_id: string
  target_absence_date: string
  context_justification: string
  approval_state: LogVerificationState
  authorized_by_user_id: string | null
}

export interface GuestEntry {
  id: number
  guest_name: string
  contact_phone: string
  originating_body: string
  target_faculty_id: string
  visitation_intent: string
  handshake_status: LogVerificationState
  timestamp_marked: string
}

export interface FacultyLocation {
  faculty_id: string
  full_name: string
  department_code: string | null
  occupancy_index: AccessReadiness
  resolved_location: string
  status: string
}

export interface FacultyAvailability {
  faculty_id: string
  full_name: string
  department_code: string | null
  availability_label: string
}

export interface Annotation {
  id: number
  ledger_instance_id: number
  creator_id: string
  classification_tag: string
  annotation_payload: string
  distribution_timestamp: string
}

export interface AcademicCycle {
  id: number
  cycle_label: string
  date_bounds_start: string
  date_bounds_end: string
  operational_status: boolean
}

export interface WSEvent<T = unknown> {
  event: string
  payload: T
}
