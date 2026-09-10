'use client'
// Copyright 2026 Chronos Ledger Contributors
// Licensed under the Apache License, Version 2.0

import { useEffect, useState } from 'react'
import { api } from '@/lib/api'

export interface Vocabulary {
  staff: string
  member: string
  activity: string
  unit: string
  lead: string
  cycle: string
}

export interface OrgConfig {
  org_profile: string
  labels: Vocabulary
  password_min_length: number
}

// Synchronous fallback so the first paint never waits on the network, and an
// offline PWA still renders something sensible. The password floor here is the
// backend's own default rather than its absolute minimum: guessing low would
// let the form accept what the API then refuses.
export const FALLBACK_CONFIG: OrgConfig = {
  org_profile: 'generic',
  labels: {
    staff: 'Staff',
    member: 'Member',
    activity: 'Activity',
    unit: 'Unit',
    lead: 'Lead',
    cycle: 'Cycle',
  },
  password_min_length: 12,
}

// One request for the whole app. `/config` is public, does not change while a
// tab is open, and three screens want a different field out of it. The
// in-flight promise is shared as well, so two components mounting together
// make one call rather than two.
let cached: OrgConfig | null = null
let inFlight: Promise<OrgConfig> | null = null

function load(): Promise<OrgConfig> {
  if (inFlight) return inFlight
  inFlight = api
    .get('/config')
    .then((res) => {
      const merged: OrgConfig = {
        ...FALLBACK_CONFIG,
        ...res.data,
        labels: { ...FALLBACK_CONFIG.labels, ...res.data?.labels },
      }
      cached = merged
      return merged
    })
    .catch(() => {
      // Offline, or a backend older than a field asked for here. The fallback
      // stands, and the next mount is free to try again.
      inFlight = null
      return FALLBACK_CONFIG
    })
  return inFlight
}

export function useOrgConfig(): OrgConfig {
  const [config, setConfig] = useState<OrgConfig>(cached ?? FALLBACK_CONFIG)

  useEffect(() => {
    if (cached) return
    let cancelled = false
    load().then((loaded) => {
      if (!cancelled) setConfig(loaded)
    })
    return () => {
      cancelled = true
    }
  }, [])

  return config
}
