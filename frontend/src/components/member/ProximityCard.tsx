'use client'
// Copyright 2026 Chronos Ledger Contributors
// Licensed under the Apache License, Version 2.0

import { useState, useEffect } from 'react'
import { motion, AnimatePresence } from 'framer-motion'
import { MapPin, Wifi, CheckCircle2, AlertCircle, Loader2, Navigation } from 'lucide-react'
import { useGeolocation } from '@/hooks/useGeolocation'
import { attendanceApi } from '@/lib/api'
import { queueAttendanceMark, getPendingCount, flushAttendanceQueue } from '@/lib/indexeddb'
import { getToken } from '@/lib/auth'
import type { LedgerEntry } from '@/types'

interface ProximityCardProps {
  currentEntry: LedgerEntry | null
  userId: string
}

export function ProximityCard({ currentEntry, userId }: ProximityCardProps) {
  const { position, error, startWatching, isWatching, hasGoodAccuracy } = useGeolocation()
  const [marking, setMarking] = useState(false)
  const [markResult, setMarkResult] = useState<'success' | 'fail' | null>(null)
  const [pendingCount, setPendingCount] = useState(0)
  const [online, setOnline] = useState(typeof navigator !== 'undefined' ? navigator.onLine : true)

  useEffect(() => {
    const handleOnline = () => setOnline(true)
    const handleOffline = () => setOnline(false)
    window.addEventListener('online', handleOnline)
    window.addEventListener('offline', handleOffline)
    return () => { window.removeEventListener('online', handleOnline); window.removeEventListener('offline', handleOffline) }
  }, [])

  useEffect(() => {
    getPendingCount().then(setPendingCount)
  }, [marking])

  // Page-side drain of the offline queue, on load and whenever the network
  // comes back. Covers browsers without Background Sync (Safari, Firefox).
  useEffect(() => {
    if (!online) return
    flushAttendanceQueue().then(() => getPendingCount().then(setPendingCount))
  }, [online])

  const markPresence = async () => {
    if (!currentEntry) return
    setMarking(true)
    setMarkResult(null)

    const payload = {
      ledger_instance_id: currentEntry.id,
      member_id: userId,
      marking_status: 'PRESENT',
      user_lat: position?.lat,
      user_lon: position?.lon,
      user_alt: position?.alt,
    }

    try {
      if (!online) {
        const token = getToken() || ''
        await queueAttendanceMark(token, payload)
        setMarkResult('success')
      } else {
        await attendanceApi.markAttendance(payload)
        setMarkResult('success')
      }
    } catch {
      setMarkResult('fail')
    } finally {
      setMarking(false)
    }
  }

  if (!currentEntry) {
    return (
      <div className="glass-card p-8 text-center">
        <MapPin className="w-10 h-10 text-chronos-muted/40 mx-auto mb-3" />
        <p className="text-sm text-chronos-muted">No active class right now.</p>
        <p className="text-xs text-chronos-muted mt-1">Attendance marking is available during class hours.</p>
      </div>
    )
  }

  const canMark = position && hasGoodAccuracy

  return (
    <div className="space-y-4">
      {/* Offline queue badge */}
      {pendingCount > 0 && (
        <div className="bg-chronos-warning/10 border border-chronos-warning/20 rounded-xl p-3 flex items-center gap-2 text-xs text-chronos-warning">
          <Wifi className="w-4 h-4" />
          {pendingCount} attendance mark(s) queued offline, will sync when connected
        </div>
      )}

      {/* Active class card */}
      <div className={`glass-card p-6 border-l-4 ${currentEntry.operational_state === 'ON_LEAVE' ? 'border-l-chronos-danger' : 'border-l-chronos-teal'}`}>
        <p className="section-title mb-3">Active Class</p>
        <h3 className="text-lg font-bold text-chronos-text">{currentEntry.activity_code}</h3>
        <p className="text-sm text-chronos-text-dim">{currentEntry.activity_title}</p>
        <p className="text-xs text-chronos-muted mt-1">
          Room {currentEntry.target_room_identifier} · {currentEntry.time_window_start} – {currentEntry.time_window_end}
        </p>
      </div>

      {/* GPS Status */}
      <div className="glass-card p-4">
        <div className="flex items-center justify-between mb-3">
          <p className="section-title">Location Verification</p>
          <button
            onClick={startWatching}
            disabled={isWatching}
            className="text-xs text-chronos-teal hover:underline flex items-center gap-1"
          >
            <Navigation className="w-3.5 h-3.5" />
            {isWatching ? 'Watching...' : 'Enable GPS'}
          </button>
        </div>

        {error ? (
          <div className="flex items-center gap-2 text-xs text-chronos-warning">
            <AlertCircle className="w-4 h-4 shrink-0" />
            {error}: BSSID Wi-Fi fallback will be used
          </div>
        ) : position ? (
          <div className="space-y-1.5 text-xs text-chronos-text-dim">
            <div className="flex items-center gap-1.5">
              <span className={`w-1.5 h-1.5 rounded-full ${hasGoodAccuracy ? 'bg-chronos-emerald' : 'bg-chronos-warning'} animate-pulse`} />
              Accuracy: {position.accuracy.toFixed(0)}m {hasGoodAccuracy ? '(Good)' : '(Poor: BSSID fallback active)'}
            </div>
            <p className="font-mono text-[10px] text-chronos-muted">
              {position.lat.toFixed(6)}, {position.lon.toFixed(6)}
              {position.alt !== null && ` · Alt ${position.alt.toFixed(1)}m`}
            </p>
          </div>
        ) : (
          <p className="text-xs text-chronos-muted">GPS not yet acquired. Enable location to mark attendance.</p>
        )}
      </div>

      {/* Mark Presence Button */}
      <motion.div>
        <AnimatePresence mode="wait">
          {markResult === 'success' ? (
            <motion.div
              key="success"
              initial={{ scale: 0.9, opacity: 0 }}
              animate={{ scale: 1, opacity: 1 }}
              className="glass-card p-5 text-center border border-chronos-emerald/30"
            >
              <CheckCircle2 className="w-12 h-12 text-chronos-emerald mx-auto mb-2" />
              <p className="font-semibold text-chronos-emerald">
                {!online ? 'Queued for Sync' : 'Attendance Marked!'}
              </p>
              <p className="text-xs text-chronos-text-dim mt-1">
                {!online ? 'Will be submitted when connectivity is restored' : 'Your presence has been recorded'}
              </p>
              <button onClick={() => setMarkResult(null)} className="mt-3 text-xs text-chronos-muted hover:text-chronos-text">
                Mark Again
              </button>
            </motion.div>
          ) : markResult === 'fail' ? (
            <motion.div
              key="fail"
              initial={{ scale: 0.9, opacity: 0 }}
              animate={{ scale: 1, opacity: 1 }}
              className="glass-card p-5 text-center border border-chronos-danger/30"
            >
              <AlertCircle className="w-12 h-12 text-chronos-danger mx-auto mb-2" />
              <p className="font-semibold text-chronos-danger">Location Mismatch</p>
              <p className="text-xs text-chronos-text-dim mt-1">You appear to be outside the class geofence boundary.</p>
              <button onClick={() => setMarkResult(null)} className="mt-3 text-xs text-chronos-muted hover:text-chronos-text">
                Try Again
              </button>
            </motion.div>
          ) : (
            <motion.button
              key="button"
              onClick={markPresence}
              disabled={marking || currentEntry.operational_state === 'ON_LEAVE'}
              whileTap={{ scale: 0.97 }}
              className={`w-full py-5 rounded-2xl text-base font-bold transition-all duration-300 flex items-center justify-center gap-3 ${
                currentEntry.operational_state === 'ON_LEAVE'
                  ? 'bg-chronos-surface border border-chronos-border text-chronos-muted cursor-not-allowed'
                  : canMark
                  ? 'bg-gradient-to-r from-chronos-teal to-chronos-emerald text-chronos-dark shadow-teal-strong animate-pulse-teal hover:shadow-teal-strong'
                  : 'bg-chronos-surface border border-chronos-border text-chronos-muted'
              }`}
            >
              {marking ? (
                <Loader2 className="w-6 h-6 animate-spin" />
              ) : (
                <MapPin className="w-6 h-6" />
              )}
              {currentEntry.operational_state === 'ON_LEAVE'
                ? 'Class Cancelled: Staff Absent'
                : marking
                ? 'Verifying Location...'
                : canMark
                ? 'Mark My Presence'
                : 'Enable GPS to Mark Attendance'}
            </motion.button>
          )}
        </AnimatePresence>
      </motion.div>
    </div>
  )
}
