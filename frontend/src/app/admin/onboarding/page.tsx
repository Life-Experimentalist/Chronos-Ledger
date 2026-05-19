'use client'
// Copyright 2026 Chronos Ledger Contributors
// Licensed under the Apache License, Version 2.0

import { Suspense } from 'react'
import { useSearchParams } from 'next/navigation'
import { useAuth } from '@/hooks/useAuth'
import { OnboardingWizard } from '@/components/admin/OnboardingWizard'

export default function OnboardingPage() {
  return (
    <Suspense>
      <OnboardingContent />
    </Suspense>
  )
}

function OnboardingContent() {
  const { user } = useAuth(['SUPER_ADMIN', 'DEPT_ADMIN'])
  const searchParams = useSearchParams()

  if (!user) return null

  const fromDashboard = searchParams.get('from') === 'dashboard'
  const stepParam = searchParams.get('step')
  const initialStep = stepParam ? Math.max(0, Math.min(4, parseInt(stepParam, 10))) : 0

  return (
    <OnboardingWizard
      fromDashboard={fromDashboard}
      initialStep={initialStep}
    />
  )
}
