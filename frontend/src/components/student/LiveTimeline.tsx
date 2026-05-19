'use client'
// Copyright 2026 Chronos Ledger Contributors
// Licensed under the Apache License, Version 2.0

import { useMemo } from 'react'
import { motion } from 'framer-motion'
import { BookOpen, Video, Clock, MapPin, ExternalLink } from 'lucide-react'
import { DynamicStateBadge } from '@/components/ui/Badge'
import type { LedgerEntry } from '@/types'

interface LiveTimelineProps {
  entries: LedgerEntry[]
  userId: string
}

export function LiveTimeline({ entries, userId }: LiveTimelineProps) {
  const now = new Date()
  const currentTime = `${now.getHours().toString().padStart(2, '0')}:${now.getMinutes().toString().padStart(2, '0')}`

  const sorted = useMemo(
    () => [...entries].sort((a, b) => (a.time_window_start || '').localeCompare(b.time_window_start || '')),
    [entries]
  )

  if (sorted.length === 0) {
    return (
      <div className="glass-card p-8 text-center">
        <BookOpen className="w-10 h-10 text-chronos-muted/40 mx-auto mb-3" />
        <p className="text-chronos-muted">No classes scheduled for today.</p>
      </div>
    )
  }

  return (
    <div className="space-y-3">
      {sorted.map((entry, idx) => {
        const isActive =
          entry.time_window_start &&
          entry.time_window_end &&
          entry.time_window_start <= currentTime &&
          entry.time_window_end >= currentTime
        const isPast = entry.time_window_end && entry.time_window_end < currentTime

        return (
          <motion.div
            key={entry.id}
            initial={{ opacity: 0, x: -12 }}
            animate={{ opacity: 1, x: 0 }}
            transition={{ delay: idx * 0.05 }}
            className={`glass-card p-4 border-l-4 transition-all ${
              isActive
                ? 'border-l-chronos-teal shadow-teal-glow'
                : isPast
                ? 'border-l-chronos-border/30 opacity-60'
                : 'border-l-chronos-border/50'
            }`}
          >
            {isActive && (
              <div className="flex items-center gap-1.5 text-xs text-chronos-teal font-semibold mb-2">
                <span className="w-1.5 h-1.5 rounded-full bg-chronos-teal animate-pulse" />
                NOW IN SESSION
              </div>
            )}

            <div className="flex items-start justify-between gap-3">
              <div className="flex-1 min-w-0">
                <div className="flex items-center gap-2 mb-1">
                  {entry.delivery_format === 'ONLINE_STREAM' ? (
                    <Video className="w-4 h-4 text-chronos-accent shrink-0" />
                  ) : (
                    <BookOpen className="w-4 h-4 text-chronos-teal shrink-0" />
                  )}
                  <span className="font-semibold text-chronos-text text-sm">
                    {entry.course_code} — {entry.course_title}
                  </span>
                </div>

                <div className="flex items-center gap-4 text-xs text-chronos-text-dim mt-1.5">
                  <span className="flex items-center gap-1">
                    <Clock className="w-3.5 h-3.5" />
                    {entry.time_window_start} – {entry.time_window_end}
                  </span>
                  <span className="flex items-center gap-1">
                    <MapPin className="w-3.5 h-3.5" />
                    {entry.delivery_format === 'ONLINE_STREAM' ? 'Online' : `Room ${entry.target_room_identifier}`}
                  </span>
                </div>

                {entry.delivery_format === 'ONLINE_STREAM' && entry.virtual_connection_string && (
                  <a
                    href={entry.virtual_connection_string}
                    target="_blank"
                    rel="noopener noreferrer"
                    className="inline-flex items-center gap-1 mt-2 text-xs text-chronos-accent hover:underline"
                  >
                    <ExternalLink className="w-3.5 h-3.5" />
                    Join Online Class
                  </a>
                )}
              </div>

              <DynamicStateBadge state={entry.operational_state} />
            </div>
          </motion.div>
        )
      })}

      <div className="text-center py-3">
        <a
          href={`/api/v1/sync/user-feed/${userId}.ics`}
          className="text-xs text-chronos-teal hover:underline flex items-center gap-1.5 justify-center"
          target="_blank"
          rel="noopener noreferrer"
        >
          <ExternalLink className="w-3.5 h-3.5" />
          Subscribe to Calendar (iCal)
        </a>
      </div>
    </div>
  )
}
