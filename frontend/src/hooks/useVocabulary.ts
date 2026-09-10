'use client'
// Copyright 2026 Chronos Ledger Contributors
// Licensed under the Apache License, Version 2.0

import { FALLBACK_CONFIG, useOrgConfig } from './useOrgConfig'
import type { Vocabulary } from './useOrgConfig'

export type { Vocabulary }

// Kept as its own export: a caller that renders a label without mounting the
// hook has been reaching for this since before there was anything else in
// /config to fetch.
export const GENERIC_VOCABULARY: Vocabulary = FALLBACK_CONFIG.labels

export function useVocabulary(): Vocabulary {
  return useOrgConfig().labels
}
