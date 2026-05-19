// Copyright 2026 Chronos Ledger Contributors
// Licensed under the Apache License, Version 2.0

import { create } from 'zustand'
import type { AuthUser } from '@/types'
import { saveSession, clearSession, getStoredUser } from '@/lib/auth'
import { authApi } from '@/lib/api'

interface AuthState {
  user: AuthUser | null
  isLoading: boolean
  error: string | null
  login: (email: string, password: string) => Promise<AuthUser>
  logout: () => void
  hydrate: () => void
  clearError: () => void
}

export const useAuthStore = create<AuthState>((set) => ({
  user: null,
  isLoading: false,
  error: null,

  hydrate: () => {
    const user = getStoredUser()
    set({ user })
  },

  login: async (email, password) => {
    set({ isLoading: true, error: null })
    try {
      const res = await authApi.login(email, password)
      const data = res.data
      saveSession(data)
      const user: AuthUser = {
        user_id: data.user_id,
        full_name: data.full_name,
        role: data.role,
        initial_login_state: data.initial_login_state,
      }
      set({ user, isLoading: false })
      return user
    } catch (err: unknown) {
      const msg = (err as { response?: { data?: { detail?: string } } })?.response?.data?.detail || 'Login failed'
      set({ isLoading: false, error: msg })
      throw err
    }
  },

  logout: () => {
    clearSession()
    set({ user: null })
  },

  clearError: () => set({ error: null }),
}))
