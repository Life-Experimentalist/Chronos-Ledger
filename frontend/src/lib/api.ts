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
  changePassword: async (current_password: string, new_password: string) => {
    const res = await api.post('/auth/change-password', { current_password, new_password })
    // The change kills every refresh token the account had, this one included,
    // and the response carries its replacement. Storing it here rather than at
    // the call site means the next screen to offer a password change cannot
    // forget to, and get itself signed out fifteen minutes later.
    if (typeof window !== 'undefined' && res.data?.refresh_token) {
      localStorage.setItem('chronos_refresh', res.data.refresh_token)
    }
    return res
  },
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
// The lobby kiosk is an unattended public terminal with no one to log in, so it
// authenticates with a device API key an admin provisions once. The key cannot
// be baked into the build: this frontend is a static export, so anything
// compiled in ships to every visitor inside the JS bundle.
const KIOSK_KEY_STORAGE = 'chronos_kiosk_key'

export const kioskKey = {
  read: () => (typeof window !== 'undefined' ? localStorage.getItem(KIOSK_KEY_STORAGE) : null),
  save: (key: string) => localStorage.setItem(KIOSK_KEY_STORAGE, key),
  forget: () => localStorage.removeItem(KIOSK_KEY_STORAGE),
}

// A separate instance on purpose. The shared client attaches a Bearer token and,
// on a 401, tries a refresh and then redirects to the sign-in page, which would
// strand a kiosk mid check-in and hand a visitor the staff login screen.
const kioskClient = axios.create({ baseURL: BASE_URL, timeout: 10000 })
kioskClient.interceptors.request.use((config) => {
  const key = kioskKey.read()
  if (key) config.headers['X-API-Key'] = key
  return config
})

export const guestApi = {
  // Kiosk-side: device key, no session.
  checkIn: (data: object) => kioskClient.post('/guest/register-checkin', data),
  searchStaff: (name?: string) =>
    kioskClient.get('/guest/directory', { params: name ? { name } : {} }),
  // Staff-side: these run inside the signed-in app.
  decidePending: (id: number, decision: string) =>
    api.patch(`/guest/${id}/decide`, { decision }),
  getPendingGuests: () => api.get('/guest/pending'),
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
      // Every new member costs a bcrypt hash on the request thread, so
      // this call is measured in seconds, not the 10s the shared client
      // assumes. Matches nginx proxy_read_timeout, which caps it anyway.
      timeout: 60000,
    })
  },
  generateLedger: (targetDate?: string) =>
    api.post('/ingestion/generate-ledger', null, { params: targetDate ? { target_date: targetDate } : {} }),
}
