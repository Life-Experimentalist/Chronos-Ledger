// Copyright 2026 Chronos Ledger Contributors
// Licensed under the Apache License, Version 2.0

import { useEffect } from 'react'
import { useRouter } from 'next/navigation'
import { useAuthStore } from '@/store/auth'
import type { InstitutionalRole } from '@/types'

export function useAuth(requiredRole?: InstitutionalRole | InstitutionalRole[]) {
  const { user, hydrate } = useAuthStore()
  const router = useRouter()

  useEffect(() => {
    hydrate()
  }, [hydrate])

  useEffect(() => {
    if (!user) return
    if (!requiredRole) return

    const allowed = Array.isArray(requiredRole) ? requiredRole : [requiredRole]
    if (!allowed.includes(user.role)) {
      router.push('/')
    }
  }, [user, requiredRole, router])

  return { user, isAuthenticated: !!user }
}
