'use client'
// Copyright 2026 Chronos Ledger Contributors
// Licensed under the Apache License, Version 2.0

import { useEffect, useState } from 'react'
import { motion } from 'framer-motion'
import { Users, ArrowRight, CheckCircle2, Loader2, RefreshCw } from 'lucide-react'
import { usersApi, attendanceApi } from '@/lib/api'
import { RsvpStateBadge } from '@/components/ui/Badge'
import type { AbsenceRequest, UserProfile } from '@/types'

export function ProxyOrchestration() {
  const [absences, setAbsences] = useState<AbsenceRequest[]>([])
  const [availableStaff, setAvailableStaff] = useState<UserProfile[]>([])
  const [loading, setLoading] = useState(true)
  const [processing, setProcessing] = useState<number | null>(null)

  const load = () => {
    setLoading(true)
    Promise.all([
      attendanceApi.getPendingAbsences(),
      usersApi.listAvailableStaff(),
    ]).then(([absRes, facRes]) => {
      setAbsences(absRes.data)
      setAvailableStaff(facRes.data)
    }).finally(() => setLoading(false))
  }

  useEffect(() => { load() }, [])

  const handleDecide = async (logId: number, decision: 'VERIFIED_APPROVED' | 'VERIFIED_DENIED') => {
    setProcessing(logId)
    try {
      await attendanceApi.decideAbsence(logId, decision)
      setAbsences((prev) => prev.filter((a) => a.id !== logId))
    } finally {
      setProcessing(null)
    }
  }

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <div>
          <h2 className="text-lg font-semibold text-chronos-text">Proxy & Absence Management</h2>
          <p className="text-sm text-chronos-muted mt-0.5">Review pending absence requests and assign substitute staff</p>
        </div>
        <button onClick={load} className="btn-secondary text-xs">
          <RefreshCw className={`w-3.5 h-3.5 ${loading ? 'animate-spin' : ''}`} />
          Refresh
        </button>
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
        {/* Pending Absences */}
        <div className="lg:col-span-2 glass-card p-5">
          <p className="section-title mb-4 flex items-center gap-2">
            <span>Pending Absence Requests</span>
            {absences.length > 0 && (
              <span className="bg-chronos-warning/20 text-chronos-warning text-xs font-bold px-1.5 py-0.5 rounded-full">
                {absences.length}
              </span>
            )}
          </p>

          {loading ? (
            <div className="flex items-center justify-center py-12">
              <Loader2 className="w-6 h-6 animate-spin text-chronos-teal" />
            </div>
          ) : absences.length === 0 ? (
            <div className="text-center py-10">
              <CheckCircle2 className="w-10 h-10 text-chronos-emerald/40 mx-auto mb-2" />
              <p className="text-sm text-chronos-muted">No pending absence requests</p>
            </div>
          ) : (
            <div className="space-y-3">
              {absences.map((absence) => (
                <motion.div
                  key={absence.id}
                  layout
                  initial={{ opacity: 0, x: -8 }}
                  animate={{ opacity: 1, x: 0 }}
                  exit={{ opacity: 0, x: 8 }}
                  className="bg-chronos-surface rounded-lg p-4 border border-chronos-border/40"
                >
                  <div className="flex items-start justify-between gap-4">
                    <div className="min-w-0">
                      <div className="flex items-center gap-2 mb-1">
                        <span className="text-sm font-medium text-chronos-text truncate">{absence.submitting_user_id}</span>
                        <RsvpStateBadge state={absence.approval_state} />
                      </div>
                      <p className="text-xs text-chronos-teal font-medium">{absence.target_absence_date}</p>
                      <p className="text-xs text-chronos-text-dim mt-1 line-clamp-2">{absence.context_justification}</p>
                    </div>
                    <div className="flex gap-2 shrink-0">
                      <button
                        onClick={() => handleDecide(absence.id, 'VERIFIED_APPROVED')}
                        disabled={processing === absence.id}
                        className="px-3 py-1.5 text-xs font-medium bg-chronos-emerald/10 hover:bg-chronos-emerald/20 text-chronos-emerald border border-chronos-emerald/20 rounded-lg transition-colors flex items-center gap-1"
                      >
                        {processing === absence.id ? <Loader2 className="w-3 h-3 animate-spin" /> : 'Approve'}
                      </button>
                      <button
                        onClick={() => handleDecide(absence.id, 'VERIFIED_DENIED')}
                        disabled={processing === absence.id}
                        className="px-3 py-1.5 text-xs font-medium bg-chronos-danger/10 hover:bg-chronos-danger/20 text-chronos-danger border border-chronos-danger/20 rounded-lg transition-colors"
                      >
                        Deny
                      </button>
                    </div>
                  </div>
                </motion.div>
              ))}
            </div>
          )}
        </div>

        {/* Available Staff */}
        <div className="glass-card p-5">
          <p className="section-title mb-4">Available Staff</p>
          <div className="space-y-2">
            {availableStaff.slice(0, 10).map((f) => (
              <div key={f.id} className="flex items-center gap-3 py-2 border-b border-chronos-border/20 last:border-0">
                <div className="w-8 h-8 rounded-full bg-chronos-teal/10 flex items-center justify-center text-chronos-teal text-xs font-bold">
                  {f.full_name.charAt(0)}
                </div>
                <div className="min-w-0">
                  <p className="text-xs font-medium text-chronos-text truncate">{f.full_name}</p>
                  <p className="text-[10px] text-chronos-muted">{f.unit_code || 'No unit'}</p>
                </div>
              </div>
            ))}
            {availableStaff.length === 0 && (
              <p className="text-xs text-chronos-muted text-center py-4">No staff data available</p>
            )}
          </div>
        </div>
      </div>
    </div>
  )
}
