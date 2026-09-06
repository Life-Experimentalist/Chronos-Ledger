// Copyright 2026 Chronos Ledger Contributors
// Licensed under the Apache License, Version 2.0

import { openDB, DBSchema, IDBPDatabase } from 'idb'
import type { LedgerEntry } from '@/types'

interface ChronosOfflineDB extends DBSchema {
  'attendance-queue': {
    key: number
    value: {
      id?: number
      token: string
      payload: object
      queued_at: string
    }
    indexes: { by_date: string }
  }
  // Cached today's schedule so it survives page reload + offline
  'schedule-cache': {
    key: string          // userId
    value: {
      user_id: string
      cached_at: string
      entries: LedgerEntry[]
    }
  }
  // Tracks which notification timers we've already scheduled (avoids duplicates)
  'notified-classes': {
    key: string          // `${date}_${ledger_id}`
    value: { key: string; notified_at: string }
  }
}

let db: IDBPDatabase<ChronosOfflineDB> | null = null

async function getDb(): Promise<IDBPDatabase<ChronosOfflineDB>> {
  if (!db) {
    db = await openDB<ChronosOfflineDB>('chronos-offline', 2, {
      upgrade(database, oldVersion) {
        // v1 schema
        if (oldVersion < 1) {
          const aq = database.createObjectStore('attendance-queue', {
            keyPath: 'id',
            autoIncrement: true,
          })
          aq.createIndex('by_date', 'queued_at')
        }
        // v2 additions
        if (oldVersion < 2) {
          database.createObjectStore('schedule-cache', { keyPath: 'user_id' })
          database.createObjectStore('notified-classes', { keyPath: 'key' })
        }
      },
    })
  }
  return db
}

// ── Attendance queue ─────────────────────────────────────────────────────────

export async function queueAttendanceMark(token: string, payload: object): Promise<void> {
  const database = await getDb()
  await database.add('attendance-queue', { token, payload, queued_at: new Date().toISOString() })

  if ('serviceWorker' in navigator && 'SyncManager' in window) {
    const registration = await navigator.serviceWorker.ready
    // @ts-ignore — SyncManager may not be in TS types for all targets
    await registration.sync.register('attendance-sync')
  }
}

export async function getPendingAttendanceQueue(): Promise<Array<{ id?: number; payload: object; token: string; queued_at: string }>> {
  const database = await getDb()
  return database.getAll('attendance-queue')
}

export async function clearQueueItem(id: number): Promise<void> {
  const database = await getDb()
  await database.delete('attendance-queue', id)
}

export async function getPendingCount(): Promise<number> {
  const database = await getDb()
  return database.count('attendance-queue')
}

const API_BASE = process.env.NEXT_PUBLIC_API_URL || 'http://localhost/api/v1'

// Drains the offline queue from the page itself. Safari and Firefox have no
// Background Sync, so without this the queue would sit in IndexedDB forever
// on those browsers. The mark endpoint upserts, so a double flush alongside
// the service worker's own sync handler is harmless.
export async function flushAttendanceQueue(): Promise<number> {
  const pending = await getPendingAttendanceQueue()
  let flushed = 0
  for (const record of pending) {
    try {
      const res = await fetch(`${API_BASE}/attendance/mark`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json', Authorization: `Bearer ${record.token}` },
        body: JSON.stringify(record.payload),
      })
      // A 4xx is a final verdict (expired token, deleted ledger): retrying
      // will never succeed, so the record is dropped either way. Only a
      // network failure or a 5xx keeps it for the next attempt.
      if (res.status < 500) {
        if (record.id !== undefined) await clearQueueItem(record.id)
        if (res.ok) flushed += 1
      }
    } catch {
      // Still offline or the server is unreachable: keep the record.
    }
  }
  return flushed
}

// ── Schedule cache ───────────────────────────────────────────────────────────

export async function cacheSchedule(userId: string, entries: LedgerEntry[]): Promise<void> {
  const database = await getDb()
  await database.put('schedule-cache', {
    user_id: userId,
    cached_at: new Date().toISOString(),
    entries,
  })
}

export async function getCachedSchedule(userId: string): Promise<LedgerEntry[] | null> {
  const database = await getDb()
  const record = await database.get('schedule-cache', userId)
  if (!record) return null
  // Invalidate cache if older than 12 hours
  const age = Date.now() - new Date(record.cached_at).getTime()
  if (age > 12 * 60 * 60 * 1000) return null
  return record.entries
}

// ── Notification deduplication ───────────────────────────────────────────────

export async function markClassNotified(ledgerId: number, date: string): Promise<void> {
  const database = await getDb()
  const key = `${date}_${ledgerId}`
  await database.put('notified-classes', { key, notified_at: new Date().toISOString() })
}

export async function wasClassNotified(ledgerId: number, date: string): Promise<boolean> {
  const database = await getDb()
  const record = await database.get('notified-classes', `${date}_${ledgerId}`)
  return !!record
}
