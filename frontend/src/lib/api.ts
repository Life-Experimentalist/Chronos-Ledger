// Copyright 2026 Chronos Ledger Contributors
// Licensed under the Apache License, Version 2.0

import axios, { AxiosInstance, InternalAxiosRequestConfig } from 'axios'

const BASE_URL = process.env.NEXT_PUBLIC_API_URL || 'http://localhost/api/v1'

let refreshInFlight: Promise<string | null> | null = null

async function tryRefresh(): Promise<string | null> {
  const stored = localStorage.getItem('chronos_refresh')
  if (!stored) return null
  try {
    // Plain axios on purpose: the client's own interceptor must not see this 401.
    const res = await axios.post(`${BASE_URL}/auth/refresh`, { refresh_token: stored })
    localStorage.setItem('chronos_token', res.data.access_token)
    localStorage.setItem('chronos_refresh', res.data.refresh_token)
    return res.data.access_token as string
  } catch {
    return null
  }
}

function createApiClient(): AxiosInstance {
  const client = axios.create({ baseURL: BASE_URL, timeout: 10000 })

  client.interceptors.request.use((config) => {
    const token = typeof window !== 'undefined' ? localStorage.getItem('chronos_token') : null
    if (token) config.headers.Authorization = `Bearer ${token}`
    return config
  })

  client.interceptors.response.use(
    (r) => r,
    async (err) => {
      const original = err.config as (InternalAxiosRequestConfig & { _retried?: boolean }) | undefined
      if (err.response?.status === 401 && typeof window !== 'undefined' && original && !original._retried) {
        // One silent refresh, shared across concurrent 401s, then retry once.
        if (!refreshInFlight) {
          refreshInFlight = tryRefresh().finally(() => {
            refreshInFlight = null
          })
        }
        const token = await refreshInFlight
        if (token) {
          original._retried = true
          original.headers.Authorization = `Bearer ${token}`
          return client(original)
        }
        localStorage.removeItem('chronos_token')
        localStorage.removeItem('chronos_refresh')
        localStorage.removeItem('chronos_user')
        window.location.href = '/'
      }
      return Promise.reject(err)
    }
  )

  return client
}

export const api = createApiClient()

// ── Auth ──────────────────────────────────────────────────────────────────────
export const authApi = {
  login: (email: string, password: string) =>
    api.post('/auth/login', { email, password }),
  me: () => api.get('/auth/me'),
  changePassword: (current_password: string, new_password: string) =>
    api.post('/auth/change-password', { current_password, new_password }),
  logout: (refresh_token: string) => api.post('/auth/logout', { refresh_token }),
}

// ── Schedule ──────────────────────────────────────────────────────────────────
export const scheduleApi = {
  getTodayLedger: () => api.get('/schedule/ledger/today'),
  getStaffLocation: (staffId: string) => api.get(`/schedule/staff/${staffId}/location`),
  getAllStaffLocations: () => api.get('/schedule/staff/all/locations'),
  listCycles: () => api.get('/schedule/cycles'),
  createCycle: (data: object) => api.post('/schedule/cycles', data),
  closeCycle: (id: number) => api.patch(`/schedule/cycles/${id}/close`),
  cloneCycle: (oldId: number, newId: number) => api.post(`/schedule/cycles/${oldId}/clone-to/${newId}`),
  updateLedger: (id: number, data: object) => api.patch(`/schedule/ledger/${id}`, data),
}

// ── Calendar sync ──────────────────────────────────────────────────────────────
export const calendarApi = {
  getFeedToken: () => api.get('/sync/feed-token'),
  rotateFeedToken: () => api.post('/sync/feed-token/rotate'),
}

// ── Attendance ────────────────────────────────────────────────────────────────
export const attendanceApi = {
  markAttendance: (data: object) => api.post('/attendance/mark', data),
  batchMark: (data: object) => api.post('/attendance/batch', data),
  getLedgerAttendance: (ledgerId: number) => api.get(`/attendance/ledger/${ledgerId}`),
  submitAbsence: (data: object) => api.post('/attendance/absence', data),
  getPendingAbsences: () => api.get('/attendance/absence/pending'),
  decideAbsence: (logId: number, decision: string) =>
    api.patch(`/attendance/absence/${logId}/decide`, { decision }),
  createAnnotation: (data: object) => api.post('/attendance/annotations', data),
  getAnnotations: (ledgerId: number) => api.get(`/attendance/annotations/${ledgerId}`),
}

// ── Guest ─────────────────────────────────────────────────────────────────────
export const guestApi = {
  checkIn: (data: object) => api.post('/guest/register-checkin', data),
  decidePending: (id: number, decision: string) =>
    api.patch(`/guest/${id}/decide`, { decision }),
  getPendingGuests: () => api.get('/guest/pending'),
  searchStaff: (name?: string) => api.get('/guest/directory', { params: name ? { name } : {} }),
}

// ── Users ─────────────────────────────────────────────────────────────────────
export const usersApi = {
  list: (params?: object) => api.get('/users/', { params }),
  create: (data: object) => api.post('/users/', data),
  getById: (id: string) => api.get(`/users/${id}`),
  update: (id: string, data: object) => api.patch(`/users/${id}`, data),
  updateStatus: (id: string, status: string) => api.put(`/users/${id}/status`, { status }),
  listAvailableStaff: (unit?: string) =>
    api.get('/users/staff/available', { params: unit ? { unit } : {} }),
}

// ── Ingestion ─────────────────────────────────────────────────────────────────
export const ingestionApi = {
  uploadCsv: (cycleId: number, file: File) => {
    const form = new FormData()
    form.append('file', file)
    return api.post(`/ingestion/upload-csv?cycle_id=${cycleId}`, form, {
      headers: { 'Content-Type': 'multipart/form-data' },
    })
  },
  generateLedger: (targetDate?: string) =>
    api.post('/ingestion/generate-ledger', null, { params: targetDate ? { target_date: targetDate } : {} }),
}
