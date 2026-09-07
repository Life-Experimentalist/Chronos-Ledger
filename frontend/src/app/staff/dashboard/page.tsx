'use client'
// Copyright 2026 Chronos Ledger Contributors
// Licensed under the Apache License, Version 2.0

import { Suspense, useEffect, useState } from 'react'
import { useSearchParams } from 'next/navigation'
import { motion } from 'framer-motion'
import { Wifi } from 'lucide-react'
import { Sidebar } from '@/components/shared/Sidebar'
import { NotificationPanel } from '@/components/shared/NotificationPanel'
import { StatusSwitcher } from '@/components/staff/StatusSwitcher'
import { AttendanceMatrix } from '@/components/staff/AttendanceMatrix'
import { InteractionDesk } from '@/components/staff/InteractionDesk'
import { useAuth } from '@/hooks/useAuth'
import { useWebSocket } from '@/hooks/useWebSocket'
import { useScheduleNotifications } from '@/hooks/useScheduleNotifications'
import { scheduleApi, attendanceApi } from '@/lib/api'
import type { LedgerEntry } from '@/types'

const TABS = ['overview', 'attendance', 'absences', 'guests'] as const
type Tab = (typeof TABS)[number]

export default function StaffDashboard() {
  return (
    <Suspense>
      <StaffDashboardContent />
    </Suspense>
  )
}

function StaffDashboardContent() {
  const { user } = useAuth('STAFF')
  const { isConnected } = useWebSocket()
  const searchParams = useSearchParams()
  const [activeTab, setActiveTab] = useState<Tab>('overview')
  const [todayClasses, setTodayClasses] = useState<LedgerEntry[]>([])
  const [selectedLedger, setSelectedLedger] = useState<LedgerEntry | null>(null)

  useEffect(() => {
    const tab = searchParams.get('tab') as Tab | null
    if (tab && TABS.includes(tab as Tab)) setActiveTab(tab as Tab)
  }, [searchParams])

  // Cache schedule + schedule class-start notifications (works offline)
  useScheduleNotifications(todayClasses)

  useEffect(() => {
    scheduleApi.getTodayLedger().then((r) => {
      setTodayClasses(r.data)
      if (r.data.length > 0) setSelectedLedger(r.data[0])
    }).catch(() => {})
  }, [])

  if (!user) return null

  return (
    <div className="flex h-screen overflow-hidden bg-chronos-dark">
      <Sidebar role={user.role} />

      <div className="flex-1 flex flex-col overflow-hidden">
        <header className="h-16 flex items-center justify-between px-6 border-b border-chronos-border/40 bg-chronos-surface/50 backdrop-blur-sm shrink-0">
          <div>
            <h1 className="text-base font-semibold text-chronos-text">Staff Command Station</h1>
            <p className="text-xs text-chronos-muted">{user.full_name}</p>
          </div>
          <div className="flex items-center gap-3">
            <div className={`flex items-center gap-1.5 text-xs ${isConnected() ? 'text-chronos-emerald' : 'text-chronos-muted'}`}>
              <Wifi className="w-3.5 h-3.5" />
              {isConnected() ? 'Live' : 'Offline'}
            </div>
            <NotificationPanel />
          </div>
        </header>

        {/* Status Switcher, always visible */}
        <div className="px-6 pt-4 shrink-0">
          <StatusSwitcher userId={user.user_id} />
        </div>

        {/* Tab bar */}
        <div className="flex gap-1 px-6 pt-3 pb-0 shrink-0">
          {[
            { id: 'overview', label: 'My Schedule' },
            { id: 'attendance', label: 'Attendance' },
            { id: 'absences', label: 'Absence Requests' },
            { id: 'guests', label: 'Interaction Desk' },
          ].map((tab) => (
            <button
              key={tab.id}
              onClick={() => setActiveTab(tab.id as Tab)}
              className={`px-4 py-2 text-sm rounded-t-lg transition-all border-b-2 ${
                activeTab === tab.id
                  ? 'text-chronos-teal border-chronos-teal bg-chronos-teal/5'
                  : 'text-chronos-text-dim border-transparent hover:text-chronos-text'
              }`}
            >
              {tab.label}
            </button>
          ))}
        </div>

        <main className="flex-1 overflow-y-auto p-6">
          <motion.div key={activeTab} initial={{ opacity: 0, y: 8 }} animate={{ opacity: 1, y: 0 }} transition={{ duration: 0.15 }}>
            {activeTab === 'overview' && (
              <div className="space-y-4 max-w-3xl">
                <p className="section-title">Today&apos;s Classes</p>
                {todayClasses.length === 0 ? (
                  <div className="glass-card p-8 text-center text-chronos-muted">No classes scheduled today.</div>
                ) : (
                  todayClasses.map((entry) => (
                    <div
                      key={entry.id}
                      onClick={() => { setSelectedLedger(entry); setActiveTab('attendance') }}
                      className="glass-card-hover p-5 cursor-pointer"
                    >
                      <div className="flex items-center justify-between">
                        <div>
                          <p className="font-semibold text-chronos-text">{entry.activity_code}, {entry.activity_title}</p>
                          <p className="text-sm text-chronos-text-dim mt-0.5">Room {entry.target_room_identifier} · {entry.time_window_start} – {entry.time_window_end}</p>
                        </div>
                        <span className={`text-xs font-medium px-2.5 py-1 rounded-full border ${
                          entry.operational_state === 'SCHEDULED'
                            ? 'text-chronos-teal bg-chronos-teal/10 border-chronos-teal/20'
                            : 'text-chronos-warning bg-chronos-warning/10 border-chronos-warning/20'
                        }`}>
                          {entry.delivery_format === 'ONLINE_STREAM' ? '🌐 Online' : '🏫 Physical'}
                        </span>
                      </div>
                    </div>
                  ))
                )}
              </div>
            )}

            {activeTab === 'attendance' && (
              <AttendanceMatrix
                classes={todayClasses}
                selectedEntry={selectedLedger}
                onSelectEntry={setSelectedLedger}
              />
            )}

            {activeTab === 'absences' && <AbsenceSubmissionPanel />}
            {activeTab === 'guests' && <InteractionDesk />}
          </motion.div>
        </main>
      </div>
    </div>
  )
}

function AbsenceSubmissionPanel() {
  const [date, setDate] = useState('')
  const [reason, setReason] = useState('')
  const [submitting, setSubmitting] = useState(false)
  const [success, setSuccess] = useState(false)

  const submit = async () => {
    if (!date || !reason) return
    setSubmitting(true)
    try {
      await attendanceApi.submitAbsence({ target_absence_date: date, context_justification: reason })
      setSuccess(true)
      setDate('')
      setReason('')
    } finally {
      setSubmitting(false)
    }
  }

  return (
    <div className="max-w-lg space-y-4">
      <h2 className="text-lg font-semibold text-chronos-text">Submit Absence Request</h2>
      <p className="text-sm text-chronos-muted">Absence requests are routed to your line manager for approval.</p>
      <div className="glass-card p-5 space-y-4">
        <div>
          <label className="block text-xs font-medium text-chronos-text-dim mb-1.5 uppercase tracking-wider">Absence Date</label>
          <input type="date" value={date} onChange={(e) => setDate(e.target.value)} className="input-field" />
        </div>
        <div>
          <label className="block text-xs font-medium text-chronos-text-dim mb-1.5 uppercase tracking-wider">Reason / Justification</label>
          <textarea value={reason} onChange={(e) => setReason(e.target.value)} rows={4} className="input-field resize-none" placeholder="Describe the reason for absence..." />
        </div>
        {success && <p className="text-sm text-chronos-emerald">Request submitted successfully. Awaiting manager approval.</p>}
        <button onClick={submit} disabled={submitting || !date || !reason} className="btn-primary">
          {submitting ? 'Submitting...' : 'Submit Request'}
        </button>
      </div>
    </div>
  )
}
