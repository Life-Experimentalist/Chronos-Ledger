// Copyright 2026 Chronos Ledger Contributors
// Licensed under the Apache License, Version 2.0

import type { AuthUser, TokenResponse } from '@/types'

export function saveSession(data: TokenResponse): void {
  localStorage.setItem('chronos_token', data.access_token)
  localStorage.setItem('chronos_refresh', data.refresh_token)
  const user: AuthUser = {
    user_id: data.user_id,
    full_name: data.full_name,
    role: data.role,
    initial_login_state: data.initial_login_state,
  }
  localStorage.setItem('chronos_user', JSON.stringify(user))
}

export function clearSession(): void {
  localStorage.removeItem('chronos_token')
  localStorage.removeItem('chronos_refresh')
  localStorage.removeItem('chronos_user')
}

export function getStoredUser(): AuthUser | null {
  if (typeof window === 'undefined') return null
  const raw = localStorage.getItem('chronos_user')
  if (!raw) return null
  try {
    return JSON.parse(raw) as AuthUser
  } catch {
    return null
  }
}

export function getRefreshToken(): string | null {
  if (typeof window === 'undefined') return null
  return localStorage.getItem('chronos_refresh')
}

export function getToken(): string | null {
  if (typeof window === 'undefined') return null
  return localStorage.getItem('chronos_token')
}

export function isAuthenticated(): boolean {
  return !!getToken()
}

export function roleRedirectPath(role: string): string {
  switch (role) {
    case 'SUPER_ADMIN':
    case 'DEPT_ADMIN':
      return '/admin/dashboard'
    case 'FACULTY':
      return '/faculty/dashboard'
    case 'STUDENT':
      return '/student/dashboard'
    default:
      return '/'
  }
}
