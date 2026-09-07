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

// Synchronous fallback so the first paint never waits on the network.
export const GENERIC_VOCABULARY: Vocabulary = {
  staff: 'Staff',
  member: 'Member',
  activity: 'Activity',
  unit: 'Unit',
  lead: 'Lead',
  cycle: 'Cycle',
}

let cached: Vocabulary | null = null

export function useVocabulary(): Vocabulary {
  const [vocab, setVocab] = useState<Vocabulary>(cached ?? GENERIC_VOCABULARY)

  useEffect(() => {
    if (cached) return
    let cancelled = false
    api
      .get('/config')
      .then((res) => {
        const merged = { ...GENERIC_VOCABULARY, ...res.data.labels }
        cached = merged
        if (!cancelled) setVocab(merged)
      })
      .catch(() => {
        // Offline or old backend: the generic labels stay.
      })
    return () => {
      cancelled = true
    }
  }, [])

  return vocab
}
