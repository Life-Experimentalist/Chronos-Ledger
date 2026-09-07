'use client'
// Copyright 2026 Chronos Ledger Contributors
// Licensed under the Apache License, Version 2.0

import { useEffect, useState } from 'react'
import { motion } from 'framer-motion'
import { CheckSquare, XSquare, Clock3, Users, Loader2, Save } from 'lucide-react'
import { attendanceApi } from '@/lib/api'
import { AttendanceBadge } from '@/components/ui/Badge'
import type { LedgerEntry, AttendanceRecord, VerificationMetric } from '@/types'

interface AttendanceMatrixProps {
  classes: LedgerEntry[]
  selectedEntry: LedgerEntry | null
  onSelectEntry: (entry: LedgerEntry) => void
}

export function AttendanceMatrix({ classes, selectedEntry, onSelectEntry }: AttendanceMatrixProps) {
  const [records, setRecords] = useState<Record<string, VerificationMetric>>({})
  const [loading, setLoading] = useState(false)
  const [saving, setSaving] = useState(false)
  const [saved, setSaved] = useState(false)

  useEffect(() => {
    if (!selectedEntry) return
    setLoading(true)
    attendanceApi.getLedgerAttendance(selectedEntry.id)
      .then((r) => {
        const map: Record<string, VerificationMetric> = {}
        r.data.forEach((rec: AttendanceRecord) => {
          map[rec.member_id] = rec.marking_status
        })
        setRecords(map)
      })
      .finally(() => setLoading(false))
  }, [selectedEntry])

  const setStatus = (memberId: string, status: VerificationMetric) => {
    setRecords((prev) => ({ ...prev, [memberId]: status }))
    setSaved(false)
  }

  const saveAll = async () => {
    if (!selectedEntry) return
    setSaving(true)
    try {
      const batch = Object.entries(records).map(([member_id, marking_status]) => ({
        ledger_instance_id: selectedEntry.id,
        member_id,
        marking_status,
      }))
      await attendanceApi.batchMark({ ledger_instance_id: selectedEntry.id, records: batch })
      setSaved(true)
    } finally {
      setSaving(false)
    }
  }

  // Generate dummy member IDs from records keys or show empty state
  const memberIds = Object.keys(records)

  return (
    <div className="space-y-4">
      {/* Class selector */}
      <div className="glass-card p-4">
        <p className="section-title mb-3">Select Class</p>
        <div className="flex flex-wrap gap-2">
          {classes.map((entry) => (
            <button
              key={entry.id}
              onClick={() => onSelectEntry(entry)}
              className={`px-3 py-1.5 text-xs rounded-lg border transition-all ${
                selectedEntry?.id === entry.id
                  ? 'bg-chronos-teal/10 border-chronos-teal/30 text-chronos-teal'
                  : 'border-chronos-border/40 text-chronos-text-dim hover:border-chronos-border'
              }`}
            >
              {entry.activity_code} · {entry.time_window_start}
            </button>
          ))}
        </div>
      </div>

      {selectedEntry ? (
        <div className="glass-card p-5">
          <div className="flex items-center justify-between mb-5">
            <div>
              <p className="font-semibold text-chronos-text">{selectedEntry.activity_code} — {selectedEntry.activity_title}</p>
              <p className="text-sm text-chronos-text-dim mt-0.5">Room {selectedEntry.target_room_identifier} · {selectedEntry.time_window_start} – {selectedEntry.time_window_end}</p>
            </div>
            <div className="flex items-center gap-2">
              {saved && <span className="text-xs text-chronos-emerald">Saved!</span>}
              <button onClick={saveAll} disabled={saving} className="btn-primary text-xs px-3 py-1.5">
                {saving ? <Loader2 className="w-3.5 h-3.5 animate-spin" /> : <Save className="w-3.5 h-3.5" />}
                {saving ? 'Saving...' : 'Save All'}
              </button>
            </div>
          </div>

          {loading ? (
            <div className="flex items-center justify-center py-12">
              <Loader2 className="w-6 h-6 animate-spin text-chronos-teal" />
            </div>
          ) : memberIds.length === 0 ? (
            <div className="text-center py-10">
              <Users className="w-10 h-10 text-chronos-muted/40 mx-auto mb-2" />
              <p className="text-sm text-chronos-muted">No attendance records yet. Members will appear as they self-mark or via import.</p>
            </div>
          ) : (
            <div className="space-y-2">
              {memberIds.map((memberId) => {
                const status = records[memberId]
                return (
                  <motion.div
                    key={memberId}
                    layout
                    className="flex items-center justify-between py-2.5 px-3 bg-chronos-surface rounded-lg"
                  >
                    <div className="flex items-center gap-3">
                      <div className="w-8 h-8 rounded-full bg-chronos-teal/10 flex items-center justify-center text-chronos-teal text-xs font-bold">
                        {memberId.slice(-2)}
                      </div>
                      <span className="text-sm text-chronos-text font-mono">{memberId}</span>
                    </div>
                    <div className="flex items-center gap-2">
                      <AttendanceBadge status={status} />
                      <div className="flex gap-1">
                        {(['PRESENT', 'ABSENT', 'LATE'] as VerificationMetric[]).map((s) => (
                          <button
                            key={s}
                            onClick={() => setStatus(memberId, s)}
                            title={s}
                            className={`p-1.5 rounded-lg transition-colors ${status === s ? 'bg-chronos-teal/20 text-chronos-teal' : 'text-chronos-muted hover:text-chronos-text'}`}
                          >
                            {s === 'PRESENT' && <CheckSquare className="w-4 h-4" />}
                            {s === 'ABSENT' && <XSquare className="w-4 h-4" />}
                            {s === 'LATE' && <Clock3 className="w-4 h-4" />}
                          </button>
                        ))}
                      </div>
                    </div>
                  </motion.div>
                )
              })}
            </div>
          )}
        </div>
      ) : (
        <div className="glass-card p-8 text-center text-chronos-muted">
          Select a class above to manage attendance.
        </div>
      )}
    </div>
  )
}
