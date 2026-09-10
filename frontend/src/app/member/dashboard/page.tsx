'use client'
// Copyright 2026 Chronos Ledger Contributors
// Licensed under the Apache License, Version 2.0

import { Suspense, useEffect, useState } from 'react'
import { useSearchParams } from 'next/navigation'
import { motion } from 'framer-motion'
import { Wifi, Calendar, Search, MapPin } from 'lucide-react'
import { Sidebar } from '@/components/shared/Sidebar'
import { NotificationPanel } from '@/components/shared/NotificationPanel'
import { LiveTimeline } from '@/components/member/LiveTimeline'
import { ProximityCard } from '@/components/member/ProximityCard'
import { StaffLocator } from '@/components/member/StaffLocator'
import { useAuth } from '@/hooks/useAuth'
import { useWebSocket } from '@/hooks/useWebSocket'
import { useScheduleNotifications } from '@/hooks/useScheduleNotifications'
import { scheduleApi } from '@/lib/api'
import { windowState } from '@/lib/schedule'
import type { LedgerEntry } from '@/types'

const TABS = ['schedule', 'attendance', 'locator'] as const
type Tab = (typeof TABS)[number]

export default function MemberDashboard() {
  return (
    <Suspense>
      <MemberDashboardContent />
    </Suspense>
  )
}

function MemberDashboardContent() {
  const { user } = useAuth('MEMBER')
  const { isConnected } = useWebSocket()
  const searchParams = useSearchParams()
  const [activeTab, setActiveTab] = useState<Tab>('schedule')
  const [todayEntries, setTodayEntries] = useState<LedgerEntry[]>([])
  const [currentEntry, setCurrentEntry] = useState<LedgerEntry | null>(null)

  // Hook that caches schedule in IndexedDB and schedules offline-capable notifications
  useScheduleNotifications(todayEntries)

  useEffect(() => {
    const tab = searchParams.get('tab')
    if (tab === 'attendance') setActiveTab('attendance')
    else if (tab === 'locator') setActiveTab('locator')
  }, [searchParams])

  useEffect(() => {
    scheduleApi.getTodayLedger().then((r) => {
      setTodayEntries(r.data)
      const now = new Date()
      const active = r.data.find((e: LedgerEntry) => windowState(e, now).active)
      if (active) setCurrentEntry(active)
    }).catch(() => {})
  }, [])

  if (!user) return null

  return (
    <div className="flex h-screen overflow-hidden bg-chronos-dark">
      <Sidebar role={user.role} />

      <div className="flex-1 flex flex-col overflow-hidden">
        <header className="h-16 flex items-center justify-between px-6 border-b border-chronos-border/40 bg-chronos-surface/50 backdrop-blur-sm shrink-0">
          <div>
            <h1 className="text-base font-semibold text-chronos-text">Member Portal</h1>
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

        {/* Tab bar */}
        <div className="flex gap-1 px-6 pt-4 pb-0 shrink-0">
          {[
            { id: 'schedule', label: 'My Schedule', icon: Calendar },
            { id: 'attendance', label: 'Mark Attendance', icon: MapPin },
            { id: 'locator', label: 'Find Staff', icon: Search },
          ].map((tab) => {
            const Icon = tab.icon
            return (
              <button
                key={tab.id}
                onClick={() => setActiveTab(tab.id as Tab)}
                className={`flex items-center gap-2 px-4 py-2 text-sm rounded-t-lg transition-all border-b-2 ${
                  activeTab === tab.id
                    ? 'text-chronos-teal border-chronos-teal bg-chronos-teal/5'
                    : 'text-chronos-text-dim border-transparent hover:text-chronos-text'
                }`}
              >
                <Icon className="w-4 h-4" />
                {tab.label}
              </button>
            )
          })}
        </div>

        <main className="flex-1 overflow-y-auto p-6">
          <motion.div key={activeTab} initial={{ opacity: 0, y: 8 }} animate={{ opacity: 1, y: 0 }} transition={{ duration: 0.15 }}>
            {activeTab === 'schedule' && (
              <div className="max-w-2xl space-y-4">
                <p className="section-title">Today&apos;s Timeline</p>
                <LiveTimeline entries={todayEntries} />
              </div>
            )}
            {activeTab === 'attendance' && (
              <div className="max-w-md">
                <ProximityCard currentEntry={currentEntry} userId={user.user_id} />
              </div>
            )}
            {activeTab === 'locator' && (
              <div className="max-w-2xl">
                <StaffLocator />
              </div>
            )}
          </motion.div>
        </main>
      </div>
    </div>
  )
}
