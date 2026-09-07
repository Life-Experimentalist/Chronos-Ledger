'use client'
// Copyright 2026 Chronos Ledger Contributors
// Licensed under the Apache License, Version 2.0

import { Suspense, useEffect, useState } from 'react'
import { useSearchParams } from 'next/navigation'
import { motion } from 'framer-motion'
import { Users, CalendarCheck, AlertTriangle, UserX, Wifi, BookOpen } from 'lucide-react'
import { useRouter } from 'next/navigation'
import { Sidebar } from '@/components/shared/Sidebar'
import { NotificationPanel } from '@/components/shared/NotificationPanel'
import { CsvImportZone } from '@/components/admin/CsvImportZone'
import { ProxyOrchestration } from '@/components/admin/ProxyOrchestration'
import { MasterLedger } from '@/components/admin/MasterLedger'
import { useAuth } from '@/hooks/useAuth'
import { useWebSocket } from '@/hooks/useWebSocket'
import { scheduleApi } from '@/lib/api'
import { isTelemetryEnabled, setTelemetryOptOut, recordView } from '@/lib/telemetry'
import type { LedgerEntry } from '@/types'

const TABS = ['overview', 'import', 'proxy', 'ledger'] as const
type Tab = (typeof TABS)[number]

// Outer wrapper provides Suspense boundary required by Next.js static export
// when useSearchParams is used inside a 'use client' component.
export default function AdminDashboard() {
  return (
    <Suspense>
      <AdminDashboardContent />
    </Suspense>
  )
}

function AdminDashboardContent() {
  const { user } = useAuth(['SUPER_ADMIN', 'UNIT_ADMIN'])
  const { isConnected } = useWebSocket()
  const router = useRouter()
  const searchParams = useSearchParams()
  const [activeTab, setActiveTab] = useState<Tab>('overview')
  const [todayLedger, setTodayLedger] = useState<LedgerEntry[]>([])
  const [stats, setStats] = useState({ activeClasses: 0, onLeave: 0, proxied: 0, guests: 0 })
  const [telemetryOn, setTelemetryOn] = useState(true)

  useEffect(() => {
    const tab = searchParams.get('tab') as Tab | null
    if (tab && TABS.includes(tab)) setActiveTab(tab)
  }, [searchParams])

  useEffect(() => {
    setTelemetryOn(isTelemetryEnabled())
    recordView('app')
  }, [])

  useEffect(() => {
    scheduleApi.getTodayLedger().then((res) => {
      const entries: LedgerEntry[] = res.data
      setTodayLedger(entries)
      setStats({
        activeClasses: entries.filter((e) => e.operational_state === 'SCHEDULED').length,
        onLeave: entries.filter((e) => e.operational_state === 'ON_LEAVE').length,
        proxied: entries.filter((e) => e.operational_state === 'PROXY_SUBSTITUTE').length,
        guests: 0,
      })
    }).catch(() => {})
  }, [])

  if (!user) return null

  return (
    <div className="flex h-screen overflow-hidden bg-chronos-dark">
      <Sidebar role={user.role} />

      <div className="flex-1 flex flex-col overflow-hidden">
        {/* Topbar */}
        <header className="h-16 flex items-center justify-between px-6 border-b border-chronos-border/40 bg-chronos-surface/50 backdrop-blur-sm shrink-0">
          <div>
            <h1 className="text-base font-semibold text-chronos-text">Admin Command Center</h1>
            <p className="text-xs text-chronos-muted">Welcome back, {user.full_name}</p>
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
        <div className="flex gap-1 px-6 pt-4 pb-0 shrink-0 items-center">
          {[
            { id: 'overview', label: 'Overview' },
            { id: 'import', label: 'Import Data' },
            { id: 'proxy', label: 'Proxy Management' },
            { id: 'ledger', label: 'Master Ledger' },
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
          <button
            onClick={() => router.push('/admin/onboarding?from=dashboard')}
            className="ml-auto flex items-center gap-1.5 px-3 py-1.5 text-xs text-chronos-teal border border-chronos-teal/30 rounded-lg hover:bg-chronos-teal/5 transition-colors"
          >
            <BookOpen className="w-3.5 h-3.5" />
            Setup Guide
          </button>
        </div>

        {/* Content */}
        <main className="flex-1 overflow-y-auto p-6">
          <motion.div
            key={activeTab}
            initial={{ opacity: 0, y: 8 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ duration: 0.15 }}
          >
            {activeTab === 'overview' && (
              <div className="space-y-6">
                <div className="grid grid-cols-1 sm:grid-cols-2 xl:grid-cols-4 gap-4">
                  <StatCard icon={CalendarCheck} label="Active Classes" value={stats.activeClasses} color="teal" />
                  <StatCard icon={UserX} label="Staff on Leave" value={stats.onLeave} color="danger" />
                  <StatCard icon={Users} label="Proxy Assignments" value={stats.proxied} color="warning" />
                  <StatCard icon={AlertTriangle} label="Pending Guests" value={stats.guests} color="accent" />
                </div>

                <div className="glass-card p-5">
                  <p className="section-title mb-3">Privacy & Telemetry</p>
                  <div className="flex items-center justify-between">
                    <div>
                      <p className="text-sm text-chronos-text">Anonymous usage analytics</p>
                      <p className="text-xs text-chronos-muted mt-0.5">Sends anonymous view counts via CFlair-Counter. No PII collected.</p>
                    </div>
                    <button
                      onClick={() => {
                        const next = !telemetryOn
                        setTelemetryOptOut(!next)
                        setTelemetryOn(next)
                      }}
                      className={`relative inline-flex h-6 w-11 items-center rounded-full transition-colors ${
                        telemetryOn ? 'bg-chronos-teal' : 'bg-chronos-border'
                      }`}
                    >
                      <span className={`inline-block h-4 w-4 rounded-full bg-white shadow transition-transform ${
                        telemetryOn ? 'translate-x-6' : 'translate-x-1'
                      }`} />
                    </button>
                  </div>
                </div>

                <div className="glass-card p-5">
                  <p className="section-title mb-4">Today&apos;s Schedule Overview</p>
                  {todayLedger.length === 0 ? (
                    <p className="text-chronos-muted text-sm">No ledger entries for today. Generate the daily ledger from the Import tab.</p>
                  ) : (
                    <div className="space-y-2">
                      {todayLedger.slice(0, 8).map((entry) => (
                        <div key={entry.id} className="flex items-center justify-between py-2 border-b border-chronos-border/20 last:border-0">
                          <div>
                            <span className="text-sm font-medium text-chronos-text">{entry.activity_code} — {entry.activity_title}</span>
                            <span className="text-xs text-chronos-muted ml-3">Room {entry.target_room_identifier} · {entry.time_window_start} – {entry.time_window_end}</span>
                          </div>
                          <span className={`text-xs font-medium px-2 py-0.5 rounded-full ${
                            entry.operational_state === 'SCHEDULED' ? 'text-chronos-teal bg-chronos-teal/10' :
                            entry.operational_state === 'ON_LEAVE' ? 'text-chronos-danger bg-chronos-danger/10' :
                            'text-chronos-warning bg-chronos-warning/10'
                          }`}>
                            {entry.operational_state}
                          </span>
                        </div>
                      ))}
                    </div>
                  )}
                </div>
              </div>
            )}

            {activeTab === 'import' && <CsvImportZone />}
            {activeTab === 'proxy' && <ProxyOrchestration />}
            {activeTab === 'ledger' && <MasterLedger entries={todayLedger} />}
          </motion.div>
        </main>
      </div>
    </div>
  )
}

function StatCard({ icon: Icon, label, value, color }: { icon: React.ElementType; label: string; value: number; color: string }) {
  const colorClasses: Record<string, string> = {
    teal: 'text-chronos-teal bg-chronos-teal/10',
    danger: 'text-chronos-danger bg-chronos-danger/10',
    warning: 'text-chronos-warning bg-chronos-warning/10',
    accent: 'text-chronos-accent bg-chronos-accent/10',
  }
  return (
    <div className="stat-card">
      <div className={`w-9 h-9 rounded-lg flex items-center justify-center ${colorClasses[color]}`}>
        <Icon className="w-5 h-5" />
      </div>
      <div>
        <p className="text-2xl font-bold text-chronos-text">{value}</p>
        <p className="text-xs text-chronos-muted">{label}</p>
      </div>
    </div>
  )
}
