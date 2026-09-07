'use client'
// Copyright 2026 Chronos Ledger Contributors
// Licensed under the Apache License, Version 2.0

import { useState, useEffect } from 'react'
import { motion, AnimatePresence } from 'framer-motion'
import { Search, MapPin, Loader2 } from 'lucide-react'
import { scheduleApi } from '@/lib/api'
import { useVocabulary } from '@/hooks/useVocabulary'
import { OccupancyBadge } from '@/components/ui/Badge'
import type { StaffLocation } from '@/types'

export function StaffLocator() {
  const vocab = useVocabulary()
  const [query, setQuery] = useState('')
  const [locations, setLocations] = useState<StaffLocation[]>([])
  const [loading, setLoading] = useState(true)

  useEffect(() => {
    scheduleApi.getAllStaffLocations()
      .then((r) => setLocations(r.data))
      .finally(() => setLoading(false))
  }, [])

  const filtered = locations.filter(
    (f) =>
      !query ||
      f.full_name.toLowerCase().includes(query.toLowerCase()) ||
      f.unit_code?.toLowerCase().includes(query.toLowerCase())
  )

  return (
    <div className="space-y-4">
      <div>
        <h2 className="text-lg font-semibold text-chronos-text">{vocab.staff} Locator</h2>
        <p className="text-sm text-chronos-muted mt-0.5">{`Find where ${vocab.staff.toLowerCase()} members are right now`}</p>
      </div>

      <div className="relative">
        <Search className="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-chronos-muted" />
        <input
          value={query}
          onChange={(e) => setQuery(e.target.value)}
          placeholder="Search by name or unit..."
          className="input-field pl-10"
          autoComplete="off"
        />
      </div>

      {loading ? (
        <div className="flex items-center justify-center py-12">
          <Loader2 className="w-6 h-6 animate-spin text-chronos-teal" />
        </div>
      ) : (
        <div className="space-y-2">
          <AnimatePresence>
            {filtered.length === 0 ? (
              <div className="glass-card p-8 text-center text-chronos-muted">
                No staff members found matching &quot;{query}&quot;
              </div>
            ) : (
              filtered.map((staff, idx) => (
                <motion.div
                  key={staff.staff_id}
                  initial={{ opacity: 0, y: 8 }}
                  animate={{ opacity: 1, y: 0 }}
                  transition={{ delay: idx * 0.03 }}
                  className="glass-card-hover p-4"
                >
                  <div className="flex items-center gap-4">
                    <div className="w-10 h-10 rounded-full bg-chronos-teal/10 flex items-center justify-center text-chronos-teal font-bold shrink-0">
                      {staff.full_name.charAt(0)}
                    </div>
                    <div className="flex-1 min-w-0">
                      <div className="flex items-center gap-2">
                        <span className="font-medium text-chronos-text text-sm">{staff.full_name}</span>
                        <OccupancyBadge status={staff.occupancy_index} />
                      </div>
                      {staff.unit_code && (
                        <p className="text-xs text-chronos-text-dim">{staff.unit_code}</p>
                      )}
                    </div>
                    <div className="text-right shrink-0">
                      <div className="flex items-center gap-1 text-xs text-chronos-text-dim">
                        <MapPin className="w-3.5 h-3.5 text-chronos-teal" />
                        <span className="font-medium text-chronos-text">{staff.resolved_location}</span>
                      </div>
                      <p className="text-[10px] text-chronos-muted mt-0.5 max-w-36 text-right truncate">
                        {staff.status}
                      </p>
                    </div>
                  </div>
                </motion.div>
              ))
            )}
          </AnimatePresence>
        </div>
      )}
    </div>
  )
}
