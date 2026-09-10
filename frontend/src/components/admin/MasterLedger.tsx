'use client'
// Copyright 2026 Chronos Ledger Contributors
// Licensed under the Apache License, Version 2.0

import { useState } from 'react'
import { Search, Filter } from 'lucide-react'
import { DynamicStateBadge } from '@/components/ui/Badge'
import type { LedgerEntry, DynamicState } from '@/types'

interface MasterLedgerProps {
  entries: LedgerEntry[]
}

export function MasterLedger({ entries }: MasterLedgerProps) {
  const [search, setSearch] = useState('')
  const [filterState, setFilterState] = useState<DynamicState | 'ALL'>('ALL')

  const filtered = entries.filter((e) => {
    const matchesSearch =
      !search ||
      e.activity_code?.toLowerCase().includes(search.toLowerCase()) ||
      e.activity_title?.toLowerCase().includes(search.toLowerCase()) ||
      e.target_room_identifier.toLowerCase().includes(search.toLowerCase())
    const matchesState = filterState === 'ALL' || e.operational_state === filterState
    return matchesSearch && matchesState
  })

  return (
    <div className="space-y-4">
      <div className="flex items-center justify-between">
        <h2 className="text-lg font-semibold text-chronos-text">Today&apos;s Master Ledger</h2>
        <span className="text-sm text-chronos-muted">{filtered.length} entries</span>
      </div>

      {/* Filters */}
      <div className="flex gap-3 flex-wrap">
        <div className="relative">
          <Search className="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-chronos-muted" />
          <input
            value={search}
            onChange={(e) => setSearch(e.target.value)}
            placeholder="Search activity, room..."
            className="input-field pl-9 w-60 text-sm"
          />
        </div>
        <select
          value={filterState}
          onChange={(e) => setFilterState(e.target.value as DynamicState | 'ALL')}
          className="input-field w-40 text-sm"
        >
          <option value="ALL">All States</option>
          <option value="SCHEDULED">Scheduled</option>
          <option value="ON_LEAVE">On Leave</option>
          <option value="PROXY_SUBSTITUTE">Proxy</option>
          <option value="ADHOC_EVENT">Ad-Hoc</option>
        </select>
      </div>

      {/* Table */}
      <div className="glass-card overflow-hidden">
        <div className="overflow-x-auto">
          <table className="w-full text-sm">
            <thead>
              <tr className="border-b border-chronos-border/40">
                <th className="text-left px-4 py-3 text-xs font-semibold text-chronos-text-dim uppercase tracking-wider">Activity</th>
                <th className="text-left px-4 py-3 text-xs font-semibold text-chronos-text-dim uppercase tracking-wider">Room</th>
                <th className="text-left px-4 py-3 text-xs font-semibold text-chronos-text-dim uppercase tracking-wider">Time</th>
                <th className="text-left px-4 py-3 text-xs font-semibold text-chronos-text-dim uppercase tracking-wider">Lead</th>
                <th className="text-left px-4 py-3 text-xs font-semibold text-chronos-text-dim uppercase tracking-wider">State</th>
                <th className="text-left px-4 py-3 text-xs font-semibold text-chronos-text-dim uppercase tracking-wider">Mode</th>
              </tr>
            </thead>
            <tbody>
              {filtered.length === 0 ? (
                <tr>
                  <td colSpan={6} className="px-4 py-12 text-center text-chronos-muted text-sm">
                    {entries.length === 0 ? 'No ledger entries for today.' : 'No entries match the current filter.'}
                  </td>
                </tr>
              ) : (
                filtered.map((entry) => (
                  <tr key={entry.id} className="table-row">
                    <td className="px-4 py-3">
                      <p className="font-medium text-chronos-text">{entry.activity_code}</p>
                      <p className="text-xs text-chronos-text-dim">{entry.activity_title}</p>
                    </td>
                    <td className="px-4 py-3 text-chronos-text-dim">{entry.target_room_identifier}</td>
                    <td className="px-4 py-3 text-chronos-text-dim text-xs font-mono">
                      {entry.time_window_start} – {entry.time_window_end}
                    </td>
                    <td className="px-4 py-3 text-chronos-text-dim text-xs">
                      {entry.substitute_lead_id
                        ? <><span className="text-chronos-warning">{entry.substitute_lead_id}</span> <span className="text-chronos-muted">(proxy)</span></>
                        : entry.active_lead_id || '-'}
                    </td>
                    <td className="px-4 py-3"><DynamicStateBadge state={entry.operational_state} /></td>
                    <td className="px-4 py-3 text-xs text-chronos-muted">{entry.delivery_format === 'ONLINE_STREAM' ? '🌐 Online' : '🏫 Physical'}</td>
                  </tr>
                ))
              )}
            </tbody>
          </table>
        </div>
      </div>
    </div>
  )
}
