// Copyright 2026 Chronos Ledger Contributors
// Licensed under the Apache License, Version 2.0
//
// Caches today's schedule in IndexedDB and schedules local browser notifications
// for upcoming classes. Notifications fire even when the network is down because
// they are driven by cached data and JS timers (while the page is open) or the
// service worker periodic sync (when the page is closed).

import { useEffect, useRef } from 'react'
import type { LedgerEntry } from '@/types'
import { cacheSchedule, markClassNotified, wasClassNotified } from '@/lib/indexeddb'
import { getStoredUser } from '@/lib/auth'

const NOTIFY_BEFORE_MS = 15 * 60 * 1000 // fire 15 min before class start

function parseTimeToday(timeStr: string): Date | null {
  if (!timeStr) return null
  const [h, m] = timeStr.split(':').map(Number)
  if (isNaN(h) || isNaN(m)) return null
  const d = new Date()
  d.setHours(h, m, 0, 0)
  return d
}

export function useScheduleNotifications(entries: LedgerEntry[]) {
  const timerIds = useRef<ReturnType<typeof setTimeout>[]>([])
  const permissionRequested = useRef(false)

  // Request notification permission once
  useEffect(() => {
    if (permissionRequested.current) return
    if (typeof Notification === 'undefined') return
    if (Notification.permission === 'default') {
      Notification.requestPermission()
    }
    permissionRequested.current = true
  }, [])

  useEffect(() => {
    if (!entries.length) return

    const user = getStoredUser()
    if (!user) return

    // Persist schedule for service worker periodic sync
    cacheSchedule(user.user_id, entries).catch(() => {})

    // Notify the service worker about the new schedule
    if ('serviceWorker' in navigator && navigator.serviceWorker.controller) {
      navigator.serviceWorker.controller.postMessage({
        type: 'SCHEDULE_UPDATE',
        userId: user.user_id,
        entries: entries.map((e) => ({
          id: e.id,
          activity_code: e.activity_code,
          activity_title: e.activity_title,
          target_room_identifier: e.target_room_identifier,
          time_window_start: e.time_window_start,
          operational_state: e.operational_state,
          delivery_format: e.delivery_format,
        })),
      })
    }

    // Cancel existing timers before scheduling new ones
    timerIds.current.forEach(clearTimeout)
    timerIds.current = []

    if (typeof Notification === 'undefined' || Notification.permission !== 'granted') return

    const today = new Date().toISOString().split('T')[0]
    const now = Date.now()

    entries.forEach((entry) => {
      if (!entry.time_window_start) return
      if (entry.operational_state === 'ON_LEAVE') return

      const classStart = parseTimeToday(entry.time_window_start)
      if (!classStart) return

      const fireAt = classStart.getTime() - NOTIFY_BEFORE_MS
      if (fireAt <= now) return // already past the notification window

      const delay = fireAt - now

      const timerId = setTimeout(async () => {
        const alreadyNotified = await wasClassNotified(entry.id, today).catch(() => false)
        if (alreadyNotified) return

        const title = entry.operational_state === 'PROXY_SUBSTITUTE'
          ? `Proxy Alert: ${entry.activity_code}`
          : `Class starting soon: ${entry.activity_code}`

        const body = [
          entry.activity_title,
          `Room ${entry.target_room_identifier}`,
          `Starts at ${entry.time_window_start}`,
          entry.delivery_format === 'ONLINE_STREAM' ? '(Online)' : '',
        ].filter(Boolean).join(' · ')

        new Notification(title, {
          body,
          icon: '/icons/icon-192x192.png',
          badge: '/icons/icon-72x72.png',
          tag: `class-${entry.id}`,
          requireInteraction: false,
        })

        markClassNotified(entry.id, today).catch(() => {})
      }, delay)

      timerIds.current.push(timerId)
    })

    return () => {
      timerIds.current.forEach(clearTimeout)
    }
  }, [entries])
}
